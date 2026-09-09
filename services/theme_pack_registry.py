"""Validated registry for declarative, permission-bounded Research Packs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from core.contracts.theme_research import PackLifecycle, ThemePackManifest
from core.observability import get_logger

logger = get_logger(__name__)

_BUILTIN_PLUGINS = {
    "builtin.identity.v1": ("validate", lambda value: value),
    "builtin.trim_string.v1": (
        "normalize",
        lambda value: value.strip() if isinstance(value, str) else value,
    ),
}
_LIFECYCLE_TRANSITIONS: dict[PackLifecycle, frozenset[PackLifecycle]] = {
    PackLifecycle.DISCOVERED: frozenset({PackLifecycle.VALIDATED}),
    PackLifecycle.VALIDATED: frozenset({PackLifecycle.ENABLED, PackLifecycle.DISABLED}),
    PackLifecycle.ENABLED: frozenset({PackLifecycle.DEGRADED, PackLifecycle.DISABLED}),
    PackLifecycle.DEGRADED: frozenset({PackLifecycle.ENABLED, PackLifecycle.DISABLED}),
    PackLifecycle.DISABLED: frozenset(),
}


class ThemePackValidationError(ValueError):
    """A manifest violates the Research Pack contract."""


class PluginSecurityError(ValueError):
    """A plugin requests or references a forbidden capability."""


class ThemePackRegistry:
    """Load manifests and execute only versioned, trusted built-in transforms."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self._manifests: dict[str, ThemePackManifest] = {}

    def discover(self) -> list[ThemePackManifest]:
        """Validate every first-party manifest in deterministic key order."""

        if self._manifests:
            return sorted(self._manifests.values(), key=lambda manifest: manifest.pack_key)
        if not self.root.exists():
            raise ThemePackValidationError("Research Pack root does not exist")
        manifests = [self.load(path) for path in sorted(self.root.glob("*/manifest.yaml"))]
        if not manifests:
            raise ThemePackValidationError("no Research Pack manifests discovered")
        return sorted(manifests, key=lambda manifest: manifest.pack_key)

    def load(self, path: Path) -> ThemePackManifest:
        """Parse a YAML manifest without allowing constructors or code execution."""

        manifest_path = Path(path).resolve()
        if not manifest_path.is_relative_to(self.root):
            raise ThemePackValidationError("manifest must remain inside the Pack root")
        try:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            logger.warning(
                "theme pack manifest read failed",
                path=str(manifest_path),
                error_type=type(exc).__name__,
            )
            raise ThemePackValidationError("manifest cannot be read safely") from exc
        if not isinstance(raw, dict):
            raise ThemePackValidationError("manifest root must be an object")
        if "plugin_permissions" in raw:
            raise ThemePackValidationError("forbidden permission declared; use trusted plugin IDs")
        try:
            manifest = ThemePackManifest.model_validate(raw)
        except ValidationError as exc:
            logger.info(
                "theme pack manifest rejected",
                path=str(manifest_path),
                error_count=exc.error_count(),
            )
            raise ThemePackValidationError("manifest validation failed") from exc
        for binding in manifest.plugins:
            builtin = _BUILTIN_PLUGINS.get(binding.plugin_id)
            if builtin is None or builtin[0] != binding.operation:
                raise ThemePackValidationError("manifest references an unknown trusted plugin ID")
        existing = self._manifests.get(manifest.pack_key)
        if existing is not None and existing.version != manifest.version:
            raise ThemePackValidationError("duplicate pack key has a conflicting version")
        self._manifests[manifest.pack_key] = manifest
        logger.info(
            "theme pack manifest validated",
            pack_key=manifest.pack_key,
            version=manifest.version,
            status=manifest.status.value,
        )
        return manifest

    def get(self, pack_key: str) -> ThemePackManifest:
        """Return one manifest, discovering the root on first use."""

        if not self._manifests:
            self.discover()
        try:
            return self._manifests[pack_key]
        except KeyError as exc:
            raise ThemePackValidationError("theme pack not found") from exc

    def transition(self, pack_key: str, target: PackLifecycle) -> ThemePackManifest:
        """Apply the documented lifecycle without implicit skips."""

        current = self.get(pack_key)
        if target not in _LIFECYCLE_TRANSITIONS[current.status]:
            raise ThemePackValidationError(
                f"invalid lifecycle transition: {current.status.value} -> {target.value}"
            )
        updated = current.model_copy(update={"status": target})
        self._manifests[pack_key] = updated
        logger.info(
            "theme pack lifecycle changed",
            pack_key=pack_key,
            version=updated.version,
            previous_status=current.status.value,
            status=target.value,
        )
        return updated

    def validate_plugin_source(self, source: str) -> None:
        """Reject all externally supplied Python source; only built-ins can execute."""

        del source
        raise PluginSecurityError("external plugin source is forbidden; use a trusted built-in ID")

    def register_plugin(
        self,
        name: str,
        operation: str,
        function: Any,
    ) -> None:
        """Reject runtime Python registration regardless of callable shape or closure."""

        del name, operation, function
        raise PluginSecurityError("arbitrary callables are forbidden; use a trusted built-in ID")

    def run_plugin(self, name: str, value: Any) -> Any:
        """Invoke a fixed built-in by immutable ID with JSON-only input and output."""

        builtin = _BUILTIN_PLUGINS.get(name)
        if builtin is None:
            raise PluginSecurityError("plugin is not a trusted built-in ID")
        safe_value = self._json_like_copy(value)
        try:
            operation, function = builtin
            result = function(safe_value)
        except Exception as exc:
            logger.warning(
                "theme pack plugin execution failed",
                plugin=name,
                operation=operation,
                error_type=type(exc).__name__,
            )
            raise PluginSecurityError("plugin execution failed") from exc
        return self._json_like_copy(result)

    @staticmethod
    def content_hash(manifest: ThemePackManifest) -> str:
        """Hash immutable declarations while lifecycle remains database-owned."""

        payload = manifest.model_dump_json(exclude_none=True, exclude={"status"})
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"

    @staticmethod
    def _json_like_copy(value: Any) -> Any:
        try:
            return json.loads(json.dumps(value, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise PluginSecurityError("plugin values must be JSON-like data") from exc
