from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.contracts.funds import FundHolding, FundManagerProfile, FundMaster, FundNavPoint
from data_layer.repositories.fund_repository import FundRepository


@pytest.fixture
def repo():
    engine = create_engine("sqlite:///:memory:", echo=False)
    session = Session(engine)
    repository = FundRepository(session)
    repository.ensure_schema()
    yield repository
    session.close()


def test_upsert_and_get_fund_master(repo):
    repo.upsert_fund_master(
        FundMaster(
            symbol="000001.OF",
            name="Alpha Growth",
            fund_type="equity",
            management_company="Alpha Fund",
            inception_date=date(2020, 1, 1),
            benchmark="沪深300",
            latest_size=12.5,
        )
    )

    repo.upsert_fund_master(
        FundMaster(
            symbol="000001.OF",
            name="Alpha Growth Updated",
            fund_type="equity",
            management_company="Alpha Fund",
            latest_size=13.5,
        )
    )

    master = repo.get_fund_master("000001.OF")

    assert master is not None
    assert master.name == "Alpha Growth Updated"
    assert master.latest_size == pytest.approx(13.5)


def test_upsert_nav_points_orders_history(repo):
    repo.upsert_fund_master(FundMaster(symbol="000001.OF", name="Alpha Growth"))
    repo.upsert_nav_points(
        [
            FundNavPoint(
                symbol="000001.OF",
                trading_day=date(2026, 6, 24),
                unit_nav=1.12,
                accumulated_nav=1.5,
                daily_return=0.01,
            ),
            FundNavPoint(
                symbol="000001.OF",
                trading_day=date(2026, 6, 23),
                unit_nav=1.10,
                accumulated_nav=1.48,
                daily_return=-0.005,
            ),
        ]
    )

    navs = repo.get_nav_history("000001.OF")

    assert [nav.trading_day for nav in navs] == [date(2026, 6, 23), date(2026, 6, 24)]
    assert navs[-1].unit_nav == pytest.approx(1.12)


def test_get_latest_holdings_returns_latest_report_only(repo):
    repo.upsert_fund_master(FundMaster(symbol="000001.OF", name="Alpha Growth"))
    repo.upsert_holdings(
        [
            FundHolding(
                symbol="000001.OF",
                report_date=date(2025, 12, 31),
                stock_symbol="000001.SZ",
                stock_name="Ping An Bank",
                industry="Bank",
                weight=0.05,
            ),
            FundHolding(
                symbol="000001.OF",
                report_date=date(2026, 3, 31),
                stock_symbol="600519.SH",
                stock_name="Kweichow Moutai",
                industry="Food & Beverage",
                theme="Consumer",
                weight=0.08,
                market_value=120000000.0,
            ),
        ]
    )

    holdings = repo.get_latest_holdings("000001.OF")

    assert len(holdings) == 1
    assert holdings[0].stock_symbol == "600519.SH"
    assert holdings[0].report_date == date(2026, 3, 31)


def test_upsert_manager_tenures_returns_profiles(repo):
    repo.upsert_fund_master(FundMaster(symbol="000001.OF", name="Alpha Growth"))
    repo.upsert_manager_tenures(
        "000001.OF",
        [
            FundManagerProfile(
                manager_id="mgr-1",
                manager_name="Jane Chen",
                institution_name="Alpha Fund",
                tenure_start=date(2022, 1, 1),
            )
        ],
    )

    managers = repo.get_manager_profiles("000001.OF")

    assert len(managers) == 1
    assert managers[0].manager_name == "Jane Chen"
    assert managers[0].tenure_start == date(2022, 1, 1)
