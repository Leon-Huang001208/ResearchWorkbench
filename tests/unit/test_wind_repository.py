"""Wind 仓储层单元测试"""

from unittest.mock import MagicMock, patch

import pytest

from data_layer.repositories.wind_repository import WindRepository


@pytest.fixture
def mock_db():
    """创建 mock 数据库会话"""
    session = MagicMock()
    return session


class TestWindRepositoryEmptyRecords:
    """空记录测试"""

    def test_save_consensus_estimates_empty(self, mock_db):
        repo = WindRepository(db=mock_db)
        count = repo.save_consensus_estimates([])
        assert count == 0
        mock_db.execute.assert_not_called()

    def test_save_margin_trading_empty(self, mock_db):
        repo = WindRepository(db=mock_db)
        count = repo.save_margin_trading([])
        assert count == 0

    def test_save_block_trades_empty(self, mock_db):
        repo = WindRepository(db=mock_db)
        count = repo.save_block_trades([])
        assert count == 0

    def test_save_daily_bars_empty(self, mock_db):
        repo = WindRepository(db=mock_db)
        count = repo.save_daily_bars([])
        assert count == 0


class TestWindRepositoryUpsert:
    """Upsert 执行测试"""

    @patch("data_layer.repositories.wind_repository.pg_insert")
    def test_save_consensus_estimates_calls_execute(self, mock_pg_insert, mock_db):
        """保存记录时调用 execute 和 commit"""
        # Mock the SQLAlchemy insert chain
        mock_insert_stmt = MagicMock()
        mock_conflict_stmt = MagicMock()
        mock_pg_insert.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.on_conflict_do_nothing.return_value = mock_conflict_stmt

        repo = WindRepository(db=mock_db)
        repo.save_consensus_estimates([{"symbol": "600519.SH", "trade_date": "2025-06-01"}])

        assert mock_db.execute.called
        assert mock_db.commit.called

    @patch("data_layer.repositories.wind_repository.pg_insert")
    def test_upsert_rollback_on_error(self, mock_pg_insert, mock_db):
        """数据库错误时回滚"""
        mock_db.execute.side_effect = RuntimeError("DB error")
        mock_insert_stmt = MagicMock()
        mock_pg_insert.return_value = mock_insert_stmt
        mock_insert_stmt.values.return_value = mock_insert_stmt
        mock_insert_stmt.on_conflict_do_nothing.return_value = mock_insert_stmt

        repo = WindRepository(db=mock_db)
        with pytest.raises(RuntimeError):
            repo.save_consensus_estimates([{"symbol": "600519.SH"}])
        assert mock_db.rollback.called

    def test_close_cleans_up(self, mock_db):
        """close 关闭数据库会话"""
        repo = WindRepository(db=mock_db)
        repo.close()
        mock_db.close.assert_called_once()


class TestWindRepositoryQuery:
    """查询方法测试"""

    def test_get_consensus_estimates_basic(self, mock_db):
        repo = WindRepository(db=mock_db)
        repo.get_consensus_estimates("600519.SH")
        assert mock_db.query.called

    def test_get_consensus_estimates_with_date_range(self, mock_db):
        repo = WindRepository(db=mock_db)
        repo.get_consensus_estimates(
            "600519.SH", start_date="2025-01-01", end_date="2025-06-01", limit=10
        )
        assert mock_db.query.called

    def test_get_margin_trading_basic(self, mock_db):
        repo = WindRepository(db=mock_db)
        repo.get_margin_trading("600519.SH")
        assert mock_db.query.called

    def test_get_block_trades_basic(self, mock_db):
        repo = WindRepository(db=mock_db)
        repo.get_block_trades("600519.SH")
        assert mock_db.query.called

    def test_get_daily_bars_basic(self, mock_db):
        repo = WindRepository(db=mock_db)
        repo.get_daily_bars("600519.SH")
        assert mock_db.query.called


class TestWindRepositoryInit:
    """初始化测试"""

    def test_default_init(self):
        repo = WindRepository()
        assert repo._db is None

    def test_init_with_db(self, mock_db):
        repo = WindRepository(db=mock_db)
        assert repo.db is mock_db
