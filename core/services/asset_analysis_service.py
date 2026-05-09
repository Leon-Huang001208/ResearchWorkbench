"""资产分析服务"""
from datetime import date, datetime, timedelta
from typing import Optional

from core.contracts import (
    AssetAnalysisSnapshot,
    AssetAnalysisCard,
    AssetBasicInfo,
    Shareholder,
    FinancialSummary,
    CapitalFlow,
    IndustryData,
    PriceBar,
    EventImpact,
    MacroSensitivity,
)
from core.interfaces import AssetSnapshotRepository, EntityRepository
from core.observability import get_logger
from data_layer.adapters import IFinDAdapter, LocalDataAdapter, AKShareAdapter

logger = get_logger(__name__)


class AssetAnalysisService:
    """资产分析服务
    
    Data source fallback chain:
    1. iFinD (if available) -> highest quality
    2. AKShare (if available) -> open source fallback for macOS
    3. Local -> cached data
    4. Mock -> last resort
    """

    def __init__(
        self,
        asset_snapshot_repo: Optional[AssetSnapshotRepository] = None,
        entity_repo: Optional[EntityRepository] = None,
        ifind_adapter: Optional[IFinDAdapter] = None,
        local_adapter: Optional[LocalDataAdapter] = None,
        akshare_adapter: Optional[AKShareAdapter] = None,
        use_mock: bool = False,
    ):
        self.asset_snapshot_repo = asset_snapshot_repo
        self.entity_repo = entity_repo
        self.ifind_adapter = ifind_adapter
        self.local_adapter = local_adapter or LocalDataAdapter()
        self.akshare_adapter = akshare_adapter or AKShareAdapter()
        self._use_mock = use_mock

    async def generate_snapshot(
        self,
        canonical_id: str,
        as_of: Optional[datetime] = None,
        use_mock: Optional[bool] = None,
        source: str = "local",
    ) -> AssetAnalysisSnapshot:
        """
        生成资产分析快照

        Args:
            canonical_id: 资产代码
            as_of: 快照时间
            use_mock: 是否使用模拟数据（兼容旧接口）；None 时使用构造函数设置
            source: 数据源: "mock", "local", "ifind"
        """
        if as_of is None:
            as_of = datetime.utcnow()

        # 合并实例级和调用级 use_mock
        effective_use_mock = use_mock if use_mock is not None else self._use_mock

        logger.info(
            "generating asset snapshot",
            canonical_id=canonical_id,
            as_of=as_of,
            source=source,
        )

        # 自动降级：iFinD → AKShare → Local → Mock
        if effective_use_mock or source == "mock":
            snapshot = self._generate_mock_snapshot(canonical_id, as_of)
        elif source == "akshare" and self.akshare_adapter.is_available():
            logger.info("Using AKShare open source data")
            snapshot = await self._fetch_from_akshare(canonical_id, as_of)
        elif source == "local":
            snapshot = self._fetch_from_local(canonical_id, as_of)
        elif source == "ifind" and self.ifind_adapter:
            try:
                snapshot = self._fetch_from_ifind(canonical_id, as_of)
            except Exception as e:
                logger.warning(f"iFinD fetch failed, falling back to AKShare: {e}")
                if self.akshare_adapter.is_available():
                    snapshot = await self._fetch_from_akshare(canonical_id, as_of)
                else:
                    snapshot = self._fetch_from_local(canonical_id, as_of)
        elif source == "auto":
            # 自动降级链
            success = False
            if self.ifind_adapter and self.ifind_adapter.is_available():
                try:
                    snapshot = self._fetch_from_ifind(canonical_id, as_of)
                    success = True
                except Exception as e:
                    logger.warning(f"iFinD failed: {e}")
            if not success and self.akshare_adapter.is_available():
                try:
                    logger.info("Auto fallback: using AKShare open source data (iFinD unavailable)")
                    snapshot = await self._fetch_from_akshare(canonical_id, as_of)
                    # 检查AKShare返回的数据是否有效，如果核心字段都是空的，说明拉取失败
                    if snapshot.price_volume.get('close_price') is None and snapshot.financial.get('eps', {}).get('ttm') is None:
                        logger.warning(f"AKShare returned empty data for {canonical_id}")
                        success = False
                    else:
                        success = True
                except Exception as e:
                    logger.warning(f"AKShare failed: {e}")
                    success = False
            if not success:
                logger.info("Auto fallback: using local cached data")
                snapshot = self._fetch_from_local(canonical_id, as_of)
                # 检查本地数据是否有效
                if snapshot.price_volume.get('close_price') is None and snapshot.financial.get('eps', {}).get('ttm') is None:
                    logger.warning(f"Local cache empty for {canonical_id}")
                    success = False
                else:
                    success = True
            if not success:
                logger.warning("All data sources failed, falling back to mock")
                snapshot = self._generate_mock_snapshot(canonical_id, as_of)
        elif self.akshare_adapter.is_available():
            logger.info("Using AKShare open source data (iFinD not available on macOS)")
            snapshot = self._fetch_from_akshare(canonical_id, as_of)
        elif source == "local":
            snapshot = self._fetch_from_local(canonical_id, as_of)
        else:
            logger.warning("No data source available, falling back to mock data")
            snapshot = self._generate_mock_snapshot(canonical_id, as_of)

        # 保存快照
        saved_snapshot = self.asset_snapshot_repo.save(snapshot)
        logger.info("asset snapshot saved", canonical_id=canonical_id)

        return saved_snapshot

    def _generate_mock_snapshot(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """生成模拟的资产分析快照"""
        return AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            financial={
                "revenue": {"ttm": 15000000000, "qoq": 0.08, "yoy": 0.15},
                "net_profit": {"ttm": 3200000000, "qoq": 0.12, "yoy": 0.22},
                "eps": {"ttm": 2.35, "qoq": 0.10, "yoy": 0.18},
                "roe": {"ttm": 0.185, "qoq": 0.005, "yoy": 0.02},
                "debt_ratio": 0.45,
            },
            fund_flow={
                "main_net_inflow": 250000000,
                "retail_net_inflow": 80000000,
                "institutional_holding": 0.62,
                "northbound_holding": 0.085,
                "pledge_ratio": 0.12,
            },
            price_volume={
                "close_price": 58.5,
                "ma5": 57.2,
                "ma20": 55.8,
                "ma60": 54.3,
                "volume_ma5": 125000000,
                "volume_ma20": 98000000,
                "high_52w": 72.3,
                "low_52w": 38.6,
                "rsi14": 62.5,
            },
            valuation={
                "pe_ttm": 24.9,
                "pe_lyr": 23.5,
                "pb": 3.8,
                "ps": 6.8,
                "ev_ebitda": 18.2,
                "dividend_yield": 0.021,
                "historical_percentile_pe": 0.65,
            },
            shareholder={
                "controlling_shareholder": "某某集团有限公司",
                "controlling_ratio": 0.352,
                "top10_holding_ratio": 0.585,
                "management_holding": 0.012,
                "pledge_notes": ["第一大股东质押比例：45%", "无平仓风险预警"],
            },
            industry={
                "sw_level1": "有色金属",
                "sw_level2": "贵金属",
                "sw_level3": "黄金",
                "industry_pe": 32.5,
                "industry_pb": 4.2,
                "sector_rank": 8,
                "total_sectors": 31,
            },
            event_impact=[
                "2026-04-28：发布一季报，净利润同比增长28%，超市场预期",
                "2026-04-15：机构调研纪要显示公司产能扩张进展良好",
                "2026-03-20：大股东增持0.5%股份，彰显信心",
            ],
            macro_exposure={
                "usd_cny_beta": 0.35,
                "gold_price_beta": 0.85,
                "interest_rate_sensitivity": -0.25,
                "crude_price_beta": 0.15,
            },
            evidence_refs=[
                "doc_20260428_q1_report",
                "doc_20260415_research_notes",
                "doc_20260320_announcement",
            ],
        )

    def _fetch_from_local(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """从本地数据文件读取"""
        data = self.local_adapter.get_asset_data(canonical_id)
        if data:
            logger.info("loaded data from local file", canonical_id=canonical_id)
            return AssetAnalysisSnapshot(canonical_id=canonical_id, as_of=as_of, **data)
        else:
            logger.warning("local data not found, falling back to mock", canonical_id=canonical_id)
            return self._generate_mock_snapshot(canonical_id, as_of)

    def _fetch_from_ifind(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """从 iFinD 获取真实数据"""
        # TODO: implement full fetching
        logger.warning("iFinD fetch not fully implemented", canonical_id=canonical_id)
        return self._generate_mock_snapshot(canonical_id, as_of)

    async def _fetch_from_akshare(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """从 AKShare 获取开源真实数据"""
        import akshare as ak
        import asyncio
        # 获取近一年行情
        end_date = as_of.strftime('%Y-%m-%d')
        start_date = (as_of.replace(year=as_of.year - 1)).strftime('%Y-%m-%d')
        
        quotes = await self.akshare_adapter.fetch_stock_quotes(canonical_id, start_date, end_date)
        financial = await self.akshare_adapter.fetch_financial_report(canonical_id)
        
        # 获取实时估值数据
        pe_ttm = None
        pb = None
        try:
            ak_code = canonical_id.split(".")[0]
            if ak_code:
                # 从东方财富接口获取实时估值
                realtime_df = ak.stock_zh_a_spot_em()
                row = realtime_df[realtime_df['代码'] == ak_code]
                if not row.empty:
                    pe_ttm = float(row.iloc[0]['PE-TTM'])
                    pb = float(row.iloc[0]['PB'])
        except Exception as e:
            # fallback: 手动计算 PE
            if quotes and financial and financial.get('eps'):
                last_quote = quotes[-1]
                pe_ttm = last_quote['close'] / financial['eps']
            logger.warning(f"AKShare failed to fetch realtime valuation: {e}, fallback manual")
        
        last_quote = quotes[-1] if quotes else None
        snapshot = AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            financial={
                'revenue': {'ttm': financial.get('revenue', None) if financial else None},
                'net_profit': {'ttm': financial.get('net_profit', None) if financial else None},
                'eps': {'ttm': financial.get('eps', None) if financial else None},
                'roe': {'ttm': financial.get('roe', None) if financial else None},
                'debt_ratio': financial.get('debt_ratio', None) if financial else None,
            },
            fund_flow={},
            price_volume={
                'close_price': last_quote['close'] if last_quote else None,
                'high_52w': max(q['high'] for q in quotes) if quotes else None,
                'low_52w': min(q['low'] for q in quotes) if quotes else None,
            },
            valuation={
                'pe_ttm': pe_ttm,
                'pb': pb,
            },
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )
        
        logger.info("Fetched real data from AKShare", canonical_id=canonical_id, quotes=len(quotes))
        return snapshot

    def list_available_assets(self) -> list[str]:
        """列出所有可用的资产代码（来自本地数据）"""
        return self.local_adapter.list_available_assets()

    def get_latest_snapshot(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """获取最新的资产分析快照"""
        return self.asset_snapshot_repo.get_latest_by_canonical_id(canonical_id)

    async def generate_analysis_card(
        self,
        canonical_id: str,
        as_of: Optional[datetime] = None,
        use_mock: Optional[bool] = None,
        source: str = "local",
    ) -> AssetAnalysisCard:
        """
        生成完整的资产分析卡片

        Args:
            canonical_id: 资产代码
            as_of: 快照时间
            use_mock: 是否使用模拟数据
            source: 数据源

        Returns:
            完整的资产分析卡片
        """
        if as_of is None:
            as_of = datetime.utcnow()

        logger.info("generating asset analysis card", canonical_id=canonical_id, source=source)

        # 先生成基础快照
        snapshot = await self.generate_snapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            use_mock=use_mock,
            source=source,
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

        # 从数据源补充额外信息
        effective_use_mock = use_mock if use_mock is not None else self._use_mock
        if effective_use_mock or source == "mock":
            card = self._generate_mock_analysis_card(canonical_id, as_of, card)
        else:
            # 尝试从AKShare获取更详细数据
            try:
                card = await self._enrich_from_akshare(card, canonical_id)
            except Exception as e:
                logger.warning(f"Failed to enrich from AKShare: {e}")
                # 降级到模拟数据补充
                card = self._generate_mock_analysis_card(canonical_id, as_of, card)

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
            main_inflow=flow_dict.get("main_net_inflow", 0) if flow_dict.get("main_net_inflow", 0) > 0 else 0,
            main_outflow=abs(flow_dict.get("main_net_inflow", 0)) if flow_dict.get("main_net_inflow", 0) < 0 else 0,
            northbound_flow=flow_dict.get("northbound_holding"),
        )

        # 市场数据
        pv_dict = snapshot.price_volume
        card.current_price = pv_dict.get("close_price")
        card.high_52w = pv_dict.get("high_52w")
        card.low_52w = pv_dict.get("low_52w")

        return card

    async def _enrich_from_akshare(
        self,
        card: AssetAnalysisCard,
        canonical_id: str,
    ) -> AssetAnalysisCard:
        """从AKShare补充详细数据"""
        # 尝试获取K线数据
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)

            quotes = await self.akshare_adapter.fetch_stock_quotes(
                canonical_id,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            if quotes:
                card.price_bars = []
                for q in quotes:
                    card.price_bars.append(PriceBar(
                        date=q.get("date", date.today()),
                        open=q.get("open", 0),
                        high=q.get("high", 0),
                        low=q.get("low", 0),
                        close=q.get("close", 0),
                        volume=q.get("volume"),
                        amount=q.get("amount"),
                        turnover=q.get("turnover"),
                    ))

                if card.price_bars:
                    last_bar = card.price_bars[-1]
                    card.current_price = last_bar.close
                    if len(card.price_bars) >= 2:
                        prev_close = card.price_bars[-2].close
                        card.price_change = last_bar.close - prev_close
                        card.price_change_pct = (last_bar.close - prev_close) / prev_close * 100

        except Exception as e:
            logger.warning(f"Failed to fetch K-line data from AKShare: {e}")

        # 尝试获取股东信息
        try:
            shareholders = await self.akshare_adapter.fetch_top_shareholders(canonical_id)
            if shareholders:
                card.top_10_shareholders = [
                    Shareholder(
                        name=sh.get("name", ""),
                        share_ratio=sh.get("ratio", 0),
                        change_ratio=sh.get("change"),
                    )
                    for sh in shareholders
                ]
        except Exception as e:
            logger.warning(f"Failed to fetch shareholders from AKShare: {e}")

        # 尝试获取新闻
        try:
            news_list = await self.akshare_adapter.fetch_news(canonical_id, limit=10)
            if news_list:
                card.recent_events = [
                    EventImpact(
                        event_id=f"news_{i}",
                        title=n.get("title", ""),
                        content=n.get("content"),
                        publish_date=n.get("publish_time"),
                        source=n.get("source"),
                        url=n.get("url"),
                    )
                    for i, n in enumerate(news_list)
                ]
        except Exception as e:
            logger.warning(f"Failed to fetch news from AKShare: {e}")

        return card

    def _generate_mock_analysis_card(
        self,
        canonical_id: str,
        as_of: datetime,
        base_card: AssetAnalysisCard,
    ) -> AssetAnalysisCard:
        """生成模拟的完整分析卡片"""
        # 基本信息
        base_card.basic_info = AssetBasicInfo(
            symbol=canonical_id,
            name="贵州茅台",
            short_name="贵州茅台",
            listing_date=date(2001, 8, 27),
            total_shares=1256197800,
            float_shares=1256197800,
            market_cap=2350000000000,
            float_market_cap=2350000000000,
            area="贵州",
            main_business="茅台酒及系列酒的生产与销售",
        )

        # 市场数据
        base_card.current_price = 1875.0
        base_card.price_change = 32.5
        base_card.price_change_pct = 1.77
        base_card.volume = 3250000
        base_card.amount = 6080000000
        base_card.turnover = 0.26
        base_card.high_52w = 2216.18
        base_card.low_52w = 1450.00

        # 生成K线数据
        base_card.price_bars = []
        start_date = as_of.date() - timedelta(days=90)
        price = 1800.0
        for i in range(90):
            current_date = start_date + timedelta(days=i)
            import random
            change = random.uniform(-30, 30)
            open_p = price + random.uniform(-10, 10)
            high_p = max(open_p, price + change) + random.uniform(0, 15)
            low_p = min(open_p, price + change) - random.uniform(0, 15)
            close_p = price + change
            volume = random.uniform(2000000, 5000000)

            base_card.price_bars.append(PriceBar(
                date=current_date,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume,
                amount=volume * close_p,
                turnover=random.uniform(0.15, 0.35),
            ))
            price = close_p

        # 财务数据
        base_card.financial = FinancialSummary(
            revenue=150000000000,
            net_profit=58000000000,
            roe=32.5,
            roa=26.8,
            gross_margin=91.8,
            debt_ratio=22.3,
            pe_ttm=28.6,
            pb_mrq=8.2,
            ev_ebitda=22.5,
            dividend_yield=1.85,
            report_date=date(2026, 3, 31),
        )

        # 资金流向
        base_card.capital_flow = CapitalFlow(
            main_inflow=850000000,
            main_outflow=620000000,
            main_net=230000000,
            super_inflow=450000000,
            super_outflow=320000000,
            super_net=130000000,
            large_inflow=400000000,
            large_outflow=300000000,
            large_net=100000000,
            medium_inflow=280000000,
            medium_outflow=250000000,
            medium_net=30000000,
            small_inflow=150000000,
            small_outflow=180000000,
            small_net=-30000000,
            northbound_flow=85000000,
            as_of=as_of,
        )

        # 前十大股东
        base_card.top_10_shareholders = [
            Shareholder(name="中国贵州茅台酒厂(集团)有限责任公司", share_ratio=58.01, is_state_owned=True),
            Shareholder(name="香港中央结算有限公司", share_ratio=6.88),
            Shareholder(name="贵州省国有资本运营有限责任公司", share_ratio=4.54, is_state_owned=True),
            Shareholder(name="贵州茅台酒厂集团技术开发公司", share_ratio=2.21, is_state_owned=True),
            Shareholder(name="中央汇金资产管理有限责任公司", share_ratio=0.83),
            Shareholder(name="中国证券金融股份有限公司", share_ratio=0.78),
            Shareholder(name="招商中证白酒指数证券投资基金", share_ratio=0.72),
            Shareholder(name="易方达蓝筹精选混合型证券投资基金", share_ratio=0.61),
            Shareholder(name="上证50交易型开放式指数证券投资基金", share_ratio=0.58),
            Shareholder(name="汇添富中盘价值精选混合型证券投资基金", share_ratio=0.51),
        ]

        # 前十大流通股东
        base_card.top_10_float_shareholders = base_card.top_10_shareholders

        # 行业数据
        base_card.industry = IndustryData(
            sw_level_1="食品饮料",
            sw_level_2="白酒",
            sw_level_3="高端白酒",
            industry_pe=32.5,
            industry_pb=6.8,
            sector_rank=3,
            total_stocks=126,
            stock_rank_in_sector=5,
            industry_heat=82.5,
            related_concepts=["白酒", "消费龙头", "MSCI中国", "北向重仓"],
        )

        # 近期事件
        base_card.recent_events = [
            EventImpact(
                event_id="evt_001",
                title="2026年一季报发布：净利润同比增长18.2%",
                content="公司发布2026年一季报，实现营收423.5亿元，同比增长16.8%；净利润216.8亿元，同比增长18.2%，业绩超市场预期。",
                impact_score=0.75,
                impact_direction="positive",
                publish_date=datetime(2026, 4, 28, 19, 30),
                price_reaction=2.3,
                event_type="earnings",
                source="公司公告",
                url="https://example.com/announcement/001",
            ),
            EventImpact(
                event_id="evt_002",
                title="贵州茅台研究院成立，聚焦科技创新",
                content="公司宣布成立贵州茅台研究院，将聚焦生物技术、智能制造、数字化转型等领域，推动企业高质量发展。",
                impact_score=0.60,
                impact_direction="positive",
                publish_date=datetime(2026, 4, 20, 9, 15),
                price_reaction=0.8,
                event_type="corporate",
                source="公司新闻",
                url="https://example.com/news/002",
            ),
            EventImpact(
                event_id="evt_003",
                title="北向资金持续增持，持股比例创近期新高",
                content="数据显示，北向资金近一月累计净买入贵州茅台超85亿元，持股比例升至6.88%，创近三个月新高。",
                impact_score=0.65,
                impact_direction="positive",
                publish_date=datetime(2026, 4, 15, 17, 0),
                price_reaction=1.2,
                event_type="capital_flow",
                source="东方财富网",
                url="https://example.com/news/003",
            ),
            EventImpact(
                event_id="evt_004",
                title="白酒板块整体走强，行业景气度持续",
                content="受消费复苏预期推动，白酒板块近期整体表现强势，贵州茅台、五粮液等龙头股均创出阶段新高。",
                impact_score=0.55,
                impact_direction="neutral",
                publish_date=datetime(2026, 4, 10, 11, 30),
                price_reaction=0.5,
                event_type="industry",
                source="券商研报",
                url="https://example.com/news/004",
            ),
        ]

        # 宏观敏感性
        base_card.macro_sensitivity = MacroSensitivity(
            interest_rate_sensitivity=-0.35,
            inflation_sensitivity=0.45,
            exchange_rate_sensitivity=0.25,
            commodity_sensitivity=-0.15,
            liquidity_sensitivity=0.65,
            key_macro_factors=["消费复苏", "通胀预期", "流动性", "汇率波动"],
        )

        return base_card
