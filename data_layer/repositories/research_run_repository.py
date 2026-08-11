"""Persistence adapter for the Research Run aggregate."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from core.contracts.research import (
    QualityGateResult,
    ResearchArtifact,
    ResearchClaim,
    ResearchRun,
    ResearchRunStatus,
    ResearchSubject,
    ResearchTask,
)
from data_layer.repositories.models import (
    ResearchArtifactDB,
    ResearchClaimDB,
    ResearchQualityGateDB,
    ResearchRunDB,
    ResearchTaskDB,
    utc_now,
)


class ResearchRunRepository:
    """Keep relational storage behind the evidence-first research aggregate."""

    def __init__(self, db: Session):
        self.db = db

    def create_run(self, run: ResearchRun, evidence_inputs: list[dict]) -> ResearchRun:
        self.db.add(
            ResearchRunDB(
                run_id=run.run_id,
                template_key=run.template_key,
                target_id=run.target_id,
                subject_type=run.subject.subject_type,
                subject_payload=run.subject.model_dump(mode="json"),
                as_of=run.as_of,
                question=run.question,
                attachment_refs=run.attachment_refs,
                evidence_inputs=evidence_inputs,
                source_plan=run.source_plan,
                status=run.status.value,
                retry_count=run.retry_count,
                resume_from=run.resume_from,
                blocked_reasons=run.blocked_reasons,
                created_at=run.created_at,
                updated_at=run.updated_at,
            )
        )
        self.db.flush()
        return self.get_run_or_raise(run.run_id)

    def get_run_or_raise(self, run_id: str) -> ResearchRun:
        model = self.db.get(ResearchRunDB, run_id)
        if model is None:
            raise KeyError(run_id)
        return self._to_run(model)

    def get_evidence_inputs(self, run_id: str) -> list[dict]:
        model = self.db.get(ResearchRunDB, run_id)
        if model is None:
            raise KeyError(run_id)
        return list(model.evidence_inputs or [])

    def list_runs(self, *, limit: int = 20) -> list[ResearchRun]:
        rows = (
            self.db.query(ResearchRunDB)
            .order_by(ResearchRunDB.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_run(row) for row in rows]

    def append_evidence_input(self, run_id: str, evidence: dict) -> None:
        model = self.db.get(ResearchRunDB, run_id)
        if model is None:
            raise KeyError(run_id)
        existing = list(model.evidence_inputs or [])
        if any(item["evidence_id"] == evidence["evidence_id"] for item in existing):
            return
        existing.append(evidence)
        model.evidence_inputs = existing
        model.updated_at = utc_now()
        self.db.flush()

    def update_run(
        self,
        run_id: str,
        *,
        status: ResearchRunStatus,
        source_plan: dict | None = None,
        blocked_reasons: list[str] | None = None,
        resume_from: str | None = None,
        increment_retry: bool = False,
        completed_at: datetime | None = None,
    ) -> ResearchRun:
        model = self.db.get(ResearchRunDB, run_id)
        if model is None:
            raise KeyError(run_id)
        model.status = status.value
        if source_plan is not None:
            model.source_plan = source_plan
        if blocked_reasons is not None:
            model.blocked_reasons = blocked_reasons
        model.resume_from = resume_from
        if increment_retry:
            model.retry_count += 1
        if completed_at is not None:
            model.completed_at = completed_at
        model.updated_at = utc_now()
        self.db.flush()
        return self._to_run(model)

    def create_task(self, task: ResearchTask) -> ResearchTask:
        self.db.add(
            ResearchTaskDB(
                task_id=task.task_id,
                run_id=task.run_id,
                task_key=task.task_key,
                status=task.status.value,
                attempt=task.attempt,
                resume_from=task.resume_from,
                state_snapshot=task.state_snapshot,
                error_message=task.error_message,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
        )
        self.db.flush()
        return task

    def get_task_or_raise(self, run_id: str) -> ResearchTask:
        model = self.db.query(ResearchTaskDB).filter_by(run_id=run_id).one_or_none()
        if model is None:
            raise KeyError(run_id)
        return self._to_task(model)

    def update_task(
        self,
        run_id: str,
        *,
        status: ResearchRunStatus,
        attempt: int,
        resume_from: str | None,
        state_snapshot: dict,
        error_message: str | None = None,
    ) -> ResearchTask:
        model = self.db.query(ResearchTaskDB).filter_by(run_id=run_id).one_or_none()
        if model is None:
            raise KeyError(run_id)
        model.status = status.value
        model.attempt = attempt
        model.resume_from = resume_from
        model.state_snapshot = state_snapshot
        model.error_message = error_message
        model.updated_at = utc_now()
        self.db.flush()
        return self._to_task(model)

    def append_artifact(self, artifact: ResearchArtifact) -> ResearchArtifact:
        existing = (
            self.db.query(ResearchArtifactDB)
            .filter_by(run_id=artifact.run_id, artifact_type=artifact.artifact_type)
            .first()
        )
        if existing is not None:
            return self._to_artifact(existing)
        self.db.add(
            ResearchArtifactDB(
                artifact_id=artifact.artifact_id,
                run_id=artifact.run_id,
                artifact_type=artifact.artifact_type,
                payload=artifact.payload,
                created_at=artifact.created_at,
            )
        )
        self.db.flush()
        return artifact

    def replace_claims(self, run_id: str, claims: Iterable[ResearchClaim]) -> list[ResearchClaim]:
        # Claims are the current query projection. Immutable historical output is
        # retained in ResearchArtifact records for every graph attempt.
        self.db.query(ResearchClaimDB).filter_by(run_id=run_id).delete()
        rows = list(claims)
        for claim in rows:
            self.db.add(
                ResearchClaimDB(
                    claim_id=claim.claim_id,
                    run_id=run_id,
                    category=claim.category,
                    text=claim.text,
                    evidence_refs=claim.evidence_refs,
                    numeric_context=claim.numeric_context,
                    conflict_status=claim.conflict_status,
                    created_at=claim.created_at,
                )
            )
        self.db.flush()
        return rows

    def replace_quality_gates(
        self, run_id: str, gates: Iterable[QualityGateResult]
    ) -> list[QualityGateResult]:
        self.db.query(ResearchQualityGateDB).filter_by(run_id=run_id).delete()
        rows = list(gates)
        for gate in rows:
            self.db.add(
                ResearchQualityGateDB(
                    gate_id=gate.gate_id,
                    run_id=run_id,
                    gate_key=gate.gate_key,
                    passed=gate.passed,
                    severity=gate.severity,
                    message=gate.message,
                    details=gate.details,
                    checked_at=gate.checked_at,
                )
            )
        self.db.flush()
        return rows

    def list_artifacts(self, run_id: str) -> list[ResearchArtifact]:
        return [
            self._to_artifact(row)
            for row in self.db.query(ResearchArtifactDB).filter_by(run_id=run_id).all()
        ]

    def list_claims(self, run_id: str) -> list[ResearchClaim]:
        return [
            self._to_claim(row)
            for row in self.db.query(ResearchClaimDB).filter_by(run_id=run_id).all()
        ]

    def list_quality_gates(self, run_id: str) -> list[QualityGateResult]:
        return [
            self._to_gate(row)
            for row in self.db.query(ResearchQualityGateDB).filter_by(run_id=run_id).all()
        ]

    def _to_run(self, model: ResearchRunDB) -> ResearchRun:
        subject_payload = dict(model.subject_payload or {})
        subject_payload.setdefault("subject_type", model.subject_type or "security")
        subject_payload.setdefault("subject_id", model.target_id)
        subject_payload.setdefault("display_name", model.target_id)
        return ResearchRun(
            run_id=model.run_id,
            template_key=model.template_key,
            target_id=model.target_id,
            subject=ResearchSubject.model_validate(subject_payload),
            as_of=model.as_of,
            question=model.question,
            attachment_refs=model.attachment_refs or [],
            source_plan=model.source_plan or {},
            status=ResearchRunStatus(model.status),
            retry_count=model.retry_count,
            resume_from=model.resume_from,
            blocked_reasons=model.blocked_reasons or [],
            quality_gates=self.list_quality_gates(model.run_id),
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )

    @staticmethod
    def _to_artifact(model: ResearchArtifactDB) -> ResearchArtifact:
        return ResearchArtifact(
            artifact_id=model.artifact_id,
            run_id=model.run_id,
            artifact_type=model.artifact_type,
            payload=model.payload or {},
            created_at=model.created_at,
        )

    @staticmethod
    def _to_task(model: ResearchTaskDB) -> ResearchTask:
        return ResearchTask(
            task_id=model.task_id,
            run_id=model.run_id,
            task_key=model.task_key,
            status=ResearchRunStatus(model.status),
            attempt=model.attempt,
            resume_from=model.resume_from,
            state_snapshot=model.state_snapshot or {},
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_claim(model: ResearchClaimDB) -> ResearchClaim:
        return ResearchClaim(
            claim_id=model.claim_id,
            run_id=model.run_id,
            category=model.category,
            text=model.text,
            evidence_refs=model.evidence_refs or [],
            numeric_context=model.numeric_context or {},
            conflict_status=model.conflict_status,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_gate(model: ResearchQualityGateDB) -> QualityGateResult:
        return QualityGateResult(
            gate_id=model.gate_id,
            run_id=model.run_id,
            gate_key=model.gate_key,
            passed=model.passed,
            severity=model.severity,
            message=model.message,
            details=model.details or {},
            checked_at=model.checked_at,
        )
