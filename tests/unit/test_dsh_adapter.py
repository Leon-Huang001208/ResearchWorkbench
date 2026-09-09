from __future__ import annotations

from typing import Any

import pytest

from core.contracts.runtime import (
    RuntimeCapabilities,
    RuntimeDescriptor,
    RuntimeUnavailableError,
)
from runtimes.dsh.adapter import DSHAdapter, DSHBridgeSettings


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append((method, path, payload))
        if path == "/alphafoundry/bridge/v1/sessions":
            return {"execution_id": "exec-1", "resumable": True}
        if path.startswith("/alphafoundry/bridge/v1/runs/run-1/events"):
            return {
                "events": [
                    {
                        "event_id": "evt-1",
                        "event_type": "SkillCompleted",
                        "run_id": "run-1",
                        "sequence": 3,
                        "payload": {"skill_id": "market-close-review"},
                    }
                ]
            }
        return {"result": {"summary": "ok"}}

    def stream_events(self, path: str) -> list[dict[str, Any]]:
        self.calls.append(("GET", path, None))
        return [
            {
                "event_id": "evt-1",
                "event_type": "SkillCompleted",
                "run_id": "run-1",
                "sequence": 3,
                "payload": {"skill_id": "market-close-review"},
            }
        ]


def _adapter(transport: RecordingTransport) -> DSHAdapter:
    return DSHAdapter(
        descriptor=RuntimeDescriptor(
            runtime_id="dsh-local",
            display_name="DSH",
            protocol_version="alphafoundry.io/v1",
            capabilities=RuntimeCapabilities(
                skills=True, streaming=True, cancellation=True, resume=True
            ),
        ),
        transport=transport,
    )


def test_dsh_adapter_uses_bridge_routes_and_never_delegates_workflow_orchestration():
    transport = RecordingTransport()
    adapter = _adapter(transport)

    handle = adapter.create_session(run_id="run-1")
    result = adapter.run_task(
        handle=handle,
        task={"skill_id": "market-close-review", "payload": {"snapshot": {}}},
    )
    events = adapter.stream_events(run_id="run-1", after_sequence=2)
    adapter.cancel(handle=handle)

    assert handle.execution_id == "exec-1"
    assert result == {"summary": "ok"}
    assert events[0].sequence == 3
    assert transport.calls == [
        ("POST", "/alphafoundry/bridge/v1/sessions", {"run_id": "run-1"}),
        (
            "POST",
            "/alphafoundry/bridge/v1/executions/exec-1/tasks",
            {"skill_id": "market-close-review", "payload": {"snapshot": {}}},
        ),
        ("GET", "/alphafoundry/bridge/v1/runs/run-1/events?after_sequence=2", None),
        ("POST", "/alphafoundry/bridge/v1/executions/exec-1/cancel", {}),
    ]
    with pytest.raises(RuntimeUnavailableError, match="workflow"):
        adapter.run_workflow(handle=handle, workflow=None)  # type: ignore[arg-type]


def test_dsh_bridge_settings_rejects_non_loopback_host():
    with pytest.raises(ValueError, match="loopback"):
        DSHBridgeSettings(bridge_url="https://dsh.example.com", bridge_token="bridge-token-012345")
