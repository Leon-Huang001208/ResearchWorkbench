#!/usr/bin/env python3
"""
回补脚本：将磁盘上已有的 PDF 文件注册到 pdf_artifact_v1。

背景：
  P0-1 修复前，ZQ 爬虫下载 PDF 后只保存了元数据 JSON，未注册到数据库。
  导致 PDFConversionService 无法发现这些 PDF。

  此脚本扫描 PDF 目录，为每个文件创建 PDFArtifactV1DB 记录。
  注册后，CrawlScheduler 的 PDF 转换任务（每 5 分钟）会自动拾取并转换。

用法：
  python scripts/backfill_pdf_artifacts.py --dry-run     # 预览不执行
  python scripts/backfill_pdf_artifacts.py                # 执行注册
"""

import argparse
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import PDFArtifactV1DB

logger = get_logger(__name__)

PDF_ROOT = "./data/crawlers/zq/pdfs"


def find_pdf_files(root: str) -> list[dict]:
    """扫描 PDF 目录，返回未注册的 PDF 文件信息列表"""
    pdfs = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            if not fname.lower().endswith(".pdf"):
                continue
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path)
            file_size = os.path.getsize(full_path)
            file_hash = _hash_file(full_path)
            broker = os.path.basename(dirpath)
            pdfs.append(
                {
                    "file_path": rel_path.replace("\\", "/"),
                    "file_name": fname,
                    "file_size": file_size,
                    "file_hash": file_hash,
                    "broker": broker,
                }
            )
    return pdfs


def _hash_file(filepath: str) -> str:
    """计算文件 SHA-256"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_existing_hashes(db) -> set:
    """获取所有已注册的文件哈希"""
    rows = db.execute(text("SELECT file_hash_sha256 FROM pdf_artifact_v1")).fetchall()
    return {r[0] for r in rows if r[0]}


def register_pdfs(pdfs: list[dict], existing_hashes: set, dry_run: bool) -> int:
    """批量注册 PDF 制品"""
    registered = 0
    for p in pdfs:
        if p["file_hash"] in existing_hashes:
            continue
        if dry_run:
            registered += 1
            continue
        try:
            db = SessionLocal()
            try:
                artifact = PDFArtifactV1DB(
                    pdf_id=f"pdf_{uuid.uuid4().hex[:12]}",
                    file_path=p["file_path"],
                    file_name=p["file_name"],
                    file_size_bytes=p["file_size"],
                    file_hash_sha256=p["file_hash"],
                    source_type="zhiqiu_reports",
                    source_name="知丘",
                    source_broker=p["broker"],
                    fetch_timestamp=datetime.now(timezone.utc),
                    parse_status="pending",
                )
                db.add(artifact)
                db.commit()
                registered += 1
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to register {p['file_name']}: {e}")
    return registered


def main():
    parser = argparse.ArgumentParser(description="回补注册磁盘上的 PDF 文件")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不执行")
    args = parser.parse_args()

    if not os.path.isdir(PDF_ROOT):
        print(f"PDF 目录不存在: {PDF_ROOT}")
        return

    pdfs = find_pdf_files(PDF_ROOT)
    print(f"磁盘上 PDF 文件: {len(pdfs)} 个")

    db = SessionLocal()
    try:
        existing_hashes = get_existing_hashes(db)
        print(f"已注册 PDF 制品: {len(existing_hashes)} 个")
    finally:
        db.close()

    new_pdfs = [p for p in pdfs if p["file_hash"] not in existing_hashes]
    print(f"待注册: {len(new_pdfs)} 个")

    if not new_pdfs:
        print("所有 PDF 已注册，无需操作。")
        return

    if args.dry_run:
        print(f"\n=== DRY RUN: 将注册 {len(new_pdfs)} 个 PDF ===")
        for p in new_pdfs[:5]:
            print(f"  {p['file_name']} ({p['broker']})")
        if len(new_pdfs) > 5:
            print(f"  ... 及其他 {len(new_pdfs) - 5} 个")
        print("\n运行 python scripts/backfill_pdf_artifacts.py 执行注册")
        return

    registered = register_pdfs(new_pdfs, existing_hashes, dry_run=False)
    print(f"\n完成。共注册 {registered} 个 PDF 制品。")
    print("CrawlScheduler 将在 5 分钟内自动开始转换。")
    print(f"预计全部转换完成时间: ~{registered * 3 // 60} 分钟（按每 PDF 3 秒估算）")


if __name__ == "__main__":
    main()
