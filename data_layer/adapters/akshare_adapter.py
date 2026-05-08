"""AKShare 开源数据适配器 - macOS 降级数据源"""
import logging
from datetime import datetime
from typing import Any, List, Optional

import akshare as ak
import pandas as pd

from core.contracts.assets import AssetAnalysisSnapshot
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter

logger = get_logger(__name__)


class AKShareAdapter(BaseDataAdapter):
    """
    AKShare 开源数据适配器
    为 macOS 提供免费公开数据源，在 iFinD 不可用时自动降级使用
    """

    def __init__(self):
        super().__init__(source_type="akshare")
        self._is_available = self._check_availability()

    def _check_availability(self) -> bool:
        """检查 AKShare 是否可用"""
        try:
            import akshare
            return True
        except ImportError:
            logger.warning("AKShare not available")
            return False

    def is_available(self) -> bool:
        return self._is_available

    async def fetch_stock_quotes(
        self, code: str, start_date: str, end_date: str
    ) -> List[dict]:
        """获取股票历史行情"""
        if not self._is_available:
            return []
        try:
            # AKShare 格式: 600000 -> sh600000
            ak_code = self._format_code(code)
            df = ak.stock_zh_a_hist(symbol=ak_code, period="daily", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))
            if df is None or df.empty:
                return []
            # 转换为统一格式
            result = []
            for _, row in df.iterrows():
                result.append({
                    "code": code,
                    "date": row["日期"].strftime("%Y-%m-%d") if isinstance(row["日期"], datetime) else str(row["日期"]).split(" ")[0],
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": float(row["成交量"]),
                    "turnover": float(row["成交额"]) / 1e8,  # 成交额转换为亿元
                })
            logger.info(f"AKShare fetched {len(result)} quotes for {code}")
            return result
        except Exception as e:
            logger.error(f"AKShare fetch quotes failed for {code}: {e}")
            return []

    async def fetch_financial_report(self, code: str) -> Optional[dict]:
        """获取最新财务报告数据"""
        if not self._is_available:
            return None
        try:
            ak_code = self._format_ak_code(code)
            # 获取主要财务指标
            df = ak.stock_financial_report_cn(stock=ak_code)

            if df is None or df.empty:
                return None
            # 取最新一期
            latest = df.iloc[-1]
            result = {
                "code": code,
                "eps": float(latest.get("基本每股收益", 0)),
                "roe": float(latest.get("净资产收益率加权(%)", 0)),
                "net_profit": float(latest.get("净利润", 0)) * 1e8,
                "revenue": float(latest.get("营业收入", 0)) * 1e8,
                "gross_margin": None,
                "debt_ratio": float(latest.get("资产负债率", 0)),
                "current_ratio": None,
            }
            logger.info(f"AKShare fetched financial report for {code}")
            return result
        except Exception as e:
            logger.error(f"AKShare fetch financial failed for {code}: {e}")
            return None

    async def fetch_shareholders(self, code: str) -> Optional[dict]:
        """获取股东信息"""
        if not self._is_available:
            return None
        try:
            ak_code = self._format_ak_code(code)
            df = ak.stock_gdfx_holding_analyse()
            # 这里 AKShare 接口限制，只返回占位
            return {
                "shareholders": [],
                "institutional_holding": None,
                "northbound_holding": None,
            }
        except Exception as e:
            logger.error(f"AKShare fetch shareholders failed: {e}")
            return None

    def _format_code(self, code: str) -> str:
        """格式化代码为 AKShare 格式"""
        # 输入: 600000.SH -> 输出: 600000
        return code.split(".")[0]

    def _format_ak_code(self, code: str) -> str:
        """格式化代码"""
        return self._format_code(code)

    # Required abstract method from DataAdapter (not used for market data)
    def fetch(self, source, **kwargs):
        raise NotImplementedError("AKShareAdapter doesn't support document fetching, use for market data only")
        
    # Required abstract method from DataAdapter (not used for market data)
    def parse(self, source, **kwargs):
        raise NotImplementedError("AKShareAdapter doesn't support document parsing, use for market data only")
