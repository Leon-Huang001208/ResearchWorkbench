"""Closed, static execution inventory is never runtime authority."""

import pytest

from app.research_web.scenarios.execution_bindings import (
    binding_for,
    read_execution_bindings,
    validate_supplier_arguments,
)
from app.research_web.scenarios.models import ScenarioError


def test_exact_frozen_inventory_and_independent_evidence():
    result = read_execution_bindings()
    rows = result["bindings"]
    assert len(rows) == len({row["original_id"] for row in rows}) == 140
    assert sum(row["original_kind"] == "skill" for row in rows) == 62
    assert sum(len(row["parameters"]) for row in rows) == 284
    native = [row for row in rows if row["native"]["action"] == "implemented_pack_subset"]
    assert len(native) == 18
    for row in rows:
        for side in ("original", "native"):
            assert row[side]["ready"] == "requires_current_host_evidence"
            assert row[side]["callable"] == "unverified"
            assert row[side]["runtime"] == row[side]["quality"] == "NOT_RUN"
    result["bindings"].clear()
    assert len(read_execution_bindings()["bindings"]) == 140


def test_every_supplier_parameter_rejects_explicit_input():
    for row in read_execution_bindings()["bindings"]:
        for parameter in row["parameters"]:
            assert parameter["support"] == "unsupported"
            assert parameter["required"] == "unknown"
            with pytest.raises(ScenarioError) as error:
                validate_supplier_arguments(row["original_id"], {parameter["name"]: None})
            assert error.value.code == "execution_parameter_unsupported"
        with pytest.raises(ScenarioError) as error:
            validate_supplier_arguments(row["original_id"], {})
        assert error.value.code == "execution_alias_unregistered"


@pytest.mark.parametrize("arguments", [{"module": "os"}, {"url": "https://example.org"}, [], None])
def test_no_dynamic_dispatch_or_unknown_arguments(arguments):
    with pytest.raises(ScenarioError) as error:
        validate_supplier_arguments("tool:query_news", arguments)
    assert error.value.code == "execution_arguments_invalid"
    with pytest.raises(ScenarioError) as unknown:
        binding_for("tool:made_up")
    assert unknown.value.code == "execution_binding_unknown"


@pytest.mark.parametrize(
    "mutation", ["bytes", "extra_row", "extra_parameter", "route", "module", "support", "ready"]
)
def test_corrupt_or_unknown_binding_fields_are_rejected(monkeypatch, mutation):
    import copy
    import hashlib
    import io
    import json
    from pathlib import Path

    from app.research_web.scenarios import execution_bindings as module

    value = copy.deepcopy(read_execution_bindings())
    row = next(row for row in value["bindings"] if row["original_id"] == "tool:query_news")
    if mutation == "extra_row":
        row["approved"] = True
    elif mutation == "extra_parameter":
        row["parameters"][0]["default"] = "guessed"
    elif mutation == "route":
        row["route"] = "python_import"
    elif mutation == "module":
        row["native_target"] = {"module": "os"}
    elif mutation == "support":
        row["parameters"][0]["support"] = "supported"
    elif mutation == "ready":
        row["native"]["ready"] = True
    raw = json.dumps(value).encode()
    original_open = Path.open

    def opened(path, *args, **kwargs):
        return (
            io.BytesIO(raw)
            if path.name == "execution-bindings-v1.json"
            else original_open(path, *args, **kwargs)
        )

    monkeypatch.setattr(Path, "open", opened)
    if mutation != "bytes":
        # Simulates reviewing new inventory bytes: structural contracts remain
        # closed even if someone updates the byte digest without an adapter.
        monkeypatch.setattr(module, "BINDINGS_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ScenarioError) as error:
        read_execution_bindings()
    assert error.value.code == "execution_bindings_invalid"
