"""MarketDataRepository 单元测试

测试 upsert 幂等性：insert → update → 不重复。
使用 SQLite 内存数据库。
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_layer.repositories.base import Base
from data_layer.repositories.market_data_repository import MarketDataRepository


@pytest.fixture
def db_session():
    """创建 SQLite 内存数据库 session"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def repo(db_session):
    return MarketDataRepository(db_session)


def _stock_master_dict(symbol="600519.SH"):
    return {
        "symbol": symbol,
        "raw_code": symbol.split(".")[0],
        "name": "Test Stock",
        "exchange": "SH",
        "market": "A-share",
        "industry_level1": "白酒",
        "source": "akshare",
    }


def _daily_bar_dict(symbol="600519.SH", trade_date=None):
    if trade_date is None:
        trade_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 103.0,
        "volume": 1000000,
        "amount": 1.03e8,
        "turnover": 0.5,
        "source": "akshare",
        "raw_payload": {},
    }


def _index_component_dict(weight=5.0):
    return {
        "index_symbol": "000300",
        "component_symbol": "300308.SZ",
        "component_name": "中际旭创",
        "weight": weight,
        "as_of": datetime(2026, 6, 9, tzinfo=timezone.utc),
        "source": "csindex",
        "raw_payload": {"rank": 1},
    }


class TestMarketDataRepository:
    def test_upsert_stock_master_insert(self, repo):
        """第一次 insert 成功"""
        saved = repo.upsert_stock_master_many([_stock_master_dict()])
        assert saved == 1

        result = repo.get_stock_master("600519.SH")
        assert result is not None
        assert result.name == "Test Stock"

    def test_upsert_stock_master_update(self, repo):
        """第二次同 symbol update 成功，不产生重复"""
        repo.upsert_stock_master_many([_stock_master_dict()])

        updated = _stock_master_dict()
        updated["name"] = "Updated Name"
        saved = repo.upsert_stock_master_many([updated])
        assert saved == 1

        result = repo.get_stock_master("600519.SH")
        assert result.name == "Updated Name"

        # 确认只有一条
        all_symbols = repo.get_all_stock_symbols()
        assert all_symbols.count("600519.SH") == 1

    def test_upsert_daily_bars_insert(self, repo):
        """日行情第一次 insert"""
        bars = [_daily_bar_dict()]
        saved = repo.upsert_daily_bars(bars)
        assert saved == 1

        result = repo.get_latest_daily_bar("600519.SH")
        assert result is not None

    def test_upsert_daily_bars_empty(self, repo):
        """空列表不报错"""
        assert repo.upsert_daily_bars([]) == 0

    def test_upsert_daily_bars_no_duplicate(self, repo):
        """同 symbol/date/source 不重复"""
        bars = [_daily_bar_dict()]
        repo.upsert_daily_bars(bars)
        repo.upsert_daily_bars(bars)  # upsert again

        result = repo.get_daily_bars("600519.SH")
        assert len(result) == 1

    def test_get_daily_bars_filter(self, repo):
        """测试日期过滤"""
        bar1 = _daily_bar_dict(trade_date=datetime(2024, 1, 10, tzinfo=timezone.utc))
        bar2 = _daily_bar_dict(trade_date=datetime(2024, 1, 15, tzinfo=timezone.utc))
        bar3 = _daily_bar_dict(trade_date=datetime(2024, 1, 20, tzinfo=timezone.utc))
        repo.upsert_daily_bars([bar1, bar2, bar3])

        filtered = repo.get_daily_bars(
            "600519.SH",
            start_date=datetime(2024, 1, 12, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 18, tzinfo=timezone.utc),
        )
        assert len(filtered) == 1  # only bar2

    def test_upsert_index_components_no_duplicate(self, repo, db_session):
        repo.upsert_index_components([_index_component_dict(weight=5.0)])
        repo.upsert_index_components([_index_component_dict(weight=5.5)])

        from data_layer.repositories.models import IndexComponentDB

        rows = db_session.query(IndexComponentDB).all()
        assert len(rows) == 1
        assert float(rows[0].weight) == 5.5

    def test_get_all_stock_symbols(self, repo):
        """获取所有股票 symbol"""
        repo.upsert_stock_master_many(
            [
                _stock_master_dict("600519.SH"),
                _stock_master_dict("000001.SZ"),
                _stock_master_dict("300750.SZ"),
            ]
        )
        symbols = repo.get_all_stock_symbols()
        assert len(symbols) == 3
        assert "600519.SH" in symbols

    def test_empty_upsert(self, repo):
        """空列表 upsert 返回 0"""
        assert repo.upsert_stock_master_many([]) == 0
        assert repo.upsert_daily_bars([]) == 0
        assert repo.upsert_financial_metrics([]) == 0
        assert repo.upsert_valuations([]) == 0
        assert repo.upsert_shareholders([]) == 0
        assert repo.upsert_index_components([]) == 0
        assert repo.insert_quote_snapshots([]) == 0
