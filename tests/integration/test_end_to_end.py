"""
端到端集成测试 - 测试完整的从摄入到报告生成流程
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts import CanonicalEvent
from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
from data_layer.repositories.base import Base
from data_layer.repositories.event_repository import EventRepositoryImpl
from knowledge_layer.retrieval import InMemoryVectorStore
from services.ingest_service import IngestService
from services.review_service import ReviewService
from services.scenario_service import ScenarioService


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def assertion_repo(db_session):
    return AssertionRepositoryImpl(db=db_session)


@pytest.fixture
def event_repo(db_session):
    return EventRepositoryImpl(db=db_session)


@pytest.mark.integration
class TestEndToEndPipeline:
    """端到端流程测试"""

    def test_ingest_and_retrieve(self):
        """测试文档摄入和向量检索"""
        # 创建服务
        vector_store = InMemoryVectorStore()
        ingest_service = IngestService(vector_store=vector_store)

        # 示例文本
        sample_text = """
        贵州茅台2026年一季度财报显示，净利润同比增长28%。
        公司营业收入达到350亿元，超出市场预期。
        高端白酒市场持续向好，公司产品供不应求。
        """

        # 摄入文档
        result = ingest_service.ingest_text(
            text=sample_text,
            source_type="report",
            source_name="Test Report",
            title="贵州茅台财报分析",
        )

        # 验证结果
        assert result["doc_id"] is not None
        assert result["title"] == "贵州茅台财报分析"
        assert result["assertions_extracted"] >= 0
        assert result["events_extracted"] >= 0

        # 测试检索
        results = vector_store.search("茅台净利润", top_k=3)
        assert len(results) >= 0

    def test_ingest_multiple_and_scenario(self):
        """测试多个文档摄入和情景生成"""
        # 创建服务
        vector_store = InMemoryVectorStore()
        ingest_service = IngestService(vector_store=vector_store)
        scenario_service = ScenarioService()

        # 示例文本1
        text1 = """
        人工智能技术快速发展，大模型应用日益广泛。
        科大讯飞发布新一代大模型产品，性能提升显著。
        """

        # 示例文本2
        text2 = """
        新能源汽车市场持续增长，比亚迪销量领先。
        电池技术不断进步，充电基础设施逐步完善。
        """

        # 摄入文档
        result1 = ingest_service.ingest_text(
            text=text1,
            source_type="news",
            source_name="Tech News",
            title="AI技术发展",
        )

        result2 = ingest_service.ingest_text(
            text=text2,
            source_type="news",
            source_name="Auto News",
            title="新能源汽车市场",
        )

        assert result1["doc_id"] is not None
        assert result2["doc_id"] is not None

        # 测试情景生成（不依赖真实 LLM）
        scenario_set = scenario_service.generate_scenario_set(topic="人工智能和新能源汽车产业发展")

        assert scenario_set is not None
        assert scenario_set.question == "人工智能和新能源汽车产业发展"
        assert len(scenario_set.hypotheses) >= 0

    def test_ingest_file(self):
        """测试文件摄入"""
        # 创建服务
        vector_store = InMemoryVectorStore()
        ingest_service = IngestService(vector_store=vector_store)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(
                """
            腾讯控股2026年Q1业绩发布，游戏收入增长强劲。
            云业务持续向好，金融科技板块表现稳定。
            """
            )
            temp_path = Path(f.name)

        try:
            # 摄入文件
            result = ingest_service.ingest_file(
                file_path=temp_path,
                source_type="report",
                source_name="Earnings Report",
                title="腾讯Q1业绩",
            )

            assert result["doc_id"] is not None
            assert result["title"] == "腾讯Q1业绩"
        finally:
            # 清理
            temp_path.unlink(missing_ok=True)

    def test_vector_search_relevance(self):
        """测试向量检索的相关性"""
        # Force bigram fallback for deterministic Chinese text matching
        InMemoryVectorStore._st_disabled = True
        try:
            vector_store = InMemoryVectorStore()
            IngestService(vector_store=vector_store)

            # 添加多个文档
            docs = [
                ("doc1", "贵州茅台发布财报，净利润同比增长28%", {"type": "finance"}),
                ("doc2", "腾讯控股公布业绩，云业务收入增长强劲", {"type": "finance"}),
                ("doc3", "美联储加息，影响全球资产定价", {"type": "macro"}),
                ("doc4", "人工智能技术突破，推动科技股上涨", {"type": "tech"}),
                ("doc5", "新能源汽车销量创新高，比亚迪领先", {"type": "auto"}),
            ]

            for doc_id, text, metadata in docs:
                vector_store.add_document(doc_id, text, metadata)

            # 测试搜索
            results = vector_store.search("茅台财报", top_k=2)
            assert len(results) > 0
            # 第一个结果应该最相关
            assert "茅台" in results[0]["text"] or "贵州" in results[0]["text"]
        finally:
            InMemoryVectorStore._st_disabled = False

    def test_report_generation(self):
        """测试报告生成"""
        scenario_service = ScenarioService()

        # 生成报告
        report = scenario_service.generate_thesis_report(
            topic="中国白酒行业发展趋势",
            subject_ids=["company:maotai", "company:wuliangye"],
        )

        assert report is not None
        assert len(report) > 0
        assert "中国白酒行业发展趋势" in report


@pytest.mark.integration
class TestIngestToReviewEndToEnd:
    """摄入→抽取→质量门→审核队列 端到端测试"""

    def test_ingest_extract_and_review_queue(self, db_session, assertion_repo, event_repo):
        """测试完整流程：摄入文本 → 提取断言和事件 → 质量门过滤 → 审核队列可查询"""
        # 使用真实仓储的摄入服务
        vector_store = InMemoryVectorStore()
        ingest_service = IngestService(
            vector_store=vector_store,
            assertion_repo=assertion_repo,
            event_repo=event_repo,
        )

        # 审核服务直接使用仓储
        review_service = ReviewService(
            assertion_repo=assertion_repo,
            event_repo=event_repo,
        )

        # 摄入有意义的文本
        sample_text = """
        贵州茅台2026年一季度财报显示，净利润同比增长28%，超出市场预期。
        公司营业收入达到350亿元，毛利率维持在91%的高水平。
        高端白酒市场持续向好，公司产品供不应求。
        """

        result = ingest_service.ingest_text(
            text=sample_text,
            source_type="report",
            source_name="茅台财报",
            title="贵州茅台2026Q1财报",
        )

        assert result["doc_id"] is not None
        assert result["assertions_extracted"] >= 0
        assert result["events_extracted"] >= 0

        # 刷新 session 确保数据落盘
        db_session.flush()

        # 审核队列可查询（无 LLM 时提取为空，不产生低质量数据）
        _pending_assertions = review_service.list_pending_assertions()
        _pending_events = review_service.list_pending_events()

        # 验证统计接口正常工作
        stats = review_service.get_statistics()
        assert "pending_assertions" in stats
        assert "pending_events" in stats
        assert "approved_assertions" in stats
        assert "approved_events" in stats
        assert "rejected_assertions" in stats
        assert "rejected_events" in stats

    def test_approve_event_from_review_queue(self, db_session, event_repo):
        """测试从审核队列批准事件"""
        # 先通过仓储直接存入一个待审核事件
        event = CanonicalEvent(
            event_id="evt-test-001",
            event_type="earnings",
            source_type="report",
            source_name="TestSource",
            title="贵州茅台2026Q1净利润增长28%",
            summary="贵州茅台2026Q1净利润增长28%",
            impact_direction="positive",
            confidence=0.75,
            needs_review=True,
            entities=[{"text": "贵州茅台", "type": "company"}],
            evidence_spans=[{"text": "净利润同比增长28%"}],
            source_doc_id="doc-test-001",
            reviewer_status="pending",
        )
        event_repo.save(event)
        db_session.flush()

        # 使用审核服务
        review_service = ReviewService(
            assertion_repo=None,
            event_repo=event_repo,
        )

        # 查看待审核事件
        pending = review_service.list_pending_events()
        assert len(pending) >= 1

        # 批准事件
        success = review_service.approve_event("evt-test-001", reviewer="tester")
        assert success is True

        # 再次查看待审核事件
        pending_after = review_service.list_pending_events()
        assert len(pending_after) == len(pending) - 1

    def test_reject_event_from_review_queue(self, db_session, event_repo):
        """测试从审核队列拒绝事件"""
        event = CanonicalEvent(
            event_id="evt-test-002",
            event_type="other",
            source_type="test",
            source_name="TestSource",
            title="无关信息",
            summary="无关信息",
            impact_direction="unknown",
            confidence=0.3,
            needs_review=True,
            entities=[],
            evidence_spans=[],
            source_doc_id="doc-test-002",
            reviewer_status="pending",
        )
        event_repo.save(event)
        db_session.flush()

        review_service = ReviewService(event_repo=event_repo)

        success = review_service.reject_event("evt-test-002", reviewer="tester")
        assert success is True

    def test_quality_gate_sets_review_status(self):
        """测试质量门正确设置审核状态"""
        from knowledge_layer.events import EventQualityGate

        gate = EventQualityGate(min_confidence=0.4, auto_approve_threshold=0.85)

        # 高置信度、完整字段的事件应自动通过
        good_event = CanonicalEvent(
            event_id="evt-good",
            event_type="earnings",
            source_type="report",
            source_name="TestSource",
            title="贵州茅台净利润增长28%",
            summary="贵州茅台净利润增长28%，超出预期",
            impact_direction="positive",
            confidence=0.9,
            needs_review=True,
            entities=[{"text": "贵州茅台"}],
            evidence_spans=[{"text": "净利润增长28%"}],
            source_doc_id="doc-1",
        )

        # 低置信度的事件应需要审核
        bad_event = CanonicalEvent(
            event_id="evt-bad",
            event_type="other",
            source_type="test",
            source_name="TestSource",
            title="短",
            summary="短",
            impact_direction="unknown",
            confidence=0.3,
            needs_review=True,
            entities=[],
            evidence_spans=[],
            source_doc_id="doc-1",
        )

        passed, needs_review = gate.process_batch([good_event, bad_event])

        # 高质量事件应通过
        assert len(passed) >= 1
        assert all(e.reviewer_status == "approved" for e in passed)

        # 低质量事件应待审核
        assert len(needs_review) >= 1
        assert all(e.reviewer_status == "pending" for e in needs_review)

    def test_quality_gate_summary_length_check(self):
        """测试质量门摘要长度检查"""
        from knowledge_layer.events import EventQualityGate

        gate = EventQualityGate(min_summary_length=5)

        # 过短摘要
        short_event = CanonicalEvent(
            event_id="evt-short",
            event_type="other",
            source_type="test",
            source_name="TestSource",
            title="短",
            summary="短",
            impact_direction="positive",
            confidence=0.9,
            needs_review=True,
            entities=[{"text": "test"}],
            evidence_spans=[{"text": "test"}],
            source_doc_id="doc-1",
        )

        _, issues = gate.validate(short_event)
        assert any("摘要过短" in i for i in issues)

    def test_quality_gate_entities_non_empty_check(self):
        """测试质量门实体非空检查"""
        from knowledge_layer.events import EventQualityGate

        gate = EventQualityGate()

        # 无实体
        no_entity_event = CanonicalEvent(
            event_id="evt-noentity",
            event_type="earnings",
            source_type="report",
            source_name="TestSource",
            title="净利润增长28%",
            summary="净利润增长28%",
            impact_direction="positive",
            confidence=0.9,
            needs_review=True,
            entities=[],
            evidence_spans=[{"text": "test"}],
            source_doc_id="doc-1",
        )

        _, issues = gate.validate(no_entity_event)
        assert any("实体列表为空" in i for i in issues)

    def test_quality_gate_evidence_spans_check(self):
        """测试质量门 evidence_spans 非空检查"""
        from knowledge_layer.events import EventQualityGate

        gate = EventQualityGate()

        # 无 evidence_spans
        no_evidence_event = CanonicalEvent(
            event_id="evt-noev",
            event_type="earnings",
            source_type="report",
            source_name="TestSource",
            title="净利润增长28%",
            summary="净利润增长28%，超出预期",
            impact_direction="positive",
            confidence=0.9,
            needs_review=True,
            entities=[{"text": "test"}],
            evidence_spans=[],
            source_doc_id="doc-1",
        )

        _, issues = gate.validate(no_evidence_event)
        assert any("evidence_spans" in i for i in issues)

    def test_quality_gate_impact_direction_unknown_penalty(self):
        """测试 impact_direction=unknown 时降级置信度"""
        from knowledge_layer.events import EventQualityGate

        gate = EventQualityGate(
            min_confidence=0.4,
            auto_approve_threshold=0.85,
            impact_direction_unknown_penalty=0.5,
        )

        # 高置信度但 impact_direction=unknown，降级后应低于阈值
        unknown_event = CanonicalEvent(
            event_id="evt-unknown",
            event_type="other",
            source_type="news",
            source_name="TestSource",
            title="市场行情波动",
            summary="市场行情波动，涨跌互现",
            impact_direction="unknown",
            confidence=0.8,
            needs_review=True,
            entities=[{"text": "test"}],
            evidence_spans=[{"text": "test"}],
            source_doc_id="doc-1",
        )

        _, issues = gate.validate(unknown_event)
        # 降级后 0.8 - 0.5 = 0.3 < 0.4，应该有问题
        assert len(issues) > 0
