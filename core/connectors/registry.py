"""Connector Registry — 已实例化的数据源连接器注册表.

升级自 core/source_registry.py，新增：
- 已实例化 connector 支持（vs. 仅类路径字符串）
- YAML 配置文件加载（每个 connector 目录下的 config.yaml）
- connector 生命周期管理（init / start / stop / health）
- 与现有 SourceSpec / SourceType 系统兼容

使用方式:
    registry = ConnectorRegistry()
    registry.discover_all()  # 自动发现并实例化所有注册的 connector

    connector = registry.get_connector("cls")
    result = connector.run(dataset="telegram", max_docs=50)

    health = registry.get_health("cnstock")  # → HealthStatus.HEALTHY
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type, cast

from core.connectors.base import BaseConnector
from core.contracts.ingestion_record import HealthStatus, IngestionResult, IngestionStatus
from core.observability import get_logger

logger = get_logger(__name__)


class DatasetRouter:
    """数据集级多源路由 — 按 fallback 组优先级自动降级.

    使用方式:
        router = DatasetRouter(registry)
        router.build()  # 从 SourceSpec fallback_group 构建路由表
        result = router.run_with_fallback(
            "daily_quotes", group="daily_quotes_cn",
            codes=["SH600519"], start_date="2026-05-30", end_date="2026-06-02"
        )
    """

    def __init__(self, registry: "ConnectorRegistry"):
        self._registry = registry
        # {fallback_group: [(source_type_str, priority), ...]}
        self._chains: Dict[str, List[str]] = {}
        # {source_type_str: set of datasets}
        self._source_datasets: Dict[str, set] = {}

    def build(self) -> int:
        """从 SourceSpec fallback_group 构建降级链.

        Returns:
            int: 构建的降级组数量.
        """
        from core.source_registry import get_fallback_groups

        self._chains.clear()
        groups = get_fallback_groups()
        for group_name, specs in groups.items():
            chain = []
            for spec in sorted(specs, key=lambda item: item.fallback_priority):
                source_str = (
                    spec.source_type.value
                    if hasattr(spec.source_type, "value")
                    else str(spec.source_type)
                )
                chain.append(source_str)
            self._chains[group_name] = chain
            logger.info(
                "fallback_chain_built",
                extra={"group": group_name, "chain": chain},
            )
        return len(self._chains)

    def get_chain(self, group: str) -> List[str]:
        """获取指定降级组的优先级链.

        Args:
            group: fallback_group 名称.

        Returns:
            按优先级排序的 source_type 字符串列表.
        """
        if not self._chains:
            self.build()
        return self._chains.get(group, [])

    def get_chain_for_source(self, source: str) -> Optional[str]:
        """查找指定 source 所属的 fallback_group.

        Returns:
            group name 或 None.
        """
        if not self._chains:
            self.build()
        for group, chain in self._chains.items():
            if source in chain:
                return group
        return None

    def run_with_fallback(
        self,
        dataset: str,
        *,
        group: Optional[str] = None,
        **params: Any,
    ) -> IngestionResult:
        """按优先级尝试 group 内的源，健康/运行失败时自动降级.

        Args:
            dataset: 数据集标识，如 "daily_quotes".
            group: fallback 组名，如 "daily_quotes_cn".
                   None 时按 dataset 搜索所有组.
            **params: 传递给 connector.run() 的参数.

        Returns:
            IngestionResult 带 routed_source 和 fallback_used 标记.
        """
        if not self._chains:
            self.build()

        chain = self._chains.get(group) if group else None

        # 如果没指定 group，尝试在所有组中查找包含 dataset 的组
        if chain is None:
            for grp_name, grp_chain in self._chains.items():
                for src in grp_chain:
                    conn = self._registry.get_connector(src)
                    if conn and dataset in conn.datasets:
                        chain = grp_chain
                        group = grp_name
                        break
                if chain:
                    break

        if not chain:
            return IngestionResult(
                source="unknown",
                dataset=dataset,
                status=IngestionStatus.FAILED,
                error_message=f"No fallback chain found for dataset '{dataset}'",
            )

        primary_source = chain[0]
        errors = []

        for idx, source_type in enumerate(chain):
            connector = self._registry.get_connector(source_type)
            if connector is None:
                errors.append(f"{source_type}: not registered")
                continue

            # 健康检查
            try:
                health = connector.health_check()
            except Exception as e:
                health = HealthStatus.UNAVAILABLE
                logger.warning(
                    "fallback_health_failed",
                    extra={"source": source_type, "error": str(e)},
                )

            if health == HealthStatus.UNAVAILABLE:
                msg = f"{source_type}: health UNAVAILABLE"
                errors.append(msg)
                logger.warning(
                    "fallback_source_unavailable",
                    extra={"source": source_type, "dataset": dataset},
                )
                continue

            # 尝试运行
            try:
                logger.info(
                    "fallback_try_source",
                    extra={"source": source_type, "dataset": dataset, "is_fallback": idx > 0},
                )
                result = connector.run(dataset=dataset, **params)

                # 标记路由信息
                result.routed_source = source_type
                result.fallback_used = idx > 0

                if idx > 0:
                    logger.info(
                        "fallback_used",
                        extra={
                            "dataset": dataset,
                            "primary": primary_source,
                            "used": source_type,
                            "fallback_level": idx,
                        },
                    )

                return result

            except Exception as e:
                msg = f"{source_type}: {e}"
                errors.append(msg)
                logger.warning(
                    "fallback_run_failed",
                    extra={"source": source_type, "dataset": dataset, "error": str(e)},
                )
                continue

        # 所有源都失败
        return IngestionResult(
            source=primary_source,
            dataset=dataset,
            status=IngestionStatus.FAILED,
            error_message=f"All fallback sources failed for '{dataset}': {'; '.join(errors)}",
        )

    def list_groups(self) -> Dict[str, List[str]]:
        """列出所有 fallback 组及其链."""
        if not self._chains:
            self.build()
        return dict(self._chains)


class ConnectorRegistry:
    """数据源连接器注册表 — 管理 connector 实例的注册、发现和生命周期.

    与现有 core/source_registry.py 集成：
    - 从现有的 data_sources/ 自动发现机制读取注册的适配器
    - 将 SourceSpec 中的 adapter_class 字符串延迟解析为 connector 实例
    - 支持两个注册体系共存（SourceSpec + Connector 实例）

    Attributes:
        _connectors: {source_type_value → BaseConnector} 已实例化的 connector 映射.
        _specs: 从 source_registry 获取的 SourceSpec 缓存.
        _configs: {source_type_value → config_dict} 每个 connector 的配置.
    """

    def __init__(self) -> None:
        self._connectors: Dict[str, BaseConnector] = {}
        self._specs: Dict[str, Any] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._health_callbacks: List[Callable] = []
        self._router: Optional[DatasetRouter] = None

    @property
    def router(self) -> DatasetRouter:
        """获取 DatasetRouter（惰性初始化）."""
        if self._router is None:
            self._router = DatasetRouter(self)
            self._router.build()
        return self._router

    def run_with_fallback(
        self,
        dataset: str,
        *,
        group: Optional[str] = None,
        **params: Any,
    ) -> IngestionResult:
        """按 fallback 优先级执行数据集摄入，自动降级.

        Args:
            dataset: 数据集标识，如 "daily_quotes".
            group: fallback 组名。None 时自动查找.
            **params: 传递给 connector.run() 的参数.

        Returns:
            IngestionResult 带 routed_source 和 fallback_used 标记.
        """
        return self.router.run_with_fallback(dataset, group=group, **params)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        source_type: str,
        connector: BaseConnector,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """注册一个已实例化的 connector.

        Args:
            source_type: 数据源标识（如 "cls", "cnstock", "akshare"）.
            connector: 已实例化的 BaseConnector 子类.
            config: 可选的连接器配置字典（加载自 config.yaml）.

        Raises:
            ValueError: 如果 source_type 已注册.
        """
        if source_type in self._connectors:
            raise ValueError(
                f"Connector '{source_type}' already registered: "
                f"{self._connectors[source_type].__class__.__name__}"
            )
        self._connectors[source_type] = connector
        if config:
            self._configs[source_type] = config

        logger.info(
            "connector_registered",
            extra={
                "source_type": source_type,
                "connector_class": connector.__class__.__name__,
                "datasets": connector.datasets,
            },
        )

    def register_class(
        self,
        source_type: str,
        connector_class: Type[BaseConnector],
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseConnector:
        """从类注册并实例化 connector.

        如果 connector 尚未实例化（如通过 SourceSpec.adapter_class 发现），
        使用此方法延迟创建实例。

        Args:
            source_type: 数据源标识.
            connector_class: BaseConnector 子类（未被实例化的）.
            config: 可选的连接器配置字典.

        Returns:
            BaseConnector: 已实例化并注册的 connector.
        """
        connector = connector_class(config=config)
        self.register(source_type, connector, config)
        return connector

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_all(self) -> int:
        """从现有 source_registry 自动发现并尝试实例化所有注册的 connector.

        对于每个已注册的 SourceSpec，尝试：
        1. 从 adapter_class 路径导入对应的类
        2. 如果该类是 BaseConnector 的子类，实例化并注册
        3. 如果不是，记录为待迁移的 source

        Returns:
            int: 已成功注册（connector 实例化）的数据源数量.

        Note:
            这是一个过渡方法，用于从旧的 SourceSpec 体系渐进迁移。
            随着 connector 重构深入，此方法会被新的 auto-discovery 替代。
        """
        from core.source_registry import _ensure_discovered, _registry

        _ensure_discovered()

        registered_count = 0
        for source_type, spec in _registry.items():
            source_type_str = (
                source_type.value if hasattr(source_type, "value") else str(source_type)
            )
            if source_type_str in self._connectors:
                continue  # 已经注册

            # 尝试从 adapter_class 导入
            try:
                connector_class = self._import_class(spec.adapter_class)

                # 检查是否已是 BaseConnector 子类（新 connector 或已包装的）
                if issubclass(connector_class, BaseConnector):
                    self.register_class(source_type_str, connector_class, spec.adapter_kwargs)
                    registered_count += 1
                    logger.info(
                        "connector_auto_migrated",
                        extra={"source_type": source_type_str, "class": spec.adapter_class},
                    )
                else:
                    # 旧的适配器类 — 等待包装为 BaseConnector
                    logger.debug(
                        "connector_pending_migration",
                        extra={
                            "source_type": source_type_str,
                            "class": spec.adapter_class,
                            "reason": "Not a BaseConnector subclass",
                        },
                    )
            except ImportError as e:
                logger.warning(
                    "connector_import_failed",
                    extra={
                        "source_type": source_type_str,
                        "class": spec.adapter_class,
                        "error": str(e),
                    },
                )
            except Exception as e:
                logger.warning(
                    "connector_init_failed",
                    extra={
                        "source_type": source_type_str,
                        "class": spec.adapter_class,
                        "error": str(e),
                    },
                )

        return registered_count

    def _import_class(self, class_path: str) -> Type:
        """从完全限定路径导入类.

        Args:
            class_path: 如 "data_layer.adapters.cls_adapter.CLSAdapter".

        Returns:
            Type: 导入的类对象.

        Raises:
            ImportError: 如果模块或类不存在.
        """
        import importlib

        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return cast(Type, getattr(module, class_name))

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_connector(self, source_type: str) -> Optional[BaseConnector]:
        """获取已注册的 connector 实例.

        Args:
            source_type: 数据源标识（如 "cls", "cnstock", "akshare"）.

        Returns:
            BaseConnector | None: connector 实例，如果未注册则返回 None.
        """
        return self._connectors.get(source_type)

    def get_connector_or_raise(self, source_type: str) -> BaseConnector:
        """获取 connector 实例，未注册时抛出异常.

        Args:
            source_type: 数据源标识.

        Returns:
            BaseConnector: connector 实例.

        Raises:
            KeyError: 如果 source_type 未注册.
        """
        if source_type not in self._connectors:
            available = list(self._connectors.keys())
            raise KeyError(
                f"Connector '{source_type}' not found. "
                f"Available connectors: {available or 'none'}. "
                f"Run registry.discover_all() first."
            )
        return self._connectors[source_type]

    def get_all_connectors(self) -> Dict[str, BaseConnector]:
        """获取所有已注册的 connector.

        Returns:
            Dict[str, BaseConnector]: {source_type → connector} 映射.
        """
        return dict(self._connectors)

    def list_sources(self) -> List[str]:
        """列出所有已注册的数据源标识.

        Returns:
            List[str]: 数据源标识列表.
        """
        return list(self._connectors.keys())

    def list_datasets(self) -> Dict[str, List[str]]:
        """列出所有数据源及其支持的数据集.

        Returns:
            Dict[str, List[str]]: {source_type → [dataset names]}.
        """
        return {source: connector.datasets for source, connector in self._connectors.items()}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def get_health(self, source_type: str) -> HealthStatus:
        """获取单个数据源的健康状态.

        如果 connector 不可用，执行 health_check()。

        Args:
            source_type: 数据源标识.

        Returns:
            HealthStatus: 健康状态.
        """
        connector = self.get_connector(source_type)
        if connector is None:
            return HealthStatus.UNKNOWN
        try:
            return connector.health_check()
        except Exception:
            return HealthStatus.UNAVAILABLE

    def get_all_health(self) -> Dict[str, HealthStatus]:
        """获取所有已注册数据源的健康状态.

        Returns:
            Dict[str, HealthStatus]: {source_type → HealthStatus}.
        """
        return {source: self.get_health(source) for source in self._connectors}

    def get_health_summary(self) -> Dict[str, int]:
        """获取健康状态汇总.

        Returns:
            Dict[str, int]: {status → count}.
        """
        summary: Dict[str, int] = {
            "healthy": 0,
            "degraded": 0,
            "unavailable": 0,
            "unknown": 0,
        }
        for health in self.get_all_health().values():
            summary[health.value] += 1
        return summary

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop_all(self) -> None:
        """停止所有 connector（清理资源、关闭连接等）.

        默认调用每个 connector 的 stop() 方法（如果存在）。
        """
        for source_type, connector in self._connectors.items():
            try:
                if hasattr(connector, "stop"):
                    connector.stop()  # type: ignore[attr-defined]
                    logger.debug("connector_stopped", extra={"source_type": source_type})
            except Exception as e:
                logger.warning(
                    "connector_stop_failed",
                    extra={"source_type": source_type, "error": str(e)},
                )

    def clear(self) -> None:
        """清空所有注册的 connector."""
        self.stop_all()
        self._connectors.clear()
        self._configs.clear()
        self._specs.clear()


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_registry: Optional[ConnectorRegistry] = None


def get_connector_registry() -> ConnectorRegistry:
    """获取全局 ConnectorRegistry 单例.

    Returns:
        ConnectorRegistry: 全局注册表实例.
    """
    global _registry
    if _registry is None:
        _registry = ConnectorRegistry()
    return _registry


def reset_connector_registry() -> None:
    """重置全局注册表（主要用于测试）."""
    global _registry
    if _registry is not None:
        _registry.clear()
    _registry = None
