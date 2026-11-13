"""Deterministic, task-bound observations from verified DataHub snapshots."""

import json
import re
from decimal import Decimal

from .research_business_evidence import _emit

_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,95}")
_DAY = re.compile(r"\d{4}(?:-\d{2}(?:-\d{2})?)?")
_UNIT = re.compile(r"[%A-Za-z\u3400-\u9fff/（）()²·_-]{1,24}")
_CURRENCY = re.compile(r"[A-Z]{3}")
_JSON = json.JSONDecoder()
_TOKEN = re.compile(r"\s*")
SNAPSHOT_METHOD = "RWB DataHub 冻结来源摘录"


def snapshot_observations(metadata, rows, raw, scope):
    """Emit only values with an explicit field unit and period, or attributed quotes."""
    policy = metadata.get("provider_metadata") or {}
    if (
        policy.get("quality_accepted") is False
        or metadata.get("source_stale") is True
        or (metadata.get("query") or {}).get("quality") == "allow_stale"
        or (metadata.get("query") or {}).get("purpose") == "display"
    ):
        return []
    identifier = "dataset:" + metadata["dataset_id"]
    digest = metadata["manifest_sha256"]
    result, cursor = [], 1
    if not raw.startswith("["):
        return result
    for row in rows[:20]:
        start = _TOKEN.match(raw, cursor).end()
        value, end = _JSON.raw_decode(raw, start)
        if value != row:
            return []
        separator = _TOKEN.match(raw, end).end()
        cursor = separator + 1
        if raw[separator : separator + 1] not in {",", "]"}:
            return []
        if not isinstance(row, dict):
            continue
        if len(json.dumps(row, ensure_ascii=False).encode()) > 32000:
            continue
        if metadata.get("snapshot_kind") == "discovery_evidence":
            result.extend(_discovery_quotes(row, raw, start, identifier, digest, metadata, scope))
        else:
            result.extend(_numeric(row, raw, start, identifier, digest, metadata, scope))
        if len(result) >= 24:
            break
    return list({item["id"]: item for item in result[:24]}.values())


def _members(raw, start):
    """Map immediate object members to their key and value offsets."""
    result, cursor = {}, start + 1
    while True:
        key_start = _TOKEN.match(raw, cursor).end()
        if raw[key_start] == "}":
            return result
        key, colon = _JSON.raw_decode(raw, key_start)
        value_start = _TOKEN.match(raw, _TOKEN.match(raw, colon).end() + 1).end()
        _, end = _JSON.raw_decode(raw, value_start)
        result[key] = (key_start, value_start, end)
        separator = _TOKEN.match(raw, end).end()
        if raw[separator] == "}":
            return result
        cursor = separator + 1


def _make(scope, identifier, digest, raw, start, end, metric, period, value, unit):
    text = raw[start:end]
    proof = {
        "source_id": identifier,
        "sha256": digest,
        "offset_unit": "unicode_codepoint",
        "spans": [{"start": start, "end": end, "text": text}],
    }
    return _emit(
        scope,
        metric,
        period,
        value,
        unit,
        [proof],
        method=SNAPSHOT_METHOD,
        text=json.loads(text) if value is None else None,
    )


def _discovery_quotes(row, raw, start, identifier, digest, metadata, scope):
    detail = row.get("detail")
    if not isinstance(detail, dict) or metadata.get("source_stale"):
        return []
    detail_start = _members(raw, start)["detail"][1]
    members = _members(raw, detail_start)
    candidates = [(detail, members)]
    candidates.extend(
        (value, _members(raw, members[key][1]))
        for key, value in detail.items()
        if isinstance(value, dict)
    )
    quotes = []
    for item, offsets in candidates[:20]:
        for name in ("title", "summary", "excerpt"):
            text = item.get(name)
            if not isinstance(text, str) or not 8 <= len(text) <= 500 or re.search(r"\d", text):
                continue
            _, start, end = offsets[name]
            quotes.append(
                _make(
                    scope,
                    identifier,
                    digest,
                    raw,
                    start,
                    end,
                    "discovery_source_statement",
                    metadata["as_of"],
                    None,
                    "引文",
                )
            )
    return quotes


def _numeric(row, raw, start, identifier, digest, metadata, scope):
    if metadata.get("status") not in {"complete", "snapshot", "success"}:
        return []
    fields = metadata.get("fields")
    if not isinstance(fields, dict):
        return []
    period = row.get("date") or row.get("period")
    if not isinstance(period, str) or not _DAY.fullmatch(period):
        return []
    values, offsets = [], _members(raw, start)
    for name, description in fields.items():
        if not isinstance(description, dict) or not _ID.fullmatch(name):
            continue
        unit, number = description.get("unit"), row.get(name)
        if (
            not isinstance(unit, str)
            or not _UNIT.fullmatch(unit)
            or unit in {"unknown", "per_row"}
            or type(number) not in (int, float)
        ):
            continue
        value = Decimal(str(number))
        if not value.is_finite():
            continue
        if unit in {"currency", "currency_per_share"}:
            currency = description.get("currency") or row.get("currency")
            if not isinstance(currency, str) or not _CURRENCY.fullmatch(currency):
                continue
            unit = currency + ("/股" if unit == "currency_per_share" else "")
        key_start, _, end = offsets[name]
        values.append(
            _make(
                scope,
                identifier,
                digest,
                raw,
                key_start,
                end,
                name,
                period,
                value,
                unit,
            )
        )
        if len(values) >= 12:
            break
    return values
