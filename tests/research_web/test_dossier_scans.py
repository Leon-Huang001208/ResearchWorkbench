"""Real archive/snapshot/Automation contracts; no provider or model calls."""

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.research_web.automation.models import AutomationCreate
from app.research_web.automation.service import AutomationService
from app.research_web.datahub import DataHub
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.dossiers import DossierService
from app.research_web.dossiers.scans import DossierSignals
from app.research_web.store import Store, StoreError

NOW = datetime(2026, 10, 23, 8, tzinfo=UTC)


def prepared(tmp_path):
    research = SimpleNamespace(store=Store(tmp_path / "personal"))
    research.dossiers = DossierService(research)
    research.datahub = DataHub(research.store)
    research.automations = AutomationService(
        research.store, research=research, scheduler=False, now=lambda: NOW
    )
    sid = research.store.create("fingpt", "离线原件")["id"]
    research.store.session(sid)["source_scope"] = ["datahub"]
    query = BusinessQuery(
        capability="financials", source="akshare", parameters={"asset": "600519.SH"}
    )
    native = Result(
        rows=[
            {
                "asset": "600519.SH",
                "report_period": "2026-06-30",
                "publication_date": "2026-10-22",
                "publication_precision": "date",
                "net_profit_yoy": -2.0,
            }
        ],
        raw=[b"frozen native disclosure"],
        status="snapshot",
        as_of="2026-10-22",
        pagination_complete=True,
        metadata={"schema_version": "akshare-sina-financial-disclosure-v1"},
    )
    manifest = Snapshots(research.store).publish(
        sid,
        query,
        native,
        request_query=query,
        authorization_fingerprint=research.datahub.source_configuration_digest("akshare"),
    )
    dossier = research.dossiers.create(
        {
            "title": "长期研究",
            "subject": {"kind": "company", "key": "600519.SH", "label": "贵州茅台"},
            "idempotency_key": "create-0001",
        }
    )
    dossier = research.dossiers.add_evidence(
        dossier["id"],
        {
            "expected_revision": 1,
            "idempotency_key": "evidence-0001",
            "source_session_id": sid,
            "reference": {"type": "dataset", "id": manifest["dataset_id"]},
        },
    )
    return research, DossierSignals(research, now=lambda: NOW), dossier, sid


@pytest.mark.asyncio
async def test_actual_snapshot_scan_replays_and_preserves_opinion(tmp_path):
    research, scans, dossier, _sid = prepared(tmp_path)
    dossier = research.dossiers.add_record(
        dossier["id"],
        {
            "expected_revision": dossier["revision"],
            "idempotency_key": "opinion-0001",
            "kind": "opinion",
            "title": "旧判断",
            "body": "待验证",
            "state": "open",
            "reason": "初判",
            "evidence_ids": [],
        },
    )
    request = {
        "expected_revision": dossier["revision"],
        "idempotency_key": "scan-0001",
        "as_of": "2026-10-23",
    }
    result = await scans.scan(dossier["id"], request)
    assert result["coverage"]["eligible"] is True
    assert len(result["signals"]) == 1
    assert result["notifications"][0]["change"] == "new"
    assert result["signals"][0]["signal_type"] == "review"
    assert scans.list(kind="review")["items"]
    assert scans.list(kind="risk")["items"] == []
    assert result["signals"][0]["evidence_ids"] == [dossier["evidence"][0]["id"]]
    assert (
        next(row for row in result["dossier"]["records"] if row["kind"] == "opinion")["body"]
        == "待验证"
    )
    assert result == await scans.scan(dossier["id"], request)
    again = await scans.scan(
        dossier["id"],
        {
            **request,
            "expected_revision": result["dossier"]["revision"],
            "idempotency_key": "scan-0002",
        },
    )
    assert again["notifications"] == []
    assert scans.list(dossier_id=dossier["id"])["items"][0]["id"] == result["signals"][0]["id"]
    reopened_store = Store(research.store.root)
    reopened = DossierService(
        SimpleNamespace(store=reopened_store, datahub=DataHub(reopened_store))
    )
    assert reopened.get(dossier["id"])["scan"]["notifications"] == []


@pytest.mark.asyncio
async def test_scan_transaction_failure_rolls_back_index_and_revision(tmp_path, monkeypatch):
    research, scans, dossier, _sid = prepared(tmp_path)
    request = {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    original = research.dossiers.metadata._append_event

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected transaction error")

    monkeypatch.setattr(research.dossiers.metadata, "_append_event", fail)
    with pytest.raises(RuntimeError, match="injected"):
        await scans.scan(dossier["id"], request)
    assert research.dossiers.get(dossier["id"])["revision"] == dossier["revision"]
    assert scans.list()["items"] == []
    monkeypatch.setattr(research.dossiers.metadata, "_append_event", original)
    assert (await scans.scan(dossier["id"], request))["signals"]


@pytest.mark.asyncio
async def test_revoked_evidence_marks_signal_stale_not_resolved(tmp_path):
    research, scans, dossier, sid = prepared(tmp_path)
    result = await scans.scan(
        dossier["id"], {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    )
    research.store.session(sid)["source_scope"] = ["uploads"]
    assert scans.list()["items"][0]["stale"] is True
    changed = await scans.scan(
        dossier["id"],
        {"expected_revision": result["dossier"]["revision"], "idempotency_key": "scan-0002"},
    )
    assert changed["signals"][0]["state"] == "open"
    assert changed["signals"][0]["stale"] is True
    assert changed["coverage"]["eligible"] is False
    assert changed["notifications"] == []


@pytest.mark.asyncio
async def test_tracking_is_opt_in_requires_manual_scan_and_replay_cannot_reenable(tmp_path):
    research, scans, dossier, _sid = prepared(tmp_path)
    assert dossier["tracking"]["enabled"] is False
    assert research.store.data.get("automations", {}) == {}
    with pytest.raises(StoreError) as error:
        scans.tracking(
            dossier["id"],
            {
                "expected_revision": dossier["revision"],
                "idempotency_key": "tracking-0001",
                "enabled": True,
            },
        )
    assert error.value.code == "dossier_tracking_manual_required"
    scanned = await scans.scan(
        dossier["id"], {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    )
    request = {
        "expected_revision": scanned["dossier"]["revision"],
        "idempotency_key": "tracking-0001",
        "enabled": True,
    }
    enabled = scans.tracking(dossier["id"], request)
    aid = enabled["tracking"]["automation_id"]
    assert enabled["tracking"]["enabled"] is True
    assert research.store.data["automations"][aid]["enabled"] is True
    assert scans.tracking(dossier["id"], request)["tracking"]["enabled"] is True
    result = await scans.scheduled(dossier["id"], "run-0001")
    assert result["suppress_delivery"] is True
    current = research.dossiers.get(dossier["id"])
    disabled = scans.tracking(
        dossier["id"],
        {
            "expected_revision": current["revision"],
            "idempotency_key": "tracking-0002",
            "enabled": False,
        },
    )
    assert disabled["tracking"]["enabled"] is False
    scans.tracking(dossier["id"], request)
    assert research.store.data["automations"][aid]["enabled"] is False
    assert research.dossiers.get(dossier["id"])["tracking"]["enabled"] is False


@pytest.mark.asyncio
async def test_failed_activation_stays_disabled_and_retry_recovers(tmp_path, monkeypatch):
    research, scans, dossier, _sid = prepared(tmp_path)
    scanned = await scans.scan(
        dossier["id"], {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    )
    request = {
        "expected_revision": scanned["dossier"]["revision"],
        "idempotency_key": "tracking-0001",
        "enabled": True,
    }
    original = research.automations.enable

    def fail(*_args, **_kwargs):
        raise RuntimeError("scheduler failure")

    monkeypatch.setattr(research.automations, "enable", fail)
    with pytest.raises(RuntimeError, match="scheduler failure"):
        scans.tracking(dossier["id"], request)
    current = research.dossiers.get(dossier["id"])
    assert current["tracking"]["enabled"] is False
    assert not any(row["enabled"] for row in research.store.data["automations"].values())
    monkeypatch.setattr(research.automations, "enable", original)
    assert scans.tracking(dossier["id"], request)["tracking"]["enabled"] is True


def test_scan_input_budget_and_non_model_automation_contract(tmp_path):
    _research, scans, _dossier, _sid = prepared(tmp_path)
    for cursor in ("not-a-number", "-1", "100001"):
        with pytest.raises(StoreError) as error:
            scans.list(cursor=cursor)
        assert error.value.status == 422
    with pytest.raises(ValueError):
        AutomationCreate(
            name="no model",
            target_kind="dossier_scan",
            target_id="a" * 32,
            target_version=1,
            input_template="scan",
            output_formats=["md"],
            schedule={"kind": "daily", "timezone": "Asia/Shanghai", "hour": 9, "minute": 0},
        )


@pytest.mark.asyncio
async def test_pending_old_authorization_cannot_adopt_upgraded_rules(tmp_path, monkeypatch):
    from app.research_web.dossiers import scans as module

    research, scans, dossier, _sid = prepared(tmp_path)
    scanned = await scans.scan(
        dossier["id"], {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    )
    request = {
        "expected_revision": scanned["dossier"]["revision"],
        "idempotency_key": "tracking-0001",
        "enabled": True,
    }
    original = research.automations.enable
    monkeypatch.setattr(
        research.automations,
        "enable",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("injected")),
    )
    with pytest.raises(RuntimeError, match="injected"):
        scans.tracking(dossier["id"], request)
    monkeypatch.setattr(research.automations, "enable", original)
    monkeypatch.setattr(module, "RULES_SHA256", "f" * 64)
    with pytest.raises(StoreError) as error:
        scans.tracking(dossier["id"], request)
    assert error.value.code == "dossier_tracking_manual_required"
    current = research.dossiers.get(dossier["id"])
    await scans.scan(
        dossier["id"],
        {"expected_revision": current["revision"], "idempotency_key": "scan-upgraded-0001"},
    )
    with pytest.raises(StoreError) as error:
        scans.tracking(dossier["id"], request)
    assert error.value.code == "dossier_tracking_definition_changed"
    assert not any(row["enabled"] for row in research.store.data["automations"].values())


@pytest.mark.asyncio
async def test_signal_disposition_filter_uses_current_transactional_state(tmp_path):
    research, scans, dossier, _sid = prepared(tmp_path)
    result = await scans.scan(
        dossier["id"], {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    )
    signal = result["signals"][0]
    research.dossiers.add_record(
        dossier["id"],
        {
            "expected_revision": result["dossier"]["revision"],
            "idempotency_key": "dismiss-0001",
            "record_id": signal["id"],
            "kind": "signal",
            "title": signal["title"],
            "body": signal["body"],
            "reason": "研究者已处理",
            "state": "dismissed",
            "evidence_ids": signal["evidence_ids"],
        },
    )
    assert scans.list(state="open")["items"] == []
    assert scans.list(state="dismissed")["items"][0]["id"] == signal["id"]


@pytest.mark.asyncio
async def test_tracking_never_silently_enables_when_scheduler_profile_is_disabled(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    research, scans, dossier, _sid = prepared(tmp_path)
    result = await scans.scan(
        dossier["id"], {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    )
    assert result["coverage"]["eligible"]
    assert result["dossier"]["tracking"]["eligible"] is False
    assert result["dossier"]["tracking"]["reason"] == "automation_disabled"
    with pytest.raises(StoreError) as error:
        scans.tracking(
            dossier["id"],
            {
                "expected_revision": result["dossier"]["revision"],
                "idempotency_key": "tracking-0001",
                "enabled": True,
            },
        )
    assert error.value.code == "dossier_tracking_unavailable"
    assert not research.store.data.get("automations", {})


@pytest.mark.asyncio
async def test_backup_restore_includes_scan_tracking_and_pins(tmp_path):
    research, scans, dossier, sid = prepared(tmp_path)
    result = await scans.scan(
        dossier["id"], {"expected_revision": dossier["revision"], "idempotency_key": "scan-0001"}
    )
    destination = tmp_path / "backup.sqlite3"
    research.dossiers.backup_to(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    research.dossiers.restore_from(destination, expected_sha256=digest)
    assert research.dossiers.get(dossier["id"])["scan"] == result["dossier"]["scan"]
    assert scans.list()["items"]
    research.store.soft_delete(sid)
    research.store.mark_native_deleted(sid)
    with pytest.raises(StoreError) as error:
        research.store.purge(sid)
    assert error.value.code == "dossier_evidence_retained"
