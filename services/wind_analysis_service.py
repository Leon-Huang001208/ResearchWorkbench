"""Wind 数据分析服务

将 Wind Excel 适配器数据映射为 AssetAnalysisCard，作为资产分析页面的首选数据源。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from core.contracts import (
    AssetAnalysisCard,
    AssetBasicInfo,
    CapitalFlow,
    FinancialSummary,
    IndustryData,
    PriceBar,
    Shareholder,
)
from core.observability import get_logger
from data_layer.adapters.wind.wind_adapter import WindAdapter

logger = get_logger(__name__)


class WindAnalysisService:
    """使用 Wind 数据填充资产分析卡片。

    当 Wind Excel 插件可用时，提供机构级数据质量的完整分析卡片。
    如果 Wind 不可用，返回 None 以触发降级到其他数据源。
    """

    def __init__(self, wind_adapter: Optional[WindAdapter] = None):
        self._adapter = wind_adapter

    def _get_adapter(self) -> WindAdapter:
        if self._adapter is None:
            self._adapter = WindAdapter()
        return self._adapter

    def is_available(self) -> bool:
        """检查 Wind 是否可用"""
        try:
            return self._get_adapter().is_available()
        except Exception:
            return False

    def build_analysis_card(
        self, canonical_id: str, as_of: Optional[datetime] = None
    ) -> Optional[AssetAnalysisCard]:
        """从 Wind 数据构建完整的资产分析卡片。

        Args:
            canonical_id: 资产代码，如 "600519.SH"
            as_of: 分析时间，默认当前时间

        Returns:
            AssetAnalysisCard 如果 Wind 可用且数据获取成功，否则 None
        """
        if as_of is None:
            as_of = datetime.utcnow()

        if not self.is_available():
            logger.info("Wind 不可用，跳过 Wind 数据源", canonical_id=canonical_id)
            return None

        logger.info("开始从 Wind 获取分析数据", canonical_id=canonical_id)

        try:
            adapter = self._get_adapter()
            codes = [canonical_id]
            today = date.today()
            end_date = today.strftime("%Y-%m-%d")
            start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
            # 最新报告期：当前日期可能还没有最新季报，用上季度末
            report_date = _latest_report_date(today)

            # ⚠️ 先执行 execute_batch（占 Z1-ZN），再用 WSD（占 Z1:Z5000）
            # 避免 WSD spill range 干扰 batch 操作
            basic_info = self._fetch_basic_info(adapter, canonical_id, today)
            valuation = self._fetch_valuation(adapter, canonical_id, end_date)

            # 并行获取各面板数据
            daily_df = self._safe_fetch(
                lambda: adapter.fetch_daily_quotes(codes, start_date, end_date),
                "daily_quotes",
            )
            financial_df = self._safe_fetch(
                lambda: adapter.fetch_financial_statements(
                    codes, trade_date=end_date, report_date=report_date
                ),
                "financials",
            )
            industry_df = self._safe_fetch(
                lambda: adapter.fetch_industry_data(codes),
                "industry",
            )
            # 资金流向只需最近几天（分析卡片仅用最新值）
            fund_flow_start = (today - timedelta(days=5)).strftime("%Y-%m-%d")
            fund_flow_df = self._safe_fetch(
                lambda: adapter.fetch_fund_flow(codes, fund_flow_start, end_date),
                "fund_flow",
            )
            holder_df = self._safe_fetch(
                lambda: adapter.fetch_holder_data(codes, report_date),
                "holders",
            )

            # 构建卡片
            card = AssetAnalysisCard(
                canonical_id=canonical_id,
                as_of=as_of,
                basic_info=basic_info,
                current_price=None,
                price_change=None,
                price_change_pct=None,
                volume=None,
                amount=None,
                turnover=None,
                high_52w=None,
                low_52w=None,
                price_bars=[],
                financial=None,
                valuation=valuation,
                capital_flow=None,
                top_10_shareholders=[],
                top_10_float_shareholders=[],
                industry=None,
                recent_events=[],
                macro_sensitivity=None,
            )

            # 填充各面板
            if daily_df is not None and not daily_df.empty:
                self._fill_price_data(card, daily_df)

            if financial_df is not None and not financial_df.empty:
                self._fill_financial(card, financial_df)

            # 即使财务数据不可用，估值数据也应该展示
            if card.financial is None and card.valuation:
                card.financial = FinancialSummary(
                    pe_ttm=_safe_float(card.valuation.get("pe_ttm")),
                    pb_mrq=_safe_float(card.valuation.get("pb_lf")),
                )

            if industry_df is not None and not industry_df.empty:
                self._fill_industry(card, industry_df)

            if fund_flow_df is not None and not fund_flow_df.empty:
                self._fill_capital_flow(card, fund_flow_df)

            if holder_df is not None and not holder_df.empty:
                self._fill_shareholders(card, holder_df)

            logger.info("Wind 分析卡片构建完成", canonical_id=canonical_id)
            return card

        except Exception as e:
            logger.error(f"Wind 数据获取失败: {e}", canonical_id=canonical_id, exc_info=True)
            return None

    def _safe_fetch(self, fetch_fn, name: str):
        """安全获取数据，失败时返回 None 并记录日志"""
        try:
            return fetch_fn()
        except Exception as e:
            logger.warning(f"Wind {name} 获取失败: {e}")
            return None

    def _fetch_basic_info(self, adapter: WindAdapter, code: str, today: date) -> AssetBasicInfo:
        """获取基本信息：公司全称、上市日期、总股本"""
        from data_layer.adapters.wind import formulas as wf

        try:
            client = adapter._get_client()
            raw = client.execute_batch(
                [
                    wf.s_info_compname(code),
                    wf.s_info_listeddate(code),
                    wf.s_info_shares(code),
                ]
            )

            def _str(idx):
                r = raw[idx]
                return str(r) if r is not None and not isinstance(r, Exception) else None

            name = _str(0) or code
            listing_date_str = _str(1)
            total_shares_str = _str(2)

            listing_date = None
            if listing_date_str:
                try:
                    listing_date = datetime.strptime(
                        listing_date_str.replace("/", "-")[:10], "%Y-%m-%d"
                    ).date()
                except (ValueError, IndexError):
                    pass

            total_shares = None
            if total_shares_str:
                try:
                    total_shares = float(total_shares_str)
                except (ValueError, TypeError):
                    pass

            return AssetBasicInfo(
                symbol=code,
                name=name,
                short_name=name,
                listing_date=listing_date,
                total_shares=total_shares,
            )
        except Exception as e:
            logger.warning(f"Wind 基本信息获取失败: {e}")
            return AssetBasicInfo(symbol=code, name=code)

    def _fetch_valuation(self, adapter: WindAdapter, code: str, trade_date: str) -> dict:
        """获取估值指标：PE(TTM), PB(LF), PCF"""
        from data_layer.adapters.wind import formulas as wf

        try:
            client = adapter._get_client()
            raw = client.execute_batch(
                [
                    wf.val_pe_ttm(code, trade_date),
                    wf.val_pb_lf(code, trade_date),
                    wf.val_pcf_ocf_ttm(code, trade_date),
                ]
            )

            def _float(idx):
                r = raw[idx]
                if r is None or isinstance(r, Exception):
                    return None
                try:
                    return float(r)
                except (ValueError, TypeError):
                    return None

            return {
                "pe_ttm": _float(0),
                "pb_lf": _float(1),
                "pcf_ocf_ttm": _float(2),
            }
        except Exception as e:
            logger.warning(f"Wind 估值数据获取失败: {e}")
            return {}

    # ── 面板填充方法 ──────────────────────────────────────────

    def _fill_price_data(self, card: AssetAnalysisCard, df: pd.DataFrame) -> None:
        """填充 K 线数据和当前价格信息"""
        # 按日期排序
        df = df.sort_values("date") if "date" in df.columns else df

        price_bars = []
        for _, row in df.iterrows():
            try:
                bar = PriceBar(
                    date=pd.Timestamp(row["date"]).date(),
                    open=float(row.get("open", 0) or 0),
                    high=float(row.get("high", 0) or 0),
                    low=float(row.get("low", 0) or 0),
                    close=float(row.get("close", 0) or 0),
                    volume=_safe_float(row.get("volume")),
                    amount=_safe_float(row.get("amount")),
                    turnover=_safe_float(row.get("turnover")),
                )
                price_bars.append(bar)
            except (ValueError, TypeError, KeyError):
                continue

        card.price_bars = price_bars

        if price_bars:
            last_bar = price_bars[-1]
            card.current_price = last_bar.close
            card.volume = last_bar.volume
            card.amount = last_bar.amount
            card.turnover = last_bar.turnover

            if len(price_bars) >= 2:
                prev_close = price_bars[-2].close
                if prev_close and prev_close != 0:
                    card.price_change = last_bar.close - prev_close
                    card.price_change_pct = (last_bar.close - prev_close) / prev_close * 100

            # 52 周最高/最低
            closes = [b.close for b in price_bars if b.close]
            if closes:
                card.high_52w = max(closes)
                card.low_52w = min(closes)

    def _fill_financial(self, card: AssetAnalysisCard, df: pd.DataFrame) -> None:
        """填充财务摘要"""
        row = df.iloc[0]
        card.financial = FinancialSummary(
            revenue=_safe_float(row.get("revenue")),
            net_profit=_safe_float(row.get("net_profit")),
            roe=_safe_float(row.get("roe")),
            gross_margin=_safe_float(row.get("gross_profit_margin")),
            pe_ttm=_safe_float(card.valuation.get("pe_ttm") if card.valuation else None),
            pb_mrq=_safe_float(card.valuation.get("pb_lf") if card.valuation else None),
            report_date=_parse_date(row.get("report_date")),
        )

    def _fill_industry(self, card: AssetAnalysisCard, df: pd.DataFrame) -> None:
        """填充行业分类"""
        row = df.iloc[0]
        card.industry = IndustryData(
            sw_level_1=_safe_str(row.get("industry_sw")),
            sw_level_2=_safe_str(row.get("industry_sw_l2")),
            sw_level_3=_safe_str(row.get("industry_sw_l3")),
        )

    def _fill_capital_flow(self, card: AssetAnalysisCard, df: pd.DataFrame) -> None:
        """填充资金流向"""
        # 取最新一条记录
        if df.empty:
            return
        row = df.sort_values("date").iloc[-1] if "date" in df.columns else df.iloc[-1]

        main_force = _safe_float(row.get("main_force_inflow")) or 0.0
        northbound_pct = _safe_float(row.get("north_bound_pct"))

        card.capital_flow = CapitalFlow(
            main_net=main_force,
            main_inflow=main_force if main_force > 0 else 0.0,
            main_outflow=abs(main_force) if main_force < 0 else 0.0,
            northbound_flow=northbound_pct,
        )

    def _fill_shareholders(self, card: AssetAnalysisCard, df: pd.DataFrame) -> None:
        """填充股东信息"""
        row = df.iloc[0]

        # Wind holder 数据不提供具体股东名单（名单需要单独处理），
        # 但提供汇总数据：户数、户均持股、前十大占比
        top10_pct = _safe_float(row.get("top10_pct"))
        institutional_pct = _safe_float(row.get("institutional_pct"))
        holder_num = _safe_float(row.get("holder_num"))

        # 构造一个汇总条目展示关键信息
        shareholders = []
        if holder_num is not None:
            shareholders.append(
                Shareholder(
                    name=f"股东户数: {holder_num:,.0f}",
                    share_ratio=0,
                    shareholder_type="summary",
                )
            )
        if top10_pct is not None:
            shareholders.append(
                Shareholder(
                    name="前十大股东合计",
                    share_ratio=top10_pct,
                    shareholder_type="top10",
                )
            )
        if institutional_pct is not None:
            shareholders.append(
                Shareholder(
                    name="机构持股合计",
                    share_ratio=institutional_pct,
                    shareholder_type="institutional",
                    is_state_owned=institutional_pct > 50,
                )
            )

        card.top_10_shareholders = shareholders


# ── 工具函数 ──────────────────────────────────────────────────


def _latest_report_date(today: date) -> str:
    """根据当前日期推算最新的财报报告期"""
    month = today.month
    year = today.year

    if month <= 4:
        # Q1 后，最新年报
        return f"{year - 1}/12/31"
    elif month <= 8:
        # Q2 后，最新一季报
        return f"{year}/03/31"
    elif month <= 10:
        # Q3 后，最新半年报
        return f"{year}/06/30"
    else:
        # Q4，最新三季报
        return f"{year}/09/30"


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_str(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_date(value) -> Optional[date]:
    if value is None:
        return None
    try:
        return pd.Timestamp(value).date()
    except (ValueError, TypeError):
        return None
