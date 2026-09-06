"""Local asset workspace state over session-isolated DataHub snapshots."""

from __future__ import annotations

import asyncio
import hashlib
import operator
import re
import time
from typing import Any
from uuid import uuid4

from core.observability import get_logger

from .datahub.contracts import BusinessQuery
from .store import StoreError

log = get_logger(__name__)

BLOCK_QUERIES = {
    "overview": "market_snapshot",
    "history": "market_bars",
    "financials": "financials",
    "activity": "market_activity",
    "announcements": "search_announcements",
    "news": "search_news",
    "research": "search_research",
}
BLOCK_STATES = {"loading", "complete", "partial", "empty", "unavailable", "error"}


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
        "missing",
        "limitations",
        "files",
    }
    return {key: value for key, value in result.items() if key in keys}


class AssetWorkspace:
    def __init__(self, service):
        self.service = service
        self.store = service.store
        self.tasks: dict[str, asyncio.Task] = {}

    def public_observation(self, row: dict) -> dict:
        result = {key: value for key, value in row.items() if key != "request"}
        result["blocks"] = {
            name: {key: value for key, value in block.items() if key != "sample"}
            for name, block in row["blocks"].items()
        }
        result["dataset_ids"] = [
            block["dataset"]["dataset_id"]
            for block in row["blocks"].values()
            if isinstance(block.get("dataset"), dict) and block["dataset"].get("dataset_id")
        ]
        return result

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
        self.tasks[observation_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(observation_id, None))
        return self.public_observation(row)

    def _parameters(self, row: dict, block: str) -> dict[str, Any]:
        request = row["request"]
        asset = row["asset"]
        if block == "overview":
            return {"assets": [asset]}
        if block == "history":
            return {
                "asset": asset,
                "start_date": request.get("start_date"),
                "end_date": request.get("end_date"),
                "frequency": request.get("frequency", "daily"),
                "adjustment": request.get("adjustment", "qfq"),
            }
        if block == "financials":
            return {"asset": asset, "statements": ["indicators"], "periods": 8}
        if block == "activity":
            return {
                "asset": asset,
                "dataset": "fund_flow",
                "start_date": request.get("start_date"),
                "end_date": request.get("end_date"),
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

    async def _run_block(self, row: dict, block: str) -> None:
        state = row["blocks"][block]
        try:
            parameters = {key: value for key, value in self._parameters(row, block).items() if value is not None}
            result = await self.service.datahub.query(
                row["session_id"],
                f"asset:{row['id']}:{block}",
                BusinessQuery(
                    capability=BLOCK_QUERIES[block],
                    source=row["source"],
                    parameters=parameters,
                ),
            )
            provider_status = result.get("status")
            status = (
                "empty"
                if provider_status == "empty"
                else "partial"
                if provider_status == "partial"
                else "unavailable"
                if provider_status in {"failed", "unavailable", "stale"}
                else "complete"
            )
            state.update(
                status=status,
                dataset=_public_dataset(result),
                sample=result.get("sample", []),
                failure_code=None if status not in {"unavailable", "error"} else "data_unavailable",
            )
            if block == "overview" and result.get("sample"):
                observation = {"status": provider_status, "as_of": result.get("as_of"), **result["sample"][0]}
                self.evaluate_alerts(row["asset"], observation)
        except asyncio.CancelledError:
            state.update(status="unavailable", failure_code="cancelled")
            raise
        except (StoreError, ValueError, TypeError, KeyError) as exc:
            state.update(status="error", failure_code="query_failed")
            log.warning(
                "asset_observation_block_failed",
                block=block,
                error_type=type(exc).__name__,
            )

    async def _run(self, row: dict) -> None:
        try:
            await asyncio.gather(*(self._run_block(row, block) for block in row["blocks"]))
            states = {block["status"] for block in row["blocks"].values()}
            if states <= {"complete", "empty"}:
                row["status"] = "complete"
            elif states <= {"error", "unavailable"}:
                row["status"] = "failed"
            else:
                row["status"] = "partial"
            row["updated_at"] = time.time()
            self.store.save()
            self.service.notify()
            log.info("asset_observation_completed", status=row["status"])
        except asyncio.CancelledError:
            row.update(status="cancelled", updated_at=time.time())
            self.store.save()
            raise

    def observation(self, observation_id: str) -> dict:
        row = _uuid_record(self.store.data["asset_observations"], observation_id, "资产观察")
        return self.public_observation(row)

    def list_observations(self) -> list[dict]:
        rows = [self.public_observation(row) for row in self.store.data["asset_observations"].values()]
        return sorted(rows, key=lambda row: row["updated_at"], reverse=True)

    def create_watchlist(self, name: str, polling_minutes: int | None) -> dict:
        row = {
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
        row = {"id": str(uuid4()), **item, "asset": item["asset"].upper(), "created_at": time.time()}
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
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
