from typing import List, Optional

from core.contracts import ReasoningTrace
from core.interfaces import TraceRepository
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import ReasoningTrace as ReasoningTraceModel

logger = get_logger(__name__)


class TraceRepositoryImpl(BaseRepository, TraceRepository):
    """推理追踪仓储实现"""

    def _to_domain(self, model: ReasoningTraceModel) -> ReasoningTrace:
        """转换为领域模型"""
        return ReasoningTrace(
            trace_id=model.trace_id,
            request_type=model.request_type,
            question=model.question,
            subject_ids=model.subject_ids,
            retrieved_doc_ids=model.retrieved_doc_ids,
            retrieved_assertion_ids=model.retrieved_assertion_ids,
            graph_paths=model.graph_paths,
            intermediate_hypotheses=model.intermediate_hypotheses,
            final_answer=model.final_answer,
            provider=model.provider,
            model_name=model.model_name,
            prompt_version=model.prompt_version,
            total_latency_ms=model.total_latency_ms,
            total_tokens=model.total_tokens,
            team_id=model.team_id,
            project_id=model.project_id,
            created_at=model.created_at,
        )

    def _to_model(self, domain: ReasoningTrace) -> ReasoningTraceModel:
        """转换为数据库模型"""
        return ReasoningTraceModel(
            trace_id=domain.trace_id,
            request_type=domain.request_type,
            question=domain.question,
            subject_ids=domain.subject_ids,
            retrieved_doc_ids=domain.retrieved_doc_ids,
            retrieved_assertion_ids=domain.retrieved_assertion_ids,
            graph_paths=domain.graph_paths,
            intermediate_hypotheses=domain.intermediate_hypotheses,
            final_answer=domain.final_answer,
            provider=domain.provider,
            model_name=domain.model_name,
            prompt_version=domain.prompt_version,
            total_latency_ms=domain.total_latency_ms,
            total_tokens=domain.total_tokens,
            team_id=domain.team_id,
            project_id=domain.project_id,
            created_at=domain.created_at,
        )

    def save(self, entity: ReasoningTrace) -> ReasoningTrace:
        """保存追踪"""
        model = self.db.query(ReasoningTraceModel).filter_by(trace_id=entity.trace_id).first()
        if model:
            for key, value in entity.model_dump().items():
                if hasattr(model, key):
                    setattr(model, key, value)
        else:
            model = self._to_model(entity)
            self.db.add(model)
        self.db.flush()
        logger.debug("trace saved", trace_id=entity.trace_id)
        return self._to_domain(model)

    def get(self, id: str) -> Optional[ReasoningTrace]:
        """根据 ID 获取追踪"""
        model = self.db.query(ReasoningTraceModel).filter_by(trace_id=id).first()
        return self._to_domain(model) if model else None

    def list(self, limit: int = 100, offset: int = 0) -> List[ReasoningTrace]:
        """列出追踪"""
        models = self.db.query(ReasoningTraceModel).limit(limit).offset(offset).all()
        return [self._to_domain(m) for m in models]

    def delete(self, id: str) -> bool:
        """删除追踪"""
        count = self.db.query(ReasoningTraceModel).filter_by(trace_id=id).delete()
        return count > 0

    def get_by_request_type(self, request_type: str) -> List[ReasoningTrace]:
        """根据请求类型获取追踪"""
        models = self.db.query(ReasoningTraceModel).filter_by(request_type=request_type).all()
        return [self._to_domain(m) for m in models]
