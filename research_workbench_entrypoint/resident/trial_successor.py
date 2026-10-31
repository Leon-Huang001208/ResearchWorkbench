"""Versioned exact-transaction handoff for the existing Native trial operator.

No research engine or independent recovery loop lives here. Mutations require
actual operator exclusions, the existing stopped boundary, and sealed evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import plistlib
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

from . import controller as c
from . import gateway_upgrade as g
from . import trial_discard_backup as backup
from .evidence import UpdateBlocked

log = logging.getLogger(__name__)
MODE = "operator-authorized-trial-retirement-v2"
LEGACY_MODE = "operator-authorized-trial-retirement-v1"
PREDECESSOR = "1529c3189b008b9861a2bee1511f051feefa76eb"
TRANSACTION = "90e13d10-96c2-4115-a062-c79d760b8fdd"
PHASE = "restore_sources_and_wheel"
PREVIOUS = "b800e50366d1a0868372bbf173822976066c143f"
PAYLOAD = "db2ae9a48ceca365852072e622aa6627aa7d0b83"
EXECUTOR_VERSION = "trial-successor-v2"
BUNDLE_LIMIT = 8 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{40}")
IMMUTABLE = (
    "transaction",
    "previous",
    "target",
    "source",
    "config",
    "gateway_config",
    "manifest",
    "model_before",
    "before",
    "asset_index_before",
    "source_transition",
    "new_wheel",
    "old_wheel",
    "accepted",
    "candidate_before",
    "trial_authorization",
    "trial_authorization_sha256",
    "trial_backup_parent",
    "primary_project",
    "gateway_project",
    "primary_identity",
    "gateway_identity",
    "primary_repository",
    "gateway_repository",
    "gateway_plist",
    "gateway_plist_sha256",
    "controller_sha256",
    "supervisor_plist_sha256",
    "proof",
    "reviewed",
)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _private(path, limit=g.JOURNAL_MAX_BYTES):
    try:
        raw, identity = backup._read(path, limit)
    except backup.TrialBackupBlocked as error:
        raise UpdateBlocked("trial_successor_private_record_unreadable") from error
    info = path.lstat()
    if identity["mode"] != 0o600 or info.st_nlink != 1:
        raise UpdateBlocked("trial_successor_private_record_invalid")
    return raw, identity


def publish_bytes(path, raw, *, limit=g.JOURNAL_MAX_BYTES):
    """Atomic no-overwrite publication, durable and exact-byte idempotent."""
    if len(raw) > limit:
        raise UpdateBlocked("trial_successor_record_oversized")
    try:
        with backup._anchored_parent(path.parent) as (fd, _):
            name = ".handoff-" + uuid4().hex
            temporary = False
            try:
                try:
                    os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    backup._write_new(fd, name, raw, 0o600)
                    temporary = True
                    try:
                        os.link(
                            name, path.name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False
                        )
                    except FileExistsError:
                        pass
                    os.unlink(name, dir_fd=fd)
                    temporary = False
                    os.fsync(fd)
                    current, _ = _private(path, limit)
                else:
                    current, _ = _private(path, limit)
                if current != raw:
                    raise UpdateBlocked("trial_successor_record_conflict")
                final = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    os.fsync(final)
                finally:
                    os.close(final)
                os.fsync(fd)
            finally:
                if temporary:
                    os.unlink(name, dir_fd=fd)
                    os.fsync(fd)
        return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    except (OSError, backup.TrialBackupBlocked) as error:
        log.error("trial_successor_publish_failed error_type=%s", type(error).__name__)
        raise UpdateBlocked("trial_successor_record_unsafe") from error


def publish(path, value, *, limit=backup.RECORD_LIMIT):
    return publish_bytes(path, encoded(value), limit=limit)


def reference(ref, expected, limit=backup.RECORD_LIMIT):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or ref["path"] != str(expected):
        raise UpdateBlocked("trial_successor_reference_scope")
    raw, _ = _private(expected, limit)
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise UpdateBlocked("trial_successor_reference_changed")
    value = json.loads(raw)
    if not isinstance(value, dict) or encoded(value) != raw:
        raise UpdateBlocked("trial_successor_record_invalid")
    return value


def check_predecessor(state):
    if (
        any(
            state.get(key) != value
            for key, value in {
                "version": 4,
                "mode": LEGACY_MODE,
                "transaction": TRANSACTION,
                "phase": PHASE,
                "previous": PREVIOUS,
                "target": PAYLOAD,
                "executor_revision": PREDECESSOR,
            }.items()
        )
        or "trial_retirement" in state
        or "trial_terminal_intent" in state
    ):
        raise UpdateBlocked("trial_successor_predecessor_not_exact")


def _directory(home, transaction=TRANSACTION):
    if str(UUID(transaction)) != transaction:
        raise UpdateBlocked("trial_successor_transaction_invalid")
    path = home / "resident/handoffs" / transaction
    g.private_root(path)
    return path


def verify_stage(home, state):
    revision = state.get("executor_revision", "")
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise UpdateBlocked("trial_successor_stage_scope")
    expected = home / "resident/artifacts" / PAYLOAD / "executors" / revision / "stage.json"
    ref = state.get("successor", {}).get("stage", {})
    if ref.get("path") != str(expected):
        raise UpdateBlocked("trial_successor_stage_scope")
    stage = reference(ref, expected)
    if any(
        stage.get(key) != value
        for key, value in {
            "version": 1,
            "mode": MODE,
            "previous": PREVIOUS,
            "payload": PAYLOAD,
            "executor_version": EXECUTOR_VERSION,
            "executor_revision": revision,
            "product_source": state["source"],
            "recovery": state["recovery"],
        }.items()
    ):
        raise UpdateBlocked("trial_successor_stage_changed")
    if (
        stage.get("executor_proof", {}).get("sha") != revision
        or stage.get("payload_proof", {}).get("sha") != PAYLOAD
    ):
        raise UpdateBlocked("trial_successor_stage_unqualified")
    artifact = Path(stage["recovery"]["artifact"])
    if artifact.parent != home / "server/run":
        raise UpdateBlocked("trial_successor_bundle_scope")
    raw, _ = _private(artifact, BUNDLE_LIMIT)
    if hashlib.sha256(raw).hexdigest() != stage["recovery"]["sha256"]:
        raise UpdateBlocked("trial_successor_bundle_changed")
    with zipfile.ZipFile(artifact) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        modules = stage["recovery"]["modules"]
        if manifest != {
            "target": PAYLOAD,
            "modules": modules,
            "product_source": state["source"],
            "executor_revision": revision,
            "executor_version": EXECUTOR_VERSION,
        }:
            raise UpdateBlocked("trial_successor_bundle_changed")
        required = {
            "model_provider_upgrade.py",
            "trial_successor.py",
            "trial_retirement.py",
            "trial_discard_backup.py",
        }
        names = {"manifest.json", "__main__.py", *("resident/" + name for name in modules)}
        if (
            not required <= set(modules)
            or len(modules) > 64
            or set(archive.namelist()) != names
            or len(archive.namelist()) != len(names)
        ):
            raise UpdateBlocked("trial_successor_bundle_changed")
        total = 0
        for name, blob in modules.items():
            if not name.endswith(".py") or "/" in name or "\\" in name or not SHA.fullmatch(blob):
                raise UpdateBlocked("trial_successor_bundle_changed")
            info = archive.getinfo("resident/" + name)
            total += info.file_size
            if info.file_size > backup.RECORD_LIMIT or total > BUNDLE_LIMIT:
                raise UpdateBlocked("trial_successor_bundle_oversized")
            content = archive.read(info)
            if (
                hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
                != blob
            ):
                raise UpdateBlocked("trial_successor_bundle_changed")
        from .model_provider_upgrade import ENTRY

        if archive.read("__main__.py").decode() != ENTRY:
            raise UpdateBlocked("trial_successor_bundle_changed")
    plist = Path(stage["recovery"]["plist"])
    if plist.parent != Path.home() / "Library/LaunchAgents":
        raise UpdateBlocked("trial_successor_job_changed")
    plist_raw, _ = _private(plist, backup.RECORD_LIMIT)
    label = "com.research-workbench.model-recovery." + stage["recovery"]["sha256"][:16]
    payload = plistlib.loads(plist_raw)
    if (
        hashlib.sha256(plist_raw).hexdigest() != stage["recovery"]["plist_sha256"]
        or plist.name != label + ".plist"
        or payload.get("Label") != label
        or payload.get("ProgramArguments")
        != [
            str(Path(state["primary_project"]) / ".venv/bin/python"),
            str(artifact),
            "recover",
            "--home",
            str(home),
        ]
        or payload.get("WorkingDirectory") != str(home)
        or payload.get("StartInterval") != 30
        or payload.get("RunAtLoad") is not True
    ):
        raise UpdateBlocked("trial_successor_job_changed")
    return stage


def stage(home, source, state, github):
    """Seal a qualified small closure; the development checkout is not a runtime dependency."""
    from . import model_provider_upgrade as upgrade

    revision = c.git(source, "rev-parse", "HEAD")
    upgrade.validate_executor(source, revision)
    c.clean(source, revision)
    if github.latest() != revision:
        raise UpdateBlocked("resident_master_moved")
    executor_proof, payload_proof = github.qualify(revision), github.qualify(PAYLOAD)
    directory = home / "resident/artifacts" / PAYLOAD / "executors" / revision
    existing_path = directory / "stage.json"
    repository = upgrade.repository_identity(source, state["config"]["repository"])
    if existing_path.exists() or existing_path.is_symlink():
        raw, _ = _private(existing_path, backup.RECORD_LIMIT)
        value = json.loads(raw)
        if value.get("source_repository") != repository:
            raise UpdateBlocked("trial_successor_stage_repository_changed")
        ref = {"path": str(existing_path), "sha256": hashlib.sha256(raw).hexdigest()}
        candidate = {
            **state,
            "executor_revision": revision,
            "executor_proof": executor_proof,
            "proof": state.get("proof", payload_proof),
            "recovery": value["recovery"],
            "successor": {"stage": ref},
        }
        verify_stage(home, candidate)
        log.info("trial_successor_stage_reused revision=%s", revision)
        return candidate
    recovery = upgrade.install_recovery(
        home,
        source,
        PAYLOAD,
        str(Path(state["primary_project"]) / ".venv/bin/python"),
        executor_revision=revision,
        executor_version=EXECUTOR_VERSION,
        product_source=state["source"],
        activate=False,
    )
    directory = home / "resident/artifacts" / PAYLOAD / "executors" / revision
    g.private_root(directory)
    value = {
        "version": 1,
        "mode": MODE,
        "previous": PREVIOUS,
        "payload": PAYLOAD,
        "executor_version": EXECUTOR_VERSION,
        "executor_revision": revision,
        "product_source": state["source"],
        "recovery": recovery,
        "executor_proof": executor_proof,
        "payload_proof": payload_proof,
        "source_repository": repository,
    }
    ref = publish(directory / "stage.json", value)
    candidate = {
        **state,
        "executor_revision": revision,
        "executor_proof": executor_proof,
        "proof": state.get("proof", payload_proof),
        "recovery": recovery,
        "successor": {"stage": ref},
    }
    verify_stage(home, candidate)
    log.info("trial_successor_stage_verified revision=%s", revision)
    return candidate


def stage_or_resume(ops, source, github, *, expected_sha256, expected_identity):
    """A pre-CAS interruption reuses the original qualified bytes, never rebuilds."""
    from . import model_provider_upgrade as upgrade

    path = _directory(ops.home) / "staged.json"
    if path.exists():
        saved = json.loads(_private(path)[0])
        if (
            saved.get("version") != 1
            or saved.get("predecessor_sha256") != expected_sha256
            or saved.get("predecessor_identity") != list(expected_identity)
        ):
            raise UpdateBlocked("trial_successor_staged_binding_changed")
        candidate = saved["candidate"]
        verify_stage(ops.home, candidate)
        if source is not None:
            c.clean(source, candidate["executor_revision"])
            upgrade.validate_executor(source, candidate["executor_revision"], candidate)
        else:
            upgrade.validate_executor(
                Path(candidate["executor_source"]), candidate["executor_revision"], candidate
            )
        return candidate
    if source is None or github is None:
        raise UpdateBlocked("trial_successor_source_required_for_stage")
    candidate = stage(ops.home, source, ops.state, github)
    candidate["executor_source"] = str(
        ops.root / "artifacts" / PAYLOAD / "executors" / candidate["executor_revision"]
    )
    publish(
        path,
        {
            "version": 1,
            "predecessor_sha256": expected_sha256,
            "predecessor_identity": list(expected_identity),
            "candidate": candidate,
        },
        limit=g.JOURNAL_MAX_BYTES,
    )
    return candidate


def activate_handoff_source(home):
    """Authenticate a staged pyz before importing app code from an older installed wheel."""
    if ".pyz/" not in str(__file__):
        return
    artifact = Path(str(__file__).split(".pyz/", 1)[0] + ".pyz")
    if Path(sys.argv[0]).absolute() != artifact:
        raise UpdateBlocked("trial_successor_executor_invocation_changed")
    raw, _ = _private(home / "server/run/gateway-upgrade.json")
    state = json.loads(raw)
    if state.get("version") == 5 and state.get("mode") == MODE:
        candidate = state
        verify_handoff(home, candidate)
    else:
        check_predecessor(state)
        staged = json.loads(_private(home / "resident/handoffs" / TRANSACTION / "staged.json")[0])
        if staged.get("predecessor_sha256") != hashlib.sha256(raw).hexdigest():
            raise UpdateBlocked("trial_successor_predecessor_changed")
        candidate = staged["candidate"]
        verify_stage(home, candidate)
    if str(artifact) != candidate["recovery"]["artifact"]:
        raise UpdateBlocked("trial_successor_executor_invocation_changed")
    product = home / "resident/artifacts" / PAYLOAD / "source"
    if candidate["source"] != str(product) or product.resolve() != product:
        raise UpdateBlocked("trial_successor_product_source_changed")
    c.clean(product, PAYLOAD)
    for relative in (
        "app/__init__.py",
        "app/research_web/__init__.py",
        "app/research_web/service_manager.py",
    ):
        required = product / relative
        if required.is_symlink() or not required.is_file():
            raise UpdateBlocked("trial_successor_product_dependencies_unavailable")
    sys.path.insert(0, str(product))
    log.info("trial_successor_product_dependencies_activated")


def _supervisor_job():
    result = subprocess.run(
        ["/bin/launchctl", "print", f"gui/{os.getuid()}/{c.LABEL}"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout
    if (
        result.returncode == 113
        and "Could not find service" in result.stderr
        and c.LABEL in result.stderr
    ):
        return None
    raise UpdateBlocked("trial_successor_supervisor_observation_unknown")


def exclusions(ops, *, stopped=True):
    if ops.state.get("mode") == MODE:
        ops.require_confirmed_successor_spawn()
    from . import trial_retirement as trial

    for path in (
        ops.root / "supervisor.lock",
        ops.root / "admission.lock",
        ops.server / "run/operator.lock",
    ):
        trial._held(path)
    ops.manager._assert_installation_scope(ops.lease)
    if (
        ops.fence is None
        or ops.fence.retain is not True
        or ops.fence.db is None
        or ops.fence.transaction != ops.state["transaction"]
    ):
        raise UpdateBlocked("trial_successor_exclusion_required")
    if stopped:
        trial.stopped(ops)


def _verify_legacy(home, state):
    check_predecessor(state)
    source = Path(state["executor_source"])
    if source != home / "resident/artifacts" / PAYLOAD / "executor":
        raise UpdateBlocked("trial_successor_predecessor_source_changed")
    c.clean(source, PREDECESSOR)
    artifact = Path(state["recovery"]["artifact"])
    if artifact.parent != home / "server/run" or c.digest(artifact) != state["recovery"]["sha256"]:
        raise UpdateBlocked("trial_successor_predecessor_artifact_changed")
    with zipfile.ZipFile(artifact) as archive:
        if json.loads(archive.read("manifest.json")) != {
            "target": PAYLOAD,
            "modules": state["recovery"]["modules"],
            "source": str(source),
            "executor_revision": PREDECESSOR,
        }:
            raise UpdateBlocked("trial_successor_predecessor_artifact_changed")
        if g.module_blobs(source, PREDECESSOR) != state["recovery"]["modules"]:
            raise UpdateBlocked("trial_successor_predecessor_artifact_changed")
        for name in state["recovery"]["modules"]:
            if archive.read("resident/" + name) != g.git_bytes(source, PREDECESSOR, name):
                raise UpdateBlocked("trial_successor_predecessor_artifact_changed")
    from . import model_provider_upgrade as upgrade

    upgrade.validate_configuration(home, state)


def _job(label):
    result = subprocess.run(
        ["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout
    if (
        result.returncode == 113
        and "Could not find service" in result.stderr
        and label in result.stderr
    ):
        return None
    raise UpdateBlocked("trial_successor_job_observation_unknown")


def _quiesce_job(
    ops,
    *,
    kind,
    plist,
    expected_hash,
    expected_argv,
    expected_journal_sha256,
    expected_process=None,
    expected_working_directory=None,
):
    from research_workbench_entrypoint.web_contract import probe_process

    exclusions(ops, stopped=False)
    content, _ = _private(plist, backup.RECORD_LIMIT)
    payload = plistlib.loads(content)
    label = payload.get("Label")
    working_directory = expected_working_directory or str(ops.home)
    if (
        hashlib.sha256(content).hexdigest() != expected_hash
        or not isinstance(label, str)
        or payload.get("ProgramArguments") != expected_argv
        or payload.get("WorkingDirectory") != working_directory
    ):
        raise UpdateBlocked("trial_successor_job_identity_unknown")
    transaction = ops.state["transaction"]
    directory = _directory(ops.home, transaction)
    intent_path = directory / (kind + "-stop-intent.json")
    job = _job(label)
    if intent_path.exists():
        intent = json.loads(_private(intent_path, backup.RECORD_LIMIT)[0])
        pid = intent.get("pid")
        if (
            intent.get("transaction") != transaction
            or intent.get("predecessor_sha256") != expected_journal_sha256
            or intent.get("plist_sha256") != expected_hash
            or intent.get("label") != label
            or job is not None
            or (pid is not None and probe_process(pid).state != "missing")
        ):
            raise UpdateBlocked("trial_successor_job_stop_unknown")
    else:
        pid = None
        observed = None
        signature = None
        if job is not None:
            fields = dict(
                re.findall(r"^\s*(path|program|working directory) = (.+)$", job, re.MULTILINE)
            )
            if fields != {
                "path": str(plist),
                "program": expected_argv[0],
                "working directory": working_directory,
            }:
                raise UpdateBlocked("trial_successor_job_identity_unknown")
            match = re.search(r"^\s*pid = ([0-9]+)$", job, re.MULTILINE)
            if match:
                pid = int(match[1])
                observed = probe_process(pid)
                if (
                    pid == os.getpid()
                    or observed.state != "alive"
                    or observed.issue is not None
                    or observed.started_at is None
                    or (observed.argv or ())[1:] != tuple(expected_argv[1:])
                    or g.native_image(pid) != g.native_image(os.getpid())
                    or int(g.run(["/bin/ps", "-p", str(pid), "-o", "uid="]).strip()) != os.getuid()
                ):
                    raise UpdateBlocked("trial_successor_job_identity_unknown")
                g.no_children(pid)
                signature = g.process(pid)
                if expected_process is not None and (
                    pid != expected_process.get("pid")
                    or observed.started_at != expected_process.get("birth")
                    or list(observed.argv) != expected_process.get("argv")
                    or signature != expected_process.get("signature")
                    or str(g.native_image(pid)) != expected_process.get("image")
                    or expected_process.get("uid") != os.getuid()
                ):
                    raise UpdateBlocked("trial_successor_job_generation_unknown")
                if not signature:
                    raise UpdateBlocked("trial_successor_job_identity_unknown")
        intent = {
            "version": 1,
            "transaction": transaction,
            "predecessor_sha256": expected_journal_sha256,
            "plist_sha256": expected_hash,
            "label": label,
            "pid": pid,
            "birth": observed.started_at if observed is not None else None,
            "argv": list(observed.argv) if observed is not None else expected_argv,
            "signature": signature,
            "observation": "loaded" if job is not None else "already_absent",
        }
        publish(intent_path, intent)
        if job is not None:
            if pid is not None and (probe_process(pid) != observed or g.process(pid) != signature):
                raise UpdateBlocked("trial_successor_job_identity_changed")
            g.run(["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{label}"])
            deadline = time.monotonic() + 90
            while _job(label) is not None or (
                pid is not None and probe_process(pid).state != "missing"
            ):
                if time.monotonic() >= deadline:
                    raise UpdateBlocked("trial_successor_job_stop_unknown")
                time.sleep(0.1)
    return publish(
        directory / (kind + "-job-quiesced.json"),
        {
            "version": 1,
            "transaction": transaction,
            "predecessor_sha256": expected_journal_sha256,
            "plist_sha256": expected_hash,
            "intent": {
                "path": str(intent_path),
                "sha256": hashlib.sha256(_private(intent_path, backup.RECORD_LIMIT)[0]).hexdigest(),
            },
            "label": label,
            "status": "quiesced",
        },
    )


def quiesce_supervisor(ops, expected_journal_sha256):
    """Fence both old automated recovery actors, recovery job first, without replay."""
    exclusions(ops, stopped=False)
    check_predecessor(ops.state)
    raw, _ = _private(ops.server / "run/gateway-upgrade.json")
    if hashlib.sha256(raw).hexdigest() != expected_journal_sha256:
        raise UpdateBlocked("trial_successor_predecessor_changed")
    old = ops.state["recovery"]
    old_argv = [
        str(Path(ops.state["primary_project"]) / ".venv/bin/python"),
        old["artifact"],
        "recover",
        "--home",
        str(ops.home),
    ]
    retired_job = _quiesce_job(
        ops,
        kind="legacy-recovery",
        plist=Path(old["plist"]),
        expected_hash=old["plist_sha256"],
        expected_argv=old_argv,
        expected_journal_sha256=expected_journal_sha256,
    )
    plist = Path.home() / "Library/LaunchAgents" / (c.LABEL + ".plist")
    argv = [
        ops.state["config"]["python"],
        str(ops.home / "resident/controller.pyz"),
        "tick",
        "--home",
        str(ops.home),
    ]
    scheduler = _quiesce_job(
        ops,
        kind="supervisor",
        plist=plist,
        expected_hash=ops.state["supervisor_plist_sha256"],
        expected_argv=argv,
        expected_journal_sha256=expected_journal_sha256,
    )
    return publish(
        _directory(ops.home) / "supervisor-quiesced.json",
        {
            "version": 1,
            "transaction": TRANSACTION,
            "predecessor_sha256": expected_journal_sha256,
            "plist_sha256": ops.state["supervisor_plist_sha256"],
            "scheduler": scheduler,
            "legacy_recovery": retired_job,
            "status": "quiesced",
        },
    )


def drain_primary(ops, expected_journal_sha256, *, fresh=False):
    """Current managed PIDs get one durable single-PID TERM, never original-map edits."""
    from app.research_web.service_manager import _GracefulStopIdentity
    from research_workbench_entrypoint.web_contract import probe_process

    from . import model_provider_upgrade as upgrade

    exclusions(ops, stopped=False)
    if fresh:
        _fresh_context(ops.home, ops.state)
    else:
        check_predecessor(ops.state)
    transaction = ops.state["transaction"]
    directory = _directory(ops.home, transaction)
    processes = {process.role: process for process in ops.manager._processes()}
    if set(processes) != {"web", "runtime"}:
        raise UpdateBlocked("trial_successor_managed_scope_unknown")
    for role in ("web", "runtime"):
        process = processes[role]
        expected_process = ops.state.get("trial_processes", {}).get(role) if fresh else None
        if fresh and not isinstance(expected_process, dict):
            raise UpdateBlocked("trial_successor_managed_generation_unknown")
        generation = "-" + digest(expected_process)[:24] if fresh else ""
        path = directory / ("primary-stop-" + role + generation + ".json")
        attempted = path.exists()
        if attempted:
            intent = json.loads(_private(path, backup.RECORD_LIMIT)[0])
            if (
                intent.get("transaction") != transaction
                or intent.get("predecessor_sha256") != expected_journal_sha256
                or intent.get("role") != role
                or intent.get("port") != process.port
            ):
                raise UpdateBlocked("trial_successor_stop_intent_changed")
            identity = _GracefulStopIdentity(
                role, intent["port"], intent["pid"], intent["birth"], tuple(intent["argv"])
            )
        else:
            probe = ops.manager._probe_service(process)
            if probe.process == "missing" and probe.port_state == "closed":
                if fresh and probe_process(expected_process["pid"]).state != "missing":
                    raise UpdateBlocked("trial_successor_managed_generation_unknown")
                ops.manager._normalize_absent_probe(process, probe, clear_runtime_auth=False)
                continue
            identity = ops.manager._graceful_stop_identity(process)
            if fresh and (
                identity.pid != expected_process.get("pid")
                or identity.started_at != expected_process.get("birth")
                or list(identity.argv) != expected_process.get("argv")
            ):
                raise UpdateBlocked("trial_successor_managed_generation_unknown")
            pgid = os.getpgid(identity.pid)
            image = g.native_image(identity.pid)
            expected_image = (
                g.native_image(os.getpid())
                if role == "web"
                else Path(ops.state["config"]["node"]).resolve()
            )
            signature = g.process(identity.pid)
            g.no_children(identity.pid)
            if (
                pgid != identity.pid
                or image != expected_image
                or not signature
                or int(g.run(["/bin/ps", "-p", str(identity.pid), "-o", "uid="]).strip())
                != os.getuid()
            ):
                raise UpdateBlocked("trial_successor_managed_identity_unknown")
            intent = {
                "version": 1,
                "transaction": transaction,
                "predecessor_sha256": expected_journal_sha256,
                "role": role,
                "port": identity.port,
                "pid": identity.pid,
                "birth": identity.started_at,
                "argv": list(identity.argv),
                "pgid": pgid,
                "uid": os.getuid(),
                "image": str(image),
                "signature": signature,
                "outcome": "USER_AUTHORIZED_TRIAL_ABORT",
            }

        def persist(intent=intent, path=path, identity=identity):
            exclusions(ops, stopped=False)
            observed = probe_process(identity.pid)
            if (
                observed.state != "alive"
                or observed.started_at != identity.started_at
                or observed.argv != identity.argv
                or os.getpgid(identity.pid) != intent["pgid"]
                or g.native_image(identity.pid) != Path(intent["image"])
                or g.process(identity.pid) != intent["signature"]
            ):
                raise UpdateBlocked("trial_successor_managed_identity_changed")
            g.no_children(identity.pid)
            publish(path, intent)

        ops.manager._graceful_stop_owned_once(
            process,
            identity,
            lease=ops.lease,
            persist_signal_intent=persist,
            signal_already_attempted=attempted,
            timeout=90,
        )
        probe = ops.manager._probe_service(process)
        if probe.process != "missing" or probe.port_state != "closed":
            raise UpdateBlocked("trial_successor_managed_drain_pending")
        ops.manager._normalize_absent_probe(process, probe, clear_runtime_auth=False)
    deadline = time.monotonic() + 90
    while not upgrade.ports_are_free(
        (ops.state["config"]["web_port"], ops.state["config"]["runtime_port"])
    ):
        if time.monotonic() >= deadline:
            raise UpdateBlocked("trial_successor_bind_release_pending")
        time.sleep(0.1)
    exclusions(ops)
    log.warning("trial_successor_primary_retired outcome=USER_AUTHORIZED_TRIAL_ABORT")


def commit(ops, candidate, *, expected_journal_sha256, expected_journal_identity, quiesced):
    """CAS the one frozen predecessor while its original exclusions remain held."""
    exclusions(ops)
    old = ops.state
    _verify_legacy(ops.home, old)
    path = ops.server / "run/gateway-upgrade.json"
    raw, identity = _private(path)
    if (
        hashlib.sha256(raw).hexdigest() != expected_journal_sha256
        or [identity["dev"], identity["ino"]] != list(expected_journal_identity)
        or json.loads(raw) != old
    ):
        raise UpdateBlocked("trial_successor_predecessor_changed")
    verify_stage(ops.home, candidate)
    directory = _directory(ops.home)
    quiet = reference(quiesced, directory / "supervisor-quiesced.json")
    if (
        quiet.get("transaction") != TRANSACTION
        or quiet.get("predecessor_sha256") != expected_journal_sha256
        or quiet.get("status") != "quiesced"
        or _supervisor_job() is not None
    ):
        raise UpdateBlocked("trial_successor_supervisor_not_quiesced")
    for key in IMMUTABLE:
        if candidate.get(key) != old.get(key):
            raise UpdateBlocked("trial_successor_scope_changed")
    previous = publish_bytes(directory / "predecessor.json", raw)
    new = copy.deepcopy(candidate)
    new.update(version=5, mode=MODE)
    new["successor"].update(origin="handoff", observe_only=True)
    initial = copy.deepcopy(new)
    intent = publish(
        directory / "intent.json",
        {
            "version": 1,
            "transaction": TRANSACTION,
            "predecessor": previous,
            "predecessor_identity": identity,
            "supervisor": quiesced,
            "initial": initial,
        },
        limit=g.JOURNAL_MAX_BYTES,
    )
    new["successor"]["handoff"] = intent
    current, current_identity = _private(path)
    if current != raw or current_identity != identity:
        raise UpdateBlocked("trial_successor_predecessor_changed")
    ensure_recovery_job(ops.home, new)
    g.write_upgrade_journal(path, new)
    ops.state.clear()
    ops.state.update(new)
    log.warning("trial_successor_journal_committed transaction=%s", TRANSACTION)
    return new


def verify_handoff(home, state):
    stage_value = verify_stage(home, state)
    if (
        state.get("version") != 5
        or state.get("mode") != MODE
        or state.get("previous") != PREVIOUS
        or state.get("target") != PAYLOAD
    ):
        raise UpdateBlocked("trial_successor_state_invalid")
    succession = state["successor"]
    if succession.get("origin") == "fresh_apply":
        from . import model_provider_upgrade as upgrade

        validator = getattr(upgrade, "verify_trial_successor_fresh", None)
        if not callable(validator):
            raise UpdateBlocked("trial_successor_fresh_apply_not_admitted")
        validator(home, state, stage_value)
        return stage_value
    if succession.get("origin") != "handoff" or state.get("transaction") != TRANSACTION:
        raise UpdateBlocked("trial_successor_handoff_scope")
    directory = home / "resident/handoffs" / TRANSACTION
    intent = reference(succession["handoff"], directory / "intent.json", g.JOURNAL_MAX_BYTES)
    raw, _ = _private(directory / "predecessor.json")
    if (
        intent["predecessor"]["path"] != str(directory / "predecessor.json")
        or hashlib.sha256(raw).hexdigest() != intent["predecessor"]["sha256"]
    ):
        raise UpdateBlocked("trial_successor_predecessor_changed")
    old = json.loads(raw)
    check_predecessor(old)
    initial = intent["initial"]
    for key in (*IMMUTABLE, "executor_revision", "recovery"):
        if state.get(key) != initial.get(key):
            raise UpdateBlocked("trial_successor_scope_changed")
    if state["successor"]["stage"] != initial["successor"]["stage"]:
        raise UpdateBlocked("trial_successor_stage_changed")
    quiet = reference(intent["supervisor"], directory / "supervisor-quiesced.json")
    if (
        quiet.get("transaction") != TRANSACTION
        or quiet.get("predecessor_sha256") != intent["predecessor"]["sha256"]
    ):
        raise UpdateBlocked("trial_successor_supervisor_changed")
    return stage_value


def observe_stopped(ops):
    from research_workbench_entrypoint.web_contract import probe_process

    verify_handoff(ops.home, ops.state)
    exclusions(ops)
    for identity in ops.state.get("trial_processes", {}).values():
        if probe_process(identity["pid"]).state != "missing":
            raise UpdateBlocked("trial_successor_original_pid_not_retired")


def _fresh_shape(state):
    if (
        state.get("mode") != MODE
        or state.get("successor", {}).get("origin") != "fresh_apply"
        or state.get("transaction") == TRANSACTION
        or str(UUID(state.get("transaction", ""))) != state.get("transaction")
    ):
        raise UpdateBlocked("trial_successor_fresh_context_invalid")
    return {
        "version": 1,
        "transaction": state["transaction"],
        "mode": MODE,
        "previous": PREVIOUS,
        "payload": PAYLOAD,
        "stage": state["successor"]["stage"],
        "prior_receipt": state["successor"]["prior_receipt"],
        "authorization_sha256": state["trial_authorization_sha256"],
        "quarantine_sha256": state["successor"]["quarantine_sha256"],
        "config": state["config"],
        "supervisor_plist_sha256": state["supervisor_plist_sha256"],
        "gateway_plist_sha256": state["gateway_plist_sha256"],
    }


def _fresh_context(home, state, *, create=True):
    verify_handoff(home, state)
    value = _fresh_shape(state)
    directory = home / "resident/handoffs" / state["transaction"]
    path = directory / "fresh-context.json"
    if create:
        g.private_root(directory)
        return publish(path, value)
    raw, _ = _private(path, backup.RECORD_LIMIT)
    if json.loads(raw) != value:
        raise UpdateBlocked("trial_successor_fresh_context_changed")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def _fresh_supervisor_observation(home, state):
    from . import model_provider_upgrade as upgrade

    directory = home / "resident/handoffs" / state["transaction"]
    context_path = directory / "fresh-context.json"
    if not context_path.exists() and not context_path.is_symlink():
        if upgrade.verify_supervisor(home, state["config"]) != state["supervisor_plist_sha256"]:
            raise UpdateBlocked("trial_successor_supervisor_changed")
        return
    context = _fresh_context(home, state, create=False)
    intent_path = directory / "fresh-supervisor-stop-intent.json"
    job = _supervisor_job()
    if job is None:
        raw, _ = _private(intent_path, backup.RECORD_LIMIT)
        intent = json.loads(raw)
        if (
            intent.get("transaction") != state["transaction"]
            or intent.get("predecessor_sha256") != context["sha256"]
            or intent.get("plist_sha256") != state["supervisor_plist_sha256"]
            or intent.get("label") != c.LABEL
        ):
            raise UpdateBlocked("trial_successor_fresh_supervisor_intent_changed")
        plist = Path.home() / "Library/LaunchAgents" / (c.LABEL + ".plist")
        if c.digest(plist) != state["supervisor_plist_sha256"]:
            raise UpdateBlocked("trial_successor_supervisor_changed")
        return
    if (
        intent_path.exists()
        and state.get("phase") not in {"stop_gateway", "rollback_gateway"}
        and not (
            (directory / "supervisor-restore-intent.json").is_file()
            and not (home / "resident/transaction.json").exists()
        )
    ):
        raise UpdateBlocked("trial_successor_supervisor_unexpectedly_active")
    if upgrade.verify_supervisor(home, state["config"]) != state["supervisor_plist_sha256"]:
        raise UpdateBlocked("trial_successor_supervisor_changed")


def stop_fresh_gateway(ops):
    """Quiesce the legacy scheduler, then boot out the one recorded gateway generation."""
    exclusions(ops, stopped=False)
    context = _fresh_context(ops.home, ops.state)
    ensure_recovery_job(ops.home, ops.state)
    plist = Path.home() / "Library/LaunchAgents" / (c.LABEL + ".plist")
    argv = [
        ops.state["config"]["python"],
        str(ops.home / "resident/controller.pyz"),
        "tick",
        "--home",
        str(ops.home),
    ]
    _quiesce_job(
        ops,
        kind="fresh-supervisor",
        plist=plist,
        expected_hash=ops.state["supervisor_plist_sha256"],
        expected_argv=argv,
        expected_journal_sha256=context["sha256"],
    )
    known = ops.state.get("trial_processes", {}).get("gateway")
    if not isinstance(known, dict):
        raise UpdateBlocked("trial_successor_gateway_generation_unknown")
    gateway = Path(ops.state["gateway_plist"])
    argv = [
        str(Path(ops.state["primary_project"]) / ".venv/bin/python"),
        "-m",
        "app.research_web.multiuser.resident",
        "--root",
        str(ops.server),
    ]
    _quiesce_job(
        ops,
        kind="fresh-gateway-" + digest(known)[:24],
        plist=gateway,
        expected_hash=ops.state["gateway_plist_sha256"],
        expected_argv=argv,
        expected_journal_sha256=context["sha256"],
        expected_process=known,
        expected_working_directory=ops.state["gateway_project"],
    )
    from . import model_provider_upgrade as upgrade

    deadline = time.monotonic() + 90
    while g.job_state() is not None or g.listener_pids() or not upgrade.ports_are_free((8089,)):
        if time.monotonic() >= deadline:
            raise UpdateBlocked("trial_successor_gateway_drain_pending")
        time.sleep(0.1)
    log.warning("trial_successor_fresh_gateway_retired outcome=USER_AUTHORIZED_TRIAL_ABORT")


def stop_fresh_primary(ops):
    exclusions(ops, stopped=False)
    context = _fresh_context(ops.home, ops.state)
    if _supervisor_job() is not None or g.job_state() is not None or g.listener_pids():
        raise UpdateBlocked("trial_successor_fresh_gateway_not_retired")
    drain_primary(ops, context["sha256"], fresh=True)


def verify_supervisor_boundary(home, state):
    from . import model_provider_upgrade as upgrade

    verify_handoff(home, state)
    if state["successor"].get("origin") == "fresh_apply":
        _fresh_supervisor_observation(home, state)
        return
    directory = home / "resident/handoffs" / TRANSACTION
    intent = reference(
        state["successor"]["handoff"], directory / "intent.json", g.JOURNAL_MAX_BYTES
    )
    quiet = reference(intent["supervisor"], directory / "supervisor-quiesced.json")
    plist = Path.home() / "Library/LaunchAgents" / (c.LABEL + ".plist")
    if (
        c.digest(plist) != state["supervisor_plist_sha256"]
        or quiet["plist_sha256"] != state["supervisor_plist_sha256"]
    ):
        raise UpdateBlocked("trial_successor_supervisor_changed")
    if _supervisor_job() is not None:
        # A terminal restore may have completed immediately before a crash.
        if (
            not (directory / "supervisor-restore-intent.json").is_file()
            or (home / "resident/transaction.json").exists()
        ):
            raise UpdateBlocked("trial_successor_supervisor_unexpectedly_active")
        if upgrade.verify_supervisor(home, state["config"]) != state["supervisor_plist_sha256"]:
            raise UpdateBlocked("trial_successor_supervisor_changed")


def ensure_recovery_job(home, state):
    verify_stage(home, state)
    recovery = state["recovery"]
    plist = Path(recovery["plist"])
    label = plistlib.loads(plist.read_bytes())["Label"]
    try:
        g.run(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])
    except UpdateBlocked:
        observed = g.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"])
        if str(plist) not in observed or recovery["artifact"] not in observed:
            raise UpdateBlocked("trial_successor_recovery_job_unknown") from None


def accept(ops):
    """Reobserve only; keep the legacy scheduler quiesced until root-journal removal."""
    ops.require_confirmed_successor_spawn()
    verify_handoff(ops.home, ops.state)
    if ops.state["successor"].get("origin") != "handoff":
        return
    if ops.state["successor"].get("observe_only") is not True:
        exclusions(ops, stopped=False)
        verify_supervisor_boundary(ops.home, ops.state)
        return
    if ops.state.get("phase") not in {
        "rollback_gateway",
        "rollback_primary",
        "restore_sources_and_wheel",
    }:
        raise UpdateBlocked("trial_successor_start_identity_unconfirmed")
    exclusions(ops)
    observe_stopped(ops)
    verify_supervisor_boundary(ops.home, ops.state)
    ensure_recovery_job(ops.home, ops.state)
    directory = _directory(ops.home)
    accepted = publish(
        directory / "accepted.json",
        {
            "version": 1,
            "transaction": TRANSACTION,
            "handoff": ops.state["successor"]["handoff"],
            "stage": ops.state["successor"]["stage"],
            "supervisor_plist_sha256": ops.state["supervisor_plist_sha256"],
        },
    )
    ops.state["successor"]["accepted"] = accepted
    ops.checkpoint(ops.state, ops.state["phase"])
    log.info("trial_successor_accepted transaction=%s", TRANSACTION)


def restore_supervisor(ops):
    """Restore the old scheduler only after its root recover trigger is gone."""
    from . import model_provider_upgrade as upgrade

    state = ops.state
    verify_handoff(ops.home, state)
    if state["successor"]["origin"] == "fresh_apply":
        _fresh_context(ops.home, state, create=False)
    elif state["successor"]["origin"] != "handoff":
        raise UpdateBlocked("trial_successor_restore_scope")
    if (ops.root / "transaction.json").exists():
        raise UpdateBlocked("trial_successor_root_recovery_trigger_present")
    directory = _directory(ops.home, state["transaction"])
    plist = Path.home() / "Library/LaunchAgents" / (c.LABEL + ".plist")
    expected = state["supervisor_plist_sha256"]
    if c.digest(plist) != expected:
        raise UpdateBlocked("trial_successor_supervisor_changed")
    restore = directory / "supervisor-restore-intent.json"
    if _supervisor_job() is None:
        if restore.exists():
            raise UpdateBlocked("trial_successor_supervisor_restore_unknown")
        publish(
            restore, {"version": 1, "transaction": state["transaction"], "plist_sha256": expected}
        )
        g.run(["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])
    if upgrade.verify_supervisor(ops.home, state["config"]) != expected:
        raise UpdateBlocked("trial_successor_supervisor_changed")
    publish(
        directory / "supervisor-restored.json",
        {"version": 1, "transaction": state["transaction"], "plist_sha256": expected},
    )
    log.info("trial_successor_supervisor_restored transaction=%s", state["transaction"])
