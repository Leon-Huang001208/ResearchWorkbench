"""Durable account-owned history jobs over the existing DataHub and snapshots."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import re
import time
from datetime import datetime
from uuid import uuid4
from weakref import WeakValueDictionary
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .asset_history import (
    ACTIVE,
    FLOOR,
    HISTORY_VERSION,
    adjust_rows,
    canonical_asset,
    chunks_near_first,
    factor_map,
    fail,
    iso_date,
    merge_rows,
    normalize_rows,
    shift_years,
)
from .datahub.adjustment_contract import CONTRACT_VERSION, DEFINITION_SHA256
from .datahub.contracts import BusinessQuery
from .datahub.providers import Result
from .datahub.security import directory, json_bytes, read_file, write_new

log = get_logger(__name__)
_OWNERS: WeakValueDictionary[tuple[str, str], asyncio.Task] = WeakValueDictionary()
REBUILD_REQUIRED = {
    "history_factor_version_changed",
    "history_overlap_conflict",
    "history_before_listing",
    "history_authorization_changed",
    "history_cache_version_changed",
    "history_cache_hash_invalid",
    "history_input_hash_invalid",
    "history_factor_conflict",
}


def digest(value) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


class HistoryJobs:
    def __init__(self, workspace):
        self.workspace = workspace
        self.service = workspace.service
        self.store = workspace.store
        self.tasks: dict[str, asyncio.Task] = {}
        self.closed = False
        recovered = False
        for row in self.store.data["asset_history_jobs"].values():
            owner = _OWNERS.get((str(self.store.root), row["id"]))
            if row.get("state") in ACTIVE and (owner is None or owner.done()):
                row.update(
                    state="interrupted", failure_code="history_interrupted", updated_at=time.time()
                )
                recovered = True
        if recovered:
            self.store.save()
            log.warning("asset_history_interrupted_recovered")

    @property
    def hub(self):
        return self.service.datahub

    def _observation(self, oid: str, *, include_deleted=False) -> dict:
        row = self.store.data["asset_observations"].get(oid)
        if not row:
            raise fail("history_observation_missing", "资产观察不存在", 404)
        self.store.session(row["session_id"], include_deleted=include_deleted)
        return row

    def _row(self, oid: str, jid: str, *, include_deleted=False) -> dict:
        self._observation(oid, include_deleted=include_deleted)
        row = self.store.data["asset_history_jobs"].get(jid)
        if not row or row.get("observation_id") != oid:
            raise fail("history_job_missing", "历史任务不存在", 404)
        return row

    def public(self, row: dict) -> dict:
        from .asset_workspace import _public_dataset

        return {
            "id": row["id"],
            "observation_id": row["observation_id"],
            "state": row["state"],
            "status": row["state"],
            "scope": row.get("scope"),
            "adjustment": row.get("adjustment"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "progress": copy.deepcopy(row.get("progress", {})),
            "coverage": copy.deepcopy(row.get("coverage", {})),
            "current_dataset": (
                _public_dataset(row["current_dataset"]) if row.get("current_dataset") else None
            ),
            "failure_code": row.get("failure_code"),
            "failure": {"code": row["failure_code"]} if row.get("failure_code") else None,
            "retryable": row["state"] in {"failed", "cancelled", "interrupted"}
            and row.get("failure_code") not in REBUILD_REQUIRED,
            "retry_of": row.get("retry_of"),
            "request_key": row.get("request_key"),
        }

    def current(self, oid: str):
        values = [
            r for r in self.store.data["asset_history_jobs"].values() if r["observation_id"] == oid
        ]
        return self.public(max(values, key=lambda r: r.get("created_at", 0))) if values else None

    def get(self, oid: str, jid: str) -> dict:
        return self.public(self._row(oid, jid))

    def list(self, oid: str) -> list[dict]:
        self._observation(oid)
        return [
            self.public(r)
            for r in sorted(
                self.store.data["asset_history_jobs"].values(),
                key=lambda r: r.get("created_at", 0),
                reverse=True,
            )
            if r["observation_id"] == oid
        ]

    def active(self, oid: str) -> bool:
        return any(
            r["observation_id"] == oid and r["state"] in ACTIVE
            for r in self.store.data["asset_history_jobs"].values()
        )

    def _canonical(self, observation: dict) -> dict | None:
        current = observation.get("blocks", {}).get("history", {}).get("dataset")
        if not current or not current.get("dataset_id"):
            return None
        manifest = self.hub.detail(observation["session_id"], current["dataset_id"])
        history = manifest.get("asset_history")
        if not isinstance(history, dict) or history.get("canonical_version") != HISTORY_VERSION:
            return None
        return manifest

    def _authorize(self, row: dict) -> None:
        query = BusinessQuery(
            capability="market_bars",
            source="tinysoft",
            parameters={
                "asset": row["asset"],
                "asset_type": "stock",
                "frequency": "daily",
                "adjustment": "none",
                "start_date": row["start_date"],
                "end_date": row["end_date"],
            },
        )
        self.hub._authorize_query(row["session_id"], query)
        if row["configuration_digest"] != self.hub.source_configuration_digest("tinysoft"):
            raise fail("history_authorization_changed", "天软授权或配置版本已变化，请重新构建历史")

    async def create(self, oid: str, body, key: str) -> dict:
        observation = self._observation(oid)
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
            raise fail("history_key_invalid", "Idempotency-Key 格式非法", 400)
        payload = body.model_dump()
        if body.as_of is None:
            payload.pop("as_of")
        key_hash = digest([oid, key])
        existing = self.store.data["asset_history_keys"].get(key_hash)
        if existing:
            row = self._row(oid, existing)
            if row["request"] != payload:
                raise fail("history_key_conflict", "同一历史任务标识不能用于不同参数")
            return self.public(row)
        if self.closed:
            raise fail("history_closed", "历史任务已停止受理", 503)
        canonical_asset(observation["asset"], observation["asset_type"])
        if observation.get("request", {}).get("frequency", "daily") != "daily":
            raise fail("history_frequency_unsupported", "历史任务仅支持日线", 400)
        if (
            self.active(oid)
            or observation.get("blocks", {}).get("history", {}).get("status") == "loading"
        ):
            raise fail("history_busy", "历史读取或刷新仍在进行")
        current = observation.get("blocks", {}).get("history", {}).get("dataset")
        canonical = self._canonical(observation) if body.scope == "older" else None
        previous = None
        if body.retry_of:
            previous = self._row(oid, body.retry_of)
            if not self.public(previous)["retryable"] or any(
                previous[k] != payload[k] for k in ("scope", "adjustment")
            ):
                raise fail("history_retry_invalid", "仅可显式重试相同口径的失败或中断任务")
            if body.as_of is not None and body.as_of != previous["requested_as_of"]:
                raise fail("history_retry_invalid", "重试必须保留原复权截止日")
        request = observation.get("request", {})
        end = iso_date(
            body.as_of
            or request.get("section_ranges", {}).get("history", {}).get("end_date")
            or request.get("end_date")
            or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        )
        end_day = datetime.fromisoformat(end).date()
        if (
            body.as_of is not None
            and not FLOOR <= end_day <= datetime.now(ZoneInfo("Asia/Shanghai")).date()
        ):
            raise fail("history_date_invalid", "历史截止日须在1990年至今的范围内", 400)
        start_day = shift_years(end_day, -2) if body.scope == "recent" else FLOOR
        if body.scope == "older":
            if not canonical:
                raise fail("history_canonical_required", "加载更早历史需要已有规范历史")
            h = canonical["asset_history"]
            if h["adjustment"] != body.adjustment:
                raise fail("history_adjustment_conflict", "更早历史须与已有规范历史口径相同")
            end = h["scanned_start"]
            start_day = max(FLOOR, shift_years(datetime.fromisoformat(end).date(), -4))
        if previous:
            start_day = datetime.fromisoformat(previous["start_date"]).date()
            end = previous["end_date"]
            canonical = self._canonical(observation) if body.scope == "older" else None
        jid = str(uuid4())
        row = {
            "id": jid,
            "observation_id": oid,
            "session_id": observation["session_id"],
            "request_key": key,
            "cancel_requested": False,
            "asset": observation["asset"],
            "state": "queued",
            **payload,
            "request": payload,
            "generation": jid,
            "start_date": start_day.isoformat(),
            "end_date": end,
            "requested_as_of": (
                canonical["asset_history"]["requested_as_of"]
                if canonical
                else (previous["requested_as_of"] if previous else end)
            ),
            "configuration_digest": self.hub.source_configuration_digest("tinysoft"),
            "expected_dataset_id": current.get("dataset_id") if current else None,
            "current_dataset": copy.deepcopy(current),
            "base_dataset_id": canonical["dataset_id"] if canonical else None,
            "chunks": copy.deepcopy(previous.get("chunks", [])) if previous else [],
            "progress": {"chunks_completed": 0, "chunks_total": 0, "rows": 0},
            "coverage": {},
            "failure_code": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._authorize(row)
        self.store.data["asset_history_jobs"][jid] = row
        self.store.data["asset_history_keys"][key_hash] = jid
        old_generation = observation.get("history_generation")
        observation["history_generation"] = jid
        try:
            self.store.save()
        except Exception:
            self.store.data["asset_history_jobs"].pop(jid, None)
            self.store.data["asset_history_keys"].pop(key_hash, None)
            if old_generation is None:
                observation.pop("history_generation", None)
            else:
                observation["history_generation"] = old_generation
            log.error("asset_history_admission_save_failed")
            raise
        task = asyncio.create_task(self._run(row), name="asset-history-job")
        self.tasks[jid] = task
        _OWNERS[(str(self.store.root), jid)] = task

        def completed(done):
            self.tasks.pop(jid, None)
            if done.cancelled() and row["state"] in ACTIVE:
                self._save(row, state="cancelled", failure_code="history_cancelled")

        task.add_done_callback(completed)
        log.info("asset_history_admitted", job_id=jid, scope=row["scope"])
        return self.public(row)

    def _save(self, row: dict, **updates) -> None:
        before = copy.deepcopy(row)
        row.update(**updates, updated_at=time.time())
        try:
            self.store.save()
        except Exception:
            row.clear()
            row.update(before)
            log.error("asset_history_state_save_failed")
            raise
        self.service.notify()

    async def _query(self, row: dict, capability: str, parameters: dict, purpose: str) -> dict:
        if row["state"] in {"cancelling", "draining"}:
            raise asyncio.CancelledError
        self._authorize(row)
        call_id = f"history:{row['id']}:{purpose}:{uuid4()}"
        row["child_call_id"] = call_id
        query = BusinessQuery(
            capability=capability, source="tinysoft", parameters=parameters, refresh=True
        )
        child = asyncio.create_task(self.hub.query(row["session_id"], call_id, query))
        try:
            result = await asyncio.shield(child)
        except asyncio.CancelledError:
            self._save(row, state="draining")
            # DataHub cancellation waits for the real provider future witness.
            await self.hub.cancel(row["session_id"], call_id)
            await asyncio.gather(child, return_exceptions=True)
            raise
        finally:
            row.pop("child_call_id", None)
        if row["state"] in {"cancelling", "draining"}:
            raise asyncio.CancelledError
        if (
            result["status"] not in {"complete", "empty"}
            or result.get("pagination_complete") is not True
        ):
            from .datahub.providers_cjpy import active_futures, wait_for_idle

            if active_futures():
                self._save(row, state="draining")
                await wait_for_idle()
            if row.get("cancel_requested"):
                raise asyncio.CancelledError
            code = next(
                (
                    x
                    for x in result.get("limitations", [])
                    if re.fullmatch(r"[a-z][a-z0-9_]{1,63}", x)
                ),
                "history_source_incomplete",
            )
            raise fail(code, "历史来源未完整返回；已完成快照保持不变")
        rows = json.loads(
            self.hub.snapshots.read(row["session_id"], result["dataset_id"], "rows.json")
        )
        with directory(
            self.store.root,
            (".control", "snapshots", row["session_id"], result["dataset_id"]),
            private=True,
        ) as fd:
            original_manifest = read_file(fd, "manifest.json", private=True)
        if hashlib.sha256(original_manifest).hexdigest() != result["manifest_sha256"]:
            raise fail("history_input_hash_invalid", "历史来源 manifest 哈希校验失败")
        return {
            "dataset_id": result["dataset_id"],
            "manifest_sha256": result["manifest_sha256"],
            "manifest": json.loads(original_manifest),
            "query": query.model_dump(),
            "rows": rows,
            "rows_sha256": digest(rows),
            "raw_files": copy.deepcopy(result["raw_files"]),
            "provider_metadata": copy.deepcopy(result.get("provider_metadata", {})),
            "configuration_digest": row["configuration_digest"],
        }

    async def _factors(self, row, days, listing, inputs):
        output = {}
        for offset in range(0, len(days), 500):
            batch = days[offset : offset + 500]
            evidence = await self._query(
                row,
                "factor_macro",
                {"series": "adjustment_factors", "assets": [row["asset"]], "dates": batch},
                "factors",
            )
            output.update(factor_map(evidence["rows"], row["asset"], batch, listing))
            inputs.append(evidence)
        return output

    async def _gate(self, row, inputs):
        metadata = await self._query(
            row, "factor_macro", {"series": "adjustment_metadata"}, "definition"
        )
        if len(metadata["rows"]) != 1:
            raise fail("history_definition_invalid", "复权定义无法核验")
        definition = metadata["rows"][0]
        if (
            definition.get("contract_version") != CONTRACT_VERSION
            or definition.get("definition_sha256") != DEFINITION_SHA256
        ):
            raise fail("history_definition_invalid", "复权定义版本或哈希无法核验")
        listing_input = await self._query(
            row, "factor_macro", {"series": "listing_date", "assets": [row["asset"]]}, "listing"
        )
        if len(listing_input["rows"]) != 1 or listing_input["rows"][0].get("asset") != row["asset"]:
            raise fail("history_listing_invalid", "上市日身份无法核验")
        listing = iso_date(listing_input["rows"][0].get("listing_date"))
        proof = await self._query(
            row,
            "market_bars",
            self._raw_parameters(row, {"start_date": listing, "end_date": listing}),
            "listing-proof",
        )
        bars = normalize_rows(
            proof["rows"], row["asset"], {"start_date": listing, "end_date": listing}
        )
        if len(bars) != 1 or bars[0]["date"] != listing:
            raise fail("history_listing_bar_missing", "真实上市首日行情未得到证明")
        inputs.extend([metadata, listing_input, proof])
        factors = await self._factors(row, [listing], listing, inputs)
        if factors[listing] != 1:
            raise fail("history_listing_factor_invalid", "上市首日复权因子须经核验为 1")
        return definition, listing, factors

    def _raw_parameters(self, row, interval):
        return {
            "asset": row["asset"],
            "asset_type": "stock",
            "frequency": "daily",
            "adjustment": "none",
            **interval,
        }

    def _cache_chunk(self, row, interval, evidence, normalized, factors, factor_inputs, definition):
        value = {
            "asset": row["asset"],
            "session_id": row["session_id"],
            "observation_id": row["observation_id"],
            "interval": interval,
            "configuration_digest": row["configuration_digest"],
            "definition_sha256": definition.get("definition_sha256"),
            "evidence": evidence,
            "normalized": normalized,
            "factors": factors,
            "factor_inputs": factor_inputs,
        }
        name = str(uuid4()) + ".json"
        data = json_bytes(value)
        with directory(
            self.store.root, (".control", "asset-history", "chunks"), create=True, private=True
        ) as fd:
            write_new(fd, name, data)
        return {"name": name, "sha256": hashlib.sha256(data).hexdigest(), "interval": interval}

    async def _reuse(self, row, interval, definition, listing):
        for item in row["chunks"]:
            if item["interval"] != interval:
                continue
            with directory(
                self.store.root, (".control", "asset-history", "chunks"), private=True
            ) as fd:
                raw = read_file(fd, item["name"], private=True)
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise fail("history_cache_hash_invalid", "冻结历史输入哈希校验失败")
            value = json.loads(raw)
            self._authorize(row)
            if (
                value["asset"] != row["asset"]
                or value["session_id"] != row["session_id"]
                or value["observation_id"] != row["observation_id"]
                or value["configuration_digest"] != row["configuration_digest"]
                or value["definition_sha256"] != definition.get("definition_sha256")
            ):
                raise fail("history_cache_version_changed", "冻结输入版本已变化，须重建完整历史")
            # Re-read original manifests and hashes, never trust index or cached rows alone.
            for evidence in [value["evidence"], *value["factor_inputs"]]:
                original = self.hub.detail(row["session_id"], evidence["dataset_id"])
                if (
                    original["manifest_sha256"] != evidence["manifest_sha256"]
                    or digest(evidence["rows"]) != evidence["rows_sha256"]
                ):
                    raise fail("history_cache_hash_invalid", "冻结来源证据校验失败")
            if value["factors"]:
                validation_inputs: list[dict] = []
                checked = await self._factors(
                    row, sorted(value["factors"]), listing, validation_inputs
                )
                if checked != value["factors"]:
                    raise fail(
                        "history_factor_version_changed",
                        "冻结复权因子已变化，须以新版本重建完整历史",
                    )
                value["factor_inputs"].extend(validation_inputs)
            return value
        return None

    def _raw_inputs(self, row, inputs):
        output = []
        for evidence in inputs:
            if (
                digest(evidence["manifest"]) != evidence["manifest_sha256"]
                or digest(evidence["rows"]) != evidence["rows_sha256"]
            ):
                raise fail("history_input_hash_invalid", "历史来源 manifest 或行哈希校验失败")
            frozen_raw = []
            with directory(
                self.store.root,
                (".control", "snapshots", row["session_id"], evidence["dataset_id"]),
                private=True,
            ) as fd:
                for item in evidence["raw_files"]:
                    raw = read_file(fd, item["name"], private=True)
                    if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                        raise fail("history_input_hash_invalid", "历史原始输入哈希校验失败")
                    output.append(raw)
                    frozen_raw.append(
                        {
                            "name": f"raw-{len(output):04d}.bin",
                            "sha256": item["sha256"],
                            "size": len(raw),
                        }
                    )
            evidence["frozen_raw_files"] = frozen_raw
        return output

    def _publish(self, row, raw_rows, factors, inputs, scanned, definition, listing, anchor):
        observation = self._observation(row["observation_id"])
        self._authorize(row)
        block = observation.setdefault("blocks", {}).setdefault(
            "history", {"status": "empty", "dataset": None}
        )
        pointer = block.get("dataset")
        if (
            row["state"] != "running"
            or observation.get("history_generation") != row["generation"]
            or (pointer.get("dataset_id") if pointer else None) != row["expected_dataset_id"]
        ):
            raise fail("history_generation_changed", "历史代次或当前快照已变化，未替换原数据")
        adjusted = adjust_rows(raw_rows, factors, row["adjustment"], anchor, listing)
        dates = [r["date"] for r in raw_rows]
        actual = {
            "start_date": min(dates) if dates else None,
            "end_date": max(dates) if dates else None,
        }
        scanned_start = min(i["start_date"] for i in scanned)
        scanned_end = max(i["end_date"] for i in scanned)
        coverage = {
            "complete": scanned_start <= row["effective_start"],
            "actual_range": actual,
            "scanned_ranges": copy.deepcopy(scanned),
            "listing_date": listing,
            "boundary_verified": bool(listing),
            "scanned_start": scanned_start,
            "scanned_end": scanned_end,
            "full_history": scanned_start <= (listing or FLOOR.isoformat()),
            "scope": row["scope"],
        }
        factor_hash = digest(factors) if row["adjustment"] != "none" else None
        history = {
            "canonical_version": HISTORY_VERSION,
            "factor_version": (
                f"{definition['contract_version']}:{factor_hash}" if factor_hash else None
            ),
            "factor_contract_version": definition.get("contract_version"),
            "factor_snapshot_sha256": factor_hash,
            "definition_sha256": definition.get("definition_sha256"),
            "definition": definition,
            "adjustment": row["adjustment"],
            "anchor_date": anchor if row["adjustment"] == "qfq" else listing,
            "requested_as_of": row["requested_as_of"],
            "scanned_start": scanned_start,
            "scanned_end": scanned_end,
            "asset": row["asset"],
            "job_id": row["id"],
            "generation": row["generation"],
            "configuration_digest": row["configuration_digest"],
            "coverage": coverage,
            "raw_rows": raw_rows,
            "factors": factors,
            "inputs": inputs,
        }
        result = Result(
            rows=adjusted,
            raw=self._raw_inputs(row, inputs),
            source_url="https://www.chinajoin.com/",
            status="complete" if adjusted else "empty",
            pagination_complete=True,
            provider_total=len(adjusted),
            provider_id="tinysoft",
            metadata={"adjustment_contract": definition, "factor_snapshot_sha256": factor_hash},
            as_of=anchor,
            fields={
                key: {"type": "number"}
                for key in ("open", "high", "low", "close", "volume", "amount")
            },
            limitations=["复权仅按已核验定义与固定锚点计算；成交量和成交额保留供应商原值。"],
        )
        query = BusinessQuery(
            capability="market_bars",
            source="tinysoft",
            parameters={
                "asset": row["asset"],
                "asset_type": "stock",
                "frequency": "daily",
                "adjustment": row["adjustment"],
                "start_date": scanned_start,
                "end_date": row["requested_as_of"],
            },
        )
        manifest = self.hub.snapshots.publish(
            row["session_id"],
            query,
            result,
            request_query=query,
            authorization_fingerprint=row["configuration_digest"],
            asset_history=history,
        )
        # This commit has no await: generation, authorization and old-pointer CAS
        # were checked immediately before immutable snapshot creation.
        before_block, before_job = copy.deepcopy(block), copy.deepcopy(row)
        previous_status = observation["status"]
        previous_updated = observation.get("updated_at")
        block.update(
            status="complete" if adjusted else "empty",
            dataset=manifest,
            failure_code=None,
            requested_range={"start_date": scanned_start, "end_date": row["requested_as_of"]},
            loaded_at=time.time(),
        )
        row.update(
            expected_dataset_id=manifest["dataset_id"],
            current_dataset=manifest,
            coverage=coverage,
            progress={
                "chunks_completed": len(scanned),
                "chunks_total": row["progress"]["chunks_total"],
                "rows": len(adjusted),
            },
            updated_at=time.time(),
        )
        from .asset_workspace import _observation_status

        observation.update(status=_observation_status(observation), updated_at=time.time())
        try:
            self.store.save()
        except Exception:
            block.clear()
            block.update(before_block)
            row.clear()
            row.update(before_job)
            observation["status"] = previous_status
            observation["updated_at"] = previous_updated
            log.error("asset_history_pointer_save_failed")
            raise
        self.service.notify()
        log.info("asset_history_chunk_published", job_id=row["id"], rows=len(adjusted))

    async def _run(self, row):
        try:
            if row["state"] in {"cancelling", "draining"}:
                raise asyncio.CancelledError
            self._save(row, state="running")
            inputs: list[dict] = []
            raw_rows: list[dict] = []
            factors: dict[str, float] = {}
            scanned: list[dict[str, str]] = []
            definition, listing, gate_factors = {}, None, {}
            if row["adjustment"] != "none":
                definition, listing, gate_factors = await self._gate(row, inputs)
            anchor = None
            if row["base_dataset_id"]:
                base = self.hub.detail(row["session_id"], row["base_dataset_id"])["asset_history"]
                if base["configuration_digest"] != row["configuration_digest"] or base.get(
                    "definition_sha256"
                ) != definition.get("definition_sha256"):
                    raise fail(
                        "history_factor_version_changed",
                        "原规范数据的来源或因子版本已变化，须重新构建完整历史",
                    )
                raw_rows, factors = copy.deepcopy(base["raw_rows"]), copy.deepcopy(base["factors"])
                inputs.extend(copy.deepcopy(base["inputs"]))
                if factors:
                    checked_factors = await self._factors(row, sorted(factors), listing, inputs)
                    if checked_factors != factors:
                        raise fail(
                            "history_factor_version_changed",
                            "原规范复权因子已变化，须以新版本重建完整历史",
                        )
                scanned = copy.deepcopy(base["coverage"]["scanned_ranges"])
                anchor = (
                    base.get("anchor_date")
                    if row["adjustment"] == "qfq"
                    else base["coverage"]["actual_range"]["end_date"]
                )
            factors.update(gate_factors)
            start = max(row["start_date"], listing or row["start_date"])
            if start > row["end_date"]:
                raise fail("history_before_listing", "请求区间早于已核验上市日，原历史数据保持不变")
            row["effective_start"] = start
            plan = chunks_near_first(
                datetime.fromisoformat(start).date(), datetime.fromisoformat(row["end_date"]).date()
            )
            row["progress"]["chunks_total"] = len(plan) + len(scanned)
            for interval in plan:
                cached = await self._reuse(row, interval, definition, listing)
                if cached:
                    evidence, normalized = cached["evidence"], cached["normalized"]
                    chunk_factors, factor_inputs = cached["factors"], cached["factor_inputs"]
                else:
                    evidence = await self._query(
                        row, "market_bars", self._raw_parameters(row, interval), "raw"
                    )
                    normalized = normalize_rows(evidence["rows"], row["asset"], interval)
                    factor_inputs, chunk_factors = [], {}
                    if row["adjustment"] != "none" and normalized:
                        chunk_factors = await self._factors(
                            row, [r["date"] for r in normalized], listing, factor_inputs
                        )
                    cached_item = self._cache_chunk(
                        row,
                        interval,
                        evidence,
                        normalized,
                        chunk_factors,
                        factor_inputs,
                        definition,
                    )
                    row["chunks"].append(cached_item)
                    self.store.save()
                inputs.extend([evidence, *factor_inputs])
                raw_rows = merge_rows(raw_rows, normalized)
                for day, value in chunk_factors.items():
                    if day in factors and factors[day] != value:
                        raise fail(
                            "history_factor_conflict", "同日复权因子冲突，原规范数据保持不变"
                        )
                    factors[day] = value
                if anchor is None and raw_rows:
                    anchor = max(r["date"] for r in raw_rows)
                scanned.append(interval)
                self._publish(row, raw_rows, factors, inputs, scanned, definition, listing, anchor)
                await asyncio.sleep(0)
            self._save(row, state="completed")
        except asyncio.CancelledError:
            self._save(row, state="cancelled", failure_code="history_cancelled")
            log.info("asset_history_cancelled", job_id=row["id"])
        except Exception as exc:  # noqa: BLE001 - every admitted job must settle with a safe code.
            code = getattr(exc, "code", "history_failed")
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", str(code)):
                code = "history_failed"
            self._save(row, state="failed", failure_code=code)
            log.warning(
                "asset_history_failed",
                job_id=row["id"],
                failure_code=code,
                error_type=type(exc).__name__,
            )

    async def cancel(self, oid, jid):
        row = self._row(oid, jid, include_deleted=True)
        if row["state"] not in ACTIVE:
            return self.public(row)
        if row["state"] not in {"cancelling", "draining"}:
            was_queued = row["state"] == "queued"
            self._save(row, state="cancelling", cancel_requested=True)
            task = self.tasks.get(jid) or _OWNERS.get((str(self.store.root), jid))
            if task and not was_queued:
                task.cancel()
        elif not row.get("cancel_requested"):
            self._save(row, cancel_requested=True)
        return self.public(row)

    async def cancel_session(self, sid):
        selected = [
            r
            for r in self.store.data["asset_history_jobs"].values()
            if r.get("session_id") == sid and r["state"] in ACTIVE
        ]
        for row in selected:
            await self.cancel(row["observation_id"], row["id"])
        tasks = [self.tasks[r["id"]] for r in selected if r["id"] in self.tasks]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        self.closed = True
        for jid in list(self.tasks):
            row = self.store.data["asset_history_jobs"][jid]
            if row["state"] in ACTIVE:
                await self.cancel(row["observation_id"], row["id"])
        if self.tasks:
            await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
