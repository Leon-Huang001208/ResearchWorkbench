"""
情景生成 CLI 命令
"""

from pathlib import Path

import click

from core.observability import get_logger
from services.scenario_service import ScenarioService

logger = get_logger(__name__)


@click.command(name="scenario")
@click.option("--topic", "-t", required=True, help="研究主题")
@click.option("--output", "-o", help="输出文件路径")
@click.option("--subject", "-s", multiple=True, help="主题 ID（可多次指定）")
def scenario_command(topic: str, output: str, subject: tuple) -> None:
    """
    生成多情景分析报告

    示例:
        rwb scenario --topic "美联储政策走向" --output report.md
        rwb scenario -t "人工智能产业发展" -s 600519.SH -s 000001.SZ
    """
    click.echo(f"Generating scenario analysis for: {topic}")

    try:
        service = ScenarioService()

        subject_ids = list(subject) if subject else None

        output_path = Path(output) if output else None

        report_content = service.generate_thesis_report(
            topic=topic,
            output_path=output_path,
            subject_ids=subject_ids,
        )

        click.echo("\n" + "=" * 60)
        click.echo(report_content)
        click.echo("\n" + "=" * 60)

        if output_path:
            click.echo(f"\n✓ Report saved to: {output_path.absolute()}")

    except Exception as e:
        click.echo(f"\n✗ Failed to generate report: {e}", err=True)
        logger.error("Failed to generate scenario report", error=str(e), exc_info=True)
        raise click.Abort()


scenario = scenario_command
