"""Bounded plugin ZIP reader: never extracts, imports, executes or resolves URLs."""

from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import unicodedata
import zipfile
from pathlib import PurePosixPath

from core.observability import get_logger

from ..store import StoreError

log = get_logger(__name__)
MAX_ARCHIVE = 10 * 1024 * 1024
MAX_FILE = 1024 * 1024
MAX_TOTAL = 20 * 1024 * 1024
MAX_FILES = 256
MANIFESTS = ("plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json")
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")


class PluginError(StoreError):
    def __init__(self, code, status=422):
        super().__init__(code, code, status)


def safe_path(name):
    """Reject alternate encodings and ambiguous ZIP paths on casefolded hosts."""
    if not isinstance(name, str):
        raise PluginError("plugin_path_invalid")
    path = PurePosixPath(name)
    if (
        not name
        or len(name) > 240
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or any(ord(char) < 32 for char in name)
        or any(char in name for char in ("\\", ":", "\x7f"))
    ):
        raise PluginError("plugin_path_invalid")
    return name


def read_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PluginError("plugin_json_duplicate_key")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise TypeError("object required")
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PluginError("plugin_json_invalid") from exc


def reject_credentials(value):
    """Never copy host credential files or inline MCP secrets into package stores."""
    if isinstance(value, dict):
        for key, item in value.items():
            reference = isinstance(item, str) and re.fullmatch(
                r"\$\{[A-Za-z_][A-Za-z0-9_:.-]*\}", item
            )
            if (
                key.casefold().replace("_", "")
                in {
                    "apikey",
                    "accesstoken",
                    "refreshtoken",
                    "clientsecret",
                    "password",
                    "authorization",
                }
                and item
                and not reference
            ):
                raise PluginError("plugin_embedded_credentials_rejected")
            if (
                key in {"env", "environment", "headers"}
                and isinstance(item, dict)
                and any(
                    not isinstance(child, str)
                    or re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_:.-]*\}", child) is None
                    for child in item.values()
                )
            ):
                raise PluginError("plugin_embedded_credentials_rejected")
            reject_credentials(item)
    elif isinstance(value, list):
        for item in value:
            reject_credentials(item)


def _component(kind, key, path=None, support="limited", reason="review_required", **extra):
    return {
        "kind": kind,
        "key": key,
        "path": path,
        "support": support,
        "reason": reason,
        "ready": False,
        **extra,
    }


def parse_archive(raw):
    """Return a digest plus complete inert files and explicit support inventory."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ARCHIVE:
        raise PluginError("plugin_archive_limit")
    files, seen, total = {}, set(), 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.infolist()) > MAX_FILES:
                raise PluginError("plugin_file_limit")
            for info in archive.infolist():
                name = safe_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
                leaf = PurePosixPath(name).name.casefold()
                if leaf in {
                    ".env",
                    "auth.json",
                    "credentials.json",
                    "settings.local.json",
                } or leaf.startswith(".env."):
                    raise PluginError("plugin_credential_file_rejected")
                folded = unicodedata.normalize("NFC", name).casefold()
                if folded in seen:
                    raise PluginError("plugin_path_collision")
                seen.add(folded)
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise PluginError("plugin_archive_compression_unsupported")
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}):
                    raise PluginError("plugin_special_file")
                if info.flag_bits & 1 or info.file_size > MAX_FILE:
                    raise PluginError("plugin_file_limit")
                total += info.file_size
                if total > MAX_TOTAL:
                    raise PluginError("plugin_expansion_limit")
                if not info.is_dir():
                    content = archive.read(info)
                    if len(content) != info.file_size:
                        raise PluginError("plugin_size_mismatch")
                    files[name] = content
    except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError) as exc:
        log.warning("plugin_archive_rejected", error_type=type(exc).__name__)
        raise PluginError("plugin_archive_invalid") from exc
    candidates = [path for path in MANIFESTS if path in files]
    if not files:
        raise PluginError("plugin_archive_empty")
    for path in files:
        if any(
            str(parent).casefold() in {name.casefold() for name in files}
            for parent in PurePosixPath(path).parents
            if str(parent) != "."
        ):
            raise PluginError("plugin_path_collision")
    if len(candidates) > 1:
        raise PluginError("plugin_manifest_ambiguous")
    manifest_path = candidates[0] if candidates else None
    manifest = read_json(files[manifest_path]) if manifest_path else {}
    reject_credentials(manifest)
    digest = hashlib.sha256(
        b"".join(
            name.encode() + b"\0" + hashlib.sha256(content).digest()
            for name, content in sorted(files.items())
        )
    ).hexdigest()
    name, version = manifest.get("name", "imported-" + digest[:12]), manifest.get(
        "version", "0.0.0"
    )
    if not isinstance(name, str) or len(name) > 80 or not NAME.fullmatch(name):
        raise PluginError("plugin_name_invalid")
    if not isinstance(version, str) or len(version) > 128 or not VERSION.fullmatch(version):
        raise PluginError("plugin_fixed_version_required")
    components = []
    extensions = manifest.get("extensions", {})
    if not isinstance(extensions, dict):
        raise PluginError("plugin_extensions_invalid")
    openai = extensions.get("com.openai", {})
    if not isinstance(openai, dict):
        raise PluginError("plugin_openai_extension_invalid")
    # Standard layouts are imported even without a vendor manifest. Explicit
    # component paths are contained relative to the package, never the host.
    for kind, field, default in (
        ("skill", "skills", "skills"),
        ("workflow", "workflows", "workflows"),
        ("command", "commands", "commands"),
        ("agent", "agents", "agents"),
    ):
        roots = manifest.get(field, openai.get(field, default))
        if isinstance(roots, str):
            roots = [roots]
        if not isinstance(roots, list) or any(not isinstance(root, str) for root in roots):
            components.append(
                _component(
                    kind, field, support="unsupported", reason="component_declaration_unsupported"
                )
            )
            continue
        paths = set()
        for number, root in enumerate(roots):
            root = safe_path(root.removeprefix("./").rstrip("/"))
            matching = {path for path in files if path == root or path.startswith(root + "/")}
            if not matching and (field in manifest or field in openai):
                components.append(
                    _component(
                        kind,
                        f"missing-{number}",
                        path=root,
                        support="unsupported",
                        reason="component_path_missing",
                    )
                )
            paths.update(matching)
        for path in sorted(paths):
            if (kind in {"skill", "workflow"} and PurePosixPath(path).name == "SKILL.md") or (
                kind in {"command", "agent"} and path.endswith(".md")
            ):
                key = (
                    PurePosixPath(path).parent.name
                    if kind in {"skill", "workflow"}
                    else PurePosixPath(path).stem
                )
                if not NAME.fullmatch(key):
                    raise PluginError("plugin_component_name_invalid")
                components.append(_component(kind, key, path))
    rwb = extensions.get("research_workbench", {})
    if not isinstance(rwb, dict):
        raise PluginError("plugin_rwb_extension_invalid")
    declared_hooks = rwb.get("hooks", [])
    if not isinstance(declared_hooks, list) or len(declared_hooks) > 32:
        raise PluginError("plugin_hook_limit")
    for number, hook in enumerate(declared_hooks):
        script = (
            isinstance(hook, dict)
            and set(hook)
            <= {"event", "type", "path", "interpreter", "timeout", "read", "write", "order"}
            and hook.get("event") == "before_message"
            and hook.get("type") == "script"
            and hook.get("interpreter") == "/bin/sh"
            and isinstance(hook.get("path"), str)
            and type(hook.get("timeout", 2)) in {int, float}
            and 0.1 <= hook.get("timeout", 2) <= 10
            and type(hook.get("order", 0)) is int
            and abs(hook.get("order", 0)) <= 1000
            and isinstance(hook.get("read", []), list)
            and isinstance(hook.get("write", []), list)
            and all(scope == "inputs" for scope in hook.get("read", []))
            and all(scope == "outputs" for scope in hook.get("write", []))
        )
        if script:
            path = safe_path(hook["path"].removeprefix("./"))
            if path not in files or not path.endswith(".sh") or len(files[path]) > 65536:
                raise PluginError("plugin_hook_script_invalid")
            from .sandbox_runner import available

            components.append(
                _component(
                    "hook",
                    str(number),
                    path=path,
                    support="limited",
                    reason=(
                        "macos_seatbelt_shell_builtins_only"
                        if available()
                        else "os_sandbox_unavailable"
                    ),
                    policy=hook,
                    sandbox_available=available(),
                )
            )
            continue
        allowed = (
            isinstance(hook, dict)
            and set(hook) <= {"event", "decision", "reason", "order"}
            and hook.get("event") == "before_message"
            and hook.get("decision") in {"allow", "deny", "cancel"}
            and type(hook.get("order", 0)) is int
            and abs(hook.get("order", 0)) <= 1000
            and isinstance(hook.get("reason", ""), str)
            and len(hook.get("reason", "")) <= 256
        )
        components.append(
            _component(
                "hook",
                str(number),
                support="supported" if allowed else "unsupported",
                reason="declarative_policy" if allowed else "hook_semantics_unsupported",
                policy=hook if allowed else None,
            )
        )
    hook_spec = manifest.get("hooks", "hooks/hooks.json" if "hooks/hooks.json" in files else None)
    if hook_spec:
        if isinstance(hook_spec, str):
            path = safe_path(hook_spec.removeprefix("./"))
            if path not in files:
                raise PluginError("plugin_hook_file_missing")
            read_json(files[path])
        components.append(
            _component(
                "hook",
                "host-hooks",
                support="unsupported",
                reason="host_hook_scripts_require_os_sandbox_and_event_review",
            )
        )
    mcp_spec = manifest.get(
        "mcpServers", openai.get("mcpServers", ".mcp.json" if ".mcp.json" in files else None)
    )
    if mcp_spec:
        if isinstance(mcp_spec, str):
            path = safe_path(mcp_spec.removeprefix("./"))
            if path not in files:
                raise PluginError("plugin_mcp_file_missing")
            mcp_spec = read_json(files[path])
        reject_credentials(mcp_spec)
        components.append(
            _component(
                "mcp",
                "host-mcp",
                support="unsupported",
                reason="native_registry_selection_required",
            )
        )
    selections = rwb.get("mcp", {})
    if not isinstance(selections, dict) or len(selections) > 20:
        raise PluginError("plugin_mcp_selection_invalid")
    from ..mcp_runtime.models import InstallationSelection

    for key, selection in selections.items():
        if not NAME.fullmatch(key):
            raise PluginError("plugin_component_name_invalid")
        try:
            validated = InstallationSelection.model_validate(selection).model_dump()
        except ValueError as exc:
            raise PluginError("plugin_mcp_selection_invalid") from exc
        components.append(
            _component(
                "mcp",
                key,
                support="supported",
                reason="native_preview_confirmation_required",
                selection=validated,
            )
        )
    known = {"skills", "commands", "agents", "mcpServers", "hooks"}
    for key in sorted(set(openai) - known):
        components.append(
            _component("host", str(key), support="unsupported", reason="host_specific_extension")
        )
    for key in ("lspServers", "outputStyles", "settings", "install", "scripts", "dependencies"):
        if key in manifest:
            components.append(
                _component(
                    "host",
                    key,
                    support="unsupported",
                    reason="host_execution_or_configuration_unsupported",
                )
            )
    identities = [(row["kind"], row["key"]) for row in components]
    if len(set(identities)) != len(identities):
        raise PluginError("plugin_component_collision")
    if not components:
        components.append(
            _component(
                "host", "unrecognized-layout", support="unsupported", reason="no_mapped_components"
            )
        )
    permissions = sorted(
        {
            {
                "skill": "skills:read",
                "workflow": "workflows:read",
                "command": "commands:invoke",
                "agent": "agents:instructions",
                "hook": "hooks:policy",
                "mcp": "mcp:manage",
            }[row["kind"]]
            for row in components
            if row["support"] != "unsupported"
        }
    )
    for component in components:
        if component["kind"] == "hook" and (component.get("policy") or {}).get("type") == "script":
            permissions.append(
                "hooks:execute:"
                + component["key"]
                + ":"
                + hashlib.sha256(files[component["path"]]).hexdigest()
            )
            permissions.extend(
                "hooks:read:" + scope for scope in component["policy"].get("read", [])
            )
            permissions.extend(
                "hooks:write:" + scope for scope in component["policy"].get("write", [])
            )
    permissions = sorted(set(permissions))
    if any(
        component["kind"] == "agent" and component["support"] != "unsupported"
        for component in components
    ):
        permissions = sorted(set(permissions) | {"agents:delegate"})
    for component in components:
        if (
            component["kind"] not in {"skill", "workflow"}
            or not component.get("path")
            or component["support"] == "unsupported"
        ):
            continue
        folder = str(PurePosixPath(component["path"]).parent) + "/"
        for path, content in files.items():
            if path.startswith(folder + "scripts/") and path.endswith(".py"):
                permissions.append("skills:sandbox-script:" + hashlib.sha256(content).hexdigest())
        metadata_path = folder + "capability.json"
        if metadata_path in files:
            metadata = read_json(files[metadata_path])
            for field, prefix, maximum in (
                ("dependencies", "dependencies:declare:", 40),
                ("required_tools", "tools:declare:", 20),
            ):
                values = metadata.get(field, [])
                if (
                    not isinstance(values, list)
                    or len(values) > maximum
                    or any(
                        not isinstance(value, str) or not value or len(value) > 200
                        for value in values
                    )
                ):
                    raise PluginError("plugin_native_metadata_invalid")
                permissions.extend(prefix + value for value in values)
    permissions = sorted(set(permissions))
    if len(permissions) > 512 or sum(len(item.encode()) for item in permissions) > 60000:
        raise PluginError("plugin_permission_limit")
    log.info("plugin_archive_previewed", digest=digest, component_count=len(components))
    return {
        "name": name,
        "version": version,
        "digest": digest,
        "format": manifest_path or "standard-layout",
        "components": components,
        "permissions": permissions,
        "manifest": manifest,
        "file_inventory": [
            {"path": path, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for path, content in sorted(files.items())
        ],
        "files": files,
    }
