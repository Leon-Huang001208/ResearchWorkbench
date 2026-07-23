"""Wind MarketDataConnector — 将现有 WindAdapter 包装为 MarketDataConnector.

Wrapper-first 策略：内部委托给 data_layer/adapters/wind/wind_adapter.py，
不立即重写内部逻辑。

依赖：macOS Excel + Wind 插件 + xlwings。

支持的 datasets:
- daily_quotes: 日行情（OHLCV + 换手率 + 涨跌幅 + 振幅）
- consensus_estimates: 一致预期（净利润、EPS、营收、目标价、评级）
- margin_trading: 融资融券
- block_trades: 龙虎榜
- financial_statements: 财务报表（TTM/MRQ）
- industry_data: 行业分类（申万）
- fund_flow: 资金流向 + 北向持股
- holder_data: 股东/持有人结构

Usage:
    connector = WindMarketConnector()
    result = connector.run(dataset="daily_quotes", codes=["600519.SH"],
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

logger = get_logger(__name__)

# dataset → (item_type, asset_type, entity_type)
DATASET_META: Dict[str, Dict[str, Any]] = {
    "daily_quotes": {
        "item_type": "daily_quotes",
        "asset_type": AssetType.MARKET,
        "entity_type": EntityType.STOCK,
    },
    "consensus_estimates": {
        "item_type": "consensus",
        "asset_type": AssetType.MARKET,
        "entity_type": EntityType.STOCK,
    },
    "margin_trading": {
        "item_type": "margin_trading",
        "asset_type": AssetType.MARKET,
        "entity_type": EntityType.STOCK,
    },
    "block_trades": {
        "item_type": "block_trades",
        "asset_type": AssetType.MARKET,
        "entity_type": EntityType.STOCK,
    },
    "financial_statements": {
        "item_type": "financials",
        "asset_type": AssetType.FUNDAMENTAL,
        "entity_type": EntityType.STOCK,
    },
    "industry_data": {
        "item_type": "industry",
        "asset_type": AssetType.OTHER,
        "entity_type": EntityType.STOCK,
    },
    "fund_flow": {
        "item_type": "fund_flow",
        "asset_type": AssetType.MARKET,
        "entity_type": EntityType.STOCK,
    },
    "holder_data": {
        "item_type": "holders",
        "asset_type": AssetType.OTHER,
        "entity_type": EntityType.STOCK,
    },
}


class WindMarketConnector(MarketDataConnector):
    """Wind 市场数据连接器.

    通过 xlwings 操控 Excel Wind 插件获取数据。
    使用前需确保 Excel 已启动且 Wind 插件已登录。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 Wind 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - adj_type: 复权方式 1-不复权 2-后复权 3-前复权（默认 1）
        """
        super().__init__(config)
        self._adj_type = self.config.get("adj_type", 1)

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return "wind"

    @property
    def datasets(self) -> List[str]:
        return [
            "daily_quotes",
            "consensus_estimates",
            "margin_trading",
            "block_trades",
            "financial_statements",
            "industry_data",
            "fund_flow",
            "holder_data",
        ]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 Wind 是否可用.

        尝试连接 Excel Wind 插件并执行心跳检测。
        """
        try:
            from data_layer.adapters.wind.wind_adapter import WindAdapter

            adapter = WindAdapter()
            if adapter.is_available():
                self._health = HealthStatus.HEALTHY
                return HealthStatus.HEALTHY
            self._health = HealthStatus.UNAVAILABLE
            return HealthStatus.UNAVAILABLE
        except ImportError as e:
            self._health = HealthStatus.DEGRADED
            logger.warning("wind_health_import_error", extra={"error": str(e)})
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("wind_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的数据对象.

        Args:
            dataset: 数据集标识（daily_quotes / consensus_estimates 等）.
            **params:
                - codes: 证券代码列表
                - start_date: 开始日期
                - end_date: 结束日期
                - trade_date: 交易日期（一致预期/财务/行业用）
                - report_date: 报告期（财务/持有人用）

        Returns:
            List[DiscoveryItem]: 发现的待抓取对象列表.
        """
        if dataset not in self.datasets:
            logger.warning(
                "wind_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        codes: List[str] = params.get("codes", [])
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        trade_date = params.get("trade_date")
        report_date = params.get("report_date")
        item_type = DATASET_META.get(dataset, {}).get("item_type", dataset)

        items: List[DiscoveryItem] = []
        for code in codes:
            item_params: Dict[str, Any] = {"code": code}
            desc_parts = [f"{dataset}: {code}"]

            if start_date:
                item_params["start_date"] = start_date
                desc_parts.append(str(start_date))
            if end_date:
                item_params["end_date"] = end_date
                desc_parts.append(f"→ {end_date}")
            if trade_date:
                item_params["trade_date"] = trade_date
                desc_parts.append(f"(trade: {trade_date})")
            if report_date:
                item_params["report_date"] = report_date
                desc_parts.append(f"(report: {report_date})")

            items.append(
                DiscoveryItem(
                    item_id=f"wind_{dataset}_{code}",
                    item_type=item_type,
                    params=item_params,
                    description=" ".join(desc_parts),
                )
            )

        if not codes:
            items.append(
                DiscoveryItem(
                    item_id=f"wind_{dataset}_all",
                    item_type=item_type,
                    params={
                        "start_date": start_date,
                        "end_date": end_date,
                        "trade_date": trade_date,
                        "report_date": report_date,
                    },
                    description=f"{dataset} (all codes)",
                )
            )

        return items

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取 Wind 原始数据.

        委托给 WindAdapter 对应的 fetch_* 方法，返回 DataFrame 序列化为 JSON。

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始 JSON 数据.
        """
        if dataset not in self.datasets:
            raise ValueError(
                f"Unknown dataset '{dataset}' for Wind connector. "
                f"Supported: {', '.join(self.datasets)}"
            )

        from data_layer.adapters.wind.wind_adapter import WindAdapter

        adapter = WindAdapter()

        code = item.params.get("code")
        codes = [code] if code else params.get("codes", [])
        start_date = item.params.get("start_date") or params.get("start_date")
        end_date = item.params.get("end_date") or params.get("end_date")
        trade_date = item.params.get("trade_date") or params.get("trade_date")
        report_date = item.params.get("report_date") or params.get("report_date")

        if not codes:
            raise ValueError("Wind fetch requires at least one code")

        # 路由到对应的 WindAdapter 方法
        if dataset == "consensus_estimates":
            df = adapter.fetch_consensus_estimates(codes, trade_date=trade_date)
        elif dataset == "margin_trading":
            df = adapter.fetch_margin_trading(codes, start_date or "", end_date or "")
        elif dataset == "block_trades":
            df = adapter.fetch_block_trades(codes, start_date or "", end_date or "")
        elif dataset == "daily_quotes":
            df = adapter.fetch_daily_quotes(
                codes, start_date or "", end_date or "", adj_type=self._adj_type
            )
        elif dataset == "financial_statements":
            df = adapter.fetch_financial_statements(
                codes, trade_date=trade_date, report_date=report_date
            )
        elif dataset == "industry_data":
            df = adapter.fetch_industry_data(codes, trade_date=trade_date)
        elif dataset == "fund_flow":
            df = adapter.fetch_fund_flow(codes, start_date or "", end_date or "")
        elif dataset == "holder_data":
            if not report_date:
                raise ValueError("holder_data requires report_date")
            df = adapter.fetch_holder_data(codes, report_date)
        else:
            raise ValueError(f"Unsupported dataset: {dataset}")

        # 序列化 DataFrame
        records = df.to_dict(orient="records")
        serialized = json.dumps(records, ensure_ascii=False, default=str)

        source_uri = f"wind://{dataset}/{','.join(codes)}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "dataset": dataset,
                "item_type": item.item_type,
                "item_count": len(records),
                "codes": codes,
                "start_date": start_date,
                "end_date": end_date,
                "trade_date": trade_date,
                "report_date": report_date,
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

        根据 dataset 类型生成对应的 payload。

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
            code = row.get("code", "")

            # 根据 dataset 构造不同的 payload
            if dataset == "daily_quotes":
                payload = MarketBarPayload(
                    trade_date=self._format_date(row.get("date") or row.get("trade_date")),
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row.get("close"),
                    volume=row.get("volume"),
                    amount=row.get("amount"),
                    turnover=row.get("turnover"),
                )
            else:
                # 非 OHLCV 数据用通用 payload（保持原始字段在 payload 中）
                payload = MarketBarPayload(
                    trade_date=self._format_date(row.get("date") or row.get("trade_date") or ""),
                )
                # 添加额外字段
                extra_fields = {
                    k: v
                    for k, v in row.items()
                    if k not in ("code", "date", "trade_date") and v is not None
                }
                payload_dict = payload.model_dump()
                payload_dict["_wind_fields"] = extra_fields
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
        """Wind 日线数据 dataset."""
        return ("daily_quotes",)

    # persist() 由 MarketDataConnector 基类提供（模板方法）
    # _format_date() / _to_decimal() 由 MarketDataConnector 基类提供
