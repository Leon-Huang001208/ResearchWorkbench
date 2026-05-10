#!/usr/bin/env python3
"""
最小可行闭环演示脚本
真实事件 → 生成信号 → 回测验证 → 记录 Outcome
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from core.observability import get_logger
from core.services.closed_loop_service import ClosedLoopService
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import AlphaSignalDB, CanonicalEvent

logger = get_logger(__name__)


def print_divider(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def check_current_state():
    """检查当前数据库状态"""
    print_divider("1. 当前数据库状态")

    db = SessionLocal()
    try:
        event_count = db.query(CanonicalEvent).count()
        signal_count = db.query(AlphaSignalDB).count()

        print(f"  事件数: {event_count}")
        print(f"  信号数: {signal_count}")

        # 显示一些事件样本
        if event_count > 0:
            print("\n  最近事件:")
            events = (
                db.query(CanonicalEvent).order_by(CanonicalEvent.created_at.desc()).limit(3).all()
            )
            for event in events:
                print(f"    - [{event.event_type}] {event.summary[:60]}...")

        return event_count, signal_count, 0

    finally:
        db.close()


def run_closed_loop():
    """运行完整闭环"""
    print_divider("2. 运行最小可行闭环")
    print("  (使用真实价格数据 - 优先在线获取，失败用本地缓存)")

    service = ClosedLoopService()
    summary = service.run_full_loop()

    return summary


def print_summary(summary: dict):
    """打印闭环摘要"""
    print_divider("3. 闭环结果摘要")

    print(f"  生成信号数: {summary['signals_generated']}")
    print(f"  回测信号数: {summary['signals_backtested']}")
    print()
    print(f"  平均收益: {summary['avg_return']:.2%}")
    print(f"  平均超额收益: {summary['avg_excess_return']:.2%}")
    print(f"  胜率: {summary['win_rate']:.1%}")
    print(f"  方向正确率: {summary['correct_direction_rate']:.1%}")

    if summary["results"]:
        print("\n  逐个信号结果:")
        for r in summary["results"]:
            direction = "✓" if r["direction_correct"] else "✗"
            print(
                f"    {direction} {r['signal_id']} ({r['subject_id']}): "
                f"return={r['return']:.2%}, excess={r['excess_return']:.2%}"
            )


def query_new_data():
    """查询新生成的数据"""
    print_divider("4. 查看新生成的数据")

    db = SessionLocal()
    try:
        # 查询新生成的信号
        signals = (
            db.query(AlphaSignalDB)
            .filter(AlphaSignalDB.event_id.isnot(None))
            .order_by(AlphaSignalDB.created_at.desc())
            .limit(3)
            .all()
        )

        if signals:
            print("\n  新生成的信号:")
            for signal in signals:
                print(f"\n    Signal ID: {signal.signal_id}")
                print(f"    Event ID: {signal.event_id}")
                print(f"    Subject: {signal.subject_id}")
                print(f"    Thesis: {signal.thesis}")
                print(
                    f"    Score: {float(signal.score):.2f}, Confidence: {float(signal.confidence):.2f}"
                )

        # 直接用 SQL 查询回测结果（避免模型问题）
        print("\n  回测结果 (直接 SQL 查询):")
        result = db.execute(
            text(
                "SELECT outcome_id, signal_id, subject_id, outcome_return, outcome_excess_return, lesson FROM signal_outcome ORDER BY created_at DESC LIMIT 3"
            )
        )
        for row in result:
            print(f"\n    Outcome ID: {row[0]}")
            print(f"    Signal ID: {row[1]}")
            print(f"    Subject: {row[2]}")
            print(f"    Return: {float(row[3]):.2%}")
            print(f"    Excess Return: {float(row[4]):.2%}")
            print(f"    Lesson: {row[5]}")

    finally:
        db.close()


def main():
    """主函数"""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 18 + "AlphaFoundry 最小可行闭环演示" + " " * 36 + "║")
    print("╚" + "═" * 78 + "╝")

    # 检查状态
    check_current_state()

    # 运行闭环
    summary = run_closed_loop()

    # 打印摘要
    print_summary(summary)

    # 查询新数据
    query_new_data()

    print_divider("演示完成")
    print("\n  闭环流程已完整运行！")
    print("  你现在可以:")
    print("  1. 用 view_db.py 查看数据库内容")
    print("  2. 查看 API /api/dashboard 获取仪表板数据")
    print("  3. 运行更多次闭环积累历史数据")
    print()


if __name__ == "__main__":
    main()
