"""
RAG 检索服务 - Issue #45.

提供完整的检索功能：
- 多种 Retrieval Profiles（日报、周报、月报、深度研究、回测）
- 时间衰减机制
- 结构化过滤（时间、来源、行业、主题、实体等）
- 混合搜索（向量 + 关键词）
- 证据包构建
- 报告与回测视角分离
"""
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.contracts.documents_v1 import (
    DocumentChunkV1,
    DocumentV1,
    SourceReliabilityLevel,
    SubjectivityLevel,
)
from core.contracts.retrieval import (
    EvidenceChunk,
    EvidenceDocument,
    EvidencePackage,
    EvidenceType,
    RetrievalFilters,
    RetrievalProfile,
    RetrievalQuery,
    get_profile,
)
from core.observability import get_logger
from knowledge_layer.retrieval.hybrid_search import HybridSearcher
from knowledge_layer.retrieval.vector_store import InMemoryVectorStore, VectorStore

logger = get_logger(__name__)


class RecencyDecayScorer:
    """
    时间衰减评分器 - Issue #45 要求.

    实现基于半衰期的时间衰减，确保较新的文档获得更高权重。
    """

    def __init__(self, half_life_days: float = 7.0, min_weight: float = 0.1):
        self.half_life_days = half_life_days
        self.min_weight = min_weight

    def score(
        self, doc_time: Optional[datetime], reference_time: Optional[datetime] = None
    ) -> float:
        """
        计算时间衰减分数.

        Args:
            doc_time: 文档时间（publish_time 或 available_time）
            reference_time: 参考时间（默认当前时间）

        Returns:
            float: 0.0-1.0 的分数
        """
        if doc_time is None:
            return 0.5

        if reference_time is None:
            reference_time = datetime.utcnow()

        days_ago = (reference_time - doc_time).total_seconds() / (24 * 60 * 60)

        if days_ago < 0:
            # 文档在未来（可能是时区问题），给满分
            return 1.0

        # 指数衰减公式
        decay_factor = math.pow(0.5, days_ago / self.half_life_days)

        # 确保不低于最小权重
        return max(self.min_weight, decay_factor)


class DocumentFilter:
    """
    文档过滤器 - 实现 Issue #45 要求的结构化过滤.
    """

    def filter_document(
        self,
        doc: DocumentV1,
        filters: RetrievalFilters,
        profile: Optional[RetrievalProfile] = None,
        reference_time: Optional[datetime] = None,
    ) -> bool:
        """
        判断文档是否通过过滤条件.

        Args:
            doc: 文档
            filters: 过滤条件
            profile: 检索 Profile
            reference_time: 参考时间

        Returns:
            bool: 是否通过过滤
        """
        if reference_time is None:
            reference_time = datetime.utcnow()

        # 时间过滤
        if not self._check_time_filters(doc, filters, profile, reference_time):
            return False

        # 来源过滤
        if not self._check_source_filters(doc, filters):
            return False

        # 分类过滤
        if not self._check_classification_filters(doc, filters):
            return False

        # 质量过滤
        if not self._check_quality_filters(doc, filters, profile):
            return False

        # 证据特征过滤
        if not self._check_evidence_filters(doc, filters):
            return False

        return True

    def _check_time_filters(
        self,
        doc: DocumentV1,
        filters: RetrievalFilters,
        profile: Optional[RetrievalProfile],
        reference_time: datetime,
    ) -> bool:
        """检查时间过滤条件"""
        # 使用 Profile 中的 available_time（回测用）
        use_available_time = profile.use_available_time if profile else False

        if use_available_time:
            # 回测模式：使用 available_time
            doc_time = doc.timeliness.available_time or doc.timeliness.publish_time
            if doc_time is None:
                return False

            # 检查回测截止时间
            if filters.available_time_before:
                if doc_time > filters.available_time_before:
                    return False

            if profile and profile.available_time_cutoff:
                if doc_time > profile.available_time_cutoff:
                    return False
        else:
            # 报告模式：使用 publish_time
            doc_time = doc.timeliness.publish_time or doc.timeliness.crawl_time

        # Profile 回看时间过滤
        if profile:
            lookback_days = profile.lookback_config.lookback_days.get(
                doc.doc_type, profile.lookback_config.default_lookback_days
            )
            cutoff_time = reference_time - timedelta(days=lookback_days)
            if doc_time and doc_time < cutoff_time:
                return False

        # 显式时间范围过滤
        if filters.publish_time_after:
            if (
                doc.timeliness.publish_time
                and doc.timeliness.publish_time < filters.publish_time_after
            ):
                return False

        if filters.publish_time_before:
            if (
                doc.timeliness.publish_time
                and doc.timeliness.publish_time > filters.publish_time_before
            ):
                return False

        return True

    def _check_source_filters(self, doc: DocumentV1, filters: RetrievalFilters) -> bool:
        """检查来源过滤条件"""
        if filters.doc_types:
            if doc.doc_type not in filters.doc_types:
                return False

        if filters.source_types:
            if doc.source_type not in filters.source_types:
                return False

        if filters.source_names:
            if doc.source_name not in filters.source_names:
                return False

        return True

    def _check_classification_filters(self, doc: DocumentV1, filters: RetrievalFilters) -> bool:
        """检查分类过滤条件"""
        if filters.primary_industries:
            if doc.classification.primary_industry not in filters.primary_industries:
                return False

        if filters.secondary_industries:
            has_any = any(
                ind in doc.classification.secondary_industries
                for ind in filters.secondary_industries
            )
            if not has_any:
                return False

        if filters.topics:
            has_any = any(topic in doc.classification.topics for topic in filters.topics)
            if not has_any:
                return False

        if filters.event_types:
            has_any = any(et in doc.classification.event_types for et in filters.event_types)
            if not has_any:
                return False

        return True

    def _check_quality_filters(
        self, doc: DocumentV1, filters: RetrievalFilters, profile: Optional[RetrievalProfile]
    ) -> bool:
        """检查质量过滤条件"""
        # Profile 中的最小研究可用性
        if profile and profile.min_research_usability > 0:
            usability = doc.quality.research_usability_score or 0.0
            if usability < profile.min_research_usability:
                return False

        # 显式最小研究可用性
        if filters.min_research_usability:
            usability = doc.quality.research_usability_score or 0.0
            if usability < filters.min_research_usability:
                return False

        # Profile 中的最小来源可信度
        if profile and profile.min_source_reliability:
            if not self._check_reliability_level(
                doc.quality.source_reliability_level, profile.min_source_reliability
            ):
                return False

        # 显式最小来源可信度
        if filters.min_source_reliability:
            if not self._check_reliability_level(
                doc.quality.source_reliability_level, filters.min_source_reliability
            ):
                return False

        # Profile 中的观点来源控制
        if profile and not profile.allow_opinion_sources:
            if not doc.quality.is_fact_source:
                return False

        # 仅事实来源
        if filters.only_fact_sources:
            if not doc.quality.is_fact_source:
                return False

        # 允许的主观性层级
        if filters.allowed_subjectivity:
            if doc.quality.subjectivity_level not in filters.allowed_subjectivity:
                return False

        # 最小证据质量
        if filters.min_evidence_quality:
            eq = doc.evidence_profile.evidence_quality_score or 0.0
            if eq < filters.min_evidence_quality:
                return False

        return True

    def _check_evidence_filters(self, doc: DocumentV1, filters: RetrievalFilters) -> bool:
        """检查证据特征过滤条件"""
        if filters.has_explicit_facts is not None:
            if doc.evidence_profile.has_explicit_facts != filters.has_explicit_facts:
                return False

        if filters.has_data_points is not None:
            if doc.evidence_profile.has_data_points != filters.has_data_points:
                return False

        if filters.has_quotes is not None:
            if doc.evidence_profile.has_quotes != filters.has_quotes:
                return False

        if filters.has_analysis is not None:
            if doc.evidence_profile.has_analysis != filters.has_analysis:
                return False

        return True

    def _check_reliability_level(
        self, doc_level: SourceReliabilityLevel, min_level: SourceReliabilityLevel
    ) -> bool:
        """检查来源可信度是否满足最小要求"""
        # 可信度排序
        level_order = [
            SourceReliabilityLevel.UNKNOWN,
            SourceReliabilityLevel.SOCIAL_MEDIA,
            SourceReliabilityLevel.OPINION_LEADER,
            SourceReliabilityLevel.SPECIALIZED_MEDIA,
            SourceReliabilityLevel.RESEARCH_INSTITUTE,
            SourceReliabilityLevel.ESTABLISHED_MEDIA,
            SourceReliabilityLevel.OFFICIAL,
        ]

        try:
            doc_index = level_order.index(doc_level)
            min_index = level_order.index(min_level)
            return doc_index >= min_index
        except ValueError:
            return False


class EvidencePackageBuilder:
    """
    证据包构建器 - Issue #45 要求.

    将检索到的文档和分块转换为 EvidencePackage，
    标注证据类型，添加引用锚点。
    """

    def __init__(self):
        self.doc_counter = 0

    def build(
        self,
        query: RetrievalQuery,
        documents: List[DocumentV1],
        chunks: Optional[List[DocumentChunkV1]] = None,
        profile: Optional[RetrievalProfile] = None,
    ) -> EvidencePackage:
        """构建证据包"""
        self.doc_counter = 0

        if chunks is None:
            chunks = []

        # 构建证据文档
        evidence_docs = []
        chunk_map = self._group_chunks_by_doc(chunks)

        for doc in documents:
            evidence_doc = self._build_evidence_doc(doc, chunk_map.get(doc.doc_id, []))
            evidence_docs.append(evidence_doc)

        # 计算分布
        source_dist = self._calculate_source_distribution(evidence_docs)
        industry_dist = self._calculate_industry_distribution(evidence_docs)

        # 构建过滤摘要
        filters_applied = self._build_filters_summary(query.filters, profile)

        return EvidencePackage(
            query=query,
            profile_used=profile,
            total_documents_found=len(documents),
            total_chunks_found=len(chunks),
            retrieved_at=datetime.utcnow(),
            documents=evidence_docs,
            filters_applied=filters_applied,
            source_distribution=source_dist,
            industry_distribution=industry_dist,
        )

    def _build_evidence_doc(
        self, doc: DocumentV1, chunks: List[DocumentChunkV1]
    ) -> EvidenceDocument:
        """构建单个证据文档"""
        self.doc_counter += 1

        # 确定证据类型
        evidence_type = self._determine_evidence_type(doc)

        # 构建分块
        evidence_chunks = [self._build_evidence_chunk(chunk, evidence_type) for chunk in chunks]

        return EvidenceDocument(
            doc_id=doc.doc_id,
            title=doc.title,
            summary=doc.summary,
            source_type=doc.source_type,
            source_name=doc.source_name,
            source_url=doc.source_url,
            publish_time=doc.timeliness.publish_time,
            available_time=doc.timeliness.available_time,
            primary_industry=doc.classification.primary_industry,
            topics=doc.classification.topics,
            event_types=doc.classification.event_types,
            source_reliability=doc.quality.source_reliability_level,
            subjectivity=doc.quality.subjectivity_level,
            evidence_quality=doc.evidence_profile.evidence_quality_score or 0.0,
            chunks=evidence_chunks,
            citation_anchor=f"[{self.doc_counter}] {doc.source_name or 'Unknown'}",
        )

    def _build_evidence_chunk(
        self, chunk: DocumentChunkV1, default_evidence_type: EvidenceType
    ) -> EvidenceChunk:
        """构建单个证据分块"""
        return EvidenceChunk(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            content=chunk.content,
            title=chunk.title,
            chunk_index=chunk.chunk_index,
            relevance_score=0.5,
            recency_score=0.5,
            quality_score=0.5,
            combined_score=0.5,
            evidence_type=default_evidence_type,
            topics=chunk.topics,
            entities=chunk.entities,
        )

    def _determine_evidence_type(self, doc: DocumentV1) -> EvidenceType:
        """确定文档的证据类型"""
        profile = doc.evidence_profile

        # 检查是否有数据
        if profile.has_data_points:
            return EvidenceType.DATA

        # 检查是否有引述
        if profile.has_quotes:
            return EvidenceType.QUOTE

        # 检查是否有分析
        if profile.has_analysis:
            return EvidenceType.ANALYSIS

        # 检查事实/观点
        if doc.quality.is_fact_source:
            return EvidenceType.FACT

        subjectivity = doc.quality.subjectivity_level
        if (
            subjectivity == SubjectivityLevel.FACT_ONLY
            or subjectivity == SubjectivityLevel.FACT_HEAVY
        ):
            return EvidenceType.FACT

        if (
            subjectivity == SubjectivityLevel.OPINION_ONLY
            or subjectivity == SubjectivityLevel.OPINION_HEAVY
        ):
            return EvidenceType.OPINION

        return EvidenceType.MIXED

    def _group_chunks_by_doc(
        self, chunks: List[DocumentChunkV1]
    ) -> Dict[str, List[DocumentChunkV1]]:
        """按文档分组分块"""
        chunk_map: Dict[str, List[DocumentChunkV1]] = {}
        for chunk in chunks:
            if chunk.doc_id not in chunk_map:
                chunk_map[chunk.doc_id] = []
            chunk_map[chunk.doc_id].append(chunk)

        # 按索引排序
        for doc_id in chunk_map:
            chunk_map[doc_id].sort(key=lambda c: c.chunk_index)

        return chunk_map

    def _calculate_source_distribution(self, docs: List[EvidenceDocument]) -> Dict[str, int]:
        """计算来源分布"""
        dist: Dict[str, int] = {}
        for doc in docs:
            source = doc.source_type.value if doc.source_type else "unknown"
            dist[source] = dist.get(source, 0) + 1
        return dist

    def _calculate_industry_distribution(self, docs: List[EvidenceDocument]) -> Dict[str, int]:
        """计算行业分布"""
        dist: Dict[str, int] = {}
        for doc in docs:
            industry = doc.primary_industry or "unknown"
            dist[industry] = dist.get(industry, 0) + 1
        return dist

    def _build_filters_summary(
        self, filters: Optional[RetrievalFilters], profile: Optional[RetrievalProfile]
    ) -> Optional[Dict[str, Any]]:
        """构建过滤条件摘要"""
        summary: Dict[str, Any] = {}

        if profile:
            summary["profile_type"] = profile.profile_type.value
            summary["max_documents"] = profile.max_documents
            summary["max_chunks"] = profile.max_chunks

        if filters:
            filter_dict = filters.model_dump(exclude_none=True)
            if filter_dict:
                summary["filters"] = filter_dict

        return summary if summary else None


class RAGRetrievalService:
    """
    RAG 检索服务 - Issue #45 主类.

    整合 Profile、过滤、搜索、评分、证据包构建功能。
    实现三层检索架构：过滤 → 召回 → 重排。
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        hybrid_searcher: Optional[HybridSearcher] = None,
        reranker: Optional[Any] = None,  # 可插拔重排器
    ):
        self.vector_store = vector_store or InMemoryVectorStore()
        self.hybrid_searcher = hybrid_searcher or HybridSearcher(vector_store=self.vector_store)
        self.filter = DocumentFilter()
        self.evidence_builder = EvidencePackageBuilder()
        self.reranker = reranker  # 重排器，支持自定义实现

        # 内存文档存储（实际项目中应使用数据库）
        self._docs: Dict[str, DocumentV1] = {}
        self._chunks: Dict[str, DocumentChunkV1] = {}

    def index_document(self, doc: DocumentV1, chunks: Optional[List[DocumentChunkV1]] = None):
        """索引文档"""
        self._docs[doc.doc_id] = doc

        # 添加到向量存储
        self.vector_store.add_document(
            doc_id=doc.doc_id,
            text=doc.content,
            metadata={"title": doc.title, "source_type": doc.source_type.value},
        )

        # 索引分块
        if chunks:
            for chunk in chunks:
                self._chunks[chunk.chunk_id] = chunk
                self.vector_store.add_document(
                    doc_id=chunk.chunk_id,
                    text=chunk.content,
                    metadata={"doc_id": doc.doc_id, "chunk_index": chunk.chunk_index},
                )

        logger.info(f"Indexed document: {doc.doc_id}")

    def retrieve(
        self, query: RetrievalQuery, reference_time: Optional[datetime] = None
    ) -> EvidencePackage:
        """
        执行检索 - 主入口.
        实现三层架构：过滤 → 召回 → 重排。

        Args:
            query: 检索查询
            reference_time: 参考时间（用于时间衰减和回测）

        Returns:
            EvidencePackage: 证据包
        """
        if reference_time is None:
            reference_time = datetime.utcnow()

        logger.info(f"Starting retrieval: {query.query_text[:50]}...")

        # 获取 Profile
        profile = None
        if query.profile_type:
            profile = get_profile(
                query.profile_type,
                available_time_cutoff=query.filters.available_time_before
                if query.filters
                else None,
            )

        filters = query.filters or RetrievalFilters()

        # =====================================================================
        # 第一层：结构化过滤（Filtering）
        # 按照时间、来源、行业、质量等条件缩小候选集范围
        # =====================================================================
        filtered_docs = self._filter_documents(filters, profile, reference_time)
        logger.info(f"Filtered to {len(filtered_docs)} docs after structured filtering")

        if not filtered_docs:
            # 没有匹配的文档，直接返回空包
            return self.evidence_builder.build(
                query=query, documents=[], chunks=[], profile=profile
            )

        # =====================================================================
        # 第二层：召回（Retrieval）
        # 对过滤后的文档进行混合召回（向量 + 关键词），得到初始候选集
        # =====================================================================
        recalled_docs = self._retrieve_candidates(
            docs=filtered_docs,
            query_text=query.query_text,
            profile=profile,
        )
        logger.info(f"Recalled {len(recalled_docs)} docs after hybrid retrieval")

        # 限制召回阶段返回数量，为了减少重排计算量
        max_recall_docs = min(len(recalled_docs), 2 * (profile.max_documents if profile else 100))
        recalled_docs = recalled_docs[:max_recall_docs]

        # =====================================================================
        # 第三层：重排（Reranking）
        # 对召回的文档进行精排，综合考虑相关性、时效性、质量、来源权重等
        # =====================================================================
        reranked_docs = self._rerank_candidates(
            docs=recalled_docs,
            query_text=query.query_text,
            profile=profile,
            reference_time=reference_time,
        )
        logger.info(f"Reranked to {len(reranked_docs)} docs after reranking")

        # 限制最终数量
        max_docs = profile.max_documents if profile else query.max_results
        selected_docs = reranked_docs[:max_docs]

        # 获取分块
        selected_chunks = []
        if query.include_chunks:
            for doc in selected_docs:
                doc_chunks = [c for c in self._chunks.values() if c.doc_id == doc.doc_id]
                selected_chunks.extend(doc_chunks)

        # 构建证据包
        evidence_package = self.evidence_builder.build(
            query=query, documents=selected_docs, chunks=selected_chunks, profile=profile
        )

        logger.info(f"Retrieval complete: {len(selected_docs)} docs, {len(selected_chunks)} chunks")

        return evidence_package

    def _filter_documents(
        self,
        filters: RetrievalFilters,
        profile: Optional[RetrievalProfile],
        reference_time: datetime,
    ) -> List[DocumentV1]:
        """过滤文档"""
        filtered = []
        for doc in self._docs.values():
            if self.filter.filter_document(doc, filters, profile, reference_time):
                filtered.append(doc)
        return filtered

    def _rerank_candidates(
        self,
        docs: List[DocumentV1],
        query_text: str,
        profile: Optional[RetrievalProfile],
        reference_time: datetime,
    ) -> List[DocumentV1]:
        """
        第三层：重排阶段，精排候选文档.

        综合考虑：
        1. 搜索相关性（来自召回阶段）
        2. 时间衰减
        3. 来源权重
        4. 文档质量
        5. （可选）外部Reranker模型评分

        Args:
            docs: 召回的候选文档
            query_text: 查询文本
            profile: 检索配置
            reference_time: 参考时间

        Returns:
            重排后的文档列表
        """
        if not docs:
            return []

        # 创建时间衰减评分器
        decay_config = profile.recency_decay if profile else None
        scorer = RecencyDecayScorer(
            half_life_days=decay_config.half_life_days if decay_config else 7.0,
            min_weight=decay_config.min_score_weight if decay_config else 0.1,
        )

        # 首先尝试使用外部Reranker（如果配置了）
        if self.reranker:
            try:
                return self._rerank_with_external_model(docs, query_text)
            except Exception as e:
                logger.warning(f"External reranker failed, falling back to default scoring: {e}")

        # 默认的综合评分逻辑
        scored_pairs = []
        for doc in docs:
            # 1. 搜索相关性分数（来自召回阶段）
            search_score = getattr(doc, "_search_score", 0.5)

            # 2. 时间衰减分数
            use_available = profile.use_available_time if profile else False
            doc_time = None
            if use_available:
                doc_time = doc.timeliness.available_time or doc.timeliness.publish_time
            else:
                doc_time = doc.timeliness.publish_time or doc.timeliness.crawl_time

            recency_score = scorer.score(doc_time, reference_time)

            # 3. 来源权重
            source_weight = 1.0
            if profile and doc.source_type in profile.source_weights.weights:
                source_weight = profile.source_weights.weights[doc.source_type]

            # 4. 文档质量评分
            quality_score = doc.quality.research_usability_score or 0.5

            # 5. 综合评分（权重可配置）
            weights = {
                "search": 0.4,
                "recency": 0.3,
                "quality": 0.2,
                "source": 0.1,
            }

            combined_score = (
                search_score * weights["search"]
                + recency_score * weights["recency"]
                + quality_score * weights["quality"]
                + source_weight * weights["source"]
            )

            # 存储分数到文档对象，方便后续追踪
            doc._combined_score = combined_score

            scored_pairs.append((doc, combined_score))

        # 按综合分数降序排序
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored_pairs]

    def _rerank_with_external_model(
        self, docs: List[DocumentV1], query_text: str
    ) -> List[DocumentV1]:
        """
        使用外部Reranker模型进行重排（示例实现）.

        实际项目中可以接入如：
        - Cohere Reranker
        - BGE Reranker
        - 自定义重排模型
        """
        if not self.reranker:
            return docs

        # 准备文档文本列表
        doc_texts = [f"{doc.title} {doc.content[:1000]}" for doc in docs]

        # 调用重排器
        scores = self.reranker.rerank(query_text, doc_texts)

        # 组合文档和分数并排序
        scored_pairs = list(zip(docs, scores))
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored_pairs]

    def _retrieve_candidates(
        self,
        docs: List[DocumentV1],
        query_text: str,
        profile: Optional[RetrievalProfile],
    ) -> List[DocumentV1]:
        """
        第二层：召回阶段，混合向量+关键词搜索.

        Args:
            docs: 过滤后的文档列表
            query_text: 查询文本
            profile: 检索配置

        Returns:
            召回的候选文档列表
        """
        if not docs:
            return []

        doc_id_map = {doc.doc_id: doc for doc in docs}

        # 获取搜索权重配置
        vector_weight = profile.vector_weight if profile else 0.7
        keyword_weight = profile.keyword_weight if profile else 0.3

        # 执行混合搜索
        search_results = self.hybrid_searcher.search(
            query_text=query_text,
            document_ids=list(doc_id_map.keys()),
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
            limit=200,  # 召回阶段返回较多候选
        )

        # 转换为文档列表，保持搜索排序
        recalled_docs = []
        for result in search_results:
            doc = doc_id_map.get(result["doc_id"])
            if doc:
                # 存储搜索分数到文档对象（临时属性）
                doc._search_score = result["score"]
                recalled_docs.append(doc)

        # 如果混合搜索没有返回结果，使用简单关键词匹配作为 fallback
        if not recalled_docs:
            keyword_scores = self._calculate_keyword_scores(docs, query_text)
            scored_docs = sorted(docs, key=lambda d: keyword_scores.get(d.doc_id, 0), reverse=True)
            for doc in scored_docs:
                doc._search_score = keyword_scores.get(doc.doc_id, 0.0)
            recalled_docs = scored_docs

        return recalled_docs

    def _calculate_keyword_scores(
        self, docs: List[DocumentV1], query_text: str
    ) -> Dict[str, float]:
        """
        计算关键词匹配分数（fallback实现）.
        """
        scores: Dict[str, float] = {}
        query_lower = query_text.lower()
        query_words = set(query_lower.split())

        for doc in docs:
            doc_text = (doc.title + " " + doc.content).lower()

            # 简单关键词匹配
            match_count = sum(1 for word in query_words if word in doc_text)
            score = min(1.0, match_count / max(1, len(query_words)))

            scores[doc.doc_id] = score

        return scores
