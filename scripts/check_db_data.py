#!/usr/bin/env python3
"""检查数据库中的数据量"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_layer.repositories.base import SessionLocal, check_database_connection
from data_layer.repositories.models import (
    AlphaSignalDB,
    CanonicalEvent,
    DocumentV1DB,
    Entity,
    EntityMentionV1DB,
    SignalOutcomeDB,
)


def check_data():
    """检查数据库中的数据"""
    check_database_connection()
    db = SessionLocal()
    try:
        print("=" * 60)
        print("AlphaFoundry 数据库数据检查")
        print("=" * 60)

        # 检查各表的数据量
        doc_count = db.query(DocumentV1DB).count()
        event_count = db.query(CanonicalEvent).count()
        signal_count = db.query(AlphaSignalDB).count()
        entity_count = db.query(Entity).count()
        mention_count = db.query(EntityMentionV1DB).count()
        outcome_count = db.query(SignalOutcomeDB).count()

        print(f"\n📊 DocumentV1（文档）:          {doc_count:4} 条")
        print(f"📰 CanonicalEvent（事件）:      {event_count:4} 条")
        print(f"📈 AlphaSignal（信号）:         {signal_count:4} 条")
        print(f"🏢 Entity（实体）:              {entity_count:4} 条")
        print(f"🔗 EntityMention（实体提及）:  {mention_count:4} 条")
        print(f"📊 SignalOutcome（回测结果）:  {outcome_count:4} 条")

        print("\n" + "=" * 60)

        if doc_count == 0 and event_count == 0 and signal_count == 0:
            print("⚠️  数据库中没有真实数据！Dashboard 将使用模拟数据。")
            print("\n建议执行以下操作之一:")
            print("  1. 运行爬虫摄入数据: python -m app.cli.main ingest")
            print("  2. 访问 Web UI 的 '文档摄入' 页面手动添加数据")
            print("  3. 运行爬虫: python -m app.cli.main crawl run --source cls")
        else:
            print("✅ 数据库中有真实数据！")

            # 显示一些示例数据
            if event_count > 0:
                latest_event = (
                    db.query(CanonicalEvent).order_by(CanonicalEvent.created_at.desc()).first()
                )
                print(
                    f"\n📰 最新事件: {latest_event.summary[:50] if latest_event.summary else '无摘要'}..."
                )
                print(f"   创建时间: {latest_event.created_at}")

            if signal_count > 0:
                latest_signal = (
                    db.query(AlphaSignalDB).order_by(AlphaSignalDB.created_at.desc()).first()
                )
                print(
                    f"\n📈 最新信号: {latest_signal.thesis[:50] if latest_signal.thesis else '无论点'}..."
                )
                print(f"   标的: {latest_signal.subject_id}, 分数: {latest_signal.score}")

        print("\n" + "=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    check_data()
