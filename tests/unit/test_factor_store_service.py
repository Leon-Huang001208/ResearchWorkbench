"""FactorStore 服务单元测试"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _mock_row(record: dict):
    """Create a simple object from a dict to simulate an ORM row."""
    return SimpleNamespace(**record)


from core.contracts.factors import (
    DynamicFactorWeights,
    FactorCategory,
    FactorDefinition,
    FactorEvaluation,
    FactorValue,
)
from services.factor_store_service import FactorStore

# ─── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def mock_repo():
    """创建一个 mock FactorRepository"""
    repo = MagicMock()
    repo.get_definitions.return_value = []
    repo.save_definitions.return_value = 3
    repo.save_values.return_value = 100
    repo.save_evaluations.return_value = 5
    repo.save_weights.return_value = 1
    repo.get_values_for_date.return_value = []
    repo.get_evaluations.return_value = []
    repo.get_latest_evaluations.return_value = []
    repo.get_latest_weights.return_value = None
    repo.get_all_categories.return_value = ["value", "momentum"]
    repo.get_available_dates.return_value = [date(2024, 12, 31)]
    repo.get_weights_history.return_value = []
    return repo


@pytest.fixture
def store(mock_repo):
    """创建带 mock repo 的 FactorStore"""
    return FactorStore(repository=mock_repo)


@pytest.fixture
def sample_definitions():
    return [
        FactorDefinition(
            factor_id="pe_ttm",
            name="PE TTM",
            category=FactorCategory.VALUE,
            direction="negative",
            description="Trailing PE ratio",
            version="v1",
            horizon_days=20,
        ),
        FactorDefinition(
            factor_id="roe_ttm",
            name="ROE TTM",
            category=FactorCategory.QUALITY,
            direction="positive",
            description="Return on equity TTM",
            version="v1",
            horizon_days=60,
        ),
        FactorDefinition(
            factor_id="momentum_20d",
            name="20-Day Momentum",
            category=FactorCategory.MOMENTUM,
            direction="positive",
            description="Price momentum 20d",
            version="v1",
            horizon_days=20,
        ),
    ]


@pytest.fixture
def sample_values():
    as_of = date(2024, 12, 31)
    return [
        FactorValue(
            factor_id="pe_ttm",
            subject_id="600519.SH",
            as_of_date=as_of,
            value=25.5,
            source="wind",
        ),
        FactorValue(
            factor_id="pe_ttm",
            subject_id="000858.SZ",
            as_of_date=as_of,
            value=18.2,
            source="wind",
        ),
        FactorValue(
            factor_id="momentum_20d",
            subject_id="600519.SH",
            as_of_date=as_of,
            value=0.05,
            source="wind",
        ),
        FactorValue(
            factor_id="momentum_20d",
            subject_id="000858.SZ",
            as_of_date=as_of,
            value=-0.03,
            source="wind",
        ),
    ]


@pytest.fixture
def sample_evaluations():
    return [
        FactorEvaluation(
            factor_id="pe_ttm",
            as_of_date=date(2024, 12, 31),
            horizon_days=20,
            sample_size=100,
            coverage=0.95,
            ic=0.05,
            rank_ic=0.06,
            decile_spread=0.02,
        ),
        FactorEvaluation(
            factor_id="momentum_20d",
            as_of_date=date(2024, 12, 31),
            horizon_days=20,
            sample_size=100,
            coverage=0.90,
            ic=0.08,
            rank_ic=0.10,
            decile_spread=0.04,
        ),
    ]


@pytest.fixture
def sample_weights():
    return DynamicFactorWeights(
        as_of_date=date(2024, 12, 31),
        lookback_periods=12,
        metric="rank_ic",
        weights={"pe_ttm": -0.4, "momentum_20d": 0.6},
        raw_scores={"pe_ttm": -0.03, "momentum_20d": 0.05},
    )


# ─── Factor Definitions ───────────────────────────────────


class TestFactorDefinitions:
    def test_register_definitions_returns_count(self, store, sample_definitions, mock_repo):
        result = store.register_definitions(sample_definitions)
        assert result == 3
        mock_repo.save_definitions.assert_called_once()

    def test_register_empty_list_returns_zero(self, store, mock_repo):
        result = store.register_definitions([])
        assert result == 0
        mock_repo.save_definitions.assert_not_called()

    def test_get_definitions_calls_repo(self, store, mock_repo):
        store.get_definitions(factor_ids=["pe_ttm"])
        mock_repo.get_definitions.assert_called_once_with(factor_ids=["pe_ttm"], category=None)

    def test_get_definitions_with_category(self, store, mock_repo):
        store.get_definitions(category="value")
        mock_repo.get_definitions.assert_called_once_with(factor_ids=None, category="value")

    def test_get_all_categories(self, store, mock_repo):
        cats = store.get_all_categories()
        assert cats == ["value", "momentum"]
        mock_repo.get_all_categories.assert_called_once()


# ─── Factor Values ────────────────────────────────────────


class TestFactorValues:
    def test_store_values_returns_count(self, store, sample_values, mock_repo):
        result = store.store_values(sample_values)
        assert result == 100
        mock_repo.save_values.assert_called_once()

    def test_store_empty_values_returns_zero(self, store, mock_repo):
        result = store.store_values([])
        assert result == 0
        mock_repo.save_values.assert_not_called()

    def test_load_values_for_date(self, store, mock_repo):
        as_of = date(2024, 12, 31)
        store.load_values(as_of_date=as_of, factor_ids=["pe_ttm"])
        mock_repo.get_values_for_date.assert_called_once_with(
            as_of_date=as_of, factor_ids=["pe_ttm"]
        )

    def test_load_values_range(self, store, mock_repo):
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        store.load_values_range(
            factor_ids=["pe_ttm"],
            start_date=start,
            end_date=end,
        )
        mock_repo.get_values.assert_called_once()

    def test_get_available_dates(self, store, mock_repo):
        dates = store.get_available_dates()
        assert dates == [date(2024, 12, 31)]
        mock_repo.get_available_dates.assert_called_once()


# ─── Factor Evaluations ───────────────────────────────────


class TestFactorEvaluations:
    def test_store_evaluations_returns_count(self, store, sample_evaluations, mock_repo):
        result = store.store_evaluations(sample_evaluations)
        assert result == 5
        mock_repo.save_evaluations.assert_called_once()

    def test_store_empty_evaluations_returns_zero(self, store, mock_repo):
        result = store.store_evaluations([])
        assert result == 0
        mock_repo.save_evaluations.assert_not_called()

    def test_load_evaluations(self, store, mock_repo):
        store.load_evaluations(factor_ids=["pe_ttm"])
        mock_repo.get_evaluations.assert_called_once()

    def test_load_latest_evaluations(self, store, mock_repo):
        store.load_latest_evaluations(factor_ids=["pe_ttm"], horizon_days=20)
        mock_repo.get_latest_evaluations.assert_called_once_with(
            factor_ids=["pe_ttm"], horizon_days=20, limit_dates=60
        )


# ─── Dynamic Weights ──────────────────────────────────────


class TestDynamicWeights:
    def test_store_weights_returns_count(self, store, sample_weights, mock_repo):
        result = store.store_weights(sample_weights)
        assert result == 1
        mock_repo.save_weights.assert_called_once()

    def test_load_latest_weights_returns_none_when_empty(self, store, mock_repo):
        mock_repo.get_latest_weights.return_value = None
        result = store.load_latest_weights(metric="rank_ic")
        assert result is None

    def test_load_weights_history(self, store, mock_repo):
        store.load_weights_history(metric="rank_ic", limit=10)
        mock_repo.get_weights_history.assert_called_once_with(metric="rank_ic", limit=10)


# ─── Record ↔ Contract Round-trip ─────────────────────────


class TestRecordContractRoundTrip:
    """验证 ORM record ↔ Pydantic contract 转换的保真性"""

    def test_definition_round_trip(self):
        from services.factor_store_service import _definition_from_row, _definition_to_record

        original = FactorDefinition(
            factor_id="pe_ttm",
            name="PE TTM",
            category=FactorCategory.VALUE,
            direction="negative",
            description="Trailing PE",
            version="v2",
            horizon_days=20,
            refresh_frequency="1d",
            metadata={"source": "wind"},
        )

        record = _definition_to_record(original)
        restored = _definition_from_row(_mock_row(record))

        assert restored.factor_id == original.factor_id
        assert restored.name == original.name
        assert restored.category == original.category
        assert restored.direction == original.direction
        assert restored.description == original.description
        assert restored.version == original.version
        assert restored.horizon_days == original.horizon_days
        assert restored.metadata == original.metadata

    def test_value_round_trip(self):
        from services.factor_store_service import _value_from_row, _value_to_record

        original = FactorValue(
            factor_id="pe_ttm",
            subject_id="600519.SH",
            as_of_date=date(2024, 12, 31),
            value=25.5,
            available_at=datetime(2024, 12, 31, 15, 0),
            source="wind",
            metadata={"adj_type": 2},
        )

        record = _value_to_record(original)
        restored = _value_from_row(_mock_row(record))

        assert restored.factor_id == original.factor_id
        assert restored.subject_id == original.subject_id
        assert restored.as_of_date == original.as_of_date
        assert restored.value == original.value
        assert restored.source == original.source
        assert restored.metadata == original.metadata

    def test_evaluation_round_trip(self):
        from services.factor_store_service import _evaluation_from_row, _evaluation_to_record

        original = FactorEvaluation(
            factor_id="pe_ttm",
            as_of_date=date(2024, 12, 31),
            horizon_days=20,
            sample_size=100,
            coverage=0.95,
            ic=0.05,
            rank_ic=0.06,
            decile_spread=0.02,
            metadata={"window": "rolling_12m"},
        )

        record = _evaluation_to_record(original)
        restored = _evaluation_from_row(_mock_row(record))

        assert restored.factor_id == original.factor_id
        assert restored.as_of_date == original.as_of_date
        assert restored.horizon_days == original.horizon_days
        assert restored.sample_size == original.sample_size
        assert restored.ic == original.ic
        assert restored.rank_ic == original.rank_ic
        assert restored.decile_spread == original.decile_spread

    def test_weights_round_trip(self):
        from services.factor_store_service import _weights_from_row, _weights_to_record

        original = DynamicFactorWeights(
            as_of_date=date(2024, 12, 31),
            lookback_periods=12,
            metric="rank_ic",
            weights={"pe_ttm": -0.4, "momentum_20d": 0.6},
            raw_scores={"pe_ttm": -0.03, "momentum_20d": 0.05},
        )

        record = _weights_to_record(original)
        restored = _weights_from_row(_mock_row(record))

        assert restored.as_of_date == original.as_of_date
        assert restored.lookback_periods == original.lookback_periods
        assert restored.metric == original.metric
        assert restored.weights == original.weights
        assert restored.raw_scores == original.raw_scores


# ─── Integration: End-to-end flow ─────────────────────────


class TestFactorStoreEndToEnd:
    """验证完整的因子研究循环：定义 → 值 → 评估 → 权重"""

    def test_full_research_cycle(
        self, store, sample_definitions, sample_values, sample_evaluations, sample_weights
    ):
        # Step 1: 注册因子定义
        store.register_definitions(sample_definitions)

        # Step 2: 存储因子值
        store.store_values(sample_values)

        # Step 3: 评估因子
        store.store_evaluations(sample_evaluations)

        # Step 4: 拟合并存储权重
        store.store_weights(sample_weights)

        # 验证每个步骤都调用了对应的 repo 方法
        store.repo.save_definitions.assert_called_once()
        store.repo.save_values.assert_called_once()
        store.repo.save_evaluations.assert_called_once()
        store.repo.save_weights.assert_called_once()
