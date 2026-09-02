"""Bounded Supervisor execution over a typed in-memory shared blackboard."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.contracts.research_workspace import (
    AgentTeamDefinition,
    BlackboardEntry,
)
from core.observability import get_logger
from services.runtime_provider_service import validate_safe_output

logger = get_logger(__name__)


class AgentBudgetError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class AgentAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1)
    task: dict[str, Any]
    reserve_tokens: int | None = Field(default=None, ge=1)
    reserve_cost: float | None = Field(default=None, ge=0)
    remaining_seconds: float | None = Field(default=None, gt=0)
    blackboard_snapshot: tuple[BlackboardEntry, ...] = ()


class AgentWorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    tokens_used: int = Field(ge=0)
    cost_used: float = Field(ge=0)


class AgentSupervisorContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str
    supervisor_role: str
    next_step: int = Field(ge=1)
    remaining_steps: int = Field(ge=0)
    reserve_tokens: int = Field(ge=0)
    reserve_cost: float = Field(ge=0)
    remaining_seconds: float = Field(gt=0)
    initial_plan: tuple[AgentAssignment, ...] = ()
    blackboard_snapshot: tuple[BlackboardEntry, ...] = ()


class AgentSupervisorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["assign", "complete"]
    assignments: list[AgentAssignment] = Field(default_factory=list)
    tokens_used: int = Field(ge=0)
    cost_used: float = Field(ge=0)

    def model_post_init(self, __context: Any, /) -> None:
        if self.action == "assign" and not self.assignments:
            raise ValueError("assign action requires at least one assignment")
        if self.action == "complete" and self.assignments:
            raise ValueError("complete action cannot include assignments")


class AgentTeamRun(BaseModel):
    status: str
    steps_used: int
    tokens_used: int
    cost_used: float
    blackboard: list[BlackboardEntry]


class AgentTeamService:
    """Supervisor is the only coordinator; workers exchange no direct messages."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None, repository=None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._repository = repository

    def save_team(self, team: AgentTeamDefinition) -> AgentTeamDefinition:
        if self._repository is None:
            raise RuntimeError("agent team repository is required")
        return self._repository.save_agent_team(team)

    def list_teams(self) -> list[AgentTeamDefinition]:
        return self._repository.list_agent_teams() if self._repository is not None else []

    def get_team(self, team_id: str) -> AgentTeamDefinition:
        if self._repository is None:
            raise KeyError(team_id)
        return self._repository.get_agent_team(team_id)

    def execute_plan(
        self,
        team: AgentTeamDefinition,
        steps: Sequence[dict[str, Any] | AgentAssignment],
        worker: Callable[[AgentAssignment], dict[str, Any] | AgentWorkerResult],
        *,
        supervisor: (
            Callable[[AgentSupervisorContext], dict[str, Any] | AgentSupervisorResult] | None
        ) = None,
    ) -> AgentTeamRun:
        if team.status != "active":
            raise AgentBudgetError("agent team is not active", code="blocked_runtime")
        if len(steps) > team.budget.max_steps:
            raise AgentBudgetError("maximum steps exceeded", code="budget_exhausted")
        started_at = self._clock()
        blackboard: list[BlackboardEntry] = []
        tokens = 0
        cost = 0.0
        pending = [AgentAssignment.model_validate(item) for item in steps]
        expanded_results: set[str] = set()
        steps_used = 0
        while True:
            remaining_seconds = self._remaining_seconds(team, started_at)
            remaining_tokens = team.budget.max_tokens - tokens
            remaining_cost = team.budget.max_cost - cost
            if remaining_tokens < 0 or remaining_cost < 0:
                raise AgentBudgetError("token or cost budget exhausted", code="budget_exhausted")
            supervisor_context = AgentSupervisorContext(
                team_id=team.team_id,
                supervisor_role=team.supervisor_role,
                next_step=steps_used + 1,
                remaining_steps=team.budget.max_steps - steps_used,
                reserve_tokens=min(512, remaining_tokens),
                reserve_cost=remaining_cost,
                remaining_seconds=remaining_seconds,
                initial_plan=tuple(pending),
                blackboard_snapshot=tuple(blackboard),
            )
            if supervisor is None:
                raw_decision = self._local_supervisor_decision(
                    pending,
                    blackboard,
                    expanded_results,
                )
            else:
                raw_decision = supervisor(supervisor_context)
            decision = AgentSupervisorResult.model_validate(raw_decision)
            if (
                decision.tokens_used > supervisor_context.reserve_tokens
                or decision.cost_used > supervisor_context.reserve_cost
            ):
                raise AgentBudgetError(
                    "supervisor exceeded its budget reservation",
                    code="budget_exhausted",
                )
            tokens += decision.tokens_used
            cost += decision.cost_used
            self._check_deadline(team, started_at)
            if decision.action == "complete":
                break
            if len(decision.assignments) > team.budget.max_concurrency:
                raise AgentBudgetError("maximum concurrency exceeded", code="budget_exhausted")
            if steps_used + len(decision.assignments) > team.budget.max_steps:
                raise AgentBudgetError("maximum steps exceeded", code="budget_exhausted")
            for raw_assignment in decision.assignments:
                remaining_seconds = self._remaining_seconds(team, started_at)
                assignment = raw_assignment.model_copy(
                    update={"blackboard_snapshot": tuple(blackboard)}
                )
                if assignment.role not in team.roles or assignment.role == team.supervisor_role:
                    raise AgentBudgetError("invalid worker role", code="blocked_runtime")
                step_number = steps_used + 1
                blackboard.append(
                    BlackboardEntry(
                        entry_id=f"blackboard-{uuid4().hex}",
                        team_id=team.team_id,
                        role=assignment.role,
                        entry_type="assignment",
                        step=step_number,
                        payload=assignment.task,
                        created_at=self._clock(),
                    )
                )
                remaining_tokens = team.budget.max_tokens - tokens
                remaining_cost = team.budget.max_cost - cost
                reserved_tokens = assignment.reserve_tokens or remaining_tokens
                reserved_cost = (
                    assignment.reserve_cost
                    if assignment.reserve_cost is not None
                    else remaining_cost
                )
                if reserved_tokens > remaining_tokens or reserved_cost > remaining_cost:
                    raise AgentBudgetError(
                        "worker budget reservation exceeds remaining budget",
                        code="budget_exhausted",
                    )
                assignment = assignment.model_copy(
                    update={
                        "reserve_tokens": reserved_tokens,
                        "reserve_cost": reserved_cost,
                        "remaining_seconds": remaining_seconds,
                    }
                )
                raw_result = worker(assignment)
                result = AgentWorkerResult.model_validate(raw_result)
                validate_safe_output(result.payload)
                self._check_deadline(team, started_at)
                if result.tokens_used > reserved_tokens or result.cost_used > reserved_cost:
                    raise AgentBudgetError(
                        "worker exceeded its budget reservation",
                        code="budget_exhausted",
                    )
                tokens += result.tokens_used
                cost += result.cost_used
                if tokens > team.budget.max_tokens or cost > team.budget.max_cost:
                    raise AgentBudgetError(
                        "token or cost budget exhausted", code="budget_exhausted"
                    )
                blackboard.append(
                    BlackboardEntry(
                        entry_id=f"blackboard-{uuid4().hex}",
                        team_id=team.team_id,
                        role=assignment.role,
                        entry_type="result",
                        step=step_number,
                        payload=result.payload,
                        created_at=self._clock(),
                    )
                )
                steps_used += 1
        return AgentTeamRun(
            status="completed",
            steps_used=steps_used,
            tokens_used=tokens,
            cost_used=cost,
            blackboard=blackboard,
        )

    def execute_batch(
        self,
        team: AgentTeamDefinition,
        assignments: Sequence[dict[str, Any] | AgentAssignment],
        worker: Callable[[AgentAssignment], dict[str, Any] | AgentWorkerResult],
    ) -> AgentTeamRun:
        if len(assignments) > team.budget.max_concurrency:
            raise AgentBudgetError("maximum concurrency exceeded", code="budget_exhausted")
        return self.execute_plan(team, assignments, worker)

    @staticmethod
    def _local_supervisor_decision(
        pending: list[AgentAssignment],
        blackboard: list[BlackboardEntry],
        expanded_results: set[str],
    ) -> AgentSupervisorResult:
        for entry in reversed(blackboard):
            if entry.entry_type != "result" or entry.entry_id in expanded_results:
                continue
            expanded_results.add(entry.entry_id)
            if entry.payload.get("supervisor_complete") is True:
                return AgentSupervisorResult(action="complete", tokens_used=0, cost_used=0)
            next_steps = entry.payload.get("next_steps")
            if isinstance(next_steps, list):
                pending[0:0] = [AgentAssignment.model_validate(item) for item in next_steps]
            break
        if not pending:
            return AgentSupervisorResult(action="complete", tokens_used=0, cost_used=0)
        return AgentSupervisorResult(
            action="assign",
            assignments=[pending.pop(0)],
            tokens_used=0,
            cost_used=0,
        )

    def _check_deadline(self, team: AgentTeamDefinition, started_at: datetime) -> None:
        self._remaining_seconds(team, started_at)

    def _remaining_seconds(self, team: AgentTeamDefinition, started_at: datetime) -> float:
        elapsed = (self._clock() - started_at).total_seconds()
        remaining = team.budget.deadline_seconds - elapsed
        if remaining <= 0:
            raise AgentBudgetError("agent deadline exceeded", code="deadline_exceeded")
        return remaining
