"""Versioned strict date/instant validation; no optional third-party checker.

RFC3339 strict subset matching pack instant precision: four-digit calendar years,
uppercase T/Z, seconds, optional 1..6 fractional digits, explicit valid offset.
Leap seconds and UTC conversions outside years 1..9999 are rejected explicitly.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime

from jsonschema import FormatChecker

log = logging.getLogger(__name__)
PROFILE = "research_pack_date_formats_v1"
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_INSTANT = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z"
)


def valid_date(value):
    if not isinstance(value, str):
        return True
    if not _DATE.fullmatch(value):
        return False
    return date.fromisoformat(value).isoformat() == value


def valid_instant(value):
    if not isinstance(value, str):
        return True
    if not _INSTANT.fullmatch(value):
        return False
    parsed = datetime.fromisoformat(value)
    return parsed.tzinfo is not None and parsed.astimezone(UTC).year in range(1, 10000)


def format_checker():
    """A private checker instance: never changes jsonschema's global registry."""
    checker = FormatChecker(formats=[])
    checker.checks("date", raises=(ValueError, OverflowError))(valid_date)
    checker.checks("date-time", raises=(ValueError, OverflowError))(valid_instant)
    return checker


def require_local_schema(schema):
    """The fixed pack schemas cannot request external resolution/dynamic schemas."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in {"$ref", "$dynamicRef", "$recursiveRef", "$id", "$schema"}:
                log.warning("research_pack_external_schema_rejected")
                raise ValueError("pack_external_schema_forbidden")
            if key == "format" and value not in {"date", "date-time"}:
                log.warning("research_pack_format_profile_rejected")
                raise ValueError("pack_format_profile_unsupported")
            require_local_schema(value)
    elif isinstance(schema, list):
        for item in schema:
            require_local_schema(item)
