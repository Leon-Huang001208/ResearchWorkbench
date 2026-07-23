"""Governance 持久化仓储实现"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.contracts.governance import ExperimentRecord, StrategyComponentType, StrategyVersion
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import ExperimentRecordDB, StrategyVersionDB

logger = get_logger(__name__)


class GovernanceRepositoryImpl(BaseRepository):
    """Governance 仓储实现"""

    # ── StrategyVersion CRUD ─────────────────────────────

    def save_strategy_version(self, version: StrategyVersion) -> StrategyVersion:
        """保存策略版本"""
        existing = self.db.query(StrategyVersionDB).filter_by(version_id=version.version_id).first()

        data = self._version_to_dict(version)

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            db_obj = existing
        else:
            db_obj = StrategyVersionDB(**data)
            self.db.add(db_obj)

        self.db.flush()
        logger.info("strategy version saved", version_id=version.version_id)
        return self._dict_to_version(self._db_version_to_dict(db_obj))

    def get_strategy_version(self, version_id: str) -> Optional[StrategyVersion]:
        """获取策略版本"""
        db_obj = (
            self.db.query(StrategyVersionDB)
            .filter(StrategyVersionDB.version_id == version_id)
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_version(self._db_version_to_dict(db_obj))

    def get_latest_version_number(
        self,
        component_type: StrategyComponentType,
        component_name: str,
    ) -> int:
        """获取指定组件的最大版本号"""
        from sqlalchemy import func

        result = (
            self.db.query(func.max(StrategyVersionDB.version_number))
            .filter(
                StrategyVersionDB.component_type == component_type.value,
                StrategyVersionDB.component_name == component_name,
            )
            .scalar()
        )
        return result or 0

    def list_strategy_versions(
        self,
        component_type: Optional[str] = None,
        component_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
    ) -> List[StrategyVersion]:
        """列出策略版本"""
        query = self.db.query(StrategyVersionDB)
        if component_type:
            query = query.filter(StrategyVersionDB.component_type == component_type)
        if component_name:
            query = query.filter(StrategyVersionDB.component_name == component_name)
        if is_active is not None:
            query = query.filter(StrategyVersionDB.is_active == is_active)
        db_objs = query.order_by(StrategyVersionDB.created_at.desc()).limit(limit).all()
        return [self._dict_to_version(self._db_version_to_dict(o)) for o in db_objs]

    def get_active_version(
        self,
        component_type: StrategyComponentType,
        component_name: str,
    ) -> Optional[StrategyVersion]:
        """获取指定组件的当前活跃版本"""
        db_obj = (
            self.db.query(StrategyVersionDB)
            .filter(
                StrategyVersionDB.component_type == component_type.value,
                StrategyVersionDB.component_name == component_name,
                StrategyVersionDB.is_active == True,  # noqa: E712
            )
            .order_by(StrategyVersionDB.created_at.desc())
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_version(self._db_version_to_dict(db_obj))

    def deactivate_version(self, version_id: str) -> None:
        """将指定版本设为非活跃"""
        db_obj = (
            self.db.query(StrategyVersionDB)
            .filter(StrategyVersionDB.version_id == version_id)
            .first()
        )
        if db_obj:
            db_obj.is_active = False
            self.db.flush()

    def activate_version(self, version_id: str) -> None:
        """将指定版本设为活跃"""
        db_obj = (
            self.db.query(StrategyVersionDB)
            .filter(StrategyVersionDB.version_id == version_id)
            .first()
        )
        if db_obj:
            db_obj.is_active = True
            self.db.flush()

    # ── ExperimentRecord CRUD ────────────────────────────

    def save_experiment(self, experiment: ExperimentRecord) -> ExperimentRecord:
        """保存实验记录"""
        existing = (
            self.db.query(ExperimentRecordDB)
            .filter_by(experiment_id=experiment.experiment_id)
            .first()
        )

        data = self._experiment_to_dict(experiment)

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            db_obj = existing
        else:
            db_obj = ExperimentRecordDB(**data)
            self.db.add(db_obj)

        self.db.flush()
        logger.info("experiment saved", experiment_id=experiment.experiment_id)
        return self._dict_to_experiment(self._db_experiment_to_dict(db_obj))

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """获取实验记录"""
        db_obj = (
            self.db.query(ExperimentRecordDB)
            .filter(ExperimentRecordDB.experiment_id == experiment_id)
            .first()
        )
        if not db_obj:
            return None
        return self._dict_to_experiment(self._db_experiment_to_dict(db_obj))

    def list_experiments(
        self,
        experiment_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ExperimentRecord]:
        """列出实验记录"""
        query = self.db.query(ExperimentRecordDB)
        if experiment_type:
            query = query.filter(ExperimentRecordDB.experiment_type == experiment_type)
        if status:
            query = query.filter(ExperimentRecordDB.status == status)
        db_objs = query.order_by(ExperimentRecordDB.started_at.desc()).limit(limit).all()
        return [self._dict_to_experiment(self._db_experiment_to_dict(o)) for o in db_objs]

    def count_experiments(self) -> int:
        """统计实验总数"""
        from sqlalchemy import func

        return self.db.query(func.count(ExperimentRecordDB.experiment_id)).scalar() or 0

    def recent_experiment_ids(self, limit: int = 10) -> List[str]:
        """获取最近实验ID列表"""
        results = (
            self.db.query(ExperimentRecordDB.experiment_id)
            .order_by(ExperimentRecordDB.started_at.desc())
            .limit(limit)
            .all()
        )
        return [r[0] for r in results]

    def update_experiment_status(
        self,
        experiment_id: str,
        status: str,
        completed_at: Optional[datetime] = None,
    ) -> Optional[ExperimentRecord]:
        """更新实验状态"""
        db_obj = (
            self.db.query(ExperimentRecordDB)
            .filter(ExperimentRecordDB.experiment_id == experiment_id)
            .first()
        )
        if not db_obj:
            return None
        db_obj.status = status
        if completed_at:
            db_obj.completed_at = completed_at
        self.db.flush()
        return self._dict_to_experiment(self._db_experiment_to_dict(db_obj))

    # ── 序列化辅助 ──────────────────────────────────────

    @staticmethod
    def _compute_content_hash(config: Dict[str, Any]) -> str:
        """计算配置内容的哈希值"""
        content = json.dumps(config, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _version_to_dict(self, version: StrategyVersion) -> Dict[str, Any]:
        """StrategyVersion → 可序列化字典"""
        return {
            "version_id": version.version_id,
            "component_type": version.component_type.value,
            "component_name": version.component_name,
            "version_number": version.version_number,
            "description": version.description,
            "config": version.config,
            "content_hash": version.content_hash or self._compute_content_hash(version.config),
            "parent_version_id": version.parent_version_id,
            "is_active": version.is_active,
            "created_at": version.created_at,
            "created_by": version.created_by,
            "tags": version.tags,
        }

    @staticmethod
    def _db_version_to_dict(db_obj: StrategyVersionDB) -> Dict[str, Any]:
        """StrategyVersionDB → 字典"""
        return {
            "version_id": db_obj.version_id,
            "component_type": db_obj.component_type,
            "component_name": db_obj.component_name,
            "version_number": db_obj.version_number,
            "description": db_obj.description or "",
            "config": db_obj.config or {},
            "content_hash": db_obj.content_hash or "",
            "parent_version_id": db_obj.parent_version_id,
            "is_active": db_obj.is_active,
            "created_at": db_obj.created_at,
            "created_by": db_obj.created_by or "system",
            "tags": db_obj.tags or [],
        }

    @staticmethod
    def _dict_to_version(data: Dict[str, Any]) -> StrategyVersion:
        """字典 → StrategyVersion"""
        return StrategyVersion(
            version_id=data["version_id"],
            component_type=StrategyComponentType(data["component_type"]),
            component_name=data["component_name"],
            version_number=data.get("version_number", 1),
            description=data.get("description", ""),
            config=data.get("config", {}),
            content_hash=data.get("content_hash", ""),
            parent_version_id=data.get("parent_version_id"),
            is_active=data.get("is_active", True),
            created_at=data["created_at"],
            created_by=data.get("created_by", "system"),
            tags=data.get("tags", []),
        )

    @staticmethod
    def _experiment_to_dict(experiment: ExperimentRecord) -> Dict[str, Any]:
        """ExperimentRecord → 可序列化字典"""
        return {
            "experiment_id": experiment.experiment_id,
            "name": experiment.name,
            "description": experiment.description,
            "strategy_version_ids": experiment.strategy_version_ids,
            "experiment_type": experiment.experiment_type,
            "entity_id": experiment.entity_id,
            "metrics": experiment.metrics,
            "status": experiment.status,
            "started_at": experiment.started_at,
            "completed_at": experiment.completed_at,
            "tags": experiment.tags,
            "experiment_metadata": experiment.metadata,
        }

    @staticmethod
    def _db_experiment_to_dict(db_obj: ExperimentRecordDB) -> Dict[str, Any]:
        """ExperimentRecordDB → 字典"""
        return {
            "experiment_id": db_obj.experiment_id,
            "name": db_obj.name,
            "description": db_obj.description or "",
            "strategy_version_ids": db_obj.strategy_version_ids or [],
            "experiment_type": db_obj.experiment_type,
            "entity_id": db_obj.entity_id,
            "metrics": db_obj.metrics or {},
            "status": db_obj.status,
            "started_at": db_obj.started_at,
            "completed_at": db_obj.completed_at,
            "tags": db_obj.tags or [],
            "metadata": db_obj.experiment_metadata or {},
        }

    @staticmethod
    def _dict_to_experiment(data: Dict[str, Any]) -> ExperimentRecord:
        """字典 → ExperimentRecord"""
        return ExperimentRecord(
            experiment_id=data["experiment_id"],
            name=data["name"],
            description=data.get("description", ""),
            strategy_version_ids=data.get("strategy_version_ids", []),
            experiment_type=data.get("experiment_type", "signal"),
            entity_id=data.get("entity_id"),
            metrics=data.get("metrics", {}),
            status=data.get("status", "running"),
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
