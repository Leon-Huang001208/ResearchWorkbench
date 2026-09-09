"""Application service for v2 runtime-neutral workflow runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.contracts.runtime import (
    AlphaEvent,
    CapabilityKind,
    RuntimeCapabilities,
    RuntimeDescriptor,
    WorkflowRunResult,
)
from core.observability import get_logger
from data_layer.repositories.runtime_workflow_repository import (
    RuntimeWorkflowRepository,
)
from runtimes.dsh.adapter import DSHAdapter
from services.daily_market_commentary_spec import (
    DailyMarketCommentarySpec,
    load_daily_market_commentary_spec,
)
from services.market_commentary_workflow import (
    DailyMarketCommentaryWorkflow,
    InMemoryMarketCommentaryTools,
    LiveAkShareMarketCommentaryTools,
    MarketCommentarySkillRuntime,
)
from services.runtime_registry import RuntimeRegistry

logger = get_logger(__name__)


class DailyMarketCommentaryRequest(BaseModel):
    as_of: datetime
    question: str = Field(min_length=1)
    runtime_id: str = "dsh-local"
    market_inputs: dict[str, Any] = Field(default_factory=dict)
    workflow_overrides: dict[str, Any] = Field(default_factory=dict)


class RuntimeWorkflowService:
    def __init__(
        self,
        repository: RuntimeWorkflowRepository,
        registry: RuntimeRegistry | None = None,
        runtime_adapters: dict[str, MarketCommentarySkillRuntime] | None = None,
    ):
        self._repository = repository
        self._registry = registry or default_runtime_registry()
        self._runtime_adapters = (
            runtime_adapters
            if runtime_adapters is not None
            else default_runtime_adapters(self._registry)
        )

    def create_daily_market_commentary(
        self, request: DailyMarketCommentaryRequest
    ) -> dict[str, Any]:
        runtime = self._require_runtime(request.runtime_id)
        config = configured_spec(request.workflow_overrides)
        workflow = DailyMarketCommentaryWorkflow(
            tools=tools_from_inputs(request.market_inputs), runtime=runtime, spec=config
        ).build_spec()
        run_id = f"workflow_{uuid4().hex}"
        self._repository.create_run(
            run_id=run_id,
            workflow=workflow,
            runtime_id=request.runtime_id,
            request_payload=request.model_dump(mode="json"),
        )
        logger.info(
            "runtime workflow created",
            run_id=run_id,
            workflow_id=workflow.workflow_id,
            runtime_id=request.runtime_id,
        )
        return {"run_id": run_id, "status": "draft", "workflow": workflow}

    def execute(self, run_id: str) -> WorkflowRunResult:
        row = self._repository.get_run_or_raise(run_id)
        if row.status == "cancelled":
            raise ValueError("已取消的工作流不能执行")
        request = DailyMarketCommentaryRequest.model_validate(row.request_payload)
        runtime = self._require_runtime(str(row.runtime_id))
        workflow = DailyMarketCommentaryWorkflow(
            tools=tools_from_inputs(request.market_inputs),
            runtime=runtime,
            spec=configured_spec(request.workflow_overrides),
        )
        self._repository.update_status(run_id, "running")
        result = workflow.run(run_id=run_id, as_of=request.as_of, question=request.question)
        self._repository.append_events(result.events)
        self._repository.replace_evidence(run_id, result.evidence)
        self._repository.append_result_artifact(result)
        self._repository.update_status(run_id, result.status, error_message=result.error_message)
        logger.info("runtime workflow executed", run_id=run_id, status=result.status)
        return result

    def cancel(self, run_id: str) -> None:
        self._repository.get_run_or_raise(run_id)
        self._repository.update_status(run_id, "cancelled")
        logger.info("runtime workflow cancelled", run_id=run_id)

    def resume(self, run_id: str) -> WorkflowRunResult:
        row = self._repository.get_run_or_raise(run_id)
        if row.status not in {"blocked", "failed"}:
            raise ValueError("只有被阻断或失败的工作流可以恢复")
        return self.execute(run_id)

    def events(self, run_id: str, after_sequence: int = -1):
        self._repository.get_run_or_raise(run_id)
        return self._repository.list_events(run_id, after_sequence=after_sequence)

    def get(self, run_id: str):
        return self._repository.get_run_or_raise(run_id)

    def capabilities(self) -> list[RuntimeDescriptor]:
        return self._registry.list()

    def run_native_tool(
        self,
        *,
        run_id: str,
        capability_id: str,
        execution_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Execute one allowlisted deterministic Tool against persisted run inputs."""
        row = self._repository.get_run_or_raise(run_id)
        request = DailyMarketCommentaryRequest.model_validate(row.request_payload)
        tools = tools_from_inputs(request.market_inputs)
        handlers = {
            "market.snapshot": tools.get_market_snapshot,
            "market.breadth": tools.get_market_breadth,
            "market.industry_returns": tools.get_industry_returns,
            "market.leaders": tools.get_market_leaders,
            "news.search": tools.search_news,
            "market.turnover": tools.get_market_turnover,
            "market.theme_indices": tools.get_theme_indices,
            "market.etf_index_signals": tools.get_etf_index_signals,
        }
        handler = handlers.get(capability_id)
        if handler is None:
            raise ValueError(f"Tool {capability_id} is not approved for daily market commentary")
        value = handler()
        self._repository.append_events(
            [
                AlphaEvent(
                    event_id=f"runtime_tool_{uuid4().hex}",
                    event_type="RuntimeToolCompleted",
                    run_id=run_id,
                    sequence=0,
                    payload={
                        "capability_id": capability_id,
                        "execution_id": execution_id,
                        "correlation_id": correlation_id,
                    },
                )
            ]
        )
        logger.info(
            "runtime native tool executed",
            run_id=run_id,
            capability_id=capability_id,
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
        return {"value": value}

    def _require_runtime(self, runtime_id: str) -> MarketCommentarySkillRuntime:
        self._registry.require(runtime_id, kind=CapabilityKind.SKILL)
        runtime = self._runtime_adapters.get(runtime_id)
        if runtime is None:
            raise RuntimeError(f"Runtime {runtime_id} is not configured for Skill execution")
        return runtime


def default_runtime_registry() -> RuntimeRegistry:
    registry = RuntimeRegistry()
    bridge_enabled = (
        DSHAdapter.from_environment(
            descriptor=RuntimeDescriptor(
                runtime_id="dsh-local",
                display_name="DSH local adapter",
                protocol_version="alphafoundry.io/v1",
                capabilities=RuntimeCapabilities(),
            )
        )
        is not None
    )
    dsh_descriptor = RuntimeDescriptor(
        runtime_id="dsh-local",
        display_name="DSH local adapter",
        protocol_version="alphafoundry.io/v1",
        capabilities=RuntimeCapabilities(
            tool_calling=True,
            skills=bridge_enabled,
            workflow=False,
            streaming=True,
            cancellation=True,
            resume=True,
        ),
    )
    registry.register(dsh_descriptor)
    registry.register(
        RuntimeDescriptor(
            runtime_id="codex-placeholder",
            display_name="Codex adapter placeholder",
            protocol_version="alphafoundry.io/v1",
            capabilities=RuntimeCapabilities(),
        )
    )
    registry.register(
        RuntimeDescriptor(
            runtime_id="claude-placeholder",
            display_name="Claude Code adapter placeholder",
            protocol_version="alphafoundry.io/v1",
            capabilities=RuntimeCapabilities(),
        )
    )
    return registry


def default_runtime_adapters(
    registry: RuntimeRegistry,
) -> dict[str, MarketCommentarySkillRuntime]:
    """Load only explicitly configured real runtimes; never fall back to a fixture."""
    dsh_descriptor = registry.get("dsh-local")
    adapter = DSHAdapter.from_environment(descriptor=dsh_descriptor)
    return {adapter.descriptor.runtime_id: adapter} if adapter is not None else {}


def tools_from_inputs(inputs: dict[str, Any]):
    """Use supplied reproducible snapshots, otherwise use native live Tools."""
    if not inputs:
        return LiveAkShareMarketCommentaryTools()
    return InMemoryMarketCommentaryTools(
        snapshot=dict(inputs.get("snapshot") or {}),
        breadth=dict(inputs.get("breadth") or {}),
        industries=list(inputs.get("industries") or []),
        leaders=list(inputs.get("leaders") or []),
        news=list(inputs.get("news") or []),
        turnover=dict(inputs.get("turnover") or {}),
        themes=list(inputs.get("themes") or []),
        etf_signals=list(inputs.get("etf_index_signals") or []),
    )


def configured_spec(overrides: dict[str, Any]) -> DailyMarketCommentarySpec:
    """Apply request-scoped UI preview changes without changing the source-of-truth YAML."""
    spec = load_daily_market_commentary_spec()
    if not overrides:
        return spec
    merged = spec.model_dump(mode="json")
    merged.update(overrides)
    return DailyMarketCommentarySpec.model_validate(merged)
