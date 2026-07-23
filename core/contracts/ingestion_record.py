"""
统一摄入记录契约 — IngestionRecord 外壳 + 分型 Payload.

本模块定义了统一的数据摄入记录模型（Issue: connector 架构重构）：
- IngestionRecord: 统一外壳，包含 source、dataset、entity_id、provenance 等元信息
- 分型 Payload: DocumentPayload / MarketBarPayload / IndexPayload 等，按 asset_type 区分
- IngestionResult: connector.run() 的统一返回类型
- IngestionRun: 单次摄入运行记录

设计原则：统一接入接口、元信息、溯源、状态管理，但不统一业务数据 schema。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class AssetType(str, Enum):
    """数据资产类型 — 区分非结构化文档和结构化市场数据."""

    DOCUMENT = "document"
    MARKET = "market"
    FUNDAMENTAL = "fundamental"
    INDEX = "index"
    NEWS = "news"
    MACRO = "macro"
    OTHER = "other"


class EntityType(str, Enum):
    """实体类型."""

    STOCK = "stock"
    INDEX = "index"
    FUND = "fund"
    SECTOR = "sector"
    MACRO = "macro"
    UNKNOWN = "unknown"


class IngestionStatus(str, Enum):
    """摄入状态."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    VALIDATING = "validating"


class HealthStatus(str, Enum):
    """数据源健康状态."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


# =============================================================================
# 分型 Payload
# =============================================================================


class DocumentPayload(BaseModel):
    """文档型数据 payload — 非结构化内容.

    Attributes:
        title: 文档标题.
        doc_type: 文档类型（公告/研报/新闻/纪要等）.
        file_type: 文件格式（pdf/html/markdown/txt）.
        text: 正文内容.
        pages: 页数（PDF 等）.
        chunks: 预分块列表（可选，交给 KnowledgePipeline 处理时可为空）.
        language: 语言（默认 "zh"）.
    """

    title: str = Field(description="文档标题")
    doc_type: Optional[str] = Field(default=None, description="文档类型（公告/研报/新闻/纪要等）")
    file_type: Optional[str] = Field(default=None, description="文件格式（pdf/html/markdown/txt）")
    text: Optional[str] = Field(default=None, description="正文内容")
    pages: Optional[int] = Field(default=None, description="页数")
    chunks: List[Dict[str, Any]] = Field(default_factory=list, description="预分块列表")
    language: str = Field(default="zh", description="语言")


class MarketBarPayload(BaseModel):
    """行情数据 payload — 单条 OHLCV 记录.

    Attributes:
        trade_date: 交易日.
        open: 开盘价.
        high: 最高价.
        low: 最低价.
        close: 收盘价.
        volume: 成交量.
        amount: 成交额.
        turnover: 换手率（可选）.
        adjustment: 复权方式（none / forward / backward）.
        currency: 币种（默认 CNY）.
    """

    trade_date: str = Field(description="交易日 (YYYY-MM-DD)")
    open: Optional[float] = Field(default=None, description="开盘价")
    high: Optional[float] = Field(default=None, description="最高价")
    low: Optional[float] = Field(default=None, description="最低价")
    close: Optional[float] = Field(default=None, description="收盘价")
    volume: Optional[float] = Field(default=None, description="成交量")
    amount: Optional[float] = Field(default=None, description="成交额")
    turnover: Optional[float] = Field(default=None, description="换手率")
    adjustment: str = Field(default="none", description="复权方式")
    currency: str = Field(default="CNY", description="币种")


class IndexPayload(BaseModel):
    """指数数据 payload — 成分股、权重、估值.

    Attributes:
        index_code: 指数代码（如 000300.SH）.
        index_name: 指数名称.
        constituents: 成分股列表，每项包含 entity_id、weight、纳入日期.
        index_pe: 指数 PE.
        index_pb: 指数 PB.
        dividend_yield: 股息率.
        as_of: 数据日期.
    """

    index_code: str = Field(description="指数代码（如 000300.SH）")
    index_name: Optional[str] = Field(default=None, description="指数名称")
    constituents: List[Dict[str, Any]] = Field(default_factory=list, description="成分股列表")
    index_pe: Optional[float] = Field(default=None, description="指数 PE")
    index_pb: Optional[float] = Field(default=None, description="指数 PB")
    dividend_yield: Optional[float] = Field(default=None, description="股息率")
    as_of: Optional[str] = Field(default=None, description="数据日期")


class NewsPayload(BaseModel):
    """新闻/快讯数据 payload.

    Attributes:
        title: 新闻标题.
        content: 新闻正文.
        summary: 摘要.
        url: 原始 URL.
        source_name: 来源名称.
        tags: 标签列表.
        related_entities: 关联实体列表.
    """

    title: str = Field(description="新闻标题")
    content: Optional[str] = Field(default=None, description="新闻正文")
    summary: Optional[str] = Field(default=None, description="摘要")
    url: Optional[str] = Field(default=None, description="原始 URL")
    source_name: Optional[str] = Field(default=None, description="来源名称")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    related_entities: List[str] = Field(default_factory=list, description="关联实体列表")


class FundamentalPayload(BaseModel):
    """基本面/财务数据 payload.

    Attributes:
        report_period: 报告期（如 2025Q4）.
        metrics: 财务指标字典（指标名 → 数值），字段灵活以适配不同数据源.
        statement_type: 报表类型（balance_sheet / income / cash_flow）.
    """

    report_period: str = Field(description="报告期（如 2025Q4）")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="财务指标字典")
    statement_type: Optional[str] = Field(
        default=None, description="报表类型（balance_sheet/income/cash_flow）"
    )


class MacroPayload(BaseModel):
    """宏观经济数据 payload.

    Attributes:
        indicator_name: 指标名称（如 CPI、GDP、PMI）.
        indicator_value: 指标值.
        frequency: 频率（monthly / quarterly / yearly）.
        region: 地区（默认 CN）.
        unit: 单位.
    """

    indicator_name: str = Field(description="指标名称（如 CPI、GDP、PMI）")
    indicator_value: Optional[float] = Field(default=None, description="指标值")
    frequency: Optional[str] = Field(default=None, description="频率（monthly/quarterly/yearly）")
    region: str = Field(default="CN", description="地区")
    unit: Optional[str] = Field(default=None, description="单位")


# =============================================================================
# 统一 IngestionRecord
# =============================================================================


class IngestionRecord(BaseModel):
    """统一摄入记录 — 外壳 + 分型 payload.

    设计原则：
    - 外壳字段（source, dataset, entity_id, content_hash, raw_uri 等）统一，
      用于调度、日志、溯源、状态管理.
    - payload 按 asset_type 分型，业务数据各自专业化.
    - 与 IngestionQueueItem 兼容：可通过 content_hash 去重，通过 entity_id 关联实体.

    Attributes:
        source: 数据源标识（如 "cninfo", "akshare", "cls"）.
        dataset: 数据集标识（如 "announcements", "stock_daily"）.
        asset_type: 数据资产类型.
        entity_type: 关联实体类型.
        entity_id: 关联实体 ID（如 "000001.SZ"）.
        published_at: 数据原始发布时间.
        fetched_at: 数据抓取时间.
        raw_uri: 原始数据存储路径.
        content_hash: 内容 SHA256 哈希（用于去重）.
        schema_version: schema 版本号.
        payload: 分型业务数据（DocumentPayload / MarketBarPayload / IndexPayload 等）.
    """

    source: str = Field(description="数据源标识（如 cninfo, akshare, cls）")
    dataset: str = Field(description="数据集标识（如 announcements, stock_daily）")
    asset_type: AssetType = Field(description="数据资产类型")

    entity_type: EntityType = Field(default=EntityType.UNKNOWN, description="关联实体类型")
    entity_id: Optional[str] = Field(default=None, description="关联实体 ID（如 000001.SZ）")

    published_at: Optional[datetime] = Field(default=None, description="数据原始发布时间")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="数据抓取时间")

    raw_uri: Optional[str] = Field(default=None, description="原始数据存储路径")
    content_hash: Optional[str] = Field(default=None, description="内容 SHA256 哈希（用于去重）")
    schema_version: str = Field(default="v1", description="schema 版本号")

    payload: Dict[str, Any] = Field(default_factory=dict, description="分型业务数据")


# =============================================================================
# 摄入运行结果
# =============================================================================


class IngestionStats(BaseModel):
    """单次摄入的统计信息.

    Attributes:
        discovered: 发现的数据对象数量.
        fetched: 成功获取的数量.
        parsed: 成功解析的数量.
        validated: 通过校验的数量.
        persisted: 成功持久化的数量.
        failed: 处理失败的数量.
        skipped: 跳过的数量（重复等）.
        errors: 错误详情列表.
    """

    discovered: int = Field(default=0, description="发现的数据对象数量")
    fetched: int = Field(default=0, description="成功获取的数量")
    parsed: int = Field(default=0, description="成功解析的数量")
    validated: int = Field(default=0, description="通过校验的数量")
    persisted: int = Field(default=0, description="成功持久化的数量")
    failed: int = Field(default=0, description="处理失败的数量")
    skipped: int = Field(default=0, description="跳过的数量（重复等）")
    errors: List[Dict[str, str]] = Field(default_factory=list, description="错误详情列表")


class RawObjectSummary(BaseModel):
    """原始数据对象摘要 — 用于 IngestionResult 溯源.

    不含完整 data 内容（原始数据已通过 save_raw() 落盘），
    仅保留溯源所需的元信息：URI、哈希、类型、抓取时间、大小.
    """

    source_uri: str = Field(description="数据来源 URI")
    content_hash: Optional[str] = Field(default=None, description="SHA256 哈希")
    content_type: str = Field(default="", description="MIME 类型或格式")
    fetched_at: Optional[datetime] = Field(default=None, description="抓取时间")
    size_bytes: Optional[int] = Field(default=None, description="数据大小（字节）")


class IngestionResult(BaseModel):
    """connector.run() 的统一返回类型.

    Attributes:
        source: 数据源标识.
        dataset: 数据集标识.
        status: 摄入状态.
        stats: 统计信息.
        records: 产出的 IngestionRecord 列表（可选，大批量时可能不返回具体内容）.
        raw_objects: 原始数据对象摘要列表（用于溯源，不含完整 data）.
        run_id: 本次运行的唯一 ID.
        started_at: 开始时间.
        finished_at: 结束时间.
        error_message: 失败时的错误信息.
    """

    source: str = Field(description="数据源标识")
    dataset: str = Field(description="数据集标识")
    status: IngestionStatus = Field(description="摄入状态")
    stats: IngestionStats = Field(default_factory=lambda: IngestionStats(), description="统计信息")

    records: List[IngestionRecord] = Field(default_factory=list, description="产出的摄入记录列表")
    raw_objects: List[RawObjectSummary] = Field(
        default_factory=list, description="原始数据对象摘要列表（用于溯源）"
    )
    run_id: Optional[str] = Field(default=None, description="本次运行的唯一 ID")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    finished_at: Optional[datetime] = Field(default=None, description="结束时间")
    error_message: Optional[str] = Field(default=None, description="失败时的错误信息")

    # Fallback 路由追踪
    routed_source: Optional[str] = Field(
        default=None, description="实际使用的数据源（fallback 路由后）"
    )
    fallback_used: bool = Field(default=False, description="是否触发了降级（使用了备源而非主源）")


class ValidationReport(BaseModel):
    """数据校验报告 — connector.validate_existing() 的返回类型.

    Attributes:
        source: 数据源标识.
        dataset: 数据集标识.
        total_checked: 校验总数.
        passed: 通过数.
        failed: 失败数.
        issues: 问题详情列表.
        checked_at: 校验时间.
    """

    source: str = Field(description="数据源标识")
    dataset: str = Field(description="数据集标识")
    total_checked: int = Field(default=0, description="校验总数")
    passed: int = Field(default=0, description="通过数")
    failed: int = Field(default=0, description="失败数")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="问题详情列表")
    checked_at: datetime = Field(default_factory=datetime.utcnow, description="校验时间")
