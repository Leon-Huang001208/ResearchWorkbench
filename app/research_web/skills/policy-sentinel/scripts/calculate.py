"""Build an evidence-only policy timeline from supplied records."""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

from cpu_budget import WorkloadBudget

LOGGER = logging.getLogger("research.skill.policy_sentinel")
SKILL_SLUG = "policy-sentinel"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("records", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "records"
ALLOWED_ROOT_FIELDS = frozenset((*REQUIRED_ROOT_FIELDS, "source_hashes"))


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalculatorError("invalid_field_type")
    return value.strip()


def _day(value: Any) -> str:
    value = _text(value)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise CalculatorError("invalid_date") from exc


def _dataset_refs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if set(payload) - ALLOWED_ROOT_FIELDS:
        raise CalculatorError("unknown_field")
    refs = payload.get("dataset_refs")
    required = {"dataset_id", "provider_id", "as_of", "sha256"}
    if not isinstance(refs, list) or not refs:
        raise CalculatorError("invalid_field_type")
    for ref in refs:
        if not isinstance(ref, dict) or not required <= set(ref):
            raise CalculatorError("invalid_dataset_ref")
        _text(ref["dataset_id"])
        _text(ref["provider_id"])
        _day(ref["as_of"])
        digest = ref["sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
        ):
            raise CalculatorError("invalid_dataset_ref")
    return refs


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    if not isinstance(payload, dict):
        raise CalculatorError("invalid_field_type")
    for field in REQUIRED_ROOT_FIELDS:
        if field not in payload:
            raise CalculatorError("missing_required_field")
    records = payload["records"]
    if not isinstance(records, list):
        raise CalculatorError("invalid_field_type")
    if not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    parameters = payload["parameters"]
    refs = _dataset_refs(payload)
    if not isinstance(parameters, dict):
        raise CalculatorError("invalid_field_type")
    keywords = parameters.get("keywords")
    start_date = _day(parameters.get("start_date"))
    end_date = _day(parameters.get("end_date"))
    if start_date > end_date or not isinstance(keywords, list) or not keywords:
        raise CalculatorError("invalid_field_type")
    normalized_keywords = sorted({_text(value) for value in keywords})

    timeline = []
    for raw in records:
        if not isinstance(raw, dict):
            raise CalculatorError("invalid_field_type")
        if not raw.get("source_ref") or not raw.get("evidence_id"):
            raise CalculatorError("evidence_required")
        published = _day(raw.get("published_at"))
        text = f"{_text(raw.get('title'))} {_text(raw.get('summary'))}"
        matched = [
            keyword for keyword in normalized_keywords if keyword.casefold() in text.casefold()
        ]
        if not start_date <= published <= end_date or not matched:
            continue
        targets = raw.get("potential_impact_objects")
        if not isinstance(targets, list):
            raise CalculatorError("invalid_field_type")
        timeline.append(
            {
                "published_at": published,
                "evidence_id": _text(raw["evidence_id"]),
                "title": _text(raw["title"]),
                "source": _text(raw.get("source")),
                "source_ref": _text(raw["source_ref"]),
                "matched_keywords": matched,
                "matched_rules": ["date_in_range", "keyword_match"],
                "potential_impact_objects": sorted({_text(value) for value in targets}),
            }
        )
    timeline.sort(key=lambda row: (row["published_at"], row["evidence_id"]))
    if not timeline:
        raise CalculatorError("empty_input")
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": _day(payload["as_of"]),
        "parameters": {
            "keywords": normalized_keywords,
            "start_date": start_date,
            "end_date": end_date,
        },
        "dataset_refs": refs,
        "status": "complete",
        "metrics": {
            "matched_record_count": len(timeline),
            "unique_impact_object_count": len(
                {target for row in timeline for target in row["potential_impact_objects"]}
            ),
        },
        "rows": timeline,
        "limitations": ["potential_impacts_are_source_supplied_not_investment_advice"],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": payload.get("source_hashes", {}),
            "rights": "internal-only",
            "transformations": [
                "validate_evidence",
                "date_filter",
                "keyword_match",
                METHOD_VERSION,
            ],
        },
    }


def _path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise CalculatorError("unsafe_input_path")
    resolved = (Path.cwd() / path).resolve()
    if not resolved.is_file():
        raise CalculatorError("input_unavailable")
    return resolved


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        if len(args) != 1:
            raise CalculatorError("usage_error")
        path = _path(args[0])
        size = path.stat().st_size
        WorkloadBudget().add_input(rows=0, bytes_count=size)
        print(
            json.dumps(
                calculate(json.loads(path.read_text(encoding="utf-8")), input_bytes=size),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (CalculatorError, json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "invalid_input")
        LOGGER.error("calculator_failed code=%s", code)
        print(json.dumps({"error": {"code": code, "message": code}}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
