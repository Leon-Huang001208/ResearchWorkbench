"""Weekly calculations use Host observations and never model-provided facts."""

import hashlib
from types import SimpleNamespace

import pytest

from app.research_web.report_workflows import evidence
from app.research_web.report_workflows.models import WorkflowError
from app.research_web.resources.research_report_plan import (
    _report_evidence_limit,
    _summary_calculation,
)


def bundle():
    return {
        "assessment": {
            "status": "passed",
            "observations": [
                {
                    "id": "domestic_000300",
                    "display_name": "沪深300",
                    "kind": "price_return",
                    "as_of": "2026-10-23",
                    "baseline_date": "2026-10-16",
                    "close": "101.25",
                    "baseline_close": "100",
                    "return_pct": "1.25",
                    "unit": "index_point",
                }
            ],
        }
    }


def test_fact_index_is_rebuilt_and_tampering_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "session"
    (root / "inputs/report-workflow").mkdir(parents=True)

    class Store:
        def directory(self, sid):
            return root

        def files(self, sid):
            return []

        def save(self):
            pass

        def open_file(self, sid, fid):
            assert fid == hashlib.sha256(evidence.FACTS_PATH.encode()).hexdigest()[:24]
            return (root / evidence.FACTS_PATH).open("rb"), "weekly-facts.txt"

    store = Store()
    store.root = tmp_path
    service = SimpleNamespace(store=store)
    monkeypatch.setattr(evidence, "_verified", lambda *_: bundle())
    monkeypatch.setattr(evidence, "_news_business_observations", lambda *_: [])
    evidence.prepare_weekly_evidence(service, "sid")
    observed = evidence.weekly_business_observations(
        service, "sid", task_id="a" * 24, contract_sha="b" * 64
    )
    assert len(observed) == 3
    assert observed[0]["heading"] == "沪深300"
    from app.research_web.resources.research_report_calculations import _primitive

    assert _primitive(observed[0])["value"] == "101.25"
    source = root / evidence.FACTS_PATH
    source.write_text(source.read_text().replace("101.25", "199.25"))
    with pytest.raises(WorkflowError):
        evidence.weekly_business_observations(
            service, "sid", task_id="a" * 24, contract_sha="b" * 64
        )


def test_mean_uses_actual_number_of_trading_observations():
    raw = [
        {
            "id": f"row{i}",
            "kind": "business_numeric",
            "metric": "weekly_raw_daily_amount",
            "unit": "CNY",
            "value": value,
            "source_ids": ["file:x"],
        }
        for i, value in enumerate(["12", "15", "21"])
    ]
    target = {
        "id": "mean",
        "kind": "business_numeric",
        "metric": "weekly_daily_mean_amount",
        "unit": "CNY",
        "value": "16",
        "source_ids": ["file:x"],
    }
    value, unit, _, _ = _summary_calculation(
        {"observations": raw},
        target,
        [{"id": "average", "operation": "mean", "operands": [r["id"] for r in raw]}],
        [0],
        {},
    )
    assert str(value) == "16"
    assert unit == "CNY"


def test_fact_evidence_is_registered_by_the_real_store(tmp_path, monkeypatch):
    from app.research_web.store import Store

    store = Store(tmp_path)
    sid = store.create("claw", "周报")["id"]
    (store.directory(sid) / "inputs/report-workflow").mkdir()
    service = SimpleNamespace(store=store)
    monkeypatch.setattr(evidence, "_verified", lambda *_: bundle())
    monkeypatch.setattr(evidence, "_news_business_observations", lambda *_: [])
    evidence.prepare_weekly_evidence(service, sid)
    files = store.files(sid)
    assert any(item["name"] == "weekly-facts.txt" for item in files)
    observed = evidence.weekly_business_observations(
        service, sid, task_id="a" * 24, contract_sha="b" * 64
    )
    assert observed and observed[0]["proofs"][0]["source_id"].startswith("file:")


def test_original_evidence_budget_stays_fixed_without_host_weekly_operands():
    assert _report_evidence_limit({"observations": []}) == 40
    assert (
        _report_evidence_limit(
            {"observations": [{"metric": "weekly_close", "content": "model says passed"}]}
        )
        == 40
    )


def test_unknown_units_and_unverified_data_never_become_facts():
    value = bundle()
    value["assessment"]["observations"][0]["unit"] = None
    with pytest.raises(WorkflowError):
        evidence.weekly_fact_rows(value)
    value["assessment"]["status"] = "blocked_data"
    with pytest.raises(WorkflowError):
        evidence.weekly_fact_rows(value)


def test_news_gap_requires_exact_period_topic_and_verified_zero_results(monkeypatch):
    from app.research_web.report_workflows import weekly_quality

    monkeypatch.setattr(
        weekly_quality,
        "trusted_weekly_context",
        lambda *_: {
            "data_contract": {"period_start": "2026-10-19"},
            "as_of": "2026-10-23",
            "requirements": [{"id": "block_ai", "text": "人工智能"}],
            "news_block_ids": ["block_ai"],
        },
    )
    metadata = {
        "dataset_id": "verified-empty",
        "capability": "search_news",
        "status": "complete",
        "row_count": 0,
        "pagination_complete": True,
        "missing": [],
        "provider_metadata": {"requested_range_verified": True},
        "query": {
            "parameters": {
                "query": "人工智能",
                "start_date": "2026-10-19",
                "end_date": "2026-10-23",
            }
        },
    }
    hub = SimpleNamespace(
        list=lambda sid: [metadata], snapshots=SimpleNamespace(read=lambda *_: b"[]")
    )
    service = SimpleNamespace(datahub=hub)
    assert (
        evidence._empty_news_records(service, "sid")[0]["statement"] == "本期未取得足够可核验材料。"
    )
    metadata["provider_metadata"]["requested_range_verified"] = False
    assert evidence._empty_news_records(service, "sid") == []
    metadata["provider_metadata"]["requested_range_verified"] = True
    metadata["query"]["parameters"]["query"] = "无关主题"
    assert evidence._empty_news_records(service, "sid") == []
    metadata["query"]["parameters"]["query"] = "人工智能"
    metadata["row_count"] = 1
    assert evidence._empty_news_records(service, "sid") == []
