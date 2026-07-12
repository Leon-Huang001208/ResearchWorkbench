"""Fund intelligence orchestration service."""

from collections import defaultdict
from math import sqrt
from statistics import stdev
from typing import Mapping, Optional

from core.contracts.funds import (
    FundDetail,
    FundExposureBreakdown,
    FundHolding,
    FundNavPoint,
    FundPerformanceMetrics,
    PortfolioFundExposure,
)
from core.observability import get_logger

logger = get_logger(__name__)


class FundIntelligenceService:
    """Build fund detail and exposure views from repository data."""

    def __init__(self, fund_repository):
        self._fund_repo = fund_repository

    def get_fund_detail(self, symbol: str) -> Optional[FundDetail]:
        """Return fund detail or None when the fund is unknown."""
        try:
            master = self._fund_repo.get_fund_master(symbol)
            if master is None:
                logger.info("fund detail not found", symbol=symbol)
                return None

            nav_history = self._fund_repo.get_nav_history(symbol)
            latest_nav = nav_history[-1] if nav_history else None
            detail = FundDetail(
                master=master,
                managers=self._fund_repo.get_manager_profiles(symbol),
                latest_nav=latest_nav,
                performance=self._calculate_performance(nav_history),
                latest_holdings=self._fund_repo.get_latest_holdings(symbol),
            )
            logger.info("fund detail built", symbol=symbol)
            return detail
        except Exception as exc:
            logger.error("failed to build fund detail", symbol=symbol, error=str(exc))
            raise

    def get_fund_exposure(self, symbol: str) -> PortfolioFundExposure:
        """Return single-fund stock, industry, and theme exposure."""
        try:
            holdings = self._fund_repo.get_latest_holdings(symbol)
            return self._build_exposure({symbol: 1.0}, {symbol: holdings})
        except Exception as exc:
            logger.error("failed to build fund exposure", symbol=symbol, error=str(exc))
            raise

    def calculate_portfolio_exposure(self, positions: Mapping[str, float]) -> PortfolioFundExposure:
        """Return weighted exposure across fund positions."""
        try:
            normalized = self._normalize_positions(positions)
            holdings_by_symbol = {
                symbol: self._fund_repo.get_latest_holdings(symbol) for symbol in normalized
            }
            exposure = self._build_exposure(normalized, holdings_by_symbol)
            logger.info("portfolio fund exposure built", fund_count=len(normalized))
            return exposure
        except Exception as exc:
            logger.error("failed to build portfolio fund exposure", error=str(exc))
            raise

    @staticmethod
    def _calculate_performance(nav_history: list[FundNavPoint]) -> FundPerformanceMetrics:
        if len(nav_history) < 2:
            return FundPerformanceMetrics()

        values = [
            nav.accumulated_nav if nav.accumulated_nav is not None else nav.unit_nav
            for nav in nav_history
        ]
        first_value = values[0]
        last_value = values[-1]
        total_return = (last_value / first_value - 1.0) if first_value else None

        days = (nav_history[-1].trading_day - nav_history[0].trading_day).days
        annualized_return = None
        if total_return is not None and days > 0:
            annualized_return = (1.0 + total_return) ** (365.0 / days) - 1.0

        peak = values[0]
        drawdowns: list[float] = []
        for value in values:
            peak = max(peak, value)
            drawdowns.append(value / peak - 1.0 if peak else 0.0)
        max_drawdown = min(drawdowns) if drawdowns else None
        ulcer_index = sqrt(sum(drawdown * drawdown for drawdown in drawdowns) / len(drawdowns))

        returns = [
            nav.daily_return
            for nav in nav_history
            if nav.daily_return is not None and nav.daily_return != 0
        ]
        win_rate = None
        volatility = None
        if returns:
            win_rate = sum(1 for item in returns if item > 0) / len(returns)
        if len(returns) >= 2:
            volatility = stdev(returns) * sqrt(252)

        return FundPerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            volatility=volatility,
            win_rate=win_rate,
            ulcer_index=ulcer_index,
        )

    @staticmethod
    def _normalize_positions(positions: Mapping[str, float]) -> dict[str, float]:
        positive = {symbol: weight for symbol, weight in positions.items() if weight > 0}
        total = sum(positive.values())
        if total <= 0:
            return {}
        return {symbol: weight / total for symbol, weight in positive.items()}

    def _build_exposure(
        self,
        positions: Mapping[str, float],
        holdings_by_symbol: Mapping[str, list[FundHolding]],
    ) -> PortfolioFundExposure:
        industry_weights: dict[str, float] = defaultdict(float)
        stock_weights: dict[str, float] = defaultdict(float)
        theme_weights: dict[str, float] = defaultdict(float)

        for fund_symbol, fund_weight in positions.items():
            for holding in holdings_by_symbol.get(fund_symbol, []):
                weighted = fund_weight * holding.weight
                stock_weights[holding.stock_symbol] += weighted
                if holding.industry:
                    industry_weights[holding.industry] += weighted
                if holding.theme:
                    theme_weights[holding.theme] += weighted

        return PortfolioFundExposure(
            positions=dict(positions),
            industry_exposure=self._to_breakdowns(industry_weights),
            stock_exposure=self._to_breakdowns(stock_weights),
            theme_exposure=self._to_breakdowns(theme_weights),
        )

    @staticmethod
    def _to_breakdowns(weights: Mapping[str, float]) -> list[FundExposureBreakdown]:
        return [
            FundExposureBreakdown(label=label, weight=weight)
            for label, weight in sorted(weights.items(), key=lambda item: (-item[1], item[0]))
        ]
