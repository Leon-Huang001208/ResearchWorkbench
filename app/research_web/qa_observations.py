"""Deterministic, task-bound observations from verified DataHub snapshots."""

import json
import re
from decimal import Decimal

from .research_business_evidence import _emit

_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,95}")
_DAY = re.compile(r"\d{4}(?:-\d{2}(?:-\d{2})?)?")
_UNIT = re.compile(r"[%A-Za-z\u3400-\u9fff/（）()²·_-]{1,24}")


def snapshot_observations(metadata, rows, raw, scope):
    """Emit only values with an explicit field unit and period, or attributed quotes."""
    identifier = "dataset:" + metadata["dataset_id"]
    digest = metadata["manifest_sha256"]
    result = []
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        if len(json.dumps(row, ensure_ascii=False).encode()) > 32000:
            continue
        if metadata.get("snapshot_kind") == "discovery_evidence":
            result.extend(_discovery_quotes(row, raw, identifier, digest, metadata, scope))
        else:
            result.extend(_numeric(row, raw, identifier, digest, metadata, scope))
        if len(result) >= 24:
            break
    return list({item["id"]: item for item in result[:24]}.values())


def _make(scope, identifier, digest, raw, needle, metric, period, value, unit):
    start = raw.find(needle)
    if start < 0 or raw.find(needle, start + 1) >= 0:
        return None
    proof = {
        "source_id": identifier,
        "sha256": digest,
        "offset_unit": "unicode_codepoint",
        "spans": [{"start": start, "end": start + len(needle), "text": needle}],
    }
    return _emit(
        scope,
        metric,
        period,
        value,
        unit,
        [proof],
        method="RWB DataHub 冻结来源摘录",
        text=json.loads(needle) if value is None else None,
    )


def _discovery_quotes(row, raw, identifier, digest, metadata, scope):
    detail = row.get("detail")
    if not isinstance(detail, dict) or metadata.get("source_stale"):
        return []
    candidates = [detail]
    candidates.extend(value for value in detail.values() if isinstance(value, dict))
    quotes = []
    for item in candidates[:20]:
        for name in ("title", "summary", "excerpt"):
            text = item.get(name)
            if not isinstance(text, str) or not 8 <= len(text) <= 500 or re.search(r"\d", text):
                continue
            observed = _make(
                scope,
                identifier,
                digest,
                raw,
                json.dumps(text, ensure_ascii=False),
                "discovery_source_statement",
                metadata["as_of"],
                None,
                "引文",
            )
            if observed:
                quotes.append(observed)
    return quotes


def _numeric(row, raw, identifier, digest, metadata, scope):
    if metadata.get("status") not in {"complete", "snapshot", "success"}:
        return []
    fields = metadata.get("fields")
    if not isinstance(fields, dict):
        return []
    period = row.get("date") or row.get("period")
    if not isinstance(period, str) or not _DAY.fullmatch(period):
        return []
    values = []
    for name, description in fields.items():
        if not isinstance(description, dict) or not _ID.fullmatch(name):
            continue
        unit, number = description.get("unit"), row.get(name)
        if (
            not isinstance(unit, str)
            or not _UNIT.fullmatch(unit)
            or type(number) not in (int, float)
        ):
            continue
        value = Decimal(str(number))
        if not value.is_finite():
            continue
        observed = _make(
            scope,
            identifier,
            digest,
            raw,
            json.dumps(name) + ": " + json.dumps(number),
            name,
            period,
            value,
            unit,
        )
        if observed:
            values.append(observed)
        if len(values) >= 12:
            break
    return values
