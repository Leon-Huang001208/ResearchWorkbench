"""Benchmark data schema and evaluation metrics for AlphaFoundry.

Provides Pydantic models for benchmark cases and results, along with
metric computation utilities.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from core.services.event_extractor import ExtractedSignalParams


class BenchmarkCase(BaseModel):
    """A single benchmark test case with gold-standard annotation."""

    case_id: str
    input_text: str
    source_type: str  # news, report, announcement
    gold: ExtractedSignalParams


class PerGroupMetrics(BaseModel):
    """Metrics for a single group (e.g. one event_type or source_type)."""

    count: int = 0
    event_type_accuracy: float = 0.0
    subject_id_precision: float = 0.0
    subject_id_recall: float = 0.0
    subject_id_f1: float = 0.0
    thesis_similarity_avg: float = 0.0


class BenchmarkResult(BaseModel):
    """Evaluation result for a benchmark run."""

    dataset_name: str
    total_cases: int
    event_type_accuracy: float
    subject_id_precision: float
    subject_id_recall: float
    subject_id_f1: float
    thesis_similarity_avg: float
    per_event_type: dict[str, dict[str, Any]] = Field(default_factory=dict)
    per_source_type: dict[str, dict[str, Any]] = Field(default_factory=dict)


# ── Chinese text tokenization (character-level for keyword overlap) ──────
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def _tokenize_chinese(text: str) -> set[str]:
    """Tokenize Chinese text into individual characters + ASCII words.

    Simple approach: split CJK into individual characters, keep ASCII words.
    Good enough for Jaccard-based thesis similarity.
    """
    tokens: set[str] = set()
    # Extract CJK characters
    for ch in text:
        if _CJK_PATTERN.match(ch):
            tokens.add(ch)
    # Extract ASCII words
    ascii_words = re.findall(r"[a-zA-Z0-9]+", text)
    tokens.update(w.lower() for w in ascii_words)
    return tokens


def compute_prf(predicted: list[str], actual: list[str]) -> tuple[float, float, float]:
    """Compute precision, recall, and F1 for two string lists.

    Returns:
        (precision, recall, f1) tuple.
    """
    if not predicted and not actual:
        return (1.0, 1.0, 1.0)
    if not predicted:
        return (0.0, 0.0, 0.0)
    if not actual:
        return (0.0, 0.0, 0.0)

    pred_set = set(predicted)
    actual_set = set(actual)
    true_pos = len(pred_set & actual_set)

    precision = true_pos / len(pred_set) if pred_set else 0.0
    recall = true_pos / len(actual_set) if actual_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return (precision, recall, f1)


def compute_thesis_similarity(predicted: str, gold: str) -> float:
    """Compute Jaccard similarity between predicted and gold thesis texts.

    Uses character-level tokenization for Chinese text.
    """
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0

    pred_tokens = _tokenize_chinese(predicted)
    gold_tokens = _tokenize_chinese(gold)

    if not pred_tokens and not gold_tokens:
        return 1.0

    intersection = pred_tokens & gold_tokens
    union = pred_tokens | gold_tokens
    return len(intersection) / len(union) if union else 0.0
