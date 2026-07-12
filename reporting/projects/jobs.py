"""In-process background jobs for report-project generation."""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Callable, Dict, List

from core.observability import get_logger
from reporting.projects.project_manager import ReportProject
from reporting.projects.run import ReportProjectRunRequest, ReportProjectRunResult

logger = get_logger(__name__)

ProgressEvent = Dict[str, Any]
JobRunner = Callable[
    [ReportProject, ReportProjectRunRequest, Callable[[ProgressEvent], None]],
    ReportProjectRunResult,
]


@dataclass(frozen=True)
class ReportGenerationJob:
    """Serializable snapshot of one report-generation job."""

    job_id: str
    project_slug: str
    status: str
    phase: str
    message: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    completed_sections: int = 0
    total_sections: int = 0
    result: ReportProjectRunResult | None = None
    error: str | None = None
    deduplicated: bool = False


class ReportGenerationJobService:
    """Run report generation away from the request lifecycle."""

    def __init__(
        self,
        *,
        runner: JobRunner,
        max_history: int = 100,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._runner = runner
        self._max_history = max(1, max_history)
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="report-generation",
        )
        self._lock = threading.RLock()
        self._jobs: Dict[str, ReportGenerationJob] = {}
        self._active_by_slug: Dict[str, str] = {}

    def submit(
        self,
        *,
        project: ReportProject,
        request: ReportProjectRunRequest,
    ) -> ReportGenerationJob:
        """Queue a report job and immediately return its current snapshot."""
        with self._lock:
            active_id = self._active_by_slug.get(project.slug)
            if active_id and active_id in self._jobs:
                return replace(self._jobs[active_id], deduplicated=True)

            job = ReportGenerationJob(
                job_id=str(uuid.uuid4()),
                project_slug=project.slug,
                status="queued",
                phase="queued",
                message="报告已进入生成队列",
                created_at=datetime.now(),
            )
            self._jobs[job.job_id] = job
            self._active_by_slug[project.slug] = job.job_id

        try:
            self._executor.submit(self._run_job, job.job_id, project, request)
        except Exception:
            logger.exception(
                "Failed to submit report generation job",
                job_id=job.job_id,
                project=project.slug,
            )
            with self._lock:
                self._jobs[job.job_id] = replace(
                    job,
                    status="failed",
                    phase="failed",
                    message="报告任务提交失败",
                    completed_at=datetime.now(),
                    error="报告任务提交失败",
                )
                self._active_by_slug.pop(project.slug, None)
            raise

        logger.info(
            "Submitted report generation job",
            job_id=job.job_id,
            project=project.slug,
        )
        return self.get(job.job_id) or job

    def get(
        self,
        job_id: str,
        *,
        project_slug: str | None = None,
    ) -> ReportGenerationJob | None:
        """Return a detached job snapshot, optionally enforcing ownership."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or (project_slug and job.project_slug != project_slug):
                return None
            return replace(job)

    def list_jobs(self) -> List[ReportGenerationJob]:
        """Return snapshots from oldest to newest."""
        with self._lock:
            return [replace(job) for job in self._jobs.values()]

    def shutdown(self, *, wait: bool = True) -> None:
        """Release the executor used by this service."""
        try:
            self._executor.shutdown(wait=wait, cancel_futures=not wait)
        except TypeError:
            self._executor.shutdown(wait=wait)

    def _run_job(
        self,
        job_id: str,
        project: ReportProject,
        request: ReportProjectRunRequest,
    ) -> None:
        self._update(
            job_id,
            status="running",
            phase="prepare",
            message="正在准备报告素材与配置",
            started_at=datetime.now(),
        )

        def report_progress(event: ProgressEvent) -> None:
            self._update(
                job_id,
                phase=str(event.get("phase") or "generate"),
                message=str(event.get("message") or "正在生成报告"),
                completed_sections=max(0, int(event.get("completed_sections") or 0)),
                total_sections=max(0, int(event.get("total_sections") or 0)),
            )

        try:
            result = self._runner(project, request, report_progress)
            self._update(
                job_id,
                status="completed",
                phase="completed",
                message="报告生成完成",
                result=result,
                completed_at=datetime.now(),
            )
            logger.info(
                "Completed report generation job",
                job_id=job_id,
                project=project.slug,
            )
        except Exception as exc:
            logger.exception(
                "Failed report generation job",
                job_id=job_id,
                project=project.slug,
            )
            self._update(
                job_id,
                status="failed",
                phase="failed",
                message="报告生成失败",
                error=str(exc) or exc.__class__.__name__,
                completed_at=datetime.now(),
            )
        finally:
            with self._lock:
                if self._active_by_slug.get(project.slug) == job_id:
                    self._active_by_slug.pop(project.slug, None)
                self._prune_terminal_jobs()

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return
            self._jobs[job_id] = replace(current, deduplicated=False, **changes)

    def _prune_terminal_jobs(self) -> None:
        overflow = len(self._jobs) - self._max_history
        if overflow <= 0:
            return
        terminal_ids = [
            job_id for job_id, job in self._jobs.items() if job.status in {"completed", "failed"}
        ]
        for job_id in terminal_ids[:overflow]:
            self._jobs.pop(job_id, None)
