"""Immutable, safe service facts for Research Web diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateFact:
    """Validated state-file facts retained only inside the service manager."""

    state: str
    pid: int | None
    signature: tuple[str, ...]
    issues: tuple[str, ...]
    started_at: float | None = None


@dataclass(frozen=True)
class ProcessFact:
    """Process and ownership facts without command or operating-system errors."""

    process: str
    ownership: str
    pid: int | None
    issues: tuple[str, ...]


@dataclass(frozen=True)
class ServiceProbe:
    """A complete service fact chain with a deliberately narrow projection."""

    role: str
    port: int
    state: str
    process: str
    ownership: str
    port_state: str
    protocol: str
    ready: bool
    pid: int | None
    issues: tuple[str, ...]

    def public(self, *, log: str | None = None) -> dict[str, object]:
        """Return safe facts; ``log`` is an opt-in status CLI compatibility field."""
        value: dict[str, object] = {
            "state": self.state,
            "process": self.process,
            "ownership": self.ownership,
            "port_state": self.port_state,
            "protocol": self.protocol,
            "ready": self.ready,
            "running": self.process == "alive" and self.ownership == "owned",
            "healthy": self.ready,
            "pid": self.pid if self.ownership == "owned" else None,
            "port": self.port,
            "issues": list(self.issues),
        }
        if log is not None:
            value["log"] = log
        return value
