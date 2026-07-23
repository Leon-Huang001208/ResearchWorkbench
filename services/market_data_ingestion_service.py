"""MarketDataIngestionService — ETL 编排服务

编排 fetcher → normalizer → repository → etl_run 全流程。
"""

import uuid
from datetime import date
from typing import Any, Optional

from core.observability import get_logger
from data_layer.crawlers.akshare.base import AkShareAdapter
from data_layer.normalizers.akshare_market import normalize_market_data, normalize_stock_info
from data_layer.repositories.etl_run_repository import ETLRunRepository
from data_layer.repositories.market_data_repository import MarketDataRepository

logger = get_logger(__name__)


class MarketDataIngestionService:
    """市场数据摄入编排服务"""

    def __init__(
        self,
        market_repo: MarketDataRepository,
        etl_repo: ETLRunRepository,
        akshare_adapter: Optional[AkShareAdapter] = None,
    ):
        self.market_repo = market_repo
        self.etl_repo = etl_repo
        self.akshare = akshare_adapter or AkShareAdapter()

    def ingest_stock_master(self, limit: Optional[int] = None) -> dict:
        """拉取股票列表 → normalize → upsert → 记录 ETL run"""
        run_id = str(uuid.uuid4())
        self.etl_repo.start(run_id, job_name="ingest_stock_master", source="akshare")

        try:
            stocks = self.akshare.market.get_stock_list(limit=limit)
            rows = [normalize_stock_info(x) for x in stocks]
            saved = self.market_repo.upsert_stock_master_many(rows)

            self.etl_repo.finish(
                run_id,
                status="success",
                items_fetched=len(stocks),
                items_normalized=len(rows),
                items_saved=saved,
            )
            logger.info(f"ingest_stock_master done: fetched={len(stocks)} saved={saved}")
            return {"run_id": run_id, "fetched": len(stocks), "saved": saved}
        except Exception as e:
            self.etl_repo.fail(run_id, str(e))
            logger.error(f"ingest_stock_master failed: {e}", exc_info=True)
            raise

    def ingest_daily_bars(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
    ) -> dict:
        """拉取日行情 → normalize → upsert → 记录 ETL run"""
        run_id = str(uuid.uuid4())
        self.etl_repo.start(run_id, job_name="ingest_daily_bars", source="akshare")

        fetched = 0
        rows: list[dict[str, Any]] = []

        try:
            for symbol in symbols:
                bars = self.akshare.market.get_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                )
                fetched += len(bars)
                rows.extend(normalize_market_data(x) for x in bars)

            saved = self.market_repo.upsert_daily_bars(rows)

            self.etl_repo.finish(
                run_id,
                status="success",
                items_fetched=fetched,
                items_normalized=len(rows),
                items_saved=saved,
            )
            logger.info(f"ingest_daily_bars done: fetched={fetched} saved={saved}")
            return {"run_id": run_id, "fetched": fetched, "saved": saved}
        except Exception as e:
            self.etl_repo.fail(run_id, str(e))
            logger.error(f"ingest_daily_bars failed: {e}", exc_info=True)
            raise
