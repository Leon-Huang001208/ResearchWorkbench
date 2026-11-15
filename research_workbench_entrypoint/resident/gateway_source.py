"""Prepare local gateway source and rehome an offline, cloud-linked installation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import plistlib
import re
import stat
import subprocess
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from . import gateway_upgrade
from .admission import file_lock
from .controller import LABEL as NATIVE_LABEL
from .controller import atomic, sync_directory
from .evidence import SHA, UpdateBlocked, run

log = logging.getLogger(__name__)
_RECORD_LIMIT = 64 * 1024
_JOURNAL = "gateway-source-rehome.json"
_DATALESS = getattr(stat, "SF_DATALESS", 0x40000000)


def _cloud(path: Path) -> bool:
    user = Path.home()
    cloud_roots = (
        user / "Desktop",
        user / "Documents",
        user / "Dropbox",
        user / "Google Drive",
        user / "OneDrive",
        user / "Library/CloudStorage",
        user / "Library/Mobile Documents",
    )
    folded = Path(str(path).casefold())
    return any(folded.is_relative_to(Path(str(root).casefold())) for root in cloud_roots)


def _safe_path(path: Path, *, local: bool = True) -> None:
    if not path.is_absolute() or ".." in path.parts or str(path).startswith("//"):
        raise UpdateBlocked("gateway_source_path_unsafe")
    if local and _cloud(path):
        raise UpdateBlocked("gateway_source_cloud_path")


def _present(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def _directory(path: Path, *, private: bool = False, local: bool = True) -> os.stat_result:
    _safe_path(path, local=local)
    try:
        for item in (*reversed(path.parents), path):
            info = item.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise UpdateBlocked("gateway_source_path_unsafe")
            if getattr(info, "st_flags", 0) & _DATALESS:
                raise UpdateBlocked("gateway_source_dataless")
        if info.st_uid != os.getuid() or info.st_mode & (0o077 if private else 0o022):
            raise UpdateBlocked("gateway_source_path_unsafe")
        return info
    except OSError as exc:
        raise UpdateBlocked("gateway_source_path_unavailable") from exc


def _file_fact(path: Path, *, private: bool = False) -> os.stat_result:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & (0o077 if private else 0o022)
        or (private and info.st_nlink != 1)
    ):
        raise UpdateBlocked("gateway_source_record_unsafe")
    if getattr(info, "st_flags", 0) & _DATALESS:
        raise UpdateBlocked("gateway_source_dataless")
    return info


def _raw(path: Path, *, private: bool = True, limit: int = _RECORD_LIMIT) -> bytes:
    try:
        original = _file_fact(path, private=private)
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if _stamp(original) != _stamp(opened) or not 0 < opened.st_size <= limit:
                raise UpdateBlocked("gateway_source_record_unsafe")
            value = stream.read(limit + 1)
            if (
                len(value) != opened.st_size
                or _stamp(opened) != _stamp(os.fstat(stream.fileno()))
                or _stamp(opened) != _stamp(_file_fact(path, private=private))
            ):
                raise UpdateBlocked("gateway_source_record_changed")
        return value
    except OSError as exc:
        raise UpdateBlocked("gateway_source_record_unavailable") from exc


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _json(raw: bytes) -> dict:
    def unique(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError("duplicate key")
        return value

    try:
        value = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise TypeError("expected object")
        return value
    except (ValueError, TypeError, RecursionError) as exc:
        raise UpdateBlocked("gateway_source_record_invalid") from exc


def _encode(value: dict) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise UpdateBlocked("gateway_source_record_invalid") from exc


def _path(value: object) -> Path:
    if not isinstance(value, str):
        raise UpdateBlocked("gateway_source_path_unsafe")
    path = Path(value)
    if str(path) != value:
        raise UpdateBlocked("gateway_source_path_unsafe")
    return path


def _revision(value: object) -> None:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise UpdateBlocked("gateway_source_revision_invalid")


def _git(*args: str, timeout: int = 15) -> str:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(
            [
                "/usr/bin/git",
                "--no-optional-locks",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-c",
                "core.fsmonitor=false",
                *args,
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode or len(result.stdout) > 1024 * 1024:
            raise UpdateBlocked("gateway_source_git_unverified")
        return result.stdout.strip()
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise UpdateBlocked("gateway_source_git_unverified") from exc


def _git_pointer(path: Path) -> Path:
    try:
        text = _raw(path, private=False, limit=4096).decode("utf-8").strip()
        if not text.startswith("gitdir: ") or "\n" in text:
            raise ValueError("invalid pointer")
        target = _path(text.removeprefix("gitdir: "))
        _safe_path(target, local=False)
        return target
    except (ValueError, UnicodeError) as exc:
        raise UpdateBlocked("gateway_source_git_unverified") from exc


def _git_config(*arguments: str, cwd: Path | None = None) -> dict[str, str]:
    location = ("-C", str(cwd)) if cwd is not None else ()
    entries = {}
    for record in _git(*location, "config", "--no-includes", "--null", "--list", *arguments).split(
        "\0"
    ):
        key, _, value = record.partition("\n")
        if key.startswith(("include.", "includeif.")):
            raise UpdateBlocked("gateway_source_git_config_include")
        if (
            key in {"core.worktree", "extensions.partialclone"}
            or key.startswith("remote.")
            and key.endswith(".promisor")
        ):
            raise UpdateBlocked("gateway_source_external_objects")
        if key:
            entries[key] = value
    return entries


def _head_metadata(head: Path, common: Path) -> None:
    raw = _raw(head, private=False, limit=4096)
    if not raw.startswith(b"ref: "):
        return
    reference = Path(os.fsdecode(raw.removeprefix(b"ref: ").strip()))
    if not reference.parts or reference.parts[0] != "refs" or ".." in reference.parts:
        raise UpdateBlocked("gateway_source_git_unverified")
    loose = common / reference
    for parent in reversed(loose.parents):
        if parent != common and parent.is_relative_to(common) and _present(parent):
            _directory(parent)
    if _present(loose):
        _file_fact(loose)


def _common(common: Path, *, staging: bool = False) -> None:
    _directory(common)
    try:
        for name in ("HEAD", "config"):
            _file_fact(common / name)
        _head_metadata(common / "HEAD", common)
        settings = _git_config(cwd=Path("/"))
        settings.update(_git_config("--file", str(common / "config")))
        for name in ("packed-refs", "shallow"):
            if _present(common / name):
                _file_fact(common / name)
        objects = common / "objects"
        _directory(objects)
        if _present(objects / "info"):
            _directory(objects / "info")
            if any(_present(objects / "info" / name) for name in ("alternates", "http-alternates")):
                raise UpdateBlocked("gateway_source_external_objects")
        if _present(objects / "pack"):
            packs = objects / "pack"
            _directory(packs)
            for item in packs.iterdir():
                _file_fact(item)
                if item.suffix == ".promisor":
                    raise UpdateBlocked("gateway_source_external_objects")
        for item in objects.iterdir():
            if re.fullmatch("[a-f0-9]{2}", item.name):
                _directory(item)
        if staging:
            hooks = settings.get("core.hookspath")
            hook_dir = Path(hooks).expanduser() if hooks else common / "hooks"
            if hook_dir.is_absolute():
                _safe_path(hook_dir)
                if _present(hook_dir):
                    _directory(hook_dir)
                    post_checkout = hook_dir / "post-checkout"
                    if _present(post_checkout):
                        _file_fact(post_checkout)
            elif ".." in hook_dir.parts:
                raise UpdateBlocked("gateway_source_path_unsafe")
    except OSError as exc:
        raise UpdateBlocked("gateway_source_git_unverified") from exc


def verify_local_checkout(project: Path, common: Path | None, revision: str) -> None:
    """Check the real local Git metadata and exact clean checkout without changing it."""
    _revision(revision)
    _directory(project)
    metadata = project / ".git"
    try:
        if stat.S_ISDIR(metadata.lstat().st_mode):
            actual_common = metadata
            gitdir = metadata
        else:
            gitdir = _git_pointer(metadata)
            _directory(gitdir)
            if _raw(gitdir / "commondir", private=False, limit=4096).strip() != b"../..":
                raise UpdateBlocked("gateway_source_git_unverified")
            actual_common = gitdir.parent.parent
            if gitdir.parent != actual_common / "worktrees":
                raise UpdateBlocked("gateway_source_git_unverified")
            expected_pointer = _raw(gitdir / "gitdir", private=False, limit=4096).strip()
            if expected_pointer != os.fsencode(metadata):
                raise UpdateBlocked("gateway_source_git_unverified")
            _head_metadata(gitdir / "HEAD", actual_common)
        _file_fact(gitdir / "index")
        if _present(gitdir / "config.worktree"):
            _file_fact(gitdir / "config.worktree")
            _git_config("--file", str(gitdir / "config.worktree"))
        if common is not None and actual_common != common:
            raise UpdateBlocked("gateway_source_common_mismatch")
        _common(actual_common)
    except OSError as exc:
        raise UpdateBlocked("gateway_source_git_unverified") from exc
    at = ("-C", str(project))
    if _git(*at, "rev-parse", "--path-format=absolute", "--git-common-dir") != str(
        actual_common
    ) or _git(*at, "rev-parse", "--show-toplevel") != str(project):
        raise UpdateBlocked("gateway_source_common_mismatch")
    if _git(*at, "rev-parse", "--verify", "HEAD") != revision:
        raise UpdateBlocked("gateway_source_revision_mismatch")
    if _git(*at, "status", "--porcelain=v1", "--untracked-files=all"):
        raise UpdateBlocked("gateway_source_checkout_dirty")


def _home(home: Path) -> None:
    if home != Path.home() / ".research-workbench":
        raise UpdateBlocked("gateway_source_home_unsafe")
    _directory(home, private=True)
    _directory(home / "resident", private=True)


def _release_path(release: Path) -> None:
    _safe_path(release)
    user = Path.home()
    roots = (user / "Developer", user / ".local/share/research-workbench/server-releases")
    if not any(release != root and release.is_relative_to(root) for root in roots):
        raise UpdateBlocked("gateway_source_release_path_unsafe")
    _directory(release.parent)


def _resident_common(home: Path, *, staging: bool = False) -> tuple[dict, Path]:
    native = _json(_raw(home / "resident/config.json"))
    common = _path(native.get("source_common"))
    _common(common, staging=staging)
    return native, common


def _verify_detached(release: Path, common: Path, revision: str) -> None:
    verify_local_checkout(release, common, revision)
    if _git("-C", str(release), "rev-parse", "--abbrev-ref", "HEAD") != "HEAD":
        raise UpdateBlocked("gateway_source_release_not_detached")


def prepare(home: Path, release: Path, revision: str) -> dict:
    """Prepare a detached release using the configured local common and exact object."""
    _home(home)
    _release_path(release)
    _revision(revision)
    _, common = _resident_common(home, staging=True)
    if (
        _git("--git-dir", str(common), "rev-parse", "--verify", f"{revision}^{{commit}}")
        != revision
    ):
        raise UpdateBlocked("gateway_source_revision_invalid")
    if not _present(release):
        _git(
            "--git-dir",
            str(common),
            "worktree",
            "add",
            "--detach",
            str(release),
            revision,
            timeout=120,
        )
    _verify_detached(release, common, revision)
    return {"status": "prepared", "project": str(release), "revision": revision}


def _locations(home: Path) -> tuple[Path, Path, Path]:
    _home(home)
    _directory(home / "server", private=True)
    run = home / "server/run"
    _directory(run, private=True)
    agents = Path.home() / "Library/LaunchAgents"
    _directory(agents)
    return home / "server/resident.json", agents / f"{gateway_upgrade.LABEL}.plist", run


def _pending(home: Path, run: Path, *, include_self: bool) -> None:
    paths = [
        home / "resident/transaction.json",
        run / "gateway-upgrade.json",
        run / "cutover.json",
        run / "birth-fence.json",
    ]
    if include_self:
        paths.append(run / _JOURNAL)
    if any(_present(path) for path in paths):
        raise UpdateBlocked("gateway_source_maintenance_pending")


def _require_offline(home: Path) -> None:
    _require_paused_jobs()
    if gateway_upgrade.job_state() is not None or gateway_upgrade.listener_pids():
        raise UpdateBlocked("gateway_source_gateway_must_be_unloaded")
    gateway_upgrade.no_private_processes(home / "server")


def _require_paused_jobs() -> None:
    """Persistently inhibit the gateway and the original automatic deployment tick."""
    uid = os.getuid()
    domain = f"gui/{uid}"
    disabled = run(["/bin/launchctl", "print-disabled", domain], timeout=5)
    for label in (gateway_upgrade.LABEL, NATIVE_LABEL):
        rows = re.findall(
            rf'^\s*"{re.escape(label)}"\s*=>\s*(\w+)\s*,?$', disabled, flags=re.MULTILINE
        )
        if rows not in (["disabled"], ["true"]):
            raise UpdateBlocked("gateway_source_launchagents_must_be_disabled")
    try:
        native = subprocess.run(
            ["/bin/launchctl", "print", f"{domain}/{NATIVE_LABEL}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateBlocked("gateway_source_native_job_unverified") from exc
    if native.returncode == 0:
        raise UpdateBlocked("gateway_source_native_job_must_be_unloaded")
    if native.returncode != 113 or native.stderr != (
        f'Bad request.\nCould not find service "{NATIVE_LABEL}" in domain for user gui: {uid}\n'
    ):
        raise UpdateBlocked("gateway_source_native_job_unverified")


def _plans(home: Path, release: Path, revision: str, config_raw: bytes, plist_raw: bytes) -> dict:
    _revision(revision)
    _release_path(release)
    native, common = _resident_common(home)
    config = _json(config_raw)
    old = _path(config.get("project"))
    if old == release:
        raise UpdateBlocked("gateway_source_already_local")
    # Only inspect the old worktree's exact, local pointer file. Opening the
    # cloud registration or invoking Git there can hydrate or hang on metadata.
    _directory(old, local=False)
    if not _cloud(old) and not _cloud(_git_pointer(old / ".git")):
        raise UpdateBlocked("gateway_source_legacy_cloud_link_required")
    manifest_path = home / "install/manifest.json"
    _directory(manifest_path.parent, private=True)
    manifest = _json(_raw(manifest_path))
    binding = config.get("binding")
    if (
        type(config.get("version")) is not int
        or config["version"] != 1
        or type(config.get("port")) is not int
        or config["port"] != 8089
        or config.get("revision") != revision
        or not isinstance(binding, dict)
        or binding.get("home") != str(home)
        or binding.get("project") != native.get("project")
        or binding.get("web_port") != native.get("web_port")
        or binding.get("runtime_port") != native.get("runtime_port")
        or config.get("node") != native.get("node")
        or config.get("origin") != native.get("private_origin")
        or manifest.get("status") != "installed"
        or manifest.get("code_commit") != binding.get("revision")
    ):
        raise UpdateBlocked("gateway_source_binding_unverified")
    _revision(binding.get("revision"))
    plan = _record_plan(home, release, revision, config_raw, plist_raw)
    _verify_detached(release, common, revision)
    return plan


def _record_plan(
    home: Path, release: Path, revision: str, config_raw: bytes, plist_raw: bytes
) -> dict:
    """Check the bounded config/plist pair independently of either checkout."""
    _revision(revision)
    _safe_path(release)
    config = _json(config_raw)
    old = _path(config.get("project"))
    _safe_path(old, local=False)
    binding = config.get("binding")
    if (
        old == release
        or config.get("revision") != revision
        or config.get("port") != 8089
        or not isinstance(binding, dict)
        or binding.get("home") != str(home)
    ):
        raise UpdateBlocked("gateway_source_record_invalid")
    try:
        plist = plistlib.loads(plist_raw)
        primary = _path(binding["project"])
        _safe_path(primary)
        arguments = [
            str(primary / ".venv/bin/python"),
            "-m",
            "app.research_web.multiuser.resident",
            "--root",
            str(home / "server"),
        ]
        if (
            not isinstance(plist, dict)
            or plist.get("Label") != gateway_upgrade.LABEL
            or plist.get("WorkingDirectory") != str(old)
            or plist.get("ProgramArguments") != arguments
            or plist.get("KeepAlive") is not True
            or plist.get("RunAtLoad") is not True
        ):
            raise ValueError("wrong launch job")
        updated_plist = plistlib.dumps({**plist, "WorkingDirectory": str(release)})
    except (KeyError, ValueError, TypeError) as exc:
        raise UpdateBlocked("gateway_source_job_unverified") from exc
    return {
        "project": str(release),
        "previous_project": str(old),
        "revision": revision,
        "before": [config_raw.hex(), plist_raw.hex()],
        "after": [_encode({**config, "project": str(release)}).hex(), updated_plist.hex()],
    }


def _seal(plan: dict) -> str:
    return hashlib.sha256(_encode(plan)).hexdigest()


def _public(plan: dict) -> dict:
    return {key: plan[key] for key in ("project", "previous_project", "revision")}


def plan_rehome(home: Path, release: Path, revision: str) -> dict:
    """Preview the exact config and plist changes without writing, or starting a job."""
    config, plist, run = _locations(home)
    _pending(home, run, include_self=True)
    _require_offline(home)
    plan = _plans(home, release, revision, _raw(config), _raw(plist))
    return {"status": "planned", **_public(plan), "seal": _seal(plan)}


@contextmanager
def _locked(home: Path, run: Path):
    with ExitStack() as stack:
        stack.enter_context(file_lock(home / "resident", "supervisor.lock", exclusive=True))
        stack.enter_context(file_lock(home / "resident", "admission.lock", exclusive=True))
        stack.enter_context(file_lock(run, "operator.lock", exclusive=True))
        yield


def _replace(path: Path, value: bytes) -> None:
    # Stage on the same filesystem; replacement is one atomic rename.
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".gateway-source-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _finish(run: Path, transaction: str, plan: dict, status: str) -> dict:
    receipt = run / f"gateway-source-rehome-{transaction}.json"
    evidence = {"version": 1, "transaction": transaction, "plan": plan, "status": status}
    if _present(receipt):
        if _json(_raw(receipt, limit=1024 * 1024)) != evidence:
            raise UpdateBlocked("gateway_source_receipt_changed")
    else:
        atomic(receipt, evidence)
    (run / _JOURNAL).unlink()
    sync_directory(run)
    log.info("gateway_source_rehome_%s", status)
    return {"status": status, **_public(plan), "receipt": str(receipt)}


def _read_pair(plan: dict, state: str) -> tuple[bytes, bytes]:
    try:
        config, plist = plan[state]
        pair = bytes.fromhex(config), bytes.fromhex(plist)
        if not all(0 < len(raw) <= _RECORD_LIMIT for raw in pair):
            raise ValueError("record size")
        return pair
    except (KeyError, TypeError, ValueError) as exc:
        raise UpdateBlocked("gateway_source_journal_invalid") from exc


def rehome(home: Path, release: Path, revision: str, *, expected_seal: str) -> dict:
    """Atomically journal a same-SHA rehome for an already-unloaded gateway."""
    config, plist, run = _locations(home)
    with _locked(home, run):
        _pending(home, run, include_self=True)
        _require_offline(home)
        plan = _plans(home, release, revision, _raw(config), _raw(plist))
        if _seal(plan) != expected_seal:
            raise UpdateBlocked("gateway_source_plan_changed")
        before = _read_pair(plan, "before")
        after = _read_pair(plan, "after")
        transaction = str(uuid4())
        atomic(run / _JOURNAL, {"version": 1, "transaction": transaction, "plan": plan})
        try:
            _require_offline(home)
            if (_raw(config), _raw(plist)) != before:
                raise UpdateBlocked("gateway_source_record_changed")
            updated_config, updated_plist = after
            _replace(config, updated_config)
            _require_offline(home)
            _replace(plist, updated_plist)
            if (_raw(config), _raw(plist)) != (updated_config, updated_plist):
                raise UpdateBlocked("gateway_source_record_changed")
            return _finish(run, transaction, plan, "rehomed")
        except (OSError, UpdateBlocked) as exc:
            log.warning(
                "gateway_source_recovery_required", extra={"error_type": type(exc).__name__}
            )
            raise UpdateBlocked("gateway_source_recovery_required") from exc


def recover_rehome(home: Path) -> dict:
    """Restore original metadata after interruption, or finish a durable terminal receipt."""
    config, plist, run = _locations(home)
    with _locked(home, run):
        journal = run / _JOURNAL
        if not _present(journal):
            return {"status": "not_required"}
        _pending(home, run, include_self=False)
        _require_offline(home)
        state = _json(_raw(journal, limit=1024 * 1024))
        try:
            transaction, plan = state["transaction"], state["plan"]
            if state["version"] != 1 or str(UUID(transaction)) != transaction:
                raise ValueError("invalid transaction")
            before, after = _read_pair(plan, "before"), _read_pair(plan, "after")
            expected = _record_plan(
                home, _path(plan["project"]), plan["revision"], before[0], before[1]
            )
            if plan != expected:
                raise ValueError("invalid plan")
        except (KeyError, TypeError, ValueError) as exc:
            raise UpdateBlocked("gateway_source_journal_invalid") from exc
        current = _raw(config), _raw(plist)
        receipt = run / f"gateway-source-rehome-{transaction}.json"
        if _present(receipt):
            completed = _json(_raw(receipt, limit=1024 * 1024)).get("status")
            if completed == "rehomed" and current == after:
                return _finish(run, transaction, plan, completed)
            if completed == "rolled_back" and current == before:
                return _finish(run, transaction, plan, completed)
            raise UpdateBlocked("gateway_source_receipt_changed")
        for original, updated, actual in zip(before, after, current, strict=True):
            if actual not in (original, updated):
                raise UpdateBlocked("gateway_source_record_changed")
        for path, original, actual in zip((config, plist), before, current, strict=True):
            if original != actual:
                _require_offline(home)
                _replace(path, original)
        if (_raw(config), _raw(plist)) != before:
            raise UpdateBlocked("gateway_source_record_changed")
        return _finish(run, transaction, plan, "rolled_back")
