"""Capability catalog that refuses silent runtime fallback."""

from __future__ import annotations

from core.contracts.runtime import (
    CapabilityKind,
    RuntimeDescriptor,
    RuntimeUnavailableError,
)
from core.observability import get_logger

logger = get_logger(__name__)


class RuntimeRegistry:
    def __init__(self) -> None:
        self._descriptors: dict[str, RuntimeDescriptor] = {}

    def register(self, descriptor: RuntimeDescriptor) -> None:
        try:
            runtime_id = descriptor.runtime_id
        except (AttributeError, TypeError) as exc:
            logger.exception(
                "runtime descriptor registration failed",
                error_type=type(exc).__name__,
            )
            raise ValueError("runtime descriptor is invalid") from exc
        self._descriptors[runtime_id] = descriptor
        logger.info("runtime descriptor registered", runtime_id=runtime_id)

    def list(self) -> list[RuntimeDescriptor]:
        return list(self._descriptors.values())

    def get(self, runtime_id: str) -> RuntimeDescriptor:
        """Return a registered descriptor without asserting a capability."""
        descriptor = self._descriptors.get(runtime_id)
        if descriptor is None:
            raise RuntimeUnavailableError(f"Runtime {runtime_id} is not registered")
        return descriptor

    def require(self, runtime_id: str, kind: CapabilityKind) -> RuntimeDescriptor:
        descriptor = self._descriptors.get(runtime_id)
        if descriptor is None:
            raise RuntimeUnavailableError(f"Runtime {runtime_id} is not registered")
        if not descriptor.capabilities.supports(kind):
            raise RuntimeUnavailableError(f"Runtime {runtime_id} does not support {kind.value}")
        return descriptor
