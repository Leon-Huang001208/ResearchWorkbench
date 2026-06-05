"""Backfill official CNINFO filings through the KnowledgePipeline."""
from __future__ import annotations

from typing import Any, Protocol

from core.contracts import DocType, DocumentV1, SourceType
from core.observability import get_logger

logger = get_logger(__name__)


class DocumentBackfillRepository(Protocol):
    """Repository surface needed for official evidence backfill."""

    def list(
        self,
        source_type: SourceType | None = None,
        doc_type: DocType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentV1]:
        """List documents."""


class KnowledgePipelineProtocol(Protocol):
    """Pipeline surface needed for backfill."""

    async def process(self, doc: DocumentV1) -> Any:
        """Process one document."""


class OfficialEvidenceBackfillService:
    """Run official CNINFO filings through the KnowledgePipeline."""

    def __init__(
        self,
        document_repo: DocumentBackfillRepository,
        knowledge_pipeline: KnowledgePipelineProtocol,
    ):
        self.document_repo = document_repo
        self.knowledge_pipeline = knowledge_pipeline

    async def backfill_cninfo(self, limit: int = 20, offset: int = 0) -> dict[str, int]:
        """Process CNINFO filing documents and return simple run statistics."""
        docs = self.document_repo.list(
            source_type=SourceType.CNINFO,
            doc_type=DocType.FILING,
            limit=limit,
            offset=offset,
        )
        processed = 0
        events = 0
        failed = 0

        for doc in docs:
            try:
                result = await self.knowledge_pipeline.process(doc)
                processed += 1
                events += len(getattr(result, "events", []) or [])
            except Exception as exc:
                failed += 1
                logger.error(
                    "official_evidence_backfill_failed",
                    doc_id=doc.doc_id,
                    source_type=doc.source_type.value
                    if hasattr(doc.source_type, "value")
                    else str(doc.source_type),
                    error=str(exc),
                    exc_info=True,
                )

        return {"processed": processed, "events": events, "failed": failed}
