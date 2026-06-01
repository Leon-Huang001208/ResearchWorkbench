"""FactorRepository 单元测试"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from data_layer.repositories.factor_repository import FactorRepository


@pytest.fixture
def mock_session():
    """创建一个 mock SQLAlchemy session"""
    session = MagicMock()
    session.query.return_value = session
    session.filter.return_value = session
    session.order_by.return_value = session
    session.limit.return_value = session
    session.all.return_value = []
    session.first.return_value = None
    session.distinct.return_value = session
    return session


@pytest.fixture
def repo(mock_session):
    """创建带 mock session 的 FactorRepository"""
    return FactorRepository(db=mock_session)


def _mock_upsert(repo):
    """Mock _upsert to return 5 without hitting real SQLAlchemy."""
    repo._upsert = MagicMock(return_value=5)


class TestFactorRepositoryInit:
    def test_init_with_provided_db(self, mock_session):
        repo = FactorRepository(db=mock_session)
        assert repo._db is mock_session

    def test_init_without_db_creates_new_session(self):
        with patch("data_layer.repositories.factor_repository.SessionLocal") as mock_sl:
            mock_sl.return_value = MagicMock()
            repo = FactorRepository()
            assert repo._db is None
            _ = repo.db
            mock_sl.assert_called_once()


class TestSaveDefinitions:
    def test_save_empty_returns_zero(self, repo):
        result = repo.save_definitions([])
        assert result == 0

    def test_save_definitions_delegates_to_upsert(self, repo):
        _mock_upsert(repo)
        records = [
            {
                "factor_id": "pe_ttm",
                "name": "PE TTM",
                "category": "value",
                "direction": "negative",
                "description": "PE TTM",
                "version": "v1",
                "horizon_days": 20,
                "refresh_frequency": "1d",
                "meta": {},
            }
        ]
        result = repo.save_definitions(records)
        assert result == 5
        repo._upsert.assert_called_once()
        call_args = repo._upsert.call_args
        assert call_args[0][1] == records
        assert call_args[0][2] == ["factor_id"]


class TestSaveValues:
    def test_save_empty_returns_zero(self, repo):
        result = repo.save_values([])
        assert result == 0

    def test_save_values_delegates_to_upsert(self, repo):
        _mock_upsert(repo)
        records = [
            {
                "factor_id": "pe_ttm",
                "subject_id": "600519.SH",
                "as_of_date": date(2024, 12, 31),
                "value": 25.5,
                "available_at": datetime(2024, 12, 31, 15, 0),
                "source": "wind",
                "meta": {},
            }
        ]
        result = repo.save_values(records)
        assert result == 5
        repo._upsert.assert_called_once()
        call_args = repo._upsert.call_args
        assert call_args[0][2] == ["factor_id", "subject_id", "as_of_date"]


class TestGetValues:
    def test_get_values_returns_list(self, repo, mock_session):
        mock_session.all.return_value = []
        result = repo.get_values(factor_ids=["pe_ttm"])
        assert result == []

    def test_get_values_for_date(self, repo, mock_session):
        mock_session.all.return_value = []
        result = repo.get_values_for_date(
            as_of_date=date(2024, 12, 31),
            factor_ids=["pe_ttm"],
        )
        assert result == []

    def test_get_available_dates(self, repo, mock_session):
        mock_session.all.return_value = [
            (date(2024, 12, 31),),
            (date(2024, 12, 30),),
        ]
        result = repo.get_available_dates()
        assert result == [date(2024, 12, 31), date(2024, 12, 30)]


class TestSaveEvaluations:
    def test_save_empty_returns_zero(self, repo):
        result = repo.save_evaluations([])
        assert result == 0

    def test_save_evaluations_delegates_to_upsert(self, repo):
        _mock_upsert(repo)
        records = [
            {
                "factor_id": "pe_ttm",
                "as_of_date": date(2024, 12, 31),
                "horizon_days": 20,
                "sample_size": 100,
                "coverage": 0.95,
                "ic": 0.05,
                "rank_ic": 0.06,
                "decile_spread": 0.02,
                "meta": {},
            }
        ]
        result = repo.save_evaluations(records)
        assert result == 5
        repo._upsert.assert_called_once()
        call_args = repo._upsert.call_args
        assert call_args[0][2] == ["factor_id", "as_of_date", "horizon_days"]


class TestSaveWeights:
    @patch("data_layer.repositories.factor_repository.pg_insert")
    def test_save_weights_success(self, mock_pg_insert, repo, mock_session):
        """save_weights has its own implementation"""
        mock_stmt = MagicMock()
        mock_pg_insert.return_value.values.return_value = mock_stmt
        mock_stmt.on_conflict_do_update.return_value = mock_stmt
        mock_session.execute.return_value = MagicMock()

        repo._upsert = MagicMock()
        record = {
            "as_of_date": date(2024, 12, 31),
            "lookback_periods": 12,
            "metric": "rank_ic",
            "weights": {"pe_ttm": -0.4},
            "raw_scores": {"pe_ttm": -0.03},
        }
        result = repo.save_weights(record)
        assert result == 1
        mock_session.commit.assert_called_once()
        repo._upsert.assert_not_called()

    @patch("data_layer.repositories.factor_repository.pg_insert")
    def test_save_weights_rollback_on_error(self, mock_pg_insert, repo, mock_session):
        mock_stmt = MagicMock()
        mock_pg_insert.return_value.values.return_value = mock_stmt
        mock_stmt.on_conflict_do_nothing.return_value = mock_stmt
        mock_session.execute.side_effect = RuntimeError("DB error")

        repo._upsert = MagicMock()
        with pytest.raises(RuntimeError):
            repo.save_weights(
                {
                    "as_of_date": date(2024, 12, 31),
                    "metric": "rank_ic",
                }
            )
        mock_session.rollback.assert_called_once()


class TestGetWeights:
    def test_get_latest_weights_returns_none_when_empty(self, repo, mock_session):
        mock_session.first.return_value = None
        result = repo.get_latest_weights(metric="rank_ic")
        assert result is None

    def test_get_weights_history_empty(self, repo, mock_session):
        mock_session.all.return_value = []
        result = repo.get_weights_history(metric="rank_ic")
        assert result == []


class TestClose:
    def test_close_clears_session(self, repo, mock_session):
        repo.close()
        mock_session.close.assert_called_once()
        assert repo._db is None
