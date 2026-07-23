"""Point-in-time factor matrix construction."""

from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

from core.contracts.factors import FactorDefinition, FactorValue
from core.observability import get_logger

logger = get_logger(__name__)


class FactorMatrixBuilder:
    """Build a cross-sectional factor matrix for one trading date."""

    def __init__(self, definitions: Iterable[FactorDefinition] | None = None):
        self._definitions: dict[str, FactorDefinition] = {}
        self._definition_order: list[str] = []
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: FactorDefinition) -> None:
        """Register or replace a factor definition."""
        if definition.factor_id not in self._definitions:
            self._definition_order.append(definition.factor_id)
        self._definitions[definition.factor_id] = definition
        logger.debug("factor definition registered", factor_id=definition.factor_id)

    def build(
        self,
        values: Iterable[FactorValue],
        as_of_date: date,
        subject_ids: Iterable[str] | None = None,
        factor_ids: Iterable[str] | None = None,
    ) -> pd.DataFrame:
        """Pivot factor observations into `subjects x factors`.

        Only values whose `as_of_date` exactly matches the requested trading date are used.
        Missing subject/factor pairs remain `NaN`, which is intentional for coverage analysis.
        """
        requested_subjects = list(subject_ids) if subject_ids is not None else None
        requested_factors = list(factor_ids) if factor_ids is not None else None
        rows: list[dict[str, object]] = []

        for value in values:
            if value.as_of_date != as_of_date:
                continue
            if requested_subjects is not None and value.subject_id not in requested_subjects:
                continue
            if requested_factors is not None and value.factor_id not in requested_factors:
                continue
            rows.append(
                {
                    "subject_id": value.subject_id,
                    "factor_id": value.factor_id,
                    "value": value.value,
                }
            )

        factor_order = self._ordered_factor_ids(requested_factors, rows)
        subject_order = self._ordered_subject_ids(requested_subjects, rows)

        if not rows:
            return pd.DataFrame(index=subject_order, columns=factor_order, dtype=float)

        raw = pd.DataFrame(rows)
        matrix = raw.pivot_table(
            index="subject_id",
            columns="factor_id",
            values="value",
            aggfunc="last",
            dropna=False,
        )
        matrix = matrix.reindex(index=subject_order, columns=factor_order)
        logger.info(
            "factor matrix built",
            as_of_date=as_of_date.isoformat(),
            subject_count=len(matrix.index),
            factor_count=len(matrix.columns),
        )
        return matrix.astype(float)

    def _ordered_factor_ids(
        self,
        requested_factors: list[str] | None,
        rows: list[dict[str, object]],
    ) -> list[str]:
        if requested_factors is not None:
            return requested_factors
        observed = [str(row["factor_id"]) for row in rows]
        observed_set = set(observed)
        ordered = [factor_id for factor_id in self._definition_order if factor_id in observed_set]
        ordered.extend(sorted(observed_set.difference(ordered)))
        return ordered

    @staticmethod
    def _ordered_subject_ids(
        requested_subjects: list[str] | None,
        rows: list[dict[str, object]],
    ) -> list[str]:
        if requested_subjects is not None:
            return requested_subjects
        return sorted({str(row["subject_id"]) for row in rows})
