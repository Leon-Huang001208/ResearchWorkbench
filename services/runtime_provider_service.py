"""Capability-based research runtime routing with explicit fallback semantics."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from core.contracts.research_workspace import (
    SAFE_INTERNAL_TOOL_IDS,
    ProviderExecutionResult,
    ProviderTerminalStatus,
    RuntimeProvider,
    RuntimeProviderStatus,
    SkillManifest,
)
from core.observability import get_logger

logger = get_logger(__name__)
T = TypeVar("T")


def load_authorized_tool_registry() -> frozenset[str]:
    """Load the platform-owned allowlist; request payloads cannot extend it."""

    configured = {
        item.strip()
        for item in os.environ.get("ALPHAFOUNDRY_AUTHORIZED_RESEARCH_TOOLS", "").split(",")
        if item.strip()
    }
    return frozenset(set(SAFE_INTERNAL_TOOL_IDS) | configured)


class RuntimeBlockedError(RuntimeError):
    """Stable runtime failure exposed to API clients."""

    def __init__(self, message: str, *, code: str = "blocked_runtime") -> None:
        super().__init__(message)
        self.code = code


class RuntimeFailedError(RuntimeError):
    """Typed execution failure that must never be converted into fallback or blocked."""

    def __init__(self, message: str, *, code: str = "research_runtime_failed") -> None:
        super().__init__(message)
        self.code = code


class RuntimeUnavailableError(RuntimeError):
    """Explicit provider availability failure eligible for FinGPT fallback only."""

    def __init__(self, message: str, *, code: str = "runtime_unavailable") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RuntimeExecutionResult:
    provider_id: str
    output: Any
    fallback_from: str | None = None
    provider_result_id: str | None = None
    terminal_status: ProviderTerminalStatus = ProviderTerminalStatus.COMPLETED


@dataclass(frozen=True)
class InvocationUsage:
    tokens_used: int
    cost_used: float


@dataclass(frozen=True)
class SkillInvocationResult:
    output: dict[str, Any]
    tokens_used: int
    cost_used: float


class ResearchToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(min_length=1, max_length=160)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AuthorizedResearchToolDispatcher:
    """Executable, closed registry for internal, MCP, attachment, and web tools."""

    def __init__(
        self,
        *,
        internal_tools: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        mcp_tools: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        attachment_resolver: Callable[[str], Any] | None = None,
        controlled_web_policies: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
    ) -> None:
        self._internal_tools = dict(internal_tools or {})
        self._mcp_tools = dict(mcp_tools or {})
        self._attachment_resolver = attachment_resolver
        self._controlled_web_policies = dict(controlled_web_policies or {})
        unsafe_internal = set(self._internal_tools).difference(SAFE_INTERNAL_TOOL_IDS)
        if unsafe_internal:
            raise ValueError(f"unsafe internal tool registration: {sorted(unsafe_internal)}")
        if any(not key.startswith("mcp:") for key in self._mcp_tools):
            raise ValueError("MCP registrations must use mcp: identifiers")

    @property
    def authorized_tool_ids(self) -> frozenset[str]:
        values = set(self._internal_tools) | set(self._mcp_tools)
        if self._attachment_resolver is not None:
            values.add("attachment:read")
        if self._controlled_web_policies:
            values.add("web:controlled")
        return frozenset(values)

    def dispatch(self, manifest: SkillManifest, request: dict[str, Any]) -> Any:
        try:
            parsed = ResearchToolRequest.model_validate(request)
        except Exception as exc:
            raise RuntimeBlockedError(
                "Invalid bounded tool request", code="invalid_tool_request"
            ) from exc
        if parsed.tool_id not in manifest.allowed_tools:
            raise RuntimeBlockedError(
                f"Tool {parsed.tool_id} is not declared by the Skill",
                code="tool_not_declared",
            )
        if parsed.tool_id.startswith("internal:"):
            handler = self._internal_tools.get(parsed.tool_id)
            if handler is None:
                raise RuntimeBlockedError(
                    f"Internal tool {parsed.tool_id} is not registered",
                    code="tool_not_registered",
                )
            result = self._invoke_registered_tool(parsed.tool_id, handler, parsed.arguments)
        elif parsed.tool_id.startswith("mcp:"):
            handler = self._mcp_tools.get(parsed.tool_id)
            if handler is None:
                raise RuntimeBlockedError(
                    f"MCP tool {parsed.tool_id} is not registered",
                    code="tool_not_registered",
                )
            result = self._invoke_registered_tool(parsed.tool_id, handler, parsed.arguments)
        elif parsed.tool_id == "attachment:read":
            if set(parsed.arguments) != {"ref"}:
                raise RuntimeBlockedError(
                    "Attachment tool accepts only a declared attachment reference",
                    code="invalid_attachment_reference",
                )
            reference = str(parsed.arguments["ref"])
            if reference not in manifest.attachment_refs or self._attachment_resolver is None:
                raise RuntimeBlockedError(
                    "attachment reference is not declared or resolver is unavailable",
                    code="invalid_attachment_reference",
                )
            result = self._invoke_registered_tool(
                parsed.tool_id,
                lambda _arguments: self._attachment_resolver(reference),
                {},
            )
        elif parsed.tool_id == "web:controlled":
            if self._contains_arbitrary_url(parsed.arguments):
                raise RuntimeBlockedError(
                    "Controlled web tools reject arbitrary URL arguments",
                    code="arbitrary_url_forbidden",
                )
            policy_id = str(parsed.arguments.get("policy_id") or "")
            policy = self._controlled_web_policies.get(policy_id)
            if policy is None:
                raise RuntimeBlockedError(
                    "Controlled web policy is not registered",
                    code="web_policy_not_registered",
                )
            result = self._invoke_registered_tool(
                f"web:controlled:{policy_id}",
                policy,
                {key: value for key, value in parsed.arguments.items() if key != "policy_id"},
            )
        else:
            raise RuntimeBlockedError(
                f"Tool {parsed.tool_id} is not registered", code="tool_not_registered"
            )
        try:
            validate_safe_output(result)
        except ValueError as exc:
            raise RuntimeBlockedError(
                "Tool output failed the safety boundary", code="unsafe_tool_output"
            ) from exc
        try:
            serialized = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            raise RuntimeFailedError(
                "Tool output is not JSON serializable", code="invalid_tool_output"
            ) from exc
        if len(serialized) > 64_000:
            raise RuntimeBlockedError(
                "Tool output exceeds size limit", code="tool_output_too_large"
            )
        return result

    @staticmethod
    def _contains_arbitrary_url(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                "url" in str(key).lower()
                or AuthorizedResearchToolDispatcher._contains_arbitrary_url(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(
                AuthorizedResearchToolDispatcher._contains_arbitrary_url(item) for item in value
            )
        return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))

    @staticmethod
    def _invoke_registered_tool(
        tool_id: str,
        handler: Callable[[dict[str, Any]], Any],
        arguments: dict[str, Any],
    ) -> Any:
        try:
            return handler(dict(arguments))
        except (RuntimeBlockedError, RuntimeFailedError):
            raise
        except Exception as exc:
            logger.exception(
                "authorized research tool invocation failed",
                tool_id=tool_id,
                error_type=type(exc).__name__,
            )
            raise RuntimeFailedError(
                f"Tool {tool_id} execution failed", code="tool_execution_failed"
            ) from exc


class ProductionResearchExecutionAdapters:
    """Production adapters for local DSH and configured model-backed Skills/Agents.

    Calls are synchronous by contract: the external HTTP/model client must enforce the
    supplied deadline before performing remote side effects. The service never starts a
    background thread whose work can outlive a rejected request.
    """

    def __init__(
        self,
        *,
        model_gateway=None,
        http_client: httpx.Client | None = None,
        tool_dispatcher: AuthorizedResearchToolDispatcher | None = None,
        cost_estimator: Callable[[Any], float] | None = None,
    ) -> None:
        self._model_gateway = model_gateway
        self._http_client = http_client
        self._tool_dispatcher = tool_dispatcher
        self._cost_estimator = cost_estimator or self._estimate_configured_cost

    @property
    def authorized_tool_ids(self) -> frozenset[str]:
        if self._tool_dispatcher is None:
            return frozenset()
        return self._tool_dispatcher.authorized_tool_ids

    def invoke_provider(
        self,
        provider: RuntimeProvider,
        payload: dict[str, Any],
        request_id: str,
    ) -> ProviderExecutionResult:
        if provider.provider_type != "dsh":
            raise ValueError("production provider adapter only accepts DSH")
        endpoint = self._resolve_local_dsh_endpoint(provider)
        request_hash = stable_runtime_request_hash(payload)
        timeout_seconds = float(os.environ.get("ALPHAFOUNDRY_DSH_TIMEOUT_SECONDS", "30"))
        if timeout_seconds <= 0:
            raise RuntimeBlockedError("DSH timeout must be positive", code="blocked_runtime")
        request_body = {
            "request_id": request_id,
            "run_id": str(payload["run_id"]),
            "request_hash": request_hash,
            "deadline_at": datetime.now(UTC).timestamp() + timeout_seconds,
            "input": payload,
        }
        client = self._http_client or httpx.Client()
        close_client = self._http_client is None
        try:
            response = client.post(endpoint, json=request_body, timeout=timeout_seconds)
            response.raise_for_status()
            result = ProviderExecutionResult.model_validate(response.json())
        except httpx.TimeoutException as exc:
            raise RuntimeUnavailableError(
                "DSH invocation timed out", code="runtime_timeout"
            ) from exc
        except httpx.ConnectError as exc:
            raise RuntimeUnavailableError(
                "DSH sidecar is unavailable", code="runtime_unavailable"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeUnavailableError(
                "DSH sidecar is unavailable", code="runtime_unavailable"
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {502, 503, 504}:
                raise RuntimeUnavailableError(
                    "DSH sidecar is unavailable", code="runtime_unavailable"
                ) from exc
            raise RuntimeFailedError("DSH returned an HTTP error", code="dsh_http_error") from exc
        except (ValueError, KeyError) as exc:
            raise RuntimeFailedError(
                "DSH returned an invalid typed result", code="invalid_provider_response"
            ) from exc
        finally:
            if close_client:
                client.close()
        if (
            result.provider_id != provider.provider_id
            or result.request_id != request_id
            or result.run_id != payload["run_id"]
            or result.request_hash != request_hash
        ):
            raise RuntimeBlockedError(
                "DSH response correlation mismatch", code="provider_correlation_mismatch"
            )
        return result

    def invoke_skill(
        self,
        manifest: SkillManifest,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillInvocationResult:
        gateway = self._get_model_gateway()
        messages = [
            {"role": "system", "content": manifest.prompt_template},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        started = time.monotonic()
        tokens_used = 0
        cost_used = 0.0
        for _round in range(3):
            remaining = float(context["remaining_seconds"]) - (time.monotonic() - started)
            if remaining <= 0:
                raise RuntimeBlockedError("Skill deadline exceeded", code="deadline_exceeded")
            remaining_tokens, _remaining_cost = self._remaining_invocation_budget(
                tokens_used,
                cost_used,
                context,
            )
            response = gateway.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=remaining_tokens,
                task="reasoning",
                timeout=remaining,
            )
            output = self._parse_gateway_json(response, label="Skill")
            usage = self._usage(response)
            tokens_used += usage.tokens_used
            cost_used += usage.cost_used
            self._enforce_invocation_budget(tokens_used, cost_used, context)
            tool_requests = output.get("tool_requests")
            if tool_requests is None:
                return SkillInvocationResult(
                    output=output,
                    tokens_used=tokens_used,
                    cost_used=cost_used,
                )
            if set(output) != {"tool_requests"} or not isinstance(tool_requests, list):
                raise RuntimeBlockedError(
                    "Skill tool envelope is invalid", code="invalid_tool_request"
                )
            if not tool_requests or len(tool_requests) > 8:
                raise RuntimeBlockedError(
                    "Skill tool request count is out of bounds", code="invalid_tool_request"
                )
            if self._tool_dispatcher is None:
                raise RuntimeBlockedError(
                    "Skill requested tools but no dispatcher is registered",
                    code="tool_dispatcher_unavailable",
                )
            results = []
            for item in tool_requests:
                self._remaining_invocation_budget(tokens_used, cost_used, context)
                result = self._tool_dispatcher.dispatch(manifest, item)
                tool_id = str(item.get("tool_id") if isinstance(item, dict) else "")
                results.append({"tool_id": tool_id, "result": result})
            messages.extend(
                [
                    {"role": "assistant", "content": json.dumps(output, ensure_ascii=False)},
                    {
                        "role": "user",
                        "content": json.dumps({"tool_results": results}, ensure_ascii=False),
                    },
                ]
            )
        raise RuntimeBlockedError("Skill tool round limit exceeded", code="tool_round_limit")

    def invoke_agent(self, assignment):
        from services.agent_team_service import AgentWorkerResult

        gateway = self._get_model_gateway()
        response = gateway.chat(
            messages=[
                {
                    "role": "system",
                    "content": f"You are the bounded research worker role: {assignment.role}.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": assignment.task,
                            "blackboard_snapshot": [
                                entry.model_dump(mode="json")
                                for entry in assignment.blackboard_snapshot
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=assignment.reserve_tokens,
            task="reasoning",
            timeout=assignment.remaining_seconds,
        )
        payload = self._parse_gateway_json(response, label="Agent")
        usage = self._usage(response)
        if assignment.reserve_tokens is not None and usage.tokens_used > assignment.reserve_tokens:
            raise RuntimeBlockedError("Agent token budget exceeded", code="budget_exhausted")
        if assignment.reserve_cost is not None and usage.cost_used > assignment.reserve_cost:
            raise RuntimeBlockedError("Agent cost budget exceeded", code="budget_exhausted")
        return AgentWorkerResult(
            payload=payload,
            tokens_used=usage.tokens_used,
            cost_used=usage.cost_used,
        )

    def invoke_supervisor(self, context):
        from services.agent_team_service import AgentSupervisorResult

        gateway = self._get_model_gateway()
        response = gateway.chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are a bounded Supervisor. Return strict JSON with action and assignments.",
                },
                {"role": "user", "content": context.model_dump_json()},
            ],
            temperature=0.1,
            max_tokens=context.reserve_tokens,
            task="reasoning",
            timeout=context.remaining_seconds,
        )
        output = self._parse_gateway_json(response, label="Supervisor")
        usage = self._usage(response)
        try:
            return AgentSupervisorResult.model_validate(
                {**output, "tokens_used": usage.tokens_used, "cost_used": usage.cost_used}
            )
        except ValueError as exc:
            raise RuntimeFailedError(
                "Supervisor returned an invalid decision",
                code="invalid_supervisor_decision",
            ) from exc

    def _get_model_gateway(self):
        if self._model_gateway is None:
            from core.model_gateway import ModelGatewayImpl

            self._model_gateway = ModelGatewayImpl()
        return self._model_gateway

    def _parse_gateway_json(self, response: Any, *, label: str) -> dict[str, Any]:
        content = getattr(response, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeFailedError(
                f"{label} model gateway returned empty content", code="model_gateway_failed"
            )
        normalized = content.strip()
        if normalized.lower().startswith("error:") or "api not available" in normalized.lower():
            raise RuntimeFailedError(
                f"{label} model gateway returned an error", code="model_gateway_failed"
            )
        try:
            output = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise RuntimeFailedError(
                f"{label} model gateway output must be JSON",
                code="invalid_model_response",
            ) from exc
        if not isinstance(output, dict):
            raise RuntimeFailedError(
                f"{label} model gateway output must be an object",
                code="invalid_model_response",
            )
        try:
            validate_safe_output(output)
        except ValueError as exc:
            raise RuntimeBlockedError(
                f"{label} output failed the safety boundary",
                code="unsafe_model_output",
            ) from exc
        return output

    def _usage(self, response: Any) -> InvocationUsage:
        try:
            tokens = int(response.tokens_used)
        except (TypeError, ValueError, AttributeError) as exc:
            raise RuntimeFailedError(
                "Model gateway omitted token usage", code="missing_model_usage"
            ) from exc
        if tokens <= 0:
            raise RuntimeFailedError(
                "Model gateway returned missing token usage", code="missing_model_usage"
            )
        try:
            cost = float(self._cost_estimator(response))
        except RuntimeFailedError:
            raise
        except Exception as exc:
            raise RuntimeFailedError(
                "Model cost estimation failed", code="invalid_model_cost_config"
            ) from exc
        if cost < 0 or (tokens > 0 and cost <= 0):
            raise RuntimeFailedError(
                "Model gateway cost estimate is missing", code="missing_model_cost"
            )
        return InvocationUsage(tokens_used=tokens, cost_used=cost)

    @staticmethod
    def _estimate_configured_cost(response: Any) -> float:
        explicit = getattr(response, "cost_used", None)
        if explicit is not None:
            return float(explicit)
        try:
            rate = float(os.environ.get("ALPHAFOUNDRY_MODEL_COST_PER_1K_TOKENS", "0.01"))
        except ValueError as exc:
            raise RuntimeFailedError(
                "Model cost configuration is invalid", code="invalid_model_cost_config"
            ) from exc
        if rate <= 0:
            raise RuntimeFailedError(
                "Model cost configuration must be positive", code="invalid_model_cost_config"
            )
        return int(getattr(response, "tokens_used", 0)) * rate / 1000

    @staticmethod
    def _enforce_invocation_budget(
        tokens_used: int,
        cost_used: float,
        context: dict[str, Any],
    ) -> None:
        if tokens_used > int(context["reserved_tokens"]) or cost_used > float(
            context["reserved_cost"]
        ):
            raise RuntimeBlockedError(
                "Skill invocation exceeded reserved budget", code="budget_exhausted"
            )

    @staticmethod
    def _remaining_invocation_budget(
        tokens_used: int,
        cost_used: float,
        context: dict[str, Any],
    ) -> tuple[int, float]:
        """Fail before starting another external model or tool side effect."""

        remaining_tokens = int(context["reserved_tokens"]) - tokens_used
        remaining_cost = float(context["reserved_cost"]) - cost_used
        if remaining_tokens < 1 or remaining_cost <= 0:
            raise RuntimeBlockedError(
                "Skill invocation budget is exhausted",
                code="budget_exhausted",
            )
        return remaining_tokens, remaining_cost

    @staticmethod
    def _resolve_local_dsh_endpoint(provider: RuntimeProvider) -> str:
        if not provider.config_ref or not provider.config_ref.startswith("env:"):
            raise RuntimeUnavailableError(
                "DSH is unavailable until a local endpoint reference is configured",
                code="runtime_unavailable",
            )
        variable = provider.config_ref.removeprefix("env:")
        endpoint = os.environ.get(variable, "")
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeBlockedError(
                "DSH endpoint must resolve to an authorized local HTTP sidecar",
                code="unauthorized_provider_endpoint",
            )
        return endpoint


def stable_runtime_request_hash(value: Any) -> str:
    """Canonical request digest shared by dispatch and callback correlation."""

    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class RuntimeProviderService:
    """Route FinGPT and Claw without treating DSH state as authoritative."""

    def __init__(
        self,
        *,
        providers: list[RuntimeProvider] | None = None,
        repository: Any | None = None,
    ) -> None:
        self._providers = providers
        self._repository = repository

    def list_providers(self) -> list[RuntimeProvider]:
        if self._repository is not None:
            merged = {item.provider_id: item for item in self._providers or []}
            merged.update(
                {item.provider_id: item for item in self._repository.list_runtime_providers()}
            )
            return [merged[key] for key in sorted(merged)]
        return list(self._providers or [])

    def save_provider(self, provider: RuntimeProvider) -> RuntimeProvider:
        if self._repository is None:
            raise RuntimeError("runtime provider repository is required")
        return self._repository.save_runtime_provider(provider)

    def route(
        self,
        mode: Literal["fingpt", "claw"] | str,
        required_capabilities: Collection[str],
    ) -> RuntimeProvider:
        required = set(required_capabilities)
        if mode == "claw":
            required.add("agent_team")
        healthy = [
            provider
            for provider in self.list_providers()
            if provider.status is RuntimeProviderStatus.HEALTHY
            and required.issubset(provider.capabilities)
        ]
        if mode == "fingpt" or mode == "claw":
            healthy.sort(key=lambda item: (item.provider_type != "dsh", item.provider_id))
        else:
            raise ValueError(f"unsupported research mode: {mode}")
        if not healthy:
            raise RuntimeBlockedError(
                f"No healthy runtime provides {sorted(required)}",
                code="blocked_runtime",
            )
        return healthy[0]

    def execute(
        self,
        mode: Literal["fingpt", "claw"] | str,
        required_capabilities: Collection[str],
        invoke: Callable[[RuntimeProvider], T],
        *,
        before_invoke: Callable[[RuntimeProvider], None] | None = None,
    ) -> RuntimeExecutionResult:
        selected = self.route(mode, required_capabilities)
        try:
            if before_invoke is not None:
                before_invoke(selected)
            return self._normalize_execution(selected.provider_id, invoke(selected))
        except (RuntimeBlockedError, RuntimeFailedError):
            raise
        except Exception as exc:
            logger.warning(
                "research runtime invocation failed",
                provider_id=selected.provider_id,
                mode=mode,
                error_type=type(exc).__name__,
            )
            fallback_allowed = isinstance(exc, (TimeoutError, RuntimeUnavailableError))
            if not fallback_allowed:
                raise RuntimeFailedError(
                    "Research runtime failed without an allowed fallback",
                    code=getattr(exc, "code", "provider_invocation_failed"),
                ) from exc
            if mode != "fingpt" or selected.provider_type != "dsh":
                raise RuntimeBlockedError(
                    "Research runtime failed without an allowed semantic fallback",
                    code=getattr(exc, "code", "blocked_runtime"),
                ) from exc
            fallback = next(
                (
                    item
                    for item in self.list_providers()
                    if item.provider_type == "langgraph"
                    and item.status is RuntimeProviderStatus.HEALTHY
                    and set(required_capabilities).issubset(item.capabilities)
                ),
                None,
            )
            if fallback is None:
                raise RuntimeBlockedError(
                    "DSH failed and LangGraph fallback is unavailable",
                    code="blocked_runtime",
                ) from exc
            logger.info(
                "research runtime fallback selected",
                fallback_from=selected.provider_id,
                provider_id=fallback.provider_id,
                mode=mode,
            )
            if before_invoke is not None:
                before_invoke(fallback)
            normalized = self._normalize_execution(fallback.provider_id, invoke(fallback))
            return RuntimeExecutionResult(
                provider_id=normalized.provider_id,
                output=normalized.output,
                fallback_from=selected.provider_id,
                provider_result_id=normalized.provider_result_id,
                terminal_status=normalized.terminal_status,
            )

    def compile_skill(
        self,
        manifest: SkillManifest,
        *,
        authorized_tool_ids: Collection[str],
    ) -> SkillManifest:
        """Revalidate every execution against the platform-owned registry."""

        manifest.validate_tool_registry(authorized_tool_ids)
        missing_executable_tools = set(manifest.allowed_tools).difference(authorized_tool_ids)
        if missing_executable_tools:
            raise ValueError(
                "allowed_tools are authorized declaratively but have no executable platform "
                f"registration: {sorted(missing_executable_tools)}"
            )
        logger.info(
            "research skill registry validated",
            skill_key=manifest.skill_key,
            version=manifest.version,
            tool_count=len(manifest.allowed_tools),
        )
        return manifest

    def save_skill(
        self,
        manifest: SkillManifest,
        *,
        authorized_tool_ids: Collection[str],
        now,
    ) -> SkillManifest:
        validated = self.compile_skill(manifest, authorized_tool_ids=authorized_tool_ids)
        if self._repository is None:
            raise RuntimeError("skill repository is required")
        return self._repository.save_skill(validated, now=now)

    def list_skills(self) -> list[SkillManifest]:
        if self._repository is None:
            return []
        return self._repository.list_skills()

    def get_skill(self, skill_key: str) -> SkillManifest:
        if self._repository is None:
            raise KeyError(skill_key)
        return self._repository.get_skill(skill_key)

    def execute_skill(
        self,
        manifest: SkillManifest,
        input_payload: dict[str, Any],
        invoke: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        *,
        authorized_tool_ids: Collection[str],
        deadline_seconds: float = 30,
        reserve_tokens: int = 1,
        remaining_tokens: int = 1_000_000,
        reserve_cost: float = 0,
        remaining_cost: float = 10_000,
        usage_callback: Callable[[InvocationUsage], None] | None = None,
    ) -> dict[str, Any]:
        """Validate authorization and both schemas around every Skill invocation."""

        if manifest.status != "enabled":
            raise ValueError("Skill must be enabled before execution")
        if deadline_seconds <= 0:
            raise ValueError("Skill deadline must be positive")
        if reserve_tokens < 1 or reserve_tokens > remaining_tokens:
            raise ValueError("Skill token reservation exceeds remaining budget")
        if reserve_cost < 0 or reserve_cost > remaining_cost:
            raise ValueError("Skill cost reservation exceeds remaining budget")
        self.compile_skill(manifest, authorized_tool_ids=authorized_tool_ids)
        _validate_json_schema(input_payload, manifest.input_schema, label="input_schema")
        context = {
            "reserved_tokens": reserve_tokens,
            "reserved_cost": reserve_cost,
            "remaining_seconds": deadline_seconds,
        }
        raw_output = invoke(input_payload, context)
        if isinstance(raw_output, SkillInvocationResult):
            output = raw_output.output
            usage = InvocationUsage(
                tokens_used=raw_output.tokens_used,
                cost_used=raw_output.cost_used,
            )
        else:
            output = raw_output
            usage = InvocationUsage(tokens_used=reserve_tokens, cost_used=reserve_cost)
        if usage.tokens_used > reserve_tokens or usage.tokens_used > remaining_tokens:
            raise RuntimeBlockedError("Skill token budget exceeded", code="budget_exhausted")
        if usage.cost_used > reserve_cost or usage.cost_used > remaining_cost:
            raise RuntimeBlockedError("Skill cost budget exceeded", code="budget_exhausted")
        _validate_json_schema(output, manifest.output_schema, label="output_schema")
        validate_safe_output(output)
        if usage_callback is not None:
            usage_callback(usage)
        return output

    def accept_provider_result(
        self,
        result: ProviderExecutionResult,
        *,
        request_hash: str,
    ) -> ProviderExecutionResult:
        """Persist a DSH terminal callback once; altered replays are conflicts."""

        if self._repository is None:
            raise RuntimeError("runtime provider repository is required")
        provider = next(
            (item for item in self.list_providers() if item.provider_id == result.provider_id),
            None,
        )
        if provider is None or provider.provider_type != "dsh":
            raise ValueError("provider result references an unknown or non-DSH provider")
        validate_safe_output(result.output)
        return self._repository.accept_provider_result(result, request_hash=request_hash)

    @staticmethod
    def _normalize_execution(provider_id: str, value: Any) -> RuntimeExecutionResult:
        if isinstance(value, ProviderExecutionResult):
            if value.provider_id != provider_id:
                raise RuntimeBlockedError(
                    "Provider result identity mismatch", code="blocked_runtime"
                )
            if value.terminal_status is ProviderTerminalStatus.FAILED:
                raise RuntimeFailedError(
                    "Provider execution failed",
                    code=value.error_code or "provider_failed",
                )
            if value.terminal_status is ProviderTerminalStatus.BLOCKED:
                raise RuntimeBlockedError(
                    f"Provider terminated with {value.terminal_status.value}",
                    code=value.error_code or "blocked_runtime",
                )
            try:
                validate_safe_output(value.output)
            except ValueError as exc:
                raise RuntimeBlockedError(
                    "Provider output failed the safety boundary",
                    code="unsafe_provider_output",
                ) from exc
            return RuntimeExecutionResult(
                provider_id=provider_id,
                provider_result_id=value.provider_result_id,
                terminal_status=value.terminal_status,
                output=value.output,
            )
        try:
            validate_safe_output(value)
        except ValueError as exc:
            raise RuntimeBlockedError(
                "Provider output failed the safety boundary",
                code="unsafe_provider_output",
            ) from exc
        return RuntimeExecutionResult(provider_id=provider_id, output=value)


def _validate_json_schema(
    value: Any,
    schema: dict[str, Any],
    *,
    label: str,
    depth: int = 0,
) -> None:
    """Validate the safe JSON-Schema subset supported by declarative Skills."""

    if depth > 16:
        raise ValueError(f"{label} exceeds maximum schema depth")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{label} value is not in enum")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{label} value does not match const")

    expected = schema.get("type")
    type_map = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }
    if expected in type_map and not isinstance(value, type_map[expected]):
        raise ValueError(f"{label} type mismatch: expected {expected}")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            raise ValueError(f"{label} is shorter than minLength")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            raise ValueError(f"{label} is longer than maxLength")
        if "pattern" in schema:
            pattern = str(schema["pattern"])
            if len(pattern) > 256:
                raise ValueError(f"{label} pattern is too long")
            try:
                matched = re.search(pattern, value)
            except re.error as exc:
                raise ValueError(f"{label} has invalid pattern") from exc
            if matched is None:
                raise ValueError(f"{label} does not match pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{label} is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{label} is above maximum")
    if expected == "object" and isinstance(value, dict):
        required = set(schema.get("required") or [])
        missing = required.difference(value)
        if missing:
            raise ValueError(f"{label} missing required fields: {sorted(missing)}")
        properties = dict(schema.get("properties") or {})
        if schema.get("additionalProperties") is False:
            unexpected = set(value).difference(properties)
            if unexpected:
                raise ValueError(f"{label} has unexpected fields: {sorted(unexpected)}")
        for key, child_schema in properties.items():
            if key in value:
                _validate_json_schema(
                    value[key], child_schema, label=f"{label}.{key}", depth=depth + 1
                )
    if expected == "array" and isinstance(value, list) and isinstance(schema.get("items"), dict):
        if len(value) < int(schema.get("minItems", 0)):
            raise ValueError(f"{label} has fewer than minItems")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            raise ValueError(f"{label} has more than maxItems")
        for index, item in enumerate(value):
            _validate_json_schema(item, schema["items"], label=f"{label}[{index}]", depth=depth + 1)


_SENSITIVE_KEY = re.compile(r"(?:api[_-]?key|authorization|password|secret|token)", re.IGNORECASE)
_SENSITIVE_VALUE = re.compile(r"(?:Bearer\s+[A-Za-z0-9._-]{8,}|sk-[A-Za-z0-9]{8,})", re.IGNORECASE)


def _reject_sensitive_output(value: Any, *, path: str = "output") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _SENSITIVE_KEY.search(str(key)):
                raise ValueError(f"sensitive output field rejected at {path}")
            _reject_sensitive_output(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sensitive_output(child, path=f"{path}[{index}]")
    elif isinstance(value, str) and _SENSITIVE_VALUE.search(value):
        raise ValueError(f"sensitive output value rejected at {path}")


def validate_safe_output(value: Any) -> None:
    """Reject secrets before Agent, Skill, or provider output crosses its boundary."""

    _reject_sensitive_output(value)
