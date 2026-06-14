"""Evidence-grounded report project generation.

This module connects report project configuration to the existing database
and model gateway:

Word placeholder -> section config -> prompt template -> evidence retrieval
-> DeepSeek/model generation -> placeholder replacement.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Protocol

from sqlalchemy import or_

from core.interfaces.model_gateway import ModelResponse
from core.model_gateway.gateway import ModelGatewayImpl
from core.observability import get_logger
from core.settings import settings
from reporting.projects.keyword_profiles import apply_keyword_profile_to_config
from reporting.projects.project_manager import ReportProject

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReportPeriod:
    """Report date window shared by placeholders, retrieval, and run logs."""

    start_date: str
    end_date: str


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
    rrf_k: int = 60
    semantic_candidate_k: int = 64
    rerank_enabled: bool = False
    rerank_provider: str = "llm"
    rerank_top_n: int = 16
    min_rerank_score: float = 0.0


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
                published_at=(row.event_time or row.created_at).isoformat()
                if (row.event_time or row.created_at)
                else None,
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
                published_at=(row.event_time or row.created_at).isoformat()
                if (row.event_time or row.created_at)
                else None,
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
        raw_terms.extend(part.strip() for part in re.split(r"[，,、；;。\n\s]+", query) if part.strip())

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
        rrf_k=max(1, _int_option(fusion.get("rrf_k") or retrieval.get("rrf_k"), 60)),
        semantic_candidate_k=max(top_k, semantic_candidate_k),
        rerank_enabled=_bool_option(rerank.get("enabled") or retrieval.get("rerank_enabled")),
        rerank_provider=str(rerank.get("provider") or retrieval.get("rerank_provider") or "llm"),
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

    candidates: List[EvidenceSnippet] = []
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
        semantic_score = (
            _semantic_similarity(_semantic_query_text(query, retrieval_config), haystack)
            if _uses_semantic_retrieval(retrieval_config)
            else None
        )
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
        item.split(":", 1)[1] if item.startswith("ingestion:") else item
        for item in source_types
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
    ) -> None:
        self.retriever = retriever or DatabaseEvidenceRetriever()
        self.model_gateway = model_gateway or ModelGatewayImpl()
        self.max_parallel_sections = max(1, max_parallel_sections)

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

            title = str(config.get("title") or placeholder)
            if str(config.get("type") or "").lower() == "report_period":
                results_by_placeholder[placeholder] = PlaceholderGenerationOutput(
                    placeholder=placeholder,
                    content=resolve_report_period_value(config, active_period),
                )
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
            content = self._fallback_content(title, evidence)

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
        """Optionally rerank candidate evidence with an LLM before writing."""
        if not retrieval_config.rerank_enabled or len(evidence) <= 1:
            return evidence[:final_limit]
        if retrieval_config.rerank_provider.lower() != "llm":
            logger.warning(
                "Unsupported report evidence reranker, falling back",
                project=project.name,
                placeholder=placeholder,
                rerank_provider=retrieval_config.rerank_provider,
            )
            return evidence[:final_limit]

        candidates = evidence[: retrieval_config.rerank_top_n]
        try:
            messages = build_rerank_messages(
                title=title,
                query=query,
                evidence=candidates,
            )
            task_name = "reporting" if "reporting" in settings.TASK_ROUTES else "default"
            response = self.model_gateway.chat(
                messages=messages,
                task=task_name,
                temperature=0.0,
                max_tokens=max(300, min(1400, len(candidates) * 90)),
            )
            reranked = apply_llm_rerank_response(
                candidates,
                response.content,
                retrieval_config=retrieval_config,
                final_limit=final_limit,
            )
            if reranked:
                logger.info(
                    "Reranked report evidence",
                    project=project.name,
                    placeholder=placeholder,
                    candidate_count=len(candidates),
                    selected_count=len(reranked),
                )
                return reranked
        except Exception as exc:
            logger.warning(
                "Failed to rerank report evidence",
                project=project.name,
                placeholder=placeholder,
                error=str(exc),
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
            max_tokens=max(300, min(1200, max_words * 3)),
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
    def _fallback_content(title: str, evidence: List[EvidenceSnippet]) -> str:
        if not evidence:
            return f"{title}相关材料不足，暂无法形成基于事实的周报段落。"
        facts = "；".join(item.content[:80] for item in evidence[:3])
        return f"{title}方面，本周材料显示：{facts}。相关判断仍需结合后续数据验证。"

    @staticmethod
    def _clean_model_content(content: str, *, title: str) -> str:
        """Keep only the final report paragraph from a chat response."""
        text = content.strip()
        if not text:
            return ""
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


def compute_report_period(report_date: str | date | datetime | None = None) -> ReportPeriod:
    """Compute report week period from a report date.

    The report end date is the selected/generated date. The start date is the
    Monday of that same ISO week.
    """
    end_date = _coerce_report_date(report_date)
    start_date = end_date - timedelta(days=end_date.weekday())
    return ReportPeriod(start_date=start_date.isoformat(), end_date=end_date.isoformat())


def resolve_report_period_value(config: Dict[str, Any], report_period: ReportPeriod) -> str:
    """Resolve a configured report-period placeholder value."""
    field = str(config.get("field") or "").strip()
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


def build_a_share_market_data_sentence(project: ReportProject, config: Dict[str, Any]) -> str:
    """Build the deterministic A-share market review sentence from workbook cache."""
    try:
        from openpyxl import load_workbook
    except Exception as exc:  # pragma: no cover - dependency is available in project env.
        raise RuntimeError("openpyxl is required for composite market review") from exc

    data_source = config.get("data_source")
    data_config: Dict[str, Any] = data_source if isinstance(data_source, dict) else {}
    workbook_name = str(data_config.get("workbook") or project.excel_workbook_path.name)
    workbook_path = project.project_dir / "data" / workbook_name
    if not workbook_path.exists():
        workbook_path = project.excel_workbook_path

    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    domestic_sheet = str(data_config.get("domestic_sheet") or "国内")
    turnover_sheet = str(data_config.get("turnover_sheet") or "市场成交")
    domestic_rows = _read_market_index_rows(workbook[domestic_sheet])
    turnover = _read_turnover_row(workbook[turnover_sheet])
    if not domestic_rows:
        raise ValueError(f"No domestic index data found in {workbook_path}")

    index_sentence = "，".join(
        f"{name}{_direction_word(value)}{abs(value):.2f}%"
        for name, value in domestic_rows[:5]
    )
    trend = _market_trend_word([value for _, value in domestic_rows[:5]])
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
    data_template = str(get_component_by_type(config, "data_template").get("template") or "").strip()
    if data_template:
        return data_template.format_map(_SafeFormatDict(fields))
    return f"本周A股市场整体呈现{trend}趋势，主要指数表现不一：{index_sentence}。{turnover_sentence}"


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


def _read_turnover_row(worksheet: Any) -> tuple[float, float] | None:
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        current = _to_float(row[1] if len(row) > 1 else None)
        previous = _to_float(row[2] if len(row) > 2 else None)
        if current is not None and previous is not None:
            return current, previous
    return None


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
    section_config: Dict[str, Any]
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
    if placeholder_type not in {"prompt", "composite_market_review"}:
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
        merged["validators"] = deep_merge_dict(
            default_validators,
            merged.get("validators") if isinstance(merged.get("validators"), dict) else {},
        )

    default_retrieval = defaults.get("retrieval")
    if isinstance(default_retrieval, dict):
        merged["retrieval"] = deep_merge_dict(
            default_retrieval,
            merged.get("retrieval") if isinstance(merged.get("retrieval"), dict) else {},
        )
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
        config.get("prompt") or f"围绕{title}撰写正式周报段落，覆盖{facets_text}。严格依据证据材料，不输出投资建议。"
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

    if validators.get("forbid_external_facts") or validators.get("require_evidence_from_uploaded_material"):
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
    merged["retrieval"] = deep_merge_dict(
        merged.get("retrieval") if isinstance(merged.get("retrieval"), dict) else {},
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
        structure = _as_text_list(get_component_by_type(config, "llm_writing").get("writing_structure"))
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
    """Build messages for the generated part of a composite market review."""
    evidence_context = format_evidence_context(evidence)
    constraints_text = render_generation_constraints(config, max_words=max_words)
    writing_parameters_text = render_writing_parameters(config)
    writing_structure_text = render_market_review_writing_structure(config, template)
    user = f"""生成约束：
{constraints_text}

写作参数：
{writing_parameters_text}

固定开头：
以下内容已由系统根据 Excel 数据生成，必须作为正文开头，不得改写、删减或重复：
{data_sentence}

续写要求：
{writing_structure_text}
- 只续写固定开头之后的内容，不要重复固定开头
- 续写内容需要和固定开头自然衔接，最终形成一段完整正文
- 不要输出标题、编号、项目符号、解释过程或换行符

Evidence：
{evidence_context}

请只输出固定开头之后的续写正文。"""
    return [
        {"role": "user", "content": user},
    ]


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
