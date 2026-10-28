"""IO-free complete results for a future reviewed Native writer.

Canonical JSON here means finite UTF-8 JSON, sorted object keys, compact separators.
Its normalized-input digest is not the hash of an original Host source file.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from core.observability import get_logger

from .contracts import encoded, require

log = get_logger(__name__)
MAX_FULL_RESULT_BYTES = 16 * 1024 * 1024


def canonical_json(value: Any, limit: int | None = None) -> bytes:
    return encoded(value, limit, sort_keys=True)


@dataclass(frozen=True)
class FullResultArtifact:
    """Immutable actual bytes and descriptors; never Host authority or a path."""

    canonical_json: bytes
    sha256: str
    byte_count: int
    root_row_count: int
    component_row_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ExecutionBundle:
    receipt: dict
    full_result: FullResultArtifact


@dataclass(frozen=True)
class _Calculation:
    receipt: dict
    full: dict
    components: tuple[dict, ...] = ()


class FullClosureBudget:
    """Count complete components before retaining the next component closure."""

    def __init__(self) -> None:
        self.byte_count = 2

    def add(self, component: dict) -> None:
        size = len(canonical_json(component, MAX_FULL_RESULT_BYTES - self.byte_count))
        self.byte_count += size + 1
        require(self.byte_count <= MAX_FULL_RESULT_BYTES, "workload_too_large")


def capture_result(
    receipt: dict,
    full_rows: list,
    canonical_input_sha256: str,
    components: tuple[dict, ...] | list[dict] = (),
) -> _Calculation:
    """Capture pre-projection rows from the one calculation, without copying them."""
    full = {
        key: value
        for key, value in receipt.items()
        if key not in {"rows", "row_delivery", "result_sha256"}
    }
    full.update(
        {
            "rows": full_rows,
            "counts": {
                "processed_input_rows": receipt["processed_input_rows"],
                "total_output_rows": len(full_rows),
                "missing_count": len(receipt["missing"]),
                "rejected_count": len(receipt["rejected_rows"]),
                "source_ref_count": len(receipt["source_refs"]),
            },
            "input_digest_kind": "normalized_canonical_json_v1",
            "input_sha256": canonical_input_sha256,
            "canonical_input_sha256": canonical_input_sha256,
            "legacy_normalized_input_sha256": receipt["input_sha256"],
            "receipt_sha256": receipt["result_sha256"],
            "code_version": {
                "method_version": receipt["method_version"],
                "source_binding": "host_required",
                "source_sha256": None,
                "frozen_resource_version": None,
            },
            "source_locator_contract": "host_frozen_snapshot_readback_required",
        }
    )
    return _Calculation(receipt, full, tuple(components))


def build_bundle(calculation: _Calculation) -> ExecutionBundle:
    """Serialize one complete closure under a single aggregate byte budget."""
    component_counts = tuple(
        (item["method"], item["counts"]["total_output_rows"]) for item in calculation.components
    )
    payload = {
        "schema": "research_pack_full_result_v1",
        "schema_version": 1,
        "root_rows_kind": (
            "component_references"
            if calculation.full["method"].startswith("pack:")
            else "calculation_rows"
        ),
        "root": calculation.full,
        "components": calculation.components,
        "counts": {
            "root_output_rows": calculation.full["counts"]["total_output_rows"],
            "component_output_rows": dict(component_counts),
        },
    }
    data = canonical_json(payload, MAX_FULL_RESULT_BYTES)
    artifact = FullResultArtifact(
        data,
        hashlib.sha256(data).hexdigest(),
        len(data),
        calculation.full["counts"]["total_output_rows"],
        component_counts,
    )
    log.info(
        "research_pack_full_result_serialized root_rows=%d components=%d bytes=%d sha256=%s",
        artifact.root_row_count,
        len(component_counts),
        artifact.byte_count,
        artifact.sha256,
    )
    return ExecutionBundle(calculation.receipt, artifact)
