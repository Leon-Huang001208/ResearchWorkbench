"""
Issue #47: 回测视角 - 核心契约

本模块定义回测视角的核心数据结构，包括：
- 时间可用性模型（available_time）
- 历史回放查询
- 消息面特征
- 事件流与技术面联动
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ==================== 时间层相关 ====================


class DataTier(str, Enum):
    """数据分层 - 热/温/冷/归档"""

    HOT = "hot"  # 热数据 - 高频访问，最近7天
    WARM = "warm"  # 温数据 - 中频访问，最近30天
    COLD = "cold"  # 冷数据 - 低频访问，最近1年
    ARCHIVED = "archived"  # 归档数据 - 历史数据，1年以上


class TimeAvailability(BaseModel):
    """时间可用性模型 - 确保回测中不会使用未来信息"""

    model_config = ConfigDict(extra="forbid")

    published_at: Optional[datetime] = Field(default=None, description="文档发布时间")
    crawl_time: datetime = Field(description="系统抓取/录入时间")
    available_time: datetime = Field(description="信息实际可用时间 = max(published_at, crawl_time)")
    event_time: Optional[datetime] = Field(default=None, description="事件实际发生时间（如适用）")
    publish_time_precision: Optional[Literal["exact", "day", "week", "month"]] = Field(
        default=None, description="发布时间精度"
    )

    @classmethod
    def create(
        cls,
        crawl_time: datetime,
        published_at: Optional[datetime] = None,
        event_time: Optional[datetime] = None,
        publish_time_precision: Optional[str] = None,
    ) -> "TimeAvailability":
        """创建时间可用性模型"""
        available_time = crawl_time
        if published_at:
            available_time = max(published_at, crawl_time)

        return cls(
            published_at=published_at,
            crawl_time=crawl_time,
            available_time=available_time,
            event_time=event_time,
            publish_time_precision=publish_time_precision,  # type: ignore
        )

    def is_available_at(self, query_time: datetime) -> bool:
        """检查在指定查询时间点，该信息是否已经可用"""
        return query_time >= self.available_time

    def get_tier(self, reference_time: Optional[datetime] = None) -> DataTier:
        """获取数据当前所在的层"""
        ref_time = reference_time or datetime.utcnow()
        age = ref_time - self.available_time

        if age <= timedelta(days=7):
            return DataTier.HOT
        elif age <= timedelta(days=30):
            return DataTier.WARM
        elif age <= timedelta(days=365):
            return DataTier.COLD
        else:
            return DataTier.ARCHIVED


# ==================== 历史回放相关 ====================


class HistoricalReplayQuery(BaseModel):
    """历史回放查询 - 在某个时间点回放当时可见的信息"""

    model_config = ConfigDict(extra="forbid")

    query_time: datetime = Field(description="查询时间点 - 只能看到这个时间之前可用的信息")
    entity_ids: Optional[List[str]] = Field(default=None, description="实体ID列表，如股票代码")
    industry_ids: Optional[List[str]] = Field(default=None, description="行业ID列表")
    source_types: Optional[List[str]] = Field(default=None, description="来源类型过滤")
    event_types: Optional[List[str]] = Field(default=None, description="事件类型过滤")
    lookback_days: int = Field(default=30, ge=1, description="回顾天数 - 从query_time往前看多少天")
    max_items: int = Field(default=100, ge=1, description="返回最大项目数")
    include_content: bool = Field(default=False, description="是否包含完整内容（否则只返回元数据）")


class HistoricalEventStream(BaseModel):
    """历史事件流 - 某个时间窗口内的事件序列"""

    model_config = ConfigDict(extra="forbid")

    query_time: datetime = Field(description="查询时间点")
    events: List["HistoricalEvent"] = Field(default_factory=list, description="事件列表")
    time_range_start: datetime = Field(description="时间范围起点")
    time_range_end: datetime = Field(description="时间范围终点")
    total_count: int = Field(description="事件总数")


class HistoricalEvent(BaseModel):
    """历史事件 - 包含时间可用性信息"""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(description="事件ID")
    event_type: str = Field(description="事件类型")
    title: str = Field(description="事件标题")
    summary: str = Field(description="事件摘要")
    time_availability: TimeAvailability = Field(description="时间可用性信息")
    entity_ids: List[str] = Field(default_factory=list, description="相关实体")
    industry_ids: List[str] = Field(default_factory=list, description="相关行业")
    source_type: str = Field(description="来源类型")
    source_name: str = Field(description="来源名称")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


# ==================== 消息面特征 ====================


class NewsFeatureType(str, Enum):
    """消息面特征类型"""

    MENTION_COUNT = "mention_count"  # 提及次数
    EVENT_COUNT = "event_count"  # 事件数量
    POSITIVE_INTENSITY = "positive_intensity"  # 正面情绪强度
    NEGATIVE_INTENSITY = "negative_intensity"  # 负面情绪强度
    SENTIMENT_SCORE = "sentiment_score"  # 情绪综合得分
    SOURCE_WEIGHTED_SIGNAL = "source_weighted_signal"  # 来源加权信号
    THEME_HEAT = "theme_heat"  # 主题热度
    ANALYST_OPINION_TREND = "analyst_opinion_trend"  # 分析师观点趋势
    NEWS_RESONANCE = "news_resonance"  # 新闻共鸣度


class NewsFeatureQuery(BaseModel):
    """消息面特征查询"""

    model_config = ConfigDict(extra="forbid")

    entity_id: Optional[str] = Field(default=None, description="实体ID，如股票代码")
    industry_id: Optional[str] = Field(default=None, description="行业ID")
    feature_types: Optional[List[NewsFeatureType]] = Field(default=None, description="特征类型")
    start_time: datetime = Field(description="开始时间")
    end_time: datetime = Field(description="结束时间")
    time_bucket: Literal["1h", "4h", "1d", "1w", "1mo"] = Field(default="1d", description="时间粒度")
    include_source_breakdown: bool = Field(default=False, description="是否包含来源细分")


class NewsFeatureValue(BaseModel):
    """消息面特征值"""

    model_config = ConfigDict(extra="forbid")

    feature_type: NewsFeatureType = Field(description="特征类型")
    timestamp: datetime = Field(description="时间戳")
    value: float = Field(description="特征值")
    entity_id: Optional[str] = Field(default=None, description="实体ID")
    industry_id: Optional[str] = Field(default=None, description="行业ID")
    source_breakdown: Optional[Dict[str, float]] = Field(default=None, description="来源细分")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class NewsFeatureSet(BaseModel):
    """消息面特征集 - 多个特征的集合"""

    model_config = ConfigDict(extra="forbid")

    query: NewsFeatureQuery = Field(description="查询条件")
    features: List[NewsFeatureValue] = Field(default_factory=list, description="特征列表")

    def get_feature(
        self,
        feature_type: NewsFeatureType,
        timestamp: Optional[datetime] = None,
    ) -> Optional[NewsFeatureValue]:
        """获取指定类型的特征"""
        for feature in self.features:
            if feature.feature_type == feature_type:
                if timestamp is None or feature.timestamp == timestamp:
                    return feature
        return None

    def to_dataframe_dict(self) -> Dict[str, List[Any]]:
        """转换为 DataFrame 可用的字典格式"""
        result: Dict[str, List[Any]] = {
            "timestamp": [],
            "feature_type": [],
            "value": [],
        }
        for feature in self.features:
            result["timestamp"].append(feature.timestamp)
            result["feature_type"].append(feature.feature_type.value)
            result["value"].append(feature.value)
            if feature.entity_id:
                if "entity_id" not in result:
                    result["entity_id"] = []
                result["entity_id"].append(feature.entity_id)
        return result


# ==================== 事件流与技术面联动 ====================


class EventTechAlignmentRequest(BaseModel):
    """事件-技术面对齐请求"""

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(description="实体ID")
    event_id: str = Field(description="事件ID")
    lookforward_days: int = Field(default=20, ge=1, description="事件后观察天数")
    lookback_days: int = Field(default=5, ge=0, description="事件前观察天数")
    include_price_data: bool = Field(default=True, description="是否包含价格数据")
    include_tech_indicators: bool = Field(default=True, description="是否包含技术指标")


class EventTechAlignment(BaseModel):
    """事件-技术面对齐结果"""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(description="事件ID")
    entity_id: str = Field(description="实体ID")
    event_time: datetime = Field(description="事件时间")
    price_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="价格数据")
    tech_indicators: Optional[Dict[str, List[float]]] = Field(default=None, description="技术指标")
    abnormal_return: Optional[float] = Field(default=None, description="异常收益")
    volatility_change: Optional[float] = Field(default=None, description="波动率变化")
    volume_spike: Optional[float] = Field(default=None, description="成交量放大倍数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


# ==================== 回测与报告视角分离 ====================


class ViewContext(str, Enum):
    """视图上下文 - 区分报告视角和回测视角"""

    REPORT = "report"  # 报告视角 - 最近数据，高可信度来源
    BACKTEST = "backtest"  # 回测视角 - 完整历史，严格时间过滤


class RetrievalConfig(BaseModel):
    """检索配置 - 根据不同视图调整"""

    model_config = ConfigDict(extra="forbid")

    view_context: ViewContext = Field(description="视图上下文")
    max_lookback_days: int = Field(default=30, description="最大回顾天数")
    allowed_source_types: List[str] = Field(default_factory=list, description="允许的来源类型")
    min_reliability_score: float = Field(default=0.0, ge=0.0, le=1.0, description="最低可信度分数")
    allow_opinion_sources: bool = Field(default=True, description="是否允许观点源")
    require_available_time_check: bool = Field(default=True, description="是否需要检查可用时间")

    @classmethod
    def for_report(cls) -> "RetrievalConfig":
        """创建报告视图配置"""
        return cls(
            view_context=ViewContext.REPORT,
            max_lookback_days=30,
            allowed_source_types=[],
            min_reliability_score=0.5,
            allow_opinion_sources=True,
            require_available_time_check=False,
        )

    @classmethod
    def for_backtest(cls) -> "RetrievalConfig":
        """创建回测视图配置"""
        return cls(
            view_context=ViewContext.BACKTEST,
            max_lookback_days=3650,  # 10年
            allowed_source_types=[],
            min_reliability_score=0.0,
            allow_opinion_sources=True,
            require_available_time_check=True,
        )


# ==================== 更新前向引用 ====================

HistoricalEventStream.model_rebuild()
