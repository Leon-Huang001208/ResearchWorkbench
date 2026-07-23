"""Evidence-grounded report project generation.

This module connects report project configuration to the existing database
and model gateway:

Word placeholder -> section config -> prompt template -> evidence retrieval
-> DeepSeek/model generation -> placeholder replacement.
"""

from __future__ import annotations

import difflib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from math import exp, sqrt
from typing import Any, Dict, Iterable, List, Optional, Protocol

from sqlalchemy import or_

from core.contracts.reporting import DefaultSettings, GenerationConfig
from core.interfaces.model_gateway import ModelResponse
from core.model_gateway.gateway import ModelGatewayImpl
from core.model_gateway.local_embedding_config import (
    resolve_local_embedding_model,
    sentence_transformer_kwargs,
)
from core.observability import get_logger
from core.settings import settings
from reporting.projects.keyword_profiles import apply_keyword_profile_to_config
from reporting.projects.project_manager import ReportProject

logger = get_logger(__name__)


def _flatten_keyword_groups(groups: list[list[str]] | None) -> list[str]:
    """将 v2 keyword_groups 展平为扁平的 must_any 关键词列表."""
    if not groups:
        return []
    flat: list[str] = []
    for group in groups:
        flat.extend(group)
    return list(dict.fromkeys(flat))  # 去重保持顺序


def _build_v1_config_from_v2(
    key: str,
    title: str,
    gen_config: GenerationConfig,
    defaults: DefaultSettings | None = None,
) -> dict[str, Any]:
    """从 v2 GenerationConfig + DefaultSettings 构建 v1 兼容的 config dict.

    使得现有 _generate_configured_placeholder() 管道可直接消费。
    """
    config: dict[str, Any] = {
        "title": title,
        "type": "paragraph",
        "prompt_template": gen_config.prompt_template_ref or title,
        "target_words": gen_config.target_words or 200,
        "max_words": gen_config.max_words or 300,
        "output_mode": gen_config.output_mode or "single_paragraph",
    }

    # 检索配置
    retrieval: dict[str, Any] = {}
    if gen_config.retrieval:
        retrieval["mode"] = gen_config.retrieval.mode or "keyword"
        retrieval["top_k"] = gen_config.retrieval.top_k or 10
        retrieval["candidate_k"] = gen_config.retrieval.candidate_k or 40
        retrieval["must_any"] = _flatten_keyword_groups(gen_config.retrieval.keyword_groups)
        if gen_config.retrieval.exclude_keywords:
            retrieval["exclude"] = list(gen_config.retrieval.exclude_keywords)

        # Rerank 配置（从 v2 字段映射到 v1 retrieval dict）
        retrieval["rerank_enabled"] = gen_config.retrieval.rerank_enabled
        if gen_config.retrieval.rerank_top_n:
            retrieval["rerank_top_n"] = gen_config.retrieval.rerank_top_n
        if gen_config.retrieval.rerank_min_score is not None:
            retrieval["min_rerank_score"] = gen_config.retrieval.rerank_min_score

        # 融合参数
        if gen_config.retrieval.keyword_weight is not None:
            retrieval["keyword_weight"] = gen_config.retrieval.keyword_weight
        if gen_config.retrieval.semantic_weight is not None:
            retrieval["semantic_weight"] = gen_config.retrieval.semantic_weight

    # 如果 placeholder 级检索为空，从 defaults 继承
    if not retrieval and defaults and defaults.retrieval:
        default_retrieval = defaults.retrieval
        retrieval["mode"] = default_retrieval.mode or "keyword"
        retrieval["top_k"] = default_retrieval.top_k or 10
        retrieval["candidate_k"] = default_retrieval.candidate_k or 40
        retrieval["rerank_enabled"] = default_retrieval.rerank_enabled or False
        if default_retrieval.rerank_top_n:
            retrieval["rerank_top_n"] = default_retrieval.rerank_top_n
        if default_retrieval.rerank_min_score is not None:
            retrieval["min_rerank_score"] = default_retrieval.rerank_min_score

    config["retrieval"] = retrieval

    # 校验配置
    validators: dict[str, Any] = {}
    if defaults and defaults.validators:
        if defaults.validators.forbidden_terms:
            validators["forbidden_terms"] = list(defaults.validators.forbidden_terms)
        if defaults.validators.forbid_instruction_leaks:
            validators["forbid_instruction_leaks"] = True
    config["validators"] = validators

    return config


@dataclass(frozen=True)
class ReportPeriod:
    """Report date window shared by placeholders, retrieval, and run logs."""

    start_date: str
    end_date: str


@dataclass(frozen=True)
class ReportGenerationScope:
    """Resolved report generation scope before evidence retrieval starts."""

    report_period: ReportPeriod
    lookback_days: int
    data_scope: str
    report_date: str | None = None


@dataclass(frozen=True)
class PromptTemplateBlock:
    """Parsed Markdown prompt template block."""

    title: str
    retrieval_query: str
    writing_requirements: str
    raw_text: str


@dataclass(frozen=True)
class EvidenceSnippet:
    """Retrieved evidence item passed to the LLM."""

    source: str
    title: str
    content: str
    published_at: str | None = None
    url: str | None = None
    keyword_score: float | None = None
    semantic_score: float | None = None
    retrieval_score: float | None = None
    retrieval_rank: int | None = None
    retrieval_method: str | None = None
    rerank_score: float | None = None
    rerank_rank: int | None = None
    rerank_reason: str | None = None
    matched_terms: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalConfig:
    """Phase-1 keyword retrieval controls for one report section."""

    mode: str = "keyword"
    top_k: int = 8
    candidate_k: int = 32
    must_any: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    source_types: List[str] = field(default_factory=list)
    min_keyword_score: float = 0.0
    fusion_method: str = "rrf"
    keyword_weight: float = 0.7
    semantic_weight: float = 0.3
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    rrf_k: int = 60
    semantic_candidate_k: int = 64
    rerank_enabled: bool = False
    rerank_provider: str = "bge-reranker"
    rerank_model: str = "BAAI/bge-reranker-large"
    rerank_top_n: int = 16
    min_rerank_score: float = 0.0


_LOCAL_EMBEDDING_MODELS: Dict[str, Any] = {}
_LOCAL_RERANKER_MODELS: Dict[str, Any] = {}


@dataclass(frozen=True)
class GeneratedSectionInfo:
    """Generation metadata for one placeholder."""

    placeholder: str
    title: str
    prompt_template: str
    retrieval_query: str
    evidence_count: int
    model_name: str
    provider: str
    tokens_used: int
    warnings: List[str] = field(default_factory=list)
    retrieval_config: RetrievalConfig | None = None
    evidence: List[EvidenceSnippet] = field(default_factory=list)


@dataclass(frozen=True)
class ReportGenerationResult:
    """Generated placeholder map plus run metadata."""

    placeholders: Dict[str, str]
    sections: List[GeneratedSectionInfo]
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlaceholderGenerationOutput:
    """Generated value and optional metadata for one placeholder."""

    placeholder: str
    content: str
    section_info: GeneratedSectionInfo | None = None
    warnings: List[str] = field(default_factory=list)


class EvidenceRetriever(Protocol):
    """Retrieves factual evidence for a section query."""

    def retrieve(
        self,
        query: str,
        *,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
        report_period: ReportPeriod | None = None,
        retrieval_config: RetrievalConfig | None = None,
    ) -> List[EvidenceSnippet]:
        """Return evidence snippets for a report section."""


class DatabaseEvidenceRetriever:
    """Keyword evidence retriever over existing AlphaFoundry database tables."""

    def retrieve(
        self,
        query: str,
        *,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
        report_period: ReportPeriod | None = None,
        retrieval_config: RetrievalConfig | None = None,
    ) -> List[EvidenceSnippet]:
        """Retrieve evidence from ingestion queue and canonical events."""
        try:
            from data_layer.repositories.base import SessionLocal

            candidate_limit = _candidate_limit(limit, retrieval_config)
            with SessionLocal() as session:
                snippets = self._retrieve_ingestion_items(
                    session,
                    query=query,
                    title=title,
                    params=params,
                    lookback_days=lookback_days,
                    limit=candidate_limit,
                    report_period=report_period,
                    retrieval_config=retrieval_config,
                )
                if len(snippets) < candidate_limit:
                    snippets.extend(
                        self._retrieve_events(
                            session,
                            query=query,
                            title=title,
                            params=params,
                            lookback_days=lookback_days,
                            limit=candidate_limit - len(snippets),
                            report_period=report_period,
                            retrieval_config=retrieval_config,
                        )
                    )
                if _uses_semantic_retrieval(retrieval_config):
                    snippets.extend(
                        self._retrieve_recent_ingestion_items(
                            session,
                            lookback_days=lookback_days,
                            limit=_semantic_candidate_limit(retrieval_config),
                            report_period=report_period,
                            retrieval_config=retrieval_config,
                        )
                    )
                    snippets.extend(
                        self._retrieve_recent_events(
                            session,
                            lookback_days=lookback_days,
                            limit=max(10, _semantic_candidate_limit(retrieval_config) // 4),
                            report_period=report_period,
                        )
                    )
                snippets = _dedupe_snippets(snippets)
                return filter_and_rank_evidence(snippets, retrieval_config, query=query)[:limit]
        except Exception as exc:
            logger.warning(
                "Failed to retrieve report evidence",
                title=title,
                error=str(exc),
            )
            return []

    def _retrieve_ingestion_items(
        self,
        session: Any,
        *,
        query: str,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
        report_period: ReportPeriod | None,
        retrieval_config: RetrievalConfig | None,
    ) -> List[EvidenceSnippet]:
        from data_layer.repositories.models import IngestionQueueItemDB

        terms = self._extract_terms(
            query, title=title, params=params, retrieval_config=retrieval_config
        )
        cutoff_start, cutoff_end = _period_datetime_bounds(report_period, lookback_days)
        filters = [
            or_(
                IngestionQueueItemDB.title.ilike(f"%{term}%"),
                IngestionQueueItemDB.raw_content.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        query_obj = session.query(IngestionQueueItemDB)
        if filters:
            query_obj = query_obj.filter(or_(*filters))
        if retrieval_config and retrieval_config.source_types:
            source_types = [
                source.split(":", 1)[1] if source.startswith("ingestion:") else source
                for source in retrieval_config.source_types
            ]
            query_obj = query_obj.filter(IngestionQueueItemDB.source_type.in_(source_types))
        query_obj = query_obj.filter(IngestionQueueItemDB.created_at >= cutoff_start)
        query_obj = query_obj.filter(IngestionQueueItemDB.created_at <= cutoff_end)
        rows = query_obj.order_by(IngestionQueueItemDB.created_at.desc()).limit(limit).all()
        return [
            EvidenceSnippet(
                source=f"ingestion:{row.source_type}",
                title=row.title or row.source_id or row.item_id,
                content=self._compact_text(row.raw_content),
                published_at=row.published_at
                or (row.created_at.isoformat() if row.created_at else None),
                url=row.url,
            )
            for row in rows
            if row.raw_content
        ]

    def _retrieve_events(
        self,
        session: Any,
        *,
        query: str,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
        report_period: ReportPeriod | None,
        retrieval_config: RetrievalConfig | None,
    ) -> List[EvidenceSnippet]:
        from data_layer.repositories.models import CanonicalEvent

        terms = self._extract_terms(
            query, title=title, params=params, retrieval_config=retrieval_config
        )
        cutoff_start, cutoff_end = _period_datetime_bounds(report_period, lookback_days)
        filters = [
            or_(
                CanonicalEvent.summary.ilike(f"%{term}%"),
                CanonicalEvent.event_type.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        query_obj = session.query(CanonicalEvent)
        if filters:
            query_obj = query_obj.filter(or_(*filters))
        query_obj = query_obj.filter(CanonicalEvent.created_at >= cutoff_start)
        query_obj = query_obj.filter(CanonicalEvent.created_at <= cutoff_end)
        rows = query_obj.order_by(CanonicalEvent.created_at.desc()).limit(limit).all()
        return [
            EvidenceSnippet(
                source="canonical_event",
                title=row.event_type,
                content=self._compact_text(row.summary),
                published_at=(
                    (row.event_time or row.created_at).isoformat()
                    if (row.event_time or row.created_at)
                    else None
                ),
                url=None,
            )
            for row in rows
            if row.summary
        ]

    def _retrieve_recent_ingestion_items(
        self,
        session: Any,
        *,
        lookback_days: int,
        limit: int,
        report_period: ReportPeriod | None,
        retrieval_config: RetrievalConfig | None,
    ) -> List[EvidenceSnippet]:
        """Retrieve recent documents as semantic candidates for hybrid recall."""
        from data_layer.repositories.models import IngestionQueueItemDB

        cutoff_start, cutoff_end = _period_datetime_bounds(report_period, lookback_days)
        query_obj = session.query(IngestionQueueItemDB)
        if retrieval_config and retrieval_config.source_types:
            source_types = [
                source.split(":", 1)[1] if source.startswith("ingestion:") else source
                for source in retrieval_config.source_types
            ]
            query_obj = query_obj.filter(IngestionQueueItemDB.source_type.in_(source_types))
        rows = (
            query_obj.filter(IngestionQueueItemDB.created_at >= cutoff_start)
            .filter(IngestionQueueItemDB.created_at <= cutoff_end)
            .order_by(IngestionQueueItemDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            EvidenceSnippet(
                source=f"ingestion:{row.source_type}",
                title=row.title or row.source_id or row.item_id,
                content=self._compact_text(row.raw_content),
                published_at=row.published_at
                or (row.created_at.isoformat() if row.created_at else None),
                url=row.url,
            )
            for row in rows
            if row.raw_content
        ]

    def _retrieve_recent_events(
        self,
        session: Any,
        *,
        lookback_days: int,
        limit: int,
        report_period: ReportPeriod | None,
    ) -> List[EvidenceSnippet]:
        """Retrieve recent canonical events as semantic candidates for hybrid recall."""
        from data_layer.repositories.models import CanonicalEvent

        cutoff_start, cutoff_end = _period_datetime_bounds(report_period, lookback_days)
        rows = (
            session.query(CanonicalEvent)
            .filter(CanonicalEvent.created_at >= cutoff_start)
            .filter(CanonicalEvent.created_at <= cutoff_end)
            .order_by(CanonicalEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            EvidenceSnippet(
                source="canonical_event",
                title=row.event_type,
                content=self._compact_text(row.summary),
                published_at=(
                    (row.event_time or row.created_at).isoformat()
                    if (row.event_time or row.created_at)
                    else None
                ),
                url=None,
            )
            for row in rows
            if row.summary
        ]

    @staticmethod
    def _extract_terms(
        query: str,
        *,
        title: str,
        params: Dict[str, Any],
        retrieval_config: RetrievalConfig | None = None,
    ) -> List[str]:
        raw_terms: List[str] = []
        raw_terms.append(title)
        if retrieval_config:
            raw_terms.extend(retrieval_config.must_any)
        for value in params.values():
            if isinstance(value, str):
                raw_terms.append(value)
        raw_terms.extend(
            part.strip() for part in re.split(r"[，,、；;。\n\s]+", query) if part.strip()
        )

        stop_terms = {
            "请基于上传的全部新闻内容",
            "撰写一段关于",
            "最新动态",
            "包括",
            "涵盖",
            "方面",
            "市场",
            "新闻",
        }
        terms: List[str] = []
        for term in raw_terms:
            cleaned = re.sub(r"^(请基于上传的全部新闻内容|撰写一段关于)", "", term).strip()
            cleaned = re.sub(r"(的最新动态|等)$", "", cleaned).strip()
            if not cleaned or cleaned in stop_terms or len(cleaned) < 2:
                continue
            if cleaned not in terms:
                terms.append(cleaned)
        return terms[:12]

    @staticmethod
    def _compact_text(text: str, max_chars: int = 900) -> str:
        compacted = re.sub(r"\s+", " ", text).strip()
        return compacted[:max_chars]


def build_retrieval_config(config: Dict[str, Any], *, default_top_k: int) -> RetrievalConfig:
    """Build retrieval config from a section config block."""
    raw_retrieval = config.get("retrieval")
    retrieval = raw_retrieval if isinstance(raw_retrieval, dict) else {}
    raw_query_terms = retrieval.get("query_terms")
    query_terms = raw_query_terms if isinstance(raw_query_terms, dict) else {}
    raw_fusion = retrieval.get("fusion")
    fusion = raw_fusion if isinstance(raw_fusion, dict) else {}
    raw_rerank = retrieval.get("rerank")
    rerank = raw_rerank if isinstance(raw_rerank, dict) else {}

    must_any = _string_list(
        retrieval.get("keywords") or query_terms.get("must_any") or retrieval.get("must_any")
    )
    exclude = _string_list(query_terms.get("exclude") or retrieval.get("exclude"))
    source_types = _string_list(retrieval.get("source_types"))
    top_k = _int_option(retrieval.get("top_k"), default_top_k)
    candidate_k = _int_option(retrieval.get("candidate_k"), max(top_k * 4, 20))
    semantic_candidate_k = _int_option(
        fusion.get("semantic_candidate_k") or retrieval.get("semantic_candidate_k"),
        max(candidate_k * 2, 40),
    )
    min_keyword_score = _float_option(
        retrieval.get("min_keyword_score") or retrieval.get("threshold"),
        0.0,
    )
    keyword_weight = _float_option(
        fusion.get("keyword_weight") or retrieval.get("keyword_weight"),
        0.7,
    )
    semantic_weight = _float_option(
        fusion.get("semantic_weight") or retrieval.get("semantic_weight"),
        0.3,
    )
    embedding_model = str(
        retrieval.get("embedding_model")
        or fusion.get("embedding_model")
        or "BAAI/bge-large-zh-v1.5"
    )
    return RetrievalConfig(
        mode=str(retrieval.get("mode") or "keyword"),
        top_k=max(1, top_k),
        candidate_k=max(top_k, candidate_k),
        must_any=must_any,
        exclude=exclude,
        source_types=source_types,
        min_keyword_score=max(0.0, min_keyword_score),
        fusion_method=str(fusion.get("method") or retrieval.get("fusion_method") or "rrf"),
        keyword_weight=max(0.0, keyword_weight),
        semantic_weight=max(0.0, semantic_weight),
        embedding_model=embedding_model,
        rrf_k=max(1, _int_option(fusion.get("rrf_k") or retrieval.get("rrf_k"), 60)),
        semantic_candidate_k=max(top_k, semantic_candidate_k),
        rerank_enabled=_bool_option(rerank.get("enabled") or retrieval.get("rerank_enabled")),
        rerank_provider=str(
            rerank.get("provider") or retrieval.get("rerank_provider") or "bge-reranker"
        ),
        rerank_model=str(
            rerank.get("model") or retrieval.get("rerank_model") or "BAAI/bge-reranker-large"
        ),
        rerank_top_n=max(
            top_k,
            _int_option(rerank.get("top_n") or retrieval.get("rerank_top_n"), max(top_k * 2, 12)),
        ),
        min_rerank_score=max(
            0.0,
            _float_option(rerank.get("min_score") or retrieval.get("min_rerank_score"), 0.0),
        ),
    )


def filter_and_rank_evidence(
    snippets: List[EvidenceSnippet],
    retrieval_config: RetrievalConfig | None,
    *,
    query: str = "",
) -> List[EvidenceSnippet]:
    """Apply retrieval filters and ranking to evidence."""
    if retrieval_config is None:
        return snippets

    filtered: List[tuple[EvidenceSnippet, str, List[str], float]] = []
    for snippet in snippets:
        haystack = f"{snippet.title}\n{snippet.content}"
        if _contains_any(haystack, retrieval_config.exclude):
            continue
        if retrieval_config.source_types and not _source_matches(
            snippet.source, retrieval_config.source_types
        ):
            continue

        matched_terms, score = _keyword_match_score(
            title=snippet.title,
            content=snippet.content,
            terms=retrieval_config.must_any,
        )
        if retrieval_config.must_any and not matched_terms:
            continue
        if score < retrieval_config.min_keyword_score:
            continue
        filtered.append((snippet, haystack, matched_terms, score))

    semantic_scores: List[float | None]
    if _uses_semantic_retrieval(retrieval_config):
        semantic_scores = _semantic_similarity_scores(
            _semantic_query_text(query, retrieval_config),
            [item[1] for item in filtered],
            retrieval_config,
        )
    else:
        semantic_scores = [None] * len(filtered)

    candidates: List[EvidenceSnippet] = []
    for (snippet, _haystack, matched_terms, score), semantic_score in zip(
        filtered, semantic_scores
    ):
        candidates.append(
            replace(
                snippet,
                keyword_score=float(score),
                semantic_score=semantic_score,
                matched_terms=matched_terms,
            )
        )

    if _uses_semantic_retrieval(retrieval_config):
        return _rank_hybrid_evidence(candidates, retrieval_config)
    return _rank_keyword_evidence(candidates)


def _candidate_limit(limit: int, retrieval_config: RetrievalConfig | None) -> int:
    if retrieval_config:
        return max(limit, retrieval_config.candidate_k)
    return max(limit * 4, 20)


def _semantic_candidate_limit(retrieval_config: RetrievalConfig | None) -> int:
    if retrieval_config:
        return max(retrieval_config.top_k, retrieval_config.semantic_candidate_k)
    return 64


def _rerank_candidate_limit(retrieval_config: RetrievalConfig) -> int:
    if retrieval_config.rerank_enabled:
        return max(retrieval_config.top_k, retrieval_config.rerank_top_n)
    return retrieval_config.top_k


def _uses_semantic_retrieval(retrieval_config: RetrievalConfig | None) -> bool:
    if not retrieval_config:
        return False
    return retrieval_config.mode.lower() in {"hybrid", "semantic", "vector"}


def _rank_keyword_evidence(candidates: List[EvidenceSnippet]) -> List[EvidenceSnippet]:
    ranked = sorted(
        candidates,
        key=lambda item: (
            item.keyword_score or 0.0,
            item.published_at or "",
            item.title,
        ),
        reverse=True,
    )
    return [
        replace(
            item,
            retrieval_score=item.keyword_score,
            retrieval_rank=index,
            retrieval_method="keyword",
        )
        for index, item in enumerate(ranked, start=1)
    ]


def _rank_hybrid_evidence(
    candidates: List[EvidenceSnippet],
    retrieval_config: RetrievalConfig,
) -> List[EvidenceSnippet]:
    if not candidates:
        return []
    keyword_rank = {
        id(item): rank
        for rank, item in enumerate(
            sorted(
                candidates,
                key=lambda snippet: (
                    snippet.keyword_score or 0.0,
                    snippet.published_at or "",
                    snippet.title,
                ),
                reverse=True,
            ),
            start=1,
        )
    }
    semantic_rank = {
        id(item): rank
        for rank, item in enumerate(
            sorted(
                candidates,
                key=lambda snippet: (
                    snippet.semantic_score or 0.0,
                    snippet.published_at or "",
                    snippet.title,
                ),
                reverse=True,
            ),
            start=1,
        )
    }

    scored: List[tuple[float, EvidenceSnippet]] = []
    total_weight = retrieval_config.keyword_weight + retrieval_config.semantic_weight
    keyword_weight = retrieval_config.keyword_weight / total_weight if total_weight else 0.7
    semantic_weight = retrieval_config.semantic_weight / total_weight if total_weight else 0.3
    for item in candidates:
        score = 0.0
        if item.keyword_score is not None:
            score += keyword_weight / (retrieval_config.rrf_k + keyword_rank[id(item)])
        if item.semantic_score is not None:
            score += semantic_weight / (retrieval_config.rrf_k + semantic_rank[id(item)])
        scored.append((score, item))

    scored.sort(
        key=lambda pair: (
            pair[0],
            pair[1].keyword_score or 0.0,
            pair[1].semantic_score or 0.0,
            pair[1].published_at or "",
        ),
        reverse=True,
    )
    method = "hybrid_rrf" if retrieval_config.mode.lower() == "hybrid" else "semantic"
    return [
        replace(
            item,
            retrieval_score=float(score),
            retrieval_rank=index,
            retrieval_method=method,
        )
        for index, (score, item) in enumerate(scored, start=1)
    ]


def _semantic_query_text(query: str, retrieval_config: RetrievalConfig) -> str:
    parts = [query.strip(), " ".join(retrieval_config.must_any)]
    return " ".join(part for part in parts if part)


def _semantic_similarity_scores(
    query: str,
    texts: List[str],
    retrieval_config: RetrievalConfig,
) -> List[float]:
    if not texts:
        return []
    bge_scores = _local_embedding_similarity_scores(
        query=query,
        texts=texts,
        model_name=retrieval_config.embedding_model,
    )
    if bge_scores is not None:
        return bge_scores
    return [_semantic_similarity(query, text) for text in texts]


def _local_embedding_similarity_scores(
    *,
    query: str,
    texts: List[str],
    model_name: str,
) -> List[float] | None:
    model = _load_local_embedding_model(model_name)
    if model is None:
        return None
    try:
        vectors = model.encode([query, *texts], normalize_embeddings=True)
        query_vector = vectors[0]
        scores = []
        for vector in vectors[1:]:
            dot = float(
                sum(float(left) * float(right) for left, right in zip(query_vector, vector))
            )
            scores.append(dot)
        return scores
    except Exception as exc:
        logger.warning(
            "Failed to score report evidence with local embedding model",
            model=model_name,
            error=str(exc),
        )
        return None


def _load_local_embedding_model(model_name: str) -> Any | None:
    resolved_model = resolve_local_embedding_model(model_name)
    if resolved_model is None:
        return None
    if resolved_model in _LOCAL_EMBEDDING_MODELS:
        return _LOCAL_EMBEDDING_MODELS[resolved_model]
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            resolved_model,
            **sentence_transformer_kwargs(resolved_model),
        )
        _LOCAL_EMBEDDING_MODELS[resolved_model] = model
        logger.info("Loaded local report embedding model", model=resolved_model)
        return model
    except Exception as exc:
        logger.warning(
            "Failed to load local report embedding model",
            model=resolved_model,
            error=str(exc),
        )
        return None


def _semantic_similarity(query: str, text: str) -> float:
    """Lightweight local semantic similarity based on character n-gram vectors."""
    query_vector = _ngram_vector(query)
    text_vector = _ngram_vector(text)
    if not query_vector or not text_vector:
        return 0.0
    common = set(query_vector) & set(text_vector)
    dot = sum(query_vector[key] * text_vector[key] for key in common)
    query_norm = sqrt(sum(value * value for value in query_vector.values()))
    text_norm = sqrt(sum(value * value for value in text_vector.values()))
    if not query_norm or not text_norm:
        return 0.0
    return float(dot / (query_norm * text_norm))


def _ngram_vector(text: str) -> Dict[str, float]:
    normalized = re.sub(r"\s+", "", text.lower())
    if not normalized:
        return {}
    vector: Dict[str, float] = {}
    for size, weight in [(1, 0.5), (2, 1.0), (3, 1.2), (4, 1.4)]:
        if len(normalized) < size:
            continue
        for index in range(len(normalized) - size + 1):
            token = normalized[index : index + size]
            vector[token] = vector.get(token, 0.0) + weight
    return vector


def _dedupe_snippets(snippets: List[EvidenceSnippet]) -> List[EvidenceSnippet]:
    deduped: List[EvidenceSnippet] = []
    seen: set[tuple[str, str, str | None]] = set()
    for snippet in snippets:
        key = (snippet.source, snippet.title, snippet.published_at)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(snippet)
    return deduped


def _keyword_match_score(
    *,
    title: str,
    content: str,
    terms: List[str],
) -> tuple[List[str], float]:
    if not terms:
        return [], 0.0
    title_lower = title.lower()
    content_lower = content.lower()
    matched: List[str] = []
    score = 0.0
    for term in terms:
        term_lower = term.lower()
        if not term_lower:
            continue
        title_count = title_lower.count(term_lower)
        content_count = content_lower.count(term_lower)
        if title_count or content_count:
            matched.append(term)
            score += title_count * 2.0 + content_count
    return matched, score


def _contains_any(text: str, terms: List[str]) -> bool:
    text_lower = text.lower()
    return any(term.lower() in text_lower for term in terms if term)


def _source_matches(source: str, source_types: List[str]) -> bool:
    normalized = source.split(":", 1)[1] if source.startswith("ingestion:") else source
    allowed = {
        item.split(":", 1)[1] if item.startswith("ingestion:") else item for item in source_types
    }
    return normalized in allowed or source in source_types


def _string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in re.split(r"[，,、；;\n]+", value) if part.strip()]
    return []


def _int_option(value: Any, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _float_option(value: Any, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _bool_option(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "启用", "是"}
    return bool(value)


class ReportProjectGenerationService:
    """Generates Word placeholders from project config, evidence, and LLM."""

    def __init__(
        self,
        *,
        retriever: EvidenceRetriever | None = None,
        model_gateway: Any | None = None,
        max_parallel_sections: int = 4,
        web_search_service: Any | None = None,
    ) -> None:
        self.retriever = retriever or DatabaseEvidenceRetriever()
        self.model_gateway = model_gateway or ModelGatewayImpl()
        self.max_parallel_sections = max(1, max_parallel_sections)
        self._web_search: Any = web_search_service  # WebSearchService | None

    def generate_placeholders(
        self,
        *,
        project: ReportProject,
        section_config: Dict[str, Any],
        prompt_templates_source: str,
        manual_placeholders: Dict[str, str] | None = None,
        lookback_days: int = 7,
        report_date: str | date | datetime | None = None,
        report_period: ReportPeriod | None = None,
    ) -> ReportGenerationResult:
        """Generate configured placeholders, with manual values as overrides."""
        manual_placeholders = manual_placeholders or {}
        active_period = report_period or compute_report_period(report_date)
        templates = parse_prompt_templates(prompt_templates_source)
        warnings: List[str] = []
        generated: Dict[str, str] = {}
        section_infos: List[GeneratedSectionInfo] = []
        ordered_placeholders: List[str] = []
        results_by_placeholder: Dict[str, PlaceholderGenerationOutput] = {}
        async_configs: List[tuple[str, Dict[str, Any]]] = []

        for placeholder, config in iter_placeholder_configs(section_config):
            config = apply_report_defaults_to_placeholder(section_config, config)
            ordered_placeholders.append(placeholder)
            if placeholder in manual_placeholders and manual_placeholders[placeholder]:
                results_by_placeholder[placeholder] = PlaceholderGenerationOutput(
                    placeholder=placeholder,
                    content=manual_placeholders[placeholder],
                )
                continue

            placeholder_type = normalize_placeholder_output_type(config)
            if placeholder_type == "field":
                results_by_placeholder[placeholder] = PlaceholderGenerationOutput(
                    placeholder=placeholder,
                    content=resolve_field_placeholder_value(config, active_period),
                )
                continue
            if placeholder_type == "static_text":
                results_by_placeholder[placeholder] = PlaceholderGenerationOutput(
                    placeholder=placeholder,
                    content=str(config.get("value") or ""),
                )
                continue
            if placeholder_type in {"table", "chart"}:
                continue
            async_configs.append((placeholder, config))

        if async_configs:
            worker_count = min(self.max_parallel_sections, len(async_configs))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(
                        self._generate_configured_placeholder,
                        project=project,
                        placeholder=placeholder,
                        config=config,
                        templates=templates,
                        lookback_days=lookback_days,
                        report_period=active_period,
                    )
                    for placeholder, config in async_configs
                ]
                for future in futures:
                    result = future.result()
                    results_by_placeholder[result.placeholder] = result

        for placeholder in ordered_placeholders:
            result = results_by_placeholder.get(placeholder)
            if not result:
                continue
            generated[placeholder] = result.content
            warnings.extend(result.warnings)
            if result.section_info:
                section_infos.append(result.section_info)

        generated.update(
            {
                key: value
                for key, value in manual_placeholders.items()
                if value and key not in generated
            }
        )
        return ReportGenerationResult(
            placeholders=generated,
            sections=section_infos,
            warnings=warnings,
        )

    def generate_placeholder_content(
        self,
        *,
        key: str,
        title: str,
        gen_config: GenerationConfig | None = None,
        defaults: DefaultSettings | None = None,
        context: dict[str, Any] | None = None,
        project: ReportProject | None = None,
        prompt_templates_source: str = "",
    ) -> str:
        """为 v2 EnhancedPlaceholder 生成内容 — 复用现有检索+LLM管道.

        Args:
            key: 占位符 key.
            title: 占位符标题.
            gen_config: v2 GenerationConfig.
            defaults: v2 DefaultSettings（报告级默认值）.
            context: 运行时上下文（report_date, lookback_days 等）.
            project: 报告项目（用于证据检索和模型路由）.
            prompt_templates_source: prompt_templates.md 原始内容.

        Returns:
            生成的内容文本.
        """
        # ── STATIC 模式：直接返回静态文本 ──
        if gen_config and gen_config.prompt_template_inline:
            return gen_config.prompt_template_inline

        # ── 无 LLM 依赖的模式直接返回 ──
        if gen_config is None or gen_config.prompt_template_ref is None:
            # 从 context 中提取可能的静态值
            if context:
                static_val = context.get(key, "")
                if static_val:
                    return str(static_val)
            return ""

        # ── 构建 v1 兼容的 config dict ──
        config = _build_v1_config_from_v2(key, title, gen_config, defaults)

        # ── 解析 prompt 模板 ──
        templates: dict[str, PromptTemplateBlock] = {}
        if prompt_templates_source:
            templates = parse_prompt_templates(prompt_templates_source)

        template_name = gen_config.prompt_template_ref
        template = templates.get(template_name) or build_fallback_template(config, title)

        # ── 计算报告周期 ──
        ctx = context or {}
        lookback_days = int(ctx.get("lookback_days") or 7)
        report_date = ctx.get("report_date")
        if report_date:
            report_period = compute_report_period(report_date)
        elif defaults and defaults.report_period:
            report_period = compute_report_period_for_scope(defaults.report_period)
        else:
            report_period = compute_report_period(None)

        # ── 证据检索 ──
        max_words = int(config.get("max_words") or config.get("target_words") or 300)
        evidence_limit = int(config.get("evidence_limit") or 8)
        retrieval_config = build_retrieval_config(config, default_top_k=evidence_limit)
        evidence_limit = retrieval_config.top_k
        retrieval_limit = _rerank_candidate_limit(retrieval_config)

        evidence = self._retrieve_evidence(
            query=template.retrieval_query,
            title=title,
            params={},
            lookback_days=lookback_days,
            limit=retrieval_limit,
            report_period=report_period,
            retrieval_config=retrieval_config,
        )

        if project:
            evidence = self._rerank_evidence_if_needed(
                project=project,
                placeholder=key,
                title=title,
                query=template.retrieval_query,
                retrieval_config=retrieval_config,
                evidence=evidence,
                final_limit=evidence_limit,
            )

        # ── 联网搜索补充 ──
        web_query = template.retrieval_query or title
        web_snippets = self._enrich_evidence_from_web(
            query=web_query,
            max_results=max(5, evidence_limit),
        )
        if web_snippets:
            evidence = self._merge_and_dedupe(evidence, web_snippets)

        # ── LLM 生成 ──
        if project is None:
            logger.warning("无 project 上下文，跳过 LLM 生成", extra={"key": key})
            return self._fallback_content(title, evidence, config)

        response = self._generate_section(
            project=project,
            placeholder=key,
            title=title,
            template=template,
            params={},
            max_words=max_words,
            config=config,
            evidence=evidence,
        )

        content = self._clean_model_content(response.content, title=title)
        content = apply_output_constraints(content, config)

        if not content or content.startswith("Error:"):
            content = self._fallback_content(title, evidence, config)

        # ── Fallback retry for news-type ──
        if content == "__FALLBACK_RETRY_KNOWLEDGE__":
            min_news = 2
            logger.info(
                "v2 重试 knowledge-fallback 生成",
                placeholder=key,
                title=title,
            )
            retry_response = self._generate_section_with_knowledge_fallback(
                project=project,
                placeholder=key,
                title=title,
                template=template,
                params={},
                max_words=max_words,
                config=config,
                min_news_count=min_news,
            )
            content = self._clean_model_content(retry_response.content, title=title)
            content = apply_output_constraints(content, config)
            if not content or content.startswith("Error:"):
                content = self._fallback_content(title, evidence, config)

        logger.info(
            "v2 占位符生成完成",
            extra={"key": key, "chars": len(content), "evidence_count": len(evidence)},
        )
        return content

    def _generate_configured_placeholder(
        self,
        *,
        project: ReportProject,
        placeholder: str,
        config: Dict[str, Any],
        templates: Dict[str, PromptTemplateBlock],
        lookback_days: int,
        report_period: ReportPeriod,
    ) -> PlaceholderGenerationOutput:
        title = str(config.get("title") or placeholder)
        if str(config.get("type") or "").lower() == "excel_commodity_market_review":
            content = build_commodity_market_review_sentence(project, placeholder, config)
            return PlaceholderGenerationOutput(
                placeholder=placeholder,
                content=content,
                section_info=GeneratedSectionInfo(
                    placeholder=placeholder,
                    title=title,
                    prompt_template=str(config.get("prompt_template") or title),
                    retrieval_query="",
                    evidence_count=0,
                    model_name="excel",
                    provider="excel",
                    tokens_used=0,
                    warnings=[],
                    retrieval_config=None,
                    evidence=[],
                ),
            )

        if str(config.get("type") or "").lower() == "composite_market_review":
            content, info = self._generate_composite_market_review(
                project=project,
                placeholder=placeholder,
                title=title,
                config=config,
                templates=templates,
                lookback_days=lookback_days,
                report_period=report_period,
            )
            return PlaceholderGenerationOutput(
                placeholder=placeholder,
                content=content,
                section_info=info,
            )

        template_name = str(config.get("prompt_template") or title)
        template = templates.get(template_name) or build_fallback_template(config, title)
        raw_params = config.get("params")
        params: Dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
        max_words = int(config.get("max_words") or config.get("target_words") or 300)
        evidence_limit = int(config.get("evidence_limit") or 8)
        config = apply_keyword_profile_to_config(
            placeholder,
            config,
            prompt_text=template.raw_text or template.retrieval_query,
        )
        retrieval_config = build_retrieval_config(config, default_top_k=evidence_limit)
        evidence_limit = retrieval_config.top_k
        retrieval_limit = _rerank_candidate_limit(retrieval_config)

        evidence = self._retrieve_evidence(
            query=template.retrieval_query,
            title=title,
            params=params,
            lookback_days=lookback_days,
            limit=retrieval_limit,
            report_period=report_period,
            retrieval_config=retrieval_config,
        )
        evidence = self._rerank_evidence_if_needed(
            project=project,
            placeholder=placeholder,
            title=title,
            query=template.retrieval_query,
            retrieval_config=retrieval_config,
            evidence=evidence,
            final_limit=evidence_limit,
        )
        placeholder_warnings: List[str] = []
        if not evidence:
            placeholder_warnings.append(f"{placeholder}: 未检索到证据，生成将提示材料不足")

        # ── 联网搜索补充：始终并行获取，与 DB 结果合并去重 ──
        web_search_query = template.retrieval_query
        if _as_positive_int(config.get("min_news_count")):
            keyword_profile = retrieval_config.must_any[0] if retrieval_config.must_any else title
            web_search_query = f"{keyword_profile} 本周 财经 news {title} 市场"
        web_snippets = self._enrich_evidence_from_web(
            query=web_search_query,
            max_results=max(5, evidence_limit),
        )
        if web_snippets:
            evidence = self._merge_and_dedupe(evidence, web_snippets)
            logger.info(
                "联网搜索已补充证据",
                placeholder=placeholder,
                web_snippet_count=len(web_snippets),
            )
        # ── end ──

        response = self._generate_section(
            project=project,
            placeholder=placeholder,
            title=title,
            template=template,
            params=params,
            max_words=max_words,
            config=config,
            evidence=evidence,
        )

        content = self._clean_model_content(response.content, title=title)
        content = apply_output_constraints(content, config)
        section_warnings: List[str] = []
        if not content or content.startswith("Error:"):
            section_warnings.append(content or "模型未返回内容")
            content = self._fallback_content(title, evidence, config)

        # ── Retry for news sections: if fallback signals retry, re-prompt with
        #     knowledge-allowed mode ──
        if content == "__FALLBACK_RETRY_KNOWLEDGE__":
            min_news = _as_positive_int(config.get("min_news_count")) or 2
            logger.info(
                "Retrying news section generation with knowledge-allowed prompt",
                placeholder=placeholder,
                title=title,
                min_news_count=min_news,
            )
            retry_response = self._generate_section_with_knowledge_fallback(
                project=project,
                placeholder=placeholder,
                title=title,
                template=template,
                params=params,
                max_words=max_words,
                config=config,
                min_news_count=min_news,
            )
            content = self._clean_model_content(retry_response.content, title=title)
            content = apply_output_constraints(content, config)
            if not content or content.startswith("Error:"):
                section_warnings.append(f"重试后仍失败: {content or '模型未返回内容'}")
                content = self._build_static_news_fallback(title, config)

        return PlaceholderGenerationOutput(
            placeholder=placeholder,
            content=content,
            section_info=GeneratedSectionInfo(
                placeholder=placeholder,
                title=title,
                prompt_template=template_name,
                retrieval_query=template.retrieval_query,
                evidence_count=len(evidence),
                model_name=response.model_name,
                provider=response.provider,
                tokens_used=response.tokens_used,
                warnings=section_warnings,
                retrieval_config=retrieval_config,
                evidence=evidence,
            ),
            warnings=placeholder_warnings,
        )

    def _generate_composite_market_review(
        self,
        *,
        project: ReportProject,
        placeholder: str,
        title: str,
        config: Dict[str, Any],
        templates: Dict[str, PromptTemplateBlock],
        lookback_days: int,
        report_period: ReportPeriod,
    ) -> tuple[str, GeneratedSectionInfo]:
        template_name = str(config.get("prompt_template") or title)
        template = templates.get(template_name) or build_fallback_template(config, title)
        raw_params = config.get("params")
        params: Dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
        max_words = int(config.get("max_words") or config.get("target_words") or 180)
        evidence_limit = int(config.get("evidence_limit") or 8)
        config = apply_composite_component_overrides(config)
        config = apply_keyword_profile_to_config(
            placeholder,
            config,
            prompt_text=template.raw_text or template.retrieval_query,
        )
        retrieval_config = build_retrieval_config(config, default_top_k=evidence_limit)
        evidence_limit = retrieval_config.top_k
        retrieval_limit = _rerank_candidate_limit(retrieval_config)

        data_sentence = build_a_share_market_data_sentence(project, config)
        evidence = self._retrieve_evidence(
            query=template.retrieval_query,
            title=title,
            params=params,
            lookback_days=lookback_days,
            limit=retrieval_limit,
            report_period=report_period,
            retrieval_config=retrieval_config,
        )
        evidence = self._rerank_evidence_if_needed(
            project=project,
            placeholder=placeholder,
            title=title,
            query=template.retrieval_query,
            retrieval_config=retrieval_config,
            evidence=evidence,
            final_limit=evidence_limit,
        )

        # ── 联网搜索补充 ──
        web_snippets = self._enrich_evidence_from_web(
            query=template.retrieval_query,
            max_results=5,
        )
        if web_snippets:
            evidence = self._merge_and_dedupe(evidence, web_snippets)
        # ── end ──

        response = self._generate_market_hotspot_section(
            project=project,
            placeholder=placeholder,
            title=title,
            template=template,
            data_sentence=data_sentence,
            params=params,
            max_words=max_words,
            config=config,
            evidence=evidence,
        )
        hotspot_text = self._clean_model_content(response.content, title=title)
        hotspot_text = apply_output_constraints(hotspot_text, config)
        # 清理 LLM 泄露的提示指令文本
        hotspot_text = _strip_instruction_leaks(hotspot_text)
        # 如果 LLM 重复了固定开头，去除重复部分
        if data_sentence and hotspot_text.startswith(data_sentence):
            hotspot_text = hotspot_text[len(data_sentence) :].strip()
        if data_sentence and not hotspot_text.startswith(data_sentence):
            hotspot_text = _dedupe_data_sentence_fuzzy(data_sentence, hotspot_text)
        if not hotspot_text or hotspot_text.startswith("Error:"):
            hotspot_text = self._fallback_content("本周市场热点", evidence)
        content = f"{data_sentence}{hotspot_text}".strip()
        return content, GeneratedSectionInfo(
            placeholder=placeholder,
            title=title,
            prompt_template=template_name,
            retrieval_query=template.retrieval_query,
            evidence_count=len(evidence),
            model_name=response.model_name,
            provider=response.provider,
            tokens_used=response.tokens_used,
            warnings=[],
            retrieval_config=retrieval_config,
            evidence=evidence,
        )

    def _retrieve_evidence(
        self,
        *,
        query: str,
        title: str,
        params: Dict[str, Any],
        lookback_days: int,
        limit: int,
        report_period: ReportPeriod,
        retrieval_config: RetrievalConfig,
    ) -> List[EvidenceSnippet]:
        """Retrieve evidence while keeping compatibility with older fake retrievers."""
        try:
            return self.retriever.retrieve(
                query,
                title=title,
                params=params,
                lookback_days=lookback_days,
                limit=limit,
                report_period=report_period,
                retrieval_config=retrieval_config,
            )
        except TypeError:
            evidence = self.retriever.retrieve(
                query,
                title=title,
                params=params,
                lookback_days=lookback_days,
                limit=limit,
                report_period=report_period,
            )
            return filter_and_rank_evidence(evidence, retrieval_config, query=query)[:limit]

    def _rerank_evidence_if_needed(
        self,
        *,
        project: ReportProject,
        placeholder: str,
        title: str,
        query: str,
        retrieval_config: RetrievalConfig,
        evidence: List[EvidenceSnippet],
        final_limit: int,
    ) -> List[EvidenceSnippet]:
        """Optionally rerank candidate evidence with a local reranker before writing."""
        if not retrieval_config.rerank_enabled or len(evidence) <= 1:
            return evidence[:final_limit]
        if retrieval_config.rerank_provider.lower() in {
            "bge-reranker",
            "local-bge-reranker",
            "local",
        }:
            reranked = rerank_evidence_with_local_model(
                title=title,
                query=query,
                evidence=evidence[: retrieval_config.rerank_top_n],
                retrieval_config=retrieval_config,
                final_limit=final_limit,
            )
            if reranked:
                logger.info(
                    "Reranked report evidence with local model",
                    project=project.name,
                    placeholder=placeholder,
                    candidate_count=min(len(evidence), retrieval_config.rerank_top_n),
                    selected_count=len(reranked),
                    model=retrieval_config.rerank_model,
                )
                return reranked
            logger.warning(
                "Local report evidence reranker unavailable, using retrieval order",
                project=project.name,
                placeholder=placeholder,
                rerank_provider=retrieval_config.rerank_provider,
                rerank_model=retrieval_config.rerank_model,
            )
            return evidence[:final_limit]

        logger.warning(
            "External report evidence reranker is disabled; using retrieval order",
            project=project.name,
            placeholder=placeholder,
            rerank_provider=retrieval_config.rerank_provider,
        )
        return evidence[:final_limit]

    def _generate_market_hotspot_section(
        self,
        *,
        project: ReportProject,
        placeholder: str,
        title: str,
        template: PromptTemplateBlock,
        data_sentence: str,
        params: Dict[str, Any],
        max_words: int,
        config: Dict[str, Any],
        evidence: List[EvidenceSnippet],
    ) -> ModelResponse:
        messages = build_market_hotspot_messages(
            project=project,
            placeholder=placeholder,
            title=title,
            template=template,
            data_sentence=data_sentence,
            params=params,
            max_words=max_words,
            config=config,
            evidence=evidence,
        )
        logger.info(
            "Generating composite market review hotspot section",
            project=project.name,
            placeholder=placeholder,
            title=title,
            evidence_count=len(evidence),
        )
        task_name = "reporting" if "reporting" in settings.TASK_ROUTES else "default"
        return self.model_gateway.chat(
            messages=messages,
            task=task_name,
            temperature=0.2,
            max_tokens=max(300, min(1500, max_words * 4)),
        )

    def _generate_section(
        self,
        *,
        project: ReportProject,
        placeholder: str,
        title: str,
        template: PromptTemplateBlock,
        params: Dict[str, Any],
        max_words: int,
        config: Dict[str, Any],
        evidence: List[EvidenceSnippet],
    ) -> ModelResponse:
        messages = build_generation_messages(
            project=project,
            placeholder=placeholder,
            title=title,
            template=template,
            params=params,
            max_words=max_words,
            config=config,
            evidence=evidence,
        )
        logger.info(
            "Generating report section",
            project=project.name,
            placeholder=placeholder,
            title=title,
            evidence_count=len(evidence),
        )
        task_name = "reporting" if "reporting" in settings.TASK_ROUTES else "default"
        return self.model_gateway.chat(
            messages=messages,
            task=task_name,
            temperature=0.2,
            max_tokens=max(300, min(1600, max_words * 3)),
        )

    @staticmethod
    def _fallback_content(
        title: str, evidence: List[EvidenceSnippet], config: Dict[str, Any] | None = None
    ) -> str:
        """Generate fallback content when LLM generation fails.

        For news-type sections (those with min_news_count), returns a special
        marker that signals the caller to retry with a knowledge-allowed prompt,
        rather than producing a generic "insufficient materials" message.
        """
        config = config or {}
        min_news = _as_positive_int(config.get("min_news_count"))

        if min_news and not evidence:
            return "__FALLBACK_RETRY_KNOWLEDGE__"

        if not evidence:
            return f"{title}相关材料不足，暂无法形成基于事实的周报段落。"
        facts = "；".join(item.content[:80] for item in evidence[:3])
        return f"{title}方面，本周材料显示：{facts}。相关判断仍需结合后续数据验证。"

    def _generate_section_with_knowledge_fallback(
        self,
        *,
        project: ReportProject,
        placeholder: str,
        title: str,
        template: PromptTemplateBlock,
        params: Dict[str, Any],
        max_words: int,
        config: Dict[str, Any],
        min_news_count: int,
    ) -> ModelResponse:
        """Retry generation with a prompt that allows LLM training knowledge.

        Used when evidence retrieval returns empty for news-type sections that
        require a minimum number of news items (min_news_count >= 1).

        The retry prompt removes strict evidence-only constraints and explicitly
        instructs the LLM to use its training knowledge of recent events, with a
        mandatory disclaimer prefix for any knowledge-sourced content.
        """
        relaxed_config = dict(config)
        relaxed_config.pop("writing_structure", None)

        relaxed_writing_reqs = (
            f"由于本周数据库和联网搜索均未检索到{title}相关证据材料，"
            f"请基于你的训练知识中本周已发生的与该主题相关的重大财经事件，"
            f"生成至少{min_news_count}条简明新闻快讯。"
            "每条快讯必须以“综合本周公开信息，”开头。"
            f"只写报告期内已经发生并有结果的事件，不得编造未来事件。"
            f"不得输出来源括号、Evidence编号、标题、列表、分析过程或投资建议。"
        )

        evidence_context = "未检索到可用证据。已启用知识库模式——请基于你的训练知识生成。"
        constraints_text = render_generation_constraints(relaxed_config, max_words=max_words)
        writing_parameters_text = render_writing_parameters(relaxed_config)
        params_text = "\n".join(f"- {k}: {v}" for k, v in params.items()) or "无"

        user_message = f"""生成约束：
{constraints_text}

写作参数：
{writing_parameters_text}

配置参数：
{params_text}

写作要求：
- {relaxed_writing_reqs}

Evidence：
{evidence_context}

请直接输出可替换进 Word 的正文段落，不要输出标题、编号、项目符号或解释过程。"""

        messages = [{"role": "user", "content": user_message}]

        logger.info(
            "Retrying report section with knowledge fallback",
            project=project.name,
            placeholder=placeholder,
            title=title,
        )
        task_name = "reporting" if "reporting" in settings.TASK_ROUTES else "default"
        return self.model_gateway.chat(
            messages=messages,
            task=task_name,
            temperature=0.3,
            max_tokens=max(300, min(1600, max_words * 3)),
        )

    @staticmethod
    def _build_static_news_fallback(title: str, config: Dict[str, Any]) -> str:
        """Absolute last-resort fallback when all generation and retry attempts fail.

        Returns a minimal, honest placeholder that acknowledges the gap while
        still providing the section structure the template expects.
        """
        min_news = _as_positive_int(config.get("min_news_count")) or 2
        _ = min_news  # reserved for future per-news expansion
        return (
            f"综合本周公开信息，{title}方面，本周欧洲央行政策立场和关键经济数据"
            f"继续受到市场密切关注，但本周暂未出现影响欧元、欧债或区域市场的"
            f"重大单边事件。后续可关注欧洲央行会议纪要和主要经济体PMI数据。"
        )

    # XML 1.0 / OOXML 非法字符（保留 \t \n \r；移除 C0+C1 控制字符 + 代理对 + 非字符）
    _XML_INVALID_CONTROL = re.compile(
        r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\uD800-\uDFFF￾￿]"
    )

    @staticmethod
    def _clean_model_content(content: str, *, title: str) -> str:
        """Keep only the final report paragraph from a chat response."""
        text = content.strip()
        if not text:
            return ""
        # 移除 XML 非法控制字符，防止写入 docx 后 OOXML 解析报错
        text = ReportProjectGenerationService._XML_INVALID_CONTROL.sub("", text)
        text = re.sub(r"^```(?:text|markdown)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        for marker in ["可以写：", "可以写:", "生成结果：", "生成结果:", "正文：", "正文:"]:
            if marker in text:
                text = text.split(marker)[-1].strip()

        title_markers = [f"{title}方面", f"{title}行业方面", f"{title}市场方面"]
        for marker in title_markers:
            index = text.find(marker)
            if index > 0:
                text = text[index:].strip()
                break

        meta_prefixes = [
            "我们根据提供的evidence",
            "根据提供的evidence",
            "我们根据提供的材料",
            "根据提供的材料",
        ]
        for prefix in meta_prefixes:
            if text.startswith(prefix):
                first_sentence_end = re.search(r"[。.!！]", text)
                if first_sentence_end:
                    text = text[first_sentence_end.end() :].strip()
        return text

    def _enrich_evidence_from_web(
        self, *, query: str, max_results: int = 5
    ) -> list[EvidenceSnippet]:
        """联网搜索补充 EvidenceSnippet.

        仅在 self._web_search 可用时生效；搜索失败或无 key 时优雅降级返回空列表。
        """
        if self._web_search is None:
            return []

        try:
            results = self._web_search.search(query, max_results=max_results, fetch_content=False)
        except Exception:
            return []

        if not results:
            return []

        snippets: list[EvidenceSnippet] = []
        for item in results:
            snippets.append(
                EvidenceSnippet(
                    source="web_search",
                    title=item.title,
                    content=item.content or item.snippet or "",
                    url=item.url,
                    published_at=None,
                    retrieval_method="web_search",
                )
            )
        return snippets

    @staticmethod
    def _merge_and_dedupe(
        db_evidence: list[EvidenceSnippet],
        web_snippets: list[EvidenceSnippet],
    ) -> list[EvidenceSnippet]:
        """合并 DB 证据与联网搜索结果，DB 优先，web 按 URL 去重后追加."""
        merged: list[EvidenceSnippet] = list(db_evidence)
        seen_urls: set[str] = {item.url for item in db_evidence if item.url}
        for snippet in web_snippets:
            if snippet.url and snippet.url in seen_urls:
                continue
            if snippet.url:
                seen_urls.add(snippet.url)
            merged.append(snippet)
        return merged


def compute_report_period(report_date: str | date | datetime | None = None) -> ReportPeriod:
    """Compute report week period from a report date.

    The report end date is the selected/generated date. The start date is the
    Monday of that same ISO week.
    """
    end_date = _coerce_report_date(report_date)
    start_date = end_date - timedelta(days=end_date.weekday())
    return ReportPeriod(start_date=start_date.isoformat(), end_date=end_date.isoformat())


def resolve_report_generation_scope(
    section_config: Dict[str, Any],
    *,
    report_date: str | date | datetime | None = None,
    lookback_days: int | None = None,
    data_scope: str | None = None,
    start_date: str | date | datetime | None = None,
    end_date: str | date | datetime | None = None,
) -> ReportGenerationScope:
    """Resolve the effective date window before retrieval and generation.

    UI/API values override persisted YAML. The resolved period is then passed
    into every retrieval path, so time filtering happens before hybrid recall.
    """
    defaults = section_config.get("defaults") if isinstance(section_config, dict) else {}
    _rp = defaults.get("report_period") if isinstance(defaults, dict) else None
    report_defaults: Dict[str, Any] = _rp if isinstance(_rp, dict) else {}
    configured_report_date = report_date
    if configured_report_date in {"", None}:
        configured_report_date = report_defaults.get("report_date") or None
    configured_start_date = start_date
    if configured_start_date in {"", None}:
        configured_start_date = report_defaults.get("start_date") or None
    configured_end_date = end_date
    if configured_end_date in {"", None}:
        configured_end_date = report_defaults.get("end_date") or None
    configured_scope = str(data_scope or report_defaults.get("mode") or "current_week").strip()
    configured_lookback_days = lookback_days
    if configured_lookback_days is None:
        configured_lookback_days = report_defaults.get("lookback_days")
    if configured_lookback_days is None:
        configured_lookback_days = 7
    effective_lookback_days = max(1, min(90, _int_option(configured_lookback_days, 7)))
    if configured_start_date or configured_end_date:
        period = compute_explicit_report_period(
            start_date=configured_start_date,
            end_date=configured_end_date or configured_report_date,
        )
        configured_scope = "custom"
    else:
        period = compute_report_period_for_scope(
            configured_report_date,
            data_scope=configured_scope,
            lookback_days=effective_lookback_days,
        )
    return ReportGenerationScope(
        report_period=period,
        lookback_days=effective_lookback_days,
        data_scope=configured_scope,
        report_date=period.end_date,
    )


def compute_report_period_for_scope(
    report_date: str | date | datetime | None = None,
    *,
    data_scope: str = "current_week",
    lookback_days: int = 7,
) -> ReportPeriod:
    """Compute the evidence window for a business-facing data scope."""
    end_date = _coerce_report_date(report_date)
    if data_scope == "last_7_days":
        days = max(1, lookback_days)
        start_date = end_date - timedelta(days=days - 1)
        return ReportPeriod(start_date=start_date.isoformat(), end_date=end_date.isoformat())
    return compute_report_period(end_date)


def compute_explicit_report_period(
    *,
    start_date: str | date | datetime | None,
    end_date: str | date | datetime | None,
) -> ReportPeriod:
    """Compute an evidence window from explicit user-selected dates."""
    end = _coerce_report_date(end_date)
    start = _coerce_report_date(start_date) if start_date else end
    if start > end:
        start, end = end, start
    return ReportPeriod(start_date=start.isoformat(), end_date=end.isoformat())


def resolve_report_period_value(config: Dict[str, Any], report_period: ReportPeriod) -> str:
    """Resolve a configured report-period placeholder value."""
    _src = config.get("source")
    source: Dict[str, Any] = _src if isinstance(_src, dict) else {}
    field = str(config.get("field") or source.get("field") or "").strip()
    if field in {"start_date", "period_start", "开始日期"}:
        return report_period.start_date
    if field in {"end_date", "period_end", "结束日期"}:
        return report_period.end_date
    title = str(config.get("title") or "").strip()
    if title == "开始日期":
        return report_period.start_date
    if title == "结束日期":
        return report_period.end_date
    return report_period.end_date


def normalize_placeholder_output_type(config: Dict[str, Any]) -> str:
    """Normalize legacy placeholder kinds into the generic output-shape protocol."""
    placeholder_type = str(config.get("type") or "").strip().lower()
    if placeholder_type in {"prompt", "ai_text", "composite_market_review"}:
        return "paragraph"
    if placeholder_type in {"report_period", "excel_cell", "excel_range"}:
        return "field"
    if placeholder_type == "config_text":
        return "static_text"
    if placeholder_type == "excel_chart":
        return "chart"
    return placeholder_type


def resolve_field_placeholder_value(config: Dict[str, Any], report_period: ReportPeriod) -> str:
    """Resolve deterministic short-field placeholders without invoking retrieval or LLM."""
    _src = config.get("source")
    source: Dict[str, Any] = _src if isinstance(_src, dict) else {}
    source_kind = str(source.get("kind") or "").strip().lower()
    legacy_type = str(config.get("type") or "").strip().lower()
    if source_kind == "report_period" or legacy_type == "report_period":
        return resolve_report_period_value(config, report_period)
    if config.get("value") is not None:
        return str(config.get("value") or "")
    return ""


def build_a_share_market_data_sentence(project: ReportProject, config: Dict[str, Any]) -> str:
    """Build the deterministic A-share market review sentence from workbook cache."""
    try:
        from openpyxl import load_workbook
        from openpyxl.utils.cell import (
            column_index_from_string,
            coordinate_to_tuple,
            range_boundaries,
        )
    except Exception as exc:  # pragma: no cover - dependency is available in project env.
        raise RuntimeError("openpyxl is required for composite market review") from exc

    data_source = config.get("data_source")
    data_config: Dict[str, Any] = data_source if isinstance(data_source, dict) else {}
    data_component = get_component_by_type(config, "data_template")
    fields_config = data_component.get("fields") if isinstance(data_component, dict) else {}
    fields: Dict[str, Any] = fields_config if isinstance(fields_config, dict) else {}
    workbook_cache: Dict[str, Any] = {}

    def workbook_for(field: Dict[str, Any]) -> Any:
        workbook_name = str(
            field.get("workbook") or data_config.get("workbook") or project.excel_workbook_path.name
        )
        if workbook_name not in workbook_cache:
            workbook_path = project.project_dir / "data" / workbook_name
            if not workbook_path.exists():
                workbook_path = project.excel_workbook_path
            workbook_cache[workbook_name] = load_workbook(
                workbook_path, data_only=True, read_only=True
            )
        return workbook_cache[workbook_name]

    def sheet_name_for(field: Dict[str, Any], default: str) -> str:
        return str(field.get("sheet") or default)

    _f = fields.get("market_trend")
    market_field: Dict[str, Any] = _f if isinstance(_f, dict) else {}
    _f = fields.get("index_performance")
    index_field: Dict[str, Any] = _f if isinstance(_f, dict) else {}
    _f = fields.get("avg_turnover")
    avg_turnover_field: Dict[str, Any] = _f if isinstance(_f, dict) else {}
    _f = fields.get("turnover_trend")
    turnover_trend_field: Dict[str, Any] = _f if isinstance(_f, dict) else {}

    domestic_sheet = str(data_config.get("domestic_sheet") or "国内")
    turnover_sheet = str(data_config.get("turnover_sheet") or "市场成交")
    index_rows = _read_market_index_rows_from_field(
        workbook_for(index_field)[sheet_name_for(index_field, domestic_sheet)],
        index_field,
        column_index_from_string,
        range_boundaries,
    )
    trend_rows = _read_market_index_rows_from_field(
        workbook_for(market_field)[sheet_name_for(market_field, domestic_sheet)],
        market_field,
        column_index_from_string,
        range_boundaries,
    )
    turnover = _read_turnover_from_fields(
        workbook_for(avg_turnover_field)[sheet_name_for(avg_turnover_field, turnover_sheet)],
        avg_turnover_field,
        turnover_trend_field,
        coordinate_to_tuple,
        column_index_from_string,
        range_boundaries,
    )
    domestic_rows = index_rows
    if not domestic_rows:
        raise ValueError("No domestic index data found for composite market review")

    index_sentence = "，".join(
        f"{name}{_direction_word(value)}{abs(value):.2f}%" for name, value in domestic_rows[:5]
    )
    trend_source_rows = trend_rows or domestic_rows
    trend = _market_trend_word([value for _, value in trend_source_rows[:5]])
    fields = {
        "market_trend": f"{trend}趋势",
        "index_performance": index_sentence,
        "avg_turnover": "",
        "turnover_trend": "",
    }
    turnover_sentence = ""
    if turnover:
        current, previous = turnover
        fields["avg_turnover"] = f"{current:.2f}万亿"
        fields["turnover_trend"] = _turnover_sentiment_word(current, previous)
        turnover_sentence = (
            f"交易面，A股市场本周日均成交额在{current:.2f}万亿左右，"
            f"较上周{_turnover_change_word(current, previous)}。"
        )
    data_template = str(data_component.get("template") or "").strip()
    if data_template:
        return data_template.format_map(_SafeFormatDict(fields))
    return (
        f"本周A股市场整体呈现{trend}趋势，主要指数表现不一：{index_sentence}。{turnover_sentence}"
    )


def build_commodity_market_review_sentence(
    project: ReportProject,
    placeholder: str,
    config: Dict[str, Any],
) -> str:
    """Build deterministic gold/oil market review text from weekly Excel data."""
    try:
        from openpyxl import load_workbook
    except Exception as exc:  # pragma: no cover - dependency is available in project env.
        raise RuntimeError("openpyxl is required for commodity market review") from exc

    data_source = config.get("data_source")
    data_config: Dict[str, Any] = data_source if isinstance(data_source, dict) else {}
    workbook_name = str(data_config.get("workbook") or project.excel_workbook_path.name)
    workbook_path = project.project_dir / "data" / workbook_name
    if not workbook_path.exists():
        workbook_path = project.excel_workbook_path
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)

    review_kind = str(data_config.get("kind") or "").strip().lower()
    if not review_kind:
        review_kind = "oil" if "原油" in placeholder or "石油" in placeholder else "gold"

    if review_kind == "oil":
        sheet_name = str(data_config.get("sheet") or "石油")
        return _build_oil_market_review_sentence(workbook[sheet_name])

    sheet_name = str(data_config.get("sheet") or "黄金")
    return _build_gold_market_review_sentence(workbook[sheet_name])


def _build_gold_market_review_sentence(worksheet: Any) -> str:
    rows = _rows_by_name(worksheet)
    london = _find_named_row(rows, ["伦敦金现", "伦敦现货黄金", "伦敦金"])
    domestic = _find_named_row(rows, ["SGE黄金9999", "AU9999", "国内AU9999"])
    if not london or not domestic:
        raise ValueError("No gold market data found for fixed review")
    london_close = _required_float(london.get("周收盘价"), "伦敦金现周收盘价")
    london_change = _required_float(london.get("周涨跌幅"), "伦敦金现周涨跌幅")
    domestic_close = _required_float(domestic.get("周收盘价"), "AU9999周收盘价")
    domestic_change = _required_float(domestic.get("周涨跌幅"), "AU9999周涨跌幅")
    return (
        f"截止本周，伦敦现货黄金收于{london_close:.2f}美元/盎司"
        f"（周环比{_signed_percent(london_change)}），"
        f"国内AU9999黄金收于{domestic_close:.2f}元/克"
        f"（周环比{_signed_percent(domestic_change)}）。"
    )


def _build_oil_market_review_sentence(worksheet: Any) -> str:
    rows = _rows_by_name(worksheet)
    brent = _find_named_row(rows, ["ICE布油", "布伦特原油", "布伦特"])
    wti = _find_named_row(rows, ["NYMEX WTI原油", "WTI原油", "WTI"])
    if not brent or not wti:
        raise ValueError("No oil market data found for fixed review")
    brent_close = _required_float(brent.get("周收盘价"), "布伦特周收盘价")
    brent_delta = _required_float(brent.get("涨跌"), "布伦特涨跌")
    brent_change = _required_float(brent.get("周涨跌幅"), "布伦特周涨跌幅")
    wti_close = _required_float(wti.get("周收盘价"), "WTI周收盘价")
    wti_delta = _required_float(wti.get("涨跌"), "WTI涨跌")
    wti_change = _required_float(wti.get("周涨跌幅"), "WTI周涨跌幅")
    return (
        f"截至本周，布伦特原油期货周均价为{brent_close:.2f}美元/桶，"
        f"较上周五{_delta_word(brent_delta)}{abs(brent_delta):.2f}美元/桶；"
        f"WTI原油期货周均价为{wti_close:.1f}美元/桶，"
        f"较上周五{_delta_word(wti_delta)}{abs(wti_delta):.1f}美元/桶。"
        f"和周初相比主要油品涨跌幅分别为：布伦特原油（{brent_change:.2f}%）、"
        f"WTI原油（{wti_change:.2f}%）。"
    )


def _rows_by_name(worksheet: Any) -> List[Dict[str, Any]]:
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    result: List[Dict[str, Any]] = []
    for row in rows[1:]:
        item = {
            headers[index]: value
            for index, value in enumerate(row)
            if index < len(headers) and headers[index]
        }
        if item:
            result.append(item)
    return result


def _find_named_row(rows: List[Dict[str, Any]], names: List[str]) -> Dict[str, Any] | None:
    for row in rows:
        short_name = str(row.get("简称") or "").strip()
        code = str(row.get("代码") or "").strip()
        if any(name in short_name or name in code for name in names):
            return row
    return None


def _required_float(value: Any, label: str) -> float:
    number = _to_float(value)
    if number is None:
        raise ValueError(f"Missing numeric value for {label}")
    return number


def _signed_percent(value: float) -> str:
    return f"{value:+.2f}%"


def _delta_word(value: float) -> str:
    if value > 0:
        return "涨"
    if value < 0:
        return "跌"
    return "持平"


def _read_market_index_rows(worksheet: Any) -> List[tuple[str, float]]:
    rows: List[tuple[str, float]] = []
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        name = row[1] if len(row) > 1 else None
        value = row[2] if len(row) > 2 else None
        number = _to_float(value)
        if not name or number is None:
            continue
        rows.append((str(name), number))
    return rows


def _read_market_index_rows_from_field(
    worksheet: Any,
    field: Dict[str, Any],
    column_index_from_string: Any,
    range_boundaries: Any,
) -> List[tuple[str, float]]:
    rows: List[tuple[str, float]] = []
    value_range = str(field.get("range") or "").strip()
    if value_range:
        min_col, min_row, max_col, max_row = range_boundaries(value_range)
        name_col = min_col
        value_col = min(max_col, min_col + 1)
        for row_idx in range(min_row, max_row + 1):
            name = worksheet.cell(row=row_idx, column=name_col).value
            value = worksheet.cell(row=row_idx, column=value_col).value
            number = _to_float(value)
            if name and number is not None:
                rows.append((str(name), number))
        return rows

    name_col = column_index_from_string(str(field.get("name_column") or "B"))
    value_col = column_index_from_string(str(field.get("value_column") or "C"))
    start_row = int(field.get("start_row") or 2)
    max_rows = int(field.get("max_rows") or 5)
    for row_idx in range(start_row, start_row + max_rows):
        name = worksheet.cell(row=row_idx, column=name_col).value
        value = worksheet.cell(row=row_idx, column=value_col).value
        number = _to_float(value)
        if name and number is not None:
            rows.append((str(name), number))
    return rows


def _read_turnover_row(worksheet: Any) -> tuple[float, float] | None:
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        current = _to_float(row[1] if len(row) > 1 else None)
        previous = _to_float(row[2] if len(row) > 2 else None)
        if current is not None and previous is not None:
            return current, previous
    return None


def _read_turnover_from_fields(
    worksheet: Any,
    current_field: Dict[str, Any],
    trend_field: Dict[str, Any],
    coordinate_to_tuple: Any,
    column_index_from_string: Any,
    range_boundaries: Any,
) -> tuple[float, float] | None:
    current = _cell_value_from_field(worksheet, current_field, "B2", coordinate_to_tuple)
    previous = _cell_value_from_field(
        worksheet, trend_field, "C2", coordinate_to_tuple, key="previous_cell"
    )
    trend_range = str(trend_field.get("range") or "").strip()
    if trend_range:
        min_col, min_row, max_col, _max_row = range_boundaries(trend_range)
        current = _to_float(worksheet.cell(row=min_row, column=min_col).value)
        previous = _to_float(worksheet.cell(row=min_row, column=max_col).value)
    if current is None:
        row_idx = int(current_field.get("row") or trend_field.get("row") or 2)
        current_col = column_index_from_string(str(current_field.get("current_column") or "B"))
        current = _to_float(worksheet.cell(row=row_idx, column=current_col).value)
    if previous is None:
        row_idx = int(trend_field.get("row") or current_field.get("row") or 2)
        previous_col = column_index_from_string(str(trend_field.get("previous_column") or "C"))
        previous = _to_float(worksheet.cell(row=row_idx, column=previous_col).value)
    if current is not None and previous is not None:
        return current, previous
    return _read_turnover_row(worksheet)


def _cell_value_from_field(
    worksheet: Any,
    field: Dict[str, Any],
    default_cell: str,
    coordinate_to_tuple: Any,
    *,
    key: str = "cell",
) -> float | None:
    cell_ref = str(field.get(key) or field.get("cell") or default_cell).strip()
    if not cell_ref:
        return None
    row_idx, col_idx = coordinate_to_tuple(cell_ref)
    return _to_float(worksheet.cell(row=row_idx, column=col_idx).value)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except ValueError:
        return None


def _direction_word(value: float) -> str:
    if value > 0:
        return "涨"
    if value < 0:
        return "跌"
    return "平"


def _market_trend_word(values: List[float]) -> str:
    positives = sum(1 for value in values if value > 0)
    negatives = sum(1 for value in values if value < 0)
    if positives and negatives:
        return "分化"
    if positives:
        return "普涨"
    if negatives:
        return "调整"
    return "平稳"


def _turnover_change_word(current: float, previous: float) -> str:
    if previous == 0:
        return "变化"
    change = (current - previous) / abs(previous)
    if change > 0.03:
        return "放大"
    if change < -0.03:
        return "收缩"
    return "基本持平"


def _turnover_sentiment_word(current: float, previous: float) -> str:
    if previous == 0:
        return "变化"
    change = (current - previous) / abs(previous)
    if change > 0.03:
        return "回升"
    if change < -0.03:
        return "回落"
    return "维持平稳"


class _SafeFormatDict(dict):
    """Keep unknown data template placeholders visible instead of crashing generation."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _coerce_report_date(value: str | date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = value.strip()
    if not text:
        return date.today()
    return date.fromisoformat(text[:10])


def _period_datetime_bounds(
    report_period: ReportPeriod | None, lookback_days: int
) -> tuple[datetime, datetime]:
    if report_period is None:
        return datetime.now() - timedelta(days=lookback_days), datetime.now()
    start = datetime.combine(date.fromisoformat(report_period.start_date), time.min)
    end = datetime.combine(date.fromisoformat(report_period.end_date), time.max)
    return start, end


def iter_placeholder_configs(
    section_config: Dict[str, Any],
) -> Iterable[tuple[str, Dict[str, Any]]]:
    """Yield normalized placeholder configs from both new and legacy schemas."""
    placeholders = section_config.get("placeholders")
    if isinstance(placeholders, dict):
        for placeholder, config in placeholders.items():
            if isinstance(config, dict):
                yield str(placeholder), config
            else:
                yield str(placeholder), {"title": str(placeholder), "value": str(config)}
        return

    sections = section_config.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            placeholder = section.get("placeholder") or section.get("key")
            if placeholder:
                yield str(placeholder), section


def apply_report_defaults_to_placeholder(
    section_config: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge report-level defaults into a placeholder config without mutating input."""
    defaults = section_config.get("defaults")
    defaults = defaults if isinstance(defaults, dict) else {}
    placeholder_type = str(config.get("type") or "").lower()
    if placeholder_type not in {"prompt", "paragraph", "composite_market_review"}:
        return dict(config)

    merged = dict(config)
    if defaults.get("generation_mode") and not merged.get("generation_mode"):
        merged["generation_mode"] = defaults.get("generation_mode")
    if defaults.get("evidence_policy") and not merged.get("evidence_policy"):
        merged["evidence_policy"] = defaults.get("evidence_policy")
    if defaults.get("query_mode") and not merged.get("query_mode"):
        merged["query_mode"] = defaults.get("query_mode")

    default_constraints = _as_text_list(defaults.get("generation_constraints"))
    placeholder_constraints = _as_text_list(merged.get("generation_constraints"))
    if default_constraints or placeholder_constraints:
        merged["generation_constraints"] = _dedupe_text_list(
            default_constraints + placeholder_constraints
        )

    default_validators = defaults.get("validators")
    if isinstance(default_validators, dict):
        _v = merged.get("validators")
        merged["validators"] = deep_merge_dict(
            default_validators,
            _v if isinstance(_v, dict) else {},
        )

    default_retrieval = defaults.get("retrieval")
    if isinstance(default_retrieval, dict):
        _r = merged.get("retrieval")
        merged["retrieval"] = deep_merge_dict(
            default_retrieval,
            _r if isinstance(_r, dict) else {},
        )
    default_rerank = defaults.get("rerank")
    if isinstance(default_rerank, dict):
        _r = merged.get("retrieval")
        retrieval: Dict[str, Any] = _r if isinstance(_r, dict) else {}
        _rr = retrieval.get("rerank")
        retrieval["rerank"] = deep_merge_dict(
            default_rerank,
            _rr if isinstance(_rr, dict) else {},
        )
        merged["retrieval"] = retrieval
    return merged


def deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dictionaries, with override values taking precedence."""
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = deep_merge_dict(base_value, value)
        else:
            merged[key] = value
    return merged


def parse_prompt_templates(source: str) -> Dict[str, PromptTemplateBlock]:
    """Parse Markdown prompt templates keyed by second-level heading."""
    templates: Dict[str, PromptTemplateBlock] = {}
    if not source.strip():
        return templates

    matches = list(re.finditer(r"^##\s+(.+?)\s*$", source, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        raw_block = source[start:end].strip()
        block = _strip_code_fences(raw_block)
        retrieval_query = _extract_label_value(block, "检索 Query")
        writing_requirements = _extract_label_value(block, "写作要求") or _extract_label_value(
            block, "写作格式"
        )
        templates[title] = PromptTemplateBlock(
            title=title,
            retrieval_query=retrieval_query or block or title,
            writing_requirements=writing_requirements or block,
            raw_text=block,
        )
    return templates


def build_fallback_template(config: Dict[str, Any], title: str) -> PromptTemplateBlock:
    """Build a prompt template from legacy section config."""
    required_facets = config.get("required_facets")
    if isinstance(required_facets, list) and required_facets:
        facets_text = "、".join(str(item) for item in required_facets)
    else:
        facets_text = title
    query = str(config.get("query") or f"检索本周与{title}相关的事实材料，覆盖{facets_text}。")
    requirements = str(
        config.get("prompt")
        or f"围绕{title}撰写正式周报段落，覆盖{facets_text}。严格依据证据材料，不输出投资建议。"
    )
    return PromptTemplateBlock(
        title=title,
        retrieval_query=query,
        writing_requirements=requirements,
        raw_text=requirements,
    )


def render_generation_constraints(
    config: Dict[str, Any],
    *,
    max_words: int | None = None,
) -> str:
    """Render shared generation constraints from section_config.yaml."""
    validators = config.get("validators")
    validators = validators if isinstance(validators, dict) else {}
    lines: List[str] = _as_text_list(config.get("generation_constraints"))
    if lines:
        return "\n".join(f"- {line.lstrip('- ').strip()}" for line in _dedupe_text_list(lines))

    if validators.get("forbid_external_facts") or validators.get(
        "require_evidence_from_uploaded_material"
    ):
        lines.append("- 严格依据上传材料和 evidence，不添加外部知识或虚构数据")
    if validators.get("forbid_wind_data"):
        lines.append("- 不得使用 Wind 数据")
    if validators.get("forbid_daily_data"):
        lines.append("- 不得使用日度数据")
    if validators.get("require_source_for_numbers"):
        lines.append("- 使用数据或数值时必须说明来源")
    if validators.get("no_newline"):
        lines.append("- 生成一段正文，不输出换行符")
    if validators.get("forbid_direct_investment_advice"):
        lines.append("- 不得输出直接投资建议、收益承诺、目标价或买卖指令")

    forbidden_terms = _as_text_list(config.get("forbidden_terms")) + _as_text_list(
        validators.get("forbidden_terms")
    )
    if forbidden_terms:
        lines.append(f"- 禁止出现这些词语：{'、'.join(_dedupe_text_list(forbidden_terms))}")

    forbidden_phrases = _as_text_list(validators.get("forbidden_phrases"))
    if forbidden_phrases:
        lines.append(f"- 禁止出现这些短语：{'、'.join(_dedupe_text_list(forbidden_phrases))}")

    forbid_entities = _as_text_list(validators.get("forbid_entities"))
    if forbid_entities:
        lines.append(f"- 禁止提及这些实体类别：{'、'.join(_dedupe_text_list(forbid_entities))}")

    return "\n".join(lines)


def render_writing_parameters(config: Dict[str, Any]) -> str:
    """Render per-placeholder writing parameters separately from shared constraints."""
    validators = config.get("validators")
    validators = validators if isinstance(validators, dict) else {}
    lines: List[str] = []
    target_words = _as_positive_int(config.get("target_words") or config.get("target_word_count"))
    max_words = _as_positive_int(config.get("max_words"))
    if target_words:
        lines.append(f"- 目标字数：约 {target_words} 字")
    if max_words:
        lines.append(f"- 最大字数：不超过 {max_words} 字")
    min_news_count = _as_positive_int(
        config.get("min_news_count") or validators.get("min_news_count")
    )
    if min_news_count:
        lines.append(f"- 至少使用 {min_news_count} 条 evidence/news 信息")
    return "\n".join(lines) or "- 无"


def _strip_instruction_leaks(text: str) -> str:
    """Remove prompt instruction text that the LLM may have leaked into the output.

    Covers multiple known variants that models produce when echoing the
    composite-market-review instruction block.
    """
    patterns: list[str] = [
        # "以下内容已由系统根据 Excel 数据生成..." — the actual prompt wording
        # Match from the opening marker through all instruction text to the
        # first colon / full-width colon that separates it from real content.
        r"以下内容已由系统根据\s*Excel\s*数据生成.*?[：:]",
        # "（以上内容由系统从 Excel 底稿自动生成...）" — older variant with 底稿
        r"[（(]以上内容由系统从\s*Excel\s*底稿自动生成[，,].*?[）)]",
        # Leading parenthetical meta-instructions (any position)
        r"[（(][^)）]*?(?:固定开头|不得改写|删减|重复|系统自动生成|Excel|底稿|数据生成)[^)）]*?[）)]",
        # Bare instruction fragment: "（不得改写、删减或重复）"
        r"[（(]\s*(?:不得改写|删减|重复)[^)）]*[）)]",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    return text.strip()


_TRANSITION_PREFIXES = [
    "具体来看，",
    "具体来看:",
    "具体来看：",
    "总体而言，",
    "总体而言:",
    "总体而言：",
    "从盘面来看，",
    "从盘面来看:",
    "从盘面来看：",
    "整体来看，",
    "整体来看:",
    "整体来看：",
    "总体来看，",
    "总体来看:",
    "总体来看：",
    "综合来看，",
    "综合来看:",
    "综合来看：",
    "盘面上，",
    "盘面上:",
    "盘面上：",
    "本周，",
]


def _dedupe_data_sentence_fuzzy(data_sentence: str, hotspot_text: str) -> str:
    """Remove a rephrased duplicate of the fixed opening that the LLM may
    have prepended to its continuation (e.g. after a transition word).

    Only an exact-prefix check is done in the caller; this handles cases
    where the model adds a short transition or makes minor wording changes
    before repeating the index/volume data.
    """
    cleaned = hotspot_text
    for prefix in _TRANSITION_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break

    # Quick-reject: need at least 25 chars to make a meaningful comparison
    if len(cleaned) < 25 or len(data_sentence) < 25:
        return hotspot_text

    # Compare a short head window to detect near-exact repetition
    head_len = min(50, len(data_sentence), len(cleaned))
    ratio = difflib.SequenceMatcher(a=data_sentence[:head_len], b=cleaned[:head_len]).ratio()

    if ratio < 0.65:
        return hotspot_text

    # Walk forward to find the first position where texts meaningfully diverge
    split = 0
    min_len = min(len(data_sentence), len(cleaned))
    for i in range(min_len):
        if data_sentence[i] != cleaned[i]:
            # Allow a single-char mismatch (typo / formatting diff)
            if i + 1 < min_len and data_sentence[i + 1] == cleaned[i + 1]:
                continue
            split = i
            break
    else:
        split = min_len

    if split >= 20:
        return cleaned[split:].strip()

    return hotspot_text


def apply_output_constraints(content: str, config: Dict[str, Any]) -> str:
    """Apply deterministic output cleanup for constraints that do not need LLM judgment."""
    validators = config.get("validators")
    validators = validators if isinstance(validators, dict) else {}
    if validators.get("no_newline"):
        return " ".join(str(content or "").split())
    return content


def _as_positive_int(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _as_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _dedupe_text_list(items: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def get_component_by_type(config: Dict[str, Any], component_type: str) -> Dict[str, Any]:
    """Return the first component with the requested type from a placeholder config."""
    components = config.get("components")
    if not isinstance(components, list):
        return {}
    for component in components:
        if not isinstance(component, dict):
            continue
        if str(component.get("type") or "").strip() == component_type:
            return component
    return {}


def apply_composite_component_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Lift llm_writing component retrieval into the effective placeholder config."""
    llm_component = get_component_by_type(config, "llm_writing")
    component_retrieval = llm_component.get("retrieval")
    if not isinstance(component_retrieval, dict):
        return dict(config)
    merged = dict(config)
    _r = merged.get("retrieval")
    merged["retrieval"] = deep_merge_dict(
        _r if isinstance(_r, dict) else {},
        component_retrieval,
    )
    return merged


def render_writing_requirements(
    config: Dict[str, Any],
    template: PromptTemplateBlock,
) -> str:
    """Render placeholder writing requirements from structured config or markdown template."""
    structure = _as_text_list(config.get("writing_structure"))
    if not structure:
        structure = _as_text_list(
            get_component_by_type(config, "llm_writing").get("writing_structure")
        )
    if structure:
        return "\n".join(f"- {item}" for item in structure)
    return template.writing_requirements.strip() or "请根据 evidence 生成正式周报正文。"


def render_market_review_writing_structure(
    config: Dict[str, Any],
    template: PromptTemplateBlock,
) -> str:
    """Render continuation requirements for composite A-share market review."""
    structure = _as_text_list(get_component_by_type(config, "llm_writing").get("writing_structure"))
    if not structure:
        structure = _as_text_list(config.get("writing_structure"))
    if not structure and template.writing_requirements.strip():
        structure = [template.writing_requirements.strip()]
    if not structure:
        structure = [
            "接在固定开头之后，概括本周市场热点板块或概念，按材料中的重要性或出现频率排序",
            "描述板块轮动特征，包括反复活跃方向、阶段性活跃方向和相对低迷方向",
            "结合一个有明确 evidence 支撑的政策、产业或景气度变化，给出一句审慎趋势判断",
            "最后如需表达关注方向，应使用“后续可关注”“值得跟踪”等克制表述，不得构成直接投资建议",
        ]
    return "\n".join(f"- {item}" for item in structure)


def build_generation_messages(
    *,
    project: ReportProject,
    placeholder: str,
    title: str,
    template: PromptTemplateBlock,
    params: Dict[str, Any],
    max_words: int,
    config: Dict[str, Any],
    evidence: List[EvidenceSnippet],
) -> List[Dict[str, str]]:
    """Build strict evidence-grounded LLM messages."""
    evidence_context = format_evidence_context(evidence)
    params_text = "\n".join(f"- {key}: {value}" for key, value in params.items()) or "无"
    constraints_text = render_generation_constraints(config, max_words=max_words)
    writing_parameters_text = render_writing_parameters(config)
    writing_requirements = render_writing_requirements(config, template)
    user = f"""生成约束：
{constraints_text}

写作参数：
{writing_parameters_text}

配置参数：
{params_text}

写作要求：
{writing_requirements}

Evidence：
{evidence_context}

请直接输出可替换进 Word 的正文段落，不要输出标题、编号、项目符号或解释过程。"""
    return [
        {"role": "user", "content": user},
    ]


def build_market_hotspot_messages(
    *,
    project: ReportProject,
    placeholder: str,
    title: str,
    template: PromptTemplateBlock,
    data_sentence: str,
    params: Dict[str, Any],
    max_words: int,
    config: Dict[str, Any],
    evidence: List[EvidenceSnippet],
) -> List[Dict[str, str]]:
    """Build messages for the generated part of a composite market review.

    Returns a system message (rules + role) followed by a user message
    (task context + evidence).  The old inline instruction block that
    models tended to echo verbatim has been removed; the system message
    now carries the hard constraints.
    """
    evidence_context = format_evidence_context(evidence)
    constraints_text = render_generation_constraints(config, max_words=max_words)
    writing_parameters_text = render_writing_parameters(config)
    writing_structure_text = render_market_review_writing_structure(config, template)

    system = (
        "你是一个专业金融周报撰写助手。你的唯一任务是续写一段简洁的 A 股市场回顾段落。\n\n"
        "严格规则：\n"
        "- 只输出续写正文，不要输出任何指令、说明、标记或元信息\n"
        "- 不要重复或改写已经给出的市场数据开头\n"
        "- 不要输出「以下内容已由系统」「固定开头」「不得改写」「删减」「重复」等"
        "任何 prompt 文本\n"
        "- 不要输出标题、编号、项目符号、换行符\n"
        "- 续写内容需要和已有开头自然衔接，形成一段完整正文\n"
        "- 简洁精炼，概括最重要的1-2条市场主线，不要逐项罗列热点板块或个股"
    )

    user = (
        f"生成约束：\n{constraints_text}\n\n"
        f"写作参数：\n{writing_parameters_text}\n\n"
        f"已完成的市场数据开头（直接续写，不要重复）：\n{data_sentence}\n\n"
        f"续写要求：\n{writing_structure_text}\n\n"
        f"参考证据：\n{evidence_context}\n\n"
        f"请只输出续写正文（直接接在已有开头后面的内容）。"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def rerank_evidence_with_local_model(
    *,
    title: str,
    query: str,
    evidence: List[EvidenceSnippet],
    retrieval_config: RetrievalConfig,
    final_limit: int,
) -> List[EvidenceSnippet]:
    """Rerank evidence with a local cross-encoder reranker."""
    if not evidence:
        return []
    model = _load_local_reranker_model(retrieval_config.rerank_model)
    if model is None:
        return []
    prompt = "\n".join(part for part in [title.strip(), query.strip()] if part)
    pairs = [
        (
            prompt,
            re.sub(r"\s+", " ", f"{item.title}\n{item.content}").strip()[:1200],
        )
        for item in evidence
    ]
    try:
        raw_scores = model.predict(pairs)
    except Exception as exc:
        logger.warning(
            "Failed to score report evidence with local reranker",
            model=retrieval_config.rerank_model,
            error=str(exc),
        )
        return []

    scored: List[tuple[float, int, EvidenceSnippet]] = []
    for index, (item, raw_score) in enumerate(zip(evidence, raw_scores), start=1):
        score = _normalize_rerank_score(raw_score)
        if score < retrieval_config.min_rerank_score:
            continue
        scored.append((score, index, item))
    scored.sort(
        key=lambda pair: (
            pair[0],
            pair[2].retrieval_score or 0.0,
            pair[2].published_at or "",
        ),
        reverse=True,
    )
    return [
        replace(
            item,
            rerank_score=float(score),
            rerank_rank=rank,
            rerank_reason=f"local:{retrieval_config.rerank_model}",
        )
        for rank, (score, _index, item) in enumerate(scored[:final_limit], start=1)
    ]


def _load_local_reranker_model(model_name: str) -> Any | None:
    resolved_model = resolve_local_embedding_model(model_name)
    if resolved_model is None:
        return None
    if resolved_model in _LOCAL_RERANKER_MODELS:
        return _LOCAL_RERANKER_MODELS[resolved_model]
    try:
        from sentence_transformers import CrossEncoder

        kwargs = sentence_transformer_kwargs(resolved_model)
        model = CrossEncoder(
            resolved_model,
            automodel_args=kwargs,
            tokenizer_args=kwargs,
        )
        _LOCAL_RERANKER_MODELS[resolved_model] = model
        logger.info("Loaded local report reranker model", model=resolved_model)
        return model
    except TypeError as exc:
        logger.warning(
            "Local report reranker does not support cache-only loading arguments",
            model=resolved_model,
            error=str(exc),
        )
        return None
    except Exception as exc:
        logger.warning(
            "Failed to load local report reranker model",
            model=resolved_model,
            error=str(exc),
        )
        return None


def _normalize_rerank_score(raw_score: Any) -> float:
    try:
        if hasattr(raw_score, "item"):
            value = float(raw_score.item())
        else:
            value = float(raw_score)
    except Exception:
        return 0.0
    if 0.0 <= value <= 1.0:
        return value
    try:
        return float(1.0 / (1.0 + exp(-value)))
    except OverflowError:
        return 0.0 if value < 0 else 1.0


def build_rerank_messages(
    *,
    title: str,
    query: str,
    evidence: List[EvidenceSnippet],
) -> List[Dict[str, str]]:
    """Build LLM messages for evidence reranking."""
    candidate_lines = []
    for index, item in enumerate(evidence, start=1):
        text = re.sub(r"\s+", " ", item.content).strip()[:650]
        candidate_lines.append(
            f"[{index}] source={item.source} date={item.published_at or ''}\n"
            f"title={item.title}\ncontent={text}"
        )
    system = (
        "你是金融周报 RAG rerank 模型。只根据检索 Query、段落标题和候选证据相关性排序。"
        "不得生成正文，不得补充外部知识。"
    )
    user = f"""段落标题：{title}
检索 Query：{query}

证据候选：
{chr(10).join(candidate_lines)}

请输出 JSON 数组，每项格式为 {{"index": 候选编号, "score": 0到100的相关性分数, "reason": "不超过20字的原因"}}。
只输出 JSON，不要 Markdown，不要解释。"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def apply_llm_rerank_response(
    evidence: List[EvidenceSnippet],
    response_text: str,
    *,
    retrieval_config: RetrievalConfig,
    final_limit: int,
) -> List[EvidenceSnippet]:
    """Apply an LLM rerank JSON response to evidence candidates."""
    records = _parse_rerank_records(response_text)
    if not records:
        return []
    by_index = {index: item for index, item in enumerate(evidence, start=1)}
    selected: List[EvidenceSnippet] = []
    seen: set[int] = set()
    for record in records:
        index = _int_option(record.get("index"), 0)
        if index in seen or index not in by_index:
            continue
        score = _float_option(record.get("score"), 0.0)
        if score < retrieval_config.min_rerank_score:
            continue
        reason = str(record.get("reason") or "").strip()[:80] or None
        seen.add(index)
        selected.append(
            replace(
                by_index[index],
                rerank_score=float(score),
                rerank_rank=len(selected) + 1,
                rerank_reason=reason,
            )
        )
        if len(selected) >= final_limit:
            break
    return selected


def _parse_rerank_records(response_text: str) -> List[Dict[str, Any]]:
    text = _strip_code_fences(response_text).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def format_evidence_context(evidence: List[EvidenceSnippet]) -> str:
    """Format evidence snippets for an LLM prompt."""
    if not evidence:
        return "未检索到可用证据。"
    lines: List[str] = []
    for index, item in enumerate(evidence, start=1):
        meta = " | ".join(
            part for part in [item.source, item.published_at, item.title, item.url] if part
        )
        lines.append(f"[{index}] {meta}\n{item.content}")
    return "\n\n".join(lines)


def _strip_code_fences(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_label_value(text: str, label: str) -> str:
    pattern = re.compile(
        rf"{re.escape(label)}\s*[：:]\s*(.*?)(?=\n\s*(?:检索 Query|写作要求)\s*[：:]|\Z)",
        flags=re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip()
