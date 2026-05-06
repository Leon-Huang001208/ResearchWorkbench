
"""AkShare 适配器子模块"""
from .exceptions import (
    AkShareAdapterError,
    AkShareDataError,
    AkShareRateLimitError,
    AkShareClientError,
)
from .akshare_mapper import AkShareMapper
from .akshare_client import AkShareClient

__all__ = [
    "AkShareMapper",
    "AkShareClient",
    "AkShareAdapterError",
    "AkShareDataError",
    "AkShareRateLimitError",
    "AkShareClientError",
]

