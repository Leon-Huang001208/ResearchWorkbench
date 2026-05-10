"""AKShare 开源数据适配器 - macOS 降级数据源"""
from datetime import datetime
from typing import List, Optional

import akshare as ak

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
            # 获取新浪财经财务摘要
            df = ak.stock_financial_report_sina(stock=ak_code, symbol="资产负债表")
            # 最新的资产负债表获取资产负债率
            debt_ratio = None
            if not df.empty:
                # 新浪接口返回格式: 每一行为一个项目，每一列是一期报告
                if "资产总计" in df.iloc[:, 0].values and "负债合计" in df.iloc[:, 0].values:
                    total_assets_row = df[df.iloc[:, 0] == "资产总计"]
                    total_debt_row = df[df.iloc[:, 0] == "负债合计"]
                    if not total_assets_row.empty and not total_debt_row.empty:
                        # 取最新一期（最后一列）
                        total_assets = float(str(total_assets_row.iloc[0, -1]).replace(",", ""))
                        total_debt = float(str(total_debt_row.iloc[0, -1]).replace(",", ""))
                        if total_assets > 0:
                            debt_ratio = 100 * total_debt / total_assets
            
            # 利润表获取核心指标
            profit_df = ak.stock_financial_report_sina(stock=ak_code, symbol="利润表")
            result = {
                "code": code,
                "eps": None,
                "roe": None,
                "net_profit": None,
                "revenue": None,
                "gross_margin": None,
                "debt_ratio": debt_ratio,
                "current_ratio": None,
            }
            
            if not profit_df.empty:
                # 尝试提取核心指标
                for name_col in ["基本每股收益", "每股收益"]:
                    eps_row = profit_df[profit_df.iloc[:, 0] == name_col]
                    if not eps_row.empty:
                        eps_str = str(eps_row.iloc[0, -1]).replace(",", "")
                        if eps_str.strip() != '':
                            try: 
                                result["eps"] = float(eps_str) 
                                break
                            except: pass
                
                for name_col in ["净利润", "归属于母公司所有者的净利润"]:
                    np_row = profit_df[profit_df.iloc[:, 0] == name_col]
                    if not np_row.empty:
                        np_str = str(np_row.iloc[0, -1]).replace(",", "")
                        if np_str.strip() != '':
                            try: 
                                result["net_profit"] = float(np_str) * 1e4  # 单位: 万元 → 元
                                break
                            except: pass
                
                for name_col in ["营业收入", "营业总收入"]:
                    rev_row = profit_df[profit_df.iloc[:, 0] == name_col]
                    if not rev_row.empty:
                        rev_str = str(rev_row.iloc[0, -1]).replace(",", "")
                        if rev_str.strip() != '':
                            try: 
                                result["revenue"] = float(rev_str) * 1e4  # 单位: 万元 → 元
                                break
                            except: pass
            
            # 财务指标摘要获取 ROE
            try:
                indicator_df = ak.stock_financial_abstract_ths(symbol=ak_code)
                if not indicator_df.empty:
                    latest_ind = indicator_df.iloc[-1]
                    roe = latest_ind.get("净资产收益率")
                    if roe is not None and str(roe).strip() != '':
                        try: result["roe"] = float(roe) 
                        except: pass
            except Exception:
                pass
                
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
        # 输入: 600000.SH -> 输出: sh600000
        # 输入: 000001.SZ -> 输出: sz000001
        # 输入: 600000 -> 输出: sh600000
        code_clean = code.split(".")[0]
        if code_clean.startswith(('6', '9')):
            return f"sh{code_clean}"
        elif code_clean.startswith(('0', '3')):
            return f"sz{code_clean}"
        return code_clean

    def _format_ak_code(self, code: str) -> str:
        """格式化代码"""
        return self._format_code(code)

    # Required abstract method from DataAdapter (not used for market data)
    def fetch(self, source, **kwargs):
        raise NotImplementedError("AKShareAdapter doesn't support document fetching, use for market data only")
        
    # Required abstract method from DataAdapter (not used for market data)
    def parse(self, source, **kwargs):
        raise NotImplementedError("AKShareAdapter doesn't support document parsing, use for market data only")
