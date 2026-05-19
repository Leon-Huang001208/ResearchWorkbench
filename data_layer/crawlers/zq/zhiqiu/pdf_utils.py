#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 处理工具模块

提供 PDF 元数据记录、哈希计算等功能。
"""

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


@dataclass
class PDFMetadata:
    """PDF 元数据"""

    obj_id: str  # 知丘文档 ID
    file_path: str  # 文件路径（相对或绝对）
    file_hash: str  # SHA-256 哈希
    file_size: int  # 文件大小（字节）
    title: str = ""  # 标题
    broker: str = ""  # 券商
    author: str = ""  # 作者
    publish_date: str = ""  # 发布日期
    download_date: str = field(default_factory=lambda: datetime.now().isoformat())  # 下载日期
    source_url: str = ""  # 来源 URL
    extra: Dict[str, Any] = field(default_factory=dict)  # 额外信息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "obj_id": self.obj_id,
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "title": self.title,
            "broker": self.broker,
            "author": self.author,
            "publish_date": self.publish_date,
            "download_date": self.download_date,
            "source_url": self.source_url,
            "extra": self.extra,
        }


def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """
    计算文件哈希

    Args:
        file_path: 文件路径
        algorithm: 哈希算法（sha256, md5, sha1 等）

    Returns:
        十六进制哈希字符串
    """
    hash_obj = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def get_file_size(file_path: str) -> int:
    """
    获取文件大小（字节）

    Args:
        file_path: 文件路径

    Returns:
        文件大小
    """
    return os.path.getsize(file_path)


def ensure_pdf_dirs(output_dir: str, pdf_subdir: str = "pdfs") -> Tuple[str, str]:
    """
    确保 PDF 相关目录存在

    Args:
        output_dir: 输出根目录
        pdf_subdir: PDF 子目录名称

    Returns:
        (pdf_dir, metadata_dir) 目录路径元组
    """
    pdf_dir = os.path.join(output_dir, pdf_subdir)
    metadata_dir = os.path.join(output_dir, "pdf_metadata")

    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(metadata_dir, exist_ok=True)

    return pdf_dir, metadata_dir


def save_pdf_metadata(metadata: PDFMetadata, output_dir: str) -> str:
    """
    保存 PDF 元数据到 JSON 文件

    Args:
        metadata: PDF 元数据对象
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    import json

    metadata_dir = os.path.join(output_dir, "pdf_metadata")
    os.makedirs(metadata_dir, exist_ok=True)

    # 按 ID 组织元数据
    file_name = f"{metadata.obj_id}_metadata.json"
    file_path = os.path.join(metadata_dir, file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)

    return file_path


def load_pdf_metadata(obj_id: str, output_dir: str) -> Optional[PDFMetadata]:
    """
    加载 PDF 元数据

    Args:
        obj_id: 文档 ID
        output_dir: 输出目录

    Returns:
        PDFMetadata 对象，或 None（如果不存在）
    """
    import json

    metadata_path = os.path.join(output_dir, "pdf_metadata", f"{obj_id}_metadata.json")
    if not os.path.exists(metadata_path):
        return None

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PDFMetadata(**data)
    except Exception:
        return None


def is_pdf_available(obj_id: str, output_dir: str, pdf_dir: str = "pdfs") -> bool:
    """
    检查 PDF 文件是否已存在

    Args:
        obj_id: 文档 ID
        output_dir: 输出目录
        pdf_dir: PDF 子目录

    Returns:
        是否存在
    """
    # 先检查元数据
    metadata = load_pdf_metadata(obj_id, output_dir)
    if metadata and metadata.file_path:
        full_path = (
            os.path.join(output_dir, metadata.file_path)
            if not os.path.isabs(metadata.file_path)
            else metadata.file_path
        )
        if os.path.exists(full_path):
            return True

    # 直接检查常见的 PDF 文件路径
    for broker_subdir in ["", "unknown"]:
        # 尝试多种可能的文件名模式
        base_dir = (
            os.path.join(output_dir, pdf_dir, broker_subdir)
            if broker_subdir
            else os.path.join(output_dir, pdf_dir)
        )
        if not os.path.exists(base_dir):
            continue

        for filename in os.listdir(base_dir):
            if filename.startswith(obj_id) and filename.endswith(".pdf"):
                return True

    return False


def get_pdf_path(obj_id: str, output_dir: str, pdf_dir: str = "pdfs") -> Optional[str]:
    """
    获取已下载 PDF 的路径

    Args:
        obj_id: 文档 ID
        output_dir: 输出目录
        pdf_dir: PDF 子目录

    Returns:
        PDF 文件路径，或 None
    """
    # 先检查元数据
    metadata = load_pdf_metadata(obj_id, output_dir)
    if metadata and metadata.file_path:
        full_path = (
            os.path.join(output_dir, metadata.file_path)
            if not os.path.isabs(metadata.file_path)
            else metadata.file_path
        )
        if os.path.exists(full_path):
            return full_path

    # 直接查找
    full_pdf_dir = os.path.join(output_dir, pdf_dir)
    if not os.path.exists(full_pdf_dir):
        return None

    # 遍历目录查找
    for root, _, files in os.walk(full_pdf_dir):
        for filename in files:
            if filename.startswith(obj_id) and filename.endswith(".pdf"):
                return os.path.join(root, filename)

    return None
