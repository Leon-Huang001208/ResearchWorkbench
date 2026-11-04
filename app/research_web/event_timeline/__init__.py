"""Account-local event timeline; deterministic data work never starts research models."""

import asyncio
import calendar
import contextvars
import hashlib
import threading
from datetime import UTC, datetime, timedelta

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import admission

from ..dossiers.lock import retention_lock
from ..store import StoreError
from . import models, sources
from .evidence import EvidenceArchive
from .storage import RecordStore, canonical, fail, now

log = get_logger(__name__)


class TimelineService:
    def __init__(self, research, *, fetcher=None, schedule_binder=None):
        self.research = research
        self.records = RecordStore(research.store.root)
        self.storage = self.records
        self.archive = EvidenceArchive(self.records)
        self.fetcher = fetcher or sources.fetch
        self.schedule_binder = schedule_binder
        self._active = set()
        self._import_slots = asyncio.Semaphore(2)
        self._closed = False

    @property
    def active(self):
        return bool(self._active)

    async def close(self):
        self._closed = True
        scheduler = getattr(self.schedule_binder, "__self__", None)
        if scheduler is not None and hasattr(scheduler, "close"):
            await scheduler.close()
        if self._active:
            await asyncio.gather(*tuple(self._active), return_exceptions=True)

    def archive_evidence(self, raw, *, source, url, metadata=None, guard=None):
        with admission():
            return self.archive.archive(raw, source=source, url=url, metadata=metadata, guard=guard)

    def read_evidence(self, reference):
        return self.archive.read(reference)

    resolve_evidence = read_evidence

    def _request(self, scope, body):
        key = body["idempotency_key"]
        return key, self.records.cached(scope, key, body)

    def create(self, body):
        body = models.Create.model_validate(body).model_dump(mode="json")
        key, old = self._request("timeline-create", body)
        if old is not None:
            return old[0]
        payload = {k: v for k, v in body.items() if k != "idempotency_key"}
        payload.update(
            admission="candidate",
            origin="manual",
            first_observed=now(),
            source_published_at=None,
            evidence_refs=[],
            report_ids=[],
            formal_backtest_eligible=False,
        )
        return self.records.batch(
            [{"kind": "event", "payload": payload}], key, intent=body, scope="timeline-create"
        )[0]

    def detail(self, identifier, revision=None):
        event = self.records.get("event", identifier, revision=revision)
        gaps = []
        for ref in event["payload"].get("evidence_refs", []):
            try:
                self.read_evidence(ref)
            except StoreError as exc:
                gaps.append({"id": ref.get("id"), "code": exc.code})
        return {**event, "evidence_gaps": gaps}

    def revise(self, identifier, body):
        body = models.Revise.model_validate(body).model_dump(mode="json")
        intent = {"id": identifier, **body}
        key, old = self._request("timeline-revise", intent)
        if old is not None:
            return old[0]
        previous = self.records.get("event", identifier)
        payload = {
            **previous["payload"],
            **{
                k: v
                for k, v in body.items()
                if k not in {"idempotency_key", "expected_revision", "reason"}
            },
        }
        payload.update(
            admission="candidate", revision_reason=body["reason"], formal_backtest_eligible=False
        )
        return self.records.batch(
            [
                {
                    "kind": "event",
                    "id": identifier,
                    "expected_revision": body["expected_revision"],
                    "payload": payload,
                }
            ],
            key,
            intent=intent,
            scope="timeline-revise",
        )[0]

    def _selected(self, refs, *, confirmed=False):
        if len({ref["id"] for ref in refs}) != len(refs):
            fail("event_duplicate_selection", 422)
        result = []
        for ref in refs:
            row = self.records.get("event", ref["id"])
            if row["revision"] != ref["revision"]:
                fail("event_revision_conflict")
            if row["payload"].get("superseded_by") or (
                confirmed and row["payload"].get("admission") != "confirmed"
            ):
                fail("event_admission_required")
            for evidence in row["payload"].get("evidence_refs", []):
                self.read_evidence(evidence)
            result.append(row)
        return result

    def decide(self, body):
        body = models.Decision.model_validate(body).model_dump(mode="json")
        key, old = self._request("timeline-decide", body)
        if old is not None:
            return {"items": old}
        rows = self._selected(body["events"])
        ops = []
        for row in rows:
            payload = {
                **row["payload"],
                "admission": body["decision"],
                "decision_reason": body["reason"],
                "decision_at": now(),
                "decision_owner": self.records.owner_binding,
            }
            ops.append(
                {
                    "kind": "event",
                    "id": row["id"],
                    "expected_revision": row["revision"],
                    "payload": payload,
                }
            )
        return {"items": self.records.batch(ops, key, intent=body, scope="timeline-decide")}

    def freeze(self, body):
        body = models.Freeze.model_validate(body).model_dump(mode="json")
        key, old = self._request("timeline-freeze", body)
        if old is not None:
            result = old[-1]
            for ref in result["payload"]["evidence_refs"]:
                self.read_evidence(ref)
            return result
        rows = self._selected(body["events"], confirmed=True)
        refs = {ref["id"]: ref for row in rows for ref in row["payload"].get("evidence_refs", [])}
        payload = {
            "label": body["label"],
            "event_refs": body["events"],
            "events": rows,
            "evidence_refs": list(refs.values()),
            "owner_binding": self.records.owner_binding,
            "frozen_at": now(),
            "formal_backtest_eligible": all(
                row["payload"].get("formal_backtest_eligible") is True for row in rows
            ),
        }
        payload["snapshot_sha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
        ops = [
            {
                "kind": "event",
                "id": row["id"],
                "payload": row["payload"],
                "expected_revision": row["revision"],
                "check_only": True,
            }
            for row in rows
        ]
        ops.append({"kind": "freeze", "payload": payload})
        return self.records.batch(ops, key, intent=body, scope="timeline-freeze")[-1]

    def merge(self, body):
        body = models.Merge.model_validate(body).model_dump(mode="json")
        key, old = self._request("timeline-merge", body)
        if old is not None:
            return {"event": old[-1], "parents": old[:-1]}
        rows = self._selected(body["events"])
        payload = {
            **rows[0]["payload"],
            "title": body["title"],
            "admission": "candidate",
            "merge_reason": body["reason"],
            "parent_refs": body["events"],
            "formal_backtest_eligible": False,
        }
        payload["evidence_refs"] = list(
            {
                ref["id"]: ref for row in rows for ref in row["payload"].get("evidence_refs", [])
            }.values()
        )
        payload["report_ids"] = list(
            dict.fromkeys(ref for row in rows for ref in row["payload"].get("report_ids", []))
        )
        token = hashlib.sha256(canonical(body).encode()).hexdigest()
        ops = [
            {
                "kind": "event",
                "id": row["id"],
                "expected_revision": row["revision"],
                "payload": {**row["payload"], "superseded_by": token, "admission": "rejected"},
            }
            for row in rows
        ]
        ops.append({"kind": "event", "payload": payload})
        result = self.records.batch(ops, key, intent=body, scope="timeline-merge")
        return {"event": result[-1], "parents": result[:-1]}

    def split(self, identifier, body):
        body = models.Split.model_validate(body).model_dump(mode="json")
        intent = {"id": identifier, **body}
        key, old = self._request("timeline-split", intent)
        if old is not None:
            return {"parent": old[0], "children": old[1:]}
        row = self._selected([{"id": identifier, "revision": body["expected_revision"]}])[0]
        ops = [
            {
                "kind": "event",
                "id": identifier,
                "expected_revision": row["revision"],
                "payload": {
                    **row["payload"],
                    "admission": "rejected",
                    "superseded_by": "split",
                    "split_reason": body["reason"],
                },
            }
        ]
        for child in body["children"]:
            ops.append(
                {
                    "kind": "event",
                    "payload": {
                        **row["payload"],
                        **child,
                        "admission": "candidate",
                        "parent_refs": [{"id": identifier, "revision": row["revision"]}],
                        "formal_backtest_eligible": False,
                    },
                }
            )
        result = self.records.batch(ops, key, intent=intent, scope="timeline-split")
        return {"parent": result[0], "children": result[1:]}

    def timeline(
        self,
        *,
        start="1990-01-01",
        end=None,
        market=None,
        category=None,
        admission_state=None,
        lifecycle=None,
        q="",
        limit=100,
        cursor=None,
    ):
        current = datetime.now(UTC)
        end = (
            end
            or f"{current.year + 1}-{current.month:02d}-{min(current.day, calendar.monthrange(current.year + 1, current.month)[1]):02d}"
        )
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            fail("event_query_invalid", 422)
        if (
            not isinstance(q, str)
            or len(q) > 120
            or start > end
            or not 1 <= limit <= 200
            or (cursor is not None and (not str(cursor).isdigit() or int(cursor) > 100000000))
        ):
            fail("event_query_invalid", 422)
        event_start = "json_extract(r.payload,'$.occurrence_start')"
        event_end = "COALESCE(json_extract(r.payload,'$.occurrence_end'),json_extract(r.payload,'$.occurrence_start'))"
        conditions, params = [
            "r.kind='event'",
            f"(CASE WHEN length({event_end})=7 THEN {event_end}||'-31' ELSE {event_end} END)>=?",
            f"(CASE WHEN length({event_start})=7 THEN {event_start}||'-01' ELSE {event_start} END)<=?",
        ], [start, end + "T23:59:59Z"]
        if q:
            conditions.append(
                "instr(lower(COALESCE(json_extract(r.payload,'$.title'),'')||' '||COALESCE(json_extract(r.payload,'$.description'),'')),lower(?))>0"
            )
            params.append(q)
        for field, value in (
            ("category", category),
            ("admission", admission_state),
            ("lifecycle", lifecycle),
        ):
            if value:
                conditions.append(f"json_extract(r.payload,'$.{field}')=?")
                params.append(value)
        if market:
            conditions.append(
                "EXISTS(SELECT 1 FROM json_each(r.payload,'$.markets') WHERE value=?)"
            )
            params.append(market)
        with self.records.connection() as conn:
            if conn is None:
                return {
                    "items": [],
                    "next_cursor": None,
                    "coverage": "not_loaded",
                    "sources": self.source_catalog()["items"],
                }
            sql = (
                "SELECT r.* FROM records r JOIN(SELECT id,MAX(revision) revision FROM records WHERE kind='event' GROUP BY id) latest ON r.id=latest.id AND r.revision=latest.revision WHERE "
                + " AND ".join(conditions)
                + " ORDER BY json_extract(r.payload,'$.occurrence_start') DESC,r.id LIMIT ? OFFSET ?"
            )
            rows = conn.execute(sql, (*params, limit + 1, int(cursor or 0))).fetchall()
            return {
                "items": [self.records._decode(row) for row in rows[:limit]],
                "next_cursor": str(int(cursor or 0) + limit) if len(rows) > limit else None,
                "coverage": "source_scoped_partial",
                "sources": self.source_catalog()["items"],
            }

    def source_catalog(self):
        schedules = {
            row["payload"]["source"]: row for row in self.records.list("source_schedule")["items"]
        }
        return {
            "items": [
                {
                    "id": key,
                    **value,
                    "schedule": schedules.get(key),
                    "enabled": self.schedule_binder is not None
                    and bool(schedules.get(key, {}).get("payload", {}).get("enabled", False)),
                    "scheduling_ready": self.schedule_binder is not None,
                }
                for key, value in sources.CATALOG.items()
            ],
            "future_default_months": 12,
            "history_start": "1990-01-01",
        }

    def coverage(self):
        return {
            "history_start": "1990-01-01",
            "complete": False,
            "qualification_reconciliation_required": self.records.qualification_status()[
                "required"
            ],
            "items": self.records.list("coverage", limit=200)["items"],
            "unsupported_auto_categories": [
                {"category": "sports", "source": "fifa", "status": "manual_only"}
            ],
            "gaps": [
                "未加载年份／来源不能视为无事件",
                "历史首次公开时间和PIT资格逐记录核验",
                "FIFA／世界杯自动采集尚未实现，当前仅支持人工录入候选",
                "中国宏观历史仍需逐源补齐",
            ],
        }

    def schedule(self, source, body):
        if source not in sources.CATALOG:
            fail("event_source_invalid", 422)
        body = {"interval_hours": 1 if source in {"gdelt", "ucdp"} else 24, **body}
        body = models.Schedule.model_validate(body).model_dump(mode="json")
        intent = {"source": source, **body}
        key, previous = self._request("timeline-schedule", intent)
        if previous is not None:
            return previous[0]
        if body["enabled"] and self.schedule_binder is None:
            fail("event_schedule_not_configured", 409)
        if body["enabled"] and sources.CATALOG[source].get("requires_token"):
            fail("event_source_credentials_required", 409)
        rows = [
            row
            for row in self.records.list("source_schedule")["items"]
            if row["payload"]["source"] == source
        ]
        payload = {
            "source": source,
            "enabled": body["enabled"],
            "interval_hours": body["interval_hours"],
            "owner_binding": self.records.owner_binding,
        }
        if self.schedule_binder is not None:
            from .scheduler import CollectionScheduler

            payload["scheduler_registration_id"] = self.schedule_binder(source, body)
            payload["definition_sha256"] = CollectionScheduler.definition(payload)
            payload["next_due"] = (
                datetime.now(UTC) + timedelta(hours=body["interval_hours"])
            ).isoformat()
        if rows:
            ops = [
                {
                    "kind": "source_schedule",
                    "id": rows[0]["id"],
                    "payload": payload,
                    "expected_revision": body["expected_revision"],
                }
            ]
            return self.records.batch(ops, key, intent=intent, scope="timeline-schedule")[0]
        if body["expected_revision"] != 1:
            fail("event_revision_conflict")
        identifier = hashlib.sha256(
            canonical(
                {
                    "owner_binding": self.records.owner_binding,
                    "source": source,
                    "format": "event-source-schedule-v1",
                }
            ).encode()
        ).hexdigest()[:32]
        return self.records.batch(
            [{"kind": "source_schedule", "new_id": identifier, "payload": payload}],
            key,
            intent=intent,
            scope="timeline-schedule",
        )[0]

    def _process_source(self, job, body, url, raw, guard, cancelled):
        """Bounded worker retains its lease until all accepted writes have drained."""

        def check():
            if cancelled.is_set() or self._closed:
                fail("event_source_cancelled")
            if guard is not None:
                guard()

        check()
        intent = {k: body[k] for k in ("source", "year", "page", "offset")}
        reference = self.archive_evidence(raw, source=body["source"], url=url, guard=check)
        parsed = sources.parse(body["source"], raw, offset=body["offset"], page=body["page"])
        next_year = body["year"]
        if body["source"] == "gdelt":
            if parsed["next_offset"] is not None:
                parsed["next_page"] = body["page"]
            else:
                try:
                    sources.endpoint("gdelt", body["year"], body["page"] + 1)
                    parsed["next_page"] = body["page"] + 1
                except StoreError:
                    next_year = body["year"] + 1
                    try:
                        sources.endpoint("gdelt", next_year, 0)
                        parsed["next_page"] = 0
                    except StoreError:
                        parsed["next_page"], next_year = None, None
        imported = []
        with admission(), retention_lock(self.records.root):
            check()
            for number, candidate in enumerate(parsed["events"]):
                check()
                external_id = candidate.pop("external_id")
                identity = {"source": body["source"], "external_id": external_id}
                source_key = (
                    "source-event:" + hashlib.sha256(canonical(identity).encode()).hexdigest()
                )
                old = self.records.cached("source-event", source_key, identity)
                first = self.records.get("event", old[0]["id"]) if old else None
                if first and first["payload"].get("superseded_by"):
                    imported.append(first["id"])
                    continue
                digest = hashlib.sha256(canonical(candidate).encode()).hexdigest()
                if first and first["payload"].get("source_content_sha256") == digest:
                    imported.append(first["id"])
                    continue
                check()
                report = self.records.create(
                    "report",
                    {
                        "source": body["source"],
                        "external_id": external_id,
                        "evidence_ref": reference,
                        "candidate": candidate,
                    },
                    f"source-report:{job['id']}:{number}",
                    guard=check,
                )
                payload = {
                    **candidate,
                    "origin": "source",
                    "source": body["source"],
                    "external_id": external_id,
                    "first_observed": first["payload"]["first_observed"] if first else now(),
                    "admission": "candidate",
                    "evidence_refs": [reference],
                    "report_ids": [report["id"]],
                    "source_content_sha256": digest,
                    "formal_backtest_eligible": False,
                }
                check()
                if first:
                    event = self.records.update(
                        "event",
                        first["id"],
                        payload,
                        first["revision"],
                        f"source-update:{job['id']}:{number}",
                        guard=check,
                    )
                else:
                    event = self.records.batch(
                        [{"kind": "event", "payload": payload}],
                        source_key,
                        intent=identity,
                        scope="source-event",
                        guard=check,
                    )[0]
                imported.append(event["id"])
                check()
                if (number + 1) % 100 == 0:
                    job = self.records.update(
                        "source_job",
                        job["id"],
                        {
                            **job["payload"],
                            "checkpoint": {
                                "page": body["page"],
                                "offset": body["offset"] + number + 1,
                                "imported": len(imported),
                            },
                        },
                        job["revision"],
                        f"source-progress:{job['id']}:{number}",
                        guard=check,
                    )
            check()
            self.records.create(
                "coverage",
                {
                    **intent,
                    "url": url,
                    "raw_ref": reference,
                    "event_count": len(imported),
                    "state": "partial_page",
                    "bounded": parsed["bounded"],
                    "observed_at": now(),
                    "historical_pit": False,
                },
                f"source-coverage:{job['id']}",
                guard=check,
            )
            payload = {
                **job["payload"],
                "state": "completed",
                "checkpoint": {
                    "page": body["page"],
                    "next_page": parsed["next_page"],
                    "next_year": next_year,
                    "offset": body["offset"],
                    "next_offset": parsed["next_offset"],
                    "imported": len(imported),
                },
                "event_ids": imported,
                "raw_ref": reference,
                "completed_at": now(),
                "coverage": "partial_page",
            }
            check()
            return self.records.update(
                "source_job",
                job["id"],
                payload,
                job["revision"],
                f"source-complete:{job['id']}",
                guard=check,
            )

    async def refresh(self, body, *, guard=None):
        body = models.Refresh.model_validate(body).model_dump(mode="json")
        if self._closed:
            fail("event_host_closed", 503)
        url = sources.endpoint(body["source"], body["year"], body["page"])
        key = "source-request:" + body["idempotency_key"]
        intent = {k: body[k] for k in ("source", "year", "page", "offset")}
        previous = self.records.cached("source_job", key, intent)
        if previous:
            return self.records.get("source_job", previous[0]["id"])
        with admission():
            job = self.records.batch(
                [
                    {
                        "kind": "source_job",
                        "payload": {
                            **intent,
                            "url": url,
                            "state": "fetching",
                            "checkpoint": {"page": body["page"], "imported": 0},
                            "started_at": now(),
                        },
                    }
                ],
                key,
                intent=intent,
                scope="source_job",
            )[0]
        task = asyncio.current_task()
        self._active.add(task)
        slot_acquired = False
        try:
            try:
                await asyncio.wait_for(self._import_slots.acquire(), timeout=0.1)
                slot_acquired = True
            except TimeoutError:
                fail("event_import_capacity", 429)
            if self._closed:
                fail("event_host_closed", 503)
            if guard is not None:
                guard()
            actual_url, raw = await self.fetcher(body["source"], body["year"], body["page"])
            if guard is not None:
                guard()
            if actual_url != url:
                fail("event_source_identity_changed", 502)
            cancelled = threading.Event()
            worker = asyncio.get_running_loop().run_in_executor(
                None,
                contextvars.copy_context().run,
                self._process_source,
                job,
                body,
                url,
                raw,
                guard,
                cancelled,
            )
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                cancelled.set()
                while not worker.done():
                    try:
                        await asyncio.shield(worker)
                    except asyncio.CancelledError:
                        continue
                    except (StoreError, ValueError, OSError):
                        break
                if worker.done() and not worker.cancelled():
                    worker.exception()
                raise
        except asyncio.CancelledError:
            job = self.records.get("source_job", job["id"])
            self.records.update(
                "source_job",
                job["id"],
                {**job["payload"], "state": "interrupted", "code": "event_source_cancelled"},
                job["revision"],
                f"source-interrupted:{job['id']}",
            )
            raise
        except (StoreError, ValueError, OSError) as exc:
            log.warning(
                "event_refresh_failed", source=body["source"], error_type=type(exc).__name__
            )
            job = self.records.get("source_job", job["id"])
            return self.records.update(
                "source_job",
                job["id"],
                {
                    **job["payload"],
                    "state": "failed",
                    "code": getattr(exc, "code", "event_source_failed"),
                },
                job["revision"],
                f"source-failed:{job['id']}",
            )
        finally:
            if slot_acquired:
                self._import_slots.release()
            self._active.discard(task)


from .routes import router

__all__ = ["TimelineService", "router"]
