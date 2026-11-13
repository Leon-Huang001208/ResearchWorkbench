"""Bound FinGPT attachment data to the owning Host and turn."""

import asyncio
import base64
import codecs
import hashlib
import json
import re
from io import BytesIO
from pathlib import Path

from core.observability import get_logger

from . import sandbox
from .qa_acceptance import OFFICIAL_ENDPOINT, OFFICIAL_MODEL
from .store import StoreError

log = get_logger(__name__)
IMAGE_MEDIA = {
    ".png": ("PNG", "image/png"),
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".webp": ("WEBP", "image/webp"),
    ".gif": ("GIF", "image/gif"),
}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx"}
TEXT_EXTENSIONS = {".md", ".txt", ".csv", ".json"}
ATTACHMENT_EXTENSIONS = TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | IMAGE_MEDIA.keys()
MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_SIDE = 8192
MAX_IMAGE_SIDE_BULK = 4096
MAX_TEXT_BYTES = 16_000


def turn_images(store, sid, attachments, connection):
    candidates = [
        (fid, media)
        for fid, name in attachments
        if (media := IMAGE_MEDIA.get(Path(name).suffix.lower()))
    ]
    if not candidates:
        return []
    endpoint, model, _, provider = connection
    official_flash = (
        provider == "deepseek-official" and model == OFFICIAL_MODEL and endpoint == OFFICIAL_ENDPOINT
    )
    compatible_vision = provider == "openai-compatible" and re.fullmatch(
        r"gpt-4(?:o(?:-mini)?|\.1(?:-mini|-nano)?)(?:-\d{4}-\d{2}-\d{2})?", model
    )
    if not (official_flash or compatible_vision):
        raise StoreError(
            "当前问答模型未确认支持图片，请选用支持图片的模型",
            "qa_image_model_unsupported",
            422,
        )
    max_side = MAX_IMAGE_SIDE_BULK if official_flash and len(candidates) >= 15 else MAX_IMAGE_SIDE
    parts, total = [], 0
    for fid, (format_name, mime) in candidates:
        stream, _ = store.open_file(sid, fid)
        with stream:
            raw = stream.read(MAX_IMAGE_BYTES + 1)
        total += len(raw)
        if len(raw) > MAX_IMAGE_BYTES or total > 2 * MAX_IMAGE_BYTES:
            raise StoreError("单张图片最多 8 MiB，每条消息合计最多 16 MiB", "qa_image_size", 422)
        from PIL import Image

        try:
            with Image.open(BytesIO(raw), formats=[format_name]) as image:
                if (
                    max(image.size) > max_side
                    or image.width * image.height > 40_000_000
                    or getattr(image, "is_animated", False)
                ):
                    raise ValueError("image_dimensions_or_animation")
                image.verify()
        except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
            log.warning("research_qa_image_rejected", error_type=type(exc).__name__)
            raise StoreError("图片格式无效、过大或为动图", "qa_image_invalid", 422) from None
        url = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


def with_turn_images(params, parts):
    messages = params["messages"].copy()
    index = next(i for i in reversed(range(len(messages))) if messages[i]["role"] == "user")
    user = messages[index]
    messages[index] = {**user, "content": [{"type": "text", "text": user["content"]}, *parts]}
    return {**params, "messages": messages}


async def read_attachment(service, sid, fid):
    store = service.store
    stream, name = store.open_file(sid, fid)
    extension = Path(name).suffix.lower()
    with stream:
        if extension in IMAGE_MEDIA:
            return name, {"content": "图片通过当前回合的模型视觉输入提供。", "truncated": False}
        limit = MAX_FILE_BYTES if extension in DOCUMENT_EXTENSIONS else MAX_TEXT_BYTES
        raw = stream.read(limit + 1)
    if extension in TEXT_EXTENSIONS:
        try:
            decoder = codecs.getincrementaldecoder("utf-8-sig")()
            content = decoder.decode(raw[:limit], final=len(raw) <= limit)
        except UnicodeError:
            raise StoreError("附件不能读取为 UTF-8 文本", "qa_attachment_not_text", 409) from None
        return name, {"content": content, "truncated": len(raw) > limit}
    if extension not in DOCUMENT_EXTENSIONS or len(raw) > limit:
        raise StoreError("文档格式无效或超过大小上限", "qa_attachment_format_invalid", 409)
    session = store.directory(sid)
    path = store.file_path(sid, fid).relative_to(session).as_posix()
    digest = hashlib.sha256(raw).hexdigest()
    del raw
    code = (
        "import json\nfrom research_helpers import read_qa_document\n"
        f"print(json.dumps(read_qa_document({path!r}, {digest!r}, {limit}, {MAX_TEXT_BYTES}), "
        "ensure_ascii=False))\n"
    )
    result = await asyncio.to_thread(sandbox.run_script, service.delivery.config, session, code)
    try:
        if result.status != "completed":
            raise ValueError("qa_document_sandbox")
        data = json.loads(result.stdout)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("content"), str)
            or not data["content"].strip()
            or len(data["content"].encode("utf-8")) > MAX_TEXT_BYTES
            or type(data.get("truncated")) is not bool
        ):
            raise ValueError("qa_document_content_unavailable")
    except ValueError as exc:
        log.warning(
            "research_qa_document_unreadable", format=extension, error_type=type(exc).__name__
        )
        raise StoreError("文档没有可安全提取的正文", "qa_attachment_unreadable", 409) from None
    return name, data
