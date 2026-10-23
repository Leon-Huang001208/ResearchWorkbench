"""Offline evidence rules: no model, network, vendor or inferred identities."""

from copy import deepcopy

import pytest

from app.research_web.dossiers.signals import evaluate_signals


def dossier():
    return {
        "id": "11111111-1111-4111-8111-111111111111",
        "subject": {"kind": "company", "key": "600519.SH", "label": "贵州茅台"},
        "records": [],
        "evidence": [{"id": "e1", "state": "available", "sha256": "a" * 64}],
    }


def material(capability="announcements", **updates):
    manifest = {
        "capability": capability,
        "source": "tinysoft",
        "provider": "tinysoft",
        "status": "complete",
        "as_of": "2026-10-22",
        "retrieved_at": "2026-10-22T10:00:00+00:00",
        "pagination_complete": True,
        "row_count": 1,
        "provider_total": 1,
        "query": {"parameters": {"asset": "600519.SH"}},
    }
    manifest.update(updates)
    return {
        "manifest": manifest,
        "rows": [{"asset": "600519.SH", "published_at": "2026-10-22", "title": "三季报公告"}],
    }


def test_native_announcement_is_an_evidence_linked_review_signal():
    result = evaluate_signals(dossier(), {"e1": material()}, "2026-10-23")
    signal = result["items"][0]
    assert signal["evidence_ids"] == ["e1"]
    assert signal["state"] == "open"
    assert signal["kind"] == "signal"
    assert signal["dossier_id"] == dossier()["id"]
    assert result["coverage"]["eligible"] is True
    assert "待核验" in signal["body"]
    assert evaluate_signals(dossier(), {"e1": material()}, "2026-10-23") == result


@pytest.mark.parametrize("asset", ["000858.SZ", "600519.SZ", "贵州茅台", "600519"])
def test_names_and_market_ambiguity_never_match_a_security(asset):
    data = material()
    data["rows"][0]["asset"] = asset
    result = evaluate_signals(dossier(), {"e1": data}, "2026-10-23")
    assert result["items"] == []
    assert any(item["code"] == "security_identity_mismatch" for item in result["missing"])


def test_clue_only_mcp_output_cannot_become_a_numeric_or_chain_fact():
    data = material(
        "risk_alerts",
        snapshot_kind="mcp_evidence",
        provider_metadata={"admission": {"status": "clue"}},
    )
    data["rows"] = [{"asset": "600519.SH", "risk_level": "high"}]
    result = evaluate_signals(dossier(), {"e1": data}, "2026-10-23")
    assert not result["items"]
    assert any(item["code"] == "source_not_admitted" for item in result["missing"])


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"pagination_complete": False}, "coverage_incomplete"),
        ({"provider_total": 21}, "coverage_incomplete"),
        ({"as_of": "2026-10-24"}, "future_evidence"),
        ({"as_of": "2026-09-01"}, "stale_evidence"),
    ],
)
def test_missing_stale_future_and_truncated_are_not_no_signal(updates, code):
    result = evaluate_signals(dossier(), {"e1": material(**updates)}, "2026-10-23")
    assert not result["items"]
    assert any(item["code"] == code for item in result["missing"])
    assert result["coverage"]["eligible"] is False


def test_retrieval_time_cannot_replace_publication_time():
    data = material()
    data["rows"][0].pop("published_at")
    result = evaluate_signals(dossier(), {"e1": data}, "2026-10-23")
    assert not result["items"]
    assert any(item["code"] == "publication_time_unknown" for item in result["missing"])


def test_duplicate_articles_preserve_both_sources_without_double_counting():
    d = dossier()
    d["evidence"].append({"id": "e2", "state": "available", "sha256": "b" * 64})
    other = material(source="akshare", provider="akshare")
    result = evaluate_signals(d, {"e1": material(), "e2": other}, "2026-10-23")
    assert len(result["items"]) == 1
    assert result["items"][0]["evidence_ids"] == ["e1", "e2"]


def test_negative_growth_stays_a_number_and_never_becomes_growth_prose():
    data = material("financials")
    data["rows"] = [
        {
            "asset": "600519.SH",
            "published_at": "2026-10-22",
            "report_period": "2026-06-30",
            "net_profit_yoy": -2.0,
        }
    ]
    before = deepcopy(data)
    result = evaluate_signals(dossier(), {"e1": data}, "2026-10-23")
    assert len(result["items"]) == 1
    assert "微增" not in result["items"][0]["body"]
    assert "已取得" in result["items"][0]["body"]
    assert data == before


def test_catalyst_watch_requires_current_evidence_and_does_not_edit_opinion():
    d = dossier()
    d["records"] = [
        {
            "id": "r1",
            "kind": "catalyst",
            "title": "财报观察",
            "body": "等待公开披露",
            "state": "open",
            "watch_from": "2026-10-24",
            "watch_until": "2026-10-30",
            "evidence_ids": ["e1"],
        }
    ]
    before = deepcopy(d)
    result = evaluate_signals(d, {"e1": material()}, "2026-10-23")
    assert any(item["rule"] == "watch_window" for item in result["items"])
    assert d == before
    d["evidence"][0]["state"] = "missing"
    unavailable = evaluate_signals(d, {}, "2026-10-23")
    assert not any(item["rule"] == "watch_window" for item in unavailable["items"])


def test_missing_forecast_data_is_explicit_and_not_synthetic_expectations():
    result = evaluate_signals(dossier(), {}, "2026-10-23")
    assert not result["items"]
    assert result["missing"]
    assert result["coverage"]["eligible"] is False


def test_unchanged_watch_window_does_not_notify_each_scan_day():
    d = dossier()
    d["records"] = [
        {
            "id": "r1",
            "kind": "risk",
            "title": "同一风险",
            "state": "open",
            "watch_from": "2026-10-24",
            "watch_until": "2026-10-30",
            "evidence_ids": ["e1"],
        }
    ]
    first = evaluate_signals(d, {"e1": material()}, "2026-10-23")
    second = evaluate_signals(d, {"e1": material()}, "2026-10-24")
    window = lambda result: next(row for row in result["items"] if row["rule"] == "watch_window")
    assert window(first)["as_of"] != window(second)["as_of"]
    assert window(first)["fingerprint"] == window(second)["fingerprint"]
    ended = evaluate_signals(d, {"e1": material()}, "2026-10-31")
    assert window(ended)["fingerprint"] != window(first)["fingerprint"]


def test_invalid_cutoff_and_oversized_rows_are_rejected():
    with pytest.raises(ValueError):
        evaluate_signals(dossier(), {}, "not-a-date")
    data = material()
    data["rows"] = [{}] * 1001
    with pytest.raises(ValueError, match="budget"):
        evaluate_signals(dossier(), {"e1": data}, "2026-10-23")
