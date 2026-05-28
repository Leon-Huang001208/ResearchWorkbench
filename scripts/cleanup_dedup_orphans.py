#!/usr/bin/env python3
"""
一次性清理脚本：移除爬虫去重文件中数据库里已不存在的孤儿条目。

背景：
  CLS 爬虫使用文件级去重（DeduplicationStore），独立于数据库。
  如果文档被从 document_v1 删除但去重文件仍保留条目，则重新爬取时
  这些项会被永久跳过（has_reached_watermark / is_processed 直接返回 True）。
  此脚本将去重文件修剪为仅包含数据库中确实存在的文档 ID。

使用：
  python scripts/cleanup_dedup_orphans.py --dry-run    # 预览不执行
  python scripts/cleanup_dedup_orphans.py               # 执行清理
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from core.observability import get_logger
from data_layer.crawlers.cls.utils.deduplication import DeduplicationStore
from data_layer.repositories.base import SessionLocal

logger = get_logger(__name__)

DEDUP_STATE_PATHS = [
    "./data/crawlers/cls/.dedup_state.json",
]


def get_valid_ids(db, source_type: str) -> set:
    """查询数据库中某个 source_type 的所有 source_doc_id"""
    rows = db.execute(
        text(
            "SELECT source_metadata->>'source_doc_id' FROM document_v1 " "WHERE source_type = :st"
        ),
        {"st": source_type},
    ).fetchall()
    return {r[0] for r in rows if r[0]}


def cleanup_state(state_path: str, source_type: str, valid_ids: set, dry_run: bool) -> dict:
    state_file = Path(state_path)
    if not state_file.exists():
        return {"exists": False, "path": state_path}

    store = DeduplicationStore(state_path)
    before = store.get_count()
    orphans = [k for k in store.state.get("processed_items", {}) if str(k) not in valid_ids]

    if dry_run:
        print(f"\n  {source_type} ({state_path}):")
        print(f"    Total processed items: {before}")
        print(f"    Valid items in DB:     {len(valid_ids)}")
        print(f"    Orphans to remove:     {len(orphans)}")
        if orphans:
            print(f"    Sample orphan IDs:     {orphans[:5]}")
    else:
        removed = store.remove_stale(valid_ids)
        print(f"  {source_type}: removed {removed} orphans ({before} → {store.get_count()})")

    return {"exists": True, "before": before, "orphans": len(orphans)}


def main():
    parser = argparse.ArgumentParser(description="清理爬虫去重文件中的孤儿条目")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不执行")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        total_orphans = 0
        for state_path in DEDUP_STATE_PATHS:
            # 从路径推导 source_type（e.g. ./data/crawlers/cls/.dedup_state.json → cls）
            source_type = Path(state_path).parent.name
            valid_ids = get_valid_ids(db, source_type)
            result = cleanup_state(state_path, source_type, valid_ids, args.dry_run)
            if result.get("exists"):
                total_orphans += result.get("orphans", 0)
            else:
                print(f"  {source_type}: state file not found at {state_path}")

        if args.dry_run:
            print(f"\n=== DRY RUN: 共发现 {total_orphans} 个孤儿条目 ===")
            print("运行 python scripts/cleanup_dedup_orphans.py 执行清理")
        else:
            print(f"\n完成。共清理 {total_orphans} 个孤儿条目。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
