"""Behavior tests for project-isolated research workspaces."""

from datetime import UTC, datetime

import pytest

from core.contracts.research import ResearchRun, ResearchRunStatus, ResearchSubject
from core.contracts.research_workspace import SessionMode
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.research_workspace_service import (
    ResearchWorkspaceService,
    WorkspaceScopeError,
)

NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def _service(db_session) -> ResearchWorkspaceService:
    return ResearchWorkspaceService(ResearchWorkspaceRepository(db_session), clock=lambda: NOW)


def _run(run_id: str) -> ResearchRun:
    return ResearchRun(
        run_id=run_id,
        template_key="a_share_deep_research",
        target_id="600519.SH",
        subject=ResearchSubject(
            subject_type="security",
            subject_id="600519.SH",
            display_name="贵州茅台",
        ),
        as_of=NOW,
        question="证据是否支持增长？",
        status=ResearchRunStatus.COMPLETED,
        created_at=NOW,
        updated_at=NOW,
        completed_at=NOW,
    )


def test_workspace_memory_never_crosses_projects(db_session):
    service = _service(db_session)
    workspace_a = service.create_workspace("project-a", "A", "workspace-key-a")
    workspace_b = service.create_workspace("project-b", "B", "workspace-key-b")
    # Store a real run row and a claim so ownership is derived from persisted relations.
    from data_layer.repositories.models import ResearchClaimDB, ResearchRunDB

    service.repository.db.add(
        ResearchRunDB(
            run_id="run-a",
            template_key="a_share_deep_research",
            target_id="600519.SH",
            subject_type="security",
            subject_payload=_run("run-a").subject.model_dump(mode="json"),
            as_of=NOW,
            question="证据是否支持增长？",
            status="completed",
            created_at=NOW,
            updated_at=NOW,
            completed_at=NOW,
        )
    )
    service.repository.db.add(
        ResearchClaimDB(
            claim_id="claim-a",
            run_id="run-a",
            category="financial",
            text="现金流支持利润质量",
            evidence_refs=["ev-a"],
            numeric_context={},
            conflict_status="clear",
            created_at=NOW,
        )
    )
    session = service.create_session(
        mode=SessionMode.WORKSPACE,
        idempotency_key="session-a",
        workspace_id=workspace_a.workspace_id,
        run_id="run-a",
    )
    assert session.workspace_id == workspace_a.workspace_id
    service.pin_note(
        workspace_a.workspace_id,
        note_key="thesis",
        source_kind="claim",
        summary="现金流支持",
        claim_id="claim-a",
    )

    assert [note.summary for note in service.build_memory_context(workspace_a.workspace_id)] == [
        "现金流支持"
    ]
    assert service.build_memory_context(workspace_b.workspace_id) == []
    with pytest.raises(WorkspaceScopeError):
        service.pin_note(
            workspace_b.workspace_id,
            note_key="leak",
            source_kind="claim",
            summary="不应跨项目",
            claim_id="claim-a",
        )


def test_session_and_message_idempotency_and_atomic_promotion(db_session):
    service = _service(db_session)
    temporary = service.create_session(
        mode=SessionMode.TEMPORARY,
        idempotency_key="temporary-1",
    )
    assert (
        service.create_session(
            mode=SessionMode.TEMPORARY,
            idempotency_key="temporary-1",
        ).session_id
        == temporary.session_id
    )
    first = service.append_message(
        temporary.session_id,
        role="user",
        content="研究黄金供需",
        idempotency_key="message-1",
    )
    duplicate = service.append_message(
        temporary.session_id,
        role="user",
        content="研究黄金供需",
        idempotency_key="message-1",
    )
    assert duplicate.message_id == first.message_id

    workspace = service.create_workspace("gold-project", "黄金", "workspace-gold")
    promoted = service.promote_session(temporary.session_id, workspace.workspace_id)
    retried = service.promote_session(temporary.session_id, workspace.workspace_id)
    assert promoted.session_id == retried.session_id
    assert promoted.mode is SessionMode.WORKSPACE
    assert promoted.workspace_id == workspace.workspace_id


def test_note_revisions_are_immutable_and_completed_run_archives_session(db_session):
    service = _service(db_session)
    workspace = service.create_workspace("project-a", "A", "workspace-a")
    from data_layer.repositories.models import ResearchArtifactDB, ResearchRunDB

    run = _run("run-1")
    service.repository.db.add(
        ResearchRunDB(
            run_id=run.run_id,
            template_key=run.template_key,
            target_id=run.target_id,
            subject_type=run.subject.subject_type,
            subject_payload=run.subject.model_dump(mode="json"),
            as_of=run.as_of,
            question=run.question,
            status=run.status.value,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
        )
    )
    service.repository.db.add_all(
        [
            ResearchArtifactDB(
                artifact_id="artifact-report-v1",
                run_id=run.run_id,
                artifact_type="report_markdown:0",
                payload={"paragraphs": [{"paragraph_id": "p1"}, {"paragraph_id": "p2"}]},
                created_at=NOW,
            )
        ]
    )
    session = service.create_session(
        mode=SessionMode.WORKSPACE,
        idempotency_key="session-1",
        workspace_id=workspace.workspace_id,
        run_id=run.run_id,
    )
    note_v1 = service.pin_note(
        workspace.workspace_id,
        note_key="conclusion",
        source_kind="paragraph",
        summary="第一版",
        run_id=run.run_id,
        paragraph_ref="artifact-report-v1#p1",
    )
    note_v2 = service.pin_note(
        workspace.workspace_id,
        note_key="conclusion",
        source_kind="paragraph",
        summary="第二版",
        run_id=run.run_id,
        paragraph_ref="artifact-report-v1#p2",
    )
    assert (note_v1.revision, note_v2.revision) == (1, 2)
    assert [note.summary for note in service.build_memory_context(workspace.workspace_id)] == [
        "第二版"
    ]

    service.archive_completed_run(run.run_id)
    assert (
        service.get_session(
            session.session_id,
            project_id="project-a",
            workspace_id=workspace.workspace_id,
        ).status.value
        == "archived"
    )


def test_run_has_one_workspace_and_all_scoped_reads_validate_project(db_session):
    service = _service(db_session)
    workspace_a = service.create_workspace("project-a", "A", "workspace-a-scope")
    workspace_b = service.create_workspace("project-b", "B", "workspace-b-scope")
    from data_layer.repositories.models import ResearchRunDB

    run = _run("run-scoped")
    service.repository.db.add(
        ResearchRunDB(
            run_id=run.run_id,
            template_key=run.template_key,
            target_id=run.target_id,
            subject_type=run.subject.subject_type,
            subject_payload=run.subject.model_dump(mode="json"),
            as_of=run.as_of,
            question=run.question,
            status=run.status.value,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
        )
    )
    session_a = service.create_session(
        mode="workspace",
        idempotency_key="session-scope-a",
        workspace_id=workspace_a.workspace_id,
    )
    session_b = service.create_session(
        mode="workspace",
        idempotency_key="session-scope-b",
        workspace_id=workspace_b.workspace_id,
    )
    service.link_session_run(
        session_a.session_id,
        run.run_id,
        project_id="project-a",
        workspace_id=workspace_a.workspace_id,
    )
    session_same_workspace = service.create_session(
        mode="workspace",
        idempotency_key="session-scope-same-workspace",
        workspace_id=workspace_a.workspace_id,
    )

    with pytest.raises(WorkspaceScopeError, match="already bound"):
        service.link_session_run(
            session_same_workspace.session_id,
            run.run_id,
            project_id="project-a",
            workspace_id=workspace_a.workspace_id,
        )

    with pytest.raises(WorkspaceScopeError):
        service.link_session_run(
            session_b.session_id,
            run.run_id,
            project_id="project-b",
            workspace_id=workspace_b.workspace_id,
        )
    with pytest.raises(WorkspaceScopeError):
        service.get_session_scoped(
            session_a.session_id,
            project_id="project-b",
            workspace_id=workspace_a.workspace_id,
        )


def test_paragraph_note_requires_real_artifact_paragraph(db_session):
    service = _service(db_session)
    workspace = service.create_workspace("project-a", "A", "workspace-artifact")
    from data_layer.repositories.models import ResearchArtifactDB, ResearchRunDB

    run = _run("run-artifact")
    service.repository.db.add(
        ResearchRunDB(
            run_id=run.run_id,
            template_key=run.template_key,
            target_id=run.target_id,
            subject_type=run.subject.subject_type,
            subject_payload=run.subject.model_dump(mode="json"),
            as_of=run.as_of,
            question=run.question,
            status=run.status.value,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
        )
    )
    service.repository.db.add(
        ResearchArtifactDB(
            artifact_id="artifact-real",
            run_id=run.run_id,
            artifact_type="research_notes:0",
            payload={"paragraphs": [{"paragraph_id": "p1", "text": "真实段落"}]},
            created_at=NOW,
        )
    )
    session = service.create_session(
        mode="workspace",
        idempotency_key="session-artifact",
        workspace_id=workspace.workspace_id,
        run_id=run.run_id,
    )
    assert session.run_id == run.run_id

    with pytest.raises(ValueError, match="paragraph"):
        service.pin_note(
            workspace.workspace_id,
            note_key="invalid",
            source_kind="paragraph",
            summary="不存在",
            run_id=run.run_id,
            paragraph_ref="artifact-real#missing",
        )


def test_archive_failure_produces_durable_archive_pending_event(db_session, monkeypatch):
    service = _service(db_session)
    from data_layer.repositories.models import ResearchRunDB

    run = _run("run-pending")
    service.repository.db.add(
        ResearchRunDB(
            run_id=run.run_id,
            template_key=run.template_key,
            target_id=run.target_id,
            subject_type=run.subject.subject_type,
            subject_payload=run.subject.model_dump(mode="json"),
            as_of=run.as_of,
            question=run.question,
            status=run.status.value,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
        )
    )
    monkeypatch.setattr(
        service.repository,
        "archive_completed_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("archive unavailable")),
    )

    service.archive_completed_run_safely(run.run_id)

    events = service.list_run_events(run.run_id)
    assert events == [
        {
            "event_id": events[0]["event_id"],
            "sequence": 0,
            "status": "archive_pending",
            "stage": "archive",
        }
    ]


def test_archive_outbox_savepoint_recovers_database_error_and_keeps_run_completed(
    db_session, monkeypatch
):
    service = _service(db_session)
    from data_layer.repositories.models import ResearchRunDB

    run = _run("run-archive-savepoint")
    row = ResearchRunDB(
        run_id=run.run_id,
        template_key=run.template_key,
        target_id=run.target_id,
        subject_type=run.subject.subject_type,
        subject_payload=run.subject.model_dump(mode="json"),
        as_of=run.as_of,
        question=run.question,
        status=run.status.value,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )
    db_session.add(row)
    db_session.flush()

    def violate_primary_key(*_args, **_kwargs):
        db_session.add(
            ResearchRunDB(
                run_id=run.run_id,
                template_key=run.template_key,
                target_id=run.target_id,
                subject_type=run.subject.subject_type,
                subject_payload=run.subject.model_dump(mode="json"),
                as_of=run.as_of,
                question=run.question,
                status=run.status.value,
                created_at=run.created_at,
                updated_at=run.updated_at,
                completed_at=run.completed_at,
            )
        )
        db_session.flush()

    monkeypatch.setattr(service.repository, "archive_completed_run", violate_primary_key)

    service.archive_completed_run_safely(run.run_id)

    assert db_session.get(ResearchRunDB, run.run_id).status == "completed"
    assert service.list_run_events(run.run_id)[0]["status"] == "archive_pending"
