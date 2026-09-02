"""Research BFF: native events, safe ownership, idempotent admission, no agent loop."""

import asyncio
import base64
import hashlib
import json
import shutil
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from websockets.exceptions import WebSocketException

from core.observability import get_logger

from .client import DSHClient, RuntimeFailure
from .delivery import FINAL, Delivery, expected_formats
from .projection import project
from .store import Store, StoreError

log = get_logger(__name__)


class ResearchService:
    def __init__(
        self,
        client: DSHClient,
        store: Store,
        *,
        owned: bool = True,
        expected_cwd: Path | None = None,
        delivery_python: Path | None = None,
    ):
        self.client, self.store, self.owned = client, store, owned
        self.expected_cwd = expected_cwd
        self.delivery = Delivery(store, delivery_python)
        self.connected: set[str] = set()
        self.events: dict[str, dict[int, dict]] = {}
        self.loaded: set[str] = set()
        self.approvals: dict[str, dict] = {}
        self.questions: dict[str, dict] = {}
        self.errors: dict[str, str] = {}
        self.running: dict[str, bool] = {}
        self.child_parents: dict[str, str] = {}
        self.child_views: dict[str, tuple[float, dict]] = {}
        self.listeners: set[asyncio.Event] = set()
        self.lock = asyncio.Lock()
        self.pump = None
        self.default_model = store.data.get(
            "model", {"provider": "deepseek-official", "model": "deepseek-v4-flash"}
        )

    async def ensure_owned(self):
        if self.expected_cwd is not None:
            info = await self.client.rpc("host.describe", {})
            self.owned = info.get("cwd") == str(self.expected_cwd.resolve())
        if not self.owned:
            raise RuntimeFailure(
                "该连接不是已确认的 AlphaFoundry 专属实例，禁止修改", "read_only_runtime"
            )

    async def start(self):
        self.pump = asyncio.create_task(self._connect(), name="dsh-events")

    async def close(self):
        if self.pump:
            self.pump.cancel()
            with suppress(asyncio.CancelledError):
                await self.pump
        await self.client.close()

    def notify(self):
        for listener in self.listeners:
            listener.set()

    async def _connect(self):
        delay = 0.5
        while True:
            tasks = [asyncio.create_task(self._consume(channel)) for channel in ("mux", "host")]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            except asyncio.CancelledError:
                raise
            except (
                OSError,
                WebSocketException,
                RuntimeFailure,
                StoreError,
                ValueError,
                KeyError,
                TypeError,
            ) as exc:
                log.warning("dsh_events_disconnected", error_type=type(exc).__name__)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                self.connected.clear()
                self.loaded.clear()
                self.approvals.clear()
                self.questions.clear()
                self.child_views.clear()
                self.notify()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5)

    async def _consume(self, channel):
        async for envelope in self.client.frames(channel):
            if envelope.get("type") == "connected":
                self.connected.add(channel)
                self.notify()
                continue
            frame = envelope["payload"]
            sid = frame.get("sessionId")
            kind = frame["type"]
            owner = sid
            if sid not in self.store.data["sessions"]:
                if kind.startswith(("approval/", "question/")):
                    owner = await self._interaction_owner(sid)
                    if owner is None:
                        continue
                elif sid in self.child_parents:
                    self.notify()
                    continue
                else:
                    continue  # Never expose unowned sessions.
            if kind == "session/event":
                event = frame["event"]
                self.events.setdefault(sid, {})[event["seq"]] = {"event": event}
                if event["type"] == "turn/start":
                    self.errors.pop(sid, None)
                    self.running[sid] = True
                if event["type"] == "turn/end":
                    self.running[sid] = False
                    row = self.store.session(sid)
                    row["status"] = project(list(self.events[sid].values()))["status"]
                    row["updated_at"] = time.time()
                    self.store.save()
            elif kind == "host/session-status":
                self.running[sid] = frame["running"]
            elif kind == "host/agent-error":
                self.errors[sid] = frame["message"]
            elif kind == "approval/requested":
                self.approvals[frame["approvalId"]] = {
                    **frame,
                    "rpc_id": envelope["rpcId"],
                    "ownerSessionId": owner,
                }
            elif kind == "approval/resolved":
                self.approvals.pop(frame["approvalId"], None)
            elif kind == "question/requested":
                self.questions[envelope["rpcId"]] = {**frame, "ownerSessionId": owner}
            elif kind == "question/resolved":
                self.questions.pop(frame["questionRpcId"], None)
            self.notify()

    async def _interaction_owner(self, sid):
        if sid in self.child_parents:
            return self.child_parents[sid]
        # Pending interactions may replay before the first detail projection.
        # Resolve only via the native parent-scoped registry, never claimed IDs.
        for row in list(self.store.data["sessions"].values()):
            if not row["created"]:
                continue
            children = await self.client.rpc("subagent.list", {"parentSessionId": row["id"]})
            if any(c.get("kind") == "child" and c.get("id") == sid for c in children["entries"]):
                self.child_parents[sid] = row["id"]
                return row["id"]
        log.warning("research_unowned_interaction_ignored")
        return None

    async def runtime(self):
        try:
            info = await self.client.rpc("host.describe", {})
            if self.expected_cwd is not None:
                self.owned = info.get("cwd") == str(self.expected_cwd.resolve())
            ready = self.connected == {"mux", "host"}
            auth = await self.client.rpc(
                "credentials.describe", {"refs": ["ALPHAFOUNDRY_DSH_API_KEY"]}
            )
            configured = (
                auth.get("credentials", {})
                .get("ALPHAFOUNDRY_DSH_API_KEY", {})
                .get("configured", False)
            )
            return {
                "connected": ready,
                "provider": info.get("provider"),
                "model": self.default_model["model"],
                "version": info["version"],
                "owned_runtime": self.owned,
                "credential_configured": configured,
                "message": (
                    ("DSH 已连接" if configured else "DSH 已连接；请先在下方配置 API Key")
                    if ready
                    else "DSH 事件通道连接中"
                ),
            }
        except RuntimeFailure as exc:
            return {
                "connected": False,
                "provider": "DSH",
                "model": None,
                "version": None,
                "owned_runtime": self.owned,
                "message": str(exc),
            }

    async def configure_model(self, provider, model, api_key=None):
        await self.ensure_owned()
        async with self.lock:
            selection = {"provider": provider, "model": model}
            native = await self.client.rpc("session.list", {})
            busy = {item["sessionId"] for item in native["items"] if item["running"]}
            if api_key:
                await self.client.rpc(
                    "credentials.set", {"ref": "ALPHAFOUNDRY_DSH_API_KEY", "value": api_key}
                )
            for sid, row in self.store.data["sessions"].items():
                if row["created"] and sid not in busy:
                    await self.client.rpc("session.selectModel", {"sessionId": sid, **selection})
                    row["model"] = model
                    self.store.save()
            # Publish the default only after native selections succeeded. No
            # concurrent create/send can observe a half-written selection.
            self.store.data["model"] = selection
            self.store.save()
            self.default_model = selection
            log.info("research_model_configured", provider=provider, model=model)
            return {"configured": True}

    async def create(self, mode="fingpt", title=None):
        await self.ensure_owned()
        async with self.lock:
            row = self.store.create(mode, title or ("Claw 研究" if mode == "claw" else "新研究"))
            sid = row["id"]
            shutil.copytree(
                Path(__file__).parent / "resources",
                self.store.directory(sid) / "resources",
                ignore=shutil.ignore_patterns("__pycache__"),
                dirs_exist_ok=True,
            )
            shutil.copytree(
                Path(__file__).parent / "skills",
                self.store.directory(sid) / "resources" / "skills",
                ignore=shutil.ignore_patterns("__pycache__"),
                dirs_exist_ok=True,
            )
            try:
                await self.client.rpc(
                    "session.create",
                    {
                        "sessionId": sid,
                        "cwd": str(self.store.directory(sid)),
                        "agentPreset": "alphafoundry-research",
                    },
                )
                row["created"] = True
                row["model"] = self.default_model["model"]
                await self.client.rpc(
                    "session.selectModel", {"sessionId": sid, **self.default_model}
                )
                await self.client.rpc("session.rename", {"sessionId": sid, "title": row["title"]})
                self.store.save()
            except RuntimeFailure:
                row["status"] = "failed"
                self.store.save()
                raise
            return self.summary(row)

    @staticmethod
    def summary(row):
        result = {
            key: row[key]
            for key in ("id", "mode", "title", "workspace_id", "status", "model", "updated_at")
        }
        if isinstance(result["updated_at"], (int, float)):
            result["updated_at"] = datetime.fromtimestamp(result["updated_at"], UTC).isoformat()
        return result

    async def list_sessions(self):
        rows = sorted(
            self.store.data["sessions"].values(), key=lambda row: row["updated_at"], reverse=True
        )
        native = await self.client.rpc("session.list", {})
        running = {item["sessionId"]: item["running"] for item in native["items"]}
        results = []
        for row in rows:
            result = self.summary(row)
            children = (
                await self.client.rpc("subagent.list", {"parentSessionId": row["id"]})
                if row["created"]
                else {"entries": []}
            )
            child_running = any(child.get("activity") == "running" for child in children["entries"])
            if running.get(row["id"]) or child_running:
                result["status"] = "running"
            elif result["status"] == "running":
                # Recover completion during BFF downtime from the authoritative log.
                self.loaded.discard(row["id"])
                detail = await self.detail(row["id"])
                result["status"] = detail["status"]
            results.append(result)
        return results

    async def detail(self, sid):
        row = self.store.session(sid)
        if not row["created"]:
            raise RuntimeFailure("该会话未成功创建，请新建研究", "session_create_failed")
        if sid not in self.loaded:
            entries = await self.client.history(sid)
            native = await self.client.rpc("session.list", {})
            self.running[sid] = any(
                item["sessionId"] == sid and item["running"] for item in native["items"]
            )
            cache = self.events.setdefault(sid, {})
            cache.update({entry["event"]["seq"]: entry for entry in entries})
            self.loaded.add(sid)
        result = {**self.summary(row), **project(list(self.events.get(sid, {}).values()))}
        # Native logs retain the execution contract. Only its product-owned
        # suffix is hidden in the human transcript, including after reload.
        markers = {
            receipt["delivery"]["marker"]
            for key, receipt in self.store.data["receipts"].items()
            if key.startswith(sid + ":") and receipt.get("delivery")
        }
        for message in result["messages"]:
            if message["role"] == "user":
                boundary = max(
                    (message["text"].rfind("\n\n" + marker) for marker in markers), default=-1
                )
                if boundary >= 0:
                    message["text"] = message["text"][:boundary]
        if self.running.get(sid):
            result["status"] = "running"
        elif result["status"] == "running":
            result.update(
                status="interrupted", error="原生执行已不在运行，但历史未记录完成；请补充指令继续"
            )
        if sid in self.errors:
            result.update(status="failed", error=self.errors[sid])
        result["files"] = self.store.files(sid)
        result["approvals"] = [
            {"id": key, "title": value["toolName"], "detail": value.get("reason", "需要授权")}
            for key, value in self.approvals.items()
            if value.get("ownerSessionId", value["sessionId"]) == sid
        ]
        result["questions"] = [
            {
                "id": key,
                "text": "\n\n".join(question["question"] for question in value["questions"]),
                "items": value["questions"],
            }
            for key, value in self.questions.items()
            if value.get("ownerSessionId", value["sessionId"]) == sid
        ]
        if result["approvals"]:
            result["status"] = "awaiting_approval"
        children = await self.client.rpc("subagent.list", {"parentSessionId": sid})
        result["subagents"] = []
        for child in children["entries"]:
            view = {
                "id": child["id"],
                "name": child.get("label", child["id"]),
                "status": child.get("reason", "unknown"),
            }
            if child["kind"] == "child":
                self.child_parents[child["id"]] = sid
                try:
                    cached = self.child_views.get(child["id"])
                    if cached and time.monotonic() - cached[0] < 1:
                        projection = cached[1]
                    else:
                        page = await self.client.rpc(
                            "subagent.history",
                            {
                                "parentSessionId": sid,
                                "childSessionId": child["id"],
                                "mode": child["mode"],
                                "maxMessages": 100,
                            },
                        )
                        projection = {
                            **project(page["events"]),
                            "history_truncated": page.get("hasMore", False),
                        }
                        self.child_views[child["id"]] = (time.monotonic(), projection)
                    view.update(
                        status=(
                            "running" if child["activity"] == "running" else projection["status"]
                        ),
                        usage=projection["usage"],
                        duration_ms=projection.get("duration_ms"),
                        error=projection.get("error"),
                        history_truncated=projection["history_truncated"],
                    )
                    result["activities"].extend(
                        {
                            **activity,
                            "id": f"{child['id']}:{activity['id']}",
                            "agent_id": child["id"],
                        }
                        for activity in projection["activities"]
                    )
                except RuntimeFailure as exc:
                    view.update(status="unavailable", error=str(exc))
            result["subagents"].append(view)
        child_running = any(child.get("activity") == "running" for child in children["entries"])
        result["can_cancel"] = bool(self.running.get(sid) or child_running)
        if child_running and not result["approvals"]:
            result["status"] = "running"
        if self.connected != {"mux", "host"}:
            result.update(
                status="disconnected", error="DSH 事件连接已断开；未重发请求，也未判定任务完成"
            )
        result["delivery"] = await self.delivery.refresh(
            sid,
            list(self.events.get(sid, {}).values()),
            busy=result["can_cancel"],
            connected=self.connected == {"mux", "host"},
        )
        return result

    async def send(self, sid, text, key, attachments=(), skill_id=None, formats=None):
        await self.ensure_owned()
        async with self.lock:
            row = self.store.session(sid)
            if not row["created"]:
                raise StoreError("会话尚未创建")
            required = expected_formats(formats, skill_id)
            payload = {
                "text": text,
                "attachments": list(attachments),
                "skill": skill_id,
                "expected_formats": required,
            }
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if f"{sid}:{key}" in self.store.data["receipts"]:
                self.store.reserve(sid, key, digest)
                if self.store.receipt(sid, key)["status"] == "accepted":
                    return {"accepted": True}
                raise RuntimeFailure(
                    "此请求受理结果未知；请检查会话历史，不要重复发送", "admission_unknown"
                )
            if self.connected != {"mux", "host"}:
                raise RuntimeFailure("DSH 事件未连接，暂不提交问题")
            current = await self.detail(sid)
            native = await self.client.rpc("session.list", {})
            busy = current["can_cancel"] or any(
                item["sessionId"] == sid and item["running"] for item in native["items"]
            )
            if busy or (current["delivery"] and current["delivery"]["status"] not in FINAL):
                raise RuntimeFailure(
                    "上一任务或子 Agent 尚未结束，或交付/受理结果未确认；请先等待并刷新，不要重复提交",
                    "delivery_pending",
                )
            files = [
                self.store.file_path(sid, fid).relative_to(self.store.directory(sid)).as_posix()
                for fid in attachments
            ]
            images = []
            image_bytes = 0
            media = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }
            for fid, filename in zip(attachments, files, strict=True):
                mime = media.get(Path(filename).suffix.lower())
                if mime:
                    stream, name = self.store.open_file(sid, fid)
                    with stream:
                        raw = stream.read(8 * 1024 * 1024 + 1)
                    image_bytes += len(raw)
                    if len(raw) > 8 * 1024 * 1024 or image_bytes > 16 * 1024 * 1024:
                        raise StoreError("单张图片最多 8 MB，每条消息图片合计最多 16 MB")
                    images.append(
                        {
                            "type": "image",
                            "mediaType": mime,
                            "name": name,
                            "data": base64.b64encode(raw).decode("ascii"),
                        }
                    )
            if skill_id:
                skills = await self.skill_catalog(sid)
                if skill_id not in {skill["name"] for skill in skills["skills"]}:
                    raise StoreError("Skill 未由 DSH 原生加载")
            delivery = self.delivery.begin(sid, key, required)
            if not self.store.reserve(sid, key, digest, delivery):
                status = self.store.receipt(sid, key)["status"]
                if status == "accepted":
                    return {"accepted": True}
                raise RuntimeFailure(
                    "此请求受理结果未知；请检查会话历史，不要重复发送", "admission_unknown"
                )
            prompt = text
            prompt += "\n\n" + delivery["marker"]
            if formats is not None:
                prompt += "\n用户显式选择的输出格式优先于 Skill 默认格式。"
                if not required:
                    prompt += "本次无需文件，直接在聊天中回答。"
            if required:
                prompt += (
                    "\n本任务文件交付要求："
                    + "、".join(required)
                    + "。必须在本次执行中新建或更新 outputs/ 下的实际文件；"
                    "聊天正文、inputs 附件和历史未修改文件不算交付。"
                    "Office 文件必须重开并有实际内容；Excel 至少包含表头与数据行。"
                    "仅使用已可用的严格沙箱工具生成，不虚构文件、数据或验证。"
                )
            if files:
                prompt += "\n\n附件（仅本会话 inputs 目录）：\n" + "\n".join(files)
            if row["mode"] == "claw":
                prompt += (
                    "\n\n使用 DSH 原生子 Agent 分工研究；只使用实际可用工具，不虚构执行或产物。"
                )
            if skill_id:
                prompt = f"/{skill_id} " + prompt
            try:
                result = await self.client.rpc(
                    "session.prompt",
                    {
                        "sessionId": sid,
                        "mode": "queue",
                        "content": [{"type": "text", "text": prompt}, *images],
                        "clientTimeZone": "Asia/Shanghai",
                    },
                )
                self.store.receipt(sid, key, "accepted")
                row.update(updated_at=time.time(), status="running")
                self.store.save()
                self.running[sid] = True
                self.errors.pop(sid, None)
                self.notify()
                log.info("research_prompt_admitted", session_id=sid)
                return result
            except RuntimeFailure:
                self.store.receipt(sid, key, "unknown")
                raise

    async def skill_catalog(self, sid):
        await self.ensure_owned()
        self.store.session(sid)
        # skill.list addresses only attached native sessions. models invokes
        # DSH's recorded-preset cold resume without submitting another prompt.
        await self.client.rpc("session.models", {"sessionId": sid})
        return await self.client.rpc("skill.list", {"sessionId": sid})

    async def approve(self, sid, aid, decision):
        await self.ensure_owned()
        self.store.session(sid)
        request = self.approvals.get(aid)
        if not request or request.get("ownerSessionId", request["sessionId"]) != sid:
            raise StoreError("审批已失效或不属于该会话")
        log.info("research_approval_response", decision=decision)
        return await self.client.respond(
            request["rpc_id"],
            {
                "sessionId": request["sessionId"],
                "approvalId": aid,
                "outcome": "allowed-once" if decision == "approve" else "rejected",
            },
        )

    async def cancel(self, sid):
        await self.ensure_owned()
        self.store.session(sid)
        try:
            result = await self.client.rpc("session.cancel", {"sessionId": sid})
        except RuntimeFailure as exc:
            if exc.code != "session-not-found":
                raise
            log.info("research_cancel_parent_offline", session_id=sid)
            result = {"accepted": True}
        children = await self.client.rpc("subagent.list", {"parentSessionId": sid})
        for child in children["entries"]:
            if child.get("kind") == "child" and child.get("mode") == "continuable":
                await self.client.rpc(
                    "subagent.interrupt",
                    {"parentSessionId": sid, "childSessionId": child["id"], "mode": "continuable"},
                )
        self.notify()
        return result

    async def answer(self, sid, qid, answers):
        await self.ensure_owned()
        self.store.session(sid)
        request = self.questions.get(qid)
        if not request or request.get("ownerSessionId", request["sessionId"]) != sid:
            raise StoreError("提问已失效或不属于该会话")
        expected = {question["id"] for question in request["questions"]}
        if {answer["id"] for answer in answers} != expected or len(answers) != len(expected):
            raise StoreError("请完整回答该组问题")
        questions = {question["id"]: question for question in request["questions"]}
        for answer in answers:
            if (
                questions[answer["id"]].get("multiSelect") is not True
                and len(answer.get("selected", [])) > 1
            ):
                log.warning("research_question_single_selection_rejected")
                raise StoreError("单选问题只能选择一个选项")
        return await self.client.respond(
            qid, {"sessionId": request["sessionId"], "answer": {"answers": answers}}
        )
