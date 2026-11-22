"""Explicit one-shot import of fixed official sources; never arms a collector."""

import asyncio
import calendar
import hashlib
from datetime import datetime
from time import monotonic
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import admission

from ..store import StoreError
from . import sources
from .exchange_calendars import EXCHANGE_SOURCES
from .storage import fail, now

log = get_logger(__name__)
INITIAL_SOURCES = (*EXCHANGE_SOURCES, "fed_fomc", "bls_cpi", "bls_jobs")
SOURCE_BUDGET_SECONDS = 14
BATCH_BUDGET_SECONDS = 90
_KIND = "source_job"
_SCOPE = "initial-batch"
_INTENT = {"format": "rwb-official-initial-batch-v1"}


def date_window(today=None):
    today = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    next_year = today.year + 1
    end = today.replace(
        year=next_year, day=min(today.day, calendar.monthrange(next_year, today.month)[1])
    )
    return today.replace(month=1, day=1).isoformat(), end.isoformat()


def overlapping(events, window):
    return [
        event
        for event in events
        if str(event["occurrence_start"])[:10] <= window[1]
        and str(event.get("occurrence_end") or event["occurrence_start"])[:10] >= window[0]
    ]


def _schedules_enabled(service):
    with service.records.connection() as conn:
        if conn is None:
            return False
        row = conn.execute(
            "SELECT 1 FROM records r JOIN (SELECT id,MAX(revision) AS revision FROM records "
            "WHERE kind='source_schedule' GROUP BY id) latest ON r.id=latest.id "
            "AND r.revision=latest.revision WHERE r.kind='source_schedule' AND "
            "COALESCE(json_type(r.payload,'$.enabled'),'null')<>'false' LIMIT 1"
        ).fetchone()
    return row is not None


def _item(source):
    definition = sources.CATALOG[source]
    return {
        "source": source,
        "label": definition["label"],
        "url": definition["url"],
        "category": definition["category"],
        "market": definition.get("market"),
    }


def _failure(item, exc):
    log.warning("event_initial_source_failed", source=item["source"], error_type=type(exc).__name__)
    return {
        **item,
        "status": "failed",
        "records": None,
        "error": getattr(exc, "code", "event_source_failed"),
    }


async def preview(service):
    """Read the actual official documents without an archive, job or store write."""
    if service._closed:
        fail("event_host_closed", 503)
    if service._initial_batch_lock.locked():
        fail("event_initial_batch_busy", 409)
    window = date_window()
    slots = asyncio.Semaphore(2)

    async def inspect(source):
        item = _item(source)
        try:
            async with slots:
                url, raw = await asyncio.wait_for(
                    service.fetcher(source, None, 0), timeout=SOURCE_BUDGET_SECONDS
                )
                if url != sources.endpoint(source):
                    fail("event_source_identity_changed", 502)
                parsed = await asyncio.to_thread(sources.parse, source, raw)
            return {
                **item,
                "status": "preview",
                "records": len(overlapping(parsed["events"], window)),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        except TimeoutError:
            return {
                **item,
                "status": "failed",
                "records": None,
                "error": "event_initial_source_timeout",
            }
        except (StoreError, ValueError, OSError) as exc:
            return _failure(item, exc)

    async with service._initial_batch_lock:
        return {
            "start": window[0],
            "end": window[1],
            "status": "preview",
            "items": await asyncio.gather(*(inspect(source) for source in INITIAL_SOURCES)),
            "schedules_enabled": _schedules_enabled(service),
        }


def _public(service, job):
    payload = job["payload"]
    return {
        "batch_id": job["id"],
        "start": payload["start"],
        "end": payload["end"],
        "status": payload["state"],
        "items": payload["items"],
        "schedules_enabled": _schedules_enabled(service),
    }


def _checkpoint(service, job, items, state):
    payload = {**job["payload"], "items": items, "state": state}
    # Terminal checkpoints follow awaited child completion/cancellation and
    # writer drain. An unexpected crash leaves the running checkpoint unproved.
    if state in {"complete", "partial", "failed", "interrupted"}:
        payload["drain_receipt"] = {"format": "initial-import-drain-v1", "state": state}
    return service.records.update(
        _KIND,
        job["id"],
        payload,
        job["revision"],
        f"initial-batch-progress:{job['id']}:{len(items)}:{state}",
    )


def _save_gap(service, job, item, window):
    service.records.create(
        "coverage",
        {
            "source": item["source"],
            "url": item["url"],
            "start": window[0],
            "end": window[1],
            "state": (
                "source_not_attempted" if item["status"] == "not_attempted" else "source_failed"
            ),
            "event_count": None,
            "observed_at": now(),
            "code": item["error"],
            "historical_pit": False,
        },
        f"initial-coverage-gap:{job['id']}:{item['source']}",
    )
    return item


async def _ingest(service, job, source, window, remaining):
    item = _item(source)
    if remaining <= 0:
        return _save_gap(
            service,
            job,
            {
                **item,
                "status": "not_attempted",
                "records": None,
                "error": "event_initial_batch_budget_exhausted",
            },
            window,
        )
    try:
        # wait_for waits for child cancellation. refresh shields and drains any
        # accepted writer before it records an interrupted source job.
        imported = await asyncio.wait_for(
            asyncio.create_task(
                service.refresh(
                    {"source": source, "idempotency_key": f"initial-source:{job['id']}:{source}"},
                    date_window=window,
                )
            ),
            timeout=min(SOURCE_BUDGET_SECONDS, remaining),
        )
        payload = imported["payload"]
        if payload["state"] == "completed":
            return {
                **item,
                "status": "completed",
                "records": payload["checkpoint"]["imported"],
                "job_id": imported["id"],
                "raw_ref": payload["raw_ref"],
            }
        item = {
            **item,
            "status": "failed",
            "records": None,
            "job_id": imported["id"],
            "error": payload.get("code", "event_initial_source_not_completed"),
        }
    except TimeoutError:
        log.warning("event_initial_source_timeout", source=source)
        item = {
            **item,
            "status": "failed",
            "records": None,
            "error": "event_initial_source_timeout",
        }
    except (StoreError, ValueError, OSError) as exc:
        item = _failure(item, exc)
    return _save_gap(service, job, item, window)


async def execute(service, idempotency_key):
    """Replay completed or unknown requests by key; a fresh intent can re-fetch."""
    if service._closed:
        fail("event_host_closed", 503)
    key = "initial-batch:" + idempotency_key
    previous = service.records.cached(_SCOPE, key, _INTENT)
    if previous:
        return _public(service, service.records.get(_KIND, previous[0]["id"]))
    if service._initial_batch_lock.locked():
        fail("event_initial_batch_busy", 409)
    async with service._initial_batch_lock:
        with admission():
            if _schedules_enabled(service):
                fail("event_initial_batch_requires_disabled_schedules", 409)
            window = date_window()
            claim = uuid4().hex
            job = service.records.batch(
                [
                    {
                        "kind": _KIND,
                        "payload": {
                            "source": "initial_batch",
                            "state": "running",
                            "claim": claim,
                            "start": window[0],
                            "end": window[1],
                            "items": [],
                            "started_at": now(),
                        },
                    }
                ],
                key,
                intent=_INTENT,
                scope=_SCOPE,
            )[0]
            if job["payload"].get("claim") != claim:
                return _public(service, service.records.get(_KIND, job["id"]))
            task = asyncio.current_task()
            service._active.add(task)
            items = []
            deadline = monotonic() + BATCH_BUDGET_SECONDS
            try:
                for source in INITIAL_SOURCES:
                    if service._closed:
                        fail("event_host_closed", 503)
                    items.append(
                        await _ingest(service, job, source, window, deadline - monotonic())
                    )
                    job = _checkpoint(service, job, items, "running")
                completed = sum(item["status"] == "completed" for item in items)
                state = (
                    "complete" if completed == len(items) else "partial" if completed else "failed"
                )
                job = _checkpoint(service, job, items, state)
                return _public(service, job)
            except (asyncio.CancelledError, StoreError, OSError, ValueError):
                try:
                    _checkpoint(service, job, items, "interrupted")
                except (StoreError, OSError, ValueError) as exc:
                    log.warning(
                        "event_initial_batch_checkpoint_failed", error_type=type(exc).__name__
                    )
                raise
            finally:
                service._active.discard(task)
