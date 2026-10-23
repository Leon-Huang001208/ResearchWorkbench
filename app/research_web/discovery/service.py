"""Per-user finite discovery cache and explicit, at-most-once research admission."""

import asyncio
import copy
import hashlib
import re
import time
from collections import OrderedDict
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException

from core.observability import get_logger

from ..client import RuntimeFailure
from ..datahub.security import json_bytes
from ..intel_routes import read_upstream
from ..projection import content_text
from ..store import StoreError
from .handoff import ensure_session, trusted_context, write_context
from .models import DiscoveryError, Prepare
from .sources import (
    SOURCE,
    SOURCE_LABEL,
    SOURCE_POLICY,
    acquired_materials,
    digest,
    evidence_projection,
    objects,
    projection,
    stamp,
    theme,
)

log = get_logger(__name__)
CACHE_SECONDS = 90
FEED_RETENTION_SECONDS = 1800
MAX_FEEDS = 6
MAX_THEMES = 60
MAX_CACHE_BYTES = 8 * 1024 * 1024
MAX_HANDOFFS = 1000


def now():
    return datetime.now(UTC).isoformat()


class DiscoveryService:
    def __init__(self, research, reader=None):
        self.research = research
        self.store = research.store
        self.reader = reader or read_upstream
        self.lock = asyncio.Lock()
        self._feed_lock = asyncio.Lock()
        self._feeds = OrderedDict()

    def _table(self):
        return self.store.data.get("discovery_handoffs", {})

    def _record(self, identifier):
        try:
            canonical = str(UUID(identifier))
        except (ValueError, TypeError, AttributeError) as exc:
            raise DiscoveryError("研究交接不存在", "discovery_handoff_not_found", 404) from exc
        record = self._table().get(canonical)
        if record is None:
            raise DiscoveryError(
                "研究交接不存在或不属于当前用户", "discovery_handoff_not_found", 404
            )
        return record

    @staticmethod
    def _public(record):
        keys = (
            "handoff_id",
            "session_id",
            "target_mode",
            "state",
            "question",
            "materials",
            "context_file",
            "context_sha256",
            "dataset_id",
            "dataset_manifest_sha256",
            "cutoff",
            "retrieved_at",
            "horizon",
            "theme_id",
            "title",
            "code",
            "prepare_request",
        )
        value = {key: copy.deepcopy(record[key]) for key in keys if key in record}
        if "prepare_request" in value:
            try:
                original = Prepare.model_validate(value["prepare_request"]).model_dump(mode="json")
            except ValueError as exc:
                raise DiscoveryError(
                    "原始确认参数不可核验", "discovery_request_conflict", 409
                ) from exc
            if digest(original) != record.get("request_sha256"):
                raise DiscoveryError("原始确认参数已变化", "discovery_request_conflict", 409)
            value["prepare_request"] = original
        value["execution_started"] = (
            True
            if record["state"] == "running"
            else (
                None
                if record["state"] in {"execution_starting", "execution_outcome_unknown"}
                else False
            )
        )
        return value

    def list_handoffs(self):
        return {
            "items": [
                self._public(row)
                for row in sorted(
                    self._table().values(), key=lambda row: row["retrieved_at"], reverse=True
                )[:100]
            ]
        }

    def _prune_feeds(self):
        cutoff = time.monotonic() - FEED_RETENTION_SECONDS
        for key, entry in list(self._feeds.items()):
            if entry["time"] < cutoff:
                self._feeds.pop(key)
        while (
            len(self._feeds) > MAX_FEEDS
            or sum(entry["size"] for entry in self._feeds.values()) > MAX_CACHE_BYTES
        ):
            self._feeds.popitem(last=False)

    async def feed(self, horizon="medium", refresh=False):
        if horizon not in {"short", "medium", "long"} or not isinstance(refresh, bool):
            raise DiscoveryError("发现期限参数非法", "discovery_horizon_invalid", 422)
        async with self._feed_lock:
            self._prune_feeds()
            previous = next(
                (
                    entry
                    for entry in reversed(self._feeds.values())
                    if entry["public"]["horizon"] == horizon and entry.get("scope") != "tracking"
                ),
                None,
            )
            if previous and not refresh and time.monotonic() - previous["time"] < CACHE_SECONDS:
                return copy.deepcopy(previous["public"])
            acquired = now()
            try:
                payload = await self.reader(
                    "/intelligence", {"impact": "medium_high", "view": "compact"}
                )
                if not isinstance(payload, dict) or not isinstance(payload.get("reading"), list):
                    raise DiscoveryError("资讯结构暂不可核验", "discovery_source_invalid", 502)
                logical = {
                    item["id"]: item.get("name", item["id"])
                    for item in objects(payload.get("logics"))
                    if isinstance(item.get("id"), str)
                }
                challenges = {item.get("id") for item in objects(payload.get("challenges"))}
                themes, proofs, seen = [], {}, set()
                for event in objects(payload["reading"]):
                    item = theme(event, acquired, logical, event.get("id") in challenges)
                    if item is None or item["id"] in seen:
                        continue
                    seen.add(item["id"])
                    themes.append(item)
                    proofs[item["id"]] = projection(event)
                    if len(themes) >= MAX_THEMES:
                        break
                feed_id = str(uuid4())
                daily = (
                    payload.get("daily_reading")
                    if isinstance(payload.get("daily_reading"), dict)
                    else {}
                )
                errors = (
                    [
                        {
                            "code": "upstream_judgment_unverified",
                            "message": "上游精选判断有核验缺口，不能作为已验证结论。",
                        }
                    ]
                    if daily.get("analysis_error")
                    else []
                )
                value = {
                    "feed_id": feed_id,
                    "horizon": horizon,
                    "cutoff": acquired,
                    "retrieved_at": acquired,
                    "source": SOURCE,
                    "source_label": SOURCE_LABEL,
                    "source_as_of": stamp(payload.get("as_of")),
                    "stale": payload.get("cache_stale") is True,
                    "state": "ready" if themes else "empty",
                    "themes": themes,
                    "errors": errors,
                    "source_policy": SOURCE_POLICY,
                    "limitations": [
                        "展示现有第三方资料；打开页面不调用模型。",
                        "期限是研究问题范围，不把来源未知期限补造成事实。",
                        "资料包正文在确认研究时取得；事件摘要无变化不证明链接网页正文未变化。",
                    ],
                    "bounded": len(payload["reading"]) > len(themes),
                }
                encoded = json_bytes({"public": value, "proofs": proofs})
                if len(encoded) > MAX_CACHE_BYTES:
                    raise DiscoveryError("发现资料超过缓存上限", "discovery_source_limit", 502)
                self._feeds[feed_id] = {
                    "public": value,
                    "proofs": proofs,
                    "time": time.monotonic(),
                    "size": len(encoded),
                }
                self._prune_feeds()
                log.info("discovery_feed_read", count=len(themes), stale=value["stale"])
                return copy.deepcopy(value)
            except (
                HTTPException,
                DiscoveryError,
                RuntimeFailure,
                OSError,
                ValueError,
                TimeoutError,
            ) as exc:
                log.warning("discovery_feed_failed", error_type=type(exc).__name__)
                if previous:
                    value = copy.deepcopy(previous["public"])
                    value.update(stale=True, state="stale")
                    value["errors"] = [
                        {
                            "code": "discovery_source_unavailable",
                            "message": "本次读取失败，当前为上次资料。",
                        }
                    ]
                    previous["public"] = copy.deepcopy(value)
                    return value
                raise DiscoveryError(
                    "发现来源暂不可用，请稍后重试", "discovery_source_unavailable", 502
                ) from exc

    def cached_preview(self, feed_id, horizon):
        """Read the exact owned preview the user confirmed, rather than a different feed."""
        self._prune_feeds()
        entry = self._feeds.get(feed_id)
        if entry is None:
            raise DiscoveryError("预览已过期，请刷新后重新选择", "discovery_feed_expired", 409)
        if entry["public"]["horizon"] != horizon:
            raise DiscoveryError("资料不属于当前预览", "discovery_selection_invalid", 409)
        return copy.deepcopy(entry["public"])

    async def selection_preview(self, feed_id, theme_id, horizon):
        """Read full current evidence only for a theme selected from an owned live preview."""
        async with self._feed_lock:
            feed = self.cached_preview(feed_id, horizon)
            selected = next((item for item in feed["themes"] if item["id"] == theme_id), None)
            if feed["horizon"] != horizon or selected is None:
                raise DiscoveryError("资料不属于当前预览", "discovery_selection_invalid", 409)
            event_ids = [material.get("event_id") for material in selected.get("materials", [])]
            if event_ids != [theme_id]:
                raise DiscoveryError("预览来源范围不可核验", "discovery_selection_invalid", 409)
        # This updates only bounded memory caches. It never reserves a session or writes Store.
        result = await self.refresh_theme(horizon, theme_id, event_ids)
        log.info("discovery_selection_preview_read")
        return result

    async def refresh_theme(self, horizon, theme_id, event_ids):
        """Refresh exactly the saved source event, independent of the discovery ranking."""
        if (
            horizon not in {"short", "medium", "long"}
            or not isinstance(theme_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", theme_id)
            or event_ids != [theme_id]
        ):
            raise DiscoveryError("跟踪来源范围尚未核验", "discovery_track_scope_unverified", 409)
        async with self._feed_lock:
            self._prune_feeds()
            try:
                detail = await self.reader("/intelligence/events/" + theme_id)
                if (
                    not isinstance(detail, dict)
                    or not isinstance(detail.get("event"), dict)
                    or detail["event"].get("id") != theme_id
                    or not isinstance(detail.get("articles", []), list)
                    or any(not isinstance(item, dict) for item in detail.get("articles", []))
                ):
                    raise DiscoveryError("事件归档结构不可核验", "discovery_source_invalid", 502)
                acquired, feed_id = now(), str(uuid4())
                item = theme(detail["event"], acquired, {})
                if item is None:
                    raise DiscoveryError("跟踪事件暂不可核验", "discovery_track_no_materials", 409)
                proof = digest(evidence_projection(detail))
                for material in item["materials"]:
                    material["evidence_sha256"] = proof
                value = {
                    "feed_id": feed_id,
                    "horizon": horizon,
                    "cutoff": acquired,
                    "retrieved_at": acquired,
                    "source": SOURCE,
                    "source_label": SOURCE_LABEL,
                    "source_as_of": stamp(detail["event"].get("updated_at")),
                    "stale": detail.get("cache_stale") is True,
                    "state": "ready",
                    "themes": [item],
                    "errors": [],
                    "source_policy": SOURCE_POLICY,
                    "bounded": False,
                    "limitations": [
                        "仅核对已批准的固定来源事件及归档报道，不依赖首页排名；未抓取链接网页全文。"
                    ],
                }
                entry = {
                    "scope": "tracking",
                    "public": value,
                    "proofs": {theme_id: projection(detail["event"])},
                    "detail_proofs": {theme_id: proof},
                    "time": time.monotonic(),
                }
                entry["size"] = len(json_bytes(entry))
                if entry["size"] > MAX_CACHE_BYTES:
                    raise DiscoveryError("发现资料超过缓存上限", "discovery_source_limit", 502)
                self._feeds[feed_id] = entry
                self._prune_feeds()
                log.info("discovery_tracked_event_refreshed")
                return copy.deepcopy(value)
            except (HTTPException, RuntimeFailure, OSError, ValueError, TimeoutError) as exc:
                log.warning("discovery_tracked_event_refresh_failed", error_type=type(exc).__name__)
                raise DiscoveryError(
                    "跟踪来源本次不可用", "discovery_track_source_unavailable", 502
                ) from exc

    async def prepare(self, body):
        body = body if isinstance(body, Prepare) else Prepare.model_validate(body)
        async with self.lock:
            request_hash = digest(body.model_dump())
            handoff_id = str(uuid5(UUID(body.request_id), "rwb-discovery-handoff"))
            existing = self._table().get(handoff_id)
            if existing:
                if existing["request_sha256"] != request_hash:
                    raise DiscoveryError(
                        "同一请求标识绑定了另一选择", "discovery_request_conflict", 409
                    )
                await self._finish_session(existing, mutate=True)
                return self._public(existing)
            self._prune_feeds()
            feed_entry = self._feeds.get(body.feed_id)
            if feed_entry is None:
                raise DiscoveryError("预览已过期，请刷新后重新选择", "discovery_feed_expired", 409)
            feed = feed_entry["public"]
            selected_theme = next(
                (item for item in feed["themes"] if item["id"] == body.theme_id), None
            )
            if feed["horizon"] != body.horizon or selected_theme is None:
                raise DiscoveryError("资料不属于当前预览", "discovery_selection_invalid", 409)
            materials = {item["id"]: item for item in selected_theme["materials"]}
            if any(identifier not in materials for identifier in body.material_ids):
                raise DiscoveryError("资料不属于当前主题", "discovery_selection_invalid", 409)
            if len(self._table()) >= MAX_HANDOFFS:
                raise DiscoveryError("研究交接记录已达上限", "discovery_handoff_limit", 409)
            # Complete and validate every source read before reserving any native identity.
            evidence = []
            for identifier in body.material_ids:
                material = materials[identifier]
                detail = await self.reader("/intelligence/events/" + material["event_id"])
                if (
                    not isinstance(detail, dict)
                    or not isinstance(detail.get("event"), dict)
                    or not isinstance(detail.get("articles", []), list)
                ):
                    raise DiscoveryError("事件归档结构不可核验", "discovery_source_invalid", 502)
                proof = projection(detail["event"])
                if (
                    digest(proof) != material["content_sha256"]
                    or proof != feed_entry["proofs"][body.theme_id]
                ):
                    raise DiscoveryError(
                        "事件版本已变化，请刷新重新选择", "discovery_evidence_changed", 409
                    )
                expected_detail = feed_entry.get("detail_proofs", {}).get(body.theme_id)
                if expected_detail and digest(evidence_projection(detail)) != expected_detail:
                    raise DiscoveryError(
                        "归档证据已变化，请重新确认", "discovery_evidence_changed", 409
                    )
                evidence.append(
                    {
                        "event_id": material["event_id"],
                        "material": material,
                        "projection": proof,
                        "preview_sha256": material["content_sha256"],
                        "detail": detail,
                        "acquired_at": now(),
                    }
                )
            frozen_at = now()
            selection_hash = digest(
                {
                    "feed_id": body.feed_id,
                    "material_ids": body.material_ids,
                    "proofs": [item["projection"] for item in evidence],
                    "details": [digest(item["detail"]) for item in evidence],
                }
            )
            record = {
                "handoff_id": handoff_id,
                "request_sha256": request_hash,
                "prepare_request": body.model_dump(mode="json"),
                "session_id": str(uuid4()),
                "target_mode": body.target_mode,
                "horizon": body.horizon,
                "theme_id": body.theme_id,
                "title": selected_theme["title"],
                "question": body.question,
                "state": "prepared",
                "selection_sha256": selection_hash,
                "cutoff": frozen_at,
                "retrieved_at": frozen_at,
                "materials": acquired_materials(evidence),
            }
            had_table = "discovery_handoffs" in self.store.data
            table = self.store.data.setdefault("discovery_handoffs", {})
            table[handoff_id] = record
            try:
                self.store.save()
            except StoreError:
                table.pop(handoff_id, None)
                if not had_table:
                    self.store.data.pop("discovery_handoffs", None)
                raise
            origin = {"handoff_id": handoff_id, "selection_sha256": selection_hash}
            self.store.reserve_discovery_session(
                record["session_id"],
                body.target_mode,
                origin,
                ("今日发现 · " + selected_theme["title"])[:120],
            )
            bundle = {
                "selection_sha256": selection_hash,
                "cutoff": frozen_at,
                "retrieved_at": frozen_at,
                "source_as_of": feed.get("source_as_of"),
                "stale": feed["stale"],
                "evidence": evidence,
            }
            dataset = self.research.datahub.snapshots.publish_discovery(
                record["session_id"], handoff_id, bundle
            )
            record.update(
                dataset_id=dataset["dataset_id"], dataset_manifest_sha256=dataset["manifest_sha256"]
            )
            write_context(self.research, record)
            self.store.save()
            await self._finish_session(record, mutate=True)
            log.info("discovery_handoff_prepared", session_id=record["session_id"])
            return self._public(record)

    async def _finish_session(self, record, *, mutate):
        if "dataset_id" not in record or "context_sha256" not in record:
            raise DiscoveryError(
                "冻结资料尚未完整保存，未提交研究", "discovery_snapshot_incomplete", 409
            )
        trusted_context(self.research, record)
        if record["state"] in {
            "running",
            "execution_starting",
            "execution_outcome_unknown",
            "failed",
        }:
            return
        try:
            await ensure_session(self.research, record, mutate=mutate)
        except RuntimeFailure as exc:
            record.update(state="session_outcome_unknown", code=exc.code)
        self.store.save()

    async def get_handoff(self, identifier):
        async with self.lock:
            record = self._record(identifier)
            await self._finish_session(record, mutate=False)
            await self._reconcile_execution(record)
            return self._public(record)

    def trusted_context(self, sid):
        row = self.store.session(sid)
        if row.get("purpose") != "discovery_research":
            return None
        origin = row.get("discovery_origin")
        if not isinstance(origin, dict):
            raise DiscoveryError("研究交接归属缺失", "discovery_session_foreign", 409)
        record = self._record(origin.get("handoff_id"))
        if record["session_id"] != sid:
            raise DiscoveryError("研究交接不属于当前会话", "discovery_session_foreign", 409)
        return copy.deepcopy(trusted_context(self.research, record))

    async def _reconcile_execution(self, record):
        if record["state"] not in {"execution_starting", "execution_outcome_unknown"}:
            return
        receipt = self.store.data["receipts"].get(
            f"{record['session_id']}:{record['delivery_key']}"
        )
        accepted = isinstance(receipt, dict) and receipt.get("status") == "accepted"
        if not accepted:
            try:
                entries = await self.research.client.history(record["session_id"])
                matches = [
                    entry
                    for entry in entries
                    if entry.get("event", {}).get("type") == "user/message"
                    and record["marker"]
                    in content_text(entry["event"].get("data", {}).get("content"))
                ]
                accepted = len(matches) == 1
            except (RuntimeFailure, ValueError, TypeError):
                log.warning("discovery_execution_reconciliation_unavailable")
        record["state"] = "running" if accepted else "execution_outcome_unknown"
        self.store.save()

    async def execute(self, identifier, request_id):
        try:
            request_id = str(UUID(request_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise DiscoveryError("执行请求标识非法", "discovery_request_invalid", 422) from exc
        async with self.lock:
            record = self._record(identifier)
            await self._finish_session(record, mutate=True)
            await self._reconcile_execution(record)
            if record["state"] != "snapshot_ready":
                return self._public(record)
            context = self.trusted_context(record["session_id"])
            key = (
                "discovery:"
                + record["handoff_id"]
                + ":"
                + hashlib.sha256(context["context_sha256"].encode()).hexdigest()
            )
            marker = "[RWB_DISCOVERY_EXECUTION:" + key + "]"
            prompt = (
                record["question"]
                + "\n\n"
                + marker
                + "\n先读取 inputs/discovery-context.json，核对冻结资料目录 inputs/datasets/"
                + record["dataset_id"]
                + " 的 manifest.json，预期SHA-256="
                + record["dataset_manifest_sha256"]
                + "。基于本次冻结选材开展研究；区分事实、第三方观点与推断，核验原始披露，列反证、失效条件、未知时间和覆盖缺口。"
                + SOURCE_POLICY
                + " 输出须沿现有研究报告与质量检查流程；未经质量门不能宣称研究通过。不要自行开启跟踪、创建日程或外部投递。"
            )
            scope = self.store.session(record["session_id"]).get("automation_research_scope")
            if scope is not None and (
                not isinstance(scope, dict)
                or not isinstance(scope.get("approved_tools"), list)
                or any(not isinstance(item, str) for item in scope["approved_tools"])
            ):
                raise DiscoveryError(
                    "跟踪工具范围不可核验", "discovery_tracking_scope_invalid", 409
                )
            tool_scope = {"tool_ids": scope["approved_tools"]} if scope is not None else {}
            previous = copy.deepcopy(record)
            record.update(
                state="execution_starting",
                delivery_key=key,
                marker=marker,
                execution_request_id=request_id,
            )
            try:
                self.store.save()
            except StoreError:
                record.clear()
                record.update(previous)
                raise
            try:
                await self.research.send(
                    record["session_id"], prompt, key, formats=["md"], **tool_scope
                )
            except (RuntimeFailure, StoreError, OSError) as exc:
                receipt = self.store.data["receipts"].get(f"{record['session_id']}:{key}")
                record.update(
                    state="execution_outcome_unknown" if receipt else "failed",
                    code=(
                        "discovery_execution_acceptance_unknown"
                        if receipt
                        else "discovery_execution_not_submitted"
                    ),
                )
                self.store.save()
                log.warning("discovery_execution_failed", error_type=type(exc).__name__)
                return self._public(record)
            record["state"] = "running"
            self.store.save()
            log.info("discovery_execution_admitted", session_id=record["session_id"])
            return self._public(record)
