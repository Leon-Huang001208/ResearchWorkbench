"""
Issue #45 单元测试 - RAG 检索层.
"""
from datetime import datetime, timedelta

import pytest

from core.contracts.documents_v1 import (
    DocType,
    DocumentChunkV1,
    DocumentClassification,
    DocumentEvidenceProfile,
    DocumentQuality,
    DocumentTimeliness,
    DocumentV1,
    SourceReliabilityLevel,
    SourceType,
    SubjectivityLevel,
)
from core.contracts.retrieval import (
    EvidencePackage,
    EvidenceType,
    RetrievalFilters,
    RetrievalProfileType,
    RetrievalQuery,
    create_daily_report_profile,
    create_weekly_report_profile,
    get_profile,
)
from core.utils.id_gen import generate_id
from services.rag_retrieval import (
    DocumentFilter,
    EvidencePackageBuilder,
    RAGRetrievalService,
    RecencyDecayScorer,
)

# ==================== Test Data ====================


def create_test_document(
    title: str = "Test Document",
    content: str = "This is a test document about investment research.",
    doc_type: DocType = DocType.NEWS,
    source_type: SourceType = SourceType.CLS,
    days_ago: int = 1,
    primary_industry: str = "tech",
    topics: list = None,
    is_fact_source: bool = True,
) -> DocumentV1:
    """创建测试文档"""
    publish_time = datetime.utcnow() - timedelta(days=days_ago)
    available_time = publish_time + timedelta(hours=2)

    return DocumentV1(
        doc_id=generate_id(),
        doc_type=doc_type,
        source_type=source_type,
        title=title,
        content=content,
        source_name="Test Source",
        language="zh",
        classification=DocumentClassification(
            primary_industry=primary_industry,
            topics=topics or ["investment", "research"],
            event_types=["earnings"],
        ),
        quality=DocumentQuality(
            source_reliability_level=SourceReliabilityLevel.ESTABLISHED_MEDIA,
            subjectivity_level=SubjectivityLevel.FACT_HEAVY,
            fact_opinion_ratio=0.8,
            research_usability_score=0.7,
            content_quality_score=0.6,
            is_fact_source=is_fact_source,
        ),
        evidence_profile=DocumentEvidenceProfile(
            has_explicit_facts=True,
            has_data_points=True,
            has_quotes=False,
            has_analysis=True,
            evidence_quality_score=0.75,
        ),
        timeliness=DocumentTimeliness(
            publish_time=publish_time,
            crawl_time=publish_time + timedelta(minutes=30),
            available_time=available_time,
            event_time=publish_time,
        ),
    )


def create_test_chunk(doc_id: str, content: str, index: int = 0) -> DocumentChunkV1:
    """创建测试分块"""
    return DocumentChunkV1(
        chunk_id=generate_id(),
        doc_id=doc_id,
        chunk_index=index,
        content=content,
        topics=["chunk-topic"],
        entities=["EntityA"],
    )


# ==================== Tests ====================


class TestRecencyDecayScorer:
    """测试时间衰减评分器"""

    def test_scorer_initialization(self):
        """测试初始化"""
        scorer = RecencyDecayScorer(half_life_days=7.0, min_weight=0.1)
        assert scorer.half_life_days == 7.0
        assert scorer.min_weight == 0.1

    def test_score_new_document(self):
        """测试新文档评分"""
        scorer = RecencyDecayScorer(half_life_days=7.0, min_weight=0.1)
        doc_time = datetime.utcnow()
        score = scorer.score(doc_time)
        assert pytest.approx(score, abs=0.01) == 1.0

    def test_score_old_document(self):
        """测试旧文档评分"""
        scorer = RecencyDecayScorer(half_life_days=7.0, min_weight=0.1)
        doc_time = datetime.utcnow() - timedelta(days=7)
        score = scorer.score(doc_time)
        assert score == pytest.approx(0.5, abs=0.05)

    def test_score_very_old_document(self):
        """测试非常旧的文档评分（不应低于最小权重）"""
        scorer = RecencyDecayScorer(half_life_days=7.0, min_weight=0.1)
        doc_time = datetime.utcnow() - timedelta(days=365)
        score = scorer.score(doc_time)
        assert score >= 0.1
        assert score == 0.1

    def test_score_no_time(self):
        """测试无时间文档评分"""
        scorer = RecencyDecayScorer()
        score = scorer.score(None)
        assert score == 0.5

    def test_score_future_document(self):
        """测试未来文档评分"""
        scorer = RecencyDecayScorer()
        doc_time = datetime.utcnow() + timedelta(days=1)
        score = scorer.score(doc_time)
        assert score == 1.0


class TestDocumentFilter:
    """测试文档过滤器"""

    def test_filter_initialization(self):
        """测试初始化"""
        doc_filter = DocumentFilter()
        assert doc_filter is not None

    def test_filter_passes_basic(self):
        """测试基本过滤通过"""
        doc_filter = DocumentFilter()
        doc = create_test_document()
        filters = RetrievalFilters()

        passes = doc_filter.filter_document(doc, filters)
        assert passes is True

    def test_filter_by_doc_type(self):
        """测试按文档类型过滤"""
        doc_filter = DocumentFilter()
        doc = create_test_document(doc_type=DocType.NEWS)
        filters = RetrievalFilters(doc_types=[DocType.REPORT])

        passes = doc_filter.filter_document(doc, filters)
        assert passes is False

    def test_filter_by_industry(self):
        """测试按行业过滤"""
        doc_filter = DocumentFilter()
        doc = create_test_document(primary_industry="tech")
        filters = RetrievalFilters(primary_industries=["finance"])

        passes = doc_filter.filter_document(doc, filters)
        assert passes is False

    def test_filter_by_quality(self):
        """测试按质量过滤"""
        doc_filter = DocumentFilter()
        doc = create_test_document()
        doc.quality.research_usability_score = 0.3
        filters = RetrievalFilters(min_research_usability=0.5)

        passes = doc_filter.filter_document(doc, filters)
        assert passes is False

    def test_filter_by_time_with_profile(self):
        """测试使用 Profile 按时间过滤"""
        doc_filter = DocumentFilter()
        doc = create_test_document(days_ago=10)
        profile = create_daily_report_profile()  # 日报只看 1-2 天
        filters = RetrievalFilters()

        passes = doc_filter.filter_document(doc, filters, profile)
        assert passes is False

    def test_filter_only_fact_sources(self):
        """测试仅事实来源过滤"""
        doc_filter = DocumentFilter()
        doc = create_test_document(is_fact_source=False)
        filters = RetrievalFilters(only_fact_sources=True)

        passes = doc_filter.filter_document(doc, filters)
        assert passes is False

    def test_filter_evidence_features(self):
        """测试证据特征过滤"""
        doc_filter = DocumentFilter()
        doc = create_test_document()
        doc.evidence_profile.has_data_points = False
        filters = RetrievalFilters(has_data_points=True)

        passes = doc_filter.filter_document(doc, filters)
        assert passes is False


class TestEvidencePackageBuilder:
    """测试证据包构建器"""

    def test_builder_initialization(self):
        """测试初始化"""
        builder = EvidencePackageBuilder()
        assert builder is not None

    def test_build_empty_package(self):
        """测试构建空包"""
        builder = EvidencePackageBuilder()
        query = RetrievalQuery(query_text="test")
        package = builder.build(query, [], [])

        assert isinstance(package, EvidencePackage)
        assert package.total_documents_found == 0
        assert len(package.documents) == 0

    def test_build_package_with_documents(self):
        """测试构建包含文档的包"""
        builder = EvidencePackageBuilder()
        query = RetrievalQuery(query_text="investment")
        doc1 = create_test_document(title="Doc 1", content="Investment research")
        doc2 = create_test_document(title="Doc 2", content="Stock analysis")

        package = builder.build(query, [doc1, doc2], [])

        assert isinstance(package, EvidencePackage)
        assert package.total_documents_found == 2
        assert len(package.documents) == 2
        assert package.query.query_text == "investment"

    def test_build_package_with_chunks(self):
        """测试构建包含分块的包"""
        builder = EvidencePackageBuilder()
        query = RetrievalQuery(query_text="investment", include_chunks=True)
        doc = create_test_document()
        chunk1 = create_test_chunk(doc.doc_id, "Chunk 1 content", 0)
        chunk2 = create_test_chunk(doc.doc_id, "Chunk 2 content", 1)

        package = builder.build(query, [doc], [chunk1, chunk2])

        assert package.total_chunks_found == 2
        assert len(package.documents[0].chunks) == 2

    def test_evidence_type_detection(self):
        """测试证据类型检测"""
        builder = EvidencePackageBuilder()
        query = RetrievalQuery(query_text="test")
        doc = create_test_document()
        doc.evidence_profile.has_data_points = True
        chunk = create_test_chunk(doc.doc_id, "Test chunk content", 0)

        package = builder.build(query, [doc], [chunk])

        assert package.documents[0].chunks[0].evidence_type == EvidenceType.DATA


class TestRetrievalProfiles:
    """测试检索 Profile"""

    def test_get_daily_profile(self):
        """测试获取日报 Profile"""
        profile = get_profile(RetrievalProfileType.DAILY_REPORT)
        assert profile.profile_type == RetrievalProfileType.DAILY_REPORT
        assert profile.name == "Daily Report"

    def test_get_weekly_profile(self):
        """测试获取周报 Profile"""
        profile = get_profile(RetrievalProfileType.WEEKLY_REPORT)
        assert profile.profile_type == RetrievalProfileType.WEEKLY_REPORT
        assert profile.name == "Weekly Report"

    def test_get_backtest_profile(self):
        """测试获取回测 Profile"""
        cutoff = datetime.utcnow() - timedelta(days=30)
        profile = get_profile(RetrievalProfileType.BACKTEST_REPLAY, cutoff)
        assert profile.profile_type == RetrievalProfileType.BACKTEST_REPLAY
        assert profile.use_available_time is True
        assert profile.available_time_cutoff == cutoff

    def test_profile_lookback_config(self):
        """测试 Profile 回看配置"""
        profile = create_daily_report_profile()
        assert DocType.TELEGRAM in profile.lookback_config.lookback_days
        assert profile.lookback_config.lookback_days[DocType.TELEGRAM] == 1

    def test_profile_recency_decay(self):
        """测试 Profile 时间衰减配置"""
        daily = create_daily_report_profile()
        weekly = create_weekly_report_profile()

        # 日报衰减更快
        assert daily.recency_decay.half_life_days < weekly.recency_decay.half_life_days


class TestRAGRetrievalService:
    """测试 RAG 检索服务"""

    def test_service_initialization(self):
        """测试初始化"""
        service = RAGRetrievalService()
        assert service is not None
        assert service.vector_store is not None
        assert service.filter is not None
        assert service.evidence_builder is not None

    def test_index_document(self):
        """测试索引文档"""
        service = RAGRetrievalService()
        doc = create_test_document()

        service.index_document(doc)

        assert doc.doc_id in service._docs

    def test_retrieve_basic(self):
        """测试基本检索"""
        service = RAGRetrievalService()
        doc1 = create_test_document(
            title="Investment Guide", content="Guide to investment research"
        )
        doc2 = create_test_document(title="Tech News", content="Technology industry updates")
        service.index_document(doc1)
        service.index_document(doc2)

        query = RetrievalQuery(
            query_text="investment research", profile_type=RetrievalProfileType.DAILY_REPORT
        )
        package = service.retrieve(query)

        assert isinstance(package, EvidencePackage)
        assert package.total_documents_found > 0

    def test_retrieve_with_filters(self):
        """测试带过滤的检索"""
        service = RAGRetrievalService()
        doc_tech = create_test_document(title="Tech News", primary_industry="tech")
        doc_finance = create_test_document(title="Finance News", primary_industry="finance")
        service.index_document(doc_tech)
        service.index_document(doc_finance)

        query = RetrievalQuery(
            query_text="news", filters=RetrievalFilters(primary_industries=["tech"])
        )
        package = service.retrieve(query)

        # 验证只返回 tech 行业
        for doc in package.documents:
            assert doc.primary_industry == "tech"

    def test_retrieve_backtest_mode(self):
        """测试回测模式检索"""
        service = RAGRetrievalService()
        cutoff = datetime.utcnow() - timedelta(days=7)

        # 创建 10 天前的文档（在 cutoff 前）
        old_doc = create_test_document(days_ago=10)
        service.index_document(old_doc)

        query = RetrievalQuery(
            query_text="test",
            profile_type=RetrievalProfileType.BACKTEST_REPLAY,
            filters=RetrievalFilters(available_time_before=cutoff),
        )
        package = service.retrieve(query)

        assert package.profile_used.use_available_time is True


class TestIssue45Integration:
    """Issue #45 集成测试"""

    def test_full_retrieval_workflow(self):
        """测试完整检索工作流"""
        # 创建服务
        service = RAGRetrievalService()

        # 索引多个文档
        for i in range(5):
            doc = create_test_document(
                title=f"Document {i}",
                content=f"Content about investment and market research {i}",
                days_ago=i + 1,
                primary_industry="tech" if i % 2 == 0 else "finance",
            )
            chunks = [
                create_test_chunk(doc.doc_id, f"Chunk {i}.1", 0),
                create_test_chunk(doc.doc_id, f"Chunk {i}.2", 1),
            ]
            service.index_document(doc, chunks)

        # 使用日报 Profile 检索
        query = RetrievalQuery(
            query_text="investment research market",
            profile_type=RetrievalProfileType.DAILY_REPORT,
            include_chunks=True,
        )
        package = service.retrieve(query)

        # 验证结果
        assert isinstance(package, EvidencePackage)
        assert package.total_documents_found > 0
        assert package.profile_used is not None
        assert "tech" in package.industry_distribution or "finance" in package.industry_distribution
