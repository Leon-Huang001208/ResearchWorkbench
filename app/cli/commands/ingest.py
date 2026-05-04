"""
数据摄入 CLI 命令
"""
from pathlib import Path

import click

from core.observability import get_logger
from core.services.ingest_service import IngestService

logger = get_logger(__name__)


@click.command(name="ingest")
@click.option("--file", "-f", required=True, help="输入文件路径")
@click.option("--source-type", "-t", default="report", help="来源类型")
@click.option("--source-name", "-s", help="来源名称")
@click.option("--title", help="文档标题")
def ingest_command(file: str, source_type: str, source_name: str, title: str):
    """
    摄入文档并提取断言和事件

    示例:
        af ingest --file report.pdf --source-type report --source-name "券商研报"
        af ingest -f news.txt -t news
    """
    file_path = Path(file)

    if not file_path.exists():
        click.echo(f"✗ File not found: {file_path}", err=True)
        raise click.Abort()

    click.echo(f"Ingesting file: {file_path}")

    try:
        service = IngestService()
        result = service.ingest_file(
            file_path=file_path,
            source_type=source_type,
            source_name=source_name,
            title=title,
        )

        click.echo("\n" + "=" * 60)
        click.echo("Ingest completed successfully!")
        click.echo("-" * 60)
        click.echo(f"Document ID: {result['doc_id']}")
        click.echo(f"Title: {result['title']}")
        click.echo("-" * 60)
        click.echo(f"Assertions extracted: {result['assertions_extracted']}")
        click.echo(f"  - Approved: {result['assertions_approved']}")
        click.echo(f"  - Pending review: {result['assertions_pending']}")
        click.echo("-" * 60)
        click.echo(f"Events extracted: {result['events_extracted']}")
        click.echo(f"  - Approved: {result['events_approved']}")
        click.echo(f"  - Pending review: {result['events_pending']}")
        click.echo("=" * 60)

        if result["assertions_pending"] > 0 or result["events_pending"] > 0:
            click.echo("\nTip: Use 'af review list' to review pending items.")

    except Exception as e:
        click.echo(f"\n✗ Failed to ingest file: {e}", err=True)
        logger.error("Failed to ingest file", error=str(e), file_path=str(file_path), exc_info=True)
        raise click.Abort()


ingest = ingest_command
