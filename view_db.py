#!/usr/bin/env python3
"""
一键查看数据库内容工具，支持查询事件、文档、断言、信号等数据
"""
import os
import sys

from sqlalchemy import create_engine, text

from core.settings.config import settings


def get_db_url():
    """获取数据库连接地址"""
    # 默认优先从配置取，没有的话找默认SQLite文件
    if hasattr(settings, "DATABASE_URL") and settings.DATABASE_URL:
        return settings.DATABASE_URL
    # 常见默认SQLite路径
    default_paths = [
        "./data/alphafoundry.db",
        "./data/db/alpha_foundry.db",
        "./alpha_foundry.db",
        "/tmp/alpha_foundry.db",
    ]
    for path in default_paths:
        if os.path.exists(path):
            return f"sqlite:///{path}"
    # 都没找到的话提示配置
    print("❌ 未找到数据库文件，请检查配置中的DATABASE_URL，或确认数据库已初始化")
    sys.exit(1)


def query_latest_events(limit=10):
    """查询最新事件"""
    print(f"\n📰 最新 {limit} 条事件：")
    print("-" * 150)
    print(f"{'事件ID':<30} {'类型':<10} {'影响方向':<8} {'置信度':<6} {'发布时间':<25} {'摘要'}")
    print("-" * 150)
    result = db.execute(
        text(
            f"SELECT event_id, event_type, impact_direction, confidence, event_time, summary FROM canonical_event ORDER BY created_at DESC LIMIT {limit}"
        )
    )
    for row in result:
        event_time = row.event_time.isoformat() if row.event_time else "N/A"
        summary = row.summary[:50] + "..." if len(row.summary) > 50 else row.summary
        print(
            f"{row.event_id:<30} {row.event_type:<10} {row.impact_direction:<8} {row.confidence:<6} {event_time:<25} {summary}"
        )


def query_latest_documents(limit=10):
    """查询最新文档"""
    print(f"\n📄 最新 {limit} 条文档：")
    print("-" * 150)
    print(f"{'文档ID':<30} {'类型':<10} {'来源':<15} {'发布时间':<25} {'标题'}")
    print("-" * 150)
    result = db.execute(
        text(
            f"SELECT doc_id, source_type, source_name, published_at, title FROM source_document ORDER BY created_at DESC LIMIT {limit}"
        )
    )
    for row in result:
        published_at = row.published_at.isoformat() if row.published_at else "N/A"
        title = row.title[:50] + "..." if row.title else ""
        title = title[:50] + "..." if len(title) > 50 else title
        print(
            f"{row.doc_id:<30} {row.source_type:<10} {row.source_name:<15} {published_at:<25} {title}"
        )


def query_db_stats():
    """查询数据库统计"""
    print("\n📊 数据库统计：")
    print("-" * 50)
    tables = [
        ("canonical_event", "事件数"),
        ("source_document", "文档数"),
        ("assertion", "断言数"),
    ]
    for table, desc in tables:
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"{desc}: {count}")
        except Exception as e:
            print(f"{desc}: 表不存在 ({e})")


def query_stock_data():
    """查询股票分析数据"""
    print("\n📈 最近股票分析数据：")
    print("-" * 100)
    try:
        result = db.execute(
            text("SELECT canonical_id, as_of FROM asset_snapshot ORDER BY as_of DESC LIMIT 10")
        )
        for row in result:
            as_of = row.as_of.isoformat() if row.as_of else "N/A"
            print(f"股票: {row.canonical_id:<10} 分析时间: {as_of:<25}")
    except Exception as e:
        print(f"股票数据表不存在: {e}")


def run_custom_query(sql):
    """运行自定义SQL查询"""
    print(f"\n⚡ 自定义查询结果: {sql}")
    print("-" * 100)
    try:
        result = db.execute(text(sql))
        columns = list(result.keys())
        print(" | ".join(columns))
        print("-" * 100)
        for row in result:
            print(" | ".join([str(col)[:30] for col in row]))
    except Exception as e:
        print(f"查询失败: {e}")


if __name__ == "__main__":
    # 连接数据库
    db_url = get_db_url()
    print(f"🔌 连接到数据库: {db_url}")
    engine = create_engine(db_url)
    db = engine.connect()

    # 打印帮助
    if len(sys.argv) == 1:
        print("\n📋 使用方法：")
        print("1. 查看统计信息 + 最新10条事件 + 最新10条文档：")
        print("   python view_db.py all\n")
        print("2. 查看最新事件：")
        print("   python view_db.py events [数量，默认10]\n")
        print("3. 查看最新文档：")
        print("   python view_db.py docs [数量，默认10]\n")
        print("4. 查看数据库统计：")
        print("   python view_db.py stats\n")
        print("5. 运行自定义SQL查询：")
        print('   python view_db.py query "SELECT * FROM canonical_event LIMIT 5"\n')

    elif sys.argv[1] == "all":
        query_db_stats()
        query_latest_events()
        query_latest_documents()
        query_stock_data()

    elif sys.argv[1] == "events":
        limit = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
        query_latest_events(limit)

    elif sys.argv[1] == "docs":
        limit = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
        query_latest_documents(limit)

    elif sys.argv[1] == "stats":
        query_db_stats()

    elif sys.argv[1] == "query" and len(sys.argv) >= 3:
        sql = " ".join(sys.argv[2:])
        run_custom_query(sql)

    else:
        print("❌ 无效参数，运行 python view_db.py 查看帮助")

    db.close()
