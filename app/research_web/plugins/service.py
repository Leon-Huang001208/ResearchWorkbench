"""Reviewed immutable plugins; native capabilities/MCP remain execution authorities.

This module has no startup side effects. Its caller serializes mutations through
the ResearchService lock (or gateway plugin lock) and provides an idle gate.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import os
import re
import shutil
from pathlib import Path

import yaml

from core.observability import get_logger

from ..capabilities.packages import encode_file
from ..store import StoreError
from .packages import PluginError, parse_archive, read_json

log = get_logger(__name__)
DIGEST = re.compile(r"^[a-f0-9]{64}$")


async def awaited(value):
    return await value if inspect.isawaitable(value) else value


def _private_directory(path):
    for candidate in (*reversed(path.parents), path):
        if candidate.is_symlink():
            raise PluginError("plugin_storage_unsafe", 503)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)


def _atomic(path, value):
    from ..datahub.security import atomic_json, directory

    try:
        with directory(path.parent, private=True) as folder:
            atomic_json(folder, path.name, value)
    except (OSError, StoreError) as exc:
        log.error("plugin_state_write_failed", error_type=type(exc).__name__)
        raise PluginError("plugin_state_write_failed", 503) from exc


def _private_json(path, *, limit=8 * 1024 * 1024):
    from ..datahub.security import directory, read_file

    with directory(path.parent, private=True) as folder:
        return read_json(read_file(folder, path.name, private=True, limit=limit))


class PluginService:
    """Package review never replaces component-specific runtime authorization."""

    def __init__(self, root: Path, capabilities=None, mcp_runtime=None, *, idle_gate=None):
        self.root = Path(root) / "plugins"
        _private_directory(self.root)
        _private_directory(self.root / "versions")
        _private_directory(self.root / "sessions")
        self.capabilities, self.mcp, self.idle_gate = capabilities, mcp_runtime, idle_gate
        self.hook_cancellations: dict[str, asyncio.Event] = {}
        self.native_names: set[str] = set()
        self.approval_roots = tuple(
            Path(value)
            for name in ("RWB_SHARED_PLUGINS_ROOT", "RWB_PERSONAL_PLUGINS_ROOT")
            if (value := os.environ.get(name))
        )
        self.path = self.root / "index.json"
        try:
            if self.path.is_symlink():
                raise PluginError("plugin_storage_unsafe", 503)
            self.data = (
                _private_json(self.path)
                if self.path.exists()
                else {"schema_version": 1, "versions": {}, "active": {}, "pending": None}
            )
            if self.data.get("schema_version") != 1 or not isinstance(
                self.data.get("versions"), dict
            ):
                raise PluginError("plugin_index_invalid", 503)
        except OSError as exc:
            raise PluginError("plugin_index_unavailable", 503) from exc

    def save(self):
        _atomic(self.path, self.data)

    def _row(self, digest):
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise PluginError("plugin_digest_invalid")
        if digest not in self.data["versions"]:
            raise PluginError("plugin_version_not_found", 404)
        return self.data["versions"][digest]

    def _archive(self, digest):
        row = self._row(digest)
        path = self.root / "versions" / digest / "package.zip"
        if path.is_symlink() or path.parent.is_symlink():
            raise PluginError("plugin_storage_unsafe", 503)
        try:
            from ..datahub.security import directory, read_file
            from .packages import MAX_ARCHIVE

            with directory(self.root, ("versions", digest), private=True) as folder:
                value = parse_archive(
                    read_file(folder, "package.zip", private=True, limit=MAX_ARCHIVE)
                )
        except (OSError, StoreError) as exc:
            raise PluginError("plugin_version_unavailable", 503) from exc
        if value["digest"] != digest or value["permissions"] != row["permissions"]:
            raise PluginError("plugin_integrity_failed", 409)
        return value

    def preview(self, raw):
        package = parse_archive(raw)
        digest = package["digest"]
        if digest not in self.data["versions"]:
            for prior in self.data["versions"].values():
                if prior["name"] == package["name"] and prior["version"] == package["version"]:
                    raise PluginError("plugin_version_content_conflict", 409)
            target = self.root / "versions" / digest
            if target.exists():
                raise PluginError("plugin_publication_uncertain", 409)
            _private_directory(target)
            try:
                with (target / "package.zip").open("xb") as handle:
                    handle.write(raw)
                os.chmod(target / "package.zip", 0o400)
                row = {
                    key: copy.deepcopy(value) for key, value in package.items() if key != "files"
                }
                row.update(review=None, bindings={}, mcp_bindings={}, state="preview")
                self.data["versions"][digest] = row
                self.save()
            except OSError as exc:
                raise PluginError("plugin_preview_store_failed", 503) from exc
        return self.detail(digest)

    def detail(self, digest):
        row = copy.deepcopy(self._row(digest))
        row["enabled"] = self.data["active"].get(row["name"]) == digest
        row["approved_for_sessions"] = self.version_authorized(digest)
        for component in row["components"]:
            component_id = component["kind"] + ":" + component["key"]
            binding = row["bindings"].get(component_id)
            component["ready"] = False
            if component_id in row.get("component_issues", {}):
                component["reason"] = "native_validation_failed"
                component["issues"] = row["component_issues"][component_id]
            if row["approved_for_sessions"] and binding and self.capabilities is not None:
                native = self.capabilities.row(binding["id"])
                component["projected"] = (
                    native["status"] == "enabled" and native["version"] == binding["version"]
                )
                native_name = (
                    native.get("versions", {})
                    .get(str(binding["version"]), {})
                    .get("native_name", native.get("native_name"))
                )
                component["ready"] = component["projected"] and native_name in self.native_names
                if component["projected"] and not component["ready"]:
                    component["reason"] = "native_discovery_pending"
                component["native_binding"] = binding
            elif component["kind"] == "hook" and component["support"] != "unsupported":
                component["ready"] = bool(
                    row["approved_for_sessions"] and component.get("sandbox_available", True)
                )
            elif (
                component["kind"] == "mcp" and component["key"] in row["mcp_bindings"] and self.mcp
            ):
                # A native install is not a ready callable tool until activated,
                # probed and separately authorized to a session by MCP Runtime.
                component["installation_id"] = row["mcp_bindings"][component["key"]]
                component["reason"] = "native_tool_session_authorization_required"
        return row

    def confirm_native(self, names):
        """Call only with the current native DSH Skill list, never package claims."""
        self.native_names = set(names)
        if os.environ.get("RWB_TENANT_MODE") == "1":
            path = self.root / "guard-state.json"
            if path.is_symlink() or not path.is_file():
                self.native_names.clear()
                return
            guard = _private_json(path)
            self.native_names.intersection_update(guard.get("skill_names", []))

    def version_authorized(self, digest, *, sources=True):
        """An upgrade retains approved old bytes; only explicit withdrawal revokes."""
        row = self._row(digest)
        review = row.get("review") or {}
        if (
            row.get("state") not in {"enabled", "superseded"}
            or review.get("digest") != digest
            or review.get("permissions") != row["permissions"]
        ):
            return False
        self._archive(digest)
        if sources and row.get("managed_approval"):
            for source in self.approval_roots:
                if (source / "plugins/index.json").exists():
                    manager = PluginService(source)
                    if digest in manager.data["versions"] and manager.version_authorized(
                        digest, sources=False
                    ):
                        return True
            return False
        return True

    def manages_capability(self, cid):
        return any(
            binding["id"] == cid
            for row in self.data["versions"].values()
            for binding in row["bindings"].values()
        )

    def capability_authorized(self, cid):
        return any(
            self.version_authorized(digest)
            for digest, row in self.data["versions"].items()
            if any(binding["id"] == cid for binding in row["bindings"].values())
        )

    def native_authorized(self, name, session_id=None):
        """Exact immutable native binding in this session's frozen package set."""
        pins = None
        if session_id is not None:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
                return False
            path = self.root / "sessions" / (session_id + ".json")
            if not path.is_file() or path.is_symlink():
                return False
            pins = {item["digest"] for item in _private_json(path)["plugins"]}
        for digest, row in self.data["versions"].items():
            if (pins is not None and digest not in pins) or not self.version_authorized(digest):
                continue
            for binding in row["bindings"].values():
                native = self.capabilities.row(binding["id"])
                version = native.get("versions", {}).get(str(binding["version"]), {})
                if (
                    native["status"] == "enabled"
                    and native["version"] == binding["version"]
                    and version.get("native_name", native.get("native_name")) == name
                ):
                    return True
        return False

    def list(self):
        return {
            "items": [self.detail(digest) for digest in self.data["versions"]],
            "pending": self.data.get("pending"),
            "deferred_updates": self.data.get("deferred_updates", {}),
            "engine": "dsh",
        }

    async def synchronize(self, approved_roots):
        """Project manager-selected approval stores, never browser paths/roles.

        Each tenant owns its native copies and credentials. Shared stores contain
        only reviewed packages; neither native installation IDs nor secrets copy.
        """
        self.approval_roots = tuple(Path(root) for root in approved_roots)
        desired = {}
        for source_root in self.approval_roots:
            source_root = Path(source_root)
            if (
                not source_root.is_absolute()
                or ".." in source_root.parts
                or any(part.is_symlink() for part in (source_root, *source_root.parents))
            ):
                raise PluginError("plugin_approval_source_unsafe", 503)
            if not (source_root / "plugins/index.json").exists():
                continue
            source = PluginService(source_root)
            for name, digest in source.data["active"].items():
                row = source._reviewed(digest)
                if name in desired:
                    raise PluginError("plugin_scope_name_collision", 409)
                desired[name] = (source, digest, row)
        for name, (source, digest, row) in desired.items():
            if self.data["active"].get(name) == digest:
                continue
            existing_digest = self.data["active"].get(name)
            if existing_digest and not self._row(existing_digest).get("managed_approval"):
                raise PluginError("plugin_scope_name_collision", 409)
            source._archive(digest)
            self.preview((source.root / "versions" / digest / "package.zip").read_bytes())
            self.review(digest, row["permissions"], row["review"]["reviewer"])
            self._row(digest)["managed_approval"] = True
            self.save()
            try:
                await self.enable(digest)
                self.data.setdefault("deferred_updates", {}).pop(name, None)
            except PluginError as exc:
                if exc.code != "plugin_mcp_upgrade_deferred":
                    raise
                self.data.setdefault("deferred_updates", {})[name] = digest
                self.save()
        for digest, local in list(self.data["versions"].items()):
            if (
                local.get("managed_approval")
                and local.get("state") in {"enabled", "superseded"}
                and not self.version_authorized(digest)
            ):
                await self.disable(digest)
        for name, digest in list(self.data["active"].items()):
            if name not in desired and self._row(digest).get("managed_approval"):
                self.data["active"].pop(name)
                if self._row(digest)["state"] == "enabled":
                    self._row(digest)["state"] = "superseded"
                self.data.setdefault("deferred_updates", {}).pop(name, None)
                self.save()
        return self.list()

    def review(self, digest, permissions, reviewer):
        row = self._row(digest)
        self._archive(digest)
        if (
            not isinstance(permissions, list)
            or sorted(permissions) != row["permissions"]
            or len(set(permissions)) != len(permissions)
        ):
            raise PluginError("plugin_permission_mismatch", 403)
        if not isinstance(reviewer, str) or not reviewer or len(reviewer) > 128:
            raise PluginError("plugin_reviewer_required", 403)
        row["review"] = {"digest": digest, "permissions": list(permissions), "reviewer": reviewer}
        if row.get("state") not in {"enabled", "superseded", "disabled"}:
            row["state"] = "reviewed"
        self.save()
        log.info("plugin_review_recorded", digest=digest)
        return self.detail(digest)

    def _reviewed(self, digest):
        row = self._row(digest)
        review = row.get("review") or {}
        if review.get("digest") != digest or review.get("permissions") != row["permissions"]:
            raise PluginError("plugin_review_required", 409)
        if self.data.get("pending"):
            raise PluginError("plugin_recovery_required", 409)
        self._archive(digest)
        return row

    async def _idle(self):
        if self.idle_gate is None or await awaited(self.idle_gate()) is not True:
            raise PluginError("plugin_runtime_busy", 409)

    def _mcp_active(self, installation):
        if self.mcp is not None:
            value = self.mcp.status(installation).get("active")
            if type(value) is bool:
                return value
            raise PluginError("plugin_mcp_upgrade_deferred", 409)
        # Launcher projection has no Host object. Only the native, private
        # activation manifest can establish that this old binding is inactive.
        try:
            active = _private_json(self.root.parent / "mcp-runtime/active.json", limit=65536)
        except (OSError, StoreError):
            raise PluginError("plugin_mcp_upgrade_deferred", 409) from None
        if (
            active.get("schema_version") != 1
            or not isinstance(active.get("installation_ids"), list)
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"mcp-installation-[a-f0-9]{32}", value)
                for value in active["installation_ids"]
            )
        ):
            raise PluginError("plugin_mcp_upgrade_deferred", 409)
        return installation in active["installation_ids"]

    def _draft(self, package, component):
        files = package["files"]
        raw = files[component["path"]]
        try:
            text = raw.decode("utf-8")
            header = {}
            body = text
            if text.startswith("---\n"):
                header_text, body = text[4:].split("\n---", 1)
                header = yaml.safe_load(header_text)
                if not isinstance(header, dict):
                    raise ValueError("invalid frontmatter")
            # Shell interpolation, host tool names, model selection, permissions,
            # context fork and hooks are NOT silently reinterpreted as DSH.
            allowed = {"name", "description", "argument-hint"}
            if set(header) - allowed or re.search(
                r"!?`[^`]+`|\$\{CLAUDE_PLUGIN_ROOT\}|\$\{CLAUDE_PROJECT_DIR\}", body
            ):
                raise PluginError("plugin_instruction_semantics_unsupported", 409)
        except (UnicodeError, ValueError, yaml.YAMLError) as exc:
            raise PluginError("plugin_instruction_invalid") from exc
        slug = "p-" + package["digest"][:16] + "-" + component["kind"] + "-" + component["key"]
        if len(slug) > 80:
            raise PluginError("plugin_component_name_too_long")
        description = str(
            header.get("description") or f"{package['name']} {component['kind']} {component['key']}"
        )[:1900]
        resources, metadata, steps = [], None, []
        if component["kind"] in {"skill", "workflow"}:
            folder = str(Path(component["path"]).parent)
            prefix = folder + "/"
            for name, content in files.items():
                if name.startswith(prefix) and name != component["path"]:
                    relative = name[len(prefix) :]
                    # Native catalog validates every resource and retains its
                    # script review/data/Tool semantics; never mark scripts reviewed.
                    if relative == "capability.json":
                        metadata = read_json(content)
                        continue
                    if relative == "workflow.json":
                        if component["kind"] != "workflow":
                            raise PluginError("plugin_workflow_kind_mismatch", 409)
                        steps = read_json(content).get("steps")
                        if not isinstance(steps, list):
                            raise PluginError("plugin_workflow_invalid")
                        continue
                    resources.append(encode_file(relative, content))
        if metadata is None:
            metadata = {
                "name": f"{package['name']} / {component['key']}",
                "description": description,
                "category": "插件",
                "inputs": [{"name": "question", "label": "输入", "type": "text", "required": True}],
                "scenarios": [description],
                "default_formats": [],
            }
        metadata["slug"] = slug
        metadata["name"] = (
            f"{package['name']} / {component['key']}"[:85]
            + f" @{package['version'][:12]}-{package['digest'][:8]}"
        )
        # Preserve declared Tools/dependencies/data semantics. The native catalog
        # enforces installed dependencies, script reviews and data preflight.
        return {
            "kind": "workflow" if component["kind"] == "workflow" else "skill",
            "metadata": metadata,
            "instructions": "---\n"
            + yaml.safe_dump({"name": slug, "description": description}, allow_unicode=True)
            + "---\n"
            + body.strip(),
            "files": resources,
            "steps": steps,
            "reviewed_scripts": [
                resource["sha256"] for resource in resources if resource["path"].endswith(".py")
            ],
        }

    async def enable(self, digest):
        row = self._reviewed(digest)
        await self._idle()
        package = self._archive(digest)
        prior_digest = self.data["active"].get(row["name"])
        if prior_digest == digest:
            row["state"] = "enabled"
            self.data.setdefault("deferred_updates", {}).pop(row["name"], None)
            self.save()
            return self.detail(digest)
        if prior_digest:
            installations = self._row(prior_digest)["mcp_bindings"].values()
            if any(self._mcp_active(installation) for installation in installations):
                raise PluginError("plugin_mcp_upgrade_deferred", 409)
        # Build/validate all adapters before touching native discovery.
        drafts = {}
        for component in row["components"]:
            if (
                component["kind"] in {"skill", "workflow", "command", "agent"}
                and component["support"] != "unsupported"
            ):
                try:
                    drafts[component["kind"] + ":" + component["key"]] = self._draft(
                        package, component
                    )
                except StoreError as exc:
                    component.update(support="unsupported", reason=exc.code, ready=False)
        self.data["pending"] = {"digest": digest, "action": "enable"}
        self.save()
        activated, deactivated = [], []
        ready_keys = []
        try:
            for key, draft in drafts.items() if self.capabilities is not None else []:
                if key not in row["bindings"]:
                    cid = row.get("draft_bindings", {}).get(key)
                    if cid is None:
                        cid = self.capabilities.create(draft)["id"]
                        row.setdefault("draft_bindings", {})[key] = cid
                        self.save()
                    if hasattr(self.capabilities, "check"):
                        checks = self.capabilities.check(cid)
                        if not checks["valid"]:
                            row.setdefault("component_issues", {})[key] = checks["issues"]
                            self.save()
                            continue
                    self.capabilities.publish(cid, _status="disabled")
                    row["bindings"][key] = {
                        "id": cid,
                        "version": self.capabilities.row(cid)["version"],
                    }
                    row.setdefault("component_issues", {}).pop(key, None)
                    self.save()
                ready_keys.append(key)
            for key in ready_keys:
                binding = row["bindings"][key]
                self.capabilities.transition(binding["id"], "enable")
                activated.append(binding)
            self.data["active"][row["name"]] = digest
            self.data.setdefault("deferred_updates", {}).pop(row["name"], None)
            if prior_digest:
                self._row(prior_digest)["state"] = "superseded"
            row["state"] = "enabled"
            self.data["pending"] = None
            self.save()
        except Exception as exc:
            log.error("plugin_activation_failed", digest=digest, error_type=type(exc).__name__)
            try:
                if prior_digest:
                    self.data["active"][row["name"]] = prior_digest
                else:
                    self.data["active"].pop(row["name"], None)
                for binding in activated:
                    self.capabilities.transition(binding["id"], "disable")
                for binding in deactivated:
                    self.capabilities.transition(binding["id"], "enable")
                self.data["pending"] = None
                self.save()
            except (OSError, StoreError, ValueError, RuntimeError, KeyError, TypeError) as recovery:
                log.error(
                    "plugin_activation_recovery_required",
                    digest=digest,
                    error_type=type(recovery).__name__,
                )
            raise PluginError("plugin_activation_failed", 503) from exc
        log.info("plugin_enabled", digest=digest)
        return self.detail(digest)

    async def disable(self, digest):
        row = self._row(digest)
        await self._idle()
        if row.get("state") in {"enabled", "superseded"}:
            if any(
                self.mcp is not None and self.mcp.status(installation).get("active")
                for installation in row["mcp_bindings"].values()
            ):
                raise PluginError("plugin_disable_mcp_first", 409)
            self.data["pending"] = {"digest": digest, "action": "disable"}
            self.save()
            for binding in row["bindings"].values():
                if self.capabilities is not None:
                    self.capabilities.transition(binding["id"], "disable")
            if self.data["active"].get(row["name"]) == digest:
                self.data["active"].pop(row["name"])
            row["state"] = "disabled"
            self.data["pending"] = None
            self.save()
        return self.detail(digest)

    async def disable_mcp(self, digest):
        """Native MCP idleness/restart owns its own lock; call outside Host lock."""
        for installation in self._row(digest)["mcp_bindings"].values():
            if self.mcp is None:
                raise PluginError("plugin_mcp_lifecycle_deferred", 409)
            if self.mcp.status(installation).get("active"):
                await self.mcp.disable(installation)

    def pin(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
            raise PluginError("plugin_session_invalid")
        path = self.root / "sessions" / (session_id + ".json")
        if path.is_symlink():
            raise PluginError("plugin_storage_unsafe", 503)
        if path.exists():
            return _private_json(path)
        if self.data.get("deferred_updates"):
            raise PluginError("plugin_version_activation_deferred", 409)
        snapshot = {
            "plugins": [self.detail(digest) for digest in sorted(self.data["active"].values())]
        }
        if any(
            component.get("projected") and not component["ready"]
            for plugin in snapshot["plugins"]
            for component in plugin["components"]
        ):
            raise PluginError("plugin_native_discovery_pending", 409)
        for plugin in snapshot["plugins"]:
            package = self._archive(plugin["digest"])
            for component in plugin["components"]:
                if component["ready"] and component["kind"] in {
                    "skill",
                    "workflow",
                    "command",
                    "agent",
                }:
                    component["instructions"] = self._draft(package, component)["instructions"]
        _atomic(path, snapshot)
        return snapshot

    def before_message(self, session_id, text):
        snapshot = self.pin(session_id)
        hooks = []
        for plugin in snapshot["plugins"]:
            for component in plugin["components"]:
                if component["kind"] == "hook" and component["ready"]:
                    if not self.version_authorized(plugin["digest"]):
                        raise PluginError("plugin_hook_authorization_revoked", 403)
                    if component["policy"].get("type") == "script":
                        continue
                    hooks.append(
                        (
                            component["policy"].get("order", 0),
                            plugin["digest"],
                            component["key"],
                            component["policy"],
                        )
                    )
        for _, digest, _, hook in sorted(hooks):
            log.info("plugin_lifecycle_policy", digest=digest, decision=hook["decision"])
            if hook["decision"] != "allow":
                raise PluginError(
                    "plugin_hook_" + ("denied" if hook["decision"] == "deny" else "cancelled"), 403
                )
        return snapshot

    async def before_message_async(self, session_id, text, session_root, cancel=None):
        snapshot = self.pin(session_id)
        from .sandbox_runner import run_script

        hooks = []
        for plugin in snapshot["plugins"]:
            for component in plugin["components"]:
                policy = component.get("policy") or {}
                if component["kind"] == "hook" and component["ready"]:
                    if not self.version_authorized(plugin["digest"]):
                        raise PluginError("plugin_hook_authorization_revoked", 403)
                    hooks.append(
                        (policy.get("order", 0), plugin["digest"], component["key"], component)
                    )
        for _, digest, _, component in sorted(hooks):
            policy = component["policy"]
            if policy.get("type") == "script":
                package = self._archive(digest)
                result = await run_script(
                    package["files"][component["path"]],
                    timeout=policy.get("timeout", 2),
                    read_paths=[session_root / scope for scope in policy.get("read", [])],
                    write_paths=[session_root / scope for scope in policy.get("write", [])],
                    cancel=cancel,
                )
            else:
                result = policy
            if result["decision"] != "allow":
                raise PluginError(
                    "plugin_hook_" + ("denied" if result["decision"] == "deny" else "cancelled"),
                    403,
                )
        return snapshot

    def hook_cancellation(self, session_id):
        event = asyncio.Event()
        self.hook_cancellations[session_id] = event
        return event

    def cancel_hook(self, session_id):
        event = self.hook_cancellations.get(session_id)
        if event is not None:
            event.set()

    def command(self, session_id, text):
        if not isinstance(text, str) or not text.startswith("/"):
            return None
        head, _, arguments = text.partition(" ")
        if ":" not in head:
            return None
        plugin_name, command_name = head[1:].split(":", 1)
        snapshot = self.pin(session_id)
        for plugin in snapshot["plugins"]:
            if plugin["name"] != plugin_name:
                continue
            if not self.version_authorized(plugin["digest"]):
                raise PluginError("plugin_command_authorization_revoked", 403)
            for component in plugin["components"]:
                if (
                    component["kind"] == "command"
                    and component["key"] == command_name
                    and component["ready"]
                ):
                    return {
                        "text": component["instructions"].replace("$ARGUMENTS", arguments),
                        "capability": component["native_binding"],
                    }
        raise PluginError("plugin_command_unavailable", 409)

    async def mcp_preview(self, digest, key):
        row = self._reviewed(digest)
        if self.mcp is None:
            raise PluginError("plugin_mcp_loader_unavailable", 503)
        component = next(
            (
                c
                for c in row["components"]
                if c["kind"] == "mcp" and c["key"] == key and c.get("selection")
            ),
            None,
        )
        if component is None:
            raise PluginError("plugin_mcp_component_not_found", 404)
        from ..mcp_runtime.models import InstallationSelection

        preview = await self.mcp.preview(
            InstallationSelection.model_validate(component["selection"])
        )
        # Native confirmation tokens are ephemeral and package-bound here;
        # credentials are accepted only by native MCP, never this package store.
        self._mcp_pending = getattr(self, "_mcp_pending", {})
        self._mcp_pending[(digest, key)] = preview["confirmation_token"]
        return preview

    async def mcp_install(self, digest, key, token, environment_values):
        row = self._reviewed(digest)
        if getattr(self, "_mcp_pending", {}).get((digest, key)) != token:
            raise PluginError("plugin_mcp_confirmation_invalid", 409)
        if key in row["mcp_bindings"]:
            raise PluginError("plugin_mcp_already_installed", 409)
        result = await self.mcp.install(token, environment_values)
        row["mcp_bindings"][key] = result["installation"]["id"]
        self.save()  # Ownership survives an uncertain launcher/fingerprint step.
        from .mcp_policy import native_fingerprint, register_managed

        native_runtime = self.mcp.runtime if hasattr(self.mcp, "runtime") else self.mcp
        register_managed(self.root.parent, result["installation"]["id"])
        if hasattr(native_runtime, "_resolve_target"):
            await native_runtime._resolve_target(
                native_runtime._manifest(result["installation"]["id"])
            )
        row.setdefault("mcp_reviews", {})[key] = native_fingerprint(
            self.root.parent, result["installation"]
        )
        self._mcp_pending.pop((digest, key))
        self.save()
        return result

    def mcp_review_snapshot(self, digest, key):
        row = self._reviewed(digest)
        installation = row["mcp_bindings"].get(key)
        if installation is None:
            raise PluginError("plugin_mcp_component_not_found", 404)
        from .mcp_policy import native_fingerprint

        native = (
            self.mcp.runtime._manifest(installation)
            if hasattr(self.mcp, "runtime")
            else self.mcp._manifest(installation)
        )
        return {
            "installation_id": installation,
            "fingerprint": native_fingerprint(
                self.root.parent, native, self.mcp.capabilities(installation)
            ),
            "capabilities": self.mcp.capabilities(installation),
        }

    def mcp_review(self, digest, key, expected=None):
        """Second explicit review binds the discovered native schema, not secrets."""
        row = self._reviewed(digest)
        installation = row["mcp_bindings"].get(key)
        if installation is None:
            raise PluginError("plugin_mcp_component_not_found", 404)
        current = self.mcp_review_snapshot(digest, key)["fingerprint"]
        if expected is None or expected != current:
            raise PluginError("plugin_mcp_review_snapshot_changed", 409)
        row.setdefault("mcp_reviews", {})[key] = current
        self.save()
        return {"installation_id": installation, "review": copy.deepcopy(row["mcp_reviews"][key])}

    async def uninstall(self, digest):
        row = self._row(digest)
        await self._idle()
        for path in (self.root / "sessions").glob("*.json"):
            if path.is_symlink():
                raise PluginError("plugin_storage_unsafe", 503)
            if any(plugin["digest"] == digest for plugin in _private_json(path)["plugins"]):
                raise PluginError("plugin_version_pinned", 409)
        await self.disable(digest)
        for installation in row["mcp_bindings"].values():
            await self.mcp.delete(installation)
        target = self.root / "versions" / digest
        self._archive(digest)
        if {path.name for path in target.iterdir()} != {"package.zip"}:
            raise PluginError("plugin_storage_unsafe", 503)
        shutil.rmtree(target)
        del self.data["versions"][digest]
        self.save()
        # Native immutable capability history is retained by its owner. Disabled
        # versions cannot be deleted behind CapabilityCatalog's lifecycle.
        log.info("plugin_uninstalled", digest=digest)
        return {"digest": digest, "removed": True, "native_history_retained": True}
