"""PostgreSQL repository for the runtime-neutral v2 workflow ledger."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from sqlalchemy.orm import Session

from core.contracts.runtime import (
    AlphaEvent,
    EvidenceRecord,
    WorkflowRunResult,
    WorkflowSpec,
)
from data_layer.repositories.models import (
    RuntimeArtifactDB,
    RuntimeEventDB,
    RuntimeEvidenceDB,
    RuntimeWorkflowRunDB,
    RuntimeWorkflowStepDB,
    utc_now,
)


class RuntimeWorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(
        self, *, run_id: str, workflow: WorkflowSpec, runtime_id: str, request_payload: dict
    ) -> None:
        self.db.add(
            RuntimeWorkflowRunDB(
                run_id=run_id,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                runtime_id=runtime_id,
                request_payload=request_payload,
                workflow_payload=workflow.model_dump(mode="json"),
                status="draft",
            )
        )
        for step in workflow.steps:
            self.db.add(
                RuntimeWorkflowStepDB(
                    step_execution_id=f"step_{uuid4().hex}",
                    run_id=run_id,
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    status="planned",
                )
            )
        self.db.flush()

    def get_run_or_raise(self, run_id: str) -> RuntimeWorkflowRunDB:
        row = self.db.get(RuntimeWorkflowRunDB, run_id)
        if row is None:
            raise KeyError(run_id)
        return row

    def update_status(self, run_id: str, status: str, *, error_message: str | None = None) -> None:
        row = self.get_run_or_raise(run_id)
        row.status, row.error_message, row.updated_at = status, error_message, utc_now()
        if status in {"completed", "cancelled"}:
            row.completed_at = utc_now()
        self.db.flush()

    def append_events(self, events: list[AlphaEvent]) -> None:
        last = (
            self.db.query(RuntimeEventDB.sequence)
            .filter_by(run_id=events[0].run_id if events else "")
            .order_by(RuntimeEventDB.sequence.desc())
            .first()
        )
        offset = (last[0] + 1) if last is not None else 0
        for index, event in enumerate(events):
            if self.db.get(RuntimeEventDB, event.event_id) is None:
                self.db.add(
                    RuntimeEventDB(
                        event_id=event.event_id,
                        run_id=event.run_id,
                        sequence=offset + index,
                        event_type=event.event_type,
                        payload=event.payload,
                        occurred_at=event.occurred_at,
                    )
                )
        self.db.flush()

    def list_events(self, run_id: str, *, after_sequence: int = -1) -> list[AlphaEvent]:
        rows = (
            self.db.query(RuntimeEventDB)
            .filter(RuntimeEventDB.run_id == run_id, RuntimeEventDB.sequence > after_sequence)
            .order_by(RuntimeEventDB.sequence)
            .all()
        )
        return [
            AlphaEvent(
                event_id=row.event_id,
                event_type=row.event_type,
                run_id=row.run_id,
                sequence=row.sequence,
                occurred_at=row.occurred_at,
                payload=row.payload or {},
            )
            for row in rows
        ]

    def replace_evidence(self, run_id: str, evidence: list[EvidenceRecord]) -> None:
        existing = {
            row[0] for row in self.db.query(RuntimeEvidenceDB.evidence_id).filter_by(run_id=run_id)
        }
        for item in evidence:
            if item.evidence_id not in existing:
                self.db.add(
                    RuntimeEvidenceDB(
                        evidence_id=item.evidence_id,
                        run_id=run_id,
                        source_ref=item.source_ref,
                        source_name=item.source_name,
                        summary=item.summary,
                        observed_at=item.observed_at,
                        conflict=item.conflict,
                    )
                )
        self.db.flush()

    def append_result_artifact(self, result: WorkflowRunResult) -> None:
        if result.report_document is None:
            return
        payload = result.report_document.model_dump(mode="json")
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        content_hash = hashlib.sha256(encoded).hexdigest()
        exists = (
            self.db.query(RuntimeArtifactDB)
            .filter_by(
                run_id=result.run_id, artifact_type="report_document", content_hash=content_hash
            )
            .first()
        )
        if exists is None:
            self.db.add(
                RuntimeArtifactDB(
                    artifact_id=f"artifact_{uuid4().hex}",
                    run_id=result.run_id,
                    artifact_type="report_document",
                    content_hash=content_hash,
                    payload=payload,
                )
            )
            self.db.flush()
