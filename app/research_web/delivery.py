"""File delivery metadata and strict sandbox validation, separate from DSH execution."""

import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

from core.observability import get_logger

from . import sandbox
from .client import RuntimeFailure
from .projection import content_text
from .store import StoreError

log = get_logger(__name__)
FORMATS = ("md", "html", "docx", "xlsx", "png")
SKILL_DEFAULTS = {
    "fund-evaluation": ["docx", "html", "xlsx"],
    "company-research": ["docx", "html", "xlsx"],
    "industry-research": ["docx", "html", "xlsx"],
}
FINAL = {"completed", "incomplete", "not_required", "verification_failed"}


def expected_formats(explicit, skill_id):
    formats = explicit if explicit is not None else SKILL_DEFAULTS.get(skill_id, [])
    if any(value not in FORMATS for value in formats):
        raise StoreError("不支持的交付格式")
    return list(dict.fromkeys(formats))


class Delivery:
    def __init__(self, store, python=None):
        self.store = store
        self.config = sandbox.SandboxConfig(store.root, Path(python or sys.executable))
        self.locks: dict[str, asyncio.Lock] = {}

    def snapshot(self, sid):
        items: dict[str, dict] = {}
        for item in self.store.files(sid):
            extension = Path(item["name"]).suffix.lower().lstrip(".")
            if item["kind"] != "outputs" or extension not in FORMATS:
                continue
            if len(items) >= 100:
                raise StoreError("交付检查最多支持每会话 100 个输出文件")
            row = {
                **item,
                "format": extension,
                "path": self.store.session(sid)["files"][item["id"]],
            }
            try:
                stream, _ = self.store.open_file(sid, item["id"])
                with stream:
                    raw = stream.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise StoreError("文件超过 16 MiB 验证上限")
                row["sha256"] = hashlib.sha256(raw).hexdigest()
            except (OSError, StoreError) as exc:
                log.warning("research_delivery_snapshot_denied", error_type=type(exc).__name__)
                row.update(sha256=None, reason="文件无法安全读取或超过 16 MiB 上限", valid=False)
            items[item["id"]] = row
        return items

    def current(self, sid):
        key = self.store.session(sid).get("delivery_key")
        return self.store.receipt(sid, key).get("delivery") if key else None

    def begin(self, sid, key, formats):
        task = hashlib.sha256(f"{sid}:{key}".encode()).hexdigest()[:24]
        before = self.snapshot(sid) if formats else {}
        return {
            "task_id": task,
            "marker": f"[RESEARCH_TASK:{task}]",
            "status": "pending",
            "required_formats": formats,
            "missing_formats": formats.copy(),
            "files": [],
            "reasons": [],
            "baseline": {fid: row["sha256"] for fid, row in before.items()},
        }

    @staticmethod
    def public(delivery):
        return {
            key: value
            for key, value in delivery.items()
            if key not in {"baseline", "marker", "cancel_request"}
        }

    async def reconcile_cancel(self, sid, client, ready):
        """Explicit task-scoped cancellation may fail closed, never fabricate turn/end."""
        async with self.locks.setdefault(sid, asyncio.Lock()):
            delivery = self.current(sid)
            if not delivery or delivery["status"] in FINAL or not ready():
                return None
            key = self.store.session(sid)["delivery_key"]
            request = delivery.get("cancel_request", {})
            if (
                self.store.receipt(sid, key)["status"] != "accepted"
                or request.get("accepted") is not True
                or request.get("key") != key
                or request.get("task_id") != delivery["task_id"]
                or request.get("marker") != delivery["marker"]
            ):
                return None
            try:
                entries = await client.history(sid)
                native = await client.rpc("session.list", {})
                children = await client.rpc("subagent.list", {"parentSessionId": sid})
                parents = [item for item in native["items"] if item.get("sessionId") == sid]
                messages = [
                    entry["event"] for entry in entries if entry["event"]["type"] == "user/message"
                ]
                markers = [
                    event
                    for event in messages
                    if delivery["marker"] in content_text(event["data"].get("content"))
                ]
                if (
                    not ready(entries)
                    or native.get("diagnostics")
                    or len(parents) != 1
                    or parents[0].get("running") is not False
                    or children.get("parentAvailable") is not True
                    or any(
                        child.get("kind") != "child" or child.get("activity") != "inactive"
                        for child in children["entries"]
                    )
                    or len(markers) != 1
                    or any(event["seq"] > markers[0]["seq"] for event in messages)
                    or self.current(sid) is not delivery
                    or self.store.session(sid)["delivery_key"] != key
                ):
                    return None
                ended = any(
                    entry["event"]["type"] == "turn/end"
                    and entry["event"]["seq"] > markers[0]["seq"]
                    for entry in entries
                )
                if not ended:
                    delivery.update(
                        status="verification_failed",
                        failure_code="cancel_terminal_event_missing",
                        reasons=[
                            "停止请求已受理且父子任务均已空闲，但原生终止事件缺失；结果未确认，未执行文件校验。可提交新的研究请求。"
                        ],
                        files=[],
                        missing_formats=delivery["required_formats"].copy(),
                        checked_at=time.time(),
                    )
                    self.store.save()
                    log.warning(
                        "research_cancel_terminal_missing",
                        session_id=sid,
                        task_id=delivery["task_id"],
                    )
                return entries
            except (RuntimeFailure, KeyError, TypeError, ValueError) as exc:
                log.warning("research_cancel_recheck_uncertain", error_type=type(exc).__name__)
                return None

    async def refresh(self, sid, entries, *, busy, connected):
        async with self.locks.setdefault(sid, asyncio.Lock()):
            delivery = self.current(sid)
            if not delivery:
                return None
            if delivery["status"] in FINAL:
                return self.public(delivery)
            key = self.store.session(sid)["delivery_key"]
            receipt = self.store.receipt(sid, key)
            marker_seq = next(
                (
                    entry["event"]["seq"]
                    for entry in entries
                    if entry["event"]["type"] == "user/message"
                    and delivery["marker"] in content_text(entry["event"]["data"].get("content"))
                ),
                None,
            )
            ended = marker_seq is not None and any(
                entry["event"]["type"] == "turn/end" and entry["event"]["seq"] > marker_seq
                for entry in entries
            )
            if busy or not connected or not ended:
                status = (
                    "admission_unknown"
                    if receipt["status"] in {"pending", "unknown"}
                    else "pending"
                )
                delivery["status"] = status
                return self.public(delivery)
            if receipt["status"] != "accepted":
                receipt["status"] = (
                    "accepted"  # Recovered from this exact native marker; no replay.
                )
            try:
                if not delivery["required_formats"]:
                    delivery["status"] = "not_required"
                else:
                    files = [
                        row
                        for fid, row in self.snapshot(sid).items()
                        if fid not in delivery["baseline"]
                        or row["sha256"] != delivery["baseline"][fid]
                    ]
                    delivery["files"] = files
                    candidates = [row for row in files if row.get("sha256")]
                    if candidates:
                        parser = Path(__file__).with_name("delivery_validation.py").read_text()
                        manifest = [
                            {key: row[key] for key in ("id", "path", "sha256", "format")}
                            for row in candidates
                        ]
                        code = "CANDIDATES = " + repr(json.dumps(manifest)) + "\n" + parser
                        result = await asyncio.to_thread(
                            sandbox.run_script, self.config, self.store.directory(sid), code
                        )
                        if result.status != "completed":
                            raise StoreError("严格沙箱验证未完成：" + result.status)
                        checks = json.loads(result.stdout)
                        if not isinstance(checks, list) or len(checks) != len(candidates):
                            raise StoreError("沙箱验证响应不完整")
                        for item, check in zip(candidates, checks, strict=True):
                            if (
                                check["id"] != item["id"]
                                or check["sha256"] != item["sha256"]
                                or not isinstance(check["valid"], bool)
                            ):
                                raise StoreError("沙箱验证响应与文件快照不匹配")
                            item.update(valid=check["valid"], reason=check["reason"])
                        # Parser success refers to its byte snapshot, not a later path.
                        # Re-open safely before publishing; do not parse on the host.
                        for item in candidates:
                            if not item.get("valid"):
                                continue
                            try:
                                stream, _ = self.store.open_file(sid, item["id"])
                                with stream:
                                    raw = stream.read(16 * 1024 * 1024 + 1)
                                if (
                                    len(raw) != item["size"]
                                    or hashlib.sha256(raw).hexdigest() != item["sha256"]
                                ):
                                    raise StoreError("交付文件在解析后发生变化")
                            except (OSError, StoreError) as exc:
                                log.warning(
                                    "research_delivery_publish_recheck_failed",
                                    error_type=type(exc).__name__,
                                )
                                item.update(
                                    valid=False,
                                    reason="文件在解析后发生变化、消失或无法安全读取，未确认交付",
                                )
                    valid = {row["format"] for row in files if row.get("valid")}
                    delivery["missing_formats"] = [
                        fmt for fmt in delivery["required_formats"] if fmt not in valid
                    ]
                    delivery["reasons"] = [
                        f"缺少本任务新建/更新且有效的 {fmt.upper()} 文件"
                        for fmt in delivery["missing_formats"]
                    ]
                    delivery["status"] = (
                        "incomplete" if delivery["missing_formats"] else "completed"
                    )
            except (OSError, ValueError, StoreError, KeyError, TypeError) as exc:
                log.warning("research_delivery_check_failed", error_type=type(exc).__name__)
                delivery.update(
                    status="verification_failed",
                    reasons=["交付验证失败；严格沙箱不可用、文件过多或检查结果不完整"],
                )
            delivery["checked_at"] = time.time()
            self.store.save()
            log.info(
                "research_delivery_checked",
                status=delivery["status"],
                formats=len(delivery["required_formats"]),
            )
            return self.public(delivery)
