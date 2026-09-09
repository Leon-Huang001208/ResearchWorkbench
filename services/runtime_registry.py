"""Capability catalog that refuses silent runtime fallback."""

from __future__ import annotations

from core.contracts.runtime import (
    CapabilityKind,
    RuntimeDescriptor,
    RuntimeUnavailableError,
)


class RuntimeRegistry:
    def __init__(self) -> None:
        self._descriptors: dict[str, RuntimeDescriptor] = {}

    def register(self, descriptor: RuntimeDescriptor) -> None:
        self._descriptors[descriptor.runtime_id] = descriptor

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
