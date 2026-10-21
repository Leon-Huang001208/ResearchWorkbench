"""Deployment fences must win races without replacing native ownership."""

import os
import sqlite3
import sys
from uuid import uuid4

import pytest

from research_workbench_entrypoint.resident.gateway_fence import BirthFence, FenceBlocked


def test_static_scopes_separate_product_and_operator_code(monkeypatch, tmp_path):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    def git(_source, *args):
        if args[0] == "diff":
            assert "--no-renames" in args
            return (
                "app/research_web/ui/server/session.mjs"
                if args[-2] == "a" * 40
                else "research_workbench_entrypoint/resident/gateway_upgrade.py"
            )
        return "d" * 40 if args[0] == "rev-parse" else ""

    monkeypatch.setattr(g, "git", git)
    scopes = g.static_scopes(tmp_path, "a" * 40, "b" * 40, "c" * 40)
    assert set(scopes) == {"payload", "tool"}
    assert "app/research_web/ui/server/session.mjs" in scopes["payload"]
    assert "research_workbench_entrypoint/resident/gateway_upgrade.py" in scopes["tool"]


@pytest.mark.parametrize(
    "path",
    [
        "app/research_web/multiuser/gateway.py",
        "requirements/web.lock",
        "research_workbench_entrypoint/resident/controller.py",
    ],
)
@pytest.mark.parametrize("bad_range", ["payload", "tool"])
def test_static_scopes_deny_backend_dependencies_and_controller_changes(
    monkeypatch, tmp_path, path, bad_range
):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    def git(_source, *args):
        if args[0] == "diff":
            kind = "payload" if args[-2] == "a" * 40 else "tool"
            return path if kind == bad_range else "docs/research-web-gateway-upgrade.md"
        return ""

    monkeypatch.setattr(g, "git", git)
    with pytest.raises(g.UpdateBlocked, match="gateway_static_scope_changed"):
        g.static_scopes(tmp_path, "a" * 40, "b" * 40, "c" * 40)


@pytest.fixture
def static_artifact(tmp_path, monkeypatch):
    import hashlib
    import json
    import subprocess
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    if not Path("/usr/bin/git").is_file():
        pytest.skip("macOS operator requires system Git")
    source, home = tmp_path / "tool-repo", tmp_path / "artifact-home"
    source.mkdir()
    package = source / g.MODULE_ROOT
    package.mkdir(parents=True)
    for file in Path(g.__file__).parent.glob("*.py"):
        (package / file.name).write_bytes(file.read_bytes())
    latest = (package / "gateway_upgrade.py").read_bytes()
    (package / "gateway_upgrade.py").write_bytes(b"# previous operator fixture\n")

    def git(*args):
        return subprocess.check_output(
            [
                "/usr/bin/git",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-C",
                str(source),
                *args,
            ],
            text=True,
        ).strip()

    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("add", ".")
    git("commit", "-qm", "previous")
    previous = git("rev-parse", "HEAD")
    ui = source / "app/research_web/ui/server/session.mjs"
    ui.parent.mkdir(parents=True)
    ui.write_text("// product UI fixture\n")
    git("add", ".")
    git("commit", "-qm", "payload")
    payload = git("rev-parse", "HEAD")
    (package / "gateway_upgrade.py").write_bytes(latest)
    git("add", ".")
    git("commit", "-qm", "operator")
    tool = git("rev-parse", "HEAD")
    (home / "server/run").mkdir(parents=True, mode=0o700)
    (home / "resident").mkdir(mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"project": str(source)}))
    (home / "Library/LaunchAgents").mkdir(parents=True)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "home", classmethod(lambda cls: home))
        patch.setattr(g, "run", lambda *_a, **_k: "")
        installed = g.install_recovery(home, source, revision=tool)
        assert g.install_recovery(home, source, revision=tool) == installed
    artifact = home / "server/run" / f"gateway-recovery-{installed['artifact_sha256'][:16]}.pyz"
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == installed["artifact_sha256"]
    return source, home, previous, payload, tool, artifact, installed, git


def static_state(recovery, static_artifact, monkeypatch):
    import json
    import zipfile

    g, home, root, state, events, live = recovery
    _source, _home, _previous, _payload, tool, artifact, installed, _git = static_artifact
    with zipfile.ZipFile(artifact) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    (root / "run" / artifact.name).write_bytes(artifact.read_bytes())
    state.update(
        version=2, mode="static-ui", primary=state["target"], tool_revision=tool, recovery=installed
    )
    state["original_config"] = {"revision": state["previous"]}
    state["reviewed"] = {
        "payload": {"app/research_web/ui/server/session.mjs": "d" * 40},
        "tool": {g.TOOL_PATH: "e" * 40},
    }
    monkeypatch.setattr(g, "static_scopes", lambda *_: state["reviewed"])
    monkeypatch.setattr(g, "module_blobs", lambda *_: manifest["modules"])
    monkeypatch.setattr(
        g, "configured", lambda *_: (home / "resident", {"source_common": "fixture-common"})
    )
    old_git = g.git
    monkeypatch.setattr(
        g,
        "git",
        lambda p, *args: (
            "fixture-common"
            if args == ("rev-parse", "--path-format=absolute", "--git-common-dir")
            else old_git(p, *args)
        ),
    )
    return g, home, root, state, events, live


@pytest.mark.parametrize(
    "phase", ["preparing", "draining", "stopped", "starting", "rolling_back", "fallback_starting"]
)
def test_static_recovery_all_phases_keep_original_transaction_guards(
    static_artifact, recovery, monkeypatch, phase
):
    import json

    g, home, root, state, events, live = static_state(recovery, static_artifact, monkeypatch)
    state["phase"] = phase
    if phase == "preparing":
        live["sha"] = state["previous"]
        (root / "resident.json").write_text(json.dumps(state["original_config"]))
    elif phase == "fallback_starting":
        live["sha"] = state["previous"]
        (root / "resident.json").write_text(json.dumps(state["fallback"]))
        live["job"] = False
    elif phase in {"draining", "stopped", "rolling_back"}:
        live["job"] = False
        live["pid"] = None
    result = g.recover_locked(home, state)
    assert result["status"] == ("aborted_before_signal" if phase == "preparing" else "rolled_back")
    assert (
        "restore_code" not in events
        if phase in {"preparing", "fallback_starting"}
        else "restore_code" in events
    )
    assert "clean:c" not in events


def test_real_legacy_recovery_rejects_version_two_before_any_action(
    static_artifact, recovery, monkeypatch
):
    import runpy
    from pathlib import Path

    g, home, _root, state, events, _live = static_state(recovery, static_artifact, monkeypatch)
    fixture = Path(__file__).parents[1] / "fixtures/research_web/gateway_recover_v1.py.txt"
    namespace = runpy.run_path(str(fixture), init_globals=dict(vars(g)))
    with pytest.raises(g.UpdateBlocked, match="gateway_recovery_identity_changed"):
        namespace["recover_locked"](home, state)
    assert events == []


def test_static_artifact_loads_contract_in_fresh_interpreter(static_artifact):
    import os
    import subprocess

    source, _home, previous, payload, tool, artifact, _installed, _git = static_artifact
    code = """import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from resident import gateway_upgrade as g
assert g.PRODUCT != sys.argv[4]
scopes=g.static_scopes(Path(sys.argv[2]),sys.argv[3],sys.argv[4],sys.argv[5])
assert 'app/research_web/ui/server/session.mjs' in scopes['payload']
assert g.TOOL_PATH in scopes['tool']
print('frozen_static_contract_passed')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(artifact), str(source), previous, payload, tool],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert "frozen_static_contract_passed" in result.stdout


@pytest.mark.parametrize(
    "phase", ["preparing", "draining", "stopped", "starting", "rolling_back", "fallback_starting"]
)
def test_frozen_artifact_recovers_each_phase_without_operator_contract_patches(
    static_artifact, tmp_path, phase
):
    import os
    import subprocess
    from pathlib import Path

    source, _home, previous, payload, tool, artifact, _installed, _git = static_artifact
    fixture = Path(__file__).parents[1] / "fixtures/research_web/gateway_static_recovery_runner.py"
    result = subprocess.run(
        [
            sys.executable,
            str(fixture),
            str(artifact),
            str(source),
            str(tmp_path / "frozen-recovery"),
            previous,
            payload,
            tool,
            phase,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "frozen_recovery_phase_passed" in result.stdout


def test_static_artifact_tamper_stops_before_native_actions(static_artifact, recovery, monkeypatch):
    g, home, root, state, events, _live = static_state(recovery, static_artifact, monkeypatch)
    checksum = state["recovery"]["artifact_sha256"]
    (root / "run" / f"gateway-recovery-{checksum[:16]}.pyz").write_bytes(b"changed")
    with pytest.raises(g.UpdateBlocked, match="gateway_recovery_identity_changed"):
        g.recover_locked(home, state)
    assert events == []


def test_static_manifest_cannot_claim_other_git_module_bytes(
    static_artifact, recovery, monkeypatch
):
    import hashlib
    import io
    import zipfile

    g, home, root, state, events, _live = static_state(recovery, static_artifact, monkeypatch)
    old = root / "run" / f"gateway-recovery-{state['recovery']['artifact_sha256'][:16]}.pyz"
    output = io.BytesIO()
    with zipfile.ZipFile(old) as original, zipfile.ZipFile(output, "w") as changed:
        for name in original.namelist():
            changed.writestr(
                name,
                (
                    b"# changed module"
                    if name == "resident/gateway_upgrade.py"
                    else original.read(name)
                ),
            )
    raw = output.getvalue()
    checksum = hashlib.sha256(raw).hexdigest()
    (root / "run" / f"gateway-recovery-{checksum[:16]}.pyz").write_bytes(raw)
    state["recovery"]["artifact_sha256"] = checksum
    with pytest.raises(g.UpdateBlocked, match="gateway_recovery_manifest_changed"):
        g.recover_locked(home, state)
    assert events == []


def test_static_rename_cannot_hide_an_operator_deletion_in_documentation(static_artifact):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    source, _home, previous, _payload, _tool, _artifact, _installed, git = static_artifact
    git("checkout", "--detach", previous)
    (source / "docs").mkdir()
    git("mv", g.TOOL_PATH, "docs/hidden.py")
    git("commit", "-qm", "disallowed rename")
    renamed = git("rev-parse", "HEAD")
    with pytest.raises(g.UpdateBlocked, match="gateway_static_scope_changed"):
        g.static_scopes(source, previous, renamed, renamed)


@pytest.mark.parametrize("identity", ["directory", "git-common"])
def test_static_recovery_refuses_replaced_source_identity(
    static_artifact, recovery, monkeypatch, identity
):
    g, home, _root, state, events, _live = static_state(recovery, static_artifact, monkeypatch)
    if identity == "directory":
        state["project_identity"] = [0, 0]
    else:
        monkeypatch.setattr(g, "git", lambda *_a: "foreign-common")
    with pytest.raises(g.UpdateBlocked, match="gateway_source_identity_changed"):
        g.recover_locked(home, state)
    assert events == []


def test_unrelated_static_helper_leaves_journal_without_acquiring_locks(
    static_artifact, recovery, monkeypatch
):
    import json

    g, home, root, state, events, _live = static_state(recovery, static_artifact, monkeypatch)
    g.write_upgrade_journal(root / "run/gateway-upgrade.json", state)
    monkeypatch.setattr(sys, "argv", [str(root / "run/gateway-recovery-deadbeefdeadbeef.pyz")])
    monkeypatch.setattr(g, "file_lock", lambda *_a, **_k: pytest.fail("wrong helper acquired lock"))
    assert g.recover(home)["status"] == "other_recovery_version"
    assert json.loads((root / "run/gateway-upgrade.json").read_text()) == state
    assert events == []


@pytest.mark.parametrize(
    "phase,expected",
    [
        ("preparing", "deferred"),
        ("draining", "recovery_required"),
        ("starting", "recovery_required"),
    ],
)
def test_busy_cli_distinguishes_pending_recovery(recovery, monkeypatch, phase, expected):
    import io

    g, home, root, state, _events, _live = recovery
    state["phase"] = phase
    g.write_upgrade_journal(root / "run/gateway-upgrade.json", state)
    (home / "logs").mkdir(exist_ok=True)

    def busy(*_a, **_k):
        raise g.MaintenanceBusy("busy")

    monkeypatch.setattr(g, "apply", busy)
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    code = g.main(
        [
            "apply-ui",
            "--home",
            str(home),
            "--source",
            str(home),
            "--primary",
            state["target"],
            "--target",
            state["target"],
            "--expected-gateway",
            state["previous"],
        ]
    )
    assert code == (0 if expected == "deferred" else 1)
    assert expected in output.getvalue()


@pytest.fixture
def ui_apply(server, monkeypatch):
    import json
    import plistlib
    from contextlib import nullcontext
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    root, primary_user, _ = server
    home = root.parent
    (home / "resident").mkdir(mode=0o700)
    source, project = home / "tool", home / "gateway"
    source.mkdir()
    project.mkdir()
    previous, payload, tool = "a" * 40, "b" * 40, "c" * 40
    python = str(Path(sys.prefix) / "bin/python")
    config = {
        "revision": previous,
        "project": str(project),
        "binding": {"primary_user_id": primary_user},
    }
    (root / "resident.json").write_text(json.dumps(config))
    agents = home / "Library/LaunchAgents"
    agents.mkdir(parents=True)
    (agents / (g.LABEL + ".plist")).write_bytes(
        plistlib.dumps(
            {
                "Label": g.LABEL,
                "WorkingDirectory": str(project),
                "ProgramArguments": [
                    python,
                    "-m",
                    "app.research_web.multiuser.resident",
                    "--root",
                    str(root),
                ],
            }
        )
    )
    events = []
    state = {"latest": tool, "sha": previous, "fail": None, "retained": False}

    class Evidence:
        def latest(self):
            events.append("latest")
            return state["latest"]

        def qualify(self, revision):
            events.append("qualify:" + revision[0])
            if state["fail"] == "qualify:" + revision[0]:
                raise g.UpdateBlocked("fixture_qualification_failed")
            return {"sha": revision}

    def git(path, *args):
        if args == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return "fixture-common"
        if args[0] == "switch":
            events.append("switch:" + args[-1][0])
            state["sha"] = args[-1]
        return tool if path == source else state["sha"]

    def scopes(*args):
        assert args == (source, previous, payload, tool)
        if state["fail"] == "scope":
            raise g.UpdateBlocked("gateway_static_scope_changed")
        return {
            "payload": {"app/research_web/ui/server/session.mjs": "d" * 40},
            "tool": {g.TOOL_PATH: "e" * 40},
        }

    def idle(*args):
        assert args == (home, payload)
        events.append("primary_idle")
        if state["fail"] == "active":
            raise g.MaintenanceBusy("active")
        return {"primary_user_id": primary_user}

    def install(actual_home, actual_source, *, revision):
        assert (actual_home, actual_source, revision) == (home, source, tool)
        events.append("install_tool_recovery")
        return {"tool_revision": tool, "artifact_sha256": "f" * 64}

    def identity(actual_home, record):
        assert (
            actual_home,
            record["version"],
            record["mode"],
            record["tool_revision"],
            record["primary"],
            record["target"],
        ) == (home, 2, "static-ui", tool, payload, payload)
        events.append("recovery_verified")

    class Fence:
        def __init__(self, *_a, **_k):
            self.retain = False

        def __enter__(self):
            events.append("fence")
            return self

        def __exit__(self, *_):
            state["retained"] = self.retain

        def release_database(self):
            events.append("release_database")

        @staticmethod
        def recover(*_a, **_k):
            events.append("recover_slots")

    def preservation(_home):
        if state["fail"] == "moved":
            state["latest"] = "d" * 40
        return {"snapshot": "unchanged"}

    def drain(*_):
        events.append("signal")
        if state["fail"] == "drain":
            raise g.MaintenanceBusy("gateway_draining")

    def startup(*_):
        events.append("start")
        if state["fail"] == "start":
            raise g.UpdateBlocked("fixture_start_failed")

    def health(*_a, **_k):
        if state["fail"] == "health":
            raise g.UpdateBlocked("fixture_health_failed")

    def preserved(*_):
        if state["fail"] == "preservation":
            raise g.UpdateBlocked("fixture_preservation_failed")

    monkeypatch.setattr(g.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(
        g,
        "configured",
        lambda *_: (
            home / "resident",
            {
                "project": str(Path(sys.prefix).parent),
                "gh": "/fixture/gh",
                "repository": "owner/repo",
                "source_common": "fixture-common",
            },
        ),
    )
    monkeypatch.setattr(g, "file_lock", lambda *_a, **_k: nullcontext())
    monkeypatch.setattr(g, "GitHubEvidence", lambda *_: Evidence())
    monkeypatch.setattr(g, "git", git)
    monkeypatch.setattr(g, "clean", lambda *_: None)
    monkeypatch.setattr(g, "static_scopes", scopes)
    monkeypatch.setattr(g, "verify_primary", idle)
    monkeypatch.setattr(g, "verify_signal_contract", lambda: None)
    monkeypatch.setattr(g, "job_pid", lambda: 111)
    monkeypatch.setattr(g, "native_image", lambda *_: Path(python).resolve())
    monkeypatch.setattr(
        g,
        "process",
        lambda *_: "Mon Jan 1 00:00:00 2026 "
        + " ".join([python, "-m", "app.research_web.multiuser.resident", "--root", str(root)]),
    )
    monkeypatch.setattr(g, "listener_pids", lambda: {111})
    monkeypatch.setattr(g, "no_children", lambda *_: None)
    monkeypatch.setattr(g, "no_private_processes", lambda *_: None)
    monkeypatch.setattr(g, "install_recovery", install)
    monkeypatch.setattr(g, "static_recovery_identity", identity)
    monkeypatch.setattr(g, "BirthFence", Fence)
    monkeypatch.setattr(g, "preservation", preservation)
    monkeypatch.setattr(g, "graceful_drain", drain)
    monkeypatch.setattr(g, "bootout_after_drain", lambda *_: events.append("bootout"))
    monkeypatch.setattr(g, "bootstrap", startup)
    monkeypatch.setattr(g, "wait_health", health)
    monkeypatch.setattr(g, "preserved", preserved)
    return g, home, root, source, previous, payload, tool, state, events


def test_apply_ui_qualifies_tool_and_payload_and_never_deploys_tool(ui_apply):
    import json

    g, home, root, source, previous, payload, tool, state, events = ui_apply
    result = g.apply(home, source, payload, payload, expected_gateway=previous)
    assert result["status"] == "deployed"
    assert events.index("qualify:b") < events.index("install_tool_recovery")
    assert events.index("qualify:c") < events.index("install_tool_recovery")
    assert events.index("recovery_verified") < events.index("signal")
    assert "switch:b" in events and "switch:c" not in events
    assert state["sha"] == payload
    assert json.loads((root / "resident.json").read_text())["revision"] == payload
    journal = json.loads((root / "run/gateway-upgrade-original.json").read_text())
    assert journal["tool_revision"] == tool
    assert journal["proof"]["sha"] == payload and journal["tool_proof"]["sha"] == tool


def test_apply_ui_requires_payload_equal_to_actual_primary(ui_apply):
    g, home, root, source, previous, payload, _tool, _state, events = ui_apply
    with pytest.raises(g.UpdateBlocked, match="gateway_static_revision_invalid"):
        g.apply(home, source, payload, "d" * 40, expected_gateway=previous)
    assert "signal" not in events and "install_tool_recovery" not in events
    assert not (root / "run/gateway-upgrade.json").exists()


@pytest.mark.parametrize("failure", ["qualify:b", "qualify:c", "scope", "baseline", "active"])
def test_apply_ui_admission_failures_do_not_signal_or_write_journal(ui_apply, failure):
    g, home, root, source, previous, payload, _tool, state, events = ui_apply
    state["fail"] = failure
    expected = "d" * 40 if failure == "baseline" else previous
    with pytest.raises((g.UpdateBlocked, g.MaintenanceBusy)):
        g.apply(home, source, payload, payload, expected_gateway=expected)
    assert "signal" not in events and "install_tool_recovery" not in events
    assert not (root / "run/gateway-upgrade.json").exists()
    assert state["sha"] == previous


def test_apply_ui_master_move_after_fence_aborts_before_signal(ui_apply):
    g, home, root, source, previous, payload, _tool, state, events = ui_apply
    state["fail"] = "moved"
    with pytest.raises(g.UpdateBlocked, match="resident_master_moved"):
        g.apply(home, source, payload, payload, expected_gateway=previous)
    assert "recover_slots" in events and "signal" not in events
    assert not (root / "run/gateway-upgrade.json").exists()


def test_apply_ui_signal_timeout_retains_recoverable_journal(ui_apply):
    import json

    g, home, root, source, previous, payload, _tool, state, events = ui_apply
    state["fail"] = "drain"
    with pytest.raises(g.MaintenanceBusy):
        g.apply(home, source, payload, payload, expected_gateway=previous)
    assert state["retained"] is True
    assert "bootout" not in events and state["sha"] == previous
    assert json.loads((root / "run/gateway-upgrade.json").read_text())["phase"] == "draining"


@pytest.mark.parametrize("failure", ["start", "health", "preservation"])
def test_apply_ui_candidate_failure_dispatches_exact_version_two_rollback(
    ui_apply, monkeypatch, failure
):
    g, home, _root, source, previous, payload, tool, state, _events = ui_apply
    state["fail"] = failure
    recovered = []

    def rollback(actual_home, record):
        recovered.append(
            (
                actual_home,
                record["version"],
                record["mode"],
                record["tool_revision"],
                record["target"],
                record["previous"],
            )
        )
        return {"status": "rolled_back"}

    monkeypatch.setattr(g, "recover_locked", rollback)
    assert (
        g.apply(home, source, payload, payload, expected_gateway=previous)["status"]
        == "rolled_back"
    )
    assert recovered == [(home, 2, "static-ui", tool, payload, previous)]


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS kernel process image")
def test_native_python_image_matches_framework_exec_instead_of_launcher():
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    image = g.native_image(os.getpid())
    command = g.process(os.getpid()).split(maxsplit=5)[-1]
    assert any(
        command.startswith(str(path) + " ")
        for path in (image, sys.executable, Path(sys.executable).resolve())
    )


def test_foreign_kernel_image_is_never_signalled(monkeypatch):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    monkeypatch.setattr(g, "verify_signal_contract", lambda: None)
    monkeypatch.setattr(g, "native_image", lambda pid: "own" if pid == os.getpid() else "foreign")
    monkeypatch.setattr(
        g.os, "kill", lambda *_: pytest.fail("foreign executable must not be signalled")
    )
    with pytest.raises(g.UpdateBlocked, match="gateway_image_changed"):
        g.graceful_drain(2000000000, "signature", "command")


@pytest.mark.parametrize("pid", [0, -1, True, 0x80000000])
def test_invalid_kernel_pid_is_rejected(pid):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    with pytest.raises(g.UpdateBlocked, match="gateway_image_unverified"):
        g.native_image(pid)


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "server"
    root.mkdir(mode=0o700)
    (root / "users").mkdir(mode=0o700)
    (root / "run").mkdir(mode=0o700)
    primary, user = str(uuid4()), str(uuid4())
    db = sqlite3.connect(root / "accounts.sqlite3")
    db.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY)")
    db.executemany("INSERT INTO accounts VALUES (?)", [(primary,), (user,)])
    db.commit()
    db.close()
    (root / "accounts.sqlite3").chmod(0o600)
    return root, primary, user


def test_fence_blocks_database_writers_and_native_birth_after_exists_check(server):
    root, primary, user = server
    owner = root / "users" / user / "state/owner.json"
    assert not owner.exists()  # native may have passed its earlier exists check
    with BirthFence(root, primary):
        with pytest.raises(FileExistsError):
            os.open(owner, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        db = sqlite3.connect(root / "accounts.sqlite3", timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                db.execute("BEGIN IMMEDIATE")
        finally:
            db.close()
    assert not owner.exists()


def test_native_winner_is_preserved_and_never_disposed(server):
    root, primary, user = server
    owner = root / "users" / user / "state/owner.json"
    owner.parent.mkdir(parents=True, mode=0o700)
    owner.parent.parent.chmod(0o700)
    owner.write_bytes(b"native-owner-bytes")
    owner.chmod(0o600)
    with pytest.raises(FenceBlocked, match="private_pool_not_empty"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert owner.read_bytes() == b"native-owner-bytes"


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_unknown_sqlite_sidecar_is_not_opened_or_recovered(server, suffix):
    root, primary, _ = server
    sidecar = root / ("accounts.sqlite3" + suffix)
    sidecar.write_bytes(b"unknown")
    with pytest.raises(FenceBlocked, match="database_sidecar_unknown"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert sidecar.read_bytes() == b"unknown"


def test_crash_after_publish_can_remove_only_its_own_reservation(server):
    root, primary, user = server
    fence = BirthFence(root, primary)
    fence.__enter__()
    fence.db.rollback()
    fence.db.close()
    fence.db = None
    BirthFence.recover(root)
    assert not (root / "users" / user / "state/owner.json").exists()


def test_recovery_never_removes_a_replaced_slot(server):
    root, primary, user = server
    fence = BirthFence(root, primary)
    fence.__enter__()
    owner = root / "users" / user / "state/owner.json"
    (owner / "reservation").unlink()
    owner.rmdir()
    owner.write_bytes(b"foreign")
    owner.chmod(0o600)
    fence.db.rollback()
    fence.db.close()
    fence.db = None
    with pytest.raises(FenceBlocked, match="reservation_changed"):
        BirthFence.recover(root)
    assert owner.read_bytes() == b"foreign"


def test_unknown_user_directory_is_deferred(server):
    root, primary, _ = server
    (root / "users" / str(uuid4())).mkdir(mode=0o700)
    with pytest.raises(FenceBlocked, match="unknown_user_directory"), BirthFence(root, primary):
        pytest.fail("must defer")


def test_another_fences_journal_is_never_recovered_on_enter_failure(server):
    root, primary, user = server
    with BirthFence(root, primary):
        journal = (root / "run/birth-fence.json").read_bytes()
        with (
            pytest.raises(FenceBlocked, match="birth_fence_recovery_required"),
            BirthFence(root, primary),
        ):
            pytest.fail("must defer")
        assert (root / "run/birth-fence.json").read_bytes() == journal
        assert (root / "users" / user / "state/owner.json").is_dir()


def test_native_wins_publication_race_without_being_removed(server, monkeypatch):
    from research_workbench_entrypoint.resident import gateway_fence as module

    root, primary, user = server
    original = module.exclusive_rename
    owner = root / "users" / user / "state/owner.json"

    def race(source, destination):
        if destination == owner:
            owner.write_bytes(b"native winner")
            owner.chmod(0o600)
        original(source, destination)

    monkeypatch.setattr(module, "exclusive_rename", race)
    with pytest.raises(FenceBlocked, match="private_pool_not_empty"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert owner.read_bytes() == b"native winner"


@pytest.mark.parametrize("name", ["auth.json", "gateway.key", "unknown.json"])
def test_no_owner_with_unknown_control_is_not_empty(server, name):
    root, primary, user = server
    state = root / "users" / user / "state"
    state.mkdir(parents=True, mode=0o700)
    state.parent.chmod(0o700)
    (state / name).write_bytes(b"private control")
    with pytest.raises(FenceBlocked, match="private_control_unknown"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert (state / name).read_bytes() == b"private control"


def test_release_crash_after_marker_unlink_is_recoverable(server, monkeypatch):
    root, primary, _ = server
    fence = BirthFence(root, primary)
    fence.__enter__()
    original = type(root).rmdir
    failed = False

    def interrupted(path):
        nonlocal failed
        if path.name.startswith("birth-slot-") and not failed:
            failed = True
            raise OSError("simulated crash")
        return original(path)

    monkeypatch.setattr(type(root), "rmdir", interrupted)
    with pytest.raises(OSError, match="simulated"):
        fence.__exit__()
    BirthFence.recover(root)
    assert not (root / "run/birth-fence.json").exists()


def test_graceful_timeout_never_escalates_signal(monkeypatch):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    command = "python -m app.research_web.multiuser.resident --root /owned"
    signature = "Tue Oct 20 12:00:00 2026 " + command
    signals = []
    monkeypatch.setattr(g, "process", lambda pid: signature)
    monkeypatch.setattr(g, "verify_signal_contract", lambda: None)
    monkeypatch.setattr(g, "native_image", lambda _: "same-image")
    monkeypatch.setattr(g, "listener_pids", lambda: {123})
    monkeypatch.setattr(g, "no_children", lambda pid: None)
    monkeypatch.setattr(g.os, "kill", lambda pid, sig: signals.append(sig))
    from research_workbench_entrypoint.resident.admission import MaintenanceBusy

    with pytest.raises(MaintenanceBusy, match="gateway_draining"):
        g.graceful_drain(123, signature, command, timeout=0)
    assert signals == [g.signal.SIGTERM]


def test_changed_listener_never_receives_signal(monkeypatch):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    command = "python -m app.research_web.multiuser.resident --root /owned"
    signature = "Tue Oct 20 12:00:00 2026 " + command
    monkeypatch.setattr(g, "process", lambda pid: signature)
    monkeypatch.setattr(g, "verify_signal_contract", lambda: None)
    monkeypatch.setattr(g, "native_image", lambda _: "same-image")
    monkeypatch.setattr(g, "listener_pids", lambda: {999})
    monkeypatch.setattr(g.os, "kill", lambda *_: pytest.fail("unknown PID must not be signalled"))
    with pytest.raises(g.UpdateBlocked, match="gateway_listener_unknown"):
        g.graceful_drain(123, signature, command)


@pytest.mark.parametrize(
    "failure", [None, "bootstrap", "wait_health", "verify_primary", "preserved"]
)
def test_candidate_success_and_every_post_switch_failure_enter_rollback(
    tmp_path, monkeypatch, failure
):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    home = tmp_path
    (home / "server/run").mkdir(parents=True, mode=0o700)
    events = []
    state = {
        "project": str(tmp_path / "project"),
        "target": "b" * 40,
        "previous": "a" * 40,
        "primary": g.PRODUCT,
        "updated": {"revision": "b" * 40},
        "before": {},
        "phase": "stopped",
    }
    monkeypatch.setattr(g, "git", lambda *_: events.append("switch"))
    monkeypatch.setattr(g, "write_config", lambda *_: events.append("config"))
    for name in ("bootstrap", "wait_health", "verify_primary", "preserved"):

        def step(*_, _name=name, **__):
            events.append(_name)
            if failure == _name:
                raise g.UpdateBlocked("injected_failure")

        monkeypatch.setattr(g, name, step)
    monkeypatch.setattr(
        g, "recover_locked", lambda *_: events.append("rollback") or {"status": "rolled_back"}
    )
    result = g.activate_gateway(home, state, tmp_path / "job.plist")
    assert result["status"] == ("rolled_back" if failure else "deployed")
    if failure:
        assert events[-1] == "rollback"
    else:
        assert not (home / "server/run/gateway-upgrade.json").exists()
        assert events == [
            "switch",
            "config",
            "bootstrap",
            "wait_health",
            "verify_primary",
            "preserved",
        ]


def test_recovery_installer_reuses_identical_qualified_artifact(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    home, source = tmp_path / "home", tmp_path / "source"
    (home / "server/run").mkdir(parents=True, mode=0o700)
    (home / "resident").mkdir(mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"project": str(source)}))
    (home / "Library/LaunchAgents").mkdir(parents=True)
    package = source / "research_workbench_entrypoint/resident"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "gateway_upgrade.py").write_text("# frozen test artifact")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(g, "run", lambda *_args, **_kwargs: "")
    first = g.install_recovery(home, source)
    assert g.install_recovery(home, source) == first
    (package / "gateway_upgrade.py").write_text("# changed")
    with pytest.raises(g.UpdateBlocked, match="gateway_recovery_artifact_changed"):
        g.install_recovery(home, source)


@pytest.fixture
def recovery(server, monkeypatch):
    import json
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    root, primary, _user = server
    home = root.parent
    project = home / "project"
    project.mkdir(mode=0o700)
    agents = home / "Library/LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / (g.LABEL + ".plist")
    plist.write_bytes(b"test job identity")
    artifact = root / "run/gateway-recovery.pyz"
    artifact.write_bytes(b"frozen test operator")
    state = {
        "version": 1,
        "phase": "starting",
        "primary": g.PRODUCT,
        "previous": "a" * 40,
        "target": "b" * 40,
        "project": str(project),
        "project_identity": [project.stat().st_dev, project.stat().st_ino],
        "old_pid": 111,
        "old_signature": "old",
        "command": "exact candidate command",
        "transaction": str(uuid4()),
        "original_config": {"revision": "b" * 40},
        "fallback": {"revision": "a" * 40, "binding": {"primary_user_id": primary}},
        "updated": {"revision": "b" * 40},
        "before": {"original": "hashes"},
        "plist_sha256": g.digest(plist),
        "recovery": {"artifact_sha256": g.digest(artifact)},
    }
    (root / "resident.json").write_text(json.dumps(state["updated"]))
    (root / "run/gateway-upgrade.json").write_text(json.dumps(state))
    events, live = [], {"job": True, "pid": 222, "sha": state["target"]}
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(g, "verify_primary", lambda *_: events.append("primary_idle"))
    monkeypatch.setattr(g, "clean", lambda _p, sha: events.append("clean:" + sha[0]))
    monkeypatch.setattr(g, "no_private_processes", lambda *_: None)
    monkeypatch.setattr(g, "process", lambda pid: None if pid == 111 else "candidate")
    monkeypatch.setattr(g, "job_state", lambda: "registered" if live["job"] else None)
    monkeypatch.setattr(g, "job_pid", lambda: live["pid"])

    def drain(*_):
        events.append("drain")
        live["pid"] = None

    monkeypatch.setattr(g, "graceful_drain", drain)

    def command(argv, **_):
        assert "bootout" in argv
        events.append("bootout")
        live["job"] = False
        return ""

    monkeypatch.setattr(g, "run", command)

    def git(_p, *args):
        if args[0] == "switch":
            events.append("restore_code")
            live["sha"] = args[-1]
        return live["sha"]

    monkeypatch.setattr(g, "git", git)
    monkeypatch.setattr(g, "preserved", lambda *_: events.append("preserved"))
    monkeypatch.setattr(g, "bootstrap", lambda *_: events.append("start_fallback"))
    monkeypatch.setattr(
        g, "wait_health", lambda config, **_: events.append("health:" + config["revision"][0])
    )
    return g, home, root, state, events, live


def test_actual_rollback_restores_matching_binding_without_touching_data(recovery):
    import json

    g, home, root, state, events, _ = recovery
    business = root / "untouched-business.txt"
    business.write_bytes(b"existing session contents")
    result = g.recover_locked(home, state)
    assert result["status"] == "rolled_back"
    assert json.loads((root / "resident.json").read_text()) == state["fallback"]
    assert business.read_bytes() == b"existing session contents"
    assert events == [
        "primary_idle",
        "clean:b",
        "drain",
        "bootout",
        "clean:b",
        "restore_code",
        "preserved",
        "start_fallback",
        "health:a",
    ]
    assert not (root / "run/gateway-upgrade.json").exists()


def test_recovery_of_inflight_legacy_drain_waits_without_stopping(recovery, monkeypatch):
    g, home, _root, state, events, _ = recovery
    state["phase"] = "draining"
    from research_workbench_entrypoint.resident.admission import MaintenanceBusy

    signature = "Tue Oct 20 12:00:00 2026 " + state["command"]
    monkeypatch.setattr(g, "process", lambda _: signature)

    def pending(*_):
        raise MaintenanceBusy("gateway_draining")

    monkeypatch.setattr(g, "graceful_drain", pending)
    with pytest.raises(MaintenanceBusy, match="gateway_draining"):
        g.recover_locked(home, state)
    assert events == ["primary_idle", "primary_idle"]


def test_recovery_after_legacy_exit_reacquires_birth_fence(recovery, monkeypatch):
    g, home, _root, state, events, live = recovery
    state["phase"] = "draining"
    live["pid"] = None
    monkeypatch.setattr(g, "bootout_after_drain", lambda _: live.update(job=False))
    assert g.recover_locked(home, state)["status"] == "rolled_back"
    assert "restore_code" in events


def test_recovery_artifact_tamper_blocks_before_process_operation(recovery):
    g, home, root, state, events, _ = recovery
    (root / "run/gateway-recovery.pyz").write_bytes(b"changed")
    with pytest.raises(g.UpdateBlocked, match="gateway_recovery_identity_changed"):
        g.recover_locked(home, state)
    assert events == []


def test_uvicorn_repeated_sigterm_never_enables_force_exit():
    import signal

    import uvicorn
    from uvicorn.server import Server

    config = uvicorn.Config(app=None)
    server = Server(config)
    server.handle_exit(signal.SIGTERM, None)
    server.handle_exit(signal.SIGTERM, None)
    assert server.should_exit is True and server.force_exit is False
    assert config.timeout_graceful_shutdown is None


def test_preparing_crash_aborts_only_owned_slots_without_stopping(recovery):
    g, home, root, state, events, _ = recovery
    state["phase"] = "preparing"
    fence = BirthFence(
        root, state["fallback"]["binding"]["primary_user_id"], transaction=state["transaction"]
    )
    fence.__enter__()
    fence.release_database()
    assert g.recover_locked(home, state)["status"] == "aborted_before_signal"
    assert events == ["primary_idle", "clean:a"]
    assert not (root / "run/birth-fence.json").exists()


@pytest.mark.parametrize("phase", ["rolling_back", "fallback_starting"])
def test_recovery_reenters_partial_rollback_without_stopping_old_service(recovery, phase):
    g, home, _root, state, events, live = recovery
    state["phase"] = phase
    live.update(job=False, pid=None, sha=state["previous"])
    if phase == "fallback_starting":
        g.write_config(home / "server/resident.json", state["fallback"])
    assert g.recover_locked(home, state)["status"] == "rolled_back"
    assert "drain" not in events


@pytest.mark.parametrize("failure", ["signal", "bootout", "journal"])
def test_every_post_signal_failure_keeps_birth_fence(recovery, monkeypatch, failure):
    g, home, root, state, _events, live = recovery
    state["phase"] = "draining"
    signature = "Tue Oct 20 12:00:00 2026 " + state["command"]
    monkeypatch.setattr(g, "process", lambda _: signature)

    def fail(*_args, **_kwargs):
        raise g.UpdateBlocked("injected_post_signal_failure")

    if failure == "signal":
        monkeypatch.setattr(g, "graceful_drain", fail)
    elif failure == "bootout":
        monkeypatch.setattr(g, "bootout_after_drain", fail)
    else:
        monkeypatch.setattr(g, "bootout_after_drain", lambda _: live.update(job=False))
        monkeypatch.setattr(g, "atomic", fail)
    with pytest.raises(g.UpdateBlocked, match="injected_post_signal_failure"):
        g.recover_locked(home, state)
    assert (root / "run/birth-fence.json").exists()
    assert list((root / "users").glob("*/state/owner.json"))


def test_real_uvicorn_drains_slow_request_after_two_sigterms(tmp_path):
    """Native subprocess evidence; no resident port, user data or model is used."""
    import concurrent.futures
    import http.client
    import signal
    import socket
    import subprocess
    import sys
    import time

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    started = tmp_path / "request-started"
    completed = tmp_path / "request-completed"
    script = """import asyncio,sys,uvicorn
from pathlib import Path
from fastapi import FastAPI
app=FastAPI()
@app.get("/slow")
async def slow():
    Path(sys.argv[2]).write_text("started")
    await asyncio.to_thread(__import__("time").sleep, 1.5)
    Path(sys.argv[3]).write_text("completed")
    return {"completed":True}
uvicorn.run(app,host="127.0.0.1",port=int(sys.argv[1]),log_config=None,access_log=False)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(port), str(started), str(completed)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def request():
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request("GET", "/slow")
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    try:
        deadline = time.monotonic() + 8
        while True:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.02)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(request)
            while not started.exists():
                assert time.monotonic() < deadline
                time.sleep(0.02)
            process.send_signal(signal.SIGTERM)
            time.sleep(0.05)
            process.send_signal(signal.SIGTERM)
            time.sleep(0.1)
            assert process.poll() is None and not completed.exists()
            assert pending.result(timeout=5)[0] == 200
            assert completed.read_text() == "completed"
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()  # Only this test-owned disposable subprocess, after failure.
            process.wait(timeout=5)


def test_full_size_preservation_journal_uses_recovery_entrypoint(recovery, monkeypatch):
    import json

    g, home, root, state, _events, _live = recovery
    state["before"]["files"] = {f"session/file-{n:05}.txt": "a" * 64 for n in range(14000)}
    journal = root / "run/gateway-upgrade.json"
    journal.write_text(json.dumps(state, indent=2))
    journal.chmod(0o600)
    assert journal.stat().st_size > 1_000_000
    with pytest.raises(g.UpdateBlocked, match="resident_record_invalid"):
        g.read_json(journal)  # The general configuration limit is unchanged.
    resident = home / "resident"
    resident.mkdir(mode=0o700)
    monkeypatch.setattr(g, "configured", lambda _: (resident, {"project": state["project"]}))
    assert g.recover(home)["status"] == "rolled_back"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS delayed native reaping")
def test_real_graceful_drain_waits_for_delayed_parent_reap(monkeypatch):
    import subprocess
    import threading
    import time

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        deadline = time.monotonic() + 5
        while g.native_image(child.pid) != g.native_image(os.getpid()):
            assert time.monotonic() < deadline
            time.sleep(0.01)
        signature = g.process(child.pid)
        command = signature.split(maxsplit=5)[-1]
        monkeypatch.setattr(g, "listener_pids", lambda: set())

        def reap():
            time.sleep(0.6)
            child.wait(timeout=5)

        reaper = threading.Thread(target=reap)
        reaper.start()
        g.graceful_drain(child.pid, signature, command, timeout=5)
        reaper.join(timeout=5)
        assert child.returncode is not None
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)


def test_journal_reader_exact_limit_and_over_limit(tmp_path, monkeypatch):
    import json

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    monkeypatch.setattr(g, "JOURNAL_MAX_BYTES", 1024)
    empty = json.dumps({"padding": ""}, separators=(",", ":")).encode()
    payload = "x" * (1024 - len(empty))
    raw = json.dumps({"padding": payload}, separators=(",", ":")).encode()
    path = tmp_path / "gateway-upgrade.json"
    path.write_bytes(raw)
    path.chmod(0o600)
    assert len(raw) == 1024 and g.read_upgrade_journal(path)["padding"] == payload
    path.write_bytes(raw + b" ")
    with pytest.raises(g.UpdateBlocked, match="gateway_journal_invalid"):
        g.read_upgrade_journal(path)


@pytest.mark.parametrize("case", ["mode", "symlink", "hardlink", "replace", "short"])
def test_journal_reader_rejects_untrusted_or_changing_file(tmp_path, monkeypatch, case):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    path = tmp_path / "gateway-upgrade.json"
    path.write_bytes(b'{"a":1} ')
    path.chmod(0o600)
    if case == "mode":
        path.chmod(0o644)
    if case == "symlink":
        other = tmp_path / "original"
        path.rename(other)
        path.symlink_to(other)
    if case == "hardlink":
        os.link(path, tmp_path / "other")
    if case in {"replace", "short"}:
        original = g.os.fdopen

        class Reader:
            def __init__(self, fd, *args):
                self.stream = original(fd, *args)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def fileno(self):
                return self.stream.fileno()

            def read(self, limit):
                raw = self.stream.read(limit)
                if case == "short":
                    return raw[:-1]
                replacement = tmp_path / "replacement"
                replacement.write_bytes(raw)
                replacement.chmod(0o600)
                replacement.replace(path)
                return raw

        monkeypatch.setattr(g.os, "fdopen", Reader)
    with pytest.raises(g.UpdateBlocked, match="gateway_journal_invalid"):
        g.read_upgrade_journal(path)


def test_oversized_journal_is_rejected_before_signal_or_write(tmp_path, monkeypatch):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    monkeypatch.setattr(g, "JOURNAL_MAX_BYTES", 8192)
    state = {"phase": "draining", "before": {"payload": "x" * 5000}}
    monkeypatch.setattr(g.os, "kill", lambda *_: pytest.fail("must not signal"))
    with pytest.raises(g.UpdateBlocked, match="gateway_journal_oversized"):
        g.journal_preflight(state)
    state["before"]["payload"] = "x" * 9000
    path = tmp_path / "gateway-upgrade.json"
    with pytest.raises(g.UpdateBlocked, match="gateway_journal_oversized"):
        g.write_upgrade_journal(path, state)
    assert not path.exists()


def test_changed_pid_after_signal_stays_deferred_without_resignal(monkeypatch):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    monkeypatch.setattr(g, "process", lambda _: "changed or unreaped")
    monkeypatch.setattr(g.os, "kill", lambda *_: pytest.fail("must not signal"))
    from research_workbench_entrypoint.resident.admission import MaintenanceBusy

    with pytest.raises(MaintenanceBusy, match="gateway_draining"):
        g.wait_retired(123, timeout=0)


def test_immutable_artifact_main_reads_large_recovery_input(tmp_path, monkeypatch):
    import json
    import subprocess
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    home = tmp_path / "home"
    run = home / "server/run"
    run.mkdir(parents=True, mode=0o700)
    (home / "resident").mkdir(mode=0o700)
    (home / "logs").mkdir(mode=0o700)
    (home / "Library/LaunchAgents").mkdir(parents=True)
    (home / "resident/config.json").write_text(json.dumps({"project": str(home / "project")}))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(g, "run", lambda *_args, **_kwargs: "")
    g.install_recovery(home, Path(g.__file__).resolve().parents[2])
    journal = run / "gateway-upgrade.json"
    journal.write_text(json.dumps({"padding": "x" * 1_100_000}))
    journal.chmod(0o600)
    script = """import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from resident import gateway_upgrade as g
h=Path(sys.argv[2])
g.configured=lambda home:(h/'resident',{'project':str(h/'project')})
# Only business/Git/launchd side effects are isolated; artifact main, recover,
# admission locks and bounded reader remain the actual immutable implementations.
g.recover_locked=lambda home,state:{'status':'fixture_input_checked','bytes':len(state['padding']),'module':g.__file__}
raise SystemExit(g.main(['recover','--home',str(h)]))
"""
    process = subprocess.run(
        [sys.executable, "-I", "-c", script, str(run / "gateway-recovery.pyz"), str(home)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["bytes"] == 1_100_000 and "gateway-recovery.pyz/" in result["module"]


def test_fifo_journal_is_rejected_without_blocking(tmp_path):
    import subprocess
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    path = tmp_path / "gateway-upgrade.json"
    os.mkfifo(path, 0o600)
    script = """import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from research_workbench_entrypoint.resident.gateway_upgrade import read_upgrade_journal,UpdateBlocked
try:read_upgrade_journal(Path(sys.argv[2]))
except UpdateBlocked as error:print(str(error))
else:raise SystemExit(2)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            script,
            str(Path(g.__file__).resolve().parents[2]),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    assert result.returncode == 0 and result.stdout.strip() == "gateway_journal_invalid"
