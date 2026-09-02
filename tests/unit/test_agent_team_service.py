"""Supervisor and typed shared-blackboard execution tests."""

from datetime import UTC, datetime, timedelta

import pytest

from core.contracts.research_workspace import AgentBudget, AgentTeamDefinition
from services.agent_team_service import AgentBudgetError, AgentTeamService

NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def _team(**budget_overrides) -> AgentTeamDefinition:
    budget = {
        "max_steps": 2,
        "max_concurrency": 2,
        "max_tokens": 100,
        "max_cost": 1.0,
        "deadline_seconds": 60,
    }
    budget.update(budget_overrides)
    return AgentTeamDefinition(
        team_id="team-1",
        name="Research team",
        supervisor_role="supervisor",
        roles=["supervisor", "analyst"],
        budget=AgentBudget(**budget),
        status="active",
    )


def test_supervisor_writes_typed_assignments_and_results_to_shared_blackboard():
    service = AgentTeamService(clock=lambda: NOW)

    result = service.execute_plan(
        _team(),
        [
            {"role": "analyst", "task": {"question": "供需"}},
            {"role": "analyst", "task": {"question": "估值"}},
        ],
        lambda assignment: {
            "payload": {"answer": assignment.task["question"]},
            "tokens_used": 20,
            "cost_used": 0.1,
        },
    )

    assert result.status == "completed"
    assert result.steps_used == 2
    assert [entry.entry_type for entry in result.blackboard] == [
        "assignment",
        "result",
        "assignment",
        "result",
    ]
    assert result.blackboard[-1].payload == {"answer": "估值"}


@pytest.mark.parametrize(
    ("team", "steps", "worker", "code"),
    [
        (
            _team(max_steps=1),
            [{"role": "analyst", "task": {}}, {"role": "analyst", "task": {}}],
            lambda _: {"payload": {}, "tokens_used": 1, "cost_used": 0},
            "budget_exhausted",
        ),
        (
            _team(max_tokens=10),
            [{"role": "analyst", "task": {}}],
            lambda _: {"payload": {}, "tokens_used": 11, "cost_used": 0},
            "budget_exhausted",
        ),
        (
            _team(max_cost=0.1),
            [{"role": "analyst", "task": {}}],
            lambda _: {"payload": {}, "tokens_used": 1, "cost_used": 0.2},
            "budget_exhausted",
        ),
    ],
)
def test_team_enforces_step_token_and_cost_budgets(team, steps, worker, code):
    with pytest.raises(AgentBudgetError) as exc:
        AgentTeamService(clock=lambda: NOW).execute_plan(team, steps, worker)
    assert exc.value.code == code


def test_team_enforces_concurrency_and_deadline_before_worker_execution():
    service = AgentTeamService(clock=lambda: NOW)
    with pytest.raises(AgentBudgetError, match="concurrency"):
        service.execute_batch(
            _team(max_concurrency=1),
            [
                {"role": "analyst", "task": {"id": 1}},
                {"role": "analyst", "task": {"id": 2}},
            ],
            lambda _: {"payload": {}, "tokens_used": 1, "cost_used": 0},
        )

    times = iter([NOW, NOW + timedelta(seconds=61)])
    with pytest.raises(AgentBudgetError) as exc:
        AgentTeamService(clock=lambda: next(times)).execute_plan(
            _team(),
            [{"role": "analyst", "task": {}}],
            lambda _: {"payload": {}, "tokens_used": 1, "cost_used": 0},
        )
    assert exc.value.code == "deadline_exceeded"


def test_team_rechecks_deadline_after_every_worker_step():
    times = iter([NOW, NOW, NOW, NOW + timedelta(seconds=61)])
    with pytest.raises(AgentBudgetError) as exc:
        AgentTeamService(clock=lambda: next(times)).execute_plan(
            _team(),
            [{"role": "analyst", "task": {}}],
            lambda _: {"payload": {}, "tokens_used": 1, "cost_used": 0},
        )
    assert exc.value.code == "deadline_exceeded"


def test_team_reserves_budget_before_call_and_enforces_hard_deadline():
    received = []

    def bounded_worker(assignment):
        received.append(assignment)
        return {"payload": {}, "tokens_used": 2, "cost_used": 0.01}

    result = AgentTeamService(clock=lambda: NOW).execute_plan(
        _team(deadline_seconds=10, max_tokens=10, max_cost=0.1),
        [
            {
                "role": "analyst",
                "task": {},
                "reserve_tokens": 2,
                "reserve_cost": 0.01,
            }
        ],
        bounded_worker,
    )
    assert result.status == "completed"
    assert received[0].reserve_tokens == 2
    assert received[0].reserve_cost == 0.01
    assert received[0].remaining_seconds == 10

    with pytest.raises(AgentBudgetError, match="reservation"):
        AgentTeamService(clock=lambda: NOW).execute_plan(
            _team(max_tokens=1),
            [{"role": "analyst", "task": {}, "reserve_tokens": 2}],
            lambda _: (_ for _ in ()).throw(AssertionError("worker must not run")),
        )


def test_agent_sensitive_output_is_rejected_before_blackboard_write():
    with pytest.raises(ValueError, match="sensitive"):
        AgentTeamService(clock=lambda: NOW).execute_plan(
            _team(),
            [{"role": "analyst", "task": {}}],
            lambda _: {
                "payload": {"authorization": "Bearer should-not-persist"},
                "tokens_used": 1,
                "cost_used": 0,
            },
        )


def test_supervisor_dynamically_adds_second_step_from_read_only_blackboard():
    supervisor_calls = []
    worker_snapshots = []

    def supervisor(context):
        supervisor_calls.append(context)
        results = [entry for entry in context.blackboard_snapshot if entry.entry_type == "result"]
        if not results:
            return {
                "action": "assign",
                "assignments": [{"role": "analyst", "task": {"question": "先核验供给"}}],
                "tokens_used": 2,
                "cost_used": 0.01,
            }
        if len(results) == 1:
            assert results[0].payload["signal"] == "supply-tight"
            return {
                "action": "assign",
                "assignments": [
                    {
                        "role": "analyst",
                        "task": {
                            "question": "根据供给结果核验需求",
                            "prior_signal": results[0].payload["signal"],
                        },
                    }
                ],
                "tokens_used": 2,
                "cost_used": 0.01,
            }
        return {
            "action": "complete",
            "assignments": [],
            "tokens_used": 1,
            "cost_used": 0.005,
        }

    def worker(assignment):
        worker_snapshots.append(assignment.blackboard_snapshot)
        if assignment.task["question"] == "先核验供给":
            return {
                "payload": {"signal": "supply-tight"},
                "tokens_used": 10,
                "cost_used": 0.1,
            }
        assert assignment.task["prior_signal"] == "supply-tight"
        return {
            "payload": {"signal": "demand-stable"},
            "tokens_used": 10,
            "cost_used": 0.1,
        }

    result = AgentTeamService(clock=lambda: NOW).execute_plan(
        _team(max_steps=3, max_tokens=100, max_cost=1),
        [],
        worker,
        supervisor=supervisor,
    )

    assert result.status == "completed"
    assert result.steps_used == 2
    assert len(supervisor_calls) == 3
    assert worker_snapshots[0] == ()
    assert any(entry.payload.get("signal") == "supply-tight" for entry in worker_snapshots[1])
    assert result.tokens_used == 25
    assert result.cost_used == pytest.approx(0.225)
