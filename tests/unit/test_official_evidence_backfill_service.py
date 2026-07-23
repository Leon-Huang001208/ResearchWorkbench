"""Tests for CNINFO KnowledgePipeline backfill service."""

from datetime import UTC, datetime

import pytest

from core.contracts import DocType, DocumentV1, SourceType
from services.official_evidence_backfill_service import OfficialEvidenceBackfillService


class _FakeDocumentRepo:
    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def list(self, source_type=None, doc_type=None, limit=100, offset=0):
        self.calls.append(
            {"source_type": source_type, "doc_type": doc_type, "limit": limit, "offset": offset}
        )
        return self.docs[offset : offset + limit]


class _FakePipeline:
    def __init__(self):
        self.docs = []

    async def process(self, doc):
        self.docs.append(doc)
        return type("PipelineResult", (), {"events": [object(), object()]})()


@pytest.mark.asyncio
async def test_backfill_processes_cninfo_filings_through_knowledge_pipeline():
    doc = DocumentV1(
        doc_id="doc_cninfo_001",
        doc_type=DocType.FILING,
        source_type=SourceType.CNINFO,
        title="贵州茅台：2025年年度报告",
        content="公司实现营业收入100亿元。",
        source_name="巨潮资讯网",
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
    )
    repo = _FakeDocumentRepo([doc])
    pipeline = _FakePipeline()
    service = OfficialEvidenceBackfillService(document_repo=repo, knowledge_pipeline=pipeline)

    result = await service.backfill_cninfo(limit=10)

    assert result == {"processed": 1, "events": 2, "failed": 0}
    assert pipeline.docs == [doc]
    assert repo.calls == [
        {"source_type": SourceType.CNINFO, "doc_type": DocType.FILING, "limit": 10, "offset": 0}
    ]


class _FailingPipeline:
    async def process(self, doc):
        raise RuntimeError("pipeline failed")


@pytest.mark.asyncio
async def test_backfill_counts_pipeline_failures():
    doc = DocumentV1(
        doc_id="doc_cninfo_002",
        doc_type=DocType.FILING,
        source_type=SourceType.CNINFO,
        title="五粮液：2025年半年度报告",
        content="公司公告正文。",
        source_name="巨潮资讯网",
    )
    service = OfficialEvidenceBackfillService(
        document_repo=_FakeDocumentRepo([doc]),
        knowledge_pipeline=_FailingPipeline(),
    )

    result = await service.backfill_cninfo(limit=5)

    assert result == {"processed": 0, "events": 0, "failed": 1}
