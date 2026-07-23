"""Report-style news evidence selection for market commentary."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from core.contracts.commentary import CommentaryEvidenceItem

COMMENTARY_RETRIEVAL_TERMS: dict[str, list[str]] = {
    "daily-close": [
        "Meta",
        "OpenAI",
        "英伟达",
        "NVIDIA",
        "美股",
        "纳指",
        "科技股",
        "AI",
        "人工智能",
        "算力",
        "半导体",
        "资本开支",
        "政策",
        "监管",
        "流动性",
        "降息",
        "汇率",
        "人民币",
        "财报",
        "订单",
        "关税",
    ],
    "market-drawdown": [
        "Meta",
        "OpenAI",
        "英伟达",
        "NVIDIA",
        "美股",
        "纳指",
        "科技股",
        "AI",
        "人工智能",
        "算力",
        "半导体",
        "资本开支",
        "大跌",
        "下跌",
        "暴跌",
        "调整",
        "抛售",
        "风险偏好",
        "流动性",
        "监管",
        "财报",
        "业绩",
    ],
    "sector-review": [
        "政策",
        "产业",
        "订单",
        "财报",
        "业绩",
        "涨价",
        "供需",
        "库存",
        "景气",
        "估值",
        "催化",
        "监管",
    ],
    "theme-event": [
        "政策",
        "发布",
        "订单",
        "产业链",
        "供需",
        "催化",
        "监管",
        "财报",
        "AI",
        "算力",
        "半导体",
    ],
    "global-shock": [
        "美股",
        "纳指",
        "科技股",
        "Meta",
        "OpenAI",
        "英伟达",
        "NVIDIA",
        "AI",
        "资本开支",
        "美元",
        "美债",
        "降息",
        "关税",
        "地缘",
    ],
}

DEFAULT_COMMENTARY_TERMS = COMMENTARY_RETRIEVAL_TERMS["daily-close"]


class CommentaryNewsSelector:
    """Select market-moving news with the report retrieval ranking primitive."""

    def select(
        self,
        items: Iterable[CommentaryEvidenceItem],
        *,
        recipe_id: str,
        limit: int = 6,
        extra_terms: Iterable[str] | None = None,
    ) -> list[CommentaryEvidenceItem]:
        from reporting.projects.generation import (
            EvidenceSnippet,
            RetrievalConfig,
            filter_and_rank_evidence,
        )

        reported_items = [item for item in items if item.source_type in {"news", "research"}]
        if not reported_items:
            return []

        dynamic_terms = _unique_terms(extra_terms or [])
        terms = _unique_terms(
            [*dynamic_terms, *COMMENTARY_RETRIEVAL_TERMS.get(recipe_id, DEFAULT_COMMENTARY_TERMS)]
        )
        config = RetrievalConfig(
            mode="keyword",
            top_k=limit,
            candidate_k=max(50, limit * 8),
            must_any=terms,
            min_keyword_score=1.0,
        )
        snippet_lookup: dict[str, CommentaryEvidenceItem] = {}
        snippets: list[EvidenceSnippet] = []
        for index, item in enumerate(reported_items):
            source_key = f"commentary:{index}:{item.source_type}"
            snippet_lookup[source_key] = item
            snippets.append(
                EvidenceSnippet(
                    source=source_key,
                    title=item.title,
                    content=item.summary,
                    published_at=str(item.metadata.get("published_at") or ""),
                    url=item.url,
                )
            )

        ranked = filter_and_rank_evidence(
            snippets,
            config,
            query=" ".join(terms),
        )
        selected = [
            self._attach_retrieval_metadata(
                snippet_lookup[snippet.source],
                snippet,
                dynamic_terms=dynamic_terms,
            )
            for snippet in ranked
            if snippet.source in snippet_lookup
        ]
        selected = self._dedupe_similar_events(selected)
        if len(selected) < limit:
            selected.extend(
                item for item in self._fallback_rank(reported_items) if item not in selected
            )
            selected = self._dedupe_similar_events(selected)
        return selected[:limit]

    @staticmethod
    def _attach_retrieval_metadata(
        item: CommentaryEvidenceItem,
        snippet: EvidenceSnippet,
        *,
        dynamic_terms: list[str],
    ) -> CommentaryEvidenceItem:
        metadata = {
            **item.metadata,
            "matched_terms": list(snippet.matched_terms),
            "dynamic_terms": dynamic_terms,
            "keyword_score": snippet.keyword_score,
            "retrieval_score": snippet.retrieval_score,
            "retrieval_rank": snippet.retrieval_rank,
            "retrieval_method": snippet.retrieval_method,
        }
        score = _market_moving_score(item) + float(snippet.keyword_score or 0.0)
        return item.model_copy(
            update={
                "confidence_score": min(0.9, max(item.confidence_score, 0.62 + score / 100)),
                "metadata": metadata,
            }
        )

    @staticmethod
    def _fallback_rank(
        items: list[CommentaryEvidenceItem],
    ) -> list[CommentaryEvidenceItem]:
        return sorted(
            items,
            key=lambda item: (
                _market_moving_score(item),
                item.confidence_score,
                _published_at_sort_key(item),
            ),
            reverse=True,
        )

    @staticmethod
    def _dedupe_similar_events(
        items: list[CommentaryEvidenceItem],
    ) -> list[CommentaryEvidenceItem]:
        selected: list[CommentaryEvidenceItem] = []
        seen_titles: list[str] = []
        for item in items:
            normalized = _normalize_event_title(item.title)
            if any(_looks_like_same_event(normalized, seen) for seen in seen_titles):
                continue
            selected.append(item)
            seen_titles.append(normalized)
        return selected


def _market_moving_score(item: CommentaryEvidenceItem) -> float:
    text = f"{item.title} {item.summary}".lower()
    entity_terms = (
        "meta",
        "openai",
        "nvidia",
        "英伟达",
        "美股",
        "纳指",
        "科技股",
        "半导体",
        "ai",
        "人工智能",
        "算力",
    )
    action_terms = (
        "大跌",
        "下跌",
        "暴跌",
        "调整",
        "抛售",
        "承压",
        "上修",
        "资本开支",
        "监管",
        "财报",
        "业绩",
    )
    score = 0.0
    score += sum(8.0 for term in entity_terms if term in text)
    score += sum(5.0 for term in action_terms if term in text)
    if item.source_type == "research":
        score += 4.0
    return score


def _unique_terms(terms: Iterable[str]) -> list[str]:
    unique: list[str] = []
    for raw_term in terms:
        term = str(raw_term or "").strip()
        if not term or term in unique:
            continue
        unique.append(term)
    return unique


def _published_at_sort_key(item: CommentaryEvidenceItem) -> str:
    raw = str(item.metadata.get("published_at") or "")
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return raw


def _normalize_event_title(title: str) -> str:
    return "".join(ch for ch in str(title or "").lower() if ch.isalnum())


def _looks_like_same_event(left: str, right: str) -> bool:
    if not left or not right:
        return False
    shorter, longer = sorted([left, right], key=len)
    if len(shorter) < 10:
        return shorter == longer
    return shorter in longer or _prefix_overlap(shorter, longer) >= 0.82


def _prefix_overlap(left: str, right: str) -> float:
    count = 0
    for left_char, right_char in zip(left, right):
        if left_char != right_char:
            break
        count += 1
    return count / max(1, len(left))
