"""Path-free Doctor facts; no collection, SQL recovery, provider or model calls."""

from core.observability import get_logger

from .event_preservation import snapshot_events
from .event_timeline.storage import RecordStore
from .store import StoreError

log = get_logger(__name__)


def event_diagnostic(root):
    report = {
        "optional": True,
        "historical_target_start": "1990-01-01",
        "future_default_months": 12,
        "source_policy": "public_free_only",
        "collection_enabled": False,
        "formal_score_enabled": False,
        "live_acceptance": "NOT_RUN",
        "coverage": "not_verified",
    }
    try:
        snapshot = snapshot_events(root, create_lock=False)
        if snapshot is None:
            return {**report, "state": "not_initialized", "metadata_integrity": "not_applicable"}
        return {
            **report,
            "state": "initialized",
            "metadata_integrity": "verified",
            "preserved_files": len(snapshot["files"]),
            "collection_enabled": None,
            "qualification": RecordStore(root).qualification_status(),
        }
    except (RuntimeError, StoreError, OSError, ValueError):
        log.warning("event_doctor_integrity_unverified")
        return {
            **report,
            "state": "needs_attention",
            "metadata_integrity": "unverified",
            "collection_enabled": None,
            "code": "event_preservation_failed",
        }
