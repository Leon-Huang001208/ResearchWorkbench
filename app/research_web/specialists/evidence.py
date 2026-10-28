"""Bind node references to owned bytes and provenance, never path identities alone."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any

from core.observability import get_logger

from ..datahub.security import directory, read_file
from ..research_web_sources import stored_sources, upload_evidence_files
from ..store import StoreError
from .contracts import NodeResult, SpecialistError
from .ledger import SpecialistLedger

log = get_logger(__name__)
MAX_BYTES = 64 * 1024 * 1024
MAX_DATASET_FILES = 512
FILE_ID = re.compile(r"^[a-f0-9]{24}$")
DATASET_ID = re.compile(r"^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RAW_NAME = re.compile(r"^raw-[0-9]{4}\.bin$")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


class _ReadBudget:
    def __init__(self) -> None:
        self.remaining = MAX_BYTES

    def accept(self, raw: bytes) -> bytes:
        if not isinstance(raw, bytes) or len(raw) > self.remaining:
            raise SpecialistError("节点证据原件超过读取上限", "specialist_evidence_limit", 409)
        self.remaining -= len(raw)
        return raw


def _dates(metadata: dict[str, Any], cutoff: date) -> None:
    """Acquisition time is not publication time or historical PIT proof."""
    values = [
        metadata.get(key)
        for key in (
            "as_of",
            "published_at",
            "publication_date",
            "disclosure_date",
            "released_at",
        )
    ]
    values.extend(
        row.get("date") for row in metadata.get("date_evidence", []) if isinstance(row, dict)
    )
    for value in values:
        if value in {None, "", "unknown"}:
            continue
        if not isinstance(value, str):
            raise SpecialistError("来源日期无法核验", "specialist_evidence_date_unknown", 409)
        try:
            observed = (
                date.fromisoformat(value)
                if len(value) == 10
                else datetime.fromisoformat(value).date()
            )
        except ValueError as exc:
            raise SpecialistError(
                "来源日期无法核验", "specialist_evidence_date_unknown", 409
            ) from exc
        if observed > cutoff:
            raise SpecialistError(
                "来源披露时间晚于冻结研究截止日", "specialist_evidence_after_cutoff", 409
            )


def _file_snapshot(
    service: Any,
    sid: str,
    fid: str,
    kind: str,
    files: dict[str, dict],
    budget: _ReadBudget,
    expected_sha: str | None = None,
) -> str:
    item = files.get(fid)
    if not FILE_ID.fullmatch(fid) or item is None or item.get("kind") != kind:
        raise SpecialistError(
            "文件不属于当前研究的指定证据类型", "specialist_evidence_unbound", 409
        )
    stream, _ = service.store.open_file(sid, fid)
    with stream:
        raw = budget.accept(stream.read(budget.remaining + 1))
    actual = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None and actual != expected_sha:
        raise SpecialistError("读取期间来源正文变化", "specialist_evidence_changed", 409)
    return _digest({"kind": kind, "file_id": fid, "sha256": actual, "size": len(raw)})


def _dataset_snapshot(service: Any, sid: str, did: str, cutoff: date, budget: _ReadBudget) -> str:
    if not DATASET_ID.fullmatch(did):
        raise SpecialistError("数据集引用身份无效", "specialist_evidence_unbound", 409)
    snapshots = service.datahub.snapshots
    manifest = snapshots.detail(sid, did)
    if (
        manifest.get("dataset_id") != did
        or manifest.get("id") != did
        or manifest.get("status") not in {"complete", "success"}
        or not SHA256.fullmatch(str(manifest.get("manifest_sha256", "")))
        or manifest.get("admission", {}).get("report_admitted") is False
        or (
            manifest.get("snapshot_kind") == "mcp_evidence"
            and manifest.get("admission", {}).get("report_admitted") is not True
        )
    ):
        raise SpecialistError(
            "数据集仍是线索、缺口或未经核验", "specialist_evidence_unqualified", 409
        )
    _dates(manifest, cutoff)
    public, originals = manifest.get("files"), manifest.get("raw_files")
    if (
        not isinstance(public, list)
        or not public
        or not isinstance(originals, list)
        or len(public) + len(originals) > MAX_DATASET_FILES
    ):
        raise SpecialistError("数据集文件清单不可核验", "specialist_evidence_unbound", 409)
    if not originals and manifest.get("snapshot_kind") != "hot_evidence":
        raise SpecialistError("数据集缺少来源原件", "specialist_evidence_original_missing", 409)
    seen, hashes = set(), {}
    # Snapshot.read independently authorizes the private/public manifest binding.
    # Then descriptor reads verify each declared public file once, avoiding the
    # quadratic full-snapshot revalidation of Snapshot.read for every object.
    manifest_bytes = budget.accept(snapshots.read(sid, did, "manifest.json"))
    with directory(service.store.root, ("sessions", sid, "inputs", "datasets", did)) as folder:
        for entry in public:
            name = entry.get("name")
            if (
                not isinstance(name, str)
                or name in seen
                or not SHA256.fullmatch(str(entry.get("sha256", "")))
            ):
                raise SpecialistError("数据集文件清单不可核验", "specialist_evidence_unbound", 409)
            seen.add(name)
            raw = (
                manifest_bytes
                if name == "manifest.json"
                else budget.accept(read_file(folder, name, limit=budget.remaining))
            )
            actual = hashlib.sha256(raw).hexdigest()
            if actual != entry["sha256"] or (
                entry.get("size") is not None and entry["size"] != len(raw)
            ):
                raise SpecialistError("数据集公开文件已变化", "specialist_evidence_changed", 409)
            hashes["public:" + name] = actual
    with directory(service.store.root, (".control", "snapshots", sid, did), private=True) as folder:
        for entry in originals:
            name = entry.get("name")
            if (
                not isinstance(name, str)
                or not RAW_NAME.fullmatch(name)
                or name in seen
                or not SHA256.fullmatch(str(entry.get("sha256", "")))
                or entry.get("path") != f".control/snapshots/{sid}/{did}/{name}"
            ):
                raise SpecialistError("来源原件清单不可核验", "specialist_evidence_unbound", 409)
            seen.add(name)
            raw = budget.accept(read_file(folder, name, private=True, limit=budget.remaining))
            actual = hashlib.sha256(raw).hexdigest()
            if actual != entry["sha256"] or (
                entry.get("size") is not None and entry["size"] != len(raw)
            ):
                raise SpecialistError("数据集来源原件已变化", "specialist_evidence_changed", 409)
            hashes["original:" + name] = actual
    if snapshots.detail(sid, did)["manifest_sha256"] != manifest["manifest_sha256"]:
        raise SpecialistError("读取期间数据集版本变化", "specialist_evidence_changed", 409)
    return _digest({"manifest": manifest, "bytes": hashes})


def evidence_snapshot(service: Any, sid: str, result: dict[str, Any]) -> dict[str, str]:
    """Freeze reference hashes from current owned bytes under the original cutoff.

    The returned hashes prove byte/provenance identity only. They do not prove
    numerical correctness, publication availability at acquisition, or backtest
    eligibility; the original Host research quality gates still apply.
    """
    try:
        parsed = NodeResult.model_validate(result).model_dump()
        row = service.store.session(sid)
        active = getattr(service, "specialist_ledger", None) or SpecialistLedger(service.store)
        state = active.read(sid)
        if state is None or parsed["as_of_date"] != state["as_of_date"]:
            raise SpecialistError("节点证据未绑定冻结截止日", "specialist_evidence_unbound", 409)
        cutoff = date.fromisoformat(state["as_of_date"])
        scope = row.get("source_scope", ["datahub", "web", "uploads"])
        files = {item["id"]: item for item in service.store.files(sid)}
        uploads = {
            item["id"]
            for item in upload_evidence_files(service.store, sid, list(files.values()))
            if item["kind"] == "inputs"
        }
        web = None
        budget, frozen = _ReadBudget(), {}
        for ref in parsed["artifact_ids"]:
            frozen[ref] = _file_snapshot(service, sid, ref, "outputs", files, budget)
        for ref in parsed["evidence_ids"]:
            if ref.startswith("file:") and "uploads" in scope and ref[5:] in uploads:
                frozen[ref] = _file_snapshot(service, sid, ref[5:], "inputs", files, budget)
            elif ref.startswith("dataset:") and "datahub" in scope:
                frozen[ref] = _dataset_snapshot(service, sid, ref[8:], cutoff, budget)
            elif ref.startswith("web:") and "web" in scope:
                if web is None:
                    web = {item["id"]: item for item in stored_sources(service.store, sid)}
                source = web.get(ref)
                if (
                    not source
                    or source.get("state") != "available"
                    or source.get("admission", {}).get("report_admitted") is False
                ):
                    raise SpecialistError(
                        "网页原件未完成核验", "specialist_evidence_unqualified", 409
                    )
                if source.get("date_status") == "conflict":
                    raise SpecialistError(
                        "来源披露日期冲突，不能确认截止前可得",
                        "specialist_evidence_date_unknown",
                        409,
                    )
                original_record = row.get("web_evidence", {}).get(ref)
                if not isinstance(original_record, dict):
                    raise SpecialistError(
                        "网页出处原始登记缺失", "specialist_evidence_unbound", 409
                    )
                _dates(original_record, cutoff)
                _dates(source, cutoff)
                body_hash = _file_snapshot(
                    service, sid, source["file_id"], "inputs", files, budget, source["sha256"]
                )
                frozen[ref] = _digest(
                    {"provenance": source, "original_record": original_record, "body": body_hash}
                )
            else:
                raise SpecialistError(
                    "引用不属于当前获授权的研究原件", "specialist_evidence_unbound", 409
                )
        if not frozen or not parsed["evidence_ids"]:
            raise SpecialistError("节点缺少真实来源引用", "specialist_evidence_unbound", 409)
        log.info("specialist_evidence_frozen", references=len(frozen))
        return frozen
    except SpecialistError:
        raise
    except (StoreError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        log.warning("specialist_evidence_unverified", error_type=type(exc).__name__)
        raise SpecialistError(
            "节点证据原件或出处无法核验", "specialist_evidence_unverified", 409
        ) from exc


def verify_snapshots(service: Any, sid: str, state: dict[str, Any]) -> list[str]:
    """Return completed attempt IDs whose immutable evidence cannot be re-proven."""
    if not isinstance(state, dict) or not isinstance(state.get("attempts"), dict):
        raise SpecialistError("协作尝试清单不可核验", "specialist_evidence_unverified", 409)
    changed = []
    for attempt_id, attempt in state["attempts"].items():
        if attempt.get("status") != "succeeded" or attempt.get("invalidated"):
            continue
        expected = attempt.get("evidence_snapshot")
        try:
            if (
                not isinstance(expected, dict)
                or not expected
                or any(
                    not isinstance(key, str) or not SHA256.fullmatch(str(value))
                    for key, value in expected.items()
                )
            ):
                raise SpecialistError(
                    "旧成果缺少冻结证据摘要", "specialist_evidence_unverified", 409
                )
            current = evidence_snapshot(service, sid, attempt["result"])
            if current != expected:
                raise SpecialistError("节点证据版本已变化", "specialist_evidence_changed", 409)
        except (SpecialistError, KeyError, TypeError) as exc:
            log.warning(
                "specialist_evidence_invalidated",
                attempt_id=attempt_id,
                error_type=type(exc).__name__,
            )
            changed.append(attempt_id)
    return changed
