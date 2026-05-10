#!/usr/bin/env python3
"""
简单测试脚本 - 不依赖完整的项目配置
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 修改导入路径，避免依赖 settings
import sys
from unittest.mock import Mock


def mock_settings():
    """模拟 settings 模块"""
    mock_settings = Mock()
    mock_settings.LOG_DIR = "logs"
    mock_settings.LOG_LEVEL = "INFO"

    sys.modules["core.settings"] = Mock()
    sys.modules["core.settings"].settings = mock_settings


mock_settings()


def test_entity_resolution():
    """测试实体解析"""
    print("=" * 60)
    print("测试实体解析")
    print("=" * 60)

    # 直接导入具体模块，而不是包
    sys.path.insert(0, str(project_root))

    from knowledge_layer.entity_resolution.canonicalizer import Canonicalizer
    from knowledge_layer.entity_resolution.resolver import EntityResolver
    from knowledge_layer.entity_resolution.types import EntityType

    resolver = EntityResolver()
    canonicalizer = Canonicalizer()

    # 测试文本
    test_text = "贵州茅台（600519.SH）发布财报，净利润同比增长28%"

    print(f"\n输入文本: {test_text}")

    # 测试规范ID生成
    test_id = canonicalizer.generate_id(
        symbol="600519.SH",
        entity_type=EntityType.COMPANY,
    )
    print(f"\n生成规范ID: {test_id}")

    print("\n✓ 实体解析测试完成")


def test_vector_retrieval():
    """测试向量检索"""
    print("\n" + "=" * 60)
    print("测试向量检索")
    print("=" * 60)

    from knowledge_layer.retrieval.hybrid_search import HybridSearcher
    from knowledge_layer.retrieval.vector_store import InMemoryVectorStore

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


def test_scenario_generation():
    """测试情景生成"""
    print("\n" + "=" * 60)
    print("测试情景生成")
    print("=" * 60)

    from reasoning.evidence.collector import EvidenceCollector
    from reasoning.router.task_router import TaskRouter
    from reasoning.scenarios.builder import HypothesisBuilder
    from reasoning.scenarios.calibrator import ProbabilityCalibrator
    from reasoning.skeptic.reviewer import Skeptic
    from reasoning.state import (
        RequestType,
        create_initial_state,
    )

    router = TaskRouter()
    collector = EvidenceCollector()
    builder = HypothesisBuilder()
    skeptic = Skeptic()
    calibrator = ProbabilityCalibrator()

    question = "人工智能产业发展对股票市场的影响"
    print(f"\n问题: {question}")

    state = create_initial_state(RequestType.THESIS_RESEARCH, question)
    state = router.route(state)
    state = collector.collect(state)
    state = builder.build(state)
    state = skeptic.review(state)
    state = calibrator.calibrate(state)

    print(f"\n生成 {len(state.hypotheses)} 个情景假设:")
    for hypothesis in state.hypotheses:
        print(f"\n  - {hypothesis.title} (概率: {hypothesis.probability:.0%})")
        if hypothesis.assumptions:
            print(f"    假设: {', '.join(hypothesis.assumptions)}")

    print(f"\n残余不确定性: {len(state.residual_uncertainty)} 项")
    for item in state.residual_uncertainty[:3]:
        print(f"  - {item}")

    print("\n✓ 情景生成测试完成")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("AlphaFoundry 六月里程碑 - 功能测试（简化版）")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    tests = [
        test_entity_resolution,
        test_vector_retrieval,
        test_scenario_generation,
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
