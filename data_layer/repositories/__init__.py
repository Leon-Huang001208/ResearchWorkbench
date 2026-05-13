from .assertion_repository import AssertionRepositoryImpl
from .asset_snapshot_repository import AssetSnapshotRepositoryImpl
from .base import BaseRepository
from .crawl_state_repository import (
    get_crawl_state,
    get_all_crawl_states,
    upsert_crawl_state,
    pause_crawl,
    resume_crawl,
    update_watermark,
    increment_crawl_stats,
    reset_crawl_state,
)
from .document_repository import DocumentRepositoryImpl
from .entity_repository import EntityRepositoryImpl
from .event_repository import EventRepositoryImpl
from .outcome_repository import OutcomeRepositoryImpl
from .pdf_artifact_repository import (
    add_pdf_artifact,
    get_pdf_by_id,
    get_pdf_by_doc_id,
    get_pdf_by_hash,
    get_pdfs_by_source,
    add_conversion,
    update_conversion_status,
    get_conversion_stats,
    get_pending_conversions,
)
from .processed_item_repository import (
    item_exists,
    item_exists_by_hash,
    add_processed_item,
    get_recent_processed,
    get_processed_stats,
    get_processed_stats_by_day,
)
from .trace_repository import TraceRepositoryImpl

__all__ = [
    "BaseRepository",
    "EntityRepositoryImpl",
    "DocumentRepositoryImpl",
    "AssertionRepositoryImpl",
    "EventRepositoryImpl",
    "TraceRepositoryImpl",
    "AssetSnapshotRepositoryImpl",
    "OutcomeRepositoryImpl",
    # Crawl State
    "get_crawl_state",
    "get_all_crawl_states",
    "upsert_crawl_state",
    "pause_crawl",
    "resume_crawl",
    "update_watermark",
    "increment_crawl_stats",
    "reset_crawl_state",
    # Processed Item
    "item_exists",
    "item_exists_by_hash",
    "add_processed_item",
    "get_recent_processed",
    "get_processed_stats",
    "get_processed_stats_by_day",
    # PDF Artifact
    "add_pdf_artifact",
    "get_pdf_by_id",
    "get_pdf_by_doc_id",
    "get_pdf_by_hash",
    "get_pdfs_by_source",
    "add_conversion",
    "update_conversion_status",
    "get_conversion_stats",
    "get_pending_conversions",
]
