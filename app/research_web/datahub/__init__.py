"""One in-process DataHub shared by read-only Web and approved native tools."""

import asyncio
import hashlib
import hmac
import json
import os
import re
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.observability import get_logger

from ..store import StoreError
from . import providers
from .broker import resolve
from .catalog import build_catalog, catalog_detail
from .connection_center import build_connection_center
from .connections import (
    SUPPORTED_CONFIGURATION_SOURCES,
    MySQLConnectionStore,
    canonical_source_id,
)
from .contracts import BusinessQuery, Query
from .probes import probe_source
from .security import load_control
from .snapshots import Snapshots

log = get_logger(__name__)
__all__ = ["BusinessQuery", "DataHub", "Query", "load_control"]
PROBE_TIMEOUT = 15

SAMPLE_BUDGET_BYTES = 32768
SAMPLE_STRING_LIMIT = 16384


def _trim_sample_strings(value: Any, limit: int = SAMPLE_STRING_LIMIT) -> Any:
    if isinstance(value, str):
        return (
            value if len(value) <= limit else value[:limit] + "…（样例截断，完整内容见 rows.json）"
        )
    if isinstance(value, dict):
        return {key: _trim_sample_strings(item, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [_trim_sample_strings(item, limit) for item in value]
    return value


def bounded_sample(rows: list[dict], budget: int = SAMPLE_BUDGET_BYTES) -> list[dict]:
    """Bound the model-facing sample; complete rows stay in rows.json."""

    if budget < 256:
        raise ValueError("sample_budget_invalid")
    kept: list[dict] = []
    for row in rows[:3]:
        candidate = row
        encoded = len(json.dumps(candidate, ensure_ascii=False, default=str).encode())
        if encoded > budget:
            candidate = _trim_sample_strings(row, max(2048, budget // 4))
            encoded = len(json.dumps(candidate, ensure_ascii=False, default=str).encode())
        if encoded > budget:
            candidate = {"truncated": True, "note": "单行样例超过大小上限；完整内容见 rows.json"}
            encoded = len(json.dumps(candidate, ensure_ascii=False).encode())
        if len(json.dumps([*kept, candidate], ensure_ascii=False, default=str).encode()) > budget:
            break
        kept.append(candidate)
    return kept


class DataHub:
    def __init__(
        self,
        store,
        *,
        transport=None,
        url=None,
        probe_runner=None,
        probe_ttl_seconds=300,
        max_retained_probes=128,
        monotonic_clock=time.monotonic,
        admission=None,
    ):
        self.store = store
        self.snapshots = Snapshots(store)
        self.connections = MySQLConnectionStore(store.root)
        self.control = load_control(store.root, url)
        self.transport = transport
        self.probe_runner = probe_runner or probe_source
        self.tasks: dict[tuple[str, str], asyncio.Task] = {}
        self.probe_tasks: dict[str, asyncio.Task] = {}
        self.directory_tasks: set[asyncio.Task] = set()
        self.probes: dict[str, dict] = {}
        self.probe_keys: dict[tuple[str, str], str] = {}
        self._probe_waiters: dict[str, int] = {}
        self._probe_completion_order: dict[str, int] = {}
        self._probe_completion_counter = 0
        self.probe_ttl_seconds = max(0.01, float(probe_ttl_seconds))
        self.max_retained_probes = max(1, int(max_retained_probes))
        self._monotonic = monotonic_clock
        self.cache_hits: dict[tuple[str, str], bool] = {}
        self.closed = False
        self.admission = admission

    def authenticate(self, value):
        return (
            isinstance(value, str)
            and value.isascii()
            and hmac.compare_digest(value, self.control["token"])
        )

    def _latest_probes(self):
        self._prune_probes()
        latest: dict[str, dict] = {}
        for probe in self.probes.values():
            if probe.get("status") != "completed":
                continue
            if probe.get("configuration_digest") != self.source_configuration_digest(
                probe["source_id"]
            ):
                continue
            current = latest.get(probe["source_id"])
            if current is None or probe["completed_at"] > current["completed_at"]:
                latest[probe["source_id"]] = probe
        return latest

    def catalog(self):
        return build_catalog(
            probes=self._latest_probes(), connection_statuses=self.connections.statuses()
        )

    def connection_center(self):
        return build_connection_center(self.catalog(), self.connections)

    def directory_fingerprint(self) -> str:
        """Reauthorize the account's explicit Tinysoft stock search without a session."""
        if self.closed:
            raise StoreError("资产目录服务已关闭", "asset_directory_closed", 503)
        query = BusinessQuery(
            capability="search_assets",
            source="tinysoft",
            allow_fallback=False,
            parameters={"query": "", "asset_type": "stock"},
        )
        resolution = resolve(
            query, probes=self._latest_probes(), connection_statuses=self.connections.statuses()
        )
        if resolution.provider_id != "tinysoft":
            raise StoreError("资产目录来源不可用", "asset_directory_unauthorized", 409)
        return self.source_configuration_digest("tinysoft")

    async def asset_directory(self) -> dict:
        """Load authorized directory data only; never create a research session."""
        from .providers_cjpy import fetch_directory

        revision = self.directory_fingerprint()
        task = asyncio.current_task()
        if task is not None:
            self.directory_tasks.add(task)
        try:
            token = await asyncio.to_thread(self.connections.read_source_secret, "tinysoft")
            if self.directory_fingerprint() != revision:
                raise StoreError("资产目录配置已变化", "asset_directory_authorization_changed", 409)
            value = await fetch_directory(token=token)
            if self.directory_fingerprint() != revision:
                raise StoreError("资产目录配置已变化", "asset_directory_authorization_changed", 409)
            return value
        except Exception as exc:
            log.warning("datahub_asset_directory_failed", error_type=type(exc).__name__)
            raise
        finally:
            if task is not None:
                self.directory_tasks.discard(task)

    def source_configuration_digest(self, source_id: str) -> str:
        """Return a canonical digest of safe configuration metadata only."""

        private = canonical_source_id(source_id) in SUPPORTED_CONFIGURATION_SOURCES
        semantics: dict[str, str] = {}
        if source_id == "akshare":
            from .providers_akshare import SEMANTICS_REVISION

            semantics["provider_semantics_revision"] = SEMANTICS_REVISION
        elif source_id == "tinysoft":
            from .adjustment_contract import CONTRACT_VERSION, DEFINITION_SHA256

            semantics.update(
                adjustment_contract_version=CONTRACT_VERSION,
                adjustment_definition_sha256=DEFINITION_SHA256,
            )
        payload = json.dumps(
            {
                "status": (
                    self.connections.source_status(source_id)
                    if private
                    else {"source_id": source_id}
                ),
                "revision": self.connections.configuration_revision(source_id),
                "namespace": self.connections.credential_service,
                **semantics,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def catalog_capability(self, capability_id):
        return catalog_detail(
            "capability",
            capability_id,
            probes=self._latest_probes(),
            connection_statuses=self.connections.statuses(),
        )

    def catalog_source(self, source_id):
        return catalog_detail(
            "source",
            source_id,
            probes=self._latest_probes(),
            connection_statuses=self.connections.statuses(),
        )

    def start_probe(self, source_id, idempotency_key):
        self._prune_probes()
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
            "configuration_digest": self.source_configuration_digest(source_id),
            "status": "checking",
            "health": "checking",
            "failure_code": None,
            "duration_ms": None,
            "last_checked_at": None,
            "completed_at": None,
            "retained_until": None,
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
            source = await asyncio.to_thread(self.catalog_source, source_id)
            state = source["readiness"]["integration_state"]
            if source_id in {"wind", "ifind"}:
                configuration = await asyncio.to_thread(
                    self.connections.source_configuration, source_id
                )
                if configuration is None:
                    outcome = {"health": "unavailable", "failure_code": state}
                else:
                    outcome = await asyncio.wait_for(
                        self.probe_runner(
                            source_id,
                            configuration.model_dump(),
                            self.connections.read_source_secret,
                        ),
                        timeout=PROBE_TIMEOUT,
                    )
            elif state != "ready":
                outcome = {"health": "unavailable", "failure_code": state}
            else:
                outcome = await asyncio.wait_for(
                    providers.probe(
                        source_id, transport=self.transport, connections=self.connections
                    ),
                    timeout=PROBE_TIMEOUT,
                )
            checked = datetime.now(UTC).isoformat()
            record.update(
                status="completed",
                health=outcome["health"],
                failure_code=outcome.get("failure_code"),
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                last_checked_at=checked,
                completed_at=checked,
                retained_until=self._monotonic() + self.probe_ttl_seconds,
            )
            log.info("datahub_probe_completed", source=source_id, health=record["health"])
        except asyncio.CancelledError:
            checked = datetime.now(UTC).isoformat()
            record.update(
                status="cancelled",
                health="untested",
                failure_code="probe_cancelled",
                completed_at=checked,
                retained_until=self._monotonic() + self.probe_ttl_seconds,
            )
            raise
        except TimeoutError as exc:
            checked = datetime.now(UTC).isoformat()
            record.update(
                status="completed",
                health="unavailable",
                failure_code="probe_timeout",
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                last_checked_at=checked,
                completed_at=checked,
                retained_until=self._monotonic() + self.probe_ttl_seconds,
            )
            log.warning("datahub_probe_timed_out", source=source_id, error_type=type(exc).__name__)
        except Exception as exc:  # noqa: BLE001 - probe boundary must close vendor errors.
            checked = datetime.now(UTC).isoformat()
            record.update(
                status="completed",
                health="unavailable",
                failure_code="probe_failed",
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                last_checked_at=checked,
                completed_at=checked,
                retained_until=self._monotonic() + self.probe_ttl_seconds,
            )
            log.warning("datahub_probe_failed", source=source_id, error_type=type(exc).__name__)
        finally:
            if record.get("status") in {"completed", "cancelled", "failed"}:
                self._mark_probe_terminal(probe_id)
            self.probe_tasks.pop(probe_id, None)
            self._prune_probes()

    def _mark_probe_terminal(self, probe_id: str) -> None:
        self._probe_completion_counter += 1
        self._probe_completion_order[probe_id] = self._probe_completion_counter

    def _prune_probes(self) -> None:
        now = self._monotonic()
        protected_ids = {probe_id for probe_id, count in self._probe_waiters.items() if count > 0}
        terminal_ids = sorted(
            (
                probe_id
                for probe_id, probe in self.probes.items()
                if probe.get("status") in {"completed", "cancelled", "failed"}
            ),
            key=lambda probe_id: self._probe_completion_order.get(probe_id, 0),
        )
        remove_ids = {
            probe_id
            for probe_id in terminal_ids
            if probe_id not in protected_ids
            if self.probes[probe_id].get("retained_until", now) <= now
        }
        retained_ids = [probe_id for probe_id in terminal_ids if probe_id not in remove_ids]
        excess = len(retained_ids) - self.max_retained_probes
        for probe_id in retained_ids:
            if excess <= 0:
                break
            if probe_id in protected_ids:
                continue
            remove_ids.add(probe_id)
            excess -= 1
        for probe_id in remove_ids:
            self.probes.pop(probe_id, None)
            self.probe_tasks.pop(probe_id, None)
            self._probe_completion_order.pop(probe_id, None)
        for key, probe_id in list(self.probe_keys.items()):
            if probe_id in remove_ids or probe_id not in self.probes:
                self.probe_keys.pop(key, None)

    def probe(self, probe_id):
        self._prune_probes()
        try:
            return self.probes[probe_id]
        except KeyError as exc:
            raise StoreError("检测记录不存在") from exc

    async def run_probe(self, source_id: str, idempotency_key: str) -> dict:
        """Start and await one legacy-compatible probe for coordinator callers."""

        record = self.start_probe(source_id, idempotency_key)
        probe_id = record["id"]
        self._probe_waiters[probe_id] = self._probe_waiters.get(probe_id, 0) + 1
        try:
            task = self.probe_tasks.get(probe_id)
            if task is not None:
                await asyncio.shield(task)
            return self.probe(probe_id)
        finally:
            remaining = self._probe_waiters.get(probe_id, 1) - 1
            if remaining > 0:
                self._probe_waiters[probe_id] = remaining
            else:
                self._probe_waiters.pop(probe_id, None)
            self._prune_probes()

    def restore_probe_statuses(self, probes: dict[str, dict]) -> None:
        """Hydrate safe persisted evidence without reusing credentials or payload data."""

        for source_id, value in probes.items():
            if self.catalog_source(source_id) is None or value.get("status") != "completed":
                continue
            probe_id = f"restored:{source_id}"
            self.probes[probe_id] = {
                "id": probe_id,
                "source_id": source_id,
                "status": "completed",
                "health": value.get("health", "untested"),
                "failure_code": value.get("failure_code"),
                "duration_ms": value.get("duration_ms"),
                "last_checked_at": value.get("last_checked_at"),
                "completed_at": value.get("completed_at") or value.get("last_checked_at"),
                "retained_until": self._monotonic() + self.probe_ttl_seconds,
            }
            self._mark_probe_terminal(probe_id)
        self._prune_probes()

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
            "asset_history",
        }
        summaries = []
        for item in self.list(sid):
            summary = {key: value for key, value in item.items() if key in keys}
            history = summary.get("asset_history")
            if isinstance(history, dict):
                summary["asset_history"] = {
                    key: value
                    for key, value in history.items()
                    if key not in {"raw_rows", "factors", "inputs", "configuration_digest"}
                }
            summaries.append(summary)
        return summaries

    def copy_for_upgrade(self, old_sid, new_sid):
        return self.snapshots.copy_for_upgrade(old_sid, new_sid)

    def copy_selected(self, old_sid, new_sid, dataset_ids):
        return self.snapshots.copy_selected(old_sid, new_sid, dataset_ids)

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
            "sample": bounded_sample(self.rows(sid, manifest["dataset_id"], 0, 3)["items"]),
            "cache_hit": cache_hit,
        }

    def _authorize_query(
        self, sid, query, *, provider=None, cached=False, authorization_fingerprint=None
    ):
        if not isinstance(query, BusinessQuery):
            return None
        checked = query
        if cached:
            if not isinstance(provider, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", provider):
                raise StoreError("缓存来源无法确认", "data_cache_source_unknown", 409)
            checked = query.model_copy(update={"source": provider, "allow_fallback": False})
            if authorization_fingerprint != self.source_configuration_digest(provider):
                raise StoreError("缓存授权版本已变化", "data_cache_authorization_changed", 409)
        resolution = resolve(
            checked, probes=self._latest_probes(), connection_statuses=self.connections.statuses()
        )
        if self.admission is not None:
            self.admission(sid, checked, resolution)
        return resolution

    async def query(self, sid, call_id, query: Query | BusinessQuery):
        self.store.session(sid)
        if self.closed or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,256}", call_id):
            raise StoreError("资料服务关闭或调用标识非法")
        # A receipt/cache is historical evidence, never current authorization.
        self._authorize_query(sid, query)
        key = (sid, call_id)
        receipt = self.snapshots.receipt(sid, call_id)
        fingerprint = query.fingerprint(include_refresh=True)
        if receipt:
            if receipt.get("fingerprint") not in (None, fingerprint):
                raise StoreError("同一资料调用标识不能用于不同参数")
            if receipt["status"] == "completed":
                manifest = self.detail(sid, receipt["dataset_id"])
                if manifest.get("snapshot_kind") == "asset_history":
                    raise StoreError(
                        "规范历史不能替代普通供应商查询缓存", "data_cache_not_equivalent", 409
                    )
                if isinstance(query, BusinessQuery):
                    self._authorize_query(
                        sid,
                        query,
                        provider=manifest.get("provider"),
                        cached=True,
                        authorization_fingerprint=manifest.get("authorization_fingerprint"),
                    )
                return self.short(sid, manifest, cache_hit=receipt["cache_hit"])
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

    async def collect_report_weekly(
        self,
        sid,
        call_id,
        cutoff,
        *,
        provider=None,
        verification_receipts=None,
        run_root=None,
        manifest=None,
        prepare_excel=None,
    ):
        """Private Host-only collection with ordinary ownership and raw snapshots.

        No HTTP route or DSH Tool accepts this request. Comparison inputs are
        existing hash-verified datasets of this session, never model booleans.
        """
        from ..report_workflows.weekly_data import (
            adopt_verified_groups,
            assess_weekly_snapshot,
            build_equivalence_proof,
            build_weekly_data_contract,
            load_weekly_mapping,
            sample_snapshot,
            weekly_code_identity,
        )
        from .broker import resolve_report_weekly
        from .providers_wind_api import WindAPIQuery, WindClientAPIProvider, wait_for_idle
        from .security import atomic_json, directory, read_file

        self.store.session(sid)
        if self.closed or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,256}", call_id):
            raise StoreError("资料服务关闭或调用标识非法")
        contract = build_weekly_data_contract(cutoff)
        query = WindAPIQuery(
            kind="weekly",
            start_date=contract["window_start"],
            end_date=contract["period_end"],
            cutoff=contract["cutoff"],
        )

        report_contract_selected = False

        def authorize():
            resolution = resolve_report_weekly(
                query,
                probes=self._latest_probes(),
                connection_statuses=self.connections.statuses(),
                report_contract_selected=report_contract_selected,
            )
            if self.admission is not None:
                self.admission(sid, query, resolution)
            return self.source_configuration_digest("wind")

        workflow_manifest = manifest
        source_contract = None
        source_contract_sha = None
        if run_root is not None or manifest is not None:
            if run_root is None or manifest is None:
                raise StoreError("周报资源上下文不完整", "weekly_resource_invalid", 409)
            from ..report_workflows.weekly_sources import load_run_source_contract

            self._report_weekly_run_context(sid, run_root, workflow_manifest)
            source_contract, source_contract_sha = load_run_source_contract(
                run_root, workflow_manifest
            )
            declared = (
                workflow_manifest.model_dump(mode="json")
                if hasattr(workflow_manifest, "model_dump")
                else workflow_manifest
            )
            policy = declared.get("weekly_production")
            report_contract_selected = (
                isinstance(policy, dict) and policy.get("policy_id") == "huaan-etf-weekly-v1"
            )
        configuration = authorize()
        receipt = self.snapshots.receipt(sid, call_id)
        fingerprint = query.fingerprint(include_refresh=True)
        if receipt:
            if receipt.get("fingerprint") != fingerprint:
                raise StoreError("同一周报取数标识不能用于不同报告期", "weekly_call_conflict", 409)
            if receipt.get("status") == "completed":
                manifest = self.detail(sid, receipt["dataset_id"])
                if manifest.get("authorization_fingerprint") != configuration:
                    raise StoreError("周报来源授权已变化", "data_cache_authorization_changed", 409)
                snapshot = self.rows(sid, manifest["dataset_id"], 0, 1)["items"][0]
                return {
                    "contract": contract,
                    "snapshot": snapshot,
                    "assessment": assess_weekly_snapshot(snapshot, contract),
                    "datasets": [manifest],
                }
            if (sid, call_id) in self.tasks:
                return await asyncio.shield(self.tasks[(sid, call_id)])
            raise StoreError("周报资料受理状态未知，不自动重发", "weekly_call_unknown", 409)

        async def collect():
            try:
                baseline = economic = None
                if verification_receipts is not None and not isinstance(
                    verification_receipts, dict
                ):
                    raise StoreError("周报比较材料引用无效", "weekly_comparison_invalid", 400)
                references = dict(verification_receipts or {})
                if set(references) - {
                    "baseline_dataset_id",
                    "economic_calendar_dataset_id",
                }:
                    raise StoreError("周报比较材料引用无效", "weekly_comparison_invalid", 400)
                for key, expected_source in (
                    ("baseline_dataset_id", "wind_excel"),
                    ("economic_calendar_dataset_id", "wind"),
                ):
                    if key not in references:
                        continue
                    dataset_manifest = self.detail(sid, references[key])
                    if dataset_manifest.get("provider") != expected_source:
                        raise StoreError("周报比较材料来源不符", "weekly_comparison_invalid", 409)
                    rows = self.rows(sid, references[key], 0, 1)["items"]
                    if len(rows) != 1:
                        raise StoreError("周报比较材料不完整", "weekly_comparison_invalid", 409)
                    if key == "baseline_dataset_id":
                        baseline = rows[0]
                    else:
                        economic = rows[0].get("economic_calendar")
                adapter = provider or WindClientAPIProvider(
                    calendar_contracts=source_contract["calendars"] if source_contract else None,
                    economic_contract=(
                        source_contract["economic_calendar"] if source_contract else None
                    ),
                )
                readiness = adapter.readiness()
                proof_identity = {
                    "configuration_sha256": configuration,
                    "source_contract_sha256": source_contract_sha,
                    "sdk_identity_sha256": readiness.get("sdk_identity_sha256"),
                    **weekly_code_identity(),
                }
                proof_key = hashlib.sha256(
                    json.dumps(proof_identity, sort_keys=True).encode()
                ).hexdigest()
                proof = None
                with directory(
                    self.store.root,
                    (".control", "report-weekly-equivalence"),
                    create=True,
                    private=True,
                ) as control:
                    if proof_key + ".json" in os.listdir(control):
                        proof = json.loads(read_file(control, proof_key + ".json", private=True))
                if readiness.get("dependency_ready") is not True:
                    snapshot = sample_snapshot(contract)
                    code = readiness.get("code") or "wind_api_dependency_missing"
                    snapshot["limitations"] = [code]
                    collected = {
                        "contract": contract,
                        "snapshot": snapshot,
                        "assessment": assess_weekly_snapshot(snapshot, contract),
                    }
                    collected["assessment"]["issues"].append(code)
                else:
                    collected = await adapter.collect(
                        contract, baseline_snapshot=baseline, economic_calendar=economic
                    )
                snapshot = collected["snapshot"]
                snapshot.update(proof_identity)
                if authorize() != configuration:
                    raise StoreError(
                        "取数期间周报来源授权变化", "data_cache_authorization_changed", 409
                    )
                # Verify all current API inputs before touching Office. The sole
                # missing prerequisite may be first-source equivalence, never
                # an SDK/login/calendar/field/data failure hidden by calibration.
                remaining = set(collected["assessment"]["issues"]) - {
                    "weekly_api_equivalence_unverified"
                }
                all_groups = {item["group"] for item in load_weekly_mapping()["series"]}
                needs_excel = proof is None or set(proof.get("groups", [])) != all_groups
                if (
                    needs_excel
                    and baseline is None
                    and run_root is not None
                    and readiness.get("dependency_ready") is True
                    and source_contract is not None
                    and not remaining
                ):
                    if prepare_excel is None:
                        raise StoreError(
                            "首次同源校准需要受控底稿刷新", "weekly_calibration_required", 409
                        )
                    await prepare_excel()
                    if authorize() != configuration:
                        raise StoreError(
                            "校准期间来源授权变化", "data_cache_authorization_changed", 409
                        )
                    registered = self.register_report_weekly_inputs(
                        sid,
                        f"{call_id}.excel",
                        cutoff,
                        run_root=run_root,
                        manifest=workflow_manifest,
                    )
                    baseline = self.rows(sid, registered["baseline_dataset_id"], 0, 1)["items"][0]
                    snapshot["equivalence_baseline"] = baseline
                if baseline is not None and all(
                    isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
                    for key, value in proof_identity.items()
                    if key != "adapter_revision"
                ):
                    try:
                        candidate = build_equivalence_proof(snapshot, baseline, **proof_identity)
                    except ValueError:
                        candidate = None
                    if candidate is not None and (
                        proof is None or set(proof.get("groups", [])) <= set(candidate["groups"])
                    ):
                        proof = candidate
                        with directory(
                            self.store.root,
                            (".control", "report-weekly-equivalence"),
                            create=True,
                            private=True,
                        ) as control:
                            atomic_json(control, proof_key + ".json", proof)
                if proof is not None:
                    snapshot = adopt_verified_groups(snapshot, baseline, proof)
                    collected["snapshot"] = snapshot
                collected["assessment"] = assess_weekly_snapshot(snapshot, contract)
                if authorize() != configuration:
                    raise StoreError(
                        "取数期间周报来源授权变化", "data_cache_authorization_changed", 409
                    )
                raw = json.dumps(
                    snapshot,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
                if len(raw) > 16 * 1024 * 1024:
                    raise StoreError("周报资料超过大小上限", "weekly_snapshot_too_large", 413)
                result = providers.Result(
                    rows=[snapshot],
                    raw=[raw],
                    source_url="wind-client-api",
                    status=(
                        "complete" if collected["assessment"]["status"] == "passed" else "partial"
                    ),
                    pages_fetched=1,
                    provider_total=1,
                    pagination_complete=True,
                    provider_id="wind_client_api",
                    as_of=contract["period_end"],
                    metadata={
                        "snapshot_kind": "report_weekly",
                        "mapping_sha256": contract["mapping_sha256"],
                        "contract_sha256": contract["contract_sha256"],
                        "assessment": collected["assessment"],
                    },
                    limitations=snapshot.get("limitations", []),
                )
                published_manifest = self.snapshots.publish(
                    sid, query, result, request_query=query, authorization_fingerprint=configuration
                )
                self.snapshots.receipt(
                    sid,
                    call_id,
                    {
                        "status": "completed",
                        "fingerprint": fingerprint,
                        "dataset_id": published_manifest["dataset_id"],
                        "cache_hit": False,
                    },
                )
                log.info(
                    "datahub_weekly_collected",
                    session_id=sid,
                    status=collected["assessment"]["status"],
                )
                return {**collected, "datasets": [published_manifest]}
            except asyncio.CancelledError:
                await wait_for_idle()
                self.snapshots.receipt(
                    sid, call_id, {"status": "cancelled", "fingerprint": fingerprint}
                )
                raise
            except Exception as exc:  # Vendor text never reaches logs.
                self.snapshots.receipt(
                    sid, call_id, {"status": "failed", "fingerprint": fingerprint}
                )
                log.warning("datahub_weekly_failed", error_type=type(exc).__name__)
                raise

        self.snapshots.receipt(sid, call_id, {"status": "pending", "fingerprint": fingerprint})
        task = asyncio.create_task(collect(), name="datahub-weekly")
        self.tasks[(sid, call_id)] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self.tasks.pop((sid, call_id), None)

    def _report_weekly_run_context(self, sid, run_root, manifest):
        """Bind private source resources to the exact owned report Run."""
        from pathlib import Path

        row = self.store.session(sid)
        binding = row.get("report_workflow", {})
        value = manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest
        root = Path(run_root)
        expected = self.store.root / "report-workflows" / "runs" / str(binding.get("run_id", ""))
        if (
            binding.get("workflow_id") != "huaan-etf-weekly"
            or binding.get("version") != value.get("version")
            or value.get("workflow_id") != binding.get("workflow_id")
            or root.is_symlink()
            or root.resolve() != expected.resolve()
        ):
            raise StoreError("周报资源不属于当前运行", "weekly_resource_invalid", 409)

    def register_report_weekly_inputs(self, sid, call_id, cutoff, *, run_root, manifest):
        """Register actual Run Excel bytes for first calibration, never pass flags."""
        from ..report_workflows.weekly_data import build_weekly_data_contract
        from ..report_workflows.weekly_sources import capture_excel_comparison
        from .providers_wind_api import WindAPIQuery

        self._report_weekly_run_context(sid, run_root, manifest)
        contract = build_weekly_data_contract(cutoff)
        baseline = capture_excel_comparison(run_root, manifest, contract)
        query = WindAPIQuery(
            kind="weekly",
            start_date=contract["window_start"],
            end_date=contract["period_end"],
            cutoff=contract["cutoff"],
        )
        raw = json.dumps(
            baseline, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        fingerprint = hashlib.sha256(raw).hexdigest()
        receipt = self.snapshots.receipt(sid, call_id)
        if receipt:
            if receipt.get("fingerprint") != fingerprint or receipt.get("status") != "completed":
                raise StoreError("Excel 对照材料受理状态冲突", "weekly_comparison_invalid", 409)
            self.detail(sid, receipt["dataset_id"])
            return {"baseline_dataset_id": receipt["dataset_id"]}
        result = providers.Result(
            rows=[baseline],
            raw=[raw],
            source_url="owned-report-run-excel",
            status="snapshot",
            provider_id="wind_excel",
            pages_fetched=1,
            provider_total=1,
            pagination_complete=True,
            as_of=contract["period_end"],
        )
        saved = self.snapshots.publish(
            sid,
            query,
            result,
            request_query=query,
            authorization_fingerprint=self.source_configuration_digest("wind"),
        )
        self.snapshots.receipt(
            sid,
            call_id,
            {
                "status": "completed",
                "fingerprint": fingerprint,
                "dataset_id": saved["dataset_id"],
                "cache_hit": False,
            },
        )
        log.info("datahub_weekly_excel_registered", session_id=sid)
        return {"baseline_dataset_id": saved["dataset_id"]}

    async def _query(self, sid, call_id, query):
        fingerprint = query.fingerprint(include_refresh=True)
        try:
            resolution = self._authorize_query(sid, query)
            if not query.refresh:
                for candidate in self.list(sid):
                    age = (
                        datetime.now(UTC) - datetime.fromisoformat(candidate["retrieved_at"])
                    ).total_seconds()
                    if (
                        candidate["query_fingerprint"] == query.fingerprint()
                        and candidate.get("snapshot_kind") != "asset_history"
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
                        if isinstance(query, BusinessQuery):
                            try:
                                self._authorize_query(
                                    sid,
                                    query,
                                    provider=candidate.get("provider"),
                                    cached=True,
                                    authorization_fingerprint=candidate.get(
                                        "authorization_fingerprint"
                                    ),
                                )
                            except StoreError:
                                log.warning("datahub_cache_authorization_changed")
                                continue
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
            if isinstance(query, BusinessQuery):
                provider_query = resolution.query
                source_label = resolution.provider_id
            else:
                provider_query = query
                source_label = query.source
            log.info("datahub_query_started", session_id=sid, source=source_label)
            authorization_fingerprint = (
                self.source_configuration_digest(source_label) if resolution else None
            )
            result = await providers.fetch(
                provider_query, transport=self.transport, connections=self.connections
            )
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
                authorization_fingerprint=authorization_fingerprint,
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
            # The task cancellation is only a request. A synchronous vendor call
            # keeps capacity until its real Future has completed.
            if getattr(query, "source", None) == "tinysoft":
                from .providers_cjpy import wait_for_idle

                await wait_for_idle()
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
        if self.directory_tasks:
            await asyncio.gather(*self.directory_tasks, return_exceptions=True)
        tasks = [*self.tasks.values(), *self.probe_tasks.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        from .providers_wind_api import wait_for_idle

        await wait_for_idle()
        self.tasks.clear()
        self.probe_tasks.clear()
