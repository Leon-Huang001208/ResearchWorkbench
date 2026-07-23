"""
Issue #47: 数据分层服务 - 管理热/温/冷/归档数据

核心功能：
1. 数据分层判定
2. 数据移动/归档策略
3. 分层查询优化
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.contracts.backtest import DataTier, TimeAvailability
from core.observability import get_logger

logger = get_logger(__name__)


class DataTierService:
    """数据分层服务"""

    # 分层配置
    TIER_CONFIGS = {
        DataTier.HOT: {
            "max_age_days": 7,
            "description": "热数据 - 高频访问",
        },
        DataTier.WARM: {
            "max_age_days": 30,
            "description": "温数据 - 中频访问",
        },
        DataTier.COLD: {
            "max_age_days": 365,
            "description": "冷数据 - 低频访问",
        },
        DataTier.ARCHIVED: {
            "max_age_days": None,
            "description": "归档数据 - 长期存储",
        },
    }

    def __init__(
        self,
        tier_configs: Optional[Dict[DataTier, Dict[str, Any]]] = None,
    ):
        self.tier_configs = tier_configs or self.TIER_CONFIGS
        # 跟踪数据的层级
        self._data_tiers: Dict[str, DataTier] = {}
        self._access_stats: Dict[str, List[datetime]] = {}

    def get_data_tier(
        self,
        time_availability: TimeAvailability,
        reference_time: Optional[datetime] = None,
    ) -> DataTier:
        """
        获取数据所属层级

        Args:
            time_availability: 时间可用性信息
            reference_time: 参考时间（默认当前时间）

        Returns:
            数据层级
        """
        return time_availability.get_tier(reference_time)

    def get_tier_for_age(
        self,
        age_days: float,
    ) -> DataTier:
        """
        根据数据年龄获取层级

        Args:
            age_days: 数据年龄（天数）

        Returns:
            数据层级
        """
        if age_days <= 7:
            return DataTier.HOT
        elif age_days <= 30:
            return DataTier.WARM
        elif age_days <= 365:
            return DataTier.COLD
        else:
            return DataTier.ARCHIVED

    def should_migrate(
        self,
        data_id: str,
        time_availability: TimeAvailability,
        reference_time: Optional[datetime] = None,
    ) -> Optional[DataTier]:
        """
        检查数据是否应该迁移到其他层级

        Args:
            data_id: 数据 ID
            time_availability: 时间可用性信息
            reference_time: 参考时间

        Returns:
            目标层级（如果需要迁移），否则 None
        """
        current_tier = self._data_tiers.get(data_id)
        target_tier = self.get_data_tier(time_availability, reference_time)

        if current_tier != target_tier:
            return target_tier
        return None

    def record_access(
        self,
        data_id: str,
        access_time: Optional[datetime] = None,
    ) -> None:
        """
        记录数据访问

        Args:
            data_id: 数据 ID
            access_time: 访问时间
        """
        access_time = access_time or datetime.utcnow()

        if data_id not in self._access_stats:
            self._access_stats[data_id] = []

        self._access_stats[data_id].append(access_time)

        # 只保留最近 30 天的访问记录
        cutoff = datetime.utcnow() - timedelta(days=30)
        self._access_stats[data_id] = [t for t in self._access_stats[data_id] if t >= cutoff]

    def get_access_frequency(
        self,
        data_id: str,
        window_days: int = 7,
    ) -> int:
        """
        获取数据访问频率

        Args:
            data_id: 数据 ID
            window_days: 时间窗口

        Returns:
            访问次数
        """
        if data_id not in self._access_stats:
            return 0

        cutoff = datetime.utcnow() - timedelta(days=window_days)
        return len([t for t in self._access_stats[data_id] if t >= cutoff])

    def get_tier_summary(
        self,
    ) -> Dict[DataTier, Dict[str, Any]]:
        """
        获取各层数据统计

        Returns:
            分层统计
        """
        counts: Dict[DataTier, int] = defaultdict(int)  # type: ignore
        for tier in self._data_tiers.values():
            counts[tier] += 1

        summary: Dict[DataTier, Dict[str, Any]] = {}
        for tier in DataTier:
            config = self.tier_configs.get(tier, {})
            summary[tier] = {
                "count": counts.get(tier, 0),
                "description": config.get("description", ""),
                "max_age_days": config.get("max_age_days"),
            }

        return summary

    def set_data_tier(
        self,
        data_id: str,
        tier: DataTier,
    ) -> None:
        """
        设置数据层级

        Args:
            data_id: 数据 ID
            tier: 层级
        """
        self._data_tiers[data_id] = tier
        logger.debug("data tier set", data_id=data_id, tier=tier.value)

    def get_migration_candidates(
        self,
        max_candidates: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取应该迁移的数据列表

        Args:
            max_candidates: 最大候选数

        Returns:
            迁移候选列表
        """
        candidates: List[Dict[str, Any]] = []

        # 实际实现中，这里会查询数据库找出应该迁移的数据
        # 这里是框架实现

        return candidates[:max_candidates]

    def get_tier_retention_policy(
        self,
        tier: DataTier,
    ) -> Dict[str, Any]:
        """
        获取层级的保留策略

        Args:
            tier: 数据层级

        Returns:
            保留策略
        """
        policies: Dict[DataTier, Dict[str, Any]] = {
            DataTier.HOT: {
                "retention_days": 7,
                "compression": "none",
                "storage_type": "ssd",
                "replication": 3,
            },
            DataTier.WARM: {
                "retention_days": 30,
                "compression": "lz4",
                "storage_type": "ssd",
                "replication": 2,
            },
            DataTier.COLD: {
                "retention_days": 365,
                "compression": "gzip",
                "storage_type": "hdd",
                "replication": 2,
            },
            DataTier.ARCHIVED: {
                "retention_days": None,
                "compression": "gzip",
                "storage_type": "cold_storage",
                "replication": 1,
            },
        }

        return policies.get(tier, {})
