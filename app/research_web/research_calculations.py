"""Bounded independent calculations from actual owned input bytes, never model output."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import threading
from collections import OrderedDict
from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, localcontext

from core.observability import get_logger

from .resources.research_report import validate_calculation_recipes
from .store import StoreError

log = get_logger(__name__)
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_ROWS = 100000
ALGORITHM = "buy-and-hold-sorted-decimal34-half-even10-v1"
_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN, Emin=-100, Emax=100)
_CACHE: OrderedDict[str, dict[str, str]] = OrderedDict()
_CACHE_LOCK = threading.RLock()
_PERIOD = "完整输入样本"
_METHOD = "采用按首行价格归一化的静态初始持仓组合。\n按文件行序累计组合峰值并计算最大回撤。\n末值情景只修改末行价格，不重算中间路径。\n仅验证输入文件的计算，不认证真实市场来源或日期。"
_LABELS = {
    "total_return": "组合收益",
    "max_drawdown": "最大回撤",
    "terminal_scenario_return": "末值情景收益",
    "row_count": "记录行数",
}


class CalculationError(ValueError):
    """A stable error code; input values and paths never enter error messages."""


def _price(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise CalculationError("calculation_price_invalid")
    try:
        value = value.strip()
        if not re.fullmatch(
            r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,3})?", value
        ):
            raise CalculationError("calculation_price_invalid")
        number = Decimal(value)
        if (
            not number.is_finite()
            or not Decimal("1e-18") <= number <= Decimal("1e18")
            or abs(number.as_tuple().exponent) > 30
        ):
            raise CalculationError("calculation_price_invalid")
        return number
    except DecimalException as exc:
        raise CalculationError("calculation_price_invalid") from exc


def _calculate(raw, recipe):
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames
        if (
            not headers
            or len(headers) > 64
            or len(set(headers)) != len(headers)
            or any(not name or len(name) > 128 for name in headers)
            or not set(recipe["weights"]).issubset(headers)
        ):
            raise CalculationError("calculation_columns_invalid")
        with localcontext(_CONTEXT):
            weights = {
                name: Decimal(str(value)) for name, value in sorted(recipe["weights"].items())
            }
            shocks = {
                name: Decimal(str(value)) for name, value in recipe["terminal_shocks"].items()
            }
            first = None
            peak, drawdown, count = Decimal(1), Decimal(0), 0
            last = {}
            for row in reader:
                count += 1
                if count > MAX_ROWS:
                    raise CalculationError("calculation_row_limit")
                if None in row or any(value is None for value in row.values()):
                    raise CalculationError("calculation_row_invalid")
                last = {name: _price(row[name]) for name in weights}
                if first is None:
                    first = last.copy()
                nav = sum(weights[name] * last[name] / first[name] for name in weights)
                peak = max(peak, nav)
                drawdown = min(drawdown, nav / peak - 1)
            if first is None:
                raise CalculationError("calculation_empty")
            scenario = sum(
                weights[name] * last[name] * (1 + shocks.get(name, Decimal(0))) / first[name]
                for name in weights
            )
            quantize = lambda value: format(value.quantize(Decimal("0.0000000001")), "f")
            return {
                "total_return": quantize(nav - 1),
                "max_drawdown": quantize(drawdown),
                "terminal_scenario_return": quantize(scenario - 1),
                "row_count": str(count),
            }
    except (UnicodeError, csv.Error, DecimalException, KeyError, TypeError) as exc:
        raise CalculationError("calculation_data_invalid") from exc


def observe_calculations(store, sid, files, sources, recipes, *, task_id=""):
    """Recheck whole bytes before a scoped result-cache lookup; no status is cached."""
    try:
        validate_calculation_recipes(recipes)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise CalculationError("calculation_recipe_invalid") from exc
    allowed = {row["id"] for row in sources}
    inputs = {"file:" + row["id"]: row for row in files if row.get("kind") == "inputs"}
    observed = []
    root_info = store.root.stat()
    for recipe in recipes:
        source_id = recipe["source_id"]
        if (
            source_id not in allowed
            or source_id not in inputs
            or not inputs[source_id]["name"].lower().endswith(".csv")
        ):
            raise CalculationError("calculation_source_unavailable")
        try:
            stream, _ = store.open_file(sid, inputs[source_id]["id"])
            with stream:
                raw = stream.read(MAX_INPUT_BYTES + 1)
        except (OSError, StoreError) as exc:
            raise CalculationError("calculation_input_unavailable") from exc
        if len(raw) > MAX_INPUT_BYTES:
            raise CalculationError("calculation_input_limit")
        input_digest = hashlib.sha256(raw).hexdigest()
        if input_digest != recipe["source_sha256"]:
            raise CalculationError("calculation_input_changed")
        recipe_digest = hashlib.sha256(
            json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        scope = [
            str(store.root),
            root_info.st_dev,
            root_info.st_ino,
            sid,
            task_id,
            ALGORITHM,
            input_digest,
            recipe_digest,
        ]
        cache_key = hashlib.sha256(json.dumps(scope).encode()).hexdigest()
        with _CACHE_LOCK:
            values = _CACHE.get(cache_key)
            if values is not None:
                _CACHE.move_to_end(cache_key)
                values = values.copy()
        if values is None:
            values = _calculate(raw, recipe)
            with _CACHE_LOCK:
                _CACHE[cache_key] = values.copy()
                _CACHE.move_to_end(cache_key)
                while len(_CACHE) > 64:
                    _CACHE.popitem(last=False)
            log.info(
                "research_calculation_verified", rows=int(values["row_count"]), metrics=len(values)
            )
        for metric, value in values.items():
            unit = "行" if metric == "row_count" else "ratio"
            content = f"{_PERIOD}{_LABELS[metric]} {value} {unit}\n{_METHOD}"
            observed.append(
                {
                    "id": "calc_" + cache_key[:24] + "_" + metric,
                    "source_id": source_id,
                    "calculation_id": recipe["id"],
                    "metric": metric,
                    "value": value,
                    "period": _PERIOD,
                    "unit": unit,
                    "content": content,
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "input_sha256": input_digest,
                    "recipe_sha256": recipe_digest,
                    "algorithm": ALGORITHM,
                }
            )
    return observed
