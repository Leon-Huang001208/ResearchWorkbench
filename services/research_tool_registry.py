"""Trusted production wiring for bounded research tools and pre-registered MCP calls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.observability import get_logger
from services.runtime_provider_service import (
    AuthorizedResearchToolDispatcher,
    RuntimeBlockedError,
)

logger = get_logger(__name__)


class ResearchMCPHandlerRegistry:
    """Process-local callable registry populated only by trusted application startup code."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register(self, tool_id: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        if not tool_id.startswith("mcp:") or not tool_id.removeprefix("mcp:").strip():
            raise ValueError("MCP tool IDs must use a non-empty mcp: identifier")
        existing = self._handlers.get(tool_id)
        if existing is not None and existing is not handler:
            raise ValueError(f"MCP handler already registered for {tool_id}")
        self._handlers[tool_id] = handler
        logger.info("research MCP handler registered", tool_id=tool_id)

    def snapshot(self) -> dict[str, Callable[[dict[str, Any]], Any]]:
        return dict(self._handlers)


_default_mcp_registry = ResearchMCPHandlerRegistry()


def get_default_research_mcp_registry() -> ResearchMCPHandlerRegistry:
    return _default_mcp_registry


def record_datahub_tool_evidence(db, run_id, tool_id, arguments, result):
    """Persist platform-observed tool results in the scoped Run, never in fact tables."""
    if tool_id not in {"internal:data_catalog", "internal:data_query"}:
        return
    from datetime import UTC, datetime

    from core.contracts.research import ResearchArtifact
    from data_layer.repositories.datahub_repository import digest
    from data_layer.repositories.research_run_repository import ResearchRunRepository

    repository = ResearchRunRepository(db)
    repository.get_run_or_raise(run_id)
    identity = digest([run_id, tool_id, arguments, result])
    repository.append_artifact(
        ResearchArtifact(
            artifact_id="datahub-tool:" + identity,
            run_id=run_id,
            artifact_type="datahub_tool:" + identity,
            payload={"tool_id": tool_id, "arguments": arguments, "result": result},
            created_at=datetime.now(UTC),
        )
    )
    for row in result.get("records", []):
        if row["freshness_status"] not in {"fresh", "stale"}:
            continue
        evidence = datahub_evidence(row, result["dataset"])
        repository.append_evidence_input(run_id, evidence.model_dump(mode="json"))
    logger.info(
        "DataHub tool evidence retained",
        run_id=run_id,
        tool_id=tool_id,
        rows=len(result.get("records", [])),
    )


def datahub_evidence(row, dataset):
    """Convert a platform-read fact to an existing research evidence input."""
    import json

    from core.contracts.research import ResearchEvidenceInput

    summary = json.dumps(
        {
            "dataset": dataset,
            "as_of": row["as_of"],
            "freshness_status": row["freshness_status"],
            "payload": row["payload"],
            "units": row["units"],
        },
        ensure_ascii=False,
    )
    return ResearchEvidenceInput(
        evidence_id=row["evidence_ref"],
        source_ref=row["evidence_ref"],
        source_name="CJPY",
        source_tier="licensed",
        evidence_kind="financial",
        summary=summary,
        claim_text=summary,
        observed_at=row["observed_at"],
    )


def build_production_research_tool_dispatcher(
    db,
    *,
    mcp_registry: ResearchMCPHandlerRegistry | None = None,
) -> AuthorizedResearchToolDispatcher:
    """Build the request-scoped executable registry; declarations cannot add handlers."""

    from data_layer.repositories.asset_observation_repository import (
        AssetObservationRepository,
    )
    from services.asset_observation_service import (
        AssetNotFoundError,
        AssetObservationService,
    )

    asset_service = AssetObservationService(AssetObservationRepository(db))

    def asset_snapshot(arguments: dict[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"asset_id"}:
            raise RuntimeBlockedError(
                "asset_snapshot accepts only asset_id",
                code="invalid_tool_arguments",
            )
        asset_id = arguments.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise RuntimeBlockedError(
                "asset_snapshot requires a non-empty asset_id",
                code="invalid_tool_arguments",
            )
        try:
            return asset_service.get_asset_snapshot(asset_id.strip()).model_dump(mode="json")
        except AssetNotFoundError as exc:
            raise RuntimeBlockedError(
                "asset_snapshot asset is unavailable",
                code="tool_resource_not_found",
            ) from exc

    from core.contracts.datahub import DataHubQuery
    from services.datahub_service import DataHubService

    datahub = DataHubService(db)

    def data_catalog(arguments):
        if set(arguments) - {"dataset"} or (
            arguments.get("dataset") is not None and not isinstance(arguments["dataset"], str)
        ):
            raise RuntimeBlockedError("Invalid catalog arguments", code="invalid_tool_arguments")
        try:
            return datahub.catalog(arguments.get("dataset"))
        except ValueError as exc:
            raise RuntimeBlockedError("Unknown catalog", code="invalid_tool_arguments") from exc

    def data_query(arguments):
        try:
            query = DataHubQuery.model_validate(arguments)
        except ValueError as exc:
            raise RuntimeBlockedError("Invalid data query", code="invalid_tool_arguments") from exc
        return datahub.query_for_tools(query)

    trusted_mcp = mcp_registry or get_default_research_mcp_registry()
    return AuthorizedResearchToolDispatcher(
        internal_tools={
            "internal:asset_snapshot": asset_snapshot,
            "internal:data_catalog": data_catalog,
            "internal:data_query": data_query,
        },
        mcp_tools=trusted_mcp.snapshot(),
    )
