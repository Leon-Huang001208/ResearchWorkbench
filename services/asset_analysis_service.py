"""资产分析服务"""

import asyncio
import os
from datetime import date, datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

from core.contracts import (
    AssetAnalysisCard,
    AssetAnalysisSnapshot,
    AssetBasicInfo,
    CapitalFlow,
    ChipDistributionPoint,
    EventImpact,
    FinancialSummary,
    IndustryData,
    MacroSensitivity,
    PriceBar,
    Shareholder,
)
from core.interfaces import AssetSnapshotRepository, EntityRepository
from core.observability import get_logger
from data_layer.adapters.akshare_adapter import AKShareAdapter
from data_layer.adapters.wind import WindAdapter
from data_layer.coordinator.multi_source_coordinator import MultiSourceCoordinator, get_coordinator
from data_layer.repositories.base import db_session
from data_layer.repositories.market_data_repository import MarketDataRepository

logger = get_logger(__name__)


def _env_float(name: str, default: float) -> float:
    """Parse a positive float from env, falling back safely on bad values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid float env value, using default", env_name=name, value=raw)
        return default
    return value if value > 0 else default


CJPY_PRICE_TIMEOUT_SECONDS = _env_float("ASSET_CJPY_PRICE_TIMEOUT_SECONDS", 25.0)
WIND_PRICE_TIMEOUT_SECONDS = _env_float("ASSET_WIND_PRICE_TIMEOUT_SECONDS", 8.0)
ASSET_ENRICHMENT_TIMEOUT_SECONDS = _env_float("ASSET_ENRICHMENT_TIMEOUT_SECONDS", 36.0)
CJPY_RECENT_LOOKBACK_DAYS = 14

# Module-level Wind availability cache — avoids repeated heartbeat checks across requests
_wind_available_cache: Optional[bool] = None  # None=未检测, True=可用, False=不可用
_wind_adapter_cache: Optional[WindAdapter] = None


class AssetAnalysisService:
    """资产分析服务

    数据源优先级:
    1. 结构化 SQL 表 (stock_daily_bar, stock_valuation, stock_financial_metric) -> 最快
    2. MultiSourceCoordinator 自动降级链: iFinD -> AKShare -> Local
    """

    def __init__(
        self,
        asset_snapshot_repo: Optional[AssetSnapshotRepository] = None,
        entity_repo: Optional[EntityRepository] = None,
        coordinator: Optional[MultiSourceCoordinator] = None,
        market_repo: Optional[MarketDataRepository] = None,
        wind_adapter: Optional[WindAdapter] = None,
    ):
        self.asset_snapshot_repo = asset_snapshot_repo
        self.entity_repo = entity_repo
        self.coordinator = coordinator or get_coordinator()
        self.market_repo = market_repo
        self.wind_adapter = wind_adapter

    async def generate_snapshot(
        self,
        canonical_id: str,
        as_of: Optional[datetime] = None,
        use_mock: Optional[bool] = None,  # 保留参数用于向后兼容
        source: Optional[str] = None,  # 保留参数用于向后兼容
    ) -> AssetAnalysisSnapshot:
        """
        生成资产分析快照

        Args:
            canonical_id: 资产代码
            as_of: 快照时间
            use_mock: 已废弃，会自动忽略
            source: 已废弃，会自动忽略
        """
        if as_of is None:
            as_of = datetime.utcnow()

        logger.info(
            "generating asset snapshot",
            canonical_id=canonical_id,
            as_of=as_of,
        )

        # 使用 MultiSourceCoordinator 自动处理数据源降级
        snapshot = await self._fetch_from_coordinator(canonical_id, as_of)

        # 保存快照
        if self.asset_snapshot_repo:
            saved_snapshot = self.asset_snapshot_repo.save(snapshot)
            logger.info("asset snapshot saved", canonical_id=canonical_id)
            return saved_snapshot

        return snapshot

    async def _fetch_from_coordinator(
        self, canonical_id: str, as_of: datetime
    ) -> AssetAnalysisSnapshot:
        """获取数据：优先从结构化表读取，回退到 coordinator"""
        # 优先从结构化 SQL 表构建快照
        if self.market_repo:
            try:
                snapshot = self._build_from_structured_tables(canonical_id, as_of)
                if self._has_enough_structured_data(snapshot):
                    return snapshot
                logger.info(
                    "Structured tables have no data, falling back to coordinator",
                    canonical_id=canonical_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to build from structured tables, falling back to coordinator: {e}",
                    canonical_id=canonical_id,
                )

        # 回退到 coordinator
        return await self._build_from_coordinator(canonical_id, as_of)

    @staticmethod
    def _has_enough_structured_data(snapshot: AssetAnalysisSnapshot) -> bool:
        """判断结构化数据是否包含可用数据"""
        return bool(
            snapshot.price_volume
            or snapshot.valuation
            or snapshot.financial
            or snapshot.shareholder
        )

    def _build_from_structured_tables(
        self, canonical_id: str, as_of: datetime
    ) -> AssetAnalysisSnapshot:
        """从结构化 SQL 表组装 AssetAnalysisSnapshot"""
        latest_bar = self.market_repo.get_latest_daily_bar(canonical_id)  # type: ignore[union-attr]
        latest_valuation = self.market_repo.get_latest_valuation(canonical_id)  # type: ignore[union-attr]
        latest_financial = self.market_repo.get_latest_financial(canonical_id)  # type: ignore[union-attr]
        shareholders = self.market_repo.get_latest_shareholders(canonical_id, limit=10)  # type: ignore[union-attr]  # type: ignore[union-attr]

        price_volume = {}
        if latest_bar:
            price_volume = {
                "close_price": float(latest_bar.close) if latest_bar.close else None,
                "open": float(latest_bar.open) if latest_bar.open else None,
                "high": float(latest_bar.high) if latest_bar.high else None,
                "low": float(latest_bar.low) if latest_bar.low else None,
                "volume": float(latest_bar.volume) if latest_bar.volume else None,
                "amount": float(latest_bar.amount) if latest_bar.amount else None,
                "turnover": float(latest_bar.turnover) if latest_bar.turnover else None,
            }

        valuation = {}
        if latest_valuation:
            valuation = {
                "pe_ttm": float(latest_valuation.pe_ttm) if latest_valuation.pe_ttm else None,
                "pe_dynamic": (
                    float(latest_valuation.pe_dynamic) if latest_valuation.pe_dynamic else None
                ),
                "pb": float(latest_valuation.pb) if latest_valuation.pb else None,
                "ps": float(latest_valuation.ps) if latest_valuation.ps else None,
                "market_cap": (
                    float(latest_valuation.market_cap) if latest_valuation.market_cap else None
                ),
                "float_market_cap": (
                    float(latest_valuation.float_market_cap)
                    if latest_valuation.float_market_cap
                    else None
                ),
            }

        financial = {}
        if latest_financial:
            financial = {
                "report_date": (
                    latest_financial.report_date.isoformat()
                    if latest_financial.report_date
                    else None
                ),
                "report_type": latest_financial.report_type,
                "total_revenue": (
                    float(latest_financial.total_revenue)
                    if latest_financial.total_revenue
                    else None
                ),
                "net_profit": (
                    float(latest_financial.net_profit) if latest_financial.net_profit else None
                ),
                "roe": float(latest_financial.roe) if latest_financial.roe else None,
                "roa": float(latest_financial.roa) if latest_financial.roa else None,
                "gross_margin": (
                    float(latest_financial.gross_margin) if latest_financial.gross_margin else None
                ),
                "net_margin": (
                    float(latest_financial.net_margin) if latest_financial.net_margin else None
                ),
                "debt_ratio": (
                    float(latest_financial.debt_ratio) if latest_financial.debt_ratio else None
                ),
                "total_assets": (
                    float(latest_financial.total_assets) if latest_financial.total_assets else None
                ),
            }

        shareholder = {}
        if shareholders:
            shareholder = {
                "top10": [
                    {
                        "name": s.holder_name,
                        "rank": s.holder_rank,
                        "shares": float(s.shares) if s.shares else None,
                        "holding_pct": float(s.holding_pct) if s.holding_pct else None,
                        "type": s.holder_type,
                    }
                    for s in shareholders
                ]
            }

        snapshot = AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            financial=financial,
            fund_flow={},
            price_volume=price_volume,
            valuation=valuation,
            shareholder=shareholder,
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )

        logger.info(
            "Built snapshot from structured tables",
            canonical_id=canonical_id,
            has_bar=latest_bar is not None,
            has_valuation=latest_valuation is not None,
            has_financial=latest_financial is not None,
        )
        return snapshot

    async def _build_from_coordinator(
        self, canonical_id: str, as_of: datetime
    ) -> AssetAnalysisSnapshot:
        """从 MultiSourceCoordinator 获取数据（回退路径）"""
        end_date = as_of.date()
        start_date = end_date - timedelta(days=365)

        result = self.coordinator.fetch_historical_data(
            symbol=canonical_id,
            start_date=start_date,
            end_date=end_date,
        )

        if not result.success:
            raise RuntimeError(f"Failed to fetch data: {result.error_message}")

        if not result.data:
            raise RuntimeError("No data returned from coordinator")

        last_quote = result.data[-1]
        highs = [quote.high for quote in result.data if quote.high is not None]
        lows = [quote.low for quote in result.data if quote.low is not None]

        snapshot = AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            financial={},
            fund_flow={},
            price_volume={
                "close_price": last_quote.close,
                "high_52w": max(highs) if highs else None,
                "low_52w": min(lows) if lows else None,
            },
            valuation={},
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )

        logger.info(
            f"Fetched from coordinator, source: {result.primary_source}",
            canonical_id=canonical_id,
        )
        return snapshot

    def get_latest_snapshot(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """获取最新的资产分析快照"""
        if self.asset_snapshot_repo:
            return self.asset_snapshot_repo.get_latest_by_canonical_id(canonical_id)
        return None

    async def generate_analysis_card(
        self,
        canonical_id: str,
        as_of: Optional[datetime] = None,
        use_mock: Optional[bool] = None,  # 保留参数用于向后兼容
        source: Optional[str] = None,  # 保留参数用于向后兼容
        time_range: Optional[str] = None,  # 1M/3M/6M/1Y/2Y/3Y/5Y/ALL
    ) -> AssetAnalysisCard:
        """
        生成完整的资产分析卡片

        Args:
            canonical_id: 资产代码
            as_of: 快照时间
            use_mock: 已废弃
            source: 已废弃
            time_range: 时间范围 (1M/3M/6M/1Y/2Y/3Y/5Y/ALL)，默认1Y

        Returns:
            完整的资产分析卡片
        """
        if as_of is None:
            as_of = datetime.utcnow()

        logger.info(
            "generating asset analysis card", canonical_id=canonical_id, time_range=time_range
        )

        # 先生成基础快照
        snapshot = await self.generate_snapshot(
            canonical_id=canonical_id,
            as_of=as_of,
        )

        # 构建完整分析卡片
        card = AssetAnalysisCard(
            canonical_id=canonical_id,
            as_of=as_of,
            financial_dict=snapshot.financial,
            fund_flow=snapshot.fund_flow,
            price_volume=snapshot.price_volume,
            valuation=snapshot.valuation,
            shareholder=snapshot.shareholder,
            industry_dict=snapshot.industry,
            event_impact=snapshot.event_impact,
            macro_exposure=snapshot.macro_exposure,
            evidence_refs=snapshot.evidence_refs,
            technical=snapshot.technical,
            sentiment=snapshot.sentiment,
        )

        # 填充结构化数据
        card = self._fill_structured_data(card, snapshot)

        # 从实时源 / 协调器补充更详细数据（带总超时保护）。
        # Cjpy 收盘后单日行情实测可能接近 20s；命中实时价格后会跳过慢补全。
        try:
            card = await asyncio.wait_for(
                self._enrich_from_coordinator(card, canonical_id, as_of, time_range),
                timeout=ASSET_ENRICHMENT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Enrichment timed out, returning partial card",
                extra={"canonical_id": canonical_id, "time_range": time_range},
            )

        return card

    def _fill_structured_data(
        self,
        card: AssetAnalysisCard,
        snapshot: AssetAnalysisSnapshot,
    ) -> AssetAnalysisCard:
        """从快照填充结构化数据"""
        # 财务数据
        fin_dict = snapshot.financial
        card.financial = FinancialSummary(
            revenue=self._metric_value(fin_dict, "revenue", "total_revenue"),
            net_profit=self._metric_value(fin_dict, "net_profit"),
            roe=self._metric_value(fin_dict, "roe"),
            roa=self._metric_value(fin_dict, "roa"),
            gross_margin=self._metric_value(fin_dict, "gross_margin"),
            debt_ratio=fin_dict.get("debt_ratio"),
            pe_ttm=snapshot.valuation.get("pe_ttm"),
            pb_mrq=snapshot.valuation.get("pb"),
            ev_ebitda=snapshot.valuation.get("ev_ebitda"),
            dividend_yield=snapshot.valuation.get("dividend_yield"),
        )

        # 资金流向
        flow_dict = snapshot.fund_flow
        card.capital_flow = CapitalFlow(
            main_net=flow_dict.get("main_net_inflow", 0),
            main_inflow=(
                flow_dict.get("main_net_inflow", 0)
                if flow_dict.get("main_net_inflow", 0) > 0
                else 0
            ),
            main_outflow=(
                abs(flow_dict.get("main_net_inflow", 0))
                if flow_dict.get("main_net_inflow", 0) < 0
                else 0
            ),
            northbound_flow=flow_dict.get("northbound_holding"),
        )

        # 市场数据
        pv_dict = snapshot.price_volume
        card.current_price = pv_dict.get("close_price")
        card.high_52w = pv_dict.get("high_52w")
        card.low_52w = pv_dict.get("low_52w")

        return card

    @staticmethod
    def _metric_value(data: dict, *keys: str) -> Optional[float]:
        """读取兼容格式的指标值，支持 {"ttm": x} 和直接数值两种结构。"""
        for key in keys:
            raw_value = data.get(key)
            if isinstance(raw_value, dict):
                raw_value = raw_value.get("ttm")
            value = AssetAnalysisService._optional_float(raw_value)
            if value is not None:
                return value
        return None

    async def _enrich_from_coordinator(
        self,
        card: AssetAnalysisCard,
        canonical_id: str,
        as_of: datetime,
        time_range: Optional[str] = None,
    ) -> AssetAnalysisCard:
        """从天软(Cjpy)优先、协调器兜底补充详细行情数据。

        优先级：Cjpy 单日实时补线 → Wind Excel 实时补线 → MultiSourceCoordinator
        """
        end_date = as_of.date()
        days = self._days_from_time_range(time_range)
        start_date = (
            end_date - timedelta(days=days) if days > 0 else end_date - timedelta(days=365 * 20)
        )

        cjpy_bars = await self._fetch_cjpy_price_bars_with_timeout(
            canonical_id, start_date, end_date
        )
        if cjpy_bars:
            self._apply_price_bars(card, cjpy_bars, source="cjpy")
            price_source = "cjpy"
        else:
            wind_bars = await self._fetch_wind_price_bars_with_timeout(
                canonical_id, start_date, end_date
            )
            if wind_bars:
                self._apply_price_bars(card, wind_bars, source="wind_excel")
                price_source = "wind_excel"
            else:
                price_source = self._fill_price_bars_from_coordinator(
                    card, canonical_id, start_date, end_date
                )
        fast_price_mode = price_source in {"cache", "cjpy", "wind_excel"}

        if not fast_price_mode:
            self._fill_wind_market_snapshot(card, canonical_id, as_of)
        else:
            logger.info(
                "Skipping live market snapshot in fast price mode",
                extra={"canonical_id": canonical_id, "price_source": price_source},
            )

        card.basic_info = self._build_basic_info(canonical_id, card.valuation)

        # Phase 2: 从 StockMasterDB / Wind 填充行业数据
        card.industry = self._fill_industry_data(
            canonical_id, allow_wind_fallback=not fast_price_mode
        )

        # Phase 3: 从 StockShareholderDB / Wind / AKShare 填充股东数据
        (
            card.top_10_shareholders,
            card.top_10_float_shareholders,
        ) = await self._fill_shareholder_data(canonical_id, allow_live_fallback=not fast_price_mode)

        # Phase 4: 从 DocumentEventV1DB 填充近期事件
        card.recent_events = self._fill_recent_events(
            canonical_id, allow_live_fallback=not fast_price_mode
        )

        if not fast_price_mode:
            # 宏观敏感性：通过时间序列回归计算
            card.macro_sensitivity = self._compute_macro_sensitivity(
                canonical_id, start_date, end_date
            )
        else:
            logger.info(
                "Skipping macro sensitivity in fast price mode",
                extra={"canonical_id": canonical_id, "price_source": price_source},
            )

        return card

    def _compute_macro_sensitivity(
        self,
        canonical_id: str,
        start_date: date,
        end_date: date,
    ) -> MacroSensitivity:
        """计算标的的宏观敏感性，不可用时返回空值。"""
        try:
            from services.macro_sensitivity import MacroSensitivityCalculator

            calculator = MacroSensitivityCalculator()
            return calculator.compute(
                canonical_id=canonical_id,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                min_observations=60,
            )
        except Exception as e:
            logger.warning(
                "Macro sensitivity computation failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )
            return MacroSensitivity()

    def _get_available_wind_adapter(self) -> Optional[WindAdapter]:
        """返回可用的 Wind 适配器，不可用时返回 None。

        优先使用注入的适配器（测试 mock），否则使用模块级缓存实例，
        避免每次请求都重复检测（最坏情况 14s heartbeat）。
        """
        # 优先使用注入的适配器（测试或显式传入）
        if self.wind_adapter is not None:
            try:
                if self.wind_adapter.is_available():
                    return self.wind_adapter
            except Exception:
                pass
            return None

        global _wind_available_cache, _wind_adapter_cache

        # 已确认不可用，直接跳过
        if _wind_available_cache is False:
            return None

        # 已确认可用且有缓存实例
        if _wind_available_cache is True and _wind_adapter_cache is not None:
            return _wind_adapter_cache

        adapter = _wind_adapter_cache
        if adapter is None:
            try:
                adapter = WindAdapter()
                _wind_adapter_cache = adapter
            except Exception as e:
                logger.warning("Wind adapter unavailable during construction: %s", e)
                _wind_available_cache = False
                return None

        try:
            if adapter.is_available():
                _wind_available_cache = True
                return adapter
        except Exception as e:
            logger.warning("Wind availability check failed: %s", e)

        _wind_available_cache = False
        return None

    def _fill_wind_market_snapshot(
        self,
        card: AssetAnalysisCard,
        canonical_id: str,
        as_of: datetime,
    ) -> None:
        """用 Wind 轻量市场快照补齐估值、换手率和市值字段。"""
        adapter = self._get_available_wind_adapter()
        if adapter is None:
            return

        try:
            df = adapter.fetch_market_snapshot([canonical_id], trade_date=as_of.date().isoformat())
        except Exception as e:
            logger.warning(
                "Wind market snapshot fetch failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )
            return

        if df is None or df.empty:
            return

        row = df.iloc[0]
        close = self._optional_float(row.get("close"))
        turnover = self._optional_float(row.get("turnover"))
        total_shares = self._optional_float(row.get("total_shares"))
        market_cap = (
            close * total_shares if close is not None and total_shares is not None else None
        )

        pe_ttm = self._optional_float(row.get("pe_ttm"))
        pb = self._optional_float(row.get("pb"))
        pcf_ocf_ttm = self._optional_float(row.get("pcf_ocf_ttm"))

        updates = {
            "pe_ttm": pe_ttm,
            "pb": pb,
            "pcf_ocf_ttm": pcf_ocf_ttm,
            "market_cap": market_cap,
            "total_shares": total_shares,
        }
        for key, value in updates.items():
            if value is not None:
                card.valuation[key] = value

        if close is not None and card.current_price is None:
            card.current_price = close
        if turnover is not None:
            card.turnover = turnover
            card.price_volume["turnover"] = turnover

        if card.financial:
            if pe_ttm is not None:
                card.financial.pe_ttm = pe_ttm
            if pb is not None:
                card.financial.pb_mrq = pb

    def _build_basic_info(self, canonical_id: str, valuation: dict) -> AssetBasicInfo:
        """从结构化 stock_master 补充名称/行业等基础信息。"""
        stock = None
        if self.market_repo:
            try:
                stock = self.market_repo.get_stock_master(canonical_id)
            except Exception as e:
                logger.warning("Failed to load stock master: %s", e, canonical_id=canonical_id)

        if stock:
            return AssetBasicInfo(
                symbol=canonical_id,
                name=stock.name or canonical_id,
                short_name=stock.name or canonical_id,
                listing_date=stock.list_date,
                total_shares=self._optional_float(valuation.get("total_shares")),
                float_shares=self._optional_float(valuation.get("float_shares")),
                market_cap=self._optional_float(valuation.get("market_cap")),
                float_market_cap=self._optional_float(valuation.get("float_market_cap")),
                area=stock.market,
                main_business=stock.industry_level1,
            )

        return AssetBasicInfo(
            symbol=canonical_id,
            name=canonical_id,
            short_name=canonical_id,
            total_shares=self._optional_float(valuation.get("total_shares")),
            float_shares=self._optional_float(valuation.get("float_shares")),
            market_cap=self._optional_float(valuation.get("market_cap")),
            float_market_cap=self._optional_float(valuation.get("float_market_cap")),
        )

    def _fill_industry_data(
        self, canonical_id: str, allow_wind_fallback: bool = True
    ) -> IndustryData:
        """从 StockMasterDB 填充行业数据，无数据时尝试 Wind。

        StockMasterDB 已有 industry_level1/2/3 字段（来自 AKShare 股票行业分类）。
        对于 ETF 等无行业数据的标的返回空 IndustryData。
        """
        stock = None
        if self.market_repo:
            try:
                stock = self.market_repo.get_stock_master(canonical_id)
            except Exception as e:
                logger.warning(
                    "Failed to load stock master for industry: %s",
                    e,
                    extra={"canonical_id": canonical_id},
                )

        stock_industry = IndustryData()
        if stock:
            stock_industry = IndustryData(
                sw_level_1=stock.industry_level1,
                sw_level_2=stock.industry_level2,
                sw_level_3=stock.industry_level3,
            )
            if stock.industry_level1 and stock.industry_level2 and stock.industry_level3:
                logger.info(
                    "Industry data filled from stock_master",
                    extra={
                        "canonical_id": canonical_id,
                        "sw_level_1": stock.industry_level1,
                        "sw_level_2": stock.industry_level2,
                        "sw_level_3": stock.industry_level3,
                    },
                )
                return stock_industry

        if not allow_wind_fallback:
            return stock_industry

        adapter = self._get_available_wind_adapter()
        if adapter:
            try:
                wind_industry = adapter.fetch_industry_data([canonical_id])
                if wind_industry is not None and not wind_industry.empty:
                    row = wind_industry.iloc[0]
                    return IndustryData(
                        sw_level_1=self._optional_str(row.get("industry_sw"))
                        or stock_industry.sw_level_1,
                        sw_level_2=self._optional_str(row.get("industry_sw_l2"))
                        or stock_industry.sw_level_2,
                        sw_level_3=self._optional_str(row.get("industry_sw_l3"))
                        or stock_industry.sw_level_3,
                    )
            except Exception as e:
                logger.warning(
                    "Wind industry fetch failed: %s",
                    e,
                    extra={"canonical_id": canonical_id},
                )

        return stock_industry

    async def _fill_shareholder_data(
        self, canonical_id: str, allow_live_fallback: bool = True
    ) -> tuple[list[Shareholder], list[Shareholder]]:
        """从结构化 DB / Wind 逐项 / Wind 聚合 / AKShare 填充前十大股东数据。

        优先级:
        1. StockShareholderDB 结构化表 (已有逐项数据)
        2. Wind Excel 逐项 (fetch_top10_holder_details, 带股东名称)
        3. Wind 聚合指标 (前十大合计 / 机构合计 / 股东户数)
        4. AKShare 开源数据 (逐项, 带股东名称)

        返回 (top_10_shareholders, top_10_float_shareholders)。
        目前不区分流通/非流通，均填入 top_10_shareholders。
        """
        # ===== 1. 结构化 DB =====
        try:
            holders = self.market_repo.get_latest_shareholders(canonical_id, limit=10)  # type: ignore[union-attr]
            if holders:
                top10: list[Shareholder] = []
                for s in holders:
                    top10.append(
                        Shareholder(
                            name=s.holder_name or "未知",
                            share_ratio=float(s.holding_pct) if s.holding_pct else 0.0,
                            shareholder_type=s.holder_type,
                        )
                    )

                logger.info(
                    "Shareholder data filled from StockShareholderDB",
                    extra={"canonical_id": canonical_id, "count": len(top10)},
                )
                return top10, []
        except Exception as e:
            logger.warning(
                "Failed to load shareholder data from DB: %s",
                e,
                extra={"canonical_id": canonical_id},
            )

        if not allow_live_fallback:
            return [], []

        report_date = self._latest_report_date().strftime("%Y/%m/%d")
        adapter = self._get_available_wind_adapter()

        # ===== 2. Wind 逐项股东详情 (带个人名称) =====
        if adapter is not None:
            try:
                # Run Wind Excel call in thread executor to avoid blocking event loop
                loop = asyncio.get_running_loop()
                details_df = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: adapter.fetch_top10_holder_details(
                            [canonical_id], report_date=report_date
                        ),
                    ),
                    timeout=15.0,
                )
                if details_df is not None and not details_df.empty:
                    individual: list[Shareholder] = []
                    for _, r in details_df.iterrows():
                        name = self._optional_str(r.get("name"))
                        if not name:
                            continue
                        ratio = (
                            float(r["ratio"])
                            if r.get("ratio") is not None and not pd.isna(r.get("ratio"))
                            else 0.0
                        )
                        individual.append(
                            Shareholder(
                                name=name,
                                share_ratio=ratio,
                                shareholder_type="top10_individual",
                            )
                        )

                    if individual:
                        logger.info(
                            "Shareholder data filled from Wind individual details",
                            extra={
                                "canonical_id": canonical_id,
                                "report_date": report_date,
                                "count": len(individual),
                            },
                        )
                        return individual, []
            except Exception as e:
                logger.warning(
                    "Wind individual holder details fetch failed: %s",
                    e,
                    extra={"canonical_id": canonical_id, "report_date": report_date},
                )

            # ===== 3. Wind 聚合指标 (前十大合计 / 机构合计 / 股东户数) =====
            try:
                df = adapter.fetch_holder_data([canonical_id], report_date=report_date)
            except Exception as e:
                logger.warning(
                    "Wind holder aggregate fetch failed: %s",
                    e,
                    extra={"canonical_id": canonical_id, "report_date": report_date},
                )
                df = None

            if df is not None and not df.empty:
                row = df.iloc[0]
                top10_pct = self._optional_float(row.get("top10_pct"))
                institutional_pct = self._optional_float(row.get("institutional_pct"))
                holder_num = self._optional_float(row.get("holder_num"))

                aggregate: list[Shareholder] = []
                if top10_pct is not None:
                    aggregate.append(
                        Shareholder(
                            name="前十大股东合计",
                            share_ratio=top10_pct,
                            shareholder_type="aggregate_top10",
                        )
                    )
                if institutional_pct is not None:
                    aggregate.append(
                        Shareholder(
                            name="机构持股合计",
                            share_ratio=institutional_pct,
                            shareholder_type="aggregate_institutional",
                        )
                    )
                if holder_num is not None:
                    aggregate.append(
                        Shareholder(
                            name="股东户数",
                            share_ratio=0.0,
                            shareholder_type=f"count:{int(holder_num)}",
                        )
                    )

                if aggregate:
                    logger.info(
                        "Shareholder data filled from Wind aggregate",
                        extra={"canonical_id": canonical_id, "count": len(aggregate)},
                    )
                    return aggregate, []

        # ===== 4. AKShare 开源数据逐项 =====
        try:
            akshare_adapter = AKShareAdapter()
            if akshare_adapter.is_available():
                akshare_holders = await akshare_adapter.fetch_top_shareholders(canonical_id)
                if akshare_holders:
                    akshare_list: list[Shareholder] = []
                    for h in akshare_holders:
                        name = h.get("name", "")
                        if not name:
                            continue
                        akshare_list.append(
                            Shareholder(
                                name=name,
                                share_ratio=float(h.get("share_ratio", 0.0)),
                                shareholder_type=h.get("holder_type") or "top10_individual",
                            )
                        )

                    if akshare_list:
                        logger.info(
                            "Shareholder data filled from AKShare",
                            extra={
                                "canonical_id": canonical_id,
                                "count": len(akshare_list),
                            },
                        )
                        return akshare_list, []
        except Exception as e:
            logger.warning(
                "AKShare shareholder fetch failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )

        return [], []

    def _fill_recent_events(
        self, canonical_id: str, allow_live_fallback: bool = True
    ) -> list[EventImpact]:
        """从多个来源填充近期事件。

        优先级:
        1. DocumentEventV1DB (结构化事件表)
        2. CanonicalEvent (规范事件表)
        3. AKShare 个股公告 (懒加载兜底)
        """
        # Path 1: DocumentEventV1DB (primary)
        if self.market_repo is not None and self.market_repo.db is not None:
            try:
                from data_layer.repositories.models import DocumentEventV1DB

                rows = (
                    self.market_repo.db.query(DocumentEventV1DB)
                    .filter(DocumentEventV1DB.subject_entity == canonical_id)
                    .order_by(DocumentEventV1DB.event_time.desc().nullslast())
                    .limit(20)
                    .all()
                )
                if rows:
                    events: list[EventImpact] = []
                    for row in rows:
                        events.append(
                            EventImpact(
                                event_id=row.event_id or "",
                                title=row.event_summary or "",
                                content=row.evidence_text,
                                impact_direction=row.impact_direction,
                                publish_date=row.event_time,
                                event_type=row.event_type,
                            )
                        )

                    logger.info(
                        "Recent events filled from DocumentEventV1DB",
                        extra={"canonical_id": canonical_id, "count": len(events)},
                    )
                    return events
            except Exception as e:
                logger.warning(
                    "DocumentEventV1DB query failed, trying next source: %s",
                    e,
                    extra={"canonical_id": canonical_id},
                )

        # Path 2: CanonicalEvent via EventRepositoryImpl
        try:
            from data_layer.repositories.event_repository import EventRepositoryImpl

            with db_session() as db:
                event_repo = EventRepositoryImpl(db)
                canonical_events = event_repo.list_by_impacted_symbol(canonical_id, limit=20)
                if canonical_events:
                    events = []
                    for ce in canonical_events:
                        event = self._map_to_event_impact(ce)
                        if event is not None:
                            events.append(event)

                    logger.info(
                        "Recent events filled from CanonicalEvent",
                        extra={"canonical_id": canonical_id, "count": len(events)},
                    )
                    return events
        except Exception as e:
            logger.warning(
                "CanonicalEvent query failed, trying next source: %s",
                e,
                extra={"canonical_id": canonical_id},
            )

        if not allow_live_fallback:
            return []

        # Path 3: AKShare stock announcements
        try:
            import akshare as ak

            code = canonical_id.replace(".SH", "").replace(".SZ", "")
            df = ak.stock_individual_notice_report(
                security=code,
                symbol="全部",
                begin_date="",
                end_date="",
            )
            if df is not None and not df.empty:
                events = []
                for _, row in df.iterrows():
                    event = self._map_to_event_impact(row)
                    if event is not None:
                        events.append(event)

                logger.info(
                    "Recent events filled from AKShare",
                    extra={"canonical_id": canonical_id, "count": len(events)},
                )
                return events[:20]
        except ImportError:
            logger.info(
                "AKShare not available for stock announcements",
                extra={"canonical_id": canonical_id},
            )
        except Exception as e:
            logger.warning(
                "AKShare stock notice fetch failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )

        return []

    @staticmethod
    def _map_to_event_impact(source: Any) -> Optional[EventImpact]:
        """将 CanonicalEvent 或公告行映射为 EventImpact。

        Args:
            source: CanonicalEvent 对象或 dict-like (AKShare DataFrame row)

        Returns:
            EventImpact 对象，或 None（如果无法映射）
        """
        # Case 1: CanonicalEvent domain object
        if hasattr(source, "event_id") and hasattr(source, "title"):
            return EventImpact(
                event_id=source.event_id,
                title=source.title,
                content=source.raw_text,
                impact_direction=(
                    source.impact_direction
                    if source.impact_direction and source.impact_direction != "unknown"
                    else None
                ),
                publish_date=source.event_time,
                event_type=source.event_type,
                source=source.source_name,
            )

        # Case 2: dict-like (AKShare DataFrame row)
        try:
            title = source.get("公告标题", "")
        except AttributeError:
            return None

        if not title:
            return None

        url = source.get("网址", "")
        event_id = url or f"akshare_{str(title)[:80]}"

        publish_date = None
        raw_date = source.get("公告日期")
        if raw_date is not None:
            try:
                publish_date = pd.Timestamp(raw_date).to_pydatetime()
            except (ValueError, TypeError):
                pass

        return EventImpact(
            event_id=event_id,
            title=str(title),
            content=str(title),
            publish_date=publish_date,
            event_type=source.get("公告类型", ""),
            source="AKShare",
            url=url,
        )

    async def _fetch_cjpy_price_bars_with_timeout(
        self,
        canonical_id: str,
        start_date: date,
        end_date: date,
        timeout_seconds: float = CJPY_PRICE_TIMEOUT_SECONDS,
    ) -> list[PriceBar]:
        """天软(Cjpy)最新行情拉取，带超时保护。

        只拉最近一个小窗口，再与缓存历史合并；收盘后宁愿多等几秒拿最新日线。
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._fetch_cjpy_price_bars,
                    canonical_id,
                    start_date,
                    end_date,
                ),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Cjpy price fetch timed out, falling back",
                extra={"canonical_id": canonical_id, "timeout_seconds": timeout_seconds},
            )
            return []
        except Exception:
            logger.exception(
                "Cjpy price fetch failed",
                extra={"canonical_id": canonical_id},
            )
            return []

    def _fetch_cjpy_price_bars(
        self,
        canonical_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PriceBar]:
        """从天软(Cjpy)获取最新日线行情并补充技术指标。

        Cjpy 返回 41 字段完整数据（含盘口）。
        开盘前 end_date 可能还没有日线，因此拉最近小窗口并取源返回的最新交易日。
        列名映射：时间→date, vol→volume, preclose→pre_close。
        """
        try:
            from data_layer.adapters.cjpy_adapter import CjpyAdapter

            recent_start_date = max(
                start_date,
                end_date - timedelta(days=CJPY_RECENT_LOOKBACK_DAYS),
            )
            adapter = CjpyAdapter()
            df = adapter.fetch_daily_quotes(
                codes=[canonical_id],
                start_date=recent_start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
        except Exception as e:
            logger.warning(
                "Cjpy price fetch failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )
            return []

        try:
            # 列名映射：Cjpy DataFrame → PriceBar 期望的列名
            cjpy_column_map = {
                "时间": "date",
                "preclose": "pre_close",
                "vol": "volume",
            }
            renamed = df.rename(columns=cjpy_column_map)
            latest_bars = self._build_price_bars_from_dataframe(renamed)
            if not latest_bars:
                return []
            return self._merge_cached_history_with_realtime_bar(
                canonical_id,
                start_date,
                end_date,
                latest_bars[-1],
            )
        except Exception as e:
            logger.warning(
                "Cjpy price data normalisation failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )
            return []

    async def _fetch_wind_price_bars_with_timeout(
        self,
        canonical_id: str,
        start_date: date,
        end_date: date,
        timeout_seconds: float = WIND_PRICE_TIMEOUT_SECONDS,
    ) -> list[PriceBar]:
        """Wind Excel 可取实时行情，但资产页只给短窗口，超时即降级。"""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._fetch_wind_price_bars,
                    canonical_id,
                    start_date,
                    end_date,
                    timeout_seconds,
                ),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Wind Excel price fetch timed out, falling back to coordinator",
                canonical_id=canonical_id,
                timeout_seconds=timeout_seconds,
            )
            return []
        except Exception:
            logger.exception(
                "Wind Excel price fetch failed",
                extra={"canonical_id": canonical_id},
            )
            return []

    def _fetch_wind_price_bars(
        self,
        canonical_id: str,
        start_date: date,
        end_date: date,
        timeout_seconds: float = WIND_PRICE_TIMEOUT_SECONDS,
    ) -> list[PriceBar]:
        """优先从 Wind Excel 获取 K 线并补充技术指标，失败时返回空列表让上层降级。"""
        adapter = self._get_available_wind_adapter()
        if adapter is None:
            return []

        try:
            df = adapter.fetch_realtime_quotes([canonical_id], timeout=timeout_seconds)
        except Exception as e:
            logger.warning("Wind price fetch failed, falling back to coordinator: %s", e)
            return []

        try:
            realtime_bars = self._build_price_bars_from_dataframe(df)
            if not realtime_bars:
                return []
            return self._merge_cached_history_with_realtime_bar(
                canonical_id,
                start_date,
                end_date,
                realtime_bars[-1],
            )
        except Exception as e:
            logger.warning("Wind price data could not be normalized: %s", e)
            return []

    def _merge_cached_history_with_realtime_bar(
        self,
        canonical_id: str,
        start_date: date,
        end_date: date,
        realtime_bar: PriceBar,
    ) -> list[PriceBar]:
        """将 Cjpy/Wind 实时行情单点合并进缓存历史序列。"""
        history_card = AssetAnalysisCard(canonical_id=canonical_id, as_of=datetime.utcnow())
        self._fill_price_bars_from_coordinator(history_card, canonical_id, start_date, end_date)
        bars = [bar for bar in history_card.price_bars if bar.date != realtime_bar.date]
        bars.append(realtime_bar)
        bars.sort(key=lambda bar: bar.date)
        return self._build_price_bars_from_dataframe(
            pd.DataFrame([bar.model_dump() for bar in bars])
        )

    def _build_price_bars_from_dataframe(self, df: pd.DataFrame) -> list[PriceBar]:
        """把 Wind/表格行情转换为带 MA、BOLL、MACD 的 PriceBar 序列。"""
        if df.empty:
            return []

        work = df.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.date
        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "turnover",
            "vwap",
            "pct_change",
            "amplitude",
        ]
        for col in numeric_cols:
            if col in work.columns:
                work[col] = pd.to_numeric(work[col], errors="coerce")

        work = (
            work.dropna(subset=["date", "open", "high", "low", "close"])
            .sort_values("date")
            .reset_index(drop=True)
        )
        if work.empty:
            return []

        close = work["close"]
        for period in (5, 10, 20, 60):
            work[f"ma{period}"] = close.rolling(window=period).mean()

        boll_middle = close.rolling(window=20).mean()
        boll_std = close.rolling(window=20).std()
        work["boll_middle"] = boll_middle
        work["boll_upper"] = boll_middle + (2 * boll_std)
        work["boll_lower"] = boll_middle - (2 * boll_std)

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        work["macd_dif"] = dif
        work["macd_dea"] = dea
        work["macd_hist"] = (dif - dea) * 2

        # KDJ (9,3,3)
        low_9 = work["low"].rolling(window=9, min_periods=1).min()
        high_9 = work["high"].rolling(window=9, min_periods=1).max()
        rsv = ((work["close"] - low_9) / (high_9 - low_9).replace(0, np.nan)) * 100
        work["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
        work["kdj_d"] = work["kdj_k"].ewm(com=2, adjust=False).mean()
        work["kdj_j"] = 3 * work["kdj_k"] - 2 * work["kdj_d"]

        # RSI(14)
        delta = work["close"].diff()
        gain = delta.clip(lower=0).rolling(window=14, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        work["rsi"] = 100 - (100 / (1 + rs))

        bars = []
        for _, row in work.iterrows():
            bars.append(
                PriceBar(
                    date=row["date"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=self._optional_float(row.get("volume")),
                    amount=self._optional_float(row.get("amount")),
                    turnover=self._optional_float(row.get("turnover")),
                    ma5=self._optional_float(row.get("ma5")),
                    ma10=self._optional_float(row.get("ma10")),
                    ma20=self._optional_float(row.get("ma20")),
                    ma60=self._optional_float(row.get("ma60")),
                    boll_upper=self._optional_float(row.get("boll_upper")),
                    boll_middle=self._optional_float(row.get("boll_middle")),
                    boll_lower=self._optional_float(row.get("boll_lower")),
                    macd_dif=self._optional_float(row.get("macd_dif")),
                    macd_dea=self._optional_float(row.get("macd_dea")),
                    macd_hist=self._optional_float(row.get("macd_hist")),
                    kdj_k=self._optional_float(row.get("kdj_k")),
                    kdj_d=self._optional_float(row.get("kdj_d")),
                    kdj_j=self._optional_float(row.get("kdj_j")),
                    rsi=self._optional_float(row.get("rsi")),
                    vwap=self._optional_float(row.get("vwap")),
                    pct_change=self._optional_float(row.get("pct_change")),
                    amplitude=self._optional_float(row.get("amplitude")),
                )
            )
        return bars

    TIME_RANGE_MAP: dict[str, int] = {
        "1M": 31,
        "3M": 92,
        "6M": 183,
        "1Y": 365,
        "2Y": 730,
        "3Y": 1095,
        "5Y": 1826,
        "ALL": 0,  # 0 means unlimited
    }

    @classmethod
    def _days_from_time_range(cls, time_range: Optional[str]) -> int:
        """将时间范围字符串映射为交易日数。返回0表示不限制。"""
        if time_range is None:
            return 252  # default: 1Y trading days
        days = cls.TIME_RANGE_MAP.get(time_range.upper())
        if days is None:
            logger.warning(f"Unknown time_range '{time_range}', defaulting to 1Y")
            return 252
        return days

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        """把 pandas/Excel 空值安全转成 Python float/None。"""
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value: Any) -> Optional[str]:
        """把 pandas/Excel 空值安全转成非空字符串或 None。"""
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        if not text or text.upper() in {"NAN", "NONE", "NULL", "#N/A"}:
            return None
        return text

    @staticmethod
    def _latest_report_date(reference: Optional[date] = None) -> date:
        """返回最近一个已披露季报期末日期，用于 Wind 持有人类公式。"""
        ref = reference or date.today()
        quarter_ends = (
            date(ref.year, 3, 31),
            date(ref.year, 6, 30),
            date(ref.year, 9, 30),
            date(ref.year, 12, 31),
        )
        for report_date in reversed(quarter_ends):
            if report_date <= ref:
                return report_date
        return date(ref.year - 1, 12, 31)

    def _apply_price_bars(
        self,
        card: AssetAnalysisCard,
        price_bars: list[PriceBar],
        source: str,
    ) -> None:
        """把 K 线序列回填到资产分析卡。"""
        card.price_bars = price_bars
        last_bar = price_bars[-1]
        card.current_price = last_bar.close
        card.volume = last_bar.volume
        card.amount = last_bar.amount
        card.turnover = last_bar.turnover
        card.high_52w = max(q.high for q in price_bars)
        card.low_52w = min(q.low for q in price_bars)
        if len(price_bars) >= 2:
            prev_close = price_bars[-2].close
            card.price_change = last_bar.close - prev_close
            card.price_change_pct = (
                ((last_bar.close - prev_close) / prev_close * 100) if prev_close else None
            )
        card.technical = {
            "provider": "wind_local" if source == "wind_excel" else source,
            "ma": {
                "ma5": last_bar.ma5,
                "ma10": last_bar.ma10,
                "ma20": last_bar.ma20,
                "ma60": last_bar.ma60,
            },
            "boll": {
                "upper": last_bar.boll_upper,
                "middle": last_bar.boll_middle,
                "lower": last_bar.boll_lower,
            },
            "macd": {
                "dif": last_bar.macd_dif,
                "dea": last_bar.macd_dea,
                "macd_bar": last_bar.macd_hist,
            },
            "kdj": {
                "k": last_bar.kdj_k,
                "d": last_bar.kdj_d,
                "j": last_bar.kdj_j,
            },
            "rsi": last_bar.rsi,
        }

        # 筹码分布
        chip_data = self._calculate_chip_distribution(price_bars)
        card.chip_distribution = chip_data
        if chip_data:
            card.avg_cost = self._calc_avg_cost(chip_data)
            card.chip_peak_price = max(chip_data, key=lambda x: x.concentration_pct).price
            peak_upper, peak_lower = self._calc_chip_peak_boundaries(chip_data)
            card.chip_peak_upper = peak_upper
            card.chip_peak_lower = peak_lower

    @staticmethod
    def _calculate_chip_distribution(
        price_bars: list[PriceBar], buckets: int = 180, window_days: int | None = None
    ) -> list[ChipDistributionPoint]:
        """按输入 K 线区间估算普通筹码/成交量价格分布。"""
        if not price_bars or len(price_bars) < 5:
            return []

        bars = (
            price_bars[-window_days:]
            if window_days and len(price_bars) > window_days
            else price_bars
        )
        valid_bars = [
            b
            for b in bars
            if b.close > 0 and b.high > 0 and b.low > 0 and b.volume is not None and b.volume > 0
        ]
        if len(valid_bars) < 5:
            return []

        price_min = min(b.low for b in valid_bars)
        price_max = max(b.high for b in valid_bars)
        if price_max <= price_min:
            return []

        bucket_width = (price_max - price_min) / buckets
        bucket_volumes = [0.0] * buckets

        for bar in valid_bars:
            daily_weights = AssetAnalysisService._daily_chip_price_weights(
                bar=bar,
                price_min=price_min,
                bucket_width=bucket_width,
                buckets=buckets,
            )
            for idx, weight in enumerate(daily_weights):
                bucket_volumes[idx] += weight * (bar.volume or 0)

        total_volume = sum(bucket_volumes)
        if total_volume <= 0:
            return []

        result = []
        for idx, volume in enumerate(bucket_volumes):
            bucket_center = price_min + (idx + 0.5) * bucket_width
            concentration = volume / total_volume * 100
            result.append(
                ChipDistributionPoint(
                    price=round(bucket_center, 2),
                    volume=round(volume, 2),
                    concentration_pct=round(concentration, 2),
                )
            )

        return result

    @staticmethod
    def _daily_chip_price_weights(
        bar: PriceBar,
        price_min: float,
        bucket_width: float,
        buckets: int,
    ) -> list[float]:
        """按当日 low-high 区间生成归一化成本分布。"""
        weights = [0.0] * buckets
        bar_low = min(bar.low, bar.high)
        bar_high = max(bar.low, bar.high)

        if bar_high <= bar_low:
            close_idx = min(max(int((bar.close - price_min) / bucket_width), 0), buckets - 1)
            weights[close_idx] = 1.0
            return weights

        low_idx = max(0, int((bar_low - price_min) / bucket_width))
        high_idx = min(buckets - 1, int((bar_high - price_min) / bucket_width))

        for idx in range(low_idx, high_idx + 1):
            bucket_low = price_min + idx * bucket_width
            bucket_high = bucket_low + bucket_width
            overlap_low = max(bar_low, bucket_low)
            overlap_high = min(bar_high, bucket_high)
            if overlap_high > overlap_low:
                weights[idx] = overlap_high - overlap_low

        total = sum(weights)
        if total <= 0:
            close_idx = min(max(int((bar.close - price_min) / bucket_width), 0), buckets - 1)
            weights[close_idx] = 1.0
            return weights

        return [weight / total for weight in weights]

    @staticmethod
    def _calc_avg_cost(chip_data: list[ChipDistributionPoint]) -> Optional[float]:
        """计算加权平均持仓成本。"""
        if not chip_data:
            return None
        total_vol = sum(c.volume for c in chip_data)
        if total_vol <= 0:
            return None
        weighted_sum = sum(c.price * c.volume for c in chip_data)
        return round(weighted_sum / total_vol, 2)

    @staticmethod
    def _calc_chip_peak_boundaries(
        chip_data: list[ChipDistributionPoint],
    ) -> tuple[Optional[float], Optional[float]]:
        """计算筹码峰的半峰高上下边界（Full Width at Half Maximum）。

        从最大筹码集中度价位向上下两侧搜索，找到筹码集中度首次
        降至峰值一半的价格点，通过线性插值精确定位。

        Args:
            chip_data: 筹码分布数据点列表

        Returns:
            (峰值上边界价格, 峰值下边界价格)，无法确定时返回 None
        """
        if not chip_data or len(chip_data) < 2:
            return None, None

        sorted_data = sorted(chip_data, key=lambda x: x.price)
        peak_point = max(sorted_data, key=lambda x: x.concentration_pct)
        peak_conc = peak_point.concentration_pct
        half_max = peak_conc / 2.0

        if half_max <= 0:
            return None, None

        peak_idx = sorted_data.index(peak_point)

        # Search upward for half-max crossing
        upper_boundary: Optional[float] = None
        for i in range(peak_idx, len(sorted_data) - 1):
            curr = sorted_data[i]
            next_pt = sorted_data[i + 1]
            if curr.concentration_pct >= half_max > next_pt.concentration_pct:
                # Linear interpolation
                if abs(curr.concentration_pct - next_pt.concentration_pct) > 1e-10:
                    ratio = (half_max - next_pt.concentration_pct) / (
                        curr.concentration_pct - next_pt.concentration_pct
                    )
                    upper_boundary = round(next_pt.price + ratio * (curr.price - next_pt.price), 2)
                else:
                    upper_boundary = round(curr.price, 2)
                break

        # Search downward for half-max crossing
        lower_boundary: Optional[float] = None
        for i in range(peak_idx, 0, -1):
            curr = sorted_data[i]
            prev_pt = sorted_data[i - 1]
            if curr.concentration_pct >= half_max > prev_pt.concentration_pct:
                # Linear interpolation
                if abs(curr.concentration_pct - prev_pt.concentration_pct) > 1e-10:
                    ratio = (half_max - prev_pt.concentration_pct) / (
                        curr.concentration_pct - prev_pt.concentration_pct
                    )
                    lower_boundary = round(prev_pt.price + ratio * (curr.price - prev_pt.price), 2)
                else:
                    lower_boundary = round(curr.price, 2)
                break

        return upper_boundary, lower_boundary

    def _fill_price_bars_from_coordinator(
        self,
        card: AssetAnalysisCard,
        canonical_id: str,
        start_date: date,
        end_date: date,
    ) -> Optional[str]:
        """使用现有多源协调器补齐行情数据，返回实际数据源。"""

        result = self.coordinator.fetch_historical_data(
            symbol=canonical_id,
            start_date=start_date,
            end_date=end_date,
        )

        if not (result.success and result.data):
            logger.warning(
                "Coordinator returned no price bars",
                canonical_id=canonical_id,
                error=getattr(result, "error_message", None),
            )
            return None

        price_bars = []
        for q in result.data:
            if q.close is None:
                continue
            open_price = q.open if q.open is not None else q.close
            high_price = q.high if q.high is not None else q.close
            low_price = q.low if q.low is not None else q.close
            price_bars.append(
                PriceBar(
                    date=q.timestamp.date(),
                    open=float(open_price),
                    high=float(high_price),
                    low=float(low_price),
                    close=float(q.close),
                    volume=self._optional_float(getattr(q, "volume", None)),
                    amount=self._optional_float(getattr(q, "amount", None)),
                    turnover=self._optional_float(getattr(q, "turnover", None)),
                )
            )
        if price_bars:
            enriched_bars = self._build_price_bars_from_dataframe(
                pd.DataFrame([bar.model_dump() for bar in price_bars])
            )
            self._apply_price_bars(card, enriched_bars or price_bars, source=result.primary_source)
            logger.info(f"Enriched from coordinator, source: {result.primary_source}")
            return result.primary_source
        return None
