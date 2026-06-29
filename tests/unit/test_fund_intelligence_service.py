from datetime import date

import pytest

from core.contracts.funds import FundHolding, FundManagerProfile, FundMaster, FundNavPoint
from services.fund_intelligence_service import FundIntelligenceService


class FakeFundRepository:
    def __init__(self):
        self.masters = {
            "000001.OF": FundMaster(symbol="000001.OF", name="Alpha Growth"),
            "000002.OF": FundMaster(symbol="000002.OF", name="Beta Balance"),
        }
        self.navs = {
            "000001.OF": [
                FundNavPoint(
                    symbol="000001.OF",
                    trading_day=date(2026, 6, 20),
                    unit_nav=1.00,
                    accumulated_nav=1.00,
                    daily_return=0.0,
                ),
                FundNavPoint(
                    symbol="000001.OF",
                    trading_day=date(2026, 6, 21),
                    unit_nav=1.10,
                    accumulated_nav=1.10,
                    daily_return=0.10,
                ),
                FundNavPoint(
                    symbol="000001.OF",
                    trading_day=date(2026, 6, 22),
                    unit_nav=1.05,
                    accumulated_nav=1.05,
                    daily_return=-0.0454545,
                ),
                FundNavPoint(
                    symbol="000001.OF",
                    trading_day=date(2026, 6, 23),
                    unit_nav=1.20,
                    accumulated_nav=1.20,
                    daily_return=0.1428571,
                ),
            ],
            "000002.OF": [
                FundNavPoint(
                    symbol="000002.OF",
                    trading_day=date(2026, 6, 20),
                    unit_nav=1.00,
                    accumulated_nav=1.00,
                ),
                FundNavPoint(
                    symbol="000002.OF",
                    trading_day=date(2026, 6, 23),
                    unit_nav=1.05,
                    accumulated_nav=1.05,
                ),
            ],
        }
        self.holdings = {
            "000001.OF": [
                FundHolding(
                    symbol="000001.OF",
                    report_date=date(2026, 3, 31),
                    stock_symbol="600519.SH",
                    stock_name="Kweichow Moutai",
                    industry="Consumer",
                    theme="Dividend",
                    weight=0.10,
                ),
                FundHolding(
                    symbol="000001.OF",
                    report_date=date(2026, 3, 31),
                    stock_symbol="688981.SH",
                    stock_name="SMIC",
                    industry="Technology",
                    theme="AI",
                    weight=0.20,
                ),
            ],
            "000002.OF": [
                FundHolding(
                    symbol="000002.OF",
                    report_date=date(2026, 3, 31),
                    stock_symbol="688981.SH",
                    stock_name="SMIC",
                    industry="Technology",
                    theme="AI",
                    weight=0.25,
                )
            ],
        }
        self.managers = {
            "000001.OF": [
                FundManagerProfile(
                    manager_id="mgr-1",
                    manager_name="Jane Chen",
                    tenure_start=date(2022, 1, 1),
                )
            ]
        }

    def get_fund_master(self, symbol):
        return self.masters.get(symbol)

    def get_nav_history(self, symbol):
        return self.navs.get(symbol, [])

    def get_latest_holdings(self, symbol):
        return self.holdings.get(symbol, [])

    def get_manager_profiles(self, symbol):
        return self.managers.get(symbol, [])


def test_get_fund_detail_builds_latest_nav_metrics_and_holdings():
    service = FundIntelligenceService(FakeFundRepository())

    detail = service.get_fund_detail("000001.OF")

    assert detail is not None
    assert detail.master.name == "Alpha Growth"
    assert detail.latest_nav.trading_day == date(2026, 6, 23)
    assert detail.performance.total_return == pytest.approx(0.20)
    assert detail.performance.max_drawdown == pytest.approx(-0.0454545, rel=1e-5)
    assert detail.performance.win_rate == pytest.approx(2 / 3)
    assert len(detail.latest_holdings) == 2


def test_get_fund_detail_returns_none_for_missing_fund():
    service = FundIntelligenceService(FakeFundRepository())

    assert service.get_fund_detail("missing") is None


def test_get_fund_exposure_aggregates_industry_stock_and_theme_weights():
    service = FundIntelligenceService(FakeFundRepository())

    exposure = service.get_fund_exposure("000001.OF")

    assert exposure.positions == {"000001.OF": 1.0}
    assert [(item.label, item.weight) for item in exposure.industry_exposure] == [
        ("Technology", pytest.approx(0.20)),
        ("Consumer", pytest.approx(0.10)),
    ]
    assert exposure.stock_exposure[0].label == "688981.SH"
    assert exposure.theme_exposure[0].label == "AI"


def test_calculate_portfolio_exposure_weights_multiple_funds():
    service = FundIntelligenceService(FakeFundRepository())

    exposure = service.calculate_portfolio_exposure({"000001.OF": 0.6, "000002.OF": 0.4})

    assert exposure.positions == {"000001.OF": pytest.approx(0.6), "000002.OF": pytest.approx(0.4)}
    assert [(item.label, item.weight) for item in exposure.industry_exposure] == [
        ("Technology", pytest.approx(0.22)),
        ("Consumer", pytest.approx(0.06)),
    ]
    assert exposure.stock_exposure[0].label == "688981.SH"
    assert exposure.stock_exposure[0].weight == pytest.approx(0.22)
