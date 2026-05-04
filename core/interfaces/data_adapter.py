from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope


class DataAdapter(ABC):
    """数据适配器基类 - 用于从不同来源获取数据"""

    @abstractmethod
    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """获取数据"""
        pass

    @abstractmethod
    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析原始数据"""
        pass
