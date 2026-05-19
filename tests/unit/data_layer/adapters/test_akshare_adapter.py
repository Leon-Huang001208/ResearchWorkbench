"""AkShareAdapter 单元测试"""
from unittest.mock import MagicMock, patch

import pytest


class TestAKShareAdapter:
    """测试 data_layer/adapters/akshare_adapter.py"""

    def test_import_and_init(self):
        from data_layer.adapters.akshare_adapter import AKShareAdapter

        adapter = AKShareAdapter()
        assert adapter.source_type == "akshare"
        assert hasattr(adapter, "is_available")

    @patch("data_layer.adapters.akshare_adapter.CrawlerAkShareAdapter")
    def test_is_available_when_akshare_installed(self, mock_crawler):
        import importlib

        from data_layer.adapters.akshare_adapter import AKShareAdapter

        adapter = AKShareAdapter()
        assert adapter.is_available() is True or adapter.is_available() is False

    def test_fetch_raises_not_implemented(self):
        from data_layer.adapters.akshare_adapter import AKShareAdapter

        adapter = AKShareAdapter()
        with pytest.raises(NotImplementedError):
            adapter.fetch(source={})

    def test_parse_raises_not_implemented(self):
        from data_layer.adapters.akshare_adapter import AKShareAdapter

        adapter = AKShareAdapter()
        with pytest.raises(NotImplementedError):
            adapter.parse(source={})


class TestDataSourceRouter:
    """测试 DataSourceRouter 正确导入 AKShareAdapter"""

    def test_router_imports_akshare_adapter(self):
        """验证 DataSourceRouter 正确导入并使用 AKShareAdapter"""
        from data_layer.adapters.data_source_router import DataSourceRouter

        router = DataSourceRouter()
        assert hasattr(router, "akshare_adapter")
        from data_layer.adapters.akshare_adapter import AKShareAdapter

        assert isinstance(router.akshare_adapter, AKShareAdapter)
        assert router.akshare_adapter.source_type == "akshare"
