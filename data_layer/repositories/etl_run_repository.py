"""ETLRunRepository — ETL 运行记录管理

管理 etl_run 表的 CRUD 操作。
"""
from datetime import datetime, timezone
from typing import Optional

from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import ETLRunDB

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ETLRunRepository(BaseRepository):
    """ETL 运行记录仓储"""

    def start(self, run_id: str, job_name: str, source: str) -> None:
        """创建一条 running 状态的 ETL 记录"""
        run = ETLRunDB(
            run_id=run_id,
            job_name=job_name,
            source=source,
            status="running",
            started_at=_utc_now(),
        )
        self.db.add(run)
        self.db.flush()
        logger.info(f"ETL run started: {run_id} ({job_name})")

    def finish(
        self,
        run_id: str,
        status: str = "success",
        items_fetched: int = 0,
        items_normalized: int = 0,
        items_saved: int = 0,
    ) -> None:
        """将 ETL 记录标记为完成"""
        run = self.db.query(ETLRunDB).filter(ETLRunDB.run_id == run_id).first()
        if run:
            run.status = status
            run.finished_at = _utc_now()
            run.items_fetched = items_fetched
            run.items_normalized = items_normalized
            run.items_saved = items_saved
            self.db.flush()
            logger.info(f"ETL run finished: {run_id} status={status} saved={items_saved}")

    def fail(self, run_id: str, error_message: str) -> None:
        """将 ETL 记录标记为失败"""
        run = self.db.query(ETLRunDB).filter(ETLRunDB.run_id == run_id).first()
        if run:
            run.status = "failed"
            run.finished_at = _utc_now()
            run.error_message = error_message
            self.db.flush()
            logger.error(f"ETL run failed: {run_id} error={error_message}")

    def get_run(self, run_id: str) -> Optional[ETLRunDB]:
        """按 run_id 查询"""
        return self.db.query(ETLRunDB).filter(ETLRunDB.run_id == run_id).first()

    def get_recent_runs(self, limit: int = 50) -> list[ETLRunDB]:
        """查询最近的 ETL 记录"""
        return self.db.query(ETLRunDB).order_by(ETLRunDB.started_at.desc()).limit(limit).all()
