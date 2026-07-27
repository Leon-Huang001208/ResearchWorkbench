"""Retired legacy YAML report-template manager.

Report projects now own their assets through ``project.yaml``,
``report_config.yaml`` and ``prompt_templates.md``. This shim only fails
clearly for stale imports; it never scans, creates or reads YAML templates.
"""

from typing import Any

from core.observability import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """Closed compatibility boundary for the removed YAML template system."""

    def __init__(self, *_: Any, **__: Any) -> None:
        logger.warning("Legacy YAML TemplateManager is retired")

    @staticmethod
    def _retired() -> None:
        raise RuntimeError(
            "Legacy YAML templates are retired; use report projects with "
            "report_config.yaml and prompt_templates.md instead."
        )

    def list_templates(self) -> list[str]:
        """Expose no templates without touching the retired storage."""
        return []

    def __getattr__(self, _: str) -> Any:
        self._retired()
