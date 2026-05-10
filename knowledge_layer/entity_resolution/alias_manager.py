"""
别名管理器
"""
from typing import Dict, List, Optional

from core.interfaces import EntityRepository
from core.observability import get_logger

logger = get_logger(__name__)


class AliasManager:
    """别名管理器"""

    def __init__(self, repository: Optional[EntityRepository] = None):
        self._repository = repository
        # 内存缓存
        self._alias_map: Dict[str, str] = {}  # alias -> canonical_id
        self._canonical_aliases: Dict[str, List[str]] = {}  # canonical_id -> aliases

    def add_alias(self, canonical_id: str, alias: str) -> None:
        """
        添加别名

        Args:
            canonical_id: 规范化 ID
            alias: 别名
        """
        alias = alias.lower().strip()

        # 更新内存
        self._alias_map[alias] = canonical_id

        if canonical_id not in self._canonical_aliases:
            self._canonical_aliases[canonical_id] = []

        if alias not in self._canonical_aliases[canonical_id]:
            self._canonical_aliases[canonical_id].append(alias)

        # 持久化（如果有 repository）
        if self._repository:
            self._save_to_repository(canonical_id, alias)

        logger.debug(f"Added alias: {alias} -> {canonical_id}")

    def add_aliases(self, canonical_id: str, aliases: List[str]) -> None:
        """批量添加别名"""
        for alias in aliases:
            self.add_alias(canonical_id, alias)

    def resolve_alias(self, alias: str) -> Optional[str]:
        """
        解析别名

        Args:
            alias: 别名

        Returns:
            canonical_id 或 None
        """
        alias = alias.lower().strip()
        return self._alias_map.get(alias)

    def get_aliases(self, canonical_id: str) -> List[str]:
        """
        获取实体的所有别名

        Args:
            canonical_id: 规范化 ID

        Returns:
            别名列表
        """
        return self._canonical_aliases.get(canonical_id, []).copy()

    def merge_entities(self, primary_id: str, secondary_id: str) -> None:
        """
        合并两个实体

        Args:
            primary_id: 主实体 ID
            secondary_id: 被合并实体 ID
        """
        # 先获取 secondary 的所有别名
        secondary_aliases = self.get_aliases(secondary_id)

        # 移到 primary
        for alias in secondary_aliases:
            self.add_alias(primary_id, alias)

        # 移除 secondary
        if secondary_id in self._canonical_aliases:
            del self._canonical_aliases[secondary_id]

        logger.info(f"Merged entity {secondary_id} into {primary_id}")

    def load_from_dictionary(self, alias_dict: Dict[str, List[str]]) -> None:
        """
        从字典加载别名映射

        Args:
            alias_dict: {canonical_id: [aliases]}
        """
        for canonical_id, aliases in alias_dict.items():
            self.add_aliases(canonical_id, aliases)

    def _save_to_repository(self, canonical_id: str, alias: str) -> None:
        """保存到 repository（如果实现）"""
        # TODO: 实现 repository 保存逻辑
        pass


# 预加载一些默认别名映射
def create_default_alias_manager(repository: Optional[EntityRepository] = None) -> AliasManager:
    """创建带有默认别名的管理器"""
    manager = AliasManager(repository)

    # 示例别名映射
    default_aliases = {
        "equity:cn:sse:600519": ["贵州茅台", "茅台", "600519", "600519.SH"],
        "equity:hk:hkex:00700": ["腾讯控股", "腾讯", "700", "00700.HK"],
    }

    manager.load_from_dictionary(default_aliases)
    return manager
