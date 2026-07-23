"""全局搜索服务"""

from typing import Dict, List, Optional

from core.observability import get_logger
from data_layer.repositories.search_repository import SearchRepository

logger = get_logger(__name__)


class GlobalSearchService:
    """全局跨类型搜索服务"""

    def __init__(self, search_repo: SearchRepository):
        self.search_repo = search_repo

    def search(
        self,
        query: str,
        type_filter: Optional[List[str]] = None,
        limit: int = 20,
    ) -> Dict[str, object]:
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

        results: Dict[str, object] = {
            "symbols": [],
            "symbol_search_status": {},
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
                results["symbols"] = self.search_repo.search_symbols(pattern, limit)
                status_getter = getattr(self.search_repo, "get_symbol_search_status", None)
                if callable(status_getter):
                    status = status_getter()
                    if isinstance(status, dict):
                        results["symbol_search_status"] = status
            except Exception as e:
                logger.warning(f"Symbol search failed: {e}")

        if "thesis" in type_filter:
            try:
                results["theses"] = self.search_repo.search_theses(pattern, limit)
            except Exception as e:
                logger.warning(f"Thesis search failed: {e}")

        if "source_doc" in type_filter:
            try:
                results["source_docs"] = self.search_repo.search_source_docs(pattern, limit)
            except Exception as e:
                logger.warning(f"Source doc search failed: {e}")

        if "failure_memory" in type_filter:
            try:
                results["failure_memories"] = self.search_repo.search_failure_memory(pattern, limit)
            except Exception as e:
                logger.warning(f"Failure memory search failed: {e}")

        if "market_episode" in type_filter:
            try:
                results["market_episodes"] = self.search_repo.search_market_episodes(pattern, limit)
            except Exception as e:
                logger.warning(f"Market episode search failed: {e}")

        if (
            "signal" in type_filter or "thesis" in type_filter
        ):  # thesis is already included in signals
            try:
                results["signals"] = self.search_repo.search_signals(pattern, limit)
            except Exception as e:
                logger.warning(f"Signal search failed: {e}")

        if "event" in type_filter or "event_type" in type_filter:
            try:
                results["events"] = self.search_repo.search_events(pattern, limit)
                if "event_type" in type_filter:
                    results["event_types"] = self.search_repo.search_event_types(pattern, limit)
            except Exception as e:
                logger.warning(f"Event search failed: {e}")

        if "outcome" in type_filter:
            try:
                results["outcomes"] = self.search_repo.search_outcomes(pattern, limit)
            except Exception as e:
                logger.warning(f"Outcome search failed: {e}")

        if "review" in type_filter:
            try:
                results["reviews"] = self.search_repo.search_reviews(query, limit)
            except Exception as e:
                logger.warning(f"Review search failed: {e}")

        return results
