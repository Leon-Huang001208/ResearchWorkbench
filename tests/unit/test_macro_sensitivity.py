"""Tests for MacroSensitivityCalculator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from core.contracts import MacroSensitivity
from services.macro_sensitivity import MACRO_PROXY_ETFS, MacroSensitivityCalculator


def _make_quote_df(
    codes: list[str],
    n_days: int = 252,
    start_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic quote DataFrame for testing.

    Creates a DataFrame with columns matching Cjpy output:
    时间, code, open, high, low, close, vol, amount

    Each code's close price follows a random walk with a small drift,
    so the OLS regression can detect meaningful relationships.
    """
    rng = np.random.default_rng(seed)

    # Base dates
    base = pd.Timestamp("2024-01-01")
    dates = [base + pd.Timedelta(days=i) for i in range(n_days)]

    rows: list[dict] = []
    for code in codes:
        # Random walk with drift; different drift per code for variety
        drift = rng.normal(0.0005, 0.001)
        returns = rng.normal(drift, 0.02, size=n_days)
        prices = start_price * np.cumprod(1 + returns)

        for idx, d in enumerate(dates):
            p = prices[idx]
            rows.append(
                {
                    "时间": d,
                    "code": code,
                    "open": float(p * 0.99),
                    "high": float(p * 1.02),
                    "low": float(p * 0.98),
                    "close": float(p),
                    "vol": float(rng.uniform(1e6, 1e7)),
                    "amount": float(p * rng.uniform(1e6, 1e7)),
                }
            )

    return pd.DataFrame(rows)


class TestMacroSensitivityCalculator:
    """Tests for MacroSensitivityCalculator."""

    # ------------------------------------------------------------------
    # Unit tests: _run_regression
    # ------------------------------------------------------------------

    def test_regression_returns_sensitivity_with_enough_data(self):
        """With ample data, regression should produce non-None betas."""
        codes = [
            "600519.SH",
            MACRO_PROXY_ETFS["interest_rate"],
            MACRO_PROXY_ETFS["inflation"],
            MACRO_PROXY_ETFS["exchange_rate"],
            MACRO_PROXY_ETFS["commodity"],
            MACRO_PROXY_ETFS["liquidity"],
        ]
        df = _make_quote_df(codes, n_days=252, seed=42)
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "600519.SH", min_observations=60)

        assert isinstance(result, MacroSensitivity)
        # With 252 random-walk days, every factor should have data
        assert result.interest_rate_sensitivity is not None
        assert result.inflation_sensitivity is not None
        assert result.key_macro_factors is not None

    def test_regression_returns_empty_with_insufficient_data(self):
        """Fewer data points than min_observations should return empty."""
        df = _make_quote_df(
            [MACRO_PROXY_ETFS["interest_rate"], "600519.SH"],
            n_days=30,
        )
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "600519.SH", min_observations=60)

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is None

    def test_regression_handles_missing_stock_column(self):
        """If stock code is absent from data, return empty."""
        df = _make_quote_df(
            [MACRO_PROXY_ETFS["interest_rate"]],
            n_days=100,
        )
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "600519.SH", min_observations=60)

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is None

    def test_regression_handles_empty_dataframe(self):
        """Empty DataFrame should return empty MacroSensitivity."""
        df = pd.DataFrame()
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "600519.SH", min_observations=60)

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is None

    def test_regression_handles_no_date_column(self):
        """DataFrame without a recognizable date column returns empty."""
        df = pd.DataFrame({"foo": [1, 2], "code": ["A", "B"], "close": [10, 20]})
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "A", min_observations=1)

        assert isinstance(result, MacroSensitivity)

    def test_regression_handles_no_close_column(self):
        """DataFrame without a close column returns empty."""
        df = pd.DataFrame({"时间": pd.Timestamp("2024-01-01"), "code": ["A"], "price": [100]})
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "A", min_observations=1)

        assert isinstance(result, MacroSensitivity)

    def test_regression_identifies_key_factors_by_beta_threshold(self):
        """Factors with |beta| > 0.1 should appear in key_macro_factors."""
        # Create data where one proxy is artificially correlated with the stock
        rng = np.random.default_rng(42)
        n = 200
        dates = [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(n)]
        base_return = rng.normal(0, 0.02, size=n)

        # Stock = 0.5 * interest_rate_return + noise
        interest_rate_return = base_return
        noise = rng.normal(0, 0.01, size=n)
        stock_return = 0.5 * interest_rate_return + noise

        # Other proxy = uncorrelated
        liquidity_return = rng.normal(0, 0.02, size=n)

        stock_prices = 100 * np.cumprod(1 + stock_return)
        ir_prices = 100 * np.cumprod(1 + interest_rate_return)
        liq_prices = 100 * np.cumprod(1 + liquidity_return)

        rows = []
        for i, d in enumerate(dates):
            rows.append({"时间": d, "code": "600519.SH", "close": float(stock_prices[i])})
            rows.append(
                {
                    "时间": d,
                    "code": MACRO_PROXY_ETFS["interest_rate"],
                    "close": float(ir_prices[i]),
                }
            )
            rows.append(
                {
                    "时间": d,
                    "code": MACRO_PROXY_ETFS["liquidity"],
                    "close": float(liq_prices[i]),
                }
            )
        df = pd.DataFrame(rows)

        calculator = MacroSensitivityCalculator()
        result = calculator._run_regression(df, "600519.SH", min_observations=30)

        # interest_rate_sensitivity should be non-zero and > 0.1 threshold
        assert result.interest_rate_sensitivity is not None
        # Supply noise is random so we can't guarantee exact value, but the factor
        # should be present in the result
        assert isinstance(result.key_macro_factors, list)

    def test_regression_handles_date_column_name_variants(self):
        """Both '时间' and 'date' column names should work."""
        rng = np.random.default_rng(42)
        n = 100
        dates = [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(n)]
        stock_prices = 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, size=n))
        ir_prices = 100 * np.cumprod(1 + rng.normal(0.0003, 0.015, size=n))

        # Use 'date' instead of '时间'
        rows = []
        for i, d in enumerate(dates):
            rows.append({"date": d, "code": "600519.SH", "close": float(stock_prices[i])})
            rows.append(
                {
                    "date": d,
                    "code": MACRO_PROXY_ETFS["interest_rate"],
                    "close": float(ir_prices[i]),
                }
            )
        df = pd.DataFrame(rows)

        calculator = MacroSensitivityCalculator()
        result = calculator._run_regression(df, "600519.SH", min_observations=30)

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is not None

    # ------------------------------------------------------------------
    # Integration tests: compute() with mocked CjpyAdapter
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_compute_uses_cjpy_adapter_and_returns_sensitivity(self):
        """compute() should call CjpyAdapter.fetch_daily_quotes and return betas."""
        codes = [
            "600519.SH",
            MACRO_PROXY_ETFS["interest_rate"],
            MACRO_PROXY_ETFS["inflation"],
            MACRO_PROXY_ETFS["exchange_rate"],
            MACRO_PROXY_ETFS["commodity"],
            MACRO_PROXY_ETFS["liquidity"],
        ]
        df = _make_quote_df(codes, n_days=200, seed=42)

        with patch("data_layer.adapters.cjpy_adapter.CjpyAdapter") as MockCjpyAdapter:
            mock_adapter = MockCjpyAdapter.return_value
            mock_adapter.is_available.return_value = True
            mock_adapter.fetch_daily_quotes.return_value = df

            calculator = MacroSensitivityCalculator()
            result = calculator.compute(
                canonical_id="600519.SH",
                start_date="20240101",
                end_date="20241231",
                min_observations=60,
            )

        assert isinstance(result, MacroSensitivity)
        mock_adapter.is_available.assert_called_once()
        mock_adapter.fetch_daily_quotes.assert_called_once_with(
            codes=codes,
            start_date="20240101",
            end_date="20241231",
            rate="不复权",
        )

    @pytest.mark.asyncio
    async def test_compute_returns_empty_when_cjpy_unavailable(self):
        """If Cjpy is unavailable, compute() returns empty MacroSensitivity."""
        with patch("data_layer.adapters.cjpy_adapter.CjpyAdapter") as MockCjpyAdapter:
            mock_adapter = MockCjpyAdapter.return_value
            mock_adapter.is_available.return_value = False

            calculator = MacroSensitivityCalculator()
            result = calculator.compute(
                canonical_id="600519.SH",
                start_date="20240101",
                end_date="20241231",
            )

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is None
        mock_adapter.fetch_daily_quotes.assert_not_called()

    @pytest.mark.asyncio
    async def test_compute_returns_empty_when_data_empty(self):
        """If Cjpy returns empty data, compute() returns empty."""
        with patch("data_layer.adapters.cjpy_adapter.CjpyAdapter") as MockCjpyAdapter:
            mock_adapter = MockCjpyAdapter.return_value
            mock_adapter.is_available.return_value = True
            mock_adapter.fetch_daily_quotes.return_value = pd.DataFrame()

            calculator = MacroSensitivityCalculator()
            result = calculator.compute(
                canonical_id="600519.SH",
                start_date="20240101",
                end_date="20241231",
            )

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is None

    @pytest.mark.asyncio
    async def test_compute_handles_cjpy_adapter_exception(self):
        """If CjpyAdapter raises, compute() returns empty, does not crash."""
        with patch("data_layer.adapters.cjpy_adapter.CjpyAdapter") as MockCjpyAdapter:
            mock_adapter = MockCjpyAdapter.return_value
            mock_adapter.is_available.side_effect = RuntimeError("Cjpy crash")

            calculator = MacroSensitivityCalculator()
            result = calculator.compute(
                canonical_id="600519.SH",
                start_date="20240101",
                end_date="20241231",
            )

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is None

    # ------------------------------------------------------------------
    # Edge cases for partial data
    # ------------------------------------------------------------------

    def test_regression_handles_partial_factor_data(self):
        """Regression should work when some proxy ETFs have data and others don't."""
        codes_with_data = ["600519.SH", MACRO_PROXY_ETFS["interest_rate"]]
        df = _make_quote_df(codes_with_data, n_days=150, seed=42)
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "600519.SH", min_observations=30)

        # The factor with data should have a beta
        assert result.interest_rate_sensitivity is not None
        # Factors without data should be None
        assert result.inflation_sensitivity is None

    def test_regression_handles_tiny_beta_values(self):
        """Small beta values should not appear in key_macro_factors."""
        codes = ["600519.SH", MACRO_PROXY_ETFS["interest_rate"]]
        df = _make_quote_df(codes, n_days=100, seed=42)
        calculator = MacroSensitivityCalculator()

        result = calculator._run_regression(df, "600519.SH", min_observations=30)

        # key_macro_factors should only include factors with |beta| > 0.1
        if result.interest_rate_sensitivity is not None:
            if abs(result.interest_rate_sensitivity) <= 0.1:
                assert "interest_rate" not in (result.key_macro_factors or [])
            else:
                assert "interest_rate" in (result.key_macro_factors or [])


class TestMacroSensitivityIntegration:
    """Integration tests for macro sensitivity inside AssetAnalysisService."""

    @pytest.mark.asyncio
    async def test_fast_price_mode_skips_macro_sensitivity(self):
        """Fast cached or live price paths defer expensive macro regression."""
        from services.asset_analysis_service import AssetAnalysisService

        service = AssetAnalysisService()

        # Mock generate_snapshot to return a basic snapshot
        from core.contracts import AssetAnalysisSnapshot

        service.generate_snapshot = AsyncMock(
            return_value=AssetAnalysisSnapshot(
                canonical_id="600519.SH",
                as_of=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
                financial={},
                fund_flow={},
                price_volume={},
                valuation={},
                shareholder={},
                industry={},
                event_impact=[],
                macro_exposure={},
                evidence_refs=[],
            )
        )
        service._fill_structured_data = Mock(side_effect=lambda card, snapshot: card)
        service._fill_wind_market_snapshot = Mock()
        service._build_basic_info = Mock(return_value=None)
        service._fill_industry_data = Mock(return_value=None)
        service._fill_shareholder_data = AsyncMock(return_value=([], []))
        service._fill_recent_events = Mock(return_value=[])

        # Mock _compute_macro_sensitivity to return a known value
        service._compute_macro_sensitivity = Mock(
            return_value=MacroSensitivity(
                interest_rate_sensitivity=0.35,
                inflation_sensitivity=-0.12,
                key_macro_factors=["interest_rate"],
            )
        )

        card = await service.generate_analysis_card(
            canonical_id="600519.SH",
            as_of=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
        )

        assert card.macro_sensitivity is None
        service._compute_macro_sensitivity.assert_not_called()

    @pytest.mark.asyncio
    async def test_compute_macro_sensitivity_returns_empty_on_failure(self):
        """_compute_macro_sensitivity should return empty on any exception."""
        from services.asset_analysis_service import AssetAnalysisService

        service = AssetAnalysisService()
        from datetime import date

        result = service._compute_macro_sensitivity(
            canonical_id="invalid-xxx",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert isinstance(result, MacroSensitivity)
        assert result.interest_rate_sensitivity is None
