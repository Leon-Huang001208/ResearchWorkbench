from pathlib import Path

import pytest

SHARED = Path(__file__).parents[2] / "app/research_web/skills/_shared"


def test_cpu_budget_accepts_every_exact_boundary():
    from app.research_web.skills._shared.cpu_budget import WorkloadBudget

    budget = WorkloadBudget()
    budget.add_input(rows=50_000, bytes_count=64 * 1024 * 1024)
    budget.validate_series(5_000)
    budget.validate_batch(symbol_count=50, rows_per_symbol=1_000)
    budget.add_artifact(16 * 1024 * 1024)


@pytest.mark.parametrize(
    "operation,metadata_key",
    [
        (lambda budget: budget.add_input(rows=50_001, bytes_count=1), "max_rows"),
        (
            lambda budget: budget.add_input(rows=1, bytes_count=64 * 1024 * 1024 + 1),
            "max_input_bytes",
        ),
        (lambda budget: budget.validate_series(5_001), "max_series_rows"),
        (lambda budget: budget.validate_batch(symbol_count=51, rows_per_symbol=1), "max_symbols"),
        (
            lambda budget: budget.validate_batch(symbol_count=1, rows_per_symbol=1_001),
            "max_rows_per_symbol",
        ),
        (lambda budget: budget.add_artifact(16 * 1024 * 1024 + 1), "max_artifact_bytes"),
    ],
)
def test_cpu_budget_rejects_each_overflow_without_truncating(operation, metadata_key):
    from app.research_web.skills._shared.cpu_budget import (
        WorkloadBudget,
        WorkloadTooLarge,
    )

    with pytest.raises(WorkloadTooLarge) as error:
        operation(WorkloadBudget())

    assert error.value.code == "workload_too_large"
    assert error.value.metadata[metadata_key] > 0
    assert error.value.metadata["suggestion"] == "reduce_scope"
    assert "input" not in error.value.metadata


def test_cpu_budget_accumulates_input_and_artifact_totals():
    from app.research_web.skills._shared.cpu_budget import (
        WorkloadBudget,
        WorkloadTooLarge,
    )

    budget = WorkloadBudget()
    budget.add_input(rows=30_000, bytes_count=32 * 1024 * 1024)
    with pytest.raises(WorkloadTooLarge):
        budget.add_input(rows=20_001, bytes_count=1)

    budget = WorkloadBudget()
    budget.add_artifact(8 * 1024 * 1024)
    with pytest.raises(WorkloadTooLarge):
        budget.add_artifact(8 * 1024 * 1024 + 1)


def test_cpu_bounded_shared_resources_define_result_and_provenance_contracts():
    policy = (SHARED / "cpu-bounded-policy.md").read_text(encoding="utf-8")
    result = (SHARED / "cpu-bounded-result-v1.md").read_text(encoding="utf-8")
    provenance = (SHARED / "provenance-v1.md").read_text(encoding="utf-8")

    assert "cpu_bounded_v1" in policy
    for field in (
        "as_of",
        "parameters",
        "dataset_refs",
        "status",
        "limitations",
        "method_version",
    ):
        assert field in result
    assert "source_hashes" in provenance
    assert "internal-only" in provenance
