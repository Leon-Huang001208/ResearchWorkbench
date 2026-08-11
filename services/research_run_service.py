"""Application service for durable, evidence-first research runs."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from docx import Document

from core.contracts.research import (
    QualityGateResult,
    ResearchArtifact,
    ResearchClaim,
    ResearchDecisionCard,
    ResearchEvidenceInput,
    ResearchRun,
    ResearchRunCreateRequest,
    ResearchRunOutputs,
    ResearchRunStatus,
    ResearchTask,
)
from core.observability import get_logger
from data_layer.repositories.research_run_repository import ResearchRunRepository
from services.research_templates import (
    ResearchTemplateRegistry,
    get_default_research_template_registry,
)

logger = get_logger(__name__)


class ResearchRunService:
    """Persist all research facts around a pure LangGraph execution plan."""

    def __init__(
        self,
        repository: ResearchRunRepository,
        registry: ResearchTemplateRegistry | None = None,
    ):
        self._repository = repository
        self._registry = registry or get_default_research_template_registry()

    def create(self, request: ResearchRunCreateRequest) -> ResearchRun:
        if request.subject is None or request.target_id is None:
            raise ValueError("Research subject normalization failed")
        template = self._registry.require_executable(request.template_key, request.subject)
        self._registry.validate_evidence_kinds(
            request.template_key, [item.evidence_kind for item in request.evidence_inputs]
        )
        now = _utc_now()
        run = ResearchRun(
            run_id=_new_id("research_run"),
            template_key=request.template_key,
            target_id=request.target_id,
            subject=request.subject,
            as_of=request.as_of,
            question=request.question,
            attachment_refs=request.attachment_refs,
            status=ResearchRunStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )
        created = self._repository.create_run(
            run, [evidence.model_dump(mode="json") for evidence in request.evidence_inputs]
        )
        self._repository.create_task(
            ResearchTask(
                task_id=_new_id("research_task"),
                run_id=created.run_id,
                task_key=template.task_key,
                status=ResearchRunStatus.DRAFT,
                created_at=now,
                updated_at=now,
            )
        )
        logger.info(
            "research run created",
            run_id=created.run_id,
            template_key=created.template_key,
            subject_type=created.subject.subject_type,
            target_id=created.target_id,
        )
        return created

    def execute(self, run_id: str) -> ResearchRun:
        run = self._get_run(run_id)
        if run.status is ResearchRunStatus.COMPLETED:
            return run
        if run.status not in {
            ResearchRunStatus.DRAFT,
            ResearchRunStatus.BLOCKED,
            ResearchRunStatus.FAILED,
        }:
            raise ValueError(f"Research run {run_id} cannot execute from {run.status.value}")
        return self._execute(run, increment_retry=run.status is not ResearchRunStatus.DRAFT)

    def resume(self, run_id: str) -> ResearchRun:
        run = self._get_run(run_id)
        if run.status is not ResearchRunStatus.BLOCKED:
            raise ValueError(f"Research run {run_id} is not blocked")
        return self._execute(run, increment_retry=True)

    def add_evidence(self, run_id: str, evidence: ResearchEvidenceInput) -> ResearchRun:
        run = self._get_run(run_id)
        if run.status not in {ResearchRunStatus.DRAFT, ResearchRunStatus.BLOCKED}:
            raise ValueError("Evidence can only be added to draft or blocked research runs")
        self._registry.validate_evidence_kinds(run.template_key, [evidence.evidence_kind])
        self._repository.append_evidence_input(run_id, evidence.model_dump(mode="json"))
        logger.info("research evidence added", run_id=run_id, evidence_id=evidence.evidence_id)
        return self._get_run(run_id)

    def get(self, run_id: str) -> ResearchRun:
        return self._get_run(run_id)

    def list_recent(self, *, limit: int = 20) -> list[ResearchRun]:
        return self._repository.list_runs(limit=limit)

    def get_task(self, run_id: str) -> ResearchTask:
        """Expose the durable task snapshot for diagnostics and resume audits."""
        try:
            return self._repository.get_task_or_raise(run_id)
        except KeyError as exc:
            logger.warning("research task not found", run_id=run_id)
            raise ValueError(f"Research task for {run_id} not found") from exc

    def get_outputs(self, run_id: str) -> ResearchRunOutputs:
        run = self._get_run(run_id)
        artifacts = self._repository.list_artifacts(run_id)
        card_artifact = _latest_artifact(artifacts, "decision_card")
        report_artifact = _latest_artifact(artifacts, "report_markdown")
        notes_artifact = _latest_artifact(artifacts, "research_notes")
        return ResearchRunOutputs(
            run_id=run_id,
            status=run.status,
            decision_card=(
                ResearchDecisionCard.model_validate(card_artifact.payload)
                if card_artifact is not None
                else None
            ),
            research_notes=(
                notes_artifact.payload.get("notes", []) if notes_artifact is not None else []
            ),
            claims=self._repository.list_claims(run_id),
            quality_gates=self._repository.list_quality_gates(run_id),
            artifacts=artifacts,
            report_markdown=(
                report_artifact.payload.get("content") if report_artifact is not None else None
            ),
        )

    def export_markdown(self, run_id: str) -> str:
        """Return a completed run's immutable Markdown report for download."""
        run = self._get_run(run_id)
        if run.status is not ResearchRunStatus.COMPLETED:
            raise ValueError("Only completed research runs can be exported")
        report = self.get_outputs(run_id).report_markdown
        if not report:
            raise ValueError("Completed research run has no Markdown report")
        return report

    def export_word(self, run_id: str) -> bytes:
        """Render the completed Markdown projection into an in-memory DOCX file."""
        markdown = self.export_markdown(run_id)
        try:
            document = Document()
            for line in markdown.splitlines():
                if line.startswith("# "):
                    document.add_heading(line[2:], level=1)
                elif line.startswith("## "):
                    document.add_heading(line[3:], level=2)
                elif line.startswith("- "):
                    document.add_paragraph(line[2:], style="List Bullet")
                elif line:
                    document.add_paragraph(line)
            buffer = BytesIO()
            document.save(buffer)
            return buffer.getvalue()
        except Exception as exc:
            logger.error(
                "research Word export failed", run_id=run_id, error=str(exc), exc_info=True
            )
            raise ValueError("无法生成 Word 研究报告。") from exc

    def _execute(self, run: ResearchRun, *, increment_retry: bool) -> ResearchRun:
        try:
            template = self._registry.require_executable(run.template_key, run.subject)
            if template.graph_factory is None:
                raise ValueError(f"Research template {run.template_key} has no executor")
            graph = template.graph_factory()
            attempt = run.retry_count + (1 if increment_retry else 0)
            self._repository.update_task(
                run.run_id,
                status=ResearchRunStatus.PLANNING,
                attempt=attempt,
                resume_from=run.resume_from,
                state_snapshot={"status": ResearchRunStatus.PLANNING.value, "attempt": attempt},
            )
            self._repository.update_run(
                run.run_id,
                status=ResearchRunStatus.PLANNING,
                increment_retry=increment_retry,
            )
            result = graph.invoke(
                {
                    "run_id": run.run_id,
                    "target_id": run.target_id,
                    "subject": run.subject.model_dump(mode="json"),
                    "as_of": run.as_of.isoformat(),
                    "question": run.question,
                    "evidence": self._repository.get_evidence_inputs(run.run_id),
                }
            )
            self._persist_execution_result(
                run.run_id, result, attempt=attempt, template_key=run.template_key
            )
            blocked_reasons = list(result.get("blocked_reasons", []))
            status = ResearchRunStatus.BLOCKED if blocked_reasons else ResearchRunStatus.COMPLETED
            completed_at = _utc_now() if status is ResearchRunStatus.COMPLETED else None
            updated = self._repository.update_run(
                run.run_id,
                status=status,
                source_plan=result.get("source_plan", {}),
                blocked_reasons=blocked_reasons,
                resume_from="validate" if blocked_reasons else None,
                completed_at=completed_at,
            )
            self._repository.update_task(
                run.run_id,
                status=status,
                attempt=attempt,
                resume_from="validate" if blocked_reasons else None,
                state_snapshot={
                    "status": status.value,
                    "attempt": attempt,
                    "source_plan": result.get("source_plan", {}),
                    "blocked_reasons": blocked_reasons,
                },
            )
            logger.info("research run executed", run_id=run.run_id, status=updated.status.value)
            return updated
        except Exception as exc:
            logger.error("research run failed", run_id=run.run_id, error=str(exc), exc_info=True)
            self._repository.update_run(
                run.run_id,
                status=ResearchRunStatus.FAILED,
                blocked_reasons=["研究运行时发生内部错误，请检查运行日志后重试。"],
                resume_from="planning",
            )
            self._repository.update_task(
                run.run_id,
                status=ResearchRunStatus.FAILED,
                attempt=run.retry_count + (1 if increment_retry else 0),
                resume_from="planning",
                state_snapshot={"status": ResearchRunStatus.FAILED.value},
                error_message="研究运行时发生内部错误，请检查运行日志后重试。",
            )
            raise

    def _persist_execution_result(
        self, run_id: str, result: dict, *, attempt: int, template_key: str
    ) -> None:
        now = _utc_now()
        self._registry.validate_evidence_kinds(
            template_key, [claim["category"] for claim in result.get("claims", [])]
        )
        artifacts = {
            "source_plan": result.get("source_plan", {}),
            "research_notes": {"notes": result.get("research_notes", [])},
            "challenge": {"quality_checks": result.get("quality_checks", [])},
        }
        if result.get("decision_card"):
            artifacts["decision_card"] = result["decision_card"]
        if result.get("report_markdown"):
            artifacts["report_markdown"] = {"content": result["report_markdown"]}
        for artifact_type, payload in artifacts.items():
            self._repository.append_artifact(
                ResearchArtifact(
                    artifact_id=_new_id("research_artifact"),
                    run_id=run_id,
                    artifact_type=f"{artifact_type}:{attempt}",
                    payload=payload,
                    created_at=now,
                )
            )

        claims = [
            ResearchClaim(
                claim_id=_new_id("research_claim"),
                run_id=run_id,
                category=claim["category"],
                text=claim["text"],
                evidence_refs=claim["evidence_refs"],
                numeric_context=claim["numeric_context"],
                conflict_status=claim["conflict_status"],
                created_at=now,
            )
            for claim in result.get("claims", [])
        ]
        self._repository.replace_claims(run_id, claims)
        gates = [
            QualityGateResult(
                gate_id=_new_id("research_gate"),
                run_id=run_id,
                gate_key=check["gate_key"],
                passed=check["passed"],
                message=check["message"],
                details={},
                checked_at=now,
            )
            for check in result.get("quality_checks", [])
        ]
        self._repository.replace_quality_gates(run_id, gates)

    def _get_run(self, run_id: str) -> ResearchRun:
        try:
            return self._repository.get_run_or_raise(run_id)
        except KeyError as exc:
            logger.warning("research run not found", run_id=run_id)
            raise ValueError(f"Research run {run_id} not found") from exc


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_artifact(
    artifacts: list[ResearchArtifact], artifact_type: str
) -> ResearchArtifact | None:
    """Return the newest immutable artifact revision for a logical output type."""
    revisions: list[tuple[int, ResearchArtifact]] = []
    prefix = f"{artifact_type}:"
    for artifact in artifacts:
        if not artifact.artifact_type.startswith(prefix):
            continue
        try:
            revisions.append((int(artifact.artifact_type.removeprefix(prefix)), artifact))
        except ValueError:
            continue
    return max(revisions, key=lambda item: item[0])[1] if revisions else None
