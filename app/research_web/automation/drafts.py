"""Native schedule proposals, persisted separately from executable Automations."""

import copy
import time
from uuid import uuid4

from core.observability import get_logger

from ..store import StoreError
from .models import AutomationCreate, AutomationUpdate
from .service import automation_feature_enabled

log = get_logger(__name__)


class AutomationDrafts:
    def __init__(self, research):
        self.research = research
        self.store = research.store

    def _session(self, sid):
        if not automation_feature_enabled():
            raise StoreError("Automation 尚未启用", "automation_disabled", 404)
        row = self.store.session(sid)
        if row["mode"] != "claw":
            raise StoreError("日程草稿仅适用于 Claw 会话")
        return row

    def list(self, sid):
        self._session(sid)
        return {
            "items": [
                copy.deepcopy(row)
                for row in self.store.data.get("automation_drafts", {}).values()
                if row["session_id"] == sid
            ]
        }

    def _get(self, sid, draft_id):
        self._session(sid)
        row = self.store.data.get("automation_drafts", {}).get(draft_id)
        if row is None or row["session_id"] != sid:
            raise StoreError("日程草稿不属于当前会话", "draft_not_found", 404)
        return row

    @staticmethod
    def _no_external_permissions(body):
        delivery = body.delivery
        if getattr(body, "mcp_tools", []) or (
            delivery is not None and (delivery.channel_ids or delivery.include_attachments)
        ):
            raise StoreError("聊天日程草稿不能授予 MCP 或投递权限", "draft_permissions_denied", 409)

    def prepare(self, sid, body: AutomationCreate):
        self._session(sid)
        self._no_external_permissions(body)
        active = [row for row in self.list(sid)["items"] if row["status"] == "proposed"]
        if len(active) >= 20:
            raise StoreError("待确认日程草稿已达上限，请先处理已有草稿", "draft_limit", 409)
        resolved = self.research.automations.resolve_definition(body)
        if resolved["version"] != body.target_version or (
            body.target_sha256 is not None and body.target_sha256 != resolved["sha256"]
        ):
            raise StoreError("目标版本已变化", "target_version_conflict", 409)
        locked = body.model_copy(update={"target_sha256": resolved["sha256"]})
        row = {
            "id": f"draft-{uuid4().hex}",
            "session_id": sid,
            "status": "proposed",
            "operation": "create",
            "body": locked.model_dump(mode="json"),
            "created_at": time.time(),
        }
        table = self.store.data.setdefault("automation_drafts", {})
        table[row["id"]] = row
        try:
            self.store.save()
        except StoreError:
            table.pop(row["id"], None)
            log.error("automation_draft_prepare_failed")
            raise
        log.info("automation_draft_prepared", session_id=sid)
        return copy.deepcopy(row)

    def confirm(self, sid, draft_id, body: AutomationCreate, *, enable=False):
        row = self._get(sid, draft_id)
        if row.get("operation", "create") != "create":
            raise StoreError("草稿操作不匹配", "draft_operation_conflict", 409)
        if row["status"] == "dismissed":
            raise StoreError("日程草稿已取消", "draft_dismissed", 409)
        self._no_external_permissions(body)
        if body.target_kind == "research_task" and not enable:
            raise StoreError(
                "研究日程需要明确确认创建并启用", "draft_enable_confirmation_required", 409
            )
        if row["status"] == "confirmed" and enable != row.get("enable_requested", False):
            raise StoreError("确认操作与已保存草稿不一致", "draft_confirmation_conflict", 409)
        for key in ("target_kind", "target_id", "target_version", "target_sha256"):
            if getattr(body, key) != row["body"][key]:
                raise StoreError("目标锁定版本不能通过草稿编辑替换", "target_version_conflict", 409)
        if row["status"] == "confirmed":
            if body.model_dump(mode="json") != row["body"]:
                raise StoreError("确认内容与已保存任务不一致", "draft_confirmation_conflict", 409)
            try:
                automation = self.research.automations.get(row["automation_id"])
            except StoreError as exc:
                raise StoreError(
                    "原日程已删除，不能重新确认旧草稿", "draft_automation_deleted", 409
                ) from exc
            return (
                self._enable(row, automation)
                if enable and not row.get("enable_completed")
                else automation
            )
        automation = self.research.automations.create(body, creation_key=f"claw:{sid}:{draft_id}")
        previous = copy.deepcopy(row)
        row.update(
            status="confirmed",
            automation_id=automation["id"],
            body=body.model_dump(mode="json"),
            enable_requested=enable,
        )
        try:
            self.store.save()
        except StoreError:
            row.clear()
            row.update(previous)
            log.error("automation_draft_checkpoint_failed", session_id=sid)
            raise
        log.info("automation_draft_confirmed", session_id=sid)
        return self._enable(row, automation) if enable else automation

    def _enable(self, row, automation):
        try:
            result = self.research.automations.enable(automation["id"])
        except StoreError as exc:
            row["enable_error"] = exc.code
            self.store.save()
            log.warning("automation_draft_enable_failed", session_id=row["session_id"])
            raise
        row.pop("enable_error", None)
        row["enable_completed"] = True
        self.store.save()
        return result

    def prepare_update(self, sid, automation_id, body: AutomationUpdate):
        self._session(sid)
        self._no_external_permissions(body)
        automation = self.research.automations.get(automation_id)
        if body.expected_version != automation.get("definition_version", 1):
            raise StoreError("日程定义版本已变化", "automation_version_conflict", 409)
        if len([draft for draft in self.list(sid)["items"] if draft["status"] == "proposed"]) >= 20:
            raise StoreError("待确认日程草稿已达上限", "draft_limit", 409)
        row = {
            "id": f"draft-{uuid4().hex}",
            "session_id": sid,
            "status": "proposed",
            "operation": "update",
            "automation_id": automation_id,
            "body": body.model_dump(mode="json"),
            "previous_definition": self.research.automations._definition_snapshot(automation),
            "created_at": time.time(),
        }
        table = self.store.data.setdefault("automation_drafts", {})
        table[row["id"]] = row
        try:
            self.store.save()
        except StoreError:
            table.pop(row["id"], None)
            log.error("automation_update_draft_prepare_failed", session_id=sid)
            raise
        log.info("automation_update_draft_prepared", session_id=sid)
        return copy.deepcopy(row)

    def confirm_update(self, sid, draft_id, body: AutomationUpdate):
        row = self._get(sid, draft_id)
        if row["status"] == "dismissed":
            raise StoreError("日程草稿已取消", "draft_dismissed", 409)
        if row.get("operation") != "update":
            raise StoreError("草稿操作不匹配", "draft_operation_conflict", 409)
        if body.model_dump(mode="json") != row["body"]:
            raise StoreError("确认内容与草稿不一致", "draft_confirmation_conflict", 409)
        self._no_external_permissions(body)
        try:
            automation = self.research.automations.get(row["automation_id"])
        except StoreError as exc:
            raise StoreError("原日程已删除", "draft_automation_deleted", 409) from exc
        if row["status"] == "confirmed":
            return automation
        result = self.research.automations.update(
            row["automation_id"], body, mutation_key=f"claw:{sid}:{draft_id}"
        )
        previous = copy.deepcopy(row)
        row.update(status="confirmed", confirmed_version=result["definition_version"])
        try:
            self.store.save()
        except StoreError:
            row.clear()
            row.update(previous)
            log.error("automation_update_draft_checkpoint_failed", session_id=sid)
            raise
        log.info("automation_update_draft_confirmed", session_id=sid)
        return result

    def dismiss(self, sid, draft_id):
        row = self._get(sid, draft_id)
        key = f"claw:{sid}:{draft_id}"
        import hashlib

        existing_id = "automation-" + hashlib.sha256(key.encode()).hexdigest()
        update = self.store.data["automations"].get(row.get("automation_id"), {})
        applied_update = any(
            revision.get("mutation_key") == key
            for revision in update.get("definition_revisions", [])
        )
        if (
            row["status"] == "confirmed"
            or existing_id in self.store.data["automations"]
            or existing_id in self.store.data.get("automation_tombstones", {})
            or applied_update
        ):
            raise StoreError("已保存任务请在 Agent 日程中管理", "draft_already_saved", 409)
        previous = row["status"]
        row["status"] = "dismissed"
        try:
            self.store.save()
        except StoreError:
            row["status"] = previous
            raise
        log.info("automation_draft_dismissed", session_id=sid)
        return copy.deepcopy(row)
