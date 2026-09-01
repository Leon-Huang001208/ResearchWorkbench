"""Fail-closed evidence gate for retiring duplicated LSH capabilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.observability import get_logger

logger = get_logger(__name__)

_REQUIRED_EVIDENCE = (
    "data_migration",
    "parity_test",
    "regression",
    "call_count_zero",
    "archive_path",
    "stable_version_observed",
)
_REMOVABLE_DISPOSITION = "remove_after_gate"
_FROZEN_DISPOSITION = "freeze_read_only"


class CapabilityMapError(ValueError):
    """Raised when the versioned capability inventory is unsafe or malformed."""


@dataclass(frozen=True, slots=True)
class LegacyCapabilityDecision:
    """Stable removal decision returned to migration and release tooling."""

    capability_key: str
    allowed: bool
    action: str
    target: str | None
    archive_path: str | None
    missing_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Capability:
    key: str
    source: str
    target: str | None
    classification: str
    disposition: str
    status: str
    evidence: dict[str, bool | str | None]


class LegacyCapabilityGate:
    """Evaluate a versioned LSH capability map without mutating either system."""

    def __init__(self, capabilities: dict[str, _Capability]) -> None:
        self._capabilities = dict(capabilities)

    @classmethod
    def from_file(cls, path: Path | str) -> LegacyCapabilityGate:
        """Load the JSON-compatible YAML inventory and validate every entry."""

        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(
                "legacy capability map load failed",
                path=str(source),
                error_type=type(exc).__name__,
            )
            raise CapabilityMapError(
                "capability map must be readable JSON-compatible YAML"
            ) from exc

        try:
            if payload.get("version") != 1:
                raise CapabilityMapError("unsupported capability map version")
            raw_capabilities = payload["capabilities"]
            if not isinstance(raw_capabilities, list) or not raw_capabilities:
                raise CapabilityMapError("capabilities must be a non-empty list")
            capabilities: dict[str, _Capability] = {}
            for raw in raw_capabilities:
                capability = cls._parse_capability(raw)
                if capability.key in capabilities:
                    raise CapabilityMapError(f"duplicate capability key: {capability.key}")
                capabilities[capability.key] = capability
        except (KeyError, TypeError, AttributeError) as exc:
            raise CapabilityMapError("capability map is missing required fields") from exc
        return cls(capabilities)

    @staticmethod
    def _parse_capability(raw: Any) -> _Capability:
        if not isinstance(raw, dict):
            raise CapabilityMapError("each capability must be an object")
        required = {
            "key",
            "source",
            "target",
            "classification",
            "disposition",
            "status",
            "evidence",
        }
        if set(raw) != required:
            raise CapabilityMapError(f"capability fields must be exactly {sorted(required)}")
        if raw["disposition"] not in {_REMOVABLE_DISPOSITION, _FROZEN_DISPOSITION}:
            raise CapabilityMapError("unsupported capability disposition")
        evidence = raw["evidence"]
        if not isinstance(evidence, dict) or set(evidence) != set(_REQUIRED_EVIDENCE):
            raise CapabilityMapError("capability evidence fields are incomplete")
        for field in _REQUIRED_EVIDENCE:
            value = evidence[field]
            if field == "archive_path":
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    raise CapabilityMapError("archive_path must be null or a non-empty string")
            elif not isinstance(value, bool):
                raise CapabilityMapError(f"{field} must be boolean")
        string_fields = ("key", "source", "classification", "status")
        if any(
            not isinstance(raw[field], str) or not raw[field].strip() for field in string_fields
        ):
            raise CapabilityMapError("capability string fields cannot be empty")
        if raw["target"] is not None and (
            not isinstance(raw["target"], str) or not raw["target"].strip()
        ):
            raise CapabilityMapError("target must be null or a non-empty string")
        return _Capability(
            key=raw["key"],
            source=raw["source"],
            target=raw["target"],
            classification=raw["classification"],
            disposition=raw["disposition"],
            status=raw["status"],
            evidence=dict(evidence),
        )

    def evaluate(self, capability_key: str) -> LegacyCapabilityDecision:
        """Return a fail-closed removal decision for one inventoried capability."""

        try:
            capability = self._capabilities[capability_key]
        except KeyError:
            logger.warning("unknown legacy capability blocked", capability_key=capability_key)
            raise KeyError(f"unknown legacy capability: {capability_key}") from None

        archive_path = capability.evidence["archive_path"]
        if capability.disposition == _FROZEN_DISPOSITION:
            decision = LegacyCapabilityDecision(
                capability_key=capability.key,
                allowed=False,
                action="retain_read_only",
                target=capability.target,
                archive_path=archive_path if isinstance(archive_path, str) else None,
                missing_evidence=("policy_forbids_removal",),
            )
        else:
            missing = tuple(field for field in _REQUIRED_EVIDENCE if not capability.evidence[field])
            if capability.status not in {"archived", "removed"}:
                missing = (*missing, "archived_status")
            decision = LegacyCapabilityDecision(
                capability_key=capability.key,
                allowed=not missing,
                action="allow_removal" if not missing else "block_removal",
                target=capability.target,
                archive_path=archive_path if isinstance(archive_path, str) else None,
                missing_evidence=missing,
            )
        logger.info(
            "legacy capability gate evaluated",
            capability_key=capability.key,
            classification=capability.classification,
            source=capability.source,
            gate_status=decision.action,
            missing_evidence=list(decision.missing_evidence),
        )
        return decision
