"""
Issue #47: 消息面特征服务 - 计算新闻相关的特征

核心功能：
1. 提及次数统计
2. 事件统计
3. 情绪强度计算
4. 主题热度计算
5. 来源加权信号
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.contracts.backtest import (
    HistoricalEvent,
    NewsFeatureQuery,
    NewsFeatureSet,
    NewsFeatureType,
    NewsFeatureValue,
)
from core.observability import get_logger

logger = get_logger(__name__)


class NewsFeatureService:
    """消息面特征服务"""

    def __init__(
        self,
        historical_replay_service: Optional[Any] = None,
    ):
        self.replay_service = historical_replay_service
        # 内存存储的事件数据
        self._events: List[HistoricalEvent] = []
        # 模拟的情绪分数
        self._sentiment_scores: Dict[str, float] = {}
        self._init_sample_data()

    def _init_sample_data(self):
        """初始化一些示例数据"""
        if self.replay_service:
            # 从 replay service 获取
            pass
        else:
            # 模拟数据
            now = datetime.utcnow()
            for i in range(30):
                now - timedelta(days=i)
                self._sentiment_scores[f"event_{i:03d}"] = 0.5 + (i % 7 - 3) * 0.1

    def compute_features(
        self,
        query: NewsFeatureQuery,
    ) -> NewsFeatureSet:
        """
        计算消息面特征

        Args:
            query: 特征查询

        Returns:
            特征集合
        """
        logger.info(
            "computing news features",
            entity_id=query.entity_id,
            industry_id=query.industry_id,
            time_bucket=query.time_bucket,
        )

        features: List[NewsFeatureValue] = []

        # 确定时间粒度
        bucket_delta = self._get_bucket_delta(query.time_bucket)

        # 遍历时间窗口
        current_time = query.end_time
        while current_time >= query.start_time:
            bucket_end = current_time
            bucket_start = bucket_end - bucket_delta

            # 计算这个时间桶内的特征
            bucket_features = self._compute_features_for_bucket(
                start=bucket_start,
                end=bucket_end,
                entity_id=query.entity_id,
                industry_id=query.industry_id,
                feature_types=query.feature_types,
                include_source_breakdown=query.include_source_breakdown,
            )
            features.extend(bucket_features)

            current_time = bucket_start - timedelta(minutes=1)

        # 按时间排序（从新到旧）
        features.sort(key=lambda f: f.timestamp, reverse=True)

        logger.info(
            "news features computed",
            total_features=len(features),
        )

        return NewsFeatureSet(query=query, features=features)

    def _compute_features_for_bucket(
        self,
        start: datetime,
        end: datetime,
        entity_id: Optional[str],
        industry_id: Optional[str],
        feature_types: Optional[List[NewsFeatureType]],
        include_source_breakdown: bool,
    ) -> List[NewsFeatureValue]:
        """计算单个时间桶内的特征"""
        if feature_types is None:
            feature_types = list(NewsFeatureType)

        features: List[NewsFeatureValue] = []

        # 过滤事件
        filtered_events = self._filter_events(
            start=start,
            end=end,
            entity_id=entity_id,
            industry_id=industry_id,
        )

        # 计算各特征
        if NewsFeatureType.MENTION_COUNT in feature_types:
            mention_count = len(filtered_events)
            features.append(
                NewsFeatureValue(
                    feature_type=NewsFeatureType.MENTION_COUNT,
                    timestamp=end,
                    value=float(mention_count),
                    entity_id=entity_id,
                    industry_id=industry_id,
                    source_breakdown=(
                        self._count_by_source(filtered_events) if include_source_breakdown else None
                    ),
                )
            )

        if NewsFeatureType.EVENT_COUNT in feature_types:
            event_count = len(filtered_events)
            features.append(
                NewsFeatureValue(
                    feature_type=NewsFeatureType.EVENT_COUNT,
                    timestamp=end,
                    value=float(event_count),
                    entity_id=entity_id,
                    industry_id=industry_id,
                )
            )

        if NewsFeatureType.SENTIMENT_SCORE in feature_types:
            sentiment = self._compute_sentiment(filtered_events)
            features.append(
                NewsFeatureValue(
                    feature_type=NewsFeatureType.SENTIMENT_SCORE,
                    timestamp=end,
                    value=sentiment,
                    entity_id=entity_id,
                    industry_id=industry_id,
                )
            )

        if NewsFeatureType.POSITIVE_INTENSITY in feature_types:
            pos_intensity = self._compute_positive_intensity(filtered_events)
            features.append(
                NewsFeatureValue(
                    feature_type=NewsFeatureType.POSITIVE_INTENSITY,
                    timestamp=end,
                    value=pos_intensity,
                    entity_id=entity_id,
                    industry_id=industry_id,
                )
            )

        if NewsFeatureType.NEGATIVE_INTENSITY in feature_types:
            neg_intensity = self._compute_negative_intensity(filtered_events)
            features.append(
                NewsFeatureValue(
                    feature_type=NewsFeatureType.NEGATIVE_INTENSITY,
                    timestamp=end,
                    value=neg_intensity,
                    entity_id=entity_id,
                    industry_id=industry_id,
                )
            )

        if NewsFeatureType.THEME_HEAT in feature_types:
            theme_heat = self._compute_theme_heat(filtered_events)
            features.append(
                NewsFeatureValue(
                    feature_type=NewsFeatureType.THEME_HEAT,
                    timestamp=end,
                    value=theme_heat,
                    entity_id=entity_id,
                    industry_id=industry_id,
                )
            )

        return features

    def _filter_events(
        self,
        start: datetime,
        end: datetime,
        entity_id: Optional[str],
        industry_id: Optional[str],
    ) -> List[HistoricalEvent]:
        """过滤事件"""
        filtered: List[HistoricalEvent] = []

        for event in self._events:
            event_time = (
                event.time_availability.event_time or event.time_availability.available_time
            )
            if event_time < start or event_time > end:
                continue

            if entity_id and entity_id not in event.entity_ids:
                continue

            if industry_id and industry_id not in event.industry_ids:
                continue

            filtered.append(event)

        return filtered

    def _count_by_source(
        self,
        events: List[HistoricalEvent],
    ) -> Dict[str, float]:
        """按来源统计"""
        counts: Dict[str, int] = defaultdict(int)
        for event in events:
            counts[event.source_type] += 1

        total = len(events) if events else 1
        return {k: v / total for k, v in counts.items()}

    def _compute_sentiment(
        self,
        events: List[HistoricalEvent],
    ) -> float:
        """计算情绪分数"""
        if not events:
            return 0.5

        # 模拟情绪计算
        total = 0.0
        for event in events:
            # 从模拟数据获取
            base = self._sentiment_scores.get(event.event_id, 0.5)
            total += base

        return total / len(events)

    def _compute_positive_intensity(
        self,
        events: List[HistoricalEvent],
    ) -> float:
        """计算正面强度"""
        sentiment = self._compute_sentiment(events)
        return max(0.0, (sentiment - 0.5) * 2)

    def _compute_negative_intensity(
        self,
        events: List[HistoricalEvent],
    ) -> float:
        """计算负面强度"""
        sentiment = self._compute_sentiment(events)
        return max(0.0, (0.5 - sentiment) * 2)

    def _compute_theme_heat(
        self,
        events: List[HistoricalEvent],
    ) -> float:
        """计算主题热度"""
        # 基于事件类型多样性和数量
        if not events:
            return 0.0

        event_types = set()
        for event in events:
            event_types.add(event.event_type)

        diversity = len(event_types) / 5.0  # 标准化到 0-1
        count_score = min(1.0, len(events) / 10.0)

        return (diversity + count_score) / 2.0

    def _get_bucket_delta(
        self,
        time_bucket: str,
    ) -> timedelta:
        """获取时间桶长度"""
        deltas = {
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1mo": timedelta(days=30),
        }
        return deltas.get(time_bucket, timedelta(days=1))

    def get_entity_feature_ts(
        self,
        entity_id: str,
        feature_type: NewsFeatureType,
        start: datetime,
        end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        获取实体特征时间序列

        Args:
            entity_id: 实体 ID
            feature_type: 特征类型
            start: 开始时间
            end: 结束时间

        Returns:
            时间序列数据
        """
        query = NewsFeatureQuery(
            entity_id=entity_id,
            feature_types=[feature_type],
            start_time=start,
            end_time=end,
            time_bucket="1d",
        )
        feature_set = self.compute_features(query)

        ts_data = []
        for feature in feature_set.features:
            ts_data.append(
                {
                    "timestamp": feature.timestamp,
                    "value": feature.value,
                }
            )

        return ts_data

    def add_event(
        self,
        event: HistoricalEvent,
        sentiment_score: Optional[float] = None,
    ) -> None:
        """
        添加事件

        Args:
            event: 历史事件
            sentiment_score: 情绪分数
        """
        self._events.append(event)
        if sentiment_score is not None:
            self._sentiment_scores[event.event_id] = sentiment_score

        logger.info(
            "added event to news feature service",
            event_id=event.event_id,
            sentiment=sentiment_score,
        )
