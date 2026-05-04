"""
Trace 写入节点
"""
import uuid
from datetime import datetime
from typing import Optional

from core.contracts import ReasoningTrace
from core.interfaces import TraceRepository
from core.observability import get_logger
from reasoning.state import ReasoningState

logger = get_logger(__name__)


class TraceWriter:
    """推理追踪写入器"""

    def __init__(self, trace_repo: Optional[TraceRepository] = None):
        self._trace_repo = trace_repo

    def write(self, state: ReasoningState) -> ReasoningState:
        """
        写入推理追踪

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        if not state.trace_id:
            state.trace_id = str(uuid.uuid4())

        trace = ReasoningTrace(
            trace_id=state.trace_id,
            request_type=state.request_type.value,
            question=state.question,
            subject_ids=state.subject_ids,
            retrieved_doc_ids=state.retrieved_doc_ids,
            retrieved_assertion_ids=state.retrieved_assertion_ids,
            graph_paths=[],
            intermediate_hypotheses=[
                h.dict()
                if hasattr(h, "dict")
                else (h.model_dump() if hasattr(h, "model_dump") else {})
                for h in state.hypotheses
            ],
            final_answer=state.final_answer,
            provider=state.provider,
            model_name=state.model_name,
            prompt_version=state.prompt_version,
            total_latency_ms=state.total_latency_ms,
            total_tokens=state.total_tokens,
            created_at=datetime.utcnow(),
        )

        if self._trace_repo:
            try:
                self._trace_repo.save(trace)
                logger.info(f"Saved reasoning trace: {state.trace_id}")
            except Exception as e:
                logger.error(f"Failed to save trace: {e}", exc_info=True)
        else:
            logger.debug(f"Trace repo not configured, not saving: {state.trace_id}")

        return state

    def get_next_node(self, state: ReasoningState) -> Optional[str]:
        """获取下一个节点（结束）"""
        return None  # 这是最后一个节点
