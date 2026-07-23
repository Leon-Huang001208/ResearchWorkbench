"""
证据收集节点
"""

from typing import Optional

from core.interfaces import AssertionRepository, EventRepository
from core.observability import get_logger
from knowledge_layer.retrieval import VectorStore
from reasoning.state import ReasoningState

logger = get_logger(__name__)


class EvidenceCollector:
    """证据收集器"""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        assertion_repo: Optional[AssertionRepository] = None,
        event_repo: Optional[EventRepository] = None,
    ):
        self._vector_store = vector_store
        self._assertion_repo = assertion_repo
        self._event_repo = event_repo

    def collect(self, state: ReasoningState) -> ReasoningState:
        """
        收集证据

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.info(f"Collecting evidence for question: {state.question}")

        # 1. 向量搜索文档
        if self._vector_store:
            results = self._vector_store.search(
                state.question,
                top_k=20,
            )
            state.retrieved_doc_ids = [r["doc_id"] for r in results]

        # 2. 查询相关断言
        if self._assertion_repo:
            for subject_id in state.subject_ids:
                assertions = self._assertion_repo.get_by_subject(subject_id)
                state.retrieved_assertion_ids.extend([a.assertion_id for a in assertions])
            # 去重
            state.retrieved_assertion_ids = list(set(state.retrieved_assertion_ids))

        # 3. 查询相关事件
        if self._event_repo:
            for subject_id in state.subject_ids:
                events = self._event_repo.get_by_entity(subject_id)
                state.retrieved_events.extend(
                    [
                        {
                            "event_id": e.event_id,
                            "title": e.title,
                            "event_time": e.event_time.isoformat() if e.event_time else None,
                        }
                        for e in events
                    ]
                )

        logger.info(
            f"Collected: {len(state.retrieved_doc_ids)} docs, "
            f"{len(state.retrieved_assertion_ids)} assertions, "
            f"{len(state.retrieved_events)} events"
        )

        return state

    def get_next_node(self, state: ReasoningState) -> str:
        """
        获取下一个节点

        Returns:
            下一个节点名称
        """
        # 下一步生成假设
        return "hypothesis_builder"
