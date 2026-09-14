"""Deterministic CPU workload budgets copied into reviewed calculator Skills."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Final

LOGGER = logging.getLogger("research_web.skills.cpu_budget")
MAX_INPUT_ROWS: Final = 50_000
MAX_INPUT_BYTES: Final = 64 * 1024 * 1024
MAX_SERIES_ROWS: Final = 5_000
MAX_SYMBOLS: Final = 50
MAX_ROWS_PER_SYMBOL: Final = 1_000
MAX_ARTIFACT_BYTES: Final = 16 * 1024 * 1024


class WorkloadTooLarge(ValueError):
    """Stable, content-free workload rejection for reviewed calculators."""

    code = "workload_too_large"

    def __init__(self, **limit: int) -> None:
        self.metadata: dict[str, int | str] = {**limit, "suggestion": "reduce_scope"}
        super().__init__(self.code)


def _count(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name}_invalid")
    return value


@dataclass
class WorkloadBudget:
    """Accumulate inputs and artifacts without silently truncating either."""

    input_rows: int = 0
    input_bytes: int = 0
    artifact_bytes: int = 0
    _events: list[str] = field(default_factory=list, repr=False)

    def add_input(self, *, rows: int, bytes_count: int) -> None:
        rows = _count(rows, "rows")
        bytes_count = _count(bytes_count, "bytes_count")
        next_rows = self.input_rows + rows
        next_bytes = self.input_bytes + bytes_count
        if next_rows > MAX_INPUT_ROWS:
            LOGGER.warning("cpu_budget_rejected reason=input_rows")
            raise WorkloadTooLarge(max_rows=MAX_INPUT_ROWS)
        if next_bytes > MAX_INPUT_BYTES:
            LOGGER.warning("cpu_budget_rejected reason=input_bytes")
            raise WorkloadTooLarge(max_input_bytes=MAX_INPUT_BYTES)
        self.input_rows = next_rows
        self.input_bytes = next_bytes
        self._events.append("input")

    def validate_series(self, rows: int) -> None:
        if _count(rows, "series_rows") > MAX_SERIES_ROWS:
            LOGGER.warning("cpu_budget_rejected reason=series_rows")
            raise WorkloadTooLarge(max_series_rows=MAX_SERIES_ROWS)

    def validate_batch(self, *, symbol_count: int, rows_per_symbol: int) -> None:
        if _count(symbol_count, "symbol_count") > MAX_SYMBOLS:
            LOGGER.warning("cpu_budget_rejected reason=symbol_count")
            raise WorkloadTooLarge(max_symbols=MAX_SYMBOLS)
        if _count(rows_per_symbol, "rows_per_symbol") > MAX_ROWS_PER_SYMBOL:
            LOGGER.warning("cpu_budget_rejected reason=rows_per_symbol")
            raise WorkloadTooLarge(max_rows_per_symbol=MAX_ROWS_PER_SYMBOL)

    def add_artifact(self, bytes_count: int) -> None:
        next_bytes = self.artifact_bytes + _count(bytes_count, "artifact_bytes")
        if next_bytes > MAX_ARTIFACT_BYTES:
            LOGGER.warning("cpu_budget_rejected reason=artifact_bytes")
            raise WorkloadTooLarge(max_artifact_bytes=MAX_ARTIFACT_BYTES)
        self.artifact_bytes = next_bytes
        self._events.append("artifact")
