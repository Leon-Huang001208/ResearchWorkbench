"""Dashboard 首页数据聚合服务"""
from datetime import UTC, datetime, timedelta
from typing import List

from sqlalchemy import desc

from core.contracts.dashboard import (
    AbnormalFlow,
    BestPerformingEventType,
    CandidateBoardSection,
    CandidateItem,
    DashboardResponse,
    GlobalNewsItem,
    HighPriorityThesis,
    LearningSection,
    MappingReviewItem,
    MarketOverviewSection,
    MissingEvidence,
    PendingAssertion,
    RecentFailure,
    ResearchQueueSection,
    SectorChangeItem,
    TodayEvent,
    TodaySection,
    WeeklyLesson,
)
from core.observability import get_logger
from data_layer.repositories.dashboard_data import DashboardDataRepository

logger = get_logger(__name__)


class DashboardService:
    """首页仪表盘数据聚合服务"""

    def __init__(self, session):
        self.session = session
        self.today_cutoff = datetime.now(UTC) - timedelta(days=1)
        self.dashboard_repo = DashboardDataRepository(session)

    def _get_mock_global_news(self) -> List[GlobalNewsItem]:
        """获取模拟的全球新闻数据"""
        now = datetime.now(UTC)
        return [
            GlobalNewsItem(
                news_id="news-001",
                title="美联储暗示或将暂停加息，全球市场应声上涨",
                source="Reuters",
                importance_score=0.95,
                summary="美联储主席在最新讲话中表示，鉴于通胀有所回落，可能会暂停加息步伐，这一表态推动了全球股市上涨。",
                content_url="https://reuters.com/business/fed-signals-pause-rate-hikes",
                published_at=(now - timedelta(hours=2)).isoformat(),
                related_symbols=["SPX", "NDX", "AAPL", "MSFT"],
                region="Global",
                is_mock=True,
            ),
            GlobalNewsItem(
                news_id="news-002",
                title="中国5月制造业PMI好于预期，经济复苏信号增强",
                source="Bloomberg",
                importance_score=0.90,
                summary="最新发布的中国制造业PMI为49.8，好于市场预期的49.5，显示经济复苏动能正在增强。",
                content_url="https://bloomberg.com/china-pmi-may-2024",
                published_at=(now - timedelta(hours=4)).isoformat(),
                related_symbols=["600519.SH", "000001.SZ", "AAPL"],
                region="China",
            ),
            GlobalNewsItem(
                news_id="news-003",
                title="英伟达发布重磅新品，AI芯片性能提升3倍",
                source="TechCrunch",
                importance_score=0.88,
                summary="英伟达在GTC大会上发布新一代GH200超级芯片，AI计算性能提升3倍，股价盘后大涨。",
                content_url="https://techcrunch.com/nvidia-gh200-launch",
                published_at=(now - timedelta(hours=6)).isoformat(),
                related_symbols=["NVDA", "MSFT", "GOOGL", "AMD"],
                region="US",
            ),
            GlobalNewsItem(
                news_id="news-004",
                title="欧盟达成绿色协议，新能源产业迎来重大利好",
                source="Financial Times",
                importance_score=0.85,
                summary="欧盟就新一轮绿色能源投资计划达成一致，将在未来5年投入5000亿欧元支持新能源产业发展。",
                content_url="https://ft.com/eu-green-deal",
                published_at=(now - timedelta(hours=8)).isoformat(),
                related_symbols=["TSLA", "ENPH", "SEDG", "002594.SZ"],
                region="Europe",
            ),
            GlobalNewsItem(
                news_id="news-005",
                title="原油价格反弹，OPEC+考虑延长减产协议",
                source="CNBC",
                importance_score=0.82,
                summary="国际油价单日上涨3.5%，因消息称OPEC+可能考虑延长减产协议至2024年底。",
                content_url="https://cnbc.com/oil-opec-production",
                published_at=(now - timedelta(hours=10)).isoformat(),
                related_symbols=["XOM", "CVX", "601857.SH"],
                region="Global",
            ),
            GlobalNewsItem(
                news_id="news-006",
                title="比特币突破6万美元，加密货币市场全线上涨",
                source="CoinDesk",
                importance_score=0.80,
                summary="比特币价格突破6万美元整数关口，创下历史新高，带动整个加密货币市场上涨。",
                content_url="https://coindesk.com/btc-60k",
                published_at=(now - timedelta(hours=12)).isoformat(),
                related_symbols=["BTC-USD", "ETH-USD", "COIN", "MSTR"],
                region="Global",
            ),
            GlobalNewsItem(
                news_id="news-007",
                title="苹果Vision Pro正式开售，首批产品秒售罄",
                source="Wall Street Journal",
                importance_score=0.78,
                summary="苹果首款混合现实设备Vision Pro正式开售，首批10万台产品在30分钟内售罄。",
                content_url="https://wsj.com/apple-vision-pro-launch",
                published_at=(now - timedelta(hours=14)).isoformat(),
                related_symbols=["AAPL", "MSFT", "META"],
                region="US",
            ),
            GlobalNewsItem(
                news_id="news-008",
                title="中国央行宣布降准0.25个百分点，释放流动性",
                source="Caixin",
                importance_score=0.75,
                summary="中国人民银行宣布下调存款准备金率0.25个百分点，预计将释放约5000亿元流动性。",
                content_url="https://caixin.com/pboc-rrr-cut",
                published_at=(now - timedelta(hours=16)).isoformat(),
                related_symbols=["601398.SH", "000001.SZ", "600036.SH"],
                region="China",
            ),
            GlobalNewsItem(
                news_id="news-009",
                title="特斯拉超级工厂落户印度，莫迪见证签约",
                source="Economic Times",
                importance_score=0.72,
                summary="特斯拉宣布在印度投资20亿美元建设超级工厂，计划年产电动车50万辆，印度总理莫迪见证签约。",
                content_url="https://economictimes.com/tesla-india-factory",
                published_at=(now - timedelta(hours=18)).isoformat(),
                related_symbols=["TSLA", "TATAMOTORS.NS"],
                region="Asia",
            ),
            GlobalNewsItem(
                news_id="news-010",
                title="国际金价创历史新高，避险情绪推动资金流入",
                source="MarketWatch",
                importance_score=0.70,
                summary="国际金价突破2500美元/盎司，创下历史新高，全球地缘政治紧张推动避险资金持续流入黄金市场。",
                content_url="https://marketwatch.com/gold-record-high",
                published_at=(now - timedelta(hours=20)).isoformat(),
                related_symbols=["GC=F", "GOLD", "600547.SH"],
                region="Global",
            ),
        ]

    def _get_mock_sectors(self) -> tuple[List[SectorChangeItem], List[SectorChangeItem]]:
        """获取模拟的板块数据"""
        top_up_sectors = [
            SectorChangeItem(
                sector_id="sector-ai",
                name="AI人工智能",
                change_pct=5.25,
                leading_stocks=["NVDA", "MSFT", "600519.SH"],
                related_news_count=12,
                is_concept=True,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-new-energy",
                name="新能源",
                change_pct=4.10,
                leading_stocks=["TSLA", "600030.SH", "002594.SZ"],
                related_news_count=8,
                is_concept=True,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-semiconductor",
                name="半导体",
                change_pct=3.65,
                leading_stocks=["AMD", "INTC", "600584.SH"],
                related_news_count=10,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-fintech",
                name="金融科技",
                change_pct=3.20,
                leading_stocks=["SQ", "PYPL", "600036.SH"],
                related_news_count=5,
                is_concept=True,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-gold",
                name="贵金属",
                change_pct=2.85,
                leading_stocks=["GOLD", "600547.SH", "601899.SH"],
                related_news_count=7,
                is_concept=False,
                is_mock=True,
            ),
        ]

        top_down_sectors = [
            SectorChangeItem(
                sector_id="sector-real-estate",
                name="房地产",
                change_pct=-3.45,
                leading_stocks=["600048.SH", "000002.SZ", "000069.SZ"],
                related_news_count=6,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-traditional-banking",
                name="传统银行",
                change_pct=-2.70,
                leading_stocks=["JPM", "WFC", "601398.SH"],
                related_news_count=4,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-retail",
                name="传统零售",
                change_pct=-2.35,
                leading_stocks=["WMT", "TGT", "600827.SH"],
                related_news_count=3,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-oil-gas",
                name="石油天然气",
                change_pct=-1.90,
                leading_stocks=["XOM", "CVX", "601857.SH"],
                related_news_count=5,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-travel",
                name="旅游酒店",
                change_pct=-1.55,
                leading_stocks=["MAR", "HLT", "600754.SH"],
                related_news_count=2,
                is_concept=False,
                is_mock=True,
            ),
        ]

        return top_up_sectors, top_down_sectors

    def get_market_overview_section(self) -> MarketOverviewSection:
        """获取市场概览板块：全球热点新闻、上涨/下跌板块概念"""
        from datetime import UTC, datetime

        has_real_news = False
        has_real_sectors = False
        last_updated = None

        try:
            # 尝试获取真实数据
            news_data, has_real_news = self.dashboard_repo.get_combined_global_news(
                limit=10, days=7
            )
            (
                up_sectors_data,
                down_sectors_data,
                has_real_sectors,
                _,
            ) = self.dashboard_repo.get_sector_changes_from_signals(days=7, limit_per_direction=10)

            if has_real_news or has_real_sectors:
                logger.info(
                    f"Using real data for market overview: news={has_real_news}, sectors={has_real_sectors}"
                )

                global_news = [GlobalNewsItem(**n, is_mock=False) for n in news_data]

                # 如果没有真实新闻数据，回退到模拟
                if not global_news:
                    global_news = self._get_mock_global_news()
                    has_real_news = False

                top_up_sectors = [SectorChangeItem(**s, is_mock=False) for s in up_sectors_data]
                top_down_sectors = [SectorChangeItem(**s, is_mock=False) for s in down_sectors_data]

                # 只要有一个方向有板块数据就使用真实数据，另一个方向可以是空的
                # 只有当两个方向都没有数据时才回退到模拟
                if not top_up_sectors and not top_down_sectors:
                    mock_up, mock_down = self._get_mock_sectors()
                    top_up_sectors = mock_up
                    top_down_sectors = mock_down
                    has_real_sectors = False

                # 使用新闻的实际发布时间作为"更新于"时间戳
                # 板块数据是实时行情（无原始发布日期），不参与计算
                def _to_utc(d: datetime) -> datetime:
                    """将 datetime 转为 UTC-aware，兼容 naive 输入"""
                    if d.tzinfo is None:
                        return d.replace(tzinfo=UTC)
                    return d.astimezone(UTC)

                candidates: List[datetime] = []
                if global_news:
                    for n in global_news:
                        if n.published_at:
                            try:
                                candidates.append(_to_utc(datetime.fromisoformat(n.published_at)))
                            except (ValueError, TypeError):
                                pass

                last_updated = max(candidates) if candidates else datetime.now(UTC)

                return MarketOverviewSection(
                    global_news=global_news,
                    top_up_sectors=top_up_sectors,
                    top_down_sectors=top_down_sectors,
                    uses_real_news=has_real_news,
                    uses_real_sectors=has_real_sectors,
                    last_updated=last_updated,
                )

        except Exception as e:
            logger.warning(f"Failed to fetch real market data: {e}, falling back to mock data")

        # 回退到模拟数据
        logger.info("Using mock data for market overview")
        global_news = self._get_mock_global_news()
        top_up_sectors, top_down_sectors = self._get_mock_sectors()

        return MarketOverviewSection(
            global_news=global_news,
            top_up_sectors=top_up_sectors,
            top_down_sectors=top_down_sectors,
            uses_real_news=False,
            uses_real_sectors=False,
            last_updated=None,
        )

    def get_today_section(self) -> TodaySection:
        """获取 Today 板块数据：新事件、高优先级论题、异常流向"""
        # 获取今日/24小时内新事件
        from data_layer.repositories.models import CanonicalEvent

        events = (
            self.session.query(CanonicalEvent)
            .filter(CanonicalEvent.created_at >= self.today_cutoff)
            .order_by(desc(CanonicalEvent.created_at))
            .limit(10)
            .all()
        )
        new_events = [
            TodayEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                summary=event.summary,
                impact_direction=event.impact_direction,
                confidence=float(event.confidence),
                created_at=event.created_at.isoformat() if event.created_at else None,
            )
            for event in events
        ]

        # 获取高优先级论题（score > 0.7 且状态活跃）
        from data_layer.repositories.models import AlphaSignalDB

        theses = (
            self.session.query(AlphaSignalDB)
            .filter(AlphaSignalDB.score >= 0.7, AlphaSignalDB.status == "active")
            .order_by(desc(AlphaSignalDB.score))
            .limit(8)
            .all()
        )
        high_priority = [
            HighPriorityThesis(
                signal_id=thesis.signal_id,
                subject_id=thesis.subject_id,
                thesis=thesis.thesis,
                score=float(thesis.score),
                confidence=float(thesis.confidence),
                status=thesis.status,
                event_type=thesis.event_type,
            )
            for thesis in theses
        ]

        # 获取异常流向（来自产业链映射）
        abnormal_flows: List[AbnormalFlow] = []
        try:
            from data_layer.repositories.industry_chain_repository import IndustryChainRepository

            repo = IndustryChainRepository(self.session)
            anomalies = repo.get_recent_abnormal_flows(limit=5)
            if anomalies:
                abnormal_flows = [
                    AbnormalFlow(
                        symbol=anomaly.symbol,
                        industry=anomaly.industry,
                        diffusion_strength=float(anomaly.diffusion_strength),
                        change_pct=float(anomaly.change_pct),
                        updated_at=anomaly.updated_at.isoformat(),
                    )
                    for anomaly in anomalies
                ]
            else:
                # 如果没有真实数据，使用模拟数据
                abnormal_flows = self._get_mock_abnormal_flows()
        except Exception as e:
            logger.warning(f"Failed to fetch abnormal flows: {e}, using mock data")
            abnormal_flows = self._get_mock_abnormal_flows()

        return TodaySection(
            new_events=new_events,
            high_priority_theses=high_priority,
            abnormal_flows=abnormal_flows,
        )

    def _get_mock_abnormal_flows(self):
        """获取模拟的异常流向数据"""
        from datetime import UTC, datetime

        return [
            AbnormalFlow(
                symbol="600519.SH",
                industry="白酒",
                diffusion_strength=0.87,
                change_pct=0.052,
                updated_at=datetime.now(UTC).isoformat(),
            ),
            AbnormalFlow(
                symbol="002594.SZ",
                industry="新能源汽车",
                diffusion_strength=0.79,
                change_pct=0.041,
                updated_at=datetime.now(UTC).isoformat(),
            ),
        ]

    def get_research_queue_section(self) -> ResearchQueueSection:
        """获取 Research Queue 板块数据：待处理断言、缺失证据、映射审查"""
        pending_assertions: List[PendingAssertion] = []
        missing_evidence: List[MissingEvidence] = []
        mapping_reviews: List[MappingReviewItem] = []
        has_real_data = False

        # 获取待处理断言（来自审查框架）
        try:
            from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
            from data_layer.repositories.models import Assertion

            # 获取待审核的断言
            AssertionRepositoryImpl(self.session)
            pending_assertions_db = (
                self.session.query(Assertion)
                .filter(Assertion.reviewer_status == "pending")
                .limit(10)
                .all()
            )

            if pending_assertions_db:
                has_real_data = True
                pending_assertions = [
                    PendingAssertion(
                        assertion_id=a.assertion_id,
                        signal_id=f"signal-linked-{a.assertion_id}",
                        subject=a.subject_entity_id or "unknown",
                        claim=f"{a.predicate} {a.object_value}" if a.object_value else a.predicate,
                        status=a.reviewer_status,
                        created_at=a.observed_at.isoformat() if a.observed_at else "",
                    )
                    for a in pending_assertions_db
                ]

            # 如果没有真实数据或部分数据缺失，使用模拟数据补充
            if not has_real_data:
                logger.info("No real research queue data found, using mock data")
                (
                    pending_assertions,
                    missing_evidence,
                    mapping_reviews,
                ) = self._get_mock_research_queue()
            else:
                # 如果有真实断言数据，但缺失其他数据，用模拟数据补充
                if not missing_evidence:
                    _, missing_evidence, _ = self._get_mock_research_queue()
                if not mapping_reviews:
                    _, _, mapping_reviews = self._get_mock_research_queue()

        except Exception as e:
            logger.warning(f"Failed to fetch research queue data: {e}, falling back to mock data")
            pending_assertions, missing_evidence, mapping_reviews = self._get_mock_research_queue()

        return ResearchQueueSection(
            pending_assertions=pending_assertions,
            missing_evidence=missing_evidence,
            mapping_reviews=mapping_reviews,
        )

    def _get_mock_research_queue(self):
        """获取模拟的研究队列数据"""
        from datetime import UTC, datetime

        pending_assertions = [
            PendingAssertion(
                assertion_id="assert-001",
                signal_id="signal-001",
                subject="600519.SH",
                claim="贵州茅台Q1净利润同比增长18.2%，超出市场预期",
                status="pending",
                created_at=datetime.now(UTC).isoformat(),
            ),
            PendingAssertion(
                assertion_id="assert-002",
                signal_id="signal-002",
                subject="002594.SZ",
                claim="比亚迪4月新能源汽车销量同比增长62%",
                status="pending",
                created_at=datetime.now(UTC).isoformat(),
            ),
            PendingAssertion(
                assertion_id="assert-003",
                signal_id="signal-003",
                subject="NVDA",
                claim="英伟达发布新一代GH200超级芯片，AI计算性能提升3倍",
                status="draft",
                created_at=datetime.now(UTC).isoformat(),
            ),
        ]

        missing_evidence = [
            MissingEvidence(
                assertion_id="assert-001",
                required_evidence_type="financial_statement",
                subject="600519.SH",
            ),
            MissingEvidence(
                assertion_id="assert-002",
                required_evidence_type="sales_data",
                subject="002594.SZ",
            ),
        ]

        mapping_reviews = [
            MappingReviewItem(
                review_id="review-001",
                subject="白酒产业链",
                reviewer="auto-mapper",
                status="pending",
            ),
            MappingReviewItem(
                review_id="review-002",
                subject="新能源汽车上下游",
                reviewer="auto-mapper",
                status="in_progress",
            ),
        ]

        return pending_assertions, missing_evidence, mapping_reviews

    def get_candidate_board_section(self) -> CandidateBoardSection:
        """获取 Candidate Board 板块：就绪度最高的候选机会"""
        candidates: List[CandidateItem] = []
        has_real_data = False

        try:
            from data_layer.repositories.models import AlphaSignalDB

            # 获取活跃信号
            active_signals = (
                self.session.query(AlphaSignalDB).filter(AlphaSignalDB.status == "active").all()
            )

            if active_signals:
                has_real_data = True
                scored = []
                for signal in active_signals:
                    # 使用简单的就绪度计算（基于 score 和 confidence）
                    score = float(signal.score or 0.5) * float(signal.confidence or 0.5)
                    scored.append(
                        {
                            "candidate_id": signal.signal_id,
                            "signal_id": signal.signal_id,
                            "subject": signal.subject_id,
                            "readiness_score": score,
                            "thesis": signal.thesis,
                            "timing_blocker": "等待更多确认信号",
                            "trigger_condition": "价格突破关键阻力位",
                            "event_type": signal.event_type or "earnings",
                        }
                    )

                # sort descending by readiness score
                scored.sort(key=lambda x: x["readiness_score"], reverse=True)
                candidates = [CandidateItem(**item) for item in scored[:10]]

            # 如果没有真实数据，使用模拟数据
            if not has_real_data:
                logger.info("No real candidate board data found, using mock data")
                candidates = self._get_mock_candidates()

        except Exception as e:
            logger.warning(f"Failed to fetch candidate board data: {e}, falling back to mock data")
            candidates = self._get_mock_candidates()

        return CandidateBoardSection(top_candidates=candidates)

    def _get_mock_candidates(self):
        """获取模拟的候选机会数据"""
        return [
            CandidateItem(
                candidate_id="candidate-001",
                signal_id="signal-001",
                subject="600519.SH",
                readiness_score=0.87,
                thesis="贵州茅台Q1业绩超预期，白酒消费复苏强劲",
                timing_blocker="等待技术面确认突破",
                trigger_condition="收盘价突破1900元",
                event_type="earnings",
            ),
            CandidateItem(
                candidate_id="candidate-002",
                signal_id="signal-002",
                subject="002594.SZ",
                readiness_score=0.82,
                thesis="比亚迪销量持续高增长，新能源汽车渗透率提升",
                timing_blocker="大盘情绪偏弱",
                trigger_condition="成交量放大2倍",
                event_type="sales_data",
            ),
            CandidateItem(
                candidate_id="candidate-003",
                signal_id="signal-003",
                subject="NVDA",
                readiness_score=0.79,
                thesis="英伟达AI芯片需求旺盛，GH200超级芯片发布",
                timing_blocker="估值偏高",
                trigger_condition="回调至合理区间",
                event_type="product_launch",
            ),
        ]

    def get_learning_section(self) -> LearningSection:
        """获取 Learning 板块：最近失败、最佳表现事件类型、每周总结"""
        recent_failures: List[RecentFailure] = []
        best_event_types: List[BestPerformingEventType] = []
        weekly_lessons: List[WeeklyLesson] = []
        has_real_data = False

        # 获取最近三个月内失败记录
        try:
            from sqlalchemy import func

            from data_layer.repositories.models import SignalOutcomeDB

            three_months_ago = datetime.now(UTC) - timedelta(days=90)
            failures = (
                self.session.query(SignalOutcomeDB)
                .filter(
                    SignalOutcomeDB.created_at >= three_months_ago,
                    SignalOutcomeDB.outcome_return < 0,
                )
                .order_by(desc(SignalOutcomeDB.created_at))
                .limit(8)
                .all()
            )

            if failures:
                has_real_data = True
                recent_failures = [
                    RecentFailure(
                        outcome_id=f.outcome_id,
                        signal_id=f.signal_id,
                        subject_id=f.subject_id,
                        failure_reason=f.failure_reason if f.failure_reason else "",
                        lesson=f.lesson if f.lesson else "",
                        outcome_return=float(f.outcome_return) if f.outcome_return else None,
                        created_at=f.created_at.isoformat() if f.created_at else None,
                    )
                    for f in failures
                ]

            # 获取最佳表现事件类型按平均超额收益
            event_stats = (
                self.session.query(
                    SignalOutcomeDB.event_type,
                    func.avg(SignalOutcomeDB.outcome_excess_return).label("avg_excess"),
                    func.count(SignalOutcomeDB.outcome_id).label("count"),
                )
                .filter(SignalOutcomeDB.event_type.isnot(None))
                .group_by(SignalOutcomeDB.event_type)
                .having(func.count(SignalOutcomeDB.outcome_id) >= 2)
                .order_by(desc("avg_excess"))
                .limit(5)
                .all()
            )

            if event_stats:
                best_event_types = [
                    BestPerformingEventType(
                        event_type=stat.event_type,
                        avg_excess_return=float(stat.avg_excess),
                        total_signals=stat.count,
                        win_rate=0.6,
                    )
                    for stat in event_stats
                ]

            # 如果没有真实数据，使用模拟数据
            if not has_real_data:
                logger.info("No real learning section data found, using mock data")
                recent_failures, best_event_types, weekly_lessons = self._get_mock_learning_data()
            elif not best_event_types or not weekly_lessons:
                # 如果部分数据缺失，用模拟数据补充
                _, mock_best, mock_lessons = self._get_mock_learning_data()
                if not best_event_types:
                    best_event_types = mock_best
                if not weekly_lessons:
                    weekly_lessons = mock_lessons

        except Exception as e:
            logger.warning(f"Failed to fetch learning section data: {e}, falling back to mock data")
            recent_failures, best_event_types, weekly_lessons = self._get_mock_learning_data()

        return LearningSection(
            recent_failures=recent_failures,
            best_event_types=best_event_types,
            weekly_lessons=weekly_lessons,
        )

    def _get_mock_learning_data(self):
        """获取模拟的学习数据"""
        from datetime import UTC, datetime

        recent_failures = [
            RecentFailure(
                outcome_id="outcome-001",
                signal_id="signal-old-001",
                subject_id="601318.SH",
                failure_reason="市场情绪超预期低迷，保险股普跌",
                lesson="需要更严格的风险控制和止损点设置",
                outcome_return=-0.085,
                created_at=(datetime.now(UTC) - timedelta(days=15)).isoformat(),
            ),
            RecentFailure(
                outcome_id="outcome-002",
                signal_id="signal-old-002",
                subject_id="AAPL",
                failure_reason="财报低于预期，科技板块整体回调",
                lesson="财报季需要更谨慎的仓位管理",
                outcome_return=-0.052,
                created_at=(datetime.now(UTC) - timedelta(days=25)).isoformat(),
            ),
        ]

        best_event_types = [
            BestPerformingEventType(
                event_type="earnings",
                avg_excess_return=0.042,
                total_signals=12,
                win_rate=0.75,
            ),
            BestPerformingEventType(
                event_type="product_launch",
                avg_excess_return=0.038,
                total_signals=8,
                win_rate=0.625,
            ),
            BestPerformingEventType(
                event_type="policy_change",
                avg_excess_return=0.031,
                total_signals=7,
                win_rate=0.571,
            ),
        ]

        weekly_lessons = [
            WeeklyLesson(
                id="lesson-2026-w19",
                week="2026-W19",
                key_takeaway="财报季来临，需要重点关注业绩预告和实际财报的差异，特别是对高预期标的要谨慎",
                created_at=datetime.now(UTC).isoformat(),
            ),
            WeeklyLesson(
                id="lesson-2026-w18",
                week="2026-W18",
                key_takeaway="政策驱动的行情往往波动大，需要分批建仓，不要追高",
                created_at=(datetime.now(UTC) - timedelta(days=7)).isoformat(),
            ),
        ]

        return recent_failures, best_event_types, weekly_lessons

    def get_crawl_feed(self, limit: int = 20, since: str = None, source_type: str = None) -> dict:
        """获取实时抓取数据流，返回 {"items": [...], "total_today": N}"""
        return self.dashboard_repo.get_recent_crawled_documents(
            limit=limit, since=since, source_type=source_type
        )

    def get_full_dashboard(self) -> DashboardResponse:
        """聚合所有板块数据生成完整仪表盘响应"""
        # 自动拉取真实数据源数据填充数据库（如果数据为空）
        from data_layer.repositories.models import CanonicalEvent

        event_count = self.session.query(CanonicalEvent).count()
        if event_count == 0:
            logger.info("No real event data found, triggering auto ingest from real data sources")
            # 异步触发真实数据拉取，不阻塞请求
            import threading

            def ingest_real_data():
                try:
                    from core.contracts import SourceType
                    from core.services.crawl_orchestrator import CrawlOrchestrator

                    orchestrator = CrawlOrchestrator()
                    orchestrator.crawl_source(SourceType.CAILIAN_SHE)
                    orchestrator.crawl_source(SourceType.CHINA_SECURITY_JOURNAL)
                    orchestrator.crawl_source(SourceType.CNSTOCK_FLASH)
                    orchestrator.crawl_source(SourceType.ZHIQIU_REPORTS)
                    orchestrator.crawl_source(SourceType.ZHIQIU_WECHAT)
                    orchestrator.crawl_source(SourceType.ZHIQIU_TRANSCRIPT)
                    logger.info("Real data ingest completed successfully via CrawlOrchestrator")
                except Exception as e:
                    logger.warning(f"Auto ingest failed: {e}")

            threading.Thread(target=ingest_real_data, daemon=True).start()

        return DashboardResponse(
            market_overview=self.get_market_overview_section(),
            today=self.get_today_section(),
            research_queue=self.get_research_queue_section(),
            candidate_board=self.get_candidate_board_section(),
            learning=self.get_learning_section(),
        )
