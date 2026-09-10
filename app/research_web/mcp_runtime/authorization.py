"""Fail-closed MCP tool authorization and approval contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from app.research_web.datahub.security import atomic_json, directory, read_file
from app.research_web.store import StoreError
from core.observability import get_logger

log = get_logger(__name__)

MAX_SCHEMA_BYTES = 64 * 1024
MAX_ARGUMENT_BYTES = 256 * 1024
MAX_STATE_BYTES = 4 * 1024 * 1024
MAX_NESTING_DEPTH = 32
MAX_NODES = 8192
RISK_TIERS = frozenset({"read_only", "private_data", "external_write_high_risk"})
HIGHEST_RISK = "external_write_high_risk"
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
SAFE_TOOL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")


class AuthorizationError(RuntimeError):
    """A stable, non-secret authorization failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _canonical_bytes(value: object, *, maximum: int, error_code: str) -> bytes:
    _validate_json(value, error_code=error_code)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise AuthorizationError(error_code) from exc
    if len(encoded) > maximum:
        raise AuthorizationError(error_code)
    return encoded


def _validate_json(value: object, *, error_code: str) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    seen: set[int] = set()
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_NESTING_DEPTH:
            raise AuthorizationError(error_code)
        if isinstance(current, dict):
            identity = id(current)
            if identity in seen:
                raise AuthorizationError(error_code)
            seen.add(identity)
            for key, child in current.items():
                if not isinstance(key, str):
                    raise AuthorizationError(error_code)
                if key == "$ref" and (
                    not isinstance(child, str) or (child != "#" and not child.startswith("#/"))
                ):
                    raise AuthorizationError("mcp_external_schema_ref")
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            identity = id(current)
            if identity in seen:
                raise AuthorizationError(error_code)
            seen.add(identity)
            stack.extend((child, depth + 1) for child in current)
        elif (
            current is None
            or isinstance(current, (str, bool, int))
            or isinstance(current, float)
            and math.isfinite(current)
        ):
            continue
        else:
            raise AuthorizationError(error_code)


def canonical_schema_hash(
    input_schema: dict[str, Any], output_schema: dict[str, Any] | None
) -> str:
    """Hash bounded canonical input and output schemas as one immutable snapshot."""
    if not isinstance(input_schema, dict) or (
        output_schema is not None and not isinstance(output_schema, dict)
    ):
        raise AuthorizationError("mcp_schema_invalid")
    canonical = {"input_schema": input_schema, "output_schema": output_schema}
    return hashlib.sha256(
        _canonical_bytes(canonical, maximum=MAX_SCHEMA_BYTES, error_code="mcp_schema_invalid")
    ).hexdigest()


def _arguments_hash(arguments: dict[str, Any]) -> str:
    if not isinstance(arguments, dict):
        raise AuthorizationError("mcp_arguments_invalid")
    return hashlib.sha256(
        _canonical_bytes(
            arguments,
            maximum=MAX_ARGUMENT_BYTES,
            error_code="mcp_arguments_invalid",
        )
    ).hexdigest()


def _checked_identifier(value: str, *, tool: bool = False) -> str:
    pattern = SAFE_TOOL_NAME if tool else SAFE_IDENTIFIER
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise AuthorizationError("mcp_identifier_invalid")
    return value


def _id_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _tool_key(installation_id: str, tool_name: str) -> str:
    return hashlib.sha256(f"{installation_id}\0{tool_name}".encode()).hexdigest()


class ExactToolAllowlist:
    """Immutable allowlist keyed by the complete DSH tool namespace."""

    def __init__(self, bindings: list[dict[str, str]]) -> None:
        entries: dict[str, tuple[str, str, str]] = {}
        if not isinstance(bindings, list):
            raise AuthorizationError("mcp_allowlist_invalid")
        for binding in bindings:
            try:
                name = binding["name"]
                installation_id = _checked_identifier(binding["installation_id"])
                version = _checked_identifier(binding["version"])
                tool_name = name.removeprefix(f"mcp__{installation_id}__")
                _checked_identifier(tool_name, tool=True)
                schema_sha256 = binding["schema_sha256"]
            except (KeyError, TypeError, AttributeError) as exc:
                raise AuthorizationError("mcp_allowlist_invalid") from exc
            if (
                name != f"mcp__{installation_id}__{tool_name}"
                or not re.fullmatch(r"[a-f0-9]{64}", schema_sha256)
                or name in entries
            ):
                raise AuthorizationError("mcp_allowlist_invalid")
            entries[name] = (installation_id, version, schema_sha256)
        self._entries = entries

    def allows(
        self,
        name: str,
        installation_id: str,
        version: str,
        schema_sha256: str,
    ) -> bool:
        expected = self._entries.get(name)
        candidate = (installation_id, version, schema_sha256)
        return expected is not None and all(
            hmac.compare_digest(left, right)
            for left, right in zip(expected, candidate, strict=True)
        )


class AuthorizationManager:
    """Persist exact tool snapshots, session grants, and one-use approvals."""

    error_type = AuthorizationError

    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root)
        self._lock = RLock()
        self._state = self._load()

    def register_tool(
        self,
        *,
        installation_id: str,
        version: str,
        tool_name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None,
        risk_tier: str | None = None,
        annotations: dict[str, Any] | None = None,
        description: str = "",
        allow_unattended: bool = False,
    ) -> dict[str, Any]:
        """Register a verified schema; untrusted annotations never lower risk."""
        del annotations
        installation_id = _checked_identifier(installation_id)
        version = _checked_identifier(version)
        tool_name = _checked_identifier(tool_name, tool=True)
        digest = canonical_schema_hash(input_schema, output_schema)
        if (
            not isinstance(description, str)
            or len(description) > 2000
            or any(ord(character) < 32 and character not in "\t\n" for character in description)
        ):
            raise AuthorizationError("mcp_description_invalid")
        # Break references to objects returned by the untrusted server. The
        # canonical validation above also rejects non-JSON values and cycles.
        stored_input_schema = json.loads(
            _canonical_bytes(
                input_schema,
                maximum=MAX_SCHEMA_BYTES,
                error_code="mcp_schema_invalid",
            )
        )
        stored_output_schema = (
            json.loads(
                _canonical_bytes(
                    output_schema,
                    maximum=MAX_SCHEMA_BYTES,
                    error_code="mcp_schema_invalid",
                )
            )
            if output_schema is not None
            else None
        )
        key = _tool_key(installation_id, tool_name)
        with self._lock:
            previous = self._state["tools"].get(key)
            unchanged = previous is not None and (
                previous["version"] == version and previous["schema_sha256"] == digest
            )
            if risk_tier is None:
                selected_risk = previous["risk_tier"] if unchanged else HIGHEST_RISK
                selected_unattended = previous["allow_unattended"] if unchanged else False
            else:
                selected_risk = self._checked_risk(risk_tier)
                selected_unattended = self._checked_unattended(selected_risk, allow_unattended)
            snapshot = {
                "id": f"mcp-tool-{uuid4().hex}",
                "installation_id": installation_id,
                "version": version,
                "tool_name": tool_name,
                "schema_sha256": digest,
                "description": description,
                "input_schema": stored_input_schema,
                "output_schema": stored_output_schema,
                "risk_tier": selected_risk,
                "allow_unattended": selected_unattended,
                "status": "active",
            }
            if unchanged:
                snapshot["id"] = previous["id"]
            else:
                self._pause_for_drift(installation_id, tool_name)
            self._state["tools"][key] = snapshot
            self._save()
        log.info(
            "mcp_tool_snapshot_registered",
            installation_id_digest=_id_digest(installation_id),
            status="active",
        )
        return dict(snapshot)

    def classify_tool(
        self,
        installation_id: str,
        tool_name: str,
        *,
        risk_tier: str,
        allow_unattended: bool = False,
    ) -> dict[str, Any]:
        installation_id = _checked_identifier(installation_id)
        tool_name = _checked_identifier(tool_name, tool=True)
        selected_risk = self._checked_risk(risk_tier)
        selected_unattended = self._checked_unattended(selected_risk, allow_unattended)
        with self._lock:
            snapshot = self._current(installation_id, tool_name)
            changed = (
                snapshot["risk_tier"] != selected_risk
                or snapshot["allow_unattended"] is not selected_unattended
            )
            snapshot["risk_tier"] = selected_risk
            snapshot["allow_unattended"] = selected_unattended
            if changed:
                self._pause_for_policy_change(installation_id, tool_name)
            self._save()
            return dict(snapshot)

    def authorize_session(
        self,
        *,
        session_id: str,
        installation_id: str,
        version: str,
        tool_name: str,
        schema_sha256: str,
    ) -> dict[str, Any]:
        session_id = _checked_identifier(session_id)
        installation_id = _checked_identifier(installation_id)
        version = _checked_identifier(version)
        tool_name = _checked_identifier(tool_name, tool=True)
        with self._lock:
            snapshot = self._current(installation_id, tool_name)
            if snapshot["version"] != version or not hmac.compare_digest(
                snapshot["schema_sha256"], schema_sha256
            ):
                raise AuthorizationError("mcp_schema_drift")
            grant = {
                "id": f"mcp-grant-{uuid4().hex}",
                "session_id": session_id,
                "installation_id": installation_id,
                "version": version,
                "tool_name": tool_name,
                "schema_sha256": schema_sha256,
                "risk_tier": snapshot["risk_tier"],
                "status": "active",
            }
            self._state["grants"][grant["id"]] = grant
            self._save()
        log.info(
            "mcp_session_authorization_created",
            session_id_digest=_id_digest(session_id),
            status="active",
        )
        return dict(grant)

    def grant(self, grant_id: str) -> dict[str, Any]:
        with self._lock:
            grant = self._state["grants"].get(grant_id)
            if grant is None:
                raise AuthorizationError("mcp_grant_not_found")
            return dict(grant)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return safe verified tool snapshots for management and DSH binding."""

        with self._lock:
            return [
                json.loads(json.dumps(item, ensure_ascii=False))
                for item in self._state["tools"].values()
            ]

    def active_bindings(self, installation_ids: set[str] | None = None) -> list[dict[str, Any]]:
        """Project active snapshots into the exact DSH adapter contract."""

        with self._lock:
            result = []
            for item in self._state["tools"].values():
                if item.get("status") != "active" or (
                    installation_ids is not None
                    and item.get("installation_id") not in installation_ids
                ):
                    continue
                installation_id = item["installation_id"]
                tool_name = item["tool_name"]
                result.append(
                    {
                        "name": f"mcp__{installation_id}__{tool_name}",
                        "installation_id": installation_id,
                        "version": item["version"],
                        "tool_name": tool_name,
                        "schema_sha256": item["schema_sha256"],
                        "description": item.get("description", ""),
                        "input_schema": json.loads(
                            json.dumps(item.get("input_schema", {}), ensure_ascii=False)
                        ),
                    }
                )
            return sorted(result, key=lambda item: item["name"])

    def list_approvals(self, *, session_id: str | None = None) -> list[dict[str, Any]]:
        """List approval metadata without argument hashes or request bodies."""

        if session_id is not None:
            session_id = _checked_identifier(session_id)
        safe_keys = (
            "id",
            "call_id",
            "session_id",
            "installation_id",
            "version",
            "tool_name",
            "schema_sha256",
            "status",
        )
        with self._lock:
            return [
                {key: approval[key] for key in safe_keys if key in approval}
                for approval in self._state["approvals"].values()
                if session_id is None or approval.get("session_id") == session_id
            ]

    def has_session_authorization(self, *, session_id: str, installation_id: str) -> bool:
        """Check whether a session holds any active exact grant for an installation."""

        session_id = _checked_identifier(session_id)
        installation_id = _checked_identifier(installation_id)
        with self._lock:
            return any(
                grant.get("status") == "active"
                and grant.get("session_id") == session_id
                and grant.get("installation_id") == installation_id
                for grant in self._state["grants"].values()
            )

    def approve(self, approval_id: str, *, session_id: str) -> dict[str, Any]:
        session_id = _checked_identifier(session_id)
        with self._lock:
            approval = self._state["approvals"].get(approval_id)
            if approval is None:
                raise AuthorizationError("mcp_approval_not_found")
            if approval["status"] != "pending":
                raise AuthorizationError("mcp_approval_not_pending")
            if not hmac.compare_digest(approval["session_id"], session_id):
                raise AuthorizationError("mcp_approval_session_mismatch")
            approval["status"] = "approved"
            self._save()
            return dict(approval)

    def deny(self, approval_id: str, *, session_id: str) -> dict[str, Any]:
        session_id = _checked_identifier(session_id)
        with self._lock:
            approval = self._state["approvals"].get(approval_id)
            if approval is None:
                raise AuthorizationError("mcp_approval_not_found")
            if approval["status"] != "pending":
                raise AuthorizationError("mcp_approval_not_pending")
            if not hmac.compare_digest(approval["session_id"], session_id):
                raise AuthorizationError("mcp_approval_session_mismatch")
            approval["status"] = "denied"
            self._save()
            return dict(approval)

    def admit_call(
        self,
        *,
        call_id: str,
        session_id: str,
        installation_id: str,
        version: str,
        tool_name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None,
        arguments: dict[str, Any],
        allowlist: ExactToolAllowlist,
        unattended: bool = False,
        automation_lock: dict[str, str] | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        call_id = _checked_identifier(call_id)
        session_id = _checked_identifier(session_id)
        installation_id = _checked_identifier(installation_id)
        version = _checked_identifier(version)
        tool_name = _checked_identifier(tool_name, tool=True)
        schema_sha256 = canonical_schema_hash(input_schema, output_schema)
        arguments_sha256 = _arguments_hash(arguments)
        namespace = f"mcp__{installation_id}__{tool_name}"
        with self._lock:
            snapshot = self._current(installation_id, tool_name)
            if snapshot["version"] != version or not hmac.compare_digest(
                snapshot["schema_sha256"], schema_sha256
            ):
                raise AuthorizationError("mcp_schema_drift")
            if not isinstance(allowlist, ExactToolAllowlist) or not allowlist.allows(
                namespace, installation_id, version, schema_sha256
            ):
                raise AuthorizationError("mcp_tool_not_allowed")
            self._require_grant(session_id, installation_id, version, tool_name, schema_sha256)
            if unattended:
                self._require_unattended(snapshot, automation_lock)
            if snapshot["risk_tier"] == HIGHEST_RISK:
                if unattended:
                    raise AuthorizationError("mcp_unattended_denied")
                if approval_id is None:
                    approval = self._new_approval(
                        call_id,
                        session_id,
                        installation_id,
                        version,
                        tool_name,
                        schema_sha256,
                        arguments_sha256,
                    )
                    self._save()
                    return {"allowed": False, "approval_id": approval["id"]}
                self._consume_approval(
                    approval_id,
                    call_id,
                    session_id,
                    installation_id,
                    version,
                    tool_name,
                    schema_sha256,
                    arguments_sha256,
                )
                self._save()
        log.info(
            "mcp_tool_call_admitted",
            call_id_digest=_id_digest(call_id),
            status="allowed",
        )
        return {"allowed": True}

    def _load(self) -> dict[str, Any]:
        empty = {"schema_version": 1, "tools": {}, "grants": {}, "approvals": {}}
        try:
            self.data_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            with directory(self.data_root, ("mcp-runtime",), create=True, private=True) as folder:
                if "authorizations.json" not in os.listdir(folder):
                    return empty
                raw = read_file(folder, "authorizations.json", private=True, limit=MAX_STATE_BYTES)
            parsed = json.loads(raw)
            if (
                not isinstance(parsed, dict)
                or parsed.get("schema_version") != 1
                or not all(
                    isinstance(parsed.get(name), dict) for name in ("tools", "grants", "approvals")
                )
            ):
                raise ValueError("invalid authorization state")
            return parsed
        except (OSError, StoreError, ValueError, json.JSONDecodeError) as exc:
            log.error("mcp_authorization_state_load_failed", error_type=type(exc).__name__)
            raise AuthorizationError("mcp_authorization_storage_invalid") from exc

    def _save(self) -> None:
        try:
            with directory(self.data_root, ("mcp-runtime",), create=True, private=True) as folder:
                atomic_json(folder, "authorizations.json", self._state)
        except (OSError, StoreError) as exc:
            log.error("mcp_authorization_state_save_failed", error_type=type(exc).__name__)
            raise AuthorizationError("mcp_authorization_storage_unavailable") from exc

    def _current(self, installation_id: str, tool_name: str) -> dict[str, Any]:
        snapshot = self._state["tools"].get(_tool_key(installation_id, tool_name))
        if snapshot is None or snapshot.get("status") != "active":
            raise AuthorizationError("mcp_tool_not_registered")
        return snapshot

    @staticmethod
    def _checked_risk(risk_tier: str) -> str:
        if risk_tier not in RISK_TIERS:
            raise AuthorizationError("mcp_risk_tier_invalid")
        return risk_tier

    @staticmethod
    def _checked_unattended(risk_tier: str, allow_unattended: bool) -> bool:
        if not isinstance(allow_unattended, bool):
            raise AuthorizationError("mcp_unattended_policy_invalid")
        if allow_unattended and risk_tier != "read_only":
            raise AuthorizationError("mcp_unattended_policy_invalid")
        return allow_unattended

    def _pause_for_drift(self, installation_id: str, tool_name: str) -> None:
        for grant in self._state["grants"].values():
            if (
                grant.get("installation_id") == installation_id
                and grant.get("tool_name") == tool_name
                and grant.get("status") == "active"
            ):
                grant["status"] = "paused_drift"
        for approval in self._state["approvals"].values():
            if (
                approval.get("installation_id") == installation_id
                and approval.get("tool_name") == tool_name
                and approval.get("status") in {"pending", "approved"}
            ):
                approval["status"] = "paused_drift"

    def _pause_for_policy_change(self, installation_id: str, tool_name: str) -> None:
        for grant in self._state["grants"].values():
            if (
                grant.get("installation_id") == installation_id
                and grant.get("tool_name") == tool_name
                and grant.get("status") == "active"
            ):
                grant["status"] = "paused_policy"
        for approval in self._state["approvals"].values():
            if (
                approval.get("installation_id") == installation_id
                and approval.get("tool_name") == tool_name
                and approval.get("status") in {"pending", "approved"}
            ):
                approval["status"] = "paused_policy"

    def _require_grant(
        self,
        session_id: str,
        installation_id: str,
        version: str,
        tool_name: str,
        schema_sha256: str,
    ) -> None:
        for grant in self._state["grants"].values():
            if (
                grant.get("status") == "active"
                and grant.get("session_id") == session_id
                and grant.get("installation_id") == installation_id
                and grant.get("version") == version
                and grant.get("tool_name") == tool_name
                and hmac.compare_digest(grant.get("schema_sha256", ""), schema_sha256)
            ):
                return
        raise AuthorizationError("mcp_authorization_required")

    @staticmethod
    def _require_unattended(
        snapshot: dict[str, Any], automation_lock: dict[str, str] | None
    ) -> None:
        expected = {
            "installation_id": snapshot["installation_id"],
            "version": snapshot["version"],
            "tool_name": snapshot["tool_name"],
            "schema_sha256": snapshot["schema_sha256"],
        }
        if (
            snapshot["risk_tier"] != "read_only"
            or snapshot["allow_unattended"] is not True
            or automation_lock != expected
        ):
            raise AuthorizationError("mcp_unattended_denied")

    def _new_approval(
        self,
        call_id: str,
        session_id: str,
        installation_id: str,
        version: str,
        tool_name: str,
        schema_sha256: str,
        arguments_sha256: str,
    ) -> dict[str, Any]:
        approval = {
            "id": f"mcp-approval-{uuid4().hex}",
            "call_id": call_id,
            "session_id": session_id,
            "installation_id": installation_id,
            "version": version,
            "tool_name": tool_name,
            "schema_sha256": schema_sha256,
            "arguments_sha256": arguments_sha256,
            "status": "pending",
        }
        self._state["approvals"][approval["id"]] = approval
        return approval

    def _consume_approval(
        self,
        approval_id: str,
        call_id: str,
        session_id: str,
        installation_id: str,
        version: str,
        tool_name: str,
        schema_sha256: str,
        arguments_sha256: str,
    ) -> None:
        approval = self._state["approvals"].get(approval_id)
        if approval is None:
            raise AuthorizationError("mcp_approval_not_found")
        if approval["status"] == "consumed":
            raise AuthorizationError("mcp_approval_consumed")
        if approval["status"] != "approved":
            raise AuthorizationError("mcp_approval_required")
        expected = (
            call_id,
            session_id,
            installation_id,
            version,
            tool_name,
            schema_sha256,
            arguments_sha256,
        )
        actual = tuple(
            approval[name]
            for name in (
                "call_id",
                "session_id",
                "installation_id",
                "version",
                "tool_name",
                "schema_sha256",
                "arguments_sha256",
            )
        )
        if not all(
            hmac.compare_digest(left, right) for left, right in zip(expected, actual, strict=True)
        ):
            raise AuthorizationError("mcp_approval_mismatch")
        approval["status"] = "consumed"
