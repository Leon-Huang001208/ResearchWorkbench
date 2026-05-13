"""
测试 Crawl State Repository
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from data_layer.repositories.models import CrawlStateV1DB


@pytest.fixture
def sample_crawl_state():
    """样例爬虫状态"""
    return CrawlStateV1DB(
        state_id="state_cls",
        source_type="cls",
        source_name="财联社",
        watermark_id="news_12345",
        watermark_timestamp=datetime.utcnow() - timedelta(hours=1),
        watermark_metadata={},
        dedupe_key=None,
        dedupe_count=42,
        total_fetched=1250,
        total_skipped=42,
        total_failed=3,
        crawl_config={"rate_limit": 10},
        crawl_mode="incremental",
        last_run_id="run_123",
        last_run_start=datetime.utcnow() - timedelta(hours=1),
        last_run_end=datetime.utcnow() - timedelta(hours=1),
        is_paused=False,
        pause_reason=None,
        created_at=datetime.utcnow() - timedelta(days=1),
        updated_at=datetime.utcnow() - timedelta(hours=1),
        extra={},
    )


class TestCrawlStateRepository:
    """测试爬虫状态仓储"""

    @patch("data_layer.repositories.crawl_state_repository.get_crawl_state")
    def test_get_crawl_state(self, mock_get_state, db_session, sample_crawl_state):
        """测试获取爬虫状态"""
        # Arrange
        mock_get_state.return_value = sample_crawl_state

        # Act
        from data_layer.repositories import crawl_state_repository
        result = crawl_state_repository.get_crawl_state(db_session, "cls")

        # Assert
        assert result is not None
        assert result.source_type == "cls"

    @patch("data_layer.repositories.crawl_state_repository.get_all_crawl_states")
    def test_get_all_crawl_states(self, mock_get_all, db_session):
        """测试获取所有状态"""
        # Arrange
        from data_layer.repositories.models import CrawlStateV1DB
        states = [
            CrawlStateV1DB(state_id="state_cls", source_type="cls"),
            CrawlStateV1DB(state_id="state_cnstock", source_type="cnstock"),
        ]
        mock_get_all.return_value = states

        # Act
        from data_layer.repositories import crawl_state_repository
        result = crawl_state_repository.get_all_crawl_states(db_session)

        # Assert
        assert len(result) == 2

    @patch("data_layer.repositories.crawl_state_repository.pause_crawl")
    def test_pause_crawl(self, mock_pause, db_session, sample_crawl_state):
        """测试暂停爬虫"""
        # Arrange
        sample_crawl_state.is_paused = True
        sample_crawl_state.pause_reason = "Maintenance"
        mock_pause.return_value = sample_crawl_state

        # Act
        from data_layer.repositories import crawl_state_repository
        result = crawl_state_repository.pause_crawl(db_session, "cls", "Maintenance")

        # Assert
        assert result is not None
        assert result.is_paused is True
        assert result.pause_reason == "Maintenance"

    @patch("data_layer.repositories.crawl_state_repository.resume_crawl")
    def test_resume_crawl(self, mock_resume, db_session, sample_crawl_state):
        """测试恢复爬虫"""
        # Arrange
        sample_crawl_state.is_paused = False
        sample_crawl_state.pause_reason = None
        mock_resume.return_value = sample_crawl_state

        # Act
        from data_layer.repositories import crawl_state_repository
        result = crawl_state_repository.resume_crawl(db_session, "cls")

        # Assert
        assert result is not None
        assert result.is_paused is False
        assert result.pause_reason is None

    @patch("data_layer.repositories.crawl_state_repository.update_watermark")
    def test_update_watermark(self, mock_update, db_session, sample_crawl_state):
        """测试更新水位线"""
        # Arrange
        new_watermark_id = "news_67890"
        new_timestamp = datetime.utcnow()
        sample_crawl_state.watermark_id = new_watermark_id
        sample_crawl_state.watermark_timestamp = new_timestamp
        mock_update.return_value = sample_crawl_state

        # Act
        from data_layer.repositories import crawl_state_repository
        result = crawl_state_repository.update_watermark(
            db_session, "cls", new_watermark_id, new_timestamp
        )

        # Assert
        assert result is not None
        assert result.watermark_id == new_watermark_id
        assert result.watermark_timestamp == new_timestamp

    @patch("data_layer.repositories.crawl_state_repository.increment_crawl_stats")
    def test_increment_crawl_stats(self, mock_increment, db_session, sample_crawl_state):
        """测试递增统计"""
        # Arrange
        sample_crawl_state.total_fetched = 1251
        sample_crawl_state.total_skipped = 43
        sample_crawl_state.total_failed = 4
        mock_increment.return_value = sample_crawl_state

        # Act
        from data_layer.repositories import crawl_state_repository
        result = crawl_state_repository.increment_crawl_stats(
            db_session, "cls", fetched=1, skipped=1, failed=1
        )

        # Assert
        assert result is not None
        assert result.total_fetched == 1251
        assert result.total_skipped == 43
        assert result.total_failed == 4

    @patch("data_layer.repositories.crawl_state_repository.reset_crawl_state")
    def test_reset_crawl_state(self, mock_reset, db_session, sample_crawl_state):
        """测试重置状态"""
        # Arrange
        sample_crawl_state.watermark_id = None
        sample_crawl_state.total_fetched = 0
        sample_crawl_state.total_skipped = 0
        sample_crawl_state.total_failed = 0
        mock_reset.return_value = sample_crawl_state

        # Act
        from data_layer.repositories import crawl_state_repository
        result = crawl_state_repository.reset_crawl_state(db_session, "cls")

        # Assert
        assert result is not None
        assert result.watermark_id is None
        assert result.total_fetched == 0
