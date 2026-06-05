"""Tests for official evidence retrieval from DocumentV1 records."""
from datetime import UTC, datetime

from core.contracts import DocType, DocumentV1, SourceType
from services.official_evidence_service import OfficialEvidenceService


class _FakeDocumentRepo:
    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def list(self, source_type=None, doc_type=None, limit=100, offset=0):
        self.calls.append(
            {"source_type": source_type, "doc_type": doc_type, "limit": limit, "offset": offset}
        )
        return self.docs[offset : offset + limit]


def test_official_evidence_service_builds_cninfo_evidence_items():
    doc = DocumentV1(
        doc_id="doc_cninfo_001",
        doc_type=DocType.FILING,
        source_type=SourceType.CNINFO,
        title="贵州茅台：2025年年度报告",
        content="公司实现营业收入100亿元，归母净利润15亿元。",
        source_name="巨潮资讯网",
        source_url="https://static.cninfo.com.cn/finalpage/2026-06-01/12345.PDF",
        doc_metadata={"sec_code": "600519", "sec_name": "贵州茅台"},
        created_at=datetime(2026, 6, 5, tzinfo=UTC),
    )
    repo = _FakeDocumentRepo([doc])
    service = OfficialEvidenceService(repo)

    evidence = service.find_for_asset("600519.SH", asset_name="贵州茅台", limit=5)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.ref_id == "doc_cninfo_001"
    assert item.ref_type == "source_document"
    assert item.evidence_kind == "official"
    assert item.source_type == "cninfo"
    assert item.source_name == "巨潮资讯网"
    assert item.reliability == 0.95
    assert "归母净利润15亿元" in item.summary
    assert item.payload["source_url"] == doc.source_url
    assert repo.calls[0]["source_type"] == SourceType.CNINFO
    assert repo.calls[0]["doc_type"] == DocType.FILING


def test_official_evidence_service_filters_unrelated_cninfo_docs():
    docs = [
        DocumentV1(
            doc_id="doc_other",
            doc_type=DocType.FILING,
            source_type=SourceType.CNINFO,
            title="五粮液：2025年年度报告",
            content="公司公告正文",
            source_name="巨潮资讯网",
            doc_metadata={"sec_code": "000858", "sec_name": "五粮液"},
        )
    ]
    service = OfficialEvidenceService(_FakeDocumentRepo(docs))

    evidence = service.find_for_asset("600519.SH", asset_name="贵州茅台", limit=5)

    assert evidence == []
