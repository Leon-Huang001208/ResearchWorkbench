"""Research Workbench CLI 主入口。"""

import json
import sys
from pathlib import Path

import click

from app.cli.commands.akshare import akshare

# 导入子命令
from app.cli.commands.analyze import analyze
from app.cli.commands.ask import ask
from app.cli.commands.backtest import backtest
from app.cli.commands.data import data_group as data
from app.cli.commands.ingest import crawl, ingest, knowledge
from app.cli.commands.memory import memory
from app.cli.commands.report import report
from app.cli.commands.review import review
from app.cli.commands.scenario import scenario
from app.cli.commands.signal import signal
from app.cli.commands.timing import timing
from app.research_web.data_migration import (
    DataMigrationError,
    migrate_data,
)
from app.research_web.data_migration import (
    archive_source as archive_legacy_source,
)
from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
    format_status,
)
from core.observability import configure_logging

LEGACY_RESEARCH_DATA_DIR = ".alpha" + "foundry"

# 强制 stdout/stderr 使用 UTF-8，防止 Windows GBK 终端上 UnicodeEncodeError
# （特殊字符如 ✓ ✗ 及中日文内容会触发 GBK 编码失败）
if hasattr(sys.stdout, "fileno"):
    try:
        sys.stdout = open(
            sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False, buffering=1
        )
    except Exception:
        pass
if hasattr(sys.stderr, "fileno"):
    try:
        sys.stderr = open(
            sys.stderr.fileno(), mode="w", encoding="utf-8", closefd=False, buffering=1
        )
    except Exception:
        pass


@click.group()
@click.option("--log-level", default="INFO", help="日志级别：DEBUG, INFO, WARNING, ERROR")
@click.option("--log-file", help="日志文件路径")
@click.version_option(version="0.1.0")
def cli(log_level: str, log_file: str | None) -> None:
    """Research Workbench - 本地优先的研究工作台。"""
    # 配置日志
    log_path: str | None = str(log_file) if log_file else None
    configure_logging(level=log_level, log_file=log_path)


@click.group()
def web() -> None:
    """管理 Web 与专属 DSH 后台服务。"""


def _run_web_action(action: str, *, force: bool = False, open_browser: bool = True) -> None:
    manager = WebServiceManager()
    try:
        if action == "start":
            status = manager.start(open_browser=open_browser)
        elif action == "stop":
            status = manager.stop()
        elif action == "restart":
            status = manager.restart(force=force, open_browser=open_browser)
        else:
            status = manager.status()
        click.echo(format_status(status))
    except ServiceManagerError as exc:
        raise click.ClickException(str(exc)) from exc


@web.command("start")
@click.option("--no-open", is_flag=True, help="启动后不打开浏览器")
def web_start(no_open: bool) -> None:
    """幂等启动 3081 DSH 和 8088 Web。"""
    _run_web_action("start", open_browser=not no_open)


@web.command("status")
def web_status() -> None:
    """查看两个项目服务的归属与健康状态。"""
    _run_web_action("status", open_browser=False)


@web.command("stop")
def web_stop() -> None:
    """停止仅属于当前项目的 8088/3081 进程。"""
    _run_web_action("stop", open_browser=False)


@web.command("restart")
@click.option("--force", is_flag=True, help="允许中断活动研究")
@click.option("--no-open", is_flag=True, help="重启后不打开浏览器")
def web_restart(force: bool, no_open: bool) -> None:
    """在无活动研究时重启项目服务。"""
    _run_web_action("restart", force=force, open_browser=not no_open)


@cli.command("migrate-research-data")
@click.option(
    "--source",
    type=click.Path(path_type=Path),
    default=lambda: Path.home() / LEGACY_RESEARCH_DATA_DIR / "research-web",
    show_default=f"~/{LEGACY_RESEARCH_DATA_DIR}/research-web",
)
@click.option(
    "--target",
    type=click.Path(path_type=Path),
    default=lambda: Path.home() / ".research-workbench" / "research-web",
    show_default="~/.research-workbench/research-web",
)
@click.option("--dry-run", is_flag=True, help="只计算迁移范围和哈希，不写文件")
@click.option("--archive-source", is_flag=True, help="校验完成后将旧目录移为只读备份")
def migrate_research_data(source: Path, target: Path, dry_run: bool, archive_source: bool) -> None:
    """迁移研究会话、附件、能力版本、数据集和产物，不复制凭据。"""
    try:
        result = migrate_data(source, target, dry_run=dry_run)
        if archive_source and not dry_run:
            result["source_archive"] = str(archive_legacy_source(source))
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    except DataMigrationError as exc:
        raise click.ClickException(str(exc)) from exc


# 注册子命令
cli.add_command(analyze)
cli.add_command(ask)
cli.add_command(report)
cli.add_command(scenario)
cli.add_command(ingest)
cli.add_command(crawl)
cli.add_command(review)
cli.add_command(signal)
cli.add_command(backtest)
cli.add_command(timing)
cli.add_command(memory)
cli.add_command(akshare)
cli.add_command(knowledge)
cli.add_command(data)
cli.add_command(web)


if __name__ == "__main__":
    cli()
