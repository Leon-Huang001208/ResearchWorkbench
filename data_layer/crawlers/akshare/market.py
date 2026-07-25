"""
AkShare 行情数据获取器
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

import pandas as pd

from core.observability import get_logger

from .base import BaseAkShareFetcher, MarketData, StockInfo
from .config import AkShareConfig
from .utils import clean_symbol, normalize_symbol, parse_date

logger = get_logger("akshare_market")


class AkShareMarketFetcher(BaseAkShareFetcher):
    """AkShare 行情数据获取器"""

    def __init__(self, config: Optional[AkShareConfig] = None):
        super().__init__(config)

    def get_stock_list(self, limit: Optional[int] = None) -> List[StockInfo]:
        """
        获取 A 股股票列表

        Args:
            limit: 返回数量限制

        Returns:
            股票信息列表
        """
        self._initialize()
        logger.debug("Fetching stock list...")

        try:
            # 获取 A 股列表 - 使用东方财富接口
            df = self.ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                logger.warning("No stock data returned")
                return []

            result: List[StockInfo] = []

            # 处理每一行
            for _, row in df.iterrows():
                if limit and len(result) >= limit:
                    break

                try:
                    # 代码转换：需要补全市场标识
                    raw_code = str(row.get("代码", ""))
                    symbol = self._normalize_symbol(raw_code)

                    stock_info = StockInfo(
                        symbol=symbol,
                        name=str(row.get("名称", "")),
                        market=self._infer_market(symbol),
                        industry=str(row.get("行业", "")) if pd.notna(row.get("行业")) else None,
                    )
                    result.append(stock_info)
                except Exception as e:
                    logger.debug(f"Error processing stock row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} stocks")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            raise

    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: Optional[str] = None,
        adjust: Optional[str] = None,
    ) -> List[MarketData]:
        """
        获取历史行情数据

        Args:
            symbol: 股票代码 (带市场标识，如 600000.SH)
            start_date: 开始日期
            end_date: 结束日期
            period: 周期 (daily/weekly/monthly)
            adjust: 复权方式 (qfq/hfq/None)

        Returns:
            行情数据列表
        """
        self._initialize()

        period = period or self.config.default_period
        adjust = adjust or self.config.default_adjust

        # 日期处理
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        # 格式化日期
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        # 清理 symbol
        clean_symbol = self._clean_symbol(symbol)

        logger.debug(f"Fetching historical data for {clean_symbol} from {start_str} to {end_str}")

        try:
            # 根据复权方式选择接口
            if adjust == "qfq":
                df = self.ak.stock_zh_a_hist(
                    symbol=clean_symbol,
                    period=period,
                    start_date=start_str,
                    end_date=end_str,
                    adjust="qfq",
                )
            elif adjust == "hfq":
                df = self.ak.stock_zh_a_hist(
                    symbol=clean_symbol,
                    period=period,
                    start_date=start_str,
                    end_date=end_str,
                    adjust="hfq",
                )
            else:
                df = self.ak.stock_zh_a_hist(
                    symbol=clean_symbol,
                    period=period,
                    start_date=start_str,
                    end_date=end_str,
                    adjust="",
                )

            if df is None or df.empty:
                logger.warning(f"No historical data for {symbol}")
                return []

            result: List[MarketData] = []

            for _, row in df.iterrows():
                try:
                    # 解析日期
                    date_str = str(row.get("日期", ""))
                    dt = self._parse_date(date_str)

                    market_data = MarketData(
                        symbol=symbol,
                        timestamp=dt,
                        open=float(row.get("开盘", 0.0)) if pd.notna(row.get("开盘")) else None,
                        high=float(row.get("最高", 0.0)) if pd.notna(row.get("最高")) else None,
                        low=float(row.get("最低", 0.0)) if pd.notna(row.get("最低")) else None,
                        close=float(row.get("收盘", 0.0)) if pd.notna(row.get("收盘")) else None,
                        volume=int(row.get("成交量", 0)) if pd.notna(row.get("成交量")) else None,
                        amount=(float(row.get("成交额", 0.0)) if pd.notna(row.get("成交额")) else None),
                        turnover=(float(row.get("换手率", 0.0)) if pd.notna(row.get("换手率")) else None),
                        extra={
                            "amplitude": (
                                float(row.get("振幅", 0.0)) if pd.notna(row.get("振幅")) else None
                            ),
                            "change_pct": (
                                float(row.get("涨跌幅", 0.0)) if pd.notna(row.get("涨跌幅")) else None
                            ),
                            "change_amount": (
                                float(row.get("涨跌额", 0.0)) if pd.notna(row.get("涨跌额")) else None
                            ),
                        },
                    )
                    result.append(market_data)
                except Exception as e:
                    logger.debug(f"Error processing market data row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} records for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch historical data for {symbol}: {e}")
            raise

    def get_realtime_quotes(self, symbols: List[str]) -> List[MarketData]:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            实时行情列表
        """
        self._initialize()
        logger.debug(f"Fetching realtime quotes for {len(symbols)} symbols")

        try:
            # 获取全部实时行情
            df = self.ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                return []

            # 构建代码索引
            symbol_set = set(self._clean_symbol(s) for s in symbols)
            result: List[MarketData] = []

            for _, row in df.iterrows():
                try:
                    raw_code = str(row.get("代码", ""))
                    clean_code = self._clean_symbol(raw_code)

                    if clean_code not in symbol_set:
                        continue

                    symbol = self._normalize_symbol(raw_code)
                    dt = datetime.now()

                    market_data = MarketData(
                        symbol=symbol,
                        timestamp=dt,
                        open=float(row.get("今开", 0.0)) if pd.notna(row.get("今开")) else None,
                        high=float(row.get("最高", 0.0)) if pd.notna(row.get("最高")) else None,
                        low=float(row.get("最低", 0.0)) if pd.notna(row.get("最低")) else None,
                        close=(float(row.get("最新价", 0.0)) if pd.notna(row.get("最新价")) else None),
                        volume=int(row.get("成交量", 0)) if pd.notna(row.get("成交量")) else None,
                        amount=(float(row.get("成交额", 0.0)) if pd.notna(row.get("成交额")) else None),
                        turnover=(float(row.get("换手率", 0.0)) if pd.notna(row.get("换手率")) else None),
                        pe=(float(row.get("市盈率-动态", 0.0)) if pd.notna(row.get("市盈率-动态")) else None),
                        pb=float(row.get("市净率", 0.0)) if pd.notna(row.get("市净率")) else None,
                        extra={
                            "change_pct": (
                                float(row.get("涨跌幅", 0.0)) if pd.notna(row.get("涨跌幅")) else None
                            ),
                        },
                    )
                    result.append(market_data)
                except Exception as e:
                    logger.debug(f"Error processing realtime quote: {e}")
                    continue

            logger.info(f"Fetched {len(result)} realtime quotes")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch realtime quotes: {e}")
            raise

    def get_index_historical(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[MarketData]:
        """
        获取指数历史数据

        Args:
            symbol: 指数代码 (如 000001.SH)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            行情数据列表
        """
        self._initialize()

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        clean_symbol = self._clean_symbol(symbol)

        logger.debug(f"Fetching index data for {clean_symbol}")

        try:
            # 使用指数历史接口
            df = self.ak.index_zh_a_hist(
                symbol=clean_symbol,
                period="daily",
                start_date=start_str,
                end_date=end_str,
            )

            if df is None or df.empty:
                logger.warning(f"No index data for {symbol}")
                return []

            result: List[MarketData] = []

            for _, row in df.iterrows():
                try:
                    date_str = str(row.get("日期", ""))
                    dt = self._parse_date(date_str)

                    market_data = MarketData(
                        symbol=symbol,
                        timestamp=dt,
                        open=float(row.get("开盘", 0.0)) if pd.notna(row.get("开盘")) else None,
                        high=float(row.get("最高", 0.0)) if pd.notna(row.get("最高")) else None,
                        low=float(row.get("最低", 0.0)) if pd.notna(row.get("最低")) else None,
                        close=float(row.get("收盘", 0.0)) if pd.notna(row.get("收盘")) else None,
                        volume=int(row.get("成交量", 0)) if pd.notna(row.get("成交量")) else None,
                        amount=(float(row.get("成交额", 0.0)) if pd.notna(row.get("成交额")) else None),
                        extra={
                            "change_pct": (
                                float(row.get("涨跌幅", 0.0)) if pd.notna(row.get("涨跌幅")) else None
                            ),
                        },
                    )
                    result.append(market_data)
                except Exception as e:
                    logger.debug(f"Error processing index data row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} index records for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch index data for {symbol}: {e}")
            raise

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码，添加市场后缀"""
        return normalize_symbol(symbol)

    def _clean_symbol(self, symbol: str) -> str:
        """清理股票代码，去除市场后缀"""
        return clean_symbol(symbol)

    def _infer_market(self, symbol: str) -> str:
        """从代码推断市场"""
        normalized = normalize_symbol(symbol)
        if ".SH" in normalized:
            return "SH"
        elif ".SZ" in normalized:
            return "SZ"
        elif ".BJ" in normalized:
            return "BJ"
        return "UNKNOWN"

    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串"""
        parsed = parse_date(date_str)
        if parsed:
            return datetime.combine(parsed, datetime.min.time())
        # 回退到当前时间
        logger.warning(f"Could not parse date: {date_str}")
        return datetime.now()
