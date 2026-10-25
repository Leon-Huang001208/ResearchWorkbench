"""Closed source-qualified reference and original-bound profitability contracts."""

import hashlib
import json

import pytest

from app.research_web.datahub import providers_baostock_reference as reference
from app.research_web.datahub.providers import ProviderError


def raw_record():
    from app.research_web.datahub.providers_baostock import FINANCIAL_FIELDS

    row = dict.fromkeys(FINANCIAL_FIELDS.split(","), "1.0")
    row.update(code="sh.600000", statDate="2026-06-30", pubDate="2026-08-28")
    return row


def test_reference_is_exact_string_scoped_and_does_not_change_rows(monkeypatch):
    record = raw_record()
    monkeypatch.setattr(
        reference,
        "REFERENCE_CELL_HASHES",
        {
            field: hashlib.sha256(record[field].encode()).hexdigest()
            for field in ("netProfit", "MBRevenue")
        },
    )
    rows, missing = reference.profitability_projection(
        json.dumps([record]).encode(), "600000.SH", "2026-06-30"
    )
    evidence = rows[0]["reference_evidence"]
    assert not missing
    assert evidence["reporting_basis"] == "year_to_date"
    assert evidence["report_scope"] == "consolidated_group"
    assert evidence["period_start"] == "2026-01-01"
    assert evidence["issuer_unit_scale"] == 1000000
    assert evidence["historical_point_in_time"] is False
    assert rows[0]["publication_date"] == "2026-08-28"
    assert evidence["date_conflict"]["issuer_listing_claim"]["raw_capture_verified"] is False
    assert rows[0]["netProfit"] == 1.0
    record["netProfit"] = "1.00"
    altered, _ = reference.profitability_projection(
        json.dumps([record]).encode(), "600000.SH", "2026-06-30"
    )
    assert "reference_evidence" not in altered[0]
    record["code"] = "sh.600001"
    other, _ = reference.profitability_projection(
        json.dumps([record]).encode(), "600001.SH", "2026-06-30"
    )
    assert "reference_evidence" not in other[0]


@pytest.mark.parametrize("bad", [True, 1.0, "NaN", "Infinity"])
def test_profitability_rejects_non_native_numbers(bad):
    row = raw_record()
    row["netProfit"] = bad
    with pytest.raises(ProviderError):
        reference.profitability_projection(json.dumps([row]).encode(), "600000.SH", "2026-06-30")
