"""
本地数据适配器

支持从本地 JSON 文件读取资产数据。
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter

logger = get_logger(__name__)


class LocalDataAdapter(BaseDataAdapter):
    """
    本地数据适配器

    从 data/samples/ 目录读取 JSON 格式的资产数据。
    """

    def __init__(self, data_dir: Optional[Path] = None):
        super().__init__(source_type="local")
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "samples"
        self.data_dir = data_dir

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """
        读取本地数据文件

        kwargs:
            canonical_id: str - 资产代码，例如 600000.SH
        """
        canonical_id = kwargs.get("canonical_id")
        if not canonical_id:
            raise ValueError("canonical_id is required")

        logger.info(f"Reading local data for {canonical_id}")

        data_file = self.data_dir / f"stock_data_{canonical_id}.json"
        if not data_file.exists():
            logger.warning(f"Data file not found: {data_file}, falling back to mock")
            return []

        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 简单封装为 DocumentEnvelope
        content = json.dumps(data, ensure_ascii=False)
        envelope = DocumentEnvelope(
            doc_id=f"local_{canonical_id}_{self._now_str()}",
            source_type="local",
            source_name=data_file.name,
            title=f"{canonical_id} 本地数据",
            metadata={
                "canonical_id": canonical_id,
                "source": data_file.name,
            },
            raw_text=content,
            canonical_text=content,
        )

        return [envelope]

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """
        解析本地 JSON 数据
        """
        if isinstance(source, Path):
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif isinstance(source, bytes):
            data = json.loads(source.decode("utf-8"))
        elif isinstance(source, str):
            data = json.loads(source)
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        canonical_id = data.get("canonical_id", "unknown")

        content = json.dumps(data, ensure_ascii=False)
        return DocumentEnvelope(
            doc_id=f"local_parsed_{canonical_id}_{self._now_str()}",
            source_type="local",
            source_name="local",
            title=data.get("name", f"{canonical_id} 数据"),
            metadata=data,
            raw_text=content,
            canonical_text=content,
        )

    def get_asset_data(self, canonical_id: str) -> Optional[Dict[str, Any]]:
        """
        直接获取资产数据字典

        Args:
            canonical_id: 资产代码

        Returns:
            资产数据字典，或 None（如果文件不存在）
        """
        data_file = self.data_dir / f"stock_data_{canonical_id}.json"
        if not data_file.exists():
            logger.warning(f"Data file not found: {data_file}")
            return None

        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("data")

    def list_available_assets(self) -> list[str]:
        """
        列出所有可用的资产代码

        Returns:
            资产代码列表
        """
        assets: list[str] = []
        if not self.data_dir.exists():
            return assets

        for data_file in self.data_dir.glob("stock_data_*.json"):
            # 从文件名提取资产代码: stock_data_600000.SH.json -> 600000.SH
            filename = data_file.stem
            if filename.startswith("stock_data_"):
                canonical_id = filename[len("stock_data_") :]
                assets.append(canonical_id)

        return sorted(assets)

    def _now_str(self) -> str:
        """返回当前时间字符串用于生成 ID"""
        from datetime import UTC, datetime

        return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
