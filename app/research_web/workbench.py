"""Research desk queries, immutable page handoffs and actual artifact indexes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from .datahub.contracts import BusinessQuery
from .store import StoreError

log = get_logger(__name__)
router = APIRouter(prefix="/api/research")

Section = Literal["market", "assets", "funds", "industry", "documents", "reports"]
MAX_CONTEXT_BYTES = 64 * 1024


class DeskQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
    section: Section
    query: BusinessQuery


class Handoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_session_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
    target_mode: Literal["fingpt", "claw"]
    section: Section
    dataset_ids: list[str] = Field(default_factory=list, max_length=20)
    context: dict[str, Any] = Field(default_factory=dict)
    scenario_id: str | None = Field(default=None, max_length=80)
    scenario_inputs: dict[str, Any] = Field(default_factory=dict)
    observation_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
    comparison_observation_ids: list[str] = Field(default_factory=list, max_length=4)
    workspace_material: dict[str, Any] | None = None
    source_scope: list[Literal["datahub", "web", "uploads"]] | None = Field(
        default=None, min_length=1, max_length=3
    )


@router.get("/scenarios")
async def scenarios(request: Request):
    from .scenario_handoffs import catalog

    return catalog(request.app.state.research)


@router.post("/scenarios/{scenario_id}/prepare")
async def prepare_scenario(scenario_id: str, body: Handoff, request: Request):
    from .scenario_handoffs import prepare_context

    if body.scenario_id != scenario_id:
        raise StoreError("场景身份不一致", "scenario_inputs_invalid", 422)
    service = request.app.state.research
    await service.ensure_owned()
    async with service.lock:
        return prepare_context(service, body)


@router.get("/handoff-requests/{request_key}")
async def handoff_request(request_key: str, request: Request):
    """Read original receipt only; unknown native creation is never retried."""
    service = request.app.state.research
    store = service.store
    identifier = store.data["handoff_keys"].get(_key(request_key))
    if not identifier:
        raise StoreError("交接请求尚无回执", "handoff_not_found", 404)
    return _public_handoff(service, store.data["handoffs"][identifier])


def _public_handoff(service, record):
    # Unknown creation is a status-only receipt, never a second read path for
    # frozen source text. The original intent remains untouched for recovery.
    safe = {key: record[key] for key in ("id", "state", "mode", "session_id") if key in record}
    if record.get("state") != "prepared":
        return safe
    from .scenario_handoffs import trusted_context

    try:
        trusted_context(service, record["session_id"], check_capabilities=False)
    except StoreError as exc:
        log.warning("research_handoff_projection_denied", code=exc.code)
        return {
            **safe,
            "state": "context_unavailable",
            "creation_state": record["state"],
            "code": exc.code,
        }
    result = {
        key: value for key, value in record.items() if key not in {"request_sha256", "copied"}
    }
    context = record.get("scenario_context", {})
    if context and context.get("pack_seal"):
        from .scenario_handoffs import fingerprint

        seal = context["pack_seal"]
        result["pack_execution"] = {
            "capability_id": seal["capability_id"],
            "version": seal["version"],
            "context_sha256": fingerprint(context),
            "input_manifest_sha256": seal["manifest_sha256"],
        }
    return result


def _copy_evidence(service, target, references):
    from .datahub.security import directory, sync_directory, write_new
    from .scenario_handoffs import resolve_reference

    datasets, files = [], []
    for reference in references:
        metadata, _manifest, raw = resolve_reference(
            service,
            reference["source_session_id"],
            reference["reference"],
            expected=reference,
            target_sid=target,
        )
        if reference["reference"]["type"] == "dataset":
            datasets.extend(
                service.datahub.copy_selected(
                    reference["source_session_id"], target, [reference["reference"]["id"]]
                )
            )
        else:
            extension = (
                ".json"
                if reference["reference"]["type"] == "file"
                and reference["reference"]["id"].endswith(".json")
                else ".txt"
            )
            name = uuid4().hex + extension
            with directory(
                service.store.root, ("sessions", target, "inputs", "page-evidence"), create=True
            ) as fd:
                write_new(fd, name, raw)
                sync_directory(fd)
            files.append(
                {
                    "path": "inputs/page-evidence/" + name,
                    "sha256": metadata["sha256"],
                    "source_session_id": reference["source_session_id"],
                    "reference": reference["reference"],
                }
            )
    return datasets, files


def _key(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", value):
        raise StoreError("Idempotency-Key 格式非法")
    return hashlib.sha256(value.encode()).hexdigest()


def _public_query(record: dict) -> dict:
    allowed = {
        "id",
        "status",
        "section",
        "session_id",
        "capability",
        "source",
        "created_at",
        "completed_at",
        "duration_ms",
        "failure_code",
        "dataset",
    }
    return {name: value for name, value in record.items() if name in allowed}


def _validate_context(value: dict[str, Any]) -> None:
    try:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    except (TypeError, ValueError) as exc:
        raise StoreError("页面上下文必须是可序列化的 JSON") from exc
    if len(raw) > MAX_CONTEXT_BYTES:
        raise StoreError("页面上下文超过 64 KiB，请缩小筛选条件或摘要")


async def _run_query(service, query_id: str, body: DeskQuery) -> None:
    record = service.store.data["data_queries"][query_id]
    started = time.monotonic()
    try:
        result = await service.datahub.query(record["session_id"], query_id, body.query)
        dataset = {
            key: result.get(key)
            for key in (
                "dataset_id",
                "name",
                "capability",
                "source",
                "provider",
                "status",
                "row_count",
                "as_of",
                "retrieved_at",
                "actual_range",
                "missing",
                "limitations",
                "files",
            )
        }
        record.update(
            status="completed",
            dataset=dataset,
            completed_at=time.time(),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        service.store.audit(
            "datahub",
            result.get("status", "unknown"),
            session_id=record["session_id"],
            source=result.get("provider") or result.get("source"),
            capability=body.query.capability,
            duration_ms=record["duration_ms"],
            rows=result.get("row_count", 0),
        )
        log.info("research_desk_query_completed", capability=body.query.capability)
    except asyncio.CancelledError:
        record.update(status="cancelled", completed_at=time.time(), failure_code="cancelled")
        service.store.save()
        raise
    except (StoreError, ValueError, TypeError, KeyError) as exc:
        record.update(
            status="failed",
            completed_at=time.time(),
            duration_ms=round((time.monotonic() - started) * 1000),
            failure_code="query_failed",
        )
        service.store.audit(
            "datahub",
            "failed",
            session_id=record["session_id"],
            capability=body.query.capability,
            duration_ms=record["duration_ms"],
            failure_code=record["failure_code"],
        )
        log.warning("research_desk_query_failed", error_type=type(exc).__name__)
    finally:
        service.store.save()
        service.notify()


@router.post("/data/queries", status_code=202)
async def start_query(
    body: DeskQuery,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    service = request.app.state.research
    digest = _key(idempotency_key)
    async with service.workbench_lock:
        existing = service.store.data["data_query_keys"].get(digest)
        if existing:
            return _public_query(service.store.data["data_queries"][existing])
        session_id = body.session_id
        if session_id is None:
            created = await service.create("fingpt", f"研究台 · {body.section}")
            session_id = created["id"]
        else:
            service.store.session(session_id)
        query_id = str(uuid4())
        record = {
            "id": query_id,
            "status": "running",
            "section": body.section,
            "session_id": session_id,
            "capability": body.query.capability,
            "source": body.query.source,
            "created_at": time.time(),
            "completed_at": None,
            "duration_ms": None,
            "failure_code": None,
            "dataset": None,
        }
        service.store.data["data_queries"][query_id] = record
        service.store.data["data_query_keys"][digest] = query_id
        service.store.save()
        task = asyncio.create_task(
            _run_query(service, query_id, body), name=f"desk-query-{query_id}"
        )
        service.datahub.tasks[(session_id, f"desk:{query_id}")] = task
        task.add_done_callback(
            lambda _: service.datahub.tasks.pop((session_id, f"desk:{query_id}"), None)
        )
    return _public_query(record)


@router.get("/data/queries")
async def list_queries(
    request: Request,
    section: Section | None = None,
    session_id: str | None = Query(default=None, pattern=r"^[a-f0-9-]{36}$"),
):
    if session_id is not None:
        request.app.state.research.store.session(session_id)
    rows = [
        _public_query(record)
        for record in request.app.state.research.store.data["data_queries"].values()
        if (section is None or record.get("section") == section)
        and (session_id is None or record.get("session_id") == session_id)
    ]
    rows.sort(key=lambda item: float(item.get("created_at", 0)), reverse=True)
    return {"items": rows}


@router.get("/data/queries/{query_id}")
async def query_status(query_id: str, request: Request):
    try:
        record = request.app.state.research.store.data["data_queries"][query_id]
    except KeyError as exc:
        raise StoreError("研究台查询不存在") from exc
    return _public_query(record)


def _write_context(
    service, sid: str, body: Handoff, copied: list[dict], lineage: list[dict]
) -> dict:
    context_id = str(uuid4())
    relative = Path("inputs") / "page-context" / f"{context_id}.json"
    path = service.store.directory(sid) / relative
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise StoreError("页面上下文目录非法")
    payload = {
        "schema_version": "1.0.0",
        "section": body.section,
        "context": body.context,
        "lineage": lineage,
        "datasets": [
            {
                key: item.get(key)
                for key in (
                    "dataset_id",
                    "origin_dataset_id",
                    "manifest_sha256",
                    "origin_manifest_sha256",
                    "retrieved_at",
                    "as_of",
                    "source",
                    "provider",
                    "status",
                    "missing",
                    "limitations",
                    "files",
                )
            }
            for item in copied
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    files = service.store.files(sid)
    item = next(file for file in files if file["name"] == path.name)
    return {**item, "path": relative.as_posix(), "sha256": hashlib.sha256(raw).hexdigest()}


@router.post("/handoffs", status_code=201)
async def create_handoff(
    body: Handoff,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    service = request.app.state.research
    digest = _key(idempotency_key)
    from .scenario_handoffs import fingerprint, freeze_lineage, prepare_context

    request_payload = body.model_dump(mode="json")
    for new_field in ("comparison_observation_ids", "workspace_material", "source_scope"):
        if request_payload[new_field] is None or request_payload[new_field] == []:
            request_payload.pop(new_field)
    request_hash = fingerprint(request_payload)
    async with service.workbench_lock:
        existing = service.store.data["handoff_keys"].get(digest)
        if existing:
            record = service.store.data["handoffs"][existing]
            if record.get("request_sha256") != request_hash:
                raise StoreError("同一交接请求已绑定其他内容", "handoff_request_conflict", 409)
            return _public_handoff(service, record)
        from .dossiers.lock import retention_lock

        try:
            _validate_context(body.context)
            if body.source_session_id:
                service.store.session(body.source_session_id)
                from .scenario_handoffs import trusted_context

                trusted_context(service, body.source_session_id, check_capabilities=False)
            elif not body.scenario_id or body.dataset_ids or body.observation_id:
                raise StoreError("来源会话缺失", "scenario_source_missing", 422)
            with retention_lock(service.store.root):
                available = (
                    set(service.datahub.snapshots.ids(body.source_session_id))
                    if body.source_session_id
                    else set()
                )
                requested = set(body.dataset_ids)
                if not body.scenario_id and not requested.issubset(available):
                    raise StoreError("交接数据集不存在或不属于来源会话")
                scenario = prepare_context(service, body) if body.scenario_id else None
                if not body.scenario_id and (
                    body.scenario_inputs
                    or body.observation_id
                    or body.comparison_observation_ids
                    or body.workspace_material
                    or body.source_scope
                ):
                    raise StoreError("场景身份缺失", "scenario_inputs_invalid", 422)
                lineage = (
                    scenario["references"]
                    if scenario
                    else (
                        freeze_lineage(service, body.source_session_id, body.dataset_ids)
                        if body.source_session_id
                        else []
                    )
                )
                handoff_id = str(uuid4())
                # Persist BEFORE native create. service.create owns its identity; if
                # its outcome is lost, this receipt must never create another one.
                intent = {
                    "id": handoff_id,
                    "state": "creation_outcome_unknown",
                    "request_sha256": request_hash,
                    "mode": body.target_mode,
                    "scenario_context": scenario,
                    "lineage": lineage,
                }
                service.store.data["handoffs"][handoff_id] = intent
                service.store.data["handoff_keys"][digest] = handoff_id
                service.store.save()
        except StoreError as exc:
            # This proof is issued only under the creation lock, before any
            # persisted intent. Existing/unknown outcomes must retain their key.
            if digest in service.store.data["handoff_keys"] or not 400 <= exc.status < 500:
                raise
            log.warning("research_handoff_not_created", code=exc.code)
            return JSONResponse(
                {
                    "error": {
                        "code": exc.code,
                        "message": str(exc),
                        "handoff_outcome": "not_created",
                    }
                },
                status_code=exc.status,
            )
        created = await service.create(
            body.target_mode,
            f"研究台交接 · {body.section}",
            source_scope=(
                scenario["source_scope"]
                if scenario
                else service.store.session(body.source_session_id).get(
                    "source_scope", ["datahub", "web", "uploads"]
                )
            ),
            metadata={"scenario_handoff_id" if scenario else "evidence_handoff_id": handoff_id},
        )
        target = created["id"]
        if scenario and scenario["scenario"]["contract"].get("pack_id"):
            # Once Native creation returned, later IO failure is a known-created
            # observation. Preserve its identity without reopening the request.
            service.store.data["handoffs"][handoff_id]["session_id"] = target
            service.store.save()
        copied, copied_files = _copy_evidence(service, target, lineage)
        if scenario:
            scenario["frozen_files"] = copied_files
            if scenario["scenario"]["contract"].get("pack_id"):
                from .scenario_pack_inputs import seal_pack_inputs

                scenario["pack_seal"] = seal_pack_inputs(service, target, handoff_id, scenario)
        context_body = body.model_copy(update={"context": scenario}) if scenario else body
        context_file = _write_context(service, target, context_body, copied, lineage)
        result = {
            "id": handoff_id,
            "session_id": target,
            "mode": body.target_mode,
            "section": body.section,
            "dataset_count": len(copied),
            "context_file": {
                key: context_file[key] for key in ("id", "name", "path", "sha256", "url")
            },
            "draft": (
                "请基于研究台冻结的页面上下文和数据集继续研究。先读取并核对 "
                + context_file["path"]
                + "；数据缺失、口径和截止时间必须在结论中明确说明。"
            ),
        }
        result.update(
            request_sha256=request_hash,
            state="prepared",
            lineage=lineage,
            copied=copied,
            copied_files=copied_files,
        )
        if scenario:
            result.update(state="prepared", scenario_context=scenario, copied=copied)
            result["draft"] = scenario["scenario"]["inputs"]["question"] + "\n\n" + result["draft"]
        service.store.data["handoffs"][handoff_id] = result
        service.store.data["handoff_keys"][digest] = handoff_id
        service.store.save()
    log.info("research_desk_handoff_created", mode=body.target_mode, datasets=len(copied))
    return _public_handoff(service, result)


@router.get("/artifacts")
async def artifacts(
    request: Request,
    session_id: str | None = Query(default=None, pattern=r"^[a-f0-9-]{36}$"),
):
    service = request.app.state.research
    rows = []
    sessions = (
        [service.store.session(session_id)]
        if session_id
        else [
            session
            for session in service.store.data["sessions"].values()
            if session.get("deleted_at") is None
        ]
    )
    for session in sessions:
        for item in service.store.files(session["id"]):
            if item["kind"] != "outputs":
                continue
            path = service.store.file_path(session["id"], item["id"])
            rows.append(
                {
                    **item,
                    "session_id": session["id"],
                    "session_title": session["title"],
                    "mode": session["mode"],
                    "updated_at": path.stat().st_mtime,
                }
            )
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return {"items": rows}
