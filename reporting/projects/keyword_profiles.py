"""Keyword profile helpers for report project retrieval.

Profiles are reusable search presets derived from the old CLS filtering
configuration. A report placeholder can inherit one by name, and unknown
placeholders receive a small editable draft instead of an empty retrieval box.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from core.observability import get_logger

logger = get_logger(__name__)

PROFILE_PATH = Path(__file__).with_name("keyword_profiles.json")

MARKET_HOTSPOT_KEYWORDS = [
    "CPO",
    "算力",
    "人工智能",
    "AI",
    "先进封装",
    "半导体",
    "光模块",
    "机器人",
    "低空经济",
    "新能源",
    "消费",
    "医药",
    "黄金",
    "原油",
]


@dataclass(frozen=True)
class KeywordProfile:
    """Reusable retrieval keyword profile."""

    name: str
    param: str
    keywords: List[str]
    query: str
    threshold: float
    source: str = "keyword_profiles"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile for API responses."""
        return {
            "name": self.name,
            "param": self.param,
            "keywords": list(self.keywords),
            "query": self.query,
            "threshold": self.threshold,
            "source": self.source,
        }


def normalize_profile_key(value: str) -> str:
    """Normalize placeholder/profile names for loose matching."""
    text = str(value or "").strip()
    text = re.sub(r"^\{\{\s*|\s*\}\}$", "", text)
    text = re.sub(r"[\s_\-（）()【】\\[\\]：:]+", "", text)
    return text.lower()


@lru_cache(maxsize=1)
def load_keyword_profiles() -> Dict[str, KeywordProfile]:
    """Load built-in keyword profiles from JSON."""
    try:
        raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Keyword profile file missing", path=str(PROFILE_PATH))
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Invalid keyword profile JSON", path=str(PROFILE_PATH), error=str(exc))
        return {}

    profiles: Dict[str, KeywordProfile] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            continue
        keywords = _dedupe_strings(item.get("KEYWORDS") or item.get("keywords") or [])
        if not keywords:
            continue
        query = str(item.get("QUERY") or item.get("query") or name).strip()
        threshold = _safe_float(item.get("THRESHOLD") or item.get("threshold"), 0.5)
        profile = KeywordProfile(
            name=str(name),
            param=str(item.get("PARAM") or item.get("param") or name),
            keywords=keywords,
            query=query,
            threshold=threshold,
        )
        for key in {profile.name, profile.param, normalize_profile_key(profile.name)}:
            normalized = normalize_profile_key(key)
            if normalized:
                profiles[normalized] = profile

    _add_alias(profiles, "原油", "石油")
    _add_alias(profiles, "港股", "香港")
    _add_alias(profiles, "医药生物", "医药生物")
    _add_market_review_profile(profiles)
    return profiles


def keyword_profiles_for_api() -> Dict[str, Dict[str, Any]]:
    """Return a stable profile dictionary keyed by display name."""
    unique: Dict[str, KeywordProfile] = {}
    for profile in load_keyword_profiles().values():
        unique[profile.name] = profile
    return {name: profile.to_dict() for name, profile in sorted(unique.items())}


def resolve_keyword_profile(name: str) -> KeywordProfile | None:
    """Resolve the best profile for a placeholder name."""
    profiles = load_keyword_profiles()
    normalized = normalize_profile_key(name)
    if not normalized:
        return None
    if normalized in profiles:
        return profiles[normalized]
    for key, profile in profiles.items():
        if key and (key in normalized or normalized in key):
            return profile
    return None


def suggest_keywords_for_placeholder(
    placeholder: str,
    *,
    prompt_text: str = "",
    max_terms: int = 24,
) -> Dict[str, Any]:
    """Suggest retrieval keywords for a placeholder.

    Known placeholders inherit the curated profile. Unknown placeholders get a
    deterministic draft built from the placeholder and prompt words, so it can
    be saved and improved later without blocking template setup.
    """
    profile = resolve_keyword_profile(placeholder)
    if profile:
        return {
            "profile": profile.name,
            "keywords": profile.keywords[:max_terms],
            "query": profile.query,
            "threshold": profile.threshold,
            "source": profile.source,
            "needs_review": False,
        }

    terms = _dedupe_strings([placeholder, *_extract_terms(prompt_text)])
    if not terms:
        terms = [str(placeholder).strip()]
    title = str(placeholder).strip()
    return {
        "profile": None,
        "keywords": terms[:max_terms],
        "query": f"{title}最新动态，覆盖政策、产业趋势、供需变化和市场影响",
        "threshold": 0.5,
        "source": "generated_draft",
        "needs_review": True,
    }


def apply_keyword_profile_to_config(
    placeholder: str,
    config: Dict[str, Any],
    *,
    prompt_text: str = "",
) -> Dict[str, Any]:
    """Return a config copy with missing retrieval keywords filled from profile."""
    next_config = dict(config)
    retrieval = dict(next_config.get("retrieval") or {})
    query_terms = dict(retrieval.get("query_terms") or {})
    existing_keywords = _dedupe_strings(
        retrieval.get("keywords") or query_terms.get("must_any") or retrieval.get("must_any")
    )
    if existing_keywords:
        return next_config

    profile_name = str(retrieval.get("keyword_profile") or "").strip()
    if profile_name:
        profile = resolve_keyword_profile(profile_name)
        suggestion = (
            {
                "profile": profile.name,
                "keywords": profile.keywords,
                "query": profile.query,
                "threshold": profile.threshold,
                "source": profile.source,
                "needs_review": False,
            }
            if profile
            else suggest_keywords_for_placeholder(placeholder, prompt_text=prompt_text)
        )
    else:
        suggestion = suggest_keywords_for_placeholder(placeholder, prompt_text=prompt_text)
    keywords = _dedupe_strings(suggestion.get("keywords"))
    if not keywords:
        return next_config

    retrieval.setdefault("mode", "hybrid")
    retrieval.setdefault("top_k", 8)
    retrieval.setdefault("candidate_k", 50)
    retrieval.setdefault("semantic_candidate_k", 100)
    retrieval.setdefault("min_keyword_score", 1)
    retrieval.setdefault(
        "fusion",
        {"method": "rrf", "keyword_weight": 0.65, "semantic_weight": 0.35, "rrf_k": 60},
    )
    retrieval.setdefault(
        "rerank", {"enabled": True, "provider": "llm", "top_n": 16, "min_score": 30}
    )
    retrieval["keywords"] = keywords
    if query_terms:
        query_terms.pop("must_any", None)
        if query_terms:
            retrieval["query_terms"] = query_terms
        else:
            retrieval.pop("query_terms", None)
    retrieval["keyword_profile"] = suggestion.get("profile")
    retrieval["keyword_profile_source"] = suggestion.get("source")
    if suggestion.get("needs_review"):
        retrieval["keyword_profile_needs_review"] = True
    next_config["retrieval"] = retrieval
    if suggestion.get("query") and not next_config.get("query"):
        next_config["query"] = suggestion["query"]
    return next_config


def _add_alias(profiles: Dict[str, KeywordProfile], alias: str, target: str) -> None:
    target_profile = profiles.get(normalize_profile_key(target))
    if target_profile:
        profiles[normalize_profile_key(alias)] = target_profile


def _add_market_review_profile(profiles: Dict[str, KeywordProfile]) -> None:
    china_profile = profiles.get(normalize_profile_key("中国"))
    keywords = _dedupe_strings(
        [*MARKET_HOTSPOT_KEYWORDS, *(china_profile.keywords if china_profile else [])]
    )
    if not keywords:
        return
    profile = KeywordProfile(
        name="A股市场回顾",
        param="A股市场回顾",
        keywords=keywords,
        query=(
            "A股市场热点和板块轮动最新动态，涵盖政策、产业趋势、"
            "成长板块、价值板块、主题概念和风险偏好变化"
        ),
        threshold=0.5,
    )
    for alias in ["A股市场回顾", "A股", "A股市场", "市场热点"]:
        profiles[normalize_profile_key(alias)] = profile


def _extract_terms(text: str) -> Iterable[str]:
    for item in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", str(text or "")):
        if item in {"检索", "Query", "写作", "要求", "格式", "本周", "最新", "动态"}:
            continue
        yield item


def _dedupe_strings(values: Any) -> List[str]:
    if isinstance(values, str):
        values = re.split(r"[\n,，、；;]+", values)
    if not isinstance(values, Iterable):
        return []
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
