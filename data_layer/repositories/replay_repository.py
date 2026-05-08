"""回放任务 & 结果仓储实现"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from core.contracts.replay import ReplayJob, ReplayResult
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import ReplayJobDB, ReplayResultDB

logger = get_logger(__name__)


class ReplayRepositoryImpl(BaseRepository):
    """回放仓储实现"""

    # ── Job CRUD ──────────────────────────────────────────

    def create_job(self, job: ReplayJob) -> ReplayJob:
        """创建回放任务"""
        db_job = ReplayJobDB(
            job_id=job.job_id,
            name=job.name,
            description=job.description,
            event_filter=job.event_filter,
            max_events=job.max_events,
            status=job.status,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )
        self.db.add(db_job)
        self.db.flush()
        logger.info("replay job created", job_id=job.job_id, name=job.name)
        return self._job_to_domain(db_job)

    def get_job(self, job_id: str) -> Optional[ReplayJob]:
        """获取回放任务"""
        db_job = self.db.query(ReplayJobDB).filter(ReplayJobDB.job_id == job_id).first()
        if not db_job:
            return None
        return self._job_to_domain(db_job)

    def update_job_status(
        self,
        job_id: str,
        status: str,
        completed_at: Optional[datetime] = None,
    ) -> Optional[ReplayJob]:
        """更新回放任务状态"""
        db_job = self.db.query(ReplayJobDB).filter(ReplayJobDB.job_id == job_id).first()
        if not db_job:
            return None
        db_job.status = status
        if completed_at is not None:
            db_job.completed_at = completed_at
        elif status in ("completed", "failed"):
            db_job.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        logger.info("replay job status updated", job_id=job_id, status=status)
        return self._job_to_domain(db_job)

    # ── Result CRUD ───────────────────────────────────────

    def save_result(self, result: ReplayResult) -> ReplayResult:
        """保存回放结果"""
        result_id = f"{result.job_id}_{result.event_id}"
        existing = self.db.query(ReplayResultDB).filter(ReplayResultDB.id == result_id).first()
        if existing:
            existing.signal_id = result.signal_id
            existing.outcome_id = result.outcome_id
            existing.event_type = result.event_type
            existing.source_type = result.source_type
            existing.signal_score = result.signal_score
            existing.signal_confidence = result.signal_confidence
            existing.timing_action = result.timing_action
            existing.outcome_return = result.outcome_return
            existing.outcome_excess_return = result.outcome_excess_return
            existing.max_drawdown = result.max_drawdown
            existing.decay = result.decay
            existing.error = result.error
            db_result = existing
        else:
            db_result = ReplayResultDB(
                id=result_id,
                job_id=result.job_id,
                event_id=result.event_id,
                signal_id=result.signal_id,
                outcome_id=result.outcome_id,
                event_type=result.event_type,
                source_type=result.source_type,
                signal_score=result.signal_score,
                signal_confidence=result.signal_confidence,
                timing_action=result.timing_action,
                outcome_return=result.outcome_return,
                outcome_excess_return=result.outcome_excess_return,
                max_drawdown=result.max_drawdown,
                decay=result.decay,
                error=result.error,
            )
            self.db.add(db_result)
        self.db.flush()
        logger.info("replay result saved", job_id=result.job_id, event_id=result.event_id)
        return self._result_to_domain(db_result)

    def get_results(self, job_id: str) -> List[ReplayResult]:
        """获取回放任务的所有结果"""
        db_results = (
            self.db.query(ReplayResultDB)
            .filter(ReplayResultDB.job_id == job_id)
            .all()
        )
        return [self._result_to_domain(r) for r in db_results]

    # ── 转换方法 ──────────────────────────────────────────

    def _job_to_domain(self, db_job: ReplayJobDB) -> ReplayJob:
        return ReplayJob(
            job_id=db_job.job_id,
            name=db_job.name,
            description=db_job.description,
            event_filter=db_job.event_filter,
            max_events=db_job.max_events,
            status=db_job.status,
            created_at=db_job.created_at,
            completed_at=db_job.completed_at,
        )

    def _result_to_domain(self, db_result: ReplayResultDB) -> ReplayResult:
        return ReplayResult(
            job_id=db_result.job_id,
            event_id=db_result.event_id,
            signal_id=db_result.signal_id,
            outcome_id=db_result.outcome_id,
            event_type=db_result.event_type,
            source_type=db_result.source_type,
            signal_score=float(db_result.signal_score) if db_result.signal_score is not None else None,
            signal_confidence=float(db_result.signal_confidence) if db_result.signal_confidence is not None else None,
            timing_action=db_result.timing_action,
            outcome_return=float(db_result.outcome_return) if db_result.outcome_return is not None else None,
            outcome_excess_return=float(db_result.outcome_excess_return) if db_result.outcome_excess_return is not None else None,
            max_drawdown=float(db_result.max_drawdown) if db_result.max_drawdown is not None else None,
            decay=float(db_result.decay) if db_result.decay is not None else None,
            error=db_result.error,
        )
