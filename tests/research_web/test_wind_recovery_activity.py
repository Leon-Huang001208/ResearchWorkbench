"""Offline Wind maintenance evidence; never imports an Office application."""

from concurrent.futures import Future
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.research_web.datahub import providers_wind, worker_activity
from app.research_web.main import create_app


def host(monkeypatch):
    from app.research_web.datahub import providers_wind_api

    monkeypatch.setattr(providers_wind_api, "activity_witness", lambda: {"active": False})
    app = create_app()
    app.state.research = SimpleNamespace(
        running={},
        approvals={},
        questions={},
        source_requests={},
        store=SimpleNamespace(data={}),
        market=SimpleNamespace(activity_witness=lambda: {"active": False}),
        report_workflows=SimpleNamespace(
            catalog=SimpleNamespace(data={"runs": {}}), runtime=SimpleNamespace(tasks={})
        ),
        asset_workspace=SimpleNamespace(directory=SimpleNamespace(active=False), tasks={}),
        datahub=SimpleNamespace(tasks={}, storage_runner=None, directory_tasks=set()),
    )
    return app


@pytest.mark.parametrize("done", [False, True])
def test_poison_keeps_future_and_cleanup_separate(monkeypatch, done):
    future = Future()
    if done:
        future.set_result(None)
    monkeypatch.setattr(providers_wind, "_WIND_OUTSTANDING", future)
    monkeypatch.setattr(providers_wind, "_WIND_POISONED", True)
    actual = TestClient(host(monkeypatch)).get("/api/research/resident").json()
    assert actual["active"] is (None if done else True)  # Both ordinary outcomes refuse idle.
    witness = actual["activity_witness"]
    assert witness["schema"] == "resident-activity-v1"
    assert witness["sources"]["wind"] == {
        "running": not done,
        "cleanup_unconfirmed": True,
    }
    assert all(value is False for key, value in witness["checks"].items() if key != "sdk_aggregate")


def test_source_failure_does_not_skip_other_source_evidence(monkeypatch):
    from app.research_web.datahub import providers_akshare, providers_baostock

    checked = []

    def failure():
        checked.append("akshare")
        raise RuntimeError("secret supplier error")

    def idle():
        checked.append("baostock")
        return ()

    monkeypatch.setattr(providers_akshare, "active_futures", failure)
    monkeypatch.setattr(providers_baostock, "active_futures", idle)
    witness = worker_activity.activity_witness()
    assert checked == ["akshare", "baostock"]
    assert witness["akshare"]["running"] is None
    assert witness["baostock"]["running"] is False
    assert "secret" not in str(witness)


def test_host_checks_do_not_skip_after_base_activity_failure(monkeypatch):
    app = host(monkeypatch)
    app.state.research.running = None
    app.state.research.questions = {"question": object()}
    actual = TestClient(app).get("/api/research/resident").json()
    assert actual["active"] is True
    checks = actual["activity_witness"]["checks"]
    assert checks["research_tasks"] is None
    assert checks["questions"] is True
    assert checks["market"] is False


@pytest.mark.parametrize(
    "running,poison,expected", [(True, False, True), (False, True, None), (True, True, True)]
)
def test_source_activity_arriving_after_aggregate_never_reports_idle(
    monkeypatch, running, poison, expected
):
    future = Future()
    if not running:
        future.set_result(None)
    monkeypatch.setattr(providers_wind, "_WIND_OUTSTANDING", None)
    monkeypatch.setattr(providers_wind, "_WIND_POISONED", False)

    def aggregate_before_activity_arrives():
        # Controlled interleaving: the aggregate's old empty observation is
        # returned just as a real tracked Future / cleanup poison is published.
        monkeypatch.setattr(providers_wind, "_WIND_OUTSTANDING", future)
        monkeypatch.setattr(providers_wind, "_WIND_POISONED", poison)
        return ()

    monkeypatch.setattr(worker_activity, "active_futures", aggregate_before_activity_arrives)
    actual = TestClient(host(monkeypatch)).get("/api/research/resident").json()
    assert actual["activity_witness"]["checks"]["sdk_aggregate"] is False
    assert actual["activity_witness"]["sources"]["wind"]["running"] is running
    assert actual["active"] is expected


def test_source_becomes_unknown_after_aggregate_never_reports_idle(monkeypatch):
    from app.research_web.datahub import providers_cjpy

    monkeypatch.setattr(worker_activity, "active_futures", lambda: ())

    def unknown():
        raise RuntimeError("unavailable observation")

    monkeypatch.setattr(providers_cjpy, "active_futures", unknown)
    actual = TestClient(host(monkeypatch)).get("/api/research/resident").json()
    assert actual["activity_witness"]["checks"]["sdk_aggregate"] is False
    assert actual["activity_witness"]["sources"]["tinysoft"]["running"] is None
    assert actual["active"] is None


@pytest.mark.parametrize(
    "missing",
    [
        "source_requests",
        "report_workflows",
        "report_runtime_tasks",
        "report_catalog_data",
        "report_catalog_runs",
    ],
)
def test_missing_host_check_is_unknown_in_final_active(monkeypatch, missing):
    app = host(monkeypatch)
    if missing == "report_runtime_tasks":
        del app.state.research.report_workflows.runtime.tasks
    elif missing == "report_catalog_data":
        del app.state.research.report_workflows.catalog.data
    elif missing == "report_catalog_runs":
        del app.state.research.report_workflows.catalog.data["runs"]
    else:
        delattr(app.state.research, missing)
    actual = TestClient(app).get("/api/research/resident").json()
    key = "source_requests" if missing == "source_requests" else "reports"
    assert actual["activity_witness"]["checks"][key] is None
    assert actual["active"] is None
