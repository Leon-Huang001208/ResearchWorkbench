"""Safe, read-only local integration discovery for the Research Web process."""

from .manager import DetectionEnvironment, LocalIntegrationError, LocalIntegrationManager

__all__ = ["DetectionEnvironment", "LocalIntegrationError", "LocalIntegrationManager"]
