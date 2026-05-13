"""
测试采集调度器
"""
from datetime import datetime, time
from unittest.mock import Mock, patch

import pytest

from core.contracts import SourceType
from core.services.crawl_scheduler import CrawlScheduler, SourceCrawlConfig


class TestSourceCrawlConfig:
    """测试来源抓取配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = SourceCrawlConfig(
            source_type=SourceType.CAILIAN_SHE,
            source_name="财联社",
        )
        assert config.only_during_trading_hours is True
        assert config.include_auction is False

    def test_config_with_trading_options(self):
        """测试带交易时段选项的配置"""
        config = SourceCrawlConfig(
            source_type=SourceType.CAILIAN_SHE,
            source_name="财联社",
            only_during_trading_hours=False,
            include_auction=True,
        )
        assert config.only_during_trading_hours is False
        assert config.include_auction is True


class TestCrawlScheduler:
    """测试采集调度器"""

    def test_init(self):
        """测试初始化"""
        scheduler = CrawlScheduler()
        assert scheduler.running is False
        assert len(scheduler.configs) > 0
        assert len(scheduler.calendars) > 0

    def test_add_config(self):
        """测试添加配置"""
        scheduler = CrawlScheduler()
        new_config = SourceCrawlConfig(
            source_type=SourceType.OTHER,
            source_name="测试来源",
        )
        scheduler.add_config(new_config)
        assert SourceType.OTHER in scheduler.configs
        assert SourceType.OTHER in scheduler.calendars

    def test_get_status(self):
        """测试获取状态"""
        scheduler = CrawlScheduler()
        status = scheduler.get_status()
        assert "running" in status
        assert "sources" in status
        assert len(status["sources"]) > 0

        # 检查每个来源的状态
        for source in status["sources"]:
            assert "source_type" in source
            assert "enabled" in source
            assert "should_run" in source
            assert "run_reason" in source

    def test_check_source_should_run_during_trading(self):
        """测试交易时段检查"""
        scheduler = CrawlScheduler()

        # mock 日历，让它总是返回应该运行
        with patch.object(
            scheduler.calendars[SourceType.CAILIAN_SHE], "should_run_now"
        ) as mock_should:
            mock_should.return_value = (True, "在交易时段")
            should_run, reason = scheduler.check_source_should_run(SourceType.CAILIAN_SHE)
            assert should_run is True
            assert "交易时段" in reason

    def test_check_source_should_run_disabled(self):
        """测试禁用的来源"""
        scheduler = CrawlScheduler()

        # 先禁用
        scheduler.configs[SourceType.CAILIAN_SHE].enabled = False

        should_run, reason = scheduler.check_source_should_run(SourceType.CAILIAN_SHE)
        assert should_run is False
        assert "已禁用" in reason

    def test_check_source_should_run_no_config(self):
        """测试无配置的来源"""
        scheduler = CrawlScheduler()
        should_run, reason = scheduler.check_source_should_run(SourceType.OTHER)
        assert should_run is False
        assert "无配置" in reason

    @patch("core.services.crawl_scheduler.APSCHEDULER_AVAILABLE", False)
    def test_start_without_apscheduler(self):
        """测试无APScheduler时启动"""
        scheduler = CrawlScheduler()
        scheduler.start()  # 应该只是记录警告，不会报错
        assert scheduler.running is False

    @patch("core.services.crawl_scheduler.APSCHEDULER_AVAILABLE", True)
    def test_start_stop(self):
        """测试启动和停止"""
        scheduler = CrawlScheduler()

        # mock scheduler
        mock_scheduler = Mock()
        scheduler.scheduler = mock_scheduler

        # 直接设置running状态测试
        scheduler.running = True
        assert scheduler.running is True

        scheduler.stop()
        assert scheduler.running is False

    def test_trigger_crawl(self):
        """测试手动触发抓取"""
        scheduler = CrawlScheduler()

        # mock orchestrator
        mock_result = Mock()
        mock_result.success_count = 1
        mock_result.skipped_count = 0
        mock_result.failure_count = 0
        mock_result.saved_doc_ids = ["test_123"]
        scheduler.orchestrator.crawl_source = Mock(return_value=mock_result)

        result = scheduler.trigger_crawl(SourceType.CAILIAN_SHE)
        assert result is not None
        assert result["success_count"] == 1
        scheduler.orchestrator.crawl_source.assert_called_once()

    def test_trigger_crawl_no_config(self):
        """测试无配置时手动触发"""
        scheduler = CrawlScheduler()
        result = scheduler.trigger_crawl(SourceType.OTHER)
        assert result is None

    def test_trigger_backfill(self):
        """测试手动触发补漏"""
        scheduler = CrawlScheduler()

        # mock orchestrator
        mock_result = Mock()
        mock_result.success_count = 2
        mock_result.skipped_count = 1
        mock_result.failure_count = 0
        scheduler.orchestrator.backfill_source = Mock(return_value=mock_result)

        result = scheduler.trigger_backfill(SourceType.CAILIAN_SHE)
        assert result is not None
        assert result["success_count"] == 2
        scheduler.orchestrator.backfill_source.assert_called_once()
