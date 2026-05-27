#!/usr/bin/env python3
"""bootstrap 脚本：填充初始结构化行情数据

用法:
    python scripts/bootstrap_market_data.py              # 全量执行
    python scripts/bootstrap_market_data.py --dry-run    # 只检查不写入
    python scripts/bootstrap_market_data.py --limit 100  # 限制股票数量
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)

# 默认核心股票
DEFAULT_SYMBOLS = [
    "600519.SH",  # 贵州茅台
    "002594.SZ",  # 比亚迪
    "601012.SH",  # 隆基绿能
    "600036.SH",  # 招商银行
    "000858.SZ",  # 五粮液
]

DRY_RUN = "--dry-run" in sys.argv
LIMIT = None
for i, arg in enumerate(sys.argv):
    if arg == "--limit" and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])


def main() -> int:
    print("=" * 60)
    print("结构化行情数据初始化 (bootstrap)")
    print("=" * 60)

    print(f"\n数据库: {settings.DATABASE_URL}")
    if DRY_RUN:
        print("模式: DRY RUN (只检查，不写入)")

    from data_layer.crawlers.akshare.base import AkShareAdapter
    from data_layer.repositories.base import db_session
    from data_layer.repositories.etl_run_repository import ETLRunRepository
    from data_layer.repositories.market_data_repository import MarketDataRepository

    # 检查网络可用性
    try:
        adapter = AkShareAdapter()
    except Exception as e:
        print(f"\n❌ AkShare 初始化失败: {e}")
        print("请确认网络连接正常，且已安装 akshare (pip install akshare)")
        return 1

    with db_session() as db:
        market_repo = MarketDataRepository(db)
        etl_repo = ETLRunRepository(db)

        from services.market_data_ingestion_service import MarketDataIngestionService

        service = MarketDataIngestionService(
            market_repo=market_repo,
            etl_repo=etl_repo,
            akshare_adapter=adapter,
        )

        # Step 1: 同步股票列表
        print(f"\n1/2 同步股票列表{' (DRY RUN)' if DRY_RUN else ''}...")
        if DRY_RUN:
            print(f"  会执行: ingest_stock_master(limit={LIMIT or 'default'})")
        else:
            try:
                result = service.ingest_stock_master(limit=LIMIT)
                print(f"   完成: fetched={result['fetched']}, saved={result['saved']}")
            except Exception as e:
                print(f"   ❌ 同步股票列表失败: {e}")
                logger.error(f"bootstrap stock_master failed: {e}", exc_info=True)
                return 1

        # Step 2: 同步核心股票日行情
        symbols = DEFAULT_SYMBOLS
        end_date = date.today()
        start_date = end_date - timedelta(days=365)
        print(f"\n2/2 同步 {len(symbols)} 只核心股票日行情{' (DRY RUN)' if DRY_RUN else ''}...")
        print(f"   区间: {start_date} ~ {end_date}")
        print(f"   标的: {', '.join(symbols)}")

        if DRY_RUN:
            print("   跳过执行")
        else:
            try:
                result = service.ingest_daily_bars(
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                )
                print(f"   完成: fetched={result['fetched']}, saved={result['saved']}")
            except Exception as e:
                print(f"   ❌ 同步日行情失败: {e}")
                logger.error(f"bootstrap daily_bars failed: {e}", exc_info=True)
                return 1

        print("\n" + "=" * 60)
        print("Bootstrap 完成")
        return 0


if __name__ == "__main__":
    sys.exit(main())
