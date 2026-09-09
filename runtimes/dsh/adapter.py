"""HTTP adapter for AlphaFoundry's project-managed DeepSeek Harness bridge.

The bridge is hosted by the AlphaFoundry DSH bundle. This module deliberately
does not import DSH packages: it owns only protocol conversion, local-host
validation, and error mapping.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, model_validator

from core.contracts.runtime import (
    AlphaEvent,
    ExecutionHandle,
    RuntimeDescriptor,
    RuntimeUnavailableError,
    SkillSpec,
    ToolSpec,
    WorkflowSpec,
)
from core.observability import get_logger

logger = get_logger(__name__)

BRIDGE_PREFIX = "/alphafoundry/bridge/v1"


class DSHBridgeSettings(BaseModel):
    """Non-secret bridge address plus the outbound AlphaFoundry credential."""

    bridge_url: str = Field(min_length=1)
    bridge_token: str = Field(min_length=16)
    timeout_seconds: int = Field(default=90, gt=0, le=900)

    @model_validator(mode="after")
    def validate_loopback_url(self) -> DSHBridgeSettings:
        parsed = urlsplit(self.bridge_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("DSH bridge URL must use an HTTP loopback host")
        if parsed.username or parsed.password or parsed.path not in {"", "/"}:
            raise ValueError("DSH bridge URL must be an origin without credentials or path")
        return self

    @classmethod
    def from_environment(cls) -> DSHBridgeSettings | None:
        url = os.getenv("ALPHAFOUNDRY_DSH_BRIDGE_URL", "").strip()
        token = os.getenv("ALPHAFOUNDRY_DSH_BRIDGE_TOKEN", "").strip()
        if not url and not token:
            return None
        if not url or not token:
            raise ValueError(
                "ALPHAFOUNDRY_DSH_BRIDGE_URL and ALPHAFOUNDRY_DSH_BRIDGE_TOKEN must be configured together"
            )
        return cls(bridge_url=url, bridge_token=token)


class DSHTransport(Protocol):
    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    def stream_events(self, path: str) -> list[dict[str, Any]]: ...


class HttpDSHTransport:
    """Small stdlib transport so DSH remains outside AlphaFoundry dependencies."""

    def __init__(self, settings: DSHBridgeSettings):
        self._settings = settings
        self._base_url = settings.bridge_url.rstrip("/")

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not path.startswith(BRIDGE_PREFIX):
            raise ValueError("DSH bridge request path is outside the approved prefix")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._settings.bridge_token}",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            with urlopen(request, timeout=self._settings.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            logger.warning("DSH bridge rejected request", status_code=exc.code, path=path)
            raise RuntimeUnavailableError(
                f"DSH bridge request failed with HTTP {exc.code}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            logger.warning("DSH bridge is unavailable", path=path, error=str(exc))
            raise RuntimeUnavailableError("DSH bridge is unavailable") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("DSH bridge returned invalid JSON", path=path)
            raise RuntimeUnavailableError("DSH bridge returned an invalid response") from exc
        if not isinstance(decoded, dict):
            raise RuntimeUnavailableError("DSH bridge response must be a JSON object")
        return decoded

    def stream_events(self, path: str) -> list[dict[str, Any]]:
        """Read the Bridge's finite replay SSE response into typed event records."""
        if not path.startswith(BRIDGE_PREFIX):
            raise ValueError("DSH bridge request path is outside the approved prefix")
        request = Request(
            f"{self._base_url}{path}",
            method="GET",
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {self._settings.bridge_token}",
            },
        )
        try:
            with urlopen(request, timeout=self._settings.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            logger.warning("DSH bridge rejected event replay", status_code=exc.code, path=path)
            raise RuntimeUnavailableError(
                f"DSH bridge event replay failed with HTTP {exc.code}"
            ) from exc
        except (URLError, TimeoutError, UnicodeDecodeError) as exc:
            logger.warning("DSH bridge event replay is unavailable", path=path, error=str(exc))
            raise RuntimeUnavailableError("DSH bridge event replay is unavailable") from exc
        events: list[dict[str, Any]] = []
        for frame in raw.split("\n\n"):
            data = next(
                (line[5:].strip() for line in frame.splitlines() if line.startswith("data:")),
                "",
            )
            if not data:
                continue
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError as exc:
                raise RuntimeUnavailableError("DSH bridge emitted an invalid SSE event") from exc
            if not isinstance(parsed, dict):
                raise RuntimeUnavailableError("DSH bridge SSE data must be a JSON object")
            events.append(parsed)
        return events


class DSHAdapter:
    """Translate the AlphaFoundry Runtime Interface to the DSH Bridge API."""

    def __init__(self, *, descriptor: RuntimeDescriptor, transport: DSHTransport):
        self.descriptor = descriptor
        self._transport = transport
        self._disposed = False

    @classmethod
    def from_environment(cls, *, descriptor: RuntimeDescriptor) -> DSHAdapter | None:
        settings = DSHBridgeSettings.from_environment()
        if settings is None:
            return None
        return cls(descriptor=descriptor, transport=HttpDSHTransport(settings))

    def create_session(self, *, run_id: str) -> ExecutionHandle:
        self._ensure_active()
        response = self._transport.request("POST", f"{BRIDGE_PREFIX}/sessions", {"run_id": run_id})
        execution_id = response.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id:
            raise RuntimeUnavailableError("DSH bridge did not return an execution_id")
        return ExecutionHandle(
            run_id=run_id,
            runtime_id=self.descriptor.runtime_id,
            execution_id=execution_id,
            resumable=bool(response.get("resumable", self.descriptor.capabilities.resume)),
        )

    def register_tools(self, tools: list[ToolSpec]) -> None:
        self._verify_deployment("tools", [item.capability_id for item in tools])

    def register_skills(self, skills: list[SkillSpec]) -> None:
        self._verify_deployment("skills", [item.capability_id for item in skills])

    def run_task(self, *, handle: ExecutionHandle, task: dict[str, Any]) -> dict[str, Any]:
        self._ensure_active()
        response = self._transport.request(
            "POST",
            f"{BRIDGE_PREFIX}/executions/{quote(handle.execution_id, safe='')}/tasks",
            task,
        )
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeUnavailableError("DSH bridge task response misses an object result")
        return result

    def run_skill(
        self, *, handle: ExecutionHandle, skill: SkillSpec, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self.run_task(
            handle=handle,
            task={
                "skill_id": skill.capability_id,
                "skill_version": skill.version,
                "payload": payload,
                "output_schema": skill.output_schema,
                "timeout_seconds": skill.timeout_seconds,
                "idempotency_key": skill.idempotency_key,
            },
        )

    def run_workflow(self, *, handle: ExecutionHandle, workflow: WorkflowSpec) -> dict[str, Any]:
        del handle, workflow
        raise RuntimeUnavailableError(
            "DSH supports Skill execution only; AlphaFoundry owns workflow orchestration"
        )

    def stream_events(self, *, run_id: str, after_sequence: int = 0) -> list[AlphaEvent]:
        self._ensure_active()
        raw_events = self._transport.stream_events(
            f"{BRIDGE_PREFIX}/runs/{quote(run_id, safe='')}/events?after_sequence={after_sequence}"
        )
        return [AlphaEvent.model_validate(item) for item in raw_events]

    def cancel(self, *, handle: ExecutionHandle) -> None:
        self._ensure_active()
        self._transport.request(
            "POST", f"{BRIDGE_PREFIX}/executions/{quote(handle.execution_id, safe='')}/cancel", {}
        )

    def resume(self, *, run_id: str) -> ExecutionHandle:
        self._ensure_active()
        response = self._transport.request(
            "POST", f"{BRIDGE_PREFIX}/runs/{quote(run_id, safe='')}/resume", {"run_id": run_id}
        )
        execution_id = response.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id:
            raise RuntimeUnavailableError("DSH bridge did not return an execution_id for resume")
        return ExecutionHandle(
            run_id=run_id,
            runtime_id=self.descriptor.runtime_id,
            execution_id=execution_id,
            resumable=True,
        )

    def health(self) -> dict[str, Any]:
        self._ensure_active()
        return self._transport.request("GET", f"{BRIDGE_PREFIX}/health")

    def dispose(self) -> None:
        """Release this client without stopping the shared project DSH Host."""
        self._disposed = True

    def _verify_deployment(self, kind: str, capability_ids: list[str]) -> None:
        state = self.health()
        declared = state.get(kind, [])
        if not isinstance(declared, list):
            raise RuntimeUnavailableError("DSH bridge deployment manifest is invalid")
        missing = sorted(set(capability_ids) - {item for item in declared if isinstance(item, str)})
        if missing:
            raise RuntimeUnavailableError(
                f"DSH bridge is missing deployed {kind}: {', '.join(missing)}"
            )

    def _ensure_active(self) -> None:
        if self._disposed:
            raise RuntimeUnavailableError("DSH adapter has been disposed")
