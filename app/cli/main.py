"""AlphaFoundry CLI 主入口"""

import sys

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
from core.observability import configure_logging

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
    """AlphaFoundry - 买方投研情报系统"""
    # 配置日志
    log_path: str | None = str(log_file) if log_file else None
    configure_logging(level=log_level, log_file=log_path)


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


if __name__ == "__main__":
    cli()
