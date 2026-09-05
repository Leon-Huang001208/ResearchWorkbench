"""FinGPT task service: AlphaFoundry governs tasks while DSH retains conversation bodies."""

from __future__ import annotations

import ipaddress
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from core.contracts.runtime import RuntimeUnavailableError
from core.observability import get_logger
from data_layer.repositories.fingpt_repository import FinGPTRepository
from services.runtime_workflow_service import (
    DailyMarketCommentaryRequest,
    RuntimeWorkflowService,
)

logger = get_logger(__name__)

PRESETS = {
    "daily-market-commentary": {"title": "每日市场点评", "workflow": True},
    "one-pager": {
        "title": "一页纸",
        "prompt": "请以买方投研一页纸结构梳理当前问题，先明确研究对象、证据缺口和待验证变量。",
    },
    "theme-research": {
        "title": "主题研究",
        "prompt": "请围绕主题建立投资研究框架：驱动、产业链、核心数据、风险与验证变量。市场和数据库数据必须调用 AlphaFoundry Tool。",
    },
    "chart": {
        "title": "画图",
        "prompt": "请先澄清图表问题、所需指标、时间区间和比较维度；数据必须来自 AlphaFoundry Tool。",
    },
    "research-checklist": {
        "title": "调研清单",
        "prompt": "请生成可执行的投研调研清单，按假设、需验证证据、访谈对象、数据源和风险分组。",
    },
}


class FinGPTService:
    def __init__(self, repository: FinGPTRepository, workflow_service: RuntimeWorkflowService):
        self._repository = repository
        self._workflow_service = workflow_service

    def health(self) -> dict:
        url = dsh_web_url()
        configured = bool(os.getenv("ALPHAFOUNDRY_DSH_BRIDGE_URL"))
        bridge_health: dict | None = None
        try:
            adapter = self._workflow_service._runtime_adapters.get(
                "dsh-local"
            )  # runtime registry owns construction
            if adapter is not None:
                bridge_health = adapter.health()
        except (OSError, RuntimeUnavailableError) as exc:  # no secret nor provider error is exposed
            logger.info("FinGPT DSH health check unavailable", error_type=type(exc).__name__)
        return {
            "available": bridge_health is not None,
            "configured": configured,
            "embed_url": url if bridge_health is not None else None,
            "embed_origin": origin_of(url),
            "diagnostic": (
                None
                if bridge_health is not None
                else "DSH Host 未就绪。请在本机启动项目托管的 DSH Profile。"
            ),
            "runtime": bridge_health,
        }

    def create_task(self, preset_id: str) -> dict:
        preset = PRESETS.get(preset_id)
        if preset is None:
            raise ValueError("不支持的 FinGPT 预置任务")
        launch_id = None if preset.get("workflow") else f"launch_{uuid4().hex}"
        task = self._repository.create_task(
            preset_id=preset_id,
            title=str(preset["title"]),
            launch_id=launch_id,
            launch_expires_at=(datetime.now(UTC) + timedelta(minutes=5)) if launch_id else None,
        )
        logger.info("FinGPT task created", task_id=task.task_id, preset_id=preset_id)
        return task_payload(task)

    def execute_daily_task(self, task_id: str, *, as_of: datetime, question: str) -> dict:
        task = self._repository.get_task_or_raise(task_id)
        if task.preset_id != "daily-market-commentary":
            raise ValueError("仅每日市场点评可通过确定性 Workflow 执行")
        run = self._workflow_service.create_daily_market_commentary(
            DailyMarketCommentaryRequest(as_of=as_of, question=question)
        )
        self._repository.attach_workflow(task_id=task_id, workflow_run_id=run["run_id"])
        result = self._workflow_service.execute(run["run_id"])
        artifacts = self._repository.link_artifacts_for_workflow(
            task_id=task_id, workflow_run_id=run["run_id"]
        )
        return {
            "task": task_payload(self._repository.get_task_or_raise(task_id)),
            "result": result.model_dump(mode="json"),
            "artifacts": [artifact_payload(a) for a in artifacts],
        }

    def consume_launch(self, launch_id: str) -> dict:
        task = self._repository.consume_launch(launch_id)
        preset = PRESETS[str(task.preset_id)]
        return {"task_id": task.task_id, "title": task.title, "prompt": preset["prompt"]}

    def accept_dsh_event(self, event: dict) -> bool:
        session_id = _required_text(event, "session_id")
        event_key = _required_text(event, "event_key")
        event_type = _required_text(event, "event_type")
        sequence = int(event.get("sequence", -1))
        task_id = event.get("task_id") if isinstance(event.get("task_id"), str) else None
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        sanitized = {
            key: value
            for key, value in payload.items()
            if key in {"tool_name", "artifact_id", "evidence_ref", "status", "reason"}
        }
        self._repository.upsert_session(
            dsh_session_id=session_id,
            task_id=task_id,
            status=str(metadata.get("status", "active")),
            sequence=sequence,
            metadata={
                key: value
                for key, value in metadata.items()
                if key in {"title", "status", "created_at"}
            },
        )
        accepted = self._repository.append_sync_event(
            event_key=event_key,
            dsh_session_id=session_id,
            sequence=sequence,
            event_type=event_type,
            payload=sanitized,
        )
        if isinstance(sanitized.get("evidence_ref"), str):
            self._repository.add_evidence_reference(
                task_id=task_id,
                dsh_session_id=session_id,
                source_ref=sanitized["evidence_ref"],
                source_name="DSH external web search",
                provenance="external_uningested",
                captured_evidence_id=None,
            )
        return accepted

    def sessions(self) -> list[dict]:
        return [
            {
                "dsh_session_id": row.dsh_session_id,
                "task_id": row.task_id,
                "title": row.title,
                "status": row.status,
                "sync_cursor": row.sync_cursor,
                "updated_at": row.updated_at,
            }
            for row in self._repository.list_sessions()
        ]

    def tasks(self) -> list[dict]:
        return [task_payload(row) for row in self._repository.list_tasks()]

    def artifacts(self, task_id: str) -> list[dict]:
        self._repository.get_task_or_raise(task_id)
        return [artifact_payload(row) for row in self._repository.list_artifacts(task_id)]


def dsh_web_url() -> str:
    raw = os.getenv("ALPHAFOUNDRY_DSH_WEB_URL", "http://127.0.0.1:3280")
    parsed = urlsplit(raw)
    if parsed.scheme != "http" or not parsed.hostname or not is_loopback_name(parsed.hostname):
        raise RuntimeError("DSH Web 只能绑定本机 loopback HTTP 地址")
    return raw.rstrip("/")


def origin_of(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_loopback_name(name: str) -> bool:
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def task_payload(task) -> dict:
    return {
        "task_id": task.task_id,
        "preset_id": task.preset_id,
        "title": task.title,
        "status": task.status,
        "workflow_run_id": task.workflow_run_id,
        "launch_id": task.launch_id,
        "created_at": task.created_at,
    }


def artifact_payload(artifact) -> dict:
    return {
        "artifact_id": artifact.artifact_id,
        "run_id": artifact.run_id,
        "artifact_type": artifact.artifact_type,
        "created_at": artifact.created_at,
    }


def _required_text(value: dict, key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"DSH 同步事件缺少 {key}")
    return item
