"""PDF 转换输出持久化 —— 将 markdown/raw_text 写入磁盘并管理路径"""
import os
from pathlib import Path
from typing import Optional

from core.observability import get_logger
from core.settings.config import settings

logger = get_logger(__name__)


def ensure_output_dirs() -> None:
    """确保输出目录存在"""
    settings.ensure_dirs()


def persist_markdown(pdf_id: str, content: str) -> str:
    """将 markdown 内容持久化到磁盘

    Args:
        pdf_id: PDF artifact ID
        content: markdown 文本内容

    Returns:
        str: 输出文件的绝对路径
    """
    output_path = _output_path(pdf_id, "md", settings.PDF_MARKDOWN_DIR)
    _write_file(output_path, content)
    logger.debug(f"Markdown 已持久化: {output_path}")
    return str(output_path)


def persist_raw_text(pdf_id: str, content: str) -> str:
    """将 raw_text 内容持久化到磁盘

    Args:
        pdf_id: PDF artifact ID
        content: 原始文本内容

    Returns:
        str: 输出文件的绝对路径
    """
    output_path = _output_path(pdf_id, "txt", settings.PDF_RAW_TEXT_DIR)
    _write_file(output_path, content)
    logger.debug(f"Raw text 已持久化: {output_path}")
    return str(output_path)


def should_inline(content: str) -> bool:
    """判断内容是否足够小以内联到数据库"""
    return len(content.encode("utf-8")) <= settings.PDF_INLINE_THRESHOLD_BYTES


def read_markdown(pdf_id: str) -> Optional[str]:
    """从磁盘读取 markdown 内容"""
    output_path = _output_path(pdf_id, "md", settings.PDF_MARKDOWN_DIR)
    return _read_file(output_path)


def read_raw_text(pdf_id: str) -> Optional[str]:
    """从磁盘读取 raw_text 内容"""
    output_path = _output_path(pdf_id, "txt", settings.PDF_RAW_TEXT_DIR)
    return _read_file(output_path)


def delete_outputs(pdf_id: str) -> None:
    """删除 pdf_id 对应的所有输出文件"""
    for dir_path in [settings.PDF_MARKDOWN_DIR, settings.PDF_RAW_TEXT_DIR]:
        for ext in ["md", "txt"]:
            file_path = _output_path(pdf_id, ext, dir_path)
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"已删除: {file_path}")


def _output_path(pdf_id: str, ext: str, base_dir: Path) -> Path:
    """生成输出文件路径，使用 pdf_id 防碰撞"""
    safe_name = _sanitize_filename(pdf_id)
    return base_dir / f"{safe_name}.{ext}"


def _sanitize_filename(name: str) -> str:
    """清除文件名中的不安全字符"""
    return "".join(c for c in name if c.isalnum() or c in "._-") or "unnamed"


def _write_file(path: Path, content: str) -> None:
    """写入文件，确保父目录存在"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_file(path: Path) -> Optional[str]:
    """读取文件内容"""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")