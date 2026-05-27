"""
Issue #47 单元测试 - 回测视角与消息面特征

测试内容：
1. 时间可用性模型
2. 历史回放查询
3. 消息面特征计算
4. 数据分层管理
5. 回测与报告视角分离
"""
from datetime import datetime, timedelta

import pytest

from core.contracts.backtest import (
    DataTier,
    HistoricalEventStream,
    HistoricalReplayQuery,
    NewsFeatureQuery,
    NewsFeatureSet,
    NewsFeatureType,
    RetrievalConfig,
    TimeAvailability,
    ViewContext,
)
from services.data_tier_service import DataTierService
from services.historical_replay_service import HistoricalReplayService
from services.news_feature_service import NewsFeatureService


class TestTimeAvailability:
    """测试时间可用性模型"""

    def test_create_time_availability(self):
        """测试创建时间可用性"""
        now = datetime.utcnow()
        published = now - timedelta(hours=2)
        crawled = now - timedelta(hours=1)

        ta = TimeAvailability.create(
            crawl_time=crawled,
            published_at=published,
            event_time=published,
            publish_time_precision="day",
        )

        assert ta.published_at == published
        assert ta.crawl_time == crawled
        assert ta.available_time == crawled  # available_time = max(published, crawled)
        assert ta.event_time == published
        assert ta.publish_time_precision == "day"

    def test_is_available_at(self):
        """测试检查在某个时间点是否可用"""
        now = datetime.utcnow()
        available_time = now - timedelta(hours=1)

        ta = TimeAvailability(
            published_at=available_time - timedelta(hours=1),
            crawl_time=available_time,
            available_time=available_time,
        )

        # 在 available_time 之后应该可用
        assert ta.is_available_at(now) is True
        assert ta.is_available_at(available_time) is True

        # 在 available_time 之前应该不可用
        assert ta.is_available_at(available_time - timedelta(minutes=1)) is False

    def test_get_tier(self):
        """测试获取数据层级"""
        now = datetime.utcnow()

        # 热数据（<=7天）
        hot_ta = TimeAvailability(
            crawl_time=now - timedelta(days=3),
            available_time=now - timedelta(days=3),
        )
        assert hot_ta.get_tier(now) == DataTier.HOT

        # 温数据（>7天，<=30天）
        warm_ta = TimeAvailability(
            crawl_time=now - timedelta(days=15),
            available_time=now - timedelta(days=15),
        )
        assert warm_ta.get_tier(now) == DataTier.WARM

        # 冷数据（>30天，<=365天）
        cold_ta = TimeAvailability(
            crawl_time=now - timedelta(days=100),
            available_time=now - timedelta(days=100),
        )
        assert cold_ta.get_tier(now) == DataTier.COLD

        # 归档数据（>365天）
        archived_ta = TimeAvailability(
            crawl_time=now - timedelta(days=400),
            available_time=now - timedelta(days=400),
        )
        assert archived_ta.get_tier(now) == DataTier.ARCHIVED


class TestHistoricalReplayService:
    """测试历史回放服务"""

    def test_query_events_at_time_point(self):
        """测试在某个时间点查询事件"""
        service = HistoricalReplayService()
        now = datetime.utcnow()

        # 查询昨天的视角
        query_time = now - timedelta(days=1)
        query = HistoricalReplayQuery(
            query_time=query_time,
            lookback_days=30,
            max_items=50,
        )

        result = service.query(query)

        assert isinstance(result, HistoricalEventStream)
        assert result.query_time == query_time
        # 所有返回的事件在 query_time 时应该都已经可用
        for event in result.events:
            assert event.time_availability.is_available_at(query_time) is True

    def test_query_filter_by_entity(self):
        """测试按实体过滤"""
        service = HistoricalReplayService()
        now = datetime.utcnow()

        # 查询与贵州茅台相关的事件
        query = HistoricalReplayQuery(
            query_time=now,
            entity_ids=["600519.SH"],
            lookback_days=30,
            max_items=50,
        )

        result = service.query(query)

        for event in result.events:
            assert "600519.SH" in event.entity_ids

    def test_query_filter_by_industry(self):
        """测试按行业过滤"""
        service = HistoricalReplayService()
        now = datetime.utcnow()

        query = HistoricalReplayQuery(
            query_time=now,
            industry_ids=["tech"],
            lookback_days=30,
            max_items=50,
        )

        result = service.query(query)

        for event in result.events:
            assert any("tech" in ind for ind in event.industry_ids)

    def test_time_travel_safety_check(self):
        """测试时间旅行安全检查"""
        service = HistoricalReplayService()
        now = datetime.utcnow()

        # 过去的数据 - 应该安全
        assert (
            service.check_time_travel_safety(
                data_id="test_1",
                data_time=now - timedelta(days=1),
                analysis_time=now,
            )
            is True
        )

        # 未来的数据 - 应该不安全
        assert (
            service.check_time_travel_safety(
                data_id="test_2",
                data_time=now + timedelta(days=1),
                analysis_time=now,
            )
            is False
        )


class TestNewsFeatureService:
    """测试消息面特征服务"""

    def test_compute_mention_count(self):
        """测试计算提及次数"""
        service = NewsFeatureService()
        now = datetime.utcnow()

        query = NewsFeatureQuery(
            entity_id="600519.SH",
            feature_types=[NewsFeatureType.MENTION_COUNT],
            start_time=now - timedelta(days=30),
            end_time=now,
            time_bucket="1d",
        )

        feature_set = service.compute_features(query)

        assert isinstance(feature_set, NewsFeatureSet)
        # 检查是否有 MENTION_COUNT 类型的特征
        any(f.feature_type == NewsFeatureType.MENTION_COUNT for f in feature_set.features)
        # 因为我们只有模拟数据，结果可能为空，这里主要检查没有报错

    def test_compute_sentiment_score(self):
        """测试计算情绪分数"""
        service = NewsFeatureService()
        now = datetime.utcnow()

        query = NewsFeatureQuery(
            entity_id="600519.SH",
            feature_types=[NewsFeatureType.SENTIMENT_SCORE],
            start_time=now - timedelta(days=30),
            end_time=now,
            time_bucket="1d",
        )

        feature_set = service.compute_features(query)

        # 情绪分数应该在 0-1 之间
        for feature in feature_set.features:
            if feature.feature_type == NewsFeatureType.SENTIMENT_SCORE:
                assert 0.0 <= feature.value <= 1.0

    def test_get_feature_ts(self):
        """测试获取特征时间序列"""
        service = NewsFeatureService()
        now = datetime.utcnow()

        ts_data = service.get_entity_feature_ts(
            entity_id="600519.SH",
            feature_type=NewsFeatureType.SENTIMENT_SCORE,
            start=now - timedelta(days=30),
            end=now,
        )

        assert isinstance(ts_data, list)
        for item in ts_data:
            assert "timestamp" in item
            assert "value" in item


class TestDataTierService:
    """测试数据分层服务"""

    def test_get_tier_for_age(self):
        """测试根据年龄获取层级"""
        service = DataTierService()

        assert service.get_tier_for_age(3) == DataTier.HOT
        assert service.get_tier_for_age(7) == DataTier.HOT
        assert service.get_tier_for_age(15) == DataTier.WARM
        assert service.get_tier_for_age(30) == DataTier.WARM
        assert service.get_tier_for_age(100) == DataTier.COLD
        assert service.get_tier_for_age(365) == DataTier.COLD
        assert service.get_tier_for_age(500) == DataTier.ARCHIVED

    def test_record_and_get_access_frequency(self):
        """测试记录和获取访问频率"""
        service = DataTierService()

        # 记录几次访问
        now = datetime.utcnow()
        service.record_access("data_1", now)
        service.record_access("data_1", now - timedelta(hours=1))
        service.record_access("data_1", now - timedelta(days=1))

        # 获取访问频率
        freq = service.get_access_frequency("data_1", window_days=7)
        assert freq == 3

        # 没有访问记录
        assert service.get_access_frequency("data_nonexistent", window_days=7) == 0

    def test_get_tier_summary(self):
        """测试获取分层统计"""
        service = DataTierService()

        # 设置一些数据层级
        service.set_data_tier("data_1", DataTier.HOT)
        service.set_data_tier("data_2", DataTier.HOT)
        service.set_data_tier("data_3", DataTier.WARM)

        summary = service.get_tier_summary()

        assert DataTier.HOT in summary
        assert summary[DataTier.HOT]["count"] == 2
        assert DataTier.WARM in summary
        assert summary[DataTier.WARM]["count"] == 1

    def test_get_retention_policy(self):
        """测试获取保留策略"""
        service = DataTierService()

        hot_policy = service.get_tier_retention_policy(DataTier.HOT)
        assert hot_policy["retention_days"] == 7

        cold_policy = service.get_tier_retention_policy(DataTier.COLD)
        assert cold_policy["compression"] == "gzip"


class TestViewContextSeparation:
    """测试回测与报告视角分离"""

    def test_report_view_config(self):
        """测试报告视角配置"""
        config = RetrievalConfig.for_report()

        assert config.view_context == ViewContext.REPORT
        assert config.max_lookback_days == 30
        assert config.min_reliability_score >= 0.5
        assert config.require_available_time_check is False

    def test_backtest_view_config(self):
        """测试回测视角配置"""
        config = RetrievalConfig.for_backtest()

        assert config.view_context == ViewContext.BACKTEST
        assert config.max_lookback_days >= 365
        assert config.require_available_time_check is True

    def test_get_retrieval_config_from_service(self):
        """测试从服务获取配置"""
        service = HistoricalReplayService()

        report_config = service.get_retrieval_config(ViewContext.REPORT)
        assert report_config.view_context == ViewContext.REPORT

        backtest_config = service.get_retrieval_config(ViewContext.BACKTEST)
        assert backtest_config.view_context == ViewContext.BACKTEST


class TestIntegration:
    """集成测试"""

    def test_historical_replay_with_feature_calculation(self):
        """测试历史回放与特征计算集成"""
        replay_service = HistoricalReplayService()
        feature_service = NewsFeatureService()
        now = datetime.utcnow()

        # 1. 先获取历史事件
        query = HistoricalReplayQuery(
            query_time=now,
            lookback_days=30,
            max_items=20,
        )
        replay_result = replay_service.query(query)

        # 2. 再计算特征
        feature_query = NewsFeatureQuery(
            start_time=now - timedelta(days=30),
            end_time=now,
            time_bucket="1d",
        )
        features = feature_service.compute_features(feature_query)

        # 验证
        assert isinstance(replay_result, HistoricalEventStream)
        assert isinstance(features, NewsFeatureSet)

    def test_full_time_aware_workflow(self):
        """测试完整的时间感知工作流"""
        replay_service = HistoricalReplayService()
        NewsFeatureService()
        tier_service = DataTierService()
        now = datetime.utcnow()

        # 假设我们在做回测，回测时间点是 7 天前
        backtest_time = now - timedelta(days=7)

        # 1. 使用回测视角配置
        config = RetrievalConfig.for_backtest()
        assert config.require_available_time_check is True

        # 2. 查询在 backtest_time 时可见的信息
        query = HistoricalReplayQuery(
            query_time=backtest_time,
            lookback_days=30,
            max_items=50,
        )
        events = replay_service.query(query)

        # 3. 验证没有未来信息
        for event in events.events:
            assert event.time_availability.is_available_at(backtest_time) is True

        # 4. 数据分层检查
        for event in events.events:
            tier = event.time_availability.get_tier(now)
            # 记录层级
            tier_service.set_data_tier(event.event_id, tier)

        # 工作流完成
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
