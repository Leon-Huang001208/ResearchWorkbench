from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes.runtime_workflows import require_dsh_tool_access
from core.contracts.runtime import (
    CapabilityKind,
    RuntimeCapabilities,
    RuntimeDescriptor,
    RuntimeUnavailableError,
)
from data_layer.repositories.runtime_workflow_repository import (
    RuntimeWorkflowRepository,
)
from services.daily_market_commentary_spec import (
    DailyMarketCommentarySpec,
    load_daily_market_commentary_spec,
    save_daily_market_commentary_spec,
)
from services.market_commentary_workflow import (
    DailyMarketCommentaryWorkflow,
    InMemoryMarketCommentaryTools,
    InMemorySkillRuntime,
    LiveAkShareMarketCommentaryTools,
)
from services.runtime_registry import RuntimeRegistry
from services.runtime_workflow_service import (
    DailyMarketCommentaryRequest,
    RuntimeWorkflowService,
)


def _runtime(*, skills: bool = True) -> InMemorySkillRuntime:
    return InMemorySkillRuntime(
        RuntimeDescriptor(
            runtime_id="dsh-local",
            display_name="DSH local",
            protocol_version="alphafoundry.io/v1",
            capabilities=RuntimeCapabilities(
                tool_calling=True,
                skills=skills,
                workflow=False,
                streaming=True,
                cancellation=True,
                resume=True,
            ),
        )
    )


def _service(db_session) -> RuntimeWorkflowService:
    runtime = _runtime()
    registry = RuntimeRegistry()
    registry.register(runtime.descriptor)
    return RuntimeWorkflowService(
        RuntimeWorkflowRepository(db_session),
        registry=registry,
        runtime_adapters={runtime.descriptor.runtime_id: runtime},
    )


def test_daily_market_commentary_workflow_composes_tools_skills_gates_and_artifact():
    workflow = DailyMarketCommentaryWorkflow(
        tools=InMemoryMarketCommentaryTools(
            snapshot={"indices": [{"name": "沪深300", "change_percent": 1.2}]},
            breadth={"up": 3200, "down": 1600},
            industries=[{"name": "机器人", "change_percent": 3.4}],
            leaders=[{"name": "机器人", "change_percent": 3.4}],
            news=[
                {
                    "source_ref": "news-1",
                    "source_name": "测试新闻",
                    "published_at": "2026-08-26T08:00:00Z",
                    "summary": "政策推动机器人产业关注度上升。",
                }
            ],
        ),
        runtime=_runtime(),
    )

    result = workflow.run(
        run_id="market-run-1",
        as_of=datetime(2026, 8, 26, tzinfo=UTC),
        question="生成今日市场收盘点评",
    )

    assert result.status == "completed"
    assert result.report_document.title == "2026年8月26日每日市场点评"
    assert [step.kind for step in result.workflow.steps] == [
        CapabilityKind.TOOL,
        CapabilityKind.TOOL,
        CapabilityKind.TOOL,
        CapabilityKind.TOOL,
        CapabilityKind.TOOL,
        CapabilityKind.TOOL,
        CapabilityKind.TOOL,
        CapabilityKind.TOOL,
        CapabilityKind.SKILL,
        CapabilityKind.SKILL,
        CapabilityKind.SKILL,
        CapabilityKind.EVALUATOR,
        CapabilityKind.SKILL,
        CapabilityKind.RENDERER,
    ]
    assert result.report_document.evidence_refs == ["news-1"]
    assert [section.heading for section in result.report_document.sections] == [
        "今日市场行情",
        "行业与风格变化",
        "后市展望",
    ]
    assert len(result.report_document.charts) == 2
    assert all(gate.passed for gate in result.gates)
    assert result.events[-1].event_type == "RunCompleted"


def test_daily_market_commentary_refuses_runtime_without_skill_capability():
    workflow = DailyMarketCommentaryWorkflow(
        tools=InMemoryMarketCommentaryTools.with_minimal_valid_data(),
        runtime=_runtime(skills=False),
    )

    with pytest.raises(RuntimeUnavailableError, match="skills"):
        workflow.run(
            run_id="market-run-2",
            as_of=datetime(2026, 8, 26, tzinfo=UTC),
            question="生成今日市场收盘点评",
        )


def test_live_market_tools_keep_data_retrieval_inside_alphafoundry(monkeypatch):
    tools = LiveAkShareMarketCommentaryTools(sector_limit=1)
    monkeypatch.setattr(
        tools,
        "get_industry_returns",
        lambda: [
            {
                "name": "电子",
                "change_percent": 2.0,
                "leading_stock": "测试股",
                "source": "test",
            },
            {
                "name": "银行",
                "change_percent": -1.0,
                "leading_stock": "测试银",
                "source": "test",
            },
        ],
    )

    leaders = tools.get_market_leaders()

    assert [item["name"] for item in leaders] == ["电子", "银行"]
    assert all(item["source"] == "test" for item in leaders)


def test_interpretive_counter_evidence_becomes_conditional_risk_not_blocker():
    workflow = DailyMarketCommentaryWorkflow(
        tools=InMemoryMarketCommentaryTools.with_minimal_valid_data(), runtime=_runtime()
    )
    gates = workflow._evaluate(
        {"indices": [{"name": "沪深300"}]},
        {"up": 1, "down": 1},
        [{"name": "电子"}],
        [],
        {"conflict": True},
        load_daily_market_commentary_spec(),
    )
    conflict_gate = next(gate for gate in gates if gate.gate_key == "conflict_detection")
    assert conflict_gate.passed is True
    assert conflict_gate.details["interpretive_conflict_as_risk"] is True


def test_daily_market_commentary_spec_is_yaml_source_of_truth(tmp_path):
    path = tmp_path / "daily.yaml"
    spec = load_daily_market_commentary_spec()
    updated = DailyMarketCommentarySpec.model_validate(
        {**spec.model_dump(mode="json"), "version": "2.0.1"}
    )
    save_daily_market_commentary_spec(updated, path)
    assert load_daily_market_commentary_spec(path).version == "2.0.1"


def test_runtime_workflow_service_persists_replayable_event_ledger(db_session):
    service = _service(db_session)
    created = service.create_daily_market_commentary(
        DailyMarketCommentaryRequest(
            as_of=datetime(2026, 8, 26, tzinfo=UTC),
            question="生成今日市场收盘点评",
            market_inputs={
                "snapshot": {"indices": [{"name": "沪深300", "change_percent": 0.2}]},
                "breadth": {"up": 2000, "down": 1800},
                "industries": [{"name": "电子", "change_percent": 1.0}],
                "leaders": [{"name": "电子", "change_percent": 1.0}],
                "news": [
                    {
                        "source_ref": "news-1",
                        "source_name": "测试新闻",
                        "summary": "市场保持活跃。",
                    }
                ],
            },
        )
    )

    result = service.execute(created["run_id"])
    replay = service.events(created["run_id"], after_sequence=0)

    assert result.status == "completed"
    assert replay[0].sequence == 1
    assert replay[-1].event_type == "RunCompleted"


def test_runtime_workflow_service_records_failed_status_before_reraising(
    db_session, monkeypatch
):
    service = _service(db_session)
    created = service.create_daily_market_commentary(
        DailyMarketCommentaryRequest(
            as_of=datetime(2026, 8, 26, tzinfo=UTC),
            question="生成今日市场收盘点评",
            market_inputs={"snapshot": {"indices": [{"name": "沪深300"}]}},
        )
    )

    def fail_run(*_args, **_kwargs):
        raise RuntimeError("simulated runtime failure")

    monkeypatch.setattr(DailyMarketCommentaryWorkflow, "run", fail_run)

    with pytest.raises(RuntimeError, match="simulated runtime failure"):
        service.execute(created["run_id"])

    assert service.get(created["run_id"]).status == "failed"


def test_default_runtime_service_does_not_fall_back_to_fixture_without_dsh_bridge(
    db_session, monkeypatch
):
    monkeypatch.delenv("ALPHAFOUNDRY_DSH_BRIDGE_URL", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_DSH_BRIDGE_TOKEN", raising=False)
    service = RuntimeWorkflowService(RuntimeWorkflowRepository(db_session))

    with pytest.raises(RuntimeUnavailableError, match="does not support skill"):
        service.create_daily_market_commentary(
            DailyMarketCommentaryRequest(
                as_of=datetime(2026, 8, 26, tzinfo=UTC),
                question="生成今日市场收盘点评",
            )
        )


def test_runtime_native_tool_reads_only_persisted_workflow_inputs(db_session):
    service = _service(db_session)
    created = service.create_daily_market_commentary(
        DailyMarketCommentaryRequest(
            as_of=datetime(2026, 8, 26, tzinfo=UTC),
            question="生成今日市场收盘点评",
            market_inputs={"snapshot": {"indices": [{"name": "沪深300"}]}},
        )
    )

    result = service.run_native_tool(
        run_id=created["run_id"],
        capability_id="market.snapshot",
        execution_id="dsh-test-execution",
        correlation_id="00000000-0000-0000-0000-000000000001",
    )

    assert result == {"value": {"indices": [{"name": "沪深300"}]}}
    assert service.events(created["run_id"])[-1].event_type == "RuntimeToolCompleted"


def test_dsh_tool_access_requires_loopback_and_dedicated_token(monkeypatch):
    monkeypatch.setenv("ALPHAFOUNDRY_DSH_TOOL_TOKEN", "tool-token-0123456789")
    loopback_request = Request({"type": "http", "client": ("127.0.0.1", 8765), "headers": []})
    require_dsh_tool_access(loopback_request, authorization="Bearer tool-token-0123456789")

    remote_request = Request({"type": "http", "client": ("10.0.0.5", 8765), "headers": []})
    with pytest.raises(HTTPException, match="Forbidden"):
        require_dsh_tool_access(remote_request, authorization="Bearer tool-token-0123456789")
