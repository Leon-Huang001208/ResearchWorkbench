"""
搜索仓储接口和实现

隐藏 SQLAlchemy session 依赖
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from sqlalchemy import or_

from core.observability import get_logger

logger = get_logger(__name__)


class SearchRepository(ABC):
    """搜索仓储接口"""

    @abstractmethod
    def search_symbols(self, pattern: str, limit: int) -> List[Dict]:
        """搜索标的"""
        pass

    def get_symbol_search_status(self) -> Dict:
        """返回标的搜索索引状态"""
        return {}

    @abstractmethod
    def search_event_types(self, pattern: str, limit: int) -> List[Dict]:
        """搜索事件类型"""
        pass

    @abstractmethod
    def search_theses(self, pattern: str, limit: int) -> List[Dict]:
        """搜索论题"""
        pass

    @abstractmethod
    def search_source_docs(self, pattern: str, limit: int) -> List[Dict]:
        """搜索源文档"""
        pass

    @abstractmethod
    def search_failure_memory(self, pattern: str, limit: int) -> List[Dict]:
        """搜索失败记忆"""
        pass

    @abstractmethod
    def search_market_episodes(self, pattern: str, limit: int) -> List[Dict]:
        """搜索市场片段"""
        pass

    @abstractmethod
    def search_signals(self, pattern: str, limit: int) -> List[Dict]:
        """搜索信号"""
        pass

    @abstractmethod
    def search_events(self, pattern: str, limit: int) -> List[Dict]:
        """搜索事件"""
        pass

    @abstractmethod
    def search_outcomes(self, pattern: str, limit: int) -> List[Dict]:
        """搜索结果"""
        pass

    @abstractmethod
    def search_reviews(self, query: str, limit: int) -> List[Dict]:
        """搜索审核记录"""
        pass


class SearchRepositoryImpl(SearchRepository):
    """搜索仓储 SQLAlchemy 实现"""

    def __init__(self, session):
        self.session = session

    def search_symbols(self, pattern: str, limit: int) -> List[Dict]:
        """搜索标的"""
        from services.asset_search_index_service import AssetSearchIndexService

        query = pattern.strip("%")
        return AssetSearchIndexService(self.session).search(query, limit=limit)

    def get_symbol_search_status(self) -> Dict:
        """返回标的搜索索引状态"""
        from services.asset_search_index_service import AssetSearchIndexService

        return AssetSearchIndexService(self.session).status()

    def search_event_types(self, pattern: str, limit: int) -> List[Dict]:
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

    def search_theses(self, pattern: str, limit: int) -> List[Dict]:
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

    def search_source_docs(self, pattern: str, limit: int) -> List[Dict]:
        """搜索源文档"""
        try:
            import importlib

            source_doc_module = importlib.import_module("ingestion.models.source_doc")
            SourceDocDB = source_doc_module.SourceDocDB

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

    def search_failure_memory(self, pattern: str, limit: int) -> List[Dict]:
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

    def search_market_episodes(self, pattern: str, limit: int) -> List[Dict]:
        """搜索市场片段"""
        try:
            import importlib

            market_episode_module = importlib.import_module("knowledge_layer.market_episode")
            MarketEpisodeDB = market_episode_module.MarketEpisodeDB

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

    def search_signals(self, pattern: str, limit: int) -> List[Dict]:
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

    def search_events(self, pattern: str, limit: int) -> List[Dict]:
        """搜索事件"""
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

    def search_outcomes(self, pattern: str, limit: int) -> List[Dict]:
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

    def search_reviews(self, query: str, limit: int) -> List[Dict]:
        """搜索审核记录"""
        from data_layer.repositories.audit_repository import AuditRepositoryImpl
        from services.audit_service import AuditService

        audit_repo = AuditRepositoryImpl(self.session)
        audit_service = AuditService(repository=audit_repo)
        return audit_service.search(query=query, limit=limit)
