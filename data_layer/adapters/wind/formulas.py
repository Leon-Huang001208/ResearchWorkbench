"""Wind 公式常量定义 —— Mac 版 Wind Excel 插件

公式来源: Wind Excel 函数浏览器 (已逐个验证)
命名规律: s_west_<indicator>_fy{N}(WindCode, tradeDate)
  - fy1 = 最近预测年度, fy2 = 次近, fy3 = 最远
  - fy1_fy2_fy3 = 三个预测年度平均值
  - tradeDate 默认为系统日期时可省略
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
