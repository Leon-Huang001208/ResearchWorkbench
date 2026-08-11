from datetime import datetime, timezone

from core.contracts.research import (
    ResearchEvidenceInput,
    ResearchRunCreateRequest,
    ResearchRunStatus,
    ResearchSubject,
)
from data_layer.repositories.research_run_repository import ResearchRunRepository
from services.research_run_service import ResearchRunService


def _request(*evidence: ResearchEvidenceInput) -> ResearchRunCreateRequest:
    return ResearchRunCreateRequest(
        template_key="a_share_deep_research",
        subject=ResearchSubject(
            subject_type="security",
            subject_id="600519.SH",
            display_name="贵州茅台",
            market="A-share",
        ),
        as_of=datetime(2026, 8, 10, tzinfo=timezone.utc),
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
            _evidence("valuation", "估值处于历史中位。").model_copy(update={"source_tier": "licensed"}),
            _evidence("risk", "库存风险需要持续跟踪。").model_copy(update={"source_tier": "licensed"}),
            _evidence("consensus", "覆盖机构维持增长预期。").model_copy(update={"source_tier": "licensed"}),
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
            as_of=datetime(2026, 8, 10, tzinfo=timezone.utc),
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
            as_of=datetime(2026, 8, 10, tzinfo=timezone.utc),
            question="该模板是否允许执行？",
        )
        try:
            service.create(request)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{template_key} should have been rejected")

    assert service.list_recent() == []
