"""SZSE (深圳证券交易所) MarketDataConnector — 深市上市公司数据源.

深圳证券交易所（SZSE）提供深市上市公司基本信息、交易数据、公告等公开数据。

Phase 1 实现：通过 szse.cn 公开 API 获取上市公司列表和基本信息。
后续可增强：公司详情、财务摘要、交易统计、公告列表。

支持的 datasets:
- listed_companies: 深市上市公司列表及基本信息

Usage:
    connector = SzseMarketConnector()
    result = connector.run(dataset="listed_companies")
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

import requests

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

# szse API 端点
SZSE_BASE = "https://www.szse.cn"
SZSE_LISTED_COMPANIES = f"{SZSE_BASE}/api/report/ShowReport/data"
SZSE_COMPANY_INFO = f"{SZSE_BASE}/api/report/ShowReport/data"


class SzseMarketConnector(MarketDataConnector):
    """深交所数据连接器.

    直接通过 szse.cn 公开 API 获取上市公司数据。
    Phase 1 实现：HTTP 请求 + JSON 解析。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 szse 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - timeout: 请求超时秒数（默认 30）
                - retry: 重试配置字典（max_retries, base_delay）
                - catalog_id: 报表分类 ID（默认 1110 = 上市公司列表）
        """
        super().__init__(config)
        self._timeout = self.config.get("timeout", 30)
        self._catalog_id = self.config.get("catalog_id", "1110")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.szse.cn/",
            }
        )

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return "szse"

    @property
    def datasets(self) -> List[str]:
        return ["listed_companies", "company_info"]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 szse API 是否可用.

        尝试请求上市公司列表接口验证连通性。
        """
        try:
            resp = self._session.get(
                SZSE_LISTED_COMPANIES,
                params={
                    "CATALOGID": self._catalog_id,
                    "TABKEY": "tab1",
                    "random": str(datetime.utcnow().timestamp()),
                },
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                self._health = HealthStatus.HEALTHY
                return HealthStatus.HEALTHY
            self._health = HealthStatus.DEGRADED
            logger.warning(
                "szse_health_http_error",
                extra={"status_code": resp.status_code},
            )
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("szse_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的数据对象.

        Args:
            dataset: 数据集标识（listed_companies / company_info）.
            **params:
                - tab_key: 报表 tab 键（默认 tab1）
                - stock_code: 股票代码（company_info 时使用）

        Returns:
            List[DiscoveryItem]: 发现的待抓取对象列表.
        """
        if dataset not in self.datasets:
            logger.warning(
                "szse_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        as_of = params.get("as_of")

        if dataset == "listed_companies":
            desc = "szse listed companies"
            item_id = "szse_listed_companies"
            item_params: Dict[str, Any] = {}
        elif dataset == "company_info":
            stock_code = params.get("stock_code", "")
            desc = f"szse company info: {stock_code}"
            item_id = f"szse_company_info_{stock_code}"
            item_params = {"stock_code": stock_code}

        if as_of:
            desc += f" as_of={as_of}"
            item_params["as_of"] = as_of

        return [
            DiscoveryItem(
                item_id=item_id,
                item_type=dataset,
                params=item_params,
                description=desc,
            )
        ]

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取深交所数据.

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始 API 响应 JSON.
        """
        if dataset not in self.datasets:
            raise ValueError(
                f"Unknown dataset '{dataset}' for szse connector. " f"Supported: {self.datasets}"
            )

        if dataset == "listed_companies":
            return self._fetch_listed_companies(item)
        elif dataset == "company_info":
            return self._fetch_company_info(item)

        raise ValueError(f"Unhandled dataset: {dataset}")

    def parse_table(self, raw: RawObject) -> ParsedTable:
        """解析原始 JSON 为结构化表格.

        Args:
            raw: fetch() 返回的原始 API 响应.

        Returns:
            ParsedTable: 解析后的表格.
        """
        if isinstance(raw.data, bytes):
            text = raw.data.decode("utf-8")
        else:
            text = raw.data

        data_raw = json.loads(text)
        if isinstance(data_raw, dict):
            # API returned a dict wrapper, try to extract the list
            data = data_raw.get("data", data_raw.get("result", []))
            if isinstance(data, dict):
                data = [data]
        elif isinstance(data_raw, list):
            data = data_raw
        else:
            data = []
        item_type = raw.metadata.get("item_type", "listed_companies")

        if not data:
            return ParsedTable(
                columns=[],
                rows=[],
                table_name=item_type,
                metadata=raw.metadata,
            )

        columns = list(data[0].keys()) if isinstance(data[0], dict) else []
        return ParsedTable(
            columns=columns,
            rows=data,
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

        深交所数据主要是上市公司元信息，使用通用的 MarketBarPayload
        存储公司基本信息，entity_id 作为 key。

        Args:
            dataset: 数据集标识.
            table: parse_table() 的输出.
            raw_uri: 原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            List[IngestionRecord]: 统一摄入记录列表.
        """
        records: List[IngestionRecord] = []

        for row in table.rows:
            # szse API 返回的字段映射
            # 常见字段: zqdm (证券代码), zqjc (证券简称), ssrq (上市日期), zgb (总股本)
            stock_code = row.get("zqdm", "") or row.get("code", "")
            stock_name = row.get("zqjc", "") or row.get("name", "")
            listing_date = row.get("ssrq", "") or row.get("listingDate", "")
            total_shares = row.get("zgb", "") or row.get("totalShares", "")

            # 构建 entity_id: 补齐后缀 .SZ
            if stock_code and not stock_code.endswith((".SZ", ".SH")):
                entity_id = f"{stock_code}.SZ"
            else:
                entity_id = stock_code

            # 使用 MarketBarPayload 存储元信息（结构灵活）
            payload = MarketBarPayload(
                trade_date=str(listing_date) if listing_date else "",
                open=None,
                high=None,
                low=None,
                close=None,
                volume=None,
                amount=None,
            )

            record = IngestionRecord(
                source=self.source,
                dataset=dataset,
                asset_type=AssetType.OTHER,
                entity_type=EntityType.STOCK,
                entity_id=entity_id,
                raw_uri=raw_uri,
                content_hash=content_hash,
                published_at=datetime.utcnow(),
                payload={
                    **payload.model_dump(),
                    "stock_name": stock_name,
                    "listing_date": str(listing_date) if listing_date else "",
                    "total_shares": str(total_shares) if total_shares else "",
                    "exchange": "SZSE",
                    # 保留原始行数据用于后续扩展
                    "_raw_row": {k: str(v) for k, v in row.items() if v is not None},
                },
            )
            records.append(record)

        return records

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _fetch_listed_companies(self, item: DiscoveryItem) -> RawObject:
        """获取深市上市公司列表.

        szse API: GET /api/report/ShowReport/data
        params: CATALOGID=1110, TABKEY=tab1
        返回 JSON 数组，每项包含 zqdm（证券代码）、zqjc（证券简称）等字段.
        """
        resp = self._session.get(
            SZSE_LISTED_COMPANIES,
            params={
                "CATALOGID": self._catalog_id,
                "TABKEY": "tab1",
                "random": str(datetime.utcnow().timestamp()),
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()

        # szse API 返回的 JSON 结构可能是嵌套的
        try:
            data = resp.json()
        except json.JSONDecodeError:
            # 某些 szse 端点返回 HTML 包裹的 JSON
            text = resp.text
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                data = []

        serialized = json.dumps(
            data if isinstance(data, list) else [data], ensure_ascii=False, default=str
        )

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=f"szse://listed_companies/{self._catalog_id}",
            metadata={
                "dataset": "listed_companies",
                "item_type": "listed_companies",
                "catalog_id": self._catalog_id,
                "item_count": len(data) if isinstance(data, list) else 1,
            },
        )

    def _fetch_company_info(self, item: DiscoveryItem) -> RawObject:
        """获取单只股票基本信息.

        Args:
            item: 包含 stock_code 的 DiscoveryItem.

        Returns:
            RawObject: 原始 API 响应.
        """
        stock_code = item.params.get("stock_code", "")
        # 去掉 .SZ 后缀（szse API 用纯数字代码）
        raw_code = stock_code.replace(".SZ", "").replace(".sz", "")

        resp = self._session.get(
            SZSE_COMPANY_INFO,
            params={
                "CATALOGID": "1110x",
                "TABKEY": "tab1",
                "stockCode": raw_code,
                "random": str(datetime.utcnow().timestamp()),
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()

        try:
            data = resp.json()
        except json.JSONDecodeError:
            # szse API sometimes wraps JSON in HTML, use same extraction as _fetch_listed_companies
            text = resp.text
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                data = []

        serialized = json.dumps(
            data if isinstance(data, list) else [data], ensure_ascii=False, default=str
        )

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=f"szse://company_info/{stock_code}",
            metadata={
                "dataset": "company_info",
                "item_type": "company_info",
                "stock_code": stock_code,
                "item_count": len(data) if isinstance(data, list) else 1,
            },
        )

    # persist() 由 MarketDataConnector 基类提供（模板方法）
    # _format_date() / _to_decimal() / _parse_date() 由 MarketDataConnector 基类提供
