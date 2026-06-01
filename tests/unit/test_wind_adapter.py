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
        assert adapter.source_type == "vendor_snapshot"

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

    def test_parse_returns_document_envelope(self):
        from core.contracts import DocumentEnvelope
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        result = adapter.parse('{"test": "data"}', data_type="consensus", code="600519.SH")
        assert isinstance(result, DocumentEnvelope)
        assert result.metadata["data_type"] == "consensus"
        assert result.metadata["code"] == "600519.SH"
        assert result.metadata["source"] == "wind_excel"

    def test_parse_from_path(self, tmp_path):
        from core.contracts import DocumentEnvelope
        from data_layer.adapters.wind import WindAdapter

        test_file = tmp_path / "wind_data.json"
        test_file.write_text('{"test": "data"}', encoding="utf-8")

        adapter = WindAdapter()
        result = adapter.parse(test_file, data_type="financials", code="000858.SZ")
        assert isinstance(result, DocumentEnvelope)
        assert result.metadata["data_type"] == "financials"


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


# ===== Phase 1 新增公式测试 =====


class TestWindPriceFormulas:
    """日行情/价格公式测试 —— 全部 s_dq_* 已确认"""

    def test_daily_open(self):
        f = wf.daily_open("600519.SH", "2025-06-01")
        assert "s_dq_open" in f
        assert f.startswith("=@")

    def test_daily_open_with_adj_type(self):
        f = wf.daily_open("600519.SH", "2025-06-01", adj_type=2)
        assert "s_dq_open" in f
        assert ",2)" in f  # 后复权

    def test_daily_high(self):
        f = wf.daily_high("600519.SH", "2025-06-01")
        assert "s_dq_high" in f
        assert f.startswith("=@")

    def test_daily_low(self):
        f = wf.daily_low("600519.SH", "2025-06-01")
        assert "s_dq_low" in f
        assert f.startswith("=@")

    def test_daily_close(self):
        f = wf.daily_close("600519.SH", "2025-06-01")
        assert "s_dq_close" in f
        assert f.startswith("=@")

    def test_daily_volume(self):
        f = wf.daily_volume("600519.SH", "2025-06-01")
        assert "s_dq_volume" in f

    def test_daily_amount(self):
        f = wf.daily_amount("600519.SH", "2025-06-01")
        assert "s_dq_amount" in f
        assert "600519.SH" in f

    def test_daily_turnover(self):
        f = wf.daily_turnover("000858.SZ", "2025-06-01")
        assert "s_dq_turn" in f
        assert "000858.SZ" in f

    def test_daily_adj_factor(self):
        f = wf.daily_adj_factor("600519.SH", "2025-06-01")
        assert "s_dq_adjfactor2" in f

    def test_daily_vwap(self):
        f = wf.daily_vwap("600519.SH", "2025-06-01")
        assert "s_dq_avgprice" in f

    def test_daily_pct_change(self):
        f = wf.daily_pct_change("600519.SH", "2025-06-01")
        assert "s_dq_pctchange" in f

    def test_daily_amplitude(self):
        f = wf.daily_amplitude("600519.SH", "2025-06-01")
        assert "s_dq_swing" in f


class TestWindFinancialFormulas:
    """财务报表公式测试 —— 全部已确认"""

    def test_fin_revenue(self):
        f = wf.fin_revenue("600519.SH", "2024-12-31")
        assert "s_fa_or_ttm" in f
        assert "2024-12-31" in f

    def test_fin_operating_cost(self):
        f = wf.fin_operating_cost("600519.SH", "2024/12/31")
        assert "s_fa_cost_ttm2" in f
        assert "2024/12/31" in f

    def test_fin_gross_profit(self):
        f = wf.fin_gross_profit("600519.SH", "2024/12/31")
        assert "s_fa_grossmargin" in f

    def test_fin_gross_profit_ttm(self):
        f = wf.fin_gross_profit_ttm("600519.SH", "2024/12/31")
        assert "s_fa_grossmargin_ttm2" in f

    def test_fin_gross_profit_margin(self):
        f = wf.fin_gross_profit_margin("600519.SH", "2024/12/31")
        assert "s_fa_grossprofitmargin" in f

    def test_fin_net_profit(self):
        f = wf.fin_net_profit("600519.SH", "2024-12-31")
        assert "s_fa_profit_ttm" in f

    def test_fin_eps(self):
        f = wf.fin_eps("000858.SZ", "2024-12-31")
        assert "s_fa_eps_ttm2" in f

    def test_fin_roe(self):
        f = wf.fin_roe("600519.SH", "2024/12/31")
        assert "s_fa_roe_ttm2" in f

    def test_fin_total_assets(self):
        f = wf.fin_total_assets("600519.SH", "2024/12/31")
        assert "s_performanceexpress_perfextotalassets" in f

    def test_fin_equity(self):
        f = wf.fin_equity("600519.SH")
        assert "s_fa_totalequity_mrq" in f
        # equity MRQ 无日期参数
        assert '""' not in f or '"600519.SH")' in f

    def test_fin_free_cf(self):
        f = wf.fin_free_cf("600519.SH", "2024/12/31")
        assert "s_fa_fcff" in f

    def test_fin_free_cf_per_share(self):
        f = wf.fin_free_cf_per_share("600519.SH", "2024/12/31")
        assert "s_fa_fcffps" in f

    def test_fin_debt_yoy(self):
        f = wf.fin_debt_yoy("600519.SH", "2024/12/31")
        assert "s_fa_yoydebt" in f

    def test_val_pe_ttm(self):
        f = wf.val_pe_ttm("600519.SH", "2024-12-31")
        assert "s_val_pe_ttm" in f

    def test_val_pb_lf(self):
        f = wf.val_pb_lf("600519.SH", "2024-12-31")
        assert "s_val_pb_lf" in f


class TestWindIndustryFormulas:
    """行业/指数公式测试 —— 全部已确认"""

    def test_industry_sw(self):
        f = wf.industry_sw("600519.SH")
        assert "s_info_industry_sw_2021" in f
        assert "600519.SH" in f

    def test_industry_sw_level2(self):
        f = wf.industry_sw_level2("600519.SH")
        assert "s_info_industry_sw_2021" in f
        assert ",2)" in f

    def test_industry_sw_level3(self):
        f = wf.industry_sw_level3("600519.SH")
        assert "s_info_industry_sw_2021" in f
        assert ",3)" in f

    def test_index_close(self):
        f = wf.index_close("000300.SH", "2025-06-01")
        assert "i_dq_close" in f
        assert "000300.SH" in f

    def test_index_pct_change(self):
        f = wf.index_pct_change("000300.SH", "2025-06-01")
        assert "i_dq_pctchange" in f

    def test_index_weight(self):
        f = wf.index_weight("600519.SH", "2025-06-01", "000300.SH")
        assert "s_info_indexweight" in f
        assert "000300.SH" in f


class TestWindFundFlowFormulas:
    """资金流向公式测试 —— 全部已确认"""

    def test_moneyflow_main_force(self):
        f = wf.moneyflow_main_force("600519.SH", "2025-06-01")
        assert "s_mfd_inflow_m" in f

    def test_moneyflow_main_force_open(self):
        f = wf.moneyflow_main_force_open("600519.SH", "2025-06-01")
        assert "s_mfd_inflow_open_m" in f

    def test_moneyflow_main_force_close(self):
        f = wf.moneyflow_main_force_close("600519.SH", "2025-06-01")
        assert "s_mfd_inflow_close_m" in f

    def test_north_bound_shares(self):
        f = wf.north_bound_shares("600519.SH", "2025-06-01")
        assert "s_share_n" in f

    def test_north_bound_pct(self):
        f = wf.north_bound_pct("600519.SH", "2025-06-01")
        assert "s_share_pct_n" in f


class TestWindHolderFormulas:
    """股东/持有人公式测试 —— 全部已确认"""

    def test_holder_num(self):
        f = wf.holder_num("600519.SH", "2024/12/31")
        assert "s_holder_num2" in f

    def test_holder_liq_num(self):
        f = wf.holder_liq_num("600519.SH", "2025-06-01")
        assert "s_liqholder_num" in f

    def test_holder_avg_hold(self):
        f = wf.holder_avg_hold("600519.SH", "2024/12/31")
        assert "s_holder_avgnum" in f

    def test_holder_avg_pct(self):
        f = wf.holder_avg_pct("600519.SH", "2024/12/31")
        assert "s_holder_avgpct" in f

    def test_top10_holder_pct(self):
        f = wf.top10_holder_pct("600519.SH", "2024/12/31")
        assert "s_holder_sumt10pct" in f

    def test_top10_holder_quantity(self):
        f = wf.top10_holder_quantity("600519.SH", "2024/12/31")
        assert "s_holder_sumt10quantity" in f

    def test_institutional_hold(self):
        f = wf.institutional_hold("600519.SH", "2024/12/31")
        assert "s_holder_totalbyinst" in f

    def test_institutional_hold_pct(self):
        f = wf.institutional_hold_pct("600519.SH", "2024/12/31")
        assert "s_holder_pctbyinst" in f


class TestWindAdapterNewMethods:
    """WindAdapter 新方法结构测试"""

    def test_fetch_daily_quotes_method_exists(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        assert hasattr(adapter, "fetch_daily_quotes")
        assert callable(adapter.fetch_daily_quotes)

    def test_fetch_financial_statements_method_exists(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        assert hasattr(adapter, "fetch_financial_statements")
        assert callable(adapter.fetch_financial_statements)

    def test_fetch_industry_data_method_exists(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        assert hasattr(adapter, "fetch_industry_data")
        assert callable(adapter.fetch_industry_data)

    def test_fetch_fund_flow_method_exists(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        assert hasattr(adapter, "fetch_fund_flow")
        assert callable(adapter.fetch_fund_flow)

    def test_fetch_holder_data_method_exists(self):
        from data_layer.adapters.wind import WindAdapter

        adapter = WindAdapter()
        assert hasattr(adapter, "fetch_holder_data")
        assert callable(adapter.fetch_holder_data)

    def test_fetch_dispatches_new_data_types(self):
        """测试 fetch() 可以分发到新的数据类型"""
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        mock_client.execute_batch.return_value = ["测试值"] * 12
        adapter = WindAdapter(client=mock_client)

        # 验证新 data_type 不会抛出 "未知数据类型"
        for data_type in ["daily_quotes", "financials", "industry", "fund_flow", "holders"]:
            try:
                result = adapter.fetch(
                    data_type=data_type,
                    codes=["600519.SH"],
                    start_date="2025-01-01",
                    end_date="2025-01-10",
                    report_date="2024-12-31",
                )
                assert isinstance(result, list)
            except ValueError as e:
                # 参数验证 error 可以接受，但不能是 "未知数据类型"
                assert "未知数据类型" not in str(e)

    def test_fetch_daily_quotes_with_mock(self):
        """使用 mock client 测试 fetch_daily_quotes 返回 DataFrame"""
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        mock_client.execute_batch.return_value = [100.0] * 11
        adapter = WindAdapter(client=mock_client)

        df = adapter.fetch_daily_quotes(["600519.SH"], "2025-01-06", "2025-01-10")
        expected_cols = [
            "code",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "turnover",
            "adj_factor",
            "vwap",
            "pct_change",
            "amplitude",
        ]
        for col in expected_cols:
            assert col in df.columns
        # 确认 adj_close 已移除（用 daily_close + adj_type=2 代替）
        assert "adj_close" not in df.columns

    def test_fetch_daily_quotes_with_adj_type(self):
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        mock_client.execute_batch.return_value = [100.0] * 11
        adapter = WindAdapter(client=mock_client)

        df = adapter.fetch_daily_quotes(["600519.SH"], "2025-01-06", "2025-01-06", adj_type=2)
        assert len(df) == 1

    def test_fetch_financial_statements_with_mock(self):
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        # 3 trade_date + 8 report_date + 1 no_date = 12 formulas total
        mock_client.execute_batch.return_value = [1e9] * 12
        adapter = WindAdapter(client=mock_client)

        df = adapter.fetch_financial_statements(
            ["600519.SH"], trade_date="2024-12-31", report_date="2024/12/31"
        )
        expected_cols = [
            "code",
            "trade_date",
            "report_date",
            "revenue",
            "operating_cost",
            "gross_profit",
            "gross_profit_ttm",
            "gross_profit_margin",
            "net_profit",
            "eps",
            "roe",
            "total_assets",
            "equity",
            "free_cf",
            "free_cf_per_share",
        ]
        for col in expected_cols:
            assert col in df.columns
        # 确认已删除的字段不存在
        assert "total_liabilities" not in df.columns
        assert "operating_cf" not in df.columns

    def test_fetch_industry_data_with_mock(self):
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        mock_client.execute_batch.return_value = ["食品饮料", "白酒", "白酒"]
        adapter = WindAdapter(client=mock_client)

        df = adapter.fetch_industry_data(["600519.SH"])
        assert "industry_sw" in df.columns
        assert "industry_sw_l2" in df.columns
        assert "industry_sw_l3" in df.columns
        # PE/PB 已删除
        assert "industry_avg_pe" not in df.columns
        assert "industry_avg_pb" not in df.columns

    def test_fetch_fund_flow_with_mock(self):
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        mock_client.execute_batch.return_value = [1e8] * 5
        adapter = WindAdapter(client=mock_client)

        df = adapter.fetch_fund_flow(["600519.SH"], "2025-01-06", "2025-01-10")
        expected_cols = [
            "code",
            "date",
            "main_force_inflow",
            "main_force_open",
            "main_force_close",
            "north_bound_shares",
            "north_bound_pct",
        ]
        for col in expected_cols:
            assert col in df.columns
        assert "net_inflow" not in df.columns
        assert "retail_inflow" not in df.columns
        assert "north_bound_inflow" not in df.columns

    def test_fetch_holder_data_with_mock(self):
        from data_layer.adapters.wind import WindAdapter, WindExcelClient

        mock_client = MagicMock(spec=WindExcelClient)
        mock_client.execute_batch.return_value = [150000] * 7
        adapter = WindAdapter(client=mock_client)

        df = adapter.fetch_holder_data(["600519.SH"], "2024-12-31")
        expected_cols = [
            "code",
            "report_date",
            "holder_num",
            "holder_avg_hold",
            "holder_avg_pct",
            "top10_pct",
            "top10_quantity",
            "institutional_hold",
            "institutional_pct",
        ]
        for col in expected_cols:
            assert col in df.columns
        assert "fund_pct" not in df.columns
