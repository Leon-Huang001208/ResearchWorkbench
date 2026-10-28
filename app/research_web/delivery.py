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
FORMATS = ("md", "html", "docx", "xlsx", "pptx", "png", "pdf")
SKILL_DEFAULTS = {
    "fund-evaluation": ["docx", "html", "xlsx"],
    "company-research": ["docx", "html", "xlsx"],
    "industry-research": ["docx", "html", "xlsx"],
}
FINAL = {"completed", "incomplete", "not_required", "verification_failed"}


def accepted_task_cancel(receipt, delivery, key, *, task_id=None):
    """Pure server task identity; pending/foreign cancellations grant nothing."""
    if not isinstance(receipt, dict) or not isinstance(delivery, dict):
        return False
    request = delivery.get("cancel_request", {})
    return (
        isinstance(request, dict)
        and isinstance(key, str)
        and bool(key)
        and isinstance(delivery.get("task_id"), str)
        and bool(delivery["task_id"])
        and isinstance(delivery.get("marker"), str)
        and bool(delivery["marker"])
        and receipt.get("status") == "accepted"
        and request.get("accepted") is True
        and request.get("key") == key
        and request.get("task_id") == delivery.get("task_id")
        and request.get("marker") == delivery.get("marker")
        and (task_id is None or task_id == delivery.get("task_id"))
    )


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
            relative = self.store.session(sid)["files"].get(item["id"], "")
            if (
                item["kind"] != "outputs"
                or extension not in FORMATS
                or Path(relative).parts[:2] == ("outputs", "report-versions")
            ):
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

    def _candidates(self, sid, delivery):
        return [
            row
            for fid, row in self.snapshot(sid).items()
            if fid not in delivery["baseline"] or row["sha256"] != delivery["baseline"][fid]
        ]

    @staticmethod
    def _signature(files):
        return sorted((row["id"], row["path"], row.get("sha256"), row["format"]) for row in files)

    def _unverified_scope(self, delivery):
        return self.public(
            {
                **delivery,
                "status": "verification_failed",
                "files": [],
                "missing_formats": delivery["required_formats"].copy(),
                "failure_code": "delivery_scope_unconfirmed",
                "reasons": ["交付任务归属未确认，旧回执不代表当前任务"],
            }
        )

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
            if not accepted_task_cancel(self.store.receipt(sid, key), delivery, key):
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

    async def refresh(self, sid, entries, *, busy, connected, key=None):
        async with self.locks.setdefault(sid, asyncio.Lock()):
            key = key or self.store.session(sid).get("delivery_key")
            receipt = self.store.data["receipts"].get(f"{sid}:{key}", {})
            delivery = receipt.get("delivery")
            if not delivery:
                return None
            if self.store.session(sid).get("delivery_key") != key:
                log.warning("research_delivery_scope_unconfirmed")
                return self._unverified_scope(delivery)
            current_candidates = None
            if delivery["status"] in FINAL:
                if (
                    delivery["status"] not in {"completed", "incomplete", "verification_failed"}
                    or delivery.get("failure_code")
                    or not delivery["required_formats"]
                ):
                    return self.public(delivery)
                try:
                    current_candidates = self._candidates(sid, delivery)
                except (OSError, ValueError, StoreError, KeyError, TypeError) as exc:
                    log.warning(
                        "research_delivery_final_snapshot_failed", error_type=type(exc).__name__
                    )
                    delivery.update(
                        status="verification_failed",
                        reasons=["当前输出不能安全核验；旧交付回执已失效"],
                    )
                    self.store.save()
                    return self.public(delivery)
                if self._signature(current_candidates) == self._signature(delivery["files"]):
                    return self.public(delivery)
                log.info("research_delivery_outputs_changed")
                delivery["status"] = "pending"
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
                    files = (
                        current_candidates
                        if current_candidates is not None
                        else self._candidates(sid, delivery)
                    )
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
                        if self.store.data["sessions"].get(sid, {}).get("delivery_key") != key:
                            log.warning("research_delivery_scope_changed_during_validation")
                            return self._unverified_scope(delivery)
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
                    if self._signature(self._candidates(sid, delivery)) != self._signature(files):
                        log.warning("research_delivery_manifest_changed_during_validation")
                        for item in files:
                            if item.get("valid"):
                                item.update(
                                    valid=False,
                                    reason="输出集合或字节在严格验证期间变化，未确认交付",
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
            if self.store.data["sessions"].get(sid, {}).get("delivery_key") != key:
                log.warning("research_delivery_scope_changed_before_publish")
                return self._unverified_scope(delivery)
            delivery["checked_at"] = time.time()
            self.store.save()
            log.info(
                "research_delivery_checked",
                status=delivery["status"],
                formats=len(delivery["required_formats"]),
            )
            return self.public(delivery)
