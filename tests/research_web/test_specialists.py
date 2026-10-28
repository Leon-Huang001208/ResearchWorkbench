"""Offline business-contract and crash-boundary tests; no model/provider calls."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.research_web.specialists import Budget, SpecialistError, SpecialistLedger, catalog
from app.research_web.store import Store, StoreError


def frozen_skills():
    return {
        name: {
            "id": name,
            "version": 1,
            "kind": "skill",
            "native_name": f"rwb-{name}-v1",
            "sha256": "a" * 64,
            "resource_path": f"resources/capabilities/{name}/1",
            "resource_snapshot_sha256": "b" * 64,
        }
        for name in ("industry-research", "factor-database-research")
    }


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "半导体协作研究")["id"]
    now = [1000.0]
    ledger = SpecialistLedger(store, clock=lambda: now[0])
    budget = {"confirmed": True, "max_tokens": 50000, "max_calls": 12}
    state = ledger.create(
        sid, budget, "2026-10-28", {"model": "test-model"}, "first-request", skills=frozen_skills()
    )
    return store, sid, ledger, budget, state, now


def nodes():
    return [
        {"id": "industry", "role": "industry", "input": {"sector": "半导体"}},
        {"id": "quant", "role": "quant", "input": {"metric": "return"}},
        {"id": "review", "role": "review", "depends_on": ["industry", "quant"]},
    ]


def invoke(setup, operation, payload, *, actor=None, call=None):
    _, sid, ledger, *_ = setup
    if operation == "model_request":
        records = ledger.read(sid)["model_requests"].values()
        step = sum(item["agent_id"] == (actor or sid) for item in records)
        payload = {"turn": 1, "step": step, **payload}
    return ledger.apply(
        sid, operation, payload, agent_id=actor or sid, call_id=call or str(uuid4())
    )


def plan(setup, values=None, version=0):
    return invoke(setup, "plan", {"nodes": values or nodes(), "expected_version": version})


def reserve(setup, node="industry", version=1, call=None):
    return invoke(
        setup,
        "reserve",
        {"node_id": node, "expected_version": version, "max_tokens": 4096},
        call=call,
    )["operation_result"]


def finish(setup, attempt, stop="completed", **extra):
    result = {
        "conclusion": "有来源的受限判断",
        "evidence_ids": ["dataset-verified"],
        "as_of_date": "2026-10-28",
        "limitations": ["仅描述性分析"],
        "artifact_ids": [],
    }
    return invoke(
        setup,
        "terminal",
        {
            "attempt_id": attempt["attempt_id"],
            "child_id": attempt["child_id"],
            "run_id": f"native-{attempt['attempt_id']}",
            "stop_reason": stop,
            **(
                {"result": result, "evidence_snapshot": {"dataset-verified": "a" * 64}}
                if stop == "completed"
                else {}
            ),
            **extra,
        },
        actor=attempt["child_id"],
    )


def test_registry_is_immutable_and_has_frozen_model():
    first = catalog()
    first["roles"]["industry"]["skills"].append("unpublished")
    assert "unpublished" not in catalog()["roles"]["industry"]["skills"]
    assert len(catalog()["digest"]) == 64
    assert catalog()["roles"]["quant"]["model"] == "inherit_frozen"


@pytest.mark.parametrize(
    "change",
    [
        {"confirmed": False},
        {"max_tokens": 0},
        {"max_calls": True},
        {"timeout_seconds": 1801},
        {"max_revisions": 3},
        {"max_concurrency": 3},
        {"unexpected": True},
    ],
)
def test_budget_requires_explicit_bounded_contract(change):
    with pytest.raises(ValidationError):
        Budget.model_validate({"confirmed": True, "max_tokens": 10000, "max_calls": 10, **change})


def test_create_idempotent_and_conflicting_input_rejected(setup):
    _, sid, ledger, budget, state, _ = setup
    assert (
        ledger.create(
            sid,
            budget,
            "2026-10-28",
            {"model": "test-model"},
            "first-request",
            skills=frozen_skills(),
        )["id"]
        == state["id"]
    )
    with pytest.raises(SpecialistError, match="绑定"):
        ledger.create(
            sid,
            budget,
            "2026-10-27",
            {"model": "test-model"},
            "first-request",
            skills=frozen_skills(),
        )
    assert ledger.read(sid)["as_of_date"] == "2026-10-28"


@pytest.mark.parametrize("kind", ["cycle", "missing", "review", "unknown-role", "unknown-skill"])
def test_rejects_unsafe_or_incomplete_graph(setup, kind):
    values = nodes()
    if kind == "cycle":
        values[0]["depends_on"] = ["review"]
    elif kind == "missing":
        values[0]["depends_on"] = ["not-present"]
    elif kind == "review":
        values[2]["depends_on"] = ["industry"]
    elif kind == "unknown-role":
        values[0]["role"] = "trader"
    else:
        values[0]["skills"] = ["unreviewed-code"]
    with pytest.raises(SpecialistError):
        plan(setup, values)
    assert setup[2].read(setup[1])["active_plan"]["version"] == 0


def test_reservation_is_durable_and_duplicate_never_creates_second_child(setup):
    plan(setup)
    first = reserve(setup, call="stable-tool-call")
    reread = SpecialistLedger(setup[0]).read(setup[1])
    assert reread["attempts"][first["attempt_id"]]["status"] == "reserved"
    replay = invoke(
        setup,
        "reserve",
        {"node_id": "industry", "expected_version": 1, "max_tokens": 4096},
        call="stable-tool-call",
    )
    assert replay["replayed"] is True
    assert replay["operation_result"]["child_id"] == first["child_id"]
    assert first["parent_session_id"] == setup[1]
    with pytest.raises(SpecialistError, match="已有尝试"):
        reserve(setup)


def test_parallel_reservations_and_concurrency_are_atomic(setup):
    values = nodes() + [{"id": "extra", "role": "industry"}]
    plan(setup, values)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda name: reserve(setup, name), ["industry", "quant"]))
    assert len({value["child_id"] for value in results}) == 2
    with pytest.raises(SpecialistError, match="并发"):
        reserve(setup, "extra")


def test_review_waits_for_both_dependencies_and_failed_peer_keeps_other_result(setup):
    plan(setup)
    with pytest.raises(SpecialistError, match="依赖"):
        reserve(setup, "review")
    industry, quant = reserve(setup), reserve(setup, "quant")
    finish(setup, industry, "error")
    final = finish(setup, quant)
    assert final["status"] == "incomplete"
    assert final["attempts"][quant["attempt_id"]]["result"]["conclusion"]
    assert not final["finalization_ready"]


def test_failed_node_cannot_silently_retry_in_same_plan(setup):
    plan(setup)
    attempt = reserve(setup)
    finish(setup, attempt, "error")
    with pytest.raises(SpecialistError, match="修订计划或确认续跑"):
        reserve(setup)
    plan(setup, nodes(), 1)
    assert reserve(setup, version=2)["child_id"] != attempt["child_id"]


def test_invalidated_live_node_blocks_replacement_until_actual_native_terminal(setup):
    plan(setup)
    old = reserve(setup)
    values = nodes()
    values[0]["input"] = {"sector": "新输入"}
    updated = plan(setup, values, 1)
    assert updated["operation_result"]["cancel_attempt_ids"] == [old["attempt_id"]]
    with pytest.raises(SpecialistError, match="取消尚未确认"):
        reserve(setup, version=2)
    late = finish(setup, old)
    assert late["attempts"][old["attempt_id"]]["result"] is None
    assert late["attempts"][old["attempt_id"]]["late_result"]
    new = reserve(setup, version=2)
    assert new["child_id"] != old["child_id"]


def test_changed_input_invalidates_finished_downstream_but_not_peer(setup):
    plan(setup)
    industry, quant = reserve(setup), reserve(setup, "quant")
    finish(setup, industry)
    finish(setup, quant)
    review = reserve(setup, "review")
    finish(setup, review)
    values = nodes()
    values[0]["input"] = {"changed": True}
    state = plan(setup, values, 1)
    assert state["attempts"][industry["attempt_id"]]["invalidated"]
    assert state["attempts"][review["attempt_id"]]["invalidated"]
    assert not state["attempts"][quant["attempt_id"]]["invalidated"]


def test_cancel_receipt_is_not_terminal_and_resume_requires_reconciliation(setup):
    plan(setup)
    attempt = reserve(setup)
    state = invoke(setup, "cancel", {})
    assert state["status"] == "cancel_pending"
    with pytest.raises(SpecialistError, match="未知或在途"):
        setup[2].resume(setup[1], confirmed=True)
    state = finish(setup, attempt, "aborted")
    assert state["status"] == "cancelled"
    with pytest.raises(SpecialistError, match="明确确认"):
        setup[2].resume(setup[1], confirmed=False)


def test_restart_is_observation_only_and_preserves_unknown_submission(setup):
    plan(setup)
    attempt = reserve(setup)
    invoke(
        setup, "dispatch", {"attempt_id": attempt["attempt_id"], "child_id": attempt["child_id"]}
    )
    invoke(setup, "recover", {})
    ledger = SpecialistLedger(setup[0])
    state = ledger.read(setup[1])
    assert state["status"] == "needs_attention"
    assert state["attempts"][attempt["attempt_id"]]["status"] == "unknown"
    with pytest.raises(SpecialistError):
        reserve(setup, "quant")


def test_model_budget_counts_requests_and_unknown_usage_reservations(setup):
    plan(setup)
    attempt = reserve(setup)
    invoke(
        setup, "dispatch", {"attempt_id": attempt["attempt_id"], "child_id": attempt["child_id"]}
    )
    actor = attempt["child_id"]
    state = invoke(
        setup, "model_request", {"request_id": "r1", "reserved_tokens": 40000}, actor=actor
    )
    assert state["operation_result"]["remaining_ms"] == 1800000
    assert state["model_requests"][f"{actor}:r1"]["usage"] is None
    with pytest.raises(SpecialistError, match="预算不足"):
        invoke(setup, "model_request", {"request_id": "r2", "reserved_tokens": 10001})
    invoke(
        setup,
        "model_usage",
        {"request_id": "r1", "input_tokens": 200, "output_tokens": 300},
        actor=actor,
    )
    invoke(setup, "model_request", {"request_id": "r2", "reserved_tokens": 49000})
    with pytest.raises(SpecialistError, match="不可重复"):
        invoke(setup, "model_request", {"request_id": "r2", "reserved_tokens": 1})


def test_deadline_and_revision_limits_fail_closed(setup):
    plan(setup)
    plan(setup, nodes(), 1)
    plan(setup, nodes(), 2)
    with pytest.raises(SpecialistError, match="修订"):
        plan(setup, nodes(), 3)
    setup[-1][0] += 1801
    with pytest.raises(SpecialistError, match="超时"):
        reserve(setup, version=3)


@pytest.mark.parametrize(
    "change",
    [
        {"as_of_date": "2026-10-29"},
        {"evidence_ids": []},
        {"artifact_ids": ["../../other-account/report.json"]},
    ],
)
def test_bad_results_never_succeed(setup, change):
    plan(setup)
    attempt = reserve(setup)
    result = {
        "conclusion": "x",
        "evidence_ids": ["known"],
        "as_of_date": "2026-10-28",
        "limitations": [],
        "artifact_ids": [],
        **change,
    }
    state = finish(setup, attempt, result=result)
    assert state["attempts"][attempt["attempt_id"]]["status"] == "failed"
    assert state["attempts"][attempt["attempt_id"]]["stop_reason"] == "invalid_output"


def test_foreign_session_agent_and_child_event_denied(setup):
    plan(setup)
    with pytest.raises(StoreError):
        setup[2].read(str(uuid4()))
    with pytest.raises(SpecialistError):
        invoke(
            setup,
            "reserve",
            {"node_id": "industry", "expected_version": 1, "max_tokens": 1},
            actor=str(uuid4()),
        )
    attempt = reserve(setup)
    with pytest.raises(SpecialistError):
        invoke(
            setup,
            "accepted",
            {"attempt_id": attempt["attempt_id"], "message_id": "m", "child_id": str(uuid4())},
        )


def test_symlink_and_corrupt_ledger_rejected_without_overwrite(setup, tmp_path):
    store, sid, ledger, *_ = setup
    path = store.root / "specialists" / sid / "ledger.json"
    target = tmp_path / "unrelated.json"
    target.write_text('{"protected":true}')
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(StoreError):
        ledger.read(sid)
    assert json.loads(target.read_text()) == {"protected": True}
    path.unlink()
    path.write_text("broken")
    path.chmod(0o600)
    with pytest.raises(SpecialistError, match="损坏"):
        ledger.read(sid)
    assert path.read_text() == "broken"


def test_failed_atomic_write_preserves_previous_ledger(setup, monkeypatch):
    from app.research_web.datahub import security

    store, sid, ledger, *_ = setup
    path = store.root / "specialists" / sid / "ledger.json"
    previous = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("injected storage failure")

    monkeypatch.setattr(security.os, "replace", fail)
    with pytest.raises(StoreError):
        plan(setup)
    assert path.read_bytes() == previous
    assert ledger.read(sid)["active_plan"]["version"] == 0


def test_explicit_resume_preserves_usage_and_old_run(setup):
    _, sid, ledger, budget, first, _ = setup
    invoke(setup, "model_request", {"request_id": "root1", "reserved_tokens": 100})
    invoke(setup, "model_usage", {"request_id": "root1", "input_tokens": 30, "output_tokens": 40})
    invoke(setup, "cancel", {})
    with pytest.raises(SpecialistError, match="明确确认"):
        ledger.create(
            sid,
            budget,
            "2026-10-28",
            {"model": "test-model"},
            "second-request",
            skills=frozen_skills(),
        )
    ledger.resume(sid, confirmed=True)
    resumed = ledger.create(
        sid, budget, "2026-10-28", {"model": "test-model"}, "second-request", skills=frozen_skills()
    )
    assert resumed["previous_run_id"] == first["id"]
    assert len(resumed["model_requests"]) == 1
    assert resumed["previous_runs"][0]["status"] == "cancelled"


def test_resume_does_not_renew_budget_or_erase_unknown_usage(setup):
    _, sid, ledger, budget, *_ = setup
    invoke(setup, "model_request", {"request_id": "unfinished", "reserved_tokens": 100})
    invoke(setup, "cancel", {})
    with pytest.raises(SpecialistError, match="未知用量"):
        ledger.resume(sid, confirmed=True)
    invoke(
        setup, "model_usage", {"request_id": "unfinished", "input_tokens": 1, "output_tokens": 2}
    )
    ledger.resume(sid, confirmed=True)
    with pytest.raises(SpecialistError, match="增加"):
        ledger.create(
            sid,
            {**budget, "max_calls": 13},
            "2026-10-28",
            {"model": "test-model"},
            "second-request",
            skills=frozen_skills(),
        )


def test_native_terminal_before_acceptance_receipt_does_not_reopen_attempt(setup):
    plan(setup)
    attempt = reserve(setup)
    finish(setup, attempt)
    state = invoke(
        setup, "accepted", {"attempt_id": attempt["attempt_id"], "message_id": "late-receipt"}
    )
    assert state["attempts"][attempt["attempt_id"]]["status"] == "succeeded"
    assert state["attempts"][attempt["attempt_id"]]["message_id"] == "late-receipt"


def test_terminal_without_native_identity_keeps_attempt_unresolved(setup):
    plan(setup)
    attempt = reserve(setup)
    with pytest.raises(SpecialistError):
        invoke(
            setup,
            "terminal",
            {
                "attempt_id": attempt["attempt_id"],
                "child_id": attempt["child_id"],
                "stop_reason": "completed",
                "result": {"conclusion": "model says complete"},
            },
            actor=attempt["child_id"],
        )
    state = setup[2].read(setup[1])
    assert state["attempts"][attempt["attempt_id"]]["status"] == "reserved"
    assert not state["can_resume"]
    assert not state["finalization_ready"]


def test_structurally_incomplete_legacy_state_is_not_accepted(setup):
    store, sid, ledger, *_ = setup
    path = store.root / "specialists" / sid / "ledger.json"
    previous = json.loads(path.read_text())
    previous["runs"][previous["current"]].pop("model_requests")
    path.write_text(json.dumps(previous))
    with pytest.raises(SpecialistError, match="损坏"):
        ledger.read(sid)
    assert "model_requests" not in json.loads(path.read_text())["runs"][previous["current"]]


@pytest.mark.parametrize("stop", ["completed", "aborted"])
def test_verified_history_terminal_can_reconcile_without_invented_native_run_id(setup, stop):
    plan(setup)
    attempt = reserve(setup)
    invoke(setup, "recover", {})
    observation = {
        "kind": "history",
        "child_id": attempt["child_id"],
        "end_seq": 31,
        "event_sha256": "a" * 64,
        "turn": 1,
    }
    result = {
        "conclusion": "历史观察到的真实结果",
        "evidence_ids": ["bound-source"],
        "as_of_date": "2026-10-28",
        "limitations": [],
        "artifact_ids": [],
    }
    state = invoke(
        setup,
        "terminal",
        {
            "attempt_id": attempt["attempt_id"],
            "child_id": attempt["child_id"],
            "terminal_observation": observation,
            "stop_reason": stop,
            **(
                {"result": result, "evidence_snapshot": {"bound-source": "b" * 64}}
                if stop == "completed"
                else {}
            ),
        },
        actor=attempt["child_id"],
    )
    saved = state["attempts"][attempt["attempt_id"]]
    assert saved["status"] == ("succeeded" if stop == "completed" else "cancelled")
    assert saved["native_run_id"] is None
    assert saved["terminal_observation"] == observation
    assert state["status"] == "needs_attention"


def test_history_corroborates_native_terminal_without_overwriting_result(setup):
    plan(setup)
    attempt = reserve(setup)
    first = finish(setup, attempt)
    original = first["attempts"][attempt["attempt_id"]]
    observed = invoke(
        setup,
        "terminal",
        {
            "attempt_id": attempt["attempt_id"],
            "child_id": attempt["child_id"],
            "terminal_observation": {
                "kind": "history",
                "child_id": attempt["child_id"],
                "end_seq": 50,
                "event_sha256": "f" * 64,
                "turn": 1,
            },
            "stop_reason": "completed",
            "result": original["result"],
            "evidence_snapshot": original["evidence_snapshot"],
        },
        actor=attempt["child_id"],
    )
    assert observed["operation_result"]["already_recorded"]
    saved = observed["attempts"][attempt["attempt_id"]]
    assert saved["native_run_id"] == original["native_run_id"]
    assert saved["result"] == original["result"]


def test_same_native_step_cannot_bypass_reservation_with_new_request_uuid(setup):
    invoke(
        setup,
        "model_request",
        {"request_id": "first-id", "reserved_tokens": 100, "turn": 3, "step": 2},
    )
    with pytest.raises(SpecialistError, match="回合步骤不可重复"):
        invoke(
            setup,
            "model_request",
            {"request_id": "different-id", "reserved_tokens": 100, "turn": 3, "step": 2},
        )
    invoke(setup, "recover", {})
    state = invoke(
        setup,
        "model_usage",
        {
            "request_id": "first-id",
            "input_tokens": 21,
            "output_tokens": 17,
        },
    )
    saved = next(iter(state["model_requests"].values()))
    assert (saved["turn"], saved["step"]) == (3, 2)
    assert saved["usage"] == {"input_tokens": 21, "output_tokens": 17}
    assert state["status"] == "needs_attention"


def test_model_request_identity_conflict_does_not_mutate_state(setup):
    state = invoke(
        setup, "model_request", {"request_id": "one", "reserved_tokens": 10}, call="stable"
    )
    with pytest.raises(SpecialistError, match="冲突"):
        invoke(setup, "model_request", {"request_id": "two", "reserved_tokens": 10}, call="stable")
    assert len(setup[2].read(setup[1])["model_requests"]) == len(state["model_requests"])


def complete_research(setup, *, settle_usage=True):
    invoke(setup, "model_request", {"request_id": "root", "reserved_tokens": 100})
    plan(setup)

    def complete_node(attempt):
        actor = attempt["child_id"]
        invoke(setup, "dispatch", {"attempt_id": attempt["attempt_id"], "child_id": actor})
        invoke(
            setup,
            "model_request",
            {"request_id": "child-first", "reserved_tokens": 100},
            actor=actor,
        )
        invoke(
            setup,
            "model_usage",
            {"request_id": "child-first", "input_tokens": 20, "output_tokens": 10},
            actor=actor,
        )
        return finish(setup, attempt)

    industry, quant = reserve(setup), reserve(setup, "quant")
    complete_node(industry)
    complete_node(quant)
    reviewer = reserve(setup, "review")
    state = complete_node(reviewer)
    if settle_usage:
        state = invoke(
            setup, "model_usage", {"request_id": "root", "input_tokens": 30, "output_tokens": 40}
        )
    return state, industry, quant, reviewer


def test_completed_in_time_remains_ready_after_deadline_and_recovery(setup):
    state, *_ = complete_research(setup)
    completed = state["completed_at"]
    assert state["finalization_ready"]
    assert completed == 1000.0
    setup[-1][0] += 2000
    later = setup[2].read(setup[1])
    assert later["finalization_ready"]
    recovered = invoke(setup, "recover", {})
    assert recovered["status"] == "ready_for_validation"
    assert recovered["completed_at"] == completed
    assert recovered["finalization_ready"]


def test_completion_first_qualified_after_deadline_cannot_be_ready(setup):
    complete_research(setup, settle_usage=False)
    assert setup[2].read(setup[1])["model_requests"][f"{setup[1]}:root"]["usage"] is None
    setup[-1][0] += 2000
    late = invoke(
        setup, "model_usage", {"request_id": "root", "input_tokens": 30, "output_tokens": 40}
    )
    assert late["completed_at"] is None
    assert late["status"] == "needs_attention"
    assert not late["finalization_ready"]


def test_missing_or_partial_usage_never_becomes_fabricated_zero(setup):
    invoke(setup, "model_request", {"request_id": "unknown", "reserved_tokens": 100})
    for payload in ({"request_id": "unknown"}, {"request_id": "unknown", "input_tokens": 0}):
        with pytest.raises(SpecialistError):
            invoke(setup, "model_usage", payload)
    invoke(setup, "recover", {})
    saved = next(iter(setup[2].read(setup[1])["model_requests"].values()))
    assert saved["usage"] is None
    assert saved["reserved_tokens"] == 100
    measured = invoke(
        setup,
        "model_usage",
        {
            "request_id": "unknown",
            "input_tokens": 0,
            "output_tokens": 0,
        },
    )
    assert next(iter(measured["model_requests"].values()))["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
    }


def test_completed_result_requires_host_qualified_evidence_snapshot(setup):
    plan(setup)
    attempt = reserve(setup)
    missing = finish(setup, attempt, evidence_snapshot=None)
    assert missing["attempts"][attempt["attempt_id"]]["status"] == "failed"
    assert missing["attempts"][attempt["attempt_id"]]["stop_reason"] == "invalid_output"


def test_byte_drift_invalidates_finished_dependency_closure_without_erasing_outputs(setup):
    state, industry, quant, reviewer = complete_research(setup)
    assert state["finalization_ready"]
    state = setup[2].invalidate_evidence(setup[1], [industry["attempt_id"]])
    assert state["status"] == "needs_attention"
    assert not state["finalization_ready"]
    assert state["completed_at"] is None
    assert state["attempts"][industry["attempt_id"]]["invalidated"]
    assert state["attempts"][reviewer["attempt_id"]]["invalidated"]
    assert not state["attempts"][quant["attempt_id"]]["invalidated"]
    assert state["attempts"][industry["attempt_id"]]["result"]
    assert state["attempts"][reviewer["attempt_id"]]["evidence_snapshot"]
    assert len(state["model_requests"]) == 4


def test_byte_drift_requests_cancel_for_inflight_dependent_and_preserves_peer(setup):
    invoke(setup, "model_request", {"request_id": "root", "reserved_tokens": 100})
    plan(setup)
    industry, quant = reserve(setup), reserve(setup, "quant")
    finish(setup, industry)
    finish(setup, quant)
    reviewer = reserve(setup, "review")
    state = setup[2].invalidate_evidence(setup[1], [industry["attempt_id"]])
    assert state["operation_result"]["cancel_attempt_ids"] == [reviewer["attempt_id"]]
    assert state["attempts"][reviewer["attempt_id"]]["status"] == "cancel_requested"
    assert not state["attempts"][quant["attempt_id"]]["invalidated"]
    assert len(state["model_requests"]) == 1


def absence_witness(setup):
    return {
        "parent_session_id": setup[1],
        "parent_idle": True,
        "parent_terminal": {"end_seq": 17, "turn": 1, "event_sha256": "c" * 64},
        "catalog_complete": True,
        "child_ids": [],
    }


def test_reserved_but_never_dispatched_attempt_can_be_confirmed_not_submitted(setup):
    plan(setup)
    attempt = reserve(setup)
    recovered = invoke(setup, "recover", {})
    assert recovered["attempts"][attempt["attempt_id"]]["status"] == "reserved"
    qualified = setup[2].confirm_not_submitted(
        setup[1], [attempt["attempt_id"]], absence_witness(setup)
    )
    saved = qualified["attempts"][attempt["attempt_id"]]
    assert saved["status"] == "not_submitted"
    assert saved["terminated_at"] == 1000.0
    assert qualified["can_resume"]
    assert len(qualified["attempts"]) == 1
    assert not qualified["model_requests"]


def test_cancel_before_dispatch_preserves_phase_for_strict_absence_recovery(setup):
    plan(setup)
    attempt = reserve(setup)
    invoke(setup, "cancel", {})
    invoke(setup, "cancel", {})
    recovered = invoke(setup, "recover", {})
    previous = recovered["attempts"][attempt["attempt_id"]]
    assert previous["status"] == "cancel_requested"
    assert previous["cancelled_from_status"] == "reserved"
    assert previous.get("dispatch_at") is None
    qualified = setup[2].confirm_not_submitted(
        setup[1],
        [attempt["attempt_id"]],
        absence_witness(setup),
    )
    assert qualified["attempts"][attempt["attempt_id"]]["status"] == "not_submitted"
    assert qualified["status"] == "cancelled"
    assert qualified["can_resume"]
    assert len(qualified["attempts"]) == 1
    assert not qualified["model_requests"]


def test_dispatch_intent_prevents_absence_from_becoming_not_submitted(setup):
    plan(setup)
    attempt = reserve(setup)
    state = invoke(
        setup, "dispatch", {"attempt_id": attempt["attempt_id"], "child_id": attempt["child_id"]}
    )
    assert state["attempts"][attempt["attempt_id"]]["status"] == "dispatching"
    with pytest.raises(SpecialistError, match="不可重复"):
        invoke(
            setup,
            "dispatch",
            {"attempt_id": attempt["attempt_id"], "child_id": attempt["child_id"]},
        )
    invoke(setup, "recover", {})
    with pytest.raises(SpecialistError, match="无法证明"):
        setup[2].confirm_not_submitted(setup[1], [attempt["attempt_id"]], absence_witness(setup))
    assert setup[2].read(setup[1])["attempts"][attempt["attempt_id"]]["status"] == "unknown"


@pytest.mark.parametrize(
    "change",
    [
        {"parent_idle": False},
        {"catalog_complete": False},
        {"parent_session_id": str(uuid4())},
    ],
)
def test_incomplete_absence_witness_cannot_erase_a_reservation(setup, change):
    plan(setup)
    attempt = reserve(setup)
    with pytest.raises(SpecialistError):
        setup[2].confirm_not_submitted(
            setup[1], [attempt["attempt_id"]], {**absence_witness(setup), **change}
        )
    assert setup[2].read(setup[1])["attempts"][attempt["attempt_id"]]["status"] == "reserved"


def test_child_cannot_consume_model_budget_before_durable_dispatch(setup):
    plan(setup)
    attempt = reserve(setup)
    with pytest.raises(SpecialistError, match="不再允许模型调用"):
        invoke(
            setup,
            "model_request",
            {"request_id": "too-early", "reserved_tokens": 10},
            actor=attempt["child_id"],
        )


def test_node_prompt_binds_real_selected_skill_and_resource_version(setup):
    plan(setup)
    attempt = reserve(setup)
    expected = frozen_skills()["industry-research"]
    assert attempt["required_skill_names"] == [expected["native_name"]]
    assert attempt["skill_snapshots"]["industry-research"] == expected
    assert expected["native_name"] in attempt["prompt"]
    assert expected["resource_path"] in attempt["prompt"]
    assert "原生 skill 工具" in attempt["prompt"]


def test_unresolved_skill_mapping_never_silently_delegates_role_only(setup):
    store, _, ledger, budget, *_ = setup
    sid = store.create("fingpt", "missing skill")["id"]
    ledger.create(sid, budget, "2026-10-28", {"model": "test-model"}, "other-request")
    ledger.apply(
        sid, "plan", {"nodes": nodes(), "expected_version": 0}, agent_id=sid, call_id="plan"
    )
    with pytest.raises(SpecialistError, match="方法尚未冻结"):
        ledger.apply(
            sid,
            "reserve",
            {"node_id": "industry", "expected_version": 1, "max_tokens": 4096},
            agent_id=sid,
            call_id="reserve",
        )


def test_frozen_skill_versions_cannot_change_on_linked_resume(setup):
    _store, sid, ledger, budget, *_ = setup
    invoke(setup, "cancel", {})
    ledger.resume(sid, confirmed=True)
    changed = frozen_skills()
    changed["industry-research"]["resource_snapshot_sha256"] = "f" * 64
    with pytest.raises(SpecialistError, match="冻结研究方法版本"):
        ledger.create(
            sid, budget, "2026-10-28", {"model": "test-model"}, "second-request", skills=changed
        )


def test_root_known_usage_does_not_imply_missing_child_usage_is_zero(setup):
    invoke(setup, "model_request", {"request_id": "root", "reserved_tokens": 100})
    invoke(setup, "model_usage", {"request_id": "root", "input_tokens": 20, "output_tokens": 10})
    plan(setup)
    industry, quant = reserve(setup), reserve(setup, "quant")
    finish(setup, industry)
    finish(setup, quant)
    reviewer = reserve(setup, "review")
    state = finish(setup, reviewer)
    assert all(attempt["status"] == "succeeded" for attempt in state["attempts"].values())
    assert len(state["model_requests"]) == 1
    assert state["completed_at"] is None
    assert not state["finalization_ready"]
