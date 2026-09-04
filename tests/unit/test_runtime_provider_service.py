"""Runtime routing and Skill authorization behavior tests."""

from datetime import UTC, datetime

import pytest

from core.contracts.research_workspace import (
    ProviderExecutionResult,
    ProviderTerminalStatus,
    RuntimeProvider,
    SkillManifest,
)
from services.runtime_provider_service import (
    AuthorizedResearchToolDispatcher,
    ProductionResearchExecutionAdapters,
    RuntimeBlockedError,
    RuntimeFailedError,
    RuntimeProviderService,
)

NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def _provider(provider_id: str, provider_type: str, capabilities: set[str], status="healthy"):
    return RuntimeProvider(
        provider_id=provider_id,
        provider_type=provider_type,
        name=provider_id,
        capabilities=capabilities,
        status=status,
        checked_at=NOW,
    )


def test_fingpt_falls_back_from_failed_dsh_to_langgraph():
    service = RuntimeProviderService(
        providers=[
            _provider("dsh", "dsh", {"single_agent"}),
            _provider("langgraph", "langgraph", {"single_agent", "resume"}),
        ]
    )
    calls: list[str] = []

    def invoke(provider: RuntimeProvider) -> str:
        calls.append(provider.provider_id)
        if provider.provider_type == "dsh":
            raise TimeoutError("sidecar timeout")
        return "completed"

    result = service.execute("fingpt", {"single_agent"}, invoke)
    assert result.output == "completed"
    assert result.provider_id == "langgraph"
    assert result.fallback_from == "dsh"
    assert calls == ["dsh", "langgraph"]


def test_claw_does_not_semantically_fallback_without_agent_team_capability():
    service = RuntimeProviderService(
        providers=[_provider("langgraph", "langgraph", {"single_agent", "resume"})]
    )
    with pytest.raises(RuntimeBlockedError) as exc:
        service.route("claw", {"agent_team"})
    assert exc.value.code == "blocked_runtime"


def test_skill_execution_revalidates_platform_registry_and_closed_internal_set():
    service = RuntimeProviderService(providers=[])
    safe = SkillManifest(
        skill_key="snapshot",
        name="Snapshot",
        version="1.0.0",
        prompt_template="Analyze {{asset_id}}",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        allowed_tools=["internal:asset_snapshot", "mcp:approved"],
    )
    assert (
        service.compile_skill(
            safe,
            authorized_tool_ids={"internal:asset_snapshot", "mcp:approved"},
        ).skill_key
        == "snapshot"
    )

    unsafe = safe.model_copy(update={"allowed_tools": ["internal:shell"]})
    with pytest.raises(ValueError, match="safe internal tool allowlist"):
        service.compile_skill(unsafe, authorized_tool_ids={"internal:shell"})


def test_skill_execution_validates_input_output_and_sensitive_values_before_return():
    manifest = SkillManifest(
        skill_key="snapshot",
        name="Snapshot",
        version="1.0.0",
        prompt_template="Analyze {{asset_id}}",
        input_schema={
            "type": "object",
            "required": ["asset_id"],
            "properties": {"asset_id": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        },
        allowed_tools=["internal:asset_snapshot"],
        status="enabled",
    )
    service = RuntimeProviderService(providers=[])

    with pytest.raises(ValueError, match="input_schema"):
        service.execute_skill(
            manifest,
            {},
            lambda _payload, _context: {"summary": "ok"},
            authorized_tool_ids={"internal:asset_snapshot"},
        )
    with pytest.raises(ValueError, match="sensitive"):
        service.execute_skill(
            manifest,
            {"asset_id": "600519.SH"},
            lambda _payload, _context: {"summary": "Bearer super-secret-token"},
            authorized_tool_ids={"internal:asset_snapshot"},
        )


def test_dsh_provider_result_is_typed_and_idempotent(db_session):
    from data_layer.repositories.research_workspace_repository import (
        ResearchWorkspaceRepository,
    )

    repository = ResearchWorkspaceRepository(db_session)
    repository.save_runtime_provider(_provider("dsh-callback", "dsh", {"single_agent"}))
    service = RuntimeProviderService(repository=repository)
    result = ProviderExecutionResult(
        provider_id="dsh-callback",
        provider_result_id="provider-result-1",
        request_id="run-1:0",
        run_id="run-1",
        request_hash="sha256:a",
        terminal_status=ProviderTerminalStatus.COMPLETED,
        output={"summary": "完成"},
    )
    first = service.accept_provider_result(result, request_hash="sha256:a")
    duplicate = service.accept_provider_result(result, request_hash="sha256:a")
    assert duplicate == first

    with pytest.raises(ValueError, match="conflict"):
        service.accept_provider_result(
            result.model_copy(update={"output": {"summary": "篡改"}}),
            request_hash="sha256:b",
        )


def test_skill_executes_sync_sandbox_with_budget_context_and_full_schema_keywords():
    manifest = SkillManifest(
        skill_key="bounded-schema",
        name="Bounded schema",
        version="1.0.0",
        prompt_template="Classify",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["score", "ticker"],
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 100},
                "ticker": {"type": "string", "pattern": "^[0-9]{6}\\.(SH|SZ)$"},
            },
        },
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["rating"],
            "properties": {"rating": {"type": "string", "enum": ["buy", "hold"]}},
        },
        status="enabled",
    )
    contexts: list[dict] = []

    result = RuntimeProviderService(providers=[]).execute_skill(
        manifest,
        {"score": 80, "ticker": "600519.SH"},
        lambda _payload, context: contexts.append(context) or {"rating": "buy"},
        authorized_tool_ids=set(),
        deadline_seconds=12,
        reserve_tokens=256,
        remaining_tokens=512,
        reserve_cost=0.2,
        remaining_cost=1,
    )

    assert result == {"rating": "buy"}
    assert contexts == [
        {
            "reserved_tokens": 256,
            "reserved_cost": 0.2,
            "remaining_seconds": 12,
        }
    ]
    for bad_input in (
        {"score": -1, "ticker": "600519.SH"},
        {"score": 80, "ticker": "../../etc/passwd"},
        {"score": 80, "ticker": "600519.SH", "unexpected": True},
    ):
        with pytest.raises(ValueError, match="input_schema"):
            RuntimeProviderService(providers=[]).execute_skill(
                manifest,
                bad_input,
                lambda _payload, _context: {"rating": "buy"},
                authorized_tool_ids=set(),
                reserve_tokens=256,
            )
    with pytest.raises(ValueError, match="output_schema"):
        RuntimeProviderService(providers=[]).execute_skill(
            manifest,
            {"score": 80, "ticker": "600519.SH"},
            lambda _payload, _context: {"rating": "sell"},
            authorized_tool_ids=set(),
            reserve_tokens=256,
        )


def test_typed_failed_provider_never_falls_back_and_blocked_keeps_error_code():
    providers = [
        _provider("dsh", "dsh", {"single_agent"}),
        _provider("langgraph", "langgraph", {"single_agent"}),
    ]
    calls: list[str] = []

    def failed(provider):
        calls.append(provider.provider_id)
        return ProviderExecutionResult(
            provider_id="dsh",
            provider_result_id="result-failed",
            request_id="request-1",
            run_id="run-1",
            request_hash="sha256:failed",
            terminal_status=ProviderTerminalStatus.FAILED,
            error_code="provider_crashed",
        )

    with pytest.raises(RuntimeFailedError) as failed_error:
        RuntimeProviderService(providers=providers).execute("fingpt", {"single_agent"}, failed)
    assert failed_error.value.code == "provider_crashed"
    assert calls == ["dsh"]

    def blocked(_provider):
        return ProviderExecutionResult(
            provider_id="dsh",
            provider_result_id="result-blocked",
            request_id="request-2",
            run_id="run-2",
            request_hash="sha256:blocked",
            terminal_status=ProviderTerminalStatus.BLOCKED,
            error_code="provider_policy_blocked",
        )

    with pytest.raises(RuntimeBlockedError) as blocked_error:
        RuntimeProviderService(providers=providers).execute("fingpt", {"single_agent"}, blocked)
    assert blocked_error.value.code == "provider_policy_blocked"


def test_production_agent_rejects_gateway_error_and_charges_estimated_cost():
    from services.agent_team_service import AgentAssignment

    class Response:
        def __init__(self, content, tokens_used=20):
            self.content = content
            self.tokens_used = tokens_used
            self.provider = "test-provider"
            self.model_name = "test-model"

    class Gateway:
        def __init__(self, responses):
            self.responses = iter(responses)
            self.calls = []

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return next(self.responses)

    assignment = AgentAssignment(
        role="analyst",
        task={"question": "供需"},
        reserve_tokens=100,
        reserve_cost=1,
        remaining_seconds=10,
    )
    failing = ProductionResearchExecutionAdapters(
        model_gateway=Gateway([Response("Error: provider unavailable", 0)]),
        cost_estimator=lambda response: response.tokens_used * 0.001,
    )
    with pytest.raises(RuntimeFailedError, match="gateway"):
        failing.invoke_agent(assignment)

    valid_gateway = Gateway([Response('{"summary":"完成"}', 20)])
    valid = ProductionResearchExecutionAdapters(
        model_gateway=valid_gateway,
        cost_estimator=lambda response: response.tokens_used * 0.001,
    ).invoke_agent(assignment)
    assert valid.payload == {"summary": "完成"}
    assert valid.tokens_used == 20
    assert valid.cost_used == pytest.approx(0.02)
    assert "blackboard_snapshot" in valid_gateway.calls[0]["messages"][1]["content"]


@pytest.mark.parametrize("content", ["Error: quota exceeded", "not-json"])
def test_production_skill_rejects_gateway_error_or_non_json(content):
    class Response:
        provider = "test-provider"
        model_name = "test-model"
        tokens_used = 10

        def __init__(self, value):
            self.content = value

    class Gateway:
        def chat(self, **_kwargs):
            return Response(content)

    manifest = SkillManifest(
        skill_key="strict-json",
        name="Strict JSON",
        version="1.0.0",
        prompt_template="Return JSON",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status="enabled",
    )
    adapters = ProductionResearchExecutionAdapters(
        model_gateway=Gateway(),
        cost_estimator=lambda response: response.tokens_used * 0.001,
    )

    with pytest.raises(RuntimeFailedError):
        adapters.invoke_skill(
            manifest,
            {},
            {"reserved_tokens": 100, "reserved_cost": 1, "remaining_seconds": 10},
        )


def test_registered_mcp_is_dispatched_and_reinjected_before_skill_final_output():
    class Response:
        def __init__(self, content, tokens_used):
            self.content = content
            self.tokens_used = tokens_used
            self.provider = "test-provider"
            self.model_name = "test-model"

    class Gateway:
        def __init__(self):
            self.calls: list[dict] = []
            self.responses = iter(
                [
                    Response(
                        '{"tool_requests":[{"tool_id":"mcp:quotes",'
                        '"arguments":{"asset_id":"600519.SH"}}]}',
                        10,
                    ),
                    Response('{"summary":"价格已核验"}', 15),
                ]
            )

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return next(self.responses)

    tool_calls: list[dict] = []
    dispatcher = AuthorizedResearchToolDispatcher(
        mcp_tools={
            "mcp:quotes": lambda arguments: tool_calls.append(arguments) or {"last_price": 1688.0}
        }
    )
    gateway = Gateway()
    adapters = ProductionResearchExecutionAdapters(
        model_gateway=gateway,
        tool_dispatcher=dispatcher,
        cost_estimator=lambda response: response.tokens_used * 0.001,
    )
    manifest = SkillManifest(
        skill_key="quote-check",
        name="Quote check",
        version="1.0.0",
        prompt_template="核验价格",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        },
        allowed_tools=["mcp:quotes"],
        status="enabled",
    )
    usage = []

    output = RuntimeProviderService(providers=[]).execute_skill(
        manifest,
        {"asset_id": "600519.SH"},
        lambda payload, context: adapters.invoke_skill(manifest, payload, context),
        authorized_tool_ids=dispatcher.authorized_tool_ids,
        reserve_tokens=100,
        remaining_tokens=100,
        reserve_cost=1,
        remaining_cost=1,
        usage_callback=usage.append,
    )

    assert output == {"summary": "价格已核验"}
    assert tool_calls == [{"asset_id": "600519.SH"}]
    assert "last_price" in gateway.calls[1]["messages"][-1]["content"]
    assert usage[0].tokens_used == 25
    assert usage[0].cost_used == pytest.approx(0.025)


def test_skill_does_not_call_tool_or_next_model_after_budget_is_exhausted():
    class GatewayResponse:
        content = (
            '{"tool_requests":[{"tool_id":"mcp:quotes",' '"arguments":{"asset_id":"600519.SH"}}]}'
        )
        tokens_used = 10
        cost_used = 0.1

    class Gateway:
        def __init__(self):
            self.calls = 0

        def chat(self, **_kwargs):
            self.calls += 1
            return GatewayResponse()

    gateway = Gateway()
    tool_calls: list[dict] = []
    dispatcher = AuthorizedResearchToolDispatcher(
        mcp_tools={"mcp:quotes": lambda arguments: tool_calls.append(arguments) or {"last": 1}}
    )
    adapters = ProductionResearchExecutionAdapters(
        model_gateway=gateway,
        tool_dispatcher=dispatcher,
    )
    manifest = SkillManifest(
        skill_key="budget-guard",
        name="Budget guard",
        version="1.0.0",
        prompt_template="Use quotes",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        allowed_tools=["mcp:quotes"],
        status="enabled",
    )

    with pytest.raises(RuntimeBlockedError) as raised:
        adapters.invoke_skill(
            manifest,
            {"asset_id": "600519.SH"},
            {
                "remaining_seconds": 30,
                "reserved_tokens": 10,
                "reserved_cost": 0.1,
            },
        )

    assert raised.value.code == "budget_exhausted"
    assert gateway.calls == 1
    assert tool_calls == []


def test_tool_dispatch_rejects_unregistered_shell_arbitrary_url_and_attachment_ref():
    manifest = SkillManifest(
        skill_key="bounded-tools",
        name="Bounded tools",
        version="1.0.0",
        prompt_template="Use bounded tools",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        allowed_tools=["mcp:quotes", "attachment:read", "web:controlled"],
        attachment_refs=["attachment-allowed"],
        status="enabled",
    )
    dispatcher = AuthorizedResearchToolDispatcher(
        attachment_resolver=lambda ref: {"ref": ref, "text": "safe"},
        controlled_web_policies={"official-filings": lambda args: {"query": args["query"]}},
    )
    for tool_id, arguments, match in (
        ("mcp:quotes", {"asset_id": "600519.SH"}, "not registered"),
        ("internal:shell", {"command": "pwd"}, "not declared"),
        (
            "web:controlled",
            {"policy_id": "official-filings", "url": "https://evil.example"},
            "arbitrary URL",
        ),
        ("attachment:read", {"ref": "../../secret"}, "attachment reference"),
    ):
        with pytest.raises(RuntimeBlockedError, match=match):
            dispatcher.dispatch(manifest, {"tool_id": tool_id, "arguments": arguments})


def test_production_service_wires_real_asset_tool_and_only_preregistered_mcp(
    db_session,
    monkeypatch,
):
    from app.api.routes.research_runs import get_research_run_service
    from data_layer.repositories.models import AssetRegistryDB
    from services import research_tool_registry
    from services.research_tool_registry import (
        ResearchMCPHandlerRegistry,
        build_production_research_tool_dispatcher,
    )

    db_session.add(
        AssetRegistryDB(
            asset_id="asset-production",
            asset_type="stock",
            canonical_name="Production asset",
            status="active",
            registry_metadata={},
            created_at=NOW,
            updated_at=NOW,
        )
    )
    db_session.flush()
    mcp_registry = ResearchMCPHandlerRegistry()
    mcp_registry.register("mcp:approved", lambda arguments: {"echo": arguments["value"]})
    monkeypatch.setattr(research_tool_registry, "_default_mcp_registry", mcp_registry)
    monkeypatch.setenv(
        "RESEARCH_AUTHORIZED_RESEARCH_TOOLS",
        "mcp:approved,mcp:configured-without-handler",
    )

    service = get_research_run_service(db_session)
    dispatcher = build_production_research_tool_dispatcher(
        db_session,
        mcp_registry=mcp_registry,
    )
    asset_manifest = SkillManifest(
        skill_key="asset-production",
        name="Asset production",
        version="1.0.0",
        prompt_template="Read asset",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        allowed_tools=["internal:asset_snapshot"],
        status="enabled",
    )

    snapshot = dispatcher.dispatch(
        asset_manifest,
        {
            "tool_id": "internal:asset_snapshot",
            "arguments": {"asset_id": "asset-production"},
        },
    )

    assert snapshot["asset"]["asset_id"] == "asset-production"
    assert service.authorized_tool_ids == {
        "internal:asset_snapshot",
        "mcp:approved",
    }
    assert "mcp:configured-without-handler" not in service.authorized_tool_ids
