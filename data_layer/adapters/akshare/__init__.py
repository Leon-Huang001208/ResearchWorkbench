"""AkShare 适配器子模块"""

from .akshare_client import AkShareClient
from .akshare_mapper import AkShareMapper
from .exceptions import (
    AkShareAdapterError,
    AkShareClientError,
    AkShareDataError,
    AkShareRateLimitError,
)

__all__ = [
    "AkShareMapper",
    "AkShareClient",
    "AkShareAdapterError",
    "AkShareDataError",
    "AkShareRateLimitError",
    "AkShareClientError",
]
