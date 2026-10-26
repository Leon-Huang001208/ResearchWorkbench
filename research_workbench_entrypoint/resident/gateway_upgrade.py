"""Explicit Mac gateway repair, with graceful drain and journaled rollback.

The primary is never stopped or installed here. Automatic compatibility, its
immutable controller, and its baseline are deliberately not changed.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.client
import inspect
import io
import json
import logging
import os
import plistlib
import re
import signal
import stat
import subprocess
import sys
import time
import zipfile
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from . import controller
from .admission import MaintenanceBusy, file_lock, private_root
from .controller import atomic, clean, configured, digest, git, sync_directory
from .evidence import SHA, GitHubEvidence, UpdateBlocked, read_json, run
from .gateway_fence import BirthFence

log = logging.getLogger(__name__)
LABEL = "com.research-workbench.multiuser-server"
RECOVERY = "com.research-workbench.gateway-recovery"
RECOVERY_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PRODUCT = "6c4ac79bcf03fb36ffbe9c1c40a647b8e8a34556"
JOURNAL_MAX_BYTES = 16_000_000
CONTROL = {
    "app/research_web/multiuser/gateway.py",
    "app/research_web/multiuser/resident.py",
    "research_workbench_entrypoint/resident/gateway_fence.py",
    "research_workbench_entrypoint/resident/gateway_upgrade.py",
    ".github/workflows/research-web-checks.yml",
    ".github/workflows/research-web-bootstrap.yml",
    "outputs/research-web-architecture/index.html",
    "outputs/research-web-architecture/api-atlas.html",
}
TOOL_PATH = "research_workbench_entrypoint/resident/gateway_upgrade.py"
MODULE_ROOT = "research_workbench_entrypoint/resident/"
RECOVERY_MAIN = "from resident.gateway_upgrade import main\nraise SystemExit(main())\n"


def review(source: Path, target: str, primary: str):
    clean(source, target)
    if primary != PRODUCT or not SHA.fullmatch(target):
        raise UpdateBlocked("gateway_product_revision_unreviewed")
    git(source, "merge-base", "--is-ancestor", primary, target)
    paths = git(source, "diff", "--name-only", primary, target).splitlines()
    if any(
        path not in CONTROL and not path.startswith(("tests/", "docs/", ".ai/reports/"))
        for path in paths
    ):
        raise UpdateBlocked("gateway_upgrade_scope_changed")
    return {path: git(source, "rev-parse", f"{target}:{path}") for path in paths}


def static_scopes(source: Path, previous: str, payload: str, tool: str):
    """Keep reviewed operator changes outside the deployed product checkout."""
    if not all(
        isinstance(value, str) and SHA.fullmatch(value) for value in (previous, payload, tool)
    ):
        raise UpdateBlocked("gateway_static_revision_invalid")
    scopes = {}
    for name, start, end in (("payload", previous, payload), ("tool", payload, tool)):
        git(source, "merge-base", "--is-ancestor", start, end)
        paths = git(source, "diff", "--no-renames", "--name-only", start, end).splitlines()
        prefixes = ("docs/", "tests/", ".ai/reports/")
        if name == "payload":
            prefixes += ("app/research_web/ui/",)
        if name == "payload" and TOOL_PATH in paths:
            try:
                payload_blob = git(source, "rev-parse", f"{end}:{TOOL_PATH}")
                tool_blob = git(source, "rev-parse", f"{tool}:{TOOL_PATH}")
            except UpdateBlocked as exc:
                raise UpdateBlocked("gateway_static_scope_changed") from exc
            if payload_blob != tool_blob:
                raise UpdateBlocked("gateway_payload_tool_mismatch")
        if any(not path.startswith(prefixes) and path != TOOL_PATH for path in paths):
            raise UpdateBlocked("gateway_static_scope_changed")
        scopes[name] = {path: git(source, "rev-parse", f"{end}:{path}") for path in paths}
    return scopes


def preserved_primary_scopes(source: Path, primary: str, previous: str, payload: str, tool: str):
    """Prove both running baselines share the payload's runtime backend bytes."""
    if not all(
        isinstance(value, str) and SHA.fullmatch(value)
        for value in (primary, previous, payload, tool)
    ):
        raise UpdateBlocked("gateway_static_revision_invalid")
    scopes = {}
    for name, start, end in (
        ("primary", primary, payload),
        ("payload", previous, payload),
        ("tool", payload, tool),
    ):
        git(source, "merge-base", "--is-ancestor", start, end)
        paths = git(source, "diff", "--no-renames", "--name-only", start, end).splitlines()
        prefixes = ("docs/", "tests/", ".ai/reports/")
        if name != "tool":
            prefixes += ("app/research_web/ui/",)
        if any(not path.startswith(prefixes) and path != TOOL_PATH for path in paths):
            raise UpdateBlocked("gateway_static_scope_changed")
        scopes[name] = {path: git(source, "rev-parse", f"{end}:{path}") for path in paths}
        if (
            name != "tool"
            and TOOL_PATH in scopes[name]
            and scopes[name][TOOL_PATH] != git(source, "rev-parse", f"{tool}:{TOOL_PATH}")
        ):
            raise UpdateBlocked("gateway_static_operator_mismatch")
    log.info("gateway_preserved_primary_scope_verified")
    return scopes


def stage_primary_ui(home: Path, source: Path, previous: str, target: str):
    """Prepare a qualified UI wheel; the immutable resident owns deploy/recover."""
    if sys.platform != "darwin" or not all(SHA.fullmatch(v or "") for v in (previous, target)):
        raise UpdateBlocked("gateway_static_revision_invalid")
    root, config = configured(home)
    with file_lock(root, "supervisor.lock", exclusive=True):
        if (root / "transaction.json").exists() or (
            home / "server/run/gateway-upgrade.json"
        ).exists():
            raise UpdateBlocked("gateway_recovery_required")
        clean(source, target)
        if (
            source.resolve() != source
            or Path(__file__).resolve() != source / TOOL_PATH
            or git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")
            != config["source_common"]
        ):
            raise UpdateBlocked("gateway_source_identity_changed")
        project = Path(config["project"])
        if Path(sys.prefix).resolve() != (project / ".venv").resolve():
            raise UpdateBlocked("gateway_interpreter_unverified")
        quarantine = root / "quarantine.json"
        if quarantine.exists() and read_json(quarantine).get("sha") == target:
            raise UpdateBlocked("resident_failed_candidate_requires_retry")
        clean(project, previous)
        manifest = read_json(home / "install/manifest.json")
        if manifest.get("code_commit") != previous or manifest.get("status") != "installed":
            raise UpdateBlocked("resident_installation_mismatch")
        review = {
            "profile": "explicit-static-ui-v1",
            "previous": previous,
            "target": target,
            "scopes": static_scopes(source, previous, target, target),
            "controller_sha256": config["artifact_sha256"],
        }
        existing = (
            read_json(root / "candidate.json") if (root / "candidate.json").exists() else None
        )
        retired = read_json(root / "accepted.json") if (root / "accepted.json").exists() else None
        if (
            existing
            and existing != retired
            and (
                existing.get("previous") != previous
                or existing.get("target") != target
                or existing.get("compatibility_review") != review
            )
        ):
            raise UpdateBlocked("resident_candidate_conflict")
        github = GitHubEvidence(
            Path(config["gh"]), config["repository"], Path(config["source_common"])
        )
        if github.latest() != target:
            raise UpdateBlocked("resident_master_moved")
        proof = github.qualify(target)
        controller.environment(home, config)
        if controller.bridge(home, config, "ensure") != {"status": "ready", "sha": previous}:
            raise UpdateBlocked("resident_process_revision_mismatch")
        directory = root / "artifacts" / target
        private_root(directory)
        new = controller.build_wheel(project, source, directory / "new" / target)
        old = controller.build_wheel(project, project, directory / "old" / previous)
        clean(source, target)
        clean(project, previous)
        if read_json(home / "install/manifest.json") != manifest or configured(home)[1] != config:
            raise UpdateBlocked("resident_configuration_changed")
        if github.latest() != target:
            raise UpdateBlocked("resident_master_moved")
        proof = github.qualify(target)
        candidate = {
            "previous": previous,
            "target": target,
            "new_wheel": new,
            "old_wheel": old,
            "manifest": manifest,
            "proof": proof,
            "compatibility_review": review,
        }
        # Do not replace another staged transaction or a changed idempotent candidate.
        if existing and existing != retired and existing != candidate:
            raise UpdateBlocked("resident_candidate_conflict")
        current = read_json(root / "candidate.json") if (root / "candidate.json").exists() else None
        if current != existing:
            raise UpdateBlocked("resident_candidate_conflict")
        atomic(root / "candidate.json", candidate)
        log.info("primary_static_ui_staged")
        return {"status": "staged", "previous": previous, "target": target}


def module_blobs(source: Path, revision: str):
    rows = git(source, "ls-tree", "-r", revision, MODULE_ROOT).splitlines()
    modules = {}
    for row in rows:
        metadata, path = row.split("\t", 1)
        if not path.endswith(".py"):
            continue
        mode, kind, blob = metadata.split()
        name = path.removeprefix(MODULE_ROOT)
        if (
            not path.startswith(MODULE_ROOT)
            or mode not in {"100644", "100755"}
            or kind != "blob"
            or "/" in name
            or not SHA.fullmatch(blob)
        ):
            raise UpdateBlocked("gateway_recovery_module_invalid")
        modules[name] = blob
    if not {"__init__.py", "gateway_upgrade.py"}.issubset(modules):
        raise UpdateBlocked("gateway_recovery_module_missing")
    return modules


def git_bytes(source: Path, revision: str, name: str):
    try:
        result = subprocess.run(
            ["/usr/bin/git", "-C", str(source), "show", f"{revision}:{MODULE_ROOT}{name}"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateBlocked("gateway_recovery_object_unavailable") from exc
    if result.returncode or len(result.stdout) > 8_000_000:
        raise UpdateBlocked("gateway_recovery_object_unavailable")
    return result.stdout


def static_recovery_identity(home: Path, state: dict):
    preserved_primary = (
        state.get("version") == 3
        and state.get("mode") == "static-gateway"
        and state.get("primary") != state.get("target")
    )
    original_static = (
        state.get("version") == 2
        and state.get("mode") == "static-ui"
        and state.get("primary") == state.get("target")
    )
    if not (preserved_primary or original_static):
        raise UpdateBlocked("gateway_recovery_identity_changed")
    tool = state.get("tool_revision", "")
    project = Path(state["project"])
    if [project.stat().st_dev, project.stat().st_ino] != state.get("project_identity"):
        raise UpdateBlocked("gateway_source_identity_changed")
    _, resident = configured(home)
    if (
        git(project, "rev-parse", "--path-format=absolute", "--git-common-dir")
        != resident["source_common"]
    ):
        raise UpdateBlocked("gateway_source_identity_changed")
    scopes = (
        preserved_primary_scopes(
            project, state["primary"], state["previous"], state["target"], tool
        )
        if preserved_primary
        else static_scopes(project, state["previous"], state["target"], tool)
    )
    if scopes != state.get("reviewed"):
        raise UpdateBlocked("gateway_static_scope_changed")
    identity = state["recovery"]
    checksum = identity.get("artifact_sha256", "")
    if (
        not isinstance(checksum, str)
        or not re.fullmatch(r"[a-f0-9]{64}", checksum)
        or identity.get("tool_revision") != tool
    ):
        raise UpdateBlocked("gateway_recovery_identity_changed")
    artifact = home / "server/run" / f"gateway-recovery-{checksum[:16]}.pyz"
    if artifact.is_symlink() or digest(artifact) != checksum:
        raise UpdateBlocked("gateway_recovery_identity_changed")
    modules = module_blobs(project, tool)
    try:
        validate_recovery_manifest(artifact, tool, modules)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise UpdateBlocked("gateway_recovery_manifest_changed") from exc
    return artifact


def validate_recovery_manifest(artifact: Path, tool: str, modules: dict):
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        expected = {"manifest.json", "__main__.py", *("resident/" + name for name in modules)}
        if (
            len(names) != len(expected)
            or set(names) != expected
            or sum(info.file_size for info in archive.infolist()) > 8_000_000
        ):
            raise UpdateBlocked("gateway_recovery_manifest_changed")
        manifest = json.loads(archive.read("manifest.json"))
        if (
            manifest != {"tool_revision": tool, "modules": modules}
            or archive.read("__main__.py") != RECOVERY_MAIN.encode()
        ):
            raise UpdateBlocked("gateway_recovery_manifest_changed")
        for name, blob in modules.items():
            raw = archive.read("resident/" + name)
            # SHA-1 here is the repository's Git blob identifier, not an artifact signature.
            actual = hashlib.sha1(
                b"blob " + str(len(raw)).encode() + b"\0" + raw, usedforsecurity=False
            ).hexdigest()
            if actual != blob:
                raise UpdateBlocked("gateway_recovery_manifest_changed")


def process(pid: int) -> str | None:
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "lstart=,command="],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 1 and not result.stdout.strip():
        return None
    if result.returncode:
        raise UpdateBlocked("gateway_process_unknown")
    return result.stdout.strip()


def job_state() -> str | None:
    result = subprocess.run(
        ["/bin/launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if (
        result.returncode == 113
        and result.stderr
        == f'Bad request.\nCould not find service "{LABEL}" in domain for user gui: {os.getuid()}\n'
    ):
        return None
    if result.returncode:
        raise UpdateBlocked("gateway_job_unknown")
    return result.stdout


def job_pid() -> int | None:
    state = job_state()
    if state is None:
        return None
    pids = [
        line.strip().split(" = ")[-1]
        for line in state.splitlines()
        if line.strip().startswith("pid = ")
    ]
    if not pids:
        return None
    if len(pids) != 1 or not pids[0].isdigit():
        raise UpdateBlocked("gateway_process_unknown")
    return int(pids[0])


def no_children(pid: int):
    lines = run(["/bin/ps", "-axo", "pid=,ppid="]).splitlines()
    if any(int(line.split()[1]) == pid for line in lines):
        raise UpdateBlocked("gateway_children_unknown")


def no_private_processes(server: Path):
    prefix = str(server / "users") + "/"
    if any(prefix in row for row in run(["/bin/ps", "-axo", "command="]).splitlines()):
        raise UpdateBlocked("gateway_private_process_unknown")


def listener_pids() -> set[int]:
    result = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP:8089", "-sTCP:LISTEN", "-Fp"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode not in {0, 1} or (result.returncode == 1 and result.stdout.strip()):
        raise UpdateBlocked("gateway_listener_unknown")
    return {int(row[1:]) for row in result.stdout.splitlines() if row.startswith("p")}


def native_image(pid: int) -> Path:
    """Bind the kernel's executable image, including Homebrew's framework exec."""
    if sys.platform != "darwin" or type(pid) is not int or not 0 < pid <= 0x7FFFFFFF:
        raise UpdateBlocked("gateway_image_unverified")
    try:
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        probe = library.proc_pidpath
        probe.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        probe.restype = ctypes.c_int
        buffer = ctypes.create_string_buffer(4096)
        if probe(pid, buffer, len(buffer)) <= 0:
            raise ValueError
        path = Path(os.fsdecode(buffer.value))
        if not path.is_absolute() or not path.is_file():
            raise ValueError
        return path.resolve(strict=True)
    except (OSError, ValueError, AttributeError) as exc:
        raise UpdateBlocked("gateway_image_unverified") from exc


def verify_signal_contract():
    import uvicorn
    from uvicorn.server import Server

    source = inspect.getsource(Server.handle_exit).encode()
    if (
        uvicorn.__version__ != "0.53.0"
        or hashlib.sha256(source).hexdigest()
        != "553276efa26e09ea84b4626425f1d03647f1b043084f5a42994f3ae7e0d1aa1e"
        or uvicorn.Config(app=None).timeout_graceful_shutdown is not None
    ):
        raise UpdateBlocked("gateway_signal_contract_unknown")


def read_upgrade_journal(path: Path) -> dict:
    """Full preservation manifests have a separate, private bounded envelope."""
    try:
        if path.resolve(strict=True) != path.absolute():
            raise ValueError
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_nlink != 1
                or before.st_size > JOURNAL_MAX_BYTES
            ):
                raise ValueError
            raw = stream.read(JOURNAL_MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            current = path.lstat()
            fields = (
                "st_dev",
                "st_ino",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
                "st_nlink",
                "st_mode",
                "st_uid",
            )
            if (
                len(raw) != before.st_size
                or len(raw) > JOURNAL_MAX_BYTES
                or any(
                    getattr(before, k) != getattr(after, k)
                    or getattr(before, k) != getattr(current, k)
                    for k in fields
                )
            ):
                raise ValueError
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (OSError, ValueError, TypeError) as exc:
        raise UpdateBlocked("gateway_journal_invalid") from exc


def journal_preflight(state: dict):
    # Subsequent phases only replace the phase string. Reserve ample space before
    # any signal so every recovery phase fits the exact same reader budget.
    if len(json.dumps(state, indent=2).encode("utf-8")) > JOURNAL_MAX_BYTES - 4096:
        raise UpdateBlocked("gateway_journal_oversized")


def write_upgrade_journal(path: Path, state: dict):
    if len(json.dumps(state, indent=2).encode("utf-8")) > JOURNAL_MAX_BYTES:
        raise UpdateBlocked("gateway_journal_oversized")
    atomic(path, state)


def wait_retired(pid: int, *, timeout: float = 45):
    """An exited but unreaped PID is not retirement; never signal it again here."""
    deadline = time.monotonic() + timeout
    while process(pid) is not None:
        if time.monotonic() >= deadline:
            raise MaintenanceBusy("gateway_draining")
        time.sleep(0.1)


def graceful_drain(pid: int, expected: str, command: str, timeout: float = 90):
    verify_signal_contract()
    if native_image(pid) != native_image(os.getpid()):
        raise UpdateBlocked("gateway_image_changed")
    if process(pid) != expected or expected.split(maxsplit=5)[-1] != command:
        raise UpdateBlocked("gateway_process_changed")
    if not listener_pids() <= {pid}:
        raise UpdateBlocked("gateway_listener_unknown")
    no_children(pid)
    os.kill(pid, signal.SIGTERM)  # uvicorn waits for accepted HTTP tasks; no SIGKILL.
    wait_retired(pid, timeout=timeout)


def health(config: dict, *, fenced: bool | None):
    connection = http.client.HTTPConnection("127.0.0.1", 8089, timeout=5)
    try:
        connection.request(
            "GET", "/api/server/health", headers={"Host": urlsplit(config["origin"]).netloc}
        )
        response = connection.getresponse()
        value = json.loads(response.read(65537))
        if (
            response.status != 200
            or value.get("status") != "ready"
            or value.get("revision") != config["revision"]
            or value.get("primary_last_verified") is not True
            or (fenced is not None and value.get("deployment_fenced") is not fenced)
        ):
            raise UpdateBlocked("gateway_health_failed")
    finally:
        connection.close()


def wait_health(config: dict, *, fenced: bool | None):
    for attempt in range(40):
        try:
            health(config, fenced=fenced)
            return
        except (OSError, ValueError, http.client.HTTPException, UpdateBlocked):
            if attempt == 39:
                raise UpdateBlocked("gateway_health_failed") from None
            time.sleep(0.5)


def verify_primary(home: Path, expected: str, *, index_reader=read_json):
    from app.research_web.multiuser.resident_binding import LegacyBinding
    from app.research_web.service_manager import WebServiceManager

    _, config = configured(home)
    clean(Path(config["project"]), expected)
    server = read_json(home / "server/resident.json")
    binding = LegacyBinding.discover(home, server["binding"]["primary_user_id"])
    state = binding.verify()
    manager = WebServiceManager(
        project_root=binding.project,
        data_root=binding.data_root,
        python=str(binding.project / ".venv/bin/python"),
        node=config["node"],
        web_port=binding.web_port,
        runtime_port=binding.runtime_port,
    )
    runtime = next(probe for probe in manager._service_probes() if probe.role == "runtime")
    if state.get("active") is not False or manager._active_research_read_only(runtime):
        raise MaintenanceBusy("research_active_or_unknown")
    index = index_reader(binding.data_root / "index.json")
    rows = index.get("automation_runs", {})
    if not isinstance(rows, dict) or any(
        not isinstance(row, dict) or row.get("research_status") in {"queued", "running"}
        for row in rows.values()
    ):
        raise MaintenanceBusy("research_active_or_unknown")
    return binding.public_config()


def write_config(path: Path, value: dict):
    atomic(path, value)


def bootout_after_drain(plist: Path):
    # The old PID has retired through uvicorn's own graceful shutdown. A KeepAlive
    # replacement cannot pass AccountStore construction while DB EX is held.
    run(["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])


def bootstrap(plist: Path):
    run(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])


def preservation(home: Path) -> dict:
    from app.research_web.multiuser.preservation import snapshot

    root = home / "server"
    values = {
        "primary": snapshot(home / "research-web"),
        "accounts": digest(root / "accounts.sqlite3"),
    }
    values["private"] = {
        folder.name: snapshot(folder / "research-web")
        for folder in (root / "users").iterdir()
        if (folder / "research-web/index.json").exists()
    }
    return values


def preserved(home: Path, before: dict):
    from app.research_web.multiuser.preservation import compare_snapshot

    after = preservation(home)
    if after["accounts"] != before["accounts"] or set(after["private"]) != set(before["private"]):
        raise UpdateBlocked("gateway_preservation_failed")
    pairs = [(before["primary"], after["primary"])] + [
        (value, after["private"][uid]) for uid, value in before["private"].items()
    ]
    if not all(compare_snapshot(a, b)["preserved"] for a, b in pairs):
        raise UpdateBlocked("gateway_preservation_failed")


def install_recovery(home: Path, source: Path, *, revision: str | None = None):
    """Separate immutable, reviewed artifact; never replace resident/controller.pyz."""
    # launchd does not inherit the operator shell's Homebrew path. Prove the
    # existing checkout hook tool is available before any fencing or signalling.
    run(["/usr/bin/env", f"PATH={RECOVERY_PATH}", "/usr/bin/git", "lfs", "version"])
    log.info("gateway_recovery_checkout_tools_verified")
    root = home / "server/run"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if revision is None:
            for path in sorted((source / "research_workbench_entrypoint/resident").glob("*.py")):
                archive.writestr(zipfile.ZipInfo("resident/" + path.name), path.read_bytes())
        else:
            if not SHA.fullmatch(revision):
                raise UpdateBlocked("gateway_static_revision_invalid")
            modules = module_blobs(source, revision)
            for name in sorted(modules):
                archive.writestr(
                    zipfile.ZipInfo("resident/" + name), git_bytes(source, revision, name)
                )
            archive.writestr(
                zipfile.ZipInfo("manifest.json"),
                json.dumps({"tool_revision": revision, "modules": modules}, sort_keys=True),
            )
        archive.writestr(
            zipfile.ZipInfo("__main__.py"),
            RECOVERY_MAIN,
        )
    raw = buffer.getvalue()
    checksum = hashlib.sha256(raw).hexdigest()
    suffix = "" if revision is None else "-" + checksum[:16]
    artifact = root / f"gateway-recovery{suffix}.pyz"
    label = RECOVERY if revision is None else RECOVERY + "." + checksum[:16]
    if artifact.exists() or artifact.is_symlink():
        if digest(artifact) != hashlib.sha256(raw).hexdigest():
            raise UpdateBlocked("gateway_recovery_artifact_changed")
    else:
        descriptor = os.open(artifact, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    sync_directory(root)
    plist = Path.home() / "Library/LaunchAgents" / (label + ".plist")
    python = str(Path(read_json(home / "resident/config.json")["project"]) / ".venv/bin/python")
    payload = {
        "Label": label,
        "ProgramArguments": [python, str(artifact), "recover", "--home", str(home)],
        "RunAtLoad": True,
        "StartInterval": 30,
        "WorkingDirectory": str(home),
        "StandardOutPath": str(home / "logs/gateway-recovery.log"),
        "StandardErrorPath": str(home / "logs/gateway-recovery-error.log"),
        "EnvironmentVariables": {"PYTHONDONTWRITEBYTECODE": "1", "PATH": RECOVERY_PATH},
    }
    if plist.exists() or plist.is_symlink():
        if plist.is_symlink() or plist.read_bytes() != plistlib.dumps(payload):
            raise UpdateBlocked("gateway_recovery_job_changed")
    else:
        descriptor = os.open(plist, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            plistlib.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
    sync_directory(plist.parent)
    bootstrap_recovery = ["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)]
    try:
        run(bootstrap_recovery)
    except UpdateBlocked:
        registered = run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"])
        if str(artifact) not in registered or python not in registered:
            raise UpdateBlocked("gateway_recovery_job_unknown") from None
    result = {"artifact_sha256": digest(artifact), "plist_sha256": digest(plist)}
    if revision is not None:
        result["tool_revision"] = revision
    return result


def finish(root: Path, state: dict, result: str):
    record = {
        "status": result,
        "target": state["target"],
        "primary": state["primary"],
        "previous": state["previous"],
        "preserved": True,
    }
    if state.get("version") in {2, 3}:
        record.update(mode=state["mode"], tool_revision=state["tool_revision"])
    atomic(root / "gateway-upgrade-result.json", record)
    (root / "gateway-upgrade.json").unlink()
    sync_directory(root)


def apply(
    home: Path,
    source: Path,
    primary: str,
    target: str,
    *,
    expected_gateway: str | None = None,
    preserve_primary: bool = False,
):
    if sys.platform != "darwin":
        raise UpdateBlocked("gateway_macos_only")
    root, resident = configured(home)
    sys.path.insert(0, resident["project"])
    server = home / "server"
    private_root(server / "run")
    with ExitStack() as stack:
        stack.enter_context(file_lock(root, "supervisor.lock", exclusive=True))
        stack.enter_context(file_lock(root, "admission.lock", exclusive=True))
        if (root / "transaction.json").exists() or (server / "run/gateway-upgrade.json").exists():
            raise UpdateBlocked("gateway_recovery_required")
        static_ui = expected_gateway is not None
        if preserve_primary and not static_ui:
            raise UpdateBlocked("gateway_upgrade_arguments_required")
        tool_revision = git(source, "rev-parse", "HEAD") if static_ui else target
        if static_ui:
            if (
                (primary == target if preserve_primary else primary != target)
                or not isinstance(expected_gateway, str)
                or not SHA.fullmatch(expected_gateway)
            ):
                raise UpdateBlocked("gateway_static_revision_invalid")
            clean(source, tool_revision)
        else:
            reviewed = review(source, target, primary)
        github = GitHubEvidence(
            Path(resident["gh"]), resident["repository"], Path(resident["source_common"])
        )
        if github.latest() != tool_revision:
            raise UpdateBlocked("resident_master_moved")
        proof = github.qualify(target)
        tool_proof = github.qualify(tool_revision) if static_ui else proof
        config = read_json(server / "resident.json")
        project = Path(config["project"])
        previous = git(project, "rev-parse", "HEAD")
        clean(project, previous)
        if config["revision"] != previous:
            raise UpdateBlocked("gateway_source_revision_mismatch")
        if static_ui:
            if previous != expected_gateway:
                raise UpdateBlocked("gateway_static_baseline_changed")
            reviewed = (
                preserved_primary_scopes(source, primary, previous, target, tool_revision)
                if preserve_primary
                else static_scopes(source, previous, target, tool_revision)
            )
        if (
            git(project, "rev-parse", "--path-format=absolute", "--git-common-dir")
            != resident["source_common"]
        ):
            raise UpdateBlocked("gateway_source_identity_changed")
        binding = verify_primary(home, primary)
        fallback = {**config, "binding": binding}
        updated = {**fallback, "revision": target}
        plist = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
        payload = plistlib.loads(plist.read_bytes())
        python = str(Path(resident["project"]) / ".venv/bin/python")
        if Path(sys.prefix).resolve() != (Path(resident["project"]) / ".venv").resolve():
            raise UpdateBlocked("gateway_interpreter_unverified")
        verify_signal_contract()
        argv = [python, "-m", "app.research_web.multiuser.resident", "--root", str(server)]
        image = native_image(os.getpid())
        commands = {
            " ".join([executable, *argv[1:]])
            for executable in {python, str(Path(python).resolve()), str(image)}
        }
        if (
            payload.get("WorkingDirectory") != str(project)
            or payload.get("Label") != LABEL
            or payload.get("ProgramArguments") != argv
        ):
            raise UpdateBlocked("gateway_job_identity_changed")
        pid = job_pid()
        signature = process(pid) if pid else None
        command = signature.split(maxsplit=5)[-1] if signature else ""
        if (
            pid is None
            or not signature
            or command not in commands
            or native_image(pid) != image
            or listener_pids() != {pid}
        ):
            raise UpdateBlocked("gateway_process_unknown")
        no_children(pid)
        no_private_processes(server)
        # Install crash recovery before fencing or signalling any service.
        recovery = (
            install_recovery(home, source, revision=tool_revision)
            if static_ui
            else install_recovery(home, source)
        )
        state = {
            "version": 1,
            "phase": "preparing",
            "primary": primary,
            "target": target,
            "previous": previous,
            "project": str(project),
            "project_identity": [project.stat().st_dev, project.stat().st_ino],
            "old_pid": pid,
            "old_signature": signature,
            "original_config": config,
            "command": command,
            "fallback": fallback,
            "updated": updated,
            "plist_sha256": digest(plist),
            "transaction": str(uuid4()),
            "reviewed": reviewed,
            "proof": proof,
            "recovery": recovery,
        }
        if static_ui:
            state.update(
                version=3 if preserve_primary else 2,
                mode="static-gateway" if preserve_primary else "static-ui",
                tool_revision=tool_revision,
                tool_proof=tool_proof,
            )
            static_recovery_identity(home, state)
        atomic(server / "run/gateway-upgrade-original.json", state)
        write_upgrade_journal(server / "run/gateway-upgrade.json", state)
        try:
            fence = stack.enter_context(
                BirthFence(server, binding["primary_user_id"], transaction=state["transaction"])
            )
            verify_primary(home, primary)
            state["before"] = preservation(home)
            journal_preflight(state)
            if github.latest() != tool_revision:
                raise UpdateBlocked("resident_master_moved")
        except Exception:
            BirthFence.recover(server, expected=state["transaction"])
            (server / "run/gateway-upgrade.json").unlink()
            sync_directory(server / "run")
            raise
        state["phase"] = "draining"
        write_upgrade_journal(server / "run/gateway-upgrade.json", state)
        fence.retain = True  # Every failure after signal intent must remain recoverable.
        try:
            graceful_drain(pid, signature, command)
        except MaintenanceBusy:
            # Persist slots while graceful shutdown completes; recovery will wait.
            fence.retain = True
            raise
        bootout_after_drain(plist)
        state["phase"] = "stopped"
        write_upgrade_journal(server / "run/gateway-upgrade.json", state)
        fence.release_database()
        BirthFence.recover(server, expected=state["transaction"])
        return activate_gateway(home, state, plist)


def activate_gateway(home: Path, state: dict, plist: Path):
    server, project = home / "server", Path(state["project"])
    try:
        git(project, "switch", "--detach", state["target"])
        write_config(server / "resident.json", state["updated"])
        state["phase"] = "starting"
        write_upgrade_journal(server / "run/gateway-upgrade.json", state)
        bootstrap(plist)
        wait_health(state["updated"], fenced=True)
        verify_primary(home, state["primary"])
        preserved(home, state["before"])
    except Exception:
        log.exception("gateway_candidate_failed_recovery_required")
        return recover_locked(home, state)
    finish(server / "run", state, "deployed")
    return {
        "status": "deployed",
        "primary": state["primary"],
        "gateway": state["target"],
        "preserved": True,
    }


def recover_locked(home: Path, state: dict):
    server, root = home / "server", home / "server/run"
    project = Path(state["project"])
    if not SHA.fullmatch(state.get("target", "")) or not SHA.fullmatch(state.get("previous", "")):
        raise UpdateBlocked("gateway_recovery_identity_changed")
    if state.get("version") in {2, 3}:
        static_recovery_identity(home, state)
    elif (
        state.get("version") != 1
        or state.get("primary") != PRODUCT
        or digest(root / "gateway-recovery.pyz") != state["recovery"]["artifact_sha256"]
    ):
        raise UpdateBlocked("gateway_recovery_identity_changed")
    if [project.stat().st_dev, project.stat().st_ino] != state["project_identity"]:
        raise UpdateBlocked("gateway_source_identity_changed")
    verify_primary(home, state["primary"])
    if state["phase"] == "preparing":
        clean(project, state["previous"])
        if read_json(server / "resident.json") != state["original_config"]:
            raise UpdateBlocked("gateway_configuration_changed")
        BirthFence.recover(server, expected=state["transaction"])
        finish(root, state, "aborted_before_signal")
        return {"status": "aborted_before_signal"}
    if state["phase"] == "fallback_starting":
        clean(project, state["previous"])
        if read_json(server / "resident.json") != state["fallback"]:
            raise UpdateBlocked("gateway_configuration_changed")
        if job_state() is None:
            bootstrap(Path.home() / "Library/LaunchAgents" / (LABEL + ".plist"))
        wait_health(state["fallback"], fenced=None)
        finish(root, state, "rolled_back")
        return {
            "status": "rolled_back",
            "primary": state["primary"],
            "gateway": state["previous"],
            "preserved": True,
        }
    plist = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    if digest(plist) != state["plist_sha256"]:
        raise UpdateBlocked("gateway_job_identity_changed")
    # A live candidate may be stopped only when its new persistent gate is proved.
    if state["phase"] == "starting":
        clean(project, state["target"])
        if read_json(server / "resident.json") != state["updated"]:
            raise UpdateBlocked("gateway_configuration_changed")
        if any((server / "users").glob("*/state/owner.json")):
            raise MaintenanceBusy("gateway_candidate_state_unknown")
        no_private_processes(server)
        # Even when health fails, exact reviewed startup code plus the durable
        # all-request gate proves no business admission. Never stop unknown code.
        if not (root / "gateway-upgrade.json").is_file():
            raise UpdateBlocked("gateway_fence_missing")
        current = job_pid()
        if current is not None:
            signature = process(current)
            if signature is None:
                raise MaintenanceBusy("gateway_candidate_state_unknown")
            graceful_drain(current, signature, state["command"])
    elif state["phase"] == "draining":
        # A KeepAlive replacement may have started after a crash released SQLite;
        # re-acquire the birth fence or defer before touching it.
        with BirthFence(
            server,
            state["fallback"]["binding"]["primary_user_id"],
            resume=True,
            transaction=state["transaction"],
        ) as fence:
            verify_primary(home, state["primary"])
            fence.retain = True
            current = job_pid()
            if current is not None:
                signature = process(current)
                if signature is None or signature.split(maxsplit=5)[-1] != state["command"]:
                    raise UpdateBlocked("gateway_process_unknown")
                try:
                    graceful_drain(current, signature, state["command"])
                except MaintenanceBusy:
                    fence.retain = True
                    raise
            if job_state() is not None:
                bootout_after_drain(plist)
            state["phase"] = "stopped"
            write_upgrade_journal(root / "gateway-upgrade.json", state)
    elif state["phase"] not in {"stopped", "rolling_back"}:
        raise UpdateBlocked("gateway_recovery_phase_unknown")
    if job_state() is not None:
        if state["phase"] != "starting":
            raise UpdateBlocked("gateway_unexpected_job_during_recovery")
        run(["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])
    BirthFence.recover(server, expected=state["transaction"])
    state["phase"] = "rolling_back"
    write_upgrade_journal(root / "gateway-upgrade.json", state)
    actual = git(project, "rev-parse", "HEAD")
    if actual not in {state["previous"], state["target"]}:
        raise UpdateBlocked("gateway_source_revision_mismatch")
    clean(project, actual)
    git(project, "switch", "--detach", state["previous"])
    write_config(server / "resident.json", state["fallback"])
    preserved(home, state["before"])
    state["phase"] = "fallback_starting"
    write_upgrade_journal(root / "gateway-upgrade.json", state)
    bootstrap(plist)
    wait_health(state["fallback"], fenced=None)
    finish(root, state, "rolled_back")
    return {
        "status": "rolled_back",
        "primary": state["primary"],
        "gateway": state["previous"],
        "preserved": True,
    }


def recover(home: Path):
    journal = home / "server/run/gateway-upgrade.json"
    if not journal.exists():
        return {"status": "idle"}
    state = read_upgrade_journal(journal)
    helper = Path(sys.argv[0])
    if helper.suffix == ".pyz" and helper.name.startswith("gateway-recovery-"):
        checksum = state.get("recovery", {}).get("artifact_sha256", "")
        if not isinstance(checksum, str):
            return {"status": "other_recovery_version"}
        expected = home / "server/run" / f"gateway-recovery-{checksum[:16]}.pyz"
        if state.get("version") not in {2, 3} or helper.resolve() != expected.resolve():
            return {"status": "other_recovery_version"}
    root, config = configured(home)
    sys.path.insert(0, config["project"])
    with (
        file_lock(root, "supervisor.lock", exclusive=True),
        file_lock(root, "admission.lock", exclusive=True),
    ):
        current = read_upgrade_journal(journal)
        if current != state:
            raise UpdateBlocked("gateway_journal_changed")
        return recover_locked(home, current)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("apply", "apply-ui", "stage-primary-ui", "recover", "status")
    )
    parser.add_argument("--home", type=Path, default=Path.home() / ".research-workbench")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--primary")
    parser.add_argument("--target")
    parser.add_argument("--expected-gateway")
    parser.add_argument("--preserve-primary", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(filename=args.home / "logs/gateway-upgrade.log", level=logging.INFO)
    try:
        if args.preserve_primary and args.command != "apply-ui":
            raise UpdateBlocked("gateway_upgrade_arguments_required")
        if args.command == "stage-primary-ui":
            if not args.source or not args.primary or not args.target or args.expected_gateway:
                raise UpdateBlocked("gateway_upgrade_arguments_required")
            value = stage_primary_ui(args.home, args.source, args.primary, args.target)
        elif args.command in {"apply", "apply-ui"}:
            if not args.source or not args.primary or not args.target:
                raise UpdateBlocked("gateway_upgrade_arguments_required")
            if args.command == "apply-ui":
                if not args.expected_gateway:
                    raise UpdateBlocked("gateway_upgrade_arguments_required")
                value = apply(
                    args.home,
                    args.source,
                    args.primary,
                    args.target,
                    expected_gateway=args.expected_gateway,
                    preserve_primary=args.preserve_primary,
                )
            else:
                if args.expected_gateway:
                    raise UpdateBlocked("gateway_upgrade_arguments_required")
                value = apply(args.home, args.source, args.primary, args.target)
        elif args.command == "recover":
            value = recover(args.home)
        else:
            path = args.home / "server/run/gateway-upgrade-result.json"
            value = read_json(path) if path.exists() else {"status": "not_run"}
        print(json.dumps(value))
        return 0
    except MaintenanceBusy as exc:
        journal = args.home / "server/run/gateway-upgrade.json"
        pending = str(exc) == "gateway_draining"
        try:
            pending = pending or (
                journal.exists() and read_upgrade_journal(journal).get("phase") != "preparing"
            )
        except UpdateBlocked:
            pending = True
        print(
            json.dumps(
                {
                    "status": "recovery_required" if pending else "deferred",
                    "reason": "research_or_gateway_not_quiescent",
                }
            )
        )
        return 1 if pending else 0
    except Exception as exc:
        log.exception("gateway_upgrade_failed")
        code = str(exc) if isinstance(exc, UpdateBlocked) else "gateway_upgrade_failed"
        print(json.dumps({"status": "blocked", "reason": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
