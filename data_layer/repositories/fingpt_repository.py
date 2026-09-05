"""Persistence for FinGPT governance records, deliberately excluding chat bodies."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from data_layer.repositories.models import (
    FinGPTArtifactLinkDB,
    FinGPTEvidenceReferenceDB,
    FinGPTSessionIndexDB,
    FinGPTSyncEventDB,
    FinGPTTaskDB,
    RuntimeArtifactDB,
    utc_now,
)


class FinGPTRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_task(
        self,
        *,
        preset_id: str,
        title: str,
        launch_id: str | None = None,
        launch_expires_at: datetime | None = None,
        task_metadata: dict | None = None,
    ) -> FinGPTTaskDB:
        row = FinGPTTaskDB(
            task_id=f"fingpt_task_{uuid4().hex}",
            preset_id=preset_id,
            title=title,
            launch_id=launch_id,
            launch_expires_at=launch_expires_at,
            task_metadata=task_metadata or {},
        )
        self.db.add(row)
        self.db.flush()
        return row

    def get_task_or_raise(self, task_id: str) -> FinGPTTaskDB:
        row = self.db.get(FinGPTTaskDB, task_id)
        if row is None:
            raise KeyError(task_id)
        return row

    def list_tasks(self, *, limit: int = 30) -> list[FinGPTTaskDB]:
        return (
            self.db.query(FinGPTTaskDB).order_by(FinGPTTaskDB.created_at.desc()).limit(limit).all()
        )

    def consume_launch(self, launch_id: str) -> FinGPTTaskDB:
        row = self.db.query(FinGPTTaskDB).filter_by(launch_id=launch_id).with_for_update().first()
        if row is None or row.launch_consumed_at is not None:
            raise KeyError(launch_id)
        expiry = row.launch_expires_at
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry is not None and expiry < utc_now():
            raise ValueError("启动任务已过期")
        row.launch_consumed_at = utc_now()
        row.status = "launched"
        row.updated_at = utc_now()
        self.db.flush()
        return row

    def upsert_session(
        self,
        *,
        dsh_session_id: str,
        task_id: str | None,
        status: str,
        sequence: int,
        metadata: dict,
    ) -> FinGPTSessionIndexDB:
        row = self.db.get(FinGPTSessionIndexDB, dsh_session_id)
        if row is None:
            row = FinGPTSessionIndexDB(
                dsh_session_id=dsh_session_id,
                task_id=task_id,
                status=status,
                sync_cursor=sequence,
                session_metadata=metadata,
            )
            self.db.add(row)
        else:
            row.task_id = task_id or row.task_id
            row.status = status
            row.sync_cursor = max(row.sync_cursor, sequence)
            row.session_metadata = {**(row.session_metadata or {}), **metadata}
            row.updated_at = utc_now()
        self.db.flush()
        return row

    def append_sync_event(
        self, *, event_key: str, dsh_session_id: str, sequence: int, event_type: str, payload: dict
    ) -> bool:
        if self.db.get(FinGPTSyncEventDB, event_key) is not None:
            return False
        self.db.add(
            FinGPTSyncEventDB(
                event_key=event_key,
                dsh_session_id=dsh_session_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
            )
        )
        self.db.flush()
        return True

    def list_sessions(self, *, limit: int = 50) -> list[FinGPTSessionIndexDB]:
        return (
            self.db.query(FinGPTSessionIndexDB)
            .order_by(FinGPTSessionIndexDB.updated_at.desc())
            .limit(limit)
            .all()
        )

    def attach_workflow(self, *, task_id: str, workflow_run_id: str) -> None:
        row = self.get_task_or_raise(task_id)
        row.workflow_run_id, row.status, row.updated_at = workflow_run_id, "running", utc_now()
        self.db.flush()

    def link_artifacts_for_workflow(
        self, *, task_id: str, workflow_run_id: str
    ) -> list[RuntimeArtifactDB]:
        artifacts = self.db.query(RuntimeArtifactDB).filter_by(run_id=workflow_run_id).all()
        known = {
            item.artifact_id
            for item in self.db.query(FinGPTArtifactLinkDB.artifact_id).filter_by(task_id=task_id)
        }
        for artifact in artifacts:
            if artifact.artifact_id not in known:
                self.db.add(
                    FinGPTArtifactLinkDB(
                        link_id=f"fingpt_artifact_{uuid4().hex}",
                        task_id=task_id,
                        artifact_id=artifact.artifact_id,
                    )
                )
        if artifacts:
            self.get_task_or_raise(task_id).status = "completed"
        self.db.flush()
        return artifacts

    def list_artifacts(self, task_id: str) -> list[RuntimeArtifactDB]:
        return (
            self.db.query(RuntimeArtifactDB)
            .join(
                FinGPTArtifactLinkDB,
                FinGPTArtifactLinkDB.artifact_id == RuntimeArtifactDB.artifact_id,
            )
            .filter(FinGPTArtifactLinkDB.task_id == task_id)
            .all()
        )

    def add_evidence_reference(
        self,
        *,
        task_id: str | None,
        dsh_session_id: str | None,
        source_ref: str,
        source_name: str,
        provenance: str,
        captured_evidence_id: str | None,
    ) -> None:
        self.db.add(
            FinGPTEvidenceReferenceDB(
                reference_id=f"fingpt_evidence_{uuid4().hex}",
                task_id=task_id,
                dsh_session_id=dsh_session_id,
                source_ref=source_ref,
                source_name=source_name,
                provenance=provenance,
                captured_evidence_id=captured_evidence_id,
            )
        )
        self.db.flush()
