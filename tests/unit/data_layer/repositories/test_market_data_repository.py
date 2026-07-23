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
        "index_id": "CSI:000300",
        "index_symbol": "000300",
        "provider_code": "CSI",
        "component_symbol": "300308.SZ",
        "component_name": "中际旭创",
        "market": "A-share",
        "weight": weight,
        "weight_pct": weight,
        "rank": 1,
        "as_of": datetime(2026, 6, 9, tzinfo=timezone.utc),
        "trade_date": datetime(2026, 6, 9, tzinfo=timezone.utc),
        "source": "csindex",
        "source_scope": "full",
        "raw_payload": {"rank": 1},
    }


def _index_master_dict(name="沪深300"):
    return {
        "index_id": "CSI:000300",
        "provider_code": "CSI",
        "official_code": "000300",
        "wind_code": "000300.SH",
        "name_cn": name,
        "name_en": "CSI 300",
        "market": "CN",
        "currency": "CNY",
        "category": "broad_based",
        "is_active": True,
        "raw_payload": {"publisher": "CSI"},
    }


def _etf_master_dict(name="沪深300ETF"):
    return {
        "etf_symbol": "510300.SH",
        "name": name,
        "exchange": "SH",
        "market": "CN",
        "fund_manager": "华泰柏瑞基金",
        "currency": "CNY",
        "status": "active",
        "raw_payload": {"provider": "wind"},
    }


def _etf_metric_dict(aum=100.0, net_flow=2.0):
    return {
        "etf_symbol": "510300.SH",
        "trade_date": datetime(2026, 6, 9, tzinfo=timezone.utc),
        "nav": 4.2,
        "close": 4.21,
        "shares_outstanding": 23.8,
        "aum": aum,
        "turnover": 1.5,
        "premium_discount_pct": 0.2,
        "net_flow_amount": net_flow,
        "source": "wind",
        "raw_payload": {"flow_formula": "shares_delta * nav"},
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

    def test_get_existing_trade_dates(self, repo):
        repo.upsert_daily_bars(
            [
                _daily_bar_dict(trade_date=datetime(2024, 1, 10, tzinfo=timezone.utc)),
                _daily_bar_dict(trade_date=datetime(2024, 1, 15, tzinfo=timezone.utc)),
                _daily_bar_dict(
                    trade_date=datetime(2024, 1, 20, tzinfo=timezone.utc),
                    symbol="000001.SZ",
                ),
            ]
        )

        dates = repo.get_existing_trade_dates(
            symbol="600519.SH",
            source="akshare",
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        assert dates == {datetime(2024, 1, 10).date(), datetime(2024, 1, 15).date()}

    def test_upsert_index_components_no_duplicate(self, repo, db_session):
        repo.upsert_index_components([_index_component_dict(weight=5.0)])
        repo.upsert_index_components([_index_component_dict(weight=5.5)])

        from data_layer.repositories.models import IndexComponentSnapshotDB

        rows = db_session.query(IndexComponentSnapshotDB).all()
        assert len(rows) == 1
        assert float(rows[0].weight_pct) == 5.5

    def test_upsert_index_provider_and_master(self, repo, db_session):
        repo.upsert_index_providers(
            [
                {
                    "provider_code": "CSI",
                    "name": "中证指数",
                    "official_site": "https://www.csindex.com.cn/",
                    "source_priority": 10,
                    "raw_payload": {"scope": "index publisher"},
                }
            ]
        )
        repo.upsert_index_master_many([_index_master_dict()])
        repo.upsert_index_master_many([_index_master_dict(name="沪深300指数")])

        from data_layer.repositories.models import IndexMasterDB, IndexProviderDB

        providers = db_session.query(IndexProviderDB).all()
        indices = db_session.query(IndexMasterDB).all()
        assert len(providers) == 1
        assert len(indices) == 1
        assert indices[0].name_cn == "沪深300指数"

    def test_get_stock_index_memberships(self, repo):
        repo.upsert_index_master_many([_index_master_dict()])
        repo.upsert_index_components([_index_component_dict(weight=5.0)])

        memberships = repo.get_stock_index_memberships(
            "300308.SZ",
            trade_date=datetime(2026, 6, 9, tzinfo=timezone.utc),
        )

        assert len(memberships) == 1
        assert memberships[0]["index_id"] == "CSI:000300"
        assert memberships[0]["provider_code"] == "CSI"
        assert memberships[0]["index_name"] == "沪深300"
        assert float(memberships[0]["weight_pct"]) == 5.0

    def test_upsert_index_etf_link_and_daily_metric(self, repo, db_session):
        repo.upsert_index_master_many([_index_master_dict()])
        repo.upsert_etf_master_many([_etf_master_dict()])
        repo.upsert_index_etf_links(
            [
                {
                    "index_id": "CSI:000300",
                    "etf_symbol": "510300.SH",
                    "tracking_role": "primary",
                    "link_source": "wind",
                    "confidence": 0.95,
                    "raw_payload": {"tracking_index": "000300.SH"},
                }
            ]
        )
        repo.upsert_etf_daily_metrics([_etf_metric_dict(aum=100.0, net_flow=2.0)])
        repo.upsert_etf_daily_metrics([_etf_metric_dict(aum=105.0, net_flow=3.0)])

        from data_layer.repositories.models import ETFDailyMetricDB

        etfs = repo.get_index_etfs("CSI:000300")
        metrics = repo.get_etf_daily_metrics("510300.SH")
        metric_rows = db_session.query(ETFDailyMetricDB).all()

        assert len(etfs) == 1
        assert etfs[0]["etf_symbol"] == "510300.SH"
        assert etfs[0]["name"] == "沪深300ETF"
        assert len(metrics) == 1
        assert len(metric_rows) == 1
        assert float(metrics[0].aum) == 105.0
        assert float(metrics[0].net_flow_amount) == 3.0

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
        assert repo.upsert_index_providers([]) == 0
        assert repo.upsert_index_master_many([]) == 0
        assert repo.upsert_etf_master_many([]) == 0
        assert repo.upsert_index_etf_links([]) == 0
        assert repo.upsert_etf_daily_metrics([]) == 0
        assert repo.insert_quote_snapshots([]) == 0
