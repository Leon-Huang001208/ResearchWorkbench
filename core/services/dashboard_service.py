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
        # 自动拉取真实数据源数据填充数据库（如果数据为空）
        from data_layer.repositories.models import CanonicalEvent
        event_count = self.session.query(CanonicalEvent).count()
        if event_count == 0:
            logger.info("No real event data found, triggering auto ingest from real data sources")
            # 异步触发真实数据拉取，不阻塞请求
            import threading
            def ingest_real_data():
                try:
                    import requests
                    # 拉取财联社电报
                    requests.post("http://127.0.0.1:8000/api/ingest/cls", json={"days": 1}, timeout=10)
                    # 拉取中国证券网新闻
                    requests.post("http://127.0.0.1:8000/api/ingest/cnstock", json={"channel": "证券"}, timeout=10)
                    # 拉取知丘研报
                    requests.post("http://127.0.0.1:8000/api/ingest/zq", json={"doc_types": "REPORT", "days": 1}, timeout=10)
                    logger.info("Real data ingest completed successfully")
                except Exception as e:
                    logger.warning(f"Auto ingest failed: {e}")
            threading.Thread(target=ingest_real_data, daemon=True).start()

        return DashboardResponse(
            today=self.get_today_section(),
            research_queue=self.get_research_queue_section(),
            candidate_board=self.get_candidate_board_section(),
            learning=self.get_learning_section(),
        )
