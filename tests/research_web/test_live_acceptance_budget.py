"""Historical policy fixtures prove accounting mechanics, never authorize live calls."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.research_web import live_acceptance_budget as budget

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
INSTALLATION = "a" * 32


@pytest.fixture
def root(tmp_path):
    if os.name != "posix":
        pytest.skip("Private FD fixtures require POSIX")
    parent = tmp_path.resolve() / "private" / "live-acceptance"
    parent.mkdir(parents=True, mode=0o700)
    parent.parent.chmod(0o700)
    return parent / INSTALLATION


def control():
    return budget.authorization(3, 512, "2026-10-09T12:30:00Z")


def initialized(root):
    budget.BudgetStore.initialize(root, INSTALLATION, control(), clock=lambda: NOW)
    return budget.BudgetStore(root, INSTALLATION, clock=lambda: NOW)


def ledger(root):
    return json.loads((root / "ledger.json").read_bytes())


def test_read_missing_never_creates(root):
    store = budget.BudgetStore(root, INSTALLATION, clock=lambda: NOW)
    assert store.read_optional() is None
    with pytest.raises(budget.BudgetError):
        store.describe()
    with pytest.raises(budget.BudgetError):
        store.reserve(1)
    assert not root.exists()


def test_current_clock_policy_is_expired_without_creating(root):
    assert datetime.now(UTC) >= budget.POLICY_EXPIRY
    with pytest.raises(budget.BudgetError, match="acceptance_budget_expired"):
        budget.BudgetStore.initialize(root, INSTALLATION, control())
    assert not root.exists()
    initialized(root)
    before = (root / "ledger.json").read_bytes()
    with pytest.raises(budget.BudgetError, match="acceptance_budget_expired"):
        budget.BudgetStore(root, INSTALLATION).reserve(1)
    assert (root / "ledger.json").read_bytes() == before


def test_canonical_limits_and_historical_cost():
    value = control()
    assert value["policyExpires"] == "2026-10-10T00:00:00Z"
    assert value["inputMicroUsdPerMillion"] == 300000
    assert value["outputMicroUsdPerMillion"] == 1200000
    assert value["totalMicroUsd"] == 3 * budget.request_cost(512) == 945564
    assert value["totalOutputTokens"] == 1536
    assert value["totalInputTokens"] == 3 * 1048576


@pytest.mark.parametrize("calls,output", [(4, 512), (True, 512), (3, 513), (3, True), (0, 1)])
def test_authorization_rejects_outside_scoped_caps(calls, output):
    with pytest.raises(budget.BudgetError, match="acceptance_budget_invalid"):
        budget.authorization(calls, output, "2026-10-09T12:30:00Z")


def test_no_refund_and_no_reset_across_instances(root):
    store = initialized(root)
    assert store.reserve(1) == {"ticket": 1, "remainingMillis": 1800000}
    assert ledger(root)["outputTokens"] == 512
    before = (root / "ledger.json").read_bytes()
    with pytest.raises(budget.BudgetError, match="acceptance_budget_exists"):
        budget.BudgetStore.initialize(root, INSTALLATION, control(), clock=lambda: NOW)
    assert (root / "ledger.json").read_bytes() == before
    fresh = budget.BudgetStore(root, INSTALLATION, clock=lambda: NOW)
    assert fresh.reserve(512)["ticket"] == 2
    assert fresh.reserve(1)["ticket"] == 3
    with pytest.raises(budget.BudgetError, match="acceptance_budget_exhausted"):
        fresh.reserve(1)
    assert ledger(root)["microUsd"] == control()["totalMicroUsd"]


def test_concurrent_reservations_cannot_overspend(root):
    initialized(root)

    def reserve(_):
        try:
            return budget.BudgetStore(root, INSTALLATION, clock=lambda: NOW).reserve(1)["ticket"]
        except budget.BudgetError as error:
            assert str(error) == "acceptance_budget_exhausted"
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(12)))
    assert sorted(value for value in results if value is not None) == [1, 2, 3]
    assert ledger(root)["tickets"] == 3


def test_reservation_persists_across_process_restart(root):
    initialized(root).reserve(1)
    code = """from datetime import UTC,datetime
from app.research_web.live_acceptance_budget import BudgetStore
import json,sys
print(json.dumps(BudgetStore(sys.argv[1],sys.argv[2],clock=lambda:datetime(2026,10,9,12,tzinfo=UTC)).reserve(1)))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root), INSTALLATION],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["ticket"] == 2
    assert ledger(root)["tickets"] == 2


@pytest.mark.parametrize("name", ["control.json", "ledger.json", "budget.lock"])
@pytest.mark.parametrize("mutation", ["mode", "symlink", "hardlink", "missing"])
def test_private_artifact_rejections(root, name, mutation):
    store = initialized(root)
    target = root / name
    if mutation == "mode":
        target.chmod(0o644)
    elif mutation == "symlink":
        saved = root / (name + ".saved")
        target.rename(saved)
        target.symlink_to(saved)
    elif mutation == "hardlink":
        os.link(target, root / (name + ".alias"))
    else:
        target.unlink()
    with pytest.raises(budget.BudgetError):
        store.reserve(1)


@pytest.mark.parametrize(
    "mutation", ["tickets", "cost", "whitespace", "duplicate", "identity", "policy"]
)
def test_tampered_control_or_ledger_rejected(root, mutation):
    store = initialized(root)
    target = root / "ledger.json"
    value = ledger(root)
    if mutation == "tickets":
        value["tickets"] = 1
    elif mutation == "cost":
        value["microUsd"] = 1
    elif mutation == "identity":
        target = root / "control.json"
        value = json.loads(target.read_bytes())
        value["installationId"] = "b" * 32
    elif mutation == "policy":
        target = root / "control.json"
        value = json.loads(target.read_bytes())
        value["authorization"]["policyExpires"] = "2027-10-10T00:00:00Z"
    if mutation == "whitespace":
        target.write_text(json.dumps(value))
    elif mutation == "duplicate":
        target.write_bytes(b'{"tickets":0,"tickets":0}')
    else:
        target.write_bytes(budget._encode(value))
    with pytest.raises(budget.BudgetError, match="acceptance_budget_invalid"):
        store.reserve(1)


def test_existing_incomplete_init_never_repaired(root):
    root.mkdir(mode=0o700)
    store = budget.BudgetStore(root, INSTALLATION, clock=lambda: NOW)
    with pytest.raises(budget.BudgetError):
        store.read_optional()
    with pytest.raises(budget.BudgetError, match="acceptance_budget_exists"):
        budget.BudgetStore.initialize(root, INSTALLATION, control(), clock=lambda: NOW)
    assert list(root.iterdir()) == []


def test_expiry_after_commit_is_uncertain_and_ticket_spent(root, monkeypatch):
    store = initialized(root)
    original = store._publish

    def publish(*args):
        original(*args)
        store.clock = lambda: NOW + timedelta(hours=1)

    monkeypatch.setattr(store, "_publish", publish)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_commit_uncertain"):
        store.reserve(1)
    assert ledger(root)["tickets"] == 1


def test_fsync_failure_after_rename_is_uncertain(root, monkeypatch):
    store = initialized(root)
    original = budget.os.fsync
    count = 0

    def fail_directory(fd):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("private detail")
        original(fd)

    monkeypatch.setattr(budget.os, "fsync", fail_directory)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_commit_uncertain"):
        store.reserve(1)
    assert ledger(root)["tickets"] == 1


def test_script_isolated_import_has_no_global_settings_or_root_mutation():
    script = Path(budget.__file__).resolve()
    code = """import importlib.util,os,sys
before=dict(os.environ)
spec=importlib.util.spec_from_file_location('isolated_budget',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert 'core.settings' not in sys.modules
assert dict(os.environ)==before
"""
    subprocess.run([sys.executable, "-I", "-c", code, str(script)], check=True, capture_output=True)


def test_cli_rejects_non_linux_with_fixed_json():
    if sys.platform == "linux":
        pytest.skip("Non-Linux rejection fixture")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(Path(budget.__file__).resolve()),
            "--installation-id",
            INSTALLATION,
        ],
        check=False,
        input='{"op":"reserve","outputTokens":1}',
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"ok": False, "error": "acceptance_budget_invalid"}


@pytest.mark.parametrize("tokens", [0, True, 513, "1", 1.5])
def test_invalid_reservation_never_spends(root, tokens):
    store = initialized(root)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_invalid"):
        store.reserve(tokens)
    assert ledger(root)["tickets"] == 0


@pytest.mark.parametrize("hours", [2, 13])
def test_init_rejects_expanded_authorization_window(root, hours):
    until = (NOW + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(budget.BudgetError, match="acceptance_budget_invalid"):
        budget.BudgetStore.initialize(
            root, INSTALLATION, budget.authorization(3, 512, until), clock=lambda: NOW
        )
    assert not root.exists()


@pytest.mark.parametrize("target", ["leaf", "parent"])
def test_unsafe_directory_mode_rejected(root, target):
    store = initialized(root)
    (root if target == "leaf" else root.parent).chmod(0o755)
    with pytest.raises(budget.BudgetError):
        store.describe()


def test_parent_symlink_never_creates_state(root):
    saved = root.parent.with_name("saved")
    root.parent.rename(saved)
    root.parent.symlink_to(saved, target_is_directory=True)
    with pytest.raises(budget.BudgetError):
        budget.BudgetStore.initialize(root, INSTALLATION, control(), clock=lambda: NOW)
    assert not (saved / INSTALLATION).exists()


def test_lock_replacement_after_commit_is_uncertain(root, monkeypatch):
    store = initialized(root)
    original = store._publish

    def replace_lock(*args):
        original(*args)
        lock = root / "budget.lock"
        lock.rename(root / "old.lock")
        lock.touch(mode=0o600)

    monkeypatch.setattr(store, "_publish", replace_lock)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_commit_uncertain"):
        store.reserve(1)
    assert ledger(root)["tickets"] == 1


def test_publish_compare_and_swap_rejects_concurrent_tamper(root, monkeypatch):
    store = initialized(root)
    original = budget.os.fsync
    changed = False

    def tamper_after_temp_flush(fd):
        nonlocal changed
        original(fd)
        if not changed:
            changed = True
            (root / "ledger.json").write_bytes(budget._encode({**ledger(root), "microUsd": 1}))

    monkeypatch.setattr(budget.os, "fsync", tamper_after_temp_flush)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_unavailable"):
        store.reserve(1)
    assert ledger(root)["tickets"] == 0
    assert not list(root.glob(".budget.*.tmp"))


def test_logging_failure_cannot_hide_rejection(root, monkeypatch):
    initialized(root)

    def failing_logger(*args, **kwargs):
        raise RuntimeError("logger unavailable")

    monkeypatch.setattr(budget.log, "warning", failing_logger)
    with pytest.raises(budget.BudgetError, match="acceptance_budget_expired"):
        budget.BudgetStore(root, INSTALLATION).describe()


@pytest.mark.parametrize("identifier", ["A" * 32, "a" * 31, "../" + "a" * 32, True])
def test_instance_id_validation(root, identifier):
    with pytest.raises(budget.BudgetError, match="acceptance_budget_invalid"):
        budget.BudgetStore(root, identifier)
