"""
证据检索器 - 报告编译器.

统一检索入口，接收 SourcePlan（含多个 RetrievalQuery），调用检索后端获取
EvidencePackage。对应 deep-research-report.md "检索器" 技能。

第一阶段采用适配器模式：定义 EvidenceRetrieverProtocol，使现有两条检索路径
（RAGRetrievalService 内存版 / DatabaseEvidenceRetriever SQL 版）可互换注入。
默认提供一个 PassthroughEvidenceRetriever，直接消费上游已检索好的 EvidencePackage，
让编译器在无检索后端时也能跑通流水线（用于测试与早期集成）。

第二阶段新增 AssertionRetriever：从 assertion 表检索已结构化断言，包成
EvidencePackage 供 fact_extractor 复用（assertion 已是事实，跳过 LLM 抽取）。
"""

from typing import Any, Optional, Protocol, runtime_checkable

from core.contracts import (
    Assertion,
    EvidenceChunk,
    EvidenceDocument,
    EvidencePackage,
    EvidenceType,
    RetrievalQuery,
    SourceType,
)
from core.observability import get_logger

logger = get_logger(__name__)


@runtime_checkable
class EvidenceRetrieverProtocol(Protocol):
    """证据检索器协议 - 与 reporting/projects/generation.py 的 EvidenceRetriever 对齐.

    任何实现该协议的检索后端都可注入 ReportCompiler。
    """

    def retrieve(self, query: RetrievalQuery, **kwargs: Any) -> EvidencePackage:
        """检索证据，返回 EvidencePackage."""
        ...


class PassthroughEvidenceRetriever:
    """透传检索器 - 直接消费上游预检索的 EvidencePackage.

    用于编译器早期集成与测试：调用方预先检索好证据，按 query_text 映射传入。
    无检索后端时不阻塞流水线。
    """

    def __init__(self, packages: Optional[dict[str, EvidencePackage]] = None):
        # query_text -> EvidencePackage
        self._packages = packages or {}

    def add_package(self, query_text: str, package: EvidencePackage) -> None:
        self._packages[query_text] = package

    def retrieve(self, query: RetrievalQuery, **kwargs: Any) -> EvidencePackage:
        package = self._packages.get(query.query_text)
        if package is None:
            logger.warning(
                "No pre-retrieved evidence for query, returning empty package",
                query=query.query_text,
            )
            return EvidencePackage(query=query)
        return package


class EvidenceRetriever:
    """证据检索器 - 编排多个 RetrievalQuery 的检索.

    第一阶段：委托注入的 EvidenceRetrieverProtocol 实现。
    """

    def __init__(self, backend: Optional[EvidenceRetrieverProtocol] = None):
        self._backend = backend or PassthroughEvidenceRetriever()

    def retrieve_evidence(
        self,
        queries: list[RetrievalQuery],
        **kwargs: Any,
    ) -> list[EvidencePackage]:
        """对一组检索查询执行检索.

        Args:
            queries: 来源规划器产出的检索查询列表

        Returns:
            每个 query 对应一个 EvidencePackage
        """
        packages: list[EvidencePackage] = []
        for query in queries:
            try:
                package = self._backend.retrieve(query, **kwargs)
                packages.append(package)
                logger.info(
                    "Evidence retrieved",
                    query=query.query_text,
                    docs=package.total_documents_found,
                    chunks=package.total_chunks_found,
                )
            except Exception as e:
                logger.error(
                    "Evidence retrieval failed, returning empty package",
                    query=query.query_text,
                    error=str(e),
                    exc_info=True,
                )
                packages.append(EvidencePackage(query=query))
        return packages


class AssertionRetriever:
    """断言检索器 - 从 assertion 表检索已结构化断言，包成 EvidencePackage.

    第二阶段"检索统一"：assertion 已是结构化事实，fact_extractor 可通过
    extract_from_assertions 直接复用，跳过 LLM 抽取。本检索器把每个 assertion
    包成一个 EvidenceChunk（content=predicate+object 文本，chunk_id=assertion_id），
    挂到按 source_doc_id 聚合的 EvidenceDocument，复用现有 EvidencePackage 结构。
    """

    def __init__(self, assertion_search: Any):
        # AssertionSearchService 实例
        self._search = assertion_search

    def retrieve(self, query: RetrievalQuery, **kwargs: Any) -> EvidencePackage:
        top_k = kwargs.get("top_k", query.max_results or 20)
        assertions: list[Assertion] = self._search.search(query.query_text, top_k=top_k)
        if not assertions:
            return EvidencePackage(query=query)

        # 按 source_doc_id 聚合成 documents
        docs_by_source: dict[str, EvidenceDocument] = {}
        total_chunks = 0
        for assertion in assertions:
            doc_id = assertion.source_doc_id or "unknown"
            doc = docs_by_source.get(doc_id)
            if doc is None:
                reliability = self._search.get_source_reliability(doc_id)
                doc = EvidenceDocument(
                    doc_id=doc_id,
                    title=doc_id,
                    source_type=SourceType.OTHER,
                    source_reliability=reliability,
                    citation_anchor=doc_id,
                )
                docs_by_source[doc_id] = doc
            chunk = self._assertion_to_chunk(assertion)
            doc.chunks.append(chunk)
            total_chunks += 1

        documents = list(docs_by_source.values())
        package = EvidencePackage(
            query=query,
            documents=documents,
            total_documents_found=len(documents),
            total_chunks_found=total_chunks,
        )
        logger.info(
            "Assertion retrieval completed",
            query=query.query_text,
            assertions=len(assertions),
            documents=len(documents),
        )
        return package

    @staticmethod
    def _assertion_to_chunk(assertion: Assertion) -> EvidenceChunk:
        """把 assertion 包成 EvidenceChunk，content 为可读的 predicate+object 文本."""
        object_text = ""
        if assertion.object_value:
            obj = assertion.object_value
            object_text = obj.get("text") or obj.get("value") or str(obj)
        content = f"{assertion.predicate}: {object_text}".strip(": ").strip()
        if not content:
            content = assertion.predicate or assertion.assertion_id
        # evidence_span 优先取 source_span.chunk_text
        span = assertion.source_span or {}
        if span.get("chunk_text"):
            content = str(span["chunk_text"])
        return EvidenceChunk(
            chunk_id=assertion.assertion_id,
            doc_id=assertion.source_doc_id or "unknown",
            content=content,
            chunk_index=(
                int(span.get("chunk_index", 0)) if span.get("chunk_index") is not None else 0
            ),
            relevance_score=float(assertion.confidence),
            quality_score=float(assertion.confidence),
            combined_score=float(assertion.confidence),
            evidence_type=EvidenceType.FACT,
        )
