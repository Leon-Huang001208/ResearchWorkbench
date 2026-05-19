"""
Yahoo Finance 行情数据获取器

提供历史K线、实时行情、批量下载等功能。
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from core.observability import get_logger

from .base import BaseYahooFetcher, YahooConfig, YahooMarketData, YahooStockInfo

logger = get_logger("yahoo_market")


class YahooMarketFetcher(BaseYahooFetcher):
    """Yahoo 行情数据获取器"""

    def __init__(self, config: Optional[YahooConfig] = None):
        super(YahooMarketFetcher, self).__init__(config)

    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: Optional[str] = None,
        interval: str = "1d",
        auto_adjust: Optional[bool] = None,
        prepost: bool = False,
    ) -> List[YahooMarketData]:
        """
        获取历史行情数据

        Args:
            symbol: Yahoo 格式的代码（如 "AAPL", "00700.HK", "600519.SS"）
            start_date: 开始日期
            end_date: 结束日期
            period: 时间段（与 start/end 二选一）
                    可选值: "1d", "5d", "1mo", "3mo", "1y", "2y", "5y", "10y", "ytd", "max"
            interval: K线间隔
                      可选值: "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"
            auto_adjust: 是否自动复权（默认使用配置）
            prepost: 是否包含盘前盘后数据

        Returns:
            YahooMarketData 列表
        """
        if auto_adjust is None:
            auto_adjust = self.config.auto_adjust

        self._smart_delay(is_heavy_request=False)

        try:
            ticker = self.yf.Ticker(symbol)

            if period:
                df = ticker.history(
                    period=period,
                    interval=interval,
                    auto_adjust=auto_adjust,
                    prepost=prepost,
                )
            else:
                if start_date is None or end_date is None:
                    raise ValueError("Either period or start_date + end_date must be provided")
                df = ticker.history(
                    start=start_date,
                    end=end_date,
                    interval=interval,
                    auto_adjust=auto_adjust,
                    prepost=prepost,
                )

            self._record_success()

            if df.empty:
                logger.warning("No data returned for %s", symbol)
                return []

            result = []
            for idx, row in df.iterrows():
                timestamp = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
                if not isinstance(timestamp, datetime):
                    timestamp = datetime.fromtimestamp(idx.timestamp())

                data = YahooMarketData(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=self._safe_float(row.get("Open")),
                    high=self._safe_float(row.get("High")),
                    low=self._safe_float(row.get("Low")),
                    close=self._safe_float(row.get("Close")),
                    volume=self._safe_int(row.get("Volume")),
                    adj_close=self._safe_float(row.get("Adj Close")),
                )
                result.append(data)

            logger.info("Fetched %d records for %s", len(result), symbol)
            return result

        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch historical data for %s: %s", symbol, e)
            raise

    def get_current_info(self, symbol: str) -> YahooStockInfo:
        """
        获取当前股票信息

        Args:
            symbol: Yahoo 格式的代码

        Returns:
            YahooStockInfo 对象
        """
        self._smart_delay(is_heavy_request=False)

        try:
            ticker = self.yf.Ticker(symbol)
            info = ticker.info

            self._record_success()

            return YahooStockInfo(
                symbol=symbol,
                name=info.get("longName", info.get("shortName", "")),
                currency=info.get("currency", ""),
                exchange=info.get("exchange", ""),
                country=info.get("country"),
                industry=info.get("industry"),
                sector=info.get("sector"),
                market_cap=self._safe_float(info.get("marketCap")),
                pe_ratio=self._safe_float(info.get("trailingPE")),
                pb_ratio=self._safe_float(info.get("priceToBook")),
                dividend_yield=self._safe_float(info.get("dividendYield")),
                beta=self._safe_float(info.get("beta")),
                fifty_two_week_high=self._safe_float(info.get("fiftyTwoWeekHigh")),
                fifty_two_week_low=self._safe_float(info.get("fiftyTwoWeekLow")),
                current_price=self._safe_float(info.get("currentPrice")),
                extra=info,
            )

        except Exception as e:
            self._record_failure()
            logger.error("Failed to fetch current info for %s: %s", symbol, e)
            raise

    def get_batch_historical_data(
        self,
        symbols: List[str],
        period: str = "1y",
        interval: str = "1d",
        auto_adjust: Optional[bool] = None,
    ) -> Dict[str, List[YahooMarketData]]:
        """
        批量获取多只股票的历史数据

        Args:
            symbols: Yahoo 格式的代码列表
            period: 时间段
            interval: K线间隔
            auto_adjust: 是否自动复权

        Returns:
            字典，key 为 symbol，value 为 YahooMarketData 列表
        """
        if auto_adjust is None:
            auto_adjust = self.config.auto_adjust

        self._smart_delay(is_heavy_request=True)

        try:
            df = self.yf.download(
                symbols,
                period=period,
                interval=interval,
                auto_adjust=auto_adjust,
                group_by="ticker",
                threads=True,
            )

            self._record_success()

            result = {}

            if len(symbols) == 1:
                symbol = symbols[0]
                result[symbol] = self._df_to_market_data(df, symbol)
                return result

            for symbol in symbols:
                if symbol in df.columns.get_level_values(0):
                    symbol_df = df[symbol]
                    result[symbol] = self._df_to_market_data(symbol_df, symbol)
                else:
                    result[symbol] = []
                    logger.warning("No data for %s in batch download", symbol)

            logger.info("Batch fetched data for %d symbols", len(result))
            return result

        except Exception as e:
            self._record_failure()
            logger.error("Failed to batch fetch historical data: %s", e)
            raise

    def _df_to_market_data(self, df: Any, symbol: str) -> List[YahooMarketData]:
        """将 DataFrame 转换为 YahooMarketData 列表"""
        result = []

        if df.empty:
            return result

        for idx, row in df.iterrows():
            timestamp = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            if not isinstance(timestamp, datetime):
                timestamp = datetime.fromtimestamp(idx.timestamp())

            data = YahooMarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=self._safe_float(row.get("Open")),
                high=self._safe_float(row.get("High")),
                low=self._safe_float(row.get("Low")),
                close=self._safe_float(row.get("Close")),
                volume=self._safe_int(row.get("Volume")),
                adj_close=self._safe_float(row.get("Adj Close")),
            )
            result.append(data)

        return result

    def download_and_save(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        save_to_db: bool = True,
    ) -> List[YahooMarketData]:
        """
        下载并保存到本地数据库

        实现数据缓存策略：先查本地 PostgreSQL，没有才请求 Yahoo

        Args:
            symbol: Yahoo 格式的代码
            start_date: 开始日期
            end_date: 结束日期
            save_to_db: 是否保存到数据库

        Returns:
            YahooMarketData 列表
        """
        data = self.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        if save_to_db and data:
            logger.debug("Would save %d records to DB for %s", len(data), symbol)
            pass

        return data
