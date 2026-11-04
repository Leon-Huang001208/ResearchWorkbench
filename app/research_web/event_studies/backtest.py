"""Long-only/cash daily replay; historical qualification is verified before calling."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from math import sqrt
from statistics import mean, pstdev

from core.observability import get_logger

from .contracts import StudyError, number, stamp

log = get_logger(__name__)
ZERO, ONE = Decimal(0), Decimal(1)


def metrics(curve, initial_cash):
    values = [float(row["nav"]) for row in curve]
    initial = float(initial_cash)
    prior = [initial] + values[:-1]
    returns = [v / p - 1 for v, p in zip(values, prior)]
    peak, drawdown = initial, 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = max(drawdown, 1 - value / peak)
    deviation = pstdev(returns) if len(returns) > 1 else 0
    return {
        "net_return": values[-1] / initial - 1,
        "cagr": (values[-1] / initial) ** (252 / len(values)) - 1,
        "sharpe": mean(returns) / deviation * sqrt(252) if deviation else None,
        "max_drawdown": drawdown,
        "daily_returns": returns,
    }


def replay(calendar, proxy, bars, signals, *, initial_cash="1000000", cost_multiplier=1):
    """Signals known after session t affect only session t+1 open.

    No broker execution, margin, shorting, implicit reinvestment or cash interest.
    Tax, lot, settlement and action data are required historical facts, not defaults.
    """
    cash = number(initial_cash)
    if cash <= 0 or cost_multiplier not in (1, 2):
        raise StudyError("backtest_configuration_invalid")
    sessions = calendar.sessions
    if sessions[0].day < proxy.listed_on:
        raise StudyError("proxy_before_listing")
    if not proxy.exact_tracking or proxy.exchange != calendar.exchange:
        raise StudyError("proxy_not_equivalent")
    if stamp(proxy.known_at) > sessions[0].opens:
        raise StudyError("proxy_identity_not_known")
    if len(bars) != len(sessions) or [r.get("day") for r in bars] != [
        s.day.isoformat() for s in sessions
    ]:
        raise StudyError("price_calendar_mismatch")
    if set(signals) - {s.day.isoformat() for s in sessions}:
        raise StudyError("signal_outside_calendar")
    for bar, session in zip(bars, sessions):
        if bar.get("historical_eligible") is not True or not bar.get("source_ref"):
            raise StudyError("prices_not_historically_eligible")
        if stamp(bar.get("execution_known_at")) > session.opens:
            raise StudyError("open_not_available_at_execution")
        if number(bar.get("open")) <= 0 or number(bar.get("close")) <= 0:
            raise StudyError("price_invalid")
        if stamp(bar.get("actions_known_at")) > session.opens:
            raise StudyError("corporate_action_not_known")
        if number(bar.get("split")) <= 0 or number(bar.get("dividend")) < 0:
            raise StudyError("corporate_action_invalid")
    lots, unsettled, fills, curve = [], [], [], []
    costs, pending = ZERO, None
    commission = Decimal(".001") * cost_multiplier
    slippage = Decimal(".001") * cost_multiplier
    for index, (session, bar) in enumerate(zip(sessions, bars)):
        day = session.day.isoformat()
        rules = [r for r in proxy.rules if r.from_date <= session.day <= r.until_date]
        if len(rules) != 1 or stamp(rules[0].known_at) > session.opens:
            raise StudyError("historical_trading_rule_missing")
        rule = rules[0]
        cash += sum((amount for ready, amount in unsettled if ready <= index), ZERO)
        unsettled = [(ready, amount) for ready, amount in unsettled if ready > index]
        split, dividend = number(bar["split"]), number(bar["dividend"])
        if split != ONE and dividend and bar.get("dividend_basis") != "pre_action_share":
            raise StudyError("combined_corporate_action_basis_unknown")
        for lot in lots:
            cash += lot["quantity"] * dividend
            lot["quantity"] *= split
            if lot["quantity"] != lot["quantity"].to_integral_value():
                raise StudyError("fractional_corporate_action_unsupported")
        opening = number(bar["open"])
        quantity = sum((lot["quantity"] for lot in lots), ZERO)
        unsettled_total = sum((a for _, a in unsettled), ZERO)
        if pending is not None and not bar.get("suspended", False):
            nav = cash + unsettled_total + quantity * opening
            target = (nav * pending / opening / rule.lot).to_integral_value(
                rounding=ROUND_FLOOR
            ) * rule.lot
            delta = target - quantity
            side = "buy" if delta > 0 else "sell"
            available = sum((lot["quantity"] for lot in lots if lot["sellable"] <= index), ZERO)
            rounding = ROUND_CEILING if delta > 0 else ROUND_FLOOR
            price = (
                opening * (ONE + slippage if delta > 0 else ONE - slippage) / rule.price_tick
            ).to_integral_value(rounding=rounding) * rule.price_tick
            tax = (rule.tax_buy_bps if delta > 0 else rule.tax_sell_bps) / Decimal(10000)
            if delta > 0:
                affordable = (
                    cash / (price * (ONE + commission + tax)) / rule.lot
                ).to_integral_value(rounding=ROUND_FLOOR) * rule.lot
                traded = min(delta, affordable)
            else:
                traded = min(-delta, available)
            if traded > 0:
                notional = traded * price
                fee = notional * (commission + tax)
                if side == "buy":
                    cash -= notional + fee
                    lots.append({"quantity": traded, "sellable": index + rule.sell_after_sessions})
                else:
                    remaining = traded
                    for lot in lots:
                        if lot["sellable"] <= index:
                            used = min(remaining, lot["quantity"])
                            lot["quantity"] -= used
                            remaining -= used
                    proceeds = notional - fee
                    if rule.settlement_sessions:
                        unsettled.append((index + rule.settlement_sessions, proceeds))
                    else:
                        cash += proceeds
                lots = [lot for lot in lots if lot["quantity"]]
                costs += fee + traded * abs(price - opening)
                fills.append(
                    {
                        "day": day,
                        "side": side,
                        "quantity": str(traded),
                        "price": str(price),
                        "fee": str(fee),
                        "rule_ref": rule.source_ref,
                    }
                )
        quantity = sum((lot["quantity"] for lot in lots), ZERO)
        unsettled_total = sum((a for _, a in unsettled), ZERO)
        nav = cash + unsettled_total + quantity * number(bar["close"])
        if cash < 0 or nav <= 0:
            raise StudyError("account_conservation_failed")
        curve.append(
            {
                "day": day,
                "nav": str(nav),
                "cash": str(cash),
                "unsettled": str(unsettled_total),
                "quantity": str(quantity),
            }
        )
        pending = number(signals[day]) if day in signals else None
        if pending is not None and not ZERO <= pending <= ONE:
            raise StudyError("signal_weight_invalid")
    log.info(
        "event_study_replay_completed",
        sessions=len(curve),
        fills=len(fills),
        cost_multiplier=cost_multiplier,
    )
    return {
        "curve": curve,
        "fills": fills,
        "costs": str(costs),
        "metrics": metrics(curve, initial_cash),
        "execution_model": "next_session_open",
        "cash_return": "0",
        "currency": proxy.currency,
    }
