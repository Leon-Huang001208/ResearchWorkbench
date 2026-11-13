"""AlphaDesk turn ownership, recovery and Research Web projections."""

import asyncio
import json
import os
import time

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import admission

from . import qa_model
from .client import RuntimeFailure
from .datahub.security import atomic_json, directory, read_file
from .projection import project
from .qa_attachments import with_turn_images
from .qa_bridge import run_worker
from .qa_tools import TurnTools
from .research_evidence import evidence_index
from .research_quality_service import (
    check_quality,
    latest_receipt,
    quality_result,
    quality_versions,
    report_delivery,
)
from .research_web_sources import stored_sources, upload_evidence_files
from .store import StoreError

log = get_logger(__name__)
ENGINE = "alphadesk"
MODES = {"quick", "deep", "agent"}
MAX_LEDGER = 4 * 1024 * 1024


def enabled(service):
    return not service.service_only and os.environ.get("RWB_ALPHADESK_QA") == "1"


def owns(row):
    return row.get("execution_engine") == ENGINE


def retired(service, row):
    return (
        enabled(service)
        and row["mode"] == "fingpt"
        and row.get("research_mode") != "specialist"
        and not owns(row)
    )


def bind(service, row, selection):
    row.update(
        execution_engine=ENGINE,
        created=True,
        model=selection["model"],
        model_provider=selection["provider"],
        model_profile_id=service.model_profile_identity(selection["provider"]),
    )
    if selection["provider"] == "openai-compatible":
        config = service.compatible_connection()
        row["model_connection_binding"] = {
            field: config[field] for field in ("base_url", "protocol", "credential_mode")
        }


class QuestionExecution:
    def __init__(self, service):
        self.service = service
        self.store = service.store
        self.tasks = {}
        self.cache = {}

    def ledger(self, sid):
        if sid not in self.cache:
            root = self.store.directory(sid)
            if not (root / ".control" / "qa.json").exists():
                return {"events": [], "messages": [], "key": None, "status": "idle"}
            with directory(root, (".control",), private=True) as folder:
                value = json.loads(read_file(folder, "qa.json", private=True, limit=MAX_LEDGER))
            if not isinstance(value, dict) or set(value) != {"events", "messages", "key", "status"}:
                raise StoreError("问答记录不可读", "qa_ledger_invalid", 409)
            self.cache[sid] = value
        return self.cache[sid]

    def persist(self, sid, ledger):
        root = self.store.directory(sid)
        if len(json.dumps(ledger, ensure_ascii=False).encode()) > MAX_LEDGER - 16384:
            raise StoreError("问答记录容量已满，请新建会话", "qa_history_limit", 409)
        with directory(root, (".control",), create=True, private=True) as folder:
            atomic_json(folder, "qa.json", ledger)
        self.cache[sid] = ledger

    @staticmethod
    def add(ledger, event, data):
        events = ledger["events"]
        events.append({"seq": len(events) + 1, "event": event, "data": data})

    def check_admission(self, sid):
        if not enabled(self.service):
            raise RuntimeFailure("AI 问答尚未启用", "qa_disabled")
        ledger = self.ledger(sid)
        if len(self.tasks) >= 2:
            raise StoreError("当前账号已有两条问答任务", "qa_concurrency_limit", 409)
        if sid in self.tasks or ledger["status"] == "running":
            raise StoreError("会话有未结束的任务", "session_busy", 409)
        if len(ledger["messages"]) >= 80:
            raise StoreError("问答已达到会话轮次上限，请新建会话", "qa_history_limit", 409)
        if len(json.dumps(ledger, ensure_ascii=False).encode()) > MAX_LEDGER // 2:
            raise StoreError("问答记录容量已满，请新建会话", "qa_history_limit", 409)
        return ledger

    async def start(self, sid, key, text, mode, prompt, attachment_ids, connection, images):
        ledger = self.check_admission(sid)
        history = []
        for message in reversed(ledger["messages"][-12:]):
            if len(json.dumps([message, *history], ensure_ascii=False).encode()) > 256000:
                break
            history.insert(0, message)
        request = {
            "mode": mode,
            "question": text,
            "history": history,
            "framework": {"name": "RWB 本轮研究合同", "text": prompt},
        }
        ledger = {
            **ledger,
            "events": ledger["events"].copy(),
            "messages": [*ledger["messages"], {"role": "user", "content": text}],
            "key": key,
            "status": "running",
        }
        self.add(ledger, "question", {"content": text, "mode": mode})
        self.persist(sid, ledger)
        row = self.store.session(sid)
        row.update(status="running", updated_at=time.time())
        self.store.receipt(sid, key, "accepted")
        self.tasks[sid] = asyncio.create_task(
            self.run(sid, key, ledger, request, attachment_ids, connection, images)
        )
        self.service.notify()
        log.info("research_qa_admitted", session_id=sid, mode=mode)
        return {"accepted": True}

    async def run(self, sid, key, ledger, request, attachment_ids, connection, images):
        answer, last_save = [], time.monotonic()
        receipt = self.store.receipt(sid, key)
        turn = TurnTools(self.service, sid, receipt, attachment_ids)
        status, code = "failed", None

        async def event(name, data):
            nonlocal last_save
            if name in {"_cot", "question", "task_end"} or (
                name == "update" and data.get("id") == "sub_question_cot"
            ):
                return
            if name == "update" and data.get("id") == "_qa_retract":
                answer.clear()
            if name == "_qa" and isinstance(data.get("content"), str):
                answer.append(data["content"])
                if len(answer) > 1 and ledger["events"][-1]["event"] == "_qa":
                    ledger["events"][-1]["data"]["content"] += data["content"]
                else:
                    self.add(ledger, name, data)
            else:
                self.add(ledger, name, data)
            now = time.monotonic()
            if len(json.dumps(ledger["events"][-1], ensure_ascii=False).encode()) > 300000:
                raise ValueError("qa_event_limit")
            if now - last_save >= 0.5:
                self.persist(sid, ledger)
                last_save = now
                self.service.notify()

        try:
            request["tools"] = turn.schemas()
            with admission():
                async with qa_model.model_client() as client:

                    async def model(params, emit):
                        if images:
                            params = with_turn_images(params, images)
                        result = await qa_model.stream_model(client, connection, params, emit)
                        if (
                            receipt.get("qa_capability_inputs")
                            and "qa_dispatched_capabilities" not in receipt
                        ):
                            receipt["qa_dispatched_capabilities"] = receipt["qa_capability_inputs"]
                            self.store.save()
                        return result

                    await run_worker(request, {"model": model, "tool": turn.call}, event)
            if not "".join(answer).strip():
                raise ValueError("qa_empty_answer")
            status = "completed"
        except asyncio.CancelledError:
            status, code = "cancelled", "qa_cancelled"
            try:
                await self.service.datahub.cancel(sid)
            except Exception as exc:  # noqa: BLE001 - background task boundary
                status, code = "interrupted", "qa_cancel_unverified"
                log.error("research_qa_cancel_failed", error_type=type(exc).__name__)
        except Exception as exc:  # noqa: BLE001 - background task boundary
            code = "qa_execution_failed"
            log.warning("research_qa_turn_failed", session_id=sid, error_type=type(exc).__name__)
        try:
            if status == "completed":
                ledger["messages"].append({"role": "assistant", "content": "".join(answer)})
            row = self.store.session(sid)
            if status in {"failed", "cancelled"}:
                receipt["delivery"].update(
                    status="verification_failed",
                    failure_code=code,
                    reasons=["本次执行已结束，未确认交付"],
                )
            elif status == "completed":
                ledger["status"] = "completed"
                await self.delivery(sid, ledger)
                if receipt["delivery"]["required_formats"]:
                    await check_quality(self.service, sid, detail_reader=self.finalizing_detail)
            ledger["status"] = status
            self.add(ledger, "task_end", {"status": status, **({"code": code} if code else {})})
            self.persist(sid, ledger)
            row.update(status=status, updated_at=time.time())
            self.store.save()
        except Exception as exc:  # noqa: BLE001 - background task boundary
            log.error("research_qa_finalize_failed", session_id=sid, error_type=type(exc).__name__)
            ledger["status"] = "interrupted"
            receipt["delivery"].update(
                status="verification_failed",
                failure_code="qa_finalization_unverified",
                reasons=["本次输出或回执尚未核对，请新建会话"],
            )
            row = self.store.session(sid)
            row["status"] = "interrupted"
            self.store.save()
        finally:
            self.tasks.pop(sid, None)
            self.service.notify()

    async def delivery(self, sid, ledger):
        receipt = latest_receipt(self.service, sid)
        delivery = receipt.get("delivery")
        if not delivery:
            return None
        return await self.service.delivery.refresh(
            sid,
            [],
            busy=sid in self.tasks and ledger["status"] == "running",
            connected=True,
            host_turn_ended=ledger["status"] == "completed"
            and ledger["key"] == self.store.session(sid).get("delivery_key"),
        )

    async def cancel(self, sid):
        task = self.tasks.get(sid)
        if task is None:
            raise StoreError("当前没有可停止的问答", "qa_not_running", 409)
        if self.ledger(sid)["status"] != "running":
            raise StoreError("正在核验本轮交付", "qa_finalizing", 409)
        if not task.done() and not task.cancelling():
            task.cancel()
        return {"accepted": True}

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            if not task.cancelling():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def status(self, sid):
        row = self.store.session(sid)
        if sid in self.tasks:
            return "running"
        if row["status"] in {"running", "interrupted"} or self.ledger(sid)["status"] == "running":
            return "interrupted"
        return self.ledger(sid)["status"]

    async def finalizing_detail(self, sid):
        return await self.detail(sid, finalizing=True)

    async def detail(self, sid, *, finalizing=False):
        service = self.service
        row = self.store.session(sid)
        ledger = self.ledger(sid)
        status = ledger["status"] if finalizing else self.status(sid)
        files, datasets = self.store.files(sid), service.datahub.summaries(sid)
        sources = {
            source["id"]: source
            for source in evidence_index(
                upload_evidence_files(self.store, sid, files), datasets, []
            )
        }
        receipt = latest_receipt(service, sid)
        for identifier in receipt.get("qa_acquired_sources", {}):
            source = sources.get(identifier)
            if source and source.get("dataset_id"):
                manifest = service.datahub.detail(sid, source["dataset_id"])
                source["sha256"] = manifest["manifest_sha256"]
        sources.update({source["id"]: source for source in row.get("web_search_sources", [])})
        sources.update({source["id"]: source for source in stored_sources(self.store, sid)})
        sources.update(
            {source["id"]: source for source in service.dossiers.registered_sources(sid)}
        )
        delivery = await self.delivery(sid, ledger)
        result = {
            **project([]),
            **service.summary(row),
            "purpose": row.get("purpose", "research"),
            "status": status,
            "can_cancel": status == "running",
            "can_recheck_stop": False,
            "qa_events": ledger["events"],
            "messages": [
                {"id": f"qa-message-{index}", "role": message["role"], "text": message["content"]}
                for index, message in enumerate(ledger["messages"])
            ],
            "files": files,
            "datasets": datasets,
            "research_sources": list(sources.values()),
            "delivery": delivery,
            "execution_status": status,
        }
        if status != "running" and receipt.get("research_contract"):
            quality = await asyncio.to_thread(
                quality_result, service, sid, receipt, files, result["research_sources"], delivery
            )
            report = quality.pop("report", None)
            bound = report_delivery(service, sid, receipt, (report or {}).get("content_sha256"))
            result.update(
                research_quality=quality,
                research_report=report,
                research_report_delivery=bound,
                research_report_versions=quality_versions(service, sid),
                research_accepted=quality["status"] == "passed"
                and status == "completed"
                and bound["status"] == "bound",
            )
        return result
