#!/usr/bin/env python
"""
重新导入+LLM提取脚本 - 从原始数据文件重新摄入，使用 LLM 提取断言和事件

用法：
    python scripts/re_ingest_with_llm.py [--sleep 1] [--dry-run]
"""

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

DATA_FILES = []
for f in sorted(os.listdir(PROJECT_ROOT / "data" / "real")):
    if f.endswith('.json'):
        name = f.replace('.json', '').replace('_', ' ')
        DATA_FILES.append((name, PROJECT_ROOT / "data" / "real" / f))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="重新导入+LLM提取")
    parser.add_argument("--sleep", type=float, default=0.3, help="每条文档间隔(秒)")
    parser.add_argument("--limit", type=int, default=50, help="限制处理数量(0=全部)")
    parser.add_argument("--dry-run", action="store_true", help="只统计不执行")
    parser.add_argument("--model", type=str, default="doubao-seed-2-0-lite-260428", help="提取使用的模型")
    args = parser.parse_args()

    # 1. 统计原始数据
    total_items = 0
    for name, path in DATA_FILES:
        if path.exists():
            data = json.load(open(path, "r", encoding="utf-8"))
            total_items += len(data)
            print(f"  {name}: {len(data)} 条 ({path.name})")
        else:
            print(f"  {name}: 文件不存在 ({path.name})")

    print(f"总计 {total_items} 条原始数据")
    if args.dry_run:
        print("[dry-run] 退出")
        return

    # 2. 清空旧数据
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM assertion")
    del_a = cursor.rowcount
    cursor.execute("DELETE FROM canonical_event")
    del_e = cursor.rowcount
    cursor.execute("DELETE FROM source_document")
    del_d = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"\n已清空旧数据：{del_d} 文档 + {del_a} 断言 + {del_e} 事件")

    # 3. 创建 LLM IngestService
    db_session = SessionLocal()
    try:
        model_gateway = ModelGatewayImpl()
        print(f"使用模型: {args.model}")
        assertion_repo = AssertionRepositoryImpl()
        assertion_repo._db = db_session
        event_repo = EventRepositoryImpl()
        event_repo._db = db_session

        service = IngestService(
            model_gateway=model_gateway,
            assertion_repo=assertion_repo,
            event_repo=event_repo,
        )
        # 设置提取使用的模型
        service._assertion_extractor._model = args.model
        service._event_extractor._model = args.model
        print(f"提取模型: {args.model}")

        # 4. 逐条导入
        success = 0
        fail = 0
        skipped = 0
        total_assertions = 0
        total_events = 0
        start_time = time.time()
        global_idx = 0

        # 获取已存在的 doc_id 集合（用于去重）
        existing_doc_ids = set()
        try:
            conn2 = sqlite3.connect(str(DB_PATH))
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT doc_id FROM source_document")
            existing_doc_ids = {row[0] for row in cursor2.fetchall()}
            conn2.close()
            print(f"已有文档: {len(existing_doc_ids)} 条（增量去重）")
        except Exception:
            print("去重检查失败，将全量导入")

        for name, path in DATA_FILES:
            if not path.exists():
                continue

            data = json.load(open(path, "r", encoding="utf-8"))
            if args.limit > 0:
                remaining = args.limit - (global_idx)
                if remaining <= 0:
                    break
                data = data[:remaining]
            print(f"\n--- 处理 {name} ({len(data)} 条) ---")

            for i, item in enumerate(data):
                global_idx += 1
                try:
                    envelope = DocumentEnvelope(**item)
                    # 去重：检查 doc_id 是否已存在于 DB
                    if existing_doc_ids and envelope.doc_id in existing_doc_ids:
                        skipped += 1
                        continue
                    result = service.ingest_envelope(envelope)
                    success += 1
                    a_count = result.get("assertions_extracted", 0)
                    e_count = result.get("events_extracted", 0)
                    total_assertions += a_count
                    total_events += e_count

                    if (global_idx) % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = global_idx / elapsed if elapsed > 0 else 0
                        print(
                            f"  [{global_idx}/{total_items}] "
                            f"断言累计:{total_assertions} 事件累计:{total_events} | "
                            f"速率:{rate:.1f} docs/s"
                        )

                    if args.sleep > 0 and global_idx < total_items:
                        time.sleep(args.sleep)

                except Exception as e:
                    fail += 1
                    if fail <= 5:
                        print(f"  FAIL [{name}#{i}]: {e}")

                # 每 50 条 commit
                if global_idx % 50 == 0:
                    db_session.commit()

        db_session.commit()

        # 5. 统计
        elapsed = time.time() - start_time
        print(f"\n=== 重新导入+LLM提取完成 ===")
        print(f"  文档: {success} 成功 / {fail} 失败 / {skipped} 跳过(去重) / {len(rows)} 总计")
        print(f"  断言: {total_assertions} 条 (LLM提取)")
        print(f"  事件: {total_events} 条 (LLM提取)")
        print(f"  耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)")

        # 验证 DB
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        for table in ["source_document", "assertion", "canonical_event"]:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  DB {table}: {c.fetchone()[0]}")
        conn.close()

    except Exception as e:
        db_session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
