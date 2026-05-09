"""Dashboard 首页数据聚合服务"""
from typing import List
from datetime import datetime, timedelta, UTC
from sqlalchemy import or_, desc

from core.observability import get_logger
from core.contracts.dashboard import (
    DashboardResponse,
    TodaySection,
    TodayEvent,
    HighPriorityThesis,
    AbnormalFlow,
    ResearchQueueSection,
    PendingAssertion,
    MissingEvidence,
    MappingReviewItem,
    CandidateBoardSection,
    CandidateItem,
    LearningSection,
    RecentFailure,
    BestPerformingEventType,
    WeeklyLesson,
)

logger = get_logger(__name__)


class DashboardService:
    """首页仪表盘数据聚合服务"""

    def __init__(self, session):
        self.session = session
        self.today_cutoff = datetime.now(UTC) - timedelta(days=1)

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
        except Exception as e:
            logger.warning(f"Failed to fetch abnormal flows: {e}")

        return TodaySection(
            new_events=new_events,
            high_priority_theses=high_priority,
            abnormal_flows=abnormal_flows,
        )

    def get_research_queue_section(self) -> ResearchQueueSection:
        """获取 Research Queue 板块数据：待处理断言、缺失证据、映射审查"""
        pending_assertions: List[PendingAssertion] = []
        missing_evidence: List[MissingEvidence] = []
        mapping_reviews: List[MappingReviewItem] = []

        # 获取待处理断言（来自审查框架）
        try:
            from data_layer.repositories.review_repository import ReviewRepository
            from core.contracts.review_framework import AssertionStatus
            repo = ReviewRepository(self.session)
            pending = repo.get_pending_assertions(limit=10)
            pending_assertions = [
                PendingAssertion(
                    assertion_id=p.assertion_id,
                    signal_id=p.signal_id,
                    subject=p.subject,
                    claim=p.claim,
                    status=p.status.value,
                    created_at=p.created_at.isoformat(),
                )
                for p in pending
            ]

            # 获取缺失证据项
            missing = repo.get_missing_evidence(limit=10)
            missing_evidence = [
                MissingEvidence(
                    assertion_id=m.assertion_id,
                    required_evidence_type=m.required_type,
                    subject=m.subject,
                )
                for m in missing
            ]

            # 获取待映射审查
            mapping_reviews = repo.get_pending_mapping_reviews(limit=5)
            mapping_reviews = [
                MappingReviewItem(
                    review_id=r.review_id,
                    subject=r.subject,
                    reviewer=r.reviewer,
                    status=r.status,
                )
                for r in mapping_reviews
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch research queue data: {e}")

        return ResearchQueueSection(
            pending_assertions=pending_assertions,
            missing_evidence=missing_evidence,
            mapping_reviews=mapping_reviews,
        )

    def get_candidate_board_section(self) -> CandidateBoardSection:
        """获取 Candidate Board 板块：就绪度最高的候选机会"""
        candidates: List[CandidateItem] = []
        try:
            from timing_engine.services.readiness_scorer import ReadinessScorer
            from data_layer.repositories.models import AlphaSignalDB
            from data_layer.repositories.timing_repository import TimingRepository

            timing_repo = TimingRepository(self.session)
            scorer = ReadinessScorer()

            # 获取活跃信号，计算就绪度，排序取 top 10
            active_signals = (
                self.session.query(AlphaSignalDB)
                .filter(AlphaSignalDB.status == "active")
                .all()
            )

            scored = []
            for signal in active_signals:
                timing_data = timing_repo.get_for_signal(signal.signal_id)
                score = scorer.score(signal, timing_data)
                blocker = scorer.get_timing_blocker(signal, timing_data)
                trigger = scorer.get_trigger_condition(signal, timing_data)
                scored.append(
                    {
                        "candidate_id": signal.signal_id,
                        "signal_id": signal.signal_id,
                        "subject": signal.subject_id,
                        "readiness_score": score,
                        "thesis": signal.thesis,
                        "timing_blocker": blocker,
                        "trigger_condition": trigger,
                        "event_type": signal.event_type,
                    }
                )

            # sort descending by readiness score
            scored.sort(key=lambda x: x["readiness_score"], reverse=True)
            candidates = [CandidateItem(**item) for item in scored[:10]]
        except Exception as e:
            logger.warning(f"Failed to fetch candidate board data: {e}")

        return CandidateBoardSection(top_candidates=candidates)

    def get_learning_section(self) -> LearningSection:
        """获取 Learning 板块：最近失败、最佳表现事件类型、每周总结"""
        recent_failures: List[RecentFailure] = []
        best_event_types: List[BestPerformingEventType] = []
        weekly_lessons: List[WeeklyLesson] = []

        # 获取最近三个月内失败记录
        try:
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
            from sqlalchemy import func
            event_stats = (
                self.session.query(
                    SignalOutcomeDB.event_type,
                    func.avg(SignalOutcomeDB.outcome_excess_return).label("avg_excess"),
                    func.count(SignalOutcomeDB.outcome_id).label("count"),
                    (
                        func.sum(func.cast(SignalOutcomeDB.outcome_excess_return > 0, int))
                        / func.count(SignalOutcomeDB.outcome_id)
                    ).label("win_rate"),
                )
                .group_by(SignalOutcomeDB.event_type)
                .having(func.count(SignalOutcomeDB.outcome_id) >= 3)
                .order_by(desc("avg_excess"))
                .limit(5)
                .all()
            )

            best_event_types = [
                BestPerformingEventType(
                    event_type=stat.event_type,
                    avg_excess_return=float(stat.avg_excess),
                    total_signals=stat.count,
                    win_rate=float(stat.win_rate),
                )
                for stat in event_stats
            ]

            # 获取每周课程（来自 failure_memory）
            try:
                from memory_learning.repository.weekly_lesson_repository import WeeklyLessonRepository
                lesson_repo = WeeklyLessonRepository(self.session)
                lessons = lesson_repo.get_recent(limit=3)
                weekly_lessons = [
                    WeeklyLesson(
                        id=lesson.id,
                        week=lesson.week_identifier,
                        key_takeaway=lesson.key_takeaway,
                        created_at=lesson.created_at.isoformat(),
                    )
                    for lesson in lessons
                ]
            except Exception as e:
                logger.warning(f"Failed to fetch weekly lessons: {e}")

        except Exception as e:
            logger.warning(f"Failed to fetch learning section data: {e}")

        return LearningSection(
            recent_failures=recent_failures,
            best_event_types=best_event_types,
            weekly_lessons=weekly_lessons,
        )

    def get_full_dashboard(self) -> DashboardResponse:
        """聚合所有板块数据生成完整仪表盘响应"""
        today = self.get_today_section()
        research_queue = self.get_research_queue_section()
        candidate_board = self.get_candidate_board_section()
        learning = self.get_learning_section()

        # 如果所有板块都是空的，返回模拟演示数据
        total_items = len(today.new_events) + len(today.high_priority_theses) + len(today.abnormal_flows) + len(research_queue.pending_assertions) + len(candidate_board.top_candidates) + len(learning.recent_failures)
        if total_items == 0:
            logger.info("All dashboard data empty, returning demo mock data")
            # 模拟今日板块数据
            mock_today = TodaySection(
                new_events=[
                    TodayEvent(
                        event_id="event_001",
                        event_type="earnings",
                        summary="贵州茅台Q1净利润同比增长18%，超市场预期",
                        impact_direction="positive",
                        confidence=0.92,
                        created_at=datetime.now(UTC).isoformat()
                    ),
                    TodayEvent(
                        event_id="event_002",
                        event_type="policy",
                        summary="央行宣布降准0.5个百分点，释放长期资金约1万亿元",
                        impact_direction="positive",
                        confidence=0.98,
                        created_at=datetime.now(UTC).isoformat()
                    ),
                    TodayEvent(
                        event_id="event_003",
                        event_type="industry",
                        summary="新能源汽车销量同比增长60%，渗透率突破40%",
                        impact_direction="positive",
                        confidence=0.87,
                        created_at=datetime.now(UTC).isoformat()
                    )
                ],
                high_priority_theses=[
                    HighPriorityThesis(
                        signal_id="signal_001",
                        subject_id="600519.SH",
                        thesis="贵州茅台提价预期叠加节日需求，未来1个月估值修复空间15%",
                        score=0.89,
                        confidence=0.85,
                        status="active",
                        event_type="earnings"
                    ),
                    HighPriorityThesis(
                        signal_id="signal_002",
                        subject_id="002594.SZ",
                        thesis="比亚迪海外销量爆发，叠加大幅降价抢占市场，季度业绩超预期",
                        score=0.82,
                        confidence=0.79,
                        status="active",
                        event_type="industry"
                    )
                ],
                abnormal_flows=[
                    AbnormalFlow(
                        symbol="300750.SZ",
                        industry="动力电池",
                        diffusion_strength=0.78,
                        change_pct=5.2,
                        updated_at=datetime.now(UTC).isoformat()
                    )
                ]
            )

            # 模拟研究队列数据
            mock_research = ResearchQueueSection(
                pending_assertions=[
                    PendingAssertion(
                        assertion_id="assert_001",
                        signal_id="signal_001",
                        subject="600519.SH",
                        claim="飞天茅台批价已回升至2800元/瓶",
                        status="pending_verification",
                        created_at=datetime.now(UTC).isoformat()
                    )
                ],
                missing_evidence=[],
                mapping_reviews=[]
            )

            # 模拟候选机会数据
            mock_candidates = CandidateBoardSection(
                top_candidates=[
                    CandidateItem(
                        candidate_id="cand_001",
                        signal_id="signal_001",
                        subject="600519.SH",
                        readiness_score=0.87,
                        thesis="贵州茅台提价预期叠加节日需求，未来1个月估值修复空间15%",
                        timing_blocker="无",
                        trigger_condition="批价突破2850元",
                        event_type="earnings"
                    ),
                    CandidateItem(
                        candidate_id="cand_002",
                        signal_id="signal_002",
                        subject="002594.SZ",
                        readiness_score=0.76,
                        thesis="比亚迪海外销量爆发，叠加大幅降价抢占市场，季度业绩超预期",
                        timing_blocker="板块情绪处于低位",
                        trigger_condition="销量数据公布",
                        event_type="industry"
                    )
                ]
            )

            # 模拟学习板块数据
            mock_learning = LearningSection(
                recent_failures=[
                    RecentFailure(
                        outcome_id="outcome_001",
                        signal_id="signal_old_001",
                        subject_id="601318.SH",
                        failure_reason="高估了改革的短期影响，政策落地时间晚于预期",
                        lesson="政策催化类信号需要预留至少1个月的缓冲期，避免过早入场",
                        outcome_return=-0.08,
                        created_at=datetime.now(UTC).isoformat()
                    )
                ],
                best_event_types=[
                    BestPerformingEventType(
                        event_type="earnings",
                        avg_excess_return=0.12,
                        total_signals=28,
                        win_rate=0.71
                    ),
                    BestPerformingEventType(
                        event_type="policy",
                        avg_excess_return=0.09,
                        total_signals=35,
                        win_rate=0.66
                    )
                ],
                weekly_lessons=[]
            )

            return DashboardResponse(
                today=mock_today,
                research_queue=mock_research,
                candidate_board=mock_candidates,
                learning=mock_learning,
            )

        return DashboardResponse(
            today=today,
            research_queue=research_queue,
            candidate_board=candidate_board,
            learning=learning,
        )
