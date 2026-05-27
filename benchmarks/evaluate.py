#!/usr/bin/env python
"""Benchmark evaluation script for AlphaFoundry.

Loads gold datasets, runs EventExtractor (keyword mode, no LLM required),
and reports precision/recall/F1 metrics.

Usage:
    python benchmarks/evaluate.py
    python benchmarks/evaluate.py --dataset event_extraction_v1
    python benchmarks/evaluate.py --dataset subject_mapping_v1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from benchmarks.SCHEMA import BenchmarkCase, BenchmarkResult, compute_prf, compute_thesis_similarity
from core.observability import get_logger
from services.event_extractor import EventExtractor

logger = get_logger(__name__)

DATASETS_DIR = Path(__file__).parent / "datasets"


def load_dataset(dataset_name: str) -> list[BenchmarkCase]:
    """Load a JSONL benchmark dataset.

    Args:
        dataset_name: Dataset filename without extension (e.g. 'event_extraction_v1').

    Returns:
        List of BenchmarkCase instances.
    """
    filepath = DATASETS_DIR / f"{dataset_name}.jsonl"
    if not filepath.exists():
        logger.error("Dataset file not found", path=str(filepath))
        raise FileNotFoundError(f"Dataset not found: {filepath}")

    cases: list[BenchmarkCase] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                case = BenchmarkCase(**data)
                cases.append(case)
            except Exception as exc:
                logger.error(
                    "Failed to parse benchmark case",
                    dataset=dataset_name,
                    line=line_num,
                    error=str(exc),
                )
                raise

    logger.info(
        "Loaded benchmark dataset",
        dataset=dataset_name,
        cases=len(cases),
    )
    return cases


async def evaluate_dataset(dataset_name: str) -> BenchmarkResult:
    """Run evaluation on a single dataset.

    Args:
        dataset_name: Dataset filename without extension.

    Returns:
        BenchmarkResult with computed metrics.
    """
    cases = load_dataset(dataset_name)
    extractor = EventExtractor(model_gateway=None)  # keyword mode only

    # Per-case accumulators
    event_type_correct = 0
    subject_precisions: list[float] = []
    subject_recalls: list[float] = []
    subject_f1s: list[float] = []
    thesis_similarities: list[float] = []

    # Grouped accumulators
    by_event_type: dict[str, dict[str, list[float]]] = {}
    by_source_type: dict[str, dict[str, list[float]]] = {}

    for case in cases:
        prediction = await extractor.extract(case.input_text)
        gold = case.gold

        # 1. Event type accuracy
        et_correct = 1 if prediction.event_type == gold.event_type else 0
        event_type_correct += et_correct

        # 2. Subject ID PRF
        p, r, f1 = compute_prf(prediction.subject_ids, gold.subject_ids)
        subject_precisions.append(p)
        subject_recalls.append(r)
        subject_f1s.append(f1)

        # 3. Thesis similarity
        sim = compute_thesis_similarity(prediction.thesis, gold.thesis)
        thesis_similarities.append(sim)

        # 4. Group by event_type
        et = gold.event_type
        if et not in by_event_type:
            by_event_type[et] = {
                "et_correct": [],
                "precision": [],
                "recall": [],
                "f1": [],
                "thesis_sim": [],
            }
        by_event_type[et]["et_correct"].append(float(et_correct))
        by_event_type[et]["precision"].append(p)
        by_event_type[et]["recall"].append(r)
        by_event_type[et]["f1"].append(f1)
        by_event_type[et]["thesis_sim"].append(sim)

        # 5. Group by source_type
        st = case.source_type
        if st not in by_source_type:
            by_source_type[st] = {
                "et_correct": [],
                "precision": [],
                "recall": [],
                "f1": [],
                "thesis_sim": [],
            }
        by_source_type[st]["et_correct"].append(float(et_correct))
        by_source_type[st]["precision"].append(p)
        by_source_type[st]["recall"].append(r)
        by_source_type[st]["f1"].append(f1)
        by_source_type[st]["thesis_sim"].append(sim)

    n = len(cases)

    def _avg(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    def _summarize_group(group: dict[str, list[float]]) -> dict[str, Any]:
        return {
            "count": len(group["et_correct"]),
            "event_type_accuracy": _avg(group["et_correct"]),
            "subject_id_precision": _avg(group["precision"]),
            "subject_id_recall": _avg(group["recall"]),
            "subject_id_f1": _avg(group["f1"]),
            "thesis_similarity_avg": _avg(group["thesis_sim"]),
        }

    result = BenchmarkResult(
        dataset_name=dataset_name,
        total_cases=n,
        event_type_accuracy=event_type_correct / n if n else 0.0,
        subject_id_precision=_avg(subject_precisions),
        subject_id_recall=_avg(subject_recalls),
        subject_id_f1=_avg(subject_f1s),
        thesis_similarity_avg=_avg(thesis_similarities),
        per_event_type={k: _summarize_group(v) for k, v in by_event_type.items()},
        per_source_type={k: _summarize_group(v) for k, v in by_source_type.items()},
    )

    return result


def print_result(result: BenchmarkResult) -> None:
    """Print a benchmark result in human-readable format."""
    logger.info("=" * 60)
    logger.info("Benchmark Result: %s", result.dataset_name)
    logger.info("=" * 60)
    logger.info("Total cases: %d", result.total_cases)
    logger.info("Event Type Accuracy:    %.4f", result.event_type_accuracy)
    logger.info("Subject ID Precision:   %.4f", result.subject_id_precision)
    logger.info("Subject ID Recall:      %.4f", result.subject_id_recall)
    logger.info("Subject ID F1:          %.4f", result.subject_id_f1)
    logger.info("Thesis Similarity Avg:  %.4f", result.thesis_similarity_avg)

    if result.per_event_type:
        logger.info("-" * 40)
        logger.info("By Event Type:")
        for et, metrics in result.per_event_type.items():
            logger.info(
                "  %-25s n=%2d  acc=%.3f  p=%.3f  r=%.3f  f1=%.3f  sim=%.3f",
                et,
                metrics["count"],
                metrics["event_type_accuracy"],
                metrics["subject_id_precision"],
                metrics["subject_id_recall"],
                metrics["subject_id_f1"],
                metrics["thesis_similarity_avg"],
            )

    if result.per_source_type:
        logger.info("-" * 40)
        logger.info("By Source Type:")
        for st, metrics in result.per_source_type.items():
            logger.info(
                "  %-25s n=%2d  acc=%.3f  p=%.3f  r=%.3f  f1=%.3f  sim=%.3f",
                st,
                metrics["count"],
                metrics["event_type_accuracy"],
                metrics["subject_id_precision"],
                metrics["subject_id_recall"],
                metrics["subject_id_f1"],
                metrics["thesis_similarity_avg"],
            )

    logger.info("=" * 60)


async def main() -> None:
    """Main entry point for benchmark evaluation."""
    parser = argparse.ArgumentParser(description="AlphaFoundry Benchmark Evaluation")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Dataset name (without .jsonl). If omitted, runs all datasets.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable format.",
    )
    args = parser.parse_args()

    if args.dataset:
        datasets = [args.dataset]
    else:
        # Discover all .jsonl files in datasets/
        datasets = sorted(f.stem for f in DATASETS_DIR.glob("*.jsonl") if f.is_file())

    if not datasets:
        logger.error("No datasets found in %s", DATASETS_DIR)
        sys.exit(1)

    results: list[BenchmarkResult] = []
    for ds_name in datasets:
        result = await evaluate_dataset(ds_name)
        results.append(result)

        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
