"""报告生成命令"""

import click

from core.observability import get_logger

logger = get_logger(__name__)


@click.command(name="report")
@click.option(
    "--template",
    "-t",
    required=True,
    help="报告模板：asset_analysis, thesis_research, market_report",
)
@click.option("--output", "-o", required=True, help="输出文件路径")
@click.option("--asset", help="资产代码（资产分析报告使用）")
def report_command(template: str, output: str, asset: str | None):
    """生成研究报告"""
    click.echo(f"Generating report with template: {template}")
    click.echo(f"Output: {output}")

    # TODO: 实现报告生成逻辑
    click.echo("Report generation coming soon...")


report = report_command
