"""Run the reviewed report renderer inside the existing research sandbox."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from core.observability import get_logger

from . import sandbox
from .store import StoreError

log = get_logger(__name__)


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
        return {"status": "missing_payload", "files": [], "reason": "缺少有效的 report_payload.json"}
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
