"""Regressions from the single Flash GDP acceptance run, without vendor calls."""

import hashlib
from types import SimpleNamespace

import pytest

from app.research_web.research_web_sources import BodyParser


@pytest.mark.parametrize(
    "body, expected",
    [
        ("<p>发布时间：2026-01-20</p><p>09:30</p>", "2026-01-20"),
        ("<p>2026 02/28 19:44:03</p><p>来源：新华网</p>", "2026-02-28"),
        ("<p>2025-12-26 10:02:26来源：央视新闻客户端</p>", "2025-12-26"),
        ('<meta name="publishdate" content="2026-01-20 09:30">', "2026-01-20"),
        ('<meta name="PubDate" content="2026-01-20"><p>发布时间：2026-01-21</p>', None),
        ("<p>2026-01-20资料截止日</p><p>数据期间2025年</p>", None),
        ("<p>发布时间：2026-02-30</p>", None),
        ("<script>发布时间：2026-01-20</script><p>没有发布日期</p>", None),
    ],
)
def test_publication_date_requires_actual_unambiguous_publication_evidence(body, expected):
    parser = BodyParser()
    parser.feed(body)
    assert parser.published == expected


TABLE = """2025年四季度和全年GDP初步核算结果
表1　2025年四季度和全年GDP初步核算数据
绝对额（亿元）
比上年同期增长（%）
四季度
全年
四季度
全年
GDP
387911
1401879
4.5
5.0
注：1.绝对额按现价计算，增长速度按不变价计算；
"""


def web_item(text):
    return {
        "id": "web:" + "a" * 24,
        "source_id": "web:" + "a" * 24,
        "content": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def test_web_numeric_table_preserves_actual_column_period_unit_and_proofs():
    from app.research_web.research_web_numeric import web_numeric_observations

    rows = web_numeric_observations(web_item(TABLE), scope="session:task")
    assert {(r["metric"], r["period"], r["value"], r["unit"]) for r in rows} == {
        ("gdp_current_price_preliminary", "2025", "1401879", "亿元"),
        ("gdp_real_growth_preliminary", "2025", "5.0", "%"),
    }
    for row in rows:
        assert row["source_ids"] == [web_item(TABLE)["id"]]
        for proof in row["proofs"]:
            assert proof["sha256"] == web_item(TABLE)["sha256"]
            for span in proof["spans"]:
                assert TABLE[span["start"] : span["end"]] == span["text"]


@pytest.mark.parametrize(
    "text",
    [
        TABLE.replace("四季度\n全年\n四季度\n全年", "全年\n四季度\n全年\n四季度"),
        TABLE.replace("绝对额按现价计算，增长速度按不变价计算", "计算方法未知"),
        TABLE.replace("1401879", "未知"),
        "搜索摘要：2025年GDP为1401879亿元，同比增长5.0%。",
    ],
)
def test_unknown_or_summary_numeric_layout_never_becomes_a_verified_claim(text):
    from app.research_web.research_web_numeric import web_numeric_observations

    assert web_numeric_observations(web_item(text), scope="session:task") == []


def test_conflicting_gdp_versions_never_silently_select_a_value():
    from app.research_web.research_web_numeric import web_numeric_observations

    conflicting = TABLE + TABLE.replace("1401879", "1401880")
    assert web_numeric_observations(web_item(conflicting), scope="session:task") == []


@pytest.mark.parametrize("upload_count", [0, 20])
def test_actual_body_to_sdk_numeric_claims_is_independently_rechecked(
    tmp_path, monkeypatch, upload_count
):
    from app.research_web.research_quality import assess_quality, make_contract
    from app.research_web.research_quality_service import observations, write_business_snapshot
    from app.research_web.research_web_sources import stored_sources
    from app.research_web.resources.research_report import (
        load_business_evidence,
        select_business_evidence,
    )
    from app.research_web.store import Store, StoreError

    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "GDP")["id"]
    root = store.directory(sid)
    path = "inputs/web-" + "a" * 24 + ".txt"
    (root / path).write_text(TABLE)
    fid = hashlib.sha256(path.encode()).hexdigest()[:24]
    item = {
        **web_item(TABLE),
        "file_id": fid,
        "path": path,
        "title": "GDP原文",
        "url": "https://example.org/gdp",
        "as_of": "2026-01-20",
    }
    store.session(sid)["files"][fid] = path
    store.session(sid)["web_evidence"] = {item["id"]: item}
    for index in range(upload_count):
        (root / "inputs" / f"upload-{index}.txt").write_text("独立上传资料。")
    store.files(sid)
    contract = make_contract("b" * 24, "GDP", ["比较GDP"], "2026-10-16", "deep")
    service = SimpleNamespace(store=store)
    write_business_snapshot(service, sid, contract)
    monkeypatch.chdir(root)
    bundle = load_business_evidence(contract["task_id"], contract["sha256"])
    assert len(bundle["observations"]) == 2
    assert item["id"] in {r["id"] for r in bundle["sources"]}  # No fake upload identity.
    assert len(bundle["sources"]) == upload_count + 1
    blocks = select_business_evidence(bundle, {r["id"]: ["r1"] for r in bundle["observations"]})
    payload = {
        "task_id": contract["task_id"],
        "title": "GDP",
        "as_of": contract["as_of"],
        "sources": [{key: item[key] for key in ("id", "title", "url")}],
        "missing": ["未取得其他年度官方原页"],
        **blocks,
    }
    actual = observations(
        service, sid, [], [item], task_id=contract["task_id"], contract_sha=contract["sha256"]
    )
    result = assess_quality(contract, payload, [item], actual)
    assert result["status"] == "incomplete" and payload["numeric_claims"]
    assert not any(issue.startswith("numeric_claim") for issue in result["issues"])
    payload["numeric_claims"][0]["value"] = "999999"
    assert any(
        issue.startswith("numeric_claim_unverified")
        for issue in assess_quality(contract, payload, [item], actual)["issues"]
    )
    (root / path).write_text(TABLE.replace("1401879", "1401880"))
    with pytest.raises(StoreError):
        stored_sources(store, sid)


def test_final_and_preliminary_prose_keep_version_and_period_distinct():
    from app.research_web.research_web_numeric import web_numeric_observations

    text = "中华人民共和国2024年国民经济和社会发展统计公报\n一、综合\n初步核算，全年国内生产总值[2]1349084亿元，比上年增长5.0%。\n[2]国内生产总值、三次产业及相关行业增加值、地区生产总值、人均国内生产总值和国民总收入绝对数按现价计算，增长速度按不变价格计算。\n经最终核实，2024年，GDP现价总量为1348066亿元，比初步核算数减少1018亿元；按不变价格计算，比上年增长5.0%，与初步核算数持平。"
    rows = web_numeric_observations(web_item(text), scope="session:task")
    assert len(rows) == 4
    assert {(r["metric"], r["value"]) for r in rows if r["unit"] == "亿元"} == {
        ("gdp_current_price_preliminary", "1349084"),
        ("gdp_current_price_final", "1348066"),
    }


def test_byte_mismatch_and_cross_session_scope_change_cannot_reuse_observation_ids():
    from app.research_web.research_web_numeric import web_numeric_observations

    assert web_numeric_observations({**web_item(TABLE), "sha256": "0" * 64}, scope="s:t") == []
    first = web_numeric_observations(web_item(TABLE), scope="session-1:task")
    second = web_numeric_observations(web_item(TABLE), scope="session-2:task")
    assert {r["id"] for r in first}.isdisjoint(r["id"] for r in second)


@pytest.mark.parametrize(
    "text",
    [
        "中华人民共和国2024年国民经济和社会发展统计公报\n上年2023年，初步核算，全年国内生产总值[2]1260582亿元，比上年增长5.2%。\n绝对数按现价计算，增长速度按不变价格计算",
        "未经最终核实，2024年，GDP现价总量为1348066亿元，比初步核算数减少1018亿元；按不变价格计算，比上年增长5.0%，与初步核算数持平。",
        "经最终核实，2024年，GDP现价总量为1348066亿元，比初步核算数减少1018亿元；按不变价格计算，比上年增长5.0%，与初步核算数持平。但上述数字不正确。",
    ],
)
def test_negated_or_previous_year_prose_is_not_certified(text):
    from app.research_web.research_web_numeric import web_numeric_observations

    assert web_numeric_observations(web_item(text), scope="session:task") == []


def test_negated_unit_basis_is_not_truncated_into_positive_evidence():
    from app.research_web.research_web_numeric import web_numeric_observations

    text = "中华人民共和国2024年国民经济和社会发展统计公报\n一、综合\n初步核算，全年国内生产总值[2]1349084亿元，比上年增长5.0%。\n注意：不能认为绝对数按现价计算，增长速度按不变价格计算。"
    assert web_numeric_observations(web_item(text), scope="session:task") == []


@pytest.mark.parametrize("cached, expected", [("2025-01-01", "unknown"), ("unknown", "2026-01-20")])
def test_cached_date_is_reconciled_with_actual_body_and_conflicts_stay_unknown(
    tmp_path, cached, expected
):
    from app.research_web.research_web_sources import stored_sources
    from app.research_web.store import Store

    store = Store(tmp_path)
    sid = store.create("fingpt", "日期")["id"]
    root = store.directory(sid)
    body = "GDP发布\n发布时间：2026-01-20\n正文。"
    path = "inputs/web-" + "a" * 24 + ".txt"
    (root / path).write_text(body)
    fid = hashlib.sha256(path.encode()).hexdigest()[:24]
    store.session(sid)["files"][fid] = path
    store.session(sid)["web_evidence"] = {
        web_item(body)["id"]: {
            **web_item(body),
            "path": path,
            "file_id": fid,
            "as_of": cached,
            "date_evidence": (
                []
                if cached == "unknown"
                else [{"date": cached, "kind": "publication_meta", "text": cached}]
            ),
        }
    }
    result = stored_sources(store, sid)[0]
    assert result["as_of"] == expected
    if cached != "unknown":
        assert result["date_status"] == "conflict"
