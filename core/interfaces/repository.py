from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

from core.contracts import (
    AlphaSignal,
    Assertion,
    AssetAnalysisSnapshot,
    CanonicalEvent,
    CanonicalId,
    DocumentEnvelope,
    ReasoningTrace,
    ScenarioSet,
)

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """仓储基类"""

    @abstractmethod
    def save(self, entity: T) -> T:
        """保存实体"""
        pass

    @abstractmethod
    def get(self, id: str) -> Optional[T]:
        """根据 ID 获取实体"""
        pass

    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        """列出实体"""
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """删除实体"""
        pass


class EntityRepository(Repository[CanonicalId]):
    """实体仓储"""

    @abstractmethod
    def get_by_symbol(self, symbol: str, venue: str) -> Optional[CanonicalId]:
        """根据代码和交易所获取实体"""
        pass

    @abstractmethod
    def search(self, query: str) -> List[CanonicalId]:
        """搜索实体"""
        pass


class DocumentRepository(Repository[DocumentEnvelope]):
    """文档仓储"""

    @abstractmethod
    def get_by_source(self, source_type: str, source_name: str) -> List[DocumentEnvelope]:
        """根据来源获取文档"""
        pass

    @abstractmethod
    def vector_search(
        self, query_embedding: List[float], limit: int = 10
    ) -> List[DocumentEnvelope]:
        """向量搜索文档"""
        pass


class AssertionRepository(Repository[Assertion]):
    """断言仓储"""

    @abstractmethod
    def get_by_subject(self, subject_entity_id: str) -> List[Assertion]:
        """获取某主体的所有断言"""
        pass

    @abstractmethod
    def get_pending_review(self) -> List[Assertion]:
        """获取待审核的断言"""
        pass


class EventRepository(Repository[CanonicalEvent]):
    """事件仓储"""

    @abstractmethod
    def get_by_entity(self, entity_id: str) -> List[CanonicalEvent]:
        """获取关联到某实体的事件"""
        pass

    @abstractmethod
    def get_by_time_range(self, start: str, end: str) -> List[CanonicalEvent]:
        """获取时间范围内的事件"""
        pass


class TraceRepository(Repository[ReasoningTrace]):
    """推理追踪仓储"""

    @abstractmethod
    def get_by_request_type(self, request_type: str) -> List[ReasoningTrace]:
        """根据请求类型获取追踪"""
        pass


class AssetSnapshotRepository(Repository[AssetAnalysisSnapshot]):
    """资产分析快照仓储"""

    @abstractmethod
    def get_latest_by_canonical_id(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """获取某资产的最新快照"""
        pass

    @abstractmethod
    def get_by_canonical_id_and_time_range(
        self, canonical_id: str, start_time: str, end_time: str
    ) -> List[AssetAnalysisSnapshot]:
        """获取某资产在时间范围内的快照"""
        pass
