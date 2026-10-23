"""Offline terminal contracts; fixture scores are not investment validation."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.research_web.market_analysis import AnalysisHistory, analyze, past_percentile, walk_forward
from app.research_web.market_portfolio import PortfolioStore
from app.research_web.market_service import MarketError, MarketService


def portfolio(**changes):
    return {
        "as_of": "2026-10-22",
        "currency": "CNY",
        "cash": 1000,
        "source": "manual",
        "holdings": [{"asset": "000001.SZ", "quantity": 100}],
        **changes,
    }


def quote_snapshot():
    return {
        "snapshot_id": "a" * 36,
        "complete": True,
        "pagination_complete": True,
        "as_of": "2026-10-22T15:00:00+08:00",
        "retrieved_at": "2026-10-22T08:00:00+00:00",
        "provider": "eastmoney",
        "source_url": "https://quote.eastmoney.com/",
        "summary": {"quote_trade_date": "2026-10-22", "closing_snapshot": True},
        "rows": [
            {
                "asset": "000001.SZ",
                "price": 10,
                "price_basis": "quote",
                "quantity": 100,
                "change_pct": 2,
                "pe_dynamic": 12,
                "pb": 1,
                "as_of": "2026-10-22T15:00:00+08:00",
                "source_closed": True,
                "trade_status": "trading",
                "limit_status": "not_at_limit",
            }
        ],
    }


def test_preview_commit_restart_and_account_isolation(tmp_path):
    store = PortfolioStore(tmp_path / "alice")
    preview = store.preview(portfolio())
    assert store.read()["items"] == []
    assert preview["snapshot"]["holdings"][0]["quantity"] == 100
    assert PortfolioStore(tmp_path / "bob").read()["items"] == []
    with pytest.raises(MarketError):
        PortfolioStore(tmp_path / "bob").commit(preview["confirmation_token"])
    saved = PortfolioStore(tmp_path / "alice").commit(preview["confirmation_token"])
    assert saved["snapshot_id"]
    assert PortfolioStore(tmp_path / "alice").commit(preview["confirmation_token"]) == saved
    assert len(store.read()["items"]) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"cash": -1},
        {"cash": True},
        {"cash": float("nan")},
        {"currency": "XYZ"},
        {"as_of": "2999-01-01"},
        {"source": "jinyuan"},
        {"holdings": [{"asset": "../../x", "quantity": 1}]},
        {"holdings": [{"asset": "000001.SZ", "quantity": float("inf")}]},
        {"holdings": [{"asset": "000001.SZ", "quantity": 0}]},
        {"risk_profile": {"equity_min": 0.8, "equity_max": 0.2}},
        {"credentials": "never"},
    ],
)
def test_import_validation(tmp_path, changes):
    with pytest.raises(MarketError):
        PortfolioStore(tmp_path).preview(portfolio(**changes))
    assert not (tmp_path / "portfolios").exists()


def test_csv_preview_strict_and_bounded(tmp_path):
    store = PortfolioStore(tmp_path)
    body = portfolio(source="csv", csv_text="asset,quantity\n000001.SZ,42\n")
    body.pop("holdings")
    assert store.preview(body)["snapshot"]["holdings"][0]["quantity"] == 42
    for text in [
        "asset,quantity\n=cmd(),2",
        "asset,quantity\n000001.SZ,2\n000001.SZ,3",
        "asset,quantity\n000001.SZ,-2",
        "asset,quantity,secret\n000001.SZ,1,x",
    ]:
        with pytest.raises(MarketError):
            store.preview({**body, "csv_text": text})


def test_portfolio_projection_real_quote_and_missing_profile(tmp_path):
    store = PortfolioStore(tmp_path)
    saved = store.commit(store.preview(portfolio())["confirmation_token"])
    result = store.project(saved, quote_snapshot(), now=datetime(2026, 10, 22, 8, tzinfo=UTC))
    assert result["valuation"]["holdings_value"] == 1000
    assert result["valuation"]["equity_ratio"] == 0.5
    assert result["allocation"] is None
    assert result["profile_status"] == "observed_only"
    result = store.project(saved, None)
    assert result["valuation"]["total_value"] is None


def test_analysis_missing_never_becomes_neutral_or_allocation():
    result = analyze({}, [], horizon="swing")
    assert set(result["axes"]) == {"trend", "breadth", "sentiment", "funds", "valuation", "risk"}
    assert all(axis["score"] is None for axis in result["axes"].values())
    assert result["total_score"] is None and result["allocation"] is None
    assert result["validation"]["status"] == "insufficient_evidence"
    assert analyze({}, [], horizon="allocation")["horizon"]["days"] == [20, 60]


def test_analysis_uses_actual_rows_and_does_not_promote_growth_value():
    quotes = quote_snapshot()
    result = analyze({"quotes": quotes}, [], horizon="intraday")
    assert result["axes"]["valuation"]["metrics"]["median_pe_dynamic"] == 12
    assert result["axes"]["valuation"]["score"] is None
    assert result["axes"]["breadth"]["metrics"]["advancing_share"] == 1
    assert result["total_score"] is None


def test_past_only_percentile_rejects_future_and_small_samples():
    history = [
        {"date": f"2026-09-{day:02}", "known_at": f"2026-09-{day:02}T16:00:00+08:00", "value": day}
        for day in range(1, 26)
    ]
    assert past_percentile(13, history, "2026-10-01T12:00:00+08:00")["value"] == 50
    history.append({"date": "2026-10-02", "known_at": "2026-10-02T16:00:00+08:00", "value": -1000})
    assert past_percentile(13, history, "2026-10-01T12:00:00+08:00")["sample_count"] == 25
    assert past_percentile(1, history, "2026-09-02T12:00:00+08:00")["value"] is None
    history[0]["known_at"] = "2026-10-03T00:00:00+08:00"
    assert past_percentile(13, history, "2026-10-01T12:00:00+08:00")["sample_count"] == 24


def test_walk_forward_diagnostics_embargo_and_no_return_claim():
    rows = [
        {
            "date": f"2026-{month:02}-{day:02}",
            "known_at": f"2026-{month:02}-{day:02}T16:00:00+08:00",
        }
        for month in (7, 8, 9)
        for day in range(1, 29)
    ]
    result = walk_forward(rows, horizon="swing")
    assert result["returns"] is None
    for fold in result["folds"]:
        assert fold["train_end"] < fold["test_start"]
        assert fold["embargo_observations"] == 20


def test_completed_observation_restart_and_intraday_cannot_overwrite(tmp_path):
    history = AnalysisHistory(tmp_path)
    quotes = quote_snapshot()
    history.capture(quotes)
    assert len(history.read()) == 1
    intraday = deepcopy(quotes)
    intraday["summary"]["closing_snapshot"] = False
    intraday["rows"][0]["price"] = 90
    history.capture(intraday)
    loaded = AnalysisHistory(tmp_path).read()
    assert len(loaded) == 1
    assert loaded[0]["metrics"]["median_pe_dynamic"] == 12


def test_service_cache_get_never_fetches_or_writes(tmp_path):
    class Forbidden:
        async def fetch(self, *args, **kwargs):
            raise AssertionError("GET must not fetch")

    service = MarketService(tmp_path, Forbidden())
    assert service.analysis("swing")["total_score"] is None
    assert not service.root.exists()


def test_extended_index_key_isolated_from_legacy(tmp_path):
    class Provider:
        def __init__(self):
            self.calls = []

        async def fetch(self, section, **kwargs):
            self.calls.append((section, kwargs))
            return {**quote_snapshot(), "rows": [], "index_set": kwargs.get("index_set", "core-v1")}

        async def close(self):
            pass

    async def run():
        provider = Provider()
        service = MarketService(tmp_path, provider)
        first = await service.refresh(["indices"])
        await asyncio.gather(*(v["task"] for v in list(service._collectors.values())))
        second = await service.refresh(["indices"], index_set="terminal-v2")
        await asyncio.gather(*(v["task"] for v in list(service._collectors.values())))
        assert "indices" in service.request(first["request_id"])["sections"]
        assert "indices:terminal-v2" in service.request(second["request_id"])["sections"]
        assert "index_set" not in provider.calls[0][1]
        assert provider.calls[1][1]["index_set"] == "terminal-v2"
        assert "indices:terminal-v2" in MarketService(tmp_path).overview()["sections"]

    asyncio.run(run())


def test_descriptive_factor_scores_need_actual_inputs_and_prior_history():
    from app.research_web.market_analysis import factor_score

    history = [
        {"date": f"2026-09-{day:02}", "known_at": f"2026-09-{day:02}T16:00:00+08:00", "value": day}
        for day in range(1, 26)
    ]
    for axis in ("trend", "funds", "valuation", "risk"):
        assert factor_score(axis, 13, history, "2026-10-01T12:00:00+08:00")["score"] == 50
        assert factor_score(axis, 13, [], "2026-10-01T12:00:00+08:00")["score"] is None
    assert factor_score("breadth", 0.8, [], "2026-10-01T12:00:00+08:00")["score"] == 80
    assert factor_score("sentiment", 0.2, [], "2026-10-01T12:00:00+08:00")["score"] == 60


def test_analysis_daily_bars_horizon_metrics_are_real_and_past_only():
    from datetime import timedelta

    origin = datetime(2026, 4, 1, tzinfo=UTC)
    bars = [
        {"date": (origin + timedelta(days=i)).date().isoformat(), "close": 100 + i}
        for i in range(150)
    ]
    index = {
        **quote_snapshot(),
        "rows": [
            {
                "asset": "000001.SH",
                "as_of": "2026-10-22T15:00:00+08:00",
                "change_pct": 2,
                "daily_bars": bars,
                "daily_source": {
                    "provider": "eastmoney",
                    "source_url": "https://quote.eastmoney.com/",
                    "retrieved_at": "2026-10-22T08:00:00+00:00",
                    "adjustment": "price_index",
                },
            }
        ],
    }
    result = analyze({"indices": index}, [], horizon="swing")
    assert result["axes"]["trend"]["metrics"]["momentum_pct"] > 0
    assert result["axes"]["trend"]["score"] is not None
    assert result["axes"]["risk"]["metrics"]["maximum_drawdown_pct"] == 0
    future = {"date": "2027-01-01", "close": 99999}
    index["rows"][0]["daily_bars"].append(future)
    assert (
        analyze({"indices": index}, [], horizon="swing")["axes"]["trend"]["metrics"]
        == result["axes"]["trend"]["metrics"]
    )


def test_portfolio_symlink_and_corrupt_disk_fail_closed(tmp_path):
    destination = tmp_path / "outside"
    destination.mkdir()
    root = tmp_path / "user"
    root.symlink_to(destination, target_is_directory=True)
    with pytest.raises(MarketError):
        PortfolioStore(root).preview(portfolio())
    assert list(destination.iterdir()) == []
    store = PortfolioStore(tmp_path / "safe")
    preview = store.preview(portfolio())
    state_path = store.directory / "state.json"
    import json

    state = json.loads(state_path.read_text())
    for item in state["previews"].values():
        item["expires_at"] = "invalid"
    state_path.write_text(json.dumps(state))
    with pytest.raises(MarketError):
        store.commit(preview["confirmation_token"])


def test_csv_commit_survives_restart_and_expiry(tmp_path):
    clock = [datetime(2026, 10, 23, tzinfo=UTC)]
    store = PortfolioStore(tmp_path, now=lambda: clock[0])
    body = portfolio(source="csv", csv_text="asset,quantity\n000001.SZ,42\n")
    body.pop("holdings")
    preview = store.preview(body)
    saved = store.commit(preview["confirmation_token"])
    assert PortfolioStore(tmp_path, now=lambda: clock[0]).read()["items"][0] == saved
    from datetime import timedelta

    clock[0] += timedelta(minutes=16)
    with pytest.raises(MarketError):
        store.commit(preview["confirmation_token"])


def test_http_preview_commit_read_and_request_limits(tmp_path):
    from types import SimpleNamespace

    import httpx
    from fastapi import FastAPI

    from app.research_web.market_portfolio import MAX_IMPORT_BYTES
    from app.research_web.market_routes import router

    async def run():
        service = MarketService(tmp_path)
        app = FastAPI()
        app.state.research = SimpleNamespace(market=service)
        app.include_router(router)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/research/market/analysis?horizon=swing")
            assert response.status_code == 200 and not service.root.exists()
            assert (
                await client.get("/api/research/market/analysis?horizon=forever")
            ).status_code == 422
            preview = await client.post("/api/research/market/portfolios/preview", json=portfolio())
            assert preview.status_code == 200
            assert (await client.get("/api/research/market/portfolios")).json()["items"] == []
            commit = await client.post(
                "/api/research/market/portfolios",
                json={"confirmation_token": preview.json()["confirmation_token"]},
            )
            assert commit.status_code == 201
            assert len((await client.get("/api/research/market/portfolios")).json()["items"]) == 1
            assert (
                await client.post(
                    "/api/research/market/portfolios",
                    json={"confirmation_token": "x", "validated": True},
                )
            ).status_code == 409
            oversized = await client.post(
                "/api/research/market/portfolios/preview", content=b"x" * (MAX_IMPORT_BYTES + 1)
            )
            assert oversized.status_code == 413
            malformed = await client.post("/api/research/market/portfolios/preview", content=b"{")
            assert malformed.status_code == 400
            readiness = (await client.get("/api/research/market/portfolios/readiness")).json()
            assert (
                readiness["credentials_accepted"] is False and readiness["trading_enabled"] is False
            )

    asyncio.run(run())


def test_risk_and_valuation_scores_reverse_raw_level_rank():
    from app.research_web.market_analysis import factor_score

    history = [
        {"date": f"2026-09-{day:02}", "known_at": f"2026-09-{day:02}T16:00:00+08:00", "value": day}
        for day in range(1, 26)
    ]
    for axis in ("risk", "valuation"):
        low = factor_score(axis, 1, history, "2026-10-01T12:00:00+08:00")
        high = factor_score(axis, 25, history, "2026-10-01T12:00:00+08:00")
        assert low["level_percentile"] < high["level_percentile"]
        assert low["score"] > high["score"]
        assert high["direction"] == "inverse"


def test_optional_cost_zero_manual_and_csv_preserved_without_return_claim(tmp_path):
    store = PortfolioStore(tmp_path)
    for source in ("manual", "csv"):
        body = portfolio(source=source)
        if source == "csv":
            body.pop("holdings")
            body["csv_text"] = "asset,quantity,cost\n000001.SZ,42,0\n"
        else:
            body["holdings"][0]["cost"] = 0
        preview = store.preview(body)
        assert preview["snapshot"]["holdings"][0]["cost"] == 0
        saved = store.commit(preview["confirmation_token"])
        assert store.project(saved, quote_snapshot())["positions"][0]["cost"] == 0
        assert "return_pct" not in store.project(saved, quote_snapshot())["positions"][0]
    with pytest.raises(MarketError):
        store.preview(portfolio(holdings=[{"asset": "000001.SZ", "quantity": 1, "cost": -1}]))


def test_real_source_metadata_named_benchmark_survives_other_history_gaps():
    from datetime import timedelta

    origin = datetime(2026, 4, 1, tzinfo=UTC)
    bars = [
        {"date": (origin + timedelta(days=i)).date().isoformat(), "close": 100 + i, "volume": 20}
        for i in range(150)
    ]
    source = {
        "provider": "sina",
        "source_url": "https://quotes.sina.cn/cn/api/jsonp.php/var%20_k=/CN_MarketData.getKLineData",
        "symbol": "sh000300",
        "retrieved_at": "2026-10-22T08:00:00+00:00",
        "adjustment": "price_index",
        "return_basis": "price_index",
        "availability_basis": "first_observed",
        "historical_pit_verified": False,
        "last_close_cross_checked": True,
    }
    snapshot = {
        **quote_snapshot(),
        "rows": [
            {
                "asset": "000300.SH",
                "as_of": "2026-10-22T15:00:00+08:00",
                "daily_bars": bars,
                "daily_source": source,
            },
            {"asset": "399001.SZ", "daily_bars": [], "daily_error": "unavailable"},
        ],
    }
    for horizon in ("intraday", "swing", "allocation"):
        result = analyze({"indices:terminal-v2": snapshot}, [], horizon=horizon)
        assert result["axes"]["trend"]["score"] is not None
        features = result["axes"]["trend"]["index_features"]
        assert features["scope"] == {"type": "benchmark", "asset": "000300.SH"}
        assert features["catalog_complete"] is False
        assert features["historical_pit_verified"] is False
        assert result["axes"]["risk"]["score"] is not None
        assert result["total_score"] is None


def test_shanghai_midnight_asof_uses_local_day_through_preview_commit_restart(tmp_path):
    now = datetime(2026, 10, 22, 16, 30, tzinfo=UTC)
    store = PortfolioStore(tmp_path, now=lambda: now)
    preview = store.preview(portfolio(as_of="2026-10-23"))
    saved = store.commit(preview["confirmation_token"])
    assert saved["portfolio"]["as_of"] == "2026-10-23"
    assert PortfolioStore(tmp_path, now=lambda: now).read()["items"][0] == saved


@pytest.mark.parametrize(
    "timestamp",
    ["1990-01-01T15:00:00+08:00", "not-a-date", "2999-01-01T15:00:00+08:00", "2026-10-22T15:00:00"],
)
def test_portfolio_invalid_or_incoherent_row_time_cannot_value(tmp_path, timestamp):
    store = PortfolioStore(tmp_path)
    saved = store.commit(store.preview(portfolio())["confirmation_token"])
    quotes = quote_snapshot()
    quotes["rows"][0]["as_of"] = timestamp
    result = store.project(saved, quotes, now=datetime(2026, 10, 22, 8, tzinfo=UTC))
    assert result["positions"][0]["timestamp_valid"] is False
    assert result["valuation"]["total_value"] is None
    assert result["valuation"]["missing_assets"] == ["000001.SZ"]


def test_service_stale_projection_blocks_old_cached_valuation(tmp_path):
    service = MarketService(tmp_path, now=lambda: datetime(2026, 10, 23, 3, 0, tzinfo=UTC))
    store = PortfolioStore(service.root, now=service.now)
    store.commit(store.preview(portfolio())["confirmation_token"])
    service._snapshots["quotes"] = quote_snapshot()
    result = service.portfolios()["items"][0]
    assert result["valuation"]["cache_status"] == "stale"
    assert result["valuation"]["stale"] is True
    assert result["valuation"]["total_value"] is None


def test_portfolio_suspended_reference_preserves_basis_without_current_total(tmp_path):
    store = PortfolioStore(tmp_path)
    saved = store.commit(store.preview(portfolio())["confirmation_token"])
    quotes = quote_snapshot()
    quotes["rows"][0].update(trade_status="suspended", price_basis="suspended_reference")
    result = store.project(saved, quotes)
    position = result["positions"][0]
    assert position["trade_status"] == "suspended"
    assert position["price_basis"] == "suspended_reference"
    assert position["reference_price"] == 10
    assert position["market_value"] is None
    assert result["valuation"]["total_value"] is None


def test_fresh_service_projection_values_coherent_current_day_quote(tmp_path):
    service = MarketService(tmp_path, now=lambda: datetime(2026, 10, 22, 8, 0, tzinfo=UTC))
    store = PortfolioStore(service.root, now=service.now)
    store.commit(store.preview(portfolio())["confirmation_token"])
    service._snapshots["quotes"] = quote_snapshot()
    result = service.portfolios()["items"][0]
    assert result["valuation"]["cache_status"] == "ready"
    assert result["valuation"]["stale"] is False
    assert result["valuation"]["total_value"] == 2000


@pytest.mark.parametrize(
    "change",
    [
        {"as_of": "2026-10-21T15:00:00+08:00"},
        {"retrieved_at": "2999-01-01T16:00:00+08:00"},
        {"retrieved_at": "not-a-date"},
        {"provider": None},
        {"source_url": None},
    ],
)
def test_portfolio_source_snapshot_coherence_required(tmp_path, change):
    store = PortfolioStore(tmp_path)
    saved = store.commit(store.preview(portfolio())["confirmation_token"])
    quotes = {**quote_snapshot(), **change}
    result = store.project(saved, quotes, now=datetime(2026, 10, 22, 8, tzinfo=UTC))
    assert result["valuation"]["total_value"] is None


def style_snapshot():
    from datetime import timedelta

    origin = datetime(2026, 4, 1, tzinfo=UTC)
    rows = []
    for offset, code in enumerate(range(399372, 399378)):
        bars = [
            {"date": (origin + timedelta(days=i)).date().isoformat(), "close": 100 + i}
            for i in range(100)
        ]
        rows.append(
            {
                "asset": f"{code}.SZ",
                "as_of": "2026-10-22T10:00:00+08:00",
                "price": 220 + offset,
                "change_pct": 2 if offset % 2 == 0 else -1,
                "previous_close": bars[-1]["close"],
                "daily_history_status": "ready",
                "daily_bars": bars,
                "daily_source": {
                    "provider": "sina",
                    "source_url": "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
                    "symbol": f"sz{code}",
                    "retrieved_at": "2026-10-22T02:01:00+00:00",
                    "adjustment": "price_index",
                    "return_basis": "price_index",
                    "availability_basis": "first_observed",
                    "historical_pit_verified": False,
                    "last_close_cross_checked": True,
                },
            }
        )
    return {**quote_snapshot(), "as_of": "2026-10-22T10:00:00+08:00", "rows": rows}


def test_style_profile_uses_distinct_intraday_20_and_60_session_returns():
    snapshot = style_snapshot()
    intraday = analyze({"indices:terminal-v2": snapshot}, [], horizon="intraday")["style_profile"]
    assert intraday["cells"][0]["return_pct"] == 2
    assert intraday["growth_minus_value_pp"] == 3
    assert intraday["style_dominance"] == "growth"
    for horizon, lookback in (("swing", 20), ("allocation", 60)):
        profile = analyze({"indices:terminal-v2": snapshot}, [], horizon=horizon)["style_profile"]
        assert profile["cells"][0]["return_pct"] == pytest.approx(
            (220 / snapshot["rows"][0]["daily_bars"][-lookback]["close"] - 1) * 100
        )
        assert profile["cells"][0]["return_pct"] != 2
        assert profile["provisional"] is True
        assert profile["micro"]["status"] == "unavailable"
        assert profile["size_dominance"] == "small"


@pytest.mark.parametrize("mutation", ["missing", "mixed_date", "history_mismatch", "future_bar"])
def test_style_profile_missing_or_incoherent_cells_never_balanced(mutation):
    snapshot = style_snapshot()
    if mutation == "missing":
        snapshot["rows"].pop()
    elif mutation == "mixed_date":
        snapshot["rows"][0]["as_of"] = "2026-10-21T10:00:00+08:00"
    elif mutation == "history_mismatch":
        snapshot["rows"][0]["previous_close"] = 1
    else:
        snapshot["rows"][0]["daily_bars"].append({"date": "2999-01-01", "close": 1})
    profile = analyze({"indices:terminal-v2": snapshot}, [], horizon="swing")["style_profile"]
    assert profile["style_dominance"] == "unknown"
    assert profile["size_dominance"] == "unknown"
    assert profile["growth_minus_value_pp"] is None


def test_style_profile_fixed_deadband_and_no_style_score_preference():
    snapshot = style_snapshot()
    for row in snapshot["rows"]:
        row["change_pct"] = 1
    result = analyze({"indices:terminal-v2": snapshot}, [], horizon="intraday")
    profile = result["style_profile"]
    assert profile["style_dominance"] == profile["size_dominance"] == "balanced"
    assert profile["deadband_pp"] == 0.1
    assert result["total_score"] is None


@pytest.mark.parametrize("mutation", ["delete_intermediate", "different_base", "missing_holiday"])
def test_style_requires_identical_comparison_date_sequence(mutation):
    from datetime import date, timedelta

    snapshot = style_snapshot()
    # Leave real gaps between observations so an intermediate-calendar mismatch
    # can remain individually ordered, positive and previous-close crosschecked.
    for row in snapshot["rows"]:
        for i, bar in enumerate(row["daily_bars"]):
            bar["date"] = (date(2026, 1, 1) + timedelta(days=2 * i)).isoformat()
    bars = snapshot["rows"][0]["daily_bars"]
    if mutation == "delete_intermediate":
        bars.pop(-10)
    elif mutation == "different_base":
        bars[-20]["date"] = (date.fromisoformat(bars[-20]["date"]) - timedelta(days=1)).isoformat()
    else:
        # Same base/last dates and count; only a claimed intermediate trading
        # day differs, as with one feed omitting a holiday/observed session.
        bars[-10]["date"] = (date.fromisoformat(bars[-10]["date"]) - timedelta(days=1)).isoformat()
    profile = analyze({"indices:terminal-v2": snapshot}, [], horizon="swing")["style_profile"]
    assert profile["status"] == "incomplete"
    assert profile["style_dominance"] == profile["size_dominance"] == "unknown"
    assert profile["growth_minus_value_pp"] is None
    assert profile["comparison_window_status"] == "mismatch"
    assert profile["cells"][0]["status"] == "unavailable"
    assert profile["cells"][0]["reason"]
