#!/usr/bin/env python3
"""测试 DashboardDataRepository 的功能"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_layer.repositories.base import SessionLocal, check_database_connection
from data_layer.repositories.dashboard_data import DashboardDataRepository


def test_dashboard_repo():
    """测试 DashboardDataRepository"""
    check_database_connection()
    db = SessionLocal()
    try:
        print("=" * 60)
        print("测试 DashboardDataRepository")
        print("=" * 60)

        repo = DashboardDataRepository(db)

        # 1. 测试获取新闻
        print("\n1️⃣  测试 get_global_news_from_events...")
        event_news = repo.get_global_news_from_events(limit=5, days=30)
        print(f"   从事件获取到 {len(event_news)} 条新闻")
        for i, news in enumerate(event_news[:2]):
            print(f"   {i+1}. {news['title'][:50]}... (源: {news['source']})")

        print("\n2️⃣  测试 get_global_news_from_documents...")
        doc_news = repo.get_global_news_from_documents(limit=5, days=30)
        print(f"   从文档获取到 {len(doc_news)} 条新闻")

        print("\n3️⃣  测试 get_combined_global_news...")
        combined, has_real = repo.get_combined_global_news(limit=10, days=30)
        print(f"   组合新闻: {len(combined)} 条, has_real={has_real}")
        for i, news in enumerate(combined[:3]):
            print(f"   {i+1}. {news['title'][:50]}... (重要性: {news['importance_score']:.2f})")

        # 2. 测试获取板块变化
        print("\n4️⃣  测试 get_sector_changes_from_signals...")
        up, down, has_sectors, _ = repo.get_sector_changes_from_signals(
            days=30, limit_per_direction=5
        )
        print(f"   上涨板块: {len(up)}, 下跌板块: {len(down)}, has_real={has_sectors}")
        for i, sector in enumerate(up[:3]):
            print(
                f"   ↑ {i+1}. {sector['name']}: +{sector['change_pct']:.2f}% (领头: {sector['leading_stocks'][:2]})"
            )
        for i, sector in enumerate(down[:3]):
            print(
                f"   ↓ {i+1}. {sector['name']}: {sector['change_pct']:.2f}% (领头: {sector['leading_stocks'][:2]})"
            )

        # 3. 检查数据是否足够
        print("\n5️⃣  测试 has_enough_data...")
        enough = repo.has_enough_data()
        print(f"   有足够数据? {enough}")

        print("\n" + "=" * 60)

        # 总结
        print("\n📊 总结:")
        if has_real:
            print("✅ 可以获取到真实的新闻数据！")
        else:
            print("⚠️  无法获取到真实的新闻数据，Dashboard 会使用模拟数据")

        if has_sectors:
            print("✅ 可以获取到真实的板块数据！")
        else:
            print("⚠️  无法获取到真实的板块数据，Dashboard 会使用模拟数据")

        print("\n" + "=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    test_dashboard_repo()
