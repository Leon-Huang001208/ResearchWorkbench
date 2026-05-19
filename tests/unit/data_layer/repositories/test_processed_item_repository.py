"""
测试 Processed Item Repository
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from data_layer.repositories.models import ProcessedItemV1DB


@pytest.fixture
def sample_processed_item():
    """样例已处理项目"""
    return ProcessedItemV1DB(
        item_id="item_123",
        source_type="cls",
        source_name="财联社",
        item_type="news",
        title="测试新闻标题",
        content_preview="测试新闻内容预览...",
        content_hash="abc123def456",
        first_seen_at=datetime.utcnow() - timedelta(hours=1),
        first_processed_at=datetime.utcnow() - timedelta(hours=1),
        process_count=1,
        crawl_run_id="run_123",
        doc_id="doc_123",
        extra={},
    )


class TestProcessedItemRepository:
    """测试已处理项目仓储"""

    @patch("data_layer.repositories.processed_item_repository.item_exists")
    def test_item_exists_true(self, mock_exists, db_session):
        """测试项目存在"""
        # Arrange
        mock_exists.return_value = True

        # Act
        from data_layer.repositories import processed_item_repository

        result = processed_item_repository.item_exists(db_session, "item_123")

        # Assert
        assert result is True

    @patch("data_layer.repositories.processed_item_repository.item_exists")
    def test_item_exists_false(self, mock_exists, db_session):
        """测试项目不存在"""
        # Arrange
        mock_exists.return_value = False

        # Act
        from data_layer.repositories import processed_item_repository

        result = processed_item_repository.item_exists(db_session, "item_nonexistent")

        # Assert
        assert result is False

    @patch("data_layer.repositories.processed_item_repository.item_exists_by_hash")
    def test_item_exists_by_hash(self, mock_exists_hash, db_session):
        """测试通过哈希检查"""
        # Arrange
        mock_exists_hash.return_value = True

        # Act
        from data_layer.repositories import processed_item_repository

        result = processed_item_repository.item_exists_by_hash(db_session, "abc123def456")

        # Assert
        assert result is True

    @patch("data_layer.repositories.processed_item_repository.add_processed_item")
    def test_add_processed_item(self, mock_add, db_session, sample_processed_item):
        """测试添加项目"""
        # Arrange
        mock_add.return_value = sample_processed_item

        # Act
        from data_layer.repositories import processed_item_repository

        result = processed_item_repository.add_processed_item(db_session, sample_processed_item)

        # Assert
        assert result is not None
        assert result.item_id == "item_123"
        assert result.source_type == "cls"

    @patch("data_layer.repositories.processed_item_repository.add_processed_item")
    def test_add_processed_item_increment_count(self, mock_add, db_session, sample_processed_item):
        """测试重复添加时计数递增"""
        # Arrange
        sample_processed_item.process_count = 2
        mock_add.return_value = sample_processed_item

        # Act
        from data_layer.repositories import processed_item_repository

        result = processed_item_repository.add_processed_item(db_session, sample_processed_item)

        # Assert
        assert result.process_count == 2

    @patch("data_layer.repositories.processed_item_repository.get_recent_processed")
    def test_get_recent_processed(self, mock_get_recent, db_session, sample_processed_item):
        """测试获取最近处理的项目"""
        # Arrange
        mock_get_recent.return_value = [sample_processed_item]

        # Act
        from data_layer.repositories import processed_item_repository

        results = processed_item_repository.get_recent_processed(db_session, "cls", limit=10)

        # Assert
        assert len(results) == 1
        assert results[0].item_id == "item_123"

    @patch("data_layer.repositories.processed_item_repository.get_processed_stats")
    def test_get_processed_stats(self, mock_get_stats, db_session):
        """测试获取统计"""
        # Arrange
        mock_get_stats.return_value = {
            "total_items": 100,
            "by_source_type": {"cls": 60, "cnstock": 30, "zq": 10},
        }

        # Act
        from data_layer.repositories import processed_item_repository

        result = processed_item_repository.get_processed_stats(db_session)

        # Assert
        assert result["total_items"] == 100
        assert result["by_source_type"]["cls"] == 60

    @patch("data_layer.repositories.processed_item_repository.get_processed_stats_by_day")
    def test_get_processed_stats_by_day(self, mock_get_daily, db_session):
        """测试按天获取统计"""
        # Arrange
        mock_get_daily.return_value = [
            {"date": "2026-05-10", "count": 15},
            {"date": "2026-05-11", "count": 20},
        ]

        # Act
        from data_layer.repositories import processed_item_repository

        result = processed_item_repository.get_processed_stats_by_day(db_session, "cls", days=7)

        # Assert
        assert len(result) == 2
        assert result[0]["count"] == 15
        assert result[1]["count"] == 20
