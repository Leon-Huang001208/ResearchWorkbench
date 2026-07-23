"""
原始数据存储服务 - Issue #43: 原始落盘

负责保存原始抓取数据到文件系统，管理原始数据生命周期
"""

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.contracts import SourceType
from core.contracts.raw_storage import (
    RawDataType,
    RawFileInfo,
    RawStorageConfig,
    generate_raw_file_name,
    get_raw_storage_path,
)
from core.observability import get_logger

logger = get_logger(__name__)


class RawStorageService:
    """原始数据存储服务"""

    def __init__(self, config: Optional[RawStorageConfig] = None):
        self.config = config or RawStorageConfig()
        self.base_path = Path(self.config.base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_raw_data(
        self,
        source_type: Union[str, SourceType],
        data: Union[str, bytes, Dict[str, Any]],
        data_type: Optional[RawDataType] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> RawFileInfo:
        """
        保存原始数据

        Args:
            source_type: 来源类型
            data: 数据内容
            data_type: 数据类型（自动推断如果不提供）
            metadata: 附加元数据
            timestamp: 时间戳

        Returns:
            RawFileInfo: 文件信息
        """
        source_type_str = source_type.value if isinstance(source_type, SourceType) else source_type
        ts = timestamp or datetime.now()

        # 推断数据类型
        if data_type is None:
            if isinstance(data, dict):
                data_type = RawDataType.JSON
            elif isinstance(data, bytes):
                data_type = RawDataType.BINARY
            else:
                data_type = RawDataType.TEXT

        # 准备数据
        if isinstance(data, dict):
            content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        elif isinstance(data, str):
            content = data.encode("utf-8")
        else:
            content = data

        # 计算校验和
        checksum = hashlib.md5(content).hexdigest()

        # 获取存储路径和文件名
        storage_path = get_raw_storage_path(
            source_type_str,
            ts,
            data_type,
            self.config.base_dir,
        )
        file_name = generate_raw_file_name(source_type_str, data_type, ts)
        file_path = storage_path / file_name

        # 压缩存储（如果配置）
        if self.config.compress and data_type in [
            RawDataType.JSON,
            RawDataType.HTML,
            RawDataType.TEXT,
        ]:
            file_path = file_path.with_suffix(file_path.suffix + ".gz")
            with gzip.open(file_path, "wb") as f:
                f.write(content)
        else:
            with open(file_path, "wb") as f:
                f.write(content)

        # 构建文件信息
        file_info = RawFileInfo(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            data_type=data_type,
            source_type=source_type_str,
            source_name=source_type_str,
            file_size_bytes=file_path.stat().st_size,
            created_at=ts,
            checksum=checksum,
            metadata=metadata or {},
        )

        logger.debug(f"Saved raw data: {file_path} ({len(content)} bytes)")
        return file_info

    def load_raw_data(
        self, file_path: Union[str, Path]
    ) -> Optional[Union[str, bytes, Dict[str, Any]]]:
        """
        加载原始数据

        Args:
            file_path: 文件路径

        Returns:
            数据内容
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Raw file not found: {file_path}")
            return None

        # 检测是否压缩
        is_compressed = path.suffix == ".gz"
        content: bytes

        if is_compressed:
            with gzip.open(path, "rb") as f:
                content = f.read()
        else:
            with open(path, "rb") as f:
                content = f.read()

        # 尝试解析
        if is_compressed:
            # 获取原始扩展名
            base_name = path.stem  # 去掉 .gz
            original_ext = Path(base_name).suffix
        else:
            original_ext = path.suffix

        if original_ext == ".json":
            try:
                return json.loads(content.decode("utf-8"))
            except Exception:
                return content.decode("utf-8", errors="replace")
        elif original_ext in [".html", ".txt"]:
            return content.decode("utf-8", errors="replace")
        else:
            return content

    def list_raw_files(
        self,
        source_type: Optional[Union[str, SourceType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        data_type: Optional[RawDataType] = None,
    ) -> List[RawFileInfo]:
        """
        列出原始文件

        Args:
            source_type: 来源类型过滤
            start_date: 开始日期
            end_date: 结束日期
            data_type: 数据类型过滤

        Returns:
            RawFileInfo 列表
        """
        source_type_str = source_type.value if isinstance(source_type, SourceType) else source_type
        all_files: List[RawFileInfo] = []

        # 构建扫描路径
        scan_base = self.base_path
        if source_type_str:
            scan_base = scan_base / source_type_str
            if not scan_base.exists():
                return []

        # 扫描目录 (兼容 Python 3.11-)
        import os

        for root, _, files in os.walk(scan_base):
            root_path = Path(root)
            for file_name in files:
                file_path = root_path / file_name
                try:
                    file_info = self._parse_file_info(file_path)
                    # 过滤
                    if start_date and file_info.created_at < start_date:
                        continue
                    if end_date and file_info.created_at > end_date:
                        continue
                    if data_type and file_info.data_type != data_type:
                        continue
                    all_files.append(file_info)
                except Exception as e:
                    logger.debug(f"Failed to parse file {file_path}: {e}")

        # 按时间倒序排列
        all_files.sort(key=lambda x: x.created_at, reverse=True)
        return all_files

    def _parse_file_info(self, file_path: Path) -> RawFileInfo:
        """从文件路径解析文件信息"""
        stat = file_path.stat()
        # 从目录结构推断 source_type
        parts = file_path.parts
        source_type = "unknown"
        for i, part in enumerate(parts):
            if part == "raw" and i + 1 < len(parts):
                source_type = parts[i + 1]
                break

        # 推断数据类型
        data_type = RawDataType.BINARY
        ext = file_path.suffix
        if ext == ".gz":
            ext = Path(file_path.stem).suffix
        if ext == ".json":
            data_type = RawDataType.JSON
        elif ext == ".html":
            data_type = RawDataType.HTML
        elif ext == ".pdf":
            data_type = RawDataType.PDF
        elif ext in [".txt", ".text"]:
            data_type = RawDataType.TEXT

        return RawFileInfo(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            data_type=data_type,
            source_type=source_type,
            source_name=source_type,
            file_size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
        )

    def cleanup_old_files(self, older_than_days: Optional[int] = None) -> int:
        """
        清理旧文件

        Args:
            older_than_days: 保留天数，默认使用配置中的 retention_days

        Returns:
            删除的文件数量
        """
        days = older_than_days or self.config.retention_days
        cutoff = datetime.now() - datetime.timedelta(days=days)
        deleted_count = 0

        for file_info in self.list_raw_files():
            if file_info.created_at < cutoff:
                try:
                    Path(file_info.file_path).unlink(missing_ok=True)
                    deleted_count += 1
                    logger.debug(f"Deleted old raw file: {file_info.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file_info.file_path}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old raw files")
        return deleted_count

    def get_file_info(self, file_path: Union[str, Path]) -> Optional[RawFileInfo]:
        """获取单个文件的信息"""
        path = Path(file_path)
        if not path.exists():
            return None
        return self._parse_file_info(path)
