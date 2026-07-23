"""AKShare MarketDataConnector — 将现有 AkShareAdapter 包装为 MarketDataConnector.

Wrapper-first 策略：内部委托给 data_layer/crawlers/akshare/ 和 data_layer/normalizers/akshare_market.py，
不立即重写内部逻辑。

支持的 datasets:
- stock_daily: A 股日线行情（OHLCV）
- stock_master: A 股股票列表
- index_daily: 指数日线行情

Usage:
    connector = AkShareMarketConnector()
    result = connector.run(dataset="stock_daily", symbols=["600000.SH"],
                           start_date="2026-01-01", end_date="2026-06-01")
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from core.connectors.base import DiscoveryItem, MarketDataConnector, ParsedTable, RawObject
from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IngestionRecord,
    MarketBarPayload,
)
from core.observability import get_logger
from data_layer.crawlers.akshare.base import AkShareAdapter, MarketData, StockInfo
from data_layer.normalizers.akshare_market import normalize_market_data, normalize_stock_info

logger = get_logger(__name__)


class AkShareMarketConnector(MarketDataConnector):
    """AKShare 市场数据连接器.

    包装 AkShareAdapter，提供统一的 MarketDataConnector 接口。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 AKShare 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - enable_cache: 是否启用缓存（默认 True）
                - timeout: 请求超时秒数（默认 30）
                - max_retries: 最大重试次数（默认 3）
                - retry: 重试配置字典（max_retries, base_delay）
        """
        super().__init__(config)
        akshare_config = None
        try:
            from data_layer.crawlers.akshare.config import AkShareConfig

            cfg = config or {}
            akshare_config = AkShareConfig(
                enable_cache=cfg.get("enable_cache", True),
                timeout=cfg.get("timeout", 30.0),
                max_retries=cfg.get("max_retries", 3),
            )
        except ImportError:
            pass
        self._adapter = AkShareAdapter(config=akshare_config)

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return "akshare"

    @property
    def datasets(self) -> List[str]:
        return ["stock_daily", "stock_master", "index_daily"]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 AKShare 数据源是否可用.

        通过尝试获取股票列表（limit=1）来验证连通性。
        """
        try:
            result = self._adapter.health_check()
            status = result.get("status", "")
            if status == "healthy":
                self._health = HealthStatus.HEALTHY
                return HealthStatus.HEALTHY
            elif status == "unavailable":
                self._health = HealthStatus.UNAVAILABLE
                logger.warning("akshare_health_unavailable", extra={"result": result})
                return HealthStatus.UNAVAILABLE
            self._health = HealthStatus.DEGRADED
            logger.warning("akshare_health_degraded", extra={"result": result})
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("akshare_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的数据对象.

        Args:
            dataset: 数据集标识（stock_daily / stock_master / index_daily）.
            **params:
                - symbols: 股票代码列表（stock_daily 时使用）
                - symbol: 单个指数代码（index_daily 时使用）
                - start_date: 开始日期
                - end_date: 结束日期

        Returns:
            List[DiscoveryItem]: 发现的待抓取对象列表.
        """
        if dataset == "stock_daily":
            symbols: List[str] = params.get("symbols", [])
            start_date = params.get("start_date")
            end_date = params.get("end_date")

            if symbols:
                return [
                    DiscoveryItem(
                        item_id=f"stock_daily_{s}_{start_date}_{end_date}",
                        item_type="stock_daily",
                        params={
                            "symbol": s,
                            "start_date": start_date,
                            "end_date": end_date,
                        },
                        description=f"daily bars: {s} ({start_date} → {end_date})",
                    )
                    for s in symbols
                ]
            # 未指定 symbols 时，先发现股票列表
            return [
                DiscoveryItem(
                    item_id="stock_master_all",
                    item_type="stock_master",
                    params={},
                    description="fetch all A-share stock master first",
                )
            ]

        elif dataset == "stock_master":
            return [
                DiscoveryItem(
                    item_id="stock_master",
                    item_type="stock_master",
                    params={},
                    description="fetch A-share stock list",
                )
            ]

        elif dataset == "index_daily":
            index_symbol = params.get("symbol", "000001.SH")
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            return [
                DiscoveryItem(
                    item_id=f"index_daily_{index_symbol}_{start_date}_{end_date}",
                    item_type="index_daily",
                    params={
                        "symbol": index_symbol,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                    description=f"index daily bars: {index_symbol}",
                )
            ]

        logger.warning(
            "akshare_unknown_dataset",
            extra={"dataset": dataset, "available": self.datasets},
        )
        return []

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取单个数据对象的原始数据.

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始数据对象（JSON 序列化的业务数据）.
        """
        item_type = item.item_type

        if item_type == "stock_daily":
            return self._fetch_stock_daily(item, params)

        elif item_type == "stock_master":
            return self._fetch_stock_master(item, params)

        elif item_type == "index_daily":
            return self._fetch_index_daily(item, params)

        else:
            raise ValueError(
                f"Unknown item_type '{item_type}' for dataset '{dataset}'. "
                f"Supported: stock_daily, stock_master, index_daily"
            )

    def parse_table(self, raw: RawObject) -> ParsedTable:
        """解析原始 JSON 数据为结构化表格.

        Args:
            raw: fetch() 返回的原始 API 响应（JSON 序列化的业务数据）.

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
                table_name=raw.metadata.get("item_type", "unknown"),
                metadata=raw.metadata,
            )

        item_type = raw.metadata.get("item_type", "stock_daily")
        columns = list(records[0].keys())

        return ParsedTable(
            columns=columns,
            rows=records,
            table_name=item_type,
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

        根据 dataset 类型生成对应的 payload：
        - stock_daily → MarketBarPayload（OHLCV 行情）
        - stock_master → 元信息 record
        - index_daily → MarketBarPayload

        Args:
            dataset: 数据集标识.
            table: parse_table() 的输出.
            raw_uri: 原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            List[IngestionRecord]: 统一摄入记录列表.
        """
        records: List[IngestionRecord] = []

        symbol = table.metadata.get("symbol", "")

        for row in table.rows:
            if dataset == "stock_daily" or table.table_name == "stock_daily":
                payload = MarketBarPayload(
                    trade_date=self._format_date(row.get("trade_date")),
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    volume=row.get("volume"),
                    amount=row.get("amount"),
                    turnover=row.get("turnover"),
                    adjustment=table.metadata.get("adjustment", "qfq"),
                )
                asset_type = AssetType.MARKET
            elif dataset == "index_daily" or table.table_name == "index_daily":
                payload = MarketBarPayload(
                    trade_date=self._format_date(row.get("trade_date")),
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    volume=row.get("volume"),
                    amount=row.get("amount"),
                )
                asset_type = AssetType.INDEX
            elif dataset == "stock_master" or table.table_name == "stock_master":
                payload = MarketBarPayload(
                    trade_date="",
                    open=None,
                    high=None,
                    low=None,
                    close=None,
                    volume=None,
                    amount=None,
                )
                asset_type = AssetType.OTHER
            else:
                payload = MarketBarPayload(trade_date="")
                asset_type = AssetType.OTHER

            records.append(
                IngestionRecord(
                    source=self.source,
                    dataset=dataset,
                    asset_type=asset_type,
                    entity_type=EntityType.STOCK if "stock" in dataset else EntityType.INDEX,
                    entity_id=symbol or row.get("symbol"),
                    raw_uri=raw_uri,
                    content_hash=content_hash,
                    payload=payload.model_dump(),
                )
            )

        return records

    def _daily_bar_datasets(self) -> tuple[str, ...]:
        """AKShare 日线数据 dataset（含股票和指数日线）."""
        return ("stock_daily", "index_daily")

    def _persist_extra_records(
        self,
        records: List[IngestionRecord],
        repo: Any,
    ) -> int:
        """处理 stock_master 的持久化."""
        master_records = [r for r in records if r.dataset == "stock_master"]
        if not master_records:
            return 0

        rows = []
        for rec in master_records:
            payload = rec.payload
            symbol = rec.entity_id or ""
            parts = symbol.split(".") if "." in symbol else [symbol, ""]
            row = {
                "symbol": symbol,
                "raw_code": parts[0],
                "name": payload.get("name", ""),
                "exchange": parts[-1] if len(parts) > 1 else "",
                "market": "A-share",
                "industry_level1": payload.get("industry"),
                "source": self.source,
            }
            rows.append(row)
        return repo.upsert_stock_master_many(rows)

    # persist() 由 MarketDataConnector 基类提供（模板方法）
    # _format_date() / _to_decimal() / _parse_date() 由 MarketDataConnector 基类提供

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _fetch_stock_daily(self, item: DiscoveryItem, params: Dict[str, Any]) -> RawObject:
        """抓取 A 股日线行情."""
        symbol = item.params.get("symbol")
        start_date = self._parse_date(item.params.get("start_date"))
        end_date = self._parse_date(item.params.get("end_date"))

        data: List[MarketData] = self._adapter.market.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        serialized = json.dumps(
            [self._market_data_to_dict(d) for d in data],
            ensure_ascii=False,
            default=str,
        )
        source_uri = f"akshare://market/stock_daily/{symbol}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "symbol": symbol,
                "dataset": "stock_daily",
                "item_type": "stock_daily",
                "item_count": len(data),
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "adjustment": self._get_adjustment(),
            },
        )

    def _fetch_stock_master(self, item: DiscoveryItem, params: Dict[str, Any]) -> RawObject:
        """抓取 A 股股票列表."""
        data: List[StockInfo] = self._adapter.market.get_stock_list()

        serialized = json.dumps(
            [self._stock_info_to_dict(d) for d in data],
            ensure_ascii=False,
            default=str,
        )
        source_uri = "akshare://market/stock_master"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "dataset": "stock_master",
                "item_type": "stock_master",
                "item_count": len(data),
            },
        )

    def _fetch_index_daily(self, item: DiscoveryItem, params: Dict[str, Any]) -> RawObject:
        """抓取指数日线行情."""
        symbol = item.params.get("symbol", "000001.SH")
        start_date = self._parse_date(item.params.get("start_date"))
        end_date = self._parse_date(item.params.get("end_date"))

        data: List[MarketData] = self._adapter.market.get_index_historical(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        serialized = json.dumps(
            [self._market_data_to_dict(d) for d in data],
            ensure_ascii=False,
            default=str,
        )
        source_uri = f"akshare://market/index_daily/{symbol}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "symbol": symbol,
                "dataset": "index_daily",
                "item_type": "index_daily",
                "item_count": len(data),
            },
        )

    @staticmethod
    def _market_data_to_dict(item: MarketData) -> Dict[str, Any]:
        """将 MarketData dataclass 转为可 JSON 序列化的 dict.

        使用现有 normalize_market_data() 函数，保持与现有 pipeline 一致。
        """
        return normalize_market_data(item)

    @staticmethod
    def _stock_info_to_dict(item: StockInfo) -> Dict[str, Any]:
        """将 StockInfo dataclass 转为可 JSON 序列化的 dict."""
        return normalize_stock_info(item)

    def _get_adjustment(self) -> str:
        """安全获取复权方式配置，避免 mock 环境下的类型问题."""
        try:
            if hasattr(self._adapter, "config") and self._adapter.config is not None:
                adjust = getattr(self._adapter.config, "default_adjust", "qfq")
                if isinstance(adjust, str):
                    return adjust
        except Exception:
            pass
        return "qfq"
