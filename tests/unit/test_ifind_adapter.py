"""iFinD 适配器单元测试"""

import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.settings.config import Settings
from data_layer.adapters.ifind import BackendRouter, IFinDMapper
from data_layer.adapters.ifind_adapter import IFinDAdapter

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_settings():
    """Mock settings fixture"""
    return Settings(
        IFIND_USERNAME="test_user",
        IFIND_PASSWORD="test_pass",
        IFIND_BACKEND="auto",
    )


class TestBackendRouter:
    """测试 BackendRouter"""

    @pytest.mark.asyncio
    @patch("platform.system", return_value="Darwin")
    @patch("data_layer.adapters.ifind.router.IFinDHTTPClient")
    async def test_auto_select_macos_http(self, mock_http_client, mock_system, mock_settings):
        """测试 macOS 自动选择 HTTP API"""
        mock_client_instance = AsyncMock()
        mock_client_instance.is_alive.return_value = True
        mock_http_client.return_value = mock_client_instance

        router = BackendRouter(mock_settings)
        client = await router.get_client()

        assert client == mock_client_instance
        mock_http_client.assert_called_once_with(mock_settings)
        mock_client_instance.login.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("platform.system", return_value="Windows")
    @patch("data_layer.adapters.ifind.router.IFIND_SDK_AVAILABLE", True)
    @patch("data_layer.adapters.ifind.router.IFinDSDKClient")
    async def test_auto_select_windows_sdk(self, mock_sdk_client, mock_system, mock_settings):
        """测试 Windows 自动选择 SDK"""
        mock_client_instance = AsyncMock()
        mock_client_instance.is_alive.return_value = True
        mock_sdk_client.return_value = mock_client_instance

        router = BackendRouter(mock_settings)
        client = await router.get_client()

        assert client == mock_client_instance
        mock_sdk_client.assert_called_once_with(mock_settings)
        mock_client_instance.login.assert_awaited_once()


class TestIFinDMapper:
    """测试 IFinDMapper"""

    def test_map_quotes(self):
        """测试映射行情数据"""
        mapper = IFinDMapper()
        raw_data = [
            {
                "code": "600519.SH",
                "ths_open_stock": 100.0,
                "ths_high_stock": 110.0,
                "ths_low_stock": 90.0,
                "ths_close_stock": 105.0,
                "ths_vol_stock": 1000000,
                "ths_turnover_stock": 100000000.0,
            }
        ]
        as_of = datetime.now()
        snapshots = mapper.map_quotes("600519.SH", raw_data, as_of)
        assert len(snapshots) == 1
        assert snapshots[0].price_volume["open"] == 100.0
        assert snapshots[0].price_volume["close"] == 105.0

    def test_map_financial(self):
        """测试映射财务数据"""
        mapper = IFinDMapper()
        raw_data = [
            {
                "code": "600519.SH",
                "ths_eps_basic_stock": 10.0,
                "ths_roe_stock": 0.2,
                "ths_net_profit_stock": 1000000000.0,
            }
        ]
        as_of = datetime.now()
        snapshots = mapper.map_financial("600519.SH", raw_data, as_of)
        assert len(snapshots) == 1
        assert snapshots[0].financial["eps"] == 10.0
        assert snapshots[0].financial["roe"] == 0.2


class TestIFinDAdapter:
    """测试 IFinDAdapter"""

    @pytest.mark.asyncio
    @patch("data_layer.adapters.ifind_adapter.BackendRouter")
    async def test_fetch_stock_quotes(self, mock_router):
        """测试获取股票行情"""
        # 创建 mock router 实例
        mock_router_instance = MagicMock()
        mock_router.return_value = mock_router_instance

        # 创建 mock client
        mock_client = AsyncMock()
        mock_client.history.return_value = [
            {
                "code": "600519.SH",
                "ths_open_stock": 100.0,
                "ths_close_stock": 105.0,
            }
        ]

        # 设置 router.get_client 返回 mock client
        mock_router_instance.get_client = AsyncMock(return_value=mock_client)

        adapter = IFinDAdapter()
        snapshots = await adapter.fetch_stock_quotes(
            codes=["600519.SH"],
            start_date="2023-01-01",
            end_date="2023-12-31",
        )
        assert len(snapshots) == 1
        assert snapshots[0].price_volume["open"] == 100.0
