"""
回测 CLI 命令
"""

from pathlib import Path
from typing import Optional

import click

from core.observability import get_logger
from signal_lab.backtests import SimpleBacktester

logger = get_logger(__name__)


@click.command(name="backtest")
@click.option("--file", "-f", help="价格数据文件路径（CSV/JSON）")
@click.option("--symbol", "-s", help="代码（用于示例数据）")
@click.option("--initial-capital", default=1000000, type=float, help="初始资金")
@click.option("--position-size", default=0.1, type=float, help="仓位大小")
@click.option("--output", "-o", help="输出文件路径")
def backtest_command(
    file: Optional[str],
    symbol: Optional[str],
    initial_capital: float,
    position_size: float,
    output: Optional[str],
):
    """
    运行信号回测

    示例:
        rwb backtest --file prices.csv --initial-capital 1000000
        rwb backtest --symbol 600519.SH --position-size 0.2
    """
    import numpy as np
    import pandas as pd

    click.echo("Running backtest...")

    try:
        # 加载数据
        if file:
            file_path = Path(file)
            if file_path.suffix == ".csv":
                prices = pd.read_csv(file_path, parse_dates=True, index_col=0)
            else:
                prices = pd.read_json(file_path)
            click.echo(f"Loaded data from: {file}")
        else:
            # 生成示例数据
            np.random.seed(42)
            dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
            base_price = 100.0
            returns = np.random.normal(0.001, 0.02, 252)
            price_series = base_price * (1 + returns).cumprod()
            prices = pd.DataFrame({"close": price_series}, index=dates)
            click.echo("Using sample price data")

        # 运行回测
        backtester = SimpleBacktester(
            initial_capital=initial_capital,
            position_size=position_size,
        )

        result = backtester.run(prices)

        # 显示结果
        click.echo("\n" + "=" * 60)
        click.echo("BACKTEST RESULTS")
        click.echo("=" * 60)
        click.echo(f"Total Return:      {result.total_return:>10.2%}")
        click.echo(f"Annual Return:     {result.annual_return:>10.2%}")
        click.echo(f"Volatility:        {result.volatility:>10.2%}")
        click.echo(f"Sharpe Ratio:      {result.sharpe_ratio:>10.2f}")
        click.echo(f"Max Drawdown:      {result.max_drawdown:>10.2%}")
        click.echo(f"Win Rate:          {result.win_rate:>10.2%}")
        click.echo(f"Number of Trades:  {result.total_trades:>10}")
        click.echo("=" * 60)

        # 保存结果
        if output:
            output_path = Path(output)
            result_dict = result.to_dict()

            if output_path.suffix == ".json":
                import json

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result_dict, f, ensure_ascii=False, indent=2)
            else:
                # 保存为文本
                output_path.write_text(
                    f"Backtest Results:\n"
                    f"Total Return: {result.total_return:.2%}\n"
                    f"Annual Return: {result.annual_return:.2%}\n"
                    f"Sharpe Ratio: {result.sharpe_ratio:.2f}\n"
                    f"Max Drawdown: {result.max_drawdown:.2%}\n",
                    encoding="utf-8",
                )

            click.echo(f"\n✓ Results saved to: {output_path.absolute()}")

    except Exception as e:
        click.echo(f"\n✗ Backtest failed: {e}", err=True)
        logger.error("Backtest failed", error=str(e), exc_info=True)
        raise click.Abort()


backtest = backtest_command
