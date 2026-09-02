"""One in-process DataHub shared by read-only Web and approved native tools."""

import asyncio
import hmac
import json
import re
from datetime import UTC, datetime

from core.observability import get_logger

from ..store import StoreError
from . import providers
from .contracts import SCHEMA_VERSION, SOURCES, Query
from .security import load_control
from .snapshots import Snapshots

log = get_logger(__name__)
__all__ = ["DataHub", "Query", "load_control"]


class DataHub:
    def __init__(self, store, *, transport=None, url=None):
        self.store = store
        self.snapshots = Snapshots(store)
        self.control = load_control(store.root, url)
        self.transport = transport
        self.tasks: dict[tuple[str, str], asyncio.Task] = {}
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

    async def query(self, sid, call_id, query: Query):
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
                        and 0 <= age < (60 if query.source == "cls_telegraph" else 900)
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
            log.info("datahub_query_started", session_id=sid, source=query.source)
            result = await providers.fetch(query, transport=self.transport)
            await asyncio.sleep(0)
            manifest = self.snapshots.publish(sid, query, result)
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
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
