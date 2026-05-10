"""全局搜索服务"""
from typing import Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import or_

from core.observability import get_logger

logger = get_logger(__name__)


class SearchResult(BaseModel):
    """搜索结果条目基类"""

    id: str
    type: str
    title: str
    subtitle: Optional[str]
    score: float
    url: Optional[str]


class GlobalSearchService:
    """全局跨类型搜索服务"""

    def __init__(self, session):
        self.session = session

    def search(
        self,
        query: str,
        type_filter: Optional[List[str]] = None,
        limit: int = 20,
    ) -> Dict[str, List[Dict]]:
        """全局搜索入口

        支持搜索类型:
        - symbol: 标的代码/名称
        - event_type: 事件类型
        - thesis: 论题关键词
        - source_doc: 源文档
        - failure_memory: 失败记忆/经验教训
        - market_episode: 市场片段
        - signal: 信号
        - event: 事件
        - outcome: 结果
        - review: 审核
        """
        if type_filter is None:
            type_filter = [
                "symbol",
                "event_type",
                "thesis",
                "source_doc",
                "failure_memory",
                "market_episode",
                "signal",
                "event",
                "outcome",
                "review",
            ]

        results: Dict[str, List[Dict]] = {
            "symbols": [],
            "event_types": [],
            "theses": [],
            "source_docs": [],
            "failure_memories": [],
            "market_episodes": [],
            "signals": [],
            "events": [],
            "outcomes": [],
            "reviews": [],
        }

        pattern = f"%{query}%"

        if "symbol" in type_filter:
            try:
                results["symbols"] = self._search_symbols(pattern, limit)
            except Exception as e:
                logger.warning(f"Symbol search failed: {e}")

        if "thesis" in type_filter:
            try:
                results["theses"] = self._search_theses(pattern, limit)
            except Exception as e:
                logger.warning(f"Thesis search failed: {e}")

        if "source_doc" in type_filter:
            try:
                results["source_docs"] = self._search_source_docs(pattern, limit)
            except Exception as e:
                logger.warning(f"Source doc search failed: {e}")

        if "failure_memory" in type_filter:
            try:
                results["failure_memories"] = self._search_failure_memory(pattern, limit)
            except Exception as e:
                logger.warning(f"Failure memory search failed: {e}")

        if "market_episode" in type_filter:
            try:
                results["market_episodes"] = self._search_market_episodes(pattern, limit)
            except Exception as e:
                logger.warning(f"Market episode search failed: {e}")

        if (
            "signal" in type_filter or "thesis" in type_filter
        ):  # thesis is already included in signals
            try:
                results["signals"] = self._search_signals(pattern, limit)
            except Exception as e:
                logger.warning(f"Signal search failed: {e}")

        if "event" in type_filter or "event_type" in type_filter:
            try:
                results["events"] = self._search_events(pattern, limit)
                if "event_type" in type_filter:
                    results["event_types"] = self._search_event_types(pattern, limit)
            except Exception as e:
                logger.warning(f"Event search failed: {e}")

        if "outcome" in type_filter:
            try:
                results["outcomes"] = self._search_outcomes(pattern, limit)
            except Exception as e:
                logger.warning(f"Outcome search failed: {e}")

        if "review" in type_filter:
            try:
                results["reviews"] = self._search_reviews(query, limit)
            except Exception as e:
                logger.warning(f"Review search failed: {e}")

        return results

    def _search_symbols(self, pattern: str, limit: int) -> List[Dict]:
        """搜索标的"""
        from data_layer.repositories.models import AssetDB

        rows = (
            self.session.query(AssetDB)
            .filter(
                or_(
                    AssetDB.symbol.ilike(pattern),
                    AssetDB.name.ilike(pattern),
                    AssetDB.display_name.ilike(pattern),
                )
            )
            .order_by(AssetDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "symbol": r.symbol,
                "name": r.name,
                "display_name": r.display_name,
                "asset_type": r.asset_type,
                "industry": r.industry,
            }
            for r in rows
        ]

    def _search_event_types(self, pattern: str, limit: int) -> List[Dict]:
        """搜索事件类型"""
        from sqlalchemy import distinct

        from data_layer.repositories.models import CanonicalEvent

        rows = (
            self.session.query(distinct(CanonicalEvent.event_type))
            .filter(CanonicalEvent.event_type.ilike(pattern))
            .limit(limit)
            .all()
        )
        return [
            {
                "event_type": r[0],
            }
            for r in rows
        ]

    def _search_theses(self, pattern: str, limit: int) -> List[Dict]:
        """搜索论题"""
        from data_layer.repositories.models import AlphaSignalDB

        rows = (
            self.session.query(AlphaSignalDB)
            .filter(AlphaSignalDB.thesis.ilike(pattern))
            .order_by(AlphaSignalDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "signal_id": r.signal_id,
                "subject_id": r.subject_id,
                "thesis": r.thesis,
                "score": float(r.score),
                "status": r.status,
            }
            for r in rows
        ]

    def _search_source_docs(self, pattern: str, limit: int) -> List[Dict]:
        """搜索源文档"""
        try:
            from ingestion.models.source_doc import SourceDocDB

            rows = (
                self.session.query(SourceDocDB)
                .filter(
                    or_(
                        SourceDocDB.title.ilike(pattern),
                        SourceDocDB.content_text.ilike(pattern),
                        SourceDocDB.url.ilike(pattern),
                    )
                )
                .order_by(SourceDocDB.ingested_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "doc_id": r.doc_id,
                    "title": r.title,
                    "source_type": r.source_type,
                    "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Source doc table not available: {e}")
            return []

    def _search_failure_memory(self, pattern: str, limit: int) -> List[Dict]:
        """搜索失败记忆"""
        from data_layer.repositories.models import SignalOutcomeDB

        rows = (
            self.session.query(SignalOutcomeDB)
            .filter(
                or_(
                    SignalOutcomeDB.lesson.ilike(pattern),
                    SignalOutcomeDB.failure_reason.ilike(pattern),
                )
            )
            .order_by(SignalOutcomeDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "outcome_id": r.outcome_id,
                "signal_id": r.signal_id,
                "subject_id": r.subject_id,
                "lesson": r.lesson,
                "failure_reason": r.failure_reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def _search_market_episodes(self, pattern: str, limit: int) -> List[Dict]:
        try:
            from knowledge_layer.market_episode import MarketEpisodeDB

            rows = (
                self.session.query(MarketEpisodeDB)
                .filter(
                    or_(
                        MarketEpisodeDB.title.ilike(pattern),
                        MarketEpisodeDB.description.ilike(pattern),
                        MarketEpisodeDB.tags.ilike(pattern),
                    )
                )
                .order_by(MarketEpisodeDB.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "episode_id": r.episode_id,
                    "title": r.title,
                    "tags": r.tags,
                    "start_date": r.start_date.isoformat() if r.start_date else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Market episode table not available: {e}")
            return []

    def _search_signals(self, pattern: str, limit: int) -> List[Dict]:
        """搜索信号"""
        from data_layer.repositories.models import AlphaSignalDB

        rows = (
            self.session.query(AlphaSignalDB)
            .filter(
                or_(
                    AlphaSignalDB.thesis.ilike(pattern),
                    AlphaSignalDB.subject_id.ilike(pattern),
                    AlphaSignalDB.event_type.ilike(pattern),
                )
            )
            .order_by(AlphaSignalDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "signal_id": r.signal_id,
                "subject_id": r.subject_id,
                "thesis": r.thesis,
                "score": float(r.score),
                "confidence": float(r.confidence),
                "status": r.status,
                "event_type": r.event_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def _search_events(self, pattern: str, limit: int) -> List[Dict]:
        """搜索规范事件"""
        from data_layer.repositories.models import CanonicalEvent

        rows = (
            self.session.query(CanonicalEvent)
            .filter(
                or_(
                    CanonicalEvent.summary.ilike(pattern),
                    CanonicalEvent.event_type.ilike(pattern),
                )
            )
            .order_by(CanonicalEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "event_id": r.event_id,
                "event_type": r.event_type,
                "summary": r.summary,
                "impact_direction": r.impact_direction,
                "confidence": float(r.confidence),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def _search_outcomes(self, pattern: str, limit: int) -> List[Dict]:
        """搜索结果"""
        from data_layer.repositories.models import SignalOutcomeDB

        rows = (
            self.session.query(SignalOutcomeDB)
            .filter(
                or_(
                    SignalOutcomeDB.lesson.ilike(pattern),
                    SignalOutcomeDB.subject_id.ilike(pattern),
                    SignalOutcomeDB.failure_reason.ilike(pattern),
                )
            )
            .order_by(SignalOutcomeDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "outcome_id": r.outcome_id,
                "signal_id": r.signal_id,
                "subject_id": r.subject_id,
                "outcome_return": float(r.outcome_return),
                "outcome_excess_return": float(r.outcome_excess_return),
                "lesson": r.lesson,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def _search_reviews(self, query: str, limit: int) -> List[Dict]:
        """搜索审核记录"""
        from core.services.audit_service import AuditService
        from data_layer.repositories.audit_repository import AuditRepositoryImpl

        audit_repo = AuditRepositoryImpl(self.session)
        audit_service = AuditService(repository=audit_repo)
        return audit_service.search(query=query, limit=limit)
