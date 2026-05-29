"""Wind 适配器单元测试 —— 所有公式名已通过 Wind Excel 实测验证"""
from unittest.mock import MagicMock, PropertyMock

import pytest

from data_layer.adapters.wind import formulas as wf
from data_layer.adapters.wind.exceptions import (
    WindError,
    WindFormulaError,
    WindNotConnectedError,
    WindSessionExpiredError,
    WindTimeoutError,
)


class TestWindExceptions:
    """自定义异常测试"""

    def test_wind_session_expired_has_clear_message(self):
        e = WindSessionExpiredError()
        assert "会话已过期" in str(e)
        assert "重新登录" in str(e)
        assert "Wind" in str(e)

    def test_wind_not_connected_has_clear_message(self):
        e = WindNotConnectedError()
        assert "未检测到运行中的 Excel" in str(e)
        assert "Wind 插件" in str(e)

    def test_wind_formula_error_stores_formula_and_error(self):
        e = WindFormulaError('=@s_test("600519.SH")', "#N/A")
        assert e.formula == '=@s_test("600519.SH")'
        assert e.excel_error == "#N/A"
        assert "#N/A" in str(e)

    def test_wind_timeout_error_stores_info(self):
        e = WindTimeoutError('=@s_test("600519.SH")', 15.0)
        assert e.formula == '=@s_test("600519.SH")'
        assert e.timeout == 15.0

    def test_exception_hierarchy(self):
        assert issubclass(WindSessionExpiredError, WindError)
        assert issubclass(WindFormulaError, WindError)
        assert issubclass(WindNotConnectedError, WindError)
        assert issubclass(WindTimeoutError, WindError)
        assert issubclass(WindError, Exception)


class TestWindFormulas:
    """Wind 公式生成测试 —— 所有公式名已通过 Wind Excel 实测验证"""

    # === 基础信息 ===
    def test_s_info_compname(self):
        assert wf.s_info_compname("600519.SH") == '=@s_info_compname("600519.SH")'

    def test_s_info_windcode(self):
        assert wf.s_info_windcode("000858.SZ") == '=@s_info_windcode("000858.SZ")'

    def test_s_info_industry(self):
        f = wf.s_info_industry("600519.SH")
        assert "s_info_industry" in f
        assert "600519.SH" in f

    # === 一致预期 - 净利润 ===
    def test_cons_net_profit_fy1(self):
        f = wf.cons_net_profit("600519.SH")
        assert "s_west_netprofit_fy1" in f

    def test_cons_net_profit_fy2(self):
        f = wf.cons_net_profit("600519.SH", fy="fy2")
        assert "s_west_netprofit_fy2" in f

    def test_cons_net_profit_fy3(self):
        f = wf.cons_net_profit("600519.SH", fy="fy3")
        assert "s_west_netprofit_fy3" in f

    def test_cons_net_profit_avg(self):
        f = wf.cons_net_profit("600519.SH", fy="avg")
        assert "s_west_netprofit_avg_fy1_fy2_fy3" in f

    def test_cons_net_profit_ftm(self):
        f = wf.cons_net_profit("600519.SH", fy="ftm")
        assert "s_west_netprofit_ftm" in f

    # === 一致预期 - EPS ===
    def test_cons_eps_fy1(self):
        f = wf.cons_eps("000858.SZ", trade_date="2024-12-31")
        assert "s_west_eps_fy1" in f
        assert "2024-12-31" in f

    def test_cons_eps_avg(self):
        f = wf.cons_eps("000858.SZ", fy="avg")
        assert "s_west_eps_avg_fy1_fy2_fy3" in f

    def test_cons_eps_ftm(self):
        f = wf.cons_eps("000858.SZ", fy="ftm")
        assert "s_west_eps_ftm" in f

    # === 一致预期 - 营收 ===
    def test_cons_revenue_fy1(self):
        f = wf.cons_revenue("600519.SH")
        assert "s_west_sales_fy1" in f

    def test_cons_revenue_ftm(self):
        f = wf.cons_revenue("600519.SH", fy="ftm")
        assert "s_west_sales_ftm" in f

    # === 目标价 ===
    def test_cons_target_price(self):
        f = wf.cons_target_price("600519.SH")
        assert "s_wrating_targetprice" in f

    def test_cons_target_price_ex(self):
        f = wf.cons_target_price_ex("600519.SH", west_period="90")
        assert "s_rating_targetprice" in f
        assert "90" in f

    # === 评级 ===
    def test_cons_rating(self):
        f = wf.cons_rating("600519.SH")
        assert "s_rating_avg" in f

    def test_cons_rating_chn(self):
        f = wf.cons_rating_chn("600519.SH")
        assert "s_rating_avgchn" in f

    def test_cons_rating_eng(self):
        f = wf.cons_rating_eng("600519.SH")
        assert "s_rating_avgeng" in f

    # === 融资融券 ===
    def test_margin_balance(self):
        f = wf.margin_balance("600519.SH", "2025-05-28")
        assert "s_margin_tradingbalance" in f

    def test_short_balance(self):
        f = wf.short_balance("600519.SH", "2025-05-28")
        assert "s_margin_seclendingbalancevolume" in f

    def test_margin_buy(self):
        f = wf.margin_buy("600519.SH", "2025-05-28")
        assert "s_margin_purchasewithborrowedmoney" in f

    def test_margin_repay(self):
        f = wf.margin_repay("600519.SH", "2025-05-28")
        assert "s_margin_repaymenttobroker" in f

    def test_short_sell_vol(self):
        f = wf.short_sell_vol("600519.SH", "2025-05-28")
        assert "s_margin_salesofborrowedsec" in f

    def test_short_repay_vol(self):
        f = wf.short_repay_vol("600519.SH", "2025-05-28")
        assert "s_margin_repaymentofborrowedsec" in f

    # === 龙虎榜 ===
    def test_lhb_net_buy(self):
        f = wf.lhb_net_buy("600519.SH", "2025-05-28")
        assert "s_abnormaltrade_netbuy" in f

    def test_lhb_buy_amt(self):
        f = wf.lhb_buy_amt("600519.SH", "2025-05-28")
        assert "s_pq_abnormaltrade_lp" in f

    def test_lhb_sell_amt(self):
        f = wf.lhb_sell_amt("600519.SH", "2025-05-28")
        assert "s_pq_abnormaltrade_sp" in f

    def test_lhb_count(self):
        f = wf.lhb_count("600519.SH", "2025-01-01", "2025-05-28")
        assert "s_pq_abnormaltradenum" in f

    # === 通用检查 ===
    def test_all_formulas_use_at_prefix(self):
        """确保所有公式使用 @ 前缀（Excel 隐式交集运算符）"""
        all_funcs = [
            wf.s_info_compname("600519.SH"),
            wf.cons_net_profit("600519.SH"),
            wf.cons_eps("600519.SH"),
            wf.cons_revenue("600519.SH"),
            wf.cons_target_price("600519.SH"),
            wf.cons_rating("600519.SH"),
            wf.margin_balance("600519.SH", "2025-01-01"),
            wf.short_balance("600519.SH", "2025-01-01"),
            wf.lhb_net_buy("600519.SH", "2025-01-01"),
            wf.lhb_buy_amt("600519.SH", "2025-01-01"),
        ]
        for f in all_funcs:
            assert f.startswith("=@")


class TestWindAdapterStructure:
    """WindAdapter 结构测试"""

    def test_adapter_import(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        assert adapter.source_type == "wind"

    def test_adapter_extends_base(self):
        from data_layer.adapters.base import BaseDataAdapter
        from data_layer.adapters.wind import WindAdapter

        assert issubclass(WindAdapter, BaseDataAdapter)

    def test_is_available_no_excel(self):
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        mock_client.heartbeat.return_value = False
        adapter = WindAdapter(client=mock_client)
        result = adapter.is_available()
        assert result is False

    def test_fetch_invalid_data_type_raises(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        with pytest.raises(ValueError, match="未知数据类型"):
            adapter.fetch(data_type="invalid_type", codes=["600519.SH"])

    def test_parse_not_implemented(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        with pytest.raises(NotImplementedError):
            adapter.parse("test")


class TestWindClientLogic:
    """WindExcelClient 逻辑测试（mock _connect 和 xlwings）"""

    def _setup_client_with_mock_sheet(self, sheet_mock):
        from data_layer.adapters.wind.client import WindExcelClient

        client = WindExcelClient()
        client._app = MagicMock()
        client._wb = MagicMock()
        client._sheet = sheet_mock
        client._col = "Z"
        return client

    def test_heartbeat_returns_true_when_wind_ok(self):
        sheet = MagicMock()
        cell = MagicMock()
        type(cell).value = PropertyMock(return_value="贵州茅台酒股份有限公司")
        sheet.range.return_value = cell

        client = self._setup_client_with_mock_sheet(sheet)
        assert client.heartbeat() is True

    def test_heartbeat_returns_false_when_wind_expired(self):
        sheet = MagicMock()
        cell = MagicMock()
        type(cell).value = PropertyMock(return_value="#N/A")
        sheet.range.return_value = cell

        client = self._setup_client_with_mock_sheet(sheet)
        assert client.heartbeat() is False

    def test_heartbeat_returns_false_on_timeout(self):
        sheet = MagicMock()
        cell = MagicMock()
        type(cell).value = PropertyMock(return_value=None)
        sheet.range.return_value = cell

        client = self._setup_client_with_mock_sheet(sheet)
        result = client.heartbeat()
        assert result is False

    def test_execute_batch_runs_heartbeat_first(self):
        from data_layer.adapters.wind.client import WindExcelClient
        from data_layer.adapters.wind.exceptions import WindSessionExpiredError

        sheet = MagicMock()
        cell = MagicMock()
        type(cell).value = PropertyMock(return_value="#N/A")
        sheet.range.return_value = cell

        client = WindExcelClient()
        client._app = MagicMock()
        client._wb = MagicMock()
        client._sheet = sheet
        client._col = "Z"

        with pytest.raises(WindSessionExpiredError):
            client.execute_batch(['=@s_info_compname("600519.SH")'])
