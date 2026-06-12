"""CSIndex (中证指数) MarketDataConnector — 指数成分股及估值数据源.

中证指数有限公司（CSIndex）是国内主要的指数编制机构，提供沪深300、
中证500 等主流指数的成分股、权重、估值、行业分布等数据。

Phase 1 实现：通过 csindex.com.cn 公开 API 获取指数列表、成分股和估值数据。
后续可增强：全量指数覆盖、增量更新、数据校验、断点续跑。

支持的 datasets:
- index_constituents: 指数成分股及权重
- index_valuation: 指数估值（PE/PB/股息率）

Usage:
    connector = CsindexMarketConnector()
    result = connector.run(dataset="index_constituents", index_code="000300")
    result = connector.run(dataset="index_valuation", index_code="000300")
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from core.connectors.base import DiscoveryItem, MarketDataConnector, ParsedTable, RawObject
from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IndexPayload,
    IngestionRecord,
)
from core.observability import get_logger

logger = get_logger(__name__)

# csindex API 端点
CSINDEX_BASE = "https://www.csindex.com.cn"
CSINDEX_SAMPLE_TRADE_DATE = (
    f"{CSINDEX_BASE}/csindex-home/indexInfo/index-sample-information-trade-date-new"
)
CSINDEX_TOP10_WEIGHT = f"{CSINDEX_BASE}/csindex-home/index/weight/top10new"
CSINDEX_BASIC_INFO = f"{CSINDEX_BASE}/csindex-home/indexInfo/index-basic-info"
CSINDEX_INDEX_FEATURE = f"{CSINDEX_BASE}/csindex-home/indexInfo/index-feature"
CSINDEX_YIELD_ITEM = f"{CSINDEX_BASE}/csindex-home/perf/get-index-yield-item"

# 常用指数代码
COMMON_INDICES = {
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "000016": "上证50",
    "399006": "创业板指",
    "399005": "中小板指",
    "000688": "科创50",
    "399300": "沪深300（深）",
}


class CsindexMarketConnector(MarketDataConnector):
    """中证指数数据连接器.

    直接通过 csindex.com.cn 公开 API 获取指数数据。
    Phase 1 实现：HTTP 请求 + JSON 解析。
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        """初始化 csindex 连接器.

        Args:
            config: 连接器配置字典。可包含：
                - timeout: 请求超时秒数（默认 30）
                - retry: 重试配置字典（max_retries, base_delay）
        """
        super().__init__(config)
        self._timeout = self.config.get("timeout", 30)
        self._session = requests.Session()
        self._session.trust_env = bool(self.config.get("trust_env", False))
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.csindex.com.cn/",
            }
        )

    # ------------------------------------------------------------------
    # 元信息
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return "csindex"

    @property
    def datasets(self) -> List[str]:
        return ["index_constituents", "index_valuation"]

    # ------------------------------------------------------------------
    # 生命周期方法
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        """检查 csindex API 是否可用.

        尝试请求指数列表接口验证连通性。
        """
        try:
            resp = self._session.get(CSINDEX_SAMPLE_TRADE_DATE, timeout=self._timeout)
            if resp.status_code == 200:
                self._health = HealthStatus.HEALTHY
                return HealthStatus.HEALTHY
            self._health = HealthStatus.DEGRADED
            logger.warning(
                "csindex_health_http_error",
                extra={"status_code": resp.status_code},
            )
            return HealthStatus.DEGRADED
        except Exception as e:
            self._health = HealthStatus.UNAVAILABLE
            logger.error("csindex_health_failed", extra={"error": str(e)}, exc_info=True)
            return HealthStatus.UNAVAILABLE

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的指数数据对象.

        Args:
            dataset: 数据集标识（index_constituents / index_valuation）.
            **params:
                - index_code: 指数代码（如 000300，单个或逗号分隔）
                - as_of: 数据日期（可选）

        Returns:
            List[DiscoveryItem]: 发现的待抓取对象列表.
        """
        if dataset not in self.datasets:
            logger.warning(
                "csindex_unknown_dataset",
                extra={"dataset": dataset, "available": self.datasets},
            )
            return []

        index_code_str = params.get("index_code", "000300")
        index_codes = [c.strip() for c in index_code_str.split(",") if c.strip()]
        as_of = params.get("as_of")

        items = []
        for code in index_codes:
            index_name = COMMON_INDICES.get(code, f"指数{code}")
            desc = f"csindex {dataset}: {index_name} ({code})"
            if as_of:
                desc += f" as_of={as_of}"

            items.append(
                DiscoveryItem(
                    item_id=f"csindex_{dataset}_{code}",
                    item_type=dataset,
                    params={
                        "index_code": code,
                        "as_of": as_of,
                    },
                    description=desc,
                )
            )
        return items

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取指数数据.

        Args:
            dataset: 数据集标识.
            item: discover() 返回的待抓取对象.
            **params: 额外参数.

        Returns:
            RawObject: 原始 API 响应 JSON.
        """
        if dataset not in self.datasets:
            raise ValueError(
                f"Unknown dataset '{dataset}' for csindex connector. " f"Supported: {self.datasets}"
            )

        index_code = item.params.get("index_code", "000300")

        if dataset == "index_constituents":
            return self._fetch_constituents(index_code)
        elif dataset == "index_valuation":
            return self._fetch_valuation(index_code)

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

        data: Dict[str, Any] = json.loads(text)

        item_type = raw.metadata.get("item_type", "index_constituents")

        if item_type == "index_constituents":
            payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
            rows = payload.get("weightList", [])
        elif item_type == "index_valuation":
            detail = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
            if not detail and isinstance(data, dict):
                detail = data
            rows = [detail] if detail else []
        else:
            rows = data if isinstance(data, list) else [data]

        columns = list(rows[0].keys()) if rows else []

        return ParsedTable(
            columns=columns,
            rows=rows,
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

        Args:
            dataset: 数据集标识.
            table: parse_table() 的输出.
            raw_uri: 原始数据存储 URI.
            content_hash: SHA256 内容哈希.

        Returns:
            List[IngestionRecord]: 统一摄入记录列表.
        """
        records: List[IngestionRecord] = []
        index_code = table.metadata.get("index_code", "")

        if dataset == "index_valuation":
            for row in table.rows:
                payload = IndexPayload(
                    index_code=index_code,
                    index_name=(
                        row.get("indexName")
                        or row.get("indexNameCN")
                        or row.get("indexNameCn")
                        or row.get("indexNameEn")
                    ),
                    index_pe=self._safe_float(row.get("pe", row.get("pe_ttm"))),
                    index_pb=self._safe_float(row.get("pb")),
                    dividend_yield=self._safe_float(row.get("dividendYield", row.get("dyr"))),
                    as_of=self._format_csindex_date(row.get("endDate", row.get("tradeDate", ""))),
                )
                records.append(
                    IngestionRecord(
                        source=self.source,
                        dataset=dataset,
                        asset_type=AssetType.INDEX,
                        entity_type=EntityType.INDEX,
                        entity_id=index_code,
                        raw_uri=raw_uri,
                        content_hash=content_hash,
                        published_at=datetime.utcnow(),
                        payload=payload.model_dump(),
                    )
                )
        elif dataset == "index_constituents":
            # 当前官网公开接口提供指数详情页十大权重，作为官方权重成分样本保存。
            constituents = []
            for row in table.rows:
                constituents.append(
                    {
                        "entity_id": self._format_security_symbol(
                            row.get("securityCode", ""),
                            row.get("marketNameCn", row.get("marketName", "")),
                        ),
                        "name": row.get("securityName", ""),
                        "name_en": row.get("securityNameEn", ""),
                        "weight": self._safe_float(row.get("weight")),
                        "market": row.get("marketNameCn", row.get("marketName", "")),
                        "rank": self._safe_int(row.get("rowNum")),
                    }
                )

            as_of = ""
            if table.rows:
                as_of = self._format_csindex_date(table.rows[0].get("tradeDate"))
            if not as_of:
                as_of = self._format_csindex_date(table.metadata.get("update_date"))

            payload = IndexPayload(
                index_code=index_code,
                index_name=COMMON_INDICES.get(index_code, ""),
                constituents=constituents,
                as_of=as_of or str(datetime.utcnow().date()),
            )
            records.append(
                IngestionRecord(
                    source=self.source,
                    dataset=dataset,
                    asset_type=AssetType.INDEX,
                    entity_type=EntityType.INDEX,
                    entity_id=index_code,
                    raw_uri=raw_uri,
                    content_hash=content_hash,
                    published_at=datetime.utcnow(),
                    payload=payload.model_dump(),
                )
            )

        return records

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _fetch_constituents(self, index_code: str) -> RawObject:
        """获取指数官方十大权重样本.

        中证官网旧的 component-list API 已下线；当前指数详情页公开暴露的是
        /index/weight/top10new/{indexCode}，返回十大权重与更新日期。
        """
        resp = self._session.get(
            f"{CSINDEX_TOP10_WEIGHT}/{index_code}",
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        serialized = json.dumps(data, ensure_ascii=False, default=str)
        source_uri = f"csindex://constituents/{index_code}/top10"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "index_code": index_code,
                "dataset": "index_constituents",
                "item_type": "index_constituents",
                "source_scope": "top10_weight",
                "update_date": self._format_csindex_date(
                    data.get("data", {}).get("updateDate") if isinstance(data, dict) else None
                ),
            },
        )

    def _fetch_valuation(self, index_code: str) -> RawObject:
        """获取指数收益/估值概览数据."""
        resp = self._session.get(
            f"{CSINDEX_YIELD_ITEM}/{index_code}",
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        serialized = json.dumps(data, ensure_ascii=False, default=str)
        source_uri = f"csindex://valuation/{index_code}"

        return RawObject(
            data=serialized,
            content_type="application/json",
            source_uri=source_uri,
            metadata={
                "index_code": index_code,
                "dataset": "index_valuation",
                "item_type": "index_valuation",
            },
        )

    def _persist_extra_records(self, records: List[IngestionRecord], repo: Any) -> int:
        if not records:
            return 0

        rows = []
        for record in records:
            if record.dataset != "index_constituents":
                continue
            payload = record.payload or {}
            as_of = self._parse_date(payload.get("as_of"))
            for component in payload.get("constituents", []):
                rows.append(
                    {
                        "index_symbol": payload.get("index_code") or record.entity_id,
                        "component_symbol": component.get("entity_id", ""),
                        "component_name": component.get("name"),
                        "weight": self._safe_float(component.get("weight")),
                        "as_of": as_of,
                        "source": self.source,
                        "raw_payload": component,
                    }
                )

        return repo.upsert_index_components(rows)

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """安全转换为 float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _format_security_symbol(code: str, market_name: str) -> str:
        if not code:
            return ""
        code = str(code)
        if code.endswith((".SH", ".SZ", ".BJ")):
            return code
        if "深圳" in str(market_name) or code.startswith(("0", "2", "3")):
            return f"{code}.SZ"
        if "上海" in str(market_name) or code.startswith(("5", "6", "9")):
            return f"{code}.SH"
        return code

    @staticmethod
    def _format_csindex_date(value: Any) -> str:
        if not value:
            return ""
        text = str(value)
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
        return text[:10]

    @staticmethod
    def _parse_date(value: Any) -> datetime:
        formatted = CsindexMarketConnector._format_csindex_date(value)
        if not formatted:
            return datetime.utcnow()
        try:
            return datetime.strptime(formatted, "%Y-%m-%d")
        except ValueError:
            return datetime.utcnow()

    # persist() 由 MarketDataConnector 基类提供（模板方法）
    # _format_date() / _to_decimal() / _parse_date() 由 MarketDataConnector 基类提供
