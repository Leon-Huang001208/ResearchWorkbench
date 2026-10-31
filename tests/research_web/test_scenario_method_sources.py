"""Real byte readback for owned methods, never a fabricated source verdict."""

import hashlib
import json
from pathlib import Path

import pytest

from app.research_web.skills._shared.source_actions import (
    inspect_company_sources,
    inspect_news_sources,
    inspect_research_materials,
    save_ledger,
)


def context(tmp_path, method="owned-news-evidence", text="Actual acquired event body"):
    folder = tmp_path / "inputs" / "methods"
    folder.mkdir(parents=True)
    raw = text.encode()
    (folder / "source.txt").write_bytes(raw)
    return {
        "schema": "research_method_source_context_v1",
        "method_id": method,
        "method_version": "1.0.0",
        "subject": {"kind": "stock", "identity": "MSFT.US"},
        "as_of": "2026-10-27",
        "sources": [
            {
                "source_id": "web:" + "a" * 24,
                "path": "inputs/methods/source.txt",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "locator": f"bytes:0-{len(raw)}",
                "publication_date": "2024-07-30",
                "category": (
                    "news-body" if method == "owned-news-evidence" else "company-disclosures"
                ),
                "full_text": True,
            }
        ],
    }


@pytest.mark.parametrize(
    "method,action",
    [
        ("owned-company-evidence", inspect_company_sources),
        ("owned-news-evidence", inspect_news_sources),
        ("owned-research-prep", inspect_research_materials),
    ],
)
def test_method_actually_reads_original_and_retains_missing_material(tmp_path, method, action):
    value = context(tmp_path, method)
    ledger = action(tmp_path, value)
    assert ledger["counts"]["checked_sources"] == 1
    assert ledger["authority"] == "analytical_output_only"
    assert ledger["research_quality"] == "NOT_RUN"
    assert ledger["status"] == "incomplete"
    assert ledger["missing"]
    (tmp_path / value["sources"][0]["path"]).write_text("changed")
    with pytest.raises(ValueError, match="hash_mismatch"):
        action(tmp_path, value)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("path", "/etc/passwd", "path_invalid"),
        ("path", "inputs/../source.txt", "path_invalid"),
        ("publication_date", "2026-10-28", "after_cutoff"),
        ("locator", "bytes:0-1", "locator_invalid"),
        ("rights", "allowed", "context_invalid"),
        ("provider", "trusted", "context_invalid"),
        ("content", "forged body", "context_invalid"),
    ],
)
def test_descriptor_claims_cannot_override_original(tmp_path, field, value, error):
    selected = context(tmp_path)
    selected["sources"][0][field] = value
    with pytest.raises(ValueError, match=error):
        inspect_news_sources(tmp_path, selected)


def test_title_only_and_unknown_publication_keep_gaps(tmp_path):
    selected = context(tmp_path, text="Headline only")
    selected["sources"][0].update(full_text=False, publication_date=None)
    ledger = inspect_news_sources(tmp_path, selected)
    assert {m["code"] for m in ledger["missing"]} >= {
        "source_full_text_unavailable",
        "publication_date_unknown",
    }


def test_company_refuses_foreign_security_and_unverified_accounting(tmp_path):
    selected = context(tmp_path, "owned-company-evidence", "Income statement USD millions")
    selected["sources"][0].update(
        category="financials",
        security="600600.SH",
        report_period="2024-06-30",
        unit="millions",
        currency="USD",
        basis="annual",
    )
    with pytest.raises(ValueError, match="security_mismatch"):
        inspect_company_sources(tmp_path, selected)
    selected["sources"][0]["security"] = "MSFT.US"
    ledger = inspect_company_sources(tmp_path, selected)
    assert any(m["code"] == "financial_basis_unverified" for m in ledger["missing"])


@pytest.mark.parametrize(
    "filename,method,action",
    [
        ("msft-income.txt", "owned-company-evidence", inspect_company_sources),
        ("fomc-september.txt", "owned-news-evidence", inspect_news_sources),
        ("msft-cashflows.txt", "owned-research-prep", inspect_research_materials),
    ],
)
def test_official_excerpt_bytes_keep_original_fixture_provenance(
    tmp_path, filename, method, action
):
    fixtures = Path(__file__).parent / "fixtures" / "business-evidence"
    provenance = next(
        row
        for row in json.loads((fixtures / "sources.json").read_text())["inputs"]
        if row["file"] == filename
    )
    raw = (fixtures / filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == provenance["sha256"]
    selected = context(tmp_path, method, raw.decode())
    ledger = action(tmp_path, selected)
    assert ledger["sources"][0]["sha256"] == provenance["sha256"]
    assert ledger["counts"]["input_bytes"] == len(raw)
    assert ledger["research_quality"] == "NOT_RUN"


def test_links_and_hardlinks_cannot_replace_selected_original(tmp_path):
    selected = context(tmp_path)
    original = tmp_path / selected["sources"][0]["path"]
    link = original.parent / "link.txt"
    link.symlink_to(original)
    selected["sources"][0]["path"] = "inputs/methods/link.txt"
    with pytest.raises(ValueError, match="path_invalid"):
        inspect_news_sources(tmp_path, selected)
    link.unlink()
    link.hardlink_to(original)
    selected["sources"][0]["path"] = "inputs/methods/source.txt"
    with pytest.raises(ValueError, match="file_invalid"):
        inspect_news_sources(tmp_path, selected)


def test_output_symlink_is_rejected_before_creating_external_directories(tmp_path):
    selected = context(tmp_path)
    ledger = inspect_news_sources(tmp_path, selected)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "outputs").symlink_to(outside)
    with pytest.raises(ValueError, match="output_path_invalid"):
        save_ledger(tmp_path, ledger, "e" * 32)
    assert not list(outside.iterdir())
