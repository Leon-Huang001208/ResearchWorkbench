"""Frozen GET protocol: reject unsupported reads before business reconciliation."""

from pathlib import PurePosixPath

from core.observability import get_logger

from ..store import StoreError

HEADER = "X-RWB-Frozen-Read"
VERSION = "v1"
log = get_logger(__name__)


def strict_read(request) -> bool:
    value = request.headers.get(HEADER)
    if value is not None and value != VERSION:
        reject()
    return value == VERSION


def reject() -> None:
    log.warning("mcp_frozen_read_rejected")
    raise StoreError("此材料不支持冻结只读访问", "frozen_read_unsupported", 409)


def input_text(relative: str) -> None:
    path = PurePosixPath(relative)
    if (
        not relative.startswith("inputs/")
        or "\\" in relative
        or ".." in path.parts
        or path.suffix.lower() not in {".txt", ".md", ".csv", ".json"}
    ):
        reject()
