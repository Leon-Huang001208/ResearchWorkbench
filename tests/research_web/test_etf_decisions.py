"""Independent accounting and causal acceptance; all fixtures are synthetic."""

import unittest
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from app.research_web.portfolio_decisions.engine import PaperEngine, replay
from app.research_web.portfolio_decisions.models import ReplayRequest
from app.research_web.portfolio_decisions.store import DecisionStore


def sample():
    days = []
    day = date(2026, 1, 5)
    while len(days) < 75:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day += timedelta(days=1)
    assets = []
    bars = []
    for symbol in ("510001.SH", "159001.SZ"):
        assets.append(
            {
                "symbol": symbol,
                "industry": "broad",
                "eligible_from": days[0],
                "eligible_until": days[-1],
                "known_at": days[0] + "T00:00:00+08:00",
                "rule_version": "fixture-only",
                "lot_size": 10,
                "price_tick": "0.001",
                "turnaround": "T+1",
            }
        )
        for index, day in enumerate(days):
            bars.append(
                {
                    "symbol": symbol,
                    "day": day,
                    "known_at": day + "T15:01:00+08:00",
                    "execution_known_at": day + "T09:25:00+08:00",
                    "open": "1.000",
                    "close": "1.000",
                    "total_return_index": str(100 + index),
                    "volume_shares": 100000,
                    "suspended": False,
                    "upper_limit": "1.100",
                    "lower_limit": "0.900",
                    "cash_distribution": "0",
                    "split_ratio": "1",
                }
            )
    return {
        "strategy": {
            "strategy_id": "fixture-etf",
            "version": "1",
            "effective_from": days[0],
            "asset_pool": [a["symbol"] for a in assets],
            "benchmark": "fixture-index",
            "initial_cash": "10000",
            "risk_budget": "0.30",
            "security_cap": "0.15",
            "industry_caps": {"broad": "0.30"},
            "min_cash_weight": "0.70",
            "fee_rate": "0.001",
            "minimum_fee": "1",
            "slippage_bps": "0",
            "max_price_deviation": "0.05",
            "participation_rate": "0.1",
            "order_lifetime_sessions": 2,
        },
        "snapshot": {
            "source": "synthetic-fixture",
            "source_ref": "acceptance-fixture",
            "data_version": "1",
            "currency": "CNY",
            "price_unit": "CNY/share",
            "volume_unit": "share",
            "price_basis": "exchange_unadjusted",
            "return_basis": "total_return_index",
            "volume_basis": "daily_post_session_participation",
            "calendar": days,
            "calendar_known_at": days[0] + "T00:00:00+08:00",
            "assets": assets,
            "bars": bars,
            "benchmark": [
                {"day": d, "known_at": d + "T15:01:00+08:00", "total_return_index": str(100 + i)}
                for i, d in enumerate(days)
            ],
            "missing": [],
            "provenance": "engineering_only",
        },
        "start_date": days[0],
        "end_date": days[-1],
        "manual_decisions": [],
    }


def request(value=None):
    return ReplayRequest.model_validate(value or sample())


def test_caps_preserve_cash_and_replay_matches_forward():
    body = request()
    result = replay(body)
    intent = next(
        x["intent"] for x in result["events"] if x.get("intent") and x["intent"]["weights"]
    )
    assert intent["weights"] == {"159001.SZ": "0.15", "510001.SH": "0.15"}
    assert intent["cash_weight"] == "0.7"
    engine = PaperEngine(body.strategy, body.snapshot, body.manual_decisions)
    for day in body.snapshot.calendar:
        engine.step(day)
    assert engine.result() == {
        key: value
        for key, value in result.items()
        if key not in {"ledger_status", "ledger_gap", "requested_range"}
    }
    assert result["real_chain"]["status"] == "BLOCKED"


def test_future_prices_and_future_eligibility_do_not_change_past_business_events():
    raw = sample()
    cutoff = raw["snapshot"]["calendar"][64]
    raw["end_date"] = cutoff
    before = replay(request(raw))
    changed = deepcopy(raw)
    for bar in changed["snapshot"]["bars"]:
        if bar["day"] > cutoff:
            bar["total_return_index"] = "999999"
    assert replay(request(changed))["events"] == before["events"]
    changed = deepcopy(raw)
    for bar in changed["snapshot"]["bars"]:
        if bar["day"] <= cutoff:
            bar["known_at"] = "2027-01-01T00:00:00+08:00"
    assert not any(
        event.get("signal", {}).get("selected") for event in replay(request(changed))["events"]
    )


def test_partial_fills_cash_and_stock_conserve_and_restore():
    raw = sample()
    for bar in raw["snapshot"]["bars"]:
        bar["volume_shares"] = 100
    body = request(raw)
    result = replay(body)
    buys = [fill for fill in result["fills"] if fill["side"] == "buy"]
    assert buys and all(fill["quantity"] == 10 for fill in buys)
    from decimal import Decimal

    spent = sum(Decimal(fill["notional"]) + Decimal(fill["fee"]) for fill in buys)
    assert Decimal(result["state"]["cash"]) == Decimal(10000) - spent
    assert sum(lot["quantity"] for lot in result["state"]["lots"]) == sum(
        fill["quantity"] for fill in buys
    )
    engine = PaperEngine(body.strategy, body.snapshot, [])
    days = body.snapshot.calendar
    for day in days[:66]:
        engine.step(day)
    restored = PaperEngine.restore(body.strategy, body.snapshot, [], engine.checkpoint())
    restored.step(days[65])  # retry must have no effect
    for day in days[66:]:
        restored.step(day)
    assert restored.result() == {
        key: value
        for key, value in result.items()
        if key not in {"ledger_status", "ledger_gap", "requested_range"}
    }


def check_invalid_data_and_execution_do_not_invent_fills(mutation):
    raw = sample()
    for bar in raw["snapshot"]["bars"]:
        if mutation == "suspended":
            bar["suspended"] = True
        if mutation == "limit":
            bar["open"] = "1.100"
        if mutation == "price":
            bar["open"] = None
        if mutation == "stale":
            bar["known_at"] = "2027-01-01T00:00:00+08:00"
    if mutation == "nav":
        raw["snapshot"]["price_basis"] = "nav"
    if mutation == "units":
        raw["snapshot"]["volume_unit"] = "lot"
    if mutation in {"nav", "units"}:
        with unittest.TestCase().assertRaises(ValueError):
            request(raw)
    else:
        assert replay(request(raw))["fills"] == []


def check_transactional_idempotency_conflicts_and_database_restart(tmp_path):
    store = DecisionStore(tmp_path)
    body = request()
    first = store.run(body, "fixture-key")
    assert DecisionStore(tmp_path).run(body, "fixture-key") == first
    assert store.run(body, "different-key") == first
    assert len(store.list_runs()) == 1
    raw = sample()
    raw["strategy"]["initial_cash"] = "20000"
    with unittest.TestCase().assertRaisesRegex(ValueError, "idempotency_conflict"):
        store.run(request(raw), "fixture-key")


def test_missing_industry_configuration_is_rejected():
    raw = sample()
    raw["strategy"]["industry_caps"] = {}
    with unittest.TestCase().assertRaises(ValueError):
        request(raw)


def test_invalid_data_and_execution_do_not_invent_fills():
    for mutation in ("suspended", "limit", "price", "stale", "nav", "units"):
        check_invalid_data_and_execution_do_not_invent_fills(mutation)


def test_transactional_idempotency_conflicts_and_database_restart():
    with TemporaryDirectory() as directory:
        check_transactional_idempotency_conflicts_and_database_restart(Path(directory))


def test_t_plus_one_only_sells_old_inventory_and_preserves_new_lot():
    body = request()
    engine = PaperEngine(body.strategy, body.snapshot, [])
    day = body.snapshot.calendar[65]
    symbol = body.strategy.asset_pool[0]
    engine.state["lots"] = [
        {
            "symbol": symbol,
            "quantity": 10,
            "buy_day": body.snapshot.calendar[64].isoformat(),
            "fill_id": "old",
        },
        {"symbol": symbol, "quantity": 10, "buy_day": day.isoformat(), "fill_id": "new"},
    ]
    engine.orders = [
        {
            "id": "sell-fixture",
            "symbol": symbol,
            "side": "sell",
            "quantity": 20,
            "remaining": 20,
            "earliest_day": day.isoformat(),
            "expires_day": day.isoformat(),
            "status": "submitted",
            "reference_price": "1",
        }
    ]
    engine.step(day)
    assert engine.fills[0]["quantity"] == 10
    assert engine.state["lots"] == [
        {"symbol": symbol, "quantity": 10, "buy_day": day.isoformat(), "fill_id": "new"}
    ]
    assert engine.orders[0]["remaining"] == 10


def test_manual_veto_saves_evidence_and_separates_mechanical_shadow():
    raw = sample()
    day = raw["snapshot"]["calendar"][64]
    raw["manual_decisions"] = [
        {
            "day": day,
            "action": "veto",
            "reason": "fixture human veto",
            "evidence_ref": "fixture-evidence",
            "decided_at": day + "T17:00:00+08:00",
        }
    ]
    result = replay(request(raw))
    veto = next(
        event for event in result["events"] if event.get("decision", {}).get("action") == "veto"
    )
    assert veto["decision"]["reason"] == "fixture human veto"
    assert veto["decision"]["order_ids"] == []
    assert result["curve"][65]["cash"] == "10000"
    assert result["mechanical_shadow"]["curve"][65]["cash"] == "7017.02"


def test_fractional_corporate_action_rejects_and_rolls_back_entire_session():
    raw = sample()
    day = raw["snapshot"]["calendar"][65]
    for bar in raw["snapshot"]["bars"]:
        if bar["day"] == day:
            bar["split_ratio"] = "1.5"
            bar["cash_distribution"] = "0.1"
    body = request(raw)
    engine = PaperEngine(body.strategy, body.snapshot, [])
    engine.state["lots"] = [
        {
            "symbol": body.strategy.asset_pool[0],
            "quantity": 1,
            "buy_day": raw["snapshot"]["calendar"][64],
            "fill_id": "fixture",
        }
    ]
    before = engine.checkpoint()
    with unittest.TestCase().assertRaisesRegex(
        ValueError, "fractional_corporate_action_unsupported"
    ):
        engine.step(date.fromisoformat(day))
    assert engine.checkpoint() == before


def load_tests(loader, tests, pattern):
    """Support stdlib unittest and pytest without installing any dependencies."""
    return unittest.TestSuite(
        unittest.FunctionTestCase(function)
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    )


def execution_case(*, close="1", minimum_fee="0"):
    raw = sample()
    raw["strategy"].update(
        security_cap="0.2",
        industry_caps={"broad": "1"},
        risk_budget="1",
        min_cash_weight="0",
        fee_rate="0",
        minimum_fee=minimum_fee,
    )
    day = raw["snapshot"]["calendar"][65]
    first, second = raw["strategy"]["asset_pool"]
    for bar in raw["snapshot"]["bars"]:
        if bar["day"] == day and bar["symbol"] == first:
            bar["close"] = close
    body = request(raw)
    engine = PaperEngine(body.strategy, body.snapshot, [])
    engine.state["cash"] = "8000"
    engine.state["lots"] = [
        {
            "symbol": first,
            "quantity": 2000,
            "buy_day": raw["snapshot"]["calendar"][64],
            "fill_id": "old",
        }
    ]
    engine.orders = [
        {
            "id": "buy-case",
            "symbol": second,
            "side": "buy",
            "quantity": 3000,
            "remaining": 3000,
            "earliest_day": day,
            "expires_day": day,
            "status": "submitted",
            "reference_price": "1",
        }
    ]
    engine.step(date.fromisoformat(day))
    return engine


def test_open_fills_do_not_depend_on_later_close():
    assert execution_case(close="1").fills == execution_case(close="2").fills


def test_post_fee_account_caps_include_existing_other_positions():
    engine = execution_case(minimum_fee="1000")
    assert engine.fills == []
    assert engine.state["cash"] == "8000"


def test_restore_cannot_skip_an_unprocessed_trading_day():
    body = request()
    engine = PaperEngine(body.strategy, body.snapshot, [])
    engine.step(body.snapshot.calendar[65])
    restored = PaperEngine.restore(body.strategy, body.snapshot, [], engine.checkpoint())
    before = restored.checkpoint()
    with unittest.TestCase().assertRaisesRegex(ValueError, "unprocessed_trading_day"):
        restored.step(body.snapshot.calendar[67])
    assert restored.checkpoint() == before


def test_late_corporate_action_cannot_certify_complete_ledger():
    raw = sample()
    day = raw["snapshot"]["calendar"][66]
    for bar in raw["snapshot"]["bars"]:
        if bar["day"] == day:
            bar["cash_distribution"] = "0.1"
            bar["split_ratio"] = "2"
            bar["execution_known_at"] = day + "T10:00:00+08:00"
    result = replay(request(raw))
    assert result["ledger_status"] == "BLOCKED"
    assert result["state"]["distributions"] == "0"
    assert result["state"]["last_day"] == raw["snapshot"]["calendar"][65]
    assert result["review"]["net_return"] is None
