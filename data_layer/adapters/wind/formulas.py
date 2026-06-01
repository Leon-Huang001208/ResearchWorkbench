"""Wind 公式常量定义 —— Mac 版 Wind Excel 插件

公式来源: Wind Excel 函数浏览器 (已逐个验证, 43个已确认)
命名空间:
  s_dq_*     — 个股日行情 (11个)
  s_fa_*     — 财务报表 TTM/MRQ (13个)
  s_val_*    — 估值指标 (4个: PE, PB, PCF×2)
  s_west_*   — 一致预期 (8个)
  s_margin_* — 融资融券 (6个)
  s_abnormaltrade_* — 龙虎榜 (5个)
  s_mfd_*    — 主力资金流 (3个)
  s_share_*  — 北向持股 (2个)
  s_holder_* — 股东/持有人 (8个)
  s_info_*   — 基本信息/行业/权重 (8个)
  i_dq_*     — 指数日行情 (2个)
  pcf_ocf_o  — 个股PCF (1个)
"""

from datetime import date
from typing import Literal

FyVariant = Literal["fy1", "fy2", "fy3", "avg", "ftm"]


def _td(trade_date: str | None = None) -> str:
    """默认交易日期为今日"""
    return trade_date or date.today().strftime("%Y-%m-%d")


# ===== 基础信息 =====
def s_info_compname(code: str) -> str:
    """公司全称"""
    return f'=@s_info_compname("{code}")'


def s_info_windcode(code: str) -> str:
    """Wind 代码"""
    return f'=@s_info_windcode("{code}")'


def s_info_industry(code: str) -> str:
    """Wind 行业分类"""
    return f'=@s_info_industry("{code}")'


def s_info_listeddate(code: str) -> str:
    """上市日期"""
    return f'=@s_info_listeddate("{code}")'


def s_info_shares(code: str) -> str:
    """总股本"""
    return f'=@s_info_shares("{code}")'


# ===== 一致预期 =====


def cons_net_profit(code: str, trade_date: str | None = None, fy: FyVariant = "fy1") -> str:
    """一致预测净利润 —— 算术平均值，单位: 元

    Args:
        code: Wind代码 或 交易代码，如 "600519.SH"
        trade_date: 交易日期 "YYYY-MM-DD"，默认系统日期
        fy: 预测年度 "fy1"|"fy2"|"fy3"|"avg"
    """
    td = _td(trade_date)
    if fy == "avg":
        return f'=@s_west_netprofit_avg_fy1_fy2_fy3("{code}","{td}")'
    if fy == "ftm":
        return f'=@s_west_netprofit_ftm("{code}","{td}")'
    return f'=@s_west_netprofit_{fy}("{code}","{td}")'


def cons_eps(code: str, trade_date: str | None = None, fy: FyVariant = "fy1") -> str:
    """一致预测 EPS —— 算术平均值，单位: 元/股"""
    td = _td(trade_date)
    if fy == "avg":
        return f'=@s_west_eps_avg_fy1_fy2_fy3("{code}","{td}")'
    return f'=@s_west_eps_{fy}("{code}","{td}")'


def cons_revenue(code: str, trade_date: str | None = None, fy: FyVariant = "fy1") -> str:
    """一致预测营业收入 —— 算术平均值，单位: 元"""
    td = _td(trade_date)
    if fy == "avg":
        return f'=@s_west_sales_avg_fy1_fy2_fy3("{code}","{td}")'
    return f'=@s_west_sales_{fy}("{code}","{td}")'


def cons_target_price(code: str, trade_date: str | None = None) -> str:
    """一致预测目标价（万得一致预测，180天） —— 算术平均值，单位: 元"""
    td = _td(trade_date)
    return f'=@s_wrating_targetprice("{code}","{td}")'


def cons_target_price_ex(code: str, trade_date: str | None = None, west_period: str = "180") -> str:
    """一致预测目标价（可选综合值类型）

    Args:
        code: Wind代码
        trade_date: 截止日期
        west_period: 综合值类型 "180"|"90"|"30"|"event" (万得一致/前瞻/领先/大事后)
    """
    td = _td(trade_date)
    return f'=@s_rating_targetprice("{code}","{td}","{west_period}")'


def cons_rating(code: str, trade_date: str | None = None) -> str:
    """综合评级(数值) —— 算术平均值，1-5分

    1=买入, 2=增持, 3=中性, 4=减持, 5=卖出。越低越好。
    """
    td = _td(trade_date)
    return f'=@s_rating_avg("{code}","{td}")'


def cons_rating_chn(code: str, trade_date: str | None = None) -> str:
    """综合评级(中文) —— 如 "买入"、"增持+"、"中性-" 等"""
    td = _td(trade_date)
    return f'=@s_rating_avgchn("{code}","{td}")'


def cons_rating_eng(code: str, trade_date: str | None = None) -> str:
    """综合评级(英文) —— 如 "Buy"、"Outperform"、"Hold" 等"""
    td = _td(trade_date)
    return f'=@s_rating_avgeng("{code}","{td}")'


def cons_rating_num(code: str, trade_date: str | None = None) -> str:
    """参与评级的机构数量 [待验证]"""
    td = _td(trade_date)
    return f'=@s_wrating_ratingnum("{code}","{td}")'


# ===== 融资融券 =====
def margin_balance(code: str, trade_date: str) -> str:
    """融资余额（元）"""
    return f'=@s_margin_tradingbalance("{code}","{trade_date}")'


def short_balance(code: str, trade_date: str) -> str:
    """融券余量（股）"""
    return f'=@s_margin_seclendingbalancevolume("{code}","{trade_date}")'


def margin_buy(code: str, trade_date: str) -> str:
    """融资买入额（元）"""
    return f'=@s_margin_purchasewithborrowedmoney("{code}","{trade_date}")'


def margin_repay(code: str, trade_date: str) -> str:
    """融资偿还额（元）"""
    return f'=@s_margin_repaymenttobroker("{code}","{trade_date}")'


def short_sell_vol(code: str, trade_date: str) -> str:
    """融券卖出量（股）"""
    return f'=@s_margin_salesofborrowedsec("{code}","{trade_date}")'


def short_repay_vol(code: str, trade_date: str) -> str:
    """融券偿还量（股）"""
    return f'=@s_margin_repaymentofborrowedsec("{code}","{trade_date}")'


# ===== 龙虎榜（异常交易） =====
def lhb_net_buy(code: str, trade_date: str) -> str:
    """龙虎榜净买入额 —— 单日（元）"""
    return f'=@s_abnormaltrade_netbuy("{code}","{trade_date}")'


def lhb_buy_amt(code: str, trade_date: str) -> str:
    """龙虎榜买入金额 —— 单日，用区间公式 start=end（元）"""
    return f'=@s_pq_abnormaltrade_lp("{code}","{trade_date}","{trade_date}")'


def lhb_sell_amt(code: str, trade_date: str) -> str:
    """龙虎榜卖出金额 —— 单日，用区间公式 start=end（元）"""
    return f'=@s_pq_abnormaltrade_sp("{code}","{trade_date}","{trade_date}")'


def lhb_buy_seat(code: str, trade_date: str) -> str:
    """龙虎榜买入席位 [待验证]"""
    return f'=@s_abnormaltrade_buybroker("{code}","{trade_date}")'


def lhb_sell_seat(code: str, trade_date: str) -> str:
    """龙虎榜卖出席位 [待验证]"""
    return f'=@s_abnormaltrade_sellbroker("{code}","{trade_date}")'


def lhb_count(code: str, start_date: str, end_date: str) -> str:
    """区间龙虎榜上榜次数"""
    return f'=@s_pq_abnormaltradenum("{code}","{start_date}","{end_date}")'


# ===== 日行情数据 =====


def daily_open(code: str, trade_date: str, adj_type: int = 1) -> str:
    """开盘价（元） ✅ 已确认

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日，如不设置则默认为系统日期
        adj_type: 复权方式 1-不复权 2-后复权 3-前复权
    """
    return f'=@s_dq_open("{code}","{trade_date}",{adj_type})'


def daily_high(code: str, trade_date: str, adj_type: int = 1) -> str:
    """最高价（元） ✅ 已确认

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日
        adj_type: 复权方式 1-不复权 2-后复权 3-前复权
    """
    return f'=@s_dq_high("{code}","{trade_date}",{adj_type})'


def daily_low(code: str, trade_date: str, adj_type: int = 1) -> str:
    """最低价（元） ✅ 已确认

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日
        adj_type: 复权方式 1-不复权 2-后复权 3-前复权
    """
    return f'=@s_dq_low("{code}","{trade_date}",{adj_type})'


def daily_close(code: str, trade_date: str, adj_type: int = 1) -> str:
    """收盘价（元） ✅ 已确认

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日
        adj_type: 复权方式 1-不复权 2-后复权 3-前复权
    """
    return f'=@s_dq_close("{code}","{trade_date}",{adj_type})'


def daily_volume(code: str, trade_date: str) -> str:
    """成交量 ✅ 已确认（2 参数，无复权方式）"""
    return f'=@s_dq_volume("{code}","{trade_date}")'


def daily_amount(code: str, trade_date: str) -> str:
    """成交额（元） ✅ 已确认"""
    return f'=@s_dq_amount("{code}","{trade_date}")'


def daily_turnover(code: str, trade_date: str) -> str:
    """换手率（%） ✅ 已确认"""
    return f'=@s_dq_turn("{code}","{trade_date}")'


def daily_adj_factor(code: str, trade_date: str) -> str:
    """复权因子 ✅ 已确认"""
    return f'=@s_dq_adjfactor2("{code}","{trade_date}")'


def daily_vwap(code: str, trade_date: str) -> str:
    """均价（元） ✅ 已确认 (Wind 函数名: s_dq_avgprice)"""
    return f'=@s_dq_avgprice("{code}","{trade_date}")'


def daily_pct_change(code: str, trade_date: str) -> str:
    """涨跌幅（%） ✅ 已确认"""
    return f'=@s_dq_pctchange("{code}","{trade_date}")'


def daily_amplitude(code: str, trade_date: str) -> str:
    """振幅（%） ✅ 已确认 (Wind 函数名: s_dq_swing)"""
    return f'=@s_dq_swing("{code}","{trade_date}")'


# ===== 日行情数据 - 日期范围版（一次返回整段时间序列）=====


def daily_open_range(code: str, start_date: str, end_date: str, adj_type: int = 1) -> str:
    """开盘价时间序列 — Wind 日期范围公式（无 @ 前缀，返回数组）"""
    return f'=s_dq_open("{code}","{start_date}","{end_date}",{adj_type})'


def daily_high_range(code: str, start_date: str, end_date: str, adj_type: int = 1) -> str:
    """最高价时间序列"""
    return f'=s_dq_high("{code}","{start_date}","{end_date}",{adj_type})'


def daily_low_range(code: str, start_date: str, end_date: str, adj_type: int = 1) -> str:
    """最低价时间序列"""
    return f'=s_dq_low("{code}","{start_date}","{end_date}",{adj_type})'


def daily_close_range(code: str, start_date: str, end_date: str, adj_type: int = 1) -> str:
    """收盘价时间序列"""
    return f'=s_dq_close("{code}","{start_date}","{end_date}",{adj_type})'


def daily_volume_range(code: str, start_date: str, end_date: str) -> str:
    """成交量时间序列（Wind 成交量函数只有 2 参数，不含复权）"""
    return f'=s_dq_volume("{code}","{start_date}","{end_date}")'


def daily_amount_range(code: str, start_date: str, end_date: str) -> str:
    """成交额时间序列"""
    return f'=s_dq_amount("{code}","{start_date}","{end_date}")'


def daily_turnover_range(code: str, start_date: str, end_date: str) -> str:
    """换手率时间序列"""
    return f'=s_dq_turn("{code}","{start_date}","{end_date}")'


def daily_adj_factor_range(code: str, start_date: str, end_date: str) -> str:
    """复权因子时间序列"""
    return f'=s_dq_adjfactor2("{code}","{start_date}","{end_date}")'


def daily_vwap_range(code: str, start_date: str, end_date: str) -> str:
    """均价时间序列"""
    return f'=s_dq_avgprice("{code}","{start_date}","{end_date}")'


def daily_pct_change_range(code: str, start_date: str, end_date: str) -> str:
    """涨跌幅时间序列"""
    return f'=s_dq_pctchange("{code}","{start_date}","{end_date}")'


def daily_amplitude_range(code: str, start_date: str, end_date: str) -> str:
    """振幅时间序列"""
    return f'=s_dq_swing("{code}","{start_date}","{end_date}")'


# ===== 财务报表数据 =====


def fin_revenue(code: str, trade_date: str | None = None) -> str:
    """营业收入 TTM（元） ✅ 已确认

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日期，默认系统日期（自动匹配最新报告期）
    """
    td = _td(trade_date)
    return f'=@s_fa_or_ttm("{code}","{td}")'


def fin_operating_cost(code: str, report_date: str) -> str:
    """营业成本 TTM（元） ✅ 已确认

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"（年报）、"2024/09/30"（三季报）
    """
    return f'=@s_fa_cost_ttm2("{code}","{report_date}")'


def fin_gross_profit(code: str, report_date: str) -> str:
    """毛利（元）—— 单报告期版 ✅ 已确认

    指定报告期的毛利绝对值，非 TTM。

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"
    """
    return f'=@s_fa_grossmargin("{code}","{report_date}")'


def fin_gross_profit_ttm(code: str, report_date: str) -> str:
    """毛利 TTM（元） ✅ 已确认"""
    return f'=@s_fa_grossmargin_ttm2("{code}","{report_date}")'


def fin_gross_profit_margin(code: str, report_date: str) -> str:
    """销售毛利率（%） ✅ 已确认"""
    return f'=@s_fa_grossprofitmargin("{code}","{report_date}")'


def fin_net_profit(code: str, trade_date: str | None = None) -> str:
    """净利润 TTM（元） ✅ 已确认

    算法：根据报告期"净利润(含少数股东损益)"计算：
    (1) 最新报告期是年报 → TTM=年报
    (2) 最新报告期不是年报 → TTM=本期+(上年年报-上年同期合并数)
    交易日参数匹配的为最新报告期的披露日期。

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日期，默认系统日期（自动匹配最新报告期）
    """
    td = _td(trade_date)
    return f'=@s_fa_profit_ttm("{code}","{td}")'


def fin_eps(code: str, trade_date: str | None = None) -> str:
    """基本每股收益 TTM（元/股） ✅ 已确认

    算法：归属母公司股东的净利润(TTM) / 最新总股本
    最新业绩快报参与计算。

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日期，默认系统日期
    """
    td = _td(trade_date)
    return f'=@s_fa_eps_ttm2("{code}","{td}")'


def fin_roe(code: str, report_date: str) -> str:
    """净资产收益率 ROE TTM（%） ✅ 已确认

    算法：归属于母公司的净利润(TTM) / 归属于母公司的股东权益(MRQ) * 100%

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"（年报）、"2024/09/30"（三季报）
    """
    return f'=@s_fa_roe_ttm2("{code}","{report_date}")'


def fin_total_assets(code: str, report_date: str) -> str:
    """总资产（元）—— 业绩快报版

    NOTE: 此为业绩快报数据 (s_performanceexpress_perfextotalassets)，非正式财报版。
    """
    return f'=@s_performanceexpress_perfextotalassets("{code}","{report_date}")'


def fin_debt_yoy(code: str, report_date: str) -> str:
    """总负债同比增长率（%） ✅ 已确认"""
    return f'=@s_fa_yoydebt("{code}","{report_date}")'


def fin_equity(code: str) -> str:
    """归属母公司股东权益 MRQ（元） ✅ 已确认

    最新报告期(资产负债表)股东权益，连日期参数都不需要。
    """
    return f'=@s_fa_totalequity_mrq("{code}")'


def fin_equity_yoy_growth(code: str, report_date: str) -> str:
    """归属母公司股东权益 比年初增长率（%）—— 业绩快报版"""
    return f'=@s_performanceexpress_eqy_growth("{code}","{report_date}")'


def fin_free_cf(code: str, report_date: str) -> str:
    """企业自由现金流量 FCFF（元） ✅ 已确认

    息前税后利润 + 折旧与摊销 - 净营运资本增加 - 资本支出
    全部投资人（股东+债权人）可支配的现金流量总和。

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"
    """
    return f'=@s_fa_fcff("{code}","{report_date}")'


def fin_free_cf_per_share(code: str, report_date: str) -> str:
    """每股企业自由现金流量（元） ✅ 已确认

    s_fa_fcff / 期末总股本

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"
    """
    return f'=@s_fa_fcffps("{code}","{report_date}")'


def val_pe_ttm(code: str, trade_date: str | None = None) -> str:
    """市盈率 PE(TTM) ✅ 已确认

    总市值2 / 归属母公司股东的净利润 TTM

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日，默认系统日期
    """
    td = _td(trade_date)
    return f'=@s_val_pe_ttm("{code}","{td}")'


def val_pb_lf(code: str, trade_date: str | None = None) -> str:
    """市净率 PB(LF) ✅ 已确认

    总市值2 / 归属母公司普通股股东权益 LF

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日，默认系统日期
    """
    td = _td(trade_date)
    return f'=@s_val_pb_lf("{code}","{td}")'


def val_pcf_ocf_ttm(code: str, trade_date: str | None = None) -> str:
    """市现率 PCF（经营现金流 TTM，可回测） ✅ 已确认

    总市值2 / 经营活动现金净流量 TTM
    可回测的估值指标。

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日，默认系统日期
    """
    td = _td(trade_date)
    return f'=@s_val_pcf_ocfttm_ard("{code}","{td}")'


def val_pcf_ocf_lyr(code: str, trade_date: str | None = None, match_rule: int = 10) -> str:
    """市现率 PCF（经营现金流，最新年报 LYR） ✅ 已确认

    收盘价 × 总股本 / 经营活动产生的现金流量
    不可回测。

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日，默认系统日期
        match_rule: 财务匹配规则 2=上年年报 10=最新年报(LYR) 等
    """
    td = _td(trade_date)
    return f'=@pcf_ocf_o("{code}","{td}",{match_rule})'


# ===== 行业/指数数据 =====


def industry_sw(code: str, trade_date: str | None = None, level: int = 1) -> str:
    """申万行业分类 (2021) ✅ 已确认

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日期，默认系统日期
        level: 行业级别 1-一级 2-二级 3-三级 4-全部明细
    """
    td = _td(trade_date)
    return f'=@s_info_industry_sw_2021("{code}","{td}",{level})'


def industry_sw_level2(code: str, trade_date: str | None = None) -> str:
    """申万二级行业分类（industry_sw 的便捷包装）"""
    return industry_sw(code, trade_date, level=2)


def industry_sw_level3(code: str, trade_date: str | None = None) -> str:
    """申万三级行业分类（industry_sw 的便捷包装）"""
    return industry_sw(code, trade_date, level=3)


def index_close(index_code: str, trade_date: str) -> str:
    """指数收盘价 ✅ 已确认（i_dq_* 为指数专用前缀）"""
    return f'=@i_dq_close("{index_code}","{trade_date}")'


def index_pct_change(index_code: str, trade_date: str) -> str:
    """指数涨跌幅（%） ✅ 已确认"""
    return f'=@i_dq_pctchange("{index_code}","{trade_date}")'


def index_weight(code: str, trade_date: str | None = None, index_code: str = "000300.SH") -> str:
    """所属指数权重（%） ✅ 已确认

    Args:
        code: 证券Wind代码
        trade_date: 交易日期，默认系统日期
        index_code: 相关指数的Wind代码，默认沪深300
    """
    td = _td(trade_date)
    return f'=@s_info_indexweight("{code}","{td}","{index_code}")'


# ===== 资金流向 =====


def moneyflow_main_force(code: str, trade_date: str) -> str:
    """主力净流入额（元） ✅ 已确认

    主力买入金额 - 主力卖出金额，"主力"指超大单与大单的合计。
    """
    return f'=@s_mfd_inflow_m("{code}","{trade_date}")'


def moneyflow_main_force_open(code: str, trade_date: str) -> str:
    """开盘主力净流入额（元） ✅ 已确认

    10点前的主力净流入金额。
    """
    return f'=@s_mfd_inflow_open_m("{code}","{trade_date}")'


def moneyflow_main_force_close(code: str, trade_date: str) -> str:
    """尾盘主力净流入额（元） ✅ 已确认

    14:30后的主力净流入金额。
    """
    return f'=@s_mfd_inflow_close_m("{code}","{trade_date}")'


def north_bound_shares(code: str, trade_date: str) -> str:
    """沪(深)股通持股数量（股） ✅ 已确认

    中央结算系统持股量。
    """
    return f'=@s_share_n("{code}","{trade_date}")'


def north_bound_pct(code: str, trade_date: str) -> str:
    """沪(深)股通持股占比（%） ✅ 已确认

    占上市及交易的A股总数的百分比。
    注：2024/08/19起披露规则调整，每季度公布一次，日常前推。
    """
    return f'=@s_share_pct_n("{code}","{trade_date}")'


# ===== 股东/持有人数据 =====


def holder_num(code: str, report_date: str, share_type: str = "总股本") -> str:
    """股东户数 ✅ 已确认

    Args:
        code: Wind代码或交易代码
        report_date: 报告期
        share_type: 股本类型，"总股本"或"流通股本"
    """
    return f'=@s_holder_num2("{code}","{report_date}","{share_type}")'


def holder_liq_num(code: str, trade_date: str) -> str:
    """流通股东户数 ✅ 已确认

    Args:
        code: Wind代码或交易代码
        trade_date: 交易日期
    """
    return f'=@s_liqholder_num("{code}","{trade_date}")'


def holder_avg_hold(code: str, report_date: str, share_type: int = 2) -> str:
    """户均持股数量（股） ✅ 已确认

    按总股本：户均持股数 = 总股本 / 股东总户数

    Args:
        code: Wind代码或交易代码
        report_date: 报告期
        share_type: 1=流通股本 2=总股本
    """
    return f'=@s_holder_avgnum("{code}","{report_date}",{share_type})'


def holder_avg_pct(code: str, report_date: str, share_type: int = 2) -> str:
    """户均持股比例（‰） ✅ 已确认

    按总股本：[总股本/股东总户数) / 总股本] × 1000‰

    Args:
        code: Wind代码或交易代码
        report_date: 报告期
        share_type: 1=流通股本 2=总股本
    """
    return f'=@s_holder_avgpct("{code}","{report_date}",{share_type})'


def top10_holder_pct(code: str, report_date: str) -> str:
    """前十大股东持股比例合计（%） ✅ 已确认

    指定报告期，上市公司持股比例排名前十位股东持股合计数占公司总股本的比例。

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"
    """
    return f'=@s_holder_sumt10pct("{code}","{report_date}")'


def top10_holder_quantity(code: str, report_date: str) -> str:
    """前十大股东持股数量合计（股） ✅ 已确认

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"
    """
    return f'=@s_holder_sumt10quantity("{code}","{report_date}")'


def institutional_hold(code: str, report_date: str) -> str:
    """机构持股数量合计（股） ✅ 已确认

    基金+券商+QFII+保险+社保+年金+信托+财务公司+银行+一般法人+阳光私募+陆股通 等合计。

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"
    """
    return f'=@s_holder_totalbyinst("{code}","{report_date}")'


def institutional_hold_pct(code: str, report_date: str) -> str:
    """机构持股比例合计（%） ✅ 已确认

    机构持股合计 / 流通A股 * 100%

    Args:
        code: Wind代码或交易代码
        report_date: 报告期，如 "2024/12/31"
    """
    return f'=@s_holder_pctbyinst("{code}","{report_date}")'
