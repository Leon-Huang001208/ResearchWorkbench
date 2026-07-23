#!/usr/bin/env python3
"""验证结构化行情数据表是否存在"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import inspect

from data_layer.repositories.base import engine

REQUIRED_TABLES = {
    "stock_master",
    "stock_daily_bar",
    "stock_quote_snapshot",
    "stock_financial_metric",
    "stock_valuation",
    "stock_shareholder",
    "index_component",
    "etl_run",
}


def main() -> int:
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = REQUIRED_TABLES - existing
    REQUIRED_TABLES & existing

    print("=" * 60)
    print("结构化行情数据表 Schema 检查")
    print("=" * 60)

    for table in sorted(REQUIRED_TABLES):
        status = "✅" if table in existing else "❌"
        print(f"  {status} {table}")

    print("\n" + "=" * 60)

    if missing:
        print(f"\n❌ 缺少 {len(missing)} 张表:")
        for table in sorted(missing):
            print(f"   - {table}")
        print("\n请执行迁移: alembic -c storage/migrations/alembic.ini upgrade head")
        return 1

    print(f"\n✅ 全部 {len(REQUIRED_TABLES)} 张结构化行情数据表已存在")
    return 0


if __name__ == "__main__":
    sys.exit(main())
