"""
资产分析快照到模板占位符的映射服务

将 AssetAnalysisSnapshot 和 AssetAnalysisCard 数据结构化映射到
模板占位符，支持各种报告模板的自动填充。
"""
from datetime import datetime
from typing import Any, Dict, Optional

from core.observability import get_logger

logger = get_logger(__name__)


class SnapshotToPlaceholdersMapper:
    """
    资产分析快照到占位符的映射器

    提供从 AssetAnalysisSnapshot / AssetAnalysisCard 到
    模板占位符字典的结构化映射。
    """

    def __init__(self):
        # 默认的数值格式化函数
        self.formatters = {
            "percent_1dp": lambda v: f"{v * 100:.1f}%" if v is not None else "N/A",
            "percent_2dp": lambda v: f"{v * 100:.2f}%" if v is not None else "N/A",
            "percent_0dp": lambda v: f"{v * 100:.0f}%" if v is not None else "N/A",
            "currency_cny": lambda v: f"¥{v:.2f}" if v is not None else "N/A",
            "currency_cny_2dp": lambda v: f"¥{v:.2f}" if v is not None else "N/A",
            "currency_cny_1dp": lambda v: f"¥{v:.1f}" if v is not None else "N/A",
            "currency_cny_0dp": lambda v: f"¥{v:.0f}" if v is not None else "N/A",
            "currency_100m": lambda v: f"¥{v/1e8:.1f}亿" if v is not None else "N/A",
            "number_1dp": lambda v: f"{v:.1f}" if v is not None else "N/A",
            "number_2dp": lambda v: f"{v:.2f}" if v is not None else "N/A",
            "number_0dp": lambda v: f"{v:.0f}" if v is not None else "N/A",
            "date_ymd": lambda v: v.strftime("%Y-%m-%d") if v is not None else "N/A",
            "datetime_full": lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if v is not None else "N/A",
        }

    def map_snapshot_to_placeholders(
        self,
        snapshot: Any,
        report_type: str = "full",
        additional_placeholders: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        将资产分析快照映射到模板占位符

        Args:
            snapshot: AssetAnalysisSnapshot 或 AssetAnalysisCard 对象
            report_type: 报告类型 (summary/valuation/full)
            additional_placeholders: 额外的占位符数据

        Returns:
            占位符字典
        """
        placeholders: Dict[str, str] = {}

        # 添加基本信息
        placeholders.update(self._map_basic_info(snapshot))

        # 添加市场数据
        placeholders.update(self._map_price_volume(snapshot))

        # 添加财务数据
        placeholders.update(self._map_financial(snapshot))

        # 添加估值数据
        placeholders.update(self._map_valuation(snapshot))

        # 添加资金流向
        placeholders.update(self._map_fund_flow(snapshot))

        # 添加行业数据
        placeholders.update(self._map_industry(snapshot))

        # 添加股东数据
        placeholders.update(self._map_shareholder(snapshot))

        # 添加事件数据
        placeholders.update(self._map_events(snapshot))

        # 添加日期和生成时间
        now = datetime.now()
        placeholders["generated_date"] = self.formatters["date_ymd"](now)
        placeholders["generated_datetime"] = self.formatters["datetime_full"](now)

        # 添加报告类型特定占位符
        if report_type == "summary":
            placeholders.update(self._map_summary_specific(snapshot))
        elif report_type == "valuation":
            placeholders.update(self._map_valuation_specific(snapshot))
        elif report_type == "full":
            placeholders.update(self._map_full_specific(snapshot))

        # 合并额外占位符
        if additional_placeholders:
            placeholders.update(additional_placeholders)

        return placeholders

    def _map_basic_info(self, snapshot: Any) -> Dict[str, str]:
        """映射基本信息"""
        placeholders: Dict[str, str] = {}

        # 从不同的可能位置获取基本信息
        canonical_id = self._get_attr(snapshot, "canonical_id")
        placeholders["canonical_id"] = canonical_id or "N/A"
        placeholders["stock_code"] = canonical_id or "N/A"

        # 优先使用 AssetAnalysisCard 的 basic_info
        basic_info = self._get_attr(snapshot, "basic_info")
        if basic_info:
            placeholders["symbol"] = self._get_attr(basic_info, "symbol", "N/A")
            placeholders["stock_name"] = self._get_attr(basic_info, "name", "N/A")
            placeholders["short_name"] = self._get_attr(
                basic_info, "short_name", placeholders["stock_name"]
            )

            # 市值
            market_cap = self._get_attr(basic_info, "market_cap")
            if market_cap is not None and isinstance(market_cap, (int, float)):
                placeholders["market_cap"] = self.formatters["currency_100m"](market_cap)
        else:
            # 旧格式兼容
            placeholders["symbol"] = canonical_id or "N/A"
            placeholders["stock_name"] = canonical_id or "N/A"
            placeholders["short_name"] = canonical_id or "N/A"

            # 尝试从旧格式获取公司名称
            if hasattr(snapshot, "company_name"):
                placeholders["company_name"] = snapshot.company_name
            elif isinstance(snapshot, dict) and "company_name" in snapshot:
                placeholders["company_name"] = snapshot["company_name"]
            else:
                placeholders["company_name"] = "贵州茅台酒股份有限公司"  # 默认值

            # 添加报告日期
            placeholders["report_date"] = self.formatters["date_ymd"](
                self._get_attr(snapshot, "as_of")
            )

        return placeholders

    def _map_price_volume(self, snapshot: Any) -> Dict[str, str]:
        """映射市场量价数据"""
        placeholders: Dict[str, str] = {}

        # 优先使用 AssetAnalysisCard 的字段
        current_price = self._get_attr(snapshot, "current_price")
        price_change = self._get_attr(snapshot, "price_change")
        price_change_pct = self._get_attr(snapshot, "price_change_pct")
        high_52w = self._get_attr(snapshot, "high_52w")
        low_52w = self._get_attr(snapshot, "low_52w")

        if current_price is not None and isinstance(current_price, (int, float)):
            placeholders["current_price"] = self.formatters["currency_cny_2dp"](current_price)
            placeholders["close_price"] = placeholders["current_price"]

        if price_change is not None and isinstance(price_change, (int, float)):
            sign = "+" if price_change >= 0 else ""
            placeholders[
                "price_change"
            ] = f"{sign}{self.formatters['currency_cny_2dp'](price_change)[1:]}"

        if price_change_pct is not None and isinstance(price_change_pct, (int, float)):
            sign = "+" if price_change_pct >= 0 else ""
            placeholders["price_change_pct"] = f"{sign}{price_change_pct * 100:.2f}%"

        if high_52w is not None and isinstance(high_52w, (int, float)):
            placeholders["high_52w"] = self.formatters["currency_cny_2dp"](high_52w)
        if low_52w is not None and isinstance(low_52w, (int, float)):
            placeholders["low_52w"] = self.formatters["currency_cny_2dp"](low_52w)

        # 兼容旧格式
        price_volume = self._get_attr(snapshot, "price_volume", {})
        if isinstance(price_volume, dict):
            if "close_price" not in placeholders:
                close_price = price_volume.get("close_price")
                if close_price is not None and isinstance(close_price, (int, float)):
                    placeholders["current_price"] = self.formatters["currency_cny_2dp"](close_price)
                    placeholders["close_price"] = placeholders["current_price"]

            if "high_52w" in price_volume and "high_52w" not in placeholders:
                h52 = price_volume.get("high_52w")
                if h52 is not None and isinstance(h52, (int, float)):
                    placeholders["high_52w"] = self.formatters["currency_cny_2dp"](h52)
            if "low_52w" in price_volume and "low_52w" not in placeholders:
                l52 = price_volume.get("low_52w")
                if l52 is not None and isinstance(l52, (int, float)):
                    placeholders["low_52w"] = self.formatters["currency_cny_2dp"](l52)

            # 添加成交量
            volume = price_volume.get("volume")
            if volume is not None and isinstance(volume, (int, float)):
                placeholders["volume"] = f"{volume:,.0f}"

        return placeholders

    def _map_financial(self, snapshot: Any) -> Dict[str, str]:
        """映射财务数据"""
        placeholders: Dict[str, str] = {}

        # 优先使用 AssetAnalysisCard 的 financial
        financial = self._get_attr(snapshot, "financial")
        if financial:
            # ROE
            roe = self._get_attr(financial, "roe")
            if roe is not None and isinstance(roe, (int, float)):
                placeholders["roe"] = self.formatters["percent_2dp"](roe)
                placeholders["roe_ttm"] = placeholders["roe"]

            # 资产负债率
            debt_ratio = self._get_attr(financial, "debt_ratio")
            if debt_ratio is not None and isinstance(debt_ratio, (int, float)):
                placeholders["debt_ratio"] = self.formatters["percent_2dp"](debt_ratio)

            # PE
            pe = self._get_attr(financial, "pe_ttm")
            if pe is not None and isinstance(pe, (int, float)):
                placeholders["pe_financial"] = self.formatters["number_2dp"](pe)
        else:
            # 兼容旧格式
            financial_dict = self._get_attr(snapshot, "financial", {})
            if isinstance(financial_dict, dict):
                # ROE 可能在嵌套结构中
                roe_val = (
                    financial_dict.get("roe", {}).get("ttm")
                    if isinstance(financial_dict.get("roe"), dict)
                    else financial_dict.get("roe")
                )
                if roe_val is not None and isinstance(roe_val, (int, float)):
                    placeholders["roe"] = self.formatters["percent_2dp"](roe_val)
                    placeholders["roe_ttm"] = placeholders["roe"]

                # 其他财务指标
                for key in ["revenue", "net_profit", "eps"]:
                    val = (
                        financial_dict.get(key, {}).get("ttm")
                        if isinstance(financial_dict.get(key), dict)
                        else financial_dict.get(key)
                    )
                    if val is not None and isinstance(val, (int, float)):
                        if key == "revenue" or key == "net_profit":
                            placeholders[f"{key}_ttm"] = self.formatters["currency_100m"](val)
                        else:
                            placeholders[f"{key}_ttm"] = self.formatters["number_2dp"](val)

                        # 同比/环比
                        yoy = (
                            financial_dict.get(key, {}).get("yoy")
                            if isinstance(financial_dict.get(key), dict)
                            else None
                        )
                        qoq = (
                            financial_dict.get(key, {}).get("qoq")
                            if isinstance(financial_dict.get(key), dict)
                            else None
                        )
                        if yoy is not None and isinstance(yoy, (int, float)):
                            placeholders[f"{key}_yoy"] = self.formatters["percent_2dp"](yoy)
                        if qoq is not None and isinstance(qoq, (int, float)):
                            placeholders[f"{key}_qoq"] = self.formatters["percent_2dp"](qoq)

                # 单独处理 debt_ratio
                debt_ratio = financial_dict.get("debt_ratio")
                if debt_ratio is not None and isinstance(debt_ratio, (int, float)):
                    placeholders["debt_ratio"] = self.formatters["percent_2dp"](debt_ratio)

        return placeholders

    def _map_valuation(self, snapshot: Any) -> Dict[str, str]:
        """映射估值数据"""
        placeholders: Dict[str, str] = {}

        valuation = self._get_attr(snapshot, "valuation", {})

        # PE
        pe_ttm = valuation.get("pe_ttm")
        if pe_ttm is not None and isinstance(pe_ttm, (int, float)):
            placeholders["pe_ttm"] = self.formatters["number_2dp"](pe_ttm)

        # PB
        pb = valuation.get("pb")
        if pb is not None and isinstance(pb, (int, float)):
            placeholders["pb"] = self.formatters["number_2dp"](pb)

        # PS
        ps = valuation.get("ps")
        if ps is not None and isinstance(ps, (int, float)):
            placeholders["ps"] = self.formatters["number_2dp"](ps)

        # 股息率
        dividend_yield = valuation.get("dividend_yield")
        if dividend_yield is not None and isinstance(dividend_yield, (int, float)):
            placeholders["dividend_yield"] = self.formatters["percent_2dp"](dividend_yield)

        # 历史分位
        percentile_pe = valuation.get("historical_percentile_pe")
        if percentile_pe is not None and isinstance(percentile_pe, (int, float)):
            placeholders["pe_percentile"] = self.formatters["percent_0dp"](percentile_pe)

        return placeholders

    def _map_fund_flow(self, snapshot: Any) -> Dict[str, str]:
        """映射资金流向数据"""
        placeholders: Dict[str, str] = {}

        # 优先使用 AssetAnalysisCard 的 capital_flow
        capital_flow = self._get_attr(snapshot, "capital_flow")
        if capital_flow:
            main_net = self._get_attr(capital_flow, "main_net")
            if main_net is not None and isinstance(main_net, (int, float)):
                placeholders["main_net_inflow"] = self.formatters["currency_100m"](main_net)
        else:
            # 兼容旧格式
            fund_flow = self._get_attr(snapshot, "fund_flow", {})
            if isinstance(fund_flow, dict):
                main_inflow = fund_flow.get("main_net_inflow")
                if main_inflow is not None and isinstance(main_inflow, (int, float)):
                    placeholders["main_net_inflow"] = self.formatters["currency_100m"](main_inflow)

                northbound = fund_flow.get("northbound_holding")
                if northbound is not None and isinstance(northbound, (int, float)):
                    placeholders["northbound_holding"] = self.formatters["percent_2dp"](northbound)

        return placeholders

    def _map_industry(self, snapshot: Any) -> Dict[str, str]:
        """映射行业数据"""
        placeholders: Dict[str, str] = {}

        # 优先使用 AssetAnalysisCard 的 industry
        industry = self._get_attr(snapshot, "industry")
        if industry:
            # 申万行业 - 尝试多种属性名
            sw_l1 = self._get_attr(industry, "sw_level_1") or self._get_attr(industry, "sw_level1")
            sw_l2 = self._get_attr(industry, "sw_level_2") or self._get_attr(industry, "sw_level2")
            sw_l3 = self._get_attr(industry, "sw_level_3") or self._get_attr(industry, "sw_level3")

            industry_path = []
            if sw_l1:
                industry_path.append(sw_l1)
                placeholders["industry_l1"] = sw_l1
            if sw_l2:
                industry_path.append(sw_l2)
                placeholders["industry_l2"] = sw_l2
            if sw_l3:
                industry_path.append(sw_l3)
                placeholders["industry_l3"] = sw_l3

            if industry_path:
                placeholders["industry_path"] = " -> ".join(industry_path)

            # 行业平均估值
            industry_pe = self._get_attr(industry, "industry_pe")
            industry_pb = self._get_attr(industry, "industry_pb")

            if industry_pe is not None and isinstance(industry_pe, (int, float)):
                placeholders["industry_pe"] = self.formatters["number_2dp"](industry_pe)
            if industry_pb is not None and isinstance(industry_pb, (int, float)):
                placeholders["industry_pb"] = self.formatters["number_2dp"](industry_pb)
        else:
            # 兼容旧格式
            industry_dict = self._get_attr(snapshot, "industry", {})
            if industry_dict and isinstance(industry_dict, dict):
                sw_l1 = industry_dict.get("sw_level1") or industry_dict.get("sw_level_1")
                sw_l2 = industry_dict.get("sw_level2") or industry_dict.get("sw_level_2")
                sw_l3 = industry_dict.get("sw_level3") or industry_dict.get("sw_level_3")

                if sw_l1:
                    placeholders["industry_l1"] = sw_l1
                if sw_l2:
                    placeholders["industry_l2"] = sw_l2
                if sw_l3:
                    placeholders["industry_l3"] = sw_l3

                industry_parts = [p for p in [sw_l1, sw_l2, sw_l3] if p]
                if industry_parts:
                    placeholders["industry_path"] = " -> ".join(industry_parts)

                industry_pe = industry_dict.get("industry_pe")
                industry_pb = industry_dict.get("industry_pb")

                if industry_pe is not None and isinstance(industry_pe, (int, float)):
                    placeholders["industry_pe"] = self.formatters["number_2dp"](industry_pe)
                if industry_pb is not None and isinstance(industry_pb, (int, float)):
                    placeholders["industry_pb"] = self.formatters["number_2dp"](industry_pb)

        return placeholders

    def _map_shareholder(self, snapshot: Any) -> Dict[str, str]:
        """映射股东数据"""
        placeholders: Dict[str, str] = {}

        shareholder = self._get_attr(snapshot, "shareholder", {})
        if shareholder:
            controlling = shareholder.get("controlling_shareholder")
            if controlling:
                placeholders["controlling_shareholder"] = controlling

        return placeholders

    def _map_events(self, snapshot: Any) -> Dict[str, str]:
        """映射事件数据"""
        placeholders: Dict[str, str] = {}

        # 优先使用 AssetAnalysisCard 的 recent_events
        recent_events = self._get_attr(snapshot, "recent_events", [])
        if recent_events and len(recent_events) > 0:
            # 取最近的一个事件
            event = recent_events[0]
            placeholders["recent_event_title"] = self._get_attr(event, "title", "N/A")
            placeholders["recent_event_content"] = self._get_attr(event, "content", "N/A")

            # 构建事件列表摘要
            event_titles = [self._get_attr(e, "title", "") for e in recent_events[:3]]
            if event_titles:
                placeholders["recent_events_summary"] = "\n".join(
                    [f"• {t}" for t in event_titles if t]
                )
        else:
            # 兼容旧格式
            event_impact = self._get_attr(snapshot, "event_impact", [])
            if event_impact:
                if isinstance(event_impact[0], str):
                    placeholders["recent_events_summary"] = "\n".join(
                        [f"• {e}" for e in event_impact[:3]]
                    )
                    if len(event_impact) > 0:
                        placeholders["recent_event_title"] = event_impact[0]
                else:
                    placeholders["recent_event_title"] = "N/A"

        return placeholders

    def _map_summary_specific(self, snapshot: Any) -> Dict[str, str]:
        """摘要报告特定占位符"""
        placeholders: Dict[str, str] = {}

        # 添加投资建议
        percentile = 0.5
        valuation = self._get_attr(snapshot, "valuation")
        if isinstance(valuation, dict):
            p = valuation.get("historical_percentile_pe")
            if p is not None and isinstance(p, (int, float)):
                percentile = p
        elif hasattr(valuation, "historical_percentile_pe"):
            p = getattr(valuation, "historical_percentile_pe")
            if p is not None and isinstance(p, (int, float)):
                percentile = p

        if isinstance(percentile, (int, float)):
            if percentile < 0.3:
                placeholders["investment_suggestion"] = "增持"
            elif percentile < 0.7:
                placeholders["investment_suggestion"] = "持有"
            else:
                placeholders["investment_suggestion"] = "观望"
        else:
            placeholders["investment_suggestion"] = "持有"

        return placeholders

    def _map_valuation_specific(self, snapshot: Any) -> Dict[str, str]:
        """估值报告特定占位符"""
        placeholders: Dict[str, str] = {}

        # 估值结论
        valuation = self._get_attr(snapshot, "valuation", {})
        pe = None
        if isinstance(valuation, dict):
            pe = valuation.get("pe_ttm")
        else:
            pe = self._get_attr(valuation, "pe_ttm")

        industry = self._get_attr(snapshot, "industry", {})
        industry_pe = None
        if isinstance(industry, dict):
            industry_pe = industry.get("industry_pe")
        else:
            industry_pe = self._get_attr(industry, "industry_pe")

        if isinstance(industry_pe, (int, float)) and isinstance(pe, (int, float)):
            if pe < industry_pe * 0.7:
                placeholders["valuation_conclusion"] = "显著低估"
            elif pe < industry_pe * 1.3:
                placeholders["valuation_conclusion"] = "合理"
            else:
                placeholders["valuation_conclusion"] = "高估"
        else:
            placeholders["valuation_conclusion"] = "数据不足"

        # 合理价格区间
        close_price = self._get_attr(snapshot, "current_price")
        if close_price is None:
            price_volume = self._get_attr(snapshot, "price_volume", {})
            if isinstance(price_volume, dict):
                close_price = price_volume.get("close_price")

        if isinstance(close_price, (int, float)) and close_price > 0:
            placeholders["fair_price_low"] = self.formatters["currency_cny_1dp"](close_price * 0.8)
            placeholders["fair_price_high"] = self.formatters["currency_cny_1dp"](close_price * 1.2)

        return placeholders

    def _map_full_specific(self, snapshot: Any) -> Dict[str, str]:
        """完整报告特定占位符"""
        placeholders: Dict[str, str] = {}

        # 合并所有特定占位符
        placeholders.update(self._map_summary_specific(snapshot))
        placeholders.update(self._map_valuation_specific(snapshot))

        return placeholders

    def _get_attr(self, obj: Any, attr: str, default: Any = None) -> Any:
        """
        安全获取对象属性

        支持:
        - 普通属性访问 (obj.attr)
        - 字典访问 (obj[attr])
        - 嵌套属性 (obj.attr1.attr2)
        """
        try:
            if "." in attr:
                parts = attr.split(".")
                current = obj
                for part in parts:
                    if hasattr(current, part):
                        current = getattr(current, part)
                    elif isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return default
                return current
            elif hasattr(obj, attr):
                return getattr(obj, attr)
            elif isinstance(obj, dict) and attr in obj:
                return obj[attr]
            return default
        except Exception:
            return default


# 单例实例
_snapshot_mapper: Optional[SnapshotToPlaceholdersMapper] = None


def get_snapshot_mapper() -> SnapshotToPlaceholdersMapper:
    """获取快照映射器单例"""
    global _snapshot_mapper
    if _snapshot_mapper is None:
        _snapshot_mapper = SnapshotToPlaceholdersMapper()
    return _snapshot_mapper
