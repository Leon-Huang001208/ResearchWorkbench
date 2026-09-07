"""Offline DataHub boundaries using actual-shaped provider payloads, never live data."""

import asyncio
import importlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.research_web.store import Store, StoreError


def test_datahub_module_exists():
    assert (
        Path(__file__).parents[2] / "app/research_web/datahub/__init__.py"
    ).exists(), "DataHub implementation missing"


@pytest.fixture
def hub_module():
    path = Path(__file__).parents[2] / "app/research_web/datahub/__init__.py"
    assert path.exists(), "DataHub implementation missing"
    return importlib.import_module("app.research_web.datahub")


def nav_row(day, value="1.2"):
    return {"FSRQ": day, "DWJZ": value, "LJJZ": " ", "JZZZL": "--", "FHSP": ""}


def nav_page(rows, total, index=1, size=20):
    return {
        "ErrCode": 0,
        "TotalCount": total,
        "PageSize": size,
        "PageIndex": index,
        "Data": {"LSJZList": rows, "FundType": "002"},
    }


def query(module, **kw):
    return module.Query(
        source="fund_nav",
        code="000001",
        start_date="2025-01-01",
        end_date="2025-12-31",
        **kw,
    )


def make_hub(module, tmp_path, handler):
    store = Store(tmp_path)
    sid = store.create("claw", "test")["id"]
    return module.DataHub(store, transport=httpx.MockTransport(handler)), store, sid


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_date": "2025-01-01"},
        {"start_date": "2025-02-30", "end_date": "2025-03-01"},
        {"start_date": "2025-03-01", "end_date": "2025-01-01"},
        {"start_date": "2000-01-01", "end_date": "2025-01-01"},
        {
            "start_date": "2025-01-01",
            "end_date": (datetime.now(UTC).date() + timedelta(days=2)).isoformat(),
        },
        {"limit": 101},
        {"limit": True},
        {"url": "https://evil.test"},
        {"session": "other"},
        {"code": "../xx"},
        {"year": 2025},
    ],
)
def test_query_rejects_untrusted_or_invalid_business_arguments(hub_module, overrides):
    with pytest.raises(ValueError):
        hub_module.Query.model_validate(
            {"source": "fund_nav", "code": "000001", **overrides}
        )


@pytest.mark.asyncio
async def test_actual_twenty_row_pages_are_drained_and_snapshot_is_scoped(
    hub_module, tmp_path
):
    rows = [
        nav_row((date(2025, 12, 31) - timedelta(days=i)).isoformat()) for i in range(43)
    ]
    requests = []

    def respond(request):
        requests.append(request)
        page = int(request.url.params["pageIndex"])
        assert request.url.params["pageSize"] == "100"
        return httpx.Response(
            200, json=nav_page(rows[(page - 1) * 20 : page * 20], 43, page)
        )

    hub, store, sid = make_hub(hub_module, tmp_path, respond)
    result = await hub.query(sid, "call-1", query(hub_module))
    assert result["status"] == "complete"
    assert (result["row_count"], result["pages_fetched"], result["provider_total"]) == (
        43,
        3,
        43,
    )
    assert result["pagination_complete"] is True
    assert len(result["sample"]) <= 3
    did = result["dataset_id"]
    assert len(hub.rows(sid, did, 0, 20)["items"]) == 20
    detail = hub.detail(sid, did)
    assert detail["actual_range"] == {
        "start_date": "2025-11-19",
        "end_date": "2025-12-31",
    }
    assert detail["fields"]["unit_nav"]["currency"] is None
    assert len(detail["raw_files"]) == 3
    assert all(item["sha256"] for item in detail["files"])
    assert not any("datasets" in str(item) for item in store.files(sid))
    other = store.create("claw", "other")["id"]
    with pytest.raises(StoreError):
        hub.detail(other, did)
    parsed = store.directory(sid) / detail["files"][0]["path"]
    parsed.write_text("corrupt")
    with pytest.raises(StoreError, match="校验"):
        hub.rows(sid, did, 0, 20)
    await hub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "problem,expected",
    [
        ("same", "partial"),
        ("conflict", "partial"),
        ("total", "partial"),
        ("repeat", "partial"),
        ("bad", "partial"),
        ("http", "partial"),
    ],
)
async def test_pagination_inconsistencies_never_become_complete(
    hub_module, tmp_path, problem, expected
):
    calls = 0

    def respond(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json=nav_page(
                    [nav_row("2025-12-31"), nav_row("2025-12-30")], 4, size=2
                ),
            )
        if problem == "http":
            return httpx.Response(503)
        rows = [nav_row("2025-12-30"), nav_row("2025-12-29")]
        if problem == "conflict":
            rows[0]["DWJZ"] = "3.4"
        if problem == "repeat":
            rows = [nav_row("2025-12-31"), nav_row("2025-12-30")]
        if problem == "bad":
            rows[1]["DWJZ"] = "NaN"
        return httpx.Response(
            200, json=nav_page(rows, 5 if problem == "total" else 4, calls, 2)
        )

    hub, _, sid = make_hub(hub_module, tmp_path, respond)
    result = await hub.query(sid, "call-1", query(hub_module))
    assert result["status"] == expected
    assert calls == 2
    assert result["pagination_complete"] is (problem == "same")
    assert result["limitations"]
    if problem == "same":
        assert result["row_count"] == 3
    if problem == "conflict":
        assert "2025-12-30" not in [
            r["date"] for r in hub.rows(sid, result["dataset_id"], 0, 20)["items"]
        ]
    await hub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,status", [(nav_page([], 0), "empty"), ({"ErrCode": 1}, "failed")]
)
async def test_empty_is_distinct_from_failed(hub_module, tmp_path, payload, status):
    hub, _, sid = make_hub(
        hub_module, tmp_path, lambda r: httpx.Response(200, json=payload)
    )
    result = await hub.query(sid, "empty", query(hub_module))
    assert result["status"] == status
    assert result["row_count"] == 0
    assert result["pagination_complete"] is (status == "empty")
    await hub.close()


@pytest.mark.asyncio
async def test_cache_refresh_same_call_and_restart_receipts(hub_module, tmp_path):
    calls = 0

    def respond(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=nav_page([nav_row("2025-12-31")], 1))

    hub, _, sid = make_hub(hub_module, tmp_path, respond)
    first = await hub.query(sid, "first", query(hub_module))
    cached = await hub.query(sid, "second", query(hub_module))
    assert cached["dataset_id"] == first["dataset_id"] and cached["cache_hit"]
    assert cached["retrieved_at"] == first["retrieved_at"]
    refreshed = await hub.query(sid, "third", query(hub_module, refresh=True))
    assert refreshed["dataset_id"] != first["dataset_id"] and not refreshed["cache_hit"]
    assert calls == 2
    with pytest.raises(StoreError):
        await hub.query(
            sid, "first", hub_module.Query(source="fund_nav", code="000002")
        )
    await hub.close()
    restarted = hub_module.DataHub(
        Store(tmp_path), transport=httpx.MockTransport(respond)
    )
    assert (await restarted.query(sid, "first", query(hub_module)))[
        "dataset_id"
    ] == first["dataset_id"]
    assert calls == 2
    other = restarted.store.create("claw", "other")["id"]
    # A different session never reuses the first session's data.
    assert (await restarted.query(other, "first", query(hub_module)))[
        "dataset_id"
    ] != first["dataset_id"]
    await restarted.close()


@pytest.mark.asyncio
async def test_cancel_and_shutdown_stop_http_and_never_publish(hub_module, tmp_path):
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def respond(request):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    hub, _, sid = make_hub(hub_module, tmp_path, respond)
    task = asyncio.create_task(hub.query(sid, "cancel-me", query(hub_module)))
    await started.wait()
    await hub.cancel(sid, "cancel-me")
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set() and hub.list(sid) == []
    with pytest.raises(StoreError):
        await hub.query(sid, "cancel-me", query(hub_module))
    started.clear()
    task = asyncio.create_task(hub.query(sid, "shutdown", query(hub_module)))
    await started.wait()
    await hub.close()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert hub.list(sid) == []


@pytest.mark.asyncio
async def test_legacy_limit_is_a_snapshot_not_all_history(hub_module, tmp_path):
    hub, _, sid = make_hub(
        hub_module,
        tmp_path,
        lambda r: httpx.Response(200, json=nav_page([nav_row("2025-12-31")], 1000)),
    )
    result = await hub.query(
        sid, "legacy", hub_module.Query(source="fund_nav", code="000001", limit=20)
    )
    assert result["pages_fetched"] == 1 and not result["pagination_complete"]
    assert result["status"] == "snapshot"
    await hub.close()


def test_private_configuration_rejects_links_permissions_and_remote_addresses(
    hub_module, tmp_path
):
    config = hub_module.load_control(tmp_path, "http://127.0.0.1:18088")
    path = tmp_path / ".control/datahub.json"
    assert len(config["token"]) >= 43 and path.stat().st_mode & 0o777 == 0o600
    assert hub_module.load_control(tmp_path)["token"] == config["token"]
    path.chmod(0o644)
    with pytest.raises(StoreError):
        hub_module.load_control(tmp_path)
    path.chmod(0o600)
    os.link(path, tmp_path / "linked")
    with pytest.raises(StoreError):
        hub_module.load_control(tmp_path)
    for url in [
        "https://evil.test",
        "http://127.0.0.1:8088/x",
        "http://user@127.0.0.1:8088",
        "http://127.0.0.1:8088?x=1",
    ]:
        with pytest.raises(StoreError):
            hub_module.load_control(tmp_path / "new", url)


@pytest.mark.asyncio
async def test_provider_size_deadline_and_page_cap(hub_module, tmp_path, monkeypatch):
    providers = importlib.import_module("app.research_web.datahub.providers")
    monkeypatch.setattr(providers, "MAX_PAGES", 2)

    def respond(request):
        page = int(request.url.params["pageIndex"])
        return httpx.Response(
            200, json=nav_page([nav_row(f"2025-12-{32 - page:02d}")], 4, page, 1)
        )

    hub, _, sid = make_hub(hub_module, tmp_path, respond)
    result = await hub.query(sid, "cap", query(hub_module))
    assert result["status"] == "partial" and result["pages_fetched"] == 2
    await hub.close()

    async def slow(request):
        await asyncio.Event().wait()

    monkeypatch.setattr(providers, "DEADLINE", 0.01)
    hub = hub_module.DataHub(Store(tmp_path), transport=httpx.MockTransport(slow))
    result = await hub.query(sid, "timeout", query(hub_module, refresh=True))
    assert result["status"] == "failed" and "deadline" in str(result["limitations"])
    await hub.close()
    hub = hub_module.DataHub(
        Store(tmp_path),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=b"x" * 1048577)
        ),
    )
    result = await hub.query(sid, "size", query(hub_module, refresh=True))
    assert result["status"] == "failed"
    await hub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,payload,expected",
    [
        (
            "fund_profile",
            '<table class="info"><tr><th>基金全称</th><td>测试基金</td><th>业绩比较基准</th><td>指数70%</td></tr><tr><th>销售服务费率</th><td>---</td></tr></table>',
            "测试基金",
        ),
        (
            "fund_distributions",
            "<table><tr><th>年份</th><th>权益登记日</th><th>除息日</th><th>每10份分红</th><th>分红发放日</th></tr><tr><td>2025年</td><td>2025-09-22</td><td>2025-09-22</td><td>每10份派现金0.1000元</td><td>2025-09-23</td></tr></table>",
            "0.1000",
        ),
        (
            "fund_holdings",
            'var apidata={ content: "<div><h4 class=\\"t\\">2025年4季度股票投资明细 截止至2025-12-31</h4><table><tr><th>序号</th><th>股票代码</th><th>股票名称</th><th>占净值比例</th><th>持股数（万股）</th><th>持仓市值（万元）</th></tr><tr><td>1</td><td>600001</td><td>测试</td><td>4.57%</td><td>22.00</td><td>13,420.00</td></tr></table></div>",arryear:[2025]};',
            "2025-12-31",
        ),
    ],
)
async def test_verified_supplemental_tables_preserve_original_units(
    hub_module, tmp_path, source, payload, expected
):
    hub, _, sid = make_hub(
        hub_module, tmp_path, lambda r: httpx.Response(200, text=payload)
    )
    result = await hub.query(
        sid, "supplement", hub_module.Query(source=source, code="000001")
    )
    assert result["status"] == "snapshot", result
    rows = hub.rows(sid, result["dataset_id"], 0, 100)["items"]
    assert expected in json.dumps(rows, ensure_ascii=False)
    assert "benchmark_timeseries" in result["missing"]
    await hub.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "original", ["每10份派现金0.1000美元", "每10份派现金0.1000元", "---"]
)
async def test_distribution_currency_is_unverified_and_original_is_preserved(
    hub_module, tmp_path, original
):
    payload = (
        "<table><tr><th>权益登记日</th><th>除息日</th><th>每10份分红</th>"
        "<th>分红发放日</th></tr><tr><td>2025-09-22</td><td>2025-09-22</td>"
        f"<td>{original}</td><td>2025-09-23</td></tr></table>"
    )
    hub, _, sid = make_hub(
        hub_module, tmp_path, lambda r: httpx.Response(200, text=payload)
    )
    result = await hub.query(
        sid,
        "distribution-currency",
        hub_module.Query(source="fund_distributions", code="000001"),
    )
    assert result["status"] == "snapshot"
    assert result["fields"]["每10份分红"]["currency"] is None
    assert "verified_currency" in result["missing"]
    assert hub.rows(sid, result["dataset_id"])["items"][0]["每10份分红"] == original
    await hub.close()


@pytest.mark.asyncio
async def test_real_holdings_headers_with_breaks_and_profile_asset_label(
    hub_module, tmp_path
):
    html = '<h4 class="t">2025年4季度股票投资明细 截止至2025-12-31</h4><table><tr><th>股票代码</th><th>股票名称</th><th>占净值<br/>比例</th><th>持股数<br/>（万股）</th><th>持仓市值<br/>（万元）</th></tr><tr><td>600001</td><td>测试</td><td>4.57%</td><td>22.00</td><td>13,420.00</td></tr></table>'
    hub, _, sid = make_hub(
        hub_module,
        tmp_path,
        lambda r: httpx.Response(
            200, text="var apidata={ content:" + json.dumps(html) + ",arryear:[2025]};"
        ),
    )
    result = await hub.query(
        sid,
        "real-header",
        hub_module.Query(source="fund_holdings", code="000001", year=2025),
    )
    assert result["status"] == "snapshot"
    assert result["row_count"] == 1
    assert any(value["unit"] == "万股" for value in result["fields"].values())
    await hub.close()
    hub = hub_module.DataHub(
        Store(tmp_path),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                text='<table class="info"><tr><th>净资产规模</th><td>12亿元（截止至：2026年06月30日）</td></tr></table>',
            )
        ),
    )
    result = await hub.query(
        sid, "profile-real", hub_module.Query(source="fund_profile", code="000001")
    )
    assert result["status"] == "snapshot"
    assert result["sample"][0]["field"] == "净资产规模"
    await hub.close()


def test_csv_preserves_json_but_escapes_formula_text_and_not_numeric_values(hub_module):
    from app.research_web.datahub.snapshots import csv_bytes

    text = csv_bytes([{"text": "=1+1", "n": -2.3, "original_numeric": "-2.3"}]).decode(
        "utf-8-sig"
    )
    assert "'=1+1" in text and "'-2.3" not in text
    assert csv_bytes([{"=1+1": "x"}]).decode("utf-8-sig").startswith("'=1+1")


@pytest.mark.asyncio
async def test_cancel_before_query_and_dataset_symlink_hardlink_rejection(
    hub_module, tmp_path
):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=nav_page([nav_row("2025-12-31")], 1))

    hub, store, sid = make_hub(hub_module, tmp_path, respond)
    await hub.cancel(sid, "before")
    with pytest.raises(StoreError):
        await hub.query(sid, "before", query(hub_module))
    assert calls == []
    result = await hub.query(sid, "one", query(hub_module))
    path = store.directory(sid) / result["files"][0]["path"]
    os.link(path, tmp_path / "hardlink")
    with pytest.raises(StoreError):
        hub.detail(sid, result["dataset_id"])
    (tmp_path / "hardlink").unlink()
    saved = path.read_bytes()
    path.unlink()
    (tmp_path / "external").write_bytes(saved)
    path.symlink_to(tmp_path / "external")
    with pytest.raises(StoreError):
        hub.detail(sid, result["dataset_id"])
    await hub.close()


def test_launcher_prepares_private_bridge_config_without_secret_environment(
    tmp_path, monkeypatch
):
    from app.research_web import launch_runtime

    source = tmp_path / "source"
    cli = source / "apps/cli/lib/bin.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// offline fixture")
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kw: launch_runtime.PINNED_COMMIT,
    )
    data = tmp_path / "data"
    _, env, _ = launch_runtime.prepare(
        source,
        data,
        "/usr/bin/node",
        3081,
        research_tools=True,
        datahub_url="http://127.0.0.1:18088",
    )
    control = json.loads((data / ".control/datahub.json").read_text())
    assert control["url"] == "http://127.0.0.1:18088"
    assert control["token"] not in str(env)
    assert (
        control["token"]
        not in (
            data / "runtime/home/.agent-presets/research-web/agent.cordis.yml"
        ).read_text()
    )


def test_launcher_enables_only_callable_datahub_tools(tmp_path, monkeypatch):
    from app.research_web import launch_runtime

    source = tmp_path / "source"
    cli = source / "apps/cli/lib/bin.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// offline fixture")
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kw: launch_runtime.PINNED_COMMIT,
    )
    monkeypatch.setattr(
        launch_runtime,
        "build_catalog",
        lambda: {
            "capabilities": [
                {"id": "search_news", "callable_source_count": 1},
                {"id": "search_web", "callable_source_count": 0},
                {"id": "fund_data", "callable_source_count": 2},
            ]
        },
    )

    data = tmp_path / "data"
    launch_runtime.prepare(source, data, "/usr/bin/node", 3081, research_tools=True)

    preset = (
        data / "runtime/home/.agent-presets/research-web/agent.cordis.yml"
    ).read_text()
    assert 'enabledTools: ["datahub_get_fund_data", "datahub_search_news"]' in preset
    assert "datahub_search_web" not in preset

    monkeypatch.setattr(
        launch_runtime,
        "build_catalog",
        lambda: {
            "capabilities": [
                {"id": "search_news", "callable_source_count": 0},
                {"id": "fund_data", "callable_source_count": 0},
            ]
        },
    )
    empty_data = tmp_path / "empty-data"
    launch_runtime.prepare(
        source, empty_data, "/usr/bin/node", 3081, research_tools=True
    )
    empty_preset = (
        empty_data / "runtime/home/.agent-presets/research-web/agent.cordis.yml"
    ).read_text()
    assert "enabledTools: []" in empty_preset


def test_launcher_rejects_invalid_datahub_tool_catalog(tmp_path, monkeypatch):
    from app.research_web import launch_runtime

    source = tmp_path / "source"
    cli = source / "apps/cli/lib/bin.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// offline fixture")
    monkeypatch.setattr(
        launch_runtime.subprocess,
        "check_output",
        lambda *args, **kw: launch_runtime.PINNED_COMMIT,
    )
    monkeypatch.setattr(launch_runtime, "build_catalog", dict)
    data = tmp_path / "data"

    with pytest.raises(RuntimeError, match="工具目录无效"):
        launch_runtime.prepare(source, data, "/usr/bin/node", 3081, research_tools=True)
    assert not (
        data / "runtime/home/.agent-presets/research-web/agent.cordis.yml"
    ).exists()


@pytest.mark.asyncio
async def test_profile_malformed_real_cells_do_not_merge_fields_and_decorated_missing_is_null(
    hub_module, tmp_path
):
    html = '<table class="info"><tr><th>基金代码</th><td>000001（前端）、000002（后端）<th>基金类型</th><td>混合型-灵活</td></td></tr><tr><th>净资产规模</th><td>39.38亿元（截止至：2026年06月30日）<th>份额规模</th><td><a href="gmbd_000001.html">24.0598亿份</a>（截止至：2026年06月30日）</td></td></tr><tr><th>销售服务费率</th><td>---（每年）</td><th>最高认购费率</th><td>1.00%（前端）</td></tr></table>'
    hub, _, sid = make_hub(
        hub_module, tmp_path, lambda r: httpx.Response(200, text=html)
    )
    result = await hub.query(
        sid, "malformed-profile", hub_module.Query(source="fund_profile", code="000001")
    )
    rows = {row["field"]: row for row in hub.rows(sid, result["dataset_id"])["items"]}
    assert rows["基金代码"]["value"] == "000001（前端）、000002（后端）"
    assert rows["净资产规模"]["value"] == "39.38亿元（截止至：2026年06月30日）"
    assert rows["销售服务费率"]["value"] is None
    assert rows["销售服务费率"]["original_value"] == "---（每年）"
    await hub.close()


@pytest.mark.asyncio
async def test_page_size_change_and_row_byte_budgets_are_partial(
    hub_module, tmp_path, monkeypatch
):
    providers = importlib.import_module("app.research_web.datahub.providers")

    def respond(request):
        page = int(request.url.params["pageIndex"])
        return httpx.Response(
            200, json=nav_page([nav_row(f"2025-12-{32 - page:02d}")], 3, page, page)
        )

    hub, _, sid = make_hub(hub_module, tmp_path, respond)
    result = await hub.query(sid, "sizes", query(hub_module))
    assert (
        result["status"] == "partial"
        and "provider_page_size_changed" in result["limitations"]
    )
    await hub.close()
    monkeypatch.setattr(providers, "MAX_ROWS", 1)
    hub = hub_module.DataHub(Store(tmp_path), transport=httpx.MockTransport(respond))
    result = await hub.query(sid, "rows", query(hub_module, refresh=True))
    assert result["status"] == "partial" and "row_limit" in result["limitations"]
    assert result["row_count"] <= 1
    await hub.close()
    monkeypatch.setattr(providers, "MAX_ROWS", 5000)
    monkeypatch.setattr(providers, "MAX_QUERY_BYTES", 300)
    hub = hub_module.DataHub(Store(tmp_path), transport=httpx.MockTransport(respond))
    result = await hub.query(sid, "bytes", query(hub_module, refresh=True))
    assert result["status"] == "partial" and "query_size_limit" in result["limitations"]
    await hub.close()


@pytest.mark.asyncio
async def test_cls_timestamp_validation_and_ttl_expiry(
    hub_module, tmp_path, monkeypatch
):
    calls = []

    def respond(request):
        calls.append(request)
        assert (
            request.url.host == "www.cls.cn"
            and request.url.params["name"] == "telegraphList"
        )
        return httpx.Response(
            200,
            json={
                "errno": 0,
                "data": {
                    "roll_data": [
                        {"id": 123, "ctime": 1788326831, "content": "<em>news</em>"}
                    ]
                },
            },
        )

    hub, _, sid = make_hub(hub_module, tmp_path, respond)
    q = hub_module.Query(source="cls_telegraph", limit=2)
    first = await hub.query(sid, "cls-1", q)
    assert first["sample"][0]["content"] == "news"
    assert first["sample"][0]["source_url"] == "https://www.cls.cn/detail/123"
    assert (await hub.query(sid, "cls-2", q))["cache_hit"]

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(UTC) + timedelta(seconds=61)

    monkeypatch.setattr(hub_module, "datetime", Later)
    later = await hub.query(sid, "cls-3", q)
    assert not later["cache_hit"] and later["dataset_id"] != first["dataset_id"]
    assert len(calls) == 2
    await hub.close()


@pytest.mark.asyncio
async def test_cls_keeps_valid_rows_when_provider_includes_empty_content(
    hub_module, tmp_path
):
    def respond(request):
        return httpx.Response(
            200,
            json={
                "errno": 0,
                "data": {
                    "roll_data": [
                        {"id": 123, "ctime": 1788326831, "content": "有效电报"},
                        {"id": 124, "ctime": 1788326830, "content": ""},
                    ]
                },
            },
        )

    hub, _, sid = make_hub(hub_module, tmp_path, respond)
    result = await hub.query(
        sid, "cls-partial", hub_module.Query(source="cls_telegraph", limit=2)
    )
    assert result["status"] == "partial"
    assert result["row_count"] == 1
    assert any("1 条空内容已跳过" in item for item in result["limitations"])
    await hub.close()


def test_non_ascii_auth_and_empty_userinfo_are_rejected(hub_module, tmp_path):
    store = Store(tmp_path)
    hub = hub_module.DataHub(store)
    assert not hub.authenticate("é" * 43)
    with pytest.raises(StoreError):
        hub_module.load_control(tmp_path / "unsafe", "http://@127.0.0.1:8088")


@pytest.mark.asyncio
async def test_crash_between_snapshot_renames_does_not_poison_catalog_or_retry_pending(
    hub_module, tmp_path, monkeypatch
):
    from app.research_web.datahub.providers import Result

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=nav_page([nav_row("2025-12-31")], 1))

    hub, store, sid = make_hub(hub_module, tmp_path, respond)
    healthy = await hub.query(sid, "healthy", query(hub_module))
    interrupted_query = hub_module.Query(source="fund_nav", code="000002")
    hub.snapshots.receipt(
        sid,
        "interrupted",
        {
            "status": "pending",
            "fingerprint": interrupted_query.fingerprint(include_refresh=True),
        },
    )
    original_rename = os.rename
    destinations = []

    class ProcessExit(BaseException):
        pass

    def crash_before_second_rename(src, dst, **kwargs):
        destinations.append(dst)
        if len(destinations) == 2:
            raise ProcessExit
        return original_rename(src, dst, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "rename", crash_before_second_rename)
        with pytest.raises(ProcessExit):
            hub.snapshots.publish(
                sid,
                interrupted_query,
                Result(
                    rows=[{"date": "2025-12-31", "unit_nav": 1.2}],
                    status="complete",
                    pagination_complete=True,
                    raw=[b'{"offline":"raw"}'],
                ),
            )
    assert len(destinations) == 2
    orphan_id = destinations[0]
    await hub.close()
    restarted = hub_module.DataHub(
        Store(tmp_path), transport=httpx.MockTransport(respond)
    )
    assert [item["dataset_id"] for item in restarted.summaries(sid)] == [
        healthy["dataset_id"]
    ]
    assert restarted.rows(sid, healthy["dataset_id"])["total"] == 1
    assert restarted.store.files(sid) == []
    with pytest.raises(StoreError):
        restarted.detail(sid, orphan_id)
    with pytest.raises(StoreError, match="不自动重发"):
        await restarted.query(sid, "interrupted", interrupted_query)
    assert len(calls) == 1
    fresh = await restarted.query(sid, "fresh-call", interrupted_query)
    assert len(calls) == 2 and fresh["dataset_id"] not in {
        orphan_id,
        healthy["dataset_id"],
    }
    assert len(restarted.summaries(sid)) == 2
    # The process-exit orphan remains isolated for diagnosis, never auto-deleted or listed.
    assert any(
        path.name == orphan_id or path.name == ".pending-" + orphan_id
        for path in (store.directory(sid) / "inputs/datasets").iterdir()
    )
    await restarted.close()
