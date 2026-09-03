"""DataHub contract and source normalization regression tests (no live credentials)."""

from datetime import UTC, datetime

import pytest

from core.contracts.datahub import DataHubSyncRequest
from data_layer.normalizers.cjpy import normalize_row


def test_sync_rejects_credentials_and_bad_dates():
    with pytest.raises(ValueError):
        DataHubSyncRequest(dataset="stock_list", params={"token": "secret"})
    with pytest.raises(ValueError):
        DataHubSyncRequest(
            dataset="daily_quotes",
            params={"codes": ["000001.SZ"], "start_date": "2026-02-30", "end_date": "2026-03-01"},
        )


def test_minutes_zero_and_adjustment_are_preserved():
    result = normalize_row(
        "daily_quotes",
        {
            "code": "SZ000001",
            "date": "20260902",
            "time": "09:35:00",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "vol": 0,
        },
        {"cycle": "5m", "rate": "后复权"},
        datetime(2026, 9, 2, 9, tzinfo=UTC),
    )
    assert result["symbol"] == "000001.SZ"
    assert result["as_of"].minute == 35
    assert result["payload"]["volume"] == 0
    assert result["payload"]["adjustment"] == "backward"
    assert result["quality_flags"] == []


def test_unrecognized_table_semantics_are_quarantined_without_losing_fields():
    row = {"代码": "000001.SZ", "未知指标": 1.25, "附注": "完整保留"}
    result = normalize_row("table_data", row, {"table_name": "示例"}, datetime.now(UTC))
    assert result["freshness_status"] == "quarantined"
    assert result["payload"]["source_fields"] == row


def test_daily_query_cannot_masquerade_as_intraday_without_time():
    result = normalize_row(
        "daily_quotes",
        {"code": "000001.SZ", "date": "20260902", "close": 1},
        {"cycle": "5m"},
        datetime.now(UTC),
    )
    assert "missing_intraday_time" in result["quality_flags"]


import json
import os
from datetime import timedelta
from types import SimpleNamespace

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from connectors.market.cjpy import CjpyMarketConnector
from core.contracts.datahub import CATALOG_DATASETS, DATASETS, DataHubQuery
from data_layer.repositories.datahub_models import DataHubBarDB, DataHubRowDB, DataHubSnapshotDB
from data_layer.repositories.datahub_repository import DataHubRepository, digest
from data_layer.repositories.models import (
    DomainEventDB,
    IndexComponentSnapshotDB,
    IndexMasterDB,
    ResearchArtifactDB,
    ResearchRunDB,
    ScheduledJobDB,
    StockDailyBarDB,
)
from services.datahub_service import DataHubService

NOW = datetime.now(UTC)


@pytest.fixture(params=["sqlite", "postgresql"])
def facts_db(request, db_session):
    if request.param == "sqlite":
        yield db_session
        return
    url = os.environ.get("DATAHUB_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set DATAHUB_TEST_DATABASE_URL to an isolated migrated PostgreSQL test database"
        )
    engine = create_engine(url)
    with Session(engine) as db:
        try:
            yield db
        finally:
            db.rollback()
    engine.dispose()


def save(db, dataset, rows, params=None, observed=NOW):
    columns = list(dict.fromkeys(k for row in rows for k in row))
    return DataHubRepository(db).save_snapshot(
        dataset, rows, columns, params or {}, digest(rows), "raw/test.json", observed
    )[0]


def seed(db):
    save(db, "stock_list", [{"value": "000001.SZ"}, {"value": "000002.SZ"}], {"date": "2020-01-01"})
    db.add(
        IndexMasterDB(
            index_id="csi:000300",
            provider_code="csi",
            official_code="000300",
            wind_code="000300.SH",
            name_cn="CSI 300",
        )
    )
    db.flush()


def dataset_case(dataset):
    if dataset in CATALOG_DATASETS:
        return [{"字段": "完整", "额外字段": None}], {
            "table_name": "股本结构"
        } if dataset == "table_fields" else {}
    if dataset == "fund_list":
        return [{"value": "OF000001"}], {"date": "2026-09-02"}
    if dataset in {"stock_list", "codes"}:
        return [{"value": "000001.SZ"}], {
            "universe": "stock.a",
            "date": "2026-09-02",
        } if dataset == "codes" else {"date": "2026-09-02"}
    if dataset == "trading_days":
        return [{"value": "20260902"}], {"start_date": "2026-09-02", "end_date": "2026-09-02"}
    if dataset == "daily_quotes":
        return [
            {
                "代码": "SZ000001",
                "时间": "2026-09-02",
                "close": 12.3,
                "vol": 0,
                "未知原始字段": {"x": [1, None]},
            }
        ], {"codes": ["000001.SZ"], "start_date": "2026-09-02", "end_date": "2026-09-02"}
    if dataset == "index_constituents":
        return [{"value": "000001.SZ"}], {"codes": ["000300.SH"], "date": "2026-09-02"}
    if dataset == "factor_data":
        return [{"代码": "SZ000001", "截止日": "20260902", "因子": 1.2}], {
            "codes": ["000001.SZ"],
            "factors": ["因子"],
            "date": "2026-09-02",
            "column_units": {"因子": "倍"},
        }
    if dataset == "table_data":
        return [{"CODE": "SZ000001", "变动日": 20260902, "总股本": 100}], {
            "codes": ["000001.SZ"],
            "table_name": "股本结构",
            "date_field": "变动日",
            "column_units": {"总股本": "股"},
        }
    return [{"截止日": "20260630", "GDP": 12.5}], {
        "indicator": "GDP@国民经济",
        "column_units": {"GDP": "亿元"},
    }


@pytest.mark.parametrize("dataset", list(DATASETS))
def test_every_dataset_full_roundtrip_and_idempotency(facts_db, dataset):
    seed(facts_db)
    rows, params = dataset_case(dataset)
    snapshot = save(facts_db, dataset, rows, params)
    same = save(facts_db, dataset, rows, params, NOW + timedelta(seconds=1))
    assert same == snapshot
    result = DataHubService(facts_db).query(DataHubQuery(dataset=dataset, snapshot_id=snapshot))
    assert result["total"] == len(rows)
    assert [r["payload"]["source_fields"] for r in result["records"]] == rows
    assert all(r["source_refs"][0]["content_hash"] == digest(rows) for r in result["records"])
    assert all(r["source_refs"][0]["source_url"] is None for r in result["records"])
    assert facts_db.scalar(
        select(func.count()).select_from(DataHubRowDB).where(DataHubRowDB.snapshot_id == snapshot)
    ) == len(rows)


def test_batches_minutes_adjustments_and_legacy_history(facts_db):
    seed(facts_db)
    rows, params = dataset_case("daily_quotes")
    facts_db.add(
        StockDailyBarDB(
            symbol="000001.SZ",
            trade_date=datetime(2026, 9, 2, tzinfo=UTC),
            source="cjpy",
            close=99,
            raw_payload={"legacy": True},
        )
    )
    facts_db.flush()
    save(facts_db, "daily_quotes", rows, params)
    rows2 = [{**rows[0], "代码": "SZ000002"}]
    save(facts_db, "daily_quotes", rows2, {**params, "codes": ["000002.SZ"]})
    minute = [{**rows[0], "时间": "2026-09-02 09:35:00"}, {**rows[0], "时间": "2026-09-02 09:40:00"}]
    for rate in ("前复权", "后复权", "不复权"):
        save(facts_db, "daily_quotes", minute, {**params, "cycle": "5m", "rate": rate})
    service = DataHubService(facts_db)
    result = service.query(DataHubQuery(dataset="daily_quotes", limit=3))
    assert result["total"] == 8
    assert len(result["records"]) == 3
    assert (
        len(service.query(DataHubQuery(dataset="daily_quotes", offset=3, limit=3))["records"]) == 3
    )
    assert facts_db.scalar(select(func.count()).select_from(DataHubBarDB)) == 8
    legacy = facts_db.scalar(select(StockDailyBarDB).where(StockDailyBarDB.symbol == "000001.SZ"))
    assert legacy.close == 99
    assert legacy.raw_payload == {"legacy": True}


def test_quarantine_missing_values_and_empty_status(facts_db):
    seed(facts_db)
    rows, params = dataset_case("daily_quotes")
    bad = [
        {**rows[0], "close": None},
        {**rows[0], "代码": "SZ999999"},
        {**rows[0], "时间": "2030-01-01"},
    ]
    snapshot = save(facts_db, "daily_quotes", bad, params)
    service = DataHubService(facts_db)
    clean = service.query(DataHubQuery(dataset="daily_quotes", snapshot_id=snapshot))
    assert clean["freshness_status"] == "quarantined" and clean["records"] == []
    admin = service.query(
        DataHubQuery(dataset="daily_quotes", snapshot_id=snapshot), include_quarantined=True
    )
    assert len(admin["records"]) == 3
    assert admin["records"][0]["payload"]["close"] is None
    assert not facts_db.scalar(select(func.count()).select_from(DataHubBarDB))
    empty = save(facts_db, "daily_quotes", [], params)
    assert (
        service.query(DataHubQuery(dataset="daily_quotes", snapshot_id=empty))["freshness_status"]
        == "unavailable"
    )


def test_historical_identity_evidence_expands_validity(facts_db):
    save(facts_db, "stock_list", [{"value": "000001.SZ"}], {"date": "2026-09-02"})
    save(facts_db, "stock_list", [{"value": "000001.SZ"}], {"date": "2020-01-01"})
    facts_db.flush()
    assert (
        DataHubRepository(facts_db)._asset_id(
            "000001.SZ", datetime(2021, 1, 1, tzinfo=UTC), "daily_quotes"
        )
        == "stock:000001.SZ"
    )


def test_complete_index_revision_removes_old_members(facts_db):
    seed(facts_db)
    params = {"codes": ["000300.SH"], "date": "2026-09-02"}
    save(facts_db, "index_constituents", [{"value": "000001.SZ"}, {"value": "000002.SZ"}], params)
    save(
        facts_db, "index_constituents", [{"value": "000001.SZ"}], params, NOW + timedelta(seconds=1)
    )
    assert list(facts_db.scalars(select(IndexComponentSnapshotDB.component_symbol))) == [
        "000001.SZ"
    ]
    save(
        facts_db, "index_constituents", [{"value": "UNMAPPED"}], params, NOW + timedelta(seconds=2)
    )
    assert list(facts_db.scalars(select(IndexComponentSnapshotDB.component_symbol))) == [
        "000001.SZ"
    ]


def test_fact_and_outbox_rollback_together(facts_db):
    seed(facts_db)
    before = facts_db.scalar(select(func.count()).select_from(DomainEventDB))
    with pytest.raises(RuntimeError), facts_db.begin_nested():
        rows, params = dataset_case("daily_quotes")
        save(facts_db, "daily_quotes", rows, params)
        raise RuntimeError("transaction aborted")
    assert facts_db.scalar(select(func.count()).select_from(DataHubBarDB)) == 0
    assert facts_db.scalar(select(func.count()).select_from(DomainEventDB)) == before


def test_connector_batches_do_not_repeat_codes_or_destroy_identity(tmp_path):
    calls = []

    def query(dataset, **params):
        calls.append(params)
        return pd.DataFrame([{"code": "SZ000002", "时间": "2026-09-02", "close": 3, "extra": None}])

    connector = CjpyMarketConnector(adapter=SimpleNamespace(query=query))
    items = connector.discover(
        "daily_quotes",
        codes=["000001.SZ", "000001.SZ", "000002.SZ"],
        start_date="2026-09-02",
        end_date="2026-09-02",
    )
    assert len(items) == 2
    raw = connector.fetch("daily_quotes", items[0])
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(raw.data)
    assert json.loads(raw_path.read_text())["rows"][0]["code"] == "SZ000002"
    records = connector.normalize_bars(
        "daily_quotes", connector.parse_table(raw), str(raw_path), digest(raw.data)
    )
    assert records[0].payload["close"] == 3
    assert "asset_code_mismatch" in records[0].payload["quality_flags"]
    assert len(calls) == 1


def test_stale_lease_cannot_save_batch(facts_db):
    from core.contracts.datahub import DataHubSyncRequest

    job = DataHubService(facts_db).sync(DataHubSyncRequest(dataset="universes"))
    row = facts_db.get(ScheduledJobDB, job["job_id"])
    row.status = "running"
    row.lease_owner = "new-worker"
    row.lease_expires_at = NOW + timedelta(hours=1)
    row.attempt = 2
    facts_db.flush()
    repo = DataHubRepository(facts_db, job_fence=("old-worker", 1))
    with pytest.raises(ValueError, match="fencing"):
        repo.save_snapshot(
            "universes", [], [], {}, digest([]), "raw/test", NOW, job_id=row.job_id, batch_key="x"
        )
    assert facts_db.scalar(select(func.count()).select_from(DataHubSnapshotDB)) == 0


def test_research_tools_share_facts_and_cannot_write(facts_db):
    from core.contracts.research_workspace import SkillManifest
    from services.research_tool_registry import (
        build_production_research_tool_dispatcher,
        record_datahub_tool_evidence,
    )
    from services.runtime_provider_service import RuntimeBlockedError

    seed(facts_db)
    rows, params = dataset_case("daily_quotes")
    save(facts_db, "daily_quotes", rows, params)
    manifest = SkillManifest(
        skill_key="facts",
        name="facts",
        version="1",
        prompt_template="facts",
        input_schema={},
        output_schema={},
        allowed_tools=["internal:data_query"],
        status="enabled",
    )
    dispatcher = build_production_research_tool_dispatcher(facts_db)
    req = {"tool_id": "internal:data_query", "arguments": {"dataset": "daily_quotes"}}
    fingpt = dispatcher.dispatch(manifest, req)
    claw = dispatcher.dispatch(manifest, req)
    assert fingpt == claw
    with pytest.raises(RuntimeBlockedError):
        dispatcher.dispatch(manifest, {"tool_id": "internal:data_sync", "arguments": {}})
    with pytest.raises(RuntimeBlockedError):
        dispatcher.dispatch(
            manifest,
            {
                "tool_id": "internal:data_query",
                "arguments": {
                    "dataset": "daily_quotes",
                    "sql": "DELETE",
                    "include_quarantined": True,
                },
            },
        )
    facts_db.add(
        ResearchRunDB(
            run_id="evidence-test",
            template_key="a_share_deep_research",
            target_id="000001.SZ",
            subject_type="security",
            subject_payload={"subject_type": "security", "subject_id": "000001.SZ"},
            as_of=NOW,
            question="evidence",
            status="collecting",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    facts_db.flush()
    record_datahub_tool_evidence(
        facts_db, "evidence-test", "internal:data_query", req["arguments"], fingpt
    )
    run = facts_db.get(ResearchRunDB, "evidence-test")
    assert run.evidence_inputs[0]["source_ref"] == fingpt["records"][0]["evidence_ref"]
    assert (
        facts_db.scalar(
            select(ResearchArtifactDB).where(ResearchArtifactDB.run_id == "evidence-test")
        ).payload["result"]
        == fingpt
    )


def test_sdk_unnamed_dataframe_index_is_not_a_financial_metric():
    rows, params = dataset_case("factor_data")
    frame = pd.DataFrame(rows, index=pd.Index([0], dtype=object))
    connector = CjpyMarketConnector(adapter=SimpleNamespace(query=lambda *a, **kw: frame))
    item = connector.discover("factor_data", **params)[0]
    raw = connector.fetch("factor_data", item)
    assert json.loads(raw.data)["index"]["values"] == [0]
    table = connector.parse_table(raw)
    assert table.rows == rows
    normalized = connector.normalize_bars("factor_data", table, "raw:test", digest(raw.data))
    assert normalized[0].payload["quality_flags"] == []


def test_response_budget_pages_without_losing_fields(facts_db):
    rows = [{"description": "数据" * 2000, "name": str(i)} for i in range(50)]
    save(facts_db, "tables", rows)
    service = DataHubService(facts_db)
    page = service.query_for_tools(DataHubQuery(dataset="tables"))
    assert 0 < len(page["records"]) < 50
    assert len(json.dumps(page, ensure_ascii=False)) < 64000
    assert page["records"][0]["payload"]["source_fields"] == rows[0]
    next_page = service.query_for_tools(DataHubQuery(dataset="tables", offset=page["next_offset"]))
    assert next_page["records"][0]["fact_id"] != page["records"][-1]["fact_id"]


def test_api_permissions_validation_and_pagination(tmp_path, request):
    from data_layer.repositories.base import Base

    engine = create_engine(
        "sqlite:///" + str(tmp_path / "api.db"), connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    db_session = Session(engine)
    request.addfinalizer(engine.dispose)
    request.addfinalizer(db_session.close)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.configuration_security import CONFIGURATION_CSRF_TOKEN
    from app.api.routes.datahub import get_datahub, router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_datahub] = lambda: DataHubService(db_session)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/datahub/sources").json()["count"] == 14
        assert len(client.get("/api/datahub/catalog").json()["datasets"]) == 17
        assert client.get("/api/datahub/records?dataset=unknown").status_code == 422
        assert client.post("/api/datahub/runs", json={"dataset": "universes"}).status_code == 403
        headers = {"X-AlphaFoundry-Config-Token": CONFIGURATION_CSRF_TOKEN}
        response = client.post(
            "/api/datahub/runs",
            json={"dataset": "universes", "idempotency_key": "same"},
            headers=headers,
        )
        assert response.status_code == 202, response.text
        repeat = client.post(
            "/api/datahub/runs",
            json={"dataset": "universes", "idempotency_key": "same"},
            headers=headers,
        )
        assert repeat.json()["job_id"] == response.json()["job_id"]
        changed = client.post(
            "/api/datahub/runs",
            json={"dataset": "tables", "idempotency_key": "same"},
            headers=headers,
        )
        assert changed.status_code == 409
        assert (
            client.post(
                "/api/datahub/runs",
                json={"dataset": "tables", "params": {"token": "secret"}},
                headers=headers,
            ).status_code
            == 422
        )


def test_partial_failure_retries_only_unsaved_batches(facts_db, monkeypatch, tmp_path):
    from contextlib import contextmanager

    from core.contracts.ingestion_record import HealthStatus
    from data_layer.repositories import base
    from data_layer.repositories.research_workspace_repository import ResearchWorkspaceRepository
    from services import datahub_service
    from services.scheduler_coordinator import SchedulerCoordinator

    seed(facts_db)

    @contextmanager
    def session_scope():
        yield facts_db
        facts_db.flush()

    monkeypatch.setattr(base, "db_session", session_scope)
    now = [datetime.now(UTC)]
    coordinator = SchedulerCoordinator(
        ResearchWorkspaceRepository(facts_db), clock=lambda: now[0], retry_base_seconds=1
    )
    coordinator.register_handler("datahub.ingest", datahub_service.execute_datahub_job)
    calls = []

    def fetch(self, dataset, item, **params):
        code = item.params["codes"][0]
        calls.append(code)
        if code == "000002.SZ" and calls.count(code) == 1:
            self._record_failure(item.item_id, "sample_failure")
            raise RuntimeError("sample_failure")
        rows = [{"code": code, "date": "2026-09-02", "close": 1}]
        from core.connectors.base import RawObject

        return RawObject(
            data=json.dumps(rows),
            content_type="application/json",
            source_uri="cjpy:test",
            fetched_at=datetime.now(UTC),
            metadata={
                "dataset": dataset,
                "columns": list(rows[0]),
                "params": item.params,
                "observed_at": datetime.now(UTC).isoformat(),
            },
        )

    monkeypatch.setattr(CjpyMarketConnector, "_fetch_with_retry", fetch)
    monkeypatch.setattr(CjpyMarketConnector, "health_check", lambda self: HealthStatus.HEALTHY)

    def raw_store(self, raw):
        path = tmp_path / (digest(raw.data) + ".json")
        path.write_text(raw.data)
        return str(path)

    monkeypatch.setattr(CjpyMarketConnector, "save_raw", raw_store)
    job = DataHubService(facts_db).sync(
        DataHubSyncRequest(
            dataset="daily_quotes",
            params={
                "codes": ["000001.SZ", "000002.SZ"],
                "start_date": "2026-09-02",
                "end_date": "2026-09-02",
            },
        )
    )
    now[0] += timedelta(seconds=1)
    first = coordinator.run_due("test-worker", lease_seconds=60, claim_now=now[0])[0]
    assert first.status.value == "idle"
    now[0] += timedelta(seconds=2)
    second = coordinator.run_due("test-worker", lease_seconds=60, claim_now=now[0])[0]
    assert second.status.value == "succeeded"
    assert calls == ["000001.SZ", "000002.SZ", "000002.SZ"]
    report = DataHubService(facts_db).runs(job["job_id"])
    assert report["saved"] == 2 and report["failed_batches"] == 0


def test_quarantine_can_be_revalidated_after_identity_arrives(facts_db):
    rows, params = dataset_case("daily_quotes")
    snapshot = save(facts_db, "daily_quotes", rows, params)
    service = DataHubService(facts_db)
    assert service.query(DataHubQuery(dataset="daily_quotes"))["total"] == 0
    seed(facts_db)
    assert save(facts_db, "daily_quotes", rows, params, NOW + timedelta(seconds=1)) == snapshot
    result = service.query(DataHubQuery(dataset="daily_quotes"))
    assert result["total"] == 1 and result["quarantined_count"] == 0
    assert result["records"][0]["payload"]["source_fields"] == rows[0]
    assert (
        facts_db.scalar(
            select(func.count())
            .select_from(DomainEventDB)
            .where(DomainEventDB.aggregate_id == snapshot)
        )
        == 2
    )


def test_fund_list_rejects_stock_identity_and_accepts_open_fund_code_namespace(facts_db):
    seed(facts_db)
    snapshot = save(
        facts_db,
        "fund_list",
        [{"value": "SZ000001"}, {"value": "OF000001"}],
        {"date": "2026-09-02"},
    )
    result = DataHubService(facts_db).query(DataHubQuery(dataset="fund_list", snapshot_id=snapshot))
    assert result["total"] == 1 and result["quarantined_count"] == 1
    assert result["records"][0]["asset_id"] == "fund:000001.OF"


def test_factor_recheck_preserves_shanghai_business_day_and_latest_value(facts_db):
    from data_layer.repositories.models import FactorValueDB

    seed(facts_db)
    rows, params = dataset_case("factor_data")
    save(facts_db, "factor_data", rows, params)
    facts_db.expire_all()
    save(facts_db, "factor_data", rows, params, NOW + timedelta(seconds=2))
    older = [{**rows[0], "因子": 0.5}]
    save(facts_db, "factor_data", older, params, NOW + timedelta(seconds=1))
    values = list(facts_db.scalars(select(FactorValueDB)))
    assert len(values) == 1 and values[0].as_of_date.isoformat() == "2026-09-02"
    assert float(values[0].value) == 1.2


def test_bounded_query_rejects_unknown_market_and_null_optional_dates():
    with pytest.raises(ValueError):
        DataHubQuery(dataset="daily_quotes", symbol="000001.XX")
    DataHubSyncRequest(
        dataset="factor_data",
        params={"codes": ["SZ000001"], "factors": ["x"], "date": "2026-09-02", "dates": None},
    )


def test_equivalent_index_queries_cannot_restore_an_older_response(facts_db):
    seed(facts_db)
    params = {"codes": ["000300.SH"], "date": "2026-09-02"}
    save(
        facts_db, "index_constituents", [{"value": "SZ000002"}], params, NOW + timedelta(seconds=2)
    )
    save(
        facts_db,
        "index_constituents",
        [{"value": "SZ000001"}],
        {"codes": ["SH000300"], "date": "20260902"},
        NOW,
    )
    assert list(facts_db.scalars(select(IndexComponentSnapshotDB.component_symbol))) == [
        "000002.SZ"
    ]


def test_factor_query_only_exposes_current_fields_with_archive_lookup(facts_db):
    seed(facts_db)
    params = {
        "codes": ["SZ000001"],
        "date": "2026-09-02",
        "factors": ["a", "b"],
        "column_units": {"a": "倍", "b": "倍"},
    }
    original = save(
        facts_db, "factor_data", [{"代码": "SZ000001", "截止日": "20260902", "a": 10, "b": 20}], params
    )
    save(
        facts_db,
        "factor_data",
        [{"代码": "SZ000001", "截止日": "20260902", "a": 11}],
        {**params, "date": None, "dates": ["2026-09-02"], "factors": ["a"]},
        NOW + timedelta(seconds=1),
    )
    service = DataHubService(facts_db)
    records = service.query(DataHubQuery(dataset="factor_data"))["records"]
    assert sorted(
        r["payload"]["source_fields"]["a"] for r in records if "a" in r["payload"]["source_fields"]
    ) == [11]
    assert any(r["payload"]["source_fields"].get("b") == 20 for r in records)
    archived = service.query(DataHubQuery(dataset="factor_data", snapshot_id=original))
    assert archived["records"][0]["payload"]["source_fields"]["a"] == 10


def test_trading_calendar_cycle_query_uses_snapshot_semantics(facts_db):
    rows, params = dataset_case("trading_days")
    save(facts_db, "trading_days", rows, params)
    service = DataHubService(facts_db)
    assert service.query(DataHubQuery(dataset="trading_days", cycle="D"))["total"] == 1
    assert service.query(DataHubQuery(dataset="trading_days", cycle="W"))["total"] == 0
