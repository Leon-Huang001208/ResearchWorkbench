"""后台知识处理 Worker — 常驻消费 ingestion_queue，并发运行 KnowledgePipeline"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.observability import get_logger
from services.system_event_bus import event_bus

logger = get_logger(__name__)

# 优先使用环境变量，打包部署（Tauri sidecar）时 __file__ 指向 exe 内部路径失效
PROJECT_DIR = (
    Path(os.environ["ALPHAFOUNDRY_PROJECT_ROOT"])
    if "ALPHAFOUNDRY_PROJECT_ROOT" in os.environ
    else Path(__file__).resolve().parent.parent
)

POLL_INTERVAL = float(os.environ.get("KNOWLEDGE_WORKER_POLL_INTERVAL", "1"))
BATCH_SIZE = int(os.environ.get("KNOWLEDGE_WORKER_BATCH_SIZE", "10"))
MAX_CONCURRENCY = int(os.environ.get("KNOWLEDGE_WORKER_MAX_CONCURRENCY", "8"))
SHUTDOWN_TIMEOUT = int(os.environ.get("KNOWLEDGE_WORKER_SHUTDOWN_TIMEOUT", "60"))
MAX_BACKOFF = float(os.environ.get("KNOWLEDGE_WORKER_MAX_BACKOFF", "60"))
ITEM_PROCESSING_TIMEOUT = float(os.environ.get("KNOWLEDGE_WORKER_ITEM_TIMEOUT", "300"))
STUCK_RECOVERY_MINUTES = int(os.environ.get("KNOWLEDGE_WORKER_STUCK_RECOVERY_MINUTES", "5"))
MAX_RESTARTS = int(os.environ.get("KNOWLEDGE_WORKER_MAX_RESTARTS", "10"))
RESTART_COOLDOWN = float(os.environ.get("KNOWLEDGE_WORKER_RESTART_COOLDOWN", "300"))
DISABLED_EXTRACTION_SOURCES = {
    source.strip()
    for source in os.environ.get("KNOWLEDGE_WORKER_DISABLED_EXTRACTION_SOURCES", "cninfo").split(
        ","
    )
    if source.strip()
}
WORKER_NAME = "knowledge_worker"


def _pid_file_for(worker_id: Optional[int] = None) -> Path:
    if worker_id is not None:
        return PROJECT_DIR / "logs" / f"knowledge_worker_{worker_id}.pid"
    return PROJECT_DIR / "logs" / "knowledge_worker.pid"


def _write_pid(worker_id: Optional[int] = None) -> None:
    pid_file = _pid_file_for(worker_id)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))


def _remove_pid(worker_id: Optional[int] = None) -> None:
    pid_file = _pid_file_for(worker_id)
    if pid_file.exists():
        pid_file.unlink()


def _heartbeat_file_for(worker_label: str) -> Path:
    return PROJECT_DIR / "logs" / f"{worker_label}.heartbeat.json"


def _write_heartbeat(worker_label: str, activity: str) -> None:
    hb_file = _heartbeat_file_for(worker_label)
    hb_file.parent.mkdir(parents=True, exist_ok=True)
    hb_file.write_text(
        json.dumps(
            {
                "timestamp": time.time(),
                "activity": activity,
            },
            ensure_ascii=False,
        )
    )


def _recover_stuck_items(db_session: Any) -> int:
    """将卡在 processing 状态超过 STUCK_RECOVERY_MINUTES 分钟的 item 重置为 pending"""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import and_, or_

    from data_layer.repositories.models import IngestionQueueItemDB

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_RECOVERY_MINUTES)
    stuck = (
        db_session.query(IngestionQueueItemDB)
        .filter(
            IngestionQueueItemDB.status == "processing",
            or_(
                IngestionQueueItemDB.processed_at < cutoff,
                and_(
                    IngestionQueueItemDB.processed_at.is_(None),
                    IngestionQueueItemDB.created_at < cutoff,
                ),
            ),
        )
        .limit(BATCH_SIZE)
        .all()
    )
    if stuck:
        for item in stuck:
            item.status = "pending"
        db_session.flush()
        logger.warning(
            "Recovered stuck processing items",
            count=len(stuck),
            cutoff=cutoff.isoformat(),
        )
    return len(stuck)


def _create_document_v1(item: Any) -> Any:
    """从 IngestionQueueItem 创建 DocumentV1"""
    import hashlib

    from core.contracts.documents_v1 import DocType, DocumentTimeliness, DocumentV1, SourceType

    source_type_map = {
        "cls": SourceType.CLS,
        "cnstock": SourceType.CNSTOCK,
        "cnstock_flash": SourceType.CNSTOCK_FLASH,
        "cninfo": SourceType.CNINFO,
        "zq": SourceType.ZHIQIU_REPORTS,
        "zhiqiu_reports": SourceType.ZHIQIU_REPORTS,
        "zhiqiu_wechat": SourceType.ZHIQIU_WECHAT,
        "zhiqiu_transcript": SourceType.ZHIQIU_TRANSCRIPT,
        "report": SourceType.ZHIQIU_REPORTS,
        "pdf": SourceType.ZHIQIU_REPORTS,
        "manual": SourceType.CNSTOCK,
    }
    doc_type_map = {
        "cls": DocType.TELEGRAM,
        "cnstock": DocType.NEWS,
        "cnstock_flash": DocType.TELEGRAM,
        "cninfo": DocType.FILING,
        "zq": DocType.REPORT,
        "zhiqiu_reports": DocType.REPORT,
        "zhiqiu_wechat": DocType.WECHAT,
        "zhiqiu_transcript": DocType.TRANSCRIPT,
        "report": DocType.REPORT,
        "pdf": DocType.REPORT,
        "manual": DocType.INTERNAL_NOTE,
    }

    return DocumentV1(
        doc_id=item.source_id or item.item_id,
        doc_type=doc_type_map.get(item.source_type, DocType.NEWS),
        source_type=source_type_map.get(item.source_type, SourceType.OTHER),
        title=item.title or "",
        content=item.raw_content,
        doc_metadata={
            "queue_item_id": item.item_id,
            "source_id": item.source_id,
        },
        source_metadata={
            "source_doc_id": item.source_id or item.item_id,
            "queue_item_id": item.item_id,
        },
        source_name=item.source_type,
        source_url=item.url,
        content_hash=hashlib.sha256((item.raw_content or "").encode("utf-8")).hexdigest(),
        timeliness=DocumentTimeliness(publish_time=_parse_published_at(item.published_at)),
    )


def _grade_document_quality(doc: Any) -> Any:
    """用 SourceGrader 回填 doc.quality 的分级字段（source_tier/trust/freshness）.

    报告编译器第二阶段：从 SourceSpec 推导 reliability 并计算来源分级，
    使后续检索与引用绑定能按 tier 排序优先锚定高可信来源。
    """
    try:
        from core.services.source_grader import SourceGrader

        SourceGrader().grade_inplace(doc)
    except Exception as e:
        logger.warning(
            "Source grading failed, leaving quality default",
            doc_id=getattr(doc, "doc_id", None),
            error=str(e),
        )
    return doc


def _parse_published_at(value: Any) -> Any:
    """Parse queue published_at text into datetime when possible."""
    from datetime import datetime

    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _create_source_document_envelope(item: Any, doc: Any) -> Any:
    """Create SourceDocument-compatible envelope for FK-backed event persistence."""
    import hashlib

    from core.contracts import DocumentEnvelope

    content_hash = (
        doc.content_hash or hashlib.sha256((item.raw_content or "").encode("utf-8")).hexdigest()
    )
    return DocumentEnvelope(
        doc_id=doc.doc_id,
        source_type=item.source_type,
        title=item.title or "",
        published_at=_parse_published_at(item.published_at),
        source_name=item.source_type,
        language="zh",
        metadata={
            "content_hash": content_hash,
            "parser_version": "knowledge_worker.v1",
            "object_uri": item.url or f"ingestion_queue://{item.item_id}",
            "url": item.url,
            "queue_item_id": item.item_id,
            "source_id": item.source_id,
        },
        raw_text=item.raw_content,
        canonical_text=item.raw_content,
    )


async def process_one(item: Any, pipeline: Any) -> Dict[str, Any]:
    """处理单个队列项：DocumentV1 -> KnowledgePipeline -> 发布事件（带超时保护）"""
    doc = _create_document_v1(item)
    _grade_document_quality(doc)
    result = await asyncio.wait_for(pipeline.process(doc), timeout=ITEM_PROCESSING_TIMEOUT)

    doc_payload = {
        "item_id": item.item_id,
        "doc_id": doc.doc_id,
        "title": item.title,
        "source_type": item.source_type,
        "event_count": len(result.events),
        "entity_count": len(result.entities),
    }
    await event_bus.publish("document_parsed", doc_payload)
    try:
        from services.pipeline_monitor import pipeline_monitor

        pipeline_monitor.record_event("document_parsed", doc_payload)
    except Exception:
        pass

    for event in result.events:
        event_payload = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "summary": event.summary,
            "doc_id": doc.doc_id,
        }
        await event_bus.publish("event_created", event_payload)
        try:
            from services.pipeline_monitor import pipeline_monitor

            pipeline_monitor.record_event("event_created", event_payload)
        except Exception:
            pass

    return {
        "item_id": item.item_id,
        "doc_id": doc.doc_id,
        "doc": doc,
        "events": len(result.events),
        "entities": len(result.entities),
        "event_list": result.events,
        "entity_list": result.entities,
        "assertions": len(result.assertions),
        "assertion_list": result.assertions,
        "chunks": len(result.chunks),
        "chunk_list": result.chunks,
    }


def _persist_extraction_artifacts(db: Any, result: Dict[str, Any]) -> None:
    """持久化 chunks / entity_mentions / assertions（facts store 打通）.

    所有写入失败均降级为 warning，不阻断 item 完成标记——facts store 是报告编译器
    的增量数据源，单条 item 的部分持久化失败不应让整条队列项回滚重试（会重复跑 LLM）。
    """
    from core.contracts import EntityMentionV1
    from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
    from data_layer.repositories.documents_v1 import (
        DocumentChunkV1Repository,
        EntityMentionV1Repository,
    )

    # chunks
    chunk_list = result.get("chunk_list") or []
    if chunk_list:
        try:
            chunk_repo = DocumentChunkV1Repository(db)
            chunk_repo.bulk_create(chunk_list)
            logger.debug("Persisted chunks", doc_id=result.get("doc_id"), count=len(chunk_list))
        except Exception as e:
            logger.warning(
                "Failed to persist chunks",
                doc_id=result.get("doc_id"),
                error=str(e),
            )

    # entity_mentions（pipeline 输出为 dict 列表，重建为 EntityMentionV1）
    entity_list = result.get("entity_list") or []
    if entity_list:
        mentions: list[EntityMentionV1] = []
        for ent in entity_list:
            try:
                if isinstance(ent, EntityMentionV1):
                    mentions.append(ent)
                elif isinstance(ent, dict):
                    # entity_id 是原始名/代码，非规范化实体 FK，置 None 避免约束失败
                    data = dict(ent)
                    data["entity_id"] = None
                    mentions.append(EntityMentionV1(**data))
            except Exception:
                continue
        if mentions:
            try:
                mention_repo = EntityMentionV1Repository(db)
                mention_repo.bulk_create(mentions)
                logger.debug(
                    "Persisted entity mentions",
                    doc_id=result.get("doc_id"),
                    count=len(mentions),
                )
            except Exception as e:
                logger.warning(
                    "Failed to persist entity mentions",
                    doc_id=result.get("doc_id"),
                    error=str(e),
                )

    # assertions（source_doc_id FK 已由 source_document 保存满足）
    assertion_list = result.get("assertion_list") or []
    if assertion_list:
        assertion_repo = AssertionRepositoryImpl(db)
        saved = 0
        for assertion in assertion_list:
            try:
                assertion_repo.save(assertion)
                saved += 1
            except Exception as e:
                logger.warning(
                    "Failed to persist assertion",
                    assertion_id=getattr(assertion, "assertion_id", None),
                    error=str(e),
                )
        if saved:
            logger.debug(
                "Persisted assertions",
                doc_id=result.get("doc_id"),
                saved=saved,
                total=len(assertion_list),
            )


def _processed_item_log_fields(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return compact log fields without raw document content."""
    doc = result.get("doc")
    return {
        "item_id": result.get("item_id"),
        "doc_id": result.get("doc_id"),
        "title": getattr(doc, "title", None),
        "source_type": getattr(doc, "source_type", None),
        "content_hash": getattr(doc, "content_hash", None),
        "events": result.get("events"),
        "entities": result.get("entities"),
        "assertions": result.get("assertions"),
        "chunks": result.get("chunks"),
    }


async def _process_and_mark(
    item: Any, semaphore: asyncio.Semaphore, pipeline: Any
) -> Dict[str, Any] | None:
    """带并发控制的单 item 处理，每个 item 使用独立的 DB 会话"""
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.document_repository import DocumentRepositoryImpl
    from data_layer.repositories.documents_v1 import DocumentV1Repository
    from data_layer.repositories.event_repository import EventRepositoryImpl
    from data_layer.repositories.ingestion_repository import IngestionQueueRepository

    async with semaphore:
        db = SessionLocal()
        try:
            if item.source_type in DISABLED_EXTRACTION_SOURCES:
                from datetime import datetime, timezone

                from data_layer.repositories.models import IngestionQueueItemDB

                db_item = db.query(IngestionQueueItemDB).filter_by(item_id=item.item_id).first()
                if db_item is not None:
                    db_item.retry_count = db_item.max_retries
                    db_item.status = "failed"
                    db_item.failure_reason = (
                        f"Extraction disabled for source_type={item.source_type}"
                    )
                    db_item.processed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(
                    "Item skipped because extraction is disabled",
                    item_id=item.item_id,
                    source_type=item.source_type,
                )
                return None

            result = await process_one(item, pipeline)

            # Persist source documents BEFORE events to satisfy source_document FK.
            doc_repo = DocumentV1Repository(db)
            doc_repo.create(result["doc"])
            source_doc_repo = DocumentRepositoryImpl(db)
            source_doc_repo.save(_create_source_document_envelope(item, result["doc"]))

            # 持久化 chunks / entity_mentions / assertions（打通 facts store）。
            # chunks.doc_id FK → document_v1；assertion.source_doc_id FK → source_document，
            # 均已在上面保存，顺序安全。失败不阻断主流程，仅记录 warning。
            _persist_extraction_artifacts(db, result)

            # Persist events to DB BEFORE marking item completed.
            if result["event_list"]:
                event_repo = EventRepositoryImpl(db)
                for event in result["event_list"]:
                    try:
                        event_repo.save(event)
                    except Exception as e:
                        logger.warning(
                            "Failed to save event",
                            event_id=event.event_id,
                            error=str(e),
                        )

            repo = IngestionQueueRepository(db)
            repo.mark_completed(item.item_id)
            db.commit()
            logger.info(
                "Item processed",
                **_processed_item_log_fields(result),
            )
            return result
        except Exception as e:
            repo = IngestionQueueRepository(db)
            repo.mark_failed(item.item_id, str(e))
            db.commit()
            try:
                logger.error(
                    "Item processing failed",
                    item_id=item.item_id,
                    error=str(e),
                    exc_info=True,
                )
            except Exception:
                pass  # 日志编码失败（如 Windows GBK + 非 ASCII 字符）时不影响后续逻辑
            await event_bus.publish(
                "error_alert",
                {"item_id": item.item_id, "error": str(e), "worker": WORKER_NAME},
            )
            return None
        finally:
            db.close()


def _create_pipeline() -> Any:
    """创建共享的 KnowledgePipeline 实例（含 ModelGateway）"""
    from ingestion.knowledge_pipeline import KnowledgePipeline, PipelineConfig

    config = PipelineConfig(auto_save=False)

    model_gateway = None
    if not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            from core.model_gateway.gateway import ModelGatewayImpl

            model_gateway = ModelGatewayImpl()
            logger.info("ModelGateway initialized for KnowledgePipeline")
        except Exception as e:
            logger.warning(f"Failed to init ModelGateway: {e}, falling back to keyword extraction")

    return KnowledgePipeline(config=config, model_gateway=model_gateway)


async def main(worker_id: Optional[int] = None) -> None:
    """主循环：持续消费 ingestion_queue，并发处理 items"""
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.ingestion_repository import IngestionQueueRepository

    worker_label = f"knowledge_worker_{worker_id}" if worker_id else "knowledge_worker"

    logger.info(
        f"[{worker_label}] Starting",
        poll_interval=POLL_INTERVAL,
        batch_size=BATCH_SIZE,
        max_concurrency=MAX_CONCURRENCY,
        max_backoff=MAX_BACKOFF,
    )

    _write_pid(worker_id)

    pipeline = _create_pipeline()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    stop_event = asyncio.Event()
    shutting_down = False
    consecutive_empty = 0

    def _force_exit() -> None:
        # Flush all log handlers before forced exit
        for handler in logging.getLogger().handlers:
            handler.flush()
        logger.warning(f"[{worker_label}] Did not exit within {SHUTDOWN_TIMEOUT}s, forcing exit")
        os._exit(1)

    def _shutdown() -> None:
        nonlocal shutting_down
        logger.info(f"[{worker_label}] Received shutdown signal, stopping gracefully")
        shutting_down = True
        stop_event.set()
        threading.Timer(SHUTDOWN_TIMEOUT, _force_exit).start()

    loop = asyncio.get_running_loop()
    try:
        # add_signal_handler is Unix-only; not supported on Windows ProactorEventLoop
        loop.add_signal_handler(signal.SIGTERM, _shutdown)
        loop.add_signal_handler(signal.SIGINT, _shutdown)
    except NotImplementedError:
        # Windows fallback: use signal.signal() instead
        signal.signal(signal.SIGTERM, lambda *_: _shutdown())
        signal.signal(signal.SIGINT, lambda *_: _shutdown())

    event_bus.record_worker_heartbeat(worker_label, "started, consuming queue")
    _write_heartbeat(worker_label, "started, consuming queue")
    logger.info(f"[{worker_label}] Started, consuming ingestion_queue")

    while not shutting_down:
        try:
            db = SessionLocal()
            repo = IngestionQueueRepository(db)

            # 恢复卡在 processing 超时的 item
            stuck_count = _recover_stuck_items(db)
            if stuck_count > 0:
                db.commit()
                logger.info(f"[{worker_label}] Recovered {stuck_count} stuck items → pending")

            items = repo.dequeue(limit=BATCH_SIZE)
            db.commit()  # release row locks so processing tasks can update same rows

            if not items:
                consecutive_empty += 1
                backoff = min(POLL_INTERVAL * (2**consecutive_empty), MAX_BACKOFF)
                if consecutive_empty == 1:
                    event_bus.record_worker_heartbeat(worker_label, "idle, queue empty")
                    _write_heartbeat(worker_label, "idle, queue empty")
                logger.debug(
                    f"[{worker_label}] Empty queue, backoff {backoff:.1f}s (empty={consecutive_empty})"
                )
                await asyncio.sleep(backoff)
                continue

            consecutive_empty = 0
            tasks = [_process_and_mark(item, semaphore, pipeline) for item in items]
            await asyncio.gather(*tasks)

            event_bus.record_worker_heartbeat(worker_label, f"processed {len(items)} items")
            _write_heartbeat(worker_label, f"processed {len(items)} items")
            queue_payload = {"processed": len(items), "worker": worker_label}
            await event_bus.publish("queue_update", queue_payload)
            try:
                from services.pipeline_monitor import pipeline_monitor

                pipeline_monitor.record_event("queue_update", queue_payload)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"[{worker_label}] Loop error", error=str(e), exc_info=True)
            await asyncio.sleep(POLL_INTERVAL)
        finally:
            db.close()

    _remove_pid(worker_id)
    logger.info(f"[{worker_label}] Stopped")
    return


def get_process_status(pid_file: Optional[str] = None) -> dict:
    """检查单个 knowledge worker 进程是否存活

    Args:
        pid_file: PID 文件路径，默认使用 logs/knowledge_worker.pid

    Returns:
        {"alive": bool, "pid": int|None, "pid_file": str}
    """
    if pid_file is None:
        pid_file = str(_pid_file_for())

    result: dict = {"alive": False, "pid": None, "pid_file": pid_file}

    pid_path = Path(pid_file)
    if not pid_path.exists():
        return result

    try:
        pid = int(pid_path.read_text().strip())
        result["pid"] = pid
        import psutil

        result["alive"] = psutil.pid_exists(pid)
    except (ValueError, OSError):
        pass

    return result


def get_all_worker_statuses() -> List[dict]:
    """检查所有 knowledge worker 进程状态

    PID 文件自愈：检测到 PID 对应进程已死亡时，删除孤儿 PID 文件并跳过，
    避免监控把残留文件误算成存活 worker。所有调用方均按 ``alive=True`` 过滤，
    因此丢弃死进程条目不影响 CLI 启停逻辑。

    Returns:
        [{"alive": bool, "pid": int|None, "pid_file": str, "worker_id": int|None}, ...]
    """
    pid_dir = PROJECT_DIR / "logs"
    if not pid_dir.exists():
        return []

    results: List[dict] = []
    for pid_path in sorted(pid_dir.glob("knowledge_worker*.pid")):
        status = get_process_status(str(pid_path))

        # 自愈：PID 文件存在但进程已死亡 → 删除孤儿文件，不返回该条目
        if not status.get("alive"):
            try:
                pid_path.unlink(missing_ok=True)
                logger.info(
                    "Removed orphaned worker PID file",
                    pid_file=str(pid_path),
                    pid=status.get("pid"),
                )
            except OSError as e:
                logger.warning(
                    "Failed to remove orphaned worker PID file",
                    pid_file=str(pid_path),
                    error=str(e),
                )
            continue

        worker_id = None
        stem = pid_path.stem
        if stem.startswith("knowledge_worker_"):
            try:
                worker_id = int(stem.split("_")[-1])
            except ValueError:
                pass

        status["worker_id"] = worker_id
        results.append(status)

    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Knowledge Worker")
    parser.add_argument(
        "--worker-id",
        type=int,
        default=None,
        help="Worker instance ID for multi-process mode",
    )
    args = parser.parse_args()
    # frozen 模式下由 watchdog 通过环境变量注入 worker_id（子进程无法传 CLI 参数）
    if args.worker_id is None:
        env_id = os.environ.get("ALPHAFOUNDRY_WORKER_ID")
        if env_id:
            try:
                args.worker_id = int(env_id)
            except ValueError:
                pass
    return args


if __name__ == "__main__":
    # 强制 UTF-8 I/O，防止 Windows GBK 控制台导致 structlog 崩溃
    # （与 backend_launcher.py 第 14-21 行保持一致）
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = _parse_args()
    restart_count = 0
    last_restart_at = 0.0

    while True:
        try:
            asyncio.run(main(worker_id=args.worker_id))
            break
        except Exception:
            try:
                logger.exception("Knowledge worker crashed with unhandled exception")
            except Exception:
                pass  # logger 本身崩溃（如编码问题）时静默，确保重启逻辑继续执行
            try:
                for handler in logging.getLogger().handlers:
                    handler.flush()
            except Exception:
                pass

        restart_count += 1
        now = time.time()

        # 冷却期内频繁重启则拉长等待
        if now - last_restart_at < RESTART_COOLDOWN and restart_count > MAX_RESTARTS:
            logger.critical(
                "Knowledge worker restart limit exceeded",
                restart_count=restart_count,
                cooldown=RESTART_COOLDOWN,
            )
            for handler in logging.getLogger().handlers:
                handler.flush()
            sys.exit(1)

        last_restart_at = now
        backoff = min(5 * (2 ** min(restart_count, 5)), 120)
        logger.info(
            "Restarting knowledge worker after crash",
            restart_count=restart_count,
            backoff_seconds=backoff,
        )
        for handler in logging.getLogger().handlers:
            handler.flush()
        time.sleep(backoff)
