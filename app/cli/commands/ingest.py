"""
数据摄入 CLI 命令
"""
from pathlib import Path
from typing import Optional

import click
import asyncio

from core.contracts import SourceType
from core.observability import get_logger
from core.services.crawl_orchestrator import CrawlOrchestrator
from core.services.crawl_scheduler import get_crawl_scheduler
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


# =============================================================================
# Crawl Commands (Issue #43)
# =============================================================================


@click.group(name="crawl")
def crawl_group():
    """数据采集命令组 (Issue #43)"""
    pass


@crawl_group.command(name="run")
@click.option("--source", "-s", type=str, required=True, help="来源类型 (cls, cnstock, zq_reports, etc.)")
@click.option("--days", type=int, default=1, help="抓取最近几天的数据 (默认 1 天)")
@click.option("--max-docs", type=int, help="最大文档数")
@click.option("--no-dedup", is_flag=True, help="禁用地重")
@click.option("--no-backfill", is_flag=True, help="禁用补漏")
def crawl_run_command(source: str, days: int, max_docs: Optional[int], no_dedup: bool, no_backfill: bool):
    """
    运行单次采集任务

    示例:
        af crawl run --source cls --days 1
        af crawl run --source cnstock --days 2 --max-docs 100
    """
    # 解析来源类型
    try:
        source_type = SourceType(source)
    except ValueError:
        click.echo(f"✗ Invalid source type: {source}", err=True)
        click.echo(f"  Valid types: {', '.join([t.value for t in SourceType])}")
        raise click.Abort()

    click.echo(f"Starting crawl for {source_type.value}")
    click.echo(f"  Days: {days}")
    click.echo(f"  Deduplication: {'Disabled' if no_dedup else 'Enabled'}")
    click.echo(f"  Backfill: {'Disabled' if no_backfill else 'Enabled'}")

    try:
        orchestrator = CrawlOrchestrator()
        result = orchestrator.crawl_source(
            source_type=source_type,
            days=days,
            max_docs=max_docs,
            skip_existing=not no_dedup,
            enable_backfill=not no_backfill,
        )

        click.echo("\n" + "=" * 60)
        click.echo("Crawl completed!")
        click.echo("-" * 60)
        click.echo(f"Successfully saved: {result.success_count}")
        click.echo(f"Skipped (duplicates): {result.skipped_count}")
        click.echo(f"Failed: {result.failure_count}")

        if result.saved_doc_ids:
            click.echo("\nSaved document IDs:")
            for doc_id in result.saved_doc_ids[:10]:
                click.echo(f"  - {doc_id}")
            if len(result.saved_doc_ids) > 10:
                click.echo(f"  ... and {len(result.saved_doc_ids) - 10} more")

        if result.error_log:
            click.echo(f"\n⚠ Errors: {result.error_log}")

        click.echo("=" * 60)

    except Exception as e:
        click.echo(f"\n✗ Crawl failed: {e}", err=True)
        logger.error("Crawl failed", error=str(e), source=source, exc_info=True)
        raise click.Abort()


@crawl_group.command(name="backfill")
@click.option("--source", "-s", type=str, required=True, help="来源类型")
@click.option("--days", type=int, default=7, help="回溯天数 (默认 7 天)")
@click.option("--max-docs", type=int, help="最大文档数")
def crawl_backfill_command(source: str, days: int, max_docs: Optional[int]):
    """
    运行补漏任务

    示例:
        af crawl backfill --source cls --days 7
    """
    try:
        source_type = SourceType(source)
    except ValueError:
        click.echo(f"✗ Invalid source type: {source}", err=True)
        raise click.Abort()

    click.echo(f"Starting backfill for {source_type.value} (last {days} days)")

    try:
        orchestrator = CrawlOrchestrator()
        result = orchestrator.backfill_source(
            source_type=source_type,
            lookback_days=days,
            max_docs=max_docs,
        )

        click.echo("\n" + "=" * 60)
        click.echo("Backfill completed!")
        click.echo("-" * 60)
        click.echo(f"Successfully saved: {result.success_count}")
        click.echo(f"Skipped (duplicates): {result.skipped_count}")
        click.echo(f"Failed: {result.failure_count}")
        click.echo("=" * 60)

    except Exception as e:
        click.echo(f"\n✗ Backfill failed: {e}", err=True)
        logger.error("Backfill failed", error=str(e), source=source, exc_info=True)
        raise click.Abort()


@crawl_group.command(name="status")
@click.option("--source", "-s", type=str, help="特定来源 (可选)")
def crawl_status_command(source: Optional[str]):
    """
    查看采集状态

    示例:
        af crawl status
        af crawl status --source cls
    """
    if source:
        try:
            source_type = SourceType(source)
            orchestrator = CrawlOrchestrator()
            status = orchestrator.get_crawl_status(source_type)

            if status:
                click.echo(f"\nCrawl status for {source_type.value}")
                click.echo("=" * 60)

                if status.get("latest_run"):
                    run = status["latest_run"]
                    click.echo(f"Latest run:")
                    click.echo(f"  Status: {run.get('status')}")
                    click.echo(f"  Started: {run.get('started_at')}")
                    click.echo(f"  Completed: {run.get('completed_at')}")
                    click.echo(f"  Success: {run.get('success_count')}")
                    click.echo(f"  Failed: {run.get('failure_count')}")

                if status.get("cursor"):
                    cursor = status["cursor"]
                    click.echo(f"\nCursor:")
                    click.echo(f"  Last crawl: {cursor.get('last_successful_crawl_time')}")
                    click.echo(f"  Last doc ID: {cursor.get('last_source_doc_id')}")
                    click.echo(f"  Consecutive failures: {cursor.get('consecutive_failures')}")
                    click.echo(f"  Paused: {cursor.get('is_paused')}")

                click.echo("=" * 60)
            else:
                click.echo(f"No crawl history for {source_type.value}")

        except ValueError:
            click.echo(f"✗ Invalid source type: {source}", err=True)
            raise click.Abort()
    else:
        # 显示所有来源的状态
        scheduler = get_crawl_scheduler()
        status = scheduler.get_status()

        click.echo("\nCrawl Scheduler Status")
        click.echo("=" * 60)
        click.echo(f"Running: {status.get('running')}")

        click.echo("\nSources:")
        for source in status.get("sources", []):
            enabled = "✓" if source.get("enabled") else "✗"
            click.echo(f"  {enabled} {source.get('source_type')}")
            click.echo(f"    Interval: {source.get('interval_minutes')} min")

        if status.get("jobs"):
            click.echo("\nScheduled jobs:")
            for job in status.get("jobs", []):
                click.echo(f"  - {job.get('id')}: next={job.get('next_run_time')}")

        click.echo("=" * 60)


@crawl_group.command(name="scheduler-start")
def crawl_scheduler_start_command():
    """
    启动采集调度器（后台运行）

    示例:
        af crawl scheduler-start
    """
    click.echo("Starting crawl scheduler...")

    try:
        scheduler = get_crawl_scheduler()
        scheduler.start()
        click.echo("✓ Crawl scheduler started successfully!")
        click.echo("\nTo stop the scheduler, press Ctrl+C")

        # 保持运行
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\nStopping scheduler...")
            scheduler.stop()
            click.echo("✓ Scheduler stopped")

    except Exception as e:
        click.echo(f"\n✗ Failed to start scheduler: {e}", err=True)
        logger.error("Scheduler start failed", error=str(e), exc_info=True)
        raise click.Abort()


crawl = crawl_group
