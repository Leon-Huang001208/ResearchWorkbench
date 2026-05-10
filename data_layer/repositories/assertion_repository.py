from typing import List, Optional

from core.contracts import Assertion
from core.interfaces import AssertionRepository
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import Assertion as AssertionModel

logger = get_logger(__name__)


class AssertionRepositoryImpl(BaseRepository, AssertionRepository):
    """断言仓储实现"""

    def _to_domain(self, model: AssertionModel) -> Assertion:
        """转换为领域模型"""
        return Assertion(
            assertion_id=model.assertion_id,
            subject_entity_id=model.subject_entity_id,
            predicate=model.predicate,
            object_entity_id=model.object_entity_id,
            object_value=model.object_value,
            observed_at=model.observed_at,
            valid_from=model.valid_from,
            valid_to=model.valid_to,
            confidence=float(model.confidence),
            source_doc_id=model.source_doc_id or "",
            source_span=model.source_span,
            extractor_version=model.extractor_version,
            reviewer_status=model.reviewer_status,
            reviewer=model.reviewer,
            reviewed_at=model.reviewed_at,
            trace_ref=model.trace_ref,
            team_id=model.team_id,
            project_id=model.project_id,
        )

    def _to_model(self, domain: Assertion) -> AssertionModel:
        """转换为数据库模型"""
        return AssertionModel(
            assertion_id=domain.assertion_id,
            subject_entity_id=domain.subject_entity_id,
            predicate=domain.predicate,
            object_entity_id=domain.object_entity_id,
            object_value=domain.object_value,
            observed_at=domain.observed_at,
            valid_from=domain.valid_from,
            valid_to=domain.valid_to,
            confidence=domain.confidence,
            source_doc_id=domain.source_doc_id,
            source_span=domain.source_span,
            extractor_version=domain.extractor_version,
            reviewer_status=domain.reviewer_status,
            reviewer=domain.reviewer,
            reviewed_at=domain.reviewed_at,
            trace_ref=domain.trace_ref,
            team_id=domain.team_id,
            project_id=domain.project_id,
        )

    def save(self, entity: Assertion) -> Assertion:
        """保存断言"""
        model = self.db.query(AssertionModel).filter_by(assertion_id=entity.assertion_id).first()
        if model:
            for key, value in entity.model_dump().items():
                if hasattr(model, key):
                    setattr(model, key, value)
        else:
            model = self._to_model(entity)
            self.db.add(model)
        self.db.flush()
        logger.debug("assertion saved", assertion_id=entity.assertion_id)
        return self._to_domain(model)

    def get(self, id: str) -> Optional[Assertion]:
        """根据 ID 获取断言"""
        model = self.db.query(AssertionModel).filter_by(assertion_id=id).first()
        return self._to_domain(model) if model else None

    def list(self, limit: int = 100, offset: int = 0) -> List[Assertion]:
        """列出断言"""
        models = self.db.query(AssertionModel).limit(limit).offset(offset).all()
        return [self._to_domain(m) for m in models]

    def delete(self, id: str) -> bool:
        """删除断言"""
        count = self.db.query(AssertionModel).filter_by(assertion_id=id).delete()
        return count > 0

    def get_by_subject(self, subject_entity_id: str) -> List[Assertion]:
        """获取某主体的所有断言"""
        models = self.db.query(AssertionModel).filter_by(subject_entity_id=subject_entity_id).all()
        return [self._to_domain(m) for m in models]

    def get_pending_review(self) -> List[Assertion]:
        """获取待审核的断言"""
        models = self.db.query(AssertionModel).filter_by(reviewer_status="pending").all()
        return [self._to_domain(m) for m in models]
