"""资产分析命令"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import List

import click

from core.contracts import AssetAnalysisSnapshot, SectionOutput
from core.observability import get_logger
from data_layer.repositories import AssetSnapshotRepositoryImpl
from data_layer.repositories.base import db_session
from reporting.projections import MarkdownProjection, WordProjection
from services import AssetAnalysisService

logger = get_logger(__name__)


@click.command(name="analyze")
@click.option("--asset", required=True, help="资产代码，例如：600000.SH")
@click.option("--output", "-o", help="输出文件路径，支持 .md 和 .docx")
@click.option("--as-of", help="指定快照时间，ISO 格式，例如：2026-05-03")
@click.option("--use-mock/--no-mock", default=True, help="是否使用模拟数据")
@click.option(
    "--source",
    type=click.Choice(["mock", "local", "ifind"]),
    default="mock",
    help="数据源: mock, local, ifind",
)
@click.option("--list-assets", is_flag=True, help="列出所有可用的本地资产数据")
def analyze_command(
    asset: str,
    output: str | None,
    as_of: str | None,
    use_mock: bool,
    source: str,
    list_assets: bool,
) -> None:
    """生成资产分析快照"""

    with db_session() as db:
        repo = AssetSnapshotRepositoryImpl(db)
        service = AssetAnalysisService(repo)

        if list_assets:
            click.echo("--list-assets is not yet implemented")
            return

        # 解析时间
        as_of_dt = None
        if as_of:
            try:
                as_of_dt = datetime.fromisoformat(as_of)
            except ValueError:
                click.echo(f"Invalid date format: {as_of}", err=True)
                ctx = click.get_current_context()
                ctx.exit(1)
                return

        # 生成快照
        try:
            snapshot = asyncio.run(
                service.generate_snapshot(
                    canonical_id=asset,
                    as_of=as_of_dt,
                    use_mock=use_mock,
                    source=source,
                )
            )
            click.echo(f"Snapshot generated successfully for {asset}")
            click.echo(f"  As of: {snapshot.as_of}")
            click.echo(f"  PE TTM: {snapshot.valuation.get('pe_ttm', 'N/A')}")
            click.echo(f"  Close price: {snapshot.price_volume.get('close_price', 'N/A')}")
        except Exception as e:
            click.echo(f"Failed to generate snapshot: {e}", err=True)
            logger.error("failed to generate snapshot", error=str(e))
            ctx = click.get_current_context()
            ctx.exit(1)
            return

        # 输出到文件（如果指定）
        if output:
            try:
                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                sections = _build_sections(snapshot)
                if output_path.suffix.lower() == ".md":
                    # 输出 Markdown
                    MarkdownProjection().save(
                        output_path,
                        title=f"{asset} 资产分析报告",
                        sections=sections,
                    )
                    click.echo(f"Markdown report saved to: {output_path}")

                elif output_path.suffix.lower() == ".docx":
                    # 输出 Word
                    WordProjection().save(
                        output_path,
                        title=f"{asset} 资产分析报告",
                        sections=sections,
                    )
                    click.echo(f"Word report saved to: {output_path}")

                else:
                    click.echo(f"Unsupported output format: {output_path.suffix}", err=True)

            except Exception as e:
                click.echo(f"Failed to write output file: {e}", err=True)
                logger.error("failed to write output file", error=str(e))


def _build_sections(snapshot: AssetAnalysisSnapshot) -> List[SectionOutput]:
    """构建报告章节"""
    from datetime import datetime

    sections = [
        SectionOutput(
            key="overview",
            title="概览",
            content=f"# {snapshot.canonical_id} 资产分析报告\n\n生成时间: {datetime.now().isoformat()}\n\n## 摘要\n\n本报告基于最新市场数据生成。",
            evidence_refs=snapshot.evidence_refs,
            warnings=[],
        ),
        SectionOutput(
            key="valuation",
            title="估值分析",
            content=f"\n## 估值分析\n\n- PE TTM: {snapshot.valuation.get('pe_ttm', 'N/A')}\n- PB: {snapshot.valuation.get('pb', 'N/A')}\n- PS: {snapshot.valuation.get('ps', 'N/A')}\n- Dividend Yield: {snapshot.valuation.get('dividend_yield', 0) * 100:.1f}%",
            evidence_refs=[],
            warnings=[],
        ),
        SectionOutput(
            key="price_volume",
            title="价量分析",
            content=f"\n## 价量分析\n\n- 收盘价: {snapshot.price_volume.get('close_price', 'N/A')}\n- MA5: {snapshot.price_volume.get('ma5', 'N/A')}\n- MA20: {snapshot.price_volume.get('ma20', 'N/A')}\n- MA60: {snapshot.price_volume.get('ma60', 'N/A')}",
            evidence_refs=[],
            warnings=[],
        ),
        SectionOutput(
            key="events",
            title="事件影响",
            content="\n## 事件影响\n\n" + "\n".join([f"- {e}" for e in snapshot.event_impact]),
            evidence_refs=snapshot.evidence_refs,
            warnings=[],
        ),
    ]
    return sections


analyze = analyze_command
