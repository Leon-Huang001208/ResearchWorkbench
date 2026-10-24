"""The explicitly reviewed model upgrade must be fenced and reversible."""

import hashlib
import json
import plistlib
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade
from research_workbench_entrypoint.resident.admission import MaintenanceBusy
from research_workbench_entrypoint.resident.gateway_fence import BirthFence

ASSET_PROFILES = (
    upgrade.ASSET_MODE,
    upgrade.ASSET_V2_MODE,
    upgrade.ASSET_V3_MODE,
    upgrade.ASSET_V4_MODE,
    upgrade.ASSET_V5_MODE,
    upgrade.ASSET_V6_MODE,
    upgrade.ASSET_V7_MODE,
    "reviewed-market-overview-v1",
    "reviewed-market-gaps-v1",
    "reviewed-market-history-v1",
    "reviewed-market-terminal-v1",
    "reviewed-etf-weekly-v1",
    "reviewed-research-dossiers-v1",
    "reviewed-discovery-v1",
    "reviewed-etf-weekly-v2",
    "reviewed-etf-historical-v1",
)


def test_discovery_profile_freezes_authorized_combination():
    assert upgrade.DISCOVERY_MODE == "reviewed-discovery-v1"
    assert (
        upgrade.previous_for(upgrade.DISCOVERY_MODE) == "5343e18d9f203a87f2d958218e4288afa527711f"
    )
    assert upgrade.DISCOVERY_PAYLOAD == "1780064b712afb61ff18f2f1811650fc31fd3038"
    assert upgrade.DISCOVERY_MODE in upgrade.ASSET_MODES
    old = {"code_commit": "old", "web_lock_sha256": "fixed-lock"}
    assert upgrade.target_manifest(
        {"manifest": old, "mode": upgrade.DISCOVERY_MODE, "target": "new"}
    ) == {**old, "code_commit": "new"}


@pytest.mark.parametrize(
    "case",
    [
        "primary_enabled",
        "private_enabled",
        "bad_enabled",
        "active_run",
        "bad_tracks",
        "workflow_enabled",
        "workflow_running",
        "workflow_corrupt",
    ],
)
def test_discovery_deploy_rechecks_all_background_work_without_writes(tmp_path, monkeypatch, case):
    home = tmp_path / "home"
    primary = home / "research-web"
    private = home / "server/users/alice/research-web"
    for root in (primary, private):
        root.mkdir(parents=True)
        (root / "index.json").write_text("{}")
    assert upgrade.discovery_background_idle(home) is True
    index = {}
    root = primary if case == "primary_enabled" else private
    if case.endswith("enabled") and not case.startswith("workflow"):
        index["automations"] = {"task": {"enabled": "false" if case == "bad_enabled" else True}}
    elif case == "active_run":
        index["automation_runs"] = {"run": {"research_status": "running"}}
    elif case == "bad_tracks":
        index["discovery_tracks"] = []
    if case.startswith("workflow"):
        folder = private / "report-workflows"
        folder.mkdir()
        catalog = {"workflows": {}, "runs": {}}
        if case == "workflow_enabled":
            catalog["workflows"]["w"] = {"schedule": {"enabled": True}}
        if case == "workflow_running":
            catalog["runs"]["r"] = {"status": "running"}
        (folder / "catalog.json").write_text(
            "{" if case == "workflow_corrupt" else json.dumps(catalog)
        )
    (root / "index.json").write_text(json.dumps(index))
    before = {str(p): p.read_bytes() for p in home.rglob("*") if p.is_file()}
    monkeypatch.setattr(
        upgrade.g,
        "no_private_processes",
        lambda *_: pytest.fail("process or HTTP probe before background gate"),
    )
    assert (
        upgrade.Operations(home, {"mode": upgrade.DISCOVERY_MODE}, None, None, None).idle() is False
    )
    assert {str(p): p.read_bytes() for p in home.rglob("*") if p.is_file()} == before


def test_market_profile_binds_resident_and_merged_product():
    assert upgrade.MARKET_MODE == "reviewed-market-overview-v1"
    assert upgrade.previous_for(upgrade.MARKET_MODE) == "4d2e3c408663b64be9e58b03213f4ca8f1152733"
    assert upgrade.MARKET_PAYLOAD == "5de7e5f2db95b8b501905af9cfdc30e8fe84db0b"


def test_wind_v3_profile_is_bound_to_the_actual_resident_and_reviewed_product():
    assert (
        upgrade.previous_for("reviewed-asset-observation-v3")
        == "5495e64c0be08c9db58e336705db90584f8ba8b5"
    )
    assert upgrade.ASSET_V3_PAYLOAD == "a0ff3ae2e2ab92bad10ba8547e45027687ec7cc1"


def test_wind_v4_profile_has_preserved_resident_and_exact_hotfix_identity():
    assert (
        upgrade.previous_for("reviewed-asset-observation-v4")
        == "5495e64c0be08c9db58e336705db90584f8ba8b5"
    )
    assert upgrade.ASSET_V4_PAYLOAD == "9b436613aad9136f4959c992c89dd72fc7354ed5"


def test_asset_profile_has_fixed_previous_and_rejects_unknown_mode():
    assert upgrade.previous_for(upgrade.ASSET_MODE) == "c68814db170900688d6a799a241efc098eb83f32"
    assert upgrade.previous_for(upgrade.ASSET_V2_MODE) == "9bc12355c3b80e4e4459f4c250e13fc2634ed23d"
    assert upgrade.ASSET_PAYLOAD == "54d4c8f9421c568de853a2f93263a2bfcd53422c"
    assert upgrade.ASSET_V2_PAYLOAD == "93d62be64084a5c92541a4a008216c0b3f56c2f1"
    assert upgrade.ASSET_MODES == frozenset(ASSET_PROFILES)
    assert upgrade.previous_for(upgrade.MODE) == upgrade.PREVIOUS
    with pytest.raises(upgrade.UpdateBlocked):
        upgrade.previous_for("unreviewed")


@pytest.mark.parametrize("profile", ASSET_PROFILES)
@pytest.mark.parametrize(
    "bad",
    [
        None,
        "backend",
        "ui",
        "dependency",
        "mode",
        "reverted",
        "deleted",
        "extra",
        "ancestry",
        "evidence",
        "evidence-mode",
        "evidence-deleted",
        "evidence-hash-malformed",
        "evidence-hash-unknown",
        "untracked",
        "gateway",
        "gateway-mode",
        "gateway-deleted",
    ],
)
def test_asset_review_uses_real_git_and_frozen_product(tmp_path, monkeypatch, bad, profile):
    def git(*args):
        return subprocess.check_output(
            ["/usr/bin/git", "-C", str(tmp_path), *args], text=True
        ).strip()

    git("init", "-b", "master")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    files = {
        upgrade.MODULE: "operator",
        upgrade.TEST: "tests",
        upgrade.ASSET_EVIDENCE: "reviewed evidence",
        upgrade.MARKET_GATEWAY: "reviewed gateway",
        "app/research_web/asset_workspace.py": "before",
        "app/research_web/ui/asset-workspace.mjs": "before",
        "requirements/web.lock": "same",
    }
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    for name in ["app/research_web/asset_workspace.py", "app/research_web/ui/asset-workspace.mjs"]:
        (tmp_path / name).write_text("reviewed")
    git("add", ".")
    git("commit", "-m", "payload")
    payload = git("rev-parse", "HEAD")
    prefix = {
        upgrade.ASSET_MODE: "ASSET",
        upgrade.ASSET_V2_MODE: "ASSET_V2",
        upgrade.ASSET_V3_MODE: "ASSET_V3",
        upgrade.ASSET_V4_MODE: "ASSET_V4",
        upgrade.ASSET_V5_MODE: "ASSET_V5",
        upgrade.ASSET_V6_MODE: "ASSET_V6",
        upgrade.ASSET_V7_MODE: "ASSET_V7",
        "reviewed-market-overview-v1": "MARKET",
        "reviewed-market-gaps-v1": "MARKET_GAPS",
        "reviewed-market-history-v1": "MARKET_HISTORY",
        "reviewed-etf-weekly-v1": "ETF_WEEKLY",
        "reviewed-research-dossiers-v1": "DOSSIERS",
        "reviewed-discovery-v1": "DISCOVERY",
        "reviewed-etf-weekly-v2": "ETF_WEEKLY_V2",
        "reviewed-etf-historical-v1": "ETF_HISTORICAL",
        "reviewed-market-terminal-v1": "MARKET_TERMINAL",
    }[profile]
    monkeypatch.setattr(upgrade, prefix + "_PREVIOUS", base)
    monkeypatch.setattr(upgrade, prefix + "_PAYLOAD", payload)
    evidence_constant = (
        "ASSET_V7_EVIDENCE_SHA256"
        if profile == upgrade.ASSET_V7_MODE
        else (
            "MARKET_TERMINAL_EVIDENCE_SHA256"
            if profile == upgrade.MARKET_TERMINAL_MODE
            else (
                "ASSET_V6_EVIDENCE_SHA256"
                if profile
                in {
                    upgrade.ASSET_V6_MODE,
                    "reviewed-etf-weekly-v1",
                    "reviewed-research-dossiers-v1",
                    "reviewed-discovery-v1",
                    "reviewed-etf-weekly-v2",
                    "reviewed-etf-historical-v1",
                }
                else "ASSET_EVIDENCE_SHA256"
            )
        )
    )
    evidence_hash = hashlib.sha256(b"reviewed evidence").hexdigest()
    if bad == "evidence-hash-malformed":
        evidence_hash = "not-a-hash"
    if bad == "evidence-hash-unknown":
        evidence_hash = "f" * 64
    monkeypatch.setattr(upgrade, evidence_constant, evidence_hash)
    monkeypatch.setattr(
        upgrade, "MARKET_GATEWAY_SHA256", hashlib.sha256(b"reviewed gateway").hexdigest()
    )
    (tmp_path / upgrade.MODULE).write_text("reviewed operator")
    if bad == "gateway":
        (tmp_path / upgrade.MARKET_GATEWAY).write_text("unreviewed gateway")
    if bad == "gateway-mode":
        (tmp_path / upgrade.MARKET_GATEWAY).chmod(0o755)
    if bad == "gateway-deleted":
        (tmp_path / upgrade.MARKET_GATEWAY).unlink()
    name = "app/research_web/asset_workspace.py"
    if bad == "evidence":
        (tmp_path / upgrade.ASSET_EVIDENCE).write_text("unreviewed evidence")
    if bad == "evidence-mode":
        (tmp_path / upgrade.ASSET_EVIDENCE).chmod(0o755)
    if bad == "evidence-deleted":
        (tmp_path / upgrade.ASSET_EVIDENCE).unlink()
    if bad == "backend":
        (tmp_path / name).write_text("unreviewed")
    if bad in {"ui", "reverted"}:
        (tmp_path / "app/research_web/ui/asset-workspace.mjs").write_text(
            "before" if bad == "reverted" else "unreviewed"
        )
    if bad == "dependency":
        (tmp_path / "requirements/web.lock").write_text("unreviewed")
    if bad == "mode":
        (tmp_path / name).chmod(0o755)
    if bad == "deleted":
        (tmp_path / name).unlink()
    if bad == "extra":
        (tmp_path / "app/research_web/ui/extra.mjs").write_text("extra")
    git("add", ".")
    git("commit", "-m", "operator")
    if bad == "ancestry":
        git("checkout", "--orphan", "foreign")
        git("commit", "-m", "foreign")
    target = git("rev-parse", "HEAD")
    if bad == "untracked":
        (tmp_path / "untracked.txt").write_text("unreviewed checkout state")
    if bad is None:
        result = upgrade.review(tmp_path, target, profile)
        assert name in result and upgrade.MODULE in result
    else:
        with pytest.raises(upgrade.UpdateBlocked):
            upgrade.review(tmp_path, target, profile)


def test_v4_accepts_exact_store_hotfix_while_v3_keeps_its_frozen_product(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(
            ["/usr/bin/git", "-C", str(tmp_path), *args], text=True
        ).strip()

    git("init", "-b", "master")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    store_name = "app/research_web/store.py"
    files = {
        upgrade.MODULE: "operator",
        upgrade.TEST: "tests",
        upgrade.ASSET_EVIDENCE: "reviewed evidence",
        upgrade.MARKET_GATEWAY: "reviewed gateway",
        store_name: "legacy Store",
    }
    for name, value in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    git("add", ".")
    git("commit", "-m", "resident baseline")
    previous = git("rev-parse", "HEAD")
    (tmp_path / store_name).write_text("reviewed v3 Store")
    git("commit", "-am", "v3 product")
    v3_payload = git("rev-parse", "HEAD")
    (tmp_path / store_name).write_text("reviewed startup-preserving Store")
    git("commit", "-am", "v4 product")
    v4_payload = git("rev-parse", "HEAD")
    (tmp_path / upgrade.MODULE).write_text("reviewed v4 operator")
    git("commit", "-am", "v4 operator")
    target = git("rev-parse", "HEAD")
    monkeypatch.setattr(upgrade, "ASSET_V3_PREVIOUS", previous)
    monkeypatch.setattr(upgrade, "ASSET_V4_PREVIOUS", previous)
    monkeypatch.setattr(upgrade, "ASSET_V3_PAYLOAD", v3_payload)
    monkeypatch.setattr(upgrade, "ASSET_V4_PAYLOAD", v4_payload)
    monkeypatch.setattr(
        upgrade, "ASSET_EVIDENCE_SHA256", hashlib.sha256(b"reviewed evidence").hexdigest()
    )
    assert upgrade.review(tmp_path, target, upgrade.ASSET_V4_MODE)[store_name] == git(
        "rev-parse", f"{v4_payload}:{store_name}"
    )
    with pytest.raises(upgrade.UpdateBlocked, match="asset_upgrade_payload_changed"):
        upgrade.review(tmp_path, target, upgrade.ASSET_V3_MODE)


@pytest.mark.parametrize(
    "state,expected",
    [
        ({}, True),
        (
            {
                "asset_observations": {
                    "x": {"status": "partial", "blocks": {"x": {"status": "partial"}}}
                }
            },
            True,
        ),
        (
            {
                "asset_observations": {
                    "x": {"status": "partial", "blocks": {"x": {"status": "loading"}}}
                }
            },
            False,
        ),
        (
            {
                "asset_observations": {
                    "x": {"status": "partial", "blocks": {"x": {"status": "error"}}}
                }
            },
            True,
        ),
        ({"asset_observations": {"x": {"status": "running"}}}, False),
        ({"data_queries": {"x": {"status": "running"}}}, False),
        ({"asset_observations": []}, False),
        (
            {
                "asset_observations": {
                    "x": {"status": "complete", "blocks": {"x": {"status": "loading"}}}
                }
            },
            False,
        ),
    ],
)
def test_asset_activity_is_not_confused_with_native_idle(state, expected):
    assert upgrade.asset_queries_idle(state) is expected


@pytest.mark.parametrize("state", ["queued", "running", "cancelling", "draining", "unknown"])
def test_history_jobs_block_resident_switching(state):
    assert not upgrade.asset_queries_idle({"asset_history_jobs": {"job": {"state": state}}})


@pytest.mark.parametrize("state", ["completed", "failed", "cancelled", "interrupted"])
def test_terminal_history_jobs_allow_resident_switching(state):
    assert upgrade.asset_queries_idle({"asset_history_jobs": {"job": {"state": state}}})


@pytest.mark.parametrize(
    "jobs", [None, [], {"job": None}, {"job": {"state": "completed", "status": "running"}}]
)
def test_malformed_history_job_activity_fails_closed(jobs):
    assert not upgrade.asset_queries_idle({"asset_history_jobs": jobs})


@pytest.mark.parametrize("profile", ASSET_PROFILES)
@pytest.mark.parametrize("scope", ["primary", "private"])
@pytest.mark.parametrize("change", ["delete", "modify", "empty", "remove_file"])
def test_asset_business_index_preservation_covers_every_scope(tmp_path, scope, change, profile):
    root = tmp_path / "research-web"
    user = tmp_path / "server/users" / str(uuid4()) / "research-web"
    value = {
        "asset_observations": {"a": {"status": "partial"}},
        "notes": {"a": "private"},
        "unknown_future_key": {"v": 0},
    }
    for folder in (root, user):
        upgrade.c.atomic(folder / "index.json", value)
    before = upgrade.asset_index_snapshot(tmp_path)
    state = {"mode": profile, "asset_index_before": before}
    upgrade.verify_asset_index(tmp_path, state)
    path = (root if scope == "primary" else user) / "index.json"
    if change == "remove_file":
        path.unlink()
    else:
        after = dict(value)
        if change == "delete":
            del after["asset_observations"]
        elif change == "modify":
            after["unknown_future_key"] = {"v": 1}
        else:
            after["notes"] = {}
        upgrade.c.atomic(path, after)
    with pytest.raises(upgrade.UpdateBlocked):
        upgrade.verify_asset_index(tmp_path, state)


def test_asset_snapshot_contains_digests_and_distinguishes_missing_from_empty(tmp_path):
    (tmp_path / "server/users").mkdir(parents=True)
    upgrade.c.atomic(
        tmp_path / "research-web/index.json", {"notes": {"body": "secret-business-note"}, "zero": 0}
    )
    before = upgrade.asset_index_snapshot(tmp_path)
    assert "secret-business-note" not in json.dumps(before)
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in before["primary"].values())
    upgrade.c.atomic(tmp_path / "research-web/index.json", {"notes": {}, "zero": 0})
    empty = upgrade.asset_index_snapshot(tmp_path)
    upgrade.c.atomic(tmp_path / "research-web/index.json", {"zero": 0})
    assert empty != before and empty != upgrade.asset_index_snapshot(tmp_path)


def test_asset_snapshot_reads_business_indexes_larger_than_metadata_records(tmp_path):
    (tmp_path / "server/users").mkdir(parents=True)
    upgrade.c.atomic(tmp_path / "research-web/index.json", {"notes": {"body": "x" * 1_200_000}})
    before = upgrade.asset_index_snapshot(tmp_path)
    assert set(before["primary"]) == {"notes"}


@pytest.mark.parametrize("bad", ["oversized", "symlink", "malformed", "list"])
def test_asset_snapshot_rejects_unsafe_or_invalid_business_index(tmp_path, monkeypatch, bad):
    (tmp_path / "server/users").mkdir(parents=True)
    root = tmp_path / "research-web"
    root.mkdir()
    path = root / "index.json"
    path.write_text("{}")
    if bad == "oversized":
        monkeypatch.setattr(upgrade, "MAX_ASSET_INDEX_BYTES", 1)
    elif bad == "symlink":
        path.rename(root / "retired.json")
        path.symlink_to(root / "retired.json")
    else:
        path.write_text("{" if bad == "malformed" else "[]")
    with pytest.raises(upgrade.UpdateBlocked, match="index_invalid"):
        upgrade.asset_index_snapshot(tmp_path)


def test_asset_snapshot_rejects_fifo_without_blocking(tmp_path):
    import os

    (tmp_path / "server/users").mkdir(parents=True)
    (tmp_path / "research-web").mkdir()
    os.mkfifo(tmp_path / "research-web/index.json")
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; from research_workbench_entrypoint.resident import model_provider_upgrade as u; u.asset_index_snapshot(Path(sys.argv[1]))",
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        timeout=3,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode != 0 and "asset_upgrade_index_invalid" in process.stderr


@pytest.mark.parametrize(
    "command,profile",
    [
        ("apply", upgrade.MODE),
        ("apply-assets", upgrade.ASSET_MODE),
        ("apply-assets-v2", upgrade.ASSET_V2_MODE),
        ("apply-assets-v3", upgrade.ASSET_V3_MODE),
        ("apply-assets-v4", upgrade.ASSET_V4_MODE),
        ("apply-assets-v5", upgrade.ASSET_V5_MODE),
        ("apply-assets-v6", upgrade.ASSET_V6_MODE),
        ("apply-assets-v7", upgrade.ASSET_V7_MODE),
        ("apply-etf-weekly", "reviewed-etf-weekly-v1"),
        ("apply-dossiers", "reviewed-research-dossiers-v1"),
        ("apply-discovery", "reviewed-discovery-v1"),
        ("apply-etf-weekly-v2", "reviewed-etf-weekly-v2"),
        ("apply-etf-historical", "reviewed-etf-historical-v1"),
        ("apply-market-history", upgrade.MARKET_HISTORY_MODE),
        ("apply-market-terminal", upgrade.MARKET_TERMINAL_MODE),
        ("apply-market", "reviewed-market-overview-v1"),
        ("apply-market-gaps", "reviewed-market-gaps-v1"),
        ("recover", upgrade.MODE),
    ],
)
def test_cli_selects_only_the_closed_profile(tmp_path, monkeypatch, command, profile):
    (tmp_path / "logs").mkdir()
    calls = []

    def operate(*args, **kwargs):
        calls.append(kwargs)
        return {"status": "deployed"}

    monkeypatch.setattr(upgrade, "operate", operate)
    assert upgrade.main([command, "--home", str(tmp_path)]) == 0
    assert calls == [{"recovering": command == "recover", "mode": profile}]


@pytest.mark.parametrize(
    "profile,previous",
    [
        (upgrade.ASSET_MODE, upgrade.PREVIOUS),
        (upgrade.ASSET_V2_MODE, upgrade.PREVIOUS),
        (upgrade.ASSET_V2_MODE, upgrade.ASSET_PREVIOUS),
        (upgrade.ASSET_V3_MODE, upgrade.PREVIOUS),
        (upgrade.ASSET_V3_MODE, upgrade.ASSET_PREVIOUS),
        (upgrade.ASSET_V3_MODE, upgrade.ASSET_V2_PREVIOUS),
        (upgrade.ASSET_V3_MODE, upgrade.ASSET_V3_PAYLOAD),
        (upgrade.ASSET_V4_MODE, upgrade.PREVIOUS),
        (upgrade.ASSET_V4_MODE, upgrade.ASSET_PREVIOUS),
        (upgrade.ASSET_V4_MODE, upgrade.ASSET_V2_PREVIOUS),
        (upgrade.ASSET_V4_MODE, upgrade.ASSET_V3_PAYLOAD),
        (upgrade.ASSET_V4_MODE, upgrade.ASSET_V4_PAYLOAD),
        (upgrade.ASSET_V6_MODE, upgrade.ASSET_V5_PREVIOUS),
        (upgrade.ASSET_V6_MODE, upgrade.ASSET_V6_PAYLOAD),
        (upgrade.ASSET_V7_MODE, upgrade.ASSET_V6_PAYLOAD),
        (upgrade.ASSET_V7_MODE, upgrade.ASSET_V7_PAYLOAD),
        (upgrade.ASSET_V5_MODE, upgrade.ASSET_V4_PREVIOUS),
        (upgrade.ASSET_V5_MODE, upgrade.MARKET_GAPS_PREVIOUS),
        (upgrade.ASSET_V5_MODE, "9bc4e4cab91130647a5bc0dfa519e97f4773416a"),
        ("reviewed-market-overview-v1", upgrade.ASSET_V4_PREVIOUS),
        ("reviewed-market-overview-v1", "5de7e5f2db95b8b501905af9cfdc30e8fe84db0b"),
        (upgrade.MARKET_GAPS_MODE, upgrade.MARKET_PREVIOUS),
        (upgrade.MARKET_GAPS_MODE, upgrade.MARKET_GAPS_PAYLOAD),
        (upgrade.MARKET_TERMINAL_MODE, upgrade.MARKET_HISTORY_PREVIOUS),
        (upgrade.MARKET_TERMINAL_MODE, upgrade.MARKET_TERMINAL_PAYLOAD),
        ("reviewed-etf-weekly-v1", upgrade.ASSET_V6_PREVIOUS),
        ("reviewed-etf-weekly-v1", "25b399a42d691766d41bcafce5adbdc3b8cc3d74"),
        ("reviewed-etf-weekly-v1", "0e0022ac792eba88fba0f233524f5c8d66024569"),
        ("reviewed-etf-weekly-v1", "988046d23f9951f889a3b9d02e355ed59fd6aa65"),
        ("reviewed-etf-weekly-v2", upgrade.ASSET_V6_PREVIOUS),
        ("reviewed-etf-weekly-v2", "988046d23f9951f889a3b9d02e355ed59fd6aa65"),
        ("reviewed-etf-weekly-v2", "2e1ba701a0f33bf1dbeab79f1f9984f320d33a24"),
        ("reviewed-etf-weekly-v2", "56709a8dbb6e01d2ab17b64533319e199ebef86f"),
        ("reviewed-etf-historical-v1", "5343e18d9f203a87f2d958218e4288afa527711f"),
        ("reviewed-etf-historical-v1", "fc96be6d147721af080619179cdad1966b26ae8f"),
        ("reviewed-etf-historical-v1", "d5d5b456706fc02505ac1100353d46438c184556"),
    ],
)
def test_asset_journal_cannot_select_the_legacy_previous(profile, previous):
    state = {
        "transaction": str(uuid4()),
        "version": 4,
        "mode": profile,
        "previous": previous,
        "model_before": {
            "provider": "fixture",
            "model": "fixture",
            "credential_configured": True,
            "credential_storage": "fixture",
        },
    }
    with pytest.raises(upgrade.UpdateBlocked, match="journal_invalid"):
        upgrade.validate_state(Path("/unused"), state)


class Operations:
    def __init__(self, *, busy=False, fail=None):
        self.busy, self.fail = busy, fail
        self.events = []

    def idle(self):
        self.events.append("idle")
        return not self.busy

    def checkpoint(self, state, phase):
        self.events.append("journal:" + phase)
        state["phase"] = phase

    def action(self, name, state):
        self.events.append(name)
        if name == self.fail:
            raise RuntimeError("synthetic_failure")

    def finish(self, state, result):
        self.events.append("finish:" + result)
        return {"status": result, "preserved": True}


def test_running_or_unknown_never_journals_or_stops():
    ops = Operations(busy=True)
    assert upgrade.execute(ops, {})["status"] == "deferred"
    assert ops.events == ["idle"]


def test_success_persists_intent_before_every_effect():
    ops = Operations()
    assert upgrade.execute(ops, {})["status"] == "deployed"
    assert ops.events[-1] == "finish:deployed"
    for i, event in enumerate(ops.events):
        if event in upgrade.FORWARD:
            assert ops.events[i - 1] == "journal:" + event


@pytest.mark.parametrize("failed", upgrade.FORWARD)
def test_every_forward_failure_restores_both_services(failed):
    ops = Operations(fail=failed)
    assert upgrade.execute(ops, {})["status"] == "rolled_back"
    assert "restore_sources_and_wheel" in ops.events
    assert "verify_previous" in ops.events
    assert ops.events[-1] == "finish:rolled_back"


@pytest.mark.parametrize("phase", upgrade.FORWARD + upgrade.BACKWARD)
def test_interrupted_phase_always_recovers_the_previous_version(phase):
    ops = Operations()
    result = upgrade.execute(ops, {"phase": phase}, recovering=True)
    assert result["status"] == "rolled_back"
    assert not any(step in ops.events for step in upgrade.FORWARD if step != "stop_gateway")


@pytest.mark.parametrize("failed", upgrade.BACKWARD)
def test_failed_rollback_retains_recovery_not_success(failed):
    ops = Operations(fail=failed)
    assert upgrade.execute(ops, {}, recovering=True)["status"] == "recovery_required"
    assert not any(e.startswith("finish:") for e in ops.events)


def test_activity_becoming_unknown_before_rollback_keeps_fence():
    ops = Operations(busy=True)
    assert upgrade.execute(ops, {}, recovering=True)["status"] == "recovery_required"
    assert ops.events == ["idle"]


def test_busy_during_signal_drain_does_not_retry_or_force_stop():
    class BusyDrain(Operations):
        def action(self, name, state):
            super().action(name, state)
            if name == "stop_gateway":
                raise MaintenanceBusy("synthetic_drain_pending")

    ops = BusyDrain()
    assert upgrade.execute(ops, {})["status"] == "recovery_required"
    assert ops.events.count("stop_gateway") == 1
    assert "restore_sources_and_wheel" not in ops.events


def test_real_birth_fence_reservations_are_not_native_owners(tmp_path):
    server = tmp_path / "server"
    server.mkdir(mode=0o700)
    users = [str(uuid4()), str(uuid4())]
    (server / "users").mkdir(mode=0o700)
    for user in users:
        (server / "users" / user).mkdir(mode=0o700)
        (server / "users" / user / "state").mkdir(mode=0o700)
    with sqlite3.connect(server / "accounts.sqlite3") as db:
        db.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO accounts VALUES (?)", [(x,) for x in users])
    (server / "accounts.sqlite3").chmod(0o600)
    with BirthFence(server, users[0]) as fence:
        assert upgrade.reserved_owners(server, fence.transaction) is True
        assert len(list((server / "users").glob("*/state/owner.json"))) == 2
        marker = server / "users" / users[0] / "state/owner.json/reservation"
        marker.write_text("foreign")
        assert upgrade.reserved_owners(server, fence.transaction) is False
        marker.write_text(fence.transaction)
        assert upgrade.reserved_owners(server, str(uuid4())) is False
    assert upgrade.reserved_owners(server, fence.transaction) is True


def test_real_native_owner_is_never_ignored(tmp_path):
    owner = tmp_path / "users" / str(uuid4()) / "state/owner.json"
    owner.parent.mkdir(parents=True)
    owner.write_text("{}")
    assert upgrade.reserved_owners(tmp_path, str(uuid4())) is False


def gateway_ops(tmp_path, monkeypatch):
    ops = upgrade.Operations.__new__(upgrade.Operations)
    plist = tmp_path / "gateway.plist"
    plist.write_bytes(plistlib.dumps({"ProgramArguments": ["/python"]}))
    ops.server = tmp_path
    ops.state = {
        "gateway_plist": str(plist),
        "gateway_plist_sha256": upgrade.c.digest(plist),
        "gateway_project": "/gateway",
        "gateway_command": "/python -m gateway",
    }
    monkeypatch.setattr(upgrade.g, "no_private_processes", lambda _root: None)
    return ops, f"path = {plist}\nprogram = /python\nworking directory = /gateway\n"


def test_loaded_no_pid_job_is_booted_out_and_proved_retired(tmp_path, monkeypatch):
    ops, raw = gateway_ops(tmp_path, monkeypatch)
    live = {"loaded": True}
    monkeypatch.setattr(upgrade.g, "job_state", lambda: raw if live["loaded"] else None)
    monkeypatch.setattr(upgrade.g, "job_pid", lambda: None)
    monkeypatch.setattr(upgrade.g, "listener_pids", lambda: set())
    monkeypatch.setattr(upgrade.g, "bootout_after_drain", lambda _p: live.update(loaded=False))
    ops.stop_gateway()
    assert live["loaded"] is False


def test_loaded_no_pid_unknown_job_never_receives_signal(tmp_path, monkeypatch):
    ops, raw = gateway_ops(tmp_path, monkeypatch)
    monkeypatch.setattr(upgrade.g, "job_state", lambda: raw.replace("/python", "/unknown"))
    monkeypatch.setattr(upgrade.g, "job_pid", lambda: None)
    monkeypatch.setattr(upgrade.g, "listener_pids", lambda: set())
    monkeypatch.setattr(
        upgrade.g, "bootout_after_drain", lambda _p: pytest.fail("must not stop unknown job")
    )
    with pytest.raises(MaintenanceBusy, match="process_unknown"):
        ops.stop_gateway()


def test_apply_executor_must_come_from_the_reviewed_source(tmp_path):
    with pytest.raises(upgrade.UpdateBlocked, match="executor_unverified"):
        upgrade.validate_executor(tmp_path, "a" * 40)


def test_older_frozen_executor_cannot_consume_new_transaction(tmp_path, monkeypatch):
    old, new = tmp_path / "old.pyz", tmp_path / "new.pyz"
    monkeypatch.setattr(upgrade, "__file__", str(old) + "/resident/model_provider_upgrade.py")
    monkeypatch.setattr(upgrade.sys, "argv", [str(old)])
    state = {"recovery": {"artifact": str(new), "sha256": "a" * 64}}
    with pytest.raises(upgrade.UpdateBlocked, match="other_model_recovery_version"):
        upgrade.validate_executor(tmp_path, "a" * 40, state)


def test_gateway_intent_is_durable_before_primary_journal(tmp_path, monkeypatch):
    ops = upgrade.Operations.__new__(upgrade.Operations)
    ops.root = tmp_path / "resident"
    ops.server = tmp_path / "server"
    ops.fence = SimpleNamespace(retain=False)
    state = {k: {} for k in ["new_wheel", "old_wheel", "manifest", "proof"]}
    state.update(
        previous=upgrade.PREVIOUS,
        target="a" * 40,
        config={"private_origin": "https://fixture.tail.ts.net"},
    )
    events = []
    monkeypatch.setattr(upgrade, "verify_serve", lambda _origin: None)
    monkeypatch.setattr(upgrade, "verify_private_fence", lambda _origin: events.append("https503"))
    monkeypatch.setattr(upgrade.g, "write_upgrade_journal", lambda _p, _s: events.append("gateway"))
    monkeypatch.setattr(upgrade.c, "atomic", lambda _p, _s: events.append("primary"))
    ops.checkpoint(state, "prepared")
    assert events == ["gateway", "https503", "primary"]
    assert ops.fence.retain is True


def test_gateway_only_crash_retains_birth_fence_without_claiming_primary_intent(
    tmp_path, monkeypatch
):
    ops = upgrade.Operations.__new__(upgrade.Operations)
    ops.root = tmp_path / "resident"
    ops.server = tmp_path / "server"
    ops.fence = SimpleNamespace(retain=False)
    state = {k: {} for k in ["new_wheel", "old_wheel", "manifest", "proof"]}
    state.update(
        previous=upgrade.PREVIOUS,
        target="a" * 40,
        config={"private_origin": "https://fixture.tail.ts.net"},
    )
    monkeypatch.setattr(upgrade, "verify_serve", lambda _origin: None)
    monkeypatch.setattr(upgrade.g, "write_upgrade_journal", lambda _p, _s: None)
    monkeypatch.setattr(
        upgrade, "verify_private_fence", lambda _origin: (_ for _ in ()).throw(SystemExit("crash"))
    )
    monkeypatch.setattr(
        upgrade.c, "atomic", lambda _p, _s: pytest.fail("primary must not be written")
    )
    with pytest.raises(SystemExit):
        ops.checkpoint(state, "prepared")
    assert ops.fence.retain is True


def test_actual_gateway_health_field_is_used(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.research_web.multiuser.accounts import AccountStore
    from app.research_web.multiuser.gateway import create_gateway

    class Pool:
        deployment_path = tmp_path / "deployment.json"

        async def health(self):
            return {"status": "ready", "revision": "a" * 40, "primary_last_verified": True}

        async def close(self):
            pass

    Pool.deployment_path.write_text("{}")
    app = create_gateway(AccountStore(tmp_path / "accounts"), Pool(), origin="http://localhost")
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/server/health").json()
        assert client.get("/").status_code == 503
    assert response["deployment_fenced"] is True and "resident_fenced" not in response
    ops = upgrade.Operations.__new__(upgrade.Operations)
    ops.home = tmp_path
    ops.server = tmp_path / "server"
    ops.server.mkdir()
    (ops.server / "resident.json").write_text("{}")
    ops.state = {
        "target": "a" * 40,
        "config": {"private_origin": "http://localhost", "web_port": 8088},
        "before": {},
        "model_before": {"provider": "fixture", "model": "fixture", "credential_configured": False},
    }
    monkeypatch.setattr(upgrade.g, "verify_primary", lambda *_a, **_k: None)
    monkeypatch.setattr(upgrade.g, "health", lambda *_a, **_k: None)
    monkeypatch.setattr(upgrade.g, "preserved", lambda *_: None)
    monkeypatch.setattr(upgrade, "model_metadata", lambda _config: ops.state["model_before"])
    monkeypatch.setattr(
        upgrade,
        "request_json",
        lambda url: (
            {"items": [{"active": True, **ops.state["model_before"]}]}
            if url.endswith("/model-profiles")
            else response
        ),
    )
    ops.verify(False)


@pytest.mark.parametrize("profile", [upgrade.MODE, *ASSET_PROFILES])
def test_immutable_old_controller_cannot_clear_primary_journal_under_gateway_fence(
    tmp_path, monkeypatch, profile
):
    """Execute the actual installed controller module, not the mutable new source."""
    import contextlib
    import hashlib
    import importlib.machinery
    import importlib.util
    import urllib.error

    import app.research_web.service_manager as manager_module

    previous = upgrade.previous_for(profile)
    fixture = (
        Path(__file__).parents[1]
        / "fixtures/research_web/model_provider_original_controller.py.txt"
    )
    raw = fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == upgrade.CONTROLLER_MODULE_SHA256
    loader = importlib.machinery.SourceFileLoader(
        "research_workbench_entrypoint.resident.original_controller_fixture", str(fixture)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    original = importlib.util.module_from_spec(spec)
    loader.exec_module(original)
    home = tmp_path.resolve()
    root = home / "resident"
    root.mkdir(mode=0o700)
    project = home / "project"
    for p in [root / "artifacts", home / "install", home / "server/run", project]:
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
    wheel = root / "artifacts/old.whl"
    wheel.write_bytes(b"fixture")
    record = {
        "previous": previous,
        "target": "b" * 40,
        "manifest": {"status": "installed", "code_commit": "b" * 40},
        "new_wheel": {"path": str(wheel), "sha256": original.digest(wheel)},
        "old_wheel": {"path": str(wheel), "sha256": original.digest(wheel)},
    }
    original.atomic(root / "transaction.json", record)
    original.atomic(home / "server/run/gateway-upgrade.json", {"version": 4, "mode": profile})
    code = {"revision": "b" * 40}
    events = []

    class Manager:
        def __init__(self, **_kwargs):
            pass

        def _installation_start_scope(self):
            return contextlib.nullcontext(object())

        def _stop_locked(self):
            events.append("old-stop-primary")

        def _start_installed(self, *_args, **_kwargs):
            events.append("old-start-primary")

        def status(self):
            return {
                "services": {
                    "web": {"running": True, "healthy": True, "port": 8088},
                    "runtime": {"running": True, "healthy": True, "port": 3081},
                }
            }

    def git(_project, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return code["revision"]
        if args[:2] == ("switch", "--detach"):
            code["revision"] = args[2]
            return ""
        pytest.fail("unexpected frozen Git call")

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, *_):
            return b"<html>actual local primary fixture</html>"

    class Opener:
        def open(self, url, **_kwargs):
            if url.startswith("https://fixture.tail.ts.net"):
                assert (home / "server/run/gateway-upgrade.json").exists()
                raise urllib.error.HTTPError(url, 503, "server_maintenance", {}, None)
            return Response()

    monkeypatch.setattr(manager_module, "WebServiceManager", Manager)
    monkeypatch.setattr(
        original,
        "configured",
        lambda _h: (
            root,
            {
                "project": str(project),
                "web_port": 8088,
                "runtime_port": 3081,
                "node": "/node",
                "private_origin": "https://fixture.tail.ts.net",
            },
        ),
    )
    monkeypatch.setattr(original, "environment", lambda *_: None)
    monkeypatch.setattr(original, "git", git)
    monkeypatch.setattr(original, "clean", lambda *_: None)
    monkeypatch.setattr(original, "run", lambda *_a, **_k: None)
    monkeypatch.setattr(original, "fixed_ports", lambda *_: contextlib.nullcontext())
    monkeypatch.setattr(upgrade.urllib.request, "build_opener", lambda *_: Opener())
    monkeypatch.setenv("RESEARCH_RESIDENT_REVISION", "test-sentinel")
    with pytest.raises(urllib.error.HTTPError):
        original.bridge_main(home, "recover")
    assert code["revision"] == previous
    assert events == ["old-stop-primary", "old-start-primary"]
    assert (root / "transaction.json").exists()
    assert (home / "server/run/gateway-upgrade.json").exists()
    # The new recovery accepts the known previous primary and still restores both roles.
    recovery = Operations()
    assert (
        upgrade.execute(recovery, {"phase": "start_gateway"}, recovering=True)["status"]
        == "rolled_back"
    )


@pytest.mark.parametrize("bad", ["redirect", "primary-html", "network", "wrong-status"])
def test_private_root_must_really_be_fenced_without_redirect(monkeypatch, bad):
    import urllib.error

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class Opener:
        def open(self, *_a, **_k):
            if bad == "network":
                raise urllib.error.URLError("synthetic")
            if bad != "primary-html":
                raise urllib.error.HTTPError(
                    "https://fixture/", 301 if bad == "redirect" else 502, "synthetic", {}, None
                )
            return Response()

    monkeypatch.setattr(upgrade.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises((upgrade.UpdateBlocked, urllib.error.URLError)):
        upgrade.verify_private_fence("https://fixture")


def test_private_fence_accepts_only_503(monkeypatch):
    import urllib.error

    class Opener:
        def open(self, *_a, **_k):
            raise urllib.error.HTTPError("https://fixture/", 503, "synthetic", {}, None)

    monkeypatch.setattr(upgrade.urllib.request, "build_opener", lambda *_: Opener())
    upgrade.verify_private_fence("https://fixture")


@pytest.fixture
def real_operations(tmp_path, monkeypatch, request):
    """Run real journals, reservations, configuration and operation methods; fake OS effects."""
    import hashlib

    import app.research_web.multiuser.resident_binding as binding_module

    mode = getattr(request, "param", upgrade.MODE)
    previous = upgrade.previous_for(mode)
    home = tmp_path.resolve()
    root, server = home / "resident", home / "server"
    primary, gateway = home / "primary", home / "gateway"
    for p in (root, server, primary, gateway, home / "research-web"):
        p.mkdir(mode=0o700)
    (server / "run").mkdir(mode=0o700)
    (server / "users").mkdir(mode=0o700)
    uid = str(uuid4())
    for p in (server / "users" / uid, server / "users" / uid / "state"):
        p.mkdir(mode=0o700)
    with sqlite3.connect(server / "accounts.sqlite3") as db:
        db.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY)")
        db.execute("INSERT INTO accounts VALUES (?)", (uid,))
    (server / "accounts.sqlite3").chmod(0o600)
    upgrade.c.atomic(home / "research-web/index.json", {"automation_runs": {}})
    body = home / "research-web/keep.txt"
    body.write_bytes(b"private fixture remains intact")
    expected_body = hashlib.sha256(body.read_bytes()).hexdigest()
    config = {
        "project": str(primary),
        "baseline": "known",
        "web_port": 8088,
        "runtime_port": 3081,
        "node": "/node",
        "private_origin": "https://fixture.tail.ts.net",
        "source_common": str(home / ".git"),
    }
    binding = {
        "primary_user_id": uid,
        "home": str(home),
        "project": str(primary),
        "revision": previous,
        "web_port": 8088,
        "runtime_port": 3081,
        "project_identity": [1, 2],
        "data_identity": [3, 4],
    }
    gw = {
        "project": str(gateway),
        "revision": previous,
        "binding": binding,
        "origin": config["private_origin"],
    }
    manifest = {"code_commit": previous, "status": "installed", "web_lock_sha256": "c" * 64}
    accepted = {"target": previous, "sentinel": "previous-accepted"}
    for path, value in (
        (root / "config.json", config),
        (server / "resident.json", gw),
        (home / "install/manifest.json", manifest),
        (root / "accepted.json", accepted),
        (root / "candidate.json", accepted),
    ):
        upgrade.c.atomic(path, value)
    plist = home / "gateway.plist"
    plist.write_bytes(plistlib.dumps({"ProgramArguments": ["/python"]}))
    wheel = root / "old.whl"
    wheel.write_bytes(b"fixture wheel")
    state = {
        "version": 4,
        "mode": mode,
        "phase": "prepared",
        "transaction": str(uuid4()),
        "previous": previous,
        "target": "b" * 40,
        "primary_project": str(primary),
        "gateway_project": str(gateway),
        "config": config,
        "gateway_config": gw,
        "gateway_plist": str(plist),
        "gateway_plist_sha256": upgrade.c.digest(plist),
        "gateway_command": "/python -m gateway",
        "manifest": manifest,
        "accepted": accepted,
        "candidate_before": accepted,
        "before": {"body": expected_body},
        "new_wheel": {"path": str(wheel), "sha256": upgrade.c.digest(wheel)},
        "old_wheel": {"path": str(wheel), "sha256": upgrade.c.digest(wheel)},
        "proof": {"qualified": True},
        "reviewed": {"fixture": "blob"},
    }
    state["model_before"] = {
        "provider": "deepseek-official",
        "model": "deepseek-flash",
        "credential_configured": True,
        "credential_storage": "system_keychain",
    }
    if mode in upgrade.ASSET_MODES:
        state["asset_index_before"] = upgrade.asset_index_snapshot(home)
    system = {
        "primary": previous,
        "gateway": previous,
        "running": True,
        "loaded": True,
        "pid": 900001,
        "active": False,
        "fail": None,
        "failed": False,
        "events": [],
    }

    def job():
        return (
            f"path = {plist}\nprogram = /python\nworking directory = {gateway}\n"
            if system["loaded"]
            else None
        )

    monkeypatch.setattr(upgrade.g, "job_state", job)
    monkeypatch.setattr(upgrade.g, "job_pid", lambda: system["pid"] if system["loaded"] else None)
    monkeypatch.setattr(
        upgrade.g,
        "listener_pids",
        lambda: {system["pid"]} if system["loaded"] and system["pid"] else set(),
    )
    monkeypatch.setattr(
        upgrade.g, "process", lambda _pid: "Wed Oct 21 10:00:00 2026 /python -m gateway"
    )
    monkeypatch.setattr(upgrade.g, "native_image", lambda _pid: Path("/python"))
    monkeypatch.setattr(upgrade.g, "no_children", lambda _pid: None)
    monkeypatch.setattr(upgrade.g, "no_private_processes", lambda _root: None)

    def drain(*_args):
        assert (server / "run/gateway-upgrade.json").exists()
        system["events"].append("SIGTERM")
        system["pid"] = None

    monkeypatch.setattr(upgrade.g, "graceful_drain", drain)
    monkeypatch.setattr(
        upgrade.g, "bootout_after_drain", lambda _p: system.update(loaded=False, pid=None)
    )
    monkeypatch.setattr(upgrade.g, "bootstrap", lambda _p: system.update(loaded=True, pid=900002))

    def git(project, *args):
        role = "primary" if Path(project) == primary else "gateway"
        if args == ("rev-parse", "HEAD"):
            return system[role]
        if args[:2] == ("switch", "--detach"):
            assert not system["loaded"] and not system["running"]
            system[role] = args[2]
            return ""
        pytest.fail("unexpected fixture Git operation")

    monkeypatch.setattr(upgrade.c, "git", git)
    monkeypatch.setattr(
        upgrade.c,
        "clean",
        lambda project, sha: (
            None if git(project, "rev-parse", "HEAD") == sha else pytest.fail("dirty source")
        ),
    )

    def install(*_args, **_kwargs):
        assert not system["loaded"] and not system["running"]
        system["events"].append("pip-no-deps")

    monkeypatch.setattr(upgrade.c, "run", install)
    monkeypatch.setattr(upgrade, "verify_serve", lambda _origin: None)
    monkeypatch.setattr(
        upgrade,
        "verify_private_fence",
        lambda _origin: (
            None
            if (server / "run/gateway-upgrade.json").exists()
            else pytest.fail("no global fence")
        ),
    )
    monkeypatch.setattr(upgrade, "ports_are_free", lambda _ports: True)
    import contextlib

    monkeypatch.setattr(upgrade.c, "fixed_ports", lambda *_args: contextlib.nullcontext())

    def health(value, *, fenced):
        assert system["loaded"] and value["revision"] == system["gateway"]
        assert fenced is True and (server / "run/gateway-upgrade.json").exists()

    monkeypatch.setattr(upgrade.g, "health", health)
    monkeypatch.setattr(upgrade.g, "wait_health", health)

    def verify_primary(_home, sha, **kwargs):
        assert system["running"] and system["primary"] == sha and not system["active"]

    monkeypatch.setattr(upgrade.g, "verify_primary", verify_primary)
    monkeypatch.setattr(
        upgrade.g,
        "preserved",
        lambda *_args: (
            None
            if hashlib.sha256(body.read_bytes()).hexdigest() == expected_body
            else pytest.fail("data changed")
        ),
    )

    def request(url):
        if url.endswith("/api/research/market"):
            return {"inflight": []}
        if url.endswith("/api/research/runtime"):
            return {"connected": True, "health_check_passed": True, **state["model_before"]}
        if url.endswith("/api/research/model-profiles"):
            return {"items": [{"active": True, **state["model_before"]}]}
        if url.endswith("/api/server/health"):
            return {
                "revision": system["gateway"],
                "deployment_fenced": (server / "run/gateway-upgrade.json").exists(),
            }
        return {"enabled": True, "revision": system["primary"], "active": system["active"]}

    monkeypatch.setattr(upgrade, "request_json", request)
    fake_binding = SimpleNamespace(
        verify=lambda: {"revision": system["primary"]},
        public_config=lambda: {
            **binding,
            "revision": system["primary"],
            "project_identity": tuple(binding["project_identity"]),
            "data_identity": tuple(binding["data_identity"]),
        },
    )
    monkeypatch.setattr(
        binding_module.LegacyBinding, "discover", classmethod(lambda *_args: fake_binding)
    )

    class Manager:
        def status(self):
            return {
                "services": {
                    role: {"running": system["running"], "healthy": system["running"]}
                    for role in ("web", "runtime")
                }
            }

        def _service_probes(self):
            return [SimpleNamespace(role="runtime")]

        def _active_research_read_only(self, _runtime):
            return system["active"] is not False

        def _stop_locked(self):
            assert not system["active"] and (root / "transaction.json").exists()
            system["running"] = False

        def _start_installed(self, *_args, **_kwargs):
            assert (root / "transaction.json").exists()
            system["running"] = True

    class CheckedOperations(upgrade.Operations):
        def action(self, name, record):
            assert record["phase"] == name
            super().action(name, record)
            if system["fail"] == name and not system["failed"]:
                system["failed"] = True
                raise RuntimeError("synthetic after-effect failure")

    config["repository"] = "fixture"
    upgrade.c.atomic(root / "config.json", config)
    for role in ("primary", "gateway"):
        state[role + "_repository"] = {"common": str(home / role / ".git"), "identity": [1, 2]}
    monkeypatch.setattr(
        upgrade,
        "repository_identity",
        lambda project, _repository: state[
            ("primary" if project == primary else "gateway") + "_repository"
        ],
    )
    monkeypatch.setenv("RESEARCH_RESIDENT_REVISION", "test-sentinel")
    return (
        home,
        state,
        system,
        lambda fence: CheckedOperations(home, state, Manager(), object(), fence),
        uid,
    )


@pytest.mark.parametrize("failed", [None, *upgrade.FORWARD])
def test_real_operation_methods_converge_and_preserve_data(real_operations, failed):
    home, state, system, make, uid = real_operations
    system["fail"] = failed
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        result = upgrade.execute(make(fence), state)
    expected = state["target"] if failed is None else upgrade.PREVIOUS
    assert result["status"] == ("deployed" if failed is None else "rolled_back")
    assert system["primary"] == system["gateway"] == expected
    assert system["running"] and system["loaded"]
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()
    assert not (home / "server/run/birth-fence.json").exists()
    assert json.loads((home / "install/manifest.json").read_text())["code_commit"] == expected


@pytest.mark.parametrize("real_operations", ASSET_PROFILES, indirect=True)
@pytest.mark.parametrize("failed", [None, *upgrade.FORWARD])
def test_asset_operation_methods_restore_the_asset_previous(real_operations, failed):
    home, state, system, make, uid = real_operations
    system["fail"] = failed
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        result = upgrade.execute(make(fence), state)
    expected = state["target"] if failed is None else state["previous"]
    assert result["status"] == ("deployed" if failed is None else "rolled_back")
    assert system["primary"] == system["gateway"] == expected
    expected_manifest = {**state["manifest"], "code_commit": expected}
    if failed is None and state["mode"] in {
        upgrade.ASSET_V5_MODE,
        upgrade.ASSET_V6_MODE,
        upgrade.ASSET_V7_MODE,
        upgrade.MARKET_HISTORY_MODE,
        upgrade.MARKET_TERMINAL_MODE,
    }:
        expected_manifest["web_lock_sha256"] = (
            "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
        )
    assert json.loads((home / "install/manifest.json").read_text()) == expected_manifest
    assert system["running"] and system["loaded"]
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()
    assert not (home / "server/run/birth-fence.json").exists()
    if failed is None:
        assert (
            upgrade.read_json(home / "resident/accepted.json")["compatibility_review"]["profile"]
            == state["mode"]
        )


@pytest.mark.parametrize("real_operations", ASSET_PROFILES, indirect=True)
@pytest.mark.parametrize("phase", [*upgrade.FORWARD, *upgrade.BACKWARD])
def test_asset_interrupted_phase_recovers_the_known_asset_previous(real_operations, phase):
    home, state, system, make, uid = real_operations
    state["phase"] = phase
    system["primary"] = system["gateway"] = state["target"]
    upgrade.g.write_upgrade_journal(home / "server/run/gateway-upgrade.json", state)
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        result = upgrade.execute(make(fence), state, recovering=True)
    assert result["status"] == "rolled_back"
    assert system["primary"] == system["gateway"] == state["previous"]
    assert not (home / "server/run/gateway-upgrade.json").exists()


@pytest.mark.parametrize("real_operations", ASSET_PROFILES, indirect=True)
def test_asset_query_running_prevents_any_switch(real_operations):
    home, state, system, make, _uid = real_operations
    upgrade.c.atomic(
        home / "research-web/index.json",
        {"automation_runs": {}, "asset_observations": {"fixture": {"status": "running"}}},
    )
    assert upgrade.execute(make(None), state)["status"] == "deferred"
    assert system["events"] == []
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()


@pytest.mark.parametrize("real_operations", ASSET_PROFILES, indirect=True)
@pytest.mark.parametrize("boundary", ["verify_target", "finish"])
def test_asset_index_loss_keeps_recovery_fenced_and_never_claims_preservation(
    real_operations, boundary
):
    home, state, _system, make, uid = real_operations
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        ops = make(fence)
        original_action, original_finish = ops.action, ops.finish

        def action(name, value):
            if name == boundary:
                upgrade.c.atomic(home / "research-web/index.json", {})
            return original_action(name, value)

        def finish(value, result):
            if boundary == "finish":
                upgrade.c.atomic(home / "research-web/index.json", {})
            return original_finish(value, result)

        ops.action, ops.finish = action, finish
        result = upgrade.execute(ops, state)
    assert result["status"] in {"recovery_required", "completion_unknown"}
    assert result.get("preserved") is not True
    assert (home / "server/run/gateway-upgrade.json").exists()
    assert not (home / "server/run/model-upgrade-result.json").exists()
    assert upgrade.read_json(home / "research-web/index.json") == {}


@pytest.mark.parametrize("profile", ASSET_PROFILES)
@pytest.mark.parametrize(
    "value",
    [None, {}, {"primary": {}, "private": []}, {"primary": {"notes": "raw"}, "private": {}}],
)
def test_asset_recovery_requires_valid_frozen_index_digests(value, profile):
    with pytest.raises(upgrade.UpdateBlocked, match="snapshot_invalid"):
        upgrade.validate_asset_snapshot({"mode": profile, "asset_index_before": value})


def test_real_activity_in_gateway_only_window_blocks_all_effects(real_operations):
    home, state, system, make, _uid = real_operations
    upgrade.g.write_upgrade_journal(home / "server/run/gateway-upgrade.json", state)
    system["active"] = True
    result = upgrade.execute(make(None), state, recovering=True)
    assert result["status"] == "recovery_required"
    assert system["events"] == []
    assert not (home / "resident/transaction.json").exists()
    assert (home / "server/run/gateway-upgrade.json").exists()


def test_release_repositories_may_be_independent_of_qualified_source(tmp_path):
    import subprocess

    projects = {}
    for role in ("source", "primary", "gateway"):
        project = tmp_path / role
        subprocess.run(["/usr/bin/git", "init", str(project)], check=True, capture_output=True)
        subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(project),
                "remote",
                "add",
                "origin",
                "git@github.com:Leon-Huang001208/ResearchWorkbench.git",
            ],
            check=True,
        )
        projects[role] = project.resolve()
    state = {
        "config": {
            "repository": "Leon-Huang001208/ResearchWorkbench",
            "source_common": str(projects["source"] / ".git"),
        }
    }
    for role in ("primary", "gateway"):
        state[role + "_project"] = str(projects[role])
        state[role + "_repository"] = upgrade.repository_identity(
            projects[role], state["config"]["repository"]
        )
        upgrade.verify_release_repository(state, role)
    assert state["primary_repository"] != state["gateway_repository"]
    subprocess.run(
        [
            "/usr/bin/git",
            "-C",
            str(projects["primary"]),
            "remote",
            "set-url",
            "origin",
            "https://example.invalid/unknown.git",
        ],
        check=True,
    )
    with pytest.raises(upgrade.UpdateBlocked, match="repository"):
        upgrade.verify_release_repository(state, "primary")


@pytest.mark.parametrize("changed", ["common", "inode"])
def test_release_repository_replacement_is_rejected(tmp_path, monkeypatch, changed):
    saved = {"common": str(tmp_path / ".git"), "identity": [1, 2]}
    actual = {**saved, changed: str(tmp_path / "other") if changed == "common" else [1, 3]}
    if changed == "inode":
        actual = {"common": saved["common"], "identity": [1, 3]}
    monkeypatch.setattr(upgrade, "repository_identity", lambda *_: actual)
    state = {
        "config": {"repository": "fixture"},
        "primary_project": str(tmp_path),
        "primary_repository": saved,
    }
    with pytest.raises(upgrade.UpdateBlocked, match="repository"):
        upgrade.verify_release_repository(state, "primary")


@pytest.mark.parametrize("profile", [upgrade.MODE, *ASSET_PROFILES])
def test_validate_state_accepts_real_independent_release_clones(tmp_path, monkeypatch, profile):
    import hashlib
    import subprocess
    import zipfile

    home = tmp_path.resolve()
    authority = home / "authority"

    def git(project, *args):
        return subprocess.check_output(
            ["/usr/bin/git", "-C", str(project), *args], text=True
        ).strip()

    subprocess.run(["/usr/bin/git", "init", str(authority)], check=True, capture_output=True)
    git(
        authority,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "fixture",
    )
    target = git(authority, "rev-parse", "HEAD")
    previous_name = {
        upgrade.MODE: "PREVIOUS",
        upgrade.ASSET_MODE: "ASSET_PREVIOUS",
        upgrade.ASSET_V2_MODE: "ASSET_V2_PREVIOUS",
        upgrade.ASSET_V3_MODE: "ASSET_V3_PREVIOUS",
        upgrade.ASSET_V4_MODE: "ASSET_V4_PREVIOUS",
        upgrade.ASSET_V5_MODE: "ASSET_V5_PREVIOUS",
        upgrade.ASSET_V6_MODE: "ASSET_V6_PREVIOUS",
        upgrade.ASSET_V7_MODE: "ASSET_V7_PREVIOUS",
        "reviewed-market-overview-v1": "MARKET_PREVIOUS",
        "reviewed-market-gaps-v1": "MARKET_GAPS_PREVIOUS",
        "reviewed-market-history-v1": "MARKET_HISTORY_PREVIOUS",
        "reviewed-market-terminal-v1": "MARKET_TERMINAL_PREVIOUS",
        "reviewed-etf-weekly-v1": "ETF_WEEKLY_PREVIOUS",
        "reviewed-research-dossiers-v1": "DOSSIERS_PREVIOUS",
        "reviewed-discovery-v1": "DISCOVERY_PREVIOUS",
        "reviewed-etf-weekly-v2": "ETF_WEEKLY_V2_PREVIOUS",
        "reviewed-etf-historical-v1": "ETF_HISTORICAL_PREVIOUS",
    }[profile]
    monkeypatch.setattr(upgrade, previous_name, target)
    upgrade.g.private_root(home / "resident")
    source = home / "resident/artifacts" / target / "source"
    source.parent.mkdir(parents=True)
    git(authority, "worktree", "add", "--detach", str(source), target)
    config = {
        "repository": "Leon-Huang001208/ResearchWorkbench",
        "source_common": str(authority / ".git"),
        "baseline": target,
    }
    state = {
        "version": 4,
        "mode": profile,
        "phase": "prepared",
        "previous": target,
        "target": target,
        "transaction": str(uuid4()),
        "source": str(source),
        "config": config,
        "reviewed": {},
        "supervisor_plist_sha256": "fixture",
        "model_before": {
            "provider": "fixture",
            "model": "fixture",
            "credential_configured": True,
            "credential_storage": "fixture",
        },
    }
    for role in ("primary", "gateway"):
        project = home / role
        subprocess.run(
            ["/usr/bin/git", "clone", "--no-hardlinks", str(authority), str(project)],
            check=True,
            capture_output=True,
        )
        git(
            project,
            "remote",
            "set-url",
            "origin",
            "git@github.com:Leon-Huang001208/ResearchWorkbench.git",
        )
        state[role + "_project"] = str(project)
        info = project.stat()
        state[role + "_identity"] = [info.st_dev, info.st_ino]
        state[role + "_repository"] = upgrade.repository_identity(project, config["repository"])
    config["project"] = state["primary_project"]
    state["gateway_config"] = {
        "project": state["gateway_project"],
        "revision": target,
        "binding": {},
    }
    state["manifest"] = {"code_commit": target}
    if profile in upgrade.ASSET_MODES:
        upgrade.g.private_root(home / "server")
        upgrade.g.private_root(home / "server/users")
        upgrade.c.atomic(home / "research-web/index.json", {"notes": {}})
        state["asset_index_before"] = upgrade.asset_index_snapshot(home)
    for path, value in [
        (home / "resident/config.json", config),
        (home / "server/resident.json", state["gateway_config"]),
        (home / "install/manifest.json", state["manifest"]),
    ]:
        upgrade.c.atomic(path, value)
    controller = home / "resident/controller.pyz"
    controller.write_bytes(b"fixture controller")
    checksum = hashlib.sha256(controller.read_bytes()).hexdigest()
    monkeypatch.setattr(upgrade, "CONTROLLER_SHA256", checksum)
    state["controller_sha256"] = checksum
    monkeypatch.setattr(upgrade, "verify_supervisor", lambda *_: "fixture")
    monkeypatch.setattr(upgrade, "validate_executor", lambda *_: None)
    monkeypatch.setattr(upgrade, "review", lambda *_: {})
    monkeypatch.setattr(upgrade.g, "module_blobs", lambda *_: {})
    artifact = home / "server/run/recovery.pyz"
    artifact.parent.mkdir(parents=True)
    with zipfile.ZipFile(artifact, "w") as archive:
        manifest = {"target": target, "modules": {}}
        if profile in {
            "reviewed-research-dossiers-v1",
            "reviewed-discovery-v1",
            "reviewed-etf-weekly-v2",
            "reviewed-etf-historical-v1",
        }:
            manifest["source"] = str(source)
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("__main__.py", upgrade.ENTRY)
    artifact.chmod(0o600)
    plist = home / "recovery.plist"
    plist.write_bytes(b"fixture plist")
    state["recovery"] = {
        "artifact": str(artifact),
        "sha256": upgrade.c.digest(artifact),
        "modules": {},
        "plist": str(plist),
        "plist_sha256": upgrade.c.digest(plist),
    }
    state["gateway_plist"] = str(plist)
    state["gateway_plist_sha256"] = upgrade.c.digest(plist)
    wheel = source.parent / "fixture.whl"
    wheel.write_bytes(b"fixture wheel")
    state["old_wheel"] = state["new_wheel"] = {
        "path": str(wheel),
        "sha256": upgrade.c.digest(wheel),
    }
    upgrade.validate_state(home, state)
    if profile in {
        "reviewed-research-dossiers-v1",
        "reviewed-discovery-v1",
        "reviewed-etf-weekly-v2",
        "reviewed-etf-historical-v1",
    }:
        original_archive = artifact.read_bytes()
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"target": target, "modules": {}}))
            archive.writestr("__main__.py", upgrade.ENTRY)
        state["recovery"]["sha256"] = upgrade.c.digest(artifact)
        with pytest.raises(upgrade.UpdateBlocked, match="artifact_changed"):
            upgrade.validate_state(home, state)
        artifact.write_bytes(original_archive)
        state["recovery"]["sha256"] = upgrade.c.digest(artifact)
        upgrade.validate_state(home, state)
    # Preserve path and origin but replace the real Git directory inode.
    import shutil

    common = Path(state["primary_repository"]["common"])
    retired = home / "retired-primary-git"
    common.rename(retired)
    shutil.copytree(retired, common)
    with pytest.raises(upgrade.UpdateBlocked, match="repository_changed"):
        upgrade.validate_state(home, state)


@pytest.mark.parametrize("real_operations", [upgrade.MODE, *ASSET_PROFILES], indirect=True)
@pytest.mark.parametrize("crash_after", upgrade.FORWARD)
def test_new_recovery_resumes_real_reservations_after_each_interruption(
    real_operations, crash_after
):
    home, state, system, make, uid = real_operations
    with (
        pytest.raises(SystemExit),
        BirthFence(home / "server", uid, transaction=state["transaction"]) as fence,
    ):
        ops = make(fence)
        original = ops.action

        def crash(name, record):
            original(name, record)
            if name == crash_after:
                raise SystemExit("synthetic process interruption")

        ops.action = crash
        upgrade.execute(ops, state)
    saved = upgrade.g.read_upgrade_journal(home / "server/run/gateway-upgrade.json")
    resume = (home / "server/run/birth-fence.json").exists()
    with BirthFence(home / "server", uid, resume=resume, transaction=saved["transaction"]) as fence:
        ops = make(fence)
        ops.state = saved
        result = upgrade.execute(ops, saved, recovering=True)
    assert result["status"] == "rolled_back"
    assert system["primary"] == system["gateway"] == state["previous"]
    assert system["running"] and system["loaded"]
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()


@pytest.mark.parametrize("name", ["config", "gateway", "manifest", "journal"])
def test_unknown_configuration_never_gets_overwritten(real_operations, name):
    home, state, _system, _make, _uid = real_operations
    paths = {
        "config": home / "resident/config.json",
        "gateway": home / "server/resident.json",
        "manifest": home / "install/manifest.json",
        "journal": home / "resident/transaction.json",
    }
    p = paths[name]
    upgrade.c.atomic(p, {"foreign": "preserve this record"})
    raw = p.read_bytes()
    with pytest.raises(upgrade.UpdateBlocked):
        upgrade.validate_configuration(home, state)
    assert p.read_bytes() == raw


@pytest.mark.parametrize(
    "configured,storage,accepted",
    [
        (True, "system_keychain", True),
        (False, "system_keychain", True),
        (None, "not_required", True),
        (None, "unknown", False),
    ],
)
def test_model_metadata_never_resolves_or_logs_key_values(
    monkeypatch, configured, storage, accepted
):
    response = {
        "connected": True,
        "health_check_passed": True,
        "provider": "deepseek-official",
        "model": "deepseek-flash",
        "credential_configured": configured,
        "credential_storage": storage,
        "ignored": "not retained",
    }
    monkeypatch.setattr(upgrade, "request_json", lambda _u: response)
    if accepted:
        assert set(upgrade.model_metadata({"web_port": 8088})) == {
            "provider",
            "model",
            "credential_configured",
            "credential_storage",
        }
    else:
        with pytest.raises(MaintenanceBusy):
            upgrade.model_metadata({"web_port": 8088})


@pytest.mark.parametrize("changed", ["root", "extra-api", "funnel", "tls"])
def test_serve_changes_cannot_bypass_private_root_gate(monkeypatch, changed):
    value = {
        "Web": {
            "fixture.tail.ts.net:443": {
                "Handlers": {
                    "/": {"Proxy": "http://127.0.0.1:8089"},
                    "/collections": {"Proxy": "http://127.0.0.1:8769"},
                }
            }
        },
        "TCP": {"443": {"HTTPS": True}},
    }
    if changed == "root":
        value["Web"]["fixture.tail.ts.net:443"]["Handlers"]["/"]["Proxy"] = "http://127.0.0.1:8088"
    if changed == "extra-api":
        value["Web"]["fixture.tail.ts.net:443"]["Handlers"]["/api"] = {
            "Proxy": "http://127.0.0.1:8088"
        }
    if changed == "funnel":
        value["AllowFunnel"] = {"fixture.tail.ts.net:443": True}
    if changed == "tls":
        value["TCP"]["443"]["HTTPS"] = False
    monkeypatch.setattr(upgrade.g, "run", lambda _args: json.dumps(value))
    with pytest.raises(upgrade.UpdateBlocked, match="private_route_unknown"):
        upgrade.verify_serve("https://fixture.tail.ts.net")


def test_existing_collections_route_is_preserved(monkeypatch):
    value = {
        "Web": {
            "fixture.tail.ts.net:443": {
                "Handlers": {
                    "/": {"Proxy": "http://127.0.0.1:8089"},
                    "/collections": {"Proxy": "http://127.0.0.1:8769"},
                }
            }
        },
        "TCP": {"443": {"HTTPS": True}},
    }
    original = json.dumps(value, sort_keys=True)
    monkeypatch.setattr(upgrade.g, "run", lambda _args: json.dumps(value))
    upgrade.verify_serve("https://fixture.tail.ts.net")
    assert json.dumps(value, sort_keys=True) == original


def test_retention_cannot_purge_existing_deleted_history_during_deployment(tmp_path):
    import time

    upgrade.c.atomic(
        tmp_path / "research-web/index.json",
        {"sessions": {"fixture": {"deleted_at": time.time() - 31 * 86400}}},
    )
    with pytest.raises(upgrade.UpdateBlocked, match="retention_due"):
        upgrade.verify_retention(tmp_path)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "ui",
        "mode",
        "backend",
        "dependency",
        "extra_ui",
        "ancestry",
        "reverted",
        "all_reverted",
    ],
)
def test_navigation_payload_is_exact_and_does_not_expand_backend_scope(monkeypatch, tmp_path, bad):
    """The deployed navigation is a frozen product, not a general UI allowance."""
    target = "f" * 40
    navigation = "4e8be6ac7405733755e4a00be10898504e71710a"
    ui = {
        f"app/research_web/ui/{name}.mjs" for name in ("app", "core", "intel", "shell", "workbench")
    }
    paths = {upgrade.MODULE, upgrade.TEST, "app/research_web/service.py", *ui}
    if bad == "dependency":
        paths.add("requirements/web.lock")
    if bad == "extra_ui":
        paths.add("app/research_web/ui/unreviewed.mjs")
    reverted = (
        ui
        if bad == "all_reverted"
        else {"app/research_web/ui/app.mjs"} if bad == "reverted" else set()
    )
    paths.difference_update(reverted)
    calls = []
    monkeypatch.setattr(upgrade.c, "clean", lambda *_: None)

    def git(_root, *args):
        calls.append(args)
        if args[0] == "merge-base":
            if bad == "ancestry" and navigation in args:
                raise upgrade.UpdateBlocked("resident_git_failed")
            return ""
        if args[0] == "diff":
            return "\n".join(sorted(paths))
        if args[0] == "rev-parse":
            revision, name = args[-1].split(":", 1)
            if name in ui:
                if revision == target and name in reverted:
                    return "a" * 40
                if bad == "ui" and revision == target:
                    return "c" * 40
                return ("b" if revision in (target, navigation) else "a") * 40
            if revision == target and (
                bad == "backend"
                and name == "app/research_web/service.py"
                or bad == "dependency"
                and name == "requirements/web.lock"
                or bad == "extra_ui"
                and name.endswith("unreviewed.mjs")
            ):
                return "b" * 40
            return "a" * 40
        if args[0] == "ls-tree":
            mode = "100755" if bad == "mode" and args[1] == target and args[-1] in ui else "100644"
            return f"{mode} blob {'a' * 40}\t{args[-1]}"
        pytest.fail("unexpected payload review query")

    monkeypatch.setattr(upgrade.c, "git", git)
    if bad is not None:
        with pytest.raises(upgrade.UpdateBlocked):
            upgrade.review(tmp_path, target)
    else:
        result = upgrade.review(tmp_path, target)
        assert set(result) == paths
        assert all(result[name] == "b" * 40 for name in ui)
        assert ("merge-base", "--is-ancestor", navigation, target) in calls


@pytest.mark.parametrize("bad", ["dependency", "payload", "mode", "workflow"])
def test_exact_profile_rejects_unreviewed_business_or_installation_changes(
    monkeypatch, tmp_path, bad
):
    monkeypatch.setattr(upgrade.c, "clean", lambda *_: None)
    path = (
        "requirements/web.lock"
        if bad == "dependency"
        else ("app/research_web/service.py" if bad in ["payload", "mode"] else upgrade.WORKFLOW)
    )

    def git(_root, *args):
        if args[0] == "merge-base":
            return ""
        if args[0] == "diff":
            return f"{upgrade.MODULE}\n{upgrade.TEST}\n{path}"
        if args[0] == "rev-parse":
            return "b" * 40 if args[-1].startswith("f" * 40) and bad != "mode" else "a" * 40
        if args[0] == "ls-tree":
            return (
                ("100755" if args[1] == "f" * 40 else "100644")
                + " blob "
                + "a" * 40
                + "\t"
                + args[-1]
            )
        if args[0] == "show":
            return (
                "unreviewed"
                if args[-1].startswith("f" * 40)
                else "tests/research_web/test_gateway_upgrade.py"
            )
        pytest.fail("unexpected profile query")

    monkeypatch.setattr(upgrade.c, "git", git)
    with pytest.raises(upgrade.UpdateBlocked):
        upgrade.review(tmp_path, "f" * 40)


@pytest.mark.parametrize(
    "already_registered,limit", [(False, 30), (True, 30), (True, 20), (True, 45)]
)
def test_reviewed_workflow_keeps_one_registered_upgrade_test(
    tmp_path, monkeypatch, already_registered, limit
):
    bare = "timeout-minutes: 20\npython -m pytest tests/research_web/test_gateway_upgrade.py"
    registered = bare + " " + upgrade.TEST
    original = registered if already_registered else bare
    monkeypatch.setattr(upgrade.c, "clean", lambda *_: None)

    def git(_source, *args):
        if args[0] == "merge-base":
            return ""
        if args[0] == "diff":
            return f"{upgrade.MODULE}\n{upgrade.TEST}\n{upgrade.WORKFLOW}"
        if args[0] == "rev-parse":
            return "a" * 40
        if args[0] == "ls-tree":
            return "100644 blob " + "a" * 40 + "\t" + args[-1]
        if args[0] == "show":
            return (
                original
                if args[1].startswith(upgrade.PAYLOAD)
                else registered.replace("timeout-minutes: 20", f"timeout-minutes: {limit}")
            )
        pytest.fail("unexpected review query")

    monkeypatch.setattr(upgrade.c, "git", git)
    if limit == 30:
        assert upgrade.WORKFLOW in upgrade.review(tmp_path, "f" * 40)
    else:
        with pytest.raises(upgrade.UpdateBlocked, match="workflow_scope"):
            upgrade.review(tmp_path, "f" * 40)


@pytest.mark.parametrize("tamper", ["none", "required-rule", "larger-limit"])
def test_reviewed_ci_policy_only_changes_bounded_timeout(tmp_path, monkeypatch, tamper):
    policy = ".agents/project-constraints.json"
    original = '{"required":["same tests","timeout-minutes: 20"],"strict":true}'
    candidate = original.replace("timeout-minutes: 20", "timeout-minutes: 30")
    if tamper == "required-rule":
        candidate = candidate.replace('"strict":true', '"strict":false')
    if tamper == "larger-limit":
        candidate = candidate.replace("timeout-minutes: 30", "timeout-minutes: 45")
    monkeypatch.setattr(upgrade.c, "clean", lambda *_: None)

    def git(_source, *args):
        if args[0] == "merge-base":
            return ""
        if args[0] == "diff":
            return f"{upgrade.MODULE}\n{upgrade.TEST}\n{policy}"
        if args[0] == "rev-parse":
            if args[-1].split(":", 1)[-1] in upgrade.NAVIGATION_FILES:
                return "a" * 40
            return "b" * 40 if args[-1].startswith("f" * 40) else "a" * 40
        if args[0] == "ls-tree":
            return "100644 blob " + "a" * 40 + "\t" + args[-1]
        if args[0] == "show":
            return original if args[-1].startswith(upgrade.PAYLOAD) else candidate
        pytest.fail("unexpected policy query")

    monkeypatch.setattr(upgrade.c, "git", git)
    if tamper == "none":
        assert policy in upgrade.review(tmp_path, "f" * 40)
    else:
        with pytest.raises(upgrade.UpdateBlocked):
            upgrade.review(tmp_path, "f" * 40)


@pytest.mark.parametrize("real_operations", [upgrade.MODE, *ASSET_PROFILES], indirect=True)
@pytest.mark.parametrize(
    "point",
    [
        "accepted",
        "candidate",
        "baseline",
        "config",
        "result",
        "record",
        "root-unlink",
        "root-sync",
        "gate-unlink",
        "gate-sync",
    ],
)
@pytest.mark.parametrize("after", [False, True])
def test_finish_failure_never_signals_again_in_same_stack(
    real_operations, monkeypatch, point, after
):
    home, state, system, make, uid = real_operations
    atomic, unlink, sync, record = (
        upgrade.c.atomic,
        Path.unlink,
        upgrade.c.sync_directory,
        upgrade.c.record,
    )
    fired = False

    def interrupt(operation, effect, *args, **kwargs):
        nonlocal fired
        selected = operation == point and not fired
        if selected and not after:
            fired = True
            raise OSError("fixture finish interruption")
        value = effect(*args, **kwargs)
        if selected:
            fired = True
            raise OSError("fixture finish interruption after effect")
        return value

    def write(path, value):
        names = {
            "accepted.json": "accepted",
            "candidate.json": "candidate",
            "config.json": "config",
            "model-upgrade-result.json": "result",
        }
        kind = "baseline" if path.parent.name == "baseline-reviews" else names.get(path.name)
        return interrupt(kind, atomic, path, value)

    def remove(path, *args, **kwargs):
        kind = (
            "root-unlink"
            if path == home / "resident/transaction.json"
            else ("gate-unlink" if path == home / "server/run/gateway-upgrade.json" else None)
        )
        return interrupt(kind, unlink, path, *args, **kwargs)

    def flush(path):
        # Inject only once source verification and startup have finished.
        final = (home / "server/run/model-upgrade-result.json").exists()
        kind = (
            (
                "root-sync"
                if path == home / "resident"
                else "gate-sync" if path == home / "server/run" else None
            )
            if final
            else None
        )
        return interrupt(kind, sync, path)

    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        ops = make(fence)
        # Patch only finish, to retain real forward method behavior.
        original = ops.finish

        def finish(value, result):
            monkeypatch.setattr(upgrade.c, "atomic", write)
            monkeypatch.setattr(Path, "unlink", remove)
            monkeypatch.setattr(upgrade.c, "sync_directory", flush)
            monkeypatch.setattr(
                upgrade.c, "record", lambda *a, **kw: interrupt("record", record, *a, **kw)
            )
            return original(value, result)

        ops.finish = finish
        result = upgrade.execute(ops, state)
    assert fired and result["status"] == "completion_unknown"
    assert system["events"].count("SIGTERM") == 1
    assert system["primary"] == system["gateway"] == state["target"]
    monkeypatch.undo()


@pytest.mark.parametrize("real_operations", [upgrade.MODE, *ASSET_PROFILES], indirect=True)
@pytest.mark.parametrize(
    "boundary", ["publish-journal", "stage-recorded", "owner-published", "releasing"]
)
def test_preparing_intent_recovers_partial_birth_fence(real_operations, monkeypatch, boundary):
    from research_workbench_entrypoint.resident import gateway_fence as module

    home, state, system, make, uid = real_operations
    monkeypatch.setattr(upgrade.g, "preservation", lambda _home: state["before"])
    make(None).prepare_fence(state)
    assert (
        json.loads((home / "server/run/gateway-upgrade.json").read_text())["phase"] == "preparing"
    )
    original_atomic, original_rename = module.atomic, module.exclusive_rename

    def write(path, value):
        original_atomic(path, value)
        if boundary == "stage-recorded" and path.name == "birth-fence.json" and value["slots"]:
            raise SystemExit("fixture kill after stage journal")
        if (
            boundary == "releasing"
            and path.name == "birth-fence.json"
            and any(s.get("releasing") for s in value["slots"])
        ):
            raise SystemExit("fixture kill during release")

    def rename(source, destination):
        original_rename(source, destination)
        if boundary == "publish-journal" and destination.name == "birth-fence.json":
            raise SystemExit("fixture kill after birth journal")
        if boundary == "owner-published" and destination.name == "owner.json":
            raise SystemExit("fixture kill after owner publish")

    monkeypatch.setattr(module, "atomic", write)
    monkeypatch.setattr(module, "exclusive_rename", rename)
    fence = BirthFence(home / "server", uid, transaction=state["transaction"])
    with pytest.raises(SystemExit):
        fence.__enter__()
        fence.__exit__(None, None, None)
    fence.release_database()
    monkeypatch.setattr(module, "atomic", original_atomic)
    monkeypatch.setattr(module, "exclusive_rename", original_rename)
    BirthFence.recover(home / "server", expected=state["transaction"])
    assert not (home / "server/run/birth-fence.json").exists()
    assert not list((home / "server/users").glob("*/state/owner.json"))
    assert make(None).idle() is True
    assert system["events"] == []


@pytest.mark.parametrize(
    "profile",
    [
        upgrade.MARKET_MODE,
        upgrade.MARKET_GAPS_MODE,
        upgrade.MARKET_HISTORY_MODE,
        upgrade.MARKET_TERMINAL_MODE,
        upgrade.ASSET_V5_MODE,
        upgrade.ASSET_V6_MODE,
        upgrade.ASSET_V7_MODE,
        "reviewed-etf-weekly-v1",
        "reviewed-research-dossiers-v1",
        "reviewed-discovery-v1",
        "reviewed-etf-weekly-v2",
        "reviewed-etf-historical-v1",
    ],
)
def test_large_business_index_keeps_metadata_limit_and_profile_reader_binding(
    tmp_path, monkeypatch, profile
):
    root = tmp_path / "research-web"
    root.mkdir()
    path = root / "index.json"
    path.write_text(json.dumps({"sessions": {}, "automation_runs": {}, "padding": "x" * 1_100_000}))
    with pytest.raises(upgrade.UpdateBlocked, match="resident_record_invalid"):
        upgrade.read_json(path)
    upgrade.verify_retention(tmp_path)
    assert upgrade.asset_queries_idle(upgrade.read_business_index(path))
    calls = []

    def verify(home, expected, **kwargs):
        calls.append(kwargs)
        assert kwargs["index_reader"](path)["sessions"] == {}

    monkeypatch.setattr(upgrade.g, "verify_primary", verify)
    upgrade.verify_primary(tmp_path, "a" * 40, profile)
    assert calls == [{"index_reader": upgrade.read_business_index}]
    with pytest.raises(upgrade.UpdateBlocked, match="asset_upgrade_index_invalid"):
        upgrade.read_business_index(tmp_path / "missing.json")


@pytest.mark.parametrize(
    "profile",
    [
        upgrade.MODE,
        upgrade.ASSET_MODE,
        upgrade.ASSET_V2_MODE,
        upgrade.ASSET_V3_MODE,
        upgrade.ASSET_V4_MODE,
    ],
)
def test_legacy_primary_reader_binding_is_unchanged(tmp_path, monkeypatch, profile):
    calls = []
    monkeypatch.setattr(
        upgrade.g, "verify_primary", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    upgrade.verify_primary(tmp_path, "a" * 40, profile)
    assert calls == [((tmp_path, "a" * 40), {})]


def test_market_gap_profile_freezes_resident_and_reviewed_source_checkpoint():
    assert upgrade.MARKET_GAPS_MODE == "reviewed-market-gaps-v1"
    assert (
        upgrade.previous_for(upgrade.MARKET_GAPS_MODE) == "99d3ee34977c47189a5638207c109a555f52a687"
    )
    assert upgrade.MARKET_GAPS_PAYLOAD == "9faeeca3003a912ca75799fb27b635ba1bb87a1a"


@pytest.mark.parametrize(
    "real_operations",
    [
        "reviewed-market-gaps-v1",
        "reviewed-market-history-v1",
        "reviewed-market-terminal-v1",
        upgrade.ASSET_V7_MODE,
        "reviewed-etf-weekly-v1",
        "reviewed-research-dossiers-v1",
        "reviewed-discovery-v1",
        "reviewed-etf-weekly-v2",
        "reviewed-etf-historical-v1",
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "response,expected",
    [
        (None, False),
        ({}, False),
        ({"inflight": None}, False),
        ({"inflight": [{}]}, False),
        ({"inflight": []}, True),
    ],
)
def test_market_refresh_activity_blocks_the_fixed_upgrade(
    real_operations, monkeypatch, response, expected
):
    home, state, _system, make, uid = real_operations
    original = upgrade.request_json
    monkeypatch.setattr(
        upgrade,
        "request_json",
        lambda url: response if url.endswith("/api/research/market") else original(url),
    )
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        assert make(fence).idle() is expected


def test_asset_v5_is_bound_to_actual_resident_and_merged_product():
    assert upgrade.ASSET_V5_MODE == "reviewed-asset-observation-v5"
    assert upgrade.previous_for(upgrade.ASSET_V5_MODE) == "51f09fa783694aae5234905933948394ca167dcc"
    assert upgrade.ASSET_V5_PAYLOAD == "88ef3817680ac822e2d7c819db845de4b7275173"


def test_market_history_profile_freezes_resident_and_reviewed_checkpoint():
    assert upgrade.MARKET_HISTORY_MODE == "reviewed-market-history-v1"
    assert (
        upgrade.previous_for(upgrade.MARKET_HISTORY_MODE)
        == "51f09fa783694aae5234905933948394ca167dcc"
    )
    assert upgrade.MARKET_HISTORY_PAYLOAD == "4f0a248fc87249d41e1c3f75f700c17c8351ad95"


@pytest.mark.parametrize("profile", [upgrade.MODE, *upgrade.ASSET_MODES])
def test_target_manifest_preserves_old_lock_except_authorized_v5_combination(profile):
    old = {"code_commit": "a" * 40, "web_lock_sha256": "c" * 64, "installed_at": "old"}
    state = {"mode": profile, "manifest": old, "target": "b" * 40}
    target = upgrade.target_manifest(state)
    expected = {**old, "code_commit": "b" * 40}
    if profile in {
        upgrade.ASSET_V5_MODE,
        upgrade.ASSET_V6_MODE,
        upgrade.ASSET_V7_MODE,
        upgrade.MARKET_HISTORY_MODE,
        upgrade.MARKET_TERMINAL_MODE,
    }:
        expected["web_lock_sha256"] = (
            "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
        )
    assert target == expected
    assert old == state["manifest"]


def test_market_terminal_profile_freezes_actual_resident_and_reviewed_checkpoint():
    assert upgrade.MARKET_TERMINAL_MODE == "reviewed-market-terminal-v1"
    assert (
        upgrade.previous_for(upgrade.MARKET_TERMINAL_MODE)
        == "0e0022ac792eba88fba0f233524f5c8d66024569"
    )
    assert upgrade.MARKET_TERMINAL_PAYLOAD == "ca20293b8244bb0644bf2039ddd96ee452a27b0b"
    assert (
        upgrade.MARKET_TERMINAL_WEB_LOCK_SHA256
        == "7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102"
    )
    reader = Path(upgrade.__file__).with_name("evidence.py").read_bytes()
    assert hashlib.sha256(reader).hexdigest() == upgrade.MARKET_TERMINAL_EVIDENCE_SHA256
    assert upgrade.MARKET_TERMINAL_EVIDENCE_SHA256 == upgrade.ASSET_V6_EVIDENCE_SHA256
    assert upgrade.MARKET_TERMINAL_EVIDENCE_SHA256 != upgrade.ASSET_EVIDENCE_SHA256


@pytest.mark.parametrize("real_operations", ["reviewed-market-terminal-v1"], indirect=True)
@pytest.mark.parametrize("credential", ["credential_configured", "credential_storage"])
def test_market_terminal_preserves_credential_contract(real_operations, monkeypatch, credential):
    home, state, _system, make, uid = real_operations
    original = upgrade.request_json

    def request(url):
        value = original(url)
        if url.endswith("/api/research/runtime"):
            return {
                **value,
                credential: False if credential == "credential_configured" else "changed",
            }
        return value

    # Model metadata is checked by the existing preservation gate rather than
    # calling a provider or reading a secret; changing its contract must refuse.
    monkeypatch.setattr(upgrade, "request_json", request)
    upgrade.g.write_upgrade_journal(home / "server/run/gateway-upgrade.json", state)
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        ops = make(fence)
        with pytest.raises(
            upgrade.UpdateBlocked, match="model_upgrade_credential_metadata_changed"
        ):
            ops.verify(previous=True)


def test_asset_v6_binds_verified_resident_product_reader_and_unchanged_old_contracts():
    assert upgrade.ASSET_V6_MODE == "reviewed-asset-observation-v6"
    assert upgrade.previous_for(upgrade.ASSET_V6_MODE) == "c1a260fa1d8dcf013426aca938d7e46a98aaee28"
    assert upgrade.ASSET_V6_PAYLOAD == "eac6806822294d75da990c751d88ec156a417f62"
    reader = Path(upgrade.__file__).with_name("evidence.py").read_bytes()
    assert hashlib.sha256(reader).hexdigest() == upgrade.ASSET_V6_EVIDENCE_SHA256
    assert (
        upgrade.ASSET_EVIDENCE_SHA256
        == "ec022e39a89a3dbd021fca26049342ce149077f5beb62a8df2aba7826d016d25"
    )
    assert (
        upgrade.CONTROLLER_SHA256
        == "4924299104d5f82a9cc732bb2ca1f811694d14056d58a2762e7c86e40f6665a2"
    )
    assert (
        upgrade.CONTROLLER_MODULE_SHA256
        == "b432f519e14a2e851a7eb39a3de179f99494b9347c857694c4192477a7996846"
    )


def test_asset_v7_pins_current_resident_and_merged_panel_product():
    assert upgrade.ASSET_V7_MODE == "reviewed-asset-observation-v7"
    assert upgrade.previous_for(upgrade.ASSET_V7_MODE) == "c4e953c4386c615cde89ad2d014d60c6e2959303"
    assert upgrade.ASSET_V7_PAYLOAD == "3a62ca1a3bff0927db681322a1ff028f08cf03cd"
    assert upgrade.ASSET_V7_WEB_LOCK_SHA256 == upgrade.ASSET_V6_WEB_LOCK_SHA256
    assert (
        hashlib.sha256(Path(upgrade.__file__).with_name("evidence.py").read_bytes()).hexdigest()
        == upgrade.ASSET_V7_EVIDENCE_SHA256
    )
    assert upgrade.ASSET_V6_PREVIOUS == "c1a260fa1d8dcf013426aca938d7e46a98aaee28"
    assert upgrade.ASSET_V6_PAYLOAD == "eac6806822294d75da990c751d88ec156a417f62"


def test_etf_weekly_profile_freezes_registered_resident_and_merged_product():
    assert upgrade.previous_for("reviewed-etf-weekly-v1") == (
        "5343e18d9f203a87f2d958218e4288afa527711f"
    )
    assert upgrade.ETF_WEEKLY_MODE == "reviewed-etf-weekly-v1"
    # Product acceptance and operator acceptance remain separate gates.
    assert upgrade.ETF_WEEKLY_PAYLOAD == "988046d23f9951f889a3b9d02e355ed59fd6aa65"
    assert upgrade.ETF_WEEKLY_MODE in upgrade.ASSET_MODES
    reader = Path(upgrade.__file__).with_name("evidence.py").read_bytes()
    assert hashlib.sha256(reader).hexdigest() == upgrade.ASSET_V6_EVIDENCE_SHA256


@pytest.mark.parametrize(
    "real_operations",
    [
        "reviewed-etf-weekly-v1",
        "reviewed-research-dossiers-v1",
        "reviewed-discovery-v1",
        "reviewed-etf-weekly-v2",
        "reviewed-etf-historical-v1",
    ],
    indirect=True,
)
@pytest.mark.parametrize("active", [True, None, "false", 0])
def test_etf_weekly_host_activity_requires_explicit_false(real_operations, monkeypatch, active):
    home, state, system, make, uid = real_operations
    original = upgrade.request_json

    def request(url):
        value = original(url)
        if url.endswith("/api/research/resident"):
            return {**value, "active": active}
        return value

    monkeypatch.setattr(upgrade, "request_json", request)
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        assert upgrade.execute(make(fence), state) == {"status": "deferred"}
    assert system["events"] == []
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()


@pytest.mark.parametrize(
    "real_operations",
    [
        "reviewed-etf-weekly-v1",
        "reviewed-research-dossiers-v1",
        "reviewed-discovery-v1",
        "reviewed-etf-weekly-v2",
        "reviewed-etf-historical-v1",
    ],
    indirect=True,
)
@pytest.mark.parametrize("guard", ["runtime", "runtime-unknown", "pool", "pool-unknown"])
def test_etf_weekly_native_or_pool_activity_defers_without_effects(
    real_operations, monkeypatch, guard
):
    home, state, system, make, uid = real_operations
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        ops = make(fence)
        if guard.startswith("runtime"):

            def activity(_probe):
                if guard == "runtime-unknown":
                    raise ValueError("fixture_runtime_unknown")
                return ["fixture-active-session"]

            monkeypatch.setattr(ops.manager, "_active_research_read_only", activity)
        else:
            monkeypatch.setattr(
                upgrade, "reserved_owners", lambda *_: False if guard == "pool" else None
            )
        assert upgrade.execute(ops, state) == {"status": "deferred"}
    assert system["events"] == []
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()


@pytest.mark.parametrize(
    "profile", ["reviewed-etf-weekly-v1", "reviewed-etf-weekly-v2", "reviewed-etf-historical-v1"]
)
def test_etf_weekly_preserves_install_lock_without_dependency_exception(profile):
    old = {"code_commit": "a" * 40, "web_lock_sha256": "c" * 64}
    state = {"mode": profile, "manifest": old, "target": "b" * 40}
    assert upgrade.target_manifest(state) == {**old, "code_commit": "b" * 40}
    assert old == state["manifest"]


def test_dossiers_profile_binds_verified_resident_and_merged_product():
    assert upgrade.DOSSIERS_MODE == "reviewed-research-dossiers-v1"
    assert upgrade.previous_for(upgrade.DOSSIERS_MODE) == "5343e18d9f203a87f2d958218e4288afa527711f"
    assert upgrade.DOSSIERS_PAYLOAD == "1780064b712afb61ff18f2f1811650fc31fd3038"
    assert upgrade.DOSSIERS_MODE in upgrade.ASSET_MODES
    assert upgrade.target_manifest(
        {"mode": upgrade.DOSSIERS_MODE, "manifest": {"web_lock_sha256": "old"}, "target": "b" * 40}
    ) == {"web_lock_sha256": "old", "code_commit": "b" * 40}


def test_etf_weekly_v2_profile_freezes_combined_product_without_rewriting_v1():
    assert upgrade.ETF_WEEKLY_V2_MODE == "reviewed-etf-weekly-v2"
    assert upgrade.previous_for(upgrade.ETF_WEEKLY_V2_MODE) == (
        "5343e18d9f203a87f2d958218e4288afa527711f"
    )
    assert upgrade.ETF_WEEKLY_V2_PAYLOAD == "56709a8dbb6e01d2ab17b64533319e199ebef86f"
    assert upgrade.ETF_WEEKLY_PAYLOAD == "988046d23f9951f889a3b9d02e355ed59fd6aa65"
    assert upgrade.ETF_WEEKLY_V2_MODE in upgrade.ASSET_MODES
    assert hashlib.sha256(
        Path(upgrade.__file__).with_name("evidence.py").read_bytes()
    ).hexdigest() == (upgrade.ASSET_V6_EVIDENCE_SHA256)
    lock = Path(__file__).resolve().parents[2] / "requirements/web.lock"
    assert hashlib.sha256(lock.read_bytes()).hexdigest() == upgrade.ASSET_V6_WEB_LOCK_SHA256


def _weekly_v2_dossiers(home, state, uid):
    from app.research_web.dossiers import DossierService
    from app.research_web.store import Store

    archives = []
    for root in (home / "research-web", home / "server/users" / uid / "research-web"):
        research = SimpleNamespace(store=Store(root))
        research.store.save()
        service = DossierService(research)
        dossier = service.create(
            {
                "title": "保全档案",
                "subject": {"kind": "theme", "key": "energy", "label": "能源"},
                "idempotency_key": "create-0001",
            }
        )
        archives.append((service, dossier))
    state["asset_index_before"] = upgrade.asset_index_snapshot(home)
    assert "@dossiers" in state["asset_index_before"]["primary"]
    assert "@dossiers" in state["asset_index_before"]["private"][uid]
    return archives


@pytest.mark.parametrize(
    "real_operations", ["reviewed-etf-weekly-v2", "reviewed-etf-historical-v1"], indirect=True
)
@pytest.mark.parametrize("failed", [None, *upgrade.FORWARD])
def test_weekly_v2_dossiers_survive_each_transaction_or_rollback(real_operations, failed):
    home, state, system, make, uid = real_operations
    _weekly_v2_dossiers(home, state, uid)
    system["fail"] = failed
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        result = upgrade.execute(make(fence), state)
    assert result["status"] == ("deployed" if failed is None else "rolled_back")
    upgrade.verify_asset_index(home, state)


@pytest.mark.parametrize(
    "real_operations", ["reviewed-etf-weekly-v2", "reviewed-etf-historical-v1"], indirect=True
)
@pytest.mark.parametrize("scope", [0, 1])
@pytest.mark.parametrize("boundary", ["verify_target", "finish", "recover"])
def test_weekly_v2_changed_dossiers_keep_recovery_fenced(real_operations, scope, boundary):
    home, state, _system, make, uid = real_operations
    archives = _weekly_v2_dossiers(home, state, uid)
    service, dossier = archives[scope]

    def mutate():
        service.patch(
            dossier["id"],
            {"expected_revision": 1, "idempotency_key": "patch-0001", "title": "不得丢失的变更"},
        )

    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        ops = make(fence)
        original_action, original_finish = ops.action, ops.finish

        def action(name, value):
            if name == boundary:
                mutate()
            return original_action(name, value)

        def finish(value, result):
            if boundary == "finish":
                mutate()
            return original_finish(value, result)

        ops.action, ops.finish = action, finish
        if boundary == "recover":
            upgrade.g.write_upgrade_journal(home / "server/run/gateway-upgrade.json", state)
            mutate()
        result = upgrade.execute(ops, state, recovering=boundary == "recover")
    assert result["status"] in {"recovery_required", "completion_unknown"}
    assert result.get("preserved") is not True
    assert (home / "server/run/gateway-upgrade.json").exists()
    assert not (home / "server/run/model-upgrade-result.json").exists()


@pytest.mark.parametrize(
    "damage",
    [None, "missing", "dirty", "source-mismatch", "target-mismatch", "checksum", "mode", "alias"],
)
def test_real_recovery_zip_preserves_dossiers_with_old_wheel(tmp_path, monkeypatch, damage):
    """Run the actual zip entry with no dossier module in the installed old app."""
    import os
    import shutil
    import zipfile

    from app.research_web.dossiers.storage import DossierStore

    project = Path(upgrade.__file__).parents[2]
    authority = tmp_path / "authority"
    authority.mkdir()

    def only_python_and_contracts(folder, names):
        return [
            name
            for name in names
            if name == "__pycache__"
            or (Path(folder, name).is_file() and Path(name).suffix not in {".py", ".json"})
        ]

    for name in ("app", "core", "research_workbench_entrypoint", "runtimes"):
        shutil.copytree(project / name, authority / name, ignore=only_python_and_contracts)

    def git(where, *args):
        return subprocess.check_output(
            ["/usr/bin/git", "-C", str(where), *args], text=True, stderr=subprocess.PIPE
        ).strip()

    git(authority, "init")
    git(authority, "config", "user.email", "fixture@example.invalid")
    git(authority, "config", "user.name", "Fixture")
    git(authority, "add", ".")
    git(authority, "commit", "-m", "frozen recovery fixture")
    target = git(authority, "rev-parse", "HEAD")
    home = tmp_path / "private-home"
    source = home / "resident/artifacts" / target / "source"
    source.parent.mkdir(parents=True)
    subprocess.run(
        ["/usr/bin/git", "clone", "--no-hardlinks", str(authority), str(source)],
        check=True,
        capture_output=True,
    )
    (home / "server/run").mkdir(parents=True)
    (home / "server/users").mkdir()
    (home / "logs").mkdir()
    data = home / "research-web"
    data.mkdir()
    (data / "index.json").write_text(json.dumps({"notes": {"fixture": "preserved"}}))
    with DossierStore(data).connection(write=True):
        pass
    fake_user = tmp_path / "fake-user"
    (fake_user / "Library/LaunchAgents").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_user))
    real_run = upgrade.g.run

    def local_system_only(argv, *args, **kwargs):
        if argv[0] == "/bin/launchctl" or argv[:2] == [
            "/usr/bin/env",
            "PATH=" + upgrade.g.RECOVERY_PATH,
        ]:
            return "fixture system command"
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(upgrade.g, "run", local_system_only)
    python = os.environ.get("RWB_RECOVERY_OLD_PYTHON", sys.executable)
    recovery = upgrade.install_recovery(home, source, target, python)
    artifact = Path(recovery["artifact"])
    with zipfile.ZipFile(artifact) as archive:
        assert json.loads(archive.read("manifest.json"))["source"] == str(source)
    state = {
        "version": 4,
        "mode": "reviewed-research-dossiers-v1",
        "target": target,
        "source": str(source),
        "recovery": recovery,
    }
    if damage == "source-mismatch":
        state["source"] = str(home / "other-source")
    elif damage == "target-mismatch":
        state["target"] = "b" * 40
    elif damage == "mode":
        state["mode"] = "unreviewed"
    elif damage == "checksum":
        state["recovery"] = {**recovery, "sha256": "0" * 64}
    journal = home / "server/run/gateway-upgrade.json"
    journal.write_text(json.dumps(state))
    journal.chmod(0o600)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)
    if "RWB_RECOVERY_OLD_PYTHON" not in os.environ:
        old_site = tmp_path / "old-wheel"
        (old_site / "app/research_web").mkdir(parents=True)
        (old_site / "app/__init__.py").write_text("")
        (old_site / "app/research_web/__init__.py").write_text("")
        env["PYTHONPATH"] = str(old_site)
    old_check = "import importlib.util; assert importlib.util.find_spec('app.research_web.dossier_preservation') is None"
    baseline = subprocess.run(
        [python, "-P", "-c", old_check],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert baseline.returncode == 0, baseline.stderr
    if damage == "missing":
        source.rename(source.with_name("retained-source"))
    elif damage == "alias":
        retained = source.with_name("retained-source")
        source.rename(retained)
        source.symlink_to(retained, target_is_directory=True)
    elif damage == "dirty":
        with (source / "app/research_web/dossier_preservation.py").open("a") as stream:
            stream.write("\n# changed frozen source\n")
    script = r"""
import json, os, runpy, subprocess, sys
from pathlib import Path
archive, home, python, old_check = sys.argv[1:]
sys.path.insert(0, archive)
from resident import model_provider_upgrade as u
original_path = os.environ.get("PYTHONPATH")
def probe(*args, **kwargs):
    home_path = Path(home)
    (home_path / "probe-called").write_text("fixture probe")
    snapshot = u.asset_index_snapshot(home_path)
    assert "@dossiers" in snapshot["primary"]
    u.verify_asset_index(home_path, {"mode": u.DOSSIERS_MODE, "asset_index_before": snapshot})
    assert os.environ.get("PYTHONPATH") == original_path
    child = subprocess.run([python, "-P", "-c", old_check], cwd=home, capture_output=True, text=True)
    assert child.returncode == 0, child.stderr
    return {"status": "not_required", "frozen_dossiers_verified": True, "old_child_unchanged": True}
u.operate = probe
sys.argv = [archive, "recover", "--home", home]
runpy.run_path(archive, run_name="__main__")
"""
    completed = subprocess.run(
        [python, "-P", "-c", script, str(artifact), str(home), python, old_check],
        check=False,
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    if damage is None:
        assert completed.returncode == 0, completed.stderr
        assert result["frozen_dossiers_verified"] and result["old_child_unchanged"]
    else:
        assert completed.returncode == 1
        assert not (home / "probe-called").exists()
        assert result["reason"] == "model_upgrade_recovery_source_unavailable"


def test_etf_historical_profile_freezes_product_ancestor_and_current_resident():
    assert upgrade.ETF_HISTORICAL_MODE == "reviewed-etf-historical-v1"
    assert upgrade.previous_for(upgrade.ETF_HISTORICAL_MODE) == (
        "b438447071d08eec38902b2a50610644283885f9"
    )
    assert upgrade.ETF_HISTORICAL_PAYLOAD == "d5d5b456706fc02505ac1100353d46438c184556"
    assert upgrade.ETF_HISTORICAL_MODE in upgrade.ASSET_MODES
    assert upgrade.ETF_WEEKLY_V2_PREVIOUS == "5343e18d9f203a87f2d958218e4288afa527711f"
    assert upgrade.ETF_WEEKLY_V2_PAYLOAD == "56709a8dbb6e01d2ab17b64533319e199ebef86f"
    assert hashlib.sha256(
        Path(upgrade.__file__).with_name("evidence.py").read_bytes()
    ).hexdigest() == (upgrade.ASSET_V6_EVIDENCE_SHA256)
    lock = Path(__file__).resolve().parents[2] / "requirements/web.lock"
    assert hashlib.sha256(lock.read_bytes()).hexdigest() == upgrade.ASSET_V6_WEB_LOCK_SHA256
