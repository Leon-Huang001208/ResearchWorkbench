"""审计日志仓储实现"""
import uuid
from typing import Any, Dict, List, Optional

from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import AuditLogDB

logger = get_logger(__name__)


class AuditRepositoryImpl(BaseRepository):
    """审计日志仓储实现"""

    def record(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """记录审计日志

        Args:
            entity_type: 实体类型 (signal, event, outcome, review)
            entity_id: 实体 ID
            action: 操作 (created, status_changed, approved, rejected, etc.)
            actor: 操作者
            details: 额外详情

        Returns:
            审计日志字典
        """
        log_id = str(uuid.uuid4())
        db_log = AuditLogDB(
            log_id=log_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=details or {},
        )
        self.db.add(db_log)
        self.db.flush()
        logger.info(
            "audit log recorded",
            log_id=log_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
        )
        return self._to_dict(db_log)

    def get_trail(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取实体的审计轨迹

        Args:
            entity_type: 实体类型
            entity_id: 实体 ID
            limit: 返回数量限制

        Returns:
            审计日志列表
        """
        db_logs = (
            self.db.query(AuditLogDB)
            .filter(
                AuditLogDB.entity_type == entity_type,
                AuditLogDB.entity_id == entity_id,
            )
            .order_by(AuditLogDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_dict(log) for log in db_logs]

    def search(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """搜索审计日志

        Args:
            query: 搜索关键词
            entity_types: 实体类型过滤
            limit: 返回数量限制

        Returns:
            审计日志列表
        """
        q = self.db.query(AuditLogDB).filter(AuditLogDB.details.cast(str).contains(query))
        if entity_types:
            q = q.filter(AuditLogDB.entity_type.in_(entity_types))
        db_logs = q.order_by(AuditLogDB.created_at.desc()).limit(limit).all()
        return [self._to_dict(log) for log in db_logs]

    def _to_dict(self, db_log: AuditLogDB) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "log_id": db_log.log_id,
            "entity_type": db_log.entity_type,
            "entity_id": db_log.entity_id,
            "action": db_log.action,
            "actor": db_log.actor,
            "details": db_log.details or {},
            "timestamp": db_log.created_at.isoformat() if db_log.created_at else None,
        }
