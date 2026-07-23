"""iFinD Python SDK 客户端实现（占位）"""

import importlib
import logging
from typing import Any

from core.settings.config import Settings
from data_layer.adapters.ifind.exceptions import IFinDSDKNotAvailableError

logger = logging.getLogger(__name__)

# 尝试导入 iFinD SDK
try:
    # iFinD SDK is optional and only available on supported terminals.
    _ifind_sdk = importlib.import_module("iFinD")
    THS_Basic = _ifind_sdk.THS_Basic
    THS_DataPool = _ifind_sdk.THS_DataPool
    THS_DateSerial = _ifind_sdk.THS_DateSerial
    THS_EdbQuery = _ifind_sdk.THS_EdbQuery
    THS_Financial = _ifind_sdk.THS_Financial
    THS_History = _ifind_sdk.THS_History
    THS_iFinDLogin = _ifind_sdk.THS_iFinDLogin
    THS_iFinDLogout = _ifind_sdk.THS_iFinDLogout
    THS_Realtime = _ifind_sdk.THS_Realtime

    IFIND_SDK_AVAILABLE = True
except ImportError:
    IFIND_SDK_AVAILABLE = False
    logger.warning("iFinD Python SDK not available")


class IFinDSDKClient:
    """iFinD Python SDK 客户端"""

    def __init__(self, settings: Settings):
        if not IFIND_SDK_AVAILABLE:
            raise IFinDSDKNotAvailableError("iFinD Python SDK is not available on this platform")
        self.settings = settings
        self.username = settings.IFIND_USERNAME
        self.password = settings.IFIND_PASSWORD
        self._logged_in = False

    async def login(self) -> bool:
        """登录认证"""
        logger.info("Attempting to login to iFinD SDK")
        # 这里使用 asyncio.to_thread 因为 SDK 是同步的
        import asyncio

        try:
            # 假设 THS_iFinDLogin 返回 0 表示成功
            result = await asyncio.to_thread(
                THS_iFinDLogin,
                self.username,
                self.password,
            )
            if result == 0:
                self._logged_in = True
                logger.info("Successfully logged in to iFinD SDK")
                return True
            else:
                logger.error(f"iFinD SDK login failed: error code {result}")
                return False
        except Exception as e:
            logger.error(f"iFinD SDK login failed: {e}")
            return False

    async def logout(self) -> None:
        """登出"""
        logger.info("Logging out from iFinD SDK")
        if self._logged_in:
            import asyncio

            try:
                await asyncio.to_thread(THS_iFinDLogout)
                self._logged_in = False
            except Exception as e:
                logger.error(f"iFinD SDK logout failed: {e}")

    async def is_alive(self) -> bool:
        """健康检查"""
        if not self._logged_in:
            return False
        # 简单检查：尝试获取一个基础数据
        try:
            # 这里可以调用一个轻量级的 SDK 函数
            return True
        except Exception:
            return False

    async def history(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
        frequency: str = "day",
    ) -> list[dict]:
        """历史行情查询"""
        import asyncio

        logger.debug(
            f"Fetching history via SDK: codes={codes}, indicators={indicators}, "
            f"start={start_date}, end={end_date}, freq={frequency}"
        )
        try:
            # 假设 THS_History 返回的数据格式需要转换
            # 这里做一个占位实现
            result = await asyncio.to_thread(
                THS_History,
                codes,
                indicators,
                start_date,
                end_date,
                frequency,
            )
            return self._convert_sdk_result(result)
        except Exception as e:
            logger.error(f"SDK history query failed: {e}")
            return []

    async def realtime(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """实时行情查询"""
        import asyncio

        logger.debug(f"Fetching realtime via SDK: codes={codes}, indicators={indicators}")
        try:
            result = await asyncio.to_thread(THS_Realtime, codes, indicators)
            return self._convert_sdk_result(result)
        except Exception as e:
            logger.error(f"SDK realtime query failed: {e}")
            return []

    async def basic(self, codes: list[str], indicators: list[str]) -> list[dict]:
        """基础数据查询"""
        import asyncio

        logger.debug(f"Fetching basic via SDK: codes={codes}, indicators={indicators}")
        try:
            result = await asyncio.to_thread(THS_Basic, codes, indicators)
            return self._convert_sdk_result(result)
        except Exception as e:
            logger.error(f"SDK basic query failed: {e}")
            return []

    async def financial(
        self,
        codes: list[str],
        indicators: list[str],
        report_date: str | None = None,
    ) -> list[dict]:
        """财务数据查询"""
        import asyncio

        logger.debug(f"Fetching financial via SDK: codes={codes}, indicators={indicators}")
        try:
            result = await asyncio.to_thread(
                THS_Financial,
                codes,
                indicators,
                report_date,
            )
            return self._convert_sdk_result(result)
        except Exception as e:
            logger.error(f"SDK financial query failed: {e}")
            return []

    async def date_serial(
        self,
        codes: list[str],
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """日期序列数据查询"""
        import asyncio

        logger.debug(
            f"Fetching date_serial via SDK: codes={codes}, indicators={indicators}, "
            f"start={start_date}, end={end_date}"
        )
        try:
            result = await asyncio.to_thread(
                THS_DateSerial,
                codes,
                indicators,
                start_date,
                end_date,
            )
            return self._convert_sdk_result(result)
        except Exception as e:
            logger.error(f"SDK date_serial query failed: {e}")
            return []

    async def data_pool(
        self,
        report_name: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        """专题报表数据池查询"""
        import asyncio

        logger.debug(f"Fetching data_pool via SDK: report_name={report_name}")
        try:
            result = await asyncio.to_thread(
                THS_DataPool,
                report_name,
                parameters or {},
            )
            return self._convert_sdk_result(result)
        except Exception as e:
            logger.error(f"SDK data_pool query failed: {e}")
            return []

    async def edb_query(
        self,
        indicators: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """宏观经济数据库查询"""
        import asyncio

        logger.debug(
            f"Fetching edb_query via SDK: indicators={indicators}, "
            f"start={start_date}, end={end_date}"
        )
        try:
            result = await asyncio.to_thread(
                THS_EdbQuery,
                indicators,
                start_date,
                end_date,
            )
            return self._convert_sdk_result(result)
        except Exception as e:
            logger.error(f"SDK edb_query query failed: {e}")
            return []

    def _convert_sdk_result(self, result: Any) -> list[dict]:
        """将 SDK 返回的结果转换为 dict 列表"""
        # 占位实现，实际使用时需要根据 SDK 返回的格式进行转换
        # 这里假设 result 已经是合适的格式
        if isinstance(result, list):
            return result
        return []
