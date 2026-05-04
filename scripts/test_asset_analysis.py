#!/usr/bin/env python3
"""资产分析端到端测试脚本"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime

from core.contracts import SectionOutput
from core.observability import configure_logging
from core.services import AssetAnalysisService
from data_layer.repositories import AssetSnapshotRepositoryImpl
from data_layer.repositories.base import Base, engine, get_db
from reporting.projections import MarkdownProjection, WordProjection


def init_database():
    """初始化数据库表"""
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")


def test_asset_snapshot():
    """测试资产快照生成"""
    print("\n=== Testing Asset Snapshot Generation ===")

    with get_db() as db:
        # 创建仓储和服务
        snapshot_repo = AssetSnapshotRepositoryImpl(db)
        service = AssetAnalysisService(snapshot_repo)

        # 生成测试快照
        canonical_id = "600000.SH"
        print(f"Generating snapshot for {canonical_id}...")

        snapshot = service.generate_snapshot(
            canonical_id=canonical_id, as_of=datetime.utcnow(), use_mock=True
        )

        print(f"✓ Snapshot generated:")
        print(f"  - Canonical ID: {snapshot.canonical_id}")
        print(f"  - As of: {snapshot.as_of}")
        print(f"  - PE TTM: {snapshot.valuation.get('pe_ttm')}")
        print(f"  - Close price: {snapshot.price_volume.get('close_price')}")
        print(f"  - Evidence refs: {len(snapshot.evidence_refs)}")

        # 测试获取最新快照
        print("\nTesting get latest snapshot...")
        latest = service.get_latest_snapshot(canonical_id)
        if latest:
            print(f"✓ Retrieved latest snapshot")
            print(f"  - PE TTM: {latest.valuation.get('pe_ttm')}")
        else:
            print("✗ Failed to retrieve latest snapshot")

        return snapshot


def test_report_generation(snapshot):
    """测试报告生成"""
    print("\n=== Testing Report Generation ===")

    # 创建输出目录
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    # 构建测试段落
    sections = [
        SectionOutput(
            key="asset_overview",
            content=f"# {snapshot.canonical_id} 资产分析报告\n\n生成时间: {datetime.now().isoformat()}\n\n## 摘要\n\n本报告基于最新市场数据生成。",
            evidence_refs=snapshot.evidence_refs,
            warnings=[],
        ),
        SectionOutput(
            key="valuation",
            content=f"\n## 估值分析\n\n- **PE TTM**: {snapshot.valuation.get('pe_ttm')}\n- **PB**: {snapshot.valuation.get('pb')}\n- **PS**: {snapshot.valuation.get('ps')}\n- **Dividend Yield**: {snapshot.valuation.get('dividend_yield', 0) * 100:.1f}%",
            evidence_refs=[],
            warnings=[],
        ),
        SectionOutput(
            key="price_volume",
            content=f"\n## 价量分析\n\n- **收盘价**: {snapshot.price_volume.get('close_price')}\n- **MA5**: {snapshot.price_volume.get('ma5')}\n- **MA20**: {snapshot.price_volume.get('ma20')}\n- **MA60**: {snapshot.price_volume.get('ma60')}",
            evidence_refs=[],
            warnings=[],
        ),
        SectionOutput(
            key="events",
            content=f"\n## 事件影响\n\n" + "\n".join([f"- {e}" for e in snapshot.event_impact]),
            evidence_refs=snapshot.evidence_refs,
            warnings=[],
        ),
    ]

    # 测试 Markdown 输出
    md_path = output_dir / f"{snapshot.canonical_id}_analysis.md"
    print(f"\nGenerating Markdown report: {md_path}")
    md_proj = MarkdownProjection()
    md_proj.save(md_path, title=f"{snapshot.canonical_id} 资产分析", sections=sections)
    print(f"✓ Markdown report saved: {md_path}")

    # 测试 Word 输出
    docx_path = output_dir / f"{snapshot.canonical_id}_analysis.docx"
    print(f"\nGenerating Word report: {docx_path}")
    try:
        docx_proj = WordProjection()
        docx_proj.save(docx_path, title=f"{snapshot.canonical_id} 资产分析", sections=sections)
        print(f"✓ Word report saved: {docx_path}")
    except ImportError:
        print("⚠ Skipping Word report: python-docx not installed")


def main():
    """主函数"""
    print("AlphaFoundry - 资产分析端到端测试")
    print("=" * 50)

    # 配置日志
    configure_logging(level="INFO")

    try:
        # 初始化数据库
        init_database()

        # 测试资产快照
        snapshot = test_asset_snapshot()

        # 测试报告生成
        test_report_generation(snapshot)

        print("\n" + "=" * 50)
        print("✓ All tests completed successfully!")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
