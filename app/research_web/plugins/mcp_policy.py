"""Tenant-only MCP package ownership and content/schema approval verification."""

import hashlib
import json
import os
import re
from pathlib import Path

from .packages import PluginError, parse_archive, read_json


def register_managed(root, installation_id):
    from ..datahub.security import atomic_json, directory, read_file

    with directory(Path(root), ("mcp-runtime",), private=True) as folder:
        path = Path(root) / "mcp-runtime/plugin-managed.json"
        value = (
            read_json(read_file(folder, "plugin-managed.json", private=True, limit=65536))
            if path.exists()
            else {"installation_ids": []}
        )
        value["installation_ids"] = sorted(set(value["installation_ids"]) | {installation_id})
        atomic_json(folder, "plugin-managed.json", value)


def requires_managed(root, installation_id):
    if root is None:
        return False
    path = Path(root) / "mcp-runtime/plugin-managed.json"
    if not path.exists() and not path.is_symlink():
        return False
    from ..datahub.security import directory, read_file

    with directory(Path(root), ("mcp-runtime",), private=True) as folder:
        value = read_json(read_file(folder, "plugin-managed.json", private=True, limit=65536))
    return installation_id in value["installation_ids"]


def canonical(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def schema_view(capabilities):
    tools = capabilities.get("tools", []) if isinstance(capabilities, dict) else capabilities
    return sorted(
        [
            {
                "name": tool.get("tool_name", tool.get("name")),
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema", tool.get("inputSchema")),
                "output_schema": tool.get("output_schema", tool.get("outputSchema")),
            }
            for tool in tools
        ],
        key=lambda tool: tool["name"],
    )


def artifact_digest(root):
    """Freshly hash installed bytes, bounded and without following links."""
    if root.is_symlink() or not root.is_dir():
        raise PluginError("plugin_mcp_artifact_missing", 409)
    digest, count, total = hashlib.sha256(), 0, 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
                raise PluginError("plugin_mcp_artifact_link", 409)
            digest.update(
                path.relative_to(root).as_posix().encode()
                + b"\0link\0"
                + os.readlink(path).encode()
            )
            continue
        if path.is_dir():
            continue
        count += 1
        identity = path.stat()
        total += identity.st_size
        if (
            not path.is_file()
            or identity.st_nlink != 1
            or count > 20000
            or total > 256 * 1024 * 1024
        ):
            raise PluginError("plugin_mcp_artifact_limit", 409)
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        with path.open("rb") as handle:
            while content := handle.read(1024 * 1024):
                digest.update(content)
    return digest.hexdigest()


def native_fingerprint(root, manifest, schemas=None):
    value = manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else dict(manifest)
    plan = value["plan"]
    installation = value["id"]
    if (
        not isinstance(installation, str)
        or not installation.startswith("mcp-installation-")
        or "/" in installation
        or "\\" in installation
    ):
        raise PluginError("plugin_mcp_identity_invalid")
    # Signed native manifest includes exact fixed source, artifacts, argv/env
    # NAMES and remote endpoint. No credential values are in this representation.
    artifact = (
        "remote"
        if "endpoint" in plan
        else artifact_digest(Path(root) / "mcp-runtime/packages" / installation)
    )
    return {
        "manifest": canonical(value),
        "artifacts": artifact,
        "schemas": canonical(schema_view(schemas)) if schemas is not None else None,
    }


def managed_binding(root, manifest, schemas=None, *, require_schema=True):
    """Read current reviewed package source before any tenant process/call."""
    root = Path(root)
    path = root / "plugins/index.json"
    if path.is_symlink():
        raise PluginError("plugin_mcp_unmanaged", 403)
    try:
        index = read_json(path.read_bytes())
    except OSError as exc:
        raise PluginError("plugin_mcp_unmanaged", 403) from exc
    value = manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else dict(manifest)
    iid = value["id"]
    found = []
    for digest, row in index["versions"].items():
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise PluginError("plugin_mcp_package_identity_invalid", 403)
        for component, installation in row.get("mcp_bindings", {}).items():
            if installation != iid:
                continue
            if (
                row.get("state") not in {"enabled", "superseded"}
                or (row.get("review") or {}).get("digest") != digest
                or row["review"].get("permissions") != row["permissions"]
            ):
                raise PluginError("plugin_mcp_approval_inactive", 403)
            archive_path = root / "plugins/versions" / digest / "package.zip"
            if archive_path.is_symlink() or archive_path.parent.is_symlink():
                raise PluginError("plugin_mcp_package_unsafe", 403)
            package = parse_archive(archive_path.read_bytes())
            if package["digest"] != digest or package["permissions"] != row["permissions"]:
                raise PluginError("plugin_mcp_package_changed", 403)
            declaration = next(
                (
                    part.get("selection")
                    for part in package["components"]
                    if part["kind"] == "mcp" and part["key"] == component
                ),
                None,
            )
            if not declaration or any(
                value["plan"].get(field) != declaration[field]
                for field in ("registry_id", "server_name", "server_version")
            ):
                raise PluginError("plugin_mcp_selection_changed", 403)
            if row.get("managed_approval"):
                authorized = False
                for name in ("RWB_SHARED_PLUGINS_ROOT", "RWB_PERSONAL_PLUGINS_ROOT"):
                    approved = os.environ.get(name)
                    if not approved:
                        continue
                    source_path = Path(approved) / "plugins/index.json"
                    if source_path.is_symlink() or any(
                        parent.is_symlink() for parent in source_path.parents
                    ):
                        raise PluginError("plugin_mcp_approval_source_unsafe", 403)
                    if source_path.exists():
                        source = read_json(source_path.read_bytes())
                        source_row = source.get("versions", {}).get(digest, {})
                        authorized |= (
                            source_row.get("state") in {"enabled", "superseded"}
                            and (source_row.get("review") or {}).get("digest") == digest
                            and source_row["review"].get("permissions") == row["permissions"]
                        )
                if not authorized:
                    raise PluginError("plugin_mcp_approval_revoked", 403)
            expected = row.get("mcp_reviews", {}).get(component)
            current = native_fingerprint(root, manifest, schemas)
            if (
                expected is None
                or expected["manifest"] != current["manifest"]
                or expected["artifacts"] != current["artifacts"]
            ):
                raise PluginError("plugin_mcp_native_review_required", 403)
            if require_schema and (
                expected.get("schemas") is None or expected["schemas"] != current["schemas"]
            ):
                raise PluginError("plugin_mcp_schema_review_required", 403)
            found.append((digest, component))
    if len(found) != 1:
        raise PluginError("plugin_mcp_unmanaged", 403)
    return found[0]
