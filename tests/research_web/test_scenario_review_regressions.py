"""Independent review reproductions: real Store, snapshots, HTTP and fake native."""

import test_workbench_operations as fixtures
from test_api import isolated_keyring  # noqa: F401

api = fixtures.api
from test_scenario_handoffs import scenario_body

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result


def publish(service, source, capability="financials"):
    q = BusinessQuery(
        capability="search_news" if capability == "news" else capability,
        source="cls" if capability == "news" else "akshare",
        parameters={} if capability == "news" else {"asset": "600600.SH"},
    )
    rows = (
        [{"published_at": "2026-10-26T10:00:00+00:00", "content": "known future news"}]
        if capability == "news"
        else [{"date": "2026-06-30", "revenue": 100}]
    )
    return service.datahub.snapshots.publish(
        source,
        q,
        Result(
            rows=rows,
            raw=[b"original"],
            status="snapshot",
            as_of="2026-10-26T10:00:00+00:00" if capability == "news" else "2026-06-30",
        ),
        request_query=q,
        authorization_fingerprint=service.datahub.source_configuration_digest(q.source),
    )["dataset_id"]


def prepare(client, source, did, key, scenario=True):
    b = scenario_body() if scenario else {"target_mode": "fingpt", "section": "assets"}
    b.update(source_session_id=source, dataset_ids=[did])
    if scenario:
        b["scenario_inputs"]["material_ids"] = [did]
    r = client.post("/api/research/handoffs", json=b, headers={"Idempotency-Key": key})
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def test_nested_copy_revocation(api):
    c, s = api
    source = c.post("/api/research/sessions", json={}).json()["id"]
    did = publish(s, source)
    first = prepare(c, source, did, "first-review-copy")
    first_did = s.datahub.snapshots.ids(first)[0]
    second = prepare(c, first, first_did, "second-review-copy")
    legacy = prepare(c, first, first_did, "legacy-review-copy", False)
    s.store.session(source)["source_scope"] = ["web"]
    results = {}
    for name, sid in [("first", first), ("second", second), ("legacy", legacy)]:
        copied = s.datahub.snapshots.ids(sid)[0]
        r = c.get(f"/api/research/sessions/{sid}/datasets/{copied}/rows")
        results[name] = {"status": r.status_code, "body": r.json()}
    print("REVIEW_REVOKE", results)
    assert results["first"]["status"] == 403
    assert results["second"]["status"] == 403
    assert results["legacy"]["status"] == 403


def test_known_news_cutoff(api):
    c, s = api
    source = c.post("/api/research/sessions", json={}).json()["id"]
    did = publish(s, source, "news")
    b = scenario_body("news-query")
    b.update(source_session_id=source, dataset_ids=[did])
    b["scenario_inputs"].update(material_ids=[did], as_of="2026-10-25")
    r = c.post("/api/research/handoffs", json=b, headers={"Idempotency-Key": "known-news-cutoff"})
    print(
        "REVIEW_CUTOFF",
        r.status_code,
        r.json().get("scenario_context", {}).get("scenario", {}).get("inputs"),
    )
    assert r.status_code == 409, r.text


def test_second_scenario_capability_missing_native_is_not_sent(api, monkeypatch):
    c, s = api
    primary = s.capabilities.selection("finance-news-event-research")
    calls = []
    original = s.client.rpc

    async def native(method, payload):
        calls.append((method, payload))
        if method == "skill.list":
            return {"skills": [{"name": primary["native_name"]}]}
        return await original(method, payload)

    monkeypatch.setattr(s.client, "rpc", native)
    monkeypatch.setattr(s, "_model_tools_verified", lambda _sid=None: True)
    b = scenario_body("news-transmission")
    prepared = c.post(
        "/api/research/handoffs", json=b, headers={"Idempotency-Key": "two-caps-review"}
    )
    assert prepared.status_code == 201, prepared.text
    sid = prepared.json()["session_id"]
    sent = c.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "按冻结方法传导研究", "expected_formats": []},
        headers={"Idempotency-Key": "two-caps-send-review"},
    )
    print(
        "REVIEW_SECOND_CAPABILITY",
        sent.status_code,
        "prompt_count",
        sum(m == "session.prompt" for m, p in calls),
        "frozen",
        [x["id"] for x in prepared.json()["scenario_context"]["scenario"]["capabilities"]],
    )
    assert sent.status_code == 409, sent.text


def test_market_snapshot_known_foreign_subject(api):
    c, s = api
    source = c.post("/api/research/sessions", json={}).json()["id"]
    q = BusinessQuery(
        capability="market_snapshot", source="akshare", parameters={"assets": ["601318.SH"]}
    )
    result = Result(
        rows=[{"asset": "601318.SH", "price": 100, "as_of": "2026-10-25"}],
        raw=[b"foreign subject original"],
        status="snapshot",
        as_of="2026-10-25",
    )
    did = s.datahub.snapshots.publish(
        source,
        q,
        result,
        request_query=q,
        authorization_fingerprint=s.datahub.source_configuration_digest("akshare"),
    )["dataset_id"]
    b = scenario_body()
    b.update(source_session_id=source, dataset_ids=[did])
    b["scenario_inputs"]["material_ids"] = [did]
    r = c.post(
        "/api/research/handoffs", json=b, headers={"Idempotency-Key": "wrong-market-subject"}
    )
    print(
        "REVIEW_ENTITY",
        r.status_code,
        r.json().get("error"),
        r.json().get("scenario_context", {}).get("scenario", {}).get("inputs"),
    )
    assert r.status_code == 409, r.text


def test_lineage_cycle_and_missing_ancestor_fail_closed(api):
    c, s = api
    source = c.post("/api/research/sessions", json={}).json()["id"]
    first = prepare(c, source, publish(s, source), "lineage-cycle-test")
    record = s.store.data["handoffs"][s.store.session(first)["scenario_handoff_id"]]
    ref = record["scenario_context"]["references"][0]
    original = ref["source_session_id"]
    did = s.datahub.snapshots.ids(first)[0]
    for ancestor, code in [
        (first, "scenario_lineage_cycle"),
        ("00000000-0000-0000-0000-000000000000", "scenario_ancestor_unknown"),
    ]:
        ref["source_session_id"] = ancestor
        result = c.get(f"/api/research/sessions/{first}/datasets/{did}/rows")
        assert result.status_code == 409
        assert result.json()["error"]["code"] == code
    ref["source_session_id"] = original
    assert c.get(f"/api/research/sessions/{first}/datasets/{did}/rows").status_code == 200


def test_copy_without_provable_ancestor_cannot_become_new_authority(api):
    c, s = api
    source = c.post("/api/research/sessions", json={}).json()["id"]
    detached = c.post("/api/research/sessions", json={}).json()["id"]
    copied = s.datahub.copy_selected(source, detached, [publish(s, source)])[0]
    body = scenario_body()
    body.update(source_session_id=detached, dataset_ids=[copied["dataset_id"]])
    body["scenario_inputs"]["material_ids"] = body["dataset_ids"]
    result = c.post(
        "/api/research/handoffs", json=body, headers={"Idempotency-Key": "detached-copy-test"}
    )
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "scenario_ancestor_unknown"


def test_news_body_and_publication_qualification_uses_real_rows(api):
    c, s = api
    source = c.post("/api/research/sessions", json={}).json()["id"]
    q = BusinessQuery(capability="search_news", source="cls", parameters={})
    for label, rows, absent in [
        ("full", [{"content": "真实已取得正文", "published_at": "2026-10-25T10:00:00Z"}], set()),
        ("unknown", [{"content": "真实已取得正文", "published_at": None}], {"publication-time"}),
        ("empty", [], {"news-source-text", "publication-time"}),
    ]:
        d = s.datahub.snapshots.publish(
            source,
            q,
            Result(rows=rows, raw=[b"owned news original"], status="snapshot" if rows else "empty"),
            request_query=q,
            authorization_fingerprint=s.datahub.source_configuration_digest("cls"),
        )
        body = scenario_body("news-query")
        body.update(source_session_id=source, dataset_ids=[d["dataset_id"]])
        body["scenario_inputs"]["material_ids"] = body["dataset_ids"]
        result = c.post(
            "/api/research/handoffs", json=body, headers={"Idempotency-Key": "news-proof-" + label}
        )
        assert result.status_code == 201, result.text
        missing = {
            x["id"]
            for x in result.json()["scenario_context"]["scenario"]["missing"]
            if x["code"].startswith("evidence_")
        }
        assert missing == absent


def test_all_required_capabilities_freeze_resources_and_quality_without_claiming_loaded(
    api, monkeypatch
):
    import hashlib
    import json

    from app.research_web.research_quality import _valid_contract, make_contract
    from app.research_web.research_quality_service import check_quality
    from app.research_web.resources.research_report_plan import write_business_report_plan

    c, s = api
    original = s.client.rpc

    async def native(method, payload):
        if method == "skill.list":
            return {
                "skills": [
                    {"name": row["native_name"]}
                    for row in s.capabilities.list()["items"]
                    if row["enabled"]
                ]
            }
        return await original(method, payload)

    monkeypatch.setattr(s.client, "rpc", native)
    monkeypatch.setattr(s, "_model_tools_verified", lambda _sid=None: True)
    frozen = c.post(
        "/api/research/handoffs",
        json=scenario_body("news-transmission"),
        headers={"Idempotency-Key": "all-required-caps"},
    ).json()
    sid = frozen["session_id"]
    sent = c.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "按冻结方法分析，保留缺口", "expected_formats": ["html"]},
        headers={"Idempotency-Key": "all-required-send"},
    )
    assert sent.status_code == 202, sent.text
    receipt, refs = s._task_capabilities(sid)
    assert {x["id"] for x in refs} == {"finance-news-event-research", "industry-chain-research"}
    assert not receipt.get("native_capabilities")
    contract = receipt["research_contract"]
    assert contract["schema_version"] == 2 and _valid_contract(contract)
    assert len(contract["execution_context"]["capabilities"]) == 2
    assert len(receipt["scenario_readiness"]) == 2
    for ref in refs:
        assert (s.store.directory(sid) / ref["resource_path"] / "SKILL.md").is_file()
        s.native_admission(sid, native_name=ref["native_name"], loaded=True)
    assert len(receipt["native_capabilities"]) == 2
    sdk = s.native_admission(sid, tool_name="research_run_script")["report_context"]
    assert sdk["contract_sha256"] == contract["sha256"]
    plan = {
        "title": "有缺口的场景报告",
        "sections": [
            {
                "id": "gap",
                "heading": "证据缺口",
                "evidence_ids": [],
                "requirement_ids": sdk["requirement_ids"],
                "analysis": "所需事实证据尚未取得。",
            }
        ],
        "missing": ["证据不足，不作事实结论。"],
    }
    with monkeypatch.context() as scoped:
        scoped.chdir(s.store.directory(sid))
        result = write_business_report_plan(sdk, plan, output=s.store.directory(sid) / "outputs")
        assert "json" in result["written"]
    quality = c.portal.call(check_quality, s, sid)
    assert quality["status"] == "incomplete"
    assert "scenario_execution_changed" not in quality["issues"]
    assert not any(x.startswith("scenario_capability_not_loaded") for x in quality["issues"])
    resource = s.store.directory(sid) / refs[1]["resource_path"] / "SKILL.md"
    original_bytes = resource.read_bytes()
    original_mode = resource.stat().st_mode & 0o777
    try:
        resource.chmod(original_mode | 0o200)
        resource.write_bytes(original_bytes + b"\nchanged")
        altered = c.portal.call(check_quality, s, sid)
        assert altered["status"] == "invalid" and "scenario_execution_changed" in altered["issues"]
    finally:
        resource.write_bytes(original_bytes)
        resource.chmod(original_mode)
    # A structurally valid, freshly rehashed client-style contract cannot replace
    # the independently frozen Host capability/resource identities.
    contract["execution_context"]["capabilities"][1]["sha256"] = "0" * 64
    contract["sha256"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in contract.items() if k != "sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert _valid_contract(contract)
    quality = c.portal.call(check_quality, s, sid)
    assert quality["status"] == "invalid"
    assert "scenario_execution_changed" in quality["issues"]
    old = make_contract("a" * 24, "旧合同", ["旧要求"], "2026-10-25", "deep")
    raw = {
        "schema_version": 1,
        "task_id": "a" * 24,
        "question": "旧合同",
        "requirements": [{"id": "r1", "text": "旧要求"}],
        "as_of": "2026-10-25",
        "mode": "deep",
        "previous_task_id": None,
    }
    raw["sha256"] = hashlib.sha256(
        json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert old == raw


def test_soft_deleted_ancestors_remain_verifiable_and_cannot_be_purged(api):
    import pytest

    from app.research_web.store import StoreError

    c, s = api
    source = c.post("/api/research/sessions", json={}).json()["id"]
    first = prepare(c, source, publish(s, source), "retained-first")
    first_did = s.datahub.snapshots.ids(first)[0]
    second = prepare(c, first, first_did, "retained-second")
    legacy = prepare(c, first, first_did, "retained-legacy", False)
    s.store.soft_delete(source)
    s.store.soft_delete(first)
    for target in [second, legacy]:
        did = s.datahub.snapshots.ids(target)[0]
        assert c.get(f"/api/research/sessions/{target}/datasets/{did}/rows").status_code == 200
    for ancestor in [source, first]:
        result = c.delete(f"/api/research/sessions/{ancestor}/permanent")
        assert result.status_code == 409, result.text
        assert result.json()["error"]["code"] == "session_referenced_by_handoff"
        with pytest.raises(StoreError) as caught:
            s.store.purge(ancestor)
        assert caught.value.code == "session_referenced_by_handoff"
        assert s.store.session(ancestor, include_deleted=True).get("native_deleted_at") is None
        s.store.restore(ancestor)
    did = s.datahub.snapshots.ids(second)[0]
    assert c.get(f"/api/research/sessions/{second}/datasets/{did}/rows").status_code == 200


def test_raw_news_preserves_only_explicit_canonical_asset_codes():
    from app.research_web.discovery.news import collect, theme

    row = {
        "title": "主体名字不能猜股票",
        "source": "offline fixture",
        "url": "https://example.test/news",
        "raw_content": "原件",
        "asset_codes": ["600600.SH", "601318.sh", "600600", "同名公司", {"code": "600600.SH"}],
    }
    item = next(iter(collect({"industries": [{"name": "样本", "items": [row]}]}).values()))
    assert theme(item, "2026-10-26")["assets"] == ["600600.SH", "601318.SH"]
    row.pop("asset_codes")
    item = next(iter(collect({"industries": [{"name": "样本", "items": [row]}]}).values()))
    assert theme(item, "2026-10-26")["assets"] == []
