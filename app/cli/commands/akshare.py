"""
AkShare 数据 CLI 命令
"""

import click

from core.observability import get_logger
from data_layer.crawlers.akshare import AkShareAdapter, AkShareConfig

logger = get_logger(__name__)


@click.group(name="akshare")
def akshare_group():
    """AkShare 开源金融数据命令组"""
    pass


@akshare_group.command(name="health")
def akshare_health_command():
    """检查 AkShare 是否可用并获取状态"""
    click.echo("Checking AkShare availability...")

    try:
        config = AkShareConfig(enable_cache=False, verbose=True)
        adapter = AkShareAdapter(config)
        status = adapter.health_check()

        click.echo("\n" + "=" * 60)
        click.echo("AkShare Status")
        click.echo("=" * 60)

        if status["status"] == "healthy":
            click.echo(f"✓ Status: {status['status']}")
            click.echo(f"✓ Source: {status['source']}")
            click.echo(f"✓ Checked at: {status['timestamp']}")
        else:
            click.echo(f"✗ Status: {status['status']}")
            if "error" in status:
                click.echo(f"✗ Error: {status['error']}")

        click.echo("=" * 60)

    except Exception as e:
        click.echo(f"\n✗ Failed to check AkShare status: {e}", err=True)
        logger.error("Failed to check AkShare status", error=str(e), exc_info=True)
        raise click.Abort()


@akshare_group.command(name="stocks")
@click.option("--limit", "-n", type=int, default=50, help="返回股票数量限制")
@click.option("--output", "-o", help="输出文件路径 (JSON)")
def akshare_stocks_command(limit: int, output: str | None):
    """获取股票列表

    示例:
        rwb akshare stocks --limit 100
        rwb akshare stocks -n 50 -o stocks.json
    """
    click.echo(f"Fetching stock list (limit={limit})...")

    try:
        config = AkShareConfig(enable_cache=False, verbose=True)
        adapter = AkShareAdapter(config)
        stocks = adapter.market.get_stock_list(limit=limit)

        click.echo("\n" + "=" * 60)
        click.echo(f"Fetched {len(stocks)} stocks")
        click.echo("=" * 60)

        if stocks:
            # 显示前 20 个
            display_count = min(len(stocks), 20)
            click.echo(f"\nShowing first {display_count} stocks:\n")
            for stock in stocks[:display_count]:
                click.echo(
                    f"  {stock.symbol:<12} {stock.name:<15} {stock.market:<3} {stock.industry or 'N/A'}"
                )

            if len(stocks) > display_count:
                click.echo(f"\n  ... and {len(stocks) - display_count} more")

            # 保存到文件
            if output:
                import json

                with open(output, "w", encoding="utf-8") as f:
                    data = [
                        {
                            "symbol": s.symbol,
                            "name": s.name,
                            "market": s.market,
                            "industry": s.industry,
                        }
                        for s in stocks
                    ]
                    json.dump(data, f, ensure_ascii=False, indent=2)
                click.echo(f"\n✓ Saved to {output}")

        click.echo("\n" + "=" * 60)

    except Exception as e:
        click.echo(f"\n✗ Failed to fetch stocks: {e}", err=True)
        logger.error("Failed to fetch stocks", error=str(e), exc_info=True)
        raise click.Abort()


@akshare_group.command(name="news")
@click.option("--limit", "-n", type=int, default=20, help="返回新闻数量限制")
@click.option("--keyword", "-k", multiple=True, help="关键词过滤 (可多次使用)")
@click.option(
    "--source",
    "-s",
    type=click.Choice(["sina", "eastmoney", "all"]),
    default="all",
    help="新闻来源",
)
@click.option("--output", "-o", help="输出文件路径 (JSON)")
def akshare_news_command(limit: int, keyword: tuple[str], source: str, output: str | None):
    """获取财经新闻

    示例:
        rwb akshare news --limit 50
        rwb akshare news -k 银行 -k 金融 -s sina
        rwb akshare news -n 20 -o news.json
    """
    click.echo(f"Fetching news (limit={limit}, source={source})...")

    try:
        config = AkShareConfig(
            enable_cache=False,
            verbose=True,
            news_limit=limit,
            news_sources=[source] if source != "all" else ["sina", "eastmoney"],
        )
        adapter = AkShareAdapter(config)

        keywords = list(keyword) if keyword else None

        if source == "all":
            news_list = adapter.news.fetch_all_news(limit=limit, keywords=keywords)
        elif source == "sina":
            news_list = adapter.news.fetch_sina_news(limit=limit, keywords=keywords)
        elif source == "eastmoney":
            news_list = adapter.news.fetch_eastmoney_news(limit=limit, keywords=keywords)
        else:
            news_list = []

        click.echo("\n" + "=" * 60)
        click.echo(f"Fetched {len(news_list)} news")
        click.echo("=" * 60)

        if news_list:
            # 显示前 10 个
            display_count = min(len(news_list), 10)
            click.echo(f"\nShowing first {display_count} news:\n")
            for i, news in enumerate(news_list[:display_count], 1):
                time_str = (
                    news.publish_time.strftime("%Y-%m-%d %H:%M") if news.publish_time else "N/A"
                )
                click.echo(f"{i}. [{news.source.upper()}] {time_str}")
                click.echo(f"   {news.title}")
                if news.summary:
                    click.echo(f"   {news.summary[:80]}...")
                click.echo()

            if len(news_list) > display_count:
                click.echo(f"\n  ... and {len(news_list) - display_count} more")

            # 保存到文件
            if output:
                import json

                with open(output, "w", encoding="utf-8") as f:
                    data = [
                        {
                            "title": n.title,
                            "content": n.content,
                            "publish_time": n.publish_time.isoformat() if n.publish_time else None,
                            "source": n.source,
                            "url": n.url,
                        }
                        for n in news_list
                    ]
                    json.dump(data, f, ensure_ascii=False, indent=2)
                click.echo(f"\n✓ Saved to {output}")

        click.echo("\n" + "=" * 60)

    except Exception as e:
        click.echo(f"\n✗ Failed to fetch news: {e}", err=True)
        logger.error("Failed to fetch news", error=str(e), exc_info=True)
        raise click.Abort()


@akshare_group.command(name="macro")
@click.option(
    "--indicator",
    "-i",
    type=click.Choice(["gdp", "cpi", "pmi", "rate", "money", "all"]),
    default="all",
    help="宏观指标",
)
@click.option("--output", "-o", help="输出文件路径 (JSON)")
def akshare_macro_command(indicator: str, output: str | None):
    """获取宏观经济数据

    示例:
        rwb akshare macro --indicator gdp
        rwb akshare macro -i all
        rwb akshare macro -i cpi -o macro.json
    """
    click.echo(f"Fetching macro data (indicator={indicator})...")

    try:
        config = AkShareConfig(enable_cache=False, verbose=True)
        adapter = AkShareAdapter(config)

        all_data = []

        indicator_map = {
            "gdp": ("GDP", adapter.macro.get_gdp),
            "cpi": ("CPI", adapter.macro.get_cpi),
            "pmi": ("PMI", adapter.macro.get_pmi),
            "rate": ("Interest Rate", adapter.macro.get_interest_rate),
            "money": ("Money Supply", adapter.macro.get_money_supply),
        }

        if indicator == "all":
            indicators_to_fetch = list(indicator_map.keys())
        else:
            indicators_to_fetch = [indicator]

        for ind in indicators_to_fetch:
            name, func = indicator_map[ind]
            click.echo(f"  Fetching {name}...")
            data = func()
            all_data.extend(data)
            click.echo(f"  Fetched {len(data)} {name} records")

        click.echo("\n" + "=" * 60)
        click.echo(f"Fetched {len(all_data)} total macro records")
        click.echo("=" * 60)

        if all_data:
            # 分组显示
            from collections import defaultdict

            data_by_indicator = defaultdict(list)
            for d in all_data:
                data_by_indicator[d.indicator].append(d)

            for ind_name, data_list in data_by_indicator.items():
                display_count = min(len(data_list), 5)
                click.echo(f"\n{ind_name} (total {len(data_list)}):")
                for d in data_list[:display_count]:
                    click.echo(f"  {d.period}: {d.value} {d.unit or ''}")
                if len(data_list) > display_count:
                    click.echo(f"  ... and {len(data_list) - display_count} more")

            # 保存到文件
            if output:
                import json

                with open(output, "w", encoding="utf-8") as f:
                    data = [
                        {
                            "indicator": d.indicator,
                            "value": d.value,
                            "period": d.period,
                            "unit": d.unit,
                            "source": d.source,
                        }
                        for d in all_data
                    ]
                    json.dump(data, f, ensure_ascii=False, indent=2)
                click.echo(f"\n✓ Saved to {output}")

        click.echo("\n" + "=" * 60)

    except Exception as e:
        click.echo(f"\n✗ Failed to fetch macro data: {e}", err=True)
        logger.error("Failed to fetch macro data", error=str(e), exc_info=True)
        raise click.Abort()


@akshare_group.command(name="quotes")
@click.option("--symbol", "-s", required=True, help="股票代码 (如 600000.SH)")
@click.option("--start-date", help="开始日期 (YYYY-MM-DD, 默认一年前)")
@click.option("--end-date", help="结束日期 (YYYY-MM-DD, 默认今天)")
@click.option(
    "--period", type=click.Choice(["daily", "weekly", "monthly"]), default="daily", help="周期"
)
@click.option("--adjust", type=click.Choice(["qfq", "hfq", "none"]), default="qfq", help="复权方式")
@click.option("--output", "-o", help="输出文件路径 (JSON/CSV)")
def akshare_quotes_command(
    symbol: str,
    start_date: str | None,
    end_date: str | None,
    period: str,
    adjust: str,
    output: str | None,
):
    """获取历史行情数据

    示例:
        rwb akshare quotes --symbol 600000.SH
        rwb akshare quotes -s 000001.SZ --start-date 2024-01-01 --period weekly
        rwb akshare quotes -s 600519.SH -o quotes.csv
    """
    click.echo(f"Fetching quotes for {symbol}...")
    click.echo(f"  Period: {period}")
    click.echo(f"  Adjust: {adjust}")

    try:
        config = AkShareConfig(
            enable_cache=False,
            verbose=True,
            default_period=period,
            default_adjust=adjust,
        )
        adapter = AkShareAdapter(config)

        # 解析日期
        from datetime import date, datetime, timedelta

        end = date.today()
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()

        start = end - timedelta(days=365)
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()

        quotes = adapter.market.get_historical_data(
            symbol=symbol,
            start_date=start,
            end_date=end,
        )

        click.echo("\n" + "=" * 60)
        click.echo(f"Fetched {len(quotes)} quotes for {symbol}")
        click.echo("=" * 60)

        if quotes:
            # 显示前 20 个
            display_count = min(len(quotes), 20)
            click.echo(f"\nShowing first {display_count} quotes:\n")
            click.echo(
                f"{'Date':<12} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Volume':>12}"
            )
            click.echo("-" * 70)
            for q in quotes[:display_count]:
                date_str = q.timestamp.strftime("%Y-%m-%d")
                open_str = f"{q.open:.2f}" if q.open else "N/A"
                high_str = f"{q.high:.2f}" if q.high else "N/A"
                low_str = f"{q.low:.2f}" if q.low else "N/A"
                close_str = f"{q.close:.2f}" if q.close else "N/A"
                vol_str = f"{q.volume:,}" if q.volume else "N/A"
                click.echo(
                    f"{date_str:<12} {open_str:>8} {high_str:>8} {low_str:>8} {close_str:>8} {vol_str:>12}"
                )

            if len(quotes) > display_count:
                click.echo(f"\n  ... and {len(quotes) - display_count} more")

            # 保存到文件
            if output:
                if output.endswith(".csv"):
                    import csv

                    with open(output, "w", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            ["date", "open", "high", "low", "close", "volume", "amount", "turnover"]
                        )
                        for q in quotes:
                            writer.writerow(
                                [
                                    q.timestamp.strftime("%Y-%m-%d"),
                                    q.open,
                                    q.high,
                                    q.low,
                                    q.close,
                                    q.volume,
                                    q.amount,
                                    q.turnover,
                                ]
                            )
                else:
                    import json

                    data = [
                        {
                            "date": q.timestamp.isoformat(),
                            "open": q.open,
                            "high": q.high,
                            "low": q.low,
                            "close": q.close,
                            "volume": q.volume,
                            "amount": q.amount,
                            "turnover": q.turnover,
                        }
                        for q in quotes
                    ]
                    with open(output, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                click.echo(f"\n✓ Saved to {output}")

        click.echo("\n" + "=" * 60)

    except Exception as e:
        click.echo(f"\n✗ Failed to fetch quotes: {e}", err=True)
        logger.error("Failed to fetch quotes", error=str(e), exc_info=True)
        raise click.Abort()


# 别名
akshare = akshare_group
