"""Closed Wallstreetcn live/articles projection.

The vendor signals success with ``code`` 20000, so the shared generic envelope
check that only accepts 0/200 would misread every valid response as a rejection.
Rows keep the vendor's own fields; nothing is inferred when a field is absent.
"""

import json
from typing import Any

from .providers import MAX_ROWS, ProviderError

WSCN_DATASETS = frozenset({"lives", "articles"})
_SUCCESS_CODE = 20000
_REQUIRED = {"lives": ("id", "display_time", "content_text"), "articles": ("id", "title")}


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Duplicate keys would make a row identity ambiguous."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def wscn_projection(raw: bytes, dataset: str) -> tuple[list[dict[str, Any]], int, bool]:
    """Validate the vendor envelope and return bounded article/live rows."""
    try:
        body = json.loads(raw, object_pairs_hook=_object)
        if not isinstance(body, dict):
            raise TypeError("envelope_required")
        code = body.get("code")
        if type(code) is not int or code != _SUCCESS_CODE:
            raise ProviderError("vendor_rejected")
        data = body.get("data")
        if not isinstance(data, dict):
            raise TypeError("invalid_data")
        items = data.get("items")
        if not isinstance(items, list):
            raise TypeError("invalid_items")
        if len(items) > MAX_ROWS:
            raise ProviderError("external_row_limit")
        required = _REQUIRED[dataset]
        rows: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for item in items:
            if not isinstance(item, dict):
                raise TypeError("invalid_item")
            identity = item.get("id")
            if type(identity) is not int or identity in seen:
                raise ValueError("row_identity_mismatch")
            if any(key not in item for key in required):
                raise ValueError("missing_row_field")
            if type(item.get("display_time")) is not int:
                raise ValueError("invalid_display_time")
            seen.add(identity)
            rows.append(item)
        return rows, len(rows), True
    except ProviderError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise ProviderError("external_wscn_schema_invalid") from None
