import asyncio
import threading

import pandas as pd
import pytest

from app.research_web.datahub.contracts import BusinessQuery


class FakeWindAdapter:
    def __init__(self, *, available=True, rows=None):
        self.available = available
        self.rows = rows or [{"code": "600519.SH", "date": "2026-09-11", "close": 1500.0}]
        self.calls = []
        self.availability_calls = 0
        self.close_calls = 0

    def is_available(self):
        self.availability_calls += 1
        return self.available

    def fetch_daily_quotes(self, **kwargs):
        self.calls.append(("fetch_daily_quotes", kwargs))
        return pd.DataFrame(self.rows)

    def fetch_index_quotes(self, **kwargs):
        self.calls.append(("fetch_index_quotes", kwargs))
        return pd.DataFrame(self.rows)

    def fetch_market_snapshot(self, **kwargs):
        self.calls.append(("fetch_market_snapshot", kwargs))
        return pd.DataFrame(self.rows)

    def fetch_financial_statements(self, **kwargs):
        self.calls.append(("fetch_financial_statements", kwargs))
        return pd.DataFrame(self.rows)

    def fetch_fund_flow(self, **kwargs):
        self.calls.append(("fetch_fund_flow", kwargs))
        return pd.DataFrame(self.rows)

    def fetch_margin_trading(self, **kwargs):
        self.calls.append(("fetch_margin_trading", kwargs))
        return pd.DataFrame(self.rows)

    def fetch_block_trades(self, **kwargs):
        self.calls.append(("fetch_block_trades", kwargs))
        return pd.DataFrame(self.rows)

    def fetch_holder_data(self, **kwargs):
        self.calls.append(("fetch_holder_data", kwargs))
        return pd.DataFrame(self.rows)

    def close(self):
        self.close_calls += 1


class BlockingWindAdapter(FakeWindAdapter):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def is_available(self):
        self.availability_calls += 1
        self.started.set()
        self.release.wait(timeout=2)
        return True


def test_business_query_accepts_market_bars_asset_type_context():
    query = BusinessQuery(
        capability="market_bars",
        source="wind",
        parameters={
            "asset": "600519.SH",
            "asset_type": "stock",
            "start_date": "2026-09-01",
            "end_date": "2026-09-11",
        },
    )

    assert query.parameters["asset_type"] == "stock"


def test_business_query_accepts_market_snapshot_asset_type_context():
    query = BusinessQuery(
        capability="market_snapshot",
        source="wind",
        parameters={
            "assets": ["600519.SH"],
            "asset_type": "stock",
            "fields": ["close"],
        },
    )

    assert query.parameters["asset_type"] == "stock"


@pytest.mark.asyncio
async def test_wind_provider_uses_owned_isolated_adapter_and_closes_it(monkeypatch):
    from app.research_web.datahub.providers_wind import fetch
    from data_layer.adapters import wind as wind_module

    client_token = object()
    client_options = {}
    created = {}

    def make_client(**kwargs):
        client_options.update(kwargs)
        return client_token

    class OwnedAdapter(FakeWindAdapter):
        def __init__(self, *, client):
            assert client is client_token
            super().__init__()
            created["adapter"] = self

    monkeypatch.setattr(wind_module, "WindExcelClient", make_client)
    monkeypatch.setattr(wind_module, "WindAdapter", OwnedAdapter)
    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-11",
                "end_date": "2026-09-11",
            },
        )
    )

    assert result.status == "complete"
    assert client_options == {
        "visible": False,
        "isolated_workbook": True,
        "isolated_app": True,
    }
    assert created["adapter"].close_calls == 1


@pytest.mark.asyncio
async def test_wind_provider_rejects_range_that_could_be_truncated_to_wsd_thousand_rows():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter(
        rows=[{"code": "600519.SH", "date": "2026-06-01", "close": 10.0} for _ in range(1000)]
    )
    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-01-01",
                "end_date": "2026-09-11",
            },
        ),
        adapter=adapter,
    )

    assert result.status == "failed"
    assert result.limitations == ["workload_too_large"]
    assert adapter.availability_calls == 0
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_wind_market_bars_marks_missing_requested_endpoint_partial():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter(rows=[{"code": "600519.SH", "date": "2026-09-09", "close": 10.0}])
    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        ),
        adapter=adapter,
    )

    assert result.status == "partial"
    assert "incomplete_requested_range" in result.limitations


@pytest.mark.asyncio
async def test_wind_provider_deadline_keeps_worker_busy_until_excel_returns(monkeypatch):
    from app.research_web.datahub import providers_wind

    monkeypatch.setattr(
        providers_wind,
        "WIND_PROVIDER_DEADLINE_SECONDS",
        0.01,
        raising=False,
    )
    query = BusinessQuery(
        capability="market_bars",
        source="wind",
        parameters={
            "asset": "600519.SH",
            "asset_type": "stock",
            "start_date": "2026-09-11",
            "end_date": "2026-09-11",
        },
    )
    blocking = BlockingWindAdapter()
    first = asyncio.create_task(providers_wind.fetch(query, adapter=blocking))
    assert await asyncio.to_thread(blocking.started.wait, 1)
    timed_out = await first
    assert timed_out.status == "failed"
    assert timed_out.limitations == ["deadline"]

    queued = FakeWindAdapter()
    busy = await providers_wind.fetch(query, adapter=queued)
    assert busy.status == "failed"
    assert busy.limitations == ["provider_busy"]
    assert queued.availability_calls == 0

    blocking.release.set()
    for _ in range(100):
        if blocking.close_calls:
            break
        await asyncio.sleep(0.01)
    assert blocking.close_calls == 1


@pytest.mark.asyncio
async def test_wind_provider_cancel_does_not_overlap_outstanding_excel_call():
    from app.research_web.datahub import providers_wind

    query = BusinessQuery(
        capability="market_bars",
        source="wind",
        parameters={
            "asset": "600519.SH",
            "asset_type": "stock",
            "start_date": "2026-09-11",
            "end_date": "2026-09-11",
        },
    )
    blocking = BlockingWindAdapter()
    first = asyncio.create_task(providers_wind.fetch(query, adapter=blocking))
    assert await asyncio.to_thread(blocking.started.wait, 1)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    queued = FakeWindAdapter()
    busy = await providers_wind.fetch(query, adapter=queued)
    assert busy.status == "failed"
    assert busy.limitations == ["provider_busy"]
    assert queued.availability_calls == 0

    blocking.release.set()
    for _ in range(100):
        if blocking.close_calls:
            break
        await asyncio.sleep(0.01)
    assert blocking.close_calls == 1


@pytest.mark.asyncio
async def test_wind_cleanup_failure_poison_blocks_new_owned_adapter(monkeypatch):
    from app.research_web.datahub import providers_wind

    class CleanupFailAdapter(FakeWindAdapter):
        def close(self):
            self.close_calls += 1
            raise RuntimeError("Excel quit was not confirmed")

    created = []

    def make_adapter():
        adapter = CleanupFailAdapter()
        created.append(adapter)
        return adapter

    monkeypatch.setattr(providers_wind, "_WIND_POISONED", False, raising=False)
    monkeypatch.setattr(providers_wind, "_make_adapter", make_adapter)
    query = BusinessQuery(
        capability="market_bars",
        source="wind",
        parameters={
            "asset": "600519.SH",
            "asset_type": "stock",
            "start_date": "2026-09-11",
            "end_date": "2026-09-11",
        },
    )

    failed = await providers_wind.fetch(query)
    assert failed.status == "failed"
    assert failed.limitations == ["wind_cleanup_failed"]
    busy = await providers_wind.fetch(query)
    assert busy.status == "failed"
    assert busy.limitations == ["provider_busy"]
    assert len(created) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "row"),
    [
        (
            BusinessQuery(
                capability="market_bars",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "asset_type": "stock",
                    "start_date": "2026-09-11",
                    "end_date": "2026-09-11",
                },
            ),
            {"code": "600519.SH", "date": "2026-09-11"},
        ),
        (
            BusinessQuery(
                capability="market_snapshot",
                source="wind",
                parameters={
                    "assets": ["600519.SH"],
                    "asset_type": "stock",
                    "fields": ["close"],
                },
            ),
            {"code": "600519.SH", "trade_date": "2026-09-11"},
        ),
        (
            BusinessQuery(
                capability="index_data",
                source="wind",
                parameters={"index": "000300.SH", "dataset": "quotes"},
            ),
            {"code": "000300.SH", "trade_date": "2026-09-11"},
        ),
        (
            BusinessQuery(
                capability="financials",
                source="wind",
                parameters={"asset": "600519.SH", "statements": ["metrics"]},
            ),
            {"code": "600519.SH", "trade_date": "2026-09-11"},
        ),
        (
            BusinessQuery(
                capability="market_activity",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "dataset": "fund_flow",
                    "start_date": "2026-09-11",
                    "end_date": "2026-09-11",
                },
            ),
            {"code": "600519.SH", "date": "2026-09-11"},
        ),
        (
            BusinessQuery(
                capability="market_activity",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "dataset": "margin_trading",
                    "start_date": "2026-09-11",
                    "end_date": "2026-09-11",
                },
            ),
            {"code": "600519.SH", "date": "2026-09-11"},
        ),
        (
            BusinessQuery(
                capability="market_activity",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "dataset": "holder_data",
                    "end_date": "2026-06-30",
                },
            ),
            {"code": "600519.SH", "report_date": "2026-06-30"},
        ),
    ],
)
async def test_wind_schema_rejects_rows_with_all_minimum_values_missing(query, row):
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(query, adapter=FakeWindAdapter(rows=[row]))

    assert result.status == "failed"
    assert result.limitations == ["critical_fields_missing"]
    assert result.rows == []


@pytest.mark.asyncio
async def test_wind_snapshot_requested_partial_fields_are_reported_partial():
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(
        BusinessQuery(
            capability="market_snapshot",
            source="wind",
            parameters={
                "assets": ["600519.SH"],
                "asset_type": "stock",
                "fields": ["close", "pb"],
            },
        ),
        adapter=FakeWindAdapter(
            rows=[
                {
                    "code": "600519.SH",
                    "trade_date": "2026-09-11",
                    "close": 10.0,
                    "pb": None,
                }
            ]
        ),
    )

    assert result.status == "partial"
    assert "partial_fields_missing" in result.limitations


@pytest.mark.asyncio
@pytest.mark.parametrize("asset_type", [None, "index", "etf"])
async def test_wind_market_snapshot_requires_explicit_stock_before_adapter_call(
    asset_type,
):
    from app.research_web.datahub.providers_wind import fetch

    parameters = {
        "assets": ["000300.SH"],
        "fields": ["close"],
    }
    if asset_type is not None:
        parameters["asset_type"] = asset_type
    query = BusinessQuery(
        capability="market_snapshot",
        source="wind",
        parameters=parameters,
    )
    adapter = FakeWindAdapter()

    result = await fetch(query, adapter=adapter)

    assert result.status == "failed"
    assert result.limitations == ["data_not_equivalent"]
    assert adapter.availability_calls == 0
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_wind_market_bars_requires_explicit_stock_asset_type():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter()
    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        ),
        adapter=adapter,
    )

    assert result.status == "failed"
    assert result.limitations == ["data_not_equivalent"]
    assert adapter.calls == []
    assert adapter.availability_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("asset_type", ["index", "etf"])
async def test_wind_market_bars_rejects_non_stock_asset_types(asset_type):
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter()
    query = BusinessQuery(
        capability="market_bars",
        source="wind",
        parameters={
            "asset": "000300.SH",
            "asset_type": asset_type,
            "start_date": "2026-09-01",
            "end_date": "2026-09-11",
        },
    )
    result = await fetch(query, adapter=adapter)

    assert result.status == "failed"
    assert result.limitations == ["data_not_equivalent"]
    assert adapter.calls == []
    assert adapter.availability_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capability", "parameters", "expected_error"),
    [
        (
            "market_bars",
            {
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-11",
                "end_date": "2026-09-01",
            },
            "data_not_equivalent",
        ),
        (
            "market_bars",
            {
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2013-01-02",
                "end_date": "2026-09-11",
            },
            "workload_too_large",
        ),
        (
            "market_bars",
            {
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2000-01-01",
                "end_date": "2026-09-11",
            },
            "workload_too_large",
        ),
        (
            "market_activity",
            {
                "asset": "600519.SH",
                "dataset": "fund_flow",
                "start_date": "2026-09-11",
                "end_date": "2026-09-01",
            },
            "data_not_equivalent",
        ),
        (
            "market_activity",
            {
                "asset": "600519.SH",
                "dataset": "margin_trading",
                "start_date": "2000-01-01",
                "end_date": "2026-09-11",
            },
            "workload_too_large",
        ),
        (
            "market_activity",
            {
                "asset": "600519.SH",
                "dataset": "fund_flow",
                "start_date": [],
                "end_date": "2026-09-11",
            },
            "data_not_equivalent",
        ),
    ],
)
async def test_wind_historical_ranges_fail_before_adapter_call(
    capability, parameters, expected_error
):
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter()
    query = BusinessQuery(
        capability=capability,
        source="wind",
        parameters=parameters,
    )
    result = await fetch(query, adapter=adapter)

    assert result.status == "failed"
    assert result.limitations == [expected_error]
    assert adapter.calls == []
    assert adapter.availability_calls == 0


@pytest.mark.asyncio
async def test_wind_market_bars_allows_exactly_sixty_calendar_days():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter()
    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-07-14",
                "end_date": "2026-09-11",
            },
        ),
        adapter=adapter,
    )

    assert result.status == "complete"
    assert adapter.availability_calls == 1
    assert adapter.calls[0][0] == "fetch_daily_quotes"


@pytest.mark.asyncio
async def test_wind_provider_maps_closed_market_bars_query_to_existing_adapter():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter()
    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
                "frequency": "1d",
                "adjustment": "none",
            },
        ),
        adapter=adapter,
    )

    assert result.status == "complete"
    assert result.provider_id == "wind"
    assert result.rows[0]["close"] == 1500.0
    assert result.rows[0] == {
        "asset": "600519.SH",
        "date": "2026-09-11",
        "open": None,
        "high": None,
        "low": None,
        "close": 1500.0,
        "volume": None,
        "turnover": None,
        "turnover_rate_pct": None,
        "adjustment": "none",
    }
    assert result.fields["date"] == {"type": "date", "unit": None, "currency": None}
    assert result.fields["close"] == {
        "type": "number",
        "unit": "currency_per_share",
        "currency": "CNY",
    }
    assert adapter.calls == [
        (
            "fetch_daily_quotes",
            {
                "codes": ["600519.SH"],
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
                "adj_type": 1,
            },
        )
    ]


@pytest.mark.asyncio
async def test_wind_provider_rejects_non_scalar_adjustment_as_not_equivalent():
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
                "adjustment": [],
            },
        ),
        adapter=FakeWindAdapter(),
    )

    assert result.status == "failed"
    assert result.limitations == ["data_not_equivalent"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unexpected", ["formula", "credential", "path"])
async def test_wind_provider_rejects_unknown_adapter_columns(unexpected):
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        ),
        adapter=FakeWindAdapter(
            rows=[
                {
                    "code": "600519.SH",
                    "date": "2026-09-11",
                    "close": 1500.0,
                    unexpected: "must-not-be-published",
                }
            ]
        ),
    )

    assert result.status == "failed"
    assert result.rows == []
    assert result.raw == []
    assert result.limitations == ["data_not_equivalent"]


@pytest.mark.asyncio
async def test_wind_index_quotes_binding_has_a_real_closed_success_path():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter(
        rows=[
            {
                "code": "000300.SH",
                "trade_date": "2026-09-14",
                "name": "沪深300",
                "close": 4200,
                "pct_change": 0.5,
            }
        ]
    )
    result = await fetch(
        BusinessQuery(
            capability="index_data",
            source="wind",
            parameters={"index": "000300.SH", "dataset": "quotes"},
        ),
        adapter=adapter,
    )

    assert result.status == "complete"
    assert result.rows == [
        {
            "asset": "000300.SH",
            "as_of": "2026-09-14",
            "name": "沪深300",
            "price": 4200.0,
            "change_pct": 0.5,
        }
    ]
    assert result.as_of == "2026-09-14"
    assert result.fields["change_pct"]["unit"] == "percent"
    assert result.fields["price"] == {"type": "number", "unit": "points", "currency": None}


@pytest.mark.asyncio
async def test_wind_margin_units_match_reviewed_adapter_formulas():
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(
        BusinessQuery(
            capability="market_activity",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "dataset": "margin_trading",
                "start_date": "2026-09-11",
                "end_date": "2026-09-11",
            },
        ),
        adapter=FakeWindAdapter(
            rows=[
                {
                    "code": "600519.SH",
                    "date": "2026-09-11",
                    "margin_balance": 100.0,
                    "short_balance": 200.0,
                    "margin_buy": 10.0,
                    "margin_repay": 5.0,
                    "short_sell_vol": 3.0,
                    "short_repay_vol": 2.0,
                }
            ]
        ),
    )

    assert result.status == "complete"
    assert result.fields["margin_balance"] == {
        "type": "number",
        "unit": "currency",
        "currency": "CNY",
    }
    assert result.fields["short_balance"] == {
        "type": "number",
        "unit": "share",
        "currency": None,
    }
    assert result.fields["short_sell_vol"]["unit"] == "share"


@pytest.mark.asyncio
async def test_wind_block_trades_fails_closed_without_calling_abnormal_trade_adapter():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter()
    result = await fetch(
        BusinessQuery(
            capability="market_activity",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "dataset": "block_trades",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        ),
        adapter=adapter,
    )

    assert result.status == "failed"
    assert result.limitations == ["data_not_equivalent"]
    assert adapter.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "row"),
    [
        (
            BusinessQuery(
                capability="market_bars",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "asset_type": "stock",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-11",
                },
            ),
            {"code": "000001.SZ", "date": "2026-09-11", "close": 10.0},
        ),
        (
            BusinessQuery(
                capability="market_bars",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "asset_type": "stock",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-11",
                },
            ),
            {"date": "2026-09-11", "close": 10.0},
        ),
        (
            BusinessQuery(
                capability="market_bars",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "asset_type": "stock",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-11",
                },
            ),
            {"code": "600519.SH", "date": "2026-08-29", "close": 10.0},
        ),
        (
            BusinessQuery(
                capability="market_snapshot",
                source="wind",
                parameters={
                    "assets": ["600519.SH"],
                    "asset_type": "stock",
                    "fields": ["close"],
                },
            ),
            {"code": "000001.SZ", "trade_date": "2026-09-11", "close": 10.0},
        ),
        (
            BusinessQuery(
                capability="index_data",
                source="wind",
                parameters={"index": "000300.SH", "dataset": "quotes"},
            ),
            {
                "code": "000905.SH",
                "trade_date": "2026-09-11",
                "name": "中证500",
                "close": 6000.0,
                "pct_change": 0.1,
            },
        ),
        (
            BusinessQuery(
                capability="financials",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "statements": ["metrics"],
                    "periods": ["2026-06-30"],
                },
            ),
            {
                "code": "600519.SH",
                "trade_date": "2026-09-11",
                "report_date": "2026-03-31",
            },
        ),
        (
            BusinessQuery(
                capability="market_activity",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "dataset": "fund_flow",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-11",
                },
            ),
            {"code": "600519.SH", "date": "2026-09-12"},
        ),
        (
            BusinessQuery(
                capability="market_activity",
                source="wind",
                parameters={
                    "asset": "600519.SH",
                    "dataset": "holder_data",
                    "end_date": "2026-06-30",
                },
            ),
            {"code": "600519.SH", "report_date": "2026-03-31"},
        ),
    ],
)
async def test_wind_provider_rejects_response_identity_or_date_mismatch(query, row):
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(query, adapter=FakeWindAdapter(rows=[row]))

    assert result.status == "failed"
    assert result.rows == []
    assert result.raw == []
    assert result.limitations == ["data_not_equivalent"]


@pytest.mark.asyncio
async def test_wind_provider_reports_not_logged_in():
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        ),
        adapter=FakeWindAdapter(available=False),
    )
    assert result.status == "failed"
    assert result.limitations == ["wind_not_logged_in"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
                "frequency": "5m",
            },
        ),
        BusinessQuery(
            capability="market_snapshot",
            source="wind",
            parameters={
                "assets": ["600519.SH"],
                "asset_type": "stock",
                "fields": ["raw_formula"],
            },
        ),
        BusinessQuery(
            capability="index_data",
            source="wind",
            parameters={"index": "000300.SH", "dataset": "quotes", "date": "2026-09-11"},
        ),
        BusinessQuery(
            capability="fund_data",
            source="wind",
            parameters={"dataset": "holdings", "code": "000001"},
        ),
        BusinessQuery(
            capability="factor_macro",
            source="wind",
            parameters={"series": "CNY10Y", "start_date": "2026-01-01", "end_date": "2026-09-11"},
        ),
        BusinessQuery(
            capability="market_activity",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "dataset": "block_trades",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        ),
    ],
)
async def test_wind_provider_fails_closed_when_dataset_or_semantics_are_not_equivalent(query):
    from app.research_web.datahub.providers_wind import fetch

    result = await fetch(query, adapter=FakeWindAdapter())
    assert result.status == "failed"
    assert result.limitations == ["data_not_equivalent"]


@pytest.mark.asyncio
async def test_wind_provider_rejects_row_overflow_without_truncating():
    from app.research_web.datahub.providers_wind import fetch

    rows = [{"code": "600519.SH", "date": f"2026-09-{index:02d}"} for index in range(1, 5002)]
    result = await fetch(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        ),
        adapter=FakeWindAdapter(rows=rows),
    )
    assert result.status == "failed"
    assert result.limitations == ["row_limit"]
    assert result.rows == []


@pytest.mark.asyncio
async def test_wind_provider_reports_missing_reviewed_adapter_method():
    from app.research_web.datahub.providers_wind import fetch

    adapter = FakeWindAdapter()
    adapter.fetch_market_snapshot = None
    result = await fetch(
        BusinessQuery(
            capability="market_snapshot",
            source="wind",
            parameters={
                "assets": ["600519.SH"],
                "asset_type": "stock",
                "fields": ["close"],
            },
        ),
        adapter=adapter,
    )

    assert result.status == "failed"
    assert result.limitations == ["wind_method_unavailable"]


@pytest.mark.parametrize("key", ["formula", "expression", "path", "credentials"])
def test_wind_business_query_forbids_arbitrary_execution_inputs(key):
    with pytest.raises(ValueError):
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
                key: '=@wss("600519.SH","rt_last")',
            },
        )


def test_wind_catalog_and_broker_expose_only_bounded_business_bindings(monkeypatch):
    from app.research_web.datahub import broker, catalog

    monkeypatch.setattr(
        catalog, "_dependency_ready", lambda source_id, dependencies: source_id == "wind"
    )
    connection_statuses = {
        "wind": {
            "configured": True,
            "credential_store_available": True,
            "preferred_adapter": "excel",
        }
    }
    built = catalog.build_catalog(
        connection_statuses=connection_statuses,
        probes={"wind": {"health": "healthy"}},
        environ={},
    )
    wind_bindings = {
        row["capability_id"]: row["datasets"]
        for row in built["bindings"]
        if row["source_id"] == "wind" and row["implemented"]
    }
    assert wind_bindings == {
        "market_bars": ["daily_quotes"],
        "market_snapshot": ["realtime"],
        "index_data": ["quotes"],
        "financials": ["financial_statements"],
        "market_activity": ["fund_flow", "margin_trading", "holder_data"],
    }
    market_bars_binding = next(
        row
        for row in built["bindings"]
        if row["source_id"] == "wind" and row["capability_id"] == "market_bars"
    )
    assert market_bars_binding["assets"] == ["股票"]
    market_snapshot_binding = next(
        row
        for row in built["bindings"]
        if row["source_id"] == "wind" and row["capability_id"] == "market_snapshot"
    )
    assert market_snapshot_binding["assets"] == ["股票"]
    wind = next(row for row in built["sources"] if row["id"] == "wind")
    assert wind["markets"] == ["A股"]
    assert all(
        row["markets"] == ["A股"]
        for row in built["bindings"]
        if row["source_id"] == "wind" and row["implemented"]
    )
    assert not any(
        row["source_id"] == "wind" and row["capability_id"] in {"factor_macro", "fund_data"}
        for row in built["bindings"]
    )
    capabilities = {row["id"]: row for row in built["capabilities"]}
    assert capabilities["factor_macro"]["callable_source_count"] == 0

    monkeypatch.setattr(broker, "build_catalog", lambda **_kwargs: built)
    resolved = broker.resolve(
        BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-09-01",
                "end_date": "2026-09-11",
            },
        )
    )
    assert resolved.provider_id == "wind"
    assert resolved.query.source == "wind"


@pytest.mark.parametrize(
    ("installed_modules", "preferred_adapter", "dependency_ready", "callable_now"),
    [
        ({"WindPy"}, "auto", False, False),
        ({"xlwings"}, "auto", True, True),
        ({"xlwings"}, "excel", True, True),
        ({"WindPy", "xlwings"}, "client_api", False, False),
    ],
)
def test_wind_catalog_readiness_matches_excel_adapter_runtime(
    monkeypatch, installed_modules, preferred_adapter, dependency_ready, callable_now
):
    from app.research_web.datahub import catalog

    monkeypatch.setattr(
        catalog,
        "find_spec",
        lambda module: object() if module in installed_modules else None,
    )
    built = catalog.build_catalog(
        connection_statuses={
            "wind": {
                "configured": True,
                "credential_store_available": True,
                "preferred_adapter": preferred_adapter,
            }
        },
        probes={"wind": {"health": "healthy"}},
        environ={},
    )

    wind = next(row for row in built["sources"] if row["id"] == "wind")
    assert wind["readiness"]["dependency_ready"] is dependency_ready
    assert wind["readiness"]["callable"] is callable_now
