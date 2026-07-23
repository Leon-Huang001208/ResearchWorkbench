"""
Abstract base classes (interfaces) for repositories.

Defines the generic Repository interface and specialized repositories for entities,
documents, assertions, events, reasoning traces, and asset analysis snapshots in
AlphaFoundry.
"""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

from core.contracts import (
    Assertion,
    AssetAnalysisSnapshot,
    CanonicalEvent,
    CanonicalId,
    DocumentEnvelope,
    ReasoningTrace,
)

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """仓储基类.

    Generic abstract base class for repositories, which handle persistence operations
    (save, get, list, delete) for entities of type T.
    """

    @abstractmethod
    def save(self, entity: T) -> T:
        """保存实体.

        Saves an entity to the repository and returns the saved entity (which may have
        additional fields set, e.g., ID, timestamps).

        Args:
            entity: Entity to save.

        Returns:
            T: Saved entity.
        """
        pass

    @abstractmethod
    def get(self, id: str) -> Optional[T]:
        """根据 ID 获取实体.

        Retrieves an entity by its unique ID (if it exists).

        Args:
            id: Unique ID of the entity to retrieve.

        Returns:
            Optional[T]: The requested entity, or None if not found.
        """
        pass

    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        """列出实体.

        Lists entities from the repository with pagination (limit and offset).

        Args:
            limit: Maximum number of entities to return (default 100).
            offset: Number of entities to skip (default 0).

        Returns:
            List[T]: List of entities.
        """
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """删除实体.

        Deletes an entity by its unique ID and returns whether the deletion was successful.

        Args:
            id: Unique ID of the entity to delete.

        Returns:
            bool: True if the entity was deleted, False otherwise.
        """
        pass


class EntityRepository(Repository[CanonicalId]):
    """实体仓储.

    Specialized repository for CanonicalId entities, adding methods to get by symbol
    and search entities.
    """

    @abstractmethod
    def get_by_symbol(self, symbol: str, venue: str) -> Optional[CanonicalId]:
        """根据代码和交易所获取实体.

        Retrieves a CanonicalId by its symbol and venue (if it exists).

        Args:
            symbol: Symbol of the entity (e.g., "AAPL", "600519").
            venue: Trading venue of the entity (e.g., "NASDAQ", "SHSE").

        Returns:
            Optional[CanonicalId]: The requested entity, or None if not found.
        """
        pass

    @abstractmethod
    def search(self, query: str) -> List[CanonicalId]:
        """搜索实体.

        Searches for entities matching the given query (implementation-specific).

        Args:
            query: Search query string.

        Returns:
            List[CanonicalId]: List of matching entities.
        """
        pass


class DocumentRepository(Repository[DocumentEnvelope]):
    """文档仓储.

    Specialized repository for DocumentEnvelope entities, adding methods to get by
    source and perform vector search.
    """

    @abstractmethod
    def get_by_source(self, source_type: str, source_name: str) -> List[DocumentEnvelope]:
        """根据来源获取文档.

        Retrieves DocumentEnvelopes from the given source type and name.

        Args:
            source_type: Type of the source (e.g., "news", "report").
            source_name: Name of the source (e.g., "Reuters", "Company X").

        Returns:
            List[DocumentEnvelope]: List of documents from the source.
        """
        pass

    @abstractmethod
    def vector_search(
        self, query_embedding: List[float], limit: int = 10
    ) -> List[DocumentEnvelope]:
        """向量搜索文档.

        Performs a vector similarity search for documents matching the query embedding.

        Args:
            query_embedding: Query embedding vector (list of floats).
            limit: Maximum number of documents to return (default 10).

        Returns:
            List[DocumentEnvelope]: List of matching documents.
        """
        pass


class AssertionRepository(Repository[Assertion]):
    """断言仓储.

    Specialized repository for Assertion entities, adding methods to get by subject
    and get pending review assertions.
    """

    @abstractmethod
    def get_by_subject(self, subject_entity_id: str) -> List[Assertion]:
        """获取某主体的所有断言.

        Retrieves all Assertions where the subject_entity_id matches the given ID.

        Args:
            subject_entity_id: Canonical ID of the subject entity.

        Returns:
            List[Assertion]: List of assertions for the subject.
        """
        pass

    @abstractmethod
    def get_pending_review(self) -> List[Assertion]:
        """获取待审核的断言.

        Retrieves all Assertions with reviewer_status = "pending".

        Returns:
            List[Assertion]: List of pending review assertions.
        """
        pass


class EventRepository(Repository[CanonicalEvent]):
    """事件仓储.

    Specialized repository for CanonicalEvent entities, adding methods to get by entity,
    time range, pending review, and list by status.
    """

    @abstractmethod
    def get_by_entity(self, entity_id: str) -> List[CanonicalEvent]:
        """获取关联到某实体的事件.

        Retrieves all CanonicalEvents associated with the given entity ID (impacted
        industries, symbols, etc.).

        Args:
            entity_id: Canonical ID of the entity.

        Returns:
            List[CanonicalEvent]: List of events associated with the entity.
        """
        pass

    @abstractmethod
    def get_by_time_range(self, start: str, end: str) -> List[CanonicalEvent]:
        """获取时间范围内的事件.

        Retrieves all CanonicalEvents with event_time between start and end (ISO format strings).

        Args:
            start: Start of the time range (ISO format string, e.g., "2024-01-01T00:00:00Z").
            end: End of the time range (ISO format string).

        Returns:
            List[CanonicalEvent]: List of events in the time range.
        """
        pass

    @abstractmethod
    def get_pending_review(self) -> List[CanonicalEvent]:
        """获取待审核的事件.

        Retrieves all CanonicalEvents with reviewer_status = "pending".

        Returns:
            List[CanonicalEvent]: List of pending review events.
        """
        pass

    @abstractmethod
    def list_by_status(self, status: str, limit: int = 100) -> List[CanonicalEvent]:
        """根据审核状态列出事件.

        Retrieves all CanonicalEvents with the given reviewer_status.

        Args:
            status: Reviewer status to filter by (e.g., "pending", "approved", "rejected").
            limit: Maximum number of events to return (default 100).

        Returns:
            List[CanonicalEvent]: List of events with the given status.
        """
        pass


class TraceRepository(Repository[ReasoningTrace]):
    """推理追踪仓储.

    Specialized repository for ReasoningTrace entities, adding method to get by request type.
    """

    @abstractmethod
    def get_by_request_type(self, request_type: str) -> List[ReasoningTrace]:
        """根据请求类型获取追踪.

        Retrieves all ReasoningTraces with the given request_type.

        Args:
            request_type: Request type to filter by (e.g., "signal_generation", "thesis_review").

        Returns:
            List[ReasoningTrace]: List of traces with the given request type.
        """
        pass


class AssetSnapshotRepository(Repository[AssetAnalysisSnapshot]):
    """资产分析快照仓储.

    Specialized repository for AssetAnalysisSnapshot entities, adding methods to get latest
    by canonical ID and get by time range.
    """

    @abstractmethod
    def get_latest_by_canonical_id(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """获取某资产的最新快照.

        Retrieves the latest AssetAnalysisSnapshot for the given canonical ID (if any).

        Args:
            canonical_id: Unique canonical ID of the asset.

        Returns:
            Optional[AssetAnalysisSnapshot]: The latest snapshot, or None if none exist.
        """
        pass

    @abstractmethod
    def get_by_canonical_id_and_time_range(
        self, canonical_id: str, start_time: str, end_time: str
    ) -> List[AssetAnalysisSnapshot]:
        """获取某资产在时间范围内的快照.

        Retrieves all AssetAnalysisSnapshots for the given canonical ID with as_of between
        start_time and end_time (ISO format strings).

        Args:
            canonical_id: Unique canonical ID of the asset.
            start_time: Start of the time range (ISO format string).
            end_time: End of the time range (ISO format string).

        Returns:
            List[AssetAnalysisSnapshot]: List of snapshots in the time range.
        """
        pass
