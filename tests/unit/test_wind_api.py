"""Wind API 路由测试"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建 TestClient，mock WindAdapter 避免真实 Excel 调用"""
    with patch("app.api.routes.wind.WindAdapter") as mock_adapter_cls:
        mock_adapter = MagicMock()
        mock_adapter.is_available.return_value = True
        mock_adapter_cls.return_value = mock_adapter

        from app.api.main import app

        test_client = TestClient(app)
        test_client._mock_adapter = mock_adapter
        yield test_client


class TestWindHealthEndpoint:
    """健康检查端点测试"""

    def test_health_returns_available_true(self, client):
        client._mock_adapter.is_available.return_value = True
        resp = client.get("/api/wind/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert "已连接" in data["message"]

    def test_health_returns_available_false(self, client):
        client._mock_adapter.is_available.return_value = False
        resp = client.get("/api/wind/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False

    def test_health_handles_exception(self, client):
        client._mock_adapter.is_available.side_effect = RuntimeError("Excel crashed")
        resp = client.get("/api/wind/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "Excel crashed" in data["message"]


class TestWindConsensusEndpoint:
    """一致预期端点测试"""

    def test_consensus_validates_input(self, client):
        """缺少必需字段时返回 422"""
        resp = client.post("/api/wind/consensus", json={})
        assert resp.status_code == 422

    def test_consensus_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_consensus_estimates.return_value = pd.DataFrame(
            [{"code": "600519.SH", "trade_date": "2025-06-01", "cons_net_profit": 1e10}]
        )
        resp = client.post("/api/wind/consensus", json={"codes": ["600519.SH"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["data"][0]["code"] == "600519.SH"


class TestWindMarginTradingEndpoint:
    """融资融券端点测试"""

    def test_margin_trading_requires_dates(self, client):
        """缺少日期字段时返回 422"""
        resp = client.post("/api/wind/margin-trading", json={"codes": ["600519.SH"]})
        assert resp.status_code == 422

    def test_margin_trading_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_margin_trading.return_value = pd.DataFrame(
            [{"code": "600519.SH", "date": "2025-06-01", "margin_balance": 5e9}]
        )
        resp = client.post(
            "/api/wind/margin-trading",
            json={"codes": ["600519.SH"], "start_date": "2025-06-01", "end_date": "2025-06-05"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


class TestWindBlockTradesEndpoint:
    """龙虎榜端点测试"""

    def test_block_trades_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_block_trades.return_value = pd.DataFrame(
            [{"code": "600519.SH", "date": "2025-06-01", "lhb_buy_amt": 1e8}]
        )
        resp = client.post(
            "/api/wind/block-trades",
            json={"codes": ["600519.SH"], "start_date": "2025-06-01", "end_date": "2025-06-05"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


class TestWindPricesEndpoint:
    """日行情端点测试"""

    def test_prices_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_daily_quotes.return_value = pd.DataFrame(
            [{"code": "600519.SH", "date": "2025-06-01", "open": 1800.0, "close": 1820.0}]
        )
        resp = client.post(
            "/api/wind/prices",
            json={"codes": ["600519.SH"], "start_date": "2025-06-01", "end_date": "2025-06-05"},
        )
        assert resp.status_code == 200


class TestWindFinancialsEndpoint:
    """财务报表端点测试"""

    def test_financials_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_financial_statements.return_value = pd.DataFrame(
            [{"code": "600519.SH", "report_date": "2024-12-31", "revenue": 1e11}]
        )
        resp = client.post(
            "/api/wind/financials",
            json={"codes": ["600519.SH"], "report_date": "2024-12-31"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


class TestWindFundFlowEndpoint:
    """资金流向端点测试"""

    def test_fund_flow_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_fund_flow.return_value = pd.DataFrame(
            [{"code": "600519.SH", "date": "2025-06-01", "net_inflow": 5e7}]
        )
        resp = client.post(
            "/api/wind/fund-flow",
            json={"codes": ["600519.SH"], "start_date": "2025-06-01", "end_date": "2025-06-05"},
        )
        assert resp.status_code == 200


class TestWindIndustryEndpoint:
    """行业分类端点测试"""

    def test_industry_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_industry_data.return_value = pd.DataFrame(
            [{"code": "600519.SH", "industry_sw": "食品饮料"}]
        )
        resp = client.post("/api/wind/industry", json={"codes": ["600519.SH"]})
        assert resp.status_code == 200


class TestWindHoldersEndpoint:
    """持有人数据端点测试"""

    def test_holders_returns_data(self, client):
        import pandas as pd

        client._mock_adapter.fetch_holder_data.return_value = pd.DataFrame(
            [{"code": "600519.SH", "report_date": "2024-12-31", "holder_num": 150000}]
        )
        resp = client.post(
            "/api/wind/holders",
            json={"codes": ["600519.SH"], "report_date": "2024-12-31"},
        )
        assert resp.status_code == 200
