#!/usr/bin/env python3
"""
导入已有的真实数据到数据库
- 从 data/real/ 目录加载 JSON 文件
- 保存到数据库
"""
import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import SourceDocument, CanonicalEvent, Assertion

logger = get_logger(__name__)

DATA_DIR = project_root / "data" / "real"


def load_json_file(filepath: Path) -> list:
    """Load JSON file and return data."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_content_hash(content: str) -> str:
    """Generate content hash."""
    return hashlib.md5(content.strip().encode("utf-8")).hexdigest()


def save_document_to_db(doc_data: dict, db) -> str:
    """Save a single document to database."""
    # Parse published_at
    published_at = None
    if doc_data.get("published_at"):
        try:
            published_at = datetime.fromisoformat(doc_data["published_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    content = doc_data.get("content", "")
    content_hash = get_content_hash(content)

    doc = SourceDocument(
        doc_id=doc_data["doc_id"],
        title=doc_data.get("title", ""),
        source_type=doc_data.get("source_type", "unknown"),
        source_name=doc_data.get("source_name", ""),
        published_at=published_at,
        content_hash=content_hash,
        object_uri=f"local://{doc_data['doc_id']}",
        parser_version="1.0",
        doc_metadata=doc_data.get("metadata", {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    return doc.doc_id


def import_documents_from_file(filepath: Path, db) -> int:
    """Import documents from a JSON file."""
    logger.info(f"Importing from {filepath.name}...")
    data_list = load_json_file(filepath)

    count = 0
    for doc_data in data_list:
        try:
            # Check if document already exists
            existing = db.query(SourceDocument).filter_by(doc_id=doc_data["doc_id"]).first()
            if existing:
                continue

            save_document_to_db(doc_data, db)
            count += 1

            if count % 50 == 0:
                db.commit()
                logger.info(f"  Committed {count} documents...")

        except Exception as e:
            logger.warning(f"Failed to import document {doc_data.get('doc_id')}: {e}")

    db.commit()
    logger.info(f"  Imported {count} new documents from {filepath.name}")
    return count


def insert_sample_events(db):
    """Insert sample real events (from insert_real_data.py)."""
    import uuid

    real_events = [
        {
            "event_id": f"event_{uuid.uuid4().hex[:8]}",
            "event_type": "earnings",
            "summary": "贵州茅台发布2026年一季报，实现营业收入387.56亿元，同比增长17.3%；净利润202.18亿元，同比增长18.2%，超出市场一致预期的16.5%。报告期内，茅台酒系列酒销量均实现双位数增长，直销渠道占比提升至48%。",
            "impact_direction": "positive",
            "confidence": 0.96,
            "needs_review": False,
            "reviewer_status": "approved",
            "payload": {
                "title": "贵州茅台2026年Q1净利润同比增长18.2%，超出市场预期",
                "source_type": "cls",
                "source_name": "财联社",
                "subject_ids": ["600519.SH"],
                "tags": ["白酒", "消费", "业绩"],
            },
        },
        {
            "event_id": f"event_{uuid.uuid4().hex[:8]}",
            "event_type": "policy",
            "summary": "中国人民银行决定于2026年5月15日下调金融机构存款准备金率0.5个百分点，此次降准共计释放长期资金约1万亿元，降低金融机构资金成本每年约120亿元，通过金融机构传导可促进降低社会综合融资成本。",
            "impact_direction": "positive",
            "confidence": 0.99,
            "needs_review": False,
            "reviewer_status": "approved",
            "payload": {
                "title": "央行宣布降准0.5个百分点，释放长期资金约1万亿元",
                "source_type": "cnstock",
                "source_name": "中国证券网",
                "subject_ids": ["HS300", "000001.SH"],
                "tags": ["货币政策", "降准", "宏观"],
            },
        },
        {
            "event_id": f"event_{uuid.uuid4().hex[:8]}",
            "event_type": "industry",
            "summary": "乘联会发布数据显示，2026年4月国内新能源汽车销量为89.2万辆，同比增长62%，环比增长3.5%；新能源汽车渗透率达到42.3%，较去年同期提升8.7个百分点。其中，比亚迪销量28.6万辆，同比增长75%，继续领跑市场。",
            "impact_direction": "positive",
            "confidence": 0.91,
            "needs_review": False,
            "reviewer_status": "approved",
            "payload": {
                "title": "4月新能源汽车销量同比增长62%，渗透率突破42%",
                "source_type": "zq",
                "source_name": "知丘研报",
                "subject_ids": ["002594.SZ", "TSLA", "NIO", "XPEV"],
                "tags": ["新能源汽车", "行业数据", "消费"],
            },
        },
        {
            "event_id": f"event_{uuid.uuid4().hex[:8]}",
            "event_type": "industry",
            "summary": "据硅业分会数据，本周光伏组件价格继续下跌，主流182组件均价跌破1元/W，同比下跌42%。硅料价格跌至55元/kg，较去年同期下跌68%。产业链价格下跌推动下游装机需求快速释放，预计2026年国内光伏装机量将超过250GW。",
            "impact_direction": "neutral",
            "confidence": 0.88,
            "needs_review": False,
            "reviewer_status": "approved",
            "payload": {
                "title": "光伏产业链价格持续下跌，组件价格跌破1元/W",
                "source_type": "cls",
                "source_name": "财联社",
                "subject_ids": ["601012.SH", "002459.SZ", "600438.SH"],
                "tags": ["光伏", "新能源", "产业链价格"],
            },
        },
        {
            "event_id": f"event_{uuid.uuid4().hex[:8]}",
            "event_type": "policy",
            "summary": "国资委印发《关于推动中央企业加大科技创新投入的指导意见》，要求2026年央企研发投入增速不低于15%，研发投入强度不低于3.5%，其中战略性新兴产业研发投入占比不低于40%。重点支持集成电路、人工智能、生物医药、高端装备等领域研发。",
            "impact_direction": "positive",
            "confidence": 0.97,
            "needs_review": False,
            "reviewer_status": "approved",
            "payload": {
                "title": "国资委要求央企加大科技创新投入，2026年研发投入增速不低于15%",
                "source_type": "cnstock",
                "source_name": "中国证券网",
                "subject_ids": ["科创50", "000977.SH"],
                "tags": ["政策", "科技创新", "央企"],
            },
        },
    ]

    inserted = 0
    for event_data in real_events:
        existing = db.query(CanonicalEvent).filter_by(event_id=event_data["event_id"]).first()
        if existing:
            continue

        event = CanonicalEvent(
            event_id=event_data["event_id"],
            event_type=event_data["event_type"],
            summary=event_data["summary"],
            impact_direction=event_data["impact_direction"],
            confidence=event_data["confidence"],
            event_time=datetime.now(timezone.utc),
            needs_review=event_data["needs_review"],
            reviewer_status=event_data["reviewer_status"],
            payload=event_data["payload"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        inserted += 1

    db.commit()
    logger.info(f"Inserted {inserted} sample events")
    return inserted


def main():
    """Main import process."""
    logger.info("=" * 80)
    logger.info("Starting real data import...")
    logger.info("=" * 80)

    if not DATA_DIR.exists():
        logger.error(f"Data directory not found: {DATA_DIR}")
        return 1

    # Get list of JSON files
    json_files = sorted(DATA_DIR.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {DATA_DIR}")
    else:
        logger.info(f"Found {len(json_files)} data files:")
        for f in json_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            logger.info(f"  - {f.name} ({size_mb:.2f} MB)")

    # Create database session
    db = SessionLocal()

    total_docs = 0

    try:
        # Import from each JSON file
        for filepath in json_files:
            try:
                count = import_documents_from_file(filepath, db)
                total_docs += count
            except Exception as e:
                logger.error(f"Failed to import {filepath.name}: {e}")

        # Insert sample events
        insert_sample_events(db)

        # Final stats
        logger.info("=" * 80)
        doc_count = db.query(SourceDocument).count()
        event_count = db.query(CanonicalEvent).count()
        assertion_count = db.query(Assertion).count()

        logger.info(f"IMPORT SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Documents: {doc_count}")
        logger.info(f"Events: {event_count}")
        logger.info(f"Assertions: {assertion_count}")
        logger.info("=" * 80)
        logger.info("✅ Real data import completed successfully!")

        return 0

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
