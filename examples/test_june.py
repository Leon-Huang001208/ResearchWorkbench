#!/usr/bin/env python3
"""
测试六月里程碑的新功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_entity_resolution():
    """测试实体解析"""
    print("=" * 60)
    print("测试实体解析")
    print("=" * 60)

    from knowledge_layer.entity_resolution import (
        Canonicalizer,
        EntityResolver,
        create_default_alias_manager,
    )

    resolver = EntityResolver()
    Canonicalizer()
    alias_manager = create_default_alias_manager()

    # 测试文本
    test_text = "贵州茅台（600519.SH）发布财报，净利润同比增长28%"

    print(f"\n输入文本: {test_text}")

    # 提取实体候选
    candidates = resolver.extract_candidates(test_text)
    print(f"\n提取到 {len(candidates)} 个实体候选:")
    for candidate in candidates:
        print(f"  - {candidate.text} ({candidate.entity_type.value}) - {candidate.confidence:.2f}")

    # 测试解析
    resolved = resolver.resolve("贵州茅台")
    if resolved:
        print("\n解析结果:")
        print(f"  ID: {resolved.canonical_id}")
        print(f"  名称: {resolved.canonical_name}")
        print(f"  类型: {resolved.entity_type.value}")

    # 测试别名
    print(f"\n贵州茅台的别名: {alias_manager.get_aliases('equity:cn:sse:600519')}")

    print("\n✓ 实体解析测试完成")


def test_scenario_generation():
    """测试情景生成"""
    print("\n" + "=" * 60)
    print("测试情景生成")
    print("=" * 60)

    from reasoning import ReasoningEngine, RequestType

    engine = ReasoningEngine()

    question = "人工智能产业发展对股票市场的影响"
    print(f"\n问题: {question}")

    state = engine.run(question, RequestType.THESIS_RESEARCH)

    print(f"\n生成 {len(state.hypotheses)} 个情景假设:")
    for hypothesis in state.hypotheses:
        print(f"\n  - {hypothesis.title} (概率: {hypothesis.probability:.0%})")
        if hypothesis.assumptions:
            print(f"    假设: {', '.join(hypothesis.assumptions)}")

    print(f"\n残余不确定性: {len(state.residual_uncertainty)} 项")
    for item in state.residual_uncertainty[:3]:
        print(f"  - {item}")

    print("\n✓ 情景生成测试完成")


def test_scenario_service():
    """测试情景服务"""
    print("\n" + "=" * 60)
    print("测试情景服务")
    print("=" * 60)

    from services.scenario_service import ScenarioService

    service = ScenarioService()

    topic = "美联储政策走向及其对资产价格的影响"
    print(f"\n主题: {topic}")

    report = service.generate_thesis_report(topic)
    print(f"\n生成报告长度: {len(report)} 字符")
    print("\n报告预览:")
    print(report[:500])

    print("\n✓ 情景服务测试完成")


def test_vector_retrieval():
    """测试向量检索"""
    print("\n" + "=" * 60)
    print("测试向量检索")
    print("=" * 60)

    from knowledge_layer.retrieval import HybridSearcher, InMemoryVectorStore

    store = InMemoryVectorStore()
    searcher = HybridSearcher(store)

    # 索引一些示例文档
    docs = [
        ("doc1", "贵州茅台发布财报，净利润同比增长28%", {"source": "财报"}),
        ("doc2", "腾讯控股公布业绩，云业务收入增长强劲", {"source": "公告"}),
        ("doc3", "美联储加息，影响全球资产定价", {"source": "新闻"}),
        ("doc4", "人工智能技术突破，推动科技股上涨", {"source": "研报"}),
    ]

    for doc_id, text, metadata in docs:
        searcher.index_document(doc_id, text, metadata)
        print(f"\n索引文档: {doc_id} - {text[:30]}...")

    # 搜索
    query = "茅台财报"
    print(f"\n搜索查询: {query}")
    results = searcher.search(query, top_k=3)

    print(f"\n找到 {len(results)} 个结果:")
    for result in results:
        print(f"  - {result['doc_id']} (分数: {result['score']:.2f}) - {result['text'][:40]}...")

    print("\n✓ 向量检索测试完成")


def test_assertion_extraction():
    """测试断言提取"""
    print("\n" + "=" * 60)
    print("测试断言提取")
    print("=" * 60)

    from knowledge_layer.assertions import AssertionExtractor

    extractor = AssertionExtractor()

    test_text = """
    贵州茅台2026年一季度财报显示，净利润同比增长28%，超出市场预期。
    公司表示，这主要得益于产品结构优化和销量提升。
    同时，公司管理层宣布将继续推进数字化转型。
    """

    print(f"\n输入文本:\n{test_text}")

    assertions = extractor.extract(test_text, source_doc_id="test_doc_001")

    print(f"\n提取到 {len(assertions)} 个断言:")
    for i, assertion in enumerate(assertions, 1):
        print(f"\n[{i}]")
        print(f"  ID: {assertion.assertion_id}")
        print(f"  主语: {assertion.subject_entity_id or 'N/A'}")
        print(f"  谓语: {assertion.predicate}")
        print(f"  宾语: {assertion.object_entity_id or assertion.object_value or 'N/A'}")
        print(f"  置信度: {assertion.confidence:.2f}")

    print("\n✓ 断言提取测试完成")


def test_event_extraction():
    """测试事件提取"""
    print("\n" + "=" * 60)
    print("测试事件提取")
    print("=" * 60)

    from knowledge_layer.events import EventExtractor

    extractor = EventExtractor()

    test_text = """
    2026年4月28日，贵州茅台发布一季报，净利润同比增长28%，超出市场预期。
    同日，公司股价上涨5%。
    分析师普遍看好公司未来表现。
    """

    print(f"\n输入文本:\n{test_text}")

    events = extractor.extract(test_text, source_doc_id="test_doc_002")

    print(f"\n提取到 {len(events)} 个事件:")
    for i, event in enumerate(events, 1):
        print(f"\n[{i}]")
        print(f"  ID: {event.event_id}")
        print(f"  类型: {event.event_type}")
        print(f"  摘要: {event.summary}")
        print(f"  影响方向: {event.impact_direction}")
        print(f"  置信度: {event.confidence:.2f}")
        print(f"  需要审核: {event.needs_review}")

    print("\n✓ 事件提取测试完成")


def test_ingest_service():
    """测试摄入服务"""
    print("\n" + "=" * 60)
    print("测试摄入服务")
    print("=" * 60)

    from services.ingest_service import IngestService

    service = IngestService()

    test_text = """
    贵州茅台2026年一季度财报显示，净利润同比增长28%，超出市场预期。
    公司表示，这主要得益于产品结构优化和销量提升。
    同时，公司管理层宣布将继续推进数字化转型。
    2026年4月28日，公司股价上涨5%。
    分析师普遍看好公司未来表现。
    """

    print("\n摄入文本...")
    result = service.ingest_text(
        test_text,
        source_type="report",
        source_name="测试数据",
        title="贵州茅台2026一季报分析",
    )

    print("\n摄入结果:")
    print(f"  文档ID: {result['doc_id']}")
    print(f"  标题: {result['title']}")
    print(f"  断言提取: {result['assertions_extracted']}")
    print(f"  断言已批准: {result['assertions_approved']}")
    print(f"  断言待审核: {result['assertions_pending']}")
    print(f"  事件提取: {result['events_extracted']}")
    print(f"  事件已批准: {result['events_approved']}")
    print(f"  事件待审核: {result['events_pending']}")

    print("\n✓ 摄入服务测试完成")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("AlphaFoundry 六月里程碑 - 功能测试")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    tests = [
        test_entity_resolution,
        test_vector_retrieval,
        test_assertion_extraction,
        test_event_extraction,
        test_scenario_generation,
        test_scenario_service,
        test_ingest_service,
    ]

    for test in tests:
        try:
            test()
            tests_passed += 1
        except Exception as e:
            print(f"\n✗ 测试失败: {test.__name__}")
            print(f"  错误: {e}")
            import traceback

            traceback.print_exc()
            tests_failed += 1

    print("\n" + "=" * 60)
    print(f"测试完成: {tests_passed} 通过, {tests_failed} 失败")
    print("=" * 60)

    return 0 if tests_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
