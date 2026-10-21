"""Explicit, exact-scope Native product upgrades; automatic policy is unchanged."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import plistlib
import re
import socket
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID, uuid4

from . import controller as c
from . import gateway_upgrade as g
from .admission import MaintenanceBusy, file_lock
from .evidence import GitHubEvidence, UpdateBlocked, read_json
from .gateway_fence import BirthFence

log = logging.getLogger(__name__)
PREVIOUS = "5df8e17e04f1b588f7e742423d81fb8e0ba34cb2"
# PR165 model backend plus already merged PR166 login presentation only.
PAYLOAD = "0d73c0348094f11c3440d8f6893c7a6896a8dbc8"
# PR168's reviewed navigation; all other product files retain PAYLOAD's identity.
NAVIGATION_PAYLOAD = "4e8be6ac7405733755e4a00be10898504e71710a"
NAVIGATION_FILES = frozenset(
    f"app/research_web/ui/{name}.mjs" for name in ("app", "core", "intel", "shell", "workbench")
)
MODULE = "research_workbench_entrypoint/resident/model_provider_upgrade.py"
WORKFLOW = ".github/workflows/research-web-checks.yml"
CONSTRAINTS = ".agents/project-constraints.json"
TEST = "tests/research_web/test_model_provider_upgrade.py"
ENTRY = "from resident.model_provider_upgrade import main\nraise SystemExit(main())\n"
MODE = "reviewed-model-providers-v1"
ASSET_MODE = "reviewed-asset-observation-v1"
ASSET_PREVIOUS = "c68814db170900688d6a799a241efc098eb83f32"
ASSET_PAYLOAD = "54d4c8f9421c568de853a2f93263a2bfcd53422c"
MAX_ASSET_INDEX_BYTES = 64 * 1024 * 1024
CONTROLLER_SHA256 = "4924299104d5f82a9cc732bb2ca1f811694d14056d58a2762e7c86e40f6665a2"
CONTROLLER_MODULE_SHA256 = "b432f519e14a2e851a7eb39a3de179f99494b9347c857694c4192477a7996846"
TAILSCALE = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
FORWARD = (
    "stop_gateway",
    "stop_primary",
    "activate_sources_and_wheel",
    "start_primary",
    "start_gateway",
    "verify_target",
)
BACKWARD = (
    "rollback_gateway",
    "rollback_primary",
    "restore_sources_and_wheel",
    "start_previous_primary",
    "start_previous_gateway",
    "verify_previous",
)


def execute(ops, state, *, recovering=False):
    """Keep every signal/install behind durable intent; uncertain drains stay fenced."""
    if not recovering:
        try:
            idle = ops.idle()
        except (MaintenanceBusy, UpdateBlocked, OSError, ValueError):
            log.warning("model_upgrade_activity_unknown")
            idle = False
        if idle is not True:
            return {"status": "deferred"}
        try:
            ops.checkpoint(state, "prepared")
            for action in FORWARD:
                ops.checkpoint(state, action)
                ops.action(action, state)
        except MaintenanceBusy:
            log.warning("model_upgrade_drain_deferred")
            return {"status": "recovery_required"}
        except Exception:
            log.exception("model_upgrade_candidate_failed")
        else:
            # A finish failure can occur AFTER HTTP admission has reopened.
            # Never signal/reinstall from this stack after that boundary. A new
            # recovery invocation must first reacquire and validate all fences.
            try:
                return ops.finish(state, "deployed")
            except Exception:
                log.exception("model_upgrade_completion_unknown")
                return {"status": "completion_unknown"}
    try:
        if ops.idle() is not True:
            return {"status": "recovery_required"}
        for action in BACKWARD:
            ops.checkpoint(state, action)
            ops.action(action, state)
        return ops.finish(state, "rolled_back")
    except Exception:
        log.exception("model_upgrade_recovery_pending")
        return {"status": "recovery_required"}


def previous_for(mode):
    if mode == MODE:
        return PREVIOUS
    if mode == ASSET_MODE:
        return ASSET_PREVIOUS
    raise UpdateBlocked("model_upgrade_profile_unknown")


def asset_queries_idle(index):
    """A Native-idle response does not prove pending DataHub work has finished."""
    observations, queries = index.get("asset_observations", {}), index.get("data_queries", {})
    if not isinstance(observations, dict) or not isinstance(queries, dict):
        return False
    for row in observations.values():
        if not isinstance(row, dict) or row.get("status") not in {"complete", "partial", "failed"}:
            return False
        blocks = row.get("blocks", {})
        if not isinstance(blocks, dict) or any(
            not isinstance(block, dict)
            or block.get("status") not in {"complete", "partial", "empty", "unavailable", "error"}
            for block in blocks.values()
        ):
            return False
    return all(
        isinstance(row, dict) and row.get("status") in {"completed", "failed"}
        for row in queries.values()
    )


def asset_index_snapshot(home: Path):
    """Hash every business-index value, preserving scope and missing/empty distinctions."""

    def snapshot(path):
        try:
            if path.resolve() != path.absolute():
                raise ValueError("index_path_unsafe")
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ASSET_INDEX_BYTES:
                    raise ValueError("index_file_invalid")
                raw = stream.read(MAX_ASSET_INDEX_BYTES + 1)
            if len(raw) > MAX_ASSET_INDEX_BYTES:
                raise ValueError("index_size_invalid")
            index = json.loads(raw)
            if not isinstance(index, dict):
                raise ValueError("index_object_required")
        except (OSError, ValueError) as exc:
            log.error("asset_upgrade_index_read_failed", extra={"error_type": type(exc).__name__})
            raise UpdateBlocked("asset_upgrade_index_invalid") from exc
        return {
            key: hashlib.sha256(
                json.dumps(
                    value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
                ).encode()
            ).hexdigest()
            for key, value in index.items()
        }

    users = home / "server/users"
    if users.is_symlink() or not users.is_dir():
        raise UpdateBlocked("asset_upgrade_index_scope_invalid")
    private = {}
    for folder in sorted(users.iterdir()):
        if folder.is_symlink() or (folder / "research-web").is_symlink():
            raise UpdateBlocked("asset_upgrade_index_scope_invalid")
        path = folder / "research-web/index.json"
        if path.exists() or path.is_symlink():
            private[folder.name] = snapshot(path)
    return {"primary": snapshot(home / "research-web/index.json"), "private": private}


def validate_asset_snapshot(state):
    if state.get("mode") != ASSET_MODE:
        return
    value = state.get("asset_index_before")
    if (
        not isinstance(value, dict)
        or set(value) != {"primary", "private"}
        or not isinstance(value["private"], dict)
    ):
        raise UpdateBlocked("asset_upgrade_index_snapshot_invalid")
    for scope in [value["primary"], *value["private"].values()]:
        if not isinstance(scope, dict) or any(
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for digest in scope.values()
        ):
            raise UpdateBlocked("asset_upgrade_index_snapshot_invalid")


def verify_asset_index(home: Path, state):
    if state.get("mode") == ASSET_MODE:
        validate_asset_snapshot(state)
        if asset_index_snapshot(home) != state["asset_index_before"]:
            log.error("asset_upgrade_business_index_changed")
            raise UpdateBlocked("asset_upgrade_business_index_changed")


def review_assets(source: Path, target: str):
    """Freeze the already reviewed PR171 product, including paths reverted from the diff."""
    c.clean(source, target)
    c.git(source, "merge-base", "--is-ancestor", ASSET_PAYLOAD, target)
    paths = {MODULE, TEST}
    for revision in (ASSET_PAYLOAD, target):
        paths.update(
            c.git(
                source, "diff", "--no-renames", "--name-only", ASSET_PREVIOUS, revision
            ).splitlines()
        )
    result = {}
    for name in sorted(paths):
        blob = c.git(source, "rev-parse", f"{target}:{name}")
        actual_mode = c.git(source, "ls-tree", target, "--", name).split()[0]
        if actual_mode not in {"100644", "100755"}:
            raise UpdateBlocked("asset_upgrade_payload_changed")
        if name.startswith(("docs/", "tests/", ".ai/reports/")) or name in {
            MODULE,
            "README.md",
            "outputs/research-web-architecture/index.html",
            "outputs/research-web-architecture/api-atlas.html",
        }:
            pass
        elif (
            blob != c.git(source, "rev-parse", f"{ASSET_PAYLOAD}:{name}")
            or actual_mode != c.git(source, "ls-tree", ASSET_PAYLOAD, "--", name).split()[0]
        ):
            raise UpdateBlocked("asset_upgrade_payload_changed")
        result[name] = blob
    log.info("asset_upgrade_payload_reviewed files=%s", len(result))
    return result


def review(source: Path, target: str, mode=MODE):
    """Only the reviewed model payload plus this operator, its test and documentation."""
    previous_for(mode)
    if mode == ASSET_MODE:
        return review_assets(source, target)
    c.clean(source, target)
    c.git(source, "merge-base", "--is-ancestor", PAYLOAD, target)
    c.git(source, "merge-base", "--is-ancestor", NAVIGATION_PAYLOAD, target)
    paths = c.git(source, "diff", "--no-renames", "--name-only", PREVIOUS, target).splitlines()
    # A reverted file disappears from PREVIOUS..target; still require every
    # reviewed navigation file so the deployed product cannot silently regress.
    paths = sorted(set(paths) | NAVIGATION_FILES)
    result = {}
    for name in paths:
        blob = c.git(source, "rev-parse", f"{target}:{name}")
        if name.startswith(("docs/", "tests/", ".ai/reports/")) or name in {
            MODULE,
            "README.md",
            "outputs/research-web-architecture/index.html",
            "outputs/research-web-architecture/api-atlas.html",
        }:
            pass
        elif name in (WORKFLOW, CONSTRAINTS):
            original = c.git(source, "show", f"{PAYLOAD}:{name}")
            expected = original
            if name == WORKFLOW and TEST not in original:
                expected = original.replace(
                    "tests/research_web/test_gateway_upgrade.py",
                    "tests/research_web/test_gateway_upgrade.py " + TEST,
                    1,
                )
            expected = expected.replace("timeout-minutes: 20", "timeout-minutes: 30", 1)
            if c.git(source, "show", f"{target}:{name}") != expected:
                raise UpdateBlocked("model_upgrade_workflow_scope_changed")
        else:
            expected = NAVIGATION_PAYLOAD if name in NAVIGATION_FILES else PAYLOAD
            expected_blob = c.git(source, "rev-parse", f"{expected}:{name}")
            expected_mode = c.git(source, "ls-tree", expected, "--", name).split()[0]
            actual_mode = c.git(source, "ls-tree", target, "--", name).split()[0]
            if blob != expected_blob or expected_mode != actual_mode:
                raise UpdateBlocked("model_upgrade_payload_changed")
        result[name] = blob
    if MODULE not in result or TEST not in result:
        raise UpdateBlocked("model_upgrade_operator_missing")
    log.info(
        "model_upgrade_payload_reviewed files=%s navigation_files=%s",
        len(result),
        len(NAVIGATION_FILES.intersection(result)),
    )
    return result


def request_json(url):
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=15) as r:
        return json.load(r)


def ports_are_free(ports):
    for port in ports:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return False
    return True


def model_metadata(config):
    value = request_json(f"http://127.0.0.1:{config['web_port']}/api/research/runtime")
    if (
        value.get("connected") is not True
        or value.get("health_check_passed") is not True
        or (
            type(value.get("credential_configured")) is not bool
            and value.get("credential_storage") != "not_required"
        )
    ):
        raise MaintenanceBusy("model_upgrade_credential_state_unknown")
    return {
        key: value.get(key)
        for key in ("provider", "model", "credential_configured", "credential_storage")
    }


def verify_retention(home):
    index = read_json(home / "research-web/index.json")
    sessions = index.get("sessions")
    if not isinstance(sessions, dict):
        raise UpdateBlocked("model_upgrade_session_state_unknown")
    cutoff = time.time() - 30 * 86400 + 3600
    if any(
        not isinstance(row, dict)
        or (isinstance(row.get("deleted_at"), (int, float)) and row["deleted_at"] <= cutoff)
        for row in sessions.values()
    ):
        raise UpdateBlocked("model_upgrade_retention_due")


def verify_serve(origin):
    from urllib.parse import urlsplit

    value = json.loads(g.run([TAILSCALE, "serve", "status", "--json"]))
    authority = urlsplit(origin).netloc + ":443"
    web = value.get("Web", {})
    handlers = web.get(authority, {}).get("Handlers", {})
    # Existing /collections is a separate private service and is never changed.
    if (
        value.get("AllowFunnel")
        or set(web) != {authority}
        or set(handlers) - {"/", "/collections"}
        or handlers.get("/") != {"Proxy": "http://127.0.0.1:8089"}
        or value.get("TCP") != {"443": {"HTTPS": True}}
    ):
        raise UpdateBlocked("model_upgrade_private_route_unknown")


def verify_private_fence(origin):
    """No redirect or primary HTML may make the old controller clear its journal."""

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(origin + "/", timeout=15):
            pass
    except urllib.error.HTTPError as error:
        if error.code == 503:
            return
    raise UpdateBlocked("model_upgrade_private_fence_unverified")


def reserved_owners(server, transaction):
    """Validate only this fence's directory reservations; never mistake one for work."""
    owners = set((server / "users").glob("*/state/owner.json"))
    journal = server / "run/birth-fence.json"
    if not journal.exists():
        return not owners
    value = read_json(journal)
    if value.get("version") != 1 or value.get("transaction") != transaction:
        return False
    expected = set()
    for slot in value["slots"]:
        user = slot["user"]
        if str(UUID(user)) != user:
            return False
        p = server / "users" / user / "state/owner.json"
        info = p.lstat()
        marker = p / "reservation"
        token_info = marker.lstat()
        if (
            p.resolve() != p
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or [info.st_dev, info.st_ino] != slot["identity"]
            or sorted(x.name for x in p.iterdir()) != ["reservation"]
            or not stat.S_ISREG(token_info.st_mode)
            or token_info.st_uid != os.getuid()
            or token_info.st_mode & 0o077
            or token_info.st_nlink != 1
            or token_info.st_size != len(transaction)
            or marker.is_symlink()
            or marker.read_text() != transaction
        ):
            return False
        expected.add(p)
    return owners == expected


def validate_executor(source, target, state=None):
    actual = Path(__file__)
    if state is not None and ".pyz/" in str(actual):
        artifact = Path(state["recovery"]["artifact"])
        if (
            Path(sys.argv[0]).absolute() != artifact
            or str(actual) != str(artifact) + "/resident/model_provider_upgrade.py"
            or c.digest(artifact) != state["recovery"]["sha256"]
        ):
            raise UpdateBlocked("other_model_recovery_version")
    elif actual.resolve() != source / MODULE or actual.read_bytes() != g.git_bytes(
        source, target, Path(MODULE).name
    ):
        raise UpdateBlocked("model_upgrade_executor_unverified")


def verify_supervisor(home, config):
    """The known immutable recovery peer must remain installed and scheduled."""
    plist = Path.home() / "Library/LaunchAgents" / (c.LABEL + ".plist")
    payload = plistlib.loads(plist.read_bytes())
    expected = [
        config["python"],
        str(home / "resident/controller.pyz"),
        "tick",
        "--home",
        str(home),
    ]
    if (
        payload.get("ProgramArguments") != expected
        or payload.get("Label") != c.LABEL
        or payload.get("WorkingDirectory") != str(home)
        or payload.get("StartInterval") != 60
        or payload.get("RunAtLoad") is not True
    ):
        raise UpdateBlocked("model_upgrade_supervisor_unknown")
    loaded = g.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{c.LABEL}"])
    if str(plist) not in loaded or str(home / "resident/controller.pyz") not in loaded:
        raise UpdateBlocked("model_upgrade_supervisor_unknown")
    return c.digest(plist)


def private_artifact(path):
    info = path.lstat()
    if (
        path.resolve() != path
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o077
    ):
        raise UpdateBlocked("model_upgrade_artifact_unsafe")


def install_recovery(home, source, target, python):
    """Freeze all operator modules from Git, before either journal or service mutation."""
    g.run(["/usr/bin/env", "PATH=" + g.RECOVERY_PATH, "/usr/bin/git", "lfs", "version"])
    modules = g.module_blobs(source, target)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(modules):
            z.writestr("resident/" + name, g.git_bytes(source, target, name))
        z.writestr("__main__.py", ENTRY)
        z.writestr(
            "manifest.json", json.dumps({"target": target, "modules": modules}, sort_keys=True)
        )
    raw = buffer.getvalue()
    checksum = hashlib.sha256(raw).hexdigest()
    label = "com.research-workbench.model-recovery." + checksum[:16]
    artifact = home / "server/run" / (label + ".pyz")
    if artifact.exists():
        private_artifact(artifact)
        if c.digest(artifact) != checksum:
            raise UpdateBlocked("model_upgrade_artifact_changed")
    else:
        with os.fdopen(
            os.open(artifact, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
        ) as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    plist = Path.home() / "Library/LaunchAgents" / (label + ".plist")
    payload = {
        "Label": label,
        "ProgramArguments": [python, str(artifact), "recover", "--home", str(home)],
        "RunAtLoad": True,
        "StartInterval": 30,
        "WorkingDirectory": str(home),
        "StandardOutPath": str(home / "logs/model-recovery.log"),
        "StandardErrorPath": str(home / "logs/model-recovery-error.log"),
        "EnvironmentVariables": {"PATH": g.RECOVERY_PATH, "PYTHONDONTWRITEBYTECODE": "1"},
    }
    raw_plist = plistlib.dumps(payload)
    if plist.exists():
        private_artifact(plist)
        if plist.is_symlink() or plist.read_bytes() != raw_plist:
            raise UpdateBlocked("model_upgrade_recovery_job_changed")
    else:
        with os.fdopen(
            os.open(plist, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
        ) as f:
            f.write(raw_plist)
            f.flush()
            os.fsync(f.fileno())
    c.sync_directory(plist.parent)
    c.sync_directory(artifact.parent)
    try:
        g.run(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])
    except UpdateBlocked:
        loaded = g.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"])
        if str(artifact) not in loaded or python not in loaded:
            raise UpdateBlocked("model_upgrade_recovery_job_unknown") from None
    return {
        "artifact": str(artifact),
        "sha256": checksum,
        "plist": str(plist),
        "plist_sha256": c.digest(plist),
        "modules": modules,
    }


def validate_state(home, state, *, executor_source=None):
    if str(UUID(state.get("transaction", ""))) != state.get("transaction"):
        raise UpdateBlocked("model_upgrade_journal_invalid")
    metadata = state.get("model_before")
    if not isinstance(metadata, dict) or set(metadata) != {
        "provider",
        "model",
        "credential_configured",
        "credential_storage",
    }:
        raise UpdateBlocked("model_upgrade_journal_invalid")
    if (
        state.get("version") != 4
        or state.get("mode") not in {MODE, ASSET_MODE}
        or state.get("previous") != previous_for(state["mode"])
    ):
        raise UpdateBlocked("model_upgrade_journal_invalid")
    if not g.SHA.fullmatch(state.get("target", "")) or state.get("phase") not in (
        "prepared",
        "preparing",
        *FORWARD,
        *BACKWARD,
    ):
        raise UpdateBlocked("model_upgrade_journal_invalid")
    validate_asset_snapshot(state)
    source = Path(state["source"])
    validate_executor(
        executor_source if executor_source is not None else source, state["target"], state
    )
    expected = home / "resident/artifacts" / state["target"] / "source"
    if (
        source != expected
        or source.resolve() != source
        or review(source, state["target"], state["mode"]) != state["reviewed"]
    ):
        raise UpdateBlocked("model_upgrade_source_changed")
    if (
        c.git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")
        != state["config"]["source_common"]
    ):
        raise UpdateBlocked("model_upgrade_source_changed")
    if (
        state["controller_sha256"] != CONTROLLER_SHA256
        or c.digest(home / "resident/controller.pyz") != CONTROLLER_SHA256
    ):
        raise UpdateBlocked("model_upgrade_controller_changed")
    if verify_supervisor(home, state["config"]) != state["supervisor_plist_sha256"]:
        raise UpdateBlocked("model_upgrade_supervisor_changed")
    recovery = state["recovery"]
    artifact = Path(recovery["artifact"])
    private_artifact(artifact)
    if artifact.parent != home / "server/run" or c.digest(artifact) != recovery["sha256"]:
        raise UpdateBlocked("model_upgrade_artifact_changed")
    with zipfile.ZipFile(artifact) as z:
        manifest = json.loads(z.read("manifest.json"))
        if (
            manifest != {"target": state["target"], "modules": recovery["modules"]}
            or z.read("__main__.py").decode() != ENTRY
        ):
            raise UpdateBlocked("model_upgrade_artifact_changed")
        if recovery["modules"] != g.module_blobs(source, state["target"]):
            raise UpdateBlocked("model_upgrade_artifact_changed")
        for name in recovery["modules"]:
            if z.read("resident/" + name) != g.git_bytes(source, state["target"], name):
                raise UpdateBlocked("model_upgrade_artifact_changed")
    if c.digest(Path(recovery["plist"])) != recovery["plist_sha256"]:
        raise UpdateBlocked("model_upgrade_recovery_job_changed")
    for key in ("new_wheel", "old_wheel"):
        wheel = state[key]
        p = Path(wheel["path"])
        if not p.is_relative_to(home / "resident/artifacts") or c.digest(p) != wheel["sha256"]:
            raise UpdateBlocked("model_upgrade_wheel_changed")
    for role in ("primary", "gateway"):
        p = Path(state[role + "_project"])
        expected_project = (
            state["config"]["project"] if role == "primary" else state["gateway_config"]["project"]
        )
        if str(p) != expected_project:
            raise UpdateBlocked("model_upgrade_project_changed")
        if p.resolve() != p or [p.stat().st_dev, p.stat().st_ino] != state[role + "_identity"]:
            raise UpdateBlocked("model_upgrade_project_changed")
        verify_release_repository(state, role)
        actual = c.git(p, "rev-parse", "HEAD")
        if actual not in (previous_for(state["mode"]), state["target"]):
            raise UpdateBlocked("model_upgrade_revision_unknown")
        c.clean(p, actual)
    if c.digest(Path(state["gateway_plist"])) != state["gateway_plist_sha256"]:
        raise UpdateBlocked("model_upgrade_job_changed")
    validate_configuration(home, state)


def repository_identity(project, repository):
    """Release clones need not share the development checkout's Git directory."""
    common = Path(c.git(project, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    info = common.lstat()
    if common.resolve() != common or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise UpdateBlocked("model_upgrade_repository_unknown")
    origin = c.git(project, "remote", "get-url", "origin")
    if origin not in {
        f"git@github.com:{repository}.git",
        f"https://github.com/{repository}.git",
        f"https://github.com/{repository}",
    }:
        raise UpdateBlocked("model_upgrade_repository_unknown")
    after = common.lstat()
    if (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino):
        raise UpdateBlocked("model_upgrade_repository_changed")
    return {"common": str(common), "identity": [info.st_dev, info.st_ino]}


def verify_release_repository(state, role):
    if (
        repository_identity(Path(state[role + "_project"]), state["config"]["repository"])
        != state[role + "_repository"]
    ):
        raise UpdateBlocked("model_upgrade_repository_changed")


def gateway_configuration(state, previous=False):
    old = state["gateway_config"]
    if previous:
        return old
    return {
        **old,
        "revision": state["target"],
        "binding": {**old["binding"], "revision": state["target"]},
    }


def validate_configuration(home, state):
    actual = read_json(home / "resident/config.json")
    if actual not in (state["config"], {**state["config"], "baseline": state["target"]}):
        raise UpdateBlocked("model_upgrade_configuration_changed")
    manifest = read_json(home / "install/manifest.json")
    if manifest not in (state["manifest"], {**state["manifest"], "code_commit": state["target"]}):
        raise UpdateBlocked("model_upgrade_manifest_changed")
    gateway = read_json(home / "server/resident.json")
    if gateway not in (gateway_configuration(state, True), gateway_configuration(state)):
        raise UpdateBlocked("model_upgrade_gateway_configuration_changed")
    pending = home / "resident/transaction.json"
    if pending.exists():
        expected = {
            k: state[k]
            for k in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
        }
        if read_json(pending) != {**expected, "phase": "switching"}:
            raise UpdateBlocked("model_upgrade_primary_journal_changed")


class Operations:
    def __init__(self, home, state, manager, lease, fence):
        self.home, self.state, self.manager, self.lease, self.fence = (
            home,
            state,
            manager,
            lease,
            fence,
        )
        self.root, self.server = home / "resident", home / "server"

    def prepare_fence(self, state):
        """Publish recoverable ownership before any reservation side effects."""
        state["before"] = g.preservation(self.home)
        if state.get("mode") == ASSET_MODE:
            state["asset_index_before"] = asset_index_snapshot(self.home)
        state["phase"] = "preparing"
        verify_serve(state["config"]["private_origin"])
        g.write_upgrade_journal(self.server / "run/gateway-upgrade.json", state)
        verify_private_fence(state["config"]["private_origin"])

    def idle(self):
        """A proved stopped role is safe; any live/unknown native or Host work is not."""
        g.no_private_processes(self.server)
        if not reserved_owners(self.server, self.state["transaction"]):
            return False
        probes = list(self.manager._service_probes())
        runtime = next(p for p in probes if p.role == "runtime")
        running = self.manager.status()["services"]
        if any(
            type(running[role][key]) is not bool
            for role in ("web", "runtime")
            for key in ("running", "healthy")
        ):
            return False
        if running["runtime"]["running"]:
            if not running["runtime"]["healthy"] or self.manager._active_research_read_only(
                runtime
            ):
                return False
        elif running["web"]["running"]:
            return False
        else:
            # No Host response is not an idle response. Only a journal already
            # fencing primary admission proves our own stopped role boundary.
            if not (self.root / "transaction.json").exists():
                return False
            if not ports_are_free(
                (self.state["config"]["web_port"], self.state["config"]["runtime_port"])
            ):
                return False
        if running["web"]["running"]:
            data = request_json(
                f"http://127.0.0.1:{self.state['config']['web_port']}/api/research/resident"
            )
            if (
                data.get("enabled") is not True
                or data.get("active") is not False
                or data.get("revision")
                not in (previous_for(self.state.get("mode", MODE)), self.state["target"])
            ):
                return False
        index = read_json(self.home / "research-web/index.json")
        if self.state.get("mode") == ASSET_MODE and not asset_queries_idle(index):
            log.info("asset_upgrade_queries_active_or_unknown")
            return False
        rows = index.get("automation_runs")
        return isinstance(rows, dict) and all(
            isinstance(v, dict) and v.get("research_status") not in ("queued", "running")
            for v in rows.values()
        )

    def checkpoint(self, state, phase):
        state["phase"] = phase
        candidate = {
            k: state[k]
            for k in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
        }
        verify_serve(state["config"]["private_origin"])
        # The old controller may recover only the known previous primary. Its
        # private '/' health cannot pass or remove the root journal under this gate.
        g.write_upgrade_journal(self.server / "run/gateway-upgrade.json", state)
        self.fence.retain = True
        if phase == "prepared" or (
            not (self.root / "transaction.json").exists() and g.job_pid() is not None
        ):
            verify_private_fence(state["config"]["private_origin"])
        c.atomic(self.root / "transaction.json", {**candidate, "phase": "switching"})
        log.info("model_upgrade_checkpoint", extra={"phase": phase})

    def stop_gateway(self):
        if c.digest(Path(self.state["gateway_plist"])) != self.state["gateway_plist_sha256"]:
            raise UpdateBlocked("model_upgrade_job_changed")
        loaded = g.job_state()
        current = g.job_pid()
        if current is None:
            if g.listener_pids():
                raise MaintenanceBusy("model_upgrade_listener_unknown")
            if loaded is None:
                return
        if loaded is None or not self.loaded_job_matches(loaded):
            raise MaintenanceBusy("model_upgrade_process_unknown")
        g.no_private_processes(self.server)
        if current is not None:
            signature = g.process(current)
            if (
                signature is None
                or signature.split(maxsplit=5)[-1] != self.state["gateway_command"]
                or g.listener_pids() != {current}
                or g.native_image(current) != g.native_image(os.getpid())
            ):
                raise MaintenanceBusy("model_upgrade_process_unknown")
            g.no_children(current)
            g.graceful_drain(current, signature, self.state["gateway_command"])
        g.bootout_after_drain(Path(self.state["gateway_plist"]))
        deadline = time.monotonic() + 15
        while g.job_state() is not None or g.listener_pids():
            if time.monotonic() >= deadline:
                raise MaintenanceBusy("model_upgrade_gateway_not_retired")
            time.sleep(0.1)

    def loaded_job_matches(self, raw):
        fields = dict(
            re.findall(r"^\s*(path|program|working directory) = (.+)$", raw, re.MULTILINE)
        )
        payload = plistlib.loads(Path(self.state["gateway_plist"]).read_bytes())
        return (
            fields.get("path") == self.state["gateway_plist"]
            and fields.get("program") == payload["ProgramArguments"][0]
            and fields.get("working directory") == self.state["gateway_project"]
        )

    def install(self, previous):
        sha = previous_for(self.state.get("mode", MODE)) if previous else self.state["target"]
        for role in ("primary", "gateway"):
            p = Path(self.state[role + "_project"])
            verify_release_repository(self.state, role)
            actual = c.git(p, "rev-parse", "HEAD")
            if actual not in (previous_for(self.state.get("mode", MODE)), self.state["target"]):
                raise UpdateBlocked("model_upgrade_revision_unknown")
            c.clean(p, actual)
            c.git(p, "switch", "--detach", sha)
        wheel = self.state["old_wheel" if previous else "new_wheel"]
        c.run(
            [
                str(Path(self.state["primary_project"]) / ".venv/bin/python"),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--force-reinstall",
                wheel["path"],
            ],
            timeout=180,
        )
        c.atomic(
            self.home / "install/manifest.json", {**self.state["manifest"], "code_commit": sha}
        )

    def start_primary(self, previous):
        os.environ["RESEARCH_RESIDENT_REVISION"] = (
            previous_for(self.state.get("mode", MODE)) if previous else self.state["target"]
        )
        ports = self.state["config"]["web_port"], self.state["config"]["runtime_port"]
        with c.fixed_ports(self.manager, ports):
            self.manager._start_installed(self.lease, open_browser=False)

    def start_gateway(self, previous):
        from app.research_web.multiuser.resident_binding import LegacyBinding

        config = dict(self.state["gateway_config"])
        if not previous:
            binding = LegacyBinding.discover(self.home, config["binding"]["primary_user_id"])
            if binding.verify().get("revision") != self.state["target"]:
                raise UpdateBlocked("model_upgrade_binding_unverified")
            config.update(
                revision=self.state["target"],
                binding=json.loads(json.dumps(binding.public_config())),
            )
        if config != gateway_configuration(self.state, previous):
            raise UpdateBlocked("model_upgrade_binding_changed")
        c.atomic(self.server / "resident.json", config)
        self.fence.release_database()
        BirthFence.recover(self.server, expected=self.state["transaction"])
        g.bootstrap(Path(self.state["gateway_plist"]))
        g.wait_health(config, fenced=True)

    def verify(self, previous):
        sha = previous_for(self.state.get("mode", MODE)) if previous else self.state["target"]
        g.verify_primary(self.home, sha)
        g.health(read_json(self.server / "resident.json"), fenced=True)
        remote = request_json(self.state["config"]["private_origin"] + "/api/server/health")
        if remote.get("revision") != sha or remote.get("deployment_fenced") is not True:
            raise UpdateBlocked("model_upgrade_private_health_failed")
        g.preserved(self.home, self.state["before"])
        verify_asset_index(self.home, self.state)
        if model_metadata(self.state["config"]) != self.state["model_before"]:
            raise UpdateBlocked("model_upgrade_credential_metadata_changed")
        if not previous:
            profiles = request_json(
                f"http://127.0.0.1:{self.state['config']['web_port']}/api/research/model-profiles"
            )
            active = [v for v in profiles.get("items", []) if v.get("active") is True]
            if (
                len(active) != 1
                or active[0].get("provider") != self.state["model_before"]["provider"]
                or active[0].get("model") != self.state["model_before"]["model"]
                or active[0].get("credential_configured")
                != self.state["model_before"]["credential_configured"]
            ):
                raise UpdateBlocked("model_upgrade_profile_projection_failed")

    def action(self, name, state):
        if name in ("stop_gateway", "rollback_gateway"):
            self.stop_gateway()
        elif name in ("stop_primary", "rollback_primary"):
            if self.idle() is not True:
                raise MaintenanceBusy("research_active_or_unknown")
            self.manager._stop_locked()
        elif name in ("activate_sources_and_wheel", "restore_sources_and_wheel"):
            self.install(name.startswith("restore"))
        elif name in ("start_primary", "start_previous_primary"):
            self.start_primary("previous" in name)
        elif name in ("start_gateway", "start_previous_gateway"):
            self.start_gateway("previous" in name)
        elif name in ("verify_target", "verify_previous"):
            self.verify(name.endswith("previous"))
        else:
            raise UpdateBlocked("model_upgrade_action_unknown")

    def finish(self, state, result):
        validate_configuration(self.home, state)
        verify_asset_index(self.home, state)
        if result == "deployed":
            candidate = {
                k: state[k]
                for k in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
            }
            candidate["compatibility_review"] = {
                "profile": state.get("mode", MODE),
                "blobs": state["reviewed"],
            }
            c.atomic(self.root / "accepted.json", candidate)
            c.atomic(self.root / "candidate.json", candidate)
            c.atomic(
                self.root / "baseline-reviews" / (state["target"] + ".json"),
                candidate["compatibility_review"],
            )
            c.atomic(self.root / "config.json", {**state["config"], "baseline": state["target"]})
        else:
            c.atomic(self.root / "config.json", state["config"])
            c.atomic(self.root / "accepted.json", state["accepted"])
            c.atomic(self.root / "candidate.json", state["candidate_before"])
            c.atomic(self.root / "quarantine.json", {"sha": state["target"]})
        record = {
            "status": result,
            "target": state["target"],
            "revision": (
                state["target"] if result == "deployed" else previous_for(state.get("mode", MODE))
            ),
            "preserved": True,
        }
        c.atomic(self.server / "run/model-upgrade-result.json", record)
        c.record(self.root, result, deployed=record["revision"])
        log.info("model_upgrade_finished", extra={"result": result})
        (self.root / "transaction.json").unlink()
        c.sync_directory(self.root)
        (self.server / "run/gateway-upgrade.json").unlink()
        c.sync_directory(self.server / "run")
        return record


def operate(home, source=None, *, recovering=False, mode=MODE):
    previous = previous_for(mode)
    if sys.platform != "darwin":
        raise UpdateBlocked("model_upgrade_macos_only")
    root, config = c.configured(home)
    if (
        config.get("artifact") != str(root / "controller.pyz")
        or config.get("artifact_sha256") != CONTROLLER_SHA256
    ):
        raise UpdateBlocked("model_upgrade_controller_unreviewed")
    c.environment(home, config)
    server = home / "server"
    g.private_root(server / "run")
    journal = server / "run/gateway-upgrade.json"
    with ExitStack() as stack:
        stack.enter_context(file_lock(root, "supervisor.lock", exclusive=True))
        stack.enter_context(file_lock(root, "admission.lock", exclusive=True))
        stack.enter_context(file_lock(server / "run", "operator.lock", exclusive=True))
        if recovering:
            if not journal.exists():
                return {"status": "not_required"}
            state = g.read_upgrade_journal(journal)
            validate_state(home, state)
            previous = previous_for(state["mode"])
            # BirthFence journals describe both staged and releasing slots.
            # Its own identity-checked recovery handles these intermediate
            # states, before the activity probe interprets owner records.
            BirthFence.recover(server, expected=state["transaction"])
        else:
            if journal.exists() or (root / "transaction.json").exists():
                raise UpdateBlocked("model_upgrade_recovery_required")
            if source is None:
                raise UpdateBlocked("model_upgrade_source_required")
            target = c.git(source, "rev-parse", "HEAD")
            validate_executor(source, target)
            if (
                c.git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")
                != config["source_common"]
            ):
                raise UpdateBlocked("model_upgrade_source_changed")
            reviewed = review(source, target, mode)
            if c.digest(root / "controller.pyz") != CONTROLLER_SHA256:
                raise UpdateBlocked("model_upgrade_controller_unreviewed")
            with zipfile.ZipFile(root / "controller.pyz") as original:
                if (
                    hashlib.sha256(original.read("resident/controller.py")).hexdigest()
                    != CONTROLLER_MODULE_SHA256
                ):
                    raise UpdateBlocked("model_upgrade_controller_unreviewed")
            verify_serve(config["private_origin"])
            verify_retention(home)
            supervisor_hash = verify_supervisor(home, config)
            github = GitHubEvidence(
                Path(config["gh"]), config["repository"], Path(config["source_common"])
            )
            if github.latest() != target:
                raise UpdateBlocked("resident_master_moved")
            proof = github.qualify(target)
            if (root / "quarantine.json").exists() and read_json(root / "quarantine.json").get(
                "sha"
            ) == target:
                raise UpdateBlocked("resident_failed_candidate_requires_retry")
            primary, gateway = Path(config["project"]), read_json(server / "resident.json")
            for project in (primary, Path(gateway["project"])):
                c.clean(project, previous)
            if (
                gateway["revision"] != previous
                or read_json(home / "install/manifest.json").get("status") != "installed"
                or read_json(home / "install/manifest.json").get("code_commit") != previous
                or read_json(root / "accepted.json").get("target") != previous
            ):
                raise UpdateBlocked("model_upgrade_previous_changed")
            g.verify_primary(home, previous)
            g.no_private_processes(server)
            directory = root / "artifacts" / target
            g.private_root(directory)
            artifact_source = directory / "source"
            if not artifact_source.exists():
                c.git(source, "worktree", "add", "--detach", str(artifact_source), target)
            c.clean(artifact_source, target)
            old_wheel = c.build_wheel(primary, primary, directory / "old" / previous)
            new_wheel = c.build_wheel(primary, artifact_source, directory / "new" / target)
            plist = Path.home() / "Library/LaunchAgents" / (g.LABEL + ".plist")
            pid = g.job_pid()
            signature = g.process(pid) if pid else None
            payload = plistlib.loads(plist.read_bytes())
            python = str(primary / ".venv/bin/python")
            expected_argv = [
                python,
                "-m",
                "app.research_web.multiuser.resident",
                "--root",
                str(server),
            ]
            if (
                payload.get("ProgramArguments") != expected_argv
                or payload.get("WorkingDirectory") != gateway["project"]
                or payload.get("Label") != g.LABEL
                or not signature
                or g.listener_pids() != {pid}
                or g.native_image(pid) != g.native_image(os.getpid())
            ):
                raise UpdateBlocked("model_upgrade_gateway_identity_unknown")
            if Path(sys.prefix).resolve() != (primary / ".venv").resolve():
                raise UpdateBlocked("model_upgrade_interpreter_unknown")
            g.verify_signal_contract()
            g.no_children(pid)
            state = {
                "version": 4,
                "mode": mode,
                "previous": previous,
                "target": target,
                "source": str(artifact_source),
                "reviewed": reviewed,
                "proof": proof,
                "phase": "prepared",
                "transaction": str(uuid4()),
                "config": config,
                "gateway_config": gateway,
                "gateway_command": signature.split(maxsplit=5)[-1],
                "gateway_plist": str(plist),
                "gateway_plist_sha256": c.digest(plist),
                "primary_project": str(primary),
                "gateway_project": gateway["project"],
                "manifest": read_json(home / "install/manifest.json"),
                "model_before": model_metadata(config),
                "accepted": read_json(root / "accepted.json"),
                "candidate_before": read_json(root / "candidate.json"),
                "new_wheel": new_wheel,
                "old_wheel": old_wheel,
                "controller_sha256": c.digest(root / "controller.pyz"),
                "supervisor_plist_sha256": supervisor_hash,
            }
            if mode == ASSET_MODE:
                state["asset_index_before"] = asset_index_snapshot(home)
            for role in ("primary", "gateway"):
                project = Path(state[role + "_project"])
                info = project.stat()
                state[role + "_identity"] = [info.st_dev, info.st_ino]
                state[role + "_repository"] = repository_identity(project, config["repository"])
                c.git(project, "cat-file", "-e", f"{target}^{{commit}}")
            state["recovery"] = install_recovery(home, source, target, python)
            # Exercise the exact recovery identity contract before any fence
            # publication or stop; an apply-only proof cannot protect rollback.
            validate_state(home, state, executor_source=source)
        from app.research_web.service_manager import WebServiceManager

        manager = WebServiceManager(
            project_root=Path(state["primary_project"]),
            data_root=home / "research-web",
            python=str(Path(state["primary_project"]) / ".venv/bin/python"),
            node=config["node"],
            web_port=config["web_port"],
            runtime_port=config["runtime_port"],
        )
        # In the gateway-only crash window a local primary caller could have
        # started work before a durable primary journal existed. Do not create
        # that journal or reservations until this real activity check is idle.
        if Operations(home, state, manager, None, None).idle() is not True:
            return {"status": "recovery_required" if recovering else "deferred"}
        if not recovering:
            # Establish recovery ownership BEFORE BirthFence publishes any
            # durable slot. A crash in __enter__ must never orphan reservations.
            Operations(home, state, manager, None, None).prepare_fence(state)
        elif state["phase"] == "preparing":
            # No service/source effect is possible before checkpoint prepared.
            validate_configuration(home, state)
            g.verify_primary(home, previous)
            g.preserved(home, state["before"])
            verify_asset_index(home, state)
            journal.unlink()
            c.sync_directory(journal.parent)
            return {"status": "aborted_before_signal"}
        fence = stack.enter_context(
            BirthFence(
                server,
                state["gateway_config"]["binding"]["primary_user_id"],
                resume=(server / "run/birth-fence.json").exists(),
                transaction=state["transaction"],
            )
        )
        lease = stack.enter_context(manager._installation_start_scope())
        ops = Operations(home, state, manager, lease, fence)
        if not recovering and (github.latest() != target or github.qualify(target) != proof):
            raise UpdateBlocked("resident_master_or_evidence_moved")
        return execute(ops, state, recovering=recovering)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply", "apply-assets", "recover"))
    parser.add_argument("--home", type=Path, default=Path.home() / ".research-workbench")
    parser.add_argument("--source", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(filename=args.home / "logs/model-upgrade.log", level=logging.INFO)
    try:
        result = operate(
            args.home,
            args.source,
            recovering=args.command == "recover",
            mode=ASSET_MODE if args.command == "apply-assets" else MODE,
        )
        print(json.dumps(result))
        return 0 if result["status"] in {"deployed", "not_required"} else 2
    except MaintenanceBusy:
        print(json.dumps({"status": "deferred", "reason": "research_or_maintenance_busy"}))
        return 2
    except Exception as error:
        log.exception("model_upgrade_blocked")
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": (
                        str(error) if isinstance(error, UpdateBlocked) else type(error).__name__
                    ),
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
