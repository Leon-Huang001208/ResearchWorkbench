"""Exact predecessor and immutable handoff evidence, using synthetic files only."""

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_trial_retirement import stopped_home

from research_workbench_entrypoint.resident import trial_retirement as trial
from research_workbench_entrypoint.resident import trial_successor as successor
from research_workbench_entrypoint.resident.evidence import UpdateBlocked

__all__ = ["stopped_home"]


def predecessor():
    return {
        "version": 4,
        "mode": successor.LEGACY_MODE,
        "transaction": successor.TRANSACTION,
        "phase": successor.PHASE,
        "previous": successor.PREVIOUS,
        "target": successor.PAYLOAD,
        "executor_revision": successor.PREDECESSOR,
        "trial_authorization": {"profile": successor.LEGACY_MODE},
        "trial_authorization_sha256": "a" * 64,
    }


def test_exact_predecessor_contract():
    successor.check_predecessor(predecessor())


@pytest.mark.parametrize(
    "field,value",
    [
        ("transaction", "00000000-0000-0000-0000-000000000000"),
        ("phase", "stop_primary"),
        ("executor_revision", "a" * 40),
        ("mode", successor.MODE),
        ("version", 5),
        ("target", "b" * 40),
        ("previous", "c" * 40),
        ("trial_retirement", {}),
    ],
)
def test_other_predecessor_or_effects_are_not_adopted(field, value):
    state = predecessor()
    state[field] = value
    with pytest.raises(UpdateBlocked):
        successor.check_predecessor(state)


def test_private_publication_is_exact_no_overwrite_and_no_symlinks(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    target = root / "receipt.json"
    value = {"transaction": successor.TRANSACTION, "proof": "frozen"}
    first = successor.publish(target, value)
    inode = target.stat().st_ino
    assert successor.publish(target, value) == first
    assert target.stat().st_ino == inode
    with pytest.raises(UpdateBlocked):
        successor.publish(target, {**value, "proof": "changed"})
    assert json.loads(target.read_bytes()) == value
    assert first["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


def test_conflicting_symlink_never_overwritten(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"protected")
    (root / "receipt.json").symlink_to(foreign)
    with pytest.raises(UpdateBlocked):
        successor.publish(root / "receipt.json", {"safe": True})
    assert foreign.read_bytes() == b"protected"


def test_stage_reference_cannot_escape_fixed_executor_namespace(tmp_path):
    state = predecessor()
    state.update(
        version=5,
        mode=successor.MODE,
        executor_revision="e" * 40,
        successor={"stage": {"path": str(tmp_path / "foreign"), "sha256": "a" * 64}},
    )
    with pytest.raises(UpdateBlocked, match="stage_scope"):
        successor.verify_stage(tmp_path, state)


@pytest.fixture
def successor_home(stopped_home, monkeypatch):
    import plistlib
    import zipfile

    from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade
    from research_workbench_entrypoint.resident.gateway_fence import BirthFence

    f = stopped_home
    ops = f.ops
    ops.home.chmod(0o700)
    ops.server.chmod(0o700)
    (ops.server / "accounts.sqlite3").chmod(0o600)
    state = ops.state
    state.update(predecessor())
    state.update(
        source=str(ops.root / "artifacts" / successor.PAYLOAD / "source"),
        primary_project=str(ops.home / "release"),
        executor_source=str(ops.root / "artifacts" / successor.PAYLOAD / "executor"),
        recovery={"artifact": "original immutable artifact"},
        supervisor_plist_sha256="a" * 64,
    )
    ops.checkpoint(state, successor.PHASE)
    old_raw = (ops.server / "run/gateway-upgrade.json").read_bytes()
    raw_hash = hashlib.sha256(old_raw).hexdigest()
    info = (ops.server / "run/gateway-upgrade.json").stat()
    identity = [info.st_dev, info.st_ino]
    system_home = ops.home / "fixture-system-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: system_home))
    revision = "e" * 40
    modules = {
        name: b"# Synthetic module bytes, never executed.\n"
        for name in (
            "model_provider_upgrade.py",
            "trial_successor.py",
            "trial_retirement.py",
            "trial_discard_backup.py",
        )
    }
    blobs = {
        name: hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        for name, raw in modules.items()
    }
    artifact = ops.server / "run/synthetic-reviewed-successor.pyz"
    manifest = {
        "target": successor.PAYLOAD,
        "modules": blobs,
        "product_source": state["source"],
        "executor_revision": revision,
        "executor_version": successor.EXECUTOR_VERSION,
    }
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("__main__.py", upgrade.ENTRY)
        for name, raw in modules.items():
            archive.writestr("resident/" + name, raw)
    artifact.chmod(0o600)
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    label = "com.research-workbench.model-recovery." + artifact_hash[:16]
    plist = system_home / "Library/LaunchAgents" / (label + ".plist")
    plist.parent.mkdir(parents=True, mode=0o700)
    plist.write_bytes(
        plistlib.dumps(
            {
                "Label": label,
                "ProgramArguments": [
                    str(Path(state["primary_project"]) / ".venv/bin/python"),
                    str(artifact),
                    "recover",
                    "--home",
                    str(ops.home),
                ],
                "WorkingDirectory": str(ops.home),
                "RunAtLoad": True,
                "StartInterval": 30,
            }
        )
    )
    plist.chmod(0o600)
    recovery = {
        "artifact": str(artifact),
        "sha256": artifact_hash,
        "plist": str(plist),
        "plist_sha256": hashlib.sha256(plist.read_bytes()).hexdigest(),
        "modules": blobs,
    }
    candidate = copy.deepcopy(state)
    candidate.update(
        executor_revision=revision,
        executor_source=str(ops.root / "artifacts" / successor.PAYLOAD / "executors" / revision),
        recovery=recovery,
    )
    stage_path = Path(candidate["executor_source"]) / "stage.json"
    stage_path.parent.mkdir(parents=True, mode=0o700)
    stage = {
        "version": 1,
        "mode": successor.MODE,
        "previous": successor.PREVIOUS,
        "payload": successor.PAYLOAD,
        "executor_version": successor.EXECUTOR_VERSION,
        "executor_revision": revision,
        "product_source": state["source"],
        "recovery": recovery,
        "executor_proof": {"sha": revision},
        "payload_proof": {"sha": successor.PAYLOAD},
    }
    candidate["successor"] = {"stage": successor.publish(stage_path, stage)}
    directory = successor._directory(ops.home)
    quiet = successor.publish(
        directory / "supervisor-quiesced.json",
        {
            "version": 1,
            "transaction": successor.TRANSACTION,
            "predecessor_sha256": raw_hash,
            "status": "quiesced",
            "plist_sha256": state["supervisor_plist_sha256"],
        },
    )
    monkeypatch.setattr(successor, "_supervisor_job", lambda: None)
    monkeypatch.setattr(
        successor, "_verify_legacy", lambda home, value: successor.check_predecessor(value)
    )
    events = []
    monkeypatch.setattr(successor.g, "run", lambda argv, **kwargs: events.append(tuple(argv)) or "")
    primary = json.loads((ops.server / "resident.json").read_bytes())["binding"]["primary_user_id"]
    with BirthFence(ops.server, primary, transaction=state["transaction"]) as fence:
        fence.retain = True
        ops.fence = fence
        yield SimpleNamespace(
            f=f,
            ops=ops,
            candidate=candidate,
            quiet=quiet,
            old_raw=old_raw,
            raw_hash=raw_hash,
            identity=identity,
            events=events,
            stage=stage,
            artifact=artifact,
            stage_path=stage_path,
        )
        fence.retain = False


def test_real_commit_preserves_predecessor_and_authenticates_small_bundle(successor_home):
    f = successor_home
    successor.commit(
        f.ops,
        f.candidate,
        expected_journal_sha256=f.raw_hash,
        expected_journal_identity=f.identity,
        quiesced=f.quiet,
    )
    state = f.ops.state
    assert state["version"] == 5 and state["mode"] == successor.MODE
    assert state["trial_authorization"]["profile"] == successor.LEGACY_MODE
    assert state["successor"]["observe_only"] is True
    assert (
        f.ops.root / "handoffs" / successor.TRANSACTION / "predecessor.json"
    ).read_bytes() == f.old_raw
    successor.verify_handoff(f.ops.home, state)
    assert len(f.events) == 1 and f.events[0][1] == "bootstrap"
    assert "trial_retirement" not in state


@pytest.mark.parametrize("damage", ["sha", "inode", "config", "scope"])
def test_handoff_cas_and_scope_mismatch_never_replace_old_journal(successor_home, damage):
    f = successor_home
    sha, identity = f.raw_hash, f.identity
    candidate = copy.deepcopy(f.candidate)
    if damage == "sha":
        sha = "0" * 64
    elif damage == "inode":
        identity = [identity[0], identity[1] + 1]
    elif damage == "config":
        candidate["config"]["web_port"] += 1
    else:
        candidate["trial_authorization"] = {"profile": "unapproved"}
    with pytest.raises(UpdateBlocked):
        successor.commit(
            f.ops,
            candidate,
            expected_journal_sha256=sha,
            expected_journal_identity=identity,
            quiesced=f.quiet,
        )
    assert (f.ops.server / "run/gateway-upgrade.json").read_bytes() == f.old_raw
    assert f.events == []


def test_bundle_byte_change_is_rejected_before_cas(successor_home):
    f = successor_home
    f.artifact.write_bytes(f.artifact.read_bytes() + b"changed")
    with pytest.raises(UpdateBlocked, match="bundle_changed"):
        successor.commit(
            f.ops,
            f.candidate,
            expected_journal_sha256=f.raw_hash,
            expected_journal_identity=f.identity,
            quiesced=f.quiet,
        )
    assert (f.ops.server / "run/gateway-upgrade.json").read_bytes() == f.old_raw
    assert not f.events


def test_failure_after_intent_keeps_old_bytes_and_retry_preserves_snapshot_inode(
    successor_home, monkeypatch
):
    f = successor_home
    original = successor.g.write_upgrade_journal
    monkeypatch.setattr(
        successor.g,
        "write_upgrade_journal",
        lambda *args: (_ for _ in ()).throw(OSError("synthetic atomic handoff failure")),
    )
    with pytest.raises(OSError):
        successor.commit(
            f.ops,
            f.candidate,
            expected_journal_sha256=f.raw_hash,
            expected_journal_identity=f.identity,
            quiesced=f.quiet,
        )
    snapshot = f.ops.root / "handoffs" / successor.TRANSACTION / "predecessor.json"
    inode = snapshot.stat().st_ino
    assert snapshot.read_bytes() == f.old_raw
    assert (f.ops.server / "run/gateway-upgrade.json").read_bytes() == f.old_raw
    monkeypatch.setattr(successor.g, "write_upgrade_journal", original)
    successor.commit(
        f.ops,
        f.candidate,
        expected_journal_sha256=f.raw_hash,
        expected_journal_identity=f.identity,
        quiesced=f.quiet,
    )
    assert snapshot.stat().st_ino == inode
    successor.verify_handoff(f.ops.home, f.ops.state)


def test_only_verified_new_mode_gets_v2_prepare_options(successor_home):
    f = successor_home
    assert f.ops.trial_archive_options() == {}
    f.ops.state["mode"] = successor.MODE
    with pytest.raises((UpdateBlocked, KeyError)):
        f.ops.trial_archive_options()
    f.ops.state["mode"] = successor.LEGACY_MODE
    successor.commit(
        f.ops,
        f.candidate,
        expected_journal_sha256=f.raw_hash,
        expected_journal_identity=f.identity,
        quiesced=f.quiet,
    )
    assert f.ops.trial_archive_options() == {"archive_policy": "rename-only-v2"}


def test_successor_observation_never_resends_known_process_signal(successor_home, monkeypatch):
    from research_workbench_entrypoint import web_contract

    f = successor_home
    successor.commit(
        f.ops,
        f.candidate,
        expected_journal_sha256=f.raw_hash,
        expected_journal_identity=f.identity,
        quiesced=f.quiet,
    )
    f.ops.state["trial_processes"] = {"web": {"pid": 12345}}
    monkeypatch.setattr(web_contract, "probe_process", lambda pid: SimpleNamespace(state="alive"))
    monkeypatch.setattr(
        successor.os, "kill", lambda *args: pytest.fail("handoff cannot resend a signal")
    )
    with pytest.raises(UpdateBlocked, match="original_pid_not_retired"):
        successor.observe_stopped(f.ops)
    monkeypatch.setattr(web_contract, "probe_process", lambda pid: SimpleNamespace(state="missing"))
    successor.observe_stopped(f.ops)
    successor.observe_stopped(f.ops)


@pytest.fixture
def managed_drain(stopped_home, monkeypatch):
    import signal
    import sys

    from app.research_web import service_manager as service
    from app.research_web.service_diagnostics import ServiceProbe
    from research_workbench_entrypoint import web_contract
    from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade
    from research_workbench_entrypoint.resident.gateway_fence import BirthFence

    f = stopped_home
    ops = f.ops
    ops.home.chmod(0o700)
    ops.server.chmod(0o700)
    (ops.server / "accounts.sqlite3").chmod(0o600)
    ops.state.update(predecessor())
    f.data.chmod(0o700)
    for folder in f.data.rglob("*"):
        if folder.is_dir():
            folder.chmod(0o700)
    project = ops.home / "release"
    project.mkdir()
    ops.state["primary_project"] = str(project)
    ops.state["config"].update(node=sys.executable)
    manager = service.WebServiceManager(
        project_root=project,
        data_root=f.data,
        python=sys.executable,
        node=sys.executable,
        web_port=ops.state["config"]["web_port"],
        runtime_port=ops.state["config"]["runtime_port"],
    )
    processes = {
        role: SimpleNamespace(
            role=role,
            port=ops.state["config"]["web_port" if role == "web" else "runtime_port"],
            signature=("python", role),
        )
        for role in ("web", "runtime")
    }
    facts = {"alive": True, "signals": [], "clock": 0.0, "bind_after": 29.0, "pgid_changed": False}
    pid = 42420
    argv = ("python", "web")

    def observed(value):
        if value != pid:
            return web_contract.ProcessFact("missing", None, None)
        return web_contract.ProcessFact(
            "alive" if facts["alive"] else "missing", "python web", None, argv, 100.0
        )

    def probe(process):
        alive = process.role == "web" and facts["alive"]
        return ServiceProbe(
            process.role,
            process.port,
            "valid" if alive else "missing",
            "alive" if alive else "missing",
            "owned" if alive else "unknown",
            "listening" if alive else "closed",
            "passed",
            alive,
            pid if alive else None,
            (),
        )

    monkeypatch.setattr(manager, "_processes", lambda: tuple(processes.values()))
    monkeypatch.setattr(manager, "_probe_service", probe)
    monkeypatch.setattr(
        manager, "_service_probes", lambda: tuple(probe(process) for process in processes.values())
    )
    monkeypatch.setattr(
        manager, "_probe_state", lambda process: service._StateFact("valid", pid, argv, (), 100.0)
    )
    monkeypatch.setattr(service, "probe_process", observed)
    monkeypatch.setattr(web_contract, "probe_process", observed)
    monkeypatch.setattr(
        service,
        "listener_pids",
        lambda port: web_contract.ListenerFact(
            "listening" if facts["alive"] else "closed", (pid,) if facts["alive"] else (), None
        ),
    )
    monkeypatch.setattr(
        successor.os, "getpgid", lambda value: value + 1 if facts["pgid_changed"] else value
    )
    monkeypatch.setattr(successor.g, "native_image", lambda value: Path(sys.executable).resolve())
    monkeypatch.setattr(
        successor.g, "process", lambda value: "original birth and exact managed command"
    )
    monkeypatch.setattr(
        successor.g,
        "run",
        lambda args, **kwargs: (
            str(successor.os.getuid())
            if args[:2] == ["/bin/ps", "-p"]
            else pytest.fail("unexpected process execution")
        ),
    )
    monkeypatch.setattr(successor.g, "no_children", lambda value: None)

    def kill(value, number):
        assert value == pid and number == signal.SIGTERM
        folder = ops.root / "handoffs" / ops.state["transaction"]
        assert list(folder.glob("primary-stop-web*.json"))
        facts["signals"].append((value, number))
        facts["alive"] = False

    monkeypatch.setattr(service.os, "kill", kill)
    monkeypatch.setattr(
        service.os, "killpg", lambda *args: pytest.fail("no process group signalling")
    )

    def sleep(seconds):
        facts["clock"] += seconds

    clock = SimpleNamespace(monotonic=lambda: facts["clock"], sleep=sleep)
    monkeypatch.setattr(successor, "time", clock)
    monkeypatch.setattr(service, "time", clock)
    monkeypatch.setattr(
        upgrade, "ports_are_free", lambda ports: facts["clock"] >= facts["bind_after"]
    )
    primary = json.loads((ops.server / "resident.json").read_bytes())["binding"]["primary_user_id"]
    with (
        BirthFence(ops.server, primary, transaction=successor.TRANSACTION) as fence,
        manager._installation_start_scope() as lease,
    ):
        fence.retain = True
        ops.fence, ops.manager, ops.lease = fence, manager, lease
        yield SimpleNamespace(ops=ops, facts=facts, pid=pid)
        fence.retain = False


def test_current_managed_pid_gets_one_real_primitive_term_and_waits_for_actual_bind(managed_drain):
    import signal

    f = managed_drain
    original_map = copy.deepcopy(f.ops.state.get("trial_processes"))
    successor.drain_primary(f.ops, "a" * 64)
    assert f.facts["signals"] == [(f.pid, signal.SIGTERM)]
    assert f.facts["clock"] >= 29
    assert f.ops.state.get("trial_processes") == original_map
    intent = f.ops.root / "handoffs" / successor.TRANSACTION / "primary-stop-web.json"
    inode = intent.stat().st_ino
    successor.drain_primary(f.ops, "a" * 64)
    assert f.facts["signals"] == [(f.pid, signal.SIGTERM)]
    assert intent.stat().st_ino == inode


def test_changed_managed_pgid_is_not_signalled(managed_drain):
    f = managed_drain
    f.facts["pgid_changed"] = True
    with pytest.raises(UpdateBlocked, match="managed_identity_unknown"):
        successor.drain_primary(f.ops, "a" * 64)
    assert not f.facts["signals"]


def test_crash_after_managed_intent_resumes_observe_only_without_term(managed_drain, monkeypatch):
    from app.research_web.service_manager import ServiceManagerError

    f = managed_drain
    publish = successor.publish

    def crash(path, value):
        result = publish(path, value)
        if path.name == "primary-stop-web.json":
            raise OSError("synthetic crash after durable intent before TERM")
        return result

    monkeypatch.setattr(successor, "publish", crash)
    with pytest.raises(OSError):
        successor.drain_primary(f.ops, "a" * 64)
    assert not f.facts["signals"]
    monkeypatch.setattr(successor, "publish", publish)
    with pytest.raises(ServiceManagerError) as error:
        successor.drain_primary(f.ops, "a" * 64)
    assert error.value.code == "graceful_stop_pending"
    assert not f.facts["signals"]
    f.facts["alive"] = False
    successor.drain_primary(f.ops, "a" * 64)
    assert not f.facts["signals"]


@pytest.fixture
def qualified_source(tmp_path, monkeypatch, stopped_home):
    """Load real operator bytes from a clean synthetic Git checkout, not a proof stub."""
    import importlib
    import io
    import subprocess
    import sys
    import zipfile

    source = tmp_path / "qualified-source"
    resident = source / "research_workbench_entrypoint/resident"
    resident.mkdir(parents=True)
    for path in Path(successor.__file__).parent.glob("*.py"):
        (resident / path.name).write_bytes(path.read_bytes())

    def git(*args):
        return subprocess.check_output(
            ["/usr/bin/git", "-C", str(source), *args], text=True
        ).strip()

    git("init", "-q")
    git("config", "user.name", "Synthetic Qualification")
    git("config", "user.email", "qualification@example.invalid")
    git("remote", "add", "origin", "git@github.com:owner/repo.git")
    git("add", ".")
    git("commit", "-qm", "synthetic reviewed resident closure")
    revision = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    common = source / ".git"
    receipts = common / "leon-engineering/deliveries"
    reviews = common / "leon-engineering/git-safety/reviews"
    receipts.mkdir(parents=True)
    reviews.mkdir(parents=True)
    targets = {revision: (revision, 1, 100), successor.PAYLOAD: ("f" * 40, 2, 101)}
    for target, (head, run, pr) in targets.items():
        name = str(pr) + ".json"
        (receipts / name).write_text(
            json.dumps(
                {
                    "remoteCommit": target,
                    "integrationCommit": head,
                    "status": "cleaned",
                    "mode": "pr",
                    "ci": {"status": "passed"},
                    "verification": {"status": "passed"},
                    "pullRequest": {"number": pr},
                }
            )
        )
        (reviews / name).write_text(json.dumps({"status": "PASS", "reviewedCommit": head}))
    previous = {
        name: value
        for name, value in sys.modules.items()
        if name == "resident" or name.startswith("resident.")
    }
    for name in previous:
        sys.modules.pop(name)
    monkeypatch.syspath_prepend(str(source / "research_workbench_entrypoint"))
    package = importlib.import_module("resident.trial_successor")
    operator = importlib.import_module("resident.model_provider_upgrade")
    evidence = importlib.import_module("resident.evidence")
    state = {"pending": False, "qualification_requests": []}

    def api(self, endpoint):
        state["qualification_requests"].append(endpoint)
        if endpoint == "commits/master":
            return {"sha": revision}
        if endpoint.startswith("pulls/"):
            number = int(endpoint.split("/")[-1])
            target, (head, run, _pr) = next(
                (target, item) for target, item in targets.items() if item[2] == number
            )
            return {
                "merged": True,
                "merge_commit_sha": target,
                "head": {"sha": head},
                "base": {"ref": "master"},
            }
        if endpoint.startswith("git/commits/"):
            return {"tree": {"sha": tree}}
        if endpoint.startswith("actions/workflows/"):
            head = endpoint.split("head_sha=")[1].split("&")[0]
            run = next(item[1] for item in targets.values() if item[0] == head)
            return {
                "workflow_runs": [
                    {
                        "id": run,
                        "status": "completed",
                        "conclusion": "failure" if state["pending"] else "success",
                    }
                ]
            }
        if "/jobs?" in endpoint:
            return {
                "jobs": [
                    {"id": 7, "name": "checks", "conclusion": "success", "labels": ["macos-14"]}
                ]
            }
        pytest.fail("unexpected synthetic GitHub API endpoint")

    def archive(args):
        run = int(args[2].split("/runs/")[1].split("/")[0])
        head = next(item[0] for item in targets.values() if item[1] == run)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as output:
            output.writestr(
                "0_checks.txt",
                "[command]/usr/bin/git log -1 --format=%H\n2026-10-31T00:00:00Z " + head,
            )
        return stream.getvalue()

    monkeypatch.setattr(evidence.GitHubEvidence, "api", api)
    monkeypatch.setattr(evidence, "run_archive", archive)
    monkeypatch.setattr(
        package.g,
        "run",
        lambda args, **kwargs: (
            "git-lfs synthetic dependency"
            if args[-3:] == ["/usr/bin/git", "lfs", "version"]
            else pytest.fail("stage must not launch any job")
        ),
    )
    home = stopped_home.ops.home
    for folder in (home / "resident", home / "server/run"):
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    fake_system_home = home / "system"
    (fake_system_home / "Library/LaunchAgents").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_system_home))
    original = predecessor()
    original.update(
        primary_project=str(home / "release"),
        source=str(home / "resident/artifacts" / successor.PAYLOAD / "source"),
        config={"repository": "owner/repo"},
    )
    github = evidence.GitHubEvidence(Path("/synthetic-gh"), "owner/repo", common)
    try:
        yield SimpleNamespace(
            package=package,
            operator=operator,
            source=source,
            home=home,
            state=original,
            github=github,
            revision=revision,
            facts=state,
            base=stopped_home,
            common=common,
        )
    finally:
        for name in tuple(sys.modules):
            if name == "resident" or name.startswith("resident."):
                sys.modules.pop(name)
        sys.modules.update(previous)
        importlib.invalidate_caches()


def test_real_stage_qualifies_clean_source_and_reuses_same_verified_zip(
    qualified_source, monkeypatch
):
    f = qualified_source
    candidate = f.package.stage(f.home, f.source, f.state, f.github)
    assert candidate["executor_revision"] == f.revision
    assert candidate["executor_proof"]["sha"] == f.revision
    assert candidate["proof"]["sha"] == successor.PAYLOAD
    artifact = Path(candidate["recovery"]["artifact"])
    inode, raw = artifact.stat().st_ino, artifact.read_bytes()
    monkeypatch.setattr(
        f.operator,
        "install_recovery",
        lambda *args, **kwargs: pytest.fail("same executor must reuse immutable stage"),
    )
    again = f.package.stage(f.home, f.source, f.state, f.github)
    assert again["recovery"] == candidate["recovery"]
    assert artifact.stat().st_ino == inode and artifact.read_bytes() == raw
    retained = f.source.with_name("temporarily-unavailable-dev-source")
    f.source.rename(retained)
    try:
        f.package.verify_stage(f.home, candidate)
    finally:
        retained.rename(f.source)


def test_real_stage_failed_ci_refuses_before_bundle_or_job(qualified_source):
    f = qualified_source
    f.facts["pending"] = True
    with pytest.raises(f.package.UpdateBlocked, match="ci_pending_or_failed"):
        f.package.stage(f.home, f.source, f.state, f.github)
    assert not list((f.home / "server/run").glob("*.pyz"))


@pytest.fixture
def fresh_actions(managed_drain, monkeypatch):
    """Real exclusions/lease/drain primitive; only native observation adapters are synthetic."""
    import plistlib
    import sys
    from uuid import uuid4

    from research_workbench_entrypoint import web_contract
    from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade
    from research_workbench_entrypoint.resident.gateway_fence import BirthFence

    f = managed_drain
    ops, state = f.ops, f.ops.state
    previous_fence = ops.fence
    previous_fence.retain = False
    previous_fence.__exit__(None, None, None)
    previous_fence.owns_journal = False
    transaction = str(uuid4())
    state.update(version=5, mode=successor.MODE, transaction=transaction, phase="stop_gateway")
    state["config"]["python"] = sys.executable
    state["successor"] = {
        "origin": "fresh_apply",
        "stage": {"path": "already-reviewed-stage", "sha256": "a" * 64},
        "prior_receipt": {"path": "completed-original-90e", "sha256": "b" * 64},
        "quarantine_sha256": "c" * 64,
    }
    state["trial_authorization_sha256"] = "d" * 64
    state["gateway_project"] = state["primary_project"]
    system_home = ops.home / "system"
    agents = system_home / "Library/LaunchAgents"
    agents.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: system_home))
    supervisor = agents / (successor.c.LABEL + ".plist")
    supervisor_argv = [
        sys.executable,
        str(ops.home / "resident/controller.pyz"),
        "tick",
        "--home",
        str(ops.home),
    ]
    supervisor.write_bytes(
        plistlib.dumps(
            {
                "Label": successor.c.LABEL,
                "ProgramArguments": supervisor_argv,
                "WorkingDirectory": str(ops.home),
                "StartInterval": 60,
                "RunAtLoad": True,
            }
        )
    )
    supervisor.chmod(0o600)
    state["supervisor_plist_sha256"] = hashlib.sha256(supervisor.read_bytes()).hexdigest()
    gateway = agents / (successor.g.LABEL + ".plist")
    gateway_argv = [
        str(Path(state["primary_project"]) / ".venv/bin/python"),
        "-m",
        "app.research_web.multiuser.resident",
        "--root",
        str(ops.server),
    ]
    gateway.write_bytes(
        plistlib.dumps(
            {
                "Label": successor.g.LABEL,
                "ProgramArguments": gateway_argv,
                "WorkingDirectory": state["gateway_project"],
            }
        )
    )
    gateway.chmod(0o600)
    state.update(
        gateway_plist=str(gateway),
        gateway_plist_sha256=hashlib.sha256(gateway.read_bytes()).hexdigest(),
    )
    image = str(Path(sys.executable).resolve())
    signature = "original birth and exact managed command"
    state["trial_processes"] = {
        role: {
            "pid": pid,
            "birth": 100.0,
            "argv": ["python", role],
            "uid": successor.os.getuid(),
            "image": image,
            "signature": signature,
        }
        for role, pid in (("web", f.pid), ("runtime", f.pid + 1))
    }
    state["trial_processes"]["gateway"] = {
        "pid": 60000,
        "birth": 200.0,
        "argv": gateway_argv,
        "uid": successor.os.getuid(),
        "image": image,
        "signature": signature,
    }
    jobs = {successor.c.LABEL: True, successor.g.LABEL: True}
    events = []
    facts = {"gateway_birth": 200.0}

    def job(label):
        if not jobs.get(label):
            return None
        path = supervisor if label == successor.c.LABEL else gateway
        payload = plistlib.loads(path.read_bytes())
        raw = f"path = {path}\nprogram = {payload['ProgramArguments'][0]}\nworking directory = {payload['WorkingDirectory']}\narguments = {' '.join(payload['ProgramArguments'])}\n"
        return raw + ("pid = 60000\n" if label == successor.g.LABEL else "")

    def run(argv, **kwargs):
        if argv[:2] == ["/bin/ps", "-p"]:
            return str(successor.os.getuid())
        assert argv[0] == "/bin/launchctl"
        if argv[1] == "bootout":
            label = argv[2].split("/")[-1]
            events.append(("bootout", label))
            jobs[label] = False
        elif argv[1] == "bootstrap":
            label = plistlib.loads(Path(argv[3]).read_bytes())["Label"]
            events.append(("bootstrap", label))
            jobs[label] = True
        else:
            assert argv[1] == "print"
            return job(argv[2].split("/")[-1]) or ""
        return ""

    original_probe = web_contract.probe_process

    def observed(pid):
        if pid == 60000:
            return web_contract.ProcessFact(
                "alive" if jobs[successor.g.LABEL] else "missing",
                "gateway",
                None,
                tuple(gateway_argv),
                facts["gateway_birth"],
            )
        return original_probe(pid)

    monkeypatch.setattr(web_contract, "probe_process", observed)
    monkeypatch.setattr(successor, "_job", job)
    monkeypatch.setattr(successor, "_supervisor_job", lambda: job(successor.c.LABEL))
    monkeypatch.setattr(successor.g, "run", run)
    monkeypatch.setattr(successor.g, "job_state", lambda: job(successor.g.LABEL))
    monkeypatch.setattr(
        successor.g, "listener_pids", lambda: {60000} if jobs[successor.g.LABEL] else set()
    )
    monkeypatch.setattr(
        upgrade,
        "ports_are_free",
        lambda ports: (
            not jobs[successor.g.LABEL]
            if ports == (8089,)
            else f.facts["clock"] >= f.facts["bind_after"]
        ),
    )

    # Entry qualification and completed-retirement retry guards are exercised separately.
    def admitted(home, value):
        assert home == ops.home and value["mode"] == successor.MODE
        assert value["transaction"] == transaction and value["successor"]["origin"] == "fresh_apply"

    monkeypatch.setattr(successor, "verify_handoff", admitted)
    monkeypatch.setattr(
        successor,
        "ensure_recovery_job",
        lambda home, value: events.append(("verified-recovery-backstop", value["transaction"])),
    )
    primary = json.loads((ops.server / "resident.json").read_bytes())["binding"]["primary_user_id"]
    with BirthFence(ops.server, primary, transaction=transaction) as fence:
        fence.retain = True
        ops.fence = fence
        yield SimpleNamespace(
            ops=ops, transaction=transaction, jobs=jobs, events=events, facts=facts, drain=f
        )
        fence.retain = False


def test_fresh_gateway_then_primary_use_existing_exact_controls_and_own_transaction(fresh_actions):
    f = fresh_actions
    successor.stop_fresh_gateway(f.ops)
    assert f.events[0][0] == "verified-recovery-backstop"
    assert [event for event in f.events if event[0] == "bootout"] == [
        ("bootout", successor.c.LABEL),
        ("bootout", successor.g.LABEL),
    ]
    f.ops.state["phase"] = "stop_primary"
    successor.stop_fresh_primary(f.ops)
    assert len(f.drain.facts["signals"]) == 1
    assert f.drain.facts["clock"] >= 29
    folder = f.ops.root / "handoffs" / f.transaction
    assert (folder / "fresh-context.json").is_file()
    assert list(folder.glob("primary-stop-web-*.json"))
    assert not (f.ops.root / "handoffs" / successor.TRANSACTION).exists()
    successor.verify_supervisor_boundary(f.ops.home, f.ops.state)
    with pytest.raises(UpdateBlocked, match="root_recovery_trigger_present"):
        successor.restore_supervisor(f.ops)
    (f.ops.root / "transaction.json").unlink()
    successor.restore_supervisor(f.ops)
    assert f.jobs[successor.c.LABEL] is True


def test_fresh_absent_scheduler_after_bootout_before_receipt_can_resume_without_repeat(
    fresh_actions, monkeypatch
):
    f = fresh_actions
    publish = successor.publish
    injected = False

    def crash(path, value):
        nonlocal injected
        result = publish(path, value)
        if path.name == "fresh-supervisor-job-quiesced.json" and not injected:
            injected = True
            raise OSError("synthetic crash after actual bootout, before next checkpoint")
        return result

    monkeypatch.setattr(successor, "publish", crash)
    with pytest.raises(OSError):
        successor.stop_fresh_gateway(f.ops)
    assert f.jobs[successor.c.LABEL] is False
    successor.verify_supervisor_boundary(f.ops.home, f.ops.state)
    successor.stop_fresh_gateway(f.ops)
    assert f.events.count(("bootout", successor.c.LABEL)) == 1
    assert f.events.count(("bootout", successor.g.LABEL)) == 1


def test_fresh_stop_intent_before_bootout_only_observes_on_retry(fresh_actions, monkeypatch):
    f = fresh_actions
    publish = successor.publish

    def crash(path, value):
        result = publish(path, value)
        if path.name == "fresh-supervisor-stop-intent.json":
            raise OSError("synthetic crash between durable stop intent and job action")
        return result

    monkeypatch.setattr(successor, "publish", crash)
    with pytest.raises(OSError):
        successor.stop_fresh_gateway(f.ops)
    monkeypatch.setattr(successor, "publish", publish)
    with pytest.raises(UpdateBlocked, match="job_stop_unknown"):
        successor.stop_fresh_gateway(f.ops)
    assert not [event for event in f.events if event[0] == "bootout"]


def test_fresh_gateway_changed_birth_is_never_booted_out(fresh_actions):
    f = fresh_actions
    f.facts["gateway_birth"] += 1
    with pytest.raises(UpdateBlocked, match="generation_unknown"):
        successor.stop_fresh_gateway(f.ops)
    assert f.jobs[successor.g.LABEL] is True
    assert ("bootout", successor.g.LABEL) not in f.events


def _require_genuine_cli_history(checkout, revisions):
    """Fail clearly before fixture setup; CI supplies only the exact historical witnesses."""
    import os
    import subprocess

    for revision in revisions:
        result = subprocess.run(
            [
                "/usr/bin/git",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-C",
                str(checkout),
                "cat-file",
                "-e",
                revision + "^{commit}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0"},
        )
        if result.returncode:
            pytest.fail("genuine_cli_required_object_missing:" + revision, pytrace=False)


@pytest.fixture
def genuine_cli(qualified_source, monkeypatch):
    """Real main/stage/legacy Git/bundle/CAS/data engine; synthetic OS/service adapters."""
    import os
    import plistlib
    import subprocess
    import sys
    import zipfile
    from contextlib import contextmanager

    from app.research_web import service_manager as services
    from app.research_web.service_diagnostics import ServiceProbe
    from research_workbench_entrypoint import web_contract

    f = qualified_source
    pkg, operator, home = f.package, f.operator, f.home
    base = f.base
    for path in (
        home,
        home / "server",
        base.data,
        *(p for p in base.data.rglob("*") if p.is_dir()),
    ):
        path.chmod(0o700)
    (home / "server/accounts.sqlite3").chmod(0o600)
    (home / "logs").mkdir(mode=0o700)
    # The canonical checkout may stay shallow; the existing CI step supplies
    # these exact commits. Fixtures never fetch network history or skip the CLI.
    checkout_root = Path(successor.__file__).parents[2]
    _require_genuine_cli_history(checkout_root, (pkg.PAYLOAD, pkg.PREDECESSOR, pkg.PREVIOUS))
    # These temporary repositories share only a read-only object alternate.
    common = subprocess.check_output(
        [
            "/usr/bin/git",
            "-C",
            str(Path(successor.__file__).parents[2]),
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ],
        text=True,
    ).strip()
    (f.common / "objects/info/alternates").write_text(str(Path(common) / "objects") + "\n")

    def git(where, *args):
        return subprocess.check_output(
            [
                "/usr/bin/git",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-C",
                str(where),
                *args,
            ],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()

    git(f.source, "config", "extensions.worktreeConfig", "true")

    def checkout(path, revision):
        git(f.source, "worktree", "add", "--detach", "--no-checkout", str(path), revision)
        git(path, "read-tree", "HEAD")
        git(path, "sparse-checkout", "set", "--cone", "research_workbench_entrypoint/resident")
        git(path, "read-tree", "-mu", "HEAD")
        git(path, "restore", "--source=HEAD", "--worktree", "--", ".")
        assert git(path, "status", "--porcelain") == ""

    product = home / "resident/artifacts" / pkg.PAYLOAD / "source"
    legacy = product.parent / "executor"
    release = home / "release"
    for path, revision in (
        (product, pkg.PAYLOAD),
        (legacy, pkg.PREDECESSOR),
        (release, pkg.PREVIOUS),
    ):
        checkout(path, revision)
    project_info = release.stat()
    python = str(Path(sys.executable).resolve())
    controller = home / "resident/controller.pyz"
    controller.write_bytes(b"synthetic immutable controller identity")
    controller.chmod(0o600)
    controller_hash = hashlib.sha256(controller.read_bytes()).hexdigest()
    monkeypatch.setattr(operator, "CONTROLLER_SHA256", controller_hash)
    config = {
        "project": str(release),
        "project_identity": [project_info.st_dev, project_info.st_ino],
        "python": python,
        "node": python,
        "artifact": str(controller),
        "artifact_sha256": controller_hash,
        "source_common": str(f.common),
        "repository": "owner/repo",
        "gh": "/synthetic-gh",
        "private_origin": "https://fixture.invalid",
        "web_port": 3081,
        "runtime_port": 8088,
        "baseline": pkg.PREVIOUS,
    }
    agents = Path.home() / "Library/LaunchAgents"

    def plist(label, argv, working, interval):
        path = agents / (label + ".plist")
        path.write_bytes(
            plistlib.dumps(
                {
                    "Label": label,
                    "ProgramArguments": argv,
                    "WorkingDirectory": str(working),
                    "RunAtLoad": True,
                    "StartInterval": interval,
                }
            )
        )
        path.chmod(0o600)
        return path

    supervisor = plist(
        pkg.c.LABEL, [python, str(controller), "tick", "--home", str(home)], home, 60
    )
    old_artifact = home / "server/run/old-reviewed-recovery.pyz"
    old_modules = pkg.g.module_blobs(legacy, pkg.PREDECESSOR)
    with zipfile.ZipFile(old_artifact, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "target": pkg.PAYLOAD,
                    "modules": old_modules,
                    "source": str(legacy),
                    "executor_revision": pkg.PREDECESSOR,
                }
            ),
        )
        archive.writestr("__main__.py", operator.ENTRY)
        for name in old_modules:
            archive.writestr("resident/" + name, pkg.g.git_bytes(legacy, pkg.PREDECESSOR, name))
    old_artifact.chmod(0o600)
    old_hash = hashlib.sha256(old_artifact.read_bytes()).hexdigest()
    old_label = "com.research-workbench.model-recovery." + old_hash[:16]
    old_plist = plist(
        old_label,
        [str(release / ".venv/bin/python"), str(old_artifact), "recover", "--home", str(home)],
        home,
        30,
    )
    gateway_argv = [
        str(release / ".venv/bin/python"),
        "-m",
        "app.research_web.multiuser.resident",
        "--root",
        str(home / "server"),
    ]
    gateway = plist(pkg.g.LABEL, gateway_argv, release, 30)
    old_wheel, new_wheel = product.parent / "old.whl", product.parent / "new.whl"
    old_wheel.write_bytes(b"synthetic old wheel")
    new_wheel.write_bytes(b"synthetic new wheel")
    info = lambda path: [path.stat().st_dev, path.stat().st_ino]
    repository = operator.repository_identity(release, "owner/repo")
    binding = json.loads((home / "server/resident.json").read_bytes())
    binding.update(project=str(release), revision=pkg.PREVIOUS, origin="http://fixture.invalid")
    operator.c.atomic(home / "server/resident.json", binding)
    from research_workbench_entrypoint.resident import trial_discard_backup as backup

    base.manifest["inventory_seal"] = backup.preview(home)["seal"]
    base.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(home))
    state = predecessor()
    state["predecessor_control_padding"] = "x" * 1_100_000
    state.update(
        config=config,
        gateway_config=binding,
        source=str(product),
        executor_source=str(legacy),
        primary_project=str(release),
        gateway_project=str(release),
        primary_identity=info(release),
        gateway_identity=info(release),
        primary_repository=repository,
        gateway_repository=repository,
        recovery={
            "artifact": str(old_artifact),
            "sha256": old_hash,
            "plist": str(old_plist),
            "plist_sha256": hashlib.sha256(old_plist.read_bytes()).hexdigest(),
            "modules": old_modules,
        },
        controller_sha256=controller_hash,
        supervisor_plist_sha256=hashlib.sha256(supervisor.read_bytes()).hexdigest(),
        gateway_plist=str(gateway),
        gateway_plist_sha256=hashlib.sha256(gateway.read_bytes()).hexdigest(),
        gateway_command=" ".join(gateway_argv),
        manifest={"status": "installed", "code_commit": pkg.PREVIOUS},
        model_before={
            "provider": "synthetic",
            "model": "synthetic",
            "credential_configured": False,
            "credential_storage": "not_required",
        },
        reviewed=operator.review(product, pkg.PAYLOAD, pkg.MODE),
        before=operator.g.preservation(home),
        asset_index_before=operator.asset_index_snapshot(home),
        new_wheel={"path": str(new_wheel), "sha256": operator.c.digest(new_wheel)},
        old_wheel={"path": str(old_wheel), "sha256": operator.c.digest(old_wheel)},
        accepted={"target": pkg.PREVIOUS},
        candidate_before={},
        proof={"sha": pkg.PAYLOAD},
        trial_authorization=base.manifest,
        trial_authorization_sha256=pkg.digest(base.manifest),
        trial_backup_parent=str(base.safe),
        trial_processes={
            role: {
                "pid": pid,
                "birth": 10.0,
                "argv": ["original", role],
                "signature": "frozen predecessor full signature",
                "image": python,
                "uid": os.getuid(),
            }
            for role, pid in (("web", 79050), ("runtime", 71627), ("gateway", 79214))
        },
    )
    monkeypatch.setattr(operator, "validate_trial_rebind", lambda value: value["config"])
    operator.c.atomic(home / "resident/config.json", config)
    operator.c.atomic(home / "install/manifest.json", state["manifest"])
    candidate_fields = {
        key: state[key]
        for key in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
    }
    operator.c.atomic(
        home / "resident/transaction.json", {**candidate_fields, "phase": "switching"}
    )
    operator.g.write_upgrade_journal(home / "server/run/gateway-upgrade.json", state)
    old_raw, identity = pkg._private(home / "server/run/gateway-upgrade.json")
    expected = hashlib.sha256(old_raw).hexdigest()
    initial = pkg.stage(home, f.source, state, f.github)
    initial["executor_source"] = str(
        home / "resident/artifacts" / pkg.PAYLOAD / "executors" / f.revision
    )
    pkg.publish(
        pkg._directory(home) / "staged.json",
        {
            "version": 1,
            "predecessor_sha256": expected,
            "predecessor_identity": [identity["dev"], identity["ino"]],
            "candidate": initial,
        },
        limit=pkg.g.JOURNAL_MAX_BYTES,
    )
    # No caller proof is passed through CLI. The real stage was already sealed above.
    facts = {
        "alive": {"web": True, "runtime": False},
        "pid": {"web": 42420, "runtime": 42421},
        "birth": {"web": 100.0, "runtime": 101.0},
        "signals": [],
        "clock": 0.0,
        "events": [],
    }
    processes = {
        role: SimpleNamespace(
            role=role,
            port=config["web_port" if role == "web" else "runtime_port"],
            signature=("python", role),
        )
        for role in ("web", "runtime")
    }
    manager = services.WebServiceManager(
        project_root=release,
        data_root=base.data,
        python=python,
        node=python,
        web_port=3081,
        runtime_port=8088,
    )

    def native(pid):
        role = next((role for role in facts["pid"] if facts["pid"][role] == pid), None)
        if role:
            return web_contract.ProcessFact(
                "alive" if facts["alive"][role] else "missing",
                "python " + role,
                None,
                ("python", role),
                facts["birth"][role],
            )
        if pid == 60000 and jobs.get(pkg.g.LABEL):
            return web_contract.ProcessFact("alive", "gateway", None, tuple(gateway_argv), 200.0)
        return web_contract.ProcessFact("missing", None, None)

    def probe(process):
        alive = facts["alive"][process.role]
        return ServiceProbe(
            process.role,
            process.port,
            "valid" if alive else "missing",
            "alive" if alive else "missing",
            "owned" if alive else "unknown",
            "listening" if alive else "closed",
            "passed",
            alive,
            facts["pid"][process.role] if alive else None,
            (),
        )

    monkeypatch.setattr(manager, "_processes", lambda: tuple(processes.values()))
    monkeypatch.setattr(manager, "_probe_service", probe)
    monkeypatch.setattr(
        manager, "_service_probes", lambda: tuple(probe(p) for p in processes.values())
    )
    monkeypatch.setattr(
        manager,
        "_probe_state",
        lambda process: services._StateFact(
            "valid", facts["pid"][process.role], process.signature, (), facts["birth"][process.role]
        ),
    )
    monkeypatch.setattr(services, "probe_process", native)
    monkeypatch.setattr(web_contract, "probe_process", native)
    monkeypatch.setattr(
        services,
        "listener_pids",
        lambda port: web_contract.ListenerFact(
            "listening" if facts["alive"]["web" if port == 3081 else "runtime"] else "closed",
            (
                (facts["pid"]["web" if port == 3081 else "runtime"],)
                if facts["alive"]["web" if port == 3081 else "runtime"]
                else ()
            ),
            None,
        ),
    )

    def kill(pid, number):
        assert number == 15 and pid == facts["pid"]["web"]
        assert (pkg._directory(home) / "primary-stop-web.json").is_file()
        facts["signals"].append((pid, number))
        facts["alive"]["web"] = False

    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(os, "killpg", lambda *args: pytest.fail("no group signals"))
    monkeypatch.setattr(os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(pkg.g, "native_image", lambda pid: Path(python))
    monkeypatch.setattr(pkg.g, "process", lambda pid: "full original birth and command " + str(pid))
    monkeypatch.setattr(pkg.g, "no_children", lambda pid: None)
    monkeypatch.setattr(
        pkg.g,
        "no_private_processes",
        lambda server: None if server == home / "server" else pytest.fail("wrong root"),
    )
    jobs = {pkg.c.LABEL: True, old_label: True, pkg.g.LABEL: False}

    def job(label):
        if not jobs.get(label):
            return None
        path = agents / (label + ".plist")
        data = plistlib.loads(path.read_bytes())
        return (
            f"path = {path}\nprogram = {data['ProgramArguments'][0]}\nworking directory = {data['WorkingDirectory']}\narguments = {' '.join(data['ProgramArguments'])}\n"
            + ("pid = 60000\n" if label == pkg.g.LABEL else "")
        )

    def run(argv, **kwargs):
        if argv[:2] == ["/bin/ps", "-p"]:
            return str(os.getuid())
        if argv[0] == operator.TAILSCALE:
            return json.dumps(
                {
                    "Web": {
                        "fixture.invalid:443": {
                            "Handlers": {"/": {"Proxy": "http://127.0.0.1:8089"}}
                        }
                    },
                    "TCP": {"443": {"HTTPS": True}},
                }
            )
        assert argv[0] == "/bin/launchctl"
        if argv[1] == "bootout":
            label = argv[2].split("/")[-1]
            facts["events"].append(("bootout", label))
            jobs[label] = False
        elif argv[1] == "bootstrap":
            label = plistlib.loads(Path(argv[3]).read_bytes())["Label"]
            if jobs.get(label):
                raise pkg.UpdateBlocked("synthetic_already_loaded")
            facts["events"].append(("bootstrap", label))
            jobs[label] = True
        else:
            assert argv[1] == "print"
            return job(argv[2].split("/")[-1]) or ""
        return ""

    monkeypatch.setattr(pkg.g, "run", run)
    monkeypatch.setattr(pkg, "_job", job)
    monkeypatch.setattr(pkg, "_supervisor_job", lambda: job(pkg.c.LABEL))
    monkeypatch.setattr(pkg.g, "job_state", lambda: job(pkg.g.LABEL))
    monkeypatch.setattr(pkg.g, "job_pid", lambda: 60000 if jobs.get(pkg.g.LABEL) else None)
    monkeypatch.setattr(pkg.g, "listener_pids", lambda: {60000} if jobs.get(pkg.g.LABEL) else set())

    def sleep(seconds):
        facts["clock"] += seconds

    clock = SimpleNamespace(monotonic=lambda: facts["clock"], sleep=sleep)
    monkeypatch.setattr(pkg, "time", clock)
    monkeypatch.setattr(services, "time", clock)
    monkeypatch.setattr(
        operator, "ports_are_free", lambda ports: facts["clock"] >= 29 if len(ports) == 2 else True
    )

    def wait_ports(ports):
        assert tuple(ports) == (3081, 8088)
        assert facts["clock"] >= 29 and not any(facts["alive"].values())

    monkeypatch.setattr(operator.c, "wait_ports", wait_ports)

    def start(lease, *, open_browser):
        manager._assert_installation_scope(lease)
        facts["events"].append(("start-primary", "known-controlled-call"))
        for index, role in enumerate(("web", "runtime")):
            facts["pid"][role] = 50000 + index
            facts["birth"][role] = 300.0 + index
            facts["alive"][role] = True

    monkeypatch.setattr(manager, "_start_installed", start)
    monkeypatch.setattr(services, "WebServiceManager", lambda **kwargs: manager)

    @contextmanager
    def held(directory, name, *, exclusive):
        trial._held(directory / name)
        yield

    monkeypatch.setattr(operator, "file_lock", held)
    monkeypatch.setattr(operator, "sys", SimpleNamespace(**{**vars(sys), "platform": "darwin"}))
    monkeypatch.setattr(operator.c, "environment", lambda *args: None)
    real_run = operator.c.run

    def install_or_git(argv, **kwargs):
        if argv[1:3] == ["-m", "pip"]:
            facts["events"].append(("install-reviewed-wheel", argv[-1]))
            return "synthetic isolated wheel boundary"
        return real_run(argv, **kwargs)

    monkeypatch.setattr(operator.c, "run", install_or_git)

    def request(url):
        if url.endswith("/api/research/resident"):
            return {"enabled": True, "revision": pkg.PREVIOUS}
        if url.endswith("/api/server/health"):
            return {"revision": pkg.PREVIOUS, "deployment_fenced": True}
        if url.endswith("/api/research/runtime"):
            return {**state["model_before"], "connected": True, "health_check_passed": True}
        pytest.fail("no model/native/send request allowed")

    monkeypatch.setattr(operator, "request_json", request)

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method, path, **kwargs):
            assert (method, path) == ("GET", "/api/server/health")

        def getresponse(self):
            return SimpleNamespace(
                status=200,
                read=lambda limit: json.dumps(
                    {
                        "status": "ready",
                        "revision": pkg.PREVIOUS,
                        "primary_last_verified": True,
                        "deployment_fenced": True,
                    }
                ).encode(),
            )

        def close(self):
            pass

    monkeypatch.setattr(pkg.g.http.client, "HTTPConnection", Connection)
    # Restore the original fixture's real exclusions before letting main acquire its own fence.
    args = [
        "handoff-trial-retirement",
        "--home",
        str(home),
        "--source",
        str(f.source),
        "--handoff-journal-sha256",
        expected,
        "--handoff-journal-dev",
        str(identity["dev"]),
        "--handoff-journal-ino",
        str(identity["ino"]),
    ]
    return SimpleNamespace(
        f=f,
        pkg=pkg,
        operator=operator,
        state=state,
        args=args,
        old_raw=old_raw,
        facts=facts,
        jobs=jobs,
        old_label=old_label,
    )


@pytest.mark.parametrize("crash", [None, "before_cas", "after_cas"])
def test_genuine_cli_resumes_same_handoff_without_restage_bootout_or_term(
    genuine_cli, monkeypatch, crash
):
    import io
    from contextlib import redirect_stdout

    f = genuine_cli

    def invoke():
        output = io.StringIO()
        with redirect_stdout(output):
            status = f.operator.main(f.args)
        return status, output.getvalue()

    if crash is not None:
        injected = False
        if crash == "before_cas":
            write = f.pkg.g.write_upgrade_journal

            def fault(path, value):
                nonlocal injected
                if value.get("version") == 5 and not injected:
                    injected = True
                    raise OSError("synthetic pre-CAS interruption")
                return write(path, value)

            monkeypatch.setattr(f.pkg.g, "write_upgrade_journal", fault)
        else:
            commit = f.pkg.commit

            def fault(*args, **kwargs):
                nonlocal injected
                result = commit(*args, **kwargs)
                if not injected:
                    injected = True
                    raise OSError("synthetic post-CAS interruption")
                return result

            monkeypatch.setattr(f.pkg, "commit", fault)
        status, output = invoke()
        assert status == 1, output
        assert len(f.facts["signals"]) == 1
        if crash == "before_cas":
            assert (f.f.home / "server/run/gateway-upgrade.json").read_bytes() == f.old_raw
    status, output = invoke()
    assert status == 0, output
    result = json.loads(output.strip().splitlines()[-1])
    assert result["status"] == "rolled_back"
    assert len(f.facts["signals"]) == 1
    assert f.facts["events"].count(("bootout", f.old_label)) == 1
    assert f.facts["events"].count(("bootout", f.pkg.c.LABEL)) == 1
    assert (
        f.f.home / "resident/handoffs" / f.pkg.TRANSACTION / "predecessor.json"
    ).read_bytes() == f.old_raw
    assert not (f.f.home / "server/run/gateway-upgrade.json").exists()
    assert not (f.f.home / "resident/transaction.json").exists()
    assert f.jobs[f.pkg.c.LABEL] is True
    assert f.jobs[f.old_label] is False
    assert json.loads((f.f.home / "research-web/index.json").read_bytes())["sessions"] == {}


@pytest.mark.parametrize("field", ["--handoff-journal-sha256", "--handoff-journal-ino"])
def test_genuine_cli_wrong_predecessor_refuses_before_runtime_actions(genuine_cli, field):
    import io
    from contextlib import redirect_stdout

    f = genuine_cli
    args = list(f.args)
    args[args.index(field) + 1] = "0" * 64 if field.endswith("sha256") else "0"
    output = io.StringIO()
    with redirect_stdout(output):
        assert f.operator.main(args) == 1
    assert (
        json.loads(output.getvalue().strip().splitlines()[-1])["reason"]
        == "trial_successor_predecessor_changed"
    )
    assert not f.facts["signals"] and not f.facts["events"]
    assert (f.f.home / "server/run/gateway-upgrade.json").read_bytes() == f.old_raw


def test_real_staged_zip_can_activate_retained_product_before_app_import(genuine_cli, monkeypatch):
    import importlib
    import subprocess
    import sys

    f = genuine_cli
    staged = json.loads((f.pkg._directory(f.f.home) / "staged.json").read_bytes())
    candidate = staged["candidate"]
    product = Path(candidate["source"])
    for relative in (
        "app/__init__.py",
        "app/research_web/__init__.py",
        "app/research_web/service_manager.py",
    ):
        target = product / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = subprocess.check_output(
            ["/usr/bin/git", "-C", str(product), "show", f"{f.pkg.PAYLOAD}:{relative}"]
        )
        target.write_bytes(raw)
    artifact = Path(candidate["recovery"]["artifact"])
    for name in tuple(sys.modules):
        if name == "resident" or name.startswith("resident."):
            sys.modules.pop(name)
    monkeypatch.syspath_prepend(str(artifact))
    monkeypatch.setattr(sys, "argv", [str(artifact), "handoff-trial-retirement"])
    package = importlib.import_module("resident.trial_successor")
    assert ".pyz/" in package.__file__
    package.activate_handoff_source(f.f.home)
    assert sys.path[0] == str(product)
    assert not f.facts["signals"] and not f.facts["events"]


def test_small_control_publish_limit_stays_one_mib(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    value = {"padding": "x" * successor.backup.RECORD_LIMIT}
    with pytest.raises(UpdateBlocked, match="record_oversized"):
        successor.publish(folder / "stage.json", value)
    assert not (folder / "stage.json").exists()


def test_large_handoff_envelope_requires_explicit_reader_exception(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    value = {"initial": {"padding": "x" * 1_100_000}}
    path = folder / "intent.json"
    ref = successor.publish(path, value, limit=successor.g.JOURNAL_MAX_BYTES)
    with pytest.raises(UpdateBlocked, match="private_record_unreadable"):
        successor.reference(ref, path)
    assert successor.reference(ref, path, successor.g.JOURNAL_MAX_BYTES) == value


@pytest.fixture
def depth_one_cli_history(tmp_path):
    """Tiny local smart-transport clone; no application history or network is copied."""
    import subprocess

    seed, shallow = tmp_path / "history-seed", tmp_path / "depth-one"
    seed.mkdir()

    def git(where, *args):
        return subprocess.check_output(
            [
                "/usr/bin/git",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-C",
                str(where),
                *args,
            ],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()

    git(seed, "init", "-q")
    git(seed, "config", "user.name", "Synthetic History")
    git(seed, "config", "user.email", "history@example.invalid")
    (seed / "history.txt").write_text("old witness\n")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "historical witness")
    old = git(seed, "rev-parse", "HEAD")
    (seed / "history.txt").write_text("new checkout\n")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "current checkout")
    current = git(seed, "rev-parse", "HEAD")
    subprocess.run(
        ["/usr/bin/git", "clone", "--depth=1", "--no-checkout", seed.as_uri(), str(shallow)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert git(shallow, "rev-parse", "--is-shallow-repository") == "true"
    return SimpleNamespace(seed=seed, shallow=shallow, old=old, current=current, git=git)


def test_genuine_cli_shallow_missing_witness_has_explicit_failure(depth_one_cli_history, tmp_path):
    import subprocess

    f = depth_one_cli_history
    missing = subprocess.run(
        [
            "/usr/bin/git",
            "-C",
            str(f.shallow),
            "worktree",
            "add",
            "--detach",
            "--no-checkout",
            str(tmp_path / "unavailable-history"),
            f.old,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode == 128
    assert "invalid reference: " + f.old in missing.stderr
    with pytest.raises(pytest.fail.Exception, match="genuine_cli_required_object_missing:" + f.old):
        _require_genuine_cli_history(f.shallow, (f.current, f.old))


def test_genuine_cli_exact_local_witness_fetch_preserves_shallow_checkout(depth_one_cli_history):
    f = depth_one_cli_history
    f.git(f.shallow, "fetch", "--no-tags", "--depth=1", f.seed.as_uri(), f.old)
    _require_genuine_cli_history(f.shallow, (f.current, f.old))
    assert f.git(f.shallow, "rev-parse", "--is-shallow-repository") == "true"
