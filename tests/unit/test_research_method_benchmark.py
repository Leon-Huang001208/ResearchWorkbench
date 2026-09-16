"""Behavioral tests for the standalone Research Method evaluation runner."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from benchmarks import research_methods as benchmark_module
from benchmarks.research_methods import (
    MethodEvalRunFailed,
    _messages,
    build_invocation_plan,
    load_method_eval_dataset,
    run_method_evals,
)
from core.interfaces import ModelResponse

DATASET = Path(__file__).parents[2] / "benchmarks" / "datasets" / "research_methods_v1.jsonl"


class DeterministicGateway:
    """Return complete single/combined outputs and a deliberately weak baseline."""

    def __init__(self, *, fail_at: int | None = None) -> None:
        self.calls: list[dict] = []
        self.fail_at = fail_at

    def chat(self, messages, model=None, temperature=0.7, max_tokens=None, **kwargs):
        call = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        self.calls.append(call)
        if self.fail_at == len(self.calls):
            return ModelResponse(
                content="not-json",
                model_name="fake-reasoner",
                provider="fake",
                tokens_used=100,
                latency_ms=1000,
            )
        payload = json.loads(messages[-1]["content"])
        baseline = payload["variant"] == "baseline"
        evidence = payload["evidence"]
        ids = [item["evidence_id"] for item in evidence]
        counter = next(item["evidence_id"] for item in evidence if item["stance"] == "counter")
        output = {
            "conclusion": "需要更多证据" if baseline else "方法化结论",
            "evidence_ids": [] if baseline else ids,
            "source_layers": (
                []
                if baseline
                else [
                    {"evidence_id": item["evidence_id"], "tier": item["source_tier"]}
                    for item in evidence
                ]
            ),
            "counter_evidence_ids": [] if baseline else [counter],
            "decision_variables": [] if baseline else ["需求兑现", "供给弹性"],
            "causal_steps": [] if baseline else ["需求变化", "供需缺口", "利润变化"],
            "expert_conflicts": [] if baseline else ["工程可行性与商业回报冲突"],
            "transfer_failure_conditions": [] if baseline else ["监管结构不同则类比失效"],
            "experiment_sample": [] if baseline else ["三家公司两周跟踪样本"],
            "stop_conditions": [] if baseline else ["关键事实被证伪即停止"],
            "decision_thresholds": [] if baseline else ["至少两项一手证据一致"],
        }
        return ModelResponse(
            content=json.dumps(output, ensure_ascii=False),
            model_name="fake-reasoner",
            provider="fake",
            tokens_used=100 if baseline else 105,
            latency_ms=1000 if baseline else 1050,
        )


def test_cli_builds_the_shared_model_gateway(monkeypatch, tmp_path: Path) -> None:
    """The CLI must reuse ModelGatewayImpl instead of owning a provider client."""

    gateway = DeterministicGateway()
    created: list[object] = []

    def build_gateway():
        created.append(gateway)
        return gateway

    monkeypatch.setattr(benchmark_module, "ModelGatewayImpl", build_gateway)
    monkeypatch.setattr(
        benchmark_module,
        "RAW_ROOT",
        tmp_path / "private",
    )
    monkeypatch.setattr(
        benchmark_module,
        "RESULTS_ROOT",
        tmp_path / "results",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "research_methods",
            "--dataset",
            str(DATASET),
            "--raw-root",
            str(tmp_path / "private"),
            "--results-root",
            str(tmp_path / "results"),
            "--run-id",
            "shared-gateway",
        ],
    )

    assert benchmark_module.main() == 0
    assert created == [gateway]
    assert len(gateway.calls) == 63


def test_dataset_and_plan_have_three_shared_baselines_and_sixty_method_calls() -> None:
    """A duplicated baseline or missing method variant must break the 63-call contract."""

    cases = load_method_eval_dataset(DATASET)
    first = build_invocation_plan(cases, seed=20260915)
    second = build_invocation_plan(cases, seed=20260915)

    assert [case.case_id for case in cases] == [
        "source-conflict-v1",
        "industry-chain-comparison-v1",
        "unfamiliar-domain-validation-v1",
    ]
    assert len(first) == 63
    assert [item.invocation_id for item in first] == [item.invocation_id for item in second]
    assert sum(item.variant == "baseline" for item in first) == 3
    assert sum(item.variant == "single" for item in first) == 30
    assert sum(item.variant == "combined" for item in first) == 30
    assert len({item.baseline_ref for item in first if item.variant != "baseline"}) == 3
    assert all(len(item.method_ids) == 2 for item in first if item.variant == "combined")


def test_prompt_embeds_the_exact_output_schema() -> None:
    """Field names and container types must not be left to model inference."""

    cases = load_method_eval_dataset(DATASET)
    invocation = build_invocation_plan(cases, seed=20260915)[0]
    case = next(item for item in cases if item.case_id == invocation.case_id)

    system_message = _messages(invocation, case)[0]["content"]
    marker = "OUTPUT_SCHEMA="
    assert marker in system_message
    schema = json.loads(system_message.split(marker, 1)[1])
    source_layer_ref = schema["properties"]["source_layers"]["items"]["$ref"]
    source_layer_name = source_layer_ref.rsplit("/", 1)[-1]

    assert "tier" in schema["$defs"][source_layer_name]["properties"]
    assert schema["properties"]["experiment_sample"]["type"] == "array"
    assert schema["properties"]["experiment_sample"]["items"]["type"] == "string"


def test_runner_uses_reasoning_route_scores_outputs_and_keeps_raw_content_private(
    tmp_path: Path,
) -> None:
    """Wrong routing, duplicate calls, or leaking output into tracked results must fail."""

    gateway = DeterministicGateway()
    raw_root = tmp_path / "private"
    results_root = tmp_path / "results"
    summary = run_method_evals(
        gateway=gateway,
        cases=load_method_eval_dataset(DATASET),
        raw_root=raw_root,
        results_root=results_root,
        run_id="unit-success",
        seed=20260915,
    )

    assert summary["status"] == "completed"
    assert summary["completed_calls"] == 63
    assert len(summary["promotion_candidates"]) == 10
    assert len(gateway.calls) == 63
    assert all(call["task"] == "reasoning" for call in gateway.calls)
    assert all(call["temperature"] == 0.0 for call in gateway.calls)
    assert {call["max_tokens"] for call in gateway.calls} == {8192}

    sanitized = (results_root / "unit-success.json").read_text(encoding="utf-8")
    assert "方法化结论" not in sanitized
    assert "工程可行性" not in sanitized
    assert '"messages"' not in sanitized
    assert '"prompt"' not in sanitized
    assert (results_root / "unit-success.md").exists()

    raw_dir = raw_root / "unit-success"
    raw_files = sorted(raw_dir.glob("*.json"))
    assert len(raw_files) == 63
    assert "方法化结论" in "".join(path.read_text(encoding="utf-8") for path in raw_files)
    assert stat.S_IMODE(raw_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in raw_files)


def test_invalid_model_output_fails_closed_without_candidates(tmp_path: Path) -> None:
    """A malformed response must stop the run and publish no promotion candidate."""

    gateway = DeterministicGateway(fail_at=4)
    results_root = tmp_path / "results"
    with pytest.raises(MethodEvalRunFailed):
        run_method_evals(
            gateway=gateway,
            cases=load_method_eval_dataset(DATASET),
            raw_root=tmp_path / "private",
            results_root=results_root,
            run_id="unit-failed",
            seed=20260915,
        )

    failed = json.loads((results_root / "unit-failed.json").read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["promotion_candidates"] == []
    assert failed["completed_calls"] == 3
    assert failed["failure"]["type"] == "output_validation_failed"
    assert "not-json" not in json.dumps(failed)
