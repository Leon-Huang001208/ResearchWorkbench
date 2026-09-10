"""Security contracts for MCP tool authorization and private Host control."""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest


def _authorization_module():
    spec = importlib.util.find_spec("app.research_web.mcp_runtime.authorization")
    assert spec is not None, "MCP authorization module is not implemented"
    return importlib.import_module("app.research_web.mcp_runtime.authorization")


def _control_module():
    spec = importlib.util.find_spec("app.research_web.mcp_runtime.control")
    assert spec is not None, "MCP control module is not implemented"
    return importlib.import_module("app.research_web.mcp_runtime.control")


def object_schema(**properties):
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }


def manager(tmp_path: Path):
    module = _authorization_module()
    cls = getattr(module, "AuthorizationManager", None)
    assert cls is not None, "AuthorizationManager is not implemented"
    return module, cls(tmp_path)


def registered_tool(tmp_path: Path, *, risk_tier="read_only", allow_unattended=False):
    module, authorization = manager(tmp_path)
    input_schema = object_schema(query={"type": "string"})
    output_schema = object_schema(result={"type": "string"})
    snapshot = authorization.register_tool(
        installation_id="weather_server",
        version="1.2.3",
        tool_name="search_weather",
        input_schema=input_schema,
        output_schema=output_schema,
        risk_tier=risk_tier,
        annotations={"readOnlyHint": True},
        allow_unattended=allow_unattended,
    )
    grant = authorization.authorize_session(
        session_id="11111111-1111-4111-8111-111111111111",
        installation_id="weather_server",
        version="1.2.3",
        tool_name="search_weather",
        schema_sha256=snapshot["schema_sha256"],
    )
    assert (
        authorization.has_session_authorization(
            session_id="11111111-1111-4111-8111-111111111111",
            installation_id="weather_server",
        )
        is True
    )
    allowlist = module.ExactToolAllowlist(
        [
            {
                "name": "mcp__weather_server__search_weather",
                "installation_id": "weather_server",
                "version": "1.2.3",
                "schema_sha256": snapshot["schema_sha256"],
            }
        ]
    )
    return module, authorization, snapshot, grant, allowlist, input_schema, output_schema


def test_schema_hash_is_canonical_and_covers_input_and_output():
    module = _authorization_module()
    digest = getattr(module, "canonical_schema_hash", None)
    assert callable(digest), "canonical_schema_hash is not implemented"
    left = digest(
        {"properties": {"x": {"type": "string"}}, "type": "object"},
        {"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )
    right = digest(
        {"type": "object", "properties": {"x": {"type": "string"}}},
        {"properties": {"ok": {"type": "boolean"}}, "type": "object"},
    )
    assert left == right
    assert left != digest(
        {"type": "object", "properties": {"x": {"type": "string"}}},
        {"type": "object", "properties": {"ok": {"type": "string"}}},
    )


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "https://schemas.example.test/tool.json"},
        {"$ref": "//schemas.example.test/tool.json"},
        {"type": "string", "description": "x" * (70 * 1024)},
    ],
)
def test_schema_hash_rejects_external_refs_and_oversized_schemas(schema):
    module = _authorization_module()
    error = getattr(module, "AuthorizationError", RuntimeError)
    with pytest.raises(error):
        module.canonical_schema_hash(schema, None)


def test_schema_hash_rejects_excessive_depth():
    module = _authorization_module()
    schema: dict = {"type": "object"}
    cursor = schema
    for _ in range(40):
        child = {"type": "object"}
        cursor["properties"] = {"child": child}
        cursor = child
    with pytest.raises(module.AuthorizationError):
        module.canonical_schema_hash(schema, None)


def test_third_party_read_only_hint_does_not_lower_default_risk(tmp_path):
    _, authorization = manager(tmp_path)
    snapshot = authorization.register_tool(
        installation_id="weather_server",
        version="1.2.3",
        tool_name="search_weather",
        input_schema=object_schema(),
        output_schema=None,
        annotations={"readOnlyHint": True},
    )
    assert snapshot["risk_tier"] == "external_write_high_risk"
    classified = authorization.classify_tool(
        "weather_server", "search_weather", risk_tier="read_only", allow_unattended=True
    )
    assert classified["risk_tier"] == "read_only"
    assert classified["allow_unattended"] is True


def test_version_or_schema_drift_pauses_old_grants(tmp_path):
    _, authorization, snapshot, grant, _, _, _ = registered_tool(tmp_path)
    changed = authorization.register_tool(
        installation_id="weather_server",
        version="1.2.4",
        tool_name="search_weather",
        input_schema=object_schema(query={"type": "string"}, units={"type": "string"}),
        output_schema=None,
        risk_tier="read_only",
    )
    assert changed["schema_sha256"] != snapshot["schema_sha256"]
    assert authorization.grant(grant["id"])["status"] == "paused_drift"
    with pytest.raises(authorization.error_type) as error:
        authorization.authorize_session(
            session_id=grant["session_id"],
            installation_id="weather_server",
            version="1.2.3",
            tool_name="search_weather",
            schema_sha256=snapshot["schema_sha256"],
        )
    assert error.value.code == "mcp_schema_drift"


def test_private_data_requires_an_exact_active_session_grant(tmp_path):
    module, authorization = manager(tmp_path)
    input_schema = object_schema(query={"type": "string"})
    snapshot = authorization.register_tool(
        installation_id="private_server",
        version="2.0.0",
        tool_name="private_search",
        input_schema=input_schema,
        output_schema=None,
        risk_tier="private_data",
    )
    allowlist = module.ExactToolAllowlist(
        [
            {
                "name": "mcp__private_server__private_search",
                "installation_id": "private_server",
                "version": "2.0.0",
                "schema_sha256": snapshot["schema_sha256"],
            }
        ]
    )
    with pytest.raises(module.AuthorizationError) as error:
        authorization.admit_call(
            call_id="call-private-1",
            session_id="11111111-1111-4111-8111-111111111111",
            installation_id="private_server",
            version="2.0.0",
            tool_name="private_search",
            input_schema=input_schema,
            output_schema=None,
            arguments={"query": "portfolio"},
            allowlist=allowlist,
        )
    assert error.value.code == "mcp_authorization_required"


def test_high_risk_approval_is_once_and_bound_to_argument_hash(tmp_path):
    module, authorization, _, _, allowlist, input_schema, output_schema = registered_tool(
        tmp_path, risk_tier="external_write_high_risk"
    )
    request = {
        "call_id": "call-high-risk-1",
        "session_id": "11111111-1111-4111-8111-111111111111",
        "installation_id": "weather_server",
        "version": "1.2.3",
        "tool_name": "search_weather",
        "input_schema": input_schema,
        "output_schema": output_schema,
        "arguments": {"query": "Shanghai"},
        "allowlist": allowlist,
    }
    pending = authorization.admit_call(**request)
    assert pending["allowed"] is False
    approval_id = pending["approval_id"]
    persisted = json.loads((tmp_path / "mcp-runtime" / "authorizations.json").read_text())
    serialized = json.dumps(persisted, ensure_ascii=False)
    assert "Shanghai" not in serialized
    assert "arguments" not in persisted["approvals"][approval_id]

    authorization.approve(approval_id, session_id=request["session_id"])
    changed = {**request, "arguments": {"query": "Beijing"}, "approval_id": approval_id}
    with pytest.raises(module.AuthorizationError) as error:
        authorization.admit_call(**changed)
    assert error.value.code == "mcp_approval_mismatch"

    allowed = authorization.admit_call(**request, approval_id=approval_id)
    assert allowed["allowed"] is True
    with pytest.raises(module.AuthorizationError) as replay:
        authorization.admit_call(**request, approval_id=approval_id)
    assert replay.value.code == "mcp_approval_consumed"


def test_unattended_requires_read_only_policy_and_exact_lock(tmp_path):
    module, authorization, snapshot, _, allowlist, input_schema, output_schema = registered_tool(
        tmp_path, risk_tier="read_only", allow_unattended=True
    )
    exact_lock = {
        "installation_id": "weather_server",
        "version": "1.2.3",
        "tool_name": "search_weather",
        "schema_sha256": snapshot["schema_sha256"],
    }
    result = authorization.admit_call(
        call_id="call-unattended-1",
        session_id="11111111-1111-4111-8111-111111111111",
        installation_id="weather_server",
        version="1.2.3",
        tool_name="search_weather",
        input_schema=input_schema,
        output_schema=output_schema,
        arguments={"query": "Shanghai"},
        allowlist=allowlist,
        unattended=True,
        automation_lock=exact_lock,
    )
    assert result["allowed"] is True

    with pytest.raises(module.AuthorizationError) as error:
        authorization.admit_call(
            call_id="call-unattended-2",
            session_id="11111111-1111-4111-8111-111111111111",
            installation_id="weather_server",
            version="1.2.3",
            tool_name="search_weather",
            input_schema=input_schema,
            output_schema=output_schema,
            arguments={"query": "Shanghai"},
            allowlist=allowlist,
            unattended=True,
            automation_lock={**exact_lock, "version": "1.2.4"},
        )
    assert error.value.code == "mcp_unattended_denied"


def test_exact_allowlist_rejects_prefix_only_or_schema_mismatch(tmp_path):
    module = _authorization_module()
    allowlist = module.ExactToolAllowlist(
        [
            {
                "name": "mcp__weather_server__search_weather",
                "installation_id": "weather_server",
                "version": "1.2.3",
                "schema_sha256": "a" * 64,
            }
        ]
    )
    assert allowlist.allows(
        "mcp__weather_server__search_weather", "weather_server", "1.2.3", "a" * 64
    )
    assert not allowlist.allows("mcp__weather_server__other", "weather_server", "1.2.3", "a" * 64)
    assert not allowlist.allows(
        "mcp__weather_server__search_weather", "weather_server", "1.2.3", "b" * 64
    )


def test_active_bindings_keep_verified_schema_and_approval_denial_is_safe(tmp_path):
    _, authorization, snapshot, _, _, input_schema, _ = registered_tool(
        tmp_path, risk_tier="external_write_high_risk"
    )
    bindings = authorization.active_bindings()
    assert bindings == [
        {
            "name": "mcp__weather_server__search_weather",
            "installation_id": "weather_server",
            "version": "1.2.3",
            "tool_name": "search_weather",
            "schema_sha256": snapshot["schema_sha256"],
            "description": "",
            "input_schema": input_schema,
        }
    ]
    pending = authorization.admit_call(
        call_id="call-deny-1",
        session_id="11111111-1111-4111-8111-111111111111",
        installation_id="weather_server",
        version="1.2.3",
        tool_name="search_weather",
        input_schema=input_schema,
        output_schema=object_schema(result={"type": "string"}),
        arguments={"query": "sensitive value"},
        allowlist=_authorization_module().ExactToolAllowlist(bindings),
    )
    approval = authorization.deny(
        pending["approval_id"], session_id="11111111-1111-4111-8111-111111111111"
    )
    assert approval["status"] == "denied"
    projected = authorization.list_approvals()
    assert "arguments_sha256" not in projected[0]
    assert "sensitive value" not in json.dumps(projected)


def test_authorization_store_fails_closed_for_existing_unsafe_file(tmp_path):
    module = _authorization_module()
    runtime = tmp_path / "mcp-runtime"
    runtime.mkdir(mode=0o700)
    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps({"schema_version": 1, "tools": {}, "grants": {}, "approvals": {}})
    )
    (runtime / "authorizations.json").symlink_to(outside)

    with pytest.raises(module.AuthorizationError) as error:
        module.AuthorizationManager(tmp_path)
    assert error.value.code == "mcp_authorization_storage_invalid"


def test_control_token_is_private_independent_and_constant_time_verified(tmp_path):
    module = _control_module()
    control = module.load_control(tmp_path, "http://127.0.0.1:8088")
    path = tmp_path / ".control" / "mcp-runtime.json"
    assert path.is_file() and not path.is_symlink()
    assert control["url"] == "http://127.0.0.1:8088"
    assert module.authenticate(control, control["token"]) is True
    assert module.authenticate(control, "not-the-token") is False
    assert module.authenticate(control, None) is False
    assert "mcp-runtime" in path.name


def test_control_rejects_alias_and_never_overwrites_existing_origin(tmp_path):
    module = _control_module()
    module.load_control(tmp_path, "http://127.0.0.1:8088")
    with pytest.raises(module.ControlError):
        module.load_control(tmp_path, "http://127.0.0.1:9999")

    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    path = tmp_path / ".control" / "mcp-runtime.json"
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(module.ControlError):
        module.load_control(tmp_path, "http://127.0.0.1:8088")
