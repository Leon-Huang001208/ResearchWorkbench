import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest

from core.contracts.research import (
    ResearchEvidenceInput,
    ResearchRunCreateRequest,
    ResearchRunStatus,
    ResearchSubject,
)
from data_layer.repositories.research_run_repository import ResearchRunRepository
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.research_run_service import ResearchRunService
from services.research_workspace_service import ResearchWorkspaceService
from services.runtime_provider_service import (
    RuntimeBlockedError,
    RuntimeFailedError,
    RuntimeProviderService,
    stable_runtime_request_hash,
)


def _request(*evidence: ResearchEvidenceInput) -> ResearchRunCreateRequest:
    return ResearchRunCreateRequest(
        template_key="a_share_deep_research",
        subject=ResearchSubject(
            subject_type="security",
            subject_id="600519.SH",
            display_name="贵州茅台",
            market="A-share",
        ),
        as_of=datetime(2026, 8, 10, tzinfo=UTC),
        question="贵州茅台的增长叙事是否被最新财报支持？",
        evidence_inputs=list(evidence),
    )


def _evidence(kind: str, claim: str) -> ResearchEvidenceInput:
    return ResearchEvidenceInput(
        evidence_id=f"evidence-{kind}",
        source_ref=f"doc-{kind}",
        source_name="测试来源",
        evidence_kind=kind,
        summary=claim,
        claim_text=claim,
    )


def test_complete_a_share_research_run_publishes_three_projections(db_session):
    service = ResearchRunService(ResearchRunRepository(db_session))
    request = _request(
        _evidence("financial", "经营现金流持续覆盖归母净利润。"),
        _evidence("industry", "高端白酒需求保持韧性。"),
        _evidence("valuation", "当前估值处于近五年中位数附近。"),
        _evidence("risk", "渠道库存上升可能压低盈利质量。"),
        _evidence("consensus", "三家机构对未来两年盈利维持正增长预期。"),
    )

    created = service.create(request)
    completed = service.execute(created.run_id)
    outputs = service.get_outputs(created.run_id)

    assert completed.status is ResearchRunStatus.COMPLETED
    assert outputs.decision_card is not None
    assert outputs.report_markdown is not None
    assert outputs.research_notes
    assert all(claim.evidence_refs for claim in outputs.claims)
    assert all(gate.passed for gate in completed.quality_gates)
    assert completed.subject.subject_id == "600519.SH"
    assert completed.subject.display_name == "贵州茅台"


def test_missing_consensus_blocks_run_until_evidence_is_added(db_session):
    service = ResearchRunService(ResearchRunRepository(db_session))
    created = service.create(
        _request(
            _evidence("financial", "经营现金流持续覆盖归母净利润。"),
            _evidence("industry", "高端白酒需求保持韧性。"),
            _evidence("valuation", "当前估值处于近五年中位数附近。"),
            _evidence("risk", "渠道库存上升可能压低盈利质量。"),
        )
    )

    blocked = service.execute(created.run_id)

    assert blocked.status is ResearchRunStatus.BLOCKED
    assert any(
        gate.gate_key == "consensus_coverage" and not gate.passed for gate in blocked.quality_gates
    )
    assert service.get_outputs(created.run_id).report_markdown is None

    service.add_evidence(created.run_id, _evidence("consensus", "三家机构维持盈利增长预期。"))
    completed = service.resume(created.run_id)
    outputs = service.get_outputs(created.run_id)

    assert completed.status is ResearchRunStatus.COMPLETED
    assert {claim.category for claim in outputs.claims} == {
        "financial",
        "industry",
        "valuation",
        "risk",
        "consensus",
    }
    assert any(note["category"] == "consensus" for note in outputs.research_notes)


def test_completed_run_is_idempotent_and_does_not_duplicate_artifacts(db_session):
    service = ResearchRunService(ResearchRunRepository(db_session))
    created = service.create(
        _request(
            _evidence("financial", "经营现金流持续覆盖归母净利润。"),
            _evidence("industry", "高端白酒需求保持韧性。"),
            _evidence("valuation", "当前估值处于近五年中位数附近。"),
            _evidence("risk", "渠道库存上升可能压低盈利质量。"),
            _evidence("consensus", "三家机构对未来两年盈利维持正增长预期。"),
        )
    )

    first = service.execute(created.run_id)
    artifact_count = len(service.get_outputs(created.run_id).artifacts)
    second = service.execute(created.run_id)

    assert first.run_id == second.run_id
    assert second.status is ResearchRunStatus.COMPLETED
    assert len(service.get_outputs(created.run_id).artifacts) == artifact_count


def test_research_run_records_source_downgrade_and_recoverable_task_snapshot(db_session):
    service = ResearchRunService(ResearchRunRepository(db_session))
    public_financial = _evidence("financial", "公开披露的现金流支持利润质量。").model_copy(
        update={"source_tier": "public"}
    )
    created = service.create(
        _request(
            public_financial,
            _evidence("industry", "行业需求稳定。").model_copy(update={"source_tier": "licensed"}),
            _evidence("valuation", "估值处于历史中位。").model_copy(
                update={"source_tier": "licensed"}
            ),
            _evidence("risk", "库存风险需要持续跟踪。").model_copy(
                update={"source_tier": "licensed"}
            ),
            _evidence("consensus", "覆盖机构维持增长预期。").model_copy(
                update={"source_tier": "licensed"}
            ),
        )
    )

    completed = service.execute(created.run_id)
    task = service.get_task(created.run_id)

    assert completed.source_plan["downgrades"] == [
        {"evidence_id": "evidence-financial", "from": "licensed", "to": "public"}
    ]
    assert task.status is ResearchRunStatus.COMPLETED
    assert task.attempt == 0
    assert task.state_snapshot["status"] == "completed"


def test_legacy_target_id_is_mapped_to_a_security_subject(db_session):
    service = ResearchRunService(ResearchRunRepository(db_session))
    created = service.create(
        ResearchRunCreateRequest(
            template_key="a_share_deep_research",
            target_id="000001.SZ",
            as_of=datetime(2026, 8, 10, tzinfo=UTC),
            question="旧版请求是否仍可创建？",
        )
    )

    assert created.target_id == "000001.SZ"
    assert created.subject == ResearchSubject(
        subject_type="security",
        subject_id="000001.SZ",
        display_name="000001.SZ",
    )


def test_unavailable_or_incompatible_templates_are_rejected_before_persistence(db_session):
    service = ResearchRunService(ResearchRunRepository(db_session))

    for template_key, subject_type in (
        ("macro_research", "macro"),
        ("a_share_deep_research", "index"),
        ("missing_template", "security"),
    ):
        request = ResearchRunCreateRequest(
            template_key=template_key,
            subject=ResearchSubject(
                subject_type=subject_type,
                subject_id="test-subject",
                display_name="测试对象",
            ),
            as_of=datetime(2026, 8, 10, tzinfo=UTC),
            question="该模板是否允许执行？",
        )
        try:
            service.create(request)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{template_key} should have been rejected")

    assert service.list_recent() == []


def test_completed_run_auto_archives_linked_workspace_session(db_session):
    workspace_service = ResearchWorkspaceService(ResearchWorkspaceRepository(db_session))
    service = ResearchRunService(
        ResearchRunRepository(db_session), workspace_service=workspace_service
    )
    workspace = workspace_service.create_workspace("project-a", "A", "workspace-a")
    request = _request(
        _evidence("financial", "经营现金流持续覆盖归母净利润。"),
        _evidence("industry", "高端白酒需求保持韧性。"),
        _evidence("valuation", "当前估值处于近五年中位数附近。"),
        _evidence("risk", "渠道库存上升可能压低盈利质量。"),
        _evidence("consensus", "三家机构维持增长预期。"),
    )
    created = service.create(request, idempotency_key="run-create-1")
    session = workspace_service.create_session(
        mode="workspace",
        idempotency_key="session-1",
        workspace_id=workspace.workspace_id,
        run_id=created.run_id,
    )

    duplicate = service.create(request, idempotency_key="run-create-1")
    completed = service.execute(
        created.run_id,
        idempotency_key="run-execute-1",
        project_id="project-a",
        workspace_id=workspace.workspace_id,
    )
    retried = service.execute(
        created.run_id,
        idempotency_key="run-execute-1",
        project_id="project-a",
        workspace_id=workspace.workspace_id,
    )

    assert duplicate.run_id == created.run_id
    assert completed.status is ResearchRunStatus.COMPLETED
    assert retried.run_id == created.run_id
    assert (
        workspace_service.get_session(
            session.session_id,
            project_id="project-a",
            workspace_id=workspace.workspace_id,
        ).status.value
        == "archived"
    )
    assert [
        event["status"]
        for event in service.list_events(
            created.run_id,
            project_id="project-a",
            workspace_id=workspace.workspace_id,
        )
    ] == [
        "draft",
        "planning",
        "collecting",
        "analyzing",
        "validating",
        "publishing",
        "completed",
    ]


def test_fingpt_real_run_uses_dsh_then_deterministically_falls_back(db_session):
    from core.contracts.research_workspace import RuntimeProvider

    workspace_service = ResearchWorkspaceService(ResearchWorkspaceRepository(db_session))
    runtime = RuntimeProviderService(
        providers=[
            RuntimeProvider(
                provider_id="dsh-1",
                provider_type="dsh",
                name="DSH",
                capabilities={"single_agent"},
                status="healthy",
                checked_at=datetime(2026, 8, 10, tzinfo=UTC),
            ),
            RuntimeProvider(
                provider_id="langgraph-1",
                provider_type="langgraph",
                name="LangGraph",
                capabilities={"single_agent", "resume"},
                status="healthy",
                checked_at=datetime(2026, 8, 10, tzinfo=UTC),
            ),
        ]
    )
    service = ResearchRunService(
        ResearchRunRepository(db_session),
        workspace_service=workspace_service,
        runtime_service=runtime,
        provider_invoker=lambda provider, payload, request_id: (_ for _ in ()).throw(
            TimeoutError("DSH unavailable")
        ),
    )
    created = service.create(
        _request(
            _evidence("financial", "经营现金流持续覆盖归母净利润。"),
            _evidence("industry", "高端白酒需求保持韧性。"),
            _evidence("valuation", "当前估值处于近五年中位数附近。"),
            _evidence("risk", "渠道库存上升可能压低盈利质量。"),
            _evidence("consensus", "三家机构维持盈利增长预期。"),
        ).model_copy(update={"mode": "fingpt"})
    )

    completed = service.execute(created.run_id, idempotency_key="execute-fallback")
    snapshot = service.get_task(created.run_id).state_snapshot
    assert completed.status is ResearchRunStatus.COMPLETED
    assert snapshot["provider_id"] == "langgraph-1"
    assert snapshot["fallback_from"] == "dsh-1"


def test_claw_without_agent_team_capability_persists_blocked_runtime_without_fallback(db_session):
    from core.contracts.research_workspace import RuntimeProvider

    workspace_service = ResearchWorkspaceService(ResearchWorkspaceRepository(db_session))
    runtime = RuntimeProviderService(
        providers=[
            RuntimeProvider(
                provider_id="langgraph-1",
                provider_type="langgraph",
                name="LangGraph",
                capabilities={"single_agent"},
                status="healthy",
                checked_at=datetime(2026, 8, 10, tzinfo=UTC),
            )
        ]
    )
    service = ResearchRunService(
        ResearchRunRepository(db_session),
        workspace_service=workspace_service,
        runtime_service=runtime,
    )
    created = service.create(
        _request().model_copy(update={"mode": "claw", "agent_team_id": "team-missing"})
    )

    with pytest.raises(RuntimeBlockedError) as exc:
        service.execute(created.run_id, idempotency_key="execute-claw")
    assert exc.value.code == "blocked_runtime"
    assert service.get(created.run_id).status is ResearchRunStatus.BLOCKED
    assert service.list_events(created.run_id)[-1]["status"] == "blocked"


def test_execute_idempotency_key_cannot_be_reused_for_another_run(db_session):
    workspace_service = ResearchWorkspaceService(ResearchWorkspaceRepository(db_session))
    service = ResearchRunService(
        ResearchRunRepository(db_session), workspace_service=workspace_service
    )
    first = service.create(_request())
    second = service.create(_request())
    service.execute(first.run_id, idempotency_key="shared-execute-key")

    with pytest.raises(ValueError, match="idempotency"):
        service.execute(second.run_id, idempotency_key="shared-execute-key")


def test_claw_real_run_executes_supervisor_team_and_shared_blackboard(db_session):
    from core.contracts.research_workspace import (
        AgentBudget,
        AgentTeamDefinition,
        RuntimeProvider,
    )
    from services.agent_team_service import AgentTeamService

    repository = ResearchWorkspaceRepository(db_session)
    repository.save_agent_team(
        AgentTeamDefinition(
            team_id="team-real",
            name="Real team",
            supervisor_role="supervisor",
            roles=["supervisor", "analyst"],
            budget=AgentBudget(
                max_steps=2,
                max_concurrency=1,
                max_tokens=100,
                max_cost=1,
                deadline_seconds=30,
            ),
            status="active",
        )
    )
    calls: list[str] = []
    service = ResearchRunService(
        ResearchRunRepository(db_session),
        runtime_service=RuntimeProviderService(
            providers=[
                RuntimeProvider(
                    provider_id="team-langgraph",
                    provider_type="langgraph",
                    name="Team LangGraph",
                    capabilities={"agent_team"},
                    status="healthy",
                    checked_at=datetime(2026, 8, 10, tzinfo=UTC),
                )
            ]
        ),
        agent_team_service=AgentTeamService(repository=repository),
        agent_worker=lambda assignment: (
            calls.append(assignment.role)
            or {
                "payload": {
                    "research_notes": [
                        {
                            "category": "risk",
                            "summary": "Agent 发现渠道库存风险需要提高跟踪频率。",
                            "evidence_refs": ["agent:analyst"],
                        }
                    ],
                    "claims": [
                        {
                            "category": "risk",
                            "text": "Agent 判断渠道库存风险正在上升。",
                            "evidence_refs": ["agent:analyst"],
                            "numeric_context": {},
                            "conflict_status": "clear",
                        }
                    ],
                    "report_markdown": "Agent Team：渠道库存风险正在上升。",
                },
                "tokens_used": 12,
                "cost_used": 0.01,
            }
        ),
    )
    created = service.create(
        _request(
            _evidence("financial", "经营现金流持续覆盖归母净利润。"),
            _evidence("industry", "高端白酒需求保持韧性。"),
            _evidence("valuation", "当前估值处于近五年中位数附近。"),
            _evidence("risk", "渠道库存上升可能压低盈利质量。"),
            _evidence("consensus", "三家机构维持增长预期。"),
        ).model_copy(update={"mode": "claw", "agent_team_id": "team-real"})
    )

    completed = service.execute(created.run_id)
    assert completed.status is ResearchRunStatus.COMPLETED
    assert calls == ["analyst"]
    outputs = service.get_outputs(created.run_id)
    assert any(claim.text == "Agent 判断渠道库存风险正在上升。" for claim in outputs.claims)
    assert "Agent Team：渠道库存风险正在上升。" in outputs.report_markdown
    assert any(item.artifact_type.startswith("agent_blackboard:") for item in outputs.artifacts)


def test_run_executes_enabled_skill_through_trusted_registry_and_schema(db_session):
    from core.contracts.research_workspace import RuntimeProvider, SkillManifest

    repository = ResearchWorkspaceRepository(db_session)
    runtime = RuntimeProviderService(
        repository=repository,
        providers=[
            RuntimeProvider(
                provider_id="skill-langgraph",
                provider_type="langgraph",
                name="Skill LangGraph",
                capabilities={"single_agent"},
                status="healthy",
                checked_at=datetime(2026, 8, 10, tzinfo=UTC),
            )
        ],
    )
    runtime.save_skill(
        SkillManifest(
            skill_key="run-context",
            name="Run context",
            version="1.0.0",
            prompt_template="Summarize {{run_id}}",
            input_schema={
                "type": "object",
                "required": ["run_id"],
                "properties": {"run_id": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "required": ["summary"],
                "properties": {"summary": {"type": "string"}},
            },
            allowed_tools=["internal:asset_snapshot"],
            status="enabled",
        ),
        authorized_tool_ids={"internal:asset_snapshot"},
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )
    invoked: list[str] = []
    service = ResearchRunService(
        ResearchRunRepository(db_session),
        runtime_service=runtime,
        skill_invoker=lambda manifest, payload, _context: (
            invoked.append(manifest.skill_key) or {"summary": payload["run_id"]}
        ),
        authorized_tool_ids={"internal:asset_snapshot"},
    )
    created = service.create(
        _request().model_copy(update={"mode": "fingpt", "skill_keys": ["run-context"]})
    )

    service.execute(created.run_id)
    assert invoked == ["run-context"]


def test_dsh_run_persists_provider_result_identity_and_typed_terminal(db_session):
    from core.contracts.research_workspace import (
        ProviderExecutionResult,
        RuntimeProvider,
    )
    from services.research_templates import get_default_research_template_registry

    registry = get_default_research_template_registry()

    def invoke_dsh(provider, payload, request_id):
        template = registry.require_executable("a_share_deep_research", _request().subject)
        return ProviderExecutionResult(
            provider_id=provider.provider_id,
            provider_result_id=f"provider:{request_id}",
            request_id=request_id,
            run_id=payload["run_id"],
            request_hash=stable_runtime_request_hash(payload),
            terminal_status="completed",
            output=template.graph_factory().invoke(payload),
        )

    service = ResearchRunService(
        ResearchRunRepository(db_session),
        runtime_service=RuntimeProviderService(
            providers=[
                RuntimeProvider(
                    provider_id="dsh-real",
                    provider_type="dsh",
                    name="DSH",
                    capabilities={"single_agent"},
                    status="healthy",
                    checked_at=datetime(2026, 8, 10, tzinfo=UTC),
                )
            ]
        ),
        provider_invoker=invoke_dsh,
    )
    created = service.create(_request())

    service.execute(created.run_id)
    snapshot = service.get_task(created.run_id).state_snapshot
    assert snapshot["provider_id"] == "dsh-real"
    assert snapshot["provider_result_id"] == f"provider:{created.run_id}:0"
    assert snapshot["provider_terminal_status"] == "completed"


def test_production_dependency_executes_registered_local_dsh_adapter(db_session, monkeypatch):
    """Regression: production DI wired no provider adapter, so healthy DSH always fell back."""

    from app.api.routes.research_runs import get_research_run_service
    from core.contracts.research_workspace import RuntimeProvider
    from services.research_graph import AShareDeepResearchGraph

    requests: list[dict] = []

    class DshHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            body = json.loads(self.rfile.read(length))
            requests.append(body)
            output = AShareDeepResearchGraph().invoke(body["input"])
            payload = json.dumps(
                {
                    "provider_id": "dsh-production",
                    "provider_result_id": f"result:{body['request_id']}",
                    "request_id": body["request_id"],
                    "run_id": body["run_id"],
                    "request_hash": body["request_hash"],
                    "terminal_status": "completed",
                    "output": output,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), DshHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "ALPHAFOUNDRY_TEST_DSH_URL",
        f"http://127.0.0.1:{server.server_address[1]}/execute",
    )
    try:
        repository = ResearchWorkspaceRepository(db_session)
        repository.save_runtime_provider(
            RuntimeProvider(
                provider_id="dsh-production",
                provider_type="dsh",
                name="DSH production",
                capabilities={"single_agent"},
                status="healthy",
                config_ref="env:ALPHAFOUNDRY_TEST_DSH_URL",
                checked_at=datetime(2026, 8, 10, tzinfo=UTC),
            )
        )
        service = get_research_run_service(db_session)
        created = service.create(
            _request(
                _evidence("financial", "经营现金流持续覆盖归母净利润。"),
                _evidence("industry", "高端白酒需求保持韧性。"),
                _evidence("valuation", "当前估值处于近五年中位数附近。"),
                _evidence("risk", "渠道库存上升可能压低盈利质量。"),
                _evidence("consensus", "三家机构维持盈利增长预期。"),
            )
        )

        completed = service.execute(created.run_id)

        assert completed.status is ResearchRunStatus.COMPLETED
        assert service.get_task(created.run_id).state_snapshot["provider_id"] == "dsh-production"
        assert requests[0]["run_id"] == created.run_id
        assert requests[0]["request_hash"]
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    ("terminal_status", "error_code", "expected_exception", "expected_status"),
    [
        ("failed", "dsh_execution_failed", RuntimeFailedError, ResearchRunStatus.FAILED),
        ("blocked", "dsh_policy_blocked", RuntimeBlockedError, ResearchRunStatus.BLOCKED),
    ],
)
def test_production_http_dsh_terminal_never_falls_back(
    db_session,
    monkeypatch,
    terminal_status,
    error_code,
    expected_exception,
    expected_status,
):
    from app.api.routes.research_runs import get_research_run_service
    from core.contracts.research_workspace import RuntimeProvider

    requests: list[dict] = []

    class DshTerminalHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            payload = json.dumps(
                {
                    "provider_id": "dsh-terminal-production",
                    "provider_result_id": f"result:{body['request_id']}",
                    "request_id": body["request_id"],
                    "run_id": body["run_id"],
                    "request_hash": body["request_hash"],
                    "terminal_status": terminal_status,
                    "error_code": error_code,
                    "output": {},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), DshTerminalHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "ALPHAFOUNDRY_TERMINAL_DSH_URL",
        f"http://127.0.0.1:{server.server_address[1]}/execute",
    )
    try:
        ResearchWorkspaceRepository(db_session).save_runtime_provider(
            RuntimeProvider(
                provider_id="dsh-terminal-production",
                provider_type="dsh",
                name="DSH terminal production",
                capabilities={"single_agent"},
                status="healthy",
                config_ref="env:ALPHAFOUNDRY_TERMINAL_DSH_URL",
                checked_at=datetime(2026, 8, 10, tzinfo=UTC),
            )
        )
        service = get_research_run_service(db_session)
        created = service.create(_request())

        with pytest.raises(expected_exception) as raised:
            service.execute(created.run_id)

        assert raised.value.code == error_code
        assert service.get(created.run_id).status is expected_status
        assert service.get_task(created.run_id).error_message == error_code
        assert len(requests) == 1
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_running_sse_stages_are_committed_before_slow_provider_returns(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.contracts.research_workspace import RuntimeProvider
    from data_layer.repositories.base import Base
    from services.runtime_provider_service import ProductionResearchExecutionAdapters

    provider_started = Event()
    release_provider = Event()

    class SlowDshHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            provider_started.set()
            assert release_provider.wait(timeout=3)
            payload = json.dumps(
                {
                    "provider_id": "dsh-slow",
                    "provider_result_id": f"result:{body['request_id']}",
                    "request_id": body["request_id"],
                    "run_id": body["run_id"],
                    "request_hash": body["request_hash"],
                    "terminal_status": "completed",
                    "output": {"source_plan": {}, "claims": [], "quality_checks": []},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowDshHandler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    monkeypatch.setenv(
        "ALPHAFOUNDRY_SLOW_DSH_URL",
        f"http://127.0.0.1:{server.server_address[1]}/execute",
    )
    engine = create_engine(
        f"sqlite:///{tmp_path / 'research-progress.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    adapters = ProductionResearchExecutionAdapters()
    try:
        with session_factory() as setup:
            repository = ResearchWorkspaceRepository(setup)
            repository.save_runtime_provider(
                RuntimeProvider(
                    provider_id="dsh-slow",
                    provider_type="dsh",
                    name="Slow DSH",
                    capabilities={"single_agent"},
                    status="healthy",
                    config_ref="env:ALPHAFOUNDRY_SLOW_DSH_URL",
                    checked_at=datetime(2026, 8, 10, tzinfo=UTC),
                )
            )
            service = ResearchRunService(
                ResearchRunRepository(setup),
                workspace_service=ResearchWorkspaceService(repository),
                runtime_service=RuntimeProviderService(repository=repository),
                provider_invoker=adapters.invoke_provider,
            )
            run_id = service.create(_request()).run_id
            setup.commit()

        execution_error: list[Exception] = []

        def execute_run():
            try:
                with session_factory() as session:
                    repository = ResearchWorkspaceRepository(session)
                    service = ResearchRunService(
                        ResearchRunRepository(session),
                        workspace_service=ResearchWorkspaceService(repository),
                        runtime_service=RuntimeProviderService(repository=repository),
                        provider_invoker=adapters.invoke_provider,
                    )
                    service.execute(run_id)
                    session.commit()
            except Exception as exc:  # noqa: BLE001 - report thread failures to test parent
                execution_error.append(exc)

        execution_thread = Thread(target=execute_run)
        execution_thread.start()
        assert provider_started.wait(timeout=2)
        with session_factory() as observer:
            events = ResearchWorkspaceService(
                ResearchWorkspaceRepository(observer)
            ).list_run_events(run_id)
            assert [item["status"] for item in events] == [
                "draft",
                "planning",
                "collecting",
                "analyzing",
            ]
        release_provider.set()
        execution_thread.join(timeout=3)
        assert not execution_thread.is_alive()
        assert execution_error == []
        with session_factory() as observer:
            events = ResearchWorkspaceService(
                ResearchWorkspaceRepository(observer)
            ).list_run_events(run_id)
            assert [item["status"] for item in events][-3:] == [
                "validating",
                "publishing",
                "completed",
            ]
    finally:
        release_provider.set()
        server.shutdown()
        server_thread.join(timeout=2)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_run_history_requires_and_filters_complete_workspace_scope(db_session):
    workspace_service = ResearchWorkspaceService(ResearchWorkspaceRepository(db_session))
    service = ResearchRunService(
        ResearchRunRepository(db_session), workspace_service=workspace_service
    )
    workspace_a = workspace_service.create_workspace("project-a", "A", "history-a")
    workspace_b = workspace_service.create_workspace("project-a", "B", "history-b")
    run_a = service.create(_request())
    run_b = service.create(_request())
    workspace_service.create_session(
        mode="workspace",
        workspace_id=workspace_a.workspace_id,
        run_id=run_a.run_id,
        idempotency_key="history-session-a",
    )
    workspace_service.create_session(
        mode="workspace",
        workspace_id=workspace_b.workspace_id,
        run_id=run_b.run_id,
        idempotency_key="history-session-b",
    )

    assert [
        item.run_id
        for item in service.list_recent(
            project_id="project-a", workspace_id=workspace_a.workspace_id
        )
    ] == [run_a.run_id]
    with pytest.raises(ValueError, match="project and workspace"):
        service.list_recent(project_id="project-a")


@pytest.mark.parametrize(
    ("terminal_status", "error_code", "expected_exception", "expected_status"),
    [
        ("failed", "provider_crashed", RuntimeFailedError, ResearchRunStatus.FAILED),
        ("blocked", "provider_policy", RuntimeBlockedError, ResearchRunStatus.BLOCKED),
    ],
)
def test_typed_provider_terminal_is_persisted_without_langgraph_fallback(
    db_session,
    terminal_status,
    error_code,
    expected_exception,
    expected_status,
):
    from core.contracts.research_workspace import (
        ProviderExecutionResult,
        RuntimeProvider,
    )

    calls: list[str] = []

    def invoke(provider, payload, request_id):
        calls.append(provider.provider_id)
        return ProviderExecutionResult(
            provider_id=provider.provider_id,
            provider_result_id=f"result:{request_id}",
            request_id=request_id,
            run_id=payload["run_id"],
            request_hash=stable_runtime_request_hash(payload),
            terminal_status=terminal_status,
            error_code=error_code,
        )

    service = ResearchRunService(
        ResearchRunRepository(db_session),
        runtime_service=RuntimeProviderService(
            providers=[
                RuntimeProvider(
                    provider_id="dsh-terminal",
                    provider_type="dsh",
                    name="DSH terminal",
                    capabilities={"single_agent"},
                    status="healthy",
                    checked_at=datetime(2026, 8, 10, tzinfo=UTC),
                ),
                RuntimeProvider(
                    provider_id="langgraph-fallback",
                    provider_type="langgraph",
                    name="LangGraph fallback",
                    capabilities={"single_agent"},
                    status="healthy",
                    checked_at=datetime(2026, 8, 10, tzinfo=UTC),
                ),
            ]
        ),
        provider_invoker=invoke,
    )
    created = service.create(_request())

    with pytest.raises(expected_exception) as raised:
        service.execute(created.run_id)

    assert raised.value.code == error_code
    assert service.get(created.run_id).status is expected_status
    assert service.get_task(created.run_id).error_message == error_code
    assert calls == ["dsh-terminal"]


def test_runtime_input_contains_only_scoped_latest_notes_and_session_messages(db_session):
    from core.contracts.research_workspace import (
        ProviderExecutionResult,
        ResearchNote,
        RuntimeProvider,
    )
    from services.research_templates import get_default_research_template_registry

    repository = ResearchWorkspaceRepository(db_session)
    workspace_service = ResearchWorkspaceService(repository)
    workspace_a = workspace_service.create_workspace("project-a", "A", "context-workspace-a")
    workspace_b = workspace_service.create_workspace("project-a", "B", "context-workspace-b")
    captured: list[dict] = []

    def invoke(provider, payload, request_id):
        captured.append(payload)
        graph = get_default_research_template_registry().require_executable(
            "a_share_deep_research", _request().subject
        )
        return ProviderExecutionResult(
            provider_id=provider.provider_id,
            provider_result_id=f"result:{request_id}",
            request_id=request_id,
            run_id=payload["run_id"],
            request_hash=stable_runtime_request_hash(payload),
            terminal_status="completed",
            output=graph.graph_factory().invoke(payload),
        )

    service = ResearchRunService(
        ResearchRunRepository(db_session),
        workspace_service=workspace_service,
        runtime_service=RuntimeProviderService(
            providers=[
                RuntimeProvider(
                    provider_id="dsh-context",
                    provider_type="dsh",
                    name="DSH context",
                    capabilities={"single_agent"},
                    status="healthy",
                    checked_at=datetime(2026, 8, 10, tzinfo=UTC),
                )
            ]
        ),
        provider_invoker=invoke,
    )
    run_a = service.create(_request())
    run_b = service.create(_request())
    session_a = workspace_service.create_session(
        mode="workspace",
        workspace_id=workspace_a.workspace_id,
        run_id=run_a.run_id,
        idempotency_key="context-session-a",
    )
    session_b = workspace_service.create_session(
        mode="workspace",
        workspace_id=workspace_b.workspace_id,
        run_id=run_b.run_id,
        idempotency_key="context-session-b",
    )
    workspace_service.append_message(
        session_a.session_id,
        role="user",
        content="A工作区私有问题",
        idempotency_key="context-message-a",
        project_id="project-a",
        workspace_id=workspace_a.workspace_id,
    )
    workspace_service.append_message(
        session_b.session_id,
        role="user",
        content="B工作区绝不能泄漏",
        idempotency_key="context-message-b",
        project_id="project-a",
        workspace_id=workspace_b.workspace_id,
    )
    workspace_service.append_message(
        session_a.session_id,
        role="assistant",
        content="X" * 20_000,
        idempotency_key="context-message-a-large",
        project_id="project-a",
        workspace_id=workspace_a.workspace_id,
    )
    repository.create_note(
        ResearchNote(
            note_id="note-context-a",
            workspace_id=workspace_a.workspace_id,
            revision=1,
            source_kind="claim",
            claim_id="claim-context-a",
            summary="A工作区最新研究记忆",
            created_at=datetime(2026, 8, 10, tzinfo=UTC),
        ),
        note_key="context-note-a",
    )
    repository.create_note(
        ResearchNote(
            note_id="note-context-b",
            workspace_id=workspace_b.workspace_id,
            revision=1,
            source_kind="claim",
            claim_id="claim-context-b",
            summary="B工作区绝不能泄漏",
            created_at=datetime(2026, 8, 10, tzinfo=UTC),
        ),
        note_key="context-note-b",
    )

    service.execute(
        run_a.run_id,
        project_id="project-a",
        workspace_id=workspace_a.workspace_id,
    )

    context = captured[0]["workspace_context"]
    serialized = json.dumps(context, ensure_ascii=False)
    assert context["project_id"] == "project-a"
    assert context["workspace_id"] == workspace_a.workspace_id
    assert "A工作区最新研究记忆" in serialized
    assert "A工作区私有问题" in serialized
    assert "B工作区绝不能泄漏" not in serialized
    assert context["truncated"] is True
    assert (
        sum(len(item.get("content") or "") for item in context["messages"])
        + sum(len(item["summary"]) for item in context["notes"])
        <= 12_000
    )


def test_production_skill_with_declared_but_unregistered_tool_is_blocked(db_session, monkeypatch):
    from app.api.routes.research_runs import get_research_run_service
    from core.contracts.research_workspace import SkillManifest

    repository = ResearchWorkspaceRepository(db_session)
    RuntimeProviderService(repository=repository).save_skill(
        SkillManifest(
            skill_key="requires-tool",
            name="Requires tool",
            version="1.0.0",
            prompt_template="Use snapshot",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            allowed_tools=["mcp:configured-only"],
            status="enabled",
        ),
        authorized_tool_ids={"mcp:configured-only"},
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )
    monkeypatch.setenv(
        "ALPHAFOUNDRY_AUTHORIZED_RESEARCH_TOOLS",
        "mcp:configured-only",
    )
    service = get_research_run_service(db_session)
    created = service.create(_request().model_copy(update={"skill_keys": ["requires-tool"]}))

    with pytest.raises(RuntimeBlockedError) as raised:
        service.execute(created.run_id)

    assert raised.value.code == "skill_boundary_rejected"
    assert service.get(created.run_id).status is ResearchRunStatus.BLOCKED
