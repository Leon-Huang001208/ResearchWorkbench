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

    trusted_mcp = mcp_registry or get_default_research_mcp_registry()
    return AuthorizedResearchToolDispatcher(
        internal_tools={"internal:asset_snapshot": asset_snapshot},
        mcp_tools=trusted_mcp.snapshot(),
    )
