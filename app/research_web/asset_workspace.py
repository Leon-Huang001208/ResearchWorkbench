"""Local asset workspace state over session-isolated DataHub snapshots."""

from __future__ import annotations

import asyncio
import hashlib
import operator
import re
import time
from typing import Any
from uuid import uuid4
from weakref import WeakValueDictionary

from core.observability import get_logger

from .datahub.contracts import CAPABILITY_PARAMETERS, BusinessQuery
from .store import StoreError

log = get_logger(__name__)

BLOCK_QUERIES = {
    "overview": "market_snapshot",
    "history": "market_bars",
    "valuation": "market_snapshot",
    "financials": "financials",
    "activity": "market_activity",
    "margin": "market_activity",
    "holders": "market_activity",
    "announcements": "search_announcements",
    "news": "search_news",
    "research": "search_research",
}
BLOCK_STATES = {"loading", "complete", "partial", "empty", "unavailable", "error"}
# Store remains single-worker. This witness also protects repeated in-process
# service construction from recovering an observation whose task is still alive.
_ACTIVE_OBSERVATIONS: WeakValueDictionary[tuple[str, str], asyncio.Task] = WeakValueDictionary()


class AssetWorkspaceError(StoreError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _uuid_record(records: dict, resource_id: str, label: str) -> dict:
    if not re.fullmatch(r"[a-f0-9-]{36}", resource_id) or resource_id not in records:
        raise AssetWorkspaceError(f"{label}不存在")
    return records[resource_id]


def _public_dataset(result: dict) -> dict:
    keys = {
        "dataset_id",
        "name",
        "capability",
        "source",
        "provider",
        "status",
        "row_count",
        "as_of",
        "actual_range",
        "requested_range",
        "retrieved_at",
        "fields",
        "units",
        "currency",
        "coverage",
        "pagination_complete",
        "provider_total",
        "missing",
        "limitations",
        "files",
        "asset_history",
    }
    public = {key: value for key, value in result.items() if key in keys}
    if isinstance(public.get("asset_history"), dict):
        public["asset_history"] = {
            key: value
            for key, value in public["asset_history"].items()
            if key not in {"raw_rows", "factors", "inputs", "configuration_digest"}
        }
    for name in ("query", "provider_query"):
        query = result.get(name)
        if not isinstance(query, dict):
            continue
        capability = query.get("capability")
        if capability in CAPABILITY_PARAMETERS:
            public[name] = {
                key: query[key]
                for key in ("capability", "source", "allow_fallback")
                if key in query
            }
            if isinstance(query.get("parameters"), dict):
                public[name]["parameters"] = {
                    key: value
                    for key, value in query["parameters"].items()
                    if key in CAPABILITY_PARAMETERS[capability]
                }
    provider_query = public.get("provider_query", {})
    if (
        result.get("provider") == "wind"
        and provider_query.get("capability") == "financials"
        and provider_query.get("parameters", {}).get("periods") == []
    ):
        public["limitations"] = [
            *public.get("limitations", []),
            "Wind 当前请求仅返回最新一期财务指标，不代表多期财务历史。",
        ]
    return public


def _failure_code(value: Any, default: str) -> str:
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{1,63}", value)
        else default
    )


def _observation_status(row: dict) -> str:
    states = {block["status"] for block in row["blocks"].values()}
    if "loading" in states:
        return "running"
    if states <= {"complete", "empty"}:
        return "complete"
    if states <= {"error", "unavailable"}:
        return "failed"
    return "partial"


class AssetWorkspace:
    def __init__(self, service):
        self.service = service
        self.store = service.store
        self.tasks: dict[str, asyncio.Task] = {}
        from .asset_history_jobs import HistoryJobs

        self.history_jobs = HistoryJobs(self)
        interrupted = False
        for row in self.store.data["asset_observations"].values():
            owner = _ACTIVE_OBSERVATIONS.get((str(self.store.root), row["id"]))
            if owner is not None and not owner.done():
                continue
            loading = [
                block for block in row["blocks"].values() if block.get("status") == "loading"
            ]
            if loading:
                for block in loading:
                    block.update(status="unavailable", failure_code="interrupted")
                row.update(status=_observation_status(row), updated_at=time.time())
                interrupted = True
        if interrupted:
            self.store.save()
            log.warning("asset_observation_interrupted_recovered")

    def _mark_cancelled(self, row: dict) -> None:
        for block in row["blocks"].values():
            if block["status"] == "loading":
                block.update(status="unavailable", failure_code="cancelled")
        row.update(status="cancelled", updated_at=time.time())
        self.store.save()
        log.info("asset_observation_cancelled")

    def _track_task(self, row: dict, key: str, task: asyncio.Task) -> None:
        self.tasks[key] = task
        _ACTIVE_OBSERVATIONS[(str(self.store.root), row["id"])] = task

        def completed(done: asyncio.Task) -> None:
            self.tasks.pop(key, None)
            # Cancelling before the coroutine starts never enters _run's try.
            if done.cancelled() and any(
                block["status"] == "loading" for block in row["blocks"].values()
            ):
                self._mark_cancelled(row)

        task.add_done_callback(completed)

    def public_observation(self, row: dict) -> dict:
        result = {
            key: value
            for key, value in row.items()
            if key not in {"request", "refresh_keys", "history_generation"}
        }
        result["request_parameters"] = {
            key: value
            for key, value in row.get("request", {}).items()
            if key
            in {
                "start_date",
                "end_date",
                "frequency",
                "adjustment",
                "section_sources",
                "section_ranges",
            }
        }
        # Project defaults for legacy records without migrating persisted requests.
        result["request_parameters"].setdefault("section_sources", {})
        result["request_parameters"].setdefault("section_ranges", {})
        result["blocks"] = {
            name: {
                **{key: value for key, value in block.items() if key != "sample"},
                "dataset": (
                    _public_dataset(block["dataset"])
                    if isinstance(block.get("dataset"), dict)
                    else None
                ),
                "requested_source": self._source(row, name),
                "requested_range": self._requested_range(row, name),
            }
            for name, block in row["blocks"].items()
        }
        result["dataset_ids"] = [
            block["dataset"]["dataset_id"]
            for block in row["blocks"].values()
            if isinstance(block.get("dataset"), dict) and block["dataset"].get("dataset_id")
        ]
        result["history_job"] = self.history_jobs.current(row["id"])
        return result

    def chart_preferences(self) -> dict:
        value = self.store.data["chart_preferences"]
        return {"panels": list(value["panels"]), "revision": value["revision"]}

    def set_chart_preferences(self, panels: list[str]) -> dict:
        if (
            not isinstance(panels, list)
            or len(panels) > 4
            or len(set(panels)) != len(panels)
            or any(p not in {"volume", "macd", "kdj", "rsi"} for p in panels)
        ):
            raise AssetWorkspaceError("图表副图必须是最多四个唯一的受支持面板")
        previous = self.store.data["chart_preferences"]
        self.store.data["chart_preferences"] = {
            "panels": list(panels),
            "revision": previous["revision"] + 1,
        }
        try:
            self.store.save()
        except Exception:
            self.store.data["chart_preferences"] = previous
            log.error("asset_chart_preferences_save_failed")
            raise
        log.info("asset_chart_preferences_updated", panels=len(panels))
        return self.chart_preferences()

    async def create_observation(self, body, idempotency_key: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", idempotency_key):
            raise AssetWorkspaceError("Idempotency-Key 格式非法")
        digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        existing = self.store.data["asset_observation_keys"].get(digest)
        if existing:
            return self.public_observation(self.store.data["asset_observations"][existing])
        session_id = body.session_id
        if session_id is None:
            created = await self.service.create("fingpt", f"资产观察 · {body.asset}")
            session_id = created["id"]
        else:
            self.store.session(session_id)
        observation_id = str(uuid4())
        sections = list(dict.fromkeys(body.sections))
        row = {
            "id": observation_id,
            "session_id": session_id,
            "asset": body.asset.upper(),
            "asset_type": body.asset_type,
            "source": body.source,
            "status": "running",
            "created_at": time.time(),
            "updated_at": time.time(),
            "blocks": {
                section: {"status": "loading", "dataset": None, "failure_code": None}
                for section in sections
            },
            "request": body.model_dump(),
        }
        self.store.data["asset_observations"][observation_id] = row
        self.store.data["asset_observation_keys"][digest] = observation_id
        self.store.save()
        task = asyncio.create_task(self._run(row), name=f"asset-observation-{observation_id}")
        self._track_task(row, observation_id, task)
        return self.public_observation(row)

    async def refresh_block(self, observation_id: str, block: str, idempotency_key: str) -> dict:
        row = _uuid_record(self.store.data["asset_observations"], observation_id, "资产观察")
        if block not in BLOCK_QUERIES or block not in row["blocks"]:
            raise AssetWorkspaceError("该观察没有此区块")
        if block == "history" and self.history_jobs.active(observation_id):
            raise AssetWorkspaceError("历史任务仍在读取或排空，请等待终态", 409)
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", idempotency_key):
            raise AssetWorkspaceError("Idempotency-Key 格式非法")
        digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        keys = row.get("refresh_keys", {})
        if digest in keys:
            if keys[digest]["block"] != block:
                raise AssetWorkspaceError("同一刷新标识不能用于不同区块", 409)
            return self.public_observation(row)
        if any(state["status"] == "loading" for state in row["blocks"].values()):
            raise AssetWorkspaceError("观察区块正在读取，请等待本次结果", 409)
        previous_block = dict(row["blocks"][block])
        previous_status, previous_updated_at = row["status"], row["updated_at"]
        had_keys = "refresh_keys" in row
        call_id = f"asset:{observation_id}:{block}:{uuid4()}"
        keys[digest] = {"block": block, "call_id": call_id}
        row["refresh_keys"] = keys
        row["blocks"][block].update(status="loading", failure_code=None)
        row.update(status="running", updated_at=time.time())
        try:
            self.store.save()
        except Exception as exc:
            # No query starts after failed or unconfirmed persistence.
            keys.pop(digest, None)
            if not had_keys:
                row.pop("refresh_keys", None)
            row["blocks"][block].clear()
            row["blocks"][block].update(previous_block)
            row.update(status=previous_status, updated_at=previous_updated_at)
            log.error("asset_observation_refresh_admission_failed", error_type=type(exc).__name__)
            raise StoreError(
                "区块刷新受理保存失败，未启动取数", "asset_observation_save_failed", 503
            ) from exc
        task = asyncio.create_task(
            self._run(row, [block], refresh_call_id=call_id), name="asset-observation-refresh"
        )
        self._track_task(row, call_id, task)
        log.info("asset_observation_block_refresh_started", block=block)
        return self.public_observation(row)

    def _parameters(self, row: dict, block: str) -> dict[str, Any]:
        request = row["request"]
        interval = request.get("section_ranges", {}).get(block, request)
        asset = row["asset"]
        if block == "overview":
            return {"assets": [asset], "asset_type": row["asset_type"]}
        if block == "valuation":
            return {
                "assets": [asset],
                "asset_type": row["asset_type"],
                "fields": ["close", "pe_ttm", "pb", "total_shares"],
            }
        if block == "history":
            return {
                "asset": asset,
                "asset_type": row["asset_type"],
                "start_date": interval.get("start_date"),
                "end_date": interval.get("end_date"),
                "frequency": request.get("frequency", "daily"),
                "adjustment": request.get("adjustment", "qfq"),
            }
        if block == "financials":
            return {"asset": asset, "statements": ["indicators"], "periods": []}
        if block == "holders":
            return {"asset": asset, "dataset": "holder_data", "end_date": request.get("end_date")}
        if block in {"activity", "margin"}:
            return {
                "asset": asset,
                "dataset": "margin_trading" if block == "margin" else "fund_flow",
                "start_date": interval.get("start_date"),
                "end_date": interval.get("end_date"),
            }
        if block == "announcements":
            return {
                "asset": asset,
                "start_date": request.get("start_date"),
                "end_date": request.get("end_date"),
            }
        if block == "news":
            return {"query": asset, "limit": 30}
        return {"query": asset, "document_type": "all", "limit": 30}

    def _source(self, row: dict, block: str) -> str:
        return row["request"].get("section_sources", {}).get(block, row["source"])

    def _requested_range(self, row: dict, block: str) -> dict[str, Any]:
        return {
            key: value
            for key, value in self._parameters(row, block).items()
            if key in {"start_date", "end_date"} and value is not None
        }

    async def _run_block(
        self, row: dict, block: str, *, refresh_call_id: str | None = None
    ) -> None:
        state = row["blocks"][block]
        try:
            parameters = {
                key: value
                for key, value in self._parameters(row, block).items()
                if value is not None
            }
            result = await self.service.datahub.query(
                row["session_id"],
                refresh_call_id or f"asset:{row['id']}:{block}",
                BusinessQuery(
                    capability=BLOCK_QUERIES[block],
                    source=self._source(row, block),
                    parameters=parameters,
                    refresh=refresh_call_id is not None,
                ),
            )
            provider_status = result.get("status")
            status = {
                "complete": "complete",
                "snapshot": "complete",
                "empty": "empty",
                "partial": "partial",
                "failed": "unavailable",
                "unavailable": "unavailable",
                "stale": "unavailable",
            }.get(provider_status, "error")
            failure = None
            if status in {"unavailable", "error"}:
                limitations = result.get("limitations", [])
                failure = _failure_code(
                    result.get("failure_code"),
                    "data_unavailable" if status == "unavailable" else "unexpected_provider_status",
                )
                if limitations:
                    failure = _failure_code(limitations[0], failure)
            state.update(
                status=status,
                dataset=(
                    state["dataset"]
                    if refresh_call_id and failure and state.get("dataset")
                    else _public_dataset(result)
                ),
                sample=result.get("sample", []),
                failure_code=failure,
            )
            if block == "overview" and status == "complete" and result.get("sample"):
                observation = {
                    "status": provider_status,
                    "as_of": result.get("as_of"),
                    **result["sample"][0],
                }
                self.evaluate_alerts(row["asset"], observation)
        except asyncio.CancelledError:
            state.update(status="unavailable", failure_code="cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 - failures must settle this block independently.
            state.update(
                status="error",
                failure_code=_failure_code(getattr(exc, "code", None), "query_failed"),
            )
            log.warning(
                "asset_observation_block_failed",
                block=block,
                error_type=type(exc).__name__,
            )

    async def _run(
        self, row: dict, blocks: list[str] | None = None, *, refresh_call_id: str | None = None
    ) -> None:
        try:
            selected = list(row["blocks"]) if blocks is None else blocks
            if any(
                self._source(row, block) in {"auto", "wind", "tinysoft", "akshare"}
                for block in selected
            ):
                for block in selected:
                    await self._run_block(row, block, refresh_call_id=refresh_call_id)
            else:
                await asyncio.gather(
                    *(
                        self._run_block(row, block, refresh_call_id=refresh_call_id)
                        for block in selected
                    )
                )
            row["status"] = _observation_status(row)
            row["updated_at"] = time.time()
            self.store.save()
            self.service.notify()
            log.info("asset_observation_completed", status=row["status"])
        except asyncio.CancelledError:
            self._mark_cancelled(row)
            raise

    def observation(self, observation_id: str) -> dict:
        row = _uuid_record(self.store.data["asset_observations"], observation_id, "资产观察")
        return self.public_observation(row)

    def list_observations(self) -> list[dict]:
        rows = [
            self.public_observation(row) for row in self.store.data["asset_observations"].values()
        ]
        return sorted(rows, key=lambda row: row["updated_at"], reverse=True)

    def create_watchlist(self, name: str, polling_minutes: int | None) -> dict:
        row: dict[str, Any] = {
            "id": str(uuid4()),
            "name": name.strip(),
            "polling_minutes": polling_minutes,
            "items": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.store.data["watchlists"][row["id"]] = row
        self.store.save()
        return row

    def add_watchlist_item(self, watchlist_id: str, item: dict) -> dict:
        watchlist = _uuid_record(self.store.data["watchlists"], watchlist_id, "自选列表")
        if any(entry["asset"] == item["asset"].upper() for entry in watchlist["items"]):
            raise AssetWorkspaceError("资产已在自选列表中", 409)
        row = {
            "id": str(uuid4()),
            **item,
            "asset": item["asset"].upper(),
            "created_at": time.time(),
        }
        watchlist["items"].append(row)
        watchlist["updated_at"] = time.time()
        self.store.save()
        return row

    def create_note(self, asset: str, text: str) -> dict:
        row = {
            "id": str(uuid4()),
            "asset": asset.upper(),
            "text": text.strip(),
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.store.data["asset_notes"][row["id"]] = row
        self.store.save()
        return row

    def patch_note(self, note_id: str, text: str) -> dict:
        row = _uuid_record(self.store.data["asset_notes"], note_id, "观察笔记")
        row.update(text=text.strip(), updated_at=time.time())
        self.store.save()
        return row

    def create_alert(self, data: dict) -> dict:
        row = {
            "id": str(uuid4()),
            **data,
            "asset": data["asset"].upper(),
            "enabled": True,
            "condition_active": False,
            "last_triggered_at": None,
            "last_evaluated_at": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.store.data["asset_alerts"][row["id"]] = row
        self.store.save()
        return row

    def patch_alert(self, alert_id: str, changes: dict) -> dict:
        row = _uuid_record(self.store.data["asset_alerts"], alert_id, "提醒规则")
        row.update({key: value for key, value in changes.items() if value is not None})
        row["updated_at"] = time.time()
        self.store.save()
        return row

    def evaluate_alerts(self, asset: str, observation: dict) -> list[dict]:
        if observation.get("status") in {"stale", "unavailable", "failed", "partial", "empty"}:
            return []
        operations = {"gt": operator.gt, "gte": operator.ge, "lt": operator.lt, "lte": operator.le}
        now = time.time()
        created = []
        changed = False
        for alert in self.store.data["asset_alerts"].values():
            if not alert.get("enabled") or alert["asset"] != asset.upper():
                continue
            value = observation.get(alert["field"])
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            matched = operations[alert["operator"]](float(value), float(alert["threshold"]))
            alert["last_evaluated_at"] = now
            changed = True
            if not matched:
                alert["condition_active"] = False
                continue
            if alert.get("condition_active"):
                continue
            previous = alert.get("last_triggered_at")
            if previous and now - previous < alert["cooldown_minutes"] * 60:
                alert["condition_active"] = True
                continue
            alert.update(condition_active=True, last_triggered_at=now)
            notification = {
                "id": str(uuid4()),
                "alert_id": alert["id"],
                "asset": alert["asset"],
                "field": alert["field"],
                "value": value,
                "threshold": alert["threshold"],
                "as_of": observation.get("as_of"),
                "created_at": now,
                "read": False,
            }
            self.store.data["asset_notifications"][notification["id"]] = notification
            created.append(notification)
        if changed:
            self.store.save()
        return created

    async def close(self) -> None:
        await self.history_jobs.close()
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
