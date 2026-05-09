"""
多数据源统一适配器
支持: AKShare -> Tushare -> BaoStock -> 本地缓存
"""
import asyncio
import io
import contextlib
from typing import List
from core.observability import get_logger

logger = get_logger(__name__)


class MultiSourcePriceAdapter:
    """
    多数据源适配器 - 按优先级尝试获取

    优先级:
    1. AKShare (免费开源)
    2. Tushare (数据全面，需token)
    3. BaoStock (证券专业)
    4. 本地缓存 (兜底)
    """

    def __init__(self):
        self.sources = []
        self._init_sources()

    def _init_sources(self):
        """初始化各个数据源"""
        # 1. AKShare
        try:
            from data_layer.adapters.akshare_adapter import AKShareAdapter
            self.sources.append({
                "name": "akshare",
                "adapter": AKShareAdapter(),
                "available": True
            })
            logger.info("AKShare source initialized")
        except Exception as e:
            logger.warning(f"AKShare not available: {e}")

        # 2. Tushare
        try:
            tushare_adapter = TushareSource()
            if tushare_adapter.available:
                self.sources.append({
                    "name": "tushare",
                    "adapter": tushare_adapter,
                    "available": True
                })
                logger.info("Tushare source initialized")
        except Exception as e:
            pass

        # 3. BaoStock
        try:
            self.sources.append({
                "name": "baostock",
                "adapter": BaoStockSource(),
                "available": True
            })
            logger.info("BaoStock source initialized")
        except Exception as e:
            pass

        # 4. 本地缓存
        from data_layer.adapters.hybrid_price_adapter import HybridPriceAdapter
        self.sources.append({
            "name": "local_cache",
            "adapter": HybridPriceAdapter(),
            "available": True
        })
        logger.info("Local cache source initialized")

    async def fetch_stock_quotes(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> List[dict]:
        """按优先级尝试多个数据源获取价格"""
        logger.info(f"Fetching {code} from {start_date} to {end_date}")

        for source in self.sources:
            if not source["available"]:
                continue

            source_name = source["name"]
            logger.info(f"Trying {source_name}...")

            try:
                if source_name == "local_cache":
                    # 本地缓存不走异步
                    data = source["adapter"]._get_from_cache(code, start_date, end_date)
                else:
                    data = await source["adapter"].fetch_stock_quotes(code, start_date, end_date)

                if data:
                    logger.info(f"Got {len(data)} records from {source_name}")
                    # 成功获取后缓存到本地
                    if source_name != "local_cache":
                        self._save_to_cache(data, source_name)
                    return data

            except Exception as e:
                pass

        logger.error(f"No data available for {code}")
        return []

    def _save_to_cache(self, data: List[dict], source: str):
        """保存到本地缓存"""
        from data_layer.adapters.hybrid_price_adapter import HybridPriceAdapter
        adapter = HybridPriceAdapter()
        adapter._save_to_cache(data, source)


class TushareSource:
    """Tushare数据源封装"""

    def __init__(self):
        self.available = False
        try:
            import tushare as ts
            # 安静地测试是否有token设置
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    with contextlib.redirect_stdout(io.StringIO()):
                        ts.pro_api()

                self.ts = ts
                self.available = True
            except Exception:
                pass
        except ImportError:
            pass

    async def fetch_stock_quotes(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> List[dict]:
        """从Tushare获取数据"""
        if not self.available:
            return []

        try:
            # 转换代码格式
            ts_code = self._convert_code(code)

            # 转换日期格式
            start = start_date.replace("-", "")
            end = end_date.replace("-", "")

            # 运行同步代码
            loop = asyncio.get_event_loop()

            def _fetch():
                with contextlib.redirect_stderr(io.StringIO()):
                    with contextlib.redirect_stdout(io.StringIO()):
                        return self.ts.pro_bar(
                            ts_code=ts_code,
                            adj='qfq',
                            start_date=start,
                            end_date=end
                        )

            df = await loop.run_in_executor(None, _fetch)

            if df is None or df.empty:
                return []

            # 转换格式
            result = []
            for _, row in df.iterrows():
                result.append({
                    "code": code,
                    "date": row["trade_date"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["vol"]) * 100,  # 手 -> 股
                    "turnover": float(row["amount"]) / 100000000,  # 元 -> 亿元
                })
            return result

        except Exception:
            return []

    def _convert_code(self, code: str) -> str:
        """转换代码格式"""
        # 600519.SH -> 600519.SH (Tushare格式一样)
        # 000001.SZ -> 000001.SZ
        return code


class BaoStockSource:
    """BaoStock数据源封装"""

    def __init__(self):
        try:
            import baostock as bs
            self.bs = bs
            self.available = True
        except ImportError:
            self.available = False

    async def fetch_stock_quotes(
        self,
        code: str, start_date: str, end_date: str
    ) -> List[dict]:
        """从BaoStock获取数据"""
        if not self.available:
            return []

        try:
            # 转换代码格式
            bs_code = self._convert_code(code)

            # 运行同步代码
            loop = asyncio.get_event_loop()

            def _fetch():
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"BaoStock login failed: {lg.error_msg}")

                rs = self.bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,volume,amount",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3"  # 前复权
                )

                result = []
                while (rs.error_code == '0') & rs.next():
                    row = rs.get_row_data()
                    result.append({
                        "code": code,
                        "date": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                        "turnover": float(row[6]) / 100000000,
                    })

                self.bs.logout()
                return result

            return await loop.run_in_executor(None, _fetch)

        except Exception:
            return []

    def _convert_code(self, code: str) -> str:
        """转换代码格式"""
        # 600519.SH -> sh.600519
        # 000001.SZ -> sz.000001
        parts = code.split(".")
        if len(parts) == 2:
            number, exchange = parts
            exchange = exchange.lower()
            return f"{exchange}.{number}"
        return code
