#!/usr/bin/env python3
"""
一次性回补脚本：将缺少 LLM 提取的文档送入摄取队列。

背景：
  deep_backfill_step 和 PDF 转换服务之前保存文档时跳过了 IngestionBridge，
  导致这些文档有 document_v1 行但没有对应的 canonical_event（LLM 提取结果）。

  此脚本找到所有缺少事件的文档，将其入队让 KnowledgePipeline 补做 LLM 提取。

用法：
  python scripts/backfill_missing_llm_extraction.py --dry-run   # 预览不执行
  python scripts/backfill_missing_llm_extraction.py              # 执行入队
  python scripts/backfill_missing_llm_extraction.py --batch 50   # 自定义批次大小
"""

import argparse
import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from core.observability import get_logger
from data_layer.repositories.base import SessionLocal

logger = get_logger(__name__)


def find_missing_docs(db):
    """查找 document_v1 中有但 canonical_event 中没有的文档"""
    result = db.execute(text("""
        SELECT d.doc_id, d.source_type, d.title, d.content,
               d.source_url, d.source_name, d.timeliness
        FROM document_v1 d
        WHERE NOT EXISTS (
            SELECT 1 FROM canonical_event ce
            WHERE ce.source_doc_id = d.doc_id
        )
        ORDER BY d.created_at
    """)).fetchall()
    return result


def build_items(rows):
    """将数据库行转为入队所需的 item dict，按 source_type 分组"""
    import json

    items_by_source = {}
    for row in rows:
        doc_id, source_type, title, content, source_url, source_name, timeliness = row

        published_at = None
        if timeliness:
            try:
                if isinstance(timeliness, str):
                    timeliness = json.loads(timeliness)
                if isinstance(timeliness, dict):
                    pt = timeliness.get("publish_time")
                    if pt:
                        published_at = pt if isinstance(pt, str) else str(pt)
            except (json.JSONDecodeError, TypeError):
                pass

        item = {
            "id": doc_id,
            "title": title or "",
            "content": content or "",
            "url": source_url or "",
            "published_at": published_at,
            "source_name": source_name or source_type,
        }

        items_by_source.setdefault(source_type, []).append(item)

    return items_by_source


def enqueue_items(items_by_source, batch_size: int, dry_run: bool):
    """按 source_type 分批入队"""
    # 延迟导入避免循环依赖
    from services.crawl_orchestrator import CrawlOrchestrator

    total = sum(len(v) for v in items_by_source.values())
    if dry_run:
        print(f"\n=== DRY RUN: 将入队 {total} 个文档 ===")
        for st, items in sorted(items_by_source.items()):
            print(f"  {st}: {len(items)} 个")
        return

    enqueued = 0
    for source_type_str, items in sorted(items_by_source.items()):
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            CrawlOrchestrator._enqueue_items(source_type_str, batch)
            enqueued += len(batch)
            logger.info(
                "Backfill enqueue progress",
                enqueued=enqueued,
                total=total,
                source_type=source_type_str,
            )
            print(f"  已入队 {enqueued}/{total} ({source_type_str})...")

    logger.info("Backfill enqueue completed", enqueued=enqueued, total=total)
    print(f"\n完成。共入队 {enqueued} 个文档到摄取队列。")
    print("Knowledge Worker 将自动消费并执行 LLM 提取。")

    # 预估处理时间
    print(f"预计处理时间: ~{enqueued * 3 // 60} 分钟（按每文档 3 秒估算）")


def main():
    parser = argparse.ArgumentParser(description="回补缺失 LLM 提取的文档")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不入队")
    parser.add_argument("--batch", type=int, default=100, help="每批入队数量 (默认 100)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = find_missing_docs(db)
        if not rows:
            print("所有文档都有 LLM 提取，无需回补。")
            return

        print(f"发现 {len(rows)} 个文档缺少 LLM 提取")
        items_by_source = build_items(rows)
        enqueue_items(items_by_source, args.batch, args.dry_run)
    finally:
        db.close()


if __name__ == "__main__":
    main()
