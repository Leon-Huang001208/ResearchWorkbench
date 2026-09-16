"""Standalone observable-output evaluation for Research Workbench methods.

The runner calls the configured ``reasoning`` model route, stores raw model
responses under a private user directory, and writes only hashes, scores and
aggregate metrics to the repository result directory. It does not call the
Research Web product API or the engineering Harness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.research_web.capabilities.methods import METHOD_IDS, METHOD_SPECS
from core.interfaces import ModelResponse
from core.model_gateway import ModelGatewayImpl
from core.observability import configure_logging, get_logger

log = get_logger(__name__)

DATASET_PATH = Path(__file__).parent / "datasets" / "research_methods_v1.jsonl"
RESULTS_ROOT = Path(__file__).parent / "results" / "research_methods_v1"
RAW_ROOT = Path.home() / ".research-workbench" / "research-evals"
MAX_TOKENS = 8192
DEFAULT_SEED = 20260915
EXPECTED_SCENARIOS = {
    "source_conflict",
    "industry_chain_comparison",
    "unfamiliar_domain_validation",
}

COMBINATION_PARTNERS = {
    "socratic-clarification": "fact-checking",
    "dual-layer-explanation": "first-principles",
    "reverse-engineering": "fact-checking",
    "horizontal-vertical-analysis": "steelman-comparison",
    "fact-checking": "steelman-comparison",
    "expert-perspectives": "steelman-comparison",
    "first-principles": "minimal-experiment",
    "cross-domain-transfer": "first-principles",
    "steelman-comparison": "fact-checking",
    "minimal-experiment": "fact-checking",
}

CRITICAL_CRITERIA = {
    "socratic-clarification": ("decision_variables", "decision_thresholds"),
    "dual-layer-explanation": ("valid_evidence_ids", "causal_steps"),
    "reverse-engineering": ("decision_variables", "causal_steps"),
    "horizontal-vertical-analysis": ("decision_variables", "causal_steps"),
    "fact-checking": ("source_layers", "counter_evidence"),
    "expert-perspectives": ("expert_conflicts",),
    "first-principles": ("decision_variables", "causal_steps"),
    "cross-domain-transfer": ("transfer_failure_conditions",),
    "steelman-comparison": ("counter_evidence", "decision_variables"),
    "minimal-experiment": (
        "experiment_sample",
        "stop_conditions",
        "decision_thresholds",
    ),
}


class EvidenceItem(BaseModel):
    """One synthetic evidence item with an explicit source tier and stance."""

    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{1,31}$")
    source_tier: Literal["primary", "secondary", "expert", "market"]
    stance: Literal["support", "counter", "context"]
    as_of: str = Field(min_length=10, max_length=10)
    text: str = Field(min_length=20, max_length=1000)


class MethodEvalCase(BaseModel):
    """Versioned synthetic research evidence pack."""

    model_config = ConfigDict(extra="forbid")
    dataset_version: Literal["1.0.0"]
    case_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*-v1$")
    scenario: Literal[
        "source_conflict",
        "industry_chain_comparison",
        "unfamiliar_domain_validation",
    ]
    question: str = Field(min_length=20, max_length=1000)
    evidence: list[EvidenceItem] = Field(min_length=4, max_length=8)

    @model_validator(mode="after")
    def validate_evidence(self) -> MethodEvalCase:
        ids = [item.evidence_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence ids must be unique within a case")
        if not any(item.stance == "counter" for item in self.evidence):
            raise ValueError("each case must contain counter evidence")
        if len({item.source_tier for item in self.evidence}) < 2:
            raise ValueError("each case must contain at least two source tiers")
        return self


class SourceLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    tier: Literal["primary", "secondary", "expert", "market"]


class MethodEvalOutput(BaseModel):
    """Shared structured output contract for every evaluation variant."""

    model_config = ConfigDict(extra="forbid")
    conclusion: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(max_length=20)
    source_layers: list[SourceLayer] = Field(max_length=20)
    counter_evidence_ids: list[str] = Field(max_length=20)
    decision_variables: list[str] = Field(max_length=20)
    causal_steps: list[str] = Field(max_length=20)
    expert_conflicts: list[str] = Field(max_length=20)
    transfer_failure_conditions: list[str] = Field(max_length=20)
    experiment_sample: list[str] = Field(max_length=20)
    stop_conditions: list[str] = Field(max_length=20)
    decision_thresholds: list[str] = Field(max_length=20)


@dataclass(frozen=True)
class EvalInvocation:
    invocation_id: str
    case_id: str
    variant: Literal["baseline", "single", "combined"]
    method_ids: tuple[str, ...]
    baseline_ref: str


class ChatGateway(Protocol):
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse: ...


class MethodEvalRunFailed(RuntimeError):
    """Raised after a failed run has written its sanitized failure record."""


class _CallFailure(RuntimeError):
    def __init__(self, failure_type: str) -> None:
        super().__init__(failure_type)
        self.failure_type = failure_type


def load_method_eval_dataset(path: Path = DATASET_PATH) -> list[MethodEvalCase]:
    """Load and validate the exact three-case method evaluation dataset."""

    if not path.is_file() or path.is_symlink():
        raise ValueError("method evaluation dataset is unavailable")
    cases: list[MethodEvalCase] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                cases.append(MethodEvalCase.model_validate_json(line))
            except ValidationError as exc:
                log.error(
                    "research_method_eval_dataset_invalid",
                    line_number=line_number,
                    error_type=type(exc).__name__,
                )
                raise ValueError("method evaluation dataset is invalid") from exc
    except (OSError, UnicodeError) as exc:
        log.error("research_method_eval_dataset_unreadable", error_type=type(exc).__name__)
        raise ValueError("method evaluation dataset is unavailable") from exc
    if len(cases) != 3 or {case.scenario for case in cases} != EXPECTED_SCENARIOS:
        raise ValueError("method evaluation dataset must contain the three required scenarios")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("method evaluation case ids must be unique")
    return cases


def build_invocation_plan(
    cases: list[MethodEvalCase], *, seed: int = DEFAULT_SEED
) -> list[EvalInvocation]:
    """Build and deterministically shuffle 3 baseline + 30 single + 30 combined calls."""

    if len(cases) != 3 or set(COMBINATION_PARTNERS) != set(METHOD_IDS):
        raise ValueError("method evaluation plan is incomplete")
    if any(partner not in METHOD_IDS for partner in COMBINATION_PARTNERS.values()):
        raise ValueError("method evaluation combination partner is unavailable")
    invocations: list[EvalInvocation] = []
    for case in cases:
        baseline_ref = f"baseline:{case.case_id}"
        invocations.append(
            EvalInvocation(
                invocation_id=baseline_ref,
                case_id=case.case_id,
                variant="baseline",
                method_ids=(),
                baseline_ref=baseline_ref,
            )
        )
        for method_id in METHOD_IDS:
            invocations.append(
                EvalInvocation(
                    invocation_id=f"single:{method_id}:{case.case_id}",
                    case_id=case.case_id,
                    variant="single",
                    method_ids=(method_id,),
                    baseline_ref=baseline_ref,
                )
            )
            partner = COMBINATION_PARTNERS[method_id]
            invocations.append(
                EvalInvocation(
                    invocation_id=f"combined:{method_id}:{partner}:{case.case_id}",
                    case_id=case.case_id,
                    variant="combined",
                    method_ids=(method_id, partner),
                    baseline_ref=baseline_ref,
                )
            )
    random.Random(seed).shuffle(invocations)
    if len(invocations) != 63:
        raise ValueError("method evaluation plan must contain exactly 63 calls")
    return invocations


def score_method_output(output: MethodEvalOutput, case: MethodEvalCase) -> dict[str, Any]:
    """Score only observable fields; do not use a judge model or hidden reasoning."""

    evidence = {item.evidence_id: item for item in case.evidence}
    valid_ids = set(evidence)
    referenced = output.evidence_ids
    layer_ids = [item.evidence_id for item in output.source_layers]
    layer_valid = bool(output.source_layers) and all(
        item.evidence_id in evidence and evidence[item.evidence_id].source_tier == item.tier
        for item in output.source_layers
    )
    criteria = {
        "valid_evidence_ids": float(
            bool(referenced)
            and len(referenced) == len(set(referenced))
            and set(referenced) <= valid_ids
        ),
        "source_layers": float(
            layer_valid
            and len(layer_ids) == len(set(layer_ids))
            and len({item.tier for item in output.source_layers}) >= 2
        ),
        "counter_evidence": float(
            bool(output.counter_evidence_ids)
            and set(output.counter_evidence_ids) <= valid_ids
            and any(evidence[item].stance == "counter" for item in output.counter_evidence_ids)
        ),
        "decision_variables": float(len(output.decision_variables) >= 2),
        "causal_steps": float(len(output.causal_steps) >= 3),
        "expert_conflicts": float(bool(output.expert_conflicts)),
        "transfer_failure_conditions": float(bool(output.transfer_failure_conditions)),
        "experiment_sample": float(bool(output.experiment_sample)),
        "stop_conditions": float(bool(output.stop_conditions)),
        "decision_thresholds": float(bool(output.decision_thresholds)),
    }
    return {"quality_score": mean(criteria.values()), "criteria": criteria}


def _method_payload(method_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    specs = {spec.method_id: spec for spec in METHOD_SPECS}
    return [
        specs[method_id].model_dump(
            include={"method_id", "version", "title", "procedure", "evaluation_rubric"}
        )
        for method_id in method_ids
    ]


def _messages(invocation: EvalInvocation, case: MethodEvalCase) -> list[dict[str, str]]:
    output_schema = json.dumps(
        MethodEvalOutput.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    system = (
        "你是投研方法评测执行器。只使用给定的合成证据，不联网，不补造事实。"
        "仅返回一个严格匹配给定 JSON Schema 的对象，不得使用 Markdown。"
        "所有字段都必须出现；没有内容时使用空数组。"
        "evidence_ids 与 counter_evidence_ids 只能引用输入中的 evidence_id；"
        "source_layers 每项必须使用 evidence_id 和 tier 两个字段，"
        "其中 tier 的值复制对应输入证据的 source_tier。"
        f"OUTPUT_SCHEMA={output_schema}"
    )
    payload = {
        "dataset_version": case.dataset_version,
        "case_id": case.case_id,
        "variant": invocation.variant,
        "question": case.question,
        "evidence": [item.model_dump(mode="json") for item in case.evidence],
        "methods": _method_payload(invocation.method_ids),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
    ]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_dataset_hash(cases: list[MethodEvalCase]) -> str:
    payload = json.dumps(
        [case.model_dump(mode="json") for case in cases],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _digest(payload)


def _safe_run_id(run_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", run_id):
        raise ValueError("invalid method evaluation run id")
    return run_id


def _private_run_dir(raw_root: Path, run_id: str) -> Path:
    raw_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if raw_root.is_symlink() or not raw_root.is_dir():
        raise ValueError("private evaluation root is unsafe")
    os.chmod(raw_root, 0o700)
    run_dir = raw_root / run_id
    try:
        run_dir.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise ValueError("method evaluation run already exists") from exc
    os.chmod(run_dir, 0o700)
    return run_dir


def _atomic_write(path: Path, content: str, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _write_raw_response(
    run_dir: Path,
    sequence: int,
    invocation: EvalInvocation,
    response: ModelResponse,
    request_hash: str,
) -> str:
    response_hash = _digest(response.content)
    payload = {
        "invocation_id": invocation.invocation_id,
        "request_hash": request_hash,
        "response_hash": response_hash,
        "model": response.model_name,
        "provider": response.provider,
        "tokens_used": response.tokens_used,
        "latency_ms": response.latency_ms,
        "content": response.content,
    }
    _atomic_write(
        run_dir / f"{sequence:03d}.json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        mode=0o600,
    )
    return response_hash


def _parse_response(response: ModelResponse) -> MethodEvalOutput:
    if not response.content.strip() or response.content.lstrip().lower().startswith("error:"):
        raise _CallFailure("model_call_failed")
    try:
        value = json.loads(response.content)
        return MethodEvalOutput.model_validate(value)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise _CallFailure("output_validation_failed") from exc


def _average(rows: list[dict[str, Any]], field: str) -> float:
    return mean(float(row[field]) for row in rows)


def _summarize_methods(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = {row["invocation_id"]: row for row in rows}
    singles: dict[str, list[dict[str, Any]]] = defaultdict(list)
    combined: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["variant"] == "single":
            singles[row["method_ids"][0]].append(row)
        elif row["variant"] == "combined":
            combined[row["method_ids"][0]].append(row)
    method_results: list[dict[str, Any]] = []
    candidates: list[str] = []
    for method_id in METHOD_IDS:
        single_rows = singles[method_id]
        combined_rows = combined[method_id]
        baseline_rows = [by_id[row["baseline_ref"]] for row in single_rows]
        critical = CRITICAL_CRITERIA[method_id]
        critical_ok = all(
            all(float(row["criteria"][criterion]) > 0 for criterion in critical)
            for row in single_rows
        )
        baseline_quality = _average(baseline_rows, "quality_score")
        single_quality = _average(single_rows, "quality_score")
        baseline_tokens = _average(baseline_rows, "tokens_used")
        single_tokens = _average(single_rows, "tokens_used")
        baseline_latency = _average(baseline_rows, "latency_ms")
        single_latency = _average(single_rows, "latency_ms")
        quality_improved = single_quality > baseline_quality
        token_ok = single_tokens <= baseline_tokens * 1.1
        latency_ok = single_latency <= baseline_latency * 1.1
        promote = quality_improved and token_ok and latency_ok and critical_ok
        if promote:
            candidates.append(method_id)
        method_results.append(
            {
                "method_id": method_id,
                "baseline": {
                    "quality": baseline_quality,
                    "token_cost_proxy": baseline_tokens,
                    "latency_ms": baseline_latency,
                },
                "single": {
                    "quality": single_quality,
                    "token_cost_proxy": single_tokens,
                    "latency_ms": single_latency,
                },
                "combined": {
                    "partner": COMBINATION_PARTNERS[method_id],
                    "quality": _average(combined_rows, "quality_score"),
                    "token_cost_proxy": _average(combined_rows, "tokens_used"),
                    "latency_ms": _average(combined_rows, "latency_ms"),
                },
                "gate": {
                    "candidate": promote,
                    "quality_improved": quality_improved,
                    "token_within_10_percent": token_ok,
                    "latency_within_10_percent": latency_ok,
                    "critical_rubric_nonzero": critical_ok,
                },
            }
        )
    return method_results, candidates


def _report(summary: dict[str, Any]) -> str:
    lines = [
        "# Research Method Eval Summary",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Dataset SHA-256: `{summary['dataset_hash']}`",
        f"- Calls: {summary['completed_calls']}/{summary['expected_calls']}",
        "- Promotion candidates are review inputs only; default recommendations were not changed.",
        "",
    ]
    if summary["status"] == "completed":
        lines.extend(
            [
                "| Method | Baseline quality | Single quality | Tokens gate | Latency gate | Candidate |",
                "| --- | ---: | ---: | --- | --- | --- |",
            ]
        )
        for row in summary["method_results"]:
            lines.append(
                "| {method} | {baseline:.3f} | {single:.3f} | {tokens} | {latency} | {candidate} |".format(
                    method=row["method_id"],
                    baseline=row["baseline"]["quality"],
                    single=row["single"]["quality"],
                    tokens="pass" if row["gate"]["token_within_10_percent"] else "fail",
                    latency="pass" if row["gate"]["latency_within_10_percent"] else "fail",
                    candidate="yes" if row["gate"]["candidate"] else "no",
                )
            )
    else:
        lines.append(f"- Failure type: `{summary['failure']['type']}`")
    lines.append("")
    return "\n".join(lines)


def _write_sanitized_results(results_root: Path, summary: dict[str, Any]) -> None:
    _atomic_write(
        results_root / f"{summary['run_id']}.json",
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
    )
    _atomic_write(results_root / f"{summary['run_id']}.md", _report(summary))


def run_method_evals(
    *,
    gateway: ChatGateway,
    cases: list[MethodEvalCase],
    raw_root: Path = RAW_ROOT,
    results_root: Path = RESULTS_ROOT,
    run_id: str,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Run all 63 calls, failing closed on any model or validation error."""

    run_id = _safe_run_id(run_id)
    plan = build_invocation_plan(cases, seed=seed)
    case_by_id = {case.case_id: case for case in cases}
    run_dir = _private_run_dir(raw_root, run_id)
    result_path = results_root / f"{run_id}.json"
    if result_path.exists() or result_path.is_symlink():
        raise ValueError("sanitized method evaluation result already exists")
    rows: list[dict[str, Any]] = []
    log.info("research_method_eval_started", run_id=run_id, call_count=len(plan), seed=seed)
    for sequence, invocation in enumerate(plan, 1):
        case = case_by_id[invocation.case_id]
        messages = _messages(invocation, case)
        request_hash = _digest(
            json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        try:
            response = gateway.chat(
                messages=messages,
                temperature=0.0,
                max_tokens=MAX_TOKENS,
                task="reasoning",
                response_format={"type": "json_object"},
            )
            if not isinstance(response, ModelResponse):
                raise _CallFailure("model_call_failed")
            response_hash = _write_raw_response(
                run_dir, sequence, invocation, response, request_hash
            )
            output = _parse_response(response)
            score = score_method_output(output, case)
            rows.append(
                {
                    "invocation_id": invocation.invocation_id,
                    "case_id": invocation.case_id,
                    "variant": invocation.variant,
                    "method_ids": list(invocation.method_ids),
                    "baseline_ref": invocation.baseline_ref,
                    "request_hash": request_hash,
                    "response_hash": response_hash,
                    "model": response.model_name,
                    "provider": response.provider,
                    "tokens_used": response.tokens_used,
                    "latency_ms": response.latency_ms,
                    **score,
                }
            )
            log.info(
                "research_method_eval_call_completed",
                run_id=run_id,
                sequence=sequence,
                variant=invocation.variant,
            )
        except _CallFailure as exc:
            summary = {
                "schema_version": 1,
                "run_id": run_id,
                "status": "failed",
                "dataset_version": cases[0].dataset_version,
                "dataset_hash": _canonical_dataset_hash(cases),
                "seed": seed,
                "expected_calls": len(plan),
                "completed_calls": len(rows),
                "calls": rows,
                "method_results": [],
                "promotion_candidates": [],
                "default_recommendations_changed": False,
                "failure": {
                    "type": exc.failure_type,
                    "invocation_id": invocation.invocation_id,
                },
            }
            _write_sanitized_results(results_root, summary)
            log.error(
                "research_method_eval_failed",
                run_id=run_id,
                sequence=sequence,
                failure_type=exc.failure_type,
            )
            raise MethodEvalRunFailed("research method evaluation failed closed") from exc
        except Exception as exc:
            summary = {
                "schema_version": 1,
                "run_id": run_id,
                "status": "failed",
                "dataset_version": cases[0].dataset_version,
                "dataset_hash": _canonical_dataset_hash(cases),
                "seed": seed,
                "expected_calls": len(plan),
                "completed_calls": len(rows),
                "calls": rows,
                "method_results": [],
                "promotion_candidates": [],
                "default_recommendations_changed": False,
                "failure": {"type": "runner_error", "invocation_id": invocation.invocation_id},
            }
            _write_sanitized_results(results_root, summary)
            log.error(
                "research_method_eval_failed",
                run_id=run_id,
                sequence=sequence,
                failure_type=type(exc).__name__,
            )
            raise MethodEvalRunFailed("research method evaluation failed closed") from exc
    method_results, candidates = _summarize_methods(rows)
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "completed",
        "dataset_version": cases[0].dataset_version,
        "dataset_hash": _canonical_dataset_hash(cases),
        "seed": seed,
        "expected_calls": len(plan),
        "completed_calls": len(rows),
        "calls": rows,
        "method_results": method_results,
        "promotion_candidates": candidates,
        "default_recommendations_changed": False,
        "failure": None,
    }
    _write_sanitized_results(results_root, summary)
    log.info(
        "research_method_eval_completed",
        run_id=run_id,
        candidate_count=len(candidates),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run observable Research Method evaluations")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--results-root", type=Path, default=RESULTS_ROOT)
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    configure_logging()
    run_id = args.run_id or datetime.now(UTC).strftime("method-eval-%Y%m%d-%H%M%S")
    try:
        gateway = ModelGatewayImpl()
        summary = run_method_evals(
            gateway=gateway,
            cases=load_method_eval_dataset(args.dataset),
            raw_root=args.raw_root,
            results_root=args.results_root,
            run_id=run_id,
            seed=args.seed,
        )
    except (MethodEvalRunFailed, ValueError) as exc:
        log.error("research_method_eval_cli_failed", error_type=type(exc).__name__)
        return 1
    print(
        json.dumps(
            {
                "run_id": summary["run_id"],
                "status": summary["status"],
                "completed_calls": summary["completed_calls"],
                "promotion_candidates": summary["promotion_candidates"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
