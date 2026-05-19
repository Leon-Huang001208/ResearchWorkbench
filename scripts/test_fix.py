#!/usr/bin/env python3
"""测试 DashboardService 修复"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.services.dashboard_service import DashboardService
from data_layer.repositories.base import SessionLocal, check_database_connection


def test_dashboard_service():
    """测试 DashboardService 的修复"""
    check_database_connection()
    db = SessionLocal()
    try:
        print("=" * 60)
        print("测试 DashboardService 修复")
        print("=" * 60)

        service = DashboardService(db)

        # 测试市场概览
        print("\n1️⃣  测试 get_market_overview_section...")
        market_overview = service.get_market_overview_section()

        print(f"\n📰 全球新闻: {len(market_overview.global_news)} 条")
        for i, news in enumerate(market_overview.global_news[:3]):
            mock_label = " (模拟)" if news.is_mock else " (真实)"
            print(f"   {i+1}. {news.title[:50]}...{mock_label}")

        print(f"\n📈 上涨板块: {len(market_overview.top_up_sectors)} 个")
        for i, sector in enumerate(market_overview.top_up_sectors[:3]):
            mock_label = " (模拟)" if sector.is_mock else " (真实)"
            print(f"   {i+1}. {sector.name}: +{sector.change_pct:.2f}%{mock_label}")

        print(f"\n📉 下跌板块: {len(market_overview.top_down_sectors)} 个")
        for i, sector in enumerate(market_overview.top_down_sectors[:3]):
            mock_label = " (模拟)" if sector.is_mock else " (真实)"
            print(f"   {i+1}. {sector.name}: {sector.change_pct:.2f}%{mock_label}")

        print("\n📊 数据来源标识:")
        print(f"   uses_real_news: {market_overview.uses_real_news}")
        print(f"   uses_real_sectors: {market_overview.uses_real_sectors}")
        print(f"   last_updated: {market_overview.last_updated}")

        # 检查结果
        print("\n" + "=" * 60)
        print("\n✅ 检查结果:")
        all_good = True

        if market_overview.uses_real_news:
            print("✅ 新闻数据使用真实数据！")
        else:
            print("⚠️  新闻数据使用模拟数据")
            all_good = False

        if market_overview.uses_real_sectors:
            print("✅ 板块数据使用真实数据！")
        else:
            print("⚠️  板块数据使用模拟数据")
            all_good = False

        # 检查是否有混合真实/模拟数据
        real_news_count = sum(1 for n in market_overview.global_news if not n.is_mock)
        mock_news_count = sum(1 for n in market_overview.global_news if n.is_mock)
        real_sectors_up = sum(1 for s in market_overview.top_up_sectors if not s.is_mock)
        real_sectors_down = sum(1 for s in market_overview.top_down_sectors if not s.is_mock)

        print("\n📊 详细统计:")
        print(f"   真实新闻: {real_news_count} 条, 模拟新闻: {mock_news_count} 条")
        print(f"   真实上涨板块: {real_sectors_up} 个")
        print(f"   真实下跌板块: {real_sectors_down} 个")

        print("\n" + "=" * 60)

        if all_good:
            print("\n🎉 所有修复正常工作！Dashboard 现在会显示真实数据！")
        else:
            print("\n⚠️  仍有部分数据使用模拟，请检查数据库")

        print("\n" + "=" * 60)

        # 测试其他板块
        print("\n2️⃣  测试 get_today_section...")
        today = service.get_today_section()
        print(f"   新事件: {len(today.new_events)} 个")
        print(f"   高优先级论题: {len(today.high_priority_theses)} 个")
        print(f"   异常流向: {len(today.abnormal_flows)} 个")

        print("\n3️⃣  测试 get_research_queue_section...")
        queue = service.get_research_queue_section()
        print(f"   待处理断言: {len(queue.pending_assertions)} 个")
        print(f"   缺失证据: {len(queue.missing_evidence)} 个")
        print(f"   待映射审查: {len(queue.mapping_reviews)} 个")

        print("\n4️⃣  测试 get_candidate_board_section...")
        candidates = service.get_candidate_board_section()
        print(f"   Top 候选: {len(candidates.top_candidates)} 个")

        print("\n5️⃣  测试 get_learning_section...")
        learning = service.get_learning_section()
        print(f"   最近失败: {len(learning.recent_failures)} 个")
        print(f"   最佳表现事件类型: {len(learning.best_event_types)} 个")
        print(f"   每周经验: {len(learning.weekly_lessons)} 个")

        print("\n" + "=" * 60)
        print("\n✅ 所有 DashboardService 功能测试完成！")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    test_dashboard_service()
