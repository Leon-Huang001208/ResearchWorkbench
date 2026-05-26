"""测试采集调度器"""
from unittest.mock import Mock, patch

from core.contracts import SourceType
from core.services.crawl_scheduler import (
    CrawlScheduler,
    SourceCrawlConfig,
    build_scheduler_status,
    get_scheduler_process_status,
)


class TestCrawlScheduler:
    """测试采集调度器"""

    def test_init(self):
        scheduler = CrawlScheduler()
        assert scheduler.running is False
        assert len(scheduler.configs) > 0
        assert len(scheduler.calendars) > 0

    def test_add_config(self):
        scheduler = CrawlScheduler()
        new_config = SourceCrawlConfig(
            source_type=SourceType.OTHER,
            source_name="测试来源",
        )
        scheduler.add_config(new_config)
        assert SourceType.OTHER in scheduler.configs
        assert SourceType.OTHER in scheduler.calendars

    @patch("core.services.crawl_scheduler.CrawlOrchestrator")
    def test_get_status(self, mock_orch_cls):
        mock_orch = Mock()
        mock_orch.get_crawl_status.return_value = {}
        mock_orch_cls.return_value = mock_orch

        scheduler = CrawlScheduler()
        status = scheduler.get_status()
        assert "running" in status
        assert "sources" in status
        assert len(status["sources"]) > 0

        for source in status["sources"]:
            assert "source_type" in source
            assert "enabled" in source
            assert "should_run" in source
            assert "run_reason" in source

    def test_check_source_should_run_during_trading(self):
        scheduler = CrawlScheduler()

        with patch.object(scheduler.calendars[SourceType.CLS], "should_run_now") as mock_should:
            mock_should.return_value = (True, "在交易时段")
            should_run, reason = scheduler.check_source_should_run(SourceType.CLS)
            assert should_run is True
            assert "交易时段" in reason

    def test_check_source_should_run_disabled(self):
        scheduler = CrawlScheduler()
        scheduler.configs[SourceType.CLS].enabled = False

        should_run, reason = scheduler.check_source_should_run(SourceType.CLS)
        assert should_run is False
        assert "已禁用" in reason

    def test_check_source_should_run_no_config(self):
        scheduler = CrawlScheduler()
        should_run, reason = scheduler.check_source_should_run(SourceType.OTHER)
        assert should_run is False
        assert "无配置" in reason

    @patch("core.services.crawl_scheduler.APSCHEDULER_AVAILABLE", False)
    def test_start_without_apscheduler(self):
        scheduler = CrawlScheduler()
        scheduler.start()
        assert scheduler.running is False

    @patch("core.services.crawl_scheduler.APSCHEDULER_AVAILABLE", True)
    def test_start_stop(self):
        scheduler = CrawlScheduler()

        mock_scheduler = Mock()
        scheduler.scheduler = mock_scheduler

        scheduler.running = True
        assert scheduler.running is True

        scheduler.stop()
        assert scheduler.running is False

    @patch("core.services.crawl_scheduler.CrawlOrchestrator")
    def test_trigger_crawl(self, mock_orch_cls):
        mock_result = Mock()
        mock_result.success_count = 1
        mock_result.skipped_count = 0
        mock_result.failure_count = 0
        mock_result.saved_doc_ids = ["test_123"]

        mock_orch = Mock()
        mock_orch.crawl_source.return_value = mock_result
        mock_orch_cls.return_value = mock_orch

        scheduler = CrawlScheduler()
        result = scheduler.trigger_crawl(SourceType.CLS)
        assert result is not None
        assert result["success_count"] == 1
        mock_orch.crawl_source.assert_called_once()

    def test_trigger_crawl_no_config(self):
        scheduler = CrawlScheduler()
        result = scheduler.trigger_crawl(SourceType.OTHER)
        assert result is None

    @patch("core.services.crawl_scheduler.CrawlOrchestrator")
    def test_trigger_backfill(self, mock_orch_cls):
        mock_result = Mock()
        mock_result.success_count = 2
        mock_result.skipped_count = 1
        mock_result.failure_count = 0

        mock_orch = Mock()
        mock_orch.backfill_source.return_value = mock_result
        mock_orch_cls.return_value = mock_orch

        scheduler = CrawlScheduler()
        result = scheduler.trigger_backfill(SourceType.CLS)
        assert result is not None
        assert result["success_count"] == 2
        mock_orch.backfill_source.assert_called_once()


class TestBuildSchedulerStatus:
    """测试 build_scheduler_status 独立函数"""

    @patch("core.services.crawl_scheduler.CrawlOrchestrator")
    def test_returns_expected_structure(self, mock_orch_cls):
        mock_orch = Mock()
        mock_orch.get_crawl_status.return_value = {}
        mock_orch_cls.return_value = mock_orch

        status = build_scheduler_status()
        assert "running" in status
        assert status["running"] is True
        assert "current_time" in status
        assert "sources" in status
        assert (
            len(status["sources"]) == 6
        )  # CLS, CNStock, CNStock Flash, ZQ Reports, WeChat, Transcript

        for source in status["sources"]:
            assert "source_type" in source
            assert "enabled" in source
            assert "interval_minutes" in source
            assert "crawl_status" in source


class TestGetSchedulerProcessStatus:
    """测试 get_scheduler_process_status"""

    def test_no_pid_file(self, tmp_path):
        pid_file = tmp_path / "nonexistent.pid"
        result = get_scheduler_process_status(str(pid_file))
        assert result["alive"] is False
        assert result["pid"] is None

    def test_invalid_pid_file(self, tmp_path):
        pid_file = tmp_path / "invalid.pid"
        pid_file.write_text("not_a_pid")
        result = get_scheduler_process_status(str(pid_file))
        assert result["alive"] is False

    def test_stale_pid_file(self, tmp_path):
        pid_file = tmp_path / "stale.pid"
        pid_file.write_text("99999")
        result = get_scheduler_process_status(str(pid_file))
        assert result["alive"] is False
