"""Validated registry for declarative, permission-bounded Research Packs."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from core.contracts.theme_research import PackLifecycle, ThemePackManifest
from core.observability import get_logger

logger = get_logger(__name__)

_ALLOWED_PLUGIN_OPERATIONS = frozenset({"normalize", "validate", "derive"})
_FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "anthropic",
        "asyncio.subprocess",
        "http",
        "httpx",
        "openai",
        "os",
        "pathlib",
        "psycopg",
        "requests",
        "socket",
        "sqlalchemy",
        "subprocess",
        "urllib",
    }
)
_FORBIDDEN_CALLS = frozenset(
    {"__import__", "compile", "eval", "exec", "open", "popen", "run", "system"}
)
_LIFECYCLE_TRANSITIONS = {
    PackLifecycle.DISCOVERED: {PackLifecycle.VALIDATED},
    PackLifecycle.VALIDATED: {PackLifecycle.ENABLED, PackLifecycle.DISABLED},
    PackLifecycle.ENABLED: {PackLifecycle.DEGRADED, PackLifecycle.DISABLED},
    PackLifecycle.DEGRADED: {PackLifecycle.ENABLED, PackLifecycle.DISABLED},
    PackLifecycle.DISABLED: set(),
}


class ThemePackValidationError(ValueError):
    """A manifest violates the Research Pack contract."""


class PluginSecurityError(ValueError):
    """A plugin requests or references a forbidden capability."""


class _RegisteredPlugin:
    def __init__(self, operation: str, function: Callable[[Any], Any], fingerprint: str):
        self.operation = operation
        self.function = function
        self.fingerprint = fingerprint


class ThemePackRegistry:
    """Load manifests and execute only explicitly registered pure plugins."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self._manifests: dict[str, ThemePackManifest] = {}
        self._plugins: dict[str, _RegisteredPlugin] = {}

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
        permissions = raw.get("plugin_permissions", [])
        forbidden = set(permissions) - _ALLOWED_PLUGIN_OPERATIONS
        if forbidden:
            raise ThemePackValidationError(f"forbidden permission declared: {sorted(forbidden)}")
        try:
            manifest = ThemePackManifest.model_validate(raw)
        except ValidationError as exc:
            logger.info(
                "theme pack manifest rejected",
                path=str(manifest_path),
                error_count=exc.error_count(),
            )
            raise ThemePackValidationError("manifest validation failed") from exc
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
        """Statically reject imports and calls that escape the pure plugin boundary."""

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise PluginSecurityError("plugin source is invalid") from exc
        functions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if not functions or not functions.issubset(_ALLOWED_PLUGIN_OPERATIONS):
            raise PluginSecurityError("plugin may only define normalize, validate, or derive")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self._reject_imports(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self._reject_imports([node.module or ""])
            elif isinstance(node, ast.Call):
                name = self._call_name(node.func)
                if name.split(".")[-1] in _FORBIDDEN_CALLS:
                    raise PluginSecurityError(f"forbidden plugin call: {name}")

    def register_plugin(
        self,
        name: str,
        operation: str,
        function: Callable[[Any], Any],
    ) -> None:
        """Register a trusted in-process pure function after bytecode capability checks."""

        if operation not in _ALLOWED_PLUGIN_OPERATIONS:
            raise PluginSecurityError("forbidden plugin operation")
        self._validate_callable(function)
        fingerprint = self._plugin_fingerprint(function)
        self._plugins[name] = _RegisteredPlugin(operation, function, fingerprint)
        logger.info("theme pack plugin registered", plugin=name, operation=operation)

    def run_plugin(self, name: str, value: Any) -> Any:
        """Revalidate the registered callable at runtime before invoking it."""

        plugin = self._plugins.get(name)
        if plugin is None:
            raise PluginSecurityError("plugin is not registered")
        self._validate_callable(plugin.function)
        if self._plugin_fingerprint(plugin.function) != plugin.fingerprint:
            raise PluginSecurityError("plugin implementation changed after registration")
        safe_value = self._json_like_copy(value)
        try:
            result = plugin.function(safe_value)
        except Exception as exc:
            logger.warning(
                "theme pack plugin execution failed",
                plugin=name,
                operation=plugin.operation,
                error_type=type(exc).__name__,
            )
            raise PluginSecurityError("plugin execution failed") from exc
        return self._json_like_copy(result)

    @staticmethod
    def content_hash(manifest: ThemePackManifest) -> str:
        """Return a stable hash for persistence and version review."""

        payload = manifest.model_dump_json(exclude_none=True)
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"

    @staticmethod
    def _call_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = ThemePackRegistry._call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    @staticmethod
    def _reject_imports(names: Any) -> None:
        for name in names:
            if any(name == root or name.startswith(f"{root}.") for root in _FORBIDDEN_IMPORT_ROOTS):
                raise PluginSecurityError(f"forbidden plugin import: {name}")
            if name.startswith(("core.model_gateway", "data_layer", "storage")):
                raise PluginSecurityError(f"forbidden plugin import: {name}")

    @staticmethod
    def _validate_callable(function: Callable[[Any], Any]) -> None:
        if not callable(function) or not hasattr(function, "__code__"):
            raise PluginSecurityError("plugin must be a Python function")
        names = set(function.__code__.co_names)
        forbidden_names = names & (_FORBIDDEN_CALLS | _FORBIDDEN_IMPORT_ROOTS)
        if forbidden_names or any(
            name.startswith(("model_gateway", "sqlalchemy", "subprocess")) for name in names
        ):
            raise PluginSecurityError("plugin callable references a forbidden capability")
        closure = inspect.getclosurevars(function)
        for value in (*closure.globals.values(), *closure.nonlocals.values()):
            module = getattr(value, "__module__", "") or getattr(value, "__name__", "")
            if any(
                module == root or module.startswith(f"{root}.") for root in _FORBIDDEN_IMPORT_ROOTS
            ):
                raise PluginSecurityError("plugin closure contains a forbidden capability")

    @staticmethod
    def _plugin_fingerprint(function: Callable[[Any], Any]) -> str:
        code = function.__code__
        payload = code.co_code + repr(code.co_consts).encode() + repr(code.co_names).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _json_like_copy(value: Any) -> Any:
        try:
            return json.loads(json.dumps(value, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise PluginSecurityError("plugin values must be JSON-like data") from exc
