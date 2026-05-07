"""
数据摄入 CLI 命令
"""
from pathlib import Path

import click
import asyncio

from core.observability import get_logger
from core.services.ingest_service import IngestService
from data_layer.adapters.data_source_router import DataSourceRouter

logger = get_logger(__name__)


@click.group(name="ingest")
def ingest_group():
    """数据摄入命令组"""
    pass


@ingest_group.command(name="file")
@click.option("--file", "-f", required=True, help="输入文件路径")
@click.option("--source-type", "-t", default="report", help="来源类型")
@click.option("--source-name", "-s", help="来源名称")
@click.option("--title", help="文档标题")
def ingest_file_command(file: str, source_type: str, source_name: str, title: str):
    """
    摄入文档并提取断言和事件

    示例:
        af ingest file --file report.pdf --source-type report --source-name "券商研报"
        af ingest file -f news.txt -t news
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


@ingest_group.command(name="cls")
@click.option("--days", type=int, default=2, help="爬取天数 (默认 2 天)")
@click.option("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
@click.option("--output-dir", type=str, default="./data/crawlers/cls", help="输出目录")
def ingest_cls_command(days: int, start_date: str, end_date: str, output_dir: str):
    """摄入财联社电报"""
    click.echo(f"Ingesting CLS telegrams: days={days}, start={start_date}, end={end_date}")

    async def _fetch():
        router = DataSourceRouter()
        envelopes = await router.fetch_news_cls(
            days=days,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir
        )
        return envelopes

    try:
        envelopes = asyncio.run(_fetch())
        click.echo(f"Fetched {len(envelopes)} CLS telegrams")

        # Ingest each envelope
        service = IngestService()
        for envelope in envelopes:
            try:
                result = service.ingest_envelope(envelope=envelope)
                click.echo(f"  Ingested: {result['title']}")
            except Exception as e:
                click.echo(f"  Failed to ingest {envelope.title}: {e}", err=True)

    except Exception as e:
        click.echo(f"\n✗ Failed to ingest CLS telegrams: {e}", err=True)
        logger.error("Failed to ingest CLS telegrams", error=str(e), exc_info=True)
        raise click.Abort()


@ingest_group.command(name="cnstock")
@click.option("--start-date", type=str, required=True, help="开始日期 (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="结束日期 (YYYY-MM-DD, 默认同开始日期)")
@click.option("--channel", type=str, default="证券", help="频道名称 (默认: 证券)")
@click.option("--output-dir", type=str, default="./data/crawlers/cnstock", help="输出目录")
def ingest_cnstock_command(start_date: str, end_date: str, channel: str, output_dir: str):
    """摄入中国证券网新闻"""
    click.echo(f"Ingesting CNStock news: start={start_date}, end={end_date}, channel={channel}")

    if not end_date:
        end_date = start_date

    async def _fetch():
        router = DataSourceRouter()
        envelopes = await router.fetch_news_cnstock(
            start_date=start_date,
            end_date=end_date,
            channel=channel,
            output_dir=output_dir
        )
        return envelopes

    try:
        envelopes = asyncio.run(_fetch())
        click.echo(f"Fetched {len(envelopes)} CNStock news")

        # Ingest each envelope
        service = IngestService()
        for envelope in envelopes:
            try:
                result = service.ingest_envelope(envelope=envelope)
                click.echo(f"  Ingested: {result['title']}")
            except Exception as e:
                click.echo(f"  Failed to ingest {envelope.title}: {e}", err=True)

    except Exception as e:
        click.echo(f"\n✗ Failed to ingest CNStock news: {e}", err=True)
        logger.error("Failed to ingest CNStock news", error=str(e), exc_info=True)
        raise click.Abort()


@ingest_group.command(name="zq")
@click.option("--search", type=str, required=True, help="搜索关键词")
@click.option("--doc-types", type=str, default="REPORT", help="文档类型 (REPORT, NEWS, ZQMEETING, 默认: REPORT)")
@click.option("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
@click.option("--output-dir", type=str, default="./data/crawlers/zq", help="输出目录")
def ingest_zq_command(search: str, doc_types: str, start_date: str, end_date: str, output_dir: str):
    """摄入知丘内容 (研报/公众号/纪要)"""
    click.echo(f"Ingesting ZQ content: search={search}, doc_types={doc_types}, start={start_date}, end={end_date}")

    async def _fetch():
        router = DataSourceRouter()
        envelopes = await router.fetch_reports_zq(
            search=search,
            doc_types=doc_types,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir
        )
        return envelopes

    try:
        envelopes = asyncio.run(_fetch())
        click.echo(f"Fetched {len(envelopes)} ZQ documents")

        # Ingest each envelope
        service = IngestService()
        for envelope in envelopes:
            try:
                result = service.ingest_envelope(envelope=envelope)
                click.echo(f"  Ingested: {result['title']}")
            except Exception as e:
                click.echo(f"  Failed to ingest {envelope.title}: {e}", err=True)

    except Exception as e:
        click.echo(f"\n✗ Failed to ingest ZQ content: {e}", err=True)
        logger.error("Failed to ingest ZQ content", error=str(e), exc_info=True)
        raise click.Abort()


# 为了向后兼容，保持 ingest_command 作为 file 命令的别名
ingest_command = ingest_file_command
ingest = ingest_group
