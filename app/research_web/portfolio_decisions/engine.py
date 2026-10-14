"""Causal ETF decisions and one accounting path for replay/forward paper use."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, time
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .models import ResearchSnapshot, StrategySpec

log = get_logger(__name__)
ZERO = Decimal(0)
ONE = Decimal(1)
TZ = ZoneInfo("Asia/Shanghai")
# Reproducibility identity only; it never grants capability admission.
IMPLEMENTATION_DIGEST = hashlib.sha256(
    Path(__file__).read_bytes() + Path(__file__).with_name("models.py").read_bytes()
).hexdigest()


def text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def cutoff(day: date) -> datetime:
    return datetime.combine(day, time(16), TZ)


def opening(day: date) -> datetime:
    return datetime.combine(day, time(9, 30), TZ)


class PaperEngine:
    """Only engineering inputs are accepted; no online capability is enabled."""

    def __init__(self, strategy: StrategySpec, snapshot: ResearchSnapshot, manual_decisions):
        self.strategy = strategy
        self.snapshot = snapshot
        self.manual = {d.day: d for d in manual_decisions}
        self.rules = {a.symbol: a for a in snapshot.assets}
        self.bars = {(b.symbol, b.day): b for b in snapshot.bars}
        self.benchmark = {b.day: b for b in snapshot.benchmark}
        self.state: dict[str, Any] = {
            "cash": text(strategy.initial_cash),
            "fees": "0",
            "distributions": "0",
            "lots": [],
            "last_day": None,
        }
        self.orders: list[dict[str, Any]] = []
        self.fills: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.curve: list[dict[str, Any]] = []
        self.last_prices: dict[str, str] = {}

    def checkpoint(self):
        return deepcopy(
            {
                "input_digest": self._identity(),
                "state": self.state,
                "orders": self.orders,
                "fills": self.fills,
                "events": self.events,
                "curve": self.curve,
                "last_prices": self.last_prices,
            }
        )

    def _identity(self):
        return digest(
            {
                "strategy": self.strategy.model_dump(mode="json"),
                "implementation_digest": IMPLEMENTATION_DIGEST,
                "snapshot": self.snapshot.model_dump(mode="json"),
                "manual": [d.model_dump(mode="json") for d in self.manual.values()],
            }
        )

    @classmethod
    def restore(cls, strategy, snapshot, manual_decisions, checkpoint):
        engine = cls(strategy, snapshot, manual_decisions)
        if checkpoint["input_digest"] != engine._identity():
            raise ValueError("checkpoint_input_mismatch")
        for key in ("state", "orders", "fills", "events", "curve", "last_prices"):
            setattr(engine, key, deepcopy(checkpoint[key]))
        return engine

    def _quantity(self, symbol, day=None):
        rule = self.rules[symbol]
        return sum(
            lot["quantity"]
            for lot in self.state["lots"]
            if lot["symbol"] == symbol
            and (
                day is None or rule.turnaround == "T+0" or date.fromisoformat(lot["buy_day"]) < day
            )
        )

    def _visible_bar(self, symbol, day):
        bar = self.bars.get((symbol, day))
        return bar if bar and bar.known_at <= cutoff(day) else None

    def _execution_bar(self, symbol, day):
        bar = self.bars.get((symbol, day))
        return bar if bar and bar.execution_known_at <= opening(day) else None

    def _execution_valuation(self, day):
        prices = {}
        missing = []
        nav = Decimal(self.state["cash"])
        for symbol in self.rules:
            bar = self._execution_bar(symbol, day)
            if bar and bar.open:
                prices[symbol] = bar.open
            quantity = self._quantity(symbol)
            if quantity:
                if symbol not in prices:
                    missing.append(symbol)
                else:
                    nav += quantity * prices[symbol]
        return nav, prices, missing

    def _post_fill_violation(self, day, symbol, quantity, notional, fee):
        _, prices, missing = self._execution_valuation(day)
        if missing or symbol not in prices:
            return "post_fill_valuation_missing"
        cash = Decimal(self.state["cash"]) - notional - fee
        holdings = {s: self._quantity(s) * prices[s] for s in self.rules if self._quantity(s)}
        holdings[symbol] = holdings.get(symbol, ZERO) + quantity * prices[symbol]
        nav = cash + sum(holdings.values(), ZERO)
        if nav <= ZERO or cash < nav * self.strategy.min_cash_weight:
            return "post_fill_cash_cap"
        if sum(holdings.values(), ZERO) > nav * self.strategy.risk_budget:
            return "post_fill_total_risk_cap"
        if any(value > nav * self.strategy.security_cap for value in holdings.values()):
            return "post_fill_security_cap"
        industries = {}
        for asset, value in holdings.items():
            industry = self.rules[asset].industry
            industries[industry] = industries.get(industry, ZERO) + value
        if any(
            value > nav * self.strategy.industry_caps[industry]
            for industry, value in industries.items()
        ):
            return "post_fill_industry_cap"
        return None

    def _valuation(self, day):
        missing = []
        value = Decimal(self.state["cash"])
        for symbol in sorted(self.rules):
            quantity = self._quantity(symbol)
            bar = self._visible_bar(symbol, day)
            if bar and bar.close:
                self.last_prices[symbol] = text(bar.close)
            if quantity:
                if not bar or not bar.close:
                    missing.append(symbol)
                if symbol in self.last_prices:
                    value += quantity * Decimal(self.last_prices[symbol])
                else:
                    return None, [symbol]
        return value, missing

    def _corporate_actions(self, day):
        for symbol in sorted(self.rules):
            bar = self._execution_bar(symbol, day)
            quantity = self._quantity(symbol)
            if not quantity:
                continue
            if not bar:
                raise ValueError("corporate_action_state_unknown")
            # Fractional entitlement/settlement requires a provider-specific contract.
            if bar.split_ratio != ONE and any(
                Decimal(lot["quantity"]) * bar.split_ratio % 1
                for lot in self.state["lots"]
                if lot["symbol"] == symbol
            ):
                raise ValueError("fractional_corporate_action_unsupported")
            cash = money(quantity * bar.cash_distribution)
            self.state["cash"] = text(Decimal(self.state["cash"]) + cash)
            self.state["distributions"] = text(Decimal(self.state["distributions"]) + cash)
            if cash or bar.split_ratio != ONE:
                for lot in self.state["lots"]:
                    if lot["symbol"] == symbol:
                        lot["quantity"] = int(Decimal(lot["quantity"]) * bar.split_ratio)
                for order in self.orders:
                    if order["symbol"] == symbol and order["status"] in {
                        "submitted",
                        "partial",
                        "deferred",
                    }:
                        order.update(
                            status="cancelled", reason="corporate_action_requires_new_plan"
                        )
                self.events.append(
                    {
                        "day": day.isoformat(),
                        "corporate_action": {
                            "symbol": symbol,
                            "cash": text(cash),
                            "split_ratio": text(bar.split_ratio),
                        },
                    }
                )

    def _fee(self, notional):
        return money(max(self.strategy.minimum_fee, notional * self.strategy.fee_rate))

    def _execute(self, day):
        capacity = {}
        for order in sorted(self.orders, key=lambda o: (o["side"] != "sell", o["id"])):
            if order["status"] not in {
                "submitted",
                "partial",
                "deferred",
            } or day < date.fromisoformat(order["earliest_day"]):
                continue
            if day > date.fromisoformat(order["expires_day"]):
                order.update(status="expired", reason="signal_expired")
                continue
            symbol = order["symbol"]
            rule = self.rules[symbol]
            bar = self._execution_bar(symbol, day)
            reason = None
            if rule.known_at > opening(day) or not rule.eligible_from <= day <= rule.eligible_until:
                reason = "execution_eligibility_unknown"
            elif not bar or not bar.open or bar.volume_shares is None:
                reason = "execution_data_missing"
            elif bar.known_at > cutoff(day):
                reason = "post_session_volume_unavailable"
            elif bar.suspended:
                reason = "suspended"
            elif bar.upper_limit is None or bar.lower_limit is None:
                reason = "trading_limits_missing"
            elif (
                order["side"] == "buy"
                and bar.open >= bar.upper_limit
                or order["side"] == "sell"
                and bar.open <= bar.lower_limit
            ):
                reason = "conservative_limit_no_fill"
            if reason:
                order.update(status="deferred", reason=reason)
                continue
            slip = self.strategy.slippage_bps / Decimal(10000)
            raw_price = bar.open * (ONE + slip if order["side"] == "buy" else ONE - slip)
            rounding = ROUND_CEILING if order["side"] == "buy" else ROUND_FLOOR
            price = (raw_price / rule.price_tick).to_integral_value(
                rounding=rounding
            ) * rule.price_tick
            if (
                price <= ZERO
                or price > bar.upper_limit
                or price < bar.lower_limit
                or abs(price / Decimal(order["reference_price"]) - ONE)
                > self.strategy.max_price_deviation
            ):
                order.update(status="deferred", reason="price_deviation_or_tick_limit")
                continue
            available = capacity.setdefault(
                symbol,
                int(Decimal(bar.volume_shares) * self.strategy.participation_rate)
                // rule.lot_size
                * rule.lot_size,
            )
            quantity = min(order["remaining"], available)
            if order["side"] == "sell":
                quantity = min(quantity, self._quantity(symbol, day))
            else:
                cash = Decimal(self.state["cash"])
                nav, prices, missing = self._execution_valuation(day)
                if missing or self.snapshot.missing:
                    order.update(status="deferred", reason="valuation_or_required_data_missing")
                    continue
                # Recheck final account constraints at the actual fill price.
                held_value = sum(
                    self._quantity(s) * prices[s] for s in self.rules if self._quantity(s)
                )
                industry_value = sum(
                    self._quantity(s) * prices[s]
                    for s in self.rules
                    if self.rules[s].industry == rule.industry and self._quantity(s)
                )
                security_value = self._quantity(symbol) * price
                limit = min(
                    nav * self.strategy.security_cap - security_value,
                    nav * self.strategy.industry_caps[rule.industry] - industry_value,
                    nav * min(self.strategy.risk_budget, ONE - self.strategy.min_cash_weight)
                    - held_value,
                    cash - nav * self.strategy.min_cash_weight,
                )
                # Closed form avoids a per-lot loop proportional to the account size.
                affordable = min(
                    (limit - self.strategy.minimum_fee) / price,
                    limit / (price * (ONE + self.strategy.fee_rate)),
                )
                quantity = min(quantity, max(0, int(affordable) // rule.lot_size * rule.lot_size))
            quantity = quantity // rule.lot_size * rule.lot_size
            if quantity <= 0:
                order.update(status="deferred", reason="liquidity_inventory_cash_or_risk_cap")
                continue
            notional = money(quantity * price)
            fee = self._fee(notional)
            if order["side"] == "buy":
                violation = self._post_fill_violation(day, symbol, quantity, notional, fee)
                if violation:
                    order.update(status="deferred", reason=violation)
                    continue
                self.state["cash"] = text(Decimal(self.state["cash"]) - notional - fee)
                self.state["lots"].append(
                    {
                        "symbol": symbol,
                        "quantity": quantity,
                        "buy_day": day.isoformat(),
                        "fill_id": digest([order["id"], day.isoformat()]),
                    }
                )
            else:
                if fee > notional:
                    order.update(status="deferred", reason="fee_exceeds_proceeds")
                    continue
                remaining = quantity
                for lot in self.state["lots"]:
                    if lot["symbol"] == symbol and (
                        rule.turnaround == "T+0" or date.fromisoformat(lot["buy_day"]) < day
                    ):
                        take = min(remaining, lot["quantity"])
                        lot["quantity"] -= take
                        remaining -= take
                self.state["cash"] = text(Decimal(self.state["cash"]) + notional - fee)
            self.state["lots"] = [lot for lot in self.state["lots"] if lot["quantity"]]
            self.state["fees"] = text(Decimal(self.state["fees"]) + fee)
            capacity[symbol] -= quantity
            order["remaining"] -= quantity
            order.update(
                status="filled" if not order["remaining"] else "partial",
                reason="simulated_next_session_open",
            )
            self.fills.append(
                {
                    "id": digest([order["id"], day.isoformat()]),
                    "order_id": order["id"],
                    "day": day.isoformat(),
                    "symbol": symbol,
                    "side": order["side"],
                    "price": text(price),
                    "quantity": quantity,
                    "notional": text(notional),
                    "fee": text(fee),
                    "mode": "paper",
                    "assumed_execution_at": opening(day).isoformat(),
                    "matched_at": cutoff(day).isoformat(),
                    "liquidity_model": "daily_post_session_participation",
                }
            )

    def _rebalance(self, day, index):
        nav, missing = self._valuation(day)
        if nav is None or missing or self.snapshot.missing:
            self.events.append(
                {
                    "day": day.isoformat(),
                    "status": "BLOCKED",
                    "reason": "required_data_or_valuation_missing",
                }
            )
            return
        scores = []
        reasons = {}
        history = self.snapshot.calendar[max(0, index - 63) : index + 1]
        for symbol in sorted(self.strategy.asset_pool):
            rule = self.rules[symbol]
            bars = [self._visible_bar(symbol, d) for d in history]
            if (
                rule.known_at > cutoff(day)
                or not rule.eligible_from <= history[0] <= day <= rule.eligible_until
            ):
                reasons[symbol] = "historical_eligibility_unknown"
            elif len(bars) != 64 or any(
                not b or b.total_return_index is None or b.close is None for b in bars
            ):
                reasons[symbol] = "insufficient_or_unavailable_history"
            elif bars[-1].suspended:
                reasons[symbol] = "suspended"
            else:
                score = bars[-1].total_return_index / bars[0].total_return_index - ONE
                if score <= ZERO:
                    reasons[symbol] = "non_positive_momentum"
                else:
                    scores.append((symbol, score))
        # Incomplete inputs are not interpreted as an exit/zero risk signal.
        if any(
            value in {"historical_eligibility_unknown", "insufficient_or_unavailable_history"}
            for value in reasons.values()
        ):
            self.events.append(
                {
                    "day": day.isoformat(),
                    "status": "BLOCKED",
                    "reason": "signal_inputs_missing",
                    "reasons": reasons,
                }
            )
            return
        selected = sorted(scores, key=lambda pair: (-pair[1], pair[0]))[:3]
        signal = {
            "id": digest(
                [
                    self.strategy.model_dump(mode="json"),
                    day.isoformat(),
                    [(s, text(v)) for s, v in selected],
                ]
            ),
            "strategy_version": self.strategy.version,
            "confirmed_at": cutoff(day).isoformat(),
            "selected": [s for s, _ in selected],
            "scores": {s: text(v) for s, v in scores},
            "reasons": reasons,
        }
        weights = {}
        industry_used = {}
        budget = min(self.strategy.risk_budget, ONE - self.strategy.min_cash_weight)
        for symbol, _ in selected:
            industry = self.rules[symbol].industry
            base = budget / len(selected)
            weight = min(
                base,
                self.strategy.security_cap,
                self.strategy.industry_caps[industry] - industry_used.get(industry, ZERO),
            )
            weights[symbol] = weight
            industry_used[industry] = industry_used.get(industry, ZERO) + weight
            if weight < base:
                reasons[symbol] = "security_or_industry_cap_reduced"
        intent = {
            "weights": {s: text(v) for s, v in weights.items()},
            "cash_weight": text(ONE - sum(weights.values(), ZERO)),
            "current_quantities": {s: self._quantity(s) for s in self.strategy.asset_pool},
            "reasons": reasons,
        }
        decision = self.manual.get(day)
        adopted = decision is None or decision.action == "adopt"
        if decision and not cutoff(day) <= decision.decided_at < datetime.combine(
            self.snapshot.calendar[index + 1], time(9, 30), TZ
        ):
            raise ValueError("manual_decision_outside_plan_window")
        event = {
            "day": day.isoformat(),
            "signal": signal,
            "intent": intent,
            "decision": {
                "action": decision.action if decision else "adopt",
                "reason": decision.reason if decision else "mechanical_rule",
                "evidence_ref": decision.evidence_ref if decision else signal["id"],
                "before": deepcopy(self.state),
                "order_ids": [],
            },
        }
        self.events.append(event)
        if not adopted:
            return
        for order in self.orders:
            if order["status"] in {"submitted", "partial", "deferred"}:
                order.update(status="cancelled", reason="superseded_by_rebalance")
        earliest = self.snapshot.calendar[index + 1]
        expiry = self.snapshot.calendar[
            min(index + self.strategy.order_lifetime_sessions, len(self.snapshot.calendar) - 1)
        ]
        for symbol in sorted(self.strategy.asset_pool):
            bar = self._visible_bar(symbol, day)
            if not bar or not bar.close:
                continue
            rule = self.rules[symbol]
            target = (
                int(nav * weights.get(symbol, ZERO) / bar.close) // rule.lot_size * rule.lot_size
            )
            delta = target - self._quantity(symbol)
            if not delta:
                continue
            order_id = digest([signal["id"], symbol, "buy" if delta > 0 else "sell"])
            self.orders.append(
                {
                    "id": order_id,
                    "signal_id": signal["id"],
                    "symbol": symbol,
                    "side": "buy" if delta > 0 else "sell",
                    "quantity": abs(delta),
                    "remaining": abs(delta),
                    "reference_price": text(bar.close),
                    "earliest_day": earliest.isoformat(),
                    "expires_day": expiry.isoformat(),
                    "status": "submitted",
                    "reason": "selected" if symbol in weights else "no_longer_selected",
                }
            )
            event["decision"]["order_ids"].append(order_id)

    def step(self, day: date):
        if self.state["last_day"] == day.isoformat():
            return
        if (
            day not in self.snapshot.calendar
            or self.state["last_day"]
            and day <= date.fromisoformat(self.state["last_day"])
        ):
            raise ValueError("clock_not_monotonic")
        if (
            self.state["last_day"]
            and self.snapshot.calendar.index(day)
            != self.snapshot.calendar.index(date.fromisoformat(self.state["last_day"])) + 1
        ):
            raise ValueError("unprocessed_trading_day")
        # Failure rolls back the entire session, including company actions/fills.
        saved = self.checkpoint()
        try:
            if self.snapshot.calendar_known_at > opening(day):
                raise ValueError("calendar_not_known")
            self._corporate_actions(day)
            self._execute(day)
            index = self.snapshot.calendar.index(day)
            if (
                day >= self.strategy.effective_from
                and index + 1 < len(self.snapshot.calendar)
                and day.isocalendar()[:2] != self.snapshot.calendar[index + 1].isocalendar()[:2]
            ):
                self._rebalance(day, index)
            nav, missing = self._valuation(day)
            bench = self.benchmark.get(day)
            self.curve.append(
                {
                    "day": day.isoformat(),
                    "nav": text(nav) if nav is not None and not missing else None,
                    "indicative_nav": text(nav) if nav is not None else None,
                    "cash": self.state["cash"],
                    "fees": self.state["fees"],
                    "valuation_missing": missing,
                    "benchmark_index": (
                        text(bench.total_return_index)
                        if bench and bench.known_at <= cutoff(day)
                        else None
                    ),
                }
            )
            self.state["last_day"] = day.isoformat()
        except (ValueError, ArithmeticError, KeyError):
            for key in ("state", "orders", "fills", "events", "curve", "last_prices"):
                setattr(self, key, saved[key])
            log.warning("etf_paper_session_rejected", code="invalid_session")
            raise

    def result(self):
        values = [Decimal(row["nav"]) for row in self.curve if row["nav"] is not None]
        complete = len(values) == len(self.curve) and bool(values)
        peak = self.strategy.initial_cash
        drawdown = ZERO
        for value in values:
            peak = max(peak, value)
            drawdown = max(drawdown, ONE - value / peak)
        review = {
            "net_return": text(values[-1] / self.strategy.initial_cash - ONE) if complete else None,
            "gross_return": (
                text((values[-1] + Decimal(self.state["fees"])) / self.strategy.initial_cash - ONE)
                if complete
                else None
            ),
            "max_drawdown": text(drawdown) if complete else None,
            "turnover": text(
                sum((Decimal(f["notional"]) for f in self.fills), ZERO) / self.strategy.initial_cash
            ),
            "cost": self.state["fees"],
            "benchmark": self.strategy.benchmark,
            "benchmark_return": None,
            "cash_weight": text(Decimal(self.state["cash"]) / values[-1]) if complete else None,
            "unfilled_quantity": sum(
                o["remaining"] for o in self.orders if o["status"] != "filled"
            ),
            "research_status": "NOT_VALIDATED",
            "parameter_trials": [self.strategy.model_dump(mode="json")],
            "limitations": [
                "工程输入不构成真实数据或策略收益证据",
                "下一交易时段开盘成交为显式日线模型假设",
                "涨跌停触价保守拒绝；不证明盘口成交概率",
                "未划分并认证真实样本外研究区间",
            ],
        }
        if self.curve and all(row["benchmark_index"] is not None for row in self.curve):
            review["benchmark_return"] = text(
                Decimal(self.curve[-1]["benchmark_index"])
                / Decimal(self.curve[0]["benchmark_index"])
                - ONE
            )
        return deepcopy(
            {
                "strategy": self.strategy.model_dump(mode="json"),
                "implementation_digest": IMPLEMENTATION_DIGEST,
                "data_digest": digest(self.snapshot.model_dump(mode="json")),
                "data_source": self.snapshot.source,
                "data_cutoff": self.state["last_day"],
                "missing": self.snapshot.missing,
                "events": self.events,
                "orders": self.orders,
                "fills": self.fills,
                "state": self.state,
                "curve": self.curve,
                "review": review,
                "real_chain": {
                    "status": "BLOCKED",
                    "gaps": [
                        "ETF完整历史资格及逐日规则尚无已准入适配",
                        "二级市场价格、总回报、公司行动与可知时间等价未认证",
                        "必要计算能力真实版本比较回执未闭合",
                    ],
                    "uploaded_data_grants_admission": False,
                },
            }
        )


def replay(body):
    engine = PaperEngine(body.strategy, body.snapshot, body.manual_decisions)
    gap = None
    for day in body.snapshot.calendar:
        if body.start_date <= day <= body.end_date:
            try:
                engine.step(day)
            except ValueError as exc:
                if str(exc) != "corporate_action_state_unknown":
                    raise
                gap = {"day": day.isoformat(), "code": "corporate_action_state_unknown"}
                break
    result = engine.result()
    result["ledger_status"] = "BLOCKED" if gap else "COMPLETE_ENGINEERING"
    result["ledger_gap"] = gap
    result["requested_range"] = {
        "start": body.start_date.isoformat(),
        "end": body.end_date.isoformat(),
    }
    if gap:
        for key in (
            "net_return",
            "gross_return",
            "max_drawdown",
            "benchmark_return",
            "cash_weight",
        ):
            result["review"][key] = None
        result["review"]["limitations"].append(
            "公司行动资料未在开盘可知；账本止于上一已确认交易日，当前区间不完整"
        )
    if body.manual_decisions:
        result["mechanical_shadow"] = replay(body.model_copy(update={"manual_decisions": []}))
    log.info(
        "etf_paper_replay_completed",
        sessions=len(engine.curve),
        fills=len(engine.fills),
        admission="blocked",
    )
    return result
