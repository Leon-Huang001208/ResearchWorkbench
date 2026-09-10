"""Research Workbench CLI 主入口。"""

import importlib
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import click

from app.research_web.data_migration import (
    DataMigrationError,
    archive_source,
    migrate_data,
)
from app.research_web.report_studio import ReportStudio, ReportStudioError
from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
    format_status,
    format_tabbit_status,
)
from app.research_web.store import Store

LEGACY_RESEARCH_DATA_DIR = ".alpha" + "foundry"
archive_legacy_source = archive_source
LAZY_COMMANDS = {
    "akshare": ("app.cli.commands.akshare", "akshare"),
    "analyze": ("app.cli.commands.analyze", "analyze"),
    "ask": ("app.cli.commands.ask", "ask"),
    "backtest": ("app.cli.commands.backtest", "backtest"),
    "crawl": ("app.cli.commands.ingest", "crawl"),
    "data": ("app.cli.commands.data", "data_group"),
    "ingest": ("app.cli.commands.ingest", "ingest"),
    "knowledge": ("app.cli.commands.ingest", "knowledge"),
    "memory": ("app.cli.commands.memory", "memory"),
    "report": ("app.cli.commands.report", "report"),
    "review": ("app.cli.commands.review", "review"),
    "scenario": ("app.cli.commands.scenario", "scenario"),
    "signal": ("app.cli.commands.signal", "signal"),
    "timing": ("app.cli.commands.timing", "timing"),
}


class LazyCommandGroup(click.Group):
    """Expose legacy commands without importing their runtime until selected."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(set(super().list_commands(ctx)) | set(LAZY_COMMANDS))

    def get_command(self, ctx: click.Context, command_name: str) -> click.Command | None:
        command = super().get_command(ctx, command_name)
        if command is not None or command_name not in LAZY_COMMANDS:
            return command
        module_name, attribute = LAZY_COMMANDS[command_name]
        try:
            module = importlib.import_module(module_name)
            loaded = getattr(module, attribute)
        except (ImportError, AttributeError) as exc:
            raise click.ClickException(
                f"无法加载子命令 {command_name}: {type(exc).__name__}"
            ) from exc
        if not isinstance(loaded, click.Command):
            raise click.ClickException(f"子命令 {command_name} 注册无效")
        return loaded

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        rows: list[tuple[str, str]] = []
        for command_name in self.list_commands(ctx):
            if command_name in LAZY_COMMANDS:
                rows.append((command_name, "历史兼容命令（按需加载）"))
                continue
            command = super().get_command(ctx, command_name)
            if command is not None and not command.hidden:
                rows.append((command_name, command.get_short_help_str()))
        if rows:
            with formatter.section("Commands"):
                formatter.write_dl(rows)


# 强制 stdout/stderr 使用 UTF-8，防止 Windows GBK 终端上 UnicodeEncodeError
# （特殊字符如 ✓ ✗ 及中日文内容会触发 GBK 编码失败）
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", write_through=True)
    except (AttributeError, OSError):
        logging.getLogger(__name__).debug("stdout UTF-8 reconfiguration unavailable")
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", write_through=True)
    except (AttributeError, OSError):
        logging.getLogger(__name__).debug("stderr UTF-8 reconfiguration unavailable")


@click.group(cls=LazyCommandGroup)
@click.option("--log-level", default="INFO", help="日志级别：DEBUG, INFO, WARNING, ERROR")
@click.option("--log-file", help="日志文件路径")
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx: click.Context, log_level: str, log_file: str | None) -> None:
    """Research Workbench - 本地优先的研究工作台。"""
    log_path: str | None = str(log_file) if log_file else None
    if ctx.invoked_subcommand in {
        "web",
        "migrate-research-data",
        "migrate-report-projects",
    }:
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise click.BadParameter("无效日志级别", param_hint="--log-level")
        logging.basicConfig(level=numeric_level, filename=log_path)
        return
    from core.observability import configure_logging

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


@web.command("tabbit-status")
def web_tabbit_status() -> None:
    """查看不含路径、Cookie 或页面元数据的 Tabbit 诊断。"""
    manager = WebServiceManager()
    try:
        click.echo(format_tabbit_status(manager.tabbit_status()))
    except ServiceManagerError as exc:
        raise click.ClickException(str(exc)) from exc


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


@cli.command("migrate-report-projects")
@click.option(
    "--source",
    type=click.Path(path_type=Path),
    default=lambda: Path(__file__).resolve().parents[2] / "report_projects",
    show_default="<project>/report_projects",
)
@click.option(
    "--target",
    type=click.Path(path_type=Path),
    default=lambda: Path.home() / ".research-workbench" / "research-web",
    show_default="~/.research-workbench/research-web",
)
@click.option("--apply", "apply_changes", is_flag=True, help="复制并登记项目；默认仅预检")
def migrate_report_projects(source: Path, target: Path, apply_changes: bool) -> None:
    """预检或迁移旧报告项目；不删除源目录，也不执行其中脚本。"""
    try:
        studio = ReportStudio(SimpleNamespace(store=Store(target)))
        result = studio.migration(source, dry_run=not apply_changes)
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    except (ReportStudioError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


cli.add_command(web)


if __name__ == "__main__":
    cli()
