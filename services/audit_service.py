"""审计服务 — 记录和查询操作审计轨迹。"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.observability import get_logger
from data_layer.repositories.audit_repository import AuditRepositoryImpl

logger = get_logger(__name__)


class AuditService:
    """审计服务"""

    def __init__(self, repository: Optional[AuditRepositoryImpl] = None):
        self.repository = repository
        self._logs: List[Dict[str, Any]] = []  # fallback if no repo

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
            action: 操作类型
            actor: 操作者
            details: 额外详情

        Returns:
            审计日志记录
        """
        if self.repository:
            return self.repository.record(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor=actor,
                details=details,
            )

        # 内存 fallback
        log_entry = {
            "log_id": str(uuid.uuid4()),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": actor,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._logs.append(log_entry)
        logger.info(
            "audit log recorded",
            log_id=log_entry["log_id"],
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
        )
        return log_entry

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
            审计日志列表（按时间倒序）
        """
        if self.repository:
            return self.repository.get_trail(
                entity_type=entity_type,
                entity_id=entity_id,
                limit=limit,
            )

        # 内存 fallback
        return [
            log
            for log in self._logs
            if log["entity_type"] == entity_type and log["entity_id"] == entity_id
        ][:limit]

    def get_trail_for_signal(self, signal_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取信号的审计轨迹（含合成记录）

        如果没有显式审计日志，基于信号的 created_at/updated_at 合成基本记录。
        """
        explicit_logs = self.get_trail("signal", signal_id, limit=limit)
        return explicit_logs

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
        if self.repository:
            return self.repository.search(
                query=query,
                entity_types=entity_types,
                limit=limit,
            )

        # 内存 fallback — 简单子串匹配
        results = []
        for log in self._logs:
            text = str(log.get("details", ""))
            if query.lower() in text.lower():
                if entity_types is None or log["entity_type"] in entity_types:
                    results.append(log)
        return results[:limit]
