"""Source collection on the existing Automation heartbeat; no timer or model loop."""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

from core.observability import get_logger

from ..store import StoreError
from .sources import CATALOG
from .storage import canonical, fail

log = get_logger(__name__)


class CollectionScheduler:
    def __init__(self, research):
        self.research = research
        self._lock = asyncio.Lock()
        self._tasks = set()
        self._closed = False

    @property
    def events(self):
        return self.research.event_timeline

    @property
    def active(self):
        """Queued collectors remain producers before their first network await."""
        return bool(self._tasks) or self._lock.locked()

    def has_enabled(self):
        return any(
            row["payload"].get("enabled") is True
            for row in self.events.records.list("source_schedule", limit=100)["items"]
        )

    def bind(self, source, body):
        """Pure validation: the caller persists registration atomically with schedule CAS."""
        if (
            source not in CATALOG
            or not isinstance(body.get("interval_hours"), int)
            or not 1 <= body["interval_hours"] <= 720
        ):
            fail("event_schedule_invalid", 422)
        return hashlib.sha256(
            canonical(
                {
                    "owner": self.events.records.owner_binding,
                    "source": source,
                    "format": "event-collection-v1",
                }
            ).encode()
        ).hexdigest()

    @staticmethod
    def definition(payload):
        return hashlib.sha256(
            canonical(
                {
                    key: payload[key]
                    for key in (
                        "source",
                        "interval_hours",
                        "owner_binding",
                        "scheduler_registration_id",
                    )
                }
            ).encode()
        ).hexdigest()

    def _request(self, row, clock):
        payload = row["payload"]
        source = payload["source"]
        result = {"source": source, "year": None, "page": 0, "offset": 0}
        if source == "gdelt":
            date = clock.date() - timedelta(days=1)
            result["year"] = date.year
            result["page"] = (date - date.replace(month=1, day=1)).days
        elif source == "ucdp":
            checkpoint = payload.get("checkpoint") or {}
            result["year"] = min(
                checkpoint.get("next_year") or clock.year, CATALOG["ucdp"]["historical_end_year"]
            )
            result["page"] = checkpoint.get("next_page") or 0
            result["offset"] = checkpoint.get("next_offset") or 0
        result["idempotency_key"] = (
            "source-scheduled:"
            + hashlib.sha256(
                canonical(
                    {"schedule": row["id"], "revision": row["revision"], "due": payload["next_due"]}
                ).encode()
            ).hexdigest()
        )
        return result

    def _guard(self, identifier, claim):
        current = self.events.records.get("source_schedule", identifier)["payload"]
        if (
            self._closed
            or self.events._closed
            or not current.get("enabled")
            or current.get("collection_claim", {}).get("id") != claim["id"]
            or current.get("definition_sha256") != claim["definition_sha256"]
            or self.definition(current) != claim["definition_sha256"]
        ):
            fail("event_collection_definition_changed")

    async def _run(self, identifier, claim):
        try:
            guard = lambda: self._guard(identifier, claim)
            guard()
            job = await self.events.refresh(claim["request"], guard=guard)
            current = self.events.records.get("source_schedule", identifier)
            if current["payload"].get("collection_claim", {}).get("id") != claim["id"]:
                return
            state = job["payload"]["state"]
            updated = {
                **current["payload"],
                "collection_claim": {**claim, "state": state, "source_job_id": job["id"]},
                "checkpoint": job["payload"].get("checkpoint", {}),
            }
            self.events.records.update(
                "source_schedule",
                identifier,
                updated,
                current["revision"],
                "collection-outcome:" + claim["id"],
            )
        except asyncio.CancelledError:
            log.warning("event_collection_interrupted")
            raise
        except (StoreError, ValueError, TypeError) as exc:
            log.warning(
                "event_collection_outcome_unresolved",
                code=getattr(exc, "code", "event_collection_failed"),
            )

    async def tick(self, clock=None):
        if self._closed or self.events._closed or self._lock.locked():
            return
        clock = clock or datetime.now(UTC)
        if clock.tzinfo is None:
            fail("event_collection_clock_invalid", 422)
        clock = clock.astimezone(UTC)
        async with self._lock:
            for row in self.events.records.list("source_schedule", limit=200)["items"]:
                if len(self._tasks) >= 2:
                    return
                payload = row["payload"]
                if not payload.get("enabled"):
                    continue
                try:
                    if (
                        payload.get("source") not in CATALOG
                        or payload.get("scheduler_registration_id")
                        != self.bind(payload["source"], payload)
                        or payload.get("definition_sha256") != self.definition(payload)
                    ):
                        continue
                    if payload.get("collection_claim", {}).get("state") in {
                        "claimed",
                        "fetching",
                        "failed",
                        "interrupted",
                    }:
                        continue
                    due = datetime.fromisoformat(payload["next_due"])
                    if due.tzinfo is None or due > clock:
                        continue
                    request = self._request(row, clock)
                    claim = {
                        "id": hashlib.sha256(request["idempotency_key"].encode()).hexdigest(),
                        "state": "claimed",
                        "request": request,
                        "definition_sha256": payload["definition_sha256"],
                        "claimed_at": clock.isoformat(),
                    }
                    update = {
                        **payload,
                        "next_due": (
                            clock + timedelta(hours=payload["interval_hours"])
                        ).isoformat(),
                        "collection_claim": claim,
                    }
                    self.events.records.update(
                        "source_schedule",
                        row["id"],
                        update,
                        row["revision"],
                        "collection-claim:" + claim["id"],
                    )
                except (StoreError, ValueError, KeyError) as exc:
                    log.warning(
                        "event_collection_claim_refused",
                        code=getattr(exc, "code", "event_schedule_invalid"),
                    )
                    continue
                task = asyncio.create_task(self._run(row["id"], claim))
                self._tasks.add(task)
                task.add_done_callback(self._finished)

    def _finished(self, task):
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            log.error("event_collection_task_failed", error_type=type(task.exception()).__name__)

    async def wait_for_idle(self):
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=False)

    async def close(self):
        self._closed = True
        await self.wait_for_idle()
