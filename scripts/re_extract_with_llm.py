#!/usr/bin/env python
"""
重新提取脚本 - 用 LLM 替代 rule-based 提取断言和事件

用法：
    python scripts/re_extract_with_llm.py [--limit 0] [--sleep 1] [--dry-run]
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.contracts import DocumentEnvelope
from core.model_gateway.gateway import ModelGatewayImpl
from core.observability import get_logger
from core.services.ingest_service import IngestService
from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.event_repository import EventRepositoryImpl

logger = get_logger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "alphafoundry.db"


def main():
    parser = argparse.ArgumentParser(description="重新提取断言和事件")
    parser.add_argument("--limit", type=int, default=0, help="限制处理数量(0=全部)")
    parser.add_argument("--sleep", type=float, default=1.0, help="每条文档间隔(秒)")
    parser.add_argument("--dry-run", action="store_true", help="只统计不执行")
    args = parser.parse_args()

    # 1. 用原始 SQL 读取所有文档（绕过 ORM metadata 冲突）
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM source_document")
    total = cursor.fetchone()[0]

    if args.limit > 0:
        cursor.execute(
            "SELECT doc_id, source_type, title, published_at, source_name, doc_metadata FROM source_document LIMIT ?",
            (args.limit,),
        )
        print(f"限制处理前 {args.limit} 条（总计 {total} 条）")
    else:
        cursor.execute(
            "SELECT doc_id, source_type, title, published_at, source_name, doc_metadata FROM source_document"
        )
        print(f"总计 {total} 篇文档待重新提取")

    rows = cursor.fetchall()
    conn.close()

    if args.dry_run:
        print("[dry-run] 退出")
        return

    # 2. 删除旧的 rule-based 数据
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM assertion WHERE extractor_version = 'rule_v1'")
    del_assertions = cursor.rowcount
    # canonical_event 表没有 extractor_version 列，删除所有旧事件
    cursor.execute("DELETE FROM canonical_event")
    del_events = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"已删除旧数据：{del_assertions} 条断言 + {del_events} 条事件")

    # 3. 创建 LLM 注入的 IngestService
    db_session = SessionLocal()
    try:
        model_gateway = ModelGatewayImpl()
        assertion_repo = AssertionRepositoryImpl()
        assertion_repo._db = db_session
        event_repo = EventRepositoryImpl()
        event_repo._db = db_session

        service = IngestService(
            model_gateway=model_gateway,
            assertion_repo=assertion_repo,
            event_repo=event_repo,
        )

        # 4. 逐条重新提取
        success = 0
        fail = 0
        total_assertions = 0
        total_events = 0
        start_time = time.time()

        for i, row in enumerate(rows):
            try:
                meta = json.loads(row["doc_metadata"]) if row["doc_metadata"] else {}

                envelope = DocumentEnvelope(
                    doc_id=row["doc_id"],
                    source_type=row["source_type"],
                    title=row["title"] or "",
                    published_at=row["published_at"],
                    source_name=row["source_name"],
                    language=meta.get("language", "zh"),
                    metadata=meta,
                    raw_text=meta.get("raw_text", ""),
                    canonical_text=meta.get("canonical_text", ""),
                )

                result = service.ingest_envelope(envelope)
                success += 1
                total_assertions += result.get("assertions_extracted", 0)
                total_events += result.get("events_extracted", 0)

                if (i + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    print(
                        f"  [{i+1}/{len(rows)}] "
                        f"断言累计:{total_assertions} 事件累计:{total_events} | "
                        f"速率:{rate:.1f} docs/s"
                    )

                if args.sleep > 0 and i < len(rows) - 1:
                    time.sleep(args.sleep)

            except Exception as e:
                fail += 1
                if fail <= 5:
                    print(f"  FAIL [{i}]: {e}")

            # 每 50 条 commit 一次
            if (i + 1) % 50 == 0:
                db_session.commit()
                print(f"  [checkpoint] committed at {i+1}")

        db_session.commit()

        # 5. 统计
        elapsed = time.time() - start_time
        print(f"\n=== 重新提取完成 ===")
        print(f"  文档: {success} 成功 / {fail} 失败 / {len(rows)} 总计")
        print(f"  断言: {total_assertions} 条 (LLM提取)")
        print(f"  事件: {total_events} 条 (LLM提取)")
        print(f"  耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)")

    except Exception as e:
        db_session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
