"""Persistence boundary for research workspaces, runtimes, teams, and schedules."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core.contracts.platform_shared import ScheduledJob, ScheduledJobStatus
from core.contracts.research_workspace import (
    AgentSchedule,
    AgentTeamDefinition,
    ProviderExecutionResult,
    ResearchMessage,
    ResearchNote,
    ResearchSession,
    ResearchWorkspace,
    RuntimeProvider,
    SessionMode,
    SessionStatus,
    SkillManifest,
    WorkspaceStatus,
)
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import (
    AgentScheduleDB,
    AgentTeamDB,
    DomainEventDB,
    ResearchArtifactDB,
    ResearchClaimDB,
    ResearchMessageDB,
    ResearchNoteDB,
    ResearchRunDB,
    ResearchSessionDB,
    ResearchWorkspaceDB,
    RuntimeProviderDB,
    ScheduledJobDB,
    SkillDefinitionDB,
)

logger = get_logger(__name__)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ResearchWorkspaceRepository(BaseRepository):
    """Request-scoped repository. Methods flush but transaction ownership stays outside."""

    def __init__(self, db: Session):
        super().__init__(db)

    def create_workspace(
        self,
        workspace: ResearchWorkspace,
        *,
        idempotency_key: str,
    ) -> ResearchWorkspace:
        existing_id = self.find_idempotent_resource("research_workspace.created", idempotency_key)
        if existing_id:
            existing = self.get_workspace(existing_id)
            if existing.project_id != workspace.project_id or existing.title != workspace.title:
                raise ValueError("workspace idempotency key conflicts with changed request")
            return existing
        row = ResearchWorkspaceDB(
            workspace_id=workspace.workspace_id,
            project_id=workspace.project_id,
            title=workspace.title,
            status=workspace.status.value,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            archived_at=workspace.archived_at,
        )
        try:
            self.db.add(row)
            self._append_event(
                event_type="research_workspace.created",
                aggregate_type="research_workspace",
                aggregate_id=workspace.workspace_id,
                idempotency_key=f"research_workspace.created:{idempotency_key}",
                occurred_at=workspace.created_at,
                payload={"resource_id": workspace.workspace_id},
            )
            self.db.flush()
            return self.get_workspace(workspace.workspace_id)
        except SQLAlchemyError:
            logger.exception(
                "research workspace creation failed", workspace_id=workspace.workspace_id
            )
            raise

    def find_idempotent_resource(self, event_type: str, key: str) -> str | None:
        payload = self.get_idempotent_record(event_type, key)
        return str(payload.get("resource_id")) if payload is not None else None

    def get_idempotent_record(self, event_type: str, key: str) -> dict | None:
        row = self.db.scalar(
            select(DomainEventDB).where(
                DomainEventDB.event_type == event_type,
                DomainEventDB.idempotency_key == f"{event_type}:{key}",
            )
        )
        return dict(row.payload or {}) if row is not None else None

    def record_idempotent_resource(
        self,
        event_type: str,
        key: str,
        resource_id: str,
        *,
        occurred_at: datetime,
        metadata: dict | None = None,
    ) -> None:
        if self.find_idempotent_resource(event_type, key) is not None:
            return
        self._append_event(
            event_type=event_type,
            aggregate_type="idempotency",
            aggregate_id=f"{event_type}:{key}",
            idempotency_key=f"{event_type}:{key}",
            occurred_at=occurred_at,
            payload={"resource_id": resource_id, **(metadata or {})},
        )
        self.db.flush()

    def get_workspace(self, workspace_id: str) -> ResearchWorkspace:
        row = self.db.get(ResearchWorkspaceDB, workspace_id)
        if row is None:
            raise KeyError(workspace_id)
        return self._to_workspace(row)

    def get_workspace_scoped(self, workspace_id: str, project_id: str) -> ResearchWorkspace:
        row = self.db.scalar(
            select(ResearchWorkspaceDB).where(
                ResearchWorkspaceDB.workspace_id == workspace_id,
                ResearchWorkspaceDB.project_id == project_id,
            )
        )
        if row is None:
            raise ValueError("workspace does not belong to project")
        return self._to_workspace(row)

    def list_workspaces(self, project_id: str | None = None) -> list[ResearchWorkspace]:
        query = select(ResearchWorkspaceDB)
        if project_id is not None:
            query = query.where(ResearchWorkspaceDB.project_id == project_id)
        rows = self.db.scalars(query.order_by(ResearchWorkspaceDB.updated_at.desc())).all()
        return [self._to_workspace(row) for row in rows]

    def create_session(self, session: ResearchSession, *, idempotency_key: str) -> ResearchSession:
        existing = self.db.scalar(
            select(ResearchSessionDB).where(ResearchSessionDB.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if (
                existing.mode != session.mode.value
                or existing.workspace_id != session.workspace_id
                or existing.run_id != session.run_id
            ):
                raise ValueError("session idempotency key conflicts with changed request")
            return self._to_session(existing)
        self.db.add(
            ResearchSessionDB(
                session_id=session.session_id,
                workspace_id=session.workspace_id,
                run_id=session.run_id,
                mode=session.mode.value,
                status=session.status.value,
                idempotency_key=idempotency_key,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
        )
        self.db.flush()
        return self.get_session(session.session_id)

    def get_session(self, session_id: str, *, for_update: bool = False) -> ResearchSession:
        query = select(ResearchSessionDB).where(ResearchSessionDB.session_id == session_id)
        if for_update:
            query = query.with_for_update()
        row = self.db.scalar(query)
        if row is None:
            raise KeyError(session_id)
        return self._to_session(row)

    def get_session_scoped(
        self,
        session_id: str,
        *,
        project_id: str,
        workspace_id: str,
        for_update: bool = False,
    ) -> ResearchSession:
        query = (
            select(ResearchSessionDB)
            .join(
                ResearchWorkspaceDB,
                ResearchWorkspaceDB.workspace_id == ResearchSessionDB.workspace_id,
            )
            .where(
                ResearchSessionDB.session_id == session_id,
                ResearchSessionDB.workspace_id == workspace_id,
                ResearchWorkspaceDB.project_id == project_id,
            )
        )
        if for_update:
            query = query.with_for_update()
        row = self.db.scalar(query)
        if row is None:
            raise ValueError("session does not belong to project/workspace")
        return self._to_session(row)

    def promote_session(
        self, session_id: str, workspace_id: str, *, now: datetime
    ) -> ResearchSession:
        self.get_workspace(workspace_id)
        row = self.db.scalar(
            select(ResearchSessionDB)
            .where(ResearchSessionDB.session_id == session_id)
            .with_for_update()
        )
        if row is None:
            raise KeyError(session_id)
        if row.mode == SessionMode.WORKSPACE.value:
            if row.workspace_id != workspace_id:
                raise ValueError("session was promoted to another workspace")
            return self._to_session(row)
        if row.status != SessionStatus.ACTIVE.value:
            raise ValueError("only active temporary sessions can be promoted")
        row.mode = SessionMode.WORKSPACE.value
        row.workspace_id = workspace_id
        row.status = SessionStatus.PROMOTED.value
        row.updated_at = now
        self.db.flush()
        return self._to_session(row)

    def append_message(self, message: ResearchMessage) -> ResearchMessage:
        self.get_session(message.session_id)
        existing = self.db.scalar(
            select(ResearchMessageDB).where(
                ResearchMessageDB.session_id == message.session_id,
                ResearchMessageDB.idempotency_key == message.idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.role != message.role
                or existing.content != message.content
                or existing.content_ref != message.content_ref
            ):
                raise ValueError("message idempotency key conflicts with changed request")
            return self._to_message(existing)
        self.db.add(
            ResearchMessageDB(
                message_id=message.message_id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                content_ref=message.content_ref,
                idempotency_key=message.idempotency_key,
                created_at=message.created_at,
            )
        )
        self.db.flush()
        return message

    def list_messages(self, session_id: str, *, limit: int = 100) -> list[ResearchMessage]:
        self.get_session(session_id)
        rows = self.db.scalars(
            select(ResearchMessageDB)
            .where(ResearchMessageDB.session_id == session_id)
            .order_by(ResearchMessageDB.created_at.asc(), ResearchMessageDB.message_id.asc())
            .limit(limit)
        ).all()
        return [self._to_message(row) for row in rows]

    def link_session_run(
        self,
        session_id: str,
        run_id: str,
        *,
        now: datetime,
        project_id: str | None = None,
        workspace_id: str | None = None,
    ) -> ResearchSession:
        run = self.db.scalar(
            select(ResearchRunDB).where(ResearchRunDB.run_id == run_id).with_for_update()
        )
        if run is None:
            raise KeyError(run_id)
        row = self.db.scalar(
            select(ResearchSessionDB)
            .where(ResearchSessionDB.session_id == session_id)
            .with_for_update()
        )
        if row is None:
            raise KeyError(session_id)
        if row.workspace_id is None:
            raise ValueError("run can only bind to a workspace session")
        if workspace_id is not None and row.workspace_id != workspace_id:
            raise ValueError("session does not belong to workspace")
        workspace = self.get_workspace(row.workspace_id)
        if project_id is not None and workspace.project_id != project_id:
            raise ValueError("session does not belong to project")
        conflicting_session = self.db.scalar(
            select(ResearchSessionDB.session_id)
            .where(
                ResearchSessionDB.run_id == run_id,
                ResearchSessionDB.session_id != session_id,
            )
            .limit(1)
        )
        if conflicting_session is not None:
            raise ValueError("run is already bound to another session")
        if row.run_id is not None and row.run_id != run_id:
            raise ValueError("session is already bound to another run")
        row.run_id = run_id
        row.updated_at = now
        self.db.flush()
        return self._to_session(row)

    def archive_completed_run(self, run_id: str, *, now: datetime) -> int:
        run = self.db.get(ResearchRunDB, run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status != "completed":
            raise ValueError("only completed runs can be archived")
        rows = self.db.scalars(
            select(ResearchSessionDB).where(ResearchSessionDB.run_id == run_id).with_for_update()
        ).all()
        for row in rows:
            row.status = SessionStatus.ARCHIVED.value
            row.updated_at = now
        self.db.flush()
        return len(rows)

    def run_belongs_to_workspace(self, run_id: str, workspace_id: str) -> bool:
        return (
            self.db.scalar(
                select(ResearchSessionDB.session_id).where(
                    ResearchSessionDB.run_id == run_id,
                    ResearchSessionDB.workspace_id == workspace_id,
                )
            )
            is not None
        )

    def assert_run_scope(self, run_id: str, *, project_id: str, workspace_id: str) -> None:
        self.get_workspace_scoped(workspace_id, project_id)
        if not self.run_belongs_to_workspace(run_id, workspace_id):
            raise ValueError("run does not belong to project/workspace")

    def get_run_scope(self, run_id: str) -> tuple[str, str] | None:
        rows = self.db.execute(
            select(ResearchWorkspaceDB.project_id, ResearchWorkspaceDB.workspace_id)
            .join(
                ResearchSessionDB,
                ResearchSessionDB.workspace_id == ResearchWorkspaceDB.workspace_id,
            )
            .where(ResearchSessionDB.run_id == run_id)
            .distinct()
            .limit(2)
        ).all()
        if len(rows) > 1:
            raise ValueError("run has conflicting workspace ownership")
        if not rows:
            return None
        return str(rows[0][0]), str(rows[0][1])

    def get_session_for_run_scoped(
        self,
        run_id: str,
        *,
        project_id: str,
        workspace_id: str,
    ) -> ResearchSession:
        """Load the one authoritative Session for a Run inside an explicit scope."""

        row = self.db.scalar(
            select(ResearchSessionDB)
            .join(
                ResearchWorkspaceDB,
                ResearchWorkspaceDB.workspace_id == ResearchSessionDB.workspace_id,
            )
            .where(
                ResearchSessionDB.run_id == run_id,
                ResearchSessionDB.workspace_id == workspace_id,
                ResearchWorkspaceDB.project_id == project_id,
            )
            .order_by(ResearchSessionDB.updated_at.desc())
            .limit(1)
        )
        if row is None:
            raise ValueError("run has no Session in the requested project/workspace")
        return self._to_session(row)

    def validate_paragraph_ref(self, run_id: str, paragraph_ref: str) -> None:
        try:
            artifact_id, paragraph_id = paragraph_ref.rsplit("#", 1)
        except ValueError as exc:
            raise ValueError("paragraph_ref must be artifact_id#paragraph_id") from exc
        artifact = self.db.get(ResearchArtifactDB, artifact_id)
        if artifact is None or artifact.run_id != run_id:
            raise ValueError("paragraph artifact does not belong to run")
        paragraphs = list((artifact.payload or {}).get("paragraphs") or [])
        if not any(str(item.get("paragraph_id")) == paragraph_id for item in paragraphs):
            raise ValueError("paragraph_ref does not identify a real artifact paragraph")

    def claim_run_id(self, claim_id: str) -> str:
        row = self.db.get(ResearchClaimDB, claim_id)
        if row is None:
            raise KeyError(claim_id)
        return row.run_id

    def create_note(self, note: ResearchNote, *, note_key: str) -> ResearchNote:
        for retry in range(3):
            try:
                with self.db.begin_nested():
                    candidate = note.model_copy(
                        update={"revision": self.next_note_revision(note.workspace_id, note_key)}
                    )
                    self.db.add(
                        ResearchNoteDB(
                            note_id=candidate.note_id,
                            note_key=note_key,
                            workspace_id=candidate.workspace_id,
                            run_id=candidate.run_id,
                            claim_id=candidate.claim_id,
                            revision=candidate.revision,
                            source_kind=candidate.source_kind,
                            paragraph_ref=candidate.paragraph_ref,
                            summary=candidate.summary,
                            pinned=candidate.pinned,
                            created_at=candidate.created_at,
                        )
                    )
                    self.db.flush()
                return candidate
            except IntegrityError:
                logger.warning(
                    "research note revision conflict retried",
                    workspace_id=note.workspace_id,
                    note_key=note_key,
                    retry=retry + 1,
                )
                self.db.expire_all()
        raise ValueError("research note revision conflict after retries")

    def next_note_revision(self, workspace_id: str, note_key: str) -> int:
        self.db.scalar(
            select(ResearchWorkspaceDB)
            .where(ResearchWorkspaceDB.workspace_id == workspace_id)
            .with_for_update()
        )
        current = self.db.scalar(
            select(func.max(ResearchNoteDB.revision)).where(
                ResearchNoteDB.workspace_id == workspace_id,
                ResearchNoteDB.note_key == note_key,
            )
        )
        return int(current or 0) + 1

    def reserve_operation(
        self,
        *,
        operation: str,
        target_id: str,
        idempotency_key: str,
        request_hash: str,
        resource_id: str,
        occurred_at: datetime,
    ) -> str:
        """Atomically reserve one global idempotency key before side effects."""

        key = f"research_operation:{idempotency_key}"
        existing = self.db.scalar(
            select(DomainEventDB).where(DomainEventDB.idempotency_key == key).with_for_update()
        )
        expected = {
            "operation": operation,
            "target_id": target_id,
            "request_hash": request_hash,
            "resource_id": resource_id,
        }
        if existing is not None:
            payload = dict(existing.payload or {})
            if any(
                payload.get(field) != expected[field]
                for field in expected
                if field != "resource_id"
            ):
                raise ValueError("idempotency key conflicts with another operation or target")
            return str(payload["resource_id"])
        try:
            with self.db.begin_nested():
                self._append_event(
                    event_type="research.operation_reserved",
                    aggregate_type="research_operation",
                    aggregate_id=target_id,
                    idempotency_key=key,
                    occurred_at=occurred_at,
                    payload=expected,
                )
                self.db.flush()
        except IntegrityError as exc:
            logger.warning(
                "research operation reservation raced",
                operation=operation,
                target_id=target_id,
            )
            raced = self.db.scalar(
                select(DomainEventDB).where(DomainEventDB.idempotency_key == key)
            )
            if raced is not None:
                payload = dict(raced.payload or {})
                if all(
                    payload.get(field) == expected[field]
                    for field in expected
                    if field != "resource_id"
                ):
                    return str(payload["resource_id"])
            raise ValueError("idempotency reservation conflict; retry request") from exc
        return resource_id

    def claim_run_execution(self, run_id: str, *, allowed_statuses: set[str]) -> str:
        """Lock the Run row and reject concurrent or invalid execution transitions."""

        row = self.db.scalar(self.run_lock_statement(run_id))
        if row is None:
            raise KeyError(run_id)
        if row.status not in allowed_statuses:
            raise ValueError(f"research run cannot execute from {row.status}")
        row.status = "planning"
        row.updated_at = datetime.now(UTC)
        self.db.flush()
        return row.status

    @staticmethod
    def run_lock_statement(run_id: str):
        return select(ResearchRunDB).where(ResearchRunDB.run_id == run_id).with_for_update()

    def list_latest_notes(self, workspace_id: str) -> list[ResearchNote]:
        self.get_workspace(workspace_id)
        rows = self.db.scalars(
            select(ResearchNoteDB)
            .where(
                ResearchNoteDB.workspace_id == workspace_id,
                ResearchNoteDB.pinned.is_(True),
            )
            .order_by(
                ResearchNoteDB.note_key.asc(),
                ResearchNoteDB.revision.desc(),
            )
        ).all()
        latest: dict[str, ResearchNoteDB] = {}
        for row in rows:
            latest.setdefault(row.note_key, row)
        return [self._to_note(row) for row in latest.values()]

    def save_runtime_provider(self, provider: RuntimeProvider) -> RuntimeProvider:
        row = self.db.get(RuntimeProviderDB, provider.provider_id)
        if row is None:
            row = RuntimeProviderDB(
                provider_id=provider.provider_id, created_at=provider.checked_at
            )
            self.db.add(row)
        row.provider_type = provider.provider_type
        row.name = provider.name
        row.capabilities = sorted(provider.capabilities)
        row.status = provider.status.value
        row.config_ref = provider.config_ref
        row.checked_at = provider.checked_at
        row.updated_at = provider.checked_at
        self.db.flush()
        return provider

    def list_runtime_providers(self) -> list[RuntimeProvider]:
        rows = self.db.scalars(
            select(RuntimeProviderDB).order_by(RuntimeProviderDB.provider_id)
        ).all()
        return [self._to_provider(row) for row in rows]

    def accept_provider_result(
        self,
        result: ProviderExecutionResult,
        *,
        request_hash: str,
    ) -> ProviderExecutionResult:
        """Store one immutable provider callback using its provider-owned result ID."""

        key = f"runtime_provider.result:{result.provider_result_id}"
        existing = self.db.scalar(
            select(DomainEventDB).where(DomainEventDB.idempotency_key == key).with_for_update()
        )
        serialized = result.model_dump(mode="json")
        if existing is not None:
            payload = dict(existing.payload or {})
            if payload.get("request_hash") != request_hash or payload.get("result") != serialized:
                raise ValueError("provider result idempotency conflict")
            return ProviderExecutionResult.model_validate(payload["result"])
        try:
            with self.db.begin_nested():
                self._append_event(
                    event_type="runtime_provider.result_received",
                    aggregate_type="runtime_provider_result",
                    aggregate_id=result.provider_result_id,
                    idempotency_key=key,
                    occurred_at=datetime.now(UTC),
                    payload={"request_hash": request_hash, "result": serialized},
                )
                self.db.flush()
        except IntegrityError as exc:
            replay = self.db.scalar(
                select(DomainEventDB).where(DomainEventDB.idempotency_key == key)
            )
            payload = dict(replay.payload or {}) if replay is not None else {}
            if payload.get("request_hash") == request_hash and payload.get("result") == serialized:
                return ProviderExecutionResult.model_validate(payload["result"])
            raise ValueError("provider result idempotency conflict") from exc
        return result

    def save_skill(self, manifest: SkillManifest, *, now: datetime) -> SkillManifest:
        row = self.db.scalar(
            select(SkillDefinitionDB).where(
                SkillDefinitionDB.skill_key == manifest.skill_key,
                SkillDefinitionDB.version == manifest.version,
            )
        )
        serialized = manifest.model_dump(mode="json")
        content_hash = hashlib.sha256(
            json.dumps(serialized, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        if row is None:
            row = SkillDefinitionDB(
                skill_id=f"skill-{uuid4().hex}",
                skill_key=manifest.skill_key,
                version=manifest.version,
                created_at=now,
            )
            self.db.add(row)
        row.status = manifest.status
        row.manifest = serialized
        row.allowed_tools = manifest.allowed_tools
        row.content_hash = content_hash
        row.updated_at = now
        self.db.flush()
        return manifest

    def list_skills(self) -> list[SkillManifest]:
        rows = self.db.scalars(
            select(SkillDefinitionDB).order_by(
                SkillDefinitionDB.skill_key, SkillDefinitionDB.version
            )
        ).all()
        return [SkillManifest.model_validate(row.manifest) for row in rows]

    def get_skill(self, skill_key: str) -> SkillManifest:
        row = self.db.scalar(
            select(SkillDefinitionDB)
            .where(
                SkillDefinitionDB.skill_key == skill_key,
                SkillDefinitionDB.status == "enabled",
            )
            .order_by(SkillDefinitionDB.updated_at.desc())
            .limit(1)
        )
        if row is None:
            raise KeyError(skill_key)
        return SkillManifest.model_validate(row.manifest)

    def save_agent_team(self, team: AgentTeamDefinition) -> AgentTeamDefinition:
        row = self.db.get(AgentTeamDB, team.team_id)
        now = datetime.now(UTC)
        if row is None:
            row = AgentTeamDB(team_id=team.team_id, created_at=now)
            self.db.add(row)
        row.name = team.name
        row.supervisor_role = team.supervisor_role
        row.roles = team.roles
        row.budget = team.budget.model_dump(mode="json")
        row.skill_keys = team.skill_keys
        row.status = team.status
        row.updated_at = now
        self.db.flush()
        return team

    def list_agent_teams(self) -> list[AgentTeamDefinition]:
        rows = self.db.scalars(select(AgentTeamDB).order_by(AgentTeamDB.team_id)).all()
        return [self._to_team(row) for row in rows]

    def get_agent_team(self, team_id: str) -> AgentTeamDefinition:
        row = self.db.get(AgentTeamDB, team_id)
        if row is None:
            raise KeyError(team_id)
        return self._to_team(row)

    def save_agent_schedule(self, schedule: AgentSchedule) -> AgentSchedule:
        self.get_agent_team(schedule.team_id)
        row = self.db.get(AgentScheduleDB, schedule.schedule_id)
        now = datetime.now(UTC)
        if row is None:
            row = AgentScheduleDB(schedule_id=schedule.schedule_id, created_at=now)
            self.db.add(row)
        row.team_id = schedule.team_id
        row.scheduled_job_id = schedule.scheduled_job_id
        row.cron_expression = schedule.cron_expression
        row.status = schedule.status
        row.allow_concurrent = schedule.allow_concurrent
        row.coalesce_policy = schedule.coalesce_policy
        row.last_run_at = schedule.last_run_at
        row.next_run_at = schedule.next_run_at
        row.updated_at = now
        self.db.flush()
        return schedule

    def get_schedule_row(self, schedule_id: str, *, for_update: bool = False) -> AgentScheduleDB:
        query = select(AgentScheduleDB).where(AgentScheduleDB.schedule_id == schedule_id)
        if for_update:
            query = query.with_for_update()
        row = self.db.scalar(query)
        if row is None:
            raise KeyError(schedule_id)
        return row

    def list_agent_schedules(self) -> list[AgentSchedule]:
        rows = self.db.scalars(select(AgentScheduleDB).order_by(AgentScheduleDB.schedule_id)).all()
        return [self._to_schedule(row) for row in rows]

    def reserve_agent_schedule_execution(
        self,
        job_id: str,
        *,
        schedule_id: str,
        attempt: int,
        occurred_at: datetime,
        reservation_seconds: int,
    ) -> tuple[str, bool, int]:
        """Acquire or take over an expired durable side-effect reservation."""

        if reservation_seconds < 1:
            raise ValueError("reservation_seconds must be positive")
        job_row = self.get_job(job_id, for_update=True)
        if job_row.attempt != attempt:
            raise ValueError("stale execution attempt cannot reserve Agent Schedule work")
        terminal = self.get_agent_schedule_execution_result(job_id)
        if terminal is not None:
            return str(terminal["execution_id"]), False, int(terminal["first_attempt"])
        existing = self.db.scalar(
            select(DomainEventDB)
            .where(
                DomainEventDB.aggregate_type == "agent_schedule_execution",
                DomainEventDB.aggregate_id == job_id,
                DomainEventDB.event_type.in_(
                    [
                        "agent_schedule.execution_reserved",
                        "agent_schedule.execution_reservation_taken_over",
                    ]
                ),
            )
            .order_by(DomainEventDB.sequence.desc())
            .limit(1)
        )
        if existing is not None:
            existing_payload = dict(existing.payload or {})
            expires_at = _aware(
                datetime.fromisoformat(str(existing_payload["reservation_expires_at"]))
            )
            if expires_at > _aware(occurred_at):
                return (
                    str(existing_payload["execution_id"]),
                    False,
                    int(existing_payload["first_attempt"]),
                )
            previous_attempt = int(existing_payload["reservation_attempt"])
            if attempt <= previous_attempt:
                raise ValueError("reservation takeover requires a newer fencing attempt")
            execution_id = str(existing_payload["execution_id"])
            first_attempt = int(existing_payload["first_attempt"])
            sequence = existing.sequence + 1
            event_type = "agent_schedule.execution_reservation_taken_over"
        else:
            execution_id = f"agent-schedule-execution:{job_id}"
            first_attempt = attempt
            sequence = 0
            event_type = "agent_schedule.execution_reserved"
        self._append_event(
            event_type=event_type,
            aggregate_type="agent_schedule_execution",
            aggregate_id=job_id,
            idempotency_key=f"agent_schedule.execution_reservation:{job_id}:{attempt}",
            occurred_at=occurred_at,
            payload={
                "status": "reserved",
                "execution_id": execution_id,
                "job_id": job_id,
                "schedule_id": schedule_id,
                "first_attempt": first_attempt,
                "reservation_attempt": attempt,
                "reservation_expires_at": (
                    _aware(occurred_at) + timedelta(seconds=reservation_seconds)
                ).isoformat(),
            },
            sequence=sequence,
        )
        self.db.flush()
        return execution_id, True, first_attempt

    def get_agent_schedule_execution_result(self, job_id: str) -> dict | None:
        row = self.db.scalar(
            select(DomainEventDB)
            .where(
                DomainEventDB.aggregate_type == "agent_schedule_execution",
                DomainEventDB.aggregate_id == job_id,
                DomainEventDB.event_type.in_(
                    [
                        "agent_schedule.execution_completed",
                        "agent_schedule.execution_blocked",
                        "agent_schedule.execution_failed",
                    ]
                ),
            )
            .order_by(DomainEventDB.sequence.desc())
            .limit(1)
        )
        return dict(row.payload or {}) if row is not None else None

    def record_agent_schedule_execution_result(
        self,
        job_id: str,
        *,
        writer_attempt: int,
        payload: dict,
        occurred_at: datetime,
    ) -> dict:
        """Persist a terminal result before the scheduler completion acknowledgement."""

        job_row = self.get_job(job_id, for_update=True)
        latest_reservation = self.db.scalar(
            select(DomainEventDB)
            .where(
                DomainEventDB.aggregate_type == "agent_schedule_execution",
                DomainEventDB.aggregate_id == job_id,
                DomainEventDB.event_type.in_(
                    [
                        "agent_schedule.execution_reserved",
                        "agent_schedule.execution_reservation_taken_over",
                    ]
                ),
            )
            .order_by(DomainEventDB.sequence.desc())
            .limit(1)
        )
        reservation_attempt = (
            int((latest_reservation.payload or {})["reservation_attempt"])
            if latest_reservation is not None
            else None
        )
        if job_row.attempt != writer_attempt or reservation_attempt != writer_attempt:
            raise ValueError("stale execution attempt cannot write terminal result")
        if int(payload.get("completed_attempt", -1)) != writer_attempt:
            raise ValueError("terminal completed_attempt does not match writer fencing token")
        existing = self.get_agent_schedule_execution_result(job_id)
        if existing is not None:
            if existing != payload:
                raise ValueError("agent schedule execution terminal result conflict")
            return existing
        current_sequence = self.db.scalar(
            select(func.max(DomainEventDB.sequence)).where(
                DomainEventDB.aggregate_type == "agent_schedule_execution",
                DomainEventDB.aggregate_id == job_id,
            )
        )
        self._append_event(
            event_type=f"agent_schedule.execution_{payload['status']}",
            aggregate_type="agent_schedule_execution",
            aggregate_id=job_id,
            idempotency_key=f"agent_schedule.execution_terminal:{job_id}",
            occurred_at=occurred_at,
            payload=payload,
            sequence=int(current_sequence) + 1 if current_sequence is not None else 0,
        )
        self.db.flush()
        return payload

    def due_agent_schedule_rows(self, now: datetime) -> list[AgentScheduleDB]:
        """Lock active schedule definitions whose next occurrence is due."""

        return list(
            self.db.scalars(
                select(AgentScheduleDB)
                .where(
                    AgentScheduleDB.status == "active",
                    AgentScheduleDB.next_run_at.is_not(None),
                    AgentScheduleDB.next_run_at <= now,
                )
                .order_by(AgentScheduleDB.next_run_at.asc(), AgentScheduleDB.schedule_id.asc())
                .with_for_update(skip_locked=True)
            ).all()
        )

    def get_job(self, job_id: str, *, for_update: bool = False) -> ScheduledJobDB:
        query = select(ScheduledJobDB).where(ScheduledJobDB.job_id == job_id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self.db.scalar(query)
        if row is None:
            raise KeyError(job_id)
        return row

    def find_job_by_idempotency(self, owner: str, key: str) -> ScheduledJobDB | None:
        return self.db.scalar(
            select(ScheduledJobDB).where(
                ScheduledJobDB.owner == owner,
                ScheduledJobDB.idempotency_key == key,
            )
        )

    def active_job(self, owner: str) -> ScheduledJobDB | None:
        return self.db.scalar(
            select(ScheduledJobDB)
            .where(
                ScheduledJobDB.owner == owner,
                ScheduledJobDB.status.in_(["idle", "leased", "running"]),
            )
            .order_by(ScheduledJobDB.scheduled_for.desc())
            .limit(1)
            .with_for_update()
        )

    def add_job(self, row: ScheduledJobDB) -> ScheduledJobDB:
        self.db.add(row)
        self.db.flush()
        return row

    def claimable_due_job(
        self,
        *,
        job_types: set[str],
        now: datetime,
    ) -> ScheduledJobDB | None:
        """Lock one due or expired-lease job for the generic coordinator."""

        return self.db.scalar(self.due_job_lock_statement(job_types=job_types, now=now))

    @staticmethod
    def due_job_lock_statement(*, job_types: set[str], now: datetime):
        return (
            select(ScheduledJobDB)
            .where(
                ScheduledJobDB.job_type.in_(sorted(job_types)),
                ScheduledJobDB.scheduled_for <= now,
                or_(
                    ScheduledJobDB.status == "idle",
                    and_(
                        ScheduledJobDB.status.in_(["leased", "running"]),
                        ScheduledJobDB.lease_expires_at <= now,
                    ),
                ),
            )
            .order_by(ScheduledJobDB.scheduled_for.asc(), ScheduledJobDB.job_id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )

    def count_pending_jobs(self, owner: str) -> int:
        return int(
            self.db.scalar(
                select(func.count(ScheduledJobDB.job_id)).where(
                    ScheduledJobDB.owner == owner,
                    ScheduledJobDB.status.in_(["idle", "leased", "running"]),
                )
            )
            or 0
        )

    def record_run_event(
        self,
        run_id: str,
        *,
        status: str,
        stage: str,
        occurred_at: datetime,
        idempotency_key: str,
    ) -> None:
        self.db.scalar(
            select(ResearchRunDB).where(ResearchRunDB.run_id == run_id).with_for_update()
        )
        existing = self.db.scalar(
            select(DomainEventDB).where(
                DomainEventDB.idempotency_key == f"research_run.event:{idempotency_key}"
            )
        )
        if existing is not None:
            return
        current_sequence = self.db.scalar(
            select(func.max(DomainEventDB.sequence)).where(
                DomainEventDB.aggregate_type == "research_run",
                DomainEventDB.aggregate_id == run_id,
            )
        )
        sequence = int(current_sequence) + 1 if current_sequence is not None else 0
        self._append_event(
            event_type="research_run.status_changed",
            aggregate_type="research_run",
            aggregate_id=run_id,
            idempotency_key=f"research_run.event:{idempotency_key}",
            occurred_at=occurred_at,
            payload={"status": status, "stage": stage},
            sequence=sequence,
        )
        self.db.flush()

    def record_archive_pending(self, run_id: str, *, occurred_at: datetime) -> None:
        existing = self.db.scalar(
            select(DomainEventDB).where(
                DomainEventDB.idempotency_key == f"research_run.archive_pending:{run_id}"
            )
        )
        if existing is not None:
            return
        self.db.scalar(
            select(ResearchRunDB).where(ResearchRunDB.run_id == run_id).with_for_update()
        )
        self._append_event(
            event_type="research_run.archive_pending",
            aggregate_type="research_run",
            aggregate_id=run_id,
            idempotency_key=f"research_run.archive_pending:{run_id}",
            occurred_at=occurred_at,
            payload={"status": "archive_pending", "stage": "archive"},
            sequence=self._next_event_sequence(run_id),
        )
        self.db.flush()

    def mark_archive_processed(self, run_id: str, *, occurred_at: datetime) -> None:
        row = self.db.scalar(
            select(DomainEventDB)
            .where(DomainEventDB.idempotency_key == f"research_run.archive_pending:{run_id}")
            .with_for_update()
        )
        if row is None:
            raise KeyError(run_id)
        row.published_at = occurred_at
        self.db.flush()

    def list_run_events(self, run_id: str, after_event_id: str | None = None) -> list[dict]:
        after_sequence = -1
        if after_event_id:
            anchor = self.db.get(DomainEventDB, after_event_id)
            if (
                anchor is None
                or anchor.aggregate_type != "research_run"
                or anchor.aggregate_id != run_id
            ):
                raise KeyError(after_event_id)
            after_sequence = anchor.sequence
        rows = self.db.scalars(
            select(DomainEventDB)
            .where(
                DomainEventDB.aggregate_type == "research_run",
                DomainEventDB.aggregate_id == run_id,
                DomainEventDB.sequence > after_sequence,
            )
            .order_by(DomainEventDB.sequence.asc())
        ).all()
        return [
            {
                "event_id": row.event_id,
                "sequence": row.sequence,
                "status": (row.payload or {}).get("status"),
                "stage": (row.payload or {}).get("stage"),
            }
            for row in rows
            if row.event_type == "research_run.status_changed"
            or (row.event_type == "research_run.archive_pending" and row.published_at is None)
        ]

    def _next_event_sequence(self, aggregate_id: str) -> int:
        current = self.db.scalar(
            select(func.max(DomainEventDB.sequence)).where(
                DomainEventDB.aggregate_type == "research_run",
                DomainEventDB.aggregate_id == aggregate_id,
            )
        )
        return int(current) + 1 if current is not None else 0

    def _append_event(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        idempotency_key: str,
        occurred_at: datetime,
        payload: dict,
        sequence: int = 0,
    ) -> None:
        self.db.add(
            DomainEventDB(
                event_id=f"event-{uuid4().hex}",
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                sequence=sequence,
                occurred_at=occurred_at,
                payload_ref=f"{aggregate_type}:{aggregate_id}",
                payload=payload,
                idempotency_key=idempotency_key,
            )
        )

    @staticmethod
    def to_scheduled_job(row: ScheduledJobDB) -> ScheduledJob:
        return ScheduledJob(
            job_id=row.job_id,
            owner=row.owner,
            job_type=row.job_type,
            idempotency_key=row.idempotency_key,
            status=ScheduledJobStatus(row.status),
            scheduled_for=_aware(row.scheduled_for),
            allow_concurrent=row.allow_concurrent,
            coalesce_policy=row.coalesce_policy,
            lease_owner=row.lease_owner,
            lease_expires_at=_aware(row.lease_expires_at) if row.lease_expires_at else None,
            payload=row.payload or {},
            attempt=row.attempt,
            fencing_token=row.attempt,
            last_error_code=row.last_error_code,
        )

    @staticmethod
    def _to_workspace(row: ResearchWorkspaceDB) -> ResearchWorkspace:
        return ResearchWorkspace(
            workspace_id=row.workspace_id,
            project_id=row.project_id,
            title=row.title,
            status=WorkspaceStatus(row.status),
            created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at),
            archived_at=_aware(row.archived_at) if row.archived_at else None,
        )

    @staticmethod
    def _to_session(row: ResearchSessionDB) -> ResearchSession:
        return ResearchSession(
            session_id=row.session_id,
            mode=SessionMode(row.mode),
            status=SessionStatus(row.status),
            workspace_id=row.workspace_id,
            run_id=row.run_id,
            created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at),
        )

    @staticmethod
    def _to_message(row: ResearchMessageDB) -> ResearchMessage:
        return ResearchMessage(
            message_id=row.message_id,
            session_id=row.session_id,
            role=row.role,
            content=row.content,
            content_ref=row.content_ref,
            idempotency_key=row.idempotency_key,
            created_at=_aware(row.created_at),
        )

    @staticmethod
    def _to_note(row: ResearchNoteDB) -> ResearchNote:
        return ResearchNote(
            note_id=row.note_id,
            workspace_id=row.workspace_id,
            revision=row.revision,
            source_kind=row.source_kind,
            run_id=row.run_id,
            claim_id=row.claim_id,
            paragraph_ref=row.paragraph_ref,
            summary=row.summary,
            pinned=row.pinned,
            created_at=_aware(row.created_at),
        )

    @staticmethod
    def _to_provider(row: RuntimeProviderDB) -> RuntimeProvider:
        return RuntimeProvider(
            provider_id=row.provider_id,
            provider_type=row.provider_type,
            name=row.name,
            capabilities=set(row.capabilities or []),
            status=row.status,
            config_ref=row.config_ref,
            checked_at=_aware(row.checked_at),
        )

    @staticmethod
    def _to_team(row: AgentTeamDB) -> AgentTeamDefinition:
        return AgentTeamDefinition(
            team_id=row.team_id,
            name=row.name,
            supervisor_role=row.supervisor_role,
            roles=row.roles or [],
            budget=row.budget or {},
            skill_keys=row.skill_keys or [],
            status=row.status,
        )

    @staticmethod
    def _to_schedule(row: AgentScheduleDB) -> AgentSchedule:
        return AgentSchedule(
            schedule_id=row.schedule_id,
            team_id=row.team_id,
            scheduled_job_id=row.scheduled_job_id,
            cron_expression=row.cron_expression,
            status=row.status,
            allow_concurrent=row.allow_concurrent,
            coalesce_policy=row.coalesce_policy,
            last_run_at=_aware(row.last_run_at) if row.last_run_at else None,
            next_run_at=_aware(row.next_run_at) if row.next_run_at else None,
        )
