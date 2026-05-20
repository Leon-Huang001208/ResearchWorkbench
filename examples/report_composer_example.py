#!/usr/bin/env python3
"""
报告合成器示例

演示如何使用 ReportComposer 生成报告。
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import configure_logging
from reporting.composer import ReportComposer


def main():
    """主函数"""
    configure_logging(level="INFO")
    print("=" * 60)
    print("报告合成器示例")
    print("=" * 60)

    composer = ReportComposer()

    # 列出可用模板
    templates = composer.list_templates()
    print("\n可用模板:")
    for t in templates:
        print(f"  - {t}")

    # 添加一些示例证据
    print("\n添加示例证据...")
    composer.add_evidence(
        evidence_id="report_2026_q1",
        source="公司财报",
        content="公司 Q1 净利润同比增长 28%，超出市场预期",
        relevance_score=0.95,
    )
    composer.add_evidence(
        evidence_id="research_note_202604",
        source="券商研报",
        content="行业景气度持续上升，维持增持评级",
        relevance_score=0.85,
    )

    # 准备上下文
    {
        "title": "2026 年 Q2 投资策略",
        "date": datetime.now(UTC).isoformat(),
        "author": "AI Analyst",
    }

    # 生成报告（仅用模板结构，不依赖 LLM）
    print("\n生成报告结构...")
    try:
        # 直接使用模板创建基本章节
        from core.contracts import SectionOutput
        from reporting.projections.markdown import MarkdownProjection

        sections = [
            SectionOutput(
                key="overview",
                content="# 2026 年 Q2 投资策略\n\n生成时间: "
                + datetime.now().isoformat()
                + "\n\n## 摘要\n\n本报告基于最新市场数据，提供投资建议。",
                evidence_refs=["report_2026_q1"],
                warnings=[],
            ),
            SectionOutput(
                key="market_outlook",
                content="\n## 市场展望\n\n当前市场环境整体向好，建议关注以下方向...",
                evidence_refs=["research_note_202604"],
                warnings=[],
            ),
            SectionOutput(
                key="conclusion",
                content="\n## 结论\n\n基于以上分析，建议谨慎乐观，控制仓位。",
                evidence_refs=[],
                warnings=[],
            ),
        ]

        # 保存 Markdown 报告
        output_path = Path("example_composed_report.md")
        projection = MarkdownProjection()
        projection.save(output_path, "2026 年 Q2 投资策略", sections)

        print(f"\n✓ 报告已生成: {output_path.absolute()}")

    except Exception as e:
        print(f"\n✗ 生成报告时出错: {e}")

    print("\n" + "=" * 60)
    print("示例完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
