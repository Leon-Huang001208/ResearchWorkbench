from datetime import date

import pytest
from pydantic import ValidationError

from core.contracts.funds import (
    FundDetail,
    FundExposureBreakdown,
    FundHolding,
    FundManagerProfile,
    FundMaster,
    FundNavPoint,
    FundPerformanceMetrics,
    PortfolioFundExposure,
)


def test_fund_master_requires_symbol_and_name():
    master = FundMaster(
        symbol="000001.OF",
        name="Alpha Growth",
        fund_type="equity",
        management_company="Alpha Fund",
    )

    assert master.symbol == "000001.OF"
    assert master.name == "Alpha Growth"
    assert master.fund_type == "equity"

    with pytest.raises(ValidationError):
        FundMaster(symbol="", name="Alpha Growth")


def test_nav_point_accepts_decimal_values():
    nav = FundNavPoint(
        symbol="000001.OF",
        trading_day=date(2026, 6, 24),
        unit_nav=1.2345,
        accumulated_nav=2.3456,
        daily_return=0.0123,
    )

    assert nav.unit_nav == pytest.approx(1.2345)
    assert nav.accumulated_nav == pytest.approx(2.3456)
    assert nav.daily_return == pytest.approx(0.0123)


def test_fund_detail_preserves_holdings_and_metrics():
    master = FundMaster(symbol="000001.OF", name="Alpha Growth")
    manager = FundManagerProfile(
        manager_id="mgr-1",
        manager_name="Jane Chen",
        institution_name="Alpha Fund",
        tenure_start=date(2022, 1, 1),
    )
    holding = FundHolding(
        symbol="000001.OF",
        report_date=date(2026, 3, 31),
        stock_symbol="600519.SH",
        stock_name="Kweichow Moutai",
        industry="Food & Beverage",
        weight=0.08,
        market_value=120000000.0,
    )
    metrics = FundPerformanceMetrics(
        total_return=0.12,
        annualized_return=0.08,
        max_drawdown=-0.06,
        volatility=0.15,
        win_rate=0.58,
        ulcer_index=0.03,
    )

    detail = FundDetail(
        master=master,
        managers=[manager],
        latest_nav=FundNavPoint(
            symbol="000001.OF",
            trading_day=date(2026, 6, 24),
            unit_nav=1.25,
            accumulated_nav=2.5,
        ),
        performance=metrics,
        latest_holdings=[holding],
    )

    assert detail.master.symbol == "000001.OF"
    assert detail.managers[0].manager_name == "Jane Chen"
    assert detail.latest_holdings[0].report_date == date(2026, 3, 31)
    assert detail.performance.max_drawdown == pytest.approx(-0.06)


def test_portfolio_exposure_normalizes_weighted_industry_values():
    exposure = PortfolioFundExposure(
        positions={"000001.OF": 0.6, "000002.OF": 0.4},
        industry_exposure=[
            FundExposureBreakdown(label="AI", weight=0.42),
            FundExposureBreakdown(label="Consumer", weight=0.18),
        ],
        stock_exposure=[
            FundExposureBreakdown(label="600519.SH", weight=0.048),
        ],
    )

    assert exposure.positions["000001.OF"] == pytest.approx(0.6)
    assert exposure.industry_exposure[0].label == "AI"
    assert exposure.stock_exposure[0].weight == pytest.approx(0.048)
