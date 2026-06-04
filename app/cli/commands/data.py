"""
统一数据命令组 — af data ingest|backfill|validate|status|list|file|schedule|workers

替换分散的 ingest / crawl / knowledge 命令，提供统一入口。
旧命令保留为别名（向后兼容）。

设计原则：
- CLI 直接调用 Connector Python API（不通过 subprocess）
- 与 MCP server 共享同一套 connector 注册表
- 保持旧命令别名可用
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import click

from core.observability import get_logger

logger = get_logger(__name__)


# =============================================================================
# 辅助：connector 注册表（使用 ConnectorRegistry 自动发现 + 手工注册）
# =============================================================================

_registry_instance = None  # type: ignore[var-annotated]


def _ensure_registry() -> Any:
    """延迟加载 connector 注册表，优先使用 ConnectorRegistry.discover_all().

    自动发现从 data_sources/ SourceSpec 注册的数据源，
    并手工补充未通过 SourceSpec 注册的 market connectors。
    """
    global _registry_instance
    if _registry_instance is not None:
        return _registry_instance

    from core.connectors.registry import get_connector_registry

    reg = get_connector_registry()
    reg.discover_all()

    # 为 "zq" 创建别名（指向 zhiqiu_reports 的 ZQDocumentConnector 实例）
    if "zq" not in reg.list_sources():
        zq_sources = ["zhiqiu_reports", "zhiqiu_wechat", "zhiqiu_transcript"]
        for zq_src in zq_sources:
            conn = reg.get_connector(zq_src)
            if conn is not None:
                reg.register("zq", conn)
                break
        else:
            # 没有 zhiqiu_* 注册，直接创建 ZQDocumentConnector
            try:
                from connectors.document.zq import ZQDocumentConnector

                reg.register_class("zq", ZQDocumentConnector)
            except ImportError:
                pass

    _registry_instance = reg
    return reg


def _get_connector(source: str) -> Any:
    """获取 connector 实例."""
    reg = _ensure_registry()
    return reg.get_connector(source)


def _get_available_sources() -> dict:
    """获取所有可用数据源及其元信息."""
    reg = _ensure_registry()
    sources = {}
    for source_name, connector in sorted(reg.get_all_connectors().items()):
        try:
            sources[source_name] = {
                "type": connector.asset_type,
                "datasets": connector.datasets,
            }
        except Exception as e:
            sources[source_name] = {
                "type": "unknown",
                "datasets": [],
                "error": str(e),
            }
    return sources


# =============================================================================
# data 命令组
# =============================================================================


@click.group(name="data")
def data_group() -> None:
    """统一数据命令组 — 数据摄入、回填、验证、状态管理

    这是 ingest / crawl / knowledge 的统一替代入口。

    \b
    常用命令:
      af data list                    列出所有可用数据源
      af data ingest -s cls -d telegram   摄入数据
      af data status                  查看数据状态
      af data validate -s akshare -d stock_daily  校验数据
    """
    pass


# ---------------------------------------------------------------------------
# data list — 列出所有可用数据源
# ---------------------------------------------------------------------------


@data_group.command(name="list")
def data_list_command() -> None:
    """列出所有可用数据源及其支持的数据集

    示例:
        af data list
    """
    sources = _get_available_sources()

    if not sources:
        click.echo("No data sources registered.")
        click.echo("Check that connector packages are installed:")
        click.echo("  connectors/document/  — CLS, CNStock, ZQ")
        click.echo("  connectors/market/    — AKShare, Wind, Yahoo")
        return

    click.echo("\nAvailable Data Sources")
    click.echo("=" * 70)

    for source_name, info in sources.items():
        type_label = info.get("type", "unknown")
        datasets = info.get("datasets", [])
        error = info.get("error")

        click.echo(f"\n  [{type_label.upper()}] {source_name}")
        if error:
            click.echo(f"    ⚠ Error: {error}")
        else:
            for ds in datasets:
                click.echo(f"    - {ds}")

    click.echo("\n" + "=" * 70)
    click.echo("Use: af data ingest --source <source> --dataset <dataset> [options]")
    click.echo()


# ---------------------------------------------------------------------------
# data ingest — 执行数据摄入（替代 af crawl run）
# ---------------------------------------------------------------------------


@data_group.command(name="ingest")
@click.option(
    "--source", "-s", type=str, required=True, help="数据源标识 (cls, akshare, wind, ... 或 'auto' 自动降级)"
)
@click.option("--dataset", "-d", type=str, required=True, help="数据集标识 (news, stock_daily, ...)")
@click.option("--start-date", help="开始日期 YYYY-MM-DD")
@click.option("--end-date", help="结束日期 YYYY-MM-DD")
@click.option("--codes", help="证券代码，逗号分隔 (如 '600519.SH,000001.SZ')")
@click.option("--days", type=int, help="抓取最近 N 天 (与 start-date/end-date 互斥)")
@click.option("--max-items", type=int, help="最大抓取数量")
def data_ingest_command(
    source: str,
    dataset: str,
    start_date: Optional[str],
    end_date: Optional[str],
    codes: Optional[str],
    days: Optional[int],
    max_items: Optional[int],
) -> None:
    """执行数据摄入任务

    调用对应 connector 的完整生命周期:
    discover → fetch → save_raw → parse → normalize → validate → persist

    \b
    示例:
        af data ingest -s cls -d telegram --days 2
        af data ingest -s akshare -d stock_daily --codes "600519.SH" --start-date 2026-01-01 --end-date 2026-06-01
        af data ingest -s auto -d daily_quotes --codes "600519.SH" --days 5   # 自动降级: Cjpy → Wind → BaoStock
        af data ingest -s cnstock -d news --max-items 50
    """
    reg = _ensure_registry()

    # 构建参数
    run_params: dict = {}
    if start_date:
        run_params["start_date"] = start_date
    if end_date:
        run_params["end_date"] = end_date
    if codes:
        run_params["codes"] = [c.strip() for c in codes.split(",") if c.strip()]
    if days:
        run_params["days"] = days
    if max_items:
        run_params["max_items"] = max_items

    # --- source="auto": 多源降级路由 ---
    if source == "auto":
        click.echo(f"\nData Ingest: auto/{dataset}")
        click.echo("-" * 50)
        click.echo("  Mode:       auto (fallback routing)")
        click.echo(f"  Dataset:    {dataset}")
        if run_params:
            for k, v in run_params.items():
                click.echo(f"  {k}:         {v}")

        result = reg.run_with_fallback(dataset, **run_params)
        result_source = result.routed_source or result.source

        click.echo(f"\n  Routed to:  {result_source}")
        if result.fallback_used:
            click.echo("  ⚠ Fallback: YES (primary source was unavailable)")

        if result.status.value == "completed":
            click.echo(f"\n✓ Ingest complete → {result.stats.persisted} records persisted")
            click.echo(f"  Source: {result_source}")
        elif result.status.value == "failed":
            click.echo(f"\n✗ All fallback sources failed: {result.error_message}", err=True)
            raise click.Abort()
        else:
            click.echo(f"\n⚠ Partial: {result.status.value}")
            click.echo(f"  {result.stats}")
        return

    # --- 普通单源模式 ---
    sources = _get_available_sources()
    if source not in sources:
        click.echo(f"✗ Unknown source: {source}", err=True)
        click.echo(f"  Available: {', '.join(sorted(sources.keys()))}")
        click.echo("  Use 'af data list' to see all sources and datasets.")
        raise click.Abort()

    source_info = sources[source]
    if dataset not in source_info.get("datasets", []):
        click.echo(f"✗ Unknown dataset '{dataset}' for source '{source}'", err=True)
        click.echo(f"  Available datasets: {', '.join(source_info['datasets'])}")
        raise click.Abort()

    connector = _get_connector(source)
    if connector is None:
        click.echo(f"✗ Failed to instantiate connector for: {source}", err=True)
        raise click.Abort()

    click.echo(f"\nData Ingest: {source}/{dataset}")
    click.echo("-" * 50)

    click.echo(f"  Source:     {source}")
    click.echo(f"  Dataset:    {dataset}")
    if run_params:
        for k, v in run_params.items():
            click.echo(f"  {k}:  {v}")

    try:
        result = connector.run(dataset=dataset, **run_params)

        click.echo(f"\n  Status:     {result.status.value}")
        click.echo(f"  Run ID:     {result.run_id}")
        click.echo(f"  Discovered: {result.stats.discovered}")
        click.echo(f"  Fetched:    {result.stats.fetched}")
        click.echo(f"  Persisted:  {result.stats.persisted}")
        click.echo(f"  Failed:     {result.stats.failed}")

        if result.stats.errors:
            click.echo(f"\n  Errors ({len(result.stats.errors)}):")
            for err in result.stats.errors[:5]:
                click.echo(f"    - {err.get('item_id', '?')}: {err.get('error', '?')}")
            if len(result.stats.errors) > 5:
                click.echo(f"    ... and {len(result.stats.errors) - 5} more")

        if result.error_message:
            click.echo(f"\n  ⚠ {result.error_message}")

        click.echo(f"\n✓ Ingest completed ({result.status.value})")

    except Exception as e:
        click.echo(f"\n✗ Ingest failed: {e}", err=True)
        logger.error(
            "data_ingest_failed",
            extra={"source": source, "dataset": dataset, "error": str(e)},
            exc_info=True,
        )
        raise click.Abort()


# ---------------------------------------------------------------------------
# data backfill — 历史数据回填（替代 af crawl backfill）
# ---------------------------------------------------------------------------


@data_group.command(name="backfill")
@click.option("--source", "-s", type=str, required=True, help="数据源标识")
@click.option("--days", type=int, default=7, help="回溯天数 (默认 7)")
@click.option("--max-items", type=int, help="最大抓取数量")
def data_backfill_command(source: str, days: int, max_items: Optional[int]) -> None:
    """历史数据回填

    对指定数据源执行回溯抓取，补全历史数据。

    \b
    示例:
        af data backfill -s cls --days 30
        af data backfill -s akshare -d stock_daily --days 90
    """
    try:
        from core.contracts import SourceType
        from services.crawl_orchestrator import CrawlOrchestrator

        source_type = SourceType(source)
    except ValueError:
        # 尝试 connector 数据源（不在旧 SourceType 枚举中）
        sources = _get_available_sources()
        if source not in sources:
            click.echo(f"✗ Unknown source: {source}", err=True)
            click.echo(f"  Available: {', '.join(sorted(sources.keys()))}")
            raise click.Abort()
        click.echo(
            f"⚠ Source '{source}' uses connector API; backfill via ingest with date range instead."
        )
        click.echo(f"  Try: af data ingest -s {source} --days {days}")
        return

    click.echo(f"Backfill: {source} (last {days} days)")

    try:
        orchestrator = CrawlOrchestrator()
        result = orchestrator.backfill_source(
            source_type=source_type,
            lookback_days=days,
            max_docs=max_items,
        )

        click.echo(f"\n  Success:  {result.success_count}")
        click.echo(f"  Skipped:  {result.skipped_count}")
        click.echo(f"  Failed:   {result.failure_count}")
        click.echo("\n✓ Backfill completed")

    except Exception as e:
        click.echo(f"\n✗ Backfill failed: {e}", err=True)
        logger.error(
            "data_backfill_failed",
            extra={"source": source, "error": str(e)},
            exc_info=True,
        )
        raise click.Abort()


# ---------------------------------------------------------------------------
# data validate — 校验已有数据（NEW）
# ---------------------------------------------------------------------------


@data_group.command(name="validate")
@click.option("--source", "-s", type=str, required=True, help="数据源标识")
@click.option("--dataset", "-d", type=str, required=True, help="数据集标识")
@click.option("--start-date", help="校验开始日期")
@click.option("--end-date", help="校验结束日期")
def data_validate_command(
    source: str,
    dataset: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> None:
    """校验已有数据

    检查数据完整性、连续性和正确性。

    \b
    示例:
        af data validate -s akshare -d stock_daily
        af data validate -s wind -d daily_quotes --start-date 2026-05-01
    """
    sources = _get_available_sources()
    if source not in sources:
        click.echo(f"✗ Unknown source: {source}", err=True)
        click.echo(f"  Available: {', '.join(sorted(sources.keys()))}")
        raise click.Abort()

    connector = _get_connector(source)
    if connector is None:
        click.echo(f"✗ Failed to instantiate connector for: {source}", err=True)
        raise click.Abort()

    click.echo(f"\nValidating: {source}/{dataset}")
    click.echo("-" * 50)

    try:
        validate_params: dict = {}
        if start_date:
            validate_params["start_date"] = start_date
        if end_date:
            validate_params["end_date"] = end_date

        report = connector.validate_existing(dataset=dataset, **validate_params)

        click.echo(f"  Total checked: {report.total_checked}")
        click.echo(f"  Passed:        {report.passed}")
        click.echo(f"  Failed:        {report.failed}")

        if report.issues:
            click.echo(f"\n  Issues ({len(report.issues)}):")
            for issue in report.issues[:10]:
                click.echo(f"    - [{issue.get('index', '?')}] {issue.get('issue', '?')}")
                if "values" in issue:
                    for k, v in issue["values"].items():
                        click.echo(f"        {k}: {v}")
            if len(report.issues) > 10:
                click.echo(f"    ... and {len(report.issues) - 10} more")

        if report.failed == 0:
            click.echo("\n✓ All checks passed")
        else:
            click.echo(f"\n⚠ {report.failed} checks failed")

    except Exception as e:
        click.echo(f"\n✗ Validation failed: {e}", err=True)
        logger.error(
            "data_validate_failed",
            extra={"source": source, "dataset": dataset, "error": str(e)},
            exc_info=True,
        )
        raise click.Abort()


# ---------------------------------------------------------------------------
# data status — 查看数据整体状态（替代 af crawl status + af knowledge status）
# ---------------------------------------------------------------------------


@data_group.command(name="status")
@click.option("--source", "-s", type=str, help="特定数据源 (可选，不指定则显示全部)")
def data_status_command(source: Optional[str]) -> None:
    """查看数据采集和加工的整体状态

    聚合 connector 健康状态 + 采集历史 + Worker 状态。

    \b
    示例:
        af data status
        af data status -s cls
    """
    # 1. Connector 健康状态
    if source:
        sources = _get_available_sources()
        if source not in sources:
            click.echo(f"✗ Unknown source: {source}", err=True)
            click.echo(f"  Available: {', '.join(sorted(sources.keys()))}")
            raise click.Abort()

        try:
            connector = _get_connector(source)
        except Exception as e:
            click.echo(f"✗ Failed to instantiate connector '{source}': {e}", err=True)
            raise click.Abort()

        if connector:
            try:
                health = connector.health_check()
            except Exception as e:
                click.echo(f"  ⚠ Health check crashed: {e}", err=True)
                health = None

            if health is None:
                status_icon, status_label = "✗", "UNKNOWN"
            else:
                status_icon = {
                    "healthy": "✓",
                    "degraded": "⚠",
                    "unavailable": "✗",
                    "unknown": "?",
                }.get(health.value, "?")
                status_label = health.value.upper()

            click.echo(f"\nData Status: {source}")
            click.echo("=" * 50)
            click.echo(f"  Health: {status_icon} {status_label}")
            click.echo(f"  Type:   {connector.asset_type}")
            click.echo(f"  Datasets: {', '.join(connector.datasets)}")
            click.echo("=" * 50)
        else:
            click.echo(f"✗ Failed to instantiate connector: {source}", err=True)
    else:
        click.echo("\nData Source Overview")
        click.echo("=" * 70)

        sources = _get_available_sources()
        healthy = degraded = unavailable = 0

        for src_name in sorted(sources.keys()):
            try:
                connector = _get_connector(src_name)
            except Exception as e:
                click.echo(f"  ✗ {src_name:12s} [unavailable   ] init failed: {e}")
                unavailable += 1
                continue

            if connector:
                try:
                    health = connector.health_check()
                except Exception:
                    health = None

                if health is None:
                    icon, label = "?", "unknown"
                    unavailable += 1
                elif health.value == "healthy":
                    icon, label = "✓", "healthy"
                    healthy += 1
                elif health.value == "degraded":
                    icon, label = "⚠", "degraded"
                    degraded += 1
                else:
                    icon, label = "✗", "unavailable"
                    unavailable += 1

                datasets_str = ", ".join(connector.datasets)
                click.echo(f"  {icon} {src_name:12s} [{label:12s}] datasets: {datasets_str}")
            else:
                click.echo(f"  ✗ {src_name:12s} [unavailable   ] failed to load")
                unavailable += 1

        click.echo("-" * 70)
        click.echo(
            f"  Total: {len(sources)} | Healthy: {healthy} | Degraded: {degraded} | Unavailable: {unavailable}"
        )
        click.echo("=" * 70)

    # 2. Worker 状态
    click.echo()
    try:
        from workers.knowledge_worker import get_all_worker_statuses

        workers = get_all_worker_statuses()
        if workers:
            alive = [w for w in workers if w["alive"]]
            click.echo(f"Knowledge Workers: {len(alive)}/{len(workers)} alive")
        else:
            click.echo("Knowledge Workers: not started")
    except Exception:
        pass

    # 3. Scheduler 状态
    try:
        from services.crawl_scheduler import get_scheduler_process_status

        sched = get_scheduler_process_status()
        if sched.get("alive"):
            click.echo(f"Crawl Scheduler: running (PID {sched.get('pid')})")
        else:
            click.echo("Crawl Scheduler: not running")
    except Exception:
        pass

    click.echo()


# ---------------------------------------------------------------------------
# data file — 摄入单个文件（替代 af ingest file）
# ---------------------------------------------------------------------------


@data_group.command(name="file")
@click.option("--file", "-f", required=True, help="输入文件路径")
@click.option("--source-type", "-t", default="report", help="来源类型")
@click.option("--source-name", "-s", help="来源名称")
@click.option("--title", help="文档标题")
def data_file_command(file: str, source_type: str, source_name: str, title: str) -> None:
    """摄入单个文件并提取断言和事件

    \b
    示例:
        af data file -f report.pdf -t report -s "券商研报"
        af data file -f news.txt -t news
    """
    from services.ingest_service import IngestService

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
        click.echo(f"Document ID:          {result['doc_id']}")
        click.echo(f"Title:                {result['title']}")
        click.echo("-" * 60)
        click.echo(f"Assertions extracted: {result['assertions_extracted']}")
        click.echo(f"  - Approved:         {result['assertions_approved']}")
        click.echo(f"  - Pending review:   {result['assertions_pending']}")
        click.echo("-" * 60)
        click.echo(f"Events extracted:     {result['events_extracted']}")
        click.echo(f"  - Approved:         {result['events_approved']}")
        click.echo(f"  - Pending review:   {result['events_pending']}")
        click.echo("=" * 60)

        if result["assertions_pending"] > 0 or result["events_pending"] > 0:
            click.echo("\nTip: Use 'af review list' to review pending items.")

    except Exception as e:
        click.echo(f"\n✗ Failed to ingest file: {e}", err=True)
        logger.error(
            "data_file_failed",
            extra={"error": str(e), "file_path": str(file_path)},
            exc_info=True,
        )
        raise click.Abort()


# ---------------------------------------------------------------------------
# data schedule — 调度管理子命令组
# ---------------------------------------------------------------------------


@data_group.command(name="stream")
@click.option("--source", "-s", default="cjpy", help="数据源（默认 cjpy）")
@click.option("--codes", "-c", required=True, help="证券代码，逗号分隔（如 SH600519,SZ000001）")
@click.option("--fields", "-f", help="订阅字段，逗号分隔（默认核心行情字段）")
@click.option("--once", is_flag=True, default=False, help="单次拉取后退出（不持续订阅）")
@click.option("--timeout", "-t", type=int, default=30, help="单次模式超时秒数（默认 30）")
def data_stream_command(source: str, codes: str, fields: str, once: bool, timeout: int) -> None:
    """启动 Cjpy 实时行情订阅

    通过 Cjpy HTTP Streaming 订阅实时行情，事件发布到 SystemEventBus，
    浏览器可通过 SSE 接收推送。

    \b
    示例:
        af data stream --codes SH600519
        af data stream --codes SH600519,SZ000001 --fields price,StockName
        af data stream --codes SH600519 --once --timeout 10

    \b
    常用字段:
        StockName price open high low pre_close volume amount
        change changeRatio highLimit lowLimit
    """
    import signal as _signal
    import sys as _sys
    import time as _time

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    from services.realtime_bridge import RealtimeBridge

    click.echo("\nCjpy Real-Time Stream")
    click.echo("=" * 60)
    click.echo(f"  Source:  {source}")
    click.echo(f"  Codes:   {', '.join(code_list)}")
    click.echo(
        f"  Fields:  {', '.join(field_list) if field_list else 'default (core quote fields)'}"
    )
    click.echo(
        f"  Mode:    {'once (exit after first event)' if once else 'continuous (Ctrl+C to stop)'}"
    )
    click.echo("=" * 60)

    bridge = RealtimeBridge(codes=code_list, fields=field_list)

    if once:
        # 单次模式：启动订阅，等待第一个事件，然后退出
        click.echo("\nWaiting for first event...")
        bridge.start()

        deadline = _time.time() + timeout
        prev_count = 0
        while _time.time() < deadline:
            _time.sleep(0.5)
            current_count = bridge._event_count
            if current_count > prev_count:
                click.echo(f"✓ Received event (total: {current_count})")
                break
            prev_count = current_count
        else:
            click.echo(f"✗ No event received within {timeout}s")

        status = bridge.get_status()
        bridge.stop()
        click.echo(f"\nEvents received: {status['event_count']}")
        click.echo(f"Errors:          {status['error_count']}")
        click.echo(f"Duration:        {status['uptime_seconds']}s")
    else:
        # 持续模式：一直运行直到 Ctrl+C
        click.echo("\nStreaming... Press Ctrl+C to stop\n")

        def _on_signal(signum: int, frame: Any) -> None:
            click.echo("\n\nStopping stream...")
            bridge.stop()
            status = bridge.get_status()
            click.echo(f"\nEvents received: {status['event_count']}")
            click.echo(f"Errors:          {status['error_count']}")
            click.echo(f"Duration:        {status['uptime_seconds']}s")
            _sys.exit(0)

        _signal.signal(_signal.SIGINT, _on_signal)
        _signal.signal(_signal.SIGTERM, _on_signal)

        bridge.start()

        try:
            while bridge.running:
                _time.sleep(1)
                if bridge._event_count > 0 and bridge._event_count % 10 == 0:
                    click.echo(f"  Events: {bridge._event_count}", err=False)
        except KeyboardInterrupt:
            pass
        finally:
            bridge.stop()


@data_group.group(name="schedule")
def schedule_group() -> None:
    """采集调度器管理

    \b
    示例:
        af data schedule start
        af data schedule stop
        af data schedule status
    """
    pass


@schedule_group.command(name="start")
def schedule_start_command() -> None:
    """启动采集调度器（后台进程）

    示例:
        af data schedule start
    """
    import subprocess
    import sys

    from services.crawl_scheduler import get_scheduler_process_status

    process_status = get_scheduler_process_status()
    if process_status["alive"]:
        click.echo(f"✓ Scheduler already running (PID {process_status['pid']})")
        return

    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    worker_module = "workers.crawl_scheduler_worker"

    click.echo("Starting crawl scheduler...")
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
        click.echo(f"✗ Failed to start scheduler: {e}", err=True)
        logger.error("schedule_start_failed", extra={"error": str(e)}, exc_info=True)
        raise click.Abort()


@schedule_group.command(name="stop")
def schedule_stop_command() -> None:
    """停止采集调度器

    示例:
        af data schedule stop
    """
    import os as _os
    import signal as _signal

    pid_files = list(Path("logs").glob("crawl_scheduler*.pid"))
    if not pid_files:
        click.echo("✓ No scheduler PID file found (scheduler not running)")
        return

    stopped = 0
    for pid_file in pid_files:
        try:
            pid = int(pid_file.read_text().strip())
            _os.kill(pid, _signal.SIGTERM)
            click.echo(f"  Stopped scheduler (PID {pid})")
            pid_file.unlink(missing_ok=True)
            stopped += 1
        except ProcessLookupError:
            click.echo(f"  PID {pid_file} not found (already stopped)")
            pid_file.unlink(missing_ok=True)
        except Exception as e:
            click.echo(f"  Failed to stop: {e}", err=True)

    if stopped > 0:
        click.echo(f"✓ Stopped {stopped} scheduler process(es)")


@schedule_group.command(name="status")
def schedule_status_command() -> None:
    """查看采集调度器状态

    示例:
        af data schedule status
    """
    from services.crawl_scheduler import build_scheduler_status, get_scheduler_process_status

    process_status = get_scheduler_process_status()
    db_status = build_scheduler_status()

    click.echo("\nCrawl Scheduler Status")
    click.echo("=" * 60)
    click.echo(f"Process alive: {process_status.get('alive')}")
    click.echo(f"PID:           {process_status.get('pid')}")

    sources = db_status.get("sources", [])
    if sources:
        click.echo("\nSources:")
        for src in sources:
            enabled = "✓" if src.get("enabled") else "✗"
            click.echo(f"  {enabled} {src.get('source_type')}")
            click.echo(f"    Interval: {src.get('interval_minutes')} min")
            click.echo(f"    Should run: {src.get('should_run')} ({src.get('run_reason')})")

    jobs = db_status.get("jobs", [])
    if jobs:
        click.echo("\nScheduled jobs:")
        for job in jobs:
            click.echo(f"  - {job.get('id')}: next={job.get('next_run_time')}")

    click.echo("=" * 60)


# ---------------------------------------------------------------------------
# data schedule market — 市场数据自动调度管理子命令组
# ---------------------------------------------------------------------------


@schedule_group.group(name="market")
def schedule_market_group() -> None:
    """市场数据自动调度管理

    \b
    示例:
        af data schedule market start
        af data schedule market stop
        af data schedule market status
    """
    pass


@schedule_market_group.command(name="start")
def market_schedule_start_command() -> None:
    """启动市场数据调度器（后台进程）

    每日收盘后自动拉取行情，定期检测数据缺口并回补。

    示例:
        af data schedule market start
    """
    import os as _os
    import subprocess
    import sys

    # 检查是否已在运行
    pid_file = Path("logs") / "market_data_scheduler.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            _os.kill(pid, 0)
            click.echo(f"✓ Market data scheduler already running (PID {pid})")
            return
        except (OSError, ValueError):
            pid_file.unlink(missing_ok=True)

    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    worker_module = "workers.market_data_scheduler_worker"

    click.echo("Starting market data scheduler...")
    try:
        subprocess.Popen(
            [sys.executable, "-m", worker_module],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        click.echo("✓ Market data scheduler started in background")
        click.echo("  Daily cron: 15:37 (after market close)")
        click.echo("  Gap check:  every 4 hours")
    except Exception as e:
        click.echo(f"✗ Failed to start market data scheduler: {e}", err=True)
        logger.error(
            "market_schedule_start_failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise click.Abort()


@schedule_market_group.command(name="stop")
def market_schedule_stop_command() -> None:
    """停止市场数据调度器

    示例:
        af data schedule market stop
    """
    import os as _os
    import signal as _signal

    pid_files = list(Path("logs").glob("market_data_scheduler*.pid"))
    if not pid_files:
        click.echo("✓ No market data scheduler PID file found (not running)")
        return

    stopped = 0
    for pid_file in pid_files:
        try:
            pid = int(pid_file.read_text().strip())
            _os.kill(pid, _signal.SIGTERM)
            click.echo(f"  Stopped market data scheduler (PID {pid})")
            pid_file.unlink(missing_ok=True)
            stopped += 1
        except ProcessLookupError:
            click.echo(f"  PID {pid_file} not found (already stopped)")
            pid_file.unlink(missing_ok=True)
        except Exception as e:
            click.echo(f"  Failed to stop: {e}", err=True)

    if stopped > 0:
        click.echo(f"✓ Stopped {stopped} market data scheduler process(es)")


@schedule_market_group.command(name="status")
def market_schedule_status_command() -> None:
    """查看市场数据调度器状态

    示例:
        af data schedule market status
    """
    import json as _json
    import os as _os
    from datetime import datetime as _datetime

    pid_file = Path("logs") / "market_data_scheduler.pid"
    heartbeat_file = Path("logs") / "market_data_scheduler.heartbeat.json"

    click.echo("\nMarket Data Scheduler Status")
    click.echo("=" * 60)

    # 检查进程
    alive = False
    pid = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            _os.kill(pid, 0)
            alive = True
        except (OSError, ValueError):
            pass

    status_icon = "✓" if alive else "✗"
    click.echo(f"Process alive: {status_icon}")
    click.echo(f"PID:           {pid or 'N/A'}")

    # 检查心跳
    if heartbeat_file.exists():
        try:
            hb = _json.loads(heartbeat_file.read_text())
            ts = _datetime.fromtimestamp(hb.get("timestamp", 0))
            activity = hb.get("activity", "unknown")
            click.echo(f"Last heartbeat: {ts.isoformat()}")
            click.echo(f"Last activity:  {activity}")
        except Exception:
            click.echo("Heartbeat:      unreadable")

    # 尝试获取更多状态（仅在 worker 进程内部可用）
    try:
        from services.market_data_scheduler import get_market_data_scheduler

        scheduler = get_market_data_scheduler()
        if scheduler.running:
            sched_status = scheduler.get_status()
            stats = sched_status.get("stats", {})
            click.echo(f"\nDataset:        {sched_status.get('dataset', 'daily_quotes')}")
            click.echo(f"Daily cron:     {sched_status.get('daily_cron', 'N/A')}")
            click.echo(f"Last daily run: {stats.get('last_daily_run', 'never')}")
            click.echo(f"Last gap check: {stats.get('last_gap_check', 'never')}")
            click.echo(f"Last gap count: {stats.get('last_gap_count', 0)}")
            click.echo(f"Total ingested: {stats.get('total_ingested', 0)}")
            click.echo(f"Total failures: {stats.get('total_failures', 0)}")
    except Exception:
        pass

    click.echo("=" * 60)


# ---------------------------------------------------------------------------
# data workers — 知识加工 Worker 管理子命令组
# ---------------------------------------------------------------------------


@data_group.group(name="workers")
def workers_group() -> None:
    """知识加工 Worker 管理

    \b
    示例:
        af data workers start
        af data workers stop
        af data workers status
    """
    pass


@workers_group.command(name="start")
@click.option("--num", "-n", type=int, default=1, help="Worker 进程数量 (默认 1)")
def workers_start_command(num: int) -> None:
    """启动知识加工 Worker（后台进程）

    示例:
        af data workers start
        af data workers start -n 4
    """
    import subprocess
    import sys

    from workers.knowledge_worker import get_all_worker_statuses

    existing = get_all_worker_statuses()
    alive_workers = [w for w in existing if w["alive"]]

    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    worker_module = "workers.knowledge_worker"

    if num < 1:
        click.echo("✗ --num must be >= 1", err=True)
        raise click.Abort()

    started = 0
    for worker_id in range(1, num + 1):
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
                "worker_start_failed",
                extra={"worker_id": worker_id, "error": str(e)},
                exc_info=True,
            )

    if started > 0:
        click.echo(f"✓ {started} knowledge worker(s) started")
    elif not any(w.get("worker_id") and w["alive"] for w in alive_workers):
        click.echo("✓ All requested workers already running")


@workers_group.command(name="stop")
def workers_stop_command() -> None:
    """停止所有知识加工 Worker 进程

    示例:
        af data workers stop
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


@workers_group.command(name="status")
def workers_status_command() -> None:
    """查看所有知识加工 Worker 状态

    示例:
        af data workers status
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
