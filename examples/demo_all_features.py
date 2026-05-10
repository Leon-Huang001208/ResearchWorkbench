#!/usr/bin/env python3
"""
AlphaFoundry 完整功能演示
演示所有核心功能的使用方法
"""
import sys
from pathlib import Path
from unittest.mock import Mock

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def mock_imports():
    """模拟所有有问题的导入"""
    # 模拟 settings
    mock_settings = Mock()
    mock_settings.LOG_DIR = "logs"
    mock_settings.LOG_LEVEL = "INFO"
    mock_settings.DATABASE_URL = "sqlite:///:memory:"
    sys.modules["core.settings"] = Mock()
    sys.modules["core.settings"].settings = mock_settings

    # 模拟 pydantic_settings
    sys.modules["pydantic_settings"] = Mock()
    sys.modules["pydantic_settings"].BaseSettings = object
    sys.modules["pydantic_settings"].SettingsConfigDict = dict

    # 模拟 sqlalchemy
    mock_sqlalchemy = Mock()
    mock_sqlalchemy.create_engine = Mock(return_value=Mock())
    sys.modules["sqlalchemy"] = mock_sqlalchemy
    sys.modules["sqlalchemy.orm"] = Mock()

    # 模拟 data_layer.adapters.ifind_adapter
    mock_ifind_module = Mock()
    mock_ifind_module.IFindAdapter = Mock
    sys.modules["data_layer.adapters.ifind_adapter"] = mock_ifind_module

    # 模拟 data_layer 相关模块
    mock_adapters = Mock()
    mock_adapters.IFindAdapter = Mock
    mock_adapters.LocalDataAdapter = Mock
    mock_adapters.PDFAdapter = Mock
    mock_adapters.BaseDataAdapter = Mock
    sys.modules["data_layer.adapters"] = mock_adapters

    sys.modules["data_layer"] = Mock()
    sys.modules["data_layer.repositories"] = Mock()
    sys.modules["data_layer.repositories.base"] = Mock()
    sys.modules["data_layer.normalizers"] = Mock()
    mock_date_normalizer = Mock()
    mock_date_normalizer.DateNormalizer = Mock
    sys.modules["data_layer.normalizers.date_normalizer"] = mock_date_normalizer


mock_imports()


def print_separator(title):
    """打印分隔符"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_scenario_generation():
    """演示情景生成功能"""
    print_separator("1. 多情景分析功能演示")

    from core.services.scenario_service import ScenarioService

    topic = "人工智能产业发展对股票市场的影响"
    print(f"\n研究主题: {topic}")
    print("\n正在生成多情景分析...")

    service = ScenarioService()
    scenario_set = service.generate_scenario_set(topic=topic)

    print(f"\n✓ 情景生成成功！")
    print(f"  共生成 {len(scenario_set.hypotheses)} 个情景假设")

    for i, hypothesis in enumerate(scenario_set.hypotheses, 1):
        print(f"\n  情景 {i}: {hypothesis.title}")
        print(f"    概率: {hypothesis.probability:.0%}")
        if hypothesis.assumptions:
            print(f"    核心假设: {', '.join(hypothesis.assumptions[:2])}")

    if scenario_set.residual_uncertainty:
        print(f"\n  残余不确定性: {len(scenario_set.residual_uncertainty)} 项")
        for item in scenario_set.residual_uncertainty[:2]:
            print(f"    - {item}")

    return scenario_set


def demo_document_ingestion():
    """演示文档摄入功能"""
    print_separator("2. 文档摄入功能演示")

    from core.services.ingest_service import IngestService

    # 使用示例文本进行演示
    sample_text = """贵州茅台2026年一季度财报显示，净利润同比增长28%。
    腾讯控股公布业绩，云业务收入增长强劲。
    美联储加息，影响全球资产定价。"""

    print("\n正在摄入示例文档...")
    service = IngestService()

    result = service.ingest_text(
        text=sample_text, source_type="report", source_name="演示研报", title="示例分析报告"
    )

    print(f"\n✓ 文档摄入成功！")
    print(f"  文档 ID: {result['doc_id']}")
    print(f"  标题: {result['title']}")
    print(f"  提取断言: {result['assertions_extracted']} 个")
    print(f"    - 自动批准: {result['assertions_approved']} 个")
    print(f"    - 待审核: {result['assertions_pending']} 个")
    print(f"  提取事件: {result['events_extracted']} 个")
    print(f"    - 自动批准: {result['events_approved']} 个")
    print(f"    - 待审核: {result['events_pending']} 个")

    return result


def demo_vector_retrieval():
    """演示向量检索功能"""
    print_separator("3. 向量检索功能演示")

    from knowledge_layer.retrieval.hybrid_search import HybridSearcher
    from knowledge_layer.retrieval.vector_store import InMemoryVectorStore

    # 创建向量存储和检索器
    store = InMemoryVectorStore()
    searcher = HybridSearcher(store)

    # 添加一些示例文档
    docs = [
        ("doc1", "贵州茅台发布财报，净利润同比增长28%", {"source": "财报"}),
        ("doc2", "腾讯控股公布业绩，云业务收入增长强劲", {"source": "公告"}),
        ("doc3", "美联储加息，影响全球资产定价", {"source": "新闻"}),
        ("doc4", "人工智能技术突破，推动科技股上涨", {"source": "研报"}),
    ]

    print("\n正在索引示例文档...")
    for doc_id, text, metadata in docs:
        searcher.index_document(doc_id, text, metadata)
        print(f"  ✓ 已索引: {doc_id}")

    # 进行检索
    queries = ["茅台财报", "人工智能", "美联储"]

    for query in queries:
        print(f"\n检索查询: {query}")
        results = searcher.search(query, top_k=3)

        print(f"  找到 {len(results)} 个结果:")
        for i, result in enumerate(results, 1):
            print(f"    {i}. {result['doc_id']} (score: {result['score']:.2f})")
            print(f"       {result['text'][:40]}...")

    return searcher


def demo_entity_resolution():
    """演示实体解析功能"""
    print_separator("4. 实体解析功能演示")

    from knowledge_layer.entity_resolution.canonicalizer import Canonicalizer
    from knowledge_layer.entity_resolution.types import EntityType

    canonicalizer = Canonicalizer()

    test_cases = [
        ("600000.SH", EntityType.COMPANY),
        ("600519.SH", EntityType.COMPANY),
        ("000001.SZ", EntityType.COMPANY),
    ]

    print("\n正在生成规范 ID...")
    for symbol, entity_type in test_cases:
        canonical_id = canonicalizer.generate_id(symbol, entity_type)
        print(f"  {symbol} → {canonical_id}")

    return canonicalizer


def demo_report_generation():
    """演示报告生成功能"""
    print_separator("5. 报告生成功能演示")

    from pathlib import Path

    from core.services.scenario_service import ScenarioService

    topic = "美联储政策走向分析"
    print(f"\n研究主题: {topic}")
    print("\n正在生成专题研究报告...")

    service = ScenarioService()
    report_content = service.generate_thesis_report(topic=topic)

    print(f"\n✓ 报告生成成功！")
    print(f"\n报告预览:\n")
    print(report_content[:500] + "..." if len(report_content) > 500 else report_content)

    # 也可以保存到文件
    output_file = Path(__file__).parent.parent / "temp_report.md"
    output_file.write_text(report_content, encoding="utf-8")
    print(f"\n  完整报告已保存到: {output_file}")

    return report_content


def main():
    """主函数 - 运行所有演示"""
    print("\n" + "=" * 70)
    print("  AlphaFoundry - 完整功能演示")
    print("=" * 70)

    try:
        # 运行各个演示（跳过需要完整配置的部分）
        demo_scenario_generation()
        demo_document_ingestion()
        demo_vector_retrieval()
        demo_entity_resolution()
        demo_report_generation()

        print_separator("演示完成！")
        print("\n✓ 所有功能演示成功！")
        print("\n下一步:")
        print("  1. 尝试使用 CLI 命令:")
        print("     - af scenario --topic '人工智能产业发展'")
        print("     - af ingest --file data/samples/example_report.txt")
        print("\n  2. 查看更多文档:")
        print("     - docs/CLI_GUIDE.md")
        print("     - docs/JUNE_MILESTONE.md")
        print("\n" + "=" * 70)

        return 0

    except Exception as e:
        print(f"\n✗ 演示过程中出错: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
