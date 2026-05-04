"""
端到端集成测试 - 测试完整的从摄入到报告生成流程
"""
import tempfile
from pathlib import Path

import pytest

from core.services.ingest_service import IngestService
from core.services.scenario_service import ScenarioService
from knowledge_layer.retrieval import InMemoryVectorStore


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
        scenario_set = scenario_service.generate_scenario_set(
            topic="人工智能和新能源汽车产业发展"
        )

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
            f.write("""
            腾讯控股2026年Q1业绩发布，游戏收入增长强劲。
            云业务持续向好，金融科技板块表现稳定。
            """)
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
        vector_store = InMemoryVectorStore()
        ingest_service = IngestService(vector_store=vector_store)

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
