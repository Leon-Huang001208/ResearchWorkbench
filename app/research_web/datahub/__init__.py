"""One in-process DataHub shared by read-only Web and approved native tools."""

import asyncio
import hmac
import json
import re
import time
from datetime import UTC, datetime
from uuid import uuid4

from core.observability import get_logger

from ..store import StoreError
from . import providers
from .broker import resolve
from .catalog import build_catalog, catalog_detail
from .contracts import SCHEMA_VERSION, SOURCES, BusinessQuery, Query
from .security import load_control
from .snapshots import Snapshots

log = get_logger(__name__)
__all__ = ["BusinessQuery", "DataHub", "Query", "load_control"]


class DataHub:
    def __init__(self, store, *, transport=None, url=None):
        self.store = store
        self.snapshots = Snapshots(store)
        self.control = load_control(store.root, url)
        self.transport = transport
        self.tasks: dict[tuple[str, str], asyncio.Task] = {}
        self.probe_tasks: dict[str, asyncio.Task] = {}
        self.probes: dict[str, dict] = {}
        self.probe_keys: dict[tuple[str, str], str] = {}
        self.cache_hits: dict[tuple[str, str], bool] = {}
        self.closed = False

    def authenticate(self, value):
        return (
            isinstance(value, str)
            and value.isascii()
            and hmac.compare_digest(value, self.control["token"])
        )

    @staticmethod
    def capabilities():
        return {
            "items": [
                {
                    "id": key,
                    "name": name,
                    "source": key,
                    "approval_required": True,
                    "available": True,
                    "schema_version": SCHEMA_VERSION,
                    "description": "父Agent单次原生审批；Web只读已有快照。",
                    "parameters": [
                        "source",
                        "code",
                        "limit",
                        "start_date",
                        "end_date",
                        "year",
                        "refresh",
                    ],
                }
                for key, name in SOURCES.items()
            ],
            "missing": ["benchmark_timeseries", "contract_download", "report_download"],
        }

    def _latest_probes(self):
        latest = {}
        for probe in self.probes.values():
            if probe.get("status") != "completed":
                continue
            current = latest.get(probe["source_id"])
            if current is None or probe["completed_at"] > current["completed_at"]:
                latest[probe["source_id"]] = probe
        return latest

    def catalog(self):
        return build_catalog(probes=self._latest_probes())

    def catalog_capability(self, capability_id):
        return catalog_detail("capability", capability_id, probes=self._latest_probes())

    def catalog_source(self, source_id):
        return catalog_detail("source", source_id, probes=self._latest_probes())

    def start_probe(self, source_id, idempotency_key):
        if not re.fullmatch(r"[a-z0-9_]{1,64}", source_id):
            raise StoreError("数据来源标识非法")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", idempotency_key):
            raise StoreError("Idempotency-Key 格式非法")
        if self.catalog_source(source_id) is None:
            raise StoreError("数据来源不存在")
        existing = self.probe_keys.get((source_id, idempotency_key))
        if existing:
            return self.probes[existing]
        probe_id = str(uuid4())
        record = {
            "id": probe_id,
            "source_id": source_id,
            "status": "checking",
            "health": "checking",
            "failure_code": None,
            "duration_ms": None,
            "last_checked_at": None,
            "completed_at": None,
        }
        self.probes[probe_id] = record
        self.probe_keys[(source_id, idempotency_key)] = probe_id
        self.probe_tasks[probe_id] = asyncio.create_task(
            self._probe(probe_id), name=f"datahub-probe-{source_id}"
        )
        return record

    async def _probe(self, probe_id):
        record = self.probes[probe_id]
        source_id = record["source_id"]
        started = time.monotonic()
        try:
            source = self.catalog_source(source_id)
            state = source["readiness"]["integration_state"]
            if state != "ready":
                outcome = {"health": "unavailable", "failure_code": state}
            else:
                outcome = await providers.probe(source_id, transport=self.transport)
            checked = datetime.now(UTC).isoformat()
            record.update(
                status="completed",
                health=outcome["health"],
                failure_code=outcome.get("failure_code"),
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                last_checked_at=checked,
                completed_at=checked,
            )
            log.info("datahub_probe_completed", source=source_id, health=record["health"])
        except asyncio.CancelledError:
            record.update(status="cancelled", health="untested", failure_code="probe_cancelled")
            raise
        except (providers.ProviderError, StoreError, KeyError, TypeError, ValueError) as exc:
            checked = datetime.now(UTC).isoformat()
            record.update(
                status="completed",
                health="unavailable",
                failure_code="probe_failed",
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                last_checked_at=checked,
                completed_at=checked,
            )
            log.warning("datahub_probe_failed", source=source_id, error_type=type(exc).__name__)
        finally:
            self.probe_tasks.pop(probe_id, None)

    def probe(self, probe_id):
        try:
            return self.probes[probe_id]
        except KeyError as exc:
            raise StoreError("检测记录不存在") from exc

    def detail(self, sid, did):
        return {
            **self.snapshots.detail(sid, did),
            "cache_hit": self.cache_hits.get((sid, did), False),
        }

    def summaries(self, sid):
        keys = {
            "id",
            "dataset_id",
            "name",
            "source",
            "provider",
            "capability",
            "attempted_sources",
            "source_url",
            "status",
            "row_count",
            "requested_range",
            "actual_range",
            "pagination_complete",
            "retrieved_at",
            "cache_hit",
            "limitations",
            "missing",
            "pages_fetched",
            "provider_total",
            "as_of",
            "files",
        }
        return [
            {key: value for key, value in item.items() if key in keys} for item in self.list(sid)
        ]

    def copy_for_upgrade(self, old_sid, new_sid):
        return self.snapshots.copy_for_upgrade(old_sid, new_sid)

    def list(self, sid):
        return sorted(
            (self.detail(sid, did) for did in self.snapshots.ids(sid)),
            key=lambda row: row["retrieved_at"],
            reverse=True,
        )

    def rows(self, sid, did, offset=0, limit=100):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 500:
            raise StoreError("资料分页参数非法")
        try:
            values = json.loads(self.snapshots.read(sid, did, "rows.json"))
            return {
                "items": values[offset : offset + limit],
                "offset": offset,
                "limit": limit,
                "total": len(values),
            }
        except ValueError as exc:
            raise StoreError("资料JSON不可读取") from exc

    def short(self, sid, manifest, *, cache_hit=False):
        self.cache_hits[(sid, manifest["dataset_id"])] = cache_hit
        return {
            **manifest,
            "sample": self.rows(sid, manifest["dataset_id"], 0, 3)["items"],
            "cache_hit": cache_hit,
        }

    async def query(self, sid, call_id, query: Query | BusinessQuery):
        self.store.session(sid)
        if self.closed or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,256}", call_id):
            raise StoreError("资料服务关闭或调用标识非法")
        key = (sid, call_id)
        receipt = self.snapshots.receipt(sid, call_id)
        fingerprint = query.fingerprint(include_refresh=True)
        if receipt:
            if receipt.get("fingerprint") not in (None, fingerprint):
                raise StoreError("同一资料调用标识不能用于不同参数")
            if receipt["status"] == "completed":
                return self.short(
                    sid, self.detail(sid, receipt["dataset_id"]), cache_hit=receipt["cache_hit"]
                )
            if key in self.tasks:
                return await asyncio.shield(self.tasks[key])
            raise StoreError("资料调用已取消、失败或上次受理状态未知；不自动重发")
        self.snapshots.receipt(sid, call_id, {"status": "pending", "fingerprint": fingerprint})
        task = asyncio.create_task(self._query(sid, call_id, query), name="datahub-query")
        self.tasks[key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self.tasks.pop(key, None)

    async def _query(self, sid, call_id, query):
        fingerprint = query.fingerprint(include_refresh=True)
        try:
            if not query.refresh:
                for candidate in self.list(sid):
                    age = (
                        datetime.now(UTC) - datetime.fromisoformat(candidate["retrieved_at"])
                    ).total_seconds()
                    if (
                        candidate["query_fingerprint"] == query.fingerprint()
                        and candidate["status"] in {"complete", "snapshot", "empty"}
                        and 0
                        <= age
                        < (
                            60
                            if query.source == "cls_telegraph"
                            or getattr(query, "capability", None) == "search_news"
                            else 900
                        )
                    ):
                        self.snapshots.receipt(
                            sid,
                            call_id,
                            {
                                "status": "completed",
                                "fingerprint": fingerprint,
                                "dataset_id": candidate["dataset_id"],
                                "cache_hit": True,
                            },
                        )
                        return self.short(sid, candidate, cache_hit=True)
            request_query = query
            resolution = None
            if isinstance(query, BusinessQuery):
                resolution = resolve(query, probes=self._latest_probes())
                provider_query = resolution.query
                source_label = resolution.provider_id
            else:
                provider_query = query
                source_label = query.source
            log.info("datahub_query_started", session_id=sid, source=source_label)
            result = await providers.fetch(provider_query, transport=self.transport)
            if resolution:
                result.provider_id = resolution.provider_id
                result.attempted_sources = resolution.attempted_sources
                keywords = request_query.parameters.get("query")
                if (
                    request_query.capability == "search_news"
                    and isinstance(keywords, str)
                    and keywords.strip()
                ):
                    before = len(result.rows)
                    needle = keywords.strip().casefold()
                    result.rows = [
                        row
                        for row in result.rows
                        if needle in str(row.get("content", "")).casefold()
                    ]
                    if before and not result.rows:
                        result.status = "empty"
                        result.limitations.append("来源快照已取得，但没有匹配关键词的电报。")
            await asyncio.sleep(0)
            manifest = self.snapshots.publish(
                sid,
                provider_query,
                result,
                request_query=request_query if resolution else None,
            )
            self.snapshots.receipt(
                sid,
                call_id,
                {
                    "status": "completed",
                    "fingerprint": fingerprint,
                    "dataset_id": manifest["dataset_id"],
                    "cache_hit": False,
                },
            )
            return self.short(sid, manifest)
        except asyncio.CancelledError:
            self.snapshots.receipt(
                sid, call_id, {"status": "cancelled", "fingerprint": fingerprint}
            )
            log.info("datahub_query_cancelled", session_id=sid)
            raise
        except Exception as exc:
            self.snapshots.receipt(sid, call_id, {"status": "failed", "fingerprint": fingerprint})
            log.error("datahub_query_failed", session_id=sid, error_type=type(exc).__name__)
            raise

    async def cancel(self, sid, call_id=None):
        self.store.session(sid)
        keys = (
            [(sid, call_id)]
            if call_id is not None
            else [key for key in self.tasks if key[0] == sid]
        )
        tasks = []
        for key in keys:
            if key in self.tasks:
                self.tasks[key].cancel()
                tasks.append(self.tasks[key])
            elif self.snapshots.receipt(key[0], key[1]) is None:
                self.snapshots.receipt(key[0], key[1], {"status": "cancelled"})
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for key in keys:
            self.tasks.pop(key, None)
        return {"cancelled": True}

    async def close(self):
        self.closed = True
        tasks = [*self.tasks.values(), *self.probe_tasks.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        self.probe_tasks.clear()
