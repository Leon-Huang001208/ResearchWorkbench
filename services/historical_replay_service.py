"""
Issue #47: 历史回放服务 - 提供过去某个时间点可见的信息

核心功能：
1. 时间切片查询 - 在某个时间点回放当时可见的信息
2. 事件流查询 - 某个时间窗口内的事件序列
3. 时间可用性验证 - 确保不使用未来信息
"""
from datetime import datetime, timedelta
from typing import Any, List, Optional

from core.contracts.backtest import (
    HistoricalEvent,
    HistoricalEventStream,
    HistoricalReplayQuery,
    RetrievalConfig,
    TimeAvailability,
    ViewContext,
)
from core.observability import get_logger

logger = get_logger(__name__)


class HistoricalReplayService:
    """历史回放服务 - 提供时间旅行视角"""

    def __init__(
        self,
        document_repository: Optional[Any] = None,
        event_repository: Optional[Any] = None,
    ):
        self.document_repo = document_repository
        self.event_repo = event_repository
        # 内存存储的模拟数据
        self._events: List[HistoricalEvent] = []
        self._init_sample_data()

    def _init_sample_data(self):
        """初始化一些示例数据用于演示"""
        now = datetime.utcnow()

        sample_events = [
            {
                "event_id": "event_001",
                "event_type": "earnings",
                "title": "贵州茅台 Q1 财报超预期",
                "summary": "贵州茅台发布 2024 Q1 财报，营收同比增长 20%，利润增长 25%",
                "entity_ids": ["600519.SH"],
                "industry_ids": ["consumer_staples", "alcohol"],
                "source_type": "news",
                "source_name": "财联社",
                "days_ago": 5,
            },
            {
                "event_id": "event_002",
                "event_type": "policy",
                "title": "央行宣布降准 0.5 个百分点",
                "summary": "中国人民银行宣布下调金融机构存款准备金率 0.5 个百分点",
                "entity_ids": [],
                "industry_ids": ["financial", "macro"],
                "source_type": "policy",
                "source_name": "中国人民银行",
                "days_ago": 10,
            },
            {
                "event_id": "event_003",
                "event_type": "product",
                "title": "宁德时代发布麒麟电池升级版",
                "summary": "宁德时代发布麒麟电池升级版，能量密度提升 15%，充电速度提升 20%",
                "entity_ids": ["300750.SZ"],
                "industry_ids": ["tech", "new_energy"],
                "source_type": "news",
                "source_name": "第一财经",
                "days_ago": 15,
            },
            {
                "event_id": "event_004",
                "event_type": "merger_acquisition",
                "title": "腾讯控股增持美团股份",
                "summary": "腾讯控股增持美团股份，持股比例从 17% 提升至 20%",
                "entity_ids": ["00700.HK", "03690.HK"],
                "industry_ids": ["tech", "internet"],
                "source_type": "report",
                "source_name": "证券时报",
                "days_ago": 20,
            },
        ]

        for sample in sample_events:
            event_time = now - timedelta(days=sample["days_ago"])
            crawl_time = event_time + timedelta(hours=2)
            available_time = crawl_time

            self._events.append(
                HistoricalEvent(
                    event_id=sample["event_id"],
                    event_type=sample["event_type"],
                    title=sample["title"],
                    summary=sample["summary"],
                    time_availability=TimeAvailability(
                        published_at=event_time,
                        crawl_time=crawl_time,
                        available_time=available_time,
                        event_time=event_time,
                        publish_time_precision="day",
                    ),
                    entity_ids=sample["entity_ids"],
                    industry_ids=sample["industry_ids"],
                    source_type=sample["source_type"],
                    source_name=sample["source_name"],
                    metadata={},
                )
            )

    def query(
        self,
        query: HistoricalReplayQuery,
    ) -> HistoricalEventStream:
        """
        历史回放查询 - 获取某个时间点可见的信息

        Args:
            query: 回放查询参数

        Returns:
            历史事件流
        """
        logger.info(
            "executing historical replay query",
            query_time=query.query_time.isoformat(),
            lookback_days=query.lookback_days,
        )

        # 计算时间范围
        start_time = query.query_time - timedelta(days=query.lookback_days)
        end_time = query.query_time

        # 过滤事件
        filtered_events: List[HistoricalEvent] = []

        for event in self._events:
            # 检查时间可用性 - 只有在 query_time 之前可用的信息才包含
            if not event.time_availability.is_available_at(query.query_time):
                continue

            # 检查事件是否在时间窗口内（event_time 或 available_time）
            event_time = (
                event.time_availability.event_time or event.time_availability.available_time
            )
            if not (start_time <= event_time <= end_time):
                continue

            # 应用实体过滤
            if query.entity_ids:
                if not any(ent in query.entity_ids for ent in event.entity_ids):
                    continue

            # 应用行业过滤
            if query.industry_ids:
                if not any(ind in query.industry_ids for ind in event.industry_ids):
                    continue

            # 应用来源类型过滤
            if query.source_types:
                if event.source_type not in query.source_types:
                    continue

            # 应用事件类型过滤
            if query.event_types:
                if event.event_type not in query.event_types:
                    continue

            filtered_events.append(event)

        # 按时间排序（从旧到新）
        filtered_events.sort(key=lambda e: e.time_availability.available_time or datetime.min)

        # 限制数量
        if len(filtered_events) > query.max_items:
            filtered_events = filtered_events[: query.max_items]

        logger.info(
            "historical replay query completed",
            total_events=len(filtered_events),
            time_range=f"{start_time.date()} to {end_time.date()}",
        )

        return HistoricalEventStream(
            query_time=query.query_time,
            events=filtered_events,
            time_range_start=start_time,
            time_range_end=end_time,
            total_count=len(filtered_events),
        )

    def get_available_at(
        self,
        entity_id: str,
        query_time: datetime,
        lookback_days: int = 30,
    ) -> List[HistoricalEvent]:
        """
        获取某个实体在某个时间点可见的所有事件

        Args:
            entity_id: 实体 ID
            query_time: 查询时间点
            lookback_days: 回顾天数

        Returns:
            历史事件列表
        """
        query = HistoricalReplayQuery(
            query_time=query_time,
            entity_ids=[entity_id],
            lookback_days=lookback_days,
            max_items=100,
        )
        result = self.query(query)
        return result.events

    def check_time_travel_safety(
        self,
        data_id: str,
        data_time: datetime,
        analysis_time: datetime,
    ) -> bool:
        """
        检查时间旅行安全性 - 确保分析时不会使用未来信息

        Args:
            data_id: 数据 ID
            data_time: 数据时间（发布或可用时间）
            analysis_time: 分析时间点

        Returns:
            是否安全
        """
        is_safe = data_time <= analysis_time

        if not is_safe:
            logger.warning(
                "time travel safety check failed - future data detected",
                data_id=data_id,
                data_time=data_time.isoformat(),
                analysis_time=analysis_time.isoformat(),
            )

        return is_safe

    def get_retrieval_config(
        self,
        view_context: ViewContext,
    ) -> RetrievalConfig:
        """
        获取合适的检索配置

        Args:
            view_context: 视图上下文（报告或回测）

        Returns:
            检索配置
        """
        if view_context == ViewContext.REPORT:
            return RetrievalConfig.for_report()
        else:
            return RetrievalConfig.for_backtest()

    def add_event(
        self,
        event: HistoricalEvent,
    ) -> None:
        """
        添加历史事件（用于数据入库）

        Args:
            event: 历史事件
        """
        self._events.append(event)
        logger.info("added historical event", event_id=event.event_id)

    def get_event(
        self,
        event_id: str,
    ) -> Optional[HistoricalEvent]:
        """
        获取单个历史事件

        Args:
            event_id: 事件 ID

        Returns:
            历史事件（如果存在）
        """
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None
