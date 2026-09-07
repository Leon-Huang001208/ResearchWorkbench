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

    source_session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    target_mode: Literal["fingpt", "claw"]
    section: Section
    dataset_ids: list[str] = Field(default_factory=list, max_length=20)
    context: dict[str, Any] = Field(default_factory=dict)


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


def _write_context(service, sid: str, body: Handoff, copied: list[dict]) -> dict:
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
    _validate_context(body.context)
    service.store.session(body.source_session_id)
    digest = _key(idempotency_key)
    async with service.workbench_lock:
        existing = service.store.data["handoff_keys"].get(digest)
        if existing:
            return service.store.data["handoffs"][existing]
        available = set(service.datahub.snapshots.ids(body.source_session_id))
        requested = set(body.dataset_ids)
        if not requested.issubset(available):
            raise StoreError("交接数据集不存在或不属于来源会话")
        created = await service.create(body.target_mode, f"研究台交接 · {body.section}")
        target = created["id"]
        copied = service.datahub.copy_selected(body.source_session_id, target, body.dataset_ids)
        context_file = _write_context(service, target, body, copied)
        handoff_id = str(uuid4())
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
        service.store.data["handoffs"][handoff_id] = result
        service.store.data["handoff_keys"][digest] = handoff_id
        service.store.save()
    log.info("research_desk_handoff_created", mode=body.target_mode, datasets=len(copied))
    return result


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
        else list(service.store.data["sessions"].values())
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
