"""后台知识处理 Worker — 常驻消费 ingestion_queue，自动跑 KnowledgePipeline"""

import asyncio
import os
from typing import Any, Dict

from core.observability import get_logger
from core.services.system_event_bus import event_bus

logger = get_logger(__name__)

POLL_INTERVAL = float(os.environ.get("KNOWLEDGE_WORKER_POLL_INTERVAL", "3"))
BATCH_SIZE = int(os.environ.get("KNOWLEDGE_WORKER_BATCH_SIZE", "10"))
WORKER_NAME = "knowledge_worker"


def _create_document_v1(item: Any) -> Any:
    """从 IngestionQueueItem 创建 DocumentV1"""
    from core.contracts.documents_v1 import DocType, DocumentTimeliness, DocumentV1, SourceType

    source_type_map = {
        "cls": SourceType.CLS,
        "cnstock": SourceType.CNSTOCK,
        "zq": SourceType.ZHIQIU_REPORTS,
        "report": SourceType.ZHIQIU_REPORTS,
        "pdf": SourceType.ZHIQIU_REPORTS,
        "manual": SourceType.CNSTOCK,
    }
    doc_type_map = {
        "cls": DocType.NEWS,
        "cnstock": DocType.NEWS,
        "zq": DocType.REPORT,
        "report": DocType.REPORT,
        "pdf": DocType.REPORT,
        "manual": DocType.INTERNAL_NOTE,
    }

    return DocumentV1(
        doc_id=item.source_id or item.item_id,
        doc_type=doc_type_map.get(item.source_type, DocType.NEWS),
        source_type=source_type_map.get(item.source_type, SourceType.CLS),
        title=item.title or "",
        content=item.raw_content,
        source_name=item.source_type,
        source_url=item.url,
        timeliness=DocumentTimeliness(publish_time=item.published_at),
    )


async def process_one(item: Any) -> Dict[str, Any]:
    """处理单个队列项：DocumentV1 -> KnowledgePipeline -> 标记完成/失败"""
    from ingestion.knowledge_pipeline import KnowledgePipeline, PipelineConfig

    config = PipelineConfig(auto_save=False)
    pipeline = KnowledgePipeline(config=config)
    doc = _create_document_v1(item)
    result = await pipeline.process(doc)

    await event_bus.publish(
        "document_parsed",
        {
            "item_id": item.item_id,
            "doc_id": doc.doc_id,
            "title": item.title,
            "source_type": item.source_type,
            "event_count": len(result.events),
            "entity_count": len(result.entities),
        },
    )

    for event in result.events:
        await event_bus.publish(
            "event_created",
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "summary": event.summary,
                "doc_id": doc.doc_id,
            },
        )

    return {
        "item_id": item.item_id,
        "doc_id": doc.doc_id,
        "events": len(result.events),
        "entities": len(result.entities),
    }


async def main() -> None:
    """主循环：持续消费 ingestion_queue"""
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.ingestion_repository import IngestionQueueRepository

    logger.info(
        "Knowledge worker starting",
        poll_interval=POLL_INTERVAL,
        batch_size=BATCH_SIZE,
    )

    while True:
        db = SessionLocal()
        try:
            repo = IngestionQueueRepository(db)
            items = repo.dequeue(limit=BATCH_SIZE)

            if not items:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            for item in items:
                try:
                    result = await process_one(item)
                    repo.mark_completed(item.item_id)
                    logger.info("Item processed", **result)
                except Exception as e:
                    repo.mark_failed(item.item_id, str(e))
                    logger.error(
                        "Item processing failed",
                        item_id=item.item_id,
                        error=str(e),
                        exc_info=True,
                    )
                    await event_bus.publish(
                        "error_alert",
                        {"item_id": item.item_id, "error": str(e), "worker": WORKER_NAME},
                    )

            event_bus.record_worker_heartbeat(WORKER_NAME)
            await event_bus.publish(
                "queue_update",
                {"processed": len(items), "worker": WORKER_NAME},
            )

        except Exception as e:
            logger.error("Worker loop error", error=str(e), exc_info=True)
            await asyncio.sleep(POLL_INTERVAL)
        finally:
            db.close()


if __name__ == "__main__":
    asyncio.run(main())
