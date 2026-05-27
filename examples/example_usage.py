#!/usr/bin/env python3
"""
AlphaFoundry 使用示例

本文件展示如何使用 AlphaFoundry 的 Python API。
"""

from datetime import UTC, datetime
from pathlib import Path

print("=" * 60)
print("AlphaFoundry 使用示例")
print("=" * 60)


def example_1_basic_analysis():
    """示例 1: 基本资产分析"""
    print("\n--- 示例 1: 基本资产分析 ---")

    from data_layer.repositories import AssetSnapshotRepositoryImpl
    from data_layer.repositories.base import get_db
    from services import AssetAnalysisService

    with get_db() as db:
        repo = AssetSnapshotRepositoryImpl(db)
        service = AssetAnalysisService(repo, use_mock=True)

        snapshot = service.generate_snapshot(
            canonical_id="600000.SH",
            as_of=datetime.now(UTC),
        )

        print(f"资产代码: {snapshot.canonical_id}")
        print(f"快照时间: {snapshot.as_of}")
        print("\n估值:")
        print(f"  PE TTM: {snapshot.valuation.get('pe_ttm')}")
        print(f"  PB: {snapshot.valuation.get('pb')}")
        print("\n价格:")
        print(f"  收盘价: {snapshot.price_volume.get('close_price')}")
        print(f"  MA20: {snapshot.price_volume.get('ma20')}")
        print("\n财务:")
        print(f"  净利润 YoY: {snapshot.financial.get('net_profit', {}).get('yoy')}")

    return snapshot


def example_2_markdown_report():
    """示例 2: 生成 Markdown 报告"""
    print("\n--- 示例 2: 生成 Markdown 报告 ---")

    from core.contracts import SectionOutput
    from reporting.projections import MarkdownProjection

    # 创建章节
    sections = [
        SectionOutput(
            key="overview",
            content="# 600000.SH 分析摘要\n\n这是 600000.SH 的资产分析摘要。",
            evidence_refs=["doc1"],
            warnings=[],
        ),
        SectionOutput(
            key="valuation",
            content="\n## 估值分析\n\n- PE TTM: 24.9x\n- PB: 3.8x\n- 处于历史中位水平",
            evidence_refs=["doc2"],
            warnings=[],
        ),
    ]

    # 生成报告
    projection = MarkdownProjection()
    output_path = Path("example_report.md")
    projection.save(output_path, "600000.SH 资产分析报告", sections)

    print(f"Markdown 报告已保存至: {output_path.absolute()}")


def example_3_word_report():
    """示例 3: 生成 Word 报告"""
    print("\n--- 示例 3: 生成 Word 报告 ---")

    try:
        from core.contracts import SectionOutput
        from reporting.projections import WordProjection

        sections = [
            SectionOutput(
                key="overview",
                content="600000.SH 分析摘要\n\n这是资产分析摘要内容。",
                evidence_refs=[],
                warnings=[],
            )
        ]

        projection = WordProjection()
        output_path = Path("example_report.docx")
        projection.save(output_path, "600000.SH 资产分析报告", sections)

        print(f"Word 报告已保存至: {output_path.absolute()}")
    except ImportError:
        print("跳过 Word 报告: python-docx 未安装")


def example_4_evidence_binding():
    """示例 4: 使用证据绑定器"""
    print("\n--- 示例 4: 使用证据绑定器 ---")

    from reporting.composer.evidence_binder import EvidenceBinder

    binder = EvidenceBinder()

    # 添加证据
    binder.add_evidence(
        evidence_id="report_q1_2026",
        source="公司季报",
        content="2026年Q1净利润同比增长28%",
        relevance_score=0.95,
    )
    binder.add_evidence(
        evidence_id="research_note",
        source="券商研报",
        content="维持买入评级，目标价65元",
        relevance_score=0.85,
    )

    # 绑定到章节
    bound = binder.bind_to_section("valuation", "净利润", top_k=2)
    print(f"找到 {len(bound)} 条相关证据:")
    for evidence in bound:
        print(f"  - [{evidence.id}] {evidence.source}: {evidence.content[:30]}...")


def example_5_retrieve_history():
    """示例 5: 检索历史快照"""
    print("\n--- 示例 5: 检索历史快照 ---")

    from data_layer.repositories import AssetSnapshotRepositoryImpl
    from data_layer.repositories.base import get_db
    from services import AssetAnalysisService

    with get_db() as db:
        repo = AssetSnapshotRepositoryImpl(db)
        service = AssetAnalysisService(repo, use_mock=True)

        # 生成几个历史快照
        from datetime import timedelta

        for days_ago in [30, 60, 90]:
            snapshot_date = datetime.now(UTC) - timedelta(days=days_ago)
            service.generate_snapshot(
                canonical_id="600000.SH",
                as_of=snapshot_date,
            )

        # 获取最新快照
        latest = service.get_latest_snapshot("600000.SH")
        if latest:
            print(f"最新快照时间: {latest.as_of}")
            print(f"PE TTM: {latest.valuation.get('pe_ttm')}")


def main():
    """运行所有示例"""
    print("AlphaFoundry 示例集合")

    try:
        example_1_basic_analysis()
        example_2_markdown_report()
        example_3_word_report()
        example_4_evidence_binding()
        example_5_retrieve_history()

        print("\n" + "=" * 60)
        print("所有示例运行完成!")
        print("=" * 60)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
