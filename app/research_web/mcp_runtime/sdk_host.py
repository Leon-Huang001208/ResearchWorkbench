"""Bounded facade over the official MCP Python SDK client."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from core.observability import get_logger

from .credentials import RuntimeCredentialError, RuntimeCredentialStore
from .oauth import OAuthError
from .transport import (
    RemoteTarget,
    StdioTarget,
    validate_remote_endpoint,
    validate_stdio_target,
)

log = get_logger(__name__)
_NAME = re.compile(r"^[A-Za-z0-9_.:/-]{1,256}$")


class MCPHostError(RuntimeError):
    """Stable Host error that omits target, arguments and third-party bodies."""


class SDKHost:
    """Expose tools/resources/prompts without sampling, elicitation or MCP Tasks."""

    def __init__(
        self,
        *,
        client_factory: Callable[..., Any] | None = None,
        target_factory: Callable[[Any], Any] | None = None,
        remote_target_factory: Callable[[str, str | None], Any] | None = None,
        credentials: RuntimeCredentialStore | None = None,
        max_result_bytes: int = 1024 * 1024,
        max_request_bytes: int = 1024 * 1024,
        max_remote_response_bytes: int = 1024 * 1024,
    ) -> None:
        self.client_factory = client_factory or self._official_client
        self.target_factory = target_factory or self._official_target
        self.remote_target_factory = remote_target_factory or self._remote_transport
        self.credentials = credentials or RuntimeCredentialStore()
        self.max_result_bytes = max_result_bytes
        self.max_request_bytes = max_request_bytes
        self.max_remote_response_bytes = max_remote_response_bytes

    @staticmethod
    def _official_client(target: Any, **options: Any):
        try:
            from mcp.client import Client
        except (ImportError, AttributeError) as exc:
            raise MCPHostError("mcp_sdk_unavailable") from exc
        return Client(target, **options)

    @staticmethod
    def _official_target(target: Any):
        if isinstance(target, StdioTarget):
            try:
                from mcp import StdioServerParameters
            except (ImportError, AttributeError) as exc:
                raise MCPHostError("mcp_sdk_unavailable") from exc
            return StdioServerParameters(
                command=target.argv[0],
                args=list(target.argv[1:]),
                cwd=str(target.cwd),
                env=dict(target.env),
            )
        return target

    @asynccontextmanager
    async def _remote_transport(self, endpoint: str, bearer_token: str | None):
        """Use an SDK transport with proxies and automatic redirects disabled."""

        try:
            import httpx2
            from mcp.client.streamable_http import streamable_http_client
        except (ImportError, AttributeError) as exc:
            raise MCPHostError("mcp_sdk_unavailable") from exc

        class _CappedStream(httpx2.AsyncByteStream):
            def __init__(self, stream, maximum: int) -> None:
                self._stream = stream
                self._maximum = maximum

            async def __aiter__(self):
                consumed = 0
                async for chunk in self._stream:
                    consumed += len(chunk)
                    if consumed > self._maximum:
                        raise MCPHostError("mcp_remote_response_too_large")
                    yield chunk

            async def aclose(self) -> None:
                await self._stream.aclose()

        async def cap_response(response) -> None:
            try:
                declared = int(response.headers.get("content-length", "0") or 0)
            except ValueError as exc:
                raise MCPHostError("mcp_remote_response_invalid") from exc
            if declared > self.max_remote_response_bytes:
                raise MCPHostError("mcp_remote_response_too_large")
            response.stream = _CappedStream(response.stream, self.max_remote_response_bytes)

        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        async with (
            httpx2.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                headers=headers,
                timeout=httpx2.Timeout(30, connect=5),
                event_hooks={"response": [cap_response]},
            ) as http,
            streamable_http_client(endpoint, http_client=http) as transport,
        ):
            yield transport

    def _client(self, target: Any):
        if isinstance(target, RemoteTarget):
            try:
                endpoint = validate_remote_endpoint(target.endpoint)
                audience = validate_remote_endpoint(target.audience)
                if endpoint != audience:
                    raise ValueError("audience differs from endpoint")
                token_record = self.credentials.read(
                    target.installation_id,
                    target.credential_slot,
                    expected_resource=audience,
                )
                token = token_record.get("access_token") if token_record else None
                if token_record and (
                    token_record.get("token_type", "").lower() != "bearer"
                    or not isinstance(token, str)
                    or not token
                    or len(token.encode("utf-8")) > 64 * 1024
                    or any(ord(char) < 32 for char in token)
                ):
                    raise ValueError("credential is invalid")
            except (ValueError, RuntimeCredentialError, OAuthError) as exc:
                raise MCPHostError("mcp_target_invalid") from exc
            bearer_token = token if isinstance(token, str) else None
            resolved = self.remote_target_factory(endpoint, bearer_token)
        elif isinstance(target, StdioTarget):
            try:
                target = validate_stdio_target(target)
            except ValueError as exc:
                raise MCPHostError("mcp_target_invalid") from exc
            resolved = self.target_factory(target)
        else:
            resolved = self.target_factory(target)
        return self.client_factory(
            resolved,
            mode="auto",
            sampling_callback=None,
            elicitation_callback=None,
            extensions=(),
            cache=None,
            read_timeout_seconds=30.0,
        )

    @staticmethod
    def _target_digest(target: Any) -> str | None:
        installation_id = getattr(target, "installation_id", None)
        if not isinstance(installation_id, str):
            return None
        return hashlib.sha256(installation_id.encode("utf-8", errors="replace")).hexdigest()[:16]

    def _bounded(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "model_dump"):
            value = result.model_dump(mode="json")
        elif isinstance(result, dict):
            value = result
        else:
            raise MCPHostError("mcp_result_invalid")
        if not isinstance(value, dict):
            raise MCPHostError("mcp_result_invalid")
        try:
            raw = json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise MCPHostError("mcp_result_invalid") from exc
        if len(raw) > self.max_result_bytes:
            raise MCPHostError("mcp_result_too_large")
        return value

    def _validate_request(self, value: Any) -> None:
        try:
            raw = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise MCPHostError("mcp_request_invalid") from exc
        if len(raw) > self.max_request_bytes:
            raise MCPHostError("mcp_request_too_large")

    async def capabilities(self, target: Any) -> dict[str, Any]:
        try:
            async with self._client(target) as client:
                tools = self._bounded(await client.list_tools()).get("tools", [])
                resources = self._bounded(await client.list_resources()).get("resources", [])
                prompts = self._bounded(await client.list_prompts()).get("prompts", [])
                projected_tools = []
                for tool in tools:
                    if not isinstance(tool, dict) or not _NAME.fullmatch(str(tool.get("name", ""))):
                        raise MCPHostError("mcp_capabilities_invalid")
                    schema = tool.get("inputSchema", tool.get("input_schema"))
                    if not isinstance(schema, dict):
                        raise MCPHostError("mcp_capabilities_invalid")
                    schema_raw = json.dumps(
                        schema, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode()
                    projected_tools.append(
                        {**tool, "schema_sha256": hashlib.sha256(schema_raw).hexdigest()}
                    )
                return {
                    "protocol_version": str(client.protocol_version),
                    "server": self._server_projection(client.server_info),
                    "tools": projected_tools,
                    "resources": resources,
                    "prompts": prompts,
                    "sampling": False,
                    "elicitation": False,
                    "tasks": False,
                }
        except MCPHostError:
            raise
        except Exception as exc:
            log.warning(
                "mcp_host_capability_failed",
                installation_id_digest=self._target_digest(target),
                error_type=type(exc).__name__,
            )
            raise MCPHostError("mcp_capability_probe_failed") from exc

    @staticmethod
    def _server_projection(server: Any) -> dict[str, str] | None:
        if server is None:
            return None
        name = getattr(server, "name", None)
        version = getattr(server, "version", None)
        if not isinstance(name, str) or not isinstance(version, str):
            return None
        return {"name": name[:256], "version": version[:256]}

    async def _invoke(self, target: Any, event: str, operation: Callable[[Any], Any]):
        try:
            async with self._client(target) as client:
                return self._bounded(await operation(client))
        except MCPHostError:
            raise
        except Exception as exc:
            log.warning(
                event,
                installation_id_digest=self._target_digest(target),
                error_type=type(exc).__name__,
            )
            raise MCPHostError("mcp_operation_failed") from exc

    async def call_tool(self, target: Any, name: str, arguments: dict[str, Any]):
        if not _NAME.fullmatch(name) or not isinstance(arguments, dict):
            raise MCPHostError("mcp_tool_request_invalid")
        self._validate_request(arguments)
        return await self._invoke(
            target,
            "mcp_host_tool_failed",
            lambda client: client.call_tool(name, arguments),
        )

    async def read_resource(self, target: Any, uri: str):
        if not isinstance(uri, str) or not uri or len(uri) > 4096 or any(ord(c) < 32 for c in uri):
            raise MCPHostError("mcp_resource_request_invalid")
        return await self._invoke(
            target,
            "mcp_host_resource_failed",
            lambda client: client.read_resource(uri),
        )

    async def get_prompt(self, target: Any, name: str, arguments: dict[str, Any] | None = None):
        if not _NAME.fullmatch(name) or (arguments is not None and not isinstance(arguments, dict)):
            raise MCPHostError("mcp_prompt_request_invalid")
        if arguments is not None:
            if any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in arguments.items()
            ):
                raise MCPHostError("mcp_prompt_request_invalid")
            self._validate_request(arguments)
        return await self._invoke(
            target,
            "mcp_host_prompt_failed",
            lambda client: client.get_prompt(name, arguments or {}),
        )
