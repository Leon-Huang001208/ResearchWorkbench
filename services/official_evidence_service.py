"""Build official EvidenceItems from trusted DocumentV1 sources."""
from __future__ import annotations

import re
from typing import Protocol

from cognitive_agents import EvidenceItem
from core.contracts import DocType, DocumentV1, SourceType
from core.observability import get_logger

logger = get_logger(__name__)


class DocumentRepositoryProtocol(Protocol):
    """Small repository surface needed for official evidence retrieval."""

    def list(
        self,
        source_type: SourceType | None = None,
        doc_type: DocType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentV1]:
        """List documents from a source."""


class OfficialEvidenceService:
    """Retrieve official source documents and convert them to EvidenceItem records."""

    def __init__(self, document_repo: DocumentRepositoryProtocol):
        self.document_repo = document_repo

    def find_for_asset(
        self,
        canonical_id: str,
        asset_name: str | None = None,
        limit: int = 5,
    ) -> list[EvidenceItem]:
        """Find recent CNINFO filing evidence for one asset."""
        code = _asset_code(canonical_id)
        name = (asset_name or "").strip()
        try:
            docs = self.document_repo.list(
                source_type=SourceType.CNINFO,
                doc_type=DocType.FILING,
                limit=max(limit * 4, limit),
                offset=0,
            )
        except Exception as exc:
            logger.error(
                "official_evidence_lookup_failed",
                canonical_id=canonical_id,
                asset_name=asset_name,
                error=str(exc),
                exc_info=True,
            )
            return []

        evidence: list[EvidenceItem] = []
        for doc in docs:
            if not _matches_asset(doc, code, name):
                continue
            evidence.append(_doc_to_evidence(doc))
            if len(evidence) >= limit:
                break
        return evidence


def _doc_to_evidence(doc: DocumentV1) -> EvidenceItem:
    summary = _compact_summary(doc.content or doc.summary or doc.title)
    return EvidenceItem(
        evidence_id=f"official_{doc.doc_id}",
        ref_id=doc.doc_id,
        ref_type="source_document",
        evidence_kind="official",
        source_type=doc.source_type.value
        if hasattr(doc.source_type, "value")
        else str(doc.source_type),
        source_name=doc.source_name or "巨潮资讯网",
        title=doc.title,
        summary=summary,
        observed_at=doc.created_at,
        reliability=0.95,
        relevance=0.9,
        payload={
            "doc_id": doc.doc_id,
            "source_url": doc.source_url,
            "doc_metadata": doc.doc_metadata,
            "source_metadata": doc.source_metadata,
            "content_hash": doc.content_hash,
        },
    )


def _matches_asset(doc: DocumentV1, code: str, asset_name: str) -> bool:
    doc_meta = doc.doc_metadata or {}
    source_meta = doc.source_metadata or {}
    haystack = "\n".join(
        [
            doc.title or "",
            doc.summary or "",
            doc.content or "",
            str(doc_meta.get("sec_code") or ""),
            str(doc_meta.get("sec_name") or ""),
            str(source_meta.get("source_doc_id") or ""),
        ]
    )
    if code and code in haystack:
        return True
    if asset_name and asset_name in haystack:
        return True
    return False


def _asset_code(canonical_id: str) -> str:
    return re.split(r"[.\\s]", canonical_id.strip(), maxsplit=1)[0]


def _compact_summary(text: str, limit: int = 500) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"
