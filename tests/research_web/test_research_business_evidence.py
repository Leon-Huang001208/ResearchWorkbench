"""Business observations are deterministic projections of actual input bytes only."""

import hashlib

import pytest

from app.research_web.research_business_evidence import business_observations as observe


def business_observations(inputs):
    return observe(inputs, scope="fixture-session-task")


def observed(text, name="a"):
    return {
        "id": "file:" + name * 24,
        "source_id": "file:" + name * 24,
        "content": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def test_business_prompt_index_remains_bounded_and_obeys_source_scope(tmp_path):
    import json
    from types import SimpleNamespace

    from app.research_web.research_quality import make_contract
    from app.research_web.research_quality_service import business_prompt_index
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "business index")["id"]
    (store.directory(sid) / "inputs/cpi.md").write_text(CPI)
    contract = make_contract("a" * 24, "Actual CPI", ["Facts"], "2026-10-19", "quick")
    result = business_prompt_index(SimpleNamespace(store=store), sid, contract)
    assert result["total"] >= 40 and len(json.dumps(result, ensure_ascii=False).encode()) <= 24000
    assert all(row["source_ids"] and "preview_truncated" in row for row in result["observations"])
    assert not {"passed", "coverage", "quality"} & result.keys()
    store.session(sid)["source_scope"] = ["datahub"]
    assert business_prompt_index(SimpleNamespace(store=store), sid, contract)["observations"] == []


def test_initial_business_snapshot_is_readable_without_literal_copying(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from app.research_web.research_quality import make_contract
    from app.research_web.research_quality_service import write_business_snapshot
    from app.research_web.resources.research_report import load_business_evidence
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "initial projection")["id"]
    (store.directory(sid) / "inputs" / "annual.md").write_text(ANNUAL)
    contract = make_contract("a" * 24, "Cash flow", ["Cash flow"], "2026-10-19", "quick")
    write_business_snapshot(SimpleNamespace(store=store), sid, contract)
    monkeypatch.chdir(store.directory(sid))
    result = load_business_evidence(contract["task_id"], contract["sha256"])
    assert any(row["metric"] == "task_defined_fcf" for row in result["observations"])
    assert not {"status", "quality", "research_accepted"} & set(result)
    with pytest.raises(ValueError):
        load_business_evidence("b" * 24, contract["sha256"])
    from app.research_web.research_evidence import evidence_index
    from app.research_web.research_quality_service import quality_result
    from app.research_web.resources.research_report import business_evidence, write_research_report

    projected = next(row for row in result["observations"] if row["metric"] == "task_defined_fcf")
    projected["content"] = projected["content"].replace(projected["value"], "123456", 1)
    projected["value"] = "123456"
    projected["sha256"] = hashlib.sha256(projected["content"].encode()).hexdigest()
    forged = {
        "task_id": contract["task_id"],
        "title": "Forged snapshot",
        "as_of": contract["as_of"],
        "sources": result["sources"],
        **business_evidence([projected], {projected["id"]: ["r1"]}),
    }
    write_research_report(store.directory(sid) / "outputs", forged)
    assert (
        quality_result(
            SimpleNamespace(store=store),
            sid,
            {"research_contract": contract},
            store.files(sid),
            evidence_index(store.files(sid), [], []),
        )["status"]
        != "passed"
    )
    store.session(sid)["source_scope"] = ["web"]
    write_business_snapshot(SimpleNamespace(store=store), sid, contract)
    assert load_business_evidence(contract["task_id"], contract["sha256"])["observations"] == []
    path = store.directory(sid) / "resources" / "research_evidence.json"
    raw = json.loads(path.read_text())
    raw["quality"] = "passed"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_business_evidence(contract["task_id"], contract["sha256"])


def test_business_snapshot_refuses_linked_resource_directory(tmp_path):
    from types import SimpleNamespace

    from app.research_web.research_quality import make_contract
    from app.research_web.research_quality_service import write_business_snapshot
    from app.research_web.store import Store, StoreError

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "linked resource")["id"]
    outside = tmp_path / "outside"
    outside.mkdir()
    resource = store.directory(sid) / "resources"
    if resource.exists():
        resource.rmdir()
    resource.symlink_to(outside, target_is_directory=True)
    contract = make_contract("a" * 24, "Facts", ["Facts"], "2026-10-19", "quick")
    with pytest.raises(StoreError):
        write_business_snapshot(SimpleNamespace(store=store), sid, contract)
    assert not list(outside.iterdir())


def metrics(rows):
    return {
        (r["metric"], r.get("period")): r["value"] for r in rows if r["kind"] == "business_numeric"
    }


ANNUAL = """| (In millions) | Year Ended June 30, |
| --- | --- |
| 2024 | 2023 | 2022 |
| --- | --- | --- |
| ElementName | Operations | | | |
| us-gaap:NetCashProvidedByUsedInOperatingActivities | Net cash from operations | 118548 | 87582 | 89035 |
| ElementName | Financing | | | |
| us-gaap:ProceedsFromIssuanceOfCommonStock | Common stock issued | 2002 | 1866 | 1841 |
| us-gaap:PaymentsForRepurchaseOfCommonStock | Common stock repurchased | (17254) | (22245) | (32696) |
| us-gaap:PaymentsOfDividendsCommonStock | Common stock cash dividends paid | (21771) | (19800) | (18135) |
| us-gaap:ProceedsFromPaymentsForOtherFinancingActivities | Other | (734) | (3756) | (9886) |
| us-gaap:NetCashProvidedByUsedInFinancingActivities | Net cash used in financing | (37757) | (43935) | (58876) |
| ElementName | Investing | | | |
| us-gaap:PaymentsToAcquirePropertyPlantAndEquipment | Additions to property and equipment | (44477) | (28107) | (23886) |
"""


def test_financial_table_joins_real_headers_and_signed_rows_without_guessing_currency():
    rows = business_observations([observed(ANNUAL)])
    data = metrics(rows)
    assert data["task_defined_fcf", "2024"] == "74071"
    assert data["cash_shareholder_return", "2024"] == "39025"
    assert data["financing_reconciliation_difference", "2024"] == "0"
    assert all(r["unit"] == "millions" for r in rows if r.get("metric") == "task_defined_fcf")
    assert all(r["source_id"] == "file:" + "a" * 24 for r in rows)


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.replace("2024 | 2023", "2024 | 2024"),
        lambda s: s.replace("(44477)", "NaN"),
        lambda s: s.replace("Year Ended June 30,", "Quarter Ended June 30,"),
        lambda s: s + s.splitlines()[8] + "\n",
    ],
)
def test_ambiguous_or_unsupported_annual_tables_produce_no_numeric_observations(change):
    assert not metrics(business_observations([observed(change(ANNUAL))]))


def test_actual_nonzero_financial_gap_cannot_be_normalized_to_zero():
    data = metrics(business_observations([observed(ANNUAL.replace("(37757)", "(37758)"))]))
    assert data["financing_reconciliation_difference", "2024"] == "-1"


CPI = """CONSUMER PRICE INDEX - DECEMBER 2024
| | Seasonally adjusted changes from preceding month | Un-<br>adjusted<br>12-mos.<br>ended<br>Dec. 2024 |
| --- | --- | --- |
| Jun.<br>2024 | Jul.<br>2024 | Aug.<br>2024 | Sep.<br>2024 | Oct.<br>2024 | Nov.<br>2024 | Dec.<br>2024 |
| --- | --- | --- | --- | --- | --- | --- |
| All items | -0.1 | 0.2 | 0.2 | 0.2 | 0.2 | 0.3 | 0.4 | 2.9 |
| All items less food and energy | 0.1 | 0.2 | 0.3 | 0.3 | 0.3 | 0.3 | 0.2 | 3.2 |
| Energy | -2.0 | 0.0 | -0.8 | -1.9 | 0.0 | 0.2 | 2.6 | -0.5 |
| Gasoline (all types) | -3.8 | 0.0 | -0.6 | -4.1 | -0.9 | 0.6 | 4.4 | -3.4 |
| Food | 0.2 | 0.2 | 0.1 | 0.4 | 0.2 | 0.4 | 0.3 | 2.5 |
Table A. Percent changes in CPI for All Urban Consumers (CPI-U): U.S. city average
"""


def test_cpi_core_yoy_uses_actual_unadjusted_header():
    rows = business_observations([observed(CPI)])
    data = metrics(rows)
    assert data["core_yoy_nsa_pct", "2024-12"] == "3.2"
    assert data["core_mom_sa_pct", "2024-12"] == "0.2"
    assert data["headline_mom_sa_pct", "2024-12"] == "0.4"
    assert not metrics(business_observations([observed(CPI.replace("Un-<br>adjusted", "Unknown"))]))


def test_failed_cpi_analysis_uses_actual_months_and_exact_percentage_points():
    from app.research_web.resources.research_report import select_business_evidence

    rows = business_observations([observed(CPI)])
    data = metrics(rows)
    assert data["headline_mom_sa_pct", "2024-11"] == "0.3"
    assert data["headline_mom_change_pp", "2024-12"] == "0.1"
    assert data["core_mom_change_pp", "2024-12"] == "-0.1"
    assert data["core_minus_headline_mom_sa_pp", "2024-12"] == "-0.2"
    assert data["core_minus_headline_yoy_nsa_pp", "2024-12"] == "0.3"
    bundle = {"observations": rows}
    with pytest.raises(ValueError, match="ambiguous"):
        select_business_evidence(bundle, {"headline_mom_sa_pct": ["r1"]})
    block = select_business_evidence(
        bundle, {"headline_mom_sa_pct@2024-11": ["r1"], "core_minus_headline_mom_sa_pp": ["r2"]}
    )
    assert len(block["numeric_claims"]) == 2
    assert len(block["coverage"]) == 2
    from app.research_web.research_quality import assess_quality, make_contract

    contract = make_contract(
        "a" * 24, "Compare actual CPI", ["Months", "Gap"], "2026-10-19", "quick"
    )
    source = observed(CPI)
    payload = {
        "task_id": contract["task_id"],
        "title": "Actual CPI",
        "as_of": "2026-10-19",
        "sources": [{"id": source["id"], "title": "Table A"}],
        **block,
    }
    assert (
        assess_quality(contract, payload, payload["sources"], [source, *rows])["status"] == "passed"
    )
    with pytest.raises(ValueError):
        select_business_evidence(bundle, {"unknown_metric": ["r1"]})


def test_real_cpi_previous_yoy_requires_complete_affirmative_paragraph():
    from pathlib import Path

    raw = (Path(__file__).parent / "fixtures/business-evidence/bls-cpi-dec2024.txt").read_text()
    data = metrics(business_observations([observed(raw)]))
    assert data["headline_yoy_nsa_pct", "2024-11"] == "2.7"
    assert data["headline_yoy_change_pp", "2024-12"] == "0.2"
    for bad in (
        raw.replace("The all items index rose", "It is false that:\n\nThe all items index rose"),
        raw.replace(
            "The all items index rose",
            "The following paragraph is hypothetical.\n\nThe all items index rose",
        ),
        raw + "\n\nThe preceding release is hypothetical.",
        raw.replace("The all items index rose", "It is false that the all items index rose"),
        raw.replace("ending November", "ending October"),
        raw.replace("rose 2.9 percent", "rose 9.9 percent"),
    ):
        data = metrics(business_observations([observed(bad)]))
        assert ("headline_yoy_nsa_pct", "2024-11") not in data


def test_nist_context_exposes_original_qualitative_evidence_without_certifying_translation():
    from app.research_web.resources.research_report import select_business_evidence

    text = "AI RMF\n\nGovernance is a cross-cutting function that enables organizations to manage risks.\n\nOrganizations cannot infer implementation from this framework."
    rows = business_observations([observed(text)])
    quotes = [r for r in rows if r["metric"] == "source_quote"]
    assert len(quotes) == 2
    assert any("cannot infer" in row["content"] for row in quotes)
    block = select_business_evidence({"observations": rows}, {quotes[0]["id"]: ["r1"]})
    assert block["sections"][0]["text"] == quotes[0]["content"]
    assert not block["numeric_claims"]
    assert not {"quality", "missing", "status"} & block.keys()
    from app.research_web.research_quality import assess_quality, make_contract

    contract = make_contract("a" * 24, "NIST", ["Governance"], "2026-10-19", "quick")
    payload = {
        "task_id": contract["task_id"],
        "title": "NIST",
        "as_of": "2026-10-19",
        "sources": [{"id": observed(text)["id"], "title": "NIST excerpt"}],
        **block,
    }
    assert (
        assess_quality(contract, payload, payload["sources"], [observed(text), *rows])["status"]
        == "passed"
    )
    payload["sections"][0]["text"] += "\n该企业已经全面通过治理认证。"
    assert (
        assess_quality(contract, payload, payload["sources"], [observed(text), *rows])["status"]
        != "passed"
    )


def statement(date, limits):
    # Synthetic publication-format fixture, not a claim about a real historical vote.
    prefix = (
        "Recent indicators suggest that economic activity has continued to expand at a solid pace. "
        "Job gains have moderated, and the unemployment rate has moved up but remains low. "
        "Inflation has eased over the past year but remains somewhat elevated. "
        "In recent months, there has been some further progress toward the Committee's 2 percent inflation objective. "
        "The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer run. "
        "The Committee judges that the risks to achieving its employment and inflation goals continue to move into better balance. "
        "The economic outlook is uncertain, and the Committee is attentive to the risks to both sides of its dual mandate. "
    )
    suffix = (
        " In considering any adjustments to the target range for the federal funds rate, the Committee will carefully assess incoming data, the evolving outlook, and the balance of risks. "
        "The Committee does not expect it will be appropriate to reduce the target range until it has gained greater confidence that inflation is moving sustainably toward 2 percent. "
        "In addition, the Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage‑backed securities. "
        "The Committee is strongly committed to returning inflation to its 2 percent objective. "
        "In assessing the appropriate stance of monetary policy, the Committee will continue to monitor the implications of incoming information for the economic outlook. "
        "The Committee would be prepared to adjust the stance of monetary policy as appropriate if risks emerge that could impede the attainment of the Committee's goals. "
        "The Committee's assessments will take into account a wide range of information, including readings on labor market conditions, inflation pressures and inflation expectations, and financial and international developments. "
        "Voting for the monetary policy action were Alex Example, Chair; Blair Example, Vice Chair; and Casey Example. "
        "For media inquiries, please email [email protected] or call 202-452-2955. Implementation Note issued "
    )
    return (
        date
        + " Federal Reserve issues FOMC statement\n\n"
        + prefix
        + "In support of its goals, the Committee decided to maintain the target range for the federal funds rate at "
        + limits
        + " percent."
        + suffix
        + date
    )


def test_fomc_fraction_normalization_and_basis_point_conversion_bind_both_inputs():
    rows = business_observations(
        [
            observed(statement("July 31, 2024", "5-1/4 to 5-1/2")),
            observed(statement("September 18, 2024", "4‑3/4 to 5"), "b"),
        ]
    )
    data = metrics(rows)
    assert data["target_lower_pct", "2024-07-31"] == "5.25"
    assert data["target_cut_bps", "2024-09-18"] == "50.00"
    derived = next(r for r in rows if r.get("metric") == "target_cut_bps")
    assert set(derived["source_ids"]) == {"file:" + "a" * 24, "file:" + "b" * 24}
    assert not metrics(business_observations([observed(statement("July 31, 2024", "5-1/0 to 6"))]))


def test_nist_count_is_actual_selected_records_and_body_is_original_text():
    text = "Govern 1.1 : Legal requirements are documented.\n\nMap 1.1 : Context is understood."
    rows = business_observations([observed(text)])
    assert metrics(rows)["selected_control_count", "uploaded_sample"] == "2"
    assert any(r["content"].split("\n")[0] == "Legal requirements are documented." for r in rows)
    assert not metrics(business_observations([observed(text + "\n" + text)]))


def test_binding_changes_with_input_bytes_and_foreign_source_identity():
    a = business_observations([observed(ANNUAL)])
    b = business_observations([observed(ANNUAL, "b")])
    c = business_observations([observed(ANNUAL.replace("118548", "118549"))])
    assert {r["id"] for r in a}.isdisjoint(r["id"] for r in b)
    assert {r["id"] for r in a}.isdisjoint(r["id"] for r in c)
    forged = observed(ANNUAL)
    forged["sha256"] = "0" * 64
    assert business_observations([forged]) == []


def test_no_partial_large_or_untrusted_report_observations_are_promoted():
    assert business_observations([observed(ANNUAL + " " * 12000)]) == []
    row = observed(ANNUAL)
    row["source_id"] = "file:" + "b" * 24
    assert business_observations([row]) == []


def test_scope_and_trailing_cpi_period_are_not_inferred():
    inputs = [observed(ANNUAL)]
    assert {r["id"] for r in observe(inputs, scope="session-one:task-one")}.isdisjoint(
        r["id"] for r in observe(inputs, scope="session-two:task-one")
    )
    assert not metrics(
        business_observations([observed(CPI.replace("ended<br>Dec. 2024", "ended<br>Dec. 2023"))])
    )
    assert not metrics(
        business_observations([observed(ANNUAL.replace("(In millions)", "(In billions)"))])
    )


def test_exact_quote_segmenter_preserves_negation_and_abbreviations():
    from app.research_web.research_business_evidence import _quotes

    item = observed(
        statement("September 18, 2024", "4-3/4 to 5")
        + "\n\nThe Committee does not expect future policy actions to be automatic. U.S. organizations face risks that cannot be assessed from this excerpt."
    )
    quotes = [
        r["content"].rsplit("\n", 1)[0]
        for r in _quotes(item, "quote-segmentation-test")
        if r["kind"] == "business_quote"
    ]
    assert any("does not expect" in q for q in quotes)
    assert not any(q.startswith("organizations face") for q in quotes)
    for quote in quotes:
        assert quote in item["content"]


def test_cross_source_derived_claim_requires_every_parent_in_notes_and_citations():
    from app.research_web.research_business_evidence import business_lineage_issues
    from app.research_web.research_quality import assess_quality, make_contract
    from app.research_web.resources.research_report import business_evidence

    obs = business_observations(
        [
            observed(statement("July 31, 2024", "5-1/4 to 5-1/2")),
            observed(statement("September 18, 2024", "4-3/4 to 5"), "b"),
        ]
    )
    row = next(r for r in obs if r["metric"] == "target_cut_bps")
    blocks = business_evidence([row], {"target_cut_bps": ["r1"]})
    report = {
        "task_id": "a" * 24,
        "title": "Policy comparison",
        "as_of": "2026-10-19",
        "sources": [{"id": "file:" + name * 24, "title": name} for name in ("a", "b")],
        **blocks,
    }
    assert business_lineage_issues(report, obs) == []
    other = next(s for s in row["source_ids"] if s != row["source_id"])
    report["sources"] = [s for s in report["sources"] if s["id"] != other]
    for s in report["sections"] + report["notes"]:
        s["citations"].remove(other)
    assert business_lineage_issues(report, obs) == [
        "business_parent_lineage_missing:" + report["numeric_claims"][0]["id"]
    ]
    contract = make_contract(
        "a" * 24, "Compare target rates", ["Comparison"], "2026-10-19", "quick"
    )
    sources = [{"id": "file:" + name * 24, "title": name} for name in ("a", "b")]
    # This extra guard strengthens the pre-existing single-source claim verifier.
    assert assess_quality(contract, report, sources, obs)["status"] == "passed"


def test_actual_store_bytes_reach_host_and_model_observations_cannot_override(tmp_path):
    import json
    from types import SimpleNamespace

    from app.research_web.research_evidence import evidence_index
    from app.research_web.research_quality import make_contract
    from app.research_web.research_quality_service import observations, quality_result
    from app.research_web.resources.research_report import business_evidence, write_research_report
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "Host business evidence")["id"]
    p = store.directory(sid) / "inputs" / "annual.md"
    p.write_text(ANNUAL)
    sources = evidence_index(store.files(sid), [], [])
    svc = SimpleNamespace(store=store)
    contract = make_contract("a" * 24, "Compute FCF", ["Cash flow"], "2026-10-19", "quick")
    host = observations(
        svc,
        sid,
        store.files(sid),
        sources,
        task_id=contract["task_id"],
        contract_sha=contract["sha256"],
    )
    row = next(r for r in host if r.get("metric") == "task_defined_fcf" and r["period"] == "2024")
    payload = {
        "task_id": contract["task_id"],
        "title": "Cash flow",
        "as_of": "2026-10-19",
        "sources": [{"id": s["id"], "title": s["title"]} for s in sources],
        **business_evidence([row], {"task_defined_fcf": ["r1"]}),
    }
    paths = write_research_report(store.directory(sid) / "outputs", payload)
    manifest = json.loads(paths["json"].read_text())
    delivery = {"files": [{**a, "valid": True} for a in manifest["artifacts"]]}
    result = quality_result(
        svc, sid, {"research_contract": contract}, store.files(sid), sources, delivery
    )
    assert result["status"] == "passed", result["issues"]
    p.write_text(ANNUAL.replace("118548", "118549"))
    payload["business_observations"] = [row]
    paths = write_research_report(store.directory(sid) / "outputs", payload)
    manifest = json.loads(paths["json"].read_text())
    delivery = {"files": [{**a, "valid": True} for a in manifest["artifacts"]]}
    result = quality_result(
        svc, sid, {"research_contract": contract}, store.files(sid), sources, delivery
    )
    assert result["status"] != "passed"


@pytest.mark.parametrize("bad", ["1$2", "1**2", "(-123)", "1,23"])
def test_malformed_financial_tokens_are_never_reinterpreted_as_other_values(bad):
    assert business_observations([observed(ANNUAL.replace("118548", bad))]) == []


def test_financial_labels_and_all_financing_rows_must_be_unambiguous():
    assert (
        business_observations(
            [observed(ANNUAL.replace("Net cash from operations", "Revenue per share"))]
        )
        == []
    )
    assert (
        business_observations(
            [
                observed(
                    ANNUAL.replace(
                        "| ElementName | Investing",
                        "| Unknown | Omitted | 10 | 10 | 10 |\n| ElementName | Investing",
                    )
                )
            ]
        )
        == []
    )


def test_quality_receipt_cache_cannot_replay_old_evidence_with_unchanged_issues():
    import asyncio
    from types import SimpleNamespace

    from app.research_web.research_quality_service import check_quality

    async def run():
        receipt = {
            "research_contract": {"task_id": "a" * 24},
            "quality_checks": {},
            "quality_repair_count": 0,
        }
        store = SimpleNamespace(
            data={"receipts": {"sid:key": receipt}},
            session=lambda sid: {"delivery_key": "key"},
            save=lambda: None,
        )
        current = {"value": "1"}

        async def detail(sid):
            return {
                "research_report": None,
                "research_quality": {
                    "status": "incomplete",
                    "issues": ["report_missing"],
                    "evidence_context": {"business_observations": [dict(current)]},
                },
            }

        service = SimpleNamespace(store=store, lock=asyncio.Lock(), detail=detail)
        first = await check_quality(service, "sid")
        current["value"] = "2"
        second = await check_quality(service, "sid")
        assert first["evidence_context"]["business_observations"][0]["value"] == "1"
        assert second["evidence_context"]["business_observations"][0]["value"] == "2"
        assert receipt["quality_repair_count"] == 1
        assert len(receipt["quality_checks"]) == 2
        assert await check_quality(service, "sid") == second

    asyncio.run(run())


def test_reordering_sources_preserves_canonical_business_observation_order():
    inputs = [
        observed(statement("July 31, 2024", "5-1/4 to 5-1/2")),
        observed(statement("September 18, 2024", "4-3/4 to 5"), "b"),
    ]
    assert business_observations(inputs) == business_observations(list(reversed(inputs)))


def test_business_projection_rechecks_whole_input_hash_after_scoring(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import app.research_web.research_quality_service as quality
    from app.research_web.research_evidence import evidence_index
    from app.research_web.research_quality import make_contract
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "input race")["id"]
    p = store.directory(sid) / "inputs" / "annual.md"
    p.write_text(ANNUAL)
    sources = evidence_index(store.files(sid), [], [])
    context = quality.source_context

    def changed(*args, **kwargs):
        p.write_text(ANNUAL.replace("118548", "118549"))
        return context(*args, **kwargs)

    monkeypatch.setattr(quality, "source_context", changed)
    contract = make_contract("a" * 24, "Cash flow", ["Cash flow"], "2026-10-19", "quick")
    result = quality.quality_result(
        SimpleNamespace(store=store),
        sid,
        {"research_contract": contract},
        store.files(sid),
        sources,
    )
    assert result["status"] == "invalid"
    assert "business_input_changed_during_verification" in result["issues"]
    assert result["evidence_context"]["business_observations"] == []


def test_disallowed_upload_scope_never_creates_business_observations(tmp_path):
    from types import SimpleNamespace

    from app.research_web.research_evidence import evidence_index
    from app.research_web.research_quality import make_contract
    from app.research_web.research_quality_service import quality_result
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "source scope")["id"]
    (store.directory(sid) / "inputs" / "annual.md").write_text(ANNUAL)
    files = store.files(sid)
    sources = evidence_index(files, [], [])
    store.session(sid)["source_scope"] = ["web"]
    contract = make_contract("a" * 24, "Scope", ["Scope"], "2026-10-19", "quick")
    result = quality_result(
        SimpleNamespace(store=store), sid, {"research_contract": contract}, files, sources
    )
    assert result["evidence_context"]["business_observations"] == []
    assert result["evidence_context"]["sources"] == []


@pytest.mark.parametrize(
    "body",
    [
        "The Committee did not maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent.",
        "An analyst recommended maintaining the target range for the federal funds rate at 5-1/4 to 5-1/2 percent. The Committee rejected this proposal.",
        "If the Committee decided to maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent.",
        "An analyst proposed the following policy. The Committee decided to maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent.",
        'An analyst wrote: "The Committee decided to maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent."',
    ],
)
def test_fomc_never_promotes_negation_proposals_conditions_or_quoted_decisions(body):
    assert (
        business_observations(
            [observed("July 31, 2024 Federal Reserve issues FOMC statement\n\n" + body)]
        )
        == []
    )


def test_negated_board_instrument_decision_is_not_an_effective_rate():
    text = "September 18, 2024 Implementation Note issued September 18, 2024\n\nThe Board did not change the interest rate paid on reserve balances to 4.9 percent, effective September 19, 2024."
    assert business_observations([observed(text)]) == []


def test_annual_header_cannot_be_borrowed_from_another_table_or_comment():
    lines = ANNUAL.splitlines()
    lines[0] = (
        "Year Ended June 30 applies to a different table.\n| (In millions) | Quarter Ended March 31, |"
    )
    assert business_observations([observed("\n".join(lines))]) == []
    assert (
        business_observations(
            [
                observed(
                    ANNUAL.replace(
                        "| 2024 | 2023 | 2022 |", "| 2024 | 2023 | 2022 |\n| separator unrelated |"
                    )
                )
            ]
        )
        == []
    )


def test_cpi_header_group_order_cannot_be_reversed():
    assert (
        business_observations(
            [
                observed(
                    CPI.replace(
                        "| | Seasonally adjusted changes from preceding month | Un-<br>adjusted<br>12-mos.<br>ended<br>Dec. 2024 |",
                        "| | Un-<br>adjusted<br>12-mos.<br>ended<br>Dec. 2024 | Seasonally adjusted changes from preceding month |",
                    )
                )
            ]
        )
        == []
    )


def test_parsed_decimal_quantities_preserve_every_digit_and_exact_limits():
    from decimal import Decimal

    from app.research_web.research_business_evidence import _number

    for raw in ("123456789012345678901234567890", "1.1234567890123456789012345678901234"):
        assert _number("(" + raw + ")") == Decimal(raw).copy_negate()
    with pytest.raises(ValueError):
        _number("1000000000000000000000000000001")


def test_legacy_idless_sections_do_not_invalidate_ordinary_reports():
    from app.research_web.research_business_evidence import business_lineage_issues

    assert (
        business_lineage_issues({"sections": [{"heading": "ordinary", "text": "original"}]}, [])
        == []
    )
    row = business_observations([observed(ANNUAL)])[0]
    assert (
        business_lineage_issues({"sections": [{"heading": "ordinary", "text": "original"}]}, [row])
        == []
    )


def test_complete_publication_layout_rejects_unknown_negating_context_anywhere():
    source = statement("July 31, 2024", "5-1/4 to 5-1/2")
    for prefix in ("It is false that:", "The following statement was not adopted."):
        assert (
            business_observations([observed(source.replace("\n\n", "\n\n" + prefix + "\n\n", 1))])
            == []
        )
        assert (
            business_observations(
                [
                    observed(
                        source.replace(
                            "In support of its goals,", prefix + " In support of its goals,", 1
                        )
                    )
                ]
            )
            == []
        )
        assert business_observations([observed(source + "\n\n" + prefix)]) == []


def test_actual_nine_official_excerpt_fixtures_and_source_spans():
    import json
    from pathlib import Path

    from app.research_web.research_quality import assess_quality, make_contract
    from app.research_web.resources.research_report import business_evidence

    folder = Path(__file__).parent / "fixtures/business-evidence"
    manifest = json.loads((folder / "sources.json").read_text())
    all_rows = {}
    for i, item in enumerate(manifest["inputs"], 1):
        raw = (folder / item["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        sid = "file:" + f"{i:024x}"
        all_rows[item["original_file"]] = {
            "id": sid,
            "source_id": sid,
            "content": raw.decode(),
            "sha256": item["sha256"],
        }
    groups = [
        ["msft-income.md", "msft-cashflows.md"],
        ["bls-cpi-dec2024.md"],
        ["fomc-july.md", "fomc-september.md", "fomc-implementation.md"],
        ["nist-core-context-1.md", "nist-core-context-2.md", "nist-controls.md"],
    ]
    expected = [
        {
            ("task_defined_fcf", "2024"): "74071",
            ("cash_shareholder_return", "2024"): "39025",
            ("financing_reconciliation_difference", "2024"): "0",
        },
        {("core_yoy_nsa_pct", "2024-12"): "3.2", ("headline_mom_sa_pct", "2024-12"): "0.4"},
        {
            ("target_cut_bps", "2024-09-18"): "50.00",
            ("reserve_balance_rate_pct", "2024-09-19"): "4.9",
            ("primary_credit_rate_pct", "2024-09-19"): "5",
            ("dissent_preferred_cut_bps", "2024-09-18"): "25.00",
        },
        {
            ("function_count", "uploaded_sample"): "4",
            ("selected_control_count", "uploaded_sample"): "8",
        },
    ]
    for names, wanted in zip(groups, expected, strict=True):
        inputs = [all_rows[name] for name in names]
        rows = business_observations(inputs)
        data = metrics(rows)
        for key, value in wanted.items():
            assert data[key] == value
        for row in rows:
            for proof in row["proofs"]:
                source = next(r for r in inputs if r["id"] == proof["source_id"])
                assert proof["sha256"] == source["sha256"]
                for span in proof["spans"]:
                    assert source["content"][span["start"] : span["end"]] == span["text"]
        selected = [r for r in rows if (r["metric"], r["period"]) in wanted]
        contract = make_contract("a" * 24, "Verify original data", ["Facts"], "2026-10-19", "quick")
        payload = {
            "task_id": "a" * 24,
            "title": "Original data",
            "as_of": "2026-10-19",
            "sources": [{"id": r["id"], "title": r["id"]} for r in inputs],
            **business_evidence(selected, {r["id"]: ["r1"] for r in selected}),
        }
        result = assess_quality(contract, payload, payload["sources"], [*inputs, *rows])
        assert result["status"] == "passed", result


def test_implementation_layout_rejects_negation_around_an_otherwise_complete_note():
    from pathlib import Path

    source = (
        Path(__file__).parent / "fixtures/business-evidence/fomc-implementation.txt"
    ).read_text()
    for prefix in ("It is false that:", "The following statement was not adopted."):
        assert (
            business_observations([observed(source.replace("\n\n", "\n\n" + prefix + "\n\n", 1))])
            == []
        )
        assert business_observations([observed(source + "\n\n" + prefix)]) == []


def test_invalid_legacy_contract_cannot_sign_business_observations(tmp_path):
    from types import SimpleNamespace

    from app.research_web.research_evidence import evidence_index
    from app.research_web.research_quality import make_contract
    from app.research_web.research_quality_service import quality_result
    from app.research_web.store import Store

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "legacy contract")["id"]
    (store.directory(sid) / "inputs" / "annual.md").write_text(ANNUAL)
    files = store.files(sid)
    sources = evidence_index(files, [], [])
    contract = make_contract("a" * 24, "Cash flow", ["Cash flow"], "2026-10-19", "quick")
    contract.pop("sha256")
    result = quality_result(
        SimpleNamespace(store=store), sid, {"research_contract": contract}, files, sources
    )
    assert result["status"] == "invalid"
    assert result["evidence_context"]["business_observations"] == []
