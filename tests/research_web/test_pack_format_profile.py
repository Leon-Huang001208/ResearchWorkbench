"""Required schema formats are explicit and identical on Host and frozen Native."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.research_web.scenarios.packs import PackError, execute_atom
from app.research_web.scenarios.packs.format_profile import format_checker, require_local_schema
from app.research_web.scenarios.packs.record_contracts import RECORD_SCHEMAS


@pytest.mark.parametrize(
    "value",
    [
        "2026-02-29T12:00:00Z",
        "2026-13-01T12:00:00Z",
        "2026-01-01T24:00:00Z",
        "2026-01-01T12:00:60Z",
        "2026-01-01T12:00:00",
        "2026-01-01",
        "20260101T120000Z",
        "2026-01-01 12:00:00Z",
        "2026-01-01T12:00:00+24:00",
        "2026-01-01T12:00:00+01:60",
        "0001-01-01T00:00:00+00:01",
        "9999-12-31T23:59:59-00:01",
        "2026-01-01T12:00:00.1234567Z",
    ],
)
def test_invalid_or_unsupported_instants_are_rejected(value):
    from app.research_web.scenarios.packs.contracts import instant

    assert not format_checker().conforms(value, "date-time")
    with pytest.raises(PackError):
        instant(value)


@pytest.mark.parametrize(
    "value",
    [
        "2024-02-29T12:00:00Z",
        "2026-01-01T12:00:00+08:00",
        "2026-01-01T12:00:00.123456-03:30",
        "0001-01-01T00:00:00Z",
        "9999-12-31T23:59:59Z",
    ],
)
def test_valid_explicit_instants_remain_valid(value):
    assert format_checker().conforms(value, "date-time")


@pytest.mark.parametrize("value", ["2026-02-29", "2026-01-32", "20260101", "0000-01-01"])
def test_bad_dates_are_rejected(value):
    assert not format_checker().conforms(value, "date")


def test_profile_covers_every_schema_format_without_global_registry_mutation():
    before = dict(FormatChecker.checkers)
    found = set()

    def visit(value):
        if isinstance(value, dict):
            if "format" in value:
                found.add(value["format"])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for schema in RECORD_SCHEMAS.values():
        require_local_schema(schema)
        visit(schema)
    assert found == {"date", "date-time"} == set(format_checker().checkers)
    assert FormatChecker.checkers == before


@pytest.mark.parametrize("key", ["$ref", "$dynamicRef", "$recursiveRef", "$id", "$schema"])
def test_external_or_dynamic_schema_is_never_admitted(key):
    with pytest.raises(ValueError, match="pack_external_schema_forbidden"):
        require_local_schema({"properties": {"payload": {key: "https://example.invalid"}}})


def test_bad_timestamp_on_unselected_field_is_still_rejected_by_record_schema():
    path = Path(__file__).parents[2] / "app/research_web/scenarios/packs/synthetic_vectors.json"
    vector = copy.deepcopy(
        next(v for v in json.loads(path.read_bytes()) if v["id"] == "validate_positions.success")
    )
    row = vector["records_by_kind"]["position"][0]
    row["origin"]["observed_at"] = "2026-02-30T12:00:00Z"
    assert list(
        Draft202012Validator(
            RECORD_SCHEMAS["position"], format_checker=format_checker()
        ).iter_errors(row)
    )
    with pytest.raises(PackError, match="record_contract_invalid"):
        execute_atom(vector["atom"], vector["records_by_kind"], vector["parameters"])
