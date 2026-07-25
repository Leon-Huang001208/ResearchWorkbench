"""Cjpy (天软/Tinysoft) MarketDataConnector — 将现有 CjpyAdapter 包装为 MarketDataConnector.

Wrapper-first 策略：内部委托给 data_layer/adapters/cjpy_adapter.py，
不立即重写内部逻辑。

支持的 datasets:
- daily_quotes: 日线/分钟线行情（OHLCV）
- factor_data: 因子数据（69 个系统因子）
- table_data: 表格数据（21 张表：股本结构、财务指标、十大股东等）
- stock_list: A 股代码列表
- fund_list: 全量基金代码列表
- trading_days: 交易日序列

Usage:
    connector = CjpyMarketConnector()
    result = connector.run(dataset="daily_quotes", codes=["000001.SZ"],
                           start_date="2026-05-01", end_date="2026-05-31")
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from services.realtime_bridge import RealtimeBridge

from core.connectors.base import DiscoveryItem, MarketDataConnector, ParsedTable, RawObject
from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IngestionRecord,
    MarketBarPayload,
)
from core.observability import get_logger

logger = get_logger(__name__)

DATASET_META: Dict[str, Dict[str, Any]] = {
    "daily_quotes": {
        "item_type": "daily_quotes",
        "asset_type": AssetType.MARKET,
        "entity_type": EntityType.STOCK,
    },
    "factor_data": {
        "item_type": "factor_data",
        "asset_type": AssetType.FUNDAMENTAL,
        "entity_type": EntityType.STOCK,
    },
    "table_data": {
        "item_type": "table_data",
        "asset_type": AssetType.FUNDAMENTAL,
        "entity_type": EntityType.STOCK,
    },
    "stock_list": {
        "item_type": "stock_list",
        "asset_type": AssetType.OTHER,
        "entity_type": EntityType.STOCK,
    },
    "fund_list": {
        "item_type": "fund_list",
        "asset_type": AssetType.OTHER,
        "entity_type": EntityType.FUND,
    },
    "trading_days": {
        "item_type": "trading_days",
        "asset_type": AssetType.OTHER,
        "entity_type": EntityType.INDEX,
    },
}


class CjpyMarketConnector(MarketDataConnector):
    """天软 (Tinysoft) 市场数据连接器.

    封装 cjpy 包的同步查询接口，提供行情、因子、表格等数据获取能力。
    使用前需确保 cjpy token 已配置（环境变量 CJ_KEY 或调用 cjpy.set_token()）。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return "cjpy"

    @property
    def datasets(self) -> List[str]:
        return [
            "daily_quotes",
            "factor_data",
            "table_data",
            "stock_list",
            "fund_list",
            "trading_days",
        ]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查天软服务是否可用."""
        try:
            from data_layer.adapters.cjpy_adapter import CjpyAdapter

            adapter = CjpyAdapter()
            if adapter.is_available():
                self._health = HealthStatus.HEALTHY
                return HealthStatus.HEALTHY
            self._health = HealthStatus.UNAVAILABLE
            return HealthStatus.UNAVAILABLE
        except ImportError as e:
            self._health = HealthStatus.DEGRADED
            logger.warning("cjpy_health_import_error", extra={"error": str(e)})
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("cjpy_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def stream(
        self,
        codes: list[str],
        fields: Optional[list[str]] = None,
    ) -> "RealtimeBridge":
        """创建 Cjpy 实时行情订阅桥接器.

        返回一个 RealtimeBridge 实例，在后台线程中运行 Cjpy subscribe()，
        将行情事件桥接到 SystemEventBus（事件类型: market.quote.cjpy）。

        Args:
            codes: 证券代码列表（Cjpy 格式，如 "SH600519"）.
            fields: 订阅字段列表，默认使用行情核心字段.

        Returns:
            RealtimeBridge: 已创建但未启动的桥接器，调用 .start() 开始接收.

        示例:
            >>> connector = CjpyMarketConnector()
            >>> bridge = connector.stream(["SH600519"], ["price", "volume"])
            >>> bridge.start()
            >>> # ... 行情数据通过 SSE event_bus 推送 ...
            >>> bridge.stop()
        """
        from services.realtime_bridge import RealtimeBridge

        return RealtimeBridge(codes=codes, fields=fields)

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可获取的数据对象.

        Args:
            dataset: 数据集标识.
            **params:
                - codes: 证券代码列表
                - start_date: 开始日期
                - end_date: 结束日期
                - date: 单个日期（股票列表/因子用）
                - dates: 日期列表（因子用）
                - factors: 因子名称列表（因子用）
                - table_name: 表格名称（表格用）
                - fields: 字段列表（表格用）
                - cycle: 周期（行情用）
                - rate: 复权方式（行情用）

        Returns:
            List[DiscoveryItem]: 发现的待获取对象列表.
        """
        if dataset not in self.datasets:
            logger.warning(
                "cjpy_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        item_type = DATASET_META.get(dataset, {}).get("item_type", dataset)

        # stock_list / fund_list / trading_days: 无 code 粒度，整体发现
        if dataset in ("stock_list", "fund_list"):
            return [
                DiscoveryItem(
                    item_id=f"cjpy_{dataset}_all",
                    item_type=item_type,
                    params=params,
                    description=f"{dataset} (all)",
                )
            ]

        if dataset == "trading_days":
            start = params.get("start_date", "")
            end = params.get("end_date", "")
            return [
                DiscoveryItem(
                    item_id=f"cjpy_trading_days_{start}_{end}",
                    item_type=item_type,
                    params=params,
                    description=f"trading_days: {start} → {end}",
                )
            ]

        # daily_quotes / factor_data / table_data: 按 code 逐只发现
        codes: List[str] = params.get("codes", [])
        items: List[DiscoveryItem] = []

        for code in codes:
            item_params: Dict[str, Any] = {**params}
            desc_parts = [f"{dataset}: {code}"]

            items.append(
                DiscoveryItem(
                    item_id=f"cjpy_{dataset}_{code}",
                    item_type=item_type,
                    params=item_params,
                    description=" ".join(desc_parts),
                )
            )

        if not codes:
            items.append(
                DiscoveryItem(
                    item_id=f"cjpy_{dataset}_all",
                    item_type=item_type,
                    params=params,
                    description=f"{dataset} (all codes)",
                )
            )

        return items

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取天软原始数据.

        委托给 CjpyAdapter 对应方法，返回 DataFrame → JSON。

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待获取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始 JSON 数据.
        """
        if dataset not in self.datasets:
            raise ValueError(
                f"Unknown dataset '{dataset}' for Cjpy connector. "
                f"Supported: {', '.join(self.datasets)}"
            )

        from data_layer.adapters.cjpy_adapter import CjpyAdapter

        adapter = CjpyAdapter()
        codes: List[str] = item.params.get("codes") or params.get("codes", [])
        start_date = item.params.get("start_date") or params.get("start_date")
        end_date = item.params.get("end_date") or params.get("end_date")

        if dataset == "stock_list":
            stocks = adapter.fetch_stock_list(date=item.params.get("date"))
            serialized = json.dumps(stocks, ensure_ascii=False)
            return RawObject(
                data=serialized,
                content_type="application/json",
                source_uri="cjpy://stock_list/all",
                metadata={
                    "dataset": dataset,
                    "item_count": len(stocks) if isinstance(stocks, list) else 0,
                },
            )

        elif dataset == "fund_list":
            funds = adapter.fetch_fund_list()
            serialized = json.dumps(funds, ensure_ascii=False)
            return RawObject(
                data=serialized,
                content_type="application/json",
                source_uri="cjpy://fund_list/all",
                metadata={
                    "dataset": dataset,
                    "item_count": len(funds) if isinstance(funds, list) else 0,
                },
            )

        elif dataset == "trading_days":
            if not start_date or not end_date:
                raise ValueError("trading_days requires start_date and end_date")
            days = adapter.fetch_trading_days(
                start=start_date,
                end=end_date,
                cycle=item.params.get("cycle", "D"),
            )
            serialized = json.dumps(days, ensure_ascii=False)
            return RawObject(
                data=serialized,
                content_type="application/json",
                source_uri=f"cjpy://trading_days/{start_date}_{end_date}",
                metadata={
                    "dataset": dataset,
                    "item_count": len(days),
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )

        elif dataset == "daily_quotes":
            if not codes:
                raise ValueError("daily_quotes requires at least one code")
            df = adapter.fetch_daily_quotes(
                codes=codes,
                start_date=start_date or "",
                end_date=end_date or "",
                cycle=item.params.get("cycle", "day"),
                rate=item.params.get("rate", "前复权"),
            )

        elif dataset == "factor_data":
            dates = item.params.get("dates") or item.params.get("date")
            factors = item.params.get("factors", [])
            if not codes:
                raise ValueError("factor_data requires codes")
            if not factors:
                raise ValueError("factor_data requires factors")
            df = adapter.fetch_factor_data(
                codes=codes,
                dates=dates or [],
                factors=factors,
                repo=item.params.get("repo"),
            )

        elif dataset == "table_data":
            table_name = item.params.get("table_name")
            if not table_name:
                raise ValueError("table_data requires table_name")
            df = adapter.fetch_table_data(
                codes=codes if codes else params.get("codes", []),
                table_name=table_name,
                fields=item.params.get("fields"),
            )

        else:
            raise ValueError(f"Unsupported dataset: {dataset}")

        records = df.to_dict(orient="records")
        serialized = json.dumps(records, ensure_ascii=False, default=str)

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=f"cjpy://{dataset}/{','.join(codes) if codes else 'all'}",
            metadata={
                "dataset": dataset,
                "item_type": item.item_type,
                "item_count": len(records),
                "codes": codes,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    def parse_table(self, raw: RawObject) -> ParsedTable:
        """解析原始 JSON 为结构化表格.

        Args:
            raw: fetch() 返回的原始数据.

        Returns:
            ParsedTable: 解析后的表格.
        """
        if isinstance(raw.data, bytes):
            text = raw.data.decode("utf-8")
        else:
            text = raw.data

        records: List[Dict[str, Any]] = json.loads(text)
        if not records:
            return ParsedTable(
                columns=[],
                rows=[],
                table_name=raw.metadata.get("dataset", "unknown"),
                metadata=raw.metadata,
            )

        # 处理非列表类型（如 stock_list 返回纯列表）
        if isinstance(records, list) and not isinstance(records[0], dict):
            records = [{"value": r} for r in records]

        columns = list(records[0].keys())
        return ParsedTable(
            columns=columns,
            rows=records,
            table_name=raw.metadata.get("dataset", "unknown"),
            metadata=raw.metadata,
        )

    def normalize_bars(
        self,
        dataset: str,
        table: ParsedTable,
        raw_uri: str,
        content_hash: str,
    ) -> List[IngestionRecord]:
        """将表格数据转为 IngestionRecord 列表.

        Args:
            dataset: 数据集标识.
            table: parse_table() 的输出.
            raw_uri: 原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            List[IngestionRecord]: 统一摄入记录列表.
        """
        records: List[IngestionRecord] = []
        meta = DATASET_META.get(dataset, {})
        asset_type = meta.get("asset_type", AssetType.OTHER)
        entity_type = meta.get("entity_type", EntityType.STOCK)

        for row in table.rows:
            code = row.get("code", row.get("代码", ""))
            date_val = (
                row.get("date") or row.get("trade_date") or row.get("time") or row.get("日期", "")
            )

            if dataset == "daily_quotes":
                payload = MarketBarPayload(
                    trade_date=self._format_date(date_val),
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    volume=row.get("vol") or row.get("volume"),
                    amount=row.get("amount"),
                )
            else:
                payload = MarketBarPayload(
                    trade_date=self._format_date(date_val) if date_val else "",
                )
                extra_fields = {
                    k: v
                    for k, v in row.items()
                    if k not in ("code", "date", "trade_date", "time", "代码", "日期") and v is not None
                }
                payload_dict = payload.model_dump()
                payload_dict["_cjpy_fields"] = extra_fields
                payload = MarketBarPayload(**payload_dict)

            records.append(
                IngestionRecord(
                    source=self.source,
                    dataset=dataset,
                    asset_type=asset_type,
                    entity_type=entity_type,
                    entity_id=code,
                    raw_uri=raw_uri,
                    content_hash=content_hash,
                    payload=payload.model_dump(),
                )
            )

        return records

    def _daily_bar_datasets(self) -> tuple[str, ...]:
        """Cjpy 日线数据 datasets."""
        return ("daily_quotes",)
