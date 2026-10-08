"""Run the reviewed report renderer inside the existing research sandbox."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from uuid import uuid4

from core.observability import get_logger

from . import sandbox
from .store import StoreError

log = get_logger(__name__)


async def execute_document_operation(
    store, session_id: str, request: dict, *, python=None, native_manager=None
) -> dict:
    """Use owned file identities and the existing reviewed renderer sandbox."""
    allowed = {
        "format",
        "operation",
        "mode",
        "file_id",
        "expected_sha256",
        "output_name",
        "content",
        "changes",
    }
    if set(request) - allowed or request.get("format") not in {"docx", "xlsx", "pptx"}:
        raise StoreError("文档请求无效")
    if request.get("operation") not in {"read", "generate", "modify"}:
        raise StoreError("文档操作无效")
    if request.get("mode") not in {"file", "native"}:
        raise StoreError("必须明确文件或原生执行模式")
    store.session(session_id)
    if request["mode"] == "native" and (
        native_manager is None
        or (request["operation"] == "generate" and request["format"] != "docx")
    ):
        return {
            "status": "unavailable",
            "mode": "native",
            "code": "native_document_executor_not_ready",
            "files": [],
        }
    encoded = json.dumps(request, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > 48_000:
        raise StoreError("文档操作超过大小限制")
    if not isinstance(request.get("content", {}), dict) or not isinstance(
        request.get("changes", []), list
    ):
        raise StoreError("文档内容或修改列表无效")
    changes = request.get("changes", [])
    for change in changes:
        if not isinstance(change, dict):
            raise StoreError("文档修改目标无效")
        for key in ("index", "table", "row", "column"):
            if key in change and (type(change[key]) is not int or not 0 <= change[key] <= 10000):
                raise StoreError("文档修改索引无效")
    config = sandbox.SandboxConfig(
        store.root,
        Path(python or __import__("sys").executable),
        timeout_seconds=30,
        max_output_bytes=131_072,
    )
    session = sandbox.validate_session(config, store.directory(session_id))
    token = uuid4().hex
    suffix = request["format"]
    output_name = request.get("output_name", f"document-{token}.{suffix}")
    if (
        not isinstance(output_name, str)
        or not re.fullmatch(r"[\w .-]{1,120}\.(docx|xlsx|pptx)", output_name)
        or not output_name.endswith("." + suffix)
    ):
        raise StoreError("输出名称无效")
    output = session / "outputs" / output_name
    if request["operation"] != "read" and (output.exists() or output.is_symlink()):
        return {"status": "conflict", "mode": "file", "code": "document_output_exists", "files": []}
    raw = None
    fingerprint = None
    file_id = request.get("file_id")
    if request["operation"] != "generate" and not file_id:
        raise StoreError("文档操作需要已有文件身份")
    if file_id:
        stream, name = store.open_file(session_id, file_id)
        with stream:
            raw = stream.read(30 * 1024 * 1024 + 1)
        if len(raw) > 30 * 1024 * 1024 or not name.lower().endswith("." + suffix):
            raise StoreError("输入文档格式或大小无效")
        fingerprint = hashlib.sha256(raw).hexdigest()
    elif suffix == "pptx" and request["operation"] == "generate":
        template = Path(__file__).with_name("office-template.pptx")
        if template.is_symlink() or not template.is_file() or template.stat().st_size > 2_000_000:
            raise StoreError("内置PPT模板不可用")
        raw = template.read_bytes()
    if request["operation"] == "modify":
        expected = request.get("expected_sha256")
        if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
            raise StoreError("修改前必须提供输入指纹")
        if expected != fingerprint:
            return {
                "status": "conflict",
                "mode": "file",
                "code": "document_input_changed",
                "files": [],
            }
    temporary = session / "tmp" / f"document-{token}.{suffix}"
    if temporary.parent.is_symlink():
        raise StoreError("文档临时目录无效")
    supplied = dict(request)
    staged_output = session / "tmp" / f"document-result-{token}.{suffix}"
    supplied["output"] = "tmp/" + staged_output.name
    staged_owned = False
    input_identity = None
    output_identity = None
    published_identity = None
    committed = False
    try:
        if request["operation"] != "read":
            with staged_output.open("xb") as stream:
                os.chmod(staged_output, 0o600)
                metadata = os.fstat(stream.fileno())
                output_identity = (metadata.st_dev, metadata.st_ino)
                supplied["output_inode"] = metadata.st_ino
        if raw is not None:
            with temporary.open("xb") as stream:
                staged_owned = True
                os.chmod(temporary, 0o600)
                metadata = os.fstat(stream.fileno())
                input_identity = (metadata.st_dev, metadata.st_ino)
                stream.write(raw)
            supplied["input"] = "tmp/" + temporary.name
        if request["mode"] == "native":
            native = await native_manager.run_document(
                session_id,
                {
                    "format": suffix,
                    "content": request.get("content", {}),
                    "source": raw,
                    "operation": request["operation"],
                    "changes": changes,
                    "read_cells": request.get("content", {}).get("read_cells"),
                },
            )
            if native.get("outcome") != "available":
                return {
                    "status": "failed",
                    "mode": "native",
                    "code": native.get("code"),
                    "comparison": native.get("comparison"),
                    "verification_id": native.get("verification_id"),
                    "diagnostics": native.get("diagnostics"),
                    "files": [],
                }
            result = {
                "status": "completed",
                "mode": "native",
                "format": suffix,
                "native_readback": native.get("native_readback"),
                "document": native.get("document"),
                "calculation_engine": native.get("calculation_engine"),
                "verification_id": native.get("verification_id"),
                "diagnostics": native.get("diagnostics"),
                "last_completed_step": "document_closed",
                "files": [],
            }
            if request["operation"] != "read":
                produced = native.get("output_bytes")
                if (
                    not isinstance(produced, bytes)
                    or not produced
                    or len(produced) > 30 * 1024 * 1024
                ):
                    raise ValueError("invalid native document output")
                descriptor = os.open(staged_output, os.O_WRONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, "wb") as stream:
                    metadata = os.fstat(stream.fileno())
                    if (metadata.st_dev, metadata.st_ino) != output_identity:
                        raise ValueError("native output stage identity changed")
                    stream.write(produced)
                result["files"] = ["tmp/" + staged_output.name]
        else:
            script = Path(__file__).with_name("report_render_script.py").read_text()
            source = "OFFICE_REQUEST = " + repr(supplied) + "\n" + script
            worker = asyncio.create_task(
                asyncio.to_thread(sandbox.run_script, config, session, source)
            )
            try:
                response = await asyncio.shield(worker)
            except asyncio.CancelledError:
                await asyncio.shield(worker)
                raise
            if response.status != "completed":
                log.warning(
                    "document_operation_sandbox_failed", status=response.status, format=suffix
                )
                return {
                    "status": "failed",
                    "mode": "file",
                    "code": "document_execution_failed",
                    "files": [],
                }
            result = json.loads(response.stdout)
        if not isinstance(result, dict) or result.get("status") not in {"completed", "failed"}:
            raise ValueError("invalid document executor response")
        if result["status"] == "completed" and request["operation"] != "read":
            # Detect changes to the original while the worker processed its copy.
            if file_id:
                stream, _ = store.open_file(session_id, file_id)
                with stream:
                    current = hashlib.sha256(stream.read(30 * 1024 * 1024 + 1)).hexdigest()
                if current != fingerprint:
                    return {
                        "status": "conflict",
                        "mode": "file",
                        "code": "document_input_changed",
                        "files": [],
                    }
            metadata = staged_output.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or (metadata.st_dev, metadata.st_ino) != output_identity
                or metadata.st_size == 0
                or result.get("files") != ["tmp/" + staged_output.name]
            ):
                raise ValueError("invalid staged document identity")
            try:
                os.link(staged_output, output, follow_symlinks=False)
                published_identity = output_identity
            except FileExistsError:
                return {
                    "status": "conflict",
                    "mode": "file",
                    "code": "document_output_exists",
                    "files": [],
                }
            # Store.open_file accepts only single-link files. Finish this step
            # before publishing the download identity or claiming success.
            staged_output.unlink()
            output_identity = None
            linked = output.lstat()
            if (linked.st_dev, linked.st_ino) != published_identity or linked.st_nlink != 1:
                raise ValueError("published document link identity invalid")
            result["files"] = ["outputs/" + output_name]
            result["output"] = next(
                item
                for item in store.files(session_id)
                if item["kind"] == "outputs" and item["name"] == output_name
            )
            after = output.lstat()
            if (after.st_dev, after.st_ino) != published_identity:
                raise ValueError("published document identity changed")
            committed = True
        log.info(
            "document_operation_finished",
            format=suffix,
            operation=request["operation"],
            status=result["status"],
        )
        return result
    except (OSError, ValueError, TypeError, StopIteration, StoreError, json.JSONDecodeError) as exc:
        log.warning("document_operation_failed", error_type=type(exc).__name__, format=suffix)
        return {
            "status": "failed",
            "mode": request["mode"],
            "code": "document_operation_failed",
            "files": [],
        }
    finally:
        for path, identity in (
            (temporary, input_identity if staged_owned else None),
            (staged_output, output_identity),
            (output, published_identity if not committed else None),
        ):
            if identity is None:
                continue
            try:
                metadata = path.lstat()
                if (metadata.st_dev, metadata.st_ino) == identity:
                    path.unlink()
                else:
                    log.warning("document_cleanup_identity_changed")
            except FileNotFoundError:
                pass
            except OSError as exc:
                log.warning("document_stage_cleanup_failed", error_type=type(exc).__name__)


async def render_report_payload(
    store,
    session_id: str,
    formats: list[str],
    *,
    python: str | Path | None = None,
) -> dict:
    """Project a model-authored payload into reviewed, deterministic file formats."""
    if not formats or any(item not in {"docx", "html", "xlsx", "pptx"} for item in formats):
        raise StoreError("报告渲染格式不受支持")
    session = store.directory(session_id)
    payload = session / "outputs" / "report_payload.json"
    if payload.is_symlink() or not payload.is_file() or payload.stat().st_size > 2_000_000:
        return {
            "status": "missing_payload",
            "files": [],
            "reason": "缺少有效的 report_payload.json",
        }
    script = Path(__file__).with_name("report_render_script.py").read_text()
    source = "FORMATS = " + repr(formats) + "\n" + script
    config = sandbox.SandboxConfig(
        store.root,
        Path(python or __import__("sys").executable),
        timeout_seconds=45,
        max_output_bytes=131_072,
    )
    result = await asyncio.to_thread(sandbox.run_script, config, session, source)
    if result.status != "completed":
        log.warning("report_projection_failed", status=result.status)
        return {"status": "failed", "files": [], "reason": "受审查报告渲染未完成"}
    try:
        output = json.loads(result.stdout)
        if output.get("status") != "completed" or not isinstance(output.get("files"), list):
            raise ValueError("invalid renderer response")
    except (TypeError, ValueError, json.JSONDecodeError):
        log.warning("report_projection_response_invalid")
        return {"status": "failed", "files": [], "reason": "受审查报告渲染响应无效"}
    return output
