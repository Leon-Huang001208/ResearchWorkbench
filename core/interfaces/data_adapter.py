"""
Abstract base class (interface) for data adapters.

Defines the interface for data adapters that fetch and parse data from various sources
into DocumentEnvelope objects in AlphaFoundry.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope


class DataAdapter(ABC):
    """数据适配器基类 - 用于从不同来源获取数据.

    Abstract base class for data adapters, which are responsible for fetching data from
    various sources and parsing raw data into DocumentEnvelope objects.
    """

    @abstractmethod
    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """获取数据.

        Fetches data from the source (implementation-specific) and returns a list of
        DocumentEnvelope objects.

        Args:
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            list[DocumentEnvelope]: List of parsed document envelopes.
        """
        pass

    @abstractmethod
    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析原始数据.

        Parses raw data (from a file path, bytes, or string) into a single DocumentEnvelope.

        Args:
            source: Raw data source (Path, bytes, or string).
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            DocumentEnvelope: Parsed document envelope.
        """
        pass
