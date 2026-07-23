"""iFinD 后端路由器"""

import logging
import platform
from typing import Literal

from core.settings.config import Settings
from data_layer.adapters.ifind.client import IFinDClient
from data_layer.adapters.ifind.exceptions import IFinDDatasourceError, IFinDSDKNotAvailableError
from data_layer.adapters.ifind.http_client import IFinDHTTPClient
from data_layer.adapters.ifind.sdk_client import IFIND_SDK_AVAILABLE, IFinDSDKClient

logger = logging.getLogger(__name__)

BackendType = Literal["auto", "python_sdk", "http_api"]


class BackendRouter:
    """iFinD 后端路由器"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: IFinDClient | None = None

    async def get_client(self) -> IFinDClient:
        """获取后端客户端"""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> IFinDClient:
        """创建后端客户端"""
        backend = self.settings.IFIND_BACKEND
        logger.info(f"Creating iFinD client with backend: {backend}")

        if backend == "auto":
            return await self._auto_select_backend()
        elif backend == "python_sdk":
            return await self._create_sdk_client()
        elif backend == "http_api":
            return await self._create_http_client()
        else:
            raise ValueError(f"Unknown backend type: {backend}")

    async def _auto_select_backend(self) -> IFinDClient:
        """自动选择后端"""
        system = platform.system()
        logger.info(f"Auto-selecting backend for platform: {system}")

        if system == "Darwin":  # macOS
            # macOS 优先使用 HTTP API
            try:
                client = await self._create_http_client()
                if await client.is_alive():
                    logger.info("Selected HTTP API backend for macOS")
                    return client
            except Exception as e:
                logger.warning(f"HTTP API backend not available: {e}")
            raise IFinDDatasourceError(
                "iFinD Python SDK is not available on macOS, and HTTP API is not available. "
                "Please check your network connection or try running on Windows."
            )
        else:  # Windows or Linux
            # 优先使用 SDK，不可用时降级到 HTTP API
            try:
                client = await self._create_sdk_client()
                if await client.is_alive():
                    logger.info("Selected Python SDK backend")
                    return client
            except IFinDSDKNotAvailableError:
                logger.warning("Python SDK not available, trying HTTP API")
            except Exception as e:
                logger.warning(f"Python SDK backend not available: {e}")
            # 降级到 HTTP API
            try:
                client = await self._create_http_client()
                if await client.is_alive():
                    logger.info("Selected HTTP API backend (fallback)")
                    return client
            except Exception as e:
                logger.warning(f"HTTP API backend not available: {e}")
            raise IFinDDatasourceError("No available iFinD backend")

    async def _create_http_client(self) -> IFinDHTTPClient:
        """创建 HTTP API 客户端"""
        client = IFinDHTTPClient(self.settings)
        await client.login()
        return client

    async def _create_sdk_client(self) -> IFinDSDKClient:
        """创建 SDK 客户端"""
        if not IFIND_SDK_AVAILABLE:
            raise IFinDSDKNotAvailableError("iFinD Python SDK is not available")
        client = IFinDSDKClient(self.settings)
        await client.login()
        return client
