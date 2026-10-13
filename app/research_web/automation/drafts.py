"""Native schedule proposals, persisted separately from executable Automations."""

import copy
import time
from uuid import uuid4

from core.observability import get_logger

from ..store import StoreError
from .models import AutomationCreate
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
        if body.mcp_tools or body.delivery.channel_ids or body.delivery.include_attachments:
            raise StoreError("聊天日程草稿不能授予 MCP 或投递权限", "draft_permissions_denied", 409)

    def prepare(self, sid, body: AutomationCreate):
        self._session(sid)
        self._no_external_permissions(body)
        active = [row for row in self.list(sid)["items"] if row["status"] == "proposed"]
        if len(active) >= 20:
            raise StoreError("待确认日程草稿已达上限，请先处理已有草稿", "draft_limit", 409)
        resolved = self.research.automations.target_resolver(
            body.target_kind, body.target_id, body.target_version
        )
        if resolved["version"] != body.target_version or (
            body.target_sha256 is not None and body.target_sha256 != resolved["sha256"]
        ):
            raise StoreError("目标版本已变化", "target_version_conflict", 409)
        locked = body.model_copy(update={"target_sha256": resolved["sha256"]})
        row = {
            "id": f"draft-{uuid4().hex}",
            "session_id": sid,
            "status": "proposed",
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

    def confirm(self, sid, draft_id, body: AutomationCreate):
        row = self._get(sid, draft_id)
        if row["status"] == "dismissed":
            raise StoreError("日程草稿已取消", "draft_dismissed", 409)
        self._no_external_permissions(body)
        for key in ("target_kind", "target_id", "target_version", "target_sha256"):
            if getattr(body, key) != row["body"][key]:
                raise StoreError("目标锁定版本不能通过草稿编辑替换", "target_version_conflict", 409)
        if row["status"] == "confirmed":
            if body.model_dump(mode="json") != row["body"]:
                raise StoreError("确认内容与已保存任务不一致", "draft_confirmation_conflict", 409)
            try:
                return self.research.automations.get(row["automation_id"])
            except StoreError as exc:
                raise StoreError(
                    "原日程已删除，不能重新确认旧草稿", "draft_automation_deleted", 409
                ) from exc
        automation = self.research.automations.create(body, creation_key=f"claw:{sid}:{draft_id}")
        previous = copy.deepcopy(row)
        row.update(
            status="confirmed", automation_id=automation["id"], body=body.model_dump(mode="json")
        )
        try:
            self.store.save()
        except StoreError:
            row.clear()
            row.update(previous)
            log.error("automation_draft_checkpoint_failed", session_id=sid)
            raise
        log.info("automation_draft_confirmed", session_id=sid)
        return automation

    def dismiss(self, sid, draft_id):
        row = self._get(sid, draft_id)
        key = f"claw:{sid}:{draft_id}"
        import hashlib

        existing_id = "automation-" + hashlib.sha256(key.encode()).hexdigest()
        if row["status"] == "confirmed" or existing_id in self.store.data["automations"]:
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
