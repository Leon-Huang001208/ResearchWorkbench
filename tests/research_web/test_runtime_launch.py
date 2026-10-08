import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from app.research_web import launch_runtime
from app.research_web.mcp_runtime.authorization import AuthorizationManager


def test_persistent_acceptance_budget_cold_reopen_never_refunds(tmp_path):
    import importlib
    from datetime import UTC, datetime

    helper = Path(launch_runtime.__file__).with_name("live_acceptance_budget.py")
    assert helper.is_file(), "persistent acceptance budget helper is missing"
    budget = importlib.import_module("app.research_web.live_acceptance_budget")
    now = datetime(2026, 10, 8, 11, tzinfo=UTC)
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    root = parent / ("b" * 32)
    control = budget.authorization(3, 512, "2026-10-08T11:30:00Z")
    budget.BudgetStore.initialize(root, "b" * 32, control, clock=lambda: now)
    for expected in range(1, 4):
        store = budget.BudgetStore(root, "b" * 32, clock=lambda: now)
        assert store.describe()["maxOutputTokens"] == 512
        assert store.reserve(512)["ticket"] == expected
    with pytest.raises(budget.BudgetError, match="acceptance_budget_exhausted"):
        budget.BudgetStore(root, "b" * 32, clock=lambda: now).reserve(512)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_exists"):
        budget.BudgetStore.initialize(root, "b" * 32, control, clock=lambda: now)
    assert control["totalInputTokens"] == 3145728
    assert control["totalOutputTokens"] == 1536
    assert control["totalMicroUsd"] == 945564


def budget_fixture(tmp_path):
    from datetime import UTC, datetime

    from app.research_web import live_acceptance_budget as budget

    now = datetime(2026, 10, 8, 11, tzinfo=UTC)
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    root = parent / ("b" * 32)
    control = budget.authorization(3, 512, "2026-10-08T11:30:00Z")
    budget.BudgetStore.initialize(root, "b" * 32, control, clock=lambda: now)
    return budget, root, now


def test_acceptance_budget_init_fsync_failure_closes_new_lock_fd(tmp_path, monkeypatch):
    budget, root, now = budget_fixture(tmp_path)
    candidate = root.parent / ("c" * 32)
    original_open, original_close, original_fsync = budget.os.open, budget.os.close, budget.os.fsync
    opened = []
    closed = []

    def open_fd(path, *args, **kwargs):
        descriptor = original_open(path, *args, **kwargs)
        if path == "budget.lock":
            opened.append(descriptor)
        return descriptor

    def close_fd(descriptor):
        if descriptor in opened:
            closed.append(descriptor)
        original_close(descriptor)

    def fsync_fd(descriptor):
        if descriptor in opened:
            raise OSError("synthetic lock fsync failure")
        original_fsync(descriptor)

    monkeypatch.setattr(budget.os, "open", open_fd)
    monkeypatch.setattr(budget.os, "close", close_fd)
    monkeypatch.setattr(budget.os, "fsync", fsync_fd)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_unavailable"):
        budget.BudgetStore.initialize(
            candidate,
            "c" * 32,
            budget.authorization(3, 512, "2026-10-08T11:30:00Z"),
            clock=lambda: now,
        )
    assert len(opened) == 1
    assert closed == opened, "init leaked its newly created permanent-lock descriptor"
    assert not (candidate / "control.json").exists()
    assert not (candidate / "ledger.json").exists()


def test_acceptance_budget_all_function_contracts_are_annotated():
    import ast

    source = Path(launch_runtime.__file__).with_name("live_acceptance_budget.py").read_text()
    tree = ast.parse(source)
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.returns is None or any(
            arg.annotation is None for arg in args if arg.arg not in {"self", "cls"}
        ):
            missing.append(node.name)
    assert missing == [], f"budget function bodies lack typed contracts: {missing}"


def test_acceptance_budget_optional_discovery_is_read_only_for_genuine_missing_paths(tmp_path):
    from datetime import UTC, datetime

    from app.research_web import live_acceptance_budget as budget

    base = tmp_path / "private"
    namespace = base / "live-acceptance"
    root = namespace / ("b" * 32)
    store = budget.BudgetStore(root, "b" * 32, clock=lambda: datetime(2026, 10, 8, 11, tzinfo=UTC))
    discover = getattr(store, "read_optional", None)
    assert callable(discover), "safe optional budget discovery is missing"
    for existing in (None, base, namespace):
        if existing is not None:
            existing.mkdir(mode=0o700)
        assert discover() is None
        assert not root.exists()
        assert not (root / "budget.lock").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "empty_leaf",
        "lock_missing",
        "control_missing",
        "ledger_missing",
        "corrupt",
        "expired",
        "identity_mismatch",
        "broken_base_alias",
        "namespace_alias",
        "leaf_alias",
        "base_mode",
        "namespace_mode",
        "leaf_mode",
    ],
)
def test_optional_budget_existing_unsafe_or_partial_installation_never_falls_back(
    tmp_path, mutation
):
    from datetime import UTC, datetime, timedelta

    from app.research_web import live_acceptance_budget as budget

    base = tmp_path / "private"
    namespace = base / "live-acceptance"
    root = namespace / ("b" * 32)
    base.mkdir(mode=0o700)
    namespace.mkdir(mode=0o700)
    now = datetime(2026, 10, 8, 11, tzinfo=UTC)
    if mutation == "empty_leaf":
        root.mkdir(mode=0o700)
    else:
        budget.BudgetStore.initialize(
            root, "b" * 32, budget.authorization(3, 512, "2026-10-08T11:30:00Z"), clock=lambda: now
        )
    if mutation.endswith("_missing"):
        (
            root
            / {
                "lock_missing": "budget.lock",
                "control_missing": "control.json",
                "ledger_missing": "ledger.json",
            }[mutation]
        ).unlink()
    elif mutation == "corrupt":
        (root / "control.json").write_bytes(b"not-json")
    elif mutation == "expired":
        now += timedelta(minutes=30)
    elif mutation == "identity_mismatch":
        record = json.loads((root / "control.json").read_bytes())
        record["installationId"] = "c" * 32
        (root / "control.json").write_bytes(budget._encode(record))
    elif mutation.endswith("alias"):
        path = {"broken_base_alias": base, "namespace_alias": namespace, "leaf_alias": root}[
            mutation
        ]
        path.rename(path.with_name(path.name + "-saved"))
        path.symlink_to(tmp_path / "missing-target")
    elif mutation.endswith("_mode"):
        {"base_mode": base, "namespace_mode": namespace, "leaf_mode": root}[mutation].chmod(0o755)
    with pytest.raises(budget.BudgetError):
        budget.BudgetStore(root, "b" * 32, clock=lambda: now).read_optional()


@pytest.mark.parametrize("mutation", ["replace", "mode"])
def test_optional_budget_missing_lookup_rechecks_retained_ancestor_before_none(
    tmp_path, monkeypatch, mutation
):
    from app.research_web import live_acceptance_budget as budget

    base = tmp_path / "private"
    base.mkdir(mode=0o700)
    root = base / "live-acceptance" / ("b" * 32)
    original = budget._open_posix_directory
    changed = False

    def open_directory(parent, name):
        nonlocal changed
        if name == "live-acceptance" and not changed:
            changed = True
            if mutation == "replace":
                base.rename(base.with_name("private-saved"))
                base.mkdir(mode=0o700)
            else:
                base.chmod(0o755)
        return original(parent, name)

    monkeypatch.setattr(budget, "_open_posix_directory", open_directory)
    with pytest.raises(budget.BudgetError):
        budget.BudgetStore(root, "b" * 32).read_optional()
    assert changed


def test_optional_budget_root_fstat_failure_closes_opened_root_fd(tmp_path, monkeypatch):
    from app.research_web import live_acceptance_budget as budget

    original_open, original_fstat, original_close = budget.os.open, budget.os.fstat, budget.os.close
    opened = []
    closed = []

    def open_fd(path, *args, **kwargs):
        descriptor = original_open(path, *args, **kwargs)
        if path == "/":
            opened.append(descriptor)
        return descriptor

    def fstat_fd(descriptor):
        if descriptor in opened:
            raise OSError("synthetic discovery root fstat failure")
        return original_fstat(descriptor)

    def close_fd(descriptor):
        if descriptor in opened:
            closed.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(budget.os, "open", open_fd)
    monkeypatch.setattr(budget.os, "fstat", fstat_fd)
    monkeypatch.setattr(budget.os, "close", close_fd)
    try:
        with pytest.raises(budget.BudgetError, match="acceptance_budget_unavailable"):
            budget.BudgetStore(
                tmp_path / "private/live-acceptance" / ("b" * 32), "b" * 32
            ).read_optional()
        assert len(opened) == 1
        assert closed == opened, "optional discovery leaked its newly opened root FD"
    finally:
        # The pre-fix RED still cleans up its own actual test descriptor without
        # counting this direct test cleanup as a helper close.
        for descriptor in opened:
            if descriptor not in closed:
                original_close(descriptor)


def test_native_budget_startup_ignores_private_authorizations_and_preserves_raw_legacy(
    tmp_path, monkeypatch
):
    def forbidden(identity):
        pytest.fail("Native must not discover Docker private authorizations")

    monkeypatch.setattr(launch_runtime, "read_optional_acceptance_budget", forbidden)
    monkeypatch.delenv("RESEARCH_ACCEPTANCE_CONTROL", raising=False)
    assert launch_runtime.live_acceptance_control(tmp_path, 3081) is None
    legacy = {"dataHome": str(tmp_path.resolve()), "modelCalls": 2, "tool": "datahub_get_fund_data"}
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps(legacy))
    assert launch_runtime.live_acceptance_control(tmp_path, 13081) == {
        "modelCalls": 2,
        "tool": "datahub_get_fund_data",
    }


def test_supervisor_owned_binding_discovers_persistent_budget_without_raw_acceptance_env(
    tmp_path, monkeypatch
):
    from datetime import UTC, datetime

    from app.research_web import live_acceptance_budget as budget
    from app.research_web.process_spec import build_process_specs
    from docker import supervisor

    source = make_source(tmp_path)
    data = tmp_path / "product-data"
    state = tmp_path / "state"
    identity = "b" * 32
    base = tmp_path / "private"
    namespace = base / "live-acceptance"
    root = namespace / identity
    base.mkdir(mode=0o700)
    namespace.mkdir(mode=0o700)
    now = datetime(2026, 10, 8, 11, tzinfo=UTC)
    original = budget.BudgetStore
    monkeypatch.setattr(
        budget, "BudgetStore", lambda path, bound_id: original(root, bound_id, clock=lambda: now)
    )
    monkeypatch.delenv("RESEARCH_ACCEPTANCE_CONTROL", raising=False)
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )
    monkeypatch.setattr(
        launch_runtime,
        "verify_staged_runtime",
        lambda *args, **kwargs: {"closure_sha256": "a" * 64, "closure_files": 1},
    )
    monkeypatch.setattr(
        supervisor, "_prepare_model_leaf", lambda path, bound_id: path / "models" / bound_id
    )
    config = supervisor.SupervisorConfig(
        data,
        state,
        Path(launch_runtime.__file__).parents[2],
        source,
        sys.executable,
        "/node",
        credential_root=Path("/run/rwb-secrets/private"),
        installation_id=identity,
    )
    specs = build_process_specs(
        python=config.python,
        node=config.node,
        project_root=config.project_root,
        data_root=config.data_root,
        runtime_source=config.runtime_source,
        state_root=config.state_root,
        web_host="0.0.0.0",
        web_port=8088,
        runtime_port=3081,
    )
    arguments = specs.runtime.command + supervisor._model_launch_arguments(config)

    def option(flag):
        return arguments[arguments.index(flag) + 1]

    binding = {
        "model_backend": option("--model-backend"),
        "model_credential_root": Path(option("--model-credential-root")),
        "model_installation_id": option("--model-installation-id"),
        "state_root": Path(option("--state")),
    }
    launch_runtime.prepare(
        Path(option("--source")),
        Path(option("--data")),
        option("--node"),
        int(option("--port")),
        **binding,
    )
    ordinary = (state / "overlay.yml").read_bytes()
    assert b"acceptance:" not in ordinary
    assert not root.exists()
    launch_runtime.prepare(
        Path(option("--source")),
        Path(option("--data")),
        option("--node"),
        int(option("--port")),
        **binding,
    )
    assert (state / "overlay.yml").read_bytes() == ordinary
    control = budget.authorization(3, 512, "2026-10-08T11:30:00Z")
    original.initialize(root, identity, control, clock=lambda: now)
    original(root, identity, clock=lambda: now).reserve(512)
    before = {item.name: item.read_bytes() for item in root.iterdir()}
    for _ in range(2):
        launch_runtime.prepare(
            Path(option("--source")),
            Path(option("--data")),
            option("--node"),
            int(option("--port")),
            **binding,
        )
        overlay = (state / "overlay.yml").read_text()
        assert "profile: docker-text" in overlay
        assert "maxTokens: 512" in overlay
        assert "- id: settings\n  disabled: true" in overlay
        assert {item.name: item.read_bytes() for item in root.iterdir()} == before
    assert original(root, identity, clock=lambda: now).reserve(512)["ticket"] == 2
    raw = {
        "dataHome": str(data.resolve()),
        "profile": "docker-text",
        "installationId": identity,
        "modelCalls": 3,
        "maxOutputTokens": 512,
    }
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps(raw))
    launch_runtime.prepare(
        Path(option("--source")),
        Path(option("--data")),
        option("--node"),
        int(option("--port")),
        **binding,
    )
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps({**raw, "maxOutputTokens": 1024}))
    with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
        launch_runtime.prepare(
            Path(option("--source")),
            Path(option("--data")),
            option("--node"),
            int(option("--port")),
            **binding,
        )
    assert original(root, identity, clock=lambda: now).reserve(512)["ticket"] == 3


def test_acceptance_budget_real_cross_process_serialization(tmp_path):
    _, root, _ = budget_fixture(tmp_path)
    code = (
        "import sys,json;from datetime import UTC,datetime;"
        f"sys.path.insert(0,{str(Path(launch_runtime.__file__).parents[2])!r});"
        "from app.research_web.live_acceptance_budget import BudgetStore,BudgetError;"
        f"store=BudgetStore({str(root)!r},'b'*32,clock=lambda:datetime(2026,10,8,11,tzinfo=UTC));"
        "\ntry: print(json.dumps(store.reserve(512)))"
        "\nexcept BudgetError as e: print(json.dumps({'error':str(e)}))"
    )
    children = [
        subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]
    outcomes = []
    for child in children:
        stdout, _ = child.communicate(timeout=15)
        assert child.returncode == 0
        outcomes.append(json.loads(stdout))
    assert sorted(value["ticket"] for value in outcomes if "ticket" in value) == [1, 2, 3]
    assert sum(value.get("error") == "acceptance_budget_exhausted" for value in outcomes) == 5


@pytest.mark.parametrize("stage", ["before", "after"])
def test_acceptance_budget_publication_failure_never_rolls_back(tmp_path, monkeypatch, stage):
    budget, root, now = budget_fixture(tmp_path)
    before = (root / "ledger.json").read_bytes()
    original_replace = budget.os.replace
    original_fsync = budget.os.fsync
    if stage == "before":
        monkeypatch.setattr(
            budget.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("private fixture text"))
        )
    else:

        def replace(*args, **kwargs):
            original_replace(*args, **kwargs)
            raise OSError("private fixture text")

        monkeypatch.setattr(budget.os, "replace", replace)
    code = (
        "acceptance_budget_unavailable"
        if stage == "before"
        else "acceptance_budget_commit_uncertain"
    )
    with pytest.raises(budget.BudgetError, match=code):
        budget.BudgetStore(root, "b" * 32, clock=lambda: now).reserve(512)
    monkeypatch.setattr(budget.os, "replace", original_replace)
    monkeypatch.setattr(budget.os, "fsync", original_fsync)
    assert ((root / "ledger.json").read_bytes() == before) == (stage == "before")
    assert budget.BudgetStore(root, "b" * 32, clock=lambda: now).reserve(512)["ticket"] == (
        1 if stage == "before" else 2
    )


def test_acceptance_budget_missing_expired_changed_and_unsafe_fail_closed(tmp_path):
    from datetime import timedelta

    budget, root, now = budget_fixture(tmp_path)
    missing = root.parent / ("c" * 32)
    with pytest.raises(budget.BudgetError):
        budget.BudgetStore(missing, "c" * 32, clock=lambda: now).describe()
    assert not missing.exists()
    with pytest.raises(budget.BudgetError, match="acceptance_budget_expired"):
        budget.BudgetStore(root, "b" * 32, clock=lambda: now + timedelta(minutes=30)).reserve(512)
    (root / "control.json").chmod(0o644)
    with pytest.raises(budget.BudgetError):
        budget.BudgetStore(root, "b" * 32, clock=lambda: now).reserve(512)
    with pytest.raises(budget.BudgetError):
        budget.BudgetStore(root, "b" * 32, clock=lambda: now).describe()
    assert json.loads((root / "ledger.json").read_bytes())["tickets"] == 0


@pytest.mark.parametrize(
    "mutation", ["symlink", "hardlink", "lock_missing", "parent_mode", "tamper"]
)
def test_acceptance_budget_rejects_alias_missing_permanent_lock_and_control_change(
    tmp_path, mutation
):
    import os

    budget, root, now = budget_fixture(tmp_path)
    control = root / "control.json"
    if mutation == "symlink":
        control.rename(root / "backup.json")
        control.symlink_to(root / "backup.json")
    elif mutation == "hardlink":
        os.link(control, root / "extra.json")
    elif mutation == "lock_missing":
        (root / "budget.lock").unlink()
    elif mutation == "parent_mode":
        root.parent.chmod(0o755)
    else:
        value = json.loads(control.read_bytes())
        value["authorization"] = budget.authorization(2, 512, "2026-10-08T11:30:00Z")
        control.write_bytes(budget._encode(value))
    with pytest.raises(budget.BudgetError):
        budget.BudgetStore(root, "b" * 32, clock=lambda: now).reserve(512)
    assert json.loads((root / "ledger.json").read_bytes())["tickets"] == 0
    if mutation == "lock_missing":
        assert not (root / "budget.lock").exists()


def test_acceptance_budget_cli_import_stdout_is_private_even_before_request_decode():
    helper = Path(launch_runtime.__file__).with_name("live_acceptance_budget.py")
    script = (
        "import builtins,runpy,sys;original=builtins.__import__;"
        "\ndef canary(name,*args,**kwargs):"
        "\n if name=='app.research_web.credential_backend': print('private-import-canary')"
        "\n return original(name,*args,**kwargs)"
        "\nbuiltins.__import__=canary"
        f"\nsys.argv=[{str(helper)!r},'--installation-id','b'*32]"
        f"\nrunpy.run_path({str(helper)!r},run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        input="{}",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"},
        cwd="/",
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout) == {"ok": False, "error": "acceptance_budget_invalid"}
    assert "private-import-canary" not in completed.stdout
    assert "private-import-canary" in completed.stderr


@pytest.mark.parametrize("ambient", [False, True])
def test_acceptance_budget_private_cli_readonly_import_and_missing_read(tmp_path, ambient):
    helper = Path(launch_runtime.__file__).with_name("live_acceptance_budget.py")
    canary = tmp_path / "untrusted.env"
    canary.write_text("LOG_DIR=/untrusted-import-canary\n")
    script = """
import builtins, errno, os, runpy, sys, sysconfig
from pathlib import Path
sysconfig.get_config_vars()  # Host stdlib configuration precedes the Linux selector simulation.
product = Path(sys.argv[1]).resolve().parents[2]
original_mkdir, original_import = os.mkdir, builtins.__import__
def readonly_mkdir(path, *args, **kwargs):
    if Path(path) != product:
        raise OSError(errno.EROFS, 'readonly-import-canary')
    return original_mkdir(path, *args, **kwargs)
os.mkdir = readonly_mkdir
def guarded_import(name, *args, **kwargs):
    imported = original_import(name, *args, **kwargs)
    if name == 'app.research_web.credential_backend':
        from core.settings.config import settings, RUNTIME_CONTEXT
        assert RUNTIME_CONTEXT.mode == 'web-prod' and RUNTIME_CONTEXT.env_path is None
        assert all(getattr(settings, key) == product for key in
            ('LOG_DIR', 'OBJECT_STORAGE_PATH', 'PDF_MARKDOWN_DIR', 'PDF_RAW_TEXT_DIR'))
        print('private-import-canary')
    return imported
builtins.__import__ = guarded_import
sys.platform = 'linux'
sys.argv = [sys.argv[1], '--installation-id', 'b' * 32]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    env = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}
    if ambient:
        env.update(
            RESEARCH_RUN_MODE="web-dev",
            RESEARCH_CONFIG_FILE=str(canary),
            PYTHONPATH=str(tmp_path),
            **{
                key: "/untrusted-import-canary"
                for key in (
                    "LOG_DIR",
                    "OBJECT_STORAGE_PATH",
                    "PDF_MARKDOWN_DIR",
                    "PDF_RAW_TEXT_DIR",
                )
            },
        )
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(helper)],
        input='{"op":"describe"}',
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env=env,
        cwd="/",
    )
    assert completed.returncode == 1
    assert completed.stdout, completed.stderr
    assert json.loads(completed.stdout) == {"ok": False, "error": "acceptance_budget_unavailable"}
    assert "private-import-canary" in completed.stderr
    assert "readonly-import-canary" not in completed.stderr
    assert list(tmp_path.iterdir()) == [canary]


def test_acceptance_budget_expiry_during_commit_keeps_ticket_and_denies_dispatch(tmp_path):
    from datetime import timedelta

    budget, root, now = budget_fixture(tmp_path)
    times = iter([now, now + timedelta(minutes=30)])
    with pytest.raises(budget.BudgetError, match="acceptance_budget_commit_uncertain"):
        budget.BudgetStore(root, "b" * 32, clock=lambda: next(times)).reserve(512)
    assert json.loads((root / "ledger.json").read_bytes())["tickets"] == 1


def test_acceptance_budget_read_atime_changes_do_not_reject_own_reservation(tmp_path, monkeypatch):
    import os

    budget, root, now = budget_fixture(tmp_path)
    original = budget.PrivateFileCredentialBackend._read
    reads = 0

    def read(directory, name):
        nonlocal reads
        value = original(directory, name)
        if value is None:
            return value
        reads += 1
        fields = list(value[1])
        fields[7] += reads
        return value[0], os.stat_result(fields)

    monkeypatch.setattr(budget.PrivateFileCredentialBackend, "_read", staticmethod(read))
    assert budget.BudgetStore(root, "b" * 32, clock=lambda: now).reserve(512)["ticket"] == 1


def test_acceptance_startup_requires_existing_control_and_cannot_raise_authorized_caps(
    tmp_path, monkeypatch
):
    import importlib

    _, root, now = budget_fixture(tmp_path)
    value = {
        "dataHome": str(tmp_path.resolve()),
        "profile": "docker-text",
        "installationId": "b" * 32,
        "modelCalls": 3,
        "maxOutputTokens": 512,
    }
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps(value))
    binding = {
        "staged": True,
        "model_backend": "docker-private-file",
        "model_installation_id": "b" * 32,
        "model_credential_root": Path("/run/rwb-secrets/private/models") / ("b" * 32),
    }
    module = importlib.import_module("app.research_web.live_acceptance_budget")
    original = module.BudgetStore
    monkeypatch.setattr(
        module, "BudgetStore", lambda path, identity: original(root, identity, clock=lambda: now)
    )
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    result = launch_runtime.live_acceptance_control(tmp_path, 3081, **binding)
    assert result["budgetBridge"]["bridge"].endswith("live_acceptance_budget.py")
    assert {path.name: path.read_bytes() for path in root.iterdir()} == before
    monkeypatch.setenv(
        "RESEARCH_ACCEPTANCE_CONTROL", json.dumps({**value, "maxOutputTokens": 1024})
    )
    with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
        launch_runtime.live_acceptance_control(tmp_path, 3081, **binding)
    (root / "control.json").unlink()
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps(value))
    with pytest.raises(RuntimeError, match="acceptance_budget_unverified"):
        launch_runtime.live_acceptance_control(tmp_path, 3081, **binding)
    assert not (root / "control.json").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"totalMicroUsd": True},
        {"inputMicroUsdPerMillion": 1},
        {"validUntil": "2026-10-08T13:00:00Z"},
        {"validUntil": "2026-10-09T01:00:00Z"},
    ],
)
def test_acceptance_budget_init_rejects_unapproved_numeric_policy_and_ttl(tmp_path, change):
    budget, root, now = budget_fixture(tmp_path)
    candidate = root.parent / ("c" * 32)
    control = {**budget.authorization(3, 512, "2026-10-08T11:30:00Z"), **change}
    with pytest.raises(budget.BudgetError, match="acceptance_budget_invalid"):
        budget.BudgetStore.initialize(candidate, "c" * 32, control, clock=lambda: now)
    assert not candidate.exists()


def test_runtime_constants_share_the_machine_contract():
    from app.research_web import PINNED_DSH_COMMIT
    from app.research_web.runtime_contract import load_runtime_contract

    contract = load_runtime_contract()
    assert PINNED_DSH_COMMIT == contract.dsh_commit
    assert launch_runtime.PINNED_COMMIT == contract.dsh_commit
    assert launch_runtime.RUNTIME_CONTRACT == contract


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "packages/boot/app-boot/lib").mkdir(parents=True)
    (source / "packages/boot/app-boot/lib/index.js").write_text("// built")
    (source / "apps/cli/lib").mkdir(parents=True)
    (source / "apps/cli/package.json").write_text("{}")
    (source / "apps/cli/lib/bin.js").write_text("// cli")
    return source


def test_runtime_module_fallback_is_healed_inside_private_source(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    target = source / "packages/example"
    target.mkdir(parents=True)

    def run(*args, **kwargs):
        assert "loadProfile('dsh', 'web', anchor, home)" in args[0][3]
        assert "healProfilesModuleFallback({ installAnchor: anchor, profile })" in args[0][3]
        profile = home / "profiles/web"
        profile.mkdir(parents=True)
        (profile / "package.json").write_text(
            json.dumps(
                {
                    "name": "dsh-profile-web",
                    "private": True,
                    "dependencies": {},
                    "dsh": {
                        "profile": {
                            "bundles": [
                                "@deepseek-ai/dsh-base",
                                "@deepseek-ai/dsh-web-app",
                            ],
                            "patchReload": "live",
                        }
                    },
                }
            )
        )
        modules = home / "profiles/node_modules/@deepseek-ai"
        modules.mkdir(parents=True)
        (modules / "dsh-example").symlink_to(target)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    assert launch_runtime.prepare_runtime_module_fallback(source, home, "/node") == 1
    assert (home / "profiles/web/package.json").is_file()


def test_runtime_module_fallback_rejects_external_target(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    external = tmp_path / "external"
    external.mkdir()

    def run(*args, **kwargs):
        modules = home / "profiles/node_modules"
        modules.mkdir(parents=True)
        (modules / "external").symlink_to(external)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="越出项目私有源码目录"):
        launch_runtime.prepare_runtime_module_fallback(source, home, "/node")


def test_runtime_module_fallback_accepts_windows_junctions_inside_private_source(
    tmp_path, monkeypatch
):
    source = make_source(tmp_path)
    home = tmp_path / "home"
    target = source / "packages/example"
    target.mkdir(parents=True)
    link = home / "profiles/node_modules/dsh-example"
    original_is_symlink = Path.is_symlink

    def run(*_args, **_kwargs):
        link.parent.mkdir(parents=True)
        link.symlink_to(target, target_is_directory=True)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: False if path == link else original_is_symlink(path),
    )
    monkeypatch.setattr(Path, "is_junction", lambda path: path == link)
    monkeypatch.setattr(launch_runtime.os, "name", "nt")

    assert launch_runtime.prepare_runtime_module_fallback(source, home, "/node") == 1


def test_runtime_keeps_dsh_home_private_but_uses_host_home_for_tabbit(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    host_home = tmp_path / "host-user"
    local_app_data = host_home / "AppData/Local"
    monkeypatch.setenv("HOME", str(host_home))
    monkeypatch.setenv("USERPROFILE", str(host_home))
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )

    _, env, _ = launch_runtime.prepare(source, data, "/node", 3081)

    assert env["DSH_HOME"] == str(data.resolve() / "runtime/home")
    assert env["HOME"] == str(host_home)
    assert env["USERPROFILE"] == str(host_home)
    assert env["LOCALAPPDATA"] == str(local_app_data)


def test_runtime_binds_model_system_store_and_separate_host_records(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *a, **kw: launch_runtime.PINNED_COMMIT
    )
    monkeypatch.setenv("RESEARCH_DSH_API_KEY", "synthetic-ambient")
    _, env, _ = launch_runtime.prepare(source, data, "/node", 13081)
    overlay = (data / "runtime/overlay.yml").read_text()
    assert "- id: credentials" in overlay
    assert "model-credentials.mjs" in overlay
    assert "model_credentials.py" in overlay
    assert ".browser-credentials.yaml" in overlay
    assert "default: research-web" in overlay
    assert "synthetic-ambient" not in overlay
    assert "RESEARCH_DSH_API_KEY" not in env


def test_staged_runtime_binds_only_explicit_model_selectors(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *a, **kw: launch_runtime.PINNED_COMMIT
    )
    monkeypatch.setattr(
        launch_runtime,
        "verify_staged_runtime",
        lambda *a, **kw: {"closure_sha256": "a" * 64, "closure_files": 1},
    )
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    identity = "a" * 32
    launch_runtime.prepare(
        source,
        data,
        "/node",
        3081,
        model_backend="docker-private-file",
        model_credential_root=Path("/run/rwb-secrets/private/models") / identity,
        model_installation_id=identity,
    )
    overlay = (data / "runtime/overlay.yml").read_text()
    assert 'source: "docker-private-file"' in overlay
    assert f'installationId: "{identity}"' in overlay
    assert f'credentialRoot: "/run/rwb-secrets/private/models/{identity}"' in overlay


def test_staged_runtime_missing_model_binding_keeps_core_and_denies_native_fallback(
    tmp_path, monkeypatch
):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *a, **kw: launch_runtime.PINNED_COMMIT
    )
    monkeypatch.setattr(
        launch_runtime,
        "verify_staged_runtime",
        lambda *a, **kw: {"closure_sha256": "a" * 64, "closure_files": 1},
    )
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    launch_runtime.prepare(source, data, "/node", 3081)
    overlay = (data / "runtime/overlay.yml").read_text()
    assert 'source: "docker-private-file"' in overlay
    assert "credentialRoot:" not in overlay


def test_native_ignores_ambient_docker_model_selector(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *a, **kw: launch_runtime.PINNED_COMMIT
    )
    launch_runtime.prepare(source, data, "/node", 3081)
    before = (data / "runtime/overlay.yml").read_bytes()
    monkeypatch.setenv("RWB_INSTALLATION_ID", "a" * 32)
    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", "/run/rwb-secrets/private")
    monkeypatch.setenv("RWB_MODEL_BACKEND", "docker-private-file")
    launch_runtime.prepare(source, data, "/node", 3081)
    assert (data / "runtime/overlay.yml").read_bytes() == before


@pytest.mark.parametrize(
    "backend,identity,root",
    [
        ("system-keychain", "a" * 32, "/run/rwb-secrets/private/models/" + "a" * 32),
        ("unknown", "a" * 32, "/run/rwb-secrets/private/models/" + "a" * 32),
        ("docker-private-file", "A" * 32, "/run/rwb-secrets/private/models/" + "A" * 32),
        ("docker-private-file", "a" * 32, "/tmp/models"),
    ],
)
def test_invalid_staged_model_binding_is_explicitly_unavailable(
    tmp_path, monkeypatch, backend, identity, root
):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *a, **kw: launch_runtime.PINNED_COMMIT
    )
    monkeypatch.setattr(
        launch_runtime,
        "verify_staged_runtime",
        lambda *a, **kw: {"closure_sha256": "a" * 64, "closure_files": 1},
    )
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    launch_runtime.prepare(
        source,
        data,
        "/node",
        3081,
        model_backend=backend,
        model_installation_id=identity,
        model_credential_root=Path(root),
    )
    overlay = (data / "runtime/overlay.yml").read_text()
    assert 'source: "docker-private-file"' in overlay
    assert "credentialRoot:" not in overlay and "installationId:" not in overlay


def test_native_explicit_docker_selection_is_denied_before_overlay(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    with pytest.raises(RuntimeError, match="model_credential_backend_unavailable"):
        launch_runtime.prepare(source, data, "/node", 3081, model_backend="docker-private-file")
    assert not (data / "runtime/overlay.yml").exists()


@pytest.mark.parametrize("marker", ["runtime", "web", "invalid", "runtime\nweb", ""])
def test_clean_runtime_exec_environment_retains_only_exact_runtime_role(
    tmp_path, monkeypatch, marker
):
    source = make_source(tmp_path)
    monkeypatch.setenv("RWB_SUPERVISOR_ROLE", marker)
    monkeypatch.setenv("UNRELATED_HOST_VALUE", "must-not-cross-exec-boundary")
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )
    _, env, _ = launch_runtime.prepare(source, tmp_path / "data", "/node", 3081)
    assert env.get("RWB_SUPERVISOR_ROLE") == ("runtime" if marker == "runtime" else None)
    assert "UNRELATED_HOST_VALUE" not in env
    assert "must-not-cross-exec-boundary" not in env.values()


def test_runtime_role_survives_real_exec_with_clean_environment(tmp_path):
    source = make_source(tmp_path)
    # Execute the actual Node preload and final exec boundary with public fixtures.
    node = shutil.which("node")
    assert node is not None
    (source / "package.json").write_text(json.dumps({"version": "fixture"}))
    (source / "apps/cli/lib/bin.js").write_text(
        "console.log(JSON.stringify({role:process.env.RWB_SUPERVISOR_ROLE,"
        "host:process.env.UNRELATED_HOST_VALUE ?? null}));\n"
    )
    runner = """
import os, sys
from app.research_web import launch_runtime as launcher
launcher.setup_logging = lambda: None
launcher.subprocess.check_output = lambda *a, **k: launcher.PINNED_COMMIT
launcher.validate_tabbit_node = lambda node: '24.0.0'
launcher.prepare_runtime_module_fallback = lambda *a: 0
launcher.stage_tabbit_package = lambda *a: {'version':'fixture','source_commit':'fixture'}
launcher.stage_tabbit_adapter = lambda *a: None
os.environ['RWB_SUPERVISOR_ROLE'] = 'runtime'
os.environ['UNRELATED_HOST_VALUE'] = 'must-not-cross-exec-boundary'
sys.argv = ['launcher', '--source', sys.argv[1], '--data', sys.argv[2], '--node', sys.argv[3]]
launcher.main()
"""
    completed = subprocess.run(
        [sys.executable, "-c", runner, str(source), str(tmp_path / "data"), node],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert json.loads(completed.stdout.splitlines()[-1]) == {"role": "runtime", "host": None}


@pytest.mark.parametrize("separate_state", [False, True])
def test_prepare_separates_persistent_data_from_runtime_state(
    tmp_path, monkeypatch, separate_state
):
    from app.research_web.client import _default_auth_path

    source = make_source(tmp_path)
    data = tmp_path / "data"
    state = tmp_path / "state" if separate_state else data / "runtime"
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )
    monkeypatch.setenv("RESEARCH_DATA_HOME", str(data))
    monkeypatch.setenv("RESEARCH_RUNTIME_AUTH", str(state / "auth.json"))
    options = {"state_root": state} if separate_state else {}
    command, env, work = launch_runtime.prepare(source, data, "/node", 3081, **options)
    assert env["DSH_HOME"] == str(data.resolve() / "runtime/home")
    assert work == data.resolve() / "runtime/work"
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--patch") + 1] == str(state.resolve() / "overlay.yml")
    assert env["RESEARCH_RUNTIME_AUTH"] == str(state.resolve() / "auth.json")
    assert env["RWB_RUNTIME_STATE"] == str(state.resolve())
    assert (state / "build-lock.json").is_file()
    assert _default_auth_path() == state / "auth.json"
    if separate_state:
        assert not (data / "runtime/overlay.yml").exists()
        assert not (data / "runtime/build-lock.json").exists()
        assert not (state / "home").exists()


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="Legacy POSIX directory permissions")
@pytest.mark.parametrize("layout", ["legacy_native", "public_parent", "custom"])
def test_direct_prepare_legacy_native_state_requires_private_data(tmp_path, monkeypatch, layout):
    source = make_source(tmp_path)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    state = data / "runtime" if layout != "custom" else tmp_path / "state"
    state.mkdir(mode=0o755)
    state.chmod(0o755)
    if layout == "public_parent":
        data.chmod(0o755)
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *_args, **_kwargs: launch_runtime.PINNED_COMMIT,
    )
    if layout == "legacy_native":
        command, env, work = launch_runtime.prepare(source, data, "/node", 3081)
        assert command[command.index("--patch") + 1] == str(state / "overlay.yml")
        assert env["DSH_HOME"] == str(state / "home")
        assert work == state / "work"
        assert state.stat().st_mode & 0o777 == 0o755
    else:
        with pytest.raises(ValueError, match="runtime_state_unsafe"):
            launch_runtime.prepare(source, data, "/node", 3081, state_root=state)
        assert not (state / "overlay.yml").exists()
        assert not (state / "build-lock.json").exists()


@pytest.mark.parametrize("mode", ["default", "explicit_state", "data_alias"])
def test_launch_cli_accepts_state_and_preserves_historical_default(tmp_path, monkeypatch, mode):
    data = tmp_path / "data"
    state = tmp_path / "state" if mode == "explicit_state" else data / "runtime"
    if mode == "data_alias":
        data.mkdir()
        alias = tmp_path / "data-alias"
        alias.symlink_to(data, target_is_directory=True)
        data = alias
    argv = ["launch_runtime", "--source", str(tmp_path / "source"), "--data", str(data)]
    if mode == "explicit_state":
        argv += ["--state", str(state)]
    monkeypatch.setattr(launch_runtime.sys, "argv", argv)
    monkeypatch.setattr(launch_runtime, "setup_logging", lambda: None)
    monkeypatch.setattr(launch_runtime, "validate_tabbit_node", lambda _node: "24.0.0")
    observed = {}

    def prepare(*args, **kwargs):
        observed.update(kwargs)
        raise RuntimeError("stop before any service launch")

    monkeypatch.setattr(launch_runtime, "prepare", prepare)
    with pytest.raises(SystemExit) as failure:
        launch_runtime.main()
    assert failure.value.code == 1
    assert observed["state_root"] == state


@pytest.mark.parametrize(
    "unsafe", ["writable", "symlink", "ancestor_symlink", "ancestor_writable", "file"]
)
@pytest.mark.parametrize("entrypoint", ["prepare", "cli"])
def test_launch_rejects_unsafe_state_before_file_access(tmp_path, monkeypatch, unsafe, entrypoint):
    if launch_runtime.os.name == "nt" and unsafe != "file":
        pytest.skip("POSIX mode and symlink fixtures; Windows semantics tested separately")
    source = make_source(tmp_path)
    state = tmp_path / "state"
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    if unsafe == "writable":
        state.mkdir(mode=0o777)
        state.chmod(0o777)
    elif unsafe == "symlink":
        state.symlink_to(target, target_is_directory=True)
    elif unsafe == "ancestor_symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(target, target_is_directory=True)
        state = alias / "state"
        (target / "state").mkdir(mode=0o700)
    elif unsafe == "ancestor_writable":
        target.chmod(0o777)
        state = target / "state"
        state.mkdir(mode=0o700)
    else:
        state.write_text("not a directory")
    original_open = Path.open

    def checked_open(path, *args, **kwargs):
        if path.parent == state:
            pytest.fail("state file accessed before rejecting unsafe directory")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kwargs: launch_runtime.PINNED_COMMIT,
    )
    if entrypoint == "prepare":
        with pytest.raises((RuntimeError, ValueError), match="runtime_state_unsafe"):
            launch_runtime.prepare(source, tmp_path / "data", "/node", 3081, state_root=state)
    else:
        monkeypatch.setattr(launch_runtime, "setup_logging", lambda: None)
        monkeypatch.setattr(launch_runtime, "validate_tabbit_node", lambda _node: "24.0.0")
        monkeypatch.setattr(
            launch_runtime.sys,
            "argv",
            [
                "launch_runtime",
                "--source",
                str(source),
                "--data",
                str(tmp_path / "data"),
                "--state",
                str(state),
            ],
        )
        with pytest.raises(SystemExit) as error:
            launch_runtime.main()
        assert error.value.code == 1


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX ownership and identity fixture")
def test_runtime_state_boundary_checks_owner_mode_and_identity(tmp_path, monkeypatch):
    import os

    from app.research_web import runtime_state

    state = tmp_path / "new" / "state"
    with runtime_state.runtime_state_directory(state, create=True):
        assert state.stat().st_mode & 0o777 == 0o700
        assert state.parent.stat().st_mode & 0o777 == 0o700
    original_lstat = Path.lstat

    def wrong_owner(path):
        identity = original_lstat(path)
        if path == state:
            fields = list(identity)
            fields[4] = os.getuid() + 1
            return os.stat_result(fields)
        return identity

    monkeypatch.setattr(Path, "lstat", wrong_owner)
    with (
        pytest.raises(runtime_state.RuntimeStateError),
        runtime_state.runtime_state_directory(state),
    ):
        pytest.fail("wrong owner accepted")
    monkeypatch.setattr(Path, "lstat", original_lstat)
    with (
        pytest.raises(runtime_state.RuntimeStateError),
        runtime_state.runtime_state_directory(state),
    ):
        state.rename(tmp_path / "old-state")
        state.mkdir(mode=0o700)


def test_runtime_state_windows_rejects_reparse_without_using_posix_mode_as_acl():
    import stat

    from app.research_web import runtime_state

    windows_identity = SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_file_attributes=0)
    runtime_state._validate_directory(windows_identity, leaf=True, platform_name="nt")
    windows_identity.st_file_attributes = 0x400
    with pytest.raises(runtime_state.RuntimeStateError):
        runtime_state._validate_directory(windows_identity, leaf=True, platform_name="nt")


def test_runtime_state_disappearance_during_open_is_rejected_before_body(tmp_path, monkeypatch):
    from app.research_web import runtime_state

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    original_lstat = Path.lstat
    calls = 0

    def disappear(path):
        nonlocal calls
        if path == state:
            calls += 1
            if calls == 2:
                raise FileNotFoundError("simulated concurrent replacement")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", disappear)
    with (
        pytest.raises(runtime_state.RuntimeStateError, match="runtime_state_unsafe"),
        runtime_state.runtime_state_directory(state),
    ):
        pytest.fail("changed directory accepted")


def test_runtime_state_boundary_preserves_caller_errors(tmp_path):
    from app.research_web.runtime_state import runtime_state_directory

    failure = ValueError("caller validation failed")
    with (
        pytest.raises(ValueError) as raised,
        runtime_state_directory(tmp_path / "state", create=True),
    ):
        raise failure
    assert raised.value is failure


@pytest.mark.parametrize("leaf", [False, True])
@pytest.mark.parametrize("reason", ["invalid_type", "reparse_point", "unsafe_owner", "unsafe_mode"])
def test_runtime_state_rejection_reason_is_private(leaf, reason, monkeypatch, caplog):
    import stat

    from app.research_web import runtime_state

    monkeypatch.setattr(runtime_state.os, "getuid", lambda: 7654321)
    value = SimpleNamespace(
        st_mode=stat.S_IFDIR | 0o700,
        st_uid=7654321,
        st_gid=8765432,
        st_file_attributes=0,
    )
    if reason == "invalid_type":
        value.st_mode = stat.S_IFREG | 0o700
    elif reason == "reparse_point":
        value.st_file_attributes = 0x400
    elif reason == "unsafe_owner":
        value.st_uid = 9876543
    else:
        value.st_mode |= 0o022
    with pytest.raises(runtime_state.RuntimeStateError, match="^runtime_state_unsafe$"):
        runtime_state._validate_directory(value, leaf=leaf, platform_name="posix")
    assert f"reason={reason} phase=enter scope={'leaf' if leaf else 'ancestor'}" in caplog.text
    assert all(secret not in caplog.text for secret in ("7654321", "8765432", "9876543"))


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX descriptor fixture")
@pytest.mark.parametrize("phase,call", [("enter", 2), ("pre_yield", 3), ("post_yield", 4)])
@pytest.mark.parametrize(
    "field,index", [("dev", 2), ("ino", 1), ("mode", 0), ("uid", 4), ("gid", 5)]
)
def test_runtime_state_identity_rejection_evidence(
    tmp_path, monkeypatch, caplog, phase, call, field, index
):
    import os

    from app.research_web import runtime_state

    state = tmp_path / "sensitive-cookie-token-path"
    state.mkdir(mode=0o700)
    original = Path.lstat
    calls = 0

    def change(path):
        nonlocal calls
        current = original(path)
        if path == state:
            calls += 1
            if calls >= call:
                fields = list(current)
                # Root is allowed for ancestors, but leaf owner changes reject first.
                fields[index] += 0o100 if field == "mode" else 1
                return os.stat_result(fields)
        return current

    monkeypatch.setattr(Path, "lstat", change)
    with (
        pytest.raises(runtime_state.RuntimeStateError, match="^runtime_state_unsafe$"),
        runtime_state.runtime_state_directory(state),
    ):
        pass
    assert f"phase={phase} scope=leaf" in caplog.text
    if field == "uid" and phase != "enter":
        assert "reason=unsafe_owner" in caplog.text
    else:
        assert f"reason=identity_changed phase={phase} scope=leaf changed={field}" in caplog.text
    assert str(tmp_path) not in caplog.text
    assert "sensitive-cookie-token-path" not in caplog.text


@pytest.mark.parametrize("guard", [False, True])
def test_runtime_state_logging_failure_preserves_rejection(tmp_path, monkeypatch, guard):
    import stat

    from app.research_web import runtime_state

    def fail(*args, **kwargs):
        raise RuntimeError("sensitive-cookie-token")

    monkeypatch.setattr(runtime_state.log, "warning", fail)
    with pytest.raises(runtime_state.RuntimeStateError, match="^runtime_state_unsafe$"):
        if guard:
            unsafe = tmp_path / "sensitive-cookie-token"
            unsafe.write_text("sensitive-cookie-token")
            with runtime_state.runtime_state_directory(unsafe):
                pytest.fail("unsafe directory accepted after logger failure")
        else:
            runtime_state._validate_directory(
                SimpleNamespace(st_mode=stat.S_IFREG), leaf=True, platform_name="posix"
            )


def test_runtime_state_valid_guard_emits_no_rejection(tmp_path, caplog):
    from app.research_web import runtime_state

    with runtime_state.runtime_state_directory(tmp_path / "private-state", create=True):
        pass
    assert "runtime_state_directory_rejected" not in caplog.text


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX descriptor fixture")
@pytest.mark.parametrize("phase,call", [("open_fd", 1), ("pre_yield", 2), ("post_yield", 3)])
@pytest.mark.parametrize("leaf", [False, True])
def test_runtime_state_fd_identity_evidence(tmp_path, monkeypatch, caplog, phase, call, leaf):
    import os

    from app.research_web import runtime_state

    state = tmp_path / "private-state"
    state.mkdir(mode=0o700)
    target = state if leaf else tmp_path
    inode = target.stat().st_ino
    original = os.fstat
    calls = 0

    def changed_fd(descriptor):
        nonlocal calls
        current = original(descriptor)
        if current.st_ino == inode:
            calls += 1
            if calls >= call:
                fields = list(current)
                fields[4] += 1
                return os.stat_result(fields)
        return current

    monkeypatch.setattr(runtime_state.os, "fstat", changed_fd)
    with (
        pytest.raises(runtime_state.RuntimeStateError, match="^runtime_state_unsafe$"),
        runtime_state.runtime_state_directory(state),
    ):
        pass
    assert (
        f"reason=identity_changed phase={phase} scope={'leaf' if leaf else 'ancestor'} changed=uid"
        in caplog.text
    )
    assert str(tmp_path) not in caplog.text


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX ownership fixture")
def test_runtime_state_same_inode_allowed_owner_change_still_rejects(tmp_path, monkeypatch, caplog):
    import os

    from app.research_web import runtime_state

    state = tmp_path / "private-state"
    state.mkdir(mode=0o700)
    original = Path.lstat
    calls = 0

    def changed_owner(path):
        nonlocal calls
        current = original(path)
        if path == tmp_path:
            calls += 1
            if calls >= 3:
                fields = list(current)
                fields[4] = 0 if current.st_uid else os.getuid() + 1
                return os.stat_result(fields)
        return current

    monkeypatch.setattr(Path, "lstat", changed_owner)
    with (
        pytest.raises(runtime_state.RuntimeStateError, match="^runtime_state_unsafe$"),
        runtime_state.runtime_state_directory(state),
    ):
        pytest.fail("same-inode ownership change accepted")
    assert "reason=identity_changed phase=pre_yield scope=ancestor changed=uid" in caplog.text


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX ownership fixture")
@pytest.mark.parametrize(
    "leaf,parent,position",
    [(True, False, "leaf"), (False, True, "parent"), (False, False, "other_ancestor")],
)
@pytest.mark.parametrize(
    "before_pair,current_pair,transition",
    [
        ((0, 0), (7654321, 8765432), "root_pair_to_runtime_pair"),
        ((7654321, 8765432), (0, 0), "reverse"),
        ((0, 8765432), (7654321, 8765432), "other"),
        ((7654321, 8765432), (0, 8765432), "other"),
        ((0, 0), (7654321, 9876543), "other"),
        ((7654321, 9876543), (0, 0), "other"),
        ((0, 9876543), (7654321, 8765432), "other"),
        ((7654321, 8765432), (7654321, 9876543), "other"),
        ((0, 0), (0, 0), "other"),
    ],
)
def test_runtime_state_private_ownership_classification(
    monkeypatch, caplog, leaf, parent, position, before_pair, current_pair, transition
):
    from app.research_web import runtime_state

    monkeypatch.setattr(runtime_state.os, "getuid", lambda: 7654321)
    monkeypatch.setattr(runtime_state.os, "getgid", lambda: 8765432)

    def identity(pair):
        return SimpleNamespace(
            st_dev=6543210,
            st_ino=5432109,
            st_mode=0o40700,
            st_uid=pair[0],
            st_gid=pair[1],
        )

    runtime_state._log_identity_change(
        identity(before_pair),
        identity(current_pair),
        phase="post_yield",
        leaf=leaf,
        parent=parent,
    )
    assert f"ownership_transition={transition} position={position}" in caplog.text
    assert all(
        value not in caplog.text
        for value in (
            "7654321",
            "8765432",
            "9876543",
            "6543210",
            "5432109",
            "40700",
        )
    )


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX ownership fixture")
@pytest.mark.parametrize("position", ["leaf", "parent", "other_ancestor"])
@pytest.mark.parametrize("source", ["path", "fd"])
def test_runtime_state_ownership_classification_keeps_rejecting(
    tmp_path, monkeypatch, caplog, position, source
):
    import os

    from app.research_web import runtime_state

    parent = tmp_path / "sensitive-token-parent"
    parent.mkdir(mode=0o700)
    state = parent / "sensitive-cookie-leaf"
    state.mkdir(mode=0o700)
    target = {"leaf": state, "parent": parent, "other_ancestor": tmp_path}[position]
    target_inode = target.stat().st_ino
    original_lstat, original_fstat = Path.lstat, os.fstat
    runtime_pair = (os.getuid(), os.getgid())
    active = False

    def identity(current, changed):
        fields = list(current)
        fields[4:6] = runtime_pair if position == "leaf" else (0, 0)
        if active and changed:
            fields[4:6] = (
                (runtime_pair[0], runtime_pair[1] + 1) if position == "leaf" else runtime_pair
            )
        return os.stat_result(fields)

    def named(path):
        current = original_lstat(path)
        return identity(current, source == "path") if path == target else current

    def opened(descriptor):
        current = original_fstat(descriptor)
        return identity(current, source == "fd") if current.st_ino == target_inode else current

    monkeypatch.setattr(Path, "lstat", named)
    monkeypatch.setattr(runtime_state.os, "fstat", opened)
    with (
        pytest.raises(runtime_state.RuntimeStateError, match="^runtime_state_unsafe$"),
        runtime_state.runtime_state_directory(state),
    ):
        active = True
    transition = "other" if position == "leaf" else "root_pair_to_runtime_pair"
    assert f"ownership_transition={transition} position={position}" in caplog.text
    assert "phase=post_yield" in caplog.text
    assert str(tmp_path) not in caplog.text
    assert "sensitive-token-parent" not in caplog.text
    assert "sensitive-cookie-leaf" not in caplog.text


@pytest.mark.skipif(launch_runtime.os.name == "nt", reason="POSIX ownership fixture")
@pytest.mark.parametrize("unavailable", [False, True])
def test_runtime_state_ownership_classification_is_optional(monkeypatch, caplog, unavailable):
    from app.research_web import runtime_state

    monkeypatch.setattr(runtime_state.os, "getuid", lambda: 0)

    def getgid():
        if unavailable:
            raise RuntimeError("sensitive-token-cookie-path")
        return 0

    monkeypatch.setattr(runtime_state.os, "getgid", getgid)
    value = SimpleNamespace(st_dev=1, st_ino=2, st_mode=0o40700, st_uid=0, st_gid=0)
    runtime_state._log_identity_change(value, value, phase="enter", leaf=False, parent=True)
    assert "ownership_transition=other position=parent" in caplog.text
    assert "sensitive-token-cookie-path" not in caplog.text


def test_runtime_projects_only_active_host_verified_mcp_bindings(tmp_path, monkeypatch):
    installation_id = "mcp-installation-0123456789abcdef0123456789abcdef"
    authorization = AuthorizationManager(tmp_path)
    snapshot = authorization.register_tool(
        installation_id=installation_id,
        version="1.2.3",
        tool_name="read_filing",
        description="Read one filing",
        input_schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        output_schema=None,
        risk_tier="read_only",
    )
    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(exist_ok=True)
    active = runtime / "active.json"
    active.write_text(json.dumps({"schema_version": 1, "installation_ids": [installation_id]}))
    active.chmod(0o600)
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "1")

    bindings = launch_runtime.load_mcp_runtime_bindings(tmp_path)

    assert bindings[0]["schema_sha256"] == snapshot["schema_sha256"]
    assert bindings[0]["name"] == f"mcp__{installation_id}__read_filing"


def test_runtime_ignores_mcp_activation_when_feature_is_disabled(tmp_path, monkeypatch):
    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(parents=True)
    (runtime / "active.json").write_text("not-json")
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")

    assert launch_runtime.load_mcp_runtime_bindings(tmp_path) == []


def test_runtime_launch_enables_mcp_bindings_by_default(monkeypatch):
    monkeypatch.delenv("RESEARCH_MCP_RUNTIME_ENABLED", raising=False)

    assert launch_runtime.mcp_runtime_enabled() is True


def test_research_runtime_readiness_accepts_only_python_312_with_required_packages(
    tmp_path, monkeypatch
):
    python = tmp_path / "python"
    python.touch()
    observed = {}

    def run(command, **options):
        observed["command"] = command
        observed["options"] = options
        return SimpleNamespace(
            returncode=0,
            stdout='{"version":[3,12],"packages":["numpy","pandas","matplotlib","openpyxl"]}\n',
            stderr="",
        )

    monkeypatch.setattr(launch_runtime.subprocess, "run", run)
    launch_runtime.validate_research_python(python)

    assert observed["command"][0] == str(python)
    assert observed["options"]["env"] == {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}


@pytest.mark.parametrize(
    "stdout,returncode",
    [
        ('{"version":[3,11],"packages":["numpy","pandas","matplotlib","openpyxl"]}\n', 0),
        ('{"version":[3,12],"packages":["numpy","pandas","matplotlib"]}\n', 0),
        ("[]\n", 0),
        ("", 1),
    ],
)
def test_research_runtime_readiness_fails_closed_with_stable_code(
    tmp_path, monkeypatch, stdout, returncode
):
    python = tmp_path / "python"
    python.touch()
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=returncode, stdout=stdout, stderr="private provider detail"
        ),
    )

    with pytest.raises(RuntimeError, match="^runtime_not_ready$"):
        launch_runtime.validate_research_python(python)


def test_runtime_rejects_non_object_mcp_activation_without_leaking_parser_errors(
    tmp_path, monkeypatch
):
    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(parents=True)
    active = runtime / "active.json"
    active.write_text("[]")
    active.chmod(0o600)
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "1")

    with pytest.raises(RuntimeError, match="激活清单无效"):
        launch_runtime.load_mcp_runtime_bindings(tmp_path)


def make_tabbit_vendor(tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    vendor.mkdir(parents=True)
    archive = vendor / "dsh-tabbit-0.3.4.tgz"
    package = json.dumps({"name": "dsh-tabbit", "version": "0.3.4"}).encode()
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("package/package.json")
        info.size = len(package)
        bundle.addfile(info, io.BytesIO(package))
        module = b"export const name = 'tabbit';"
        info = tarfile.TarInfo("package/lib/core/index.js")
        info.size = len(module)
        bundle.addfile(info, io.BytesIO(module))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    license_path = vendor / "LICENSE"
    license_path.write_text("MIT test license\n")
    (vendor / "manifest.json").write_text(
        json.dumps(
            {
                "name": "dsh-tabbit",
                "version": "0.3.4",
                "source_commit": "361ef61f4d42ae51d657ca1351acacd6b5db5d44",
                "archive": archive.name,
                "sha256": digest,
                "license": "MIT",
                "license_sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
                "files": ["lib/core/index.js", "package.json"],
            }
        )
    )
    return vendor


def test_tabbit_archive_is_verified_and_staged_into_private_profile(tmp_path):
    vendor = make_tabbit_vendor(tmp_path)
    home = tmp_path / "home"
    profile = home / "profiles/web"
    profile.mkdir(parents=True)
    (profile / "package.json").write_text(
        json.dumps(
            {
                "name": "dsh-profile-web",
                "private": True,
                "dependencies": {},
                "dsh": {
                    "profile": {
                        "bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"],
                        "patchReload": "live",
                    }
                },
            }
        )
    )

    result = launch_runtime.stage_tabbit_package(vendor, home)

    installed = home / "profiles/node_modules/dsh-tabbit"
    assert json.loads((installed / "package.json").read_text())["version"] == "0.3.4"
    profile_package = json.loads((profile / "package.json").read_text())
    assert profile_package["dependencies"]["dsh-tabbit"] == "0.3.4"
    assert profile_package["dsh"]["profile"]["bundles"][-1] == "dsh-tabbit"
    assert result["source_commit"] == "361ef61f4d42ae51d657ca1351acacd6b5db5d44"


def test_tabbit_archive_hash_mismatch_fails_closed(tmp_path):
    vendor = make_tabbit_vendor(tmp_path)
    manifest = json.loads((vendor / "manifest.json").read_text())
    manifest["sha256"] = "0" * 64
    (vendor / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="完整性"):
        launch_runtime.stage_tabbit_package(vendor, tmp_path / "home")


def test_tabbit_license_or_file_manifest_mismatch_fails_closed(tmp_path):
    vendor = make_tabbit_vendor(tmp_path)
    (vendor / "LICENSE").write_text("changed")
    with pytest.raises(RuntimeError, match="许可证"):
        launch_runtime.stage_tabbit_package(vendor, tmp_path / "home")

    vendor = make_tabbit_vendor(tmp_path / "second")
    manifest = json.loads((vendor / "manifest.json").read_text())
    manifest["files"] = ["package.json"]
    (vendor / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="文件清单"):
        launch_runtime.stage_tabbit_package(vendor, tmp_path / "home")


def test_tabbit_archive_member_paths_use_posix_manifest_semantics():
    assert launch_runtime._tabbit_archive_parts("package/lib/core/index.js") == (
        "package",
        "lib",
        "core",
        "index.js",
    )
    with pytest.raises(RuntimeError, match="不安全路径"):
        launch_runtime._tabbit_archive_parts(r"package\..\outside.js")


def test_runtime_atomic_json_uses_windows_compatible_permissions(tmp_path, monkeypatch):
    target = tmp_path / "profile" / "package.json"
    monkeypatch.delattr(launch_runtime.os, "fchmod", raising=False)
    monkeypatch.setattr(launch_runtime.os, "name", "nt")

    launch_runtime._atomic_json(target, {"name": "研究运行时"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"name": "研究运行时"}


def test_runtime_overlay_disables_installer_and_keeps_fetch_takeover_off_by_default(tmp_path):
    config = launch_runtime.load_tabbit_config(tmp_path)
    overlay = launch_runtime.tabbit_overlay(config, PureWindowsPath("/adapter.mjs"))

    assert config == {
        "browser_enabled": True,
        "web_fetch_enabled": False,
        "instance_id": None,
    }
    assert "id: tabbit-installer\n  disabled: true" in overlay
    assert "id: tabbit-tool-browser\n  disabled: false" in overlay
    assert "fetchProvider: http" in overlay
    assert 'name: "/adapter.mjs"' in overlay


@pytest.mark.parametrize("version", ["v22.19.0", "v22.20.1", "v24.0.0", "v24.19.0"])
def test_tabbit_node_supported_versions(version, monkeypatch):
    monkeypatch.setattr(launch_runtime.subprocess, "check_output", lambda *args, **kwargs: version)
    assert launch_runtime.validate_tabbit_node("node") == version.removeprefix("v")


@pytest.mark.parametrize("version", ["v22.18.0", "v23.9.0", "v25.9.0", "v21.20.0"])
def test_tabbit_node_unsupported_versions_fail_closed(version, monkeypatch):
    monkeypatch.setattr(launch_runtime.subprocess, "check_output", lambda *args, **kwargs: version)
    with pytest.raises(RuntimeError, match="22.19"):
        launch_runtime.validate_tabbit_node("node")


def test_live_acceptance_control_is_instance_bound_and_disables_retries(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "research"
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *a, **kw: launch_runtime.PINNED_COMMIT
    )
    monkeypatch.setenv(
        "RESEARCH_ACCEPTANCE_CONTROL",
        json.dumps(
            {
                "dataHome": str(data.resolve()),
                "modelCalls": 6,
                "tool": "datahub_get_fund_data",
            }
        ),
    )
    launch_runtime.prepare(source, data, "/node", 13081)
    overlay = (data / "runtime/overlay.yml").read_text()
    assert "maxRetries: 0" in overlay
    assert "acceptance:" in overlay
    assert "modelCalls: 6" in overlay
    assert "tool: datahub_get_fund_data" in overlay
    with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
        launch_runtime.prepare(source, tmp_path / "other", "/node", 13081)
    with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
        launch_runtime.prepare(source, data, "/node", 3081)


def test_docker_text_acceptance_requires_exact_staged_model_binding(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    data = tmp_path / "isolated-data"
    identity = "b" * 32
    control = {
        "dataHome": str(data.resolve()),
        "profile": "docker-text",
        "installationId": identity,
        "modelCalls": 3,
        "maxOutputTokens": 512,
    }
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps(control))
    monkeypatch.setattr(
        launch_runtime,
        "read_acceptance_budget",
        lambda _: {"modelCalls": 3, "maxOutputTokens": 512},
        raising=False,
    )
    monkeypatch.setattr(
        launch_runtime.subprocess, "check_output", lambda *a, **kw: launch_runtime.PINNED_COMMIT
    )
    with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
        launch_runtime.prepare(source, data, "/node", 3081)
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    monkeypatch.setattr(
        launch_runtime,
        "verify_staged_runtime",
        lambda *a, **kw: {"closure_sha256": "a" * 64, "closure_files": 1},
    )
    binding = {
        "model_backend": "docker-private-file",
        "model_credential_root": Path("/run/rwb-secrets/private/models") / identity,
        "model_installation_id": identity,
    }
    for changes in (
        {"model_backend": None},
        {"model_installation_id": "c" * 32},
        {"model_credential_root": tmp_path / "ambient"},
    ):
        with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
            launch_runtime.prepare(source, data, "/node", 3081, **{**binding, **changes})
    for changes in (
        {"dataHome": str(tmp_path / "other")},
        {"installationId": "c" * 32},
        {"modelCalls": 4},
        {"budgetVerified": True},
        {"tool": "datahub_get_fund_data"},
    ):
        monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps({**control, **changes}))
        with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
            launch_runtime.prepare(source, data, "/node", 3081, **binding)
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps(control))
    _, env, _ = launch_runtime.prepare(source, data, "/node", 3081, **binding)
    overlay = (data / "runtime/overlay.yml").read_text()
    assert "profile: docker-text" in overlay
    assert f'installationId: "{identity}"' in overlay
    assert "maxOutputTokens: 512" in overlay
    assert "maxTokens: 512" in overlay
    assert "maxRetries: 0" in overlay
    assert "baseURL: https://api.deepseek.com" in overlay
    assert "- id: settings\n  disabled: true" in overlay
    assert "budgetBridge:" in overlay
    import yaml

    rows = {row["id"]: row for row in yaml.safe_load(overlay) if "id" in row}
    for plugin in (
        "tabbit-browser",
        "tabbit-permissions",
        "tabbit-tool-browser",
        "tabbit-web-fetch",
        "tabbit-mentions",
        "tabbit-installer",
        "research-tabbit-adapter",
    ):
        assert rows[plugin]["disabled"] is True
    assert "tool: datahub_get_fund_data" not in overlay
    assert "RESEARCH_ACCEPTANCE_CONTROL" not in env


def test_docker_text_generated_overlay_activates_actual_fixed_sdk(tmp_path, monkeypatch):
    import os
    import socket

    source_name = os.environ.get("RWB_TEST_FIXED_DSH_SOURCE")
    node = os.environ.get("RWB_TEST_NODE")
    if not source_name or not node:
        pytest.skip("explicit existing fixed SDK and Node required; no dependency installation")
    source = Path(source_name)
    data = tmp_path / "isolated-data"
    identity = "b" * 32
    monkeypatch.setenv("RWB_DSH_STAGED", "1")
    monkeypatch.setenv(
        "RESEARCH_ACCEPTANCE_CONTROL",
        json.dumps(
            {
                "dataHome": str(data.resolve()),
                "profile": "docker-text",
                "installationId": identity,
                "modelCalls": 3,
                "maxOutputTokens": 512,
            }
        ),
    )
    monkeypatch.setattr(
        launch_runtime,
        "verify_staged_runtime",
        lambda *a, **kw: {
            "closure_sha256": "a" * 64,
            "closure_files": 1,
        },
    )
    monkeypatch.setattr(
        launch_runtime,
        "read_acceptance_budget",
        lambda _: {
            "modelCalls": 3,
            "maxOutputTokens": 512,
        },
    )
    _, _, work = launch_runtime.prepare(
        source,
        data,
        node,
        3081,
        model_backend="docker-private-file",
        model_credential_root=Path("/run/rwb-secrets/private/models") / identity,
        model_installation_id=identity,
    )
    home = data / "runtime/home"
    launch_runtime.prepare_runtime_module_fallback(source, home, node)
    vendor = Path(launch_runtime.__file__).parents[2] / "vendor/dsh-tabbit/0.3.4"
    launch_runtime.stage_tabbit_package(vendor, home)
    launch_runtime.stage_tabbit_adapter(
        Path(launch_runtime.__file__).with_name("runtime") / "tabbit-adapter.mjs", home
    )
    launch_runtime.prepare_runtime_module_fallback(source, home, node)
    settings = home / "settings.yaml"
    settings.write_text(
        "llm-deepseek:\n  baseURL: https://invalid.example.test\n", encoding="utf-8"
    )
    before = settings.read_bytes()
    for _ in range(2):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = str(listener.getsockname()[1])
        result = subprocess.run(
            [
                node,
                str(Path(__file__).with_name("model_credentials_native.mjs")),
                str(source),
                str(data),
                "sdk-docker-text-activation",
                port,
            ],
            cwd=work,
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "en_US.UTF-8",
                "HOME": str(home),
                "DSH_HOME": str(home),
                "DSH_TELEMETRY_DISABLED": "1",
            },
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        safe = [
            line
            for line in result.stdout.splitlines()
            if line.startswith("DOCKER_TEXT_ACTIVATION:")
        ]
        assert result.returncode == 0, safe
        assert len(safe) == 1
        proof = json.loads(safe[0].split(":", 1)[1])
        assert proof["result"] == "PASS" and proof["networkCalls"] == 0
        assert settings.read_bytes() == before


@pytest.mark.parametrize("bad_cap", [True, 0, -1, 4097, 512.0, "512"])
def test_docker_text_acceptance_rejects_invalid_output_cap(tmp_path, monkeypatch, bad_cap):
    control = {
        "dataHome": str(tmp_path.resolve()),
        "profile": "docker-text",
        "installationId": "b" * 32,
        "modelCalls": 3,
        "maxOutputTokens": bad_cap,
    }
    monkeypatch.setenv("RESEARCH_ACCEPTANCE_CONTROL", json.dumps(control))
    with pytest.raises(RuntimeError, match="acceptance_control_invalid"):
        launch_runtime.live_acceptance_control(tmp_path, 3081)


@pytest.mark.parametrize(
    ("target", "stage"),
    [
        ("validate_tabbit_node", "launcher_node"),
        ("prepare", "launcher_prepare"),
        ("prepare_runtime_module_fallback", "launcher_modules"),
        ("stage_tabbit_package", "launcher_tabbit_package"),
        ("stage_tabbit_adapter", "launcher_tabbit_adapter"),
        ("_atomic_json", "launcher_config"),
        ("execve", "launcher_exec"),
    ],
)
def test_launcher_failure_emits_fixed_stage_without_exception_text(
    tmp_path, monkeypatch, target, stage
):
    messages = []
    monkeypatch.setattr(
        sys, "argv", ["launcher", "--source", str(tmp_path), "--data", str(tmp_path)]
    )
    monkeypatch.setattr(launch_runtime, "setup_logging", lambda: None)
    monkeypatch.setattr(
        launch_runtime,
        "log",
        SimpleNamespace(
            error=lambda event, **fields: messages.append((event, fields)),
            info=lambda *args, **kwargs: None,
        ),
    )
    monkeypatch.setattr(launch_runtime, "validate_tabbit_node", lambda *args: "24.19.0")
    monkeypatch.setattr(launch_runtime, "prepare", lambda *args, **kwargs: (["node"], {}, tmp_path))
    monkeypatch.setattr(launch_runtime, "prepare_runtime_module_fallback", lambda *args: 1)
    monkeypatch.setattr(
        launch_runtime,
        "stage_tabbit_package",
        lambda *args: {"version": "fixture", "source_commit": "fixture"},
    )
    monkeypatch.setattr(launch_runtime, "stage_tabbit_adapter", lambda *args: None)
    monkeypatch.setattr(launch_runtime, "load_tabbit_config", lambda *args: {})
    monkeypatch.setattr(launch_runtime, "_atomic_json", lambda *args: None)
    monkeypatch.setattr(launch_runtime.os, "chdir", lambda *args: None)

    def fail(*args, **kwargs):
        raise PermissionError(13, "fixture-private-path-command-token")

    if target == "execve":
        monkeypatch.setattr(launch_runtime.os, target, fail)
    else:
        monkeypatch.setattr(launch_runtime, target, fail)
    with pytest.raises(SystemExit) as error:
        launch_runtime.main()
    assert error.value.code == 1
    records = [
        json.loads(event.removeprefix("container_startup_failure "))
        for event, _ in messages
        if event.startswith("container_startup_failure ")
    ]
    assert records == [
        {
            "stage": stage,
            "exception_class": "PermissionError",
            "errno": 13,
            "runtime_returncode": None,
            "web_returncode": None,
        }
    ]
    assert "fixture-private" not in json.dumps(messages)
