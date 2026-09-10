"""iFinD HTTP API 客户端实现"""

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from core.settings.config import Settings
from data_layer.adapters.ifind.exceptions import (
    IFinDAuthError,
    IFinDDatasourceError,
    IFinDPermissionError,
    IFinDRateLimitError,
)

logger = logging.getLogger(__name__)


class IFinDHTTPClient:
    """iFinD HTTP API 客户端"""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.base_url = settings.IFIND_HTTP_BASE_URL.rstrip("/")
        self.username = settings.IFIND_USERNAME
        self.password = settings.IFIND_PASSWORD
        self.token: str | None = None
        self.token_expires_at: datetime | None = None
        self._client: httpx.AsyncClient | None = None
        self._transport = transport

    async def _get_client(self) -> httpx.AsyncClient:
        """获取异步 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                transport=self._transport,
            )
        return self._client

    async def login(self) -> bool:
        """登录认证"""
        logger.info("Attempting to login to iFinD HTTP API")
        try:
            client = await self._get_client()
            response = await client.post(
                "/login",
                json={
                    "username": self.username,
                    "password": self.password,
                },
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get("token")
            if not isinstance(self.token, str) or not self.token:
                raise IFinDAuthError("iFinD login response did not contain a token")
            expires_in = data.get("expires_in", 7200)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
            logger.info("Successfully logged in to iFinD HTTP API")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise IFinDAuthError("Invalid iFinD credentials") from e
            raise IFinDDatasourceError(f"Login failed: {e}") from e
        except Exception as e:
            raise IFinDDatasourceError(f"Login failed: {e}") from e

    async def logout(self) -> None:
        """登出"""
        logger.info("Logging out from iFinD HTTP API")
        if self._client:
            await self._client.aclose()
            self._client = None
        self.token = None
        self.token_expires_at = None

    async def is_alive(self) -> bool:
        """健康检查"""
        if not self.token:
            return False
        if not self.token_expires_at or datetime.now() >= self.token_expires_at:
            try:
                await self.login()
            except Exception:
                return False
        try:
            client = await self._get_client()
            response = await client.get(
                "/health",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def _ensure_token(self) -> None:
        """确保 token 有效"""
        if not self.token or (self.token_expires_at and datetime.now() >= self.token_expires_at):
            await self.login()

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """发送请求"""
        await self._ensure_token()
        client = await self._get_client()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = await client.request(
                method=method,
                url=endpoint,
                headers=headers,
                **kwargs,
            )
            if response.status_code == 429:
                raise IFinDRateLimitError("Rate limit exceeded")
            if response.status_code == 403:
                raise IFinDPermissionError("Permission denied")
            if response.status_code == 401:
                await self.login()
                return await self._request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise IFinDDatasourceError(f"Request failed: {e}") from e

    async def history(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
        frequency: str = "day",
    ) -> list[dict]:
        """历史行情查询"""
        logger.debug(
            f"Fetching history: codes={codes}, indicators={indicators}, "
            f"start={start_date}, end={end_date}, freq={frequency}"
        )
        data = await self._request(
            "POST",
            "/history",
            json={
                "codes": codes,
                "indicators": indicators,
                "start_date": start_date,
                "end_date": end_date,
                "frequency": frequency,
            },
        )
        return data.get("data", [])

    async def realtime(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """实时行情查询"""
        logger.debug(f"Fetching realtime: codes={codes}, indicators={indicators}")
        data = await self._request(
            "POST",
            "/realtime",
            json={
                "codes": codes,
                "indicators": indicators,
            },
        )
        return data.get("data", [])

    async def basic(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """基础数据查询"""
        logger.debug(f"Fetching basic: codes={codes}, indicators={indicators}")
        data = await self._request(
            "POST",
            "/basic",
            json={
                "codes": codes,
                "indicators": indicators,
            },
        )
        return data.get("data", [])

    async def probe_query(self) -> list[dict]:
        """Execute the smallest supported read-only query used by connection probes."""

        return await self.basic(
            ["000001.SZ"],
            ["ths_stock_short_name_stock"],
        )

    async def financial(
        self,
        codes: list[str],
        indicators: list[str],
        report_date: str | None = None,
    ) -> list[dict]:
        """财务数据查询"""
        logger.debug(f"Fetching financial: codes={codes}, indicators={indicators}")
        data = await self._request(
            "POST",
            "/financial",
            json={
                "codes": codes,
                "indicators": indicators,
                "report_date": report_date,
            },
        )
        return data.get("data", [])

    async def date_serial(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """日期序列数据查询"""
        logger.debug(
            f"Fetching date_serial: codes={codes}, indicators={indicators}, "
            f"start={start_date}, end={end_date}"
        )
        data = await self._request(
            "POST",
            "/date_serial",
            json={
                "codes": codes,
                "indicators": indicators,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return data.get("data", [])

    async def data_pool(
        self,
        report_name: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        """专题报表数据池查询"""
        logger.debug(f"Fetching data_pool: report_name={report_name}")
        data = await self._request(
            "POST",
            "/data_pool",
            json={
                "report_name": report_name,
                "parameters": parameters or {},
            },
        )
        return data.get("data", [])

    async def edb_query(
        self,
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """宏观经济数据库查询"""
        logger.debug(
            f"Fetching edb_query: indicators={indicators}, " f"start={start_date}, end={end_date}"
        )
        data = await self._request(
            "POST",
            "/edb_query",
            json={
                "indicators": indicators,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return data.get("data", [])
