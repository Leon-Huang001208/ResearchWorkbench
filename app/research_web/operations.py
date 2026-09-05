"""Read-only, content-free operations projections over existing Research Web evidence."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query, Request

from core.observability import get_logger

from .client import RuntimeFailure
from .projection import project
from .store import StoreError

log = get_logger(__name__)
router = APIRouter(prefix="/api/research/operations")


def _window(value: str, start: date | None, end: date | None) -> tuple[float, float, dict]:
    today = datetime.now(UTC).date()
    if value == "custom":
        if start is None or end is None or start > end or (end - start).days > 366:
            raise ValueError("自定义日期范围非法")
        left, right = start, end
    else:
        days = {"today": 1, "7d": 7, "30d": 30}.get(value)
        if days is None:
            raise ValueError("时间范围非法")
        left, right = today - timedelta(days=days - 1), today
    return (
        datetime.combine(left, datetime.min.time(), tzinfo=UTC).timestamp(),
        datetime.combine(right + timedelta(days=1), datetime.min.time(), tzinfo=UTC).timestamp(),
        {"range": value, "start": left.isoformat(), "end": right.isoformat()},
    )


def _timestamp(value) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    # Native DSH events may use milliseconds; product index uses seconds.
    return value / 1000 if value > 10_000_000_000 else float(value)


async def _projections(service, start_at: float, end_at: float):
    semaphore = asyncio.Semaphore(4)

    async def load(row):
        if not start_at <= float(row.get("updated_at", 0)) < end_at:
            return None
        async with semaphore:
            try:
                detail = await service.detail(row["id"])
                entries = list(service.events.get(row["id"], {}).values())
                relevant = []
                for entry in entries:
                    event_time = _timestamp(entry.get("event", {}).get("time"))
                    if event_time is None or start_at <= event_time < end_at:
                        relevant.append(entry)
                return row, project(relevant), detail
            except (RuntimeFailure, StoreError, OSError, ValueError, KeyError, TypeError) as exc:
                log.warning(
                    "operations_session_projection_unavailable", error_type=type(exc).__name__
                )
                return None

    projected = await asyncio.gather(
        *(load(row) for row in service.store.data["sessions"].values())
    )
    return [item for item in projected if item is not None]


def _audit(service, start_at: float, end_at: float):
    return [
        item
        for item in service.store.data.get("operation_audit", [])
        if start_at <= float(item.get("at", 0)) < end_at
    ]


async def usage_projection(service, start_at, end_at, window, rows=None):
    rows = rows if rows is not None else await _projections(service, start_at, end_at)
    totals = {"input": 0, "output": 0, "total": 0, "known_sessions": 0, "unknown_sessions": 0}
    models = Counter()
    statuses = Counter()
    turns = 0
    durations = []
    for row, view, _detail in rows:
        usage = view.get("usage") or {}
        if usage:
            totals["input"] += int(usage.get("input_tokens", 0))
            totals["output"] += int(usage.get("output_tokens", 0))
            totals["total"] += int(usage.get("tokens", 0))
            totals["known_sessions"] += 1
        else:
            totals["unknown_sessions"] += 1
        models[row.get("model") or "未知模型"] += 1
        statuses[view.get("status") or row.get("status") or "unknown"] += 1
        turns += sum(1 for message in view.get("messages", []) if message.get("role") == "user")
        if view.get("duration_ms") is not None:
            durations.append(view["duration_ms"])
    return {
        "window": window,
        "sessions": len(rows),
        "turns": turns,
        "average_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "tokens": {**totals, "known": totals["known_sessions"] > 0},
        "models": [{"model": name, "sessions": count} for name, count in models.most_common()],
        "outcomes": dict(statuses),
        "cost": {"status": "not_configured", "amount": None, "currency": None},
    }


async def tools_projection(service, start_at, end_at, window, rows=None):
    rows = rows if rows is not None else await _projections(service, start_at, end_at)
    calls = Counter()
    failures = Counter()
    durations = defaultdict(list)
    subagents = Counter()
    subagent_durations = []
    claw_tasks = 0
    running = []
    for row, view, detail in rows:
        if row.get("mode") == "claw":
            claw_tasks += 1
        if view.get("status") == "running":
            running.append({"session_id": row["id"], "title": row["title"], "mode": row["mode"]})
        for item in view.get("activities", []):
            name = item.get("title") or "未知工具"
            calls[name] += 1
            if item.get("status") == "failed":
                failures[name] += 1
            if item.get("duration_ms") is not None:
                durations[name].append(item["duration_ms"])
        # detail() enriches subagents, while project intentionally does not duplicate them.
        for agent in detail.get("subagents", []):
            subagents[agent.get("status", "unknown")] += 1
            if isinstance(agent.get("duration_ms"), (int, float)):
                subagent_durations.append(agent["duration_ms"])
    approvals = Counter(
        item.get("outcome", "unknown")
        for item in _audit(service, start_at, end_at)
        if item.get("kind") == "approval"
    )
    return {
        "window": window,
        "calls": sum(calls.values()),
        "tools": [
            {
                "name": name,
                "calls": count,
                "failures": failures[name],
                "average_duration_ms": (
                    round(sum(durations[name]) / len(durations[name])) if durations[name] else None
                ),
            }
            for name, count in calls.most_common()
        ],
        "approvals": {
            "approved": approvals["approved"],
            "denied": approvals["denied"],
            "cancelled": approvals["cancelled"],
            "historical_completeness": "从本版本起记录；此前决策为未知",
        },
        "claw_tasks": claw_tasks,
        "subagents": {
            "total": sum(subagents.values()),
            "outcomes": dict(subagents),
            "success_rate": (
                round(subagents["completed"] / sum(subagents.values()) * 100, 1)
                if subagents
                else None
            ),
            "failure_rate": (
                round(subagents["failed"] / sum(subagents.values()) * 100, 1) if subagents else None
            ),
            "average_duration_ms": (
                round(sum(subagent_durations) / len(subagent_durations))
                if subagent_durations
                else None
            ),
        },
        "running": running,
    }


def datahub_projection(service, start_at, end_at, window):
    manifests = []
    for row in service.store.data["sessions"].values():
        try:
            manifests.extend(service.datahub.list(row["id"]))
        except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("operations_dataset_manifest_unavailable", error_type=type(exc).__name__)
    manifests = [
        item
        for item in manifests
        if start_at <= (datetime.fromisoformat(item["retrieved_at"]).timestamp()) < end_at
    ]
    outcomes = Counter(item.get("status", "unknown") for item in manifests)
    sources = Counter(item.get("provider") or item.get("source") or "unknown" for item in manifests)
    bytes_total = sum(
        int(file.get("size", 0))
        for item in manifests
        for file in item.get("files", [])
        if file.get("name") != "manifest.json"
    )
    audit = [item for item in _audit(service, start_at, end_at) if item.get("kind") == "datahub"]
    durations = [item["duration_ms"] for item in audit if isinstance(item.get("duration_ms"), int)]
    capabilities = Counter(item.get("capability", "unknown") for item in audit)
    recent_errors = [
        {
            "at": item["at"],
            "capability": item.get("capability", "unknown"),
            "source": item.get("source"),
            "failure_code": item.get("failure_code", "unknown"),
        }
        for item in reversed(audit)
        if item.get("outcome") == "failed"
    ][:5]
    catalog = service.datahub.catalog()
    return {
        "window": window,
        "calls": len(audit) if audit else len(manifests),
        "outcomes": dict(outcomes),
        "average_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "sources": [
            {"source": source, "snapshots": count} for source, count in sources.most_common()
        ],
        "capabilities": [
            {"capability": capability, "calls": count}
            for capability, count in capabilities.most_common()
        ],
        "recent_errors": recent_errors,
        "snapshots": {
            "count": len(manifests),
            "bytes": bytes_total,
            "rows": sum(item.get("row_count", 0) for item in manifests),
        },
        "readiness": catalog["summary"],
    }


def _managed_state(root: Path, role: str, port: int) -> dict:
    path = root.parent / "run" / f"{role}.json"
    state = None
    try:
        if path.is_file() and not path.is_symlink():
            candidate = json.loads(path.read_text())
            command = candidate.get("command")
            signature = candidate.get("signature")
            pid = candidate.get("pid")
            fingerprint = hashlib.sha256(
                json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest()
            valid = (
                candidate.get("version") == 1
                and candidate.get("role") == role
                and candidate.get("port") == port
                and candidate.get("data_root") == str(root.resolve())
                and candidate.get("project_root") == str(Path(__file__).parents[2].resolve())
                and isinstance(command, list)
                and all(isinstance(item, str) for item in command)
                and candidate.get("fingerprint") == fingerprint
                and isinstance(signature, list)
                and signature
                and all(isinstance(item, str) for item in signature)
                and isinstance(pid, int)
                and pid > 1
            )
            if valid:
                os.kill(pid, 0)
                result = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "command="],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0 and all(item in result.stdout for item in signature):
                    state = candidate
    except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        state = None
        log.warning("operations_managed_state_unavailable", role=role)
    started = state.get("started_at") if state else None
    return {
        "id": role,
        "port": port,
        "process_running": state is not None,
        "pid": state.get("pid") if state else None,
        "started_at": started,
        "uptime_seconds": (
            max(0, round(time.time() - started)) if isinstance(started, (int, float)) else None
        ),
    }


async def services_projection(service):
    runtime = await service.runtime()
    web = _managed_state(service.store.root, "web", 8088)
    dsh = _managed_state(service.store.root, "runtime", 3081)
    # Serving this response is the Web health proof even when started outside rwb CLI.
    web.update(process_running=True, health_passed=True)
    dsh.update(health_passed=runtime.get("health_check_passed") is True)
    active = [
        {"session_id": row["id"], "title": row["title"], "mode": row["mode"]}
        for row in service.store.data["sessions"].values()
        if service.running.get(row["id"]) is True
    ]
    return {
        "services": [web, dsh],
        "runtime": {
            "model": runtime.get("model"),
            "connected": runtime.get("connected", False),
            "health_check_passed": runtime.get("health_check_passed", False),
            "version": runtime.get("version"),
            "last_successful_communication_at": runtime.get("last_successful_communication_at"),
        },
        "sse_connections": len(service.listeners),
        "running_research": active,
    }


def _measure(path: Path, *, include=None, exclude=None):
    count = size = recent = 0
    if not path.exists() or path.is_symlink():
        return {"files": 0, "bytes": 0, "last_24h_bytes": 0}
    cutoff = time.time() - 86400
    try:
        candidates = path.rglob("*") if path.is_dir() else [path]
        for item in candidates:
            if item.is_symlink() or not item.is_file():
                continue
            relative = item.relative_to(path) if path.is_dir() else Path(item.name)
            if include and not include(relative):
                continue
            if exclude and exclude(relative):
                continue
            stat = item.stat()
            count += 1
            size += stat.st_size
            if stat.st_mtime >= cutoff:
                recent += stat.st_size
    except OSError as exc:
        log.warning("operations_storage_scan_partial", error_type=type(exc).__name__)
    return {"files": count, "bytes": size, "last_24h_bytes": recent}


def storage_projection(service):
    root = service.store.root
    sessions = root / "sessions"
    categories = [
        (
            "attachments",
            "附件",
            sessions,
            lambda p: "inputs" in p.parts and "datasets" not in p.parts,
        ),
        ("datasets", "数据集", sessions, lambda p: "datasets" in p.parts),
        ("artifacts", "报告与产物", sessions, lambda p: "outputs" in p.parts),
        ("logs", "日志", root.parent / "logs", None),
        ("dsh_source", "DSH 源码", root.parent / "dsh-source", None),
    ]
    return {
        "scope": str(root),
        "categories": [
            {"id": cid, "name": name, **_measure(path, include=predicate)}
            for cid, name, path, predicate in categories
        ],
        "read_only": True,
    }


def _params(range_value, start, end):
    try:
        return _window(range_value, start, end)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc


@router.get("/usage")
async def usage(
    request: Request,
    range_value: Literal["today", "7d", "30d", "custom"] = Query("7d", alias="range"),
    start: date | None = None,
    end: date | None = None,
):
    left, right, window = _params(range_value, start, end)
    return await usage_projection(request.app.state.research, left, right, window)


@router.get("/tools")
async def tools(
    request: Request,
    range_value: Literal["today", "7d", "30d", "custom"] = Query("7d", alias="range"),
    start: date | None = None,
    end: date | None = None,
):
    left, right, window = _params(range_value, start, end)
    return await tools_projection(request.app.state.research, left, right, window)


@router.get("/datahub")
async def datahub(
    request: Request,
    range_value: Literal["today", "7d", "30d", "custom"] = Query("7d", alias="range"),
    start: date | None = None,
    end: date | None = None,
):
    left, right, window = _params(range_value, start, end)
    return datahub_projection(request.app.state.research, left, right, window)


@router.get("/services")
async def services(request: Request):
    return await services_projection(request.app.state.research)


@router.get("/storage")
async def storage(request: Request):
    return storage_projection(request.app.state.research)


@router.get("/summary")
async def summary(
    request: Request,
    range_value: Literal["today", "7d", "30d", "custom"] = Query("7d", alias="range"),
    start: date | None = None,
    end: date | None = None,
):
    left, right, window = _params(range_value, start, end)
    service = request.app.state.research
    rows = await _projections(service, left, right)
    return {
        "window": window,
        "usage": await usage_projection(service, left, right, window, rows),
        "tools": await tools_projection(service, left, right, window, rows),
        "datahub": datahub_projection(service, left, right, window),
        "services": await services_projection(service),
        "storage": storage_projection(service),
    }
