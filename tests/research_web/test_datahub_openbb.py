"""OpenBB stays a fixed, separately installed SDK behind the DataHub boundary."""

import asyncio
import json
import subprocess
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.research_web.datahub import BusinessQuery, DataHub, providers_openbb
from app.research_web.datahub.catalog import build_catalog
from app.research_web.datahub.providers import ProviderError, Result
from app.research_web.store import Store


def arguments(**overrides):
    value = {
        "params": {"symbol": "AAPL", "provider": "nasdaq"},
        "query": {"start_date": "2026-11-20", "end_date": "2026-11-25"},
    }
    value.update(overrides)
    return json.dumps(value)


def query(**parameters):
    return BusinessQuery(
        capability="external_data",
        source="openbb",
        purpose="display",
        parameters={"dataset": "equity_daily", "arguments_json": arguments(), **parameters},
    )


def payload(status="snapshot", rows=None):
    result = Result(
        rows=[{"date": "2026-11-25", "close": 355.58}] if rows is None else rows,
        raw=[b"date,close\n2026-11-25,355.58\n"],
        status=status,
        provider_id="openbb",
        fields={"date": {"type": "date", "unit": "date"}},
        metadata={"schema_version": providers_openbb.CONTRACT},
    )
    encoded = asdict(result)
    encoded["raw"] = ["ZGF0ZSxjbG9zZQoyMDI2LTExLTI1LDM1NS41OAo="]
    return encoded


def test_fixed_arguments_reject_unreviewed_sdk_inputs():
    for value in (
        '{"params": {"symbol": "AAPL", "provider": "arbitrary"}}',
        '{"params": {"symbol": "AAPL", "provider": "nasdaq"}, "body": {}}',
        (
            '{"params": {"symbol": "AAPL; rm -rf /", "provider": "nasdaq"},'
            ' "query": {"start_date": "2026-11-20", "end_date": "2026-11-25"}}'
        ),
        (
            '{"params": {"symbol": "AAPL", "provider": "nasdaq"},'
            ' "query": {"start_date": "2026-11-25", "end_date": "2026-11-20"}}'
        ),
        (
            '{"params": {"symbol": "AAPL", "provider": "nasdaq"},'
            ' "query": {"start_date": "2026-11-20", "end_date": "2026-11-25"},'
            ' "headers": {"x": "y"}}'
        ),
    ):
        with pytest.raises(ProviderError):
            providers_openbb._arguments(value)


def test_fixed_arguments_accept_the_reviewed_contract():
    assert providers_openbb._arguments(arguments()) == {
        "symbol": "AAPL",
        "provider": "nasdaq",
        "start": "2026-11-20",
        "end": "2026-11-25",
    }


def test_backtest_and_historical_semantics_are_rejected_before_start():
    with pytest.raises(ProviderError, match="openbb_historical_semantics_unsupported"):
        providers_openbb.validate(
            BusinessQuery(
                capability="external_data",
                source="openbb",
                parameters={"dataset": "equity_daily", "arguments_json": arguments()},
                purpose="backtest",
                as_of="2026-11-25T00:00:00+08:00",
            )
        )
    with pytest.raises(ProviderError, match="data_operation_unsupported"):
        providers_openbb.validate(
            BusinessQuery(
                capability="external_data",
                source="ext_fred",
                parameters={"dataset": "equity_daily", "arguments_json": arguments()},
            )
        )


def test_missing_interpreter_is_a_dependency_failure(monkeypatch):
    monkeypatch.setenv(providers_openbb.PYTHON_ENV, "/nonexistent/python")
    assert providers_openbb.interpreter() is None
    with pytest.raises(ProviderError, match="missing_dependency"):
        asyncio.run(providers_openbb.fetch(query()))


def test_worker_command_and_environment_are_fixed(monkeypatch, tmp_path):
    interpreter = tmp_path / "python"
    interpreter.write_text("#!/bin/sh\n")
    interpreter.chmod(0o755)
    monkeypatch.setenv(providers_openbb.PYTHON_ENV, str(interpreter))
    encoded = payload()
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"ok": True, "result": encoded}).encode(),
        )

    with patch("app.research_web.datahub.providers_openbb.subprocess.run", run):
        result = providers_openbb._invoke(query())

    command, kwargs = calls[0]
    assert command[1:] == ["-m", "app.research_web.datahub.public_worker", "openbb"]
    assert command[0] == str(interpreter)
    assert kwargs["timeout"] == providers_openbb.DEADLINE
    assert kwargs["env"]["HOME"] == kwargs["cwd"]
    assert kwargs["env"]["RESEARCH_PROJECT_ROOT"] == kwargs["cwd"]
    assert "OPENBB" not in kwargs["env"]
    assert result.provider_id == "openbb"
    assert result.rows == encoded["rows"]
    assert result.raw == [b"date,close\n2026-11-25,355.58\n"]


def test_deadline_and_malformed_output_fail_closed(monkeypatch, tmp_path):
    interpreter = tmp_path / "python"
    interpreter.write_text("#!/bin/sh\n")
    interpreter.chmod(0o755)
    monkeypatch.setenv(providers_openbb.PYTHON_ENV, str(interpreter))

    with (
        patch(
            "app.research_web.datahub.providers_openbb.subprocess.run",
            side_effect=subprocess.TimeoutExpired("openbb", providers_openbb.DEADLINE),
        ),
        pytest.raises(ProviderError, match="deadline"),
    ):
        providers_openbb._invoke(query())

    with (
        patch(
            "app.research_web.datahub.providers_openbb.subprocess.run",
            return_value=SimpleNamespace(
                returncode=0, stdout=b'{"ok": true, "result": {"rows": []}}'
            ),
        ),
        pytest.raises(ProviderError, match="vendor_schema_invalid"),
    ):
        providers_openbb._invoke(query())

    with (
        patch(
            "app.research_web.datahub.providers_openbb.subprocess.run",
            return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps({"ok": False, "code": "secret text"}).encode()
            ),
        ),
        pytest.raises(ProviderError, match="vendor_unreachable"),
    ):
        providers_openbb._invoke(query())


def test_catalog_exposes_openbb_only_when_the_interpreter_is_configured(monkeypatch):
    monkeypatch.setattr(providers_openbb, "interpreter", lambda: None)
    catalog = build_catalog(environ={})
    openbb = next(source for source in catalog["sources"] if source["id"] == "openbb")
    assert openbb["readiness"]["integration_state"] == "blocked_dependency"
    assert openbb["readiness"]["callable"] is False
    external = [
        binding
        for binding in catalog["bindings"]
        if binding["capability_id"] == "external_data" and binding["source_id"] == "openbb"
    ]
    assert len(external) == 1
    assert external[0]["datasets"] == ["equity_daily"]

    monkeypatch.setattr(providers_openbb, "interpreter", lambda: "/opt/openbb/python")
    catalog = build_catalog(environ={})
    openbb = next(source for source in catalog["sources"] if source["id"] == "openbb")
    assert openbb["readiness"]["integration_state"] == "ready"
    assert openbb["readiness"]["callable"] is True
    external = [
        binding
        for binding in catalog["bindings"]
        if binding["capability_id"] == "external_data" and binding["source_id"] == "openbb"
    ]
    assert len(external) == 1
    assert external[0]["datasets"] == ["equity_daily"]
    assert external[0]["implemented"] is True


@pytest.mark.asyncio
async def test_end_to_end_query_publishes_a_source_qualified_snapshot(monkeypatch, tmp_path):
    interpreter = tmp_path / "python"
    interpreter.write_text("#!/bin/sh\n")
    interpreter.chmod(0o755)
    monkeypatch.setenv(providers_openbb.PYTHON_ENV, str(interpreter))
    encoded = payload()

    with patch(
        "app.research_web.datahub.providers_openbb.subprocess.run",
        return_value=SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"ok": True, "result": encoded}).encode(),
        ),
    ):
        store = Store(tmp_path / "store")
        sid = store.create("claw", "test")["id"]
        hub = DataHub(store)
        try:
            result = await hub.query(sid, "openbb-1", query())
            snapshots = hub.list(sid)
        finally:
            await hub.close()

    assert result["status"] == "snapshot"
    assert result["data_success"] is True
    assert result["status"] == "snapshot"
    assert result["attempted_sources"] == [
        {"source": "openbb", "status": "selected", "reason": None}
    ]
    assert len(snapshots) == 1
    assert snapshots[0]["provider"] == "openbb"
    assert snapshots[0]["row_count"] == 1


@pytest.mark.asyncio
async def test_broker_rejects_dataset_outside_the_fixed_contract(monkeypatch, tmp_path):
    monkeypatch.setenv(providers_openbb.PYTHON_ENV, "/opt/openbb/python")
    store = Store(tmp_path)
    sid = store.create("claw", "test")["id"]
    hub = DataHub(store)
    try:
        with pytest.raises(ProviderError, match="data_operation_unsupported"):
            await hub.query(
                sid,
                "openbb-2",
                BusinessQuery(
                    capability="external_data",
                    source="openbb",
                    parameters={"dataset": "arbitrary"},
                ),
            )
    finally:
        await hub.close()
