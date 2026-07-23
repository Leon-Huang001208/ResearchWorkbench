"""
BaoStock 行情数据获取器

实现与 AkShare 相同的接口，返回统一的 MarketData 结构。
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from core.observability import get_logger
from data_layer.crawlers.akshare.base import MarketData, StockInfo
from data_layer.crawlers.baostock.base import BaoStockConfig, BaoStockError, BaseBaoStockFetcher

logger = get_logger("baostock_market")


class BaoStockMarketFetcher(BaseBaoStockFetcher):
    """BaoStock 行情数据获取器"""

    def __init__(self, config: Optional[BaoStockConfig] = None):
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
        logger.debug("Fetching stock list from BaoStock...")

        try:
            with self.login_session():
                # 获取全部 A 股
                rs = self.bs.query_all_stock(day=date.today().strftime("%Y-%m-%d"))

                if rs.error_code != "0":
                    logger.error(f"Failed to get stock list: {rs.error_msg}")
                    raise BaoStockError(f"Stock list query failed: {rs.error_msg}")

                result: List[StockInfo] = []

                while (rs.error_code == "0") & rs.next():
                    if limit and len(result) >= limit:
                        break

                    row = rs.get_row_data()
                    code = row[0]  # code
                    name = row[1]  # code_name
                    # row[2] = tradeStatus
                    # row[3] = ipoDate

                    # 转换代码格式: sh.600519 -> 600519.SH
                    symbol = self._convert_bs_code_to_standard(code)
                    market = self._infer_market(symbol)

                    stock_info = StockInfo(
                        symbol=symbol,
                        name=name,
                        market=market,
                    )
                    result.append(stock_info)

                logger.info(f"Fetched {len(result)} stocks from BaoStock")
                return result

        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            raise

    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        frequency: Optional[str] = None,
        adjustflag: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[MarketData]:
        """
        获取历史行情数据

        Args:
            symbol: 股票代码 (带市场后缀，如 600519.SH)
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率 (d=日, w=周, m=月)
            adjustflag: 复权方式 (1=后复权, 2=前复权, 3=不复权)
            limit: 返回数量限制 (仅用于测试)

        Returns:
            行情数据列表
        """
        self._initialize()

        frequency = frequency or self.config.default_frequency
        adjustflag = adjustflag or self.config.default_adjustflag

        # 日期处理
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        # 格式化日期
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # 转换代码格式
        bs_code = self._convert_standard_code_to_bs(symbol)

        logger.debug(f"Fetching historical data for {bs_code} from {start_str} to {end_str}")

        try:
            with self.login_session():
                # 查询历史 K 线
                fields = "date,open,high,low,close,volume,amount,turn"
                rs = self.bs.query_history_k_data_plus(
                    bs_code,
                    fields,
                    start_date=start_str,
                    end_date=end_str,
                    frequency=frequency,
                    adjustflag=adjustflag,
                )

                if rs.error_code != "0":
                    logger.error(f"Failed to get historical data: {rs.error_msg}")
                    raise BaoStockError(f"Historical data query failed: {rs.error_msg}")

                result: List[MarketData] = []

                while (rs.error_code == "0") & rs.next():
                    if limit and len(result) >= limit:
                        break

                    row = rs.get_row_data()

                    try:
                        # 解析日期
                        date_str = row[0]
                        dt = self._parse_date(date_str)

                        # 解析价格数据，处理空值
                        open_price = self._safe_float(row[1])
                        high_price = self._safe_float(row[2])
                        low_price = self._safe_float(row[3])
                        close_price = self._safe_float(row[4])
                        volume = self._safe_int(row[5])
                        amount = self._safe_float(row[6])
                        turnover = self._safe_float(row[7])

                        market_data = MarketData(
                            symbol=symbol,
                            timestamp=dt,
                            open=open_price,
                            high=high_price,
                            low=low_price,
                            close=close_price,
                            volume=volume,
                            amount=amount,
                            turnover=turnover,
                            source="baostock",
                            extra={
                                "frequency": frequency,
                                "adjustflag": adjustflag,
                            },
                        )
                        result.append(market_data)
                    except Exception as e:
                        logger.debug(f"Error processing market data row: {e}")
                        continue

                logger.info(f"Fetched {len(result)} records from BaoStock for {symbol}")
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
        logger.debug(f"Fetching realtime quotes from BaoStock for {len(symbols)} symbols")

        try:
            result: List[MarketData] = []
            with self.login_session():
                for symbol in symbols:
                    bs_code = self._convert_standard_code_to_bs(symbol)

                    # 获取最近交易日的日 K 线作为"实时"数据
                    end_date = date.today()
                    start_date = end_date - timedelta(days=10)

                    rs = self.bs.query_history_k_data_plus(
                        bs_code,
                        "date,open,high,low,close,volume,amount,turn",
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        frequency="d",
                        adjustflag="3",
                    )

                    if rs.error_code != "0":
                        logger.warning(f"Failed to get realtime data for {symbol}: {rs.error_msg}")
                        continue

                    # 获取最后一条数据
                    last_row = None
                    while (rs.error_code == "0") & rs.next():
                        last_row = rs.get_row_data()

                    if last_row:
                        try:
                            dt = datetime.now()
                            market_data = MarketData(
                                symbol=symbol,
                                timestamp=dt,
                                open=self._safe_float(last_row[1]),
                                high=self._safe_float(last_row[2]),
                                low=self._safe_float(last_row[3]),
                                close=self._safe_float(last_row[4]),
                                volume=self._safe_int(last_row[5]),
                                amount=self._safe_float(last_row[6]),
                                turnover=self._safe_float(last_row[7]),
                                source="baostock",
                                extra={"realtime": "simulated"},
                            )
                            result.append(market_data)
                        except Exception as e:
                            logger.debug(f"Error processing realtime quote: {e}")
                            continue

            logger.info(f"Fetched {len(result)} realtime quotes from BaoStock")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch realtime quotes: {e}")
            raise

    def _convert_standard_code_to_bs(self, symbol: str) -> str:
        """
        转换标准代码到 BaoStock 格式

        600519.SH -> sh.600519
        000001.SZ -> sz.000001
        """
        parts = symbol.split(".")
        if len(parts) == 2:
            number, exchange = parts
            exchange = exchange.lower()
            return f"{exchange}.{number}"
        return symbol

    def _convert_bs_code_to_standard(self, bs_code: str) -> str:
        """
        转换 BaoStock 代码到标准格式

        sh.600519 -> 600519.SH
        sz.000001 -> 000001.SZ
        """
        parts = bs_code.split(".")
        if len(parts) == 2:
            exchange, number = parts
            exchange = exchange.upper()
            return f"{number}.{exchange}"
        return bs_code

    def _infer_market(self, symbol: str) -> str:
        """从代码推断市场"""
        if ".SH" in symbol:
            return "SH"
        elif ".SZ" in symbol:
            return "SZ"
        elif ".BJ" in symbol:
            return "BJ"
        return "UNKNOWN"

    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串"""
        try:
            d = date.fromisoformat(date_str)
            return datetime.combine(d, datetime.min.time())
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date: {date_str}")
            return datetime.now()

    def _safe_float(self, value: str) -> Optional[float]:
        """安全转换为 float"""
        if not value or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: str) -> Optional[int]:
        """安全转换为 int"""
        if not value or value == "":
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
