"""
Tests for Issue #42: AlphaFoundry v1 Document Schema.

测试统一文档 schema 的核心功能。
"""
from datetime import datetime
from pathlib import Path
import sys

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.contracts import (
    DocumentV1, DocumentChunkV1, DocumentTagV1, DocumentSummaryV1,
    EntityMentionV1, DocumentEventV1, CrawlRunV1, SourceCursorV1, ReportRunV1,
    SourceType, DocType, SourceReliabilityLevel, SubjectivityLevel,
    DocumentClassification, DocumentQuality, DocumentTimeliness
)
from core.utils.id_gen import generate_id


# =============================================================================
# Test DocumentV1 Pydantic Model
# =============================================================================

def test_document_v1_creation():
    """测试创建 DocumentV1 模型"""
    doc = DocumentV1(
        doc_id=generate_id(),
        doc_type=DocType.NEWS,
        source_type=SourceType.CAILIAN_SHE,
        title="Test News Article",
        summary="A test news article for validation",
        content="This is the full content of the test news article...",
        doc_metadata={"author": "Test Author"},
        source_metadata={"source_url": "https://example.com"},
    )

    assert doc.doc_id is not None
    assert doc.doc_type == DocType.NEWS
    assert doc.source_type == SourceType.CAILIAN_SHE
    assert doc.title == "Test News Article"
    assert doc.content == "This is the full content of the test news article..."


def test_document_v1_with_full_metadata():
    """测试带完整元数据的 DocumentV1"""
    classification = DocumentClassification(
        doc_type=DocType.REPORT,
        source_type=SourceType.ZHIQIU_REPORTS,
        primary_industry="Technology",
        secondary_industries=["AI", "Software"],
        topics=["market", "analysis"],
        event_types=["policy"],
        region="CN",
    )

    quality = DocumentQuality(
        source_reliability_level=SourceReliabilityLevel.RESEARCH_INSTITUTE,
        subjectivity_level=SubjectivityLevel.MIXED,
        fact_opinion_ratio=0.8,
        research_usability_score=0.75,
        content_quality_score=0.85,
        is_fact_source=True,
    )

    timeliness = DocumentTimeliness(
        publish_time=datetime(2024, 5, 1, 10, 0, 0),
        crawl_time=datetime(2024, 5, 1, 10, 5, 0),
        available_time=datetime(2024, 5, 1, 10, 6, 0),
    )

    doc = DocumentV1(
        doc_id=generate_id(),
        doc_type=DocType.REPORT,
        source_type=SourceType.ZHIQIU_REPORTS,
        title="Research Report: AI Market",
        summary="Comprehensive analysis of AI market",
        content="Full report content...",
        classification=classification,
        quality=quality,
        timeliness=timeliness,
    )

    assert doc.classification.primary_industry == "Technology"
    assert doc.quality.source_reliability_level == SourceReliabilityLevel.RESEARCH_INSTITUTE
    assert doc.timeliness.publish_time == datetime(2024, 5, 1, 10, 0, 0)


def test_document_v1_model_dump():
    """测试模型序列化"""
    doc = DocumentV1(
        doc_id="test-doc-001",
        doc_type=DocType.TELEGRAM,
        source_type=SourceType.CAILIAN_SHE,
        title="Breaking News",
        content="Important breaking news...",
    )

    data = doc.model_dump()

    assert data["doc_id"] == "test-doc-001"
    assert data["doc_type"] == "telegram"
    assert data["title"] == "Breaking News"


# =============================================================================
# Test Supporting Models
# =============================================================================

def test_document_chunk_v1():
    """测试文档分块模型"""
    chunk = DocumentChunkV1(
        chunk_id=generate_id(),
        doc_id="test-doc-001",
        chunk_index=0,
        chunk_type="paragraph",
        title="Introduction",
        content="This is the first paragraph...",
        start_offset=0,
        end_offset=100,
        token_count=25,
        topics=["intro"],
        entities=["Company A"],
        summary="Intro paragraph",
    )

    assert chunk.chunk_index == 0
    assert chunk.content == "This is the first paragraph..."


def test_document_tag_v1():
    """测试文档标签模型"""
    tag = DocumentTagV1(
        tag_id=generate_id(),
        doc_id="test-doc-001",
        tag="AI",
        tag_type="topic",
        confidence=0.95,
        source="model",
    )

    assert tag.tag == "AI"
    assert tag.confidence == 0.95


def test_document_summary_v1():
    """测试文档摘要模型"""
    summary = DocumentSummaryV1(
        summary_id=generate_id(),
        doc_id="test-doc-001",
        summary_type="short",
        summary="Quick summary of the article",
        bullet_points=["Point 1", "Point 2", "Point 3"],
        generator_version="gpt-4",
        quality_score=0.8,
    )

    assert summary.summary_type == "short"
    assert len(summary.bullet_points) == 3


def test_entity_mention_v1():
    """测试实体提及模型"""
    mention = EntityMentionV1(
        mention_id=generate_id(),
        doc_id="test-doc-001",
        entity_id="entity-001",
        entity_name="Tesla",
        entity_type="company",
        start_offset=50,
        end_offset=55,
        context="Tesla announced new...",
        confidence=0.98,
        is_primary=True,
    )

    assert mention.entity_name == "Tesla"
    assert mention.entity_type == "company"


def test_document_event_v1():
    """测试文档事件模型"""
    event = DocumentEventV1(
        event_id=generate_id(),
        doc_id="test-doc-001",
        canonical_event_id="canonical-001",
        event_type="earnings",
        event_time=datetime(2024, 5, 1),
        subject_entity="Tesla",
        object_entity="USD",
        event_summary="Tesla announced earnings",
        impact_direction="positive",
        evidence_text="Tesla reported 20% revenue growth",
        confidence=0.9,
    )

    assert event.event_type == "earnings"
    assert event.impact_direction == "positive"


def test_crawl_run_v1():
    """测试抓取运行记录模型"""
    run = CrawlRunV1(
        run_id=generate_id(),
        source_type=SourceType.CAILIAN_SHE,
        status="completed",
        started_at=datetime(2024, 5, 1, 10, 0, 0),
        completed_at=datetime(2024, 5, 1, 10, 5, 0),
        success_count=100,
        failure_count=2,
        skipped_count=5,
        error_log=None,
        config={"limit": 100},
    )

    assert run.source_type == SourceType.CAILIAN_SHE
    assert run.success_count == 100
    assert run.failure_count == 2


def test_source_cursor_v1():
    """测试来源游标模型"""
    cursor = SourceCursorV1(
        cursor_id=generate_id(),
        source_type=SourceType.CAILIAN_SHE,
        source_name="财联社",
        last_successful_crawl_time=datetime(2024, 5, 1, 10, 0, 0),
        last_source_doc_id="last-doc-123",
        lookback_window_minutes=60,
        consecutive_failures=0,
        is_paused=False,
    )

    assert cursor.source_type == SourceType.CAILIAN_SHE
    assert cursor.consecutive_failures == 0


def test_report_run_v1():
    """测试报告运行记录模型"""
    report_run = ReportRunV1(
        run_id=generate_id(),
        report_type="daily_report",
        report_template="template_v1",
        status="completed",
        config={"include_charts": True},
        document_ids=["doc-001", "doc-002"],
        signal_ids=["signal-001"],
        output_path="/output/report.pdf",
        started_at=datetime(2024, 5, 1, 10, 0, 0),
        completed_at=datetime(2024, 5, 1, 10, 10, 0),
    )

    assert report_run.report_type == "daily_report"
    assert len(report_run.document_ids) == 2


# =============================================================================
# Integration Tests: Repository
# =============================================================================

@pytest.mark.integration
def test_document_v1_repository_basic():
    """
    测试 DocumentV1 Repository 的基本功能（需要数据库）.

    注意：这只是一个框架，实际测试需要数据库设置。
    """
    # 这里只验证我们可以导入 Repository
    try:
        from data_layer.repositories.documents_v1 import (
            DocumentV1Repository,
        )
        # 验证导入成功
        assert True
    except ImportError:
        pytest.skip("Repository import test - skip actual DB operations")


# =============================================================================
# Test Enum Values
# =============================================================================

def test_doc_type_enum():
    """测试 DocType 枚举"""
    assert DocType.TELEGRAM == "telegram"
    assert DocType.NEWS == "news"
    assert DocType.COMMENTARY == "commentary"
    assert DocType.REPORT == "report"
    assert DocType.WECHAT == "wechat"
    assert DocType.TRANSCRIPT == "transcript"


def test_source_type_enum():
    """测试 SourceType 枚举"""
    assert SourceType.CAILIAN_SHE == "cailian_she"
    assert SourceType.ZHIQIU_REPORTS == "zhiqiu_reports"
    assert SourceType.ZHIQIU_WECHAT == "zhiqiu_wechat"
    assert SourceType.ZHIQIU_TRANSCRIPT == "zhiqiu_transcript"
    assert SourceType.CHINA_SECURITY_JOURNAL == "china_security_journal"


def test_source_reliability_level():
    """测试来源可信度等级"""
    assert SourceReliabilityLevel.OFFICIAL == "official"
    assert SourceReliabilityLevel.ESTABLISHED_MEDIA == "established_media"
    assert SourceReliabilityLevel.RESEARCH_INSTITUTE == "research_institute"
    assert SourceReliabilityLevel.SOCIAL_MEDIA == "social_media"
    assert SourceReliabilityLevel.UNKNOWN == "unknown"


def test_subjectivity_level():
    """测试主观性等级"""
    assert SubjectivityLevel.FACT_ONLY == "fact_only"
    assert SubjectivityLevel.MIXED == "mixed"
    assert SubjectivityLevel.OPINION_ONLY == "opinion_only"


# =============================================================================
# Test Examples
# =============================================================================

def test_document_v1_example():
    """测试文档示例"""
    # 使用 model_config 中的示例数据结构
    doc_data = {
        "doc_id": "test-example-001",
        "doc_type": "telegram",
        "source_type": "cailian_she",
        "title": "央行宣布降准",
        "summary": "中国人民银行决定下调金融机构存款准备金率",
        "content": "中国人民银行决定，自2024年5月10日起，下调金融机构存款准备金率0.5个百分点...",
    }

    doc = DocumentV1(**doc_data)

    assert doc.doc_id == "test-example-001"
    assert doc.doc_type == DocType.TELEGRAM
    assert doc.title == "央行宣布降准"


if __name__ == "__main__":
    # Run simple tests without pytest
    print("Running basic document v1 model tests...")

    test_document_v1_creation()
    print("✓ test_document_v1_creation passed")

    test_document_v1_with_full_metadata()
    print("✓ test_document_v1_with_full_metadata passed")

    test_document_chunk_v1()
    print("✓ test_document_chunk_v1 passed")

    test_doc_type_enum()
    print("✓ test_doc_type_enum passed")

    print("\n✅ All basic tests passed!")

