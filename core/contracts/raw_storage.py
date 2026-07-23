"""
原始数据存储契约 - Issue #43: 原始落盘规范

定义原始数据的存储结构、文件格式和元数据
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class RawDataType(str, Enum):
    """原始数据类型"""

    JSON = "json"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"
    IMAGE = "image"
    BINARY = "binary"


@dataclass
class RawFileInfo:
    """原始文件信息"""

    file_path: str
    file_name: str
    data_type: RawDataType
    source_type: str
    source_name: str
    file_size_bytes: int
    created_at: datetime
    checksum: Optional[str] = None  # MD5/SHA256
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawStorageConfig:
    """原始存储配置"""

    base_dir: str = "./data/raw"
    max_file_size_mb: int = 100
    compress: bool = True
    compression_format: str = "gzip"
    retention_days: int = 90


def get_raw_storage_path(
    source_type: str,
    date: datetime,
    data_type: RawDataType,
    base_dir: str = "./data/raw",
) -> Path:
    """
    获取原始数据存储路径

    目录结构:
    data/raw/
      {source_type}/
        {YYYY}/
          {MM}/
            {DD}/
              {timestamp}_{random_id}.{ext}
    """
    # 处理 SourceType 枚举
    if hasattr(source_type, "value"):
        source_type = source_type.value

    path = (
        Path(base_dir)
        / source_type
        / date.strftime("%Y")
        / date.strftime("%m")
        / date.strftime("%d")
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_raw_file_name(
    source_type: str,
    data_type: RawDataType,
    timestamp: Optional[datetime] = None,
) -> str:
    """生成原始文件名"""
    import uuid

    ts = timestamp or datetime.now()
    unique_id = str(uuid.uuid4())[:8]
    ext_map = {
        RawDataType.JSON: "json",
        RawDataType.HTML: "html",
        RawDataType.PDF: "pdf",
        RawDataType.TEXT: "txt",
        RawDataType.IMAGE: "bin",
        RawDataType.BINARY: "bin",
    }
    ext = ext_map.get(data_type, "bin")
    return f"{ts.strftime('%Y%m%d_%H%M%S')}_{source_type}_{unique_id}.{ext}"
