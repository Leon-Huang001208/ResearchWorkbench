"""Unit tests for benchmark datasets and evaluation utilities.

Validates:
1. Gold datasets parse correctly into BenchmarkCase models
2. Evaluation script runs end-to-end
3. Metric computation functions (compute_prf, compute_thesis_similarity) are correct
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from benchmarks.evaluate import evaluate_dataset, load_dataset
from benchmarks.SCHEMA import BenchmarkCase, BenchmarkResult, compute_prf, compute_thesis_similarity

DATASETS_DIR = Path(__file__).parent.parent.parent / "benchmarks" / "datasets"


# ── Metric function tests ─────────────────────────────────────────────────


class TestComputePRF:
    """Tests for compute_prf (precision, recall, F1)."""

    def test_perfect_match(self) -> None:
        p, r, f1 = compute_prf(["a", "b"], ["a", "b"])
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_partial_match(self) -> None:
        p, r, f1 = compute_prf(["a", "b"], ["b", "c"])
        # pred={a,b}, actual={b,c}, TP={b}
        assert p == 0.5  # 1/2
        assert r == 0.5  # 1/2
        assert f1 == 0.5  # 2*0.5*0.5/(0.5+0.5)

    def test_no_overlap(self) -> None:
        p, r, f1 = compute_prf(["a"], ["b"])
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_both_empty(self) -> None:
        p, r, f1 = compute_prf([], [])
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_predicted_empty_actual_not(self) -> None:
        p, r, f1 = compute_prf([], ["a"])
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_actual_empty_predicted_not(self) -> None:
        p, r, f1 = compute_prf(["a"], [])
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_superset_prediction(self) -> None:
        p, r, f1 = compute_prf(["a", "b", "c"], ["a", "b"])
        assert p == pytest.approx(2 / 3)
        assert r == 1.0
        assert f1 == pytest.approx(2 * (2 / 3) * 1.0 / (2 / 3 + 1.0))

    def test_subset_prediction(self) -> None:
        p, r, f1 = compute_prf(["a"], ["a", "b", "c"])
        assert p == 1.0
        assert r == pytest.approx(1 / 3)
        assert f1 == pytest.approx(2 * 1.0 * (1 / 3) / (1.0 + 1 / 3))

    def test_with_stock_codes(self) -> None:
        p, r, f1 = compute_prf(
            ["600000.SH", "601398.SH", "000002.SZ"],
            ["600000.SH", "601398.SH"],
        )
        assert p == pytest.approx(2 / 3)
        assert r == 1.0


class TestThesisSimilarity:
    """Tests for compute_thesis_similarity."""

    def test_identical(self) -> None:
        sim = compute_thesis_similarity("政策利好银行", "政策利好银行")
        assert sim == 1.0

    def test_no_overlap(self) -> None:
        sim = compute_thesis_similarity("降准利好", "加息利空")
        # CJK chars: {降,准,利,好} vs {加,息,利,空} → intersection={利} → 1/7
        assert 0.0 < sim < 1.0

    def test_both_empty(self) -> None:
        sim = compute_thesis_similarity("", "")
        assert sim == 1.0

    def test_one_empty(self) -> None:
        sim = compute_thesis_similarity("测试", "")
        assert sim == 0.0

    def test_partial_overlap(self) -> None:
        sim = compute_thesis_similarity("降准利好银行股", "降息利好保险股")
        # Common chars: {降,利,好,股} → should be > 0
        assert sim > 0.0
        assert sim < 1.0


# ── Gold dataset parsing tests ────────────────────────────────────────────


class TestGoldDatasetParsing:
    """Validate that gold datasets can be parsed into BenchmarkCase models."""

    @pytest.mark.parametrize(
        "dataset_file",
        [
            "event_extraction_v1.jsonl",
            "subject_mapping_v1.jsonl",
        ],
    )
    def test_dataset_loads(self, dataset_file: str) -> None:
        filepath = DATASETS_DIR / dataset_file
        assert filepath.exists(), f"Dataset file missing: {filepath}"

        cases: list[BenchmarkCase] = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                case = BenchmarkCase(**data)
                cases.append(case)

        assert len(cases) > 0, f"Dataset {dataset_file} is empty"

    def test_event_extraction_min_count(self) -> None:
        """Event extraction dataset should have at least 20 cases."""
        cases = load_dataset("event_extraction_v1")
        assert len(cases) >= 20, f"event_extraction_v1 has only {len(cases)} cases, expected >= 20"

    def test_subject_mapping_min_count(self) -> None:
        """Subject mapping dataset should have at least 15 cases."""
        cases = load_dataset("subject_mapping_v1")
        assert len(cases) >= 15, f"subject_mapping_v1 has only {len(cases)} cases, expected >= 15"

    @pytest.mark.parametrize(
        "dataset_file",
        [
            "event_extraction_v1.jsonl",
            "subject_mapping_v1.jsonl",
        ],
    )
    def test_case_ids_unique(self, dataset_file: str) -> None:
        """All case_ids within a dataset should be unique."""
        cases = load_dataset(dataset_file.replace(".jsonl", ""))
        case_ids = [c.case_id for c in cases]
        assert len(case_ids) == len(set(case_ids)), "Duplicate case_ids found"

    @pytest.mark.parametrize(
        "dataset_file",
        [
            "event_extraction_v1.jsonl",
            "subject_mapping_v1.jsonl",
        ],
    )
    def test_source_types_valid(self, dataset_file: str) -> None:
        """Source types should be one of: news, report, announcement."""
        valid_types = {"news", "report", "announcement"}
        cases = load_dataset(dataset_file.replace(".jsonl", ""))
        for case in cases:
            assert (
                case.source_type in valid_types
            ), f"Invalid source_type '{case.source_type}' in {case.case_id}"

    @pytest.mark.parametrize(
        "dataset_file",
        [
            "event_extraction_v1.jsonl",
            "subject_mapping_v1.jsonl",
        ],
    )
    def test_event_types_valid(self, dataset_file: str) -> None:
        """Gold event_type should be from the standard set."""
        valid_types = {
            "earnings",
            "policy",
            "product",
            "merger_acquisition",
            "rating_change",
            "supply_chain",
            "macro",
        }
        cases = load_dataset(dataset_file.replace(".jsonl", ""))
        for case in cases:
            assert (
                case.gold.event_type in valid_types
            ), f"Invalid event_type '{case.gold.event_type}' in {case.case_id}"

    def test_event_extraction_covers_multiple_event_types(self) -> None:
        """Event extraction should cover at least 5 distinct event types."""
        cases = load_dataset("event_extraction_v1")
        event_types = {c.gold.event_type for c in cases}
        assert len(event_types) >= 5, f"Only {len(event_types)} event types covered: {event_types}"

    def test_event_extraction_covers_multiple_source_types(self) -> None:
        """Event extraction should cover at least 2 distinct source types."""
        cases = load_dataset("event_extraction_v1")
        source_types = {c.source_type for c in cases}
        assert (
            len(source_types) >= 2
        ), f"Only {len(source_types)} source types covered: {source_types}"


# ── Evaluation script tests ──────────────────────────────────────────────


class TestEvaluateScript:
    """Test that the evaluation script runs and produces valid results."""

    def test_evaluate_event_extraction(self) -> None:
        """Run evaluation on event_extraction_v1 and check result structure."""
        result = asyncio.run(evaluate_dataset("event_extraction_v1"))
        assert isinstance(result, BenchmarkResult)
        assert result.dataset_name == "event_extraction_v1"
        assert result.total_cases >= 20
        assert 0.0 <= result.event_type_accuracy <= 1.0
        assert 0.0 <= result.subject_id_precision <= 1.0
        assert 0.0 <= result.subject_id_recall <= 1.0
        assert 0.0 <= result.subject_id_f1 <= 1.0
        assert 0.0 <= result.thesis_similarity_avg <= 1.0

    def test_evaluate_subject_mapping(self) -> None:
        """Run evaluation on subject_mapping_v1 and check result structure."""
        result = asyncio.run(evaluate_dataset("subject_mapping_v1"))
        assert isinstance(result, BenchmarkResult)
        assert result.dataset_name == "subject_mapping_v1"
        assert result.total_cases >= 15
        assert 0.0 <= result.event_type_accuracy <= 1.0
        assert 0.0 <= result.subject_id_precision <= 1.0
        assert 0.0 <= result.subject_id_recall <= 1.0
        assert 0.0 <= result.subject_id_f1 <= 1.0
        assert 0.0 <= result.thesis_similarity_avg <= 1.0

    def test_evaluate_with_temp_dataset(self) -> None:
        """Test evaluation with a minimal temporary dataset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "test_mini.jsonl"
            case_data = {
                "case_id": "test_001",
                "input_text": "降准利好银行，600000.SH盘中上涨",
                "source_type": "news",
                "gold": {
                    "event_type": "policy",
                    "subject_ids": ["600000.SH"],
                    "thesis": "降准利好银行",
                    "impact_path": ["降准→银行利好"],
                    "bullish_companies": ["600000.SH"],
                    "bearish_companies": [],
                    "score": 0.7,
                    "confidence": 0.6,
                    "diffusion_stage": "early_awareness",
                    "industry_impacts": ["finance"],
                    "market_regime": None,
                },
            }
            dataset_path.write_text(
                json.dumps(case_data, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            # Temporarily patch the DATASETS_DIR
            import benchmarks.evaluate as eval_module

            original_dir = eval_module.DATASETS_DIR
            eval_module.DATASETS_DIR = Path(tmpdir)
            try:
                result = asyncio.run(evaluate_dataset("test_mini"))
                assert result.total_cases == 1
                assert 0.0 <= result.event_type_accuracy <= 1.0
            finally:
                eval_module.DATASETS_DIR = original_dir


# ── BenchmarkResult model tests ──────────────────────────────────────────


class TestBenchmarkResultModel:
    """Test BenchmarkResult model serialization."""

    def test_result_serialization(self) -> None:
        result = BenchmarkResult(
            dataset_name="test",
            total_cases=10,
            event_type_accuracy=0.8,
            subject_id_precision=0.7,
            subject_id_recall=0.6,
            subject_id_f1=0.65,
            thesis_similarity_avg=0.5,
        )
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["dataset_name"] == "test"
        assert parsed["total_cases"] == 10

    def test_result_with_groups(self) -> None:
        result = BenchmarkResult(
            dataset_name="test",
            total_cases=5,
            event_type_accuracy=0.6,
            subject_id_precision=0.5,
            subject_id_recall=0.4,
            subject_id_f1=0.44,
            thesis_similarity_avg=0.3,
            per_event_type={
                "earnings": {
                    "count": 3,
                    "event_type_accuracy": 0.67,
                    "subject_id_precision": 0.5,
                    "subject_id_recall": 0.4,
                    "subject_id_f1": 0.44,
                    "thesis_similarity_avg": 0.3,
                }
            },
        )
        assert "earnings" in result.per_event_type
