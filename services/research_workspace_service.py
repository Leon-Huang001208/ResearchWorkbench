"""Project-isolated research workspace application service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from core.contracts.research_workspace import (
    ResearchMessage,
    ResearchNote,
    ResearchSession,
    ResearchWorkspace,
    SessionMode,
)
from core.observability import get_logger
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)

logger = get_logger(__name__)


class WorkspaceScopeError(ValueError):
    """A referenced research object does not belong to the requested workspace."""


class ResearchWorkspaceService:
    """Own Workspace/Session/Message/Note lifecycle and scope validation."""

    def __init__(
        self,
        repository: ResearchWorkspaceRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_workspace(
        self, project_id: str, title: str, idempotency_key: str
    ) -> ResearchWorkspace:
        now = self._clock()
        workspace = ResearchWorkspace(
            workspace_id=f"workspace-{uuid4().hex}",
            project_id=project_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        created = self.repository.create_workspace(workspace, idempotency_key=idempotency_key)
        logger.info(
            "research workspace created",
            workspace_id=created.workspace_id,
            project_id=created.project_id,
        )
        return created

    def get_workspace(self, workspace_id: str) -> ResearchWorkspace:
        return self.repository.get_workspace(workspace_id)

    def get_workspace_scoped(self, workspace_id: str, project_id: str) -> ResearchWorkspace:
        try:
            return self.repository.get_workspace_scoped(workspace_id, project_id)
        except ValueError as exc:
            raise WorkspaceScopeError(str(exc)) from exc

    def list_workspaces(self, project_id: str | None = None) -> list[ResearchWorkspace]:
        return self.repository.list_workspaces(project_id)

    def create_session(
        self,
        *,
        mode: SessionMode | str,
        idempotency_key: str,
        workspace_id: str | None = None,
        run_id: str | None = None,
    ) -> ResearchSession:
        normalized_mode = SessionMode(mode)
        if workspace_id is not None:
            self.repository.get_workspace(workspace_id)
        if run_id is not None and normalized_mode is SessionMode.TEMPORARY:
            raise ValueError("temporary session cannot bind a research run")
        now = self._clock()
        session = ResearchSession(
            session_id=f"session-{uuid4().hex}",
            mode=normalized_mode,
            workspace_id=workspace_id,
            run_id=None,
            created_at=now,
            updated_at=now,
        )
        created = self.repository.create_session(session, idempotency_key=idempotency_key)
        if run_id is not None:
            created = self.link_session_run(created.session_id, run_id)
        logger.info(
            "research session created",
            session_id=created.session_id,
            workspace_id=created.workspace_id,
            mode=created.mode.value,
        )
        return created

    def get_session(
        self,
        session_id: str,
        *,
        project_id: str | None = None,
        workspace_id: str | None = None,
    ) -> ResearchSession:
        session = self.repository.get_session(session_id)
        if session.workspace_id is not None:
            if not project_id or workspace_id != session.workspace_id:
                raise WorkspaceScopeError("explicit project/workspace scope is required")
            return self.get_session_scoped(
                session_id, project_id=project_id, workspace_id=workspace_id
            )
        return session

    def get_session_scoped(
        self,
        session_id: str,
        *,
        project_id: str,
        workspace_id: str,
    ) -> ResearchSession:
        try:
            return self.repository.get_session_scoped(
                session_id,
                project_id=project_id,
                workspace_id=workspace_id,
            )
        except ValueError as exc:
            raise WorkspaceScopeError(str(exc)) from exc

    def promote_session(self, session_id: str, workspace_id: str) -> ResearchSession:
        promoted = self.repository.promote_session(session_id, workspace_id, now=self._clock())
        logger.info(
            "research session promoted",
            session_id=session_id,
            workspace_id=workspace_id,
        )
        return promoted

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        idempotency_key: str,
        content: str | None = None,
        content_ref: str | None = None,
        project_id: str | None = None,
        workspace_id: str | None = None,
    ) -> ResearchMessage:
        self.get_session(session_id, project_id=project_id, workspace_id=workspace_id)
        message = ResearchMessage(
            message_id=f"message-{uuid4().hex}",
            session_id=session_id,
            role=role,
            content=content,
            content_ref=content_ref,
            idempotency_key=idempotency_key,
            created_at=self._clock(),
        )
        created = self.repository.append_message(message)
        logger.info(
            "research message persisted",
            session_id=session_id,
            message_id=created.message_id,
            role=created.role,
        )
        return created

    def list_messages(
        self,
        session_id: str,
        *,
        limit: int = 100,
        project_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[ResearchMessage]:
        self.get_session(session_id, project_id=project_id, workspace_id=workspace_id)
        return self.repository.list_messages(session_id, limit=limit)

    def link_session_run(
        self,
        session_id: str,
        run_id: str,
        *,
        project_id: str | None = None,
        workspace_id: str | None = None,
    ) -> ResearchSession:
        try:
            return self.repository.link_session_run(
                session_id,
                run_id,
                now=self._clock(),
                project_id=project_id,
                workspace_id=workspace_id,
            )
        except ValueError as exc:
            raise WorkspaceScopeError(str(exc)) from exc

    def pin_note(
        self,
        workspace_id: str,
        *,
        note_key: str,
        source_kind: str,
        summary: str,
        claim_id: str | None = None,
        run_id: str | None = None,
        paragraph_ref: str | None = None,
    ) -> ResearchNote:
        self.repository.get_workspace(workspace_id)
        effective_run_id = (
            self.repository.claim_run_id(claim_id)
            if source_kind == "claim" and claim_id
            else run_id
        )
        if not effective_run_id or not self.repository.run_belongs_to_workspace(
            effective_run_id, workspace_id
        ):
            logger.warning(
                "research note scope rejected",
                workspace_id=workspace_id,
                run_id=effective_run_id,
                source_kind=source_kind,
            )
            raise WorkspaceScopeError("note source does not belong to workspace")
        if source_kind == "paragraph" and run_id and paragraph_ref:
            self.repository.validate_paragraph_ref(run_id, paragraph_ref)
        note = ResearchNote(
            note_id=f"note-{uuid4().hex}",
            workspace_id=workspace_id,
            revision=self.repository.next_note_revision(workspace_id, note_key),
            source_kind=source_kind,
            run_id=run_id,
            claim_id=claim_id,
            paragraph_ref=paragraph_ref,
            summary=summary,
            pinned=True,
            created_at=self._clock(),
        )
        return self.repository.create_note(note, note_key=note_key)

    def build_memory_context(self, workspace_id: str) -> list[ResearchNote]:
        """Return only the latest pinned revisions in the requested project scope."""

        return self.repository.list_latest_notes(workspace_id)

    def build_run_runtime_context(
        self,
        run_id: str,
        *,
        max_notes: int = 20,
        max_messages: int = 50,
        max_chars: int = 12_000,
    ) -> dict[str, object]:
        """Build bounded memory only from the Run's authoritative project/workspace."""

        scope = self.repository.get_run_scope(run_id)
        if scope is None:
            return {}
        project_id, workspace_id = scope
        self.repository.get_workspace_scoped(workspace_id, project_id)
        session = self.repository.get_session_for_run_scoped(
            run_id,
            project_id=project_id,
            workspace_id=workspace_id,
        )
        remaining = max_chars

        def bounded(value: str | None) -> str | None:
            nonlocal remaining
            if value is None or remaining <= 0:
                return None
            selected = value[:remaining]
            remaining -= len(selected)
            return selected

        notes = []
        for note in self.repository.list_latest_notes(workspace_id)[:max_notes]:
            summary = bounded(note.summary)
            if summary is None:
                break
            notes.append(
                {
                    "note_id": note.note_id,
                    "revision": note.revision,
                    "source_kind": note.source_kind,
                    "summary": summary,
                }
            )
        messages = []
        for message in self.repository.list_messages(
            session.session_id,
            limit=max_messages,
        ):
            content = bounded(message.content)
            content_ref = bounded(message.content_ref)
            if content is None and content_ref is None:
                break
            messages.append(
                {
                    "message_id": message.message_id,
                    "role": message.role,
                    "content": content,
                    "content_ref": content_ref,
                }
            )
        logger.info(
            "bounded research runtime context built",
            run_id=run_id,
            project_id=project_id,
            workspace_id=workspace_id,
            note_count=len(notes),
            message_count=len(messages),
            chars_used=max_chars - remaining,
        )
        return {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "session_id": session.session_id,
            "notes": notes,
            "messages": messages,
            "truncated": remaining == 0,
        }

    def archive_completed_run(self, run_id: str) -> None:
        self.repository.archive_completed_run(run_id, now=self._clock())
        logger.info("completed research run archived", run_id=run_id)

    def archive_completed_run_safely(self, run_id: str) -> None:
        """Process a retryable archive outbox without changing the Run terminal state."""

        try:
            self.repository.record_archive_pending(run_id, occurred_at=self._clock())
            with self.repository.db.begin_nested():
                self.archive_completed_run(run_id)
                self.repository.mark_archive_processed(run_id, occurred_at=self._clock())
        except Exception as exc:  # noqa: BLE001 - archive failure becomes durable retry state
            logger.error(
                "completed research run archive deferred",
                run_id=run_id,
                error_type=type(exc).__name__,
            )

    def record_run_event(
        self,
        run_id: str,
        *,
        status: str,
        stage: str,
        idempotency_key: str,
    ) -> None:
        self.repository.record_run_event(
            run_id,
            status=status,
            stage=stage,
            occurred_at=self._clock(),
            idempotency_key=idempotency_key,
        )

    def list_run_events(self, run_id: str, after_event_id: str | None = None) -> list[dict]:
        return self.repository.list_run_events(run_id, after_event_id)

    def find_idempotent_resource(self, event_type: str, key: str) -> str | None:
        return self.repository.find_idempotent_resource(event_type, key)

    def record_idempotent_resource(self, event_type: str, key: str, resource_id: str) -> None:
        self.repository.record_idempotent_resource(
            event_type,
            key,
            resource_id,
            occurred_at=self._clock(),
        )

    def reserve_operation(
        self,
        *,
        operation: str,
        target_id: str,
        idempotency_key: str,
        request_hash: str,
        resource_id: str,
    ) -> str:
        return self.repository.reserve_operation(
            operation=operation,
            target_id=target_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            resource_id=resource_id,
            occurred_at=self._clock(),
        )

    def claim_run_execution(self, run_id: str, *, allowed_statuses: set[str]) -> None:
        self.repository.claim_run_execution(run_id, allowed_statuses=allowed_statuses)

    def assert_run_scope(self, run_id: str, *, project_id: str, workspace_id: str) -> None:
        try:
            self.repository.assert_run_scope(
                run_id,
                project_id=project_id,
                workspace_id=workspace_id,
            )
        except ValueError as exc:
            raise WorkspaceScopeError(str(exc)) from exc

    def require_run_scope(
        self,
        run_id: str,
        *,
        project_id: str | None,
        workspace_id: str | None,
    ) -> None:
        """Require explicit scope whenever a Run has a Workspace owner."""

        scope = self.repository.get_run_scope(run_id)
        if scope is None:
            return
        if not project_id or not workspace_id or scope != (project_id, workspace_id):
            raise WorkspaceScopeError("explicit project/workspace scope is required for run")
