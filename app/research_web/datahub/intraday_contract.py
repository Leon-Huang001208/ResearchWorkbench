"""CJPY 0.5.2 minute definitions verified from real vendor dictionary 2026-10-26."""

import hashlib
import json

from .providers import ProviderError

DEFINITIONS = [
    {
        "中文名": "成交量",
        "单位/计算规则": "股票：股；指数：上交所高频为手、日线为股，深交所/中证/申万高频和日线为股；基金：份；期货/期权：合约数量；债券：深交所历史成交量 2003-12-08 起由手变为张，上交所为手。",
        "字段名": "vol",
        "类型": "real",
        "详细说明": "周期内成交量。如果周期为分钟，则表示该分钟成交量，并非从开盘累计。",
    },
    {
        "中文名": "成交金额",
        "单位/计算规则": "股票：元；沪深交易所指数：元；中证指数高频为万元、日线为元；申万指数高频和日线为元；基金/债券：元；期货/期权：元。郑商所发布的成交金额未乘以合约乘数。",
        "字段名": "amount",
        "类型": "real",
        "详细说明": "周期内成交金额。如果周期为分钟，则表示该分钟成交金额，并非从开盘累计。",
    },
    {
        "中文名": "前日收盘",
        "单位/计算规则": "",
        "字段名": "sectional_yclose",
        "类型": "real",
        "详细说明": "上一交易日（日周期）的收盘价。与 yclose“上次价”不同；yclose 表示前一个周期的收盘价。",
    },
    {
        "中文名": "时点当日累计成交量",
        "单位/计算规则": "成交量 = 主买 + 主卖。",
        "字段名": "sectional_vol",
        "类型": "real",
        "详细说明": "从开盘到当前时间的成交量之和。",
    },
    {
        "中文名": "时点当日累计成交金额",
        "单位/计算规则": "成交金额 = 主买 + 主卖。",
        "字段名": "sectional_amount",
        "类型": "real",
        "详细说明": "从开盘到当前时间的成交金额之和。",
    },
]


def validate_definitions(rows):
    observed = {row.get("字段名"): row for row in rows}
    for expected in DEFINITIONS:
        if any(
            observed.get(expected["字段名"], {}).get(key) != value
            for key, value in expected.items()
        ):
            raise ProviderError("intraday_field_definition_changed")
    return hashlib.sha256(
        json.dumps(DEFINITIONS, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
