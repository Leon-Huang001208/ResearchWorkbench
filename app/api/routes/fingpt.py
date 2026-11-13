"""FinGPT shell APIs; DSH owns transcript storage, AlphaFoundry owns governance."""

from __future__ import annotations

import os
import re
import stat
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from app.api.routes.runtime_workflows import require_dsh_tool_access
from app.research_web.multiuser.origin import validate_origin
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.fingpt_repository import FinGPTRepository
from data_layer.repositories.runtime_workflow_repository import (
    RuntimeWorkflowRepository,
)
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from research_workbench_entrypoint.resident.admission import admission
from services.fingpt_service import FinGPTService
from services.runtime_workflow_service import RuntimeWorkflowService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v2/fingpt", tags=["fingpt"])
log = get_logger(__name__)


def _has_entry(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _resident_root():
    configured = os.environ.get("RESEARCH_RESIDENT_HOME")
    root = Path(configured) if configured else Path.home() / ".research-workbench/resident"
    if not configured and not _has_entry(root):
        return None
    if (
        os.name != "posix"
        or not root.is_absolute()
        or root.name != "resident"
        or root.resolve(strict=True) != root
    ):
        raise ValueError("legacy_fingpt_resident_root_invalid")
    for folder in (root.parent, root, root.parent / "install"):
        _check_private_folder(folder)
    return root


def _check_private_folder(folder):
    identity = folder.lstat()
    if (
        not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != os.getuid()
        or identity.st_mode & 0o077
    ):
        raise ValueError("legacy_fingpt_resident_root_invalid")


def _replacement_url(root):
    # Read only this host's private records. No request header or remote probe
    # participates in either the cutover decision or the destination URL.
    from app.research_web.multiuser.resident_binding import read_json

    home = root.parent
    if _has_entry(root / "transaction.json") or _has_entry(
        home / "server/run/gateway-upgrade.json"
    ):
        raise ValueError("legacy_fingpt_cutover_pending")
    manifest = read_json(home / "install/manifest.json")
    manifest_flag = manifest.get("alphadesk_qa", False)
    gateway_file = home / "server/resident.json"
    if _has_entry(gateway_file):
        _check_private_folder(gateway_file.parent)
        gateway = read_json(gateway_file)
    else:
        gateway = {}
    gateway_flag = gateway.get("alphadesk_qa", False)
    if manifest_flag is False and gateway_flag is False:
        return None
    config = read_json(root / "config.json")
    accepted = read_json(root / "accepted.json")
    revision = manifest["code_commit"]
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
        or manifest.get("status") != "installed"
        or type(gateway.get("version")) is not int
        or gateway["version"] != 1
        or not isinstance(revision, str)
        or not re.fullmatch(r"[a-f0-9]{40}", revision)
        or not all(
            value == revision
            for value in (
                config["baseline"],
                gateway["revision"],
                gateway["binding"]["revision"],
                accepted["target"],
            )
        )
        or gateway["binding"]["home"] != str(home)
        or manifest_flag is not True
        or gateway_flag is not True
    ):
        raise ValueError("legacy_fingpt_cutover_unverified")
    if accepted["compatibility_review"]["profile"] != "reviewed-fingpt-alphadesk-v1":
        raise ValueError("legacy_fingpt_cutover_unverified")
    origin = validate_origin(config["private_origin"])
    if origin != "https://" + urlsplit(origin).netloc or origin != gateway["origin"]:
        raise ValueError("legacy_fingpt_cutover_origin_invalid")
    return origin + "/#/qa"


def _cutover_unavailable(exc):
    log.warning("legacy_fingpt_cutover_unavailable", error_type=type(exc).__name__)
    return HTTPException(status_code=503, detail="FinGPT 切换状态暂不可核验，请稍后重试。")


@contextmanager
def _cutover_state():
    with ExitStack() as stack:
        try:
            root = _resident_root()
            replacement = None
            if root is not None:
                stack.enter_context(admission(root=root))
                replacement = _replacement_url(root)
        except (OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
            raise _cutover_unavailable(exc) from None
        yield replacement


def _require_legacy_fingpt():
    # Generator dependency holds shared resident admission through the handler
    # and later dependencies (including the database commit on exit).
    with _cutover_state() as replacement:
        if replacement:
            raise HTTPException(status_code=410, detail="旧预设任务已退役，请打开 FinGPT。")
        yield


class CreateTaskRequest(BaseModel):
    preset_id: str = Field(min_length=1)


class ExecuteDailyTaskRequest(BaseModel):
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
    question: str = Field(default="生成当日 A 股每日收盘点评。", min_length=1)


class DshSyncEvent(BaseModel):
    session_id: str = Field(min_length=1)
    event_key: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    sequence: int = -1
    task_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)


def get_fingpt_service(db: Session = Depends(get_db)) -> FinGPTService:  # noqa: B008
    return FinGPTService(
        FinGPTRepository(db), RuntimeWorkflowService(RuntimeWorkflowRepository(db))
    )


@router.get("/health")
def fingpt_health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    with _cutover_state() as replacement:
        if replacement:
            return {"retired": True, "research_web_url": replacement}
        try:
            with contextmanager(get_db)() as db:
                return get_fingpt_service(db).health()
        except Exception as exc:
            raise _http_error(exc) from exc


@router.get("/sessions")
async def list_sessions(service: FinGPTService = Depends(get_fingpt_service)):  # noqa: B008
    return {"sessions": service.sessions()}


@router.get("/tasks")
async def list_tasks(service: FinGPTService = Depends(get_fingpt_service)):  # noqa: B008
    return {"tasks": service.tasks()}


@router.post(
    "/tasks",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_legacy_fingpt)],
)
async def create_task(
    payload: CreateTaskRequest,
    service: FinGPTService = Depends(get_fingpt_service),  # noqa: B008
):
    try:
        return service.create_task(payload.preset_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/tasks/{task_id}/execute", dependencies=[Depends(_require_legacy_fingpt)])
async def execute_daily_task(
    task_id: str,
    payload: ExecuteDailyTaskRequest,
    service: FinGPTService = Depends(get_fingpt_service),  # noqa: B008
):
    try:
        return service.execute_daily_task(task_id, as_of=payload.as_of, question=payload.question)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/launches/{launch_id}/consume",
    dependencies=[Depends(require_dsh_tool_access), Depends(_require_legacy_fingpt)],
)
async def consume_launch(
    launch_id: str,
    service: FinGPTService = Depends(get_fingpt_service),  # noqa: B008
):
    try:
        return service.consume_launch(launch_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/dsh-events",
    dependencies=[Depends(require_dsh_tool_access)],
    status_code=status.HTTP_202_ACCEPTED,
)
async def accept_dsh_event(
    payload: DshSyncEvent,
    service: FinGPTService = Depends(get_fingpt_service),  # noqa: B008
):
    try:
        return {"accepted": service.accept_dsh_event(payload.model_dump())}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/tasks/{task_id}/artifacts")
async def task_artifacts(
    task_id: str,
    service: FinGPTService = Depends(get_fingpt_service),  # noqa: B008
):
    try:
        return {"artifacts": service.artifacts(task_id)}
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="FinGPT 任务或启动标识不存在。")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=503, detail="FinGPT 服务暂不可用。")
