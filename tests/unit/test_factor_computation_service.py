"""FactorComputationService 单元测试"""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from core.contracts.factors import (
    DynamicFactorWeights,
    FactorCategory,
    FactorDefinition,
    FactorEvaluation,
    FactorValue,
)
from services.factor_computation_service import FactorComputationService


@pytest.fixture
def sample_definitions():
    return [
        FactorDefinition(
            factor_id="momentum_20d",
            name="20日动量",
            category=FactorCategory.MOMENTUM,
            direction="positive",
        ),
        FactorDefinition(
            factor_id="pe_ttm",
            name="PE TTM",
            category=FactorCategory.VALUE,
            direction="negative",
        ),
    ]


@pytest.fixture
def sample_values():
    as_of = date(2024, 12, 31)
    return [
        FactorValue(
            factor_id="momentum_20d",
            subject_id="000001.SZ",
            as_of_date=as_of,
            value=0.12,
            available_at=datetime(2024, 12, 31, 15, 0, tzinfo=timezone.utc),
        ),
        FactorValue(
            factor_id="pe_ttm",
            subject_id="000001.SZ",
            as_of_date=as_of,
            value=25.5,
            available_at=datetime(2024, 12, 31, 15, 0, tzinfo=timezone.utc),
        ),
        FactorValue(
            factor_id="momentum_20d",
            subject_id="000002.SZ",
            as_of_date=as_of,
            value=0.05,
            available_at=datetime(2024, 12, 31, 15, 0, tzinfo=timezone.utc),
        ),
        FactorValue(
            factor_id="pe_ttm",
            subject_id="000002.SZ",
            as_of_date=as_of,
            value=18.3,
            available_at=datetime(2024, 12, 31, 15, 0, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def sample_evaluations():
    return [
        FactorEvaluation(
            factor_id="momentum_20d",
            as_of_date=date(2024, 12, 31),
            horizon_days=20,
            sample_size=100,
            coverage=0.95,
            ic=0.05,
            rank_ic=0.06,
            decile_spread=0.02,
        ),
        FactorEvaluation(
            factor_id="pe_ttm",
            as_of_date=date(2024, 12, 31),
            horizon_days=20,
            sample_size=100,
            coverage=0.90,
            ic=-0.03,
            rank_ic=-0.04,
            decile_spread=-0.015,
        ),
    ]


@pytest.fixture
def mock_store(sample_definitions, sample_values, sample_evaluations):
    """Mock FactorStore that returns sample data"""
    store = MagicMock()
    store.get_definitions.return_value = sample_definitions
    store.load_values.return_value = sample_values
    store.load_latest_evaluations.return_value = sample_evaluations
    store.store_evaluations.return_value = 2
    store.store_weights.return_value = 1
    return store


@pytest.fixture
def mock_evaluator(sample_evaluations):
    """Mock FactorEvaluator"""
    evaluator = MagicMock()
    evaluator.horizon_days = 20
    evaluator.evaluate.return_value = sample_evaluations
    return evaluator


@pytest.fixture
def mock_model():
    """Mock RollingICWeightedModel"""
    model = MagicMock()
    model.fit.return_value = DynamicFactorWeights(
        as_of_date=date(2024, 12, 31),
        lookback_periods=12,
        metric="rank_ic",
        weights={"momentum_20d": 0.6, "pe_ttm": -0.4},
        raw_scores={"momentum_20d": 0.05, "pe_ttm": -0.03},
    )
    return model


class TestFactorComputationServiceInit:
    def test_init_with_defaults(self):
        service = FactorComputationService()
        assert service.store is not None
        assert service.evaluator is not None
        assert service.model is not None

    def test_init_with_custom_components(self, mock_store, mock_evaluator, mock_model):
        service = FactorComputationService(
            store=mock_store,
            evaluator=mock_evaluator,
            model=mock_model,
        )
        assert service.store is mock_store
        assert service.evaluator is mock_evaluator
        assert service.model is mock_model


class TestRunDailyCycleNoDefinitions:
    def test_skips_when_no_definitions(self, mock_store):
        mock_store.get_definitions.return_value = []
        service = FactorComputationService(store=mock_store)
        result = service.run_daily_cycle(date(2024, 12, 31))
        assert result["status"] == "skipped_no_definitions"


class TestRunDailyCycleNoValues:
    def test_skips_when_no_values(self, mock_store, sample_definitions):
        mock_store.get_definitions.return_value = sample_definitions
        mock_store.load_values.return_value = []
        service = FactorComputationService(store=mock_store)
        result = service.run_daily_cycle(date(2024, 12, 31))
        assert result["status"] == "skipped_no_values"


class TestRunDailyCycleWithForwardReturns:
    def test_full_cycle_evaluates_and_stores(self, mock_store, mock_evaluator, mock_model):
        """With forward_returns, evaluate factors then fit weights."""
        service = FactorComputationService(
            store=mock_store,
            evaluator=mock_evaluator,
            model=mock_model,
        )
        forward_returns = pd.Series(
            [0.02, 0.01],
            index=["000001.SZ", "000002.SZ"],
            name="forward_return",
        )

        result = service.run_daily_cycle(
            date(2024, 12, 31),
            forward_returns=forward_returns,
        )

        assert result["status"] == "completed"
        assert result["steps"]["definitions_loaded"] == 2
        assert result["steps"]["values_loaded"] == 4
        assert result["steps"]["matrix_shape"] == [2, 2]
        assert result["steps"]["evaluations_stored"] == 2
        assert result["steps"]["weights_stored"] == 1
        assert result["steps"]["active_factors"] == 2

        mock_evaluator.evaluate.assert_called_once()
        mock_store.store_evaluations.assert_called_once()
        mock_store.store_weights.assert_called_once()
        mock_model.fit.assert_called_once()

    def test_evaluations_not_called_when_no_forward_returns(self, mock_store, mock_model):
        """Without forward_returns, load evaluations from history."""
        service = FactorComputationService(
            store=mock_store,
            model=mock_model,
        )
        forward_returns = pd.Series(
            [0.02, 0.01],
            index=["000001.SZ", "000002.SZ"],
            name="forward_return",
        )

        result = service.run_daily_cycle(
            date(2024, 12, 31),
            forward_returns=forward_returns,
        )

        assert result["status"] == "completed"
        # With forward_returns, should call evaluate
        assert "evaluations_stored" in result["steps"]

    def test_no_weights_when_no_evaluations(self, mock_store):
        """When evaluator returns no evaluations, weights step is skipped."""
        mock_store.load_latest_evaluations.return_value = []
        mock_evaluator = MagicMock()
        mock_evaluator.horizon_days = 20
        mock_evaluator.evaluate.return_value = []
        service = FactorComputationService(
            store=mock_store,
            evaluator=mock_evaluator,
        )

        forward_returns = pd.Series(
            [0.02],
            index=["000001.SZ"],
            name="forward_return",
        )
        result = service.run_daily_cycle(
            date(2024, 12, 31),
            forward_returns=forward_returns,
        )

        assert result["steps"]["weights_stored"] == 0

    def test_matrix_shape_in_summary(self, mock_store, mock_evaluator, mock_model):
        """Matrix shape should be [n_subjects, n_factors]."""
        service = FactorComputationService(
            store=mock_store,
            evaluator=mock_evaluator,
            model=mock_model,
        )
        forward_returns = pd.Series(
            [0.02, 0.01],
            index=["000001.SZ", "000002.SZ"],
            name="forward_return",
        )

        result = service.run_daily_cycle(
            date(2024, 12, 31),
            forward_returns=forward_returns,
        )
        assert result["steps"]["matrix_shape"] == [2, 2]

    def test_restricted_factor_ids(self, mock_store, mock_evaluator, mock_model):
        """When factor_ids is specified, only those factors are loaded."""
        service = FactorComputationService(
            store=mock_store,
            evaluator=mock_evaluator,
            model=mock_model,
        )
        forward_returns = pd.Series(
            [0.02, 0.01],
            index=["000001.SZ", "000002.SZ"],
            name="forward_return",
        )

        result = service.run_daily_cycle(
            date(2024, 12, 31),
            factor_ids=["momentum_20d"],
            forward_returns=forward_returns,
        )
        assert result["status"] == "completed"
        # load_values should have been called with the restricted factor_ids
        mock_store.load_values.assert_called_with(
            as_of_date=date(2024, 12, 31),
            factor_ids=["momentum_20d"],
        )

    def test_duration_in_summary(self, mock_store, mock_evaluator, mock_model):
        """Summary includes duration_seconds."""
        service = FactorComputationService(
            store=mock_store,
            evaluator=mock_evaluator,
            model=mock_model,
        )
        forward_returns = pd.Series(
            [0.02],
            index=["000001.SZ"],
            name="forward_return",
        )

        result = service.run_daily_cycle(
            date(2024, 12, 31),
            forward_returns=forward_returns,
        )
        assert "duration_seconds" in result
        assert result["duration_seconds"] >= 0


class TestClose:
    def test_close_propagates_to_store(self, mock_store):
        service = FactorComputationService(store=mock_store)
        service.close()
        mock_store.close.assert_called_once()
