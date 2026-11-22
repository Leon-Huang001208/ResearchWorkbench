"""Thread-propagated, per-operation cancellation and truthful commit outcomes."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Event, RLock

from core.observability import get_logger

from .models import MarketStoreError

log = get_logger(__name__)


@dataclass(frozen=True)
class OperationOutcome:
    committed: bool
    cancelled: bool
    result: object = None


class MarketStoreCancelled(MarketStoreError):
    def __init__(self, outcome):
        super().__init__("warehouse_operation_cancelled")
        self.outcome = outcome


class OperationContext:
    """One Event per operation. Cancellation never touches other calls/users.

    A cancellation requested during an in-flight database commit cannot promise
    rollback: committed/result remain authoritative after the worker is drained.
    """

    def __init__(self):
        self._cancelled = Event()
        self._lock = RLock()
        self._committed = False
        self._result = None

    def cancel(self):
        self._cancelled.set()

    @property
    def committed(self):
        with self._lock:
            return self._committed

    @property
    def outcome(self):
        with self._lock:
            return OperationOutcome(self._committed, self._cancelled.is_set(), self._result)

    def checkpoint(self):
        if self._cancelled.is_set():
            log.info("market_store_operation_cancelled", committed=self.committed)
            raise MarketStoreCancelled(self.outcome)

    def record_committed(self, result=None):
        with self._lock:
            self._committed = True
            if result is not None:
                self._result = result


_CURRENT: ContextVar[OperationContext | None] = ContextVar("market_store_operation", default=None)


@contextmanager
def operation_context(context=None):
    current = context if context is not None else OperationContext()
    if not isinstance(current, OperationContext):
        raise MarketStoreError("invalid_operation_context")
    token = _CURRENT.set(current)
    try:
        yield current
    finally:
        _CURRENT.reset(token)


def checkpoint():
    current = _CURRENT.get()
    if current is not None:
        current.checkpoint()


def record_committed(result=None):
    current = _CURRENT.get()
    if current is not None:
        current.record_committed(result)
