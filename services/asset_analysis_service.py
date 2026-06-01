"""资产分析服务"""
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from core.contracts import (
    AssetAnalysisCard,
    AssetAnalysisSnapshot,
    AssetBasicInfo,
    CapitalFlow,
    FinancialSummary,
    IndustryData,
    MacroSensitivity,
    PriceBar,
)
from core.interfaces import AssetSnapshotRepository, EntityRepository
from core.observability import get_logger
from data_layer.coordinator.multi_source_coordinator import MultiSourceCoordinator, get_coordinator
from data_layer.repositories.market_data_repository import MarketDataRepository

if TYPE_CHECKING:
    from services.wind_analysis_service import WindAnalysisService

logger = get_logger(__name__)


class AssetAnalysisService:
    """资产分析服务

    数据源优先级:
    1. Wind Excel 插件 (如可用) -> 机构级数据质量
    2. 结构化 SQL 表 (stock_daily_bar, stock_valuation, stock_financial_metric)
    3. MultiSourceCoordinator 自动降级链: AKShare -> BaoStock -> Yahoo
    """

    def __init__(
        self,
        asset_snapshot_repo: Optional[AssetSnapshotRepository] = None,
        entity_repo: Optional[EntityRepository] = None,
        coordinator: Optional[MultiSourceCoordinator] = None,
        market_repo: Optional[MarketDataRepository] = None,
        wind_service: Optional["WindAnalysisService"] = None,
    ):
        self.asset_snapshot_repo = asset_snapshot_repo
        self.entity_repo = entity_repo
        self.coordinator = coordinator or get_coordinator()
        self.market_repo = market_repo
        self.wind_service = wind_service

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
        latest_bar = self.market_repo.get_latest_daily_bar(canonical_id)
        latest_valuation = self.market_repo.get_latest_valuation(canonical_id)
        latest_financial = self.market_repo.get_latest_financial(canonical_id)
        shareholders = self.market_repo.get_latest_shareholders(canonical_id, limit=10)

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
                "pe_dynamic": float(latest_valuation.pe_dynamic)
                if latest_valuation.pe_dynamic
                else None,
                "pb": float(latest_valuation.pb) if latest_valuation.pb else None,
                "ps": float(latest_valuation.ps) if latest_valuation.ps else None,
                "market_cap": float(latest_valuation.market_cap)
                if latest_valuation.market_cap
                else None,
                "float_market_cap": float(latest_valuation.float_market_cap)
                if latest_valuation.float_market_cap
                else None,
            }

        financial = {}
        if latest_financial:
            financial = {
                "report_date": latest_financial.report_date.isoformat()
                if latest_financial.report_date
                else None,
                "report_type": latest_financial.report_type,
                "total_revenue": float(latest_financial.total_revenue)
                if latest_financial.total_revenue
                else None,
                "net_profit": float(latest_financial.net_profit)
                if latest_financial.net_profit
                else None,
                "roe": float(latest_financial.roe) if latest_financial.roe else None,
                "roa": float(latest_financial.roa) if latest_financial.roa else None,
                "gross_margin": float(latest_financial.gross_margin)
                if latest_financial.gross_margin
                else None,
                "net_margin": float(latest_financial.net_margin)
                if latest_financial.net_margin
                else None,
                "debt_ratio": float(latest_financial.debt_ratio)
                if latest_financial.debt_ratio
                else None,
                "total_assets": float(latest_financial.total_assets)
                if latest_financial.total_assets
                else None,
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

        snapshot = AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            financial={},
            fund_flow={},
            price_volume={
                "close_price": last_quote.close,
                "high_52w": max(q.high for q in result.data),
                "low_52w": min(q.low for q in result.data),
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
    ) -> AssetAnalysisCard:
        """
        生成完整的资产分析卡片

        数据源优先级:
        1. Wind Excel 插件 (如可用)
        2. 结构化 SQL 表 -> MultiSourceCoordinator 降级

        Args:
            canonical_id: 资产代码
            as_of: 快照时间
            use_mock: 已废弃
            source: 已废弃

        Returns:
            完整的资产分析卡片
        """
        if as_of is None:
            as_of = datetime.utcnow()

        logger.info("generating asset analysis card", canonical_id=canonical_id)

        # 数据源优先级:
        # 1. Wind Excel 插件 (如可用，WSD 批量获取 ~15-30 秒)
        # 2. 结构化 SQL 表 (毫秒级)
        # 3. MultiSourceCoordinator 降级链

        # 优先尝试 Wind 数据源
        if self.wind_service is not None:
            try:
                wind_card = self.wind_service.build_analysis_card(
                    canonical_id=canonical_id, as_of=as_of
                )
                if wind_card is not None:
                    logger.info("analysis card built from Wind", canonical_id=canonical_id)
                    return wind_card
            except Exception as e:
                logger.warning(
                    f"Wind data source failed, falling back: {e}",
                    canonical_id=canonical_id,
                )

        # Wind 不可用或失败，回退到原有逻辑
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

        # 从协调器补充更详细数据
        card = await self._enrich_from_coordinator(card, canonical_id, as_of)

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
            revenue=fin_dict.get("revenue", {}).get("ttm"),
            net_profit=fin_dict.get("net_profit", {}).get("ttm"),
            roe=fin_dict.get("roe", {}).get("ttm"),
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
            main_inflow=flow_dict.get("main_net_inflow", 0)
            if flow_dict.get("main_net_inflow", 0) > 0
            else 0,
            main_outflow=abs(flow_dict.get("main_net_inflow", 0))
            if flow_dict.get("main_net_inflow", 0) < 0
            else 0,
            northbound_flow=flow_dict.get("northbound_holding"),
        )

        # 市场数据
        pv_dict = snapshot.price_volume
        card.current_price = pv_dict.get("close_price")
        card.high_52w = pv_dict.get("high_52w")
        card.low_52w = pv_dict.get("low_52w")

        return card

    async def _enrich_from_coordinator(
        self,
        card: AssetAnalysisCard,
        canonical_id: str,
        as_of: datetime,
    ) -> AssetAnalysisCard:
        """从协调器补充详细数据"""
        # 获取K线数据
        end_date = as_of.date()
        start_date = end_date - timedelta(days=365)

        result = self.coordinator.fetch_historical_data(
            symbol=canonical_id,
            start_date=start_date,
            end_date=end_date,
        )

        if result.success and result.data:
            card.price_bars = []
            for q in result.data:
                card.price_bars.append(
                    PriceBar(
                        date=q.timestamp.date(),
                        open=q.open,
                        high=q.high,
                        low=q.low,
                        close=q.close,
                        volume=q.volume,
                        amount=q.amount,
                        turnover=getattr(q, "turnover", None),
                    )
                )

            if card.price_bars:
                last_bar = card.price_bars[-1]
                card.current_price = last_bar.close
                card.volume = last_bar.volume
                card.amount = last_bar.amount
                card.turnover = last_bar.turnover
                if len(card.price_bars) >= 2:
                    prev_close = card.price_bars[-2].close
                    card.price_change = last_bar.close - prev_close
                    card.price_change_pct = (last_bar.close - prev_close) / prev_close * 100

        # 填充基本信息（需要从其他数据源获取）
        card.basic_info = AssetBasicInfo(
            symbol=canonical_id,
            name=canonical_id,
            short_name=canonical_id,
        )

        # 空的股东列表
        card.top_10_shareholders = []
        card.top_10_float_shareholders = []

        # 空的行业数据
        card.industry = IndustryData()

        # 空的事件列表
        card.recent_events = []

        # 空的宏观敏感性
        card.macro_sensitivity = MacroSensitivity()

        logger.info(f"Enriched from coordinator, source: {result.primary_source}")

        return card
