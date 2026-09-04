"""rwb ask 命令：联网查询后回答问题"""

import click

from core.observability import get_logger
from services.ask_factory import build_ask_service

logger = get_logger(__name__)


@click.command(name="ask")
@click.argument("question")
@click.option(
    "--max-results",
    "-n",
    default=5,
    type=int,
    help="联网搜索最大结果数",
)
@click.option(
    "--no-fetch-content",
    is_flag=True,
    default=False,
    help="不抓取网页正文，只用搜索摘要",
)
def ask(question: str, max_results: int, no_fetch_content: bool) -> None:
    """联网查询后回答问题（始终先联网再综合）.

    QUESTION 为要查询的问题。
    """
    service = build_ask_service()
    try:
        result = service.ask(
            question,
            max_results=max_results,
            fetch_content=not no_fetch_content,
        )
    except Exception as e:
        click.echo(f"查询失败：{e}", err=True)
        logger.error("ask command failed", error=str(e))
        ctx = click.get_current_context()
        ctx.exit(1)
        return

    if not result.online:
        click.echo("[未联网] 本次未获取到联网搜索结果，以下为模型自身知识回答：\n")

    click.echo(result.answer)
    click.echo("")
    click.echo(f"— 模型: {result.model or 'N/A'}")
    click.echo(f"— 来源 ({len(result.sources)}):")
    for i, s in enumerate(result.sources, 1):
        click.echo(f"  [{i}] {s.title} - {s.url}")
