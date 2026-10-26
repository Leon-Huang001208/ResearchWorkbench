"""Explicit discovery tracking over the existing per-user Automation scheduler."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import re
import time
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.observability import get_logger

from ..automation.models import AutomationCreate
from ..research_quality_service import receipt_archives
from ..store import StoreError

log = get_logger(__name__)
TRACK_SCHEMA = "discovery-tracking-v1"
SAFE_TOOLS = ["research_run_script", "research_document_operation"]
TERMINAL = {
    "completed",
    "incomplete",
    "invalid",
    "blocked",
    "failed",
    "cancelled",
    "interrupted",
    "disconnected",
}


def _sha(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _raw_description(condition, news_id, event_ids):
    return (
        condition
        + "\n\n[RWB_RAW_SOURCE_SCOPE:"
        + _sha({"news_id": news_id, "event_ids": sorted(event_ids)})
        + "]"
    )


class TrackSave(BaseModel):
    """No arbitrary targets, upstream URLs, MCP or external delivery permissions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    feed_id: str
    horizon: Literal["short", "medium", "long"]
    theme_id: str = Field(min_length=1, max_length=160)
    condition: str = Field(min_length=1, max_length=4000)
    frequency: Literal["daily", "weekly"]
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"

    @field_validator("request_id", "feed_id")
    @classmethod
    def uuid_value(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("uuid_invalid")
        return value

    @field_validator("condition")
    @classmethod
    def condition_nonempty(cls, value):
        if not value.strip():
            raise ValueError("condition_required")
        return value


class DiscoveryTracking:
    """Restrict consent, identity, novelty and quality; never own a second timer."""

    def __init__(self, research, discovery):
        self.research, self.discovery, self.store = research, discovery, research.store
        self.automations = research.automations
        self.lock = asyncio.Lock()

    def _table(self):
        return self.store.data.get("discovery_tracks", {})

    def _owned(self, automation_id):
        row = self._table().get(automation_id)
        automation = self.store.data.get("automations", {}).get(automation_id)
        if not row or not automation or not self.eligible(automation):
            raise StoreError("跟踪任务不存在或不属于当前用户", "discovery_track_not_found", 404)
        return row, automation

    def eligible(self, automation):
        """Local index identity plus the original locked definition, never a UI claim."""
        row = self._table().get(automation.get("id"))
        raw = isinstance(row, dict) and row.get("source_kind") == "news"
        description = automation.get("research_task", {}).get("description", "")
        bound = False
        if (
            raw
            and isinstance(row.get("body"), dict)
            and isinstance(row.get("approved_event_ids"), list)
        ):
            try:
                bound = description == _raw_description(
                    row["body"]["condition"], row["body"]["theme_id"], row["approved_event_ids"]
                )
            except (KeyError, TypeError, ValueError):
                log.warning("discovery_raw_scope_invalid")
        return bool(
            isinstance(row, dict)
            and (bound if raw else "[RWB_RAW_SOURCE_SCOPE:" not in description)
            and row.get("schema") == TRACK_SCHEMA
            and row.get("source_kind", "event") in {"event", "news"}
            and (
                row.get("source_kind") != "news"
                or row.get("approved_news_ids") == [row.get("body", {}).get("theme_id")]
            )
            and row.get("automation_id") == automation.get("id")
            and row.get("definition_sha256")
            == _sha(self.automations._definition_snapshot(automation))
            and automation.get("target", {}).get("kind") == "research_task"
            and automation.get("mcp_tools") == []
            and automation.get("delivery") == {"channel_ids": [], "include_attachments": False}
        )

    @staticmethod
    def _theme(feed, theme_id):
        rows = [row for row in feed.get("themes", []) if row.get("id") == theme_id]
        if len(rows) != 1 or not rows[0].get("materials"):
            raise StoreError("本次未取得该主题资料", "discovery_track_no_materials", 409)
        theme = rows[0]
        if not all(
            isinstance(row.get("id"), str) and row.get("content_sha256")
            for row in theme["materials"]
        ):
            raise StoreError("资料版本尚未核验", "discovery_track_evidence_unverified", 409)
        return theme

    @staticmethod
    def _fingerprint(theme):
        # A complete baseline and each later observation use the same acquired evidence contract.
        if theme.get("source_kind") == "news":
            materials = theme["materials"]
            if (
                len(materials) != 1
                or materials[0].get("source_kind") != "news"
                or materials[0].get("news_id") != theme["id"]
                or "event_id" in materials[0]
                or not re.fullmatch(r"news-[a-f0-9]{48}", theme["id"])
                or not re.fullmatch(r"[a-f0-9]{64}", str(materials[0].get("evidence_sha256", "")))
            ):
                raise StoreError(
                    "原始资讯归档指纹未核验", "discovery_track_evidence_unverified", 409
                )
            return _sha(
                {
                    "source_kind": "news",
                    "news_id": theme["id"],
                    "evidence_sha256": materials[0]["evidence_sha256"],
                }
            )
        if any(
            not isinstance(row.get("event_id"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("evidence_sha256", "")))
            for row in theme["materials"][:20]
        ):
            raise StoreError("归档证据指纹未核验", "discovery_track_evidence_unverified", 409)
        return _sha(
            sorted(
                [
                    {"event_id": row["event_id"], "evidence_sha256": row["evidence_sha256"]}
                    for row in theme["materials"][:20]
                ],
                key=lambda row: row["event_id"],
            )
        )

    async def save(self, body):
        body = TrackSave.model_validate(body)
        payload = body.model_dump(mode="json")
        digest = _sha(payload)
        async with self.lock:
            existing = next(
                (row for row in self._table().values() if row.get("request_id") == body.request_id),
                None,
            )
            if existing:
                if existing.get("request_sha256") != digest:
                    raise StoreError(
                        "同一请求不能保存不同跟踪定义", "discovery_track_conflict", 409
                    )
                return self._public(*self._owned(existing["automation_id"]))
            feed = self.discovery.cached_preview(body.feed_id, body.horizon)
            if feed.get("feed_id") != body.feed_id:
                raise StoreError("发现资料已更新，请重新确认", "discovery_feed_changed", 409)
            theme = self._theme(feed, body.theme_id)
            raw_news = theme.get("source_kind") == "news"
            event_ids = (
                [x["event_id"] for x in theme.get("related_events", [])]
                if raw_news
                else [material.get("event_id") for material in theme["materials"][:20]]
            )
            if raw_news:
                if (
                    len(theme["materials"]) != 1
                    or theme["materials"][0].get("news_id") != body.theme_id
                ):
                    raise StoreError(
                        "跟踪来源范围尚未核验", "discovery_track_scope_unverified", 409
                    )
                baseline_feed = await self.discovery.refresh_news(
                    body.horizon, body.theme_id, event_ids
                )
            else:
                if event_ids != [body.theme_id]:
                    raise StoreError(
                        "跟踪来源范围尚未核验", "discovery_track_scope_unverified", 409
                    )
                baseline_feed = await self.discovery.refresh_theme(
                    body.horizon, body.theme_id, event_ids
                )
            if baseline_feed.get("stale") is True:
                raise StoreError(
                    "跟踪基线来源本次不可用", "discovery_track_source_unavailable", 503
                )
            baseline = self._theme(baseline_feed, body.theme_id)
            if [item["content_sha256"] for item in baseline["materials"]] != [
                item["content_sha256"] for item in theme["materials"]
            ]:
                raise StoreError(
                    "预览中的研究判断已变化，请刷新后确认", "discovery_evidence_changed", 409
                )
            if any(
                old.get("evidence_sha256") and old["evidence_sha256"] != new.get("evidence_sha256")
                for old, new in zip(theme["materials"], baseline["materials"])
            ):
                raise StoreError("归档证据已变化，请重新确认", "discovery_evidence_changed", 409)
            model = copy.deepcopy(self.research.default_model)
            if model.get("provider") not in {"deepseek-official", "openai-compatible"}:
                raise StoreError("当前模型不支持跟踪", "discovery_model_unavailable", 409)
            profile = self.research.model_profile_identity(model["provider"])
            hour, minute = map(int, body.time.split(":"))
            schedule = {
                "kind": body.frequency,
                "timezone": body.timezone,
                "hour": hour,
                "minute": minute,
            }
            if body.frequency == "weekly":
                # The approved weekly UI contract is Friday in the fixed account timezone.
                schedule["weekday"] = 4
            definition = AutomationCreate.model_validate(
                {
                    "name": f"今日发现 · {theme['title']}"[:160],
                    "target_kind": "research_task",
                    "research_task": {
                        "description": (
                            _raw_description(body.condition, body.theme_id, event_ids)
                            if raw_news
                            else body.condition
                        ),
                        "model_provider": model["provider"],
                        "model_id": model["model"],
                        "output_requirements": "核对冻结资料、反证与失效条件，沿用原研究质量门。",
                        "approved_data_sources": ["datahub", "uploads"],
                        "approved_tools": SAFE_TOOLS,
                    },
                    "schedule": schedule,
                    "output_formats": ["md"],
                }
            )

            def companion(automation):
                existed = "discovery_tracks" in self.store.data
                table = self.store.data.setdefault("discovery_tracks", {})
                table[automation["id"]] = {
                    "schema": TRACK_SCHEMA,
                    "automation_id": automation["id"],
                    "request_id": body.request_id,
                    "request_sha256": digest,
                    "body": payload,
                    "title": theme["title"],
                    "model": model,
                    "model_profile_id": profile,
                    "approved_event_ids": event_ids,
                    "definition_sha256": _sha(self.automations._definition_snapshot(automation)),
                    "last_seen_fingerprint": self._fingerprint(baseline),
                    "last_attempt_fingerprint": None,
                    "last_accepted_fingerprint": None,
                    "created_at": time.time(),
                    "enable_error": None,
                    "max_model_runs_per_day": 1,
                }

                if raw_news:
                    table[automation["id"]].update(
                        source_kind="news", approved_news_ids=[body.theme_id]
                    )

                def rollback():
                    table.pop(automation["id"], None)
                    if not existed and not table:
                        self.store.data.pop("discovery_tracks", None)
                    log.error("discovery_tracking_save_failed")

                return rollback

            automation = self.automations.create(
                definition, creation_key=f"discovery:{body.request_id}", before_save=companion
            )
            row, _ = self._owned(automation["id"])
            log.info("discovery_tracking_saved", status="disabled")
            return self._public(row, automation)

    @staticmethod
    def _version(automation, expected_version):
        if type(expected_version) is not int or expected_version != automation.get(
            "definition_version"
        ):
            raise StoreError("跟踪定义版本已变化，请重新确认", "automation_version_conflict", 409)

    def enable(self, automation_id, expected_version):
        row, automation = self._owned(automation_id)
        self._version(automation, expected_version)
        try:
            if not self._model_current(row):
                raise StoreError("当前模型连接与批准跟踪不一致", "discovery_model_changed", 409)
            result = self.automations.enable(automation_id, expected_version=expected_version)
        except StoreError as exc:
            row["enable_error"] = exc.code
            self.store.save()
            log.warning("discovery_tracking_enable_failed", code=exc.code)
            raise
        row["enable_error"] = None
        self.store.save()
        log.info("discovery_tracking_enabled")
        return self._public(row, result)

    def disable(self, automation_id, expected_version):
        row, automation = self._owned(automation_id)
        self._version(automation, expected_version)
        result = self.automations.disable(automation_id)
        log.info("discovery_tracking_disabled")
        return self._public(row, result)

    def _public(self, row, automation):
        result = {
            key: copy.deepcopy(row.get(key))
            for key in (
                "title",
                "created_at",
                "enable_error",
                "last_checked_at",
                "last_attempt_at",
                "last_seen_fingerprint",
                "last_attempt_fingerprint",
                "last_accepted_fingerprint",
                "max_model_runs_per_day",
            )
        }
        result.update(
            id=automation["id"],
            request_id=row["request_id"],
            enabled=automation["enabled"],
            definition_version=automation["definition_version"],
            next_run_at=automation.get("next_run_at"),
            schedule=copy.deepcopy(automation["schedule"]),
            model=copy.deepcopy(row["model"]),
            condition=row["body"]["condition"],
            horizon=row["body"]["horizon"],
            theme_id=row["body"]["theme_id"],
            notification_policy="meaningful_change_only",
            limitations=["跟踪核对已批准事件及上游归档报道；链接网页全文未独立抓取。"],
        )
        runs = [
            run
            for run in self.store.data.get("automation_runs", {}).values()
            if run.get("automation_id") == automation["id"]
        ]
        runs.sort(key=lambda run: run.get("created_at", 0), reverse=True)
        result["runs"] = [
            {
                "id": run["id"],
                "session_id": run.get("session_id"),
                "handoff_id": run.get("discovery_handoff_id"),
                "created_at": run.get("created_at"),
                "execution_status": run.get("research_status", "unknown"),
                "quality_status": run.get("discovery_quality_status", "not_checked"),
                "accepted": run.get("discovery_accepted") is True,
                "failure_code": run.get("failure_code"),
                "notification": run.get("discovery_notification", "none"),
            }
            for run in runs[:10]
        ]
        return result

    def list(self):
        items = []
        for automation_id in self._table():
            automation = self.store.data.get("automations", {}).get(automation_id)
            if automation and self.eligible(automation):
                items.append(self._public(self._table()[automation_id], automation))
        return {"items": sorted(items, key=lambda row: row["created_at"], reverse=True)}

    def has_enabled(self):
        """Startup need probe is read-only, including on old indexes without this extension."""
        return any(
            automation.get("enabled") is True and self.eligible(automation)
            for automation in self.store.data.get("automations", {}).values()
        )

    def _model_current(self, row):
        return (
            self.research.default_model == row["model"]
            and self.research.model_profile_identity(row["model"]["provider"])
            == row["model_profile_id"]
        )

    async def execute(self, automation, run):
        """Collect new evidence first; persist one attempt before preparing/sending."""
        row, _ = self._owned(automation["id"])
        actual = self.automations._run_row(run["id"])
        if not self._model_current(row):
            raise StoreError("当前模型连接与批准跟踪不一致", "discovery_model_changed", 409)
        if row.get("source_kind") == "news":
            if row.get("approved_news_ids") != [row["body"]["theme_id"]]:
                raise StoreError("跟踪来源范围尚未核验", "discovery_track_scope_unverified", 409)
            feed = await self.discovery.refresh_news(
                row["body"]["horizon"], row["body"]["theme_id"], row.get("approved_event_ids")
            )
        else:
            feed = await self.discovery.refresh_theme(
                row["body"]["horizon"], row["body"]["theme_id"], row.get("approved_event_ids")
            )
        if feed.get("stale") is True or feed.get("state") == "stale":
            raise StoreError("本次未取得新的来源观察", "discovery_track_source_unavailable", 503)
        theme = self._theme(feed, row["body"]["theme_id"])
        fingerprint = self._fingerprint(theme)
        async with self.lock:
            row["last_checked_at"] = time.time()
            if fingerprint in {
                row.get("last_seen_fingerprint"),
                row.get("last_attempt_fingerprint"),
            }:
                self.store.save()
                log.info("discovery_tracking_unchanged")
                return {"status": "skipped_unchanged"}
            from zoneinfo import ZoneInfo

            today = self.automations.now().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
            if row.get("last_attempt_day") == today:
                log.info("discovery_tracking_daily_limit")
                return {"status": "blocked", "failure_code": "discovery_daily_model_limit"}
            before = copy.deepcopy(row)
            row.update(
                last_seen_fingerprint=fingerprint,
                last_attempt_fingerprint=fingerprint,
                last_attempt_at=time.time(),
                last_attempt_day=today,
                last_attempt_run_id=run["id"],
            )
            actual.update(
                discovery_fingerprint=fingerprint,
                discovery_quality_status="not_checked",
                discovery_accepted=False,
                discovery_notification="none",
            )
            try:
                self.store.save()
            except StoreError:
                row.clear()
                row.update(before)
                log.error("discovery_tracking_attempt_checkpoint_failed")
                raise
        from .models import Prepare

        # Source content remains data inside the original handoff, never tool instructions.
        prepared = await self.discovery.prepare(
            Prepare(
                request_id=str(uuid4()),
                feed_id=feed["feed_id"],
                horizon=row["body"]["horizon"],
                theme_id=row["body"]["theme_id"],
                material_ids=[item["id"] for item in theme["materials"][:20]],
                target_mode="fingpt",
                question=row["body"]["condition"],
            ),
            **({"require_fresh": True} if row.get("source_kind") == "news" else {}),
        )
        actual["discovery_handoff_id"] = prepared["handoff_id"]
        self.automations._persist_native_reference(run["id"], session_id=prepared["session_id"])
        context = self.discovery.trusted_context(prepared["session_id"])
        if inspect.isawaitable(context):
            context = await context
        if not context or context.get("handoff_id") != prepared["handoff_id"]:
            raise StoreError("冻结研究归属未核验", "discovery_context_changed", 409)
        session = self.store.session(prepared["session_id"])
        if (
            session.get("mode") != "fingpt"
            or session.get("model_provider") != row["model"]["provider"]
            or session.get("model") != row["model"]["model"]
            or session.get("model_profile_id") != row["model_profile_id"]
        ):
            raise StoreError("冻结研究模型与批准连接不一致", "discovery_model_changed", 409)
        session["automation_research_scope"] = copy.deepcopy(automation["research_task"])
        session["source_scope"] = list(automation["research_task"]["approved_data_sources"])
        self.store.save()
        # Recheck after all awaited preparation. Never change the approved model connection.
        if not self._model_current(row):
            raise StoreError("准备期间模型连接已变化", "discovery_model_changed", 409)
        accepted = await self.discovery.execute(prepared["handoff_id"], str(uuid4()))
        if accepted.get("state") in {
            "execution_starting",
            "execution_outcome_unknown",
            "session_outcome_unknown",
        }:
            actual["discovery_notification"] = "action_required"
            self.store.save()
            return {
                "status": "interrupted",
                "session_id": prepared["session_id"],
                "failure_code": "discovery_execution_unknown",
            }
        if accepted.get("state") not in {"running", "completed"}:
            return {
                "status": "failed",
                "session_id": prepared["session_id"],
                "failure_code": accepted.get("code") or "discovery_execution_not_accepted",
            }
        return await self._monitor(actual, row)

    async def _monitor(self, run, track):
        """The Host quality and exact report binding remain the only acceptance oracle."""
        while True:
            detail = await self.research.detail(run["session_id"])
            status = detail.get("status", "unknown")
            if status in TERMINAL and detail.get("can_cancel") is not True:
                quality = detail.get("research_quality") or {}
                report = detail.get("research_report") or {}
                delivery = detail.get("research_report_delivery") or {}
                digest = report.get("content_sha256")
                task_id = (quality.get("contract") or {}).get("task_id")
                handoff = self.store.data.get("discovery_handoffs", {}).get(
                    run.get("discovery_handoff_id"), {}
                )
                delivery_key = handoff.get("delivery_key")
                receipt = (
                    self.store.data.get("receipts", {}).get(
                        f"{run['session_id']}:{delivery_key}", {}
                    )
                    if delivery_key
                    else {}
                )
                original_task_id = (receipt.get("research_contract") or {}).get("task_id")
                version_id = delivery.get("version_id")
                bound_check = next(
                    (
                        checked
                        for anchor, checked in receipt_archives(receipt)
                        if anchor.get("version_id") == version_id
                        and anchor.get("task_id") == task_id
                        and checked.get("status") == "passed"
                        and checked.get("report_content_sha256") == digest
                    ),
                    None,
                )
                current_version = next(
                    (
                        version
                        for version in detail.get("research_report_versions", [])
                        if version.get("version_id") == version_id
                        and version.get("task_id") == task_id
                        and version.get("is_current") is True
                        and version.get("quality_binding") == "host_check"
                        and (version.get("quality") or {}).get("status") == "passed"
                        and (version.get("quality") or {}).get("report_content_sha256") == digest
                        and any(
                            item.get("name") == "research-report.json"
                            and item.get("sha256") == digest
                            for item in version.get("files", [])
                        )
                    ),
                    None,
                )
                accepted = bool(
                    status == "completed"
                    and quality.get("status") == "passed"
                    and detail.get("execution_restricted") is not True
                    and isinstance(digest, str)
                    and re.fullmatch(r"[a-f0-9]{64}", digest)
                    and bound_check
                    and delivery.get("status") == "bound"
                    and delivery.get("quality_status") == "passed"
                    and delivery.get("report_content_sha256") == digest
                    and task_id
                    and handoff.get("session_id") == run["session_id"]
                    and receipt.get("status") == "accepted"
                    and original_task_id == task_id
                    and report.get("task_id") == task_id
                    and delivery.get("task_id") == task_id
                    and current_version
                )
                run.update(
                    discovery_quality_status=quality.get("status", "not_checked"),
                    discovery_accepted=accepted,
                    discovery_notification="meaningful_change" if accepted else "action_required",
                )
                if accepted:
                    track["last_accepted_fingerprint"] = run.get("discovery_fingerprint")
                self.store.save()
                log.info("discovery_tracking_observed", execution_status=status, accepted=accepted)
                return {
                    "status": status,
                    "session_id": run["session_id"],
                    "failure_code": None if status == "completed" else f"session_{status}",
                }
            if status == "unknown":
                return {
                    "status": "interrupted",
                    "session_id": run["session_id"],
                    "failure_code": "discovery_execution_unknown",
                }
            await self.automations.sleep(1)

    async def resume(self, run_id):
        """Observe a retained reference only. Recovery never calls prepare or execute."""
        run = self.automations._run_row(run_id)
        track, _ = self._owned(run["automation_id"])
        hid = run.get("discovery_handoff_id")
        if not hid or not run.get("session_id"):
            raise StoreError("跟踪运行关联尚未核验", "discovery_execution_unknown", 409)
        handoff = self.discovery.get_handoff(hid)
        if inspect.isawaitable(handoff):
            handoff = await handoff
        if handoff.get("session_id") != run["session_id"] or handoff.get("state") not in {
            "running",
            "completed",
        }:
            raise StoreError("跟踪提交结果未知，未重新发送", "discovery_execution_unknown", 409)
        result = await self._monitor(run, track)
        run.update(
            research_status=result["status"],
            failure_code=result.get("failure_code"),
            updated_at=time.time(),
        )
        self.store.save()
