"""Scoped, bounded report arithmetic from Host primitives, never a quality verdict.

This stdlib module also runs in the original read-only report SDK. The Host must
independently reconstruct its input observations from owned bytes; self-consistent
hashes alone do not certify publisher authenticity or cross-version comparability.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from decimal import Decimal, DecimalException
from fractions import Fraction
from typing import Any

log = logging.getLogger("research_web.report_calculations")
ALGORITHM = "business-derived-rational-half-up-v1"
ERROR = "research_report_calculation_invalid"
METHOD = (
    "Calculated only from scoped primitive observations; source authenticity and "
    "cross-version comparability are not certified. Display rounding does not "
    "replace the retained exact calculation."
)
_HASH = re.compile(r"[a-f0-9]{64}")
_SOURCE = re.compile(r"(?:web|file|dataset):[a-f0-9]{24}")
_METRIC = re.compile(r"[a-z][a-z_]{0,95}")
_FIELDS = ("algorithm", "scope_sha256", "metric", "period", "unit", "value", "content", "proofs")


def _encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _number(value: Any) -> Decimal:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or not re.fullmatch(r"-?\d+(?:\.\d+)?", value)
    ):
        raise ValueError(ERROR)
    result = Decimal(value)
    if (
        not result.is_finite()
        or result.copy_abs() > Decimal("1e30")
        or (result and result.adjusted() < -60)
    ):
        raise ValueError(ERROR)
    return result


def _primitive(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict) or any(field not in row for field in _FIELDS):
        raise ValueError(ERROR)
    metric, period, unit = row["metric"], row["period"], row["unit"]
    if (
        row.get("kind") != "business_numeric"
        or row["algorithm"] != "business-excerpts-v1"
        or not isinstance(row["scope_sha256"], str)
        or not _HASH.fullmatch(row["scope_sha256"])
        or not isinstance(metric, str)
        or not _METRIC.fullmatch(metric)
        or any(not isinstance(v, str) or not 1 <= len(v) <= 80 or "\n" in v for v in (period, unit))
        or not isinstance(row["content"], str)
        or len(row["content"].encode()) > 16000
        or row["content"].split("\n", 1)[0] != f"{metric} {period} {row['value']} {unit}"
        or row.get("sha256") != hashlib.sha256(row["content"].encode()).hexdigest()
    ):
        raise ValueError(ERROR)
    _number(row["value"])
    proofs = row["proofs"]
    if not isinstance(proofs, list) or not 1 <= len(proofs) <= 16:
        raise ValueError(ERROR)
    for proof in proofs:
        if (
            not isinstance(proof, dict)
            or set(proof) != {"source_id", "sha256", "offset_unit", "spans"}
            or not isinstance(proof["source_id"], str)
            or not _SOURCE.fullmatch(proof["source_id"])
            or not isinstance(proof["sha256"], str)
            or not _HASH.fullmatch(proof["sha256"])
            or proof["offset_unit"] != "unicode_codepoint"
            or not isinstance(proof["spans"], list)
            or not 1 <= len(proof["spans"]) <= 32
        ):
            raise ValueError(ERROR)
        for span in proof["spans"]:
            if (
                not isinstance(span, dict)
                or set(span) != {"start", "end", "text"}
                or any(
                    isinstance(span[k], bool) or not isinstance(span[k], int)
                    for k in ("start", "end")
                )
                or not 0 <= span["start"] < span["end"] <= 4_000_000
                or not isinstance(span["text"], str)
                or not 0 < len(span["text"]) <= 64000
                or span["end"] - span["start"] != len(span["text"])
            ):
                raise ValueError(ERROR)
    refs = [p["source_id"] for p in proofs]
    if (
        refs != sorted(set(refs))
        or row.get("source_ids") != refs
        or row.get("source_id") != refs[-1]
        or row.get("id") != "business_" + _digest({k: row[k] for k in _FIELDS})[:32]
    ):
        raise ValueError(ERROR)
    return row


def _resolve(observations: list[dict[str, Any]], ref: Any) -> dict[str, Any]:
    if not isinstance(ref, str) or not 1 <= len(ref) <= 200 or ref.startswith("$"):
        raise ValueError(ERROR)
    matches = [
        r
        for r in observations
        if ref == r.get("id") or ref == str(r.get("metric")) + "@" + str(r.get("period"))
    ]
    if len(matches) != 1:
        raise ValueError(ERROR)
    return matches[0]


def _derive(rows: list[dict[str, Any]], recipe: dict[str, Any], task_id: str) -> dict[str, Any]:
    operation = recipe["operation"]
    families = [re.sub(r"_(?:final|preliminary)$", "", row["metric"]) for row in rows]
    if (
        len({r["unit"] for r in rows}) != 1
        or (operation in {"sum", "difference"} and len({r["period"] for r in rows}) != 1)
        or len(set(families)) != 1
    ):
        raise ValueError(ERROR)
    # Exact integer ratios avoid double rounding even at an accepted decimal boundary.
    numbers = [Fraction(r["value"]) for r in rows]
    if operation == "identity":
        exact = numbers[0]
    elif operation == "sum":
        exact = sum(numbers, Fraction(0))
    elif operation == "difference":
        exact = numbers[0] - numbers[1]
    elif operation == "ratio":
        exact = numbers[0] / numbers[1]
    else:
        exact = (numbers[0] - numbers[1]) / numbers[1] * 100
    if abs(exact) > 10**30:
        raise ValueError(ERROR)
    places = recipe["decimal_places"]
    quotient, remainder = divmod(abs(exact.numerator) * 10**places, exact.denominator)
    quotient += int(remainder * 2 >= exact.denominator)
    digits = str(quotient).zfill(places + 1)
    rounded = ("-" if exact < 0 else "") + (
        digits[:-places] + "." + digits[-places:] if places else digits
    )
    metric, period = families[0] + "_" + operation, rows[0]["period"]
    unit = (
        "%"
        if operation == "percent_change"
        else "ratio" if operation == "ratio" else rows[0]["unit"]
    )
    if operation == "difference" and unit == "%":
        unit = "percentage_points"
    proofs_by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        for proof in row["proofs"]:
            previous = proofs_by_source.get(proof["source_id"])
            if previous is not None and previous["sha256"] != proof["sha256"]:
                raise ValueError(ERROR)
            if previous is None:
                proofs_by_source[proof["source_id"]] = copy.deepcopy(proof)
            else:
                for span in proof["spans"]:
                    if span not in previous["spans"]:
                        previous["spans"].append(copy.deepcopy(span))
    proofs = sorted(proofs_by_source.values(), key=lambda p: p["source_id"])
    for proof in proofs:
        proof["spans"].sort(key=lambda s: (s["start"], s["end"], s["text"]))
    scope = {
        "task_id": task_id,
        "recipe": recipe,
        "inputs": [{k: row[k] for k in ("id", "sha256", "scope_sha256")} for row in rows],
    }
    values = [r["value"] for r in rows]
    expression = {
        "identity": values[0],
        "sum": " + ".join(values),
        "difference": " − ".join(values),
        "ratio": " ÷ ".join(values),
        "percent_change": (f"({values[0]} − {values[-1]}) ÷ {values[-1]} × 100"),
    }[operation]
    formula = expression + " ≈ " + rounded + " " + unit
    content = f"{metric} {period} {rounded} {unit}\n{METHOD}"
    payload = {
        "algorithm": ALGORITHM,
        "scope_sha256": _digest(scope),
        "metric": metric,
        "period": period,
        "unit": unit,
        "value": rounded,
        "content": content,
        "proofs": proofs,
    }
    return {
        "id": "business_" + _digest(payload)[:32],
        "source_id": proofs[-1]["source_id"],
        "source_ids": [p["source_id"] for p in proofs],
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "kind": "business_numeric",
        "heading": metric,
        **payload,
        "selection_id": "$" + recipe["id"],
        "input_ids": [row["id"] for row in rows],
        "exact_value": str(exact),
        "decimal_places": recipe["decimal_places"],
        "calculation": copy.deepcopy(recipe),
        "calculation_trace": {
            "id": recipe["id"],
            "operation": operation,
            "operands": [
                {key: row[key] for key in ("id", "metric", "period", "value", "unit", "source_ids")}
                for row in rows
            ],
            "exact_value": str(exact),
            "formula": formula,
            "display_value": rounded,
            "unit": unit,
            "decimal_places": places,
            "rounding": "ROUND_HALF_UP",
            "scope_sha256": payload["scope_sha256"],
        },
    }


def derive_business_observations(
    observations: list[dict[str, Any]], recipes: list[dict[str, Any]], *, task_id: str
) -> list[dict[str, Any]]:
    """Derive scoped display quantities; callers independently repeat on Host bytes."""
    try:
        if (
            not isinstance(task_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id)
            or not isinstance(observations, list)
            or len(observations) > 256
            or not isinstance(recipes, list)
            or len(recipes) > 16
            or len(_encoded(observations)) > 4_000_000
        ):
            raise ValueError(ERROR)
        if any(not isinstance(row, dict) for row in observations) or len(
            {row.get("id") for row in observations}
        ) != len(observations):
            raise ValueError(ERROR)
        seen, result = set(), []
        for recipe in recipes:
            if not isinstance(recipe, dict) or set(recipe) != {
                "id",
                "operation",
                "operands",
                "decimal_places",
            }:
                raise ValueError(ERROR)
            identifier, operation, refs, places = (
                recipe[k] for k in ("id", "operation", "operands", "decimal_places")
            )
            if (
                not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", identifier)
                or identifier in seen
                or not isinstance(operation, str)
                or operation not in {"identity", "sum", "difference", "ratio", "percent_change"}
                or not isinstance(refs, list)
                or not 1 <= len(refs) <= 8
                or isinstance(places, bool)
                or not isinstance(places, int)
                or not 0 <= places <= 12
            ):
                raise ValueError(ERROR)
            # Unselected valid Host layouts may have non-canonical numeric prose;
            # validate only the exact operands, rather than disabling other plans.
            rows = [_primitive(_resolve(observations, ref)) for ref in refs]
            arity = {"identity": 1, "difference": 2, "ratio": 2, "percent_change": 2}
            if (operation in arity and len(rows) != arity[operation]) or len(
                {r["id"] for r in rows}
            ) != len(rows):
                raise ValueError(ERROR)
            result.append(_derive(rows, recipe, task_id))
            seen.add(identifier)
        log.info("research_report_calculations_derived count=%d", len(result))
        return result
    except (
        ValueError,
        TypeError,
        KeyError,
        DecimalException,
        ArithmeticError,
        RecursionError,
        OverflowError,
    ) as exc:
        log.warning("research_report_calculations_rejected type=%s", type(exc).__name__)
        raise ValueError(ERROR) from exc
