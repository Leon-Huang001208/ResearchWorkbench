"""Bounded execution attempts; authorization and equivalence remain resolver-owned."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from core.observability import get_logger

from .providers import ProviderError, Result

log = get_logger(__name__)
Candidate = TypeVar("Candidate")
TOTAL_DEADLINE = 18.0  # Below the existing 22-second native bridge deadline.
MAX_ATTEMPTS = 4
HEALTH_LIMIT = 256
TRANSIENT_HEALTH_CODES = frozenset(
    {"deadline", "provider_timeout", "vendor_unreachable", "vendor_rate_limited"}
)
TRANSIENT_CODES = frozenset(
    {
        "deadline",
        "provider_timeout",
        "provider_busy",
        "provider_error",
        "vendor_unreachable",
        "vendor_rate_limited",
        "vendor_auth_failed",
        "vendor_permission_denied",
        "wind_not_logged_in",
        "wind_method_unavailable",
        "blocked_config",
        "missing_dependency",
        "vendor_schema_invalid",
    }
)


class CircuitBreaker:
    """Per-authority/endpoint health; a new configuration never inherits denial."""

    def __init__(self, *, clock=time.monotonic, threshold=3, cooldown=60.0):
        if threshold < 1 or cooldown <= 0:
            raise ValueError("data_health_policy_invalid")
        self.clock, self.threshold, self.cooldown = clock, threshold, cooldown
        self._states: dict[tuple[str, str, str], dict] = {}

    def available(self, key: tuple[str, str, str]) -> bool:
        state = self._states.get(key)
        return state is None or self.clock() >= state["open_until"]

    def record(self, key: tuple[str, str, str], *, accepted: bool, code: str | None):
        if key not in self._states and len(self._states) >= HEALTH_LIMIT:
            oldest = min(self._states, key=lambda item: self._states[item]["checked_at"])
            del self._states[oldest]
        state = self._states.setdefault(key, {"failures": 0, "open_until": 0.0})
        state["checked_at"] = self.clock()
        state["last_failure_code"] = code if code in TRANSIENT_CODES else None
        if accepted:
            state.update(failures=0, open_until=0.0)
        elif code in TRANSIENT_HEALTH_CODES:
            state["failures"] += 1
            if state["failures"] >= self.threshold:
                state["open_until"] = self.clock() + self.cooldown
                log.warning("datahub_circuit_opened", source=key[0], capability=key[1])

    def snapshot(self) -> list[dict]:
        return [
            {
                "source": key[0],
                "capability": key[1],
                "configuration_digest": key[2],
                **state,
                "available": self.available(key),
            }
            for key, state in self._states.items()
        ]


def failure_code(result: Result) -> str | None:
    """Only known non-sensitive codes enter execution diagnostics."""
    return next((code for code in result.limitations if code in TRANSIENT_CODES), None)


async def execute(
    *,
    resolve: Callable[[frozenset[str]], Candidate | None],
    fetch: Callable[[Candidate], Awaitable[Result]],
    source_id: Callable[[Candidate], str],
    budget: float = TOTAL_DEADLINE,
    allow_fallback: bool = True,
    accept_partial: bool = False,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[Result, Candidate]:
    """One logical call, one shared deadline; never retry an unknown outcome.

    The resolver must recheck current source authorization and query semantics
    on every invocation. Cancellation propagates to the owning DataHub lifecycle;
    it must drain actual synchronous futures before releasing their capacity.
    """
    if not 0 < budget <= TOTAL_DEADLINE:
        raise ValueError("data_query_budget_invalid")
    deadline = monotonic() + budget
    excluded: frozenset[str] = frozenset()
    attempts: list[dict] = []
    last: tuple[Result, Candidate] | None = None
    for _ in range(MAX_ATTEMPTS):
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        candidate = resolve(excluded)
        if candidate is None:
            break
        source = source_id(candidate)
        if source in excluded:
            break
        started = monotonic()
        timer = asyncio.timeout(remaining)
        try:
            async with timer:
                result = await fetch(candidate)
        except asyncio.CancelledError:
            if not timer.expired():
                raise
            # A drained storage cancellation subclasses CancelledError. The
            # deadline still owns it even when timeout cannot translate it.
            result = Result(status="failed", limitations=["deadline"])
        except TimeoutError:
            result = Result(status="failed", limitations=["deadline"])
        except ProviderError as exc:
            code = str(exc)
            if code not in TRANSIENT_CODES:
                log.warning("datahub_execution_rejected", source=source)
                raise
            result = Result(status="failed", limitations=[code])
        code = failure_code(result)
        accepted = result.status in {"complete", "snapshot", "empty"} or (
            accept_partial and result.status == "partial"
        )
        attempts.append(
            {
                "source": source,
                "stage": "execution",
                "status": result.status,
                "failure_code": code,
                "quality_accepted": accepted,
                "duration_ms": max(0, round((monotonic() - started) * 1000)),
            }
        )
        result.attempted_sources = [*attempts]
        result.metadata = {**result.metadata, "quality_accepted": accepted}
        last = result, candidate
        log.info(
            "datahub_execution_attempt",
            source=source,
            status=result.status,
            quality_accepted=accepted,
            attempt=len(attempts),
        )
        if accepted or not allow_fallback or (result.status == "failed" and code is None):
            return last
        excluded = excluded | {source}
    if last is None:
        raise ProviderError("data_no_authorized_candidate")
    return last
