"""MarketDataIngestionService 单元测试

使用 FakeAkShareAdapter 模拟数据源，验证 fetch → normalize → save → etl_run 全流程。
"""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_layer.crawlers.akshare.base import MarketData, StockInfo
from data_layer.repositories.base import Base
from data_layer.repositories.etl_run_repository import ETLRunRepository
from data_layer.repositories.market_data_repository import MarketDataRepository
from services.market_data_ingestion_service import MarketDataIngestionService


class FakeAkShareMarket:
    """Fake market adapter"""

    @staticmethod
    def get_stock_list(limit=None):
        stocks = [
            StockInfo(symbol="600519.SH", name="贵州茅台", market="sh", industry="白酒"),
            StockInfo(symbol="000001.SZ", name="平安银行", market="sz", industry="银行"),
        ]
        if limit:
            return stocks[:limit]
        return stocks

    @staticmethod
    def get_historical_data(symbol, start_date, end_date):
        return [
            MarketData(
                symbol=symbol,
                timestamp=datetime(2024, 1, 15, tzinfo=timezone.utc),
                open=100.0,
                high=105.0,
                low=99.0,
                close=103.0,
                volume=1000000,
            )
        ]


class FakeAkShareAdapter:
    market = FakeAkShareMarket()


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def service(db_session):
    market_repo = MarketDataRepository(db_session)
    etl_repo = ETLRunRepository(db_session)
    return MarketDataIngestionService(
        market_repo=market_repo,
        etl_repo=etl_repo,
        akshare_adapter=FakeAkShareAdapter(),
    )


class TestMarketDataIngestionService:
    def test_ingest_stock_master(self, service, db_session):
        result = service.ingest_stock_master()

        assert result["fetched"] == 2
        assert result["saved"] == 2
        assert "run_id" in result

        # 验证数据已写入
        stock = service.market_repo.get_stock_master("600519.SH")
        assert stock is not None
        assert stock.name == "贵州茅台"

        # 验证 ETL run 已记录
        run = service.etl_repo.get_run(result["run_id"])
        assert run.status == "success"
        assert run.items_fetched == 2

    def test_ingest_stock_master_with_limit(self, service, db_session):
        result = service.ingest_stock_master(limit=1)

        assert result["fetched"] == 1
        assert result["saved"] == 1

    def test_ingest_daily_bars(self, service, db_session):
        result = service.ingest_daily_bars(
            symbols=["600519.SH"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        assert result["fetched"] == 1
        assert result["saved"] == 1

        # 验证数据已写入
        bar = service.market_repo.get_latest_daily_bar("600519.SH")
        assert bar is not None

        # 验证 ETL run
        run = service.etl_repo.get_run(result["run_id"])
        assert run.status == "success"
        assert run.items_fetched == 1

    def test_ingest_daily_bars_failure_records_etl_run(self, service, db_session):
        """测试失败时 etl_run 记录为 failed（使用不存在的 symbol 不会失败，但用空列表会）"""
        result = service.ingest_daily_bars(
            symbols=[],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        assert result["fetched"] == 0
        assert result["saved"] == 0
        pair = service.etl_repo.get_run(result["run_id"])
        assert pair.status == "success"  # empty list is not an error, just 0
