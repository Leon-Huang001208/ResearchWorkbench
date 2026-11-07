"""Credential-free, network-free diagnosis of the optional material backend."""

from core.observability import get_logger

from ..store import StoreError
from .service import RELEASE, SOURCE_COMMIT
from .storage import KnowledgeStore

log = get_logger(__name__)


def knowledge_diagnostic(root):
    result = {
        "optional": True,
        "expected_release": RELEASE,
        "expected_source_commit": SOURCE_COMMIT,
        "state": "unconfigured",
        "connectivity": "not_verified",
        "model_acceptance": "NOT_RUN",
        "report_acceptance": "NOT_RUN",
    }
    try:
        store = KnowledgeStore(root)
        binding = store.binding() if root.exists() else None
        if root.exists():
            store.preservation(create_lock=False)
        return {**result, "state": "configured" if binding else "unconfigured"}
    except (OSError, ValueError, StoreError):
        log.warning("knowledge_doctor_integrity_unknown")
        return {**result, "state": "needs_attention", "code": "knowledge_binding_invalid"}
