"""
数据摄入 CLI 命令
"""

from pathlib import Path
from typing import Optional

import click

from core.contracts import SourceType
from core.observability import get_logger
from services.crawl_orchestrator import CrawlOrchestrator
from services.ingest_service import IngestService

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
        rwb ingest file --file report.pdf --source-type report --source-name "券商研报"
        rwb ingest file -f news.txt -t news
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
            click.echo("\nTip: Use 'rwb review list' to review pending items.")

    except Exception as e:
        click.echo(f"\n✗ Failed to ingest file: {e}", err=True)
        logger.error("Failed to ingest file", error=str(e), file_path=str(file_path), exc_info=True)
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
@click.option(
    "--source", "-s", type=str, required=True, help="来源类型 (cls, cnstock, zq_reports, etc.)"
)
@click.option("--days", type=int, default=1, help="抓取最近几天的数据 (默认 1 天)")
@click.option("--max-docs", type=int, help="最大文档数")
@click.option("--no-dedup", is_flag=True, help="禁用地重")
@click.option("--no-backfill", is_flag=True, help="禁用补漏")
def crawl_run_command(
    source: str, days: int, max_docs: Optional[int], no_dedup: bool, no_backfill: bool
):
    """
    运行单次采集任务

    示例:
        rwb crawl run --source cls --days 1
        rwb crawl run --source cnstock --days 2 --max-docs 100
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
        rwb crawl backfill --source cls --days 7
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
        rwb crawl status
        rwb crawl status --source cls
    """
    if source:
        try:
            source_type = SourceType(source)
            orchestrator = CrawlOrchestrator()
            crawl_status = orchestrator.get_crawl_status(source_type)

            if crawl_status:
                click.echo(f"\nCrawl status for {source_type.value}")
                click.echo("=" * 60)

                if crawl_status.get("latest_run"):
                    run = crawl_status["latest_run"]
                    click.echo("Latest run:")
                    click.echo(f"  Status: {run.get('status')}")
                    click.echo(f"  Started: {run.get('started_at')}")
                    click.echo(f"  Completed: {run.get('completed_at')}")
                    click.echo(f"  Success: {run.get('success_count')}")
                    click.echo(f"  Failed: {run.get('failure_count')}")

                if crawl_status.get("cursor"):
                    cursor = crawl_status["cursor"]
                    click.echo("\nCursor:")
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
        from services.crawl_scheduler import build_scheduler_status, get_scheduler_process_status

        process_status = get_scheduler_process_status()
        db_status = build_scheduler_status()

        click.echo("\nCrawl Scheduler Status")
        click.echo("=" * 60)
        click.echo(f"Process alive: {process_status.get('alive')}")
        click.echo(f"PID: {process_status.get('pid')}")

        click.echo("\nSources:")
        for src in db_status.get("sources", []):
            enabled = "✓" if src.get("enabled") else "✗"
            click.echo(f"  {enabled} {src.get('source_type')}")
            click.echo(f"    Interval: {src.get('interval_minutes')} min")
            click.echo(f"    Should run: {src.get('should_run')} ({src.get('run_reason')})")

        if db_status.get("jobs"):
            click.echo("\nScheduled jobs:")
            for job in db_status.get("jobs", []):
                click.echo(f"  - {job.get('id')}: next={job.get('next_run_time')}")

        click.echo("=" * 60)


@crawl_group.command(name="scheduler-start")
def crawl_scheduler_start_command():
    """
    启动采集调度器（后台独立进程）

    示例:
        rwb crawl scheduler-start
    """
    import subprocess
    import sys
    from pathlib import Path

    from services.crawl_scheduler import get_scheduler_process_status

    process_status = get_scheduler_process_status()
    if process_status["alive"]:
        click.echo(f"✓ Scheduler already running (PID {process_status['pid']})")
        return

    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    worker_module = "workers.crawl_scheduler_worker"

    click.echo("Starting crawl scheduler process...")

    try:
        subprocess.Popen(
            [sys.executable, "-m", worker_module],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        click.echo("✓ Crawl scheduler started in background")
    except Exception as e:
        click.echo(f"\n✗ Failed to start scheduler: {e}", err=True)
        logger.error("Scheduler start failed", error=str(e), exc_info=True)
        raise click.Abort()


crawl = crawl_group


# =============================================================================
# Knowledge Worker Commands
# =============================================================================


@click.group(name="knowledge")
def knowledge_group():
    """知识加工 Worker 命令组"""
    pass


@knowledge_group.command(name="start")
@click.option("--workers", "-w", type=int, default=1, help="Worker 进程数量 (默认 1)")
def knowledge_start_command(workers: int):
    """启动知识加工 Worker（后台独立进程）

    示例:
        rwb knowledge start
        rwb knowledge start --workers 4
    """
    import subprocess
    import sys
    from pathlib import Path

    from workers.knowledge_worker import get_all_worker_statuses

    existing = get_all_worker_statuses()
    alive_workers = [w for w in existing if w["alive"]]

    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    worker_module = "workers.knowledge_worker"

    if workers < 1:
        click.echo("✗ --workers must be >= 1", err=True)
        raise click.Abort()

    started = 0
    for worker_id in range(1, workers + 1):
        already_running = any(w.get("worker_id") == worker_id and w["alive"] for w in alive_workers)
        if already_running:
            click.echo(f"  Worker {worker_id}: already running, skipped")
            continue

        try:
            subprocess.Popen(
                [sys.executable, "-m", worker_module, "--worker-id", str(worker_id)],
                cwd=str(project_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            click.echo(f"  Worker {worker_id}: started")
            started += 1
        except Exception as e:
            click.echo(f"  Worker {worker_id}: failed - {e}", err=True)
            logger.error(
                "Knowledge worker start failed", worker_id=worker_id, error=str(e), exc_info=True
            )

    if started > 0:
        click.echo(f"✓ {started} knowledge worker(s) started")
    elif not any(w.get("worker_id") and w["alive"] for w in alive_workers):
        click.echo("✓ All requested workers already running")


@knowledge_group.command(name="stop")
def knowledge_stop_command():
    """停止所有知识加工 Worker 进程

    示例:
        rwb knowledge stop
    """
    import os as _os
    import signal as _signal

    from workers.knowledge_worker import get_all_worker_statuses

    all_statuses = get_all_worker_statuses()
    alive_workers = [w for w in all_statuses if w["alive"]]

    if not alive_workers:
        for pid_path in Path("logs").glob("knowledge_worker*.pid"):
            pid_path.unlink(missing_ok=True)
        click.echo("✓ No knowledge workers running")
        return

    stopped = 0
    for w in alive_workers:
        label = f"worker {w['worker_id']}" if w.get("worker_id") else "main worker"
        try:
            _os.kill(w["pid"], _signal.SIGTERM)
            click.echo(f"  {label}: stopped (PID {w['pid']})")
            stopped += 1
        except OSError as e:
            click.echo(f"  {label}: failed to stop - {e}", err=True)

    click.echo(f"✓ Stopped {stopped} knowledge worker(s)")


@knowledge_group.command(name="status")
def knowledge_status_command():
    """查看所有知识加工 Worker 状态

    示例:
        rwb knowledge status
    """
    from workers.knowledge_worker import get_all_worker_statuses

    all_statuses = get_all_worker_statuses()

    if not all_statuses:
        click.echo("\nKnowledge Worker Status")
        click.echo("=" * 40)
        click.echo("No PID files found. Worker not started yet.")
        click.echo("=" * 40)
        return

    click.echo("\nKnowledge Worker Status")
    click.echo("=" * 50)
    for w in all_statuses:
        label = f"Worker {w['worker_id']}" if w.get("worker_id") else "Main worker"
        status_icon = "✓" if w["alive"] else "✗"
        pid = w["pid"] or "N/A"
        click.echo(f"  {status_icon} {label}: PID {pid}")
    click.echo("=" * 50)


knowledge = knowledge_group
