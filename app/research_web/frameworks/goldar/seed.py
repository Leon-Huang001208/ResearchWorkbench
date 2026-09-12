"""Deterministic offline snapshot used until each live source is configured."""

import hashlib
import json

from .contracts import GoldSnapshot

AS_OF = "2026-08-30"
FETCHED_AT = "2026-08-30T16:00:00+08:00"


def _source(name: str, url: str, observed_at: str, unit: str, method: str, proxy=False):
    return {
        "name": name,
        "url": url,
        "observed_at": observed_at,
        "unit": unit,
        "method": method,
        "proxy": proxy,
    }


def compute_revision(value: dict) -> str:
    payload = {key: item for key, item in value.items() if key != "revision"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_seed() -> GoldSnapshot:
    fred = _source("FRED", "https://fred.stlouisfed.org/", AS_OF, "mixed", "offline fixture")
    goldhub = _source(
        "World Gold Council Goldhub",
        "https://www.gold.org/goldhub/data",
        "2026 Q2",
        "tonnes",
        "offline fixture",
    )
    gld = _source(
        "GLD options",
        "https://www.cboe.com/",
        "2026-08-29",
        "contracts",
        "listed option proxy fixture",
        True,
    )
    value = {
        "schema_version": 1,
        "revision": "0" * 64,
        "as_of": AS_OF,
        "fetched_at": FETCHED_AT,
        "status": "待核验",
        "coverage": 78,
        "market_context": {
            "as_of": AS_OF,
            "fetched_at": FETCHED_AT,
            "status": "fixture",
            "sources": [
                _source(
                    "Illustrative gold series",
                    "https://example.invalid/gold-fixture",
                    AS_OF,
                    "USD/oz",
                    "offline fixture",
                )
            ],
            "gaps": [],
            "price": 2516.4,
            "change_percent": 0.7,
            "range_low": 2384,
            "range_high": 2531,
            "series": [
                {"label": label, "value": price}
                for label, price in zip(
                    [
                        "06/14",
                        "06/21",
                        "06/28",
                        "07/05",
                        "07/12",
                        "07/19",
                        "07/26",
                        "08/02",
                        "08/09",
                        "08/16",
                        "08/23",
                        "08/30",
                    ],
                    [2384, 2398, 2411, 2406, 2432, 2458, 2449, 2476, 2492, 2487, 2510, 2516],
                    strict=True,
                )
            ],
        },
        "pricing_drivers": {
            "as_of": AS_OF,
            "fetched_at": FETCHED_AT,
            "status": "fixture",
            "sources": [fred],
            "gaps": [],
            "factors": [
                {"label": "实际利率", "value": 0.31},
                {"label": "美元", "value": -0.18},
                {"label": "通胀预期", "value": 0.12},
                {"label": "风险波动", "value": 0.08},
                {"label": "资金流", "value": 0.09},
            ],
            "relationships": [
                {
                    "label": "10Y 实际利率",
                    "value": "1.71%",
                    "direction": "回落",
                    "interpretation": "机会成本边际缓和",
                },
                {
                    "label": "美元指数",
                    "value": "102.4",
                    "direction": "震荡",
                    "interpretation": "尚未提供趋势确认",
                },
                {
                    "label": "10Y 盈亏平衡通胀",
                    "value": "2.31%",
                    "direction": "抬升",
                    "interpretation": "通胀补偿温和扩张",
                },
                {
                    "label": "VIX",
                    "value": "18.6",
                    "direction": "上行",
                    "interpretation": "避险需求有所增加",
                },
            ],
        },
        "supply_demand": {
            "as_of": "2026 Q2",
            "fetched_at": FETCHED_AT,
            "status": "fixture",
            "sources": [goldhub],
            "gaps": [
                {
                    "id": "goldhub-q3",
                    "label": "2026 Q3 尚未发布",
                    "severity": "medium",
                    "next_check": "Goldhub 季报发布后更新",
                }
            ],
            "categories": [
                {"label": "珠宝", "current": 391, "previous": 476},
                {"label": "科技", "current": 81, "previous": 79},
                {"label": "央行", "current": 244, "previous": 229},
                {"label": "投资", "current": 477, "previous": 382},
            ],
            "flows": [
                {"label": "黄金 ETF 月度净流", "value": "+38 t", "note": "连续第二月转正"},
                {"label": "央行季度净购金", "value": "244 t", "note": "仍高于五年中位数"},
                {"label": "期现基差", "value": "+0.34%", "note": "近月结构平稳"},
            ],
        },
        "cycle_macro": {
            "as_of": AS_OF,
            "fetched_at": FETCHED_AT,
            "status": "fixture",
            "sources": [fred],
            "gaps": [],
            "policy_phase": "通胀后再平衡",
            "regimes": [
                {
                    "label": "增长放缓 / 通胀回落",
                    "fit": "较有利",
                    "reason": "实际利率与美元约束可能同步缓和",
                },
                {
                    "label": "增长强劲 / 通胀黏性",
                    "fit": "中性",
                    "reason": "名义价格支撑与紧缩约束并存",
                },
                {"label": "增长下行 / 通胀抬升", "fit": "有利", "reason": "避险与通胀补偿共同增强"},
            ],
        },
        "options": {
            "as_of": "2026-08-29",
            "fetched_at": FETCHED_AT,
            "status": "proxy",
            "sources": [gld],
            "gaps": [
                {
                    "id": "otc-options",
                    "label": "场外期权敞口不可得",
                    "severity": "medium",
                    "next_check": "继续用 GLD 上市期权作代理并显式标注",
                }
            ],
            "positioning": [
                {"label": "管理基金净多", "value": "182k", "note": "71% 历史分位"},
                {"label": "GVZ", "value": "17.8", "note": "一月均值 16.9"},
                {"label": "看跌 / 看涨", "value": "0.84", "note": "保护需求抬升"},
            ],
            "strikes": [
                {"label": "GLD 220", "value": 18, "side": "neutral"},
                {"label": "GLD 225", "value": 34, "side": "support"},
                {"label": "GLD 230", "value": 49, "side": "support"},
                {"label": "GLD 235", "value": 61, "side": "pressure"},
                {"label": "GLD 240", "value": 43, "side": "pressure"},
            ],
        },
        "research_state": {
            "label": "待核验",
            "score": 0.42,
            "confidence": 64,
            "supports": ["实际利率回落", "ETF 流向改善", "央行需求仍具韧性"],
            "drags": ["美元尚未形成趋势性走弱", "期权上方压力集中"],
            "next_check": "核验最新央行购金与 CFTC 周度持仓是否同向确认。",
        },
        "allocation_context": {
            "as_of": "2016-01 / 2026-08",
            "fetched_at": FETCHED_AT,
            "status": "fixture",
            "sources": [
                _source(
                    "Illustrative allocation study",
                    "https://example.invalid/allocation-fixture",
                    "2016-01 / 2026-08",
                    "monthly return",
                    "offline fixture",
                )
            ],
            "gaps": [
                {
                    "id": "allocation-costs",
                    "label": "未纳入税费与交易约束",
                    "severity": "low",
                    "next_check": "仅作历史背景，不形成仓位建议",
                }
            ],
            "diversification_note": "历史样例中，黄金与美元负相关、与股债相关性较低；关系会随制度切换。",
            "drawdown_note": "黄金可缓和部分风险资产回撤，但流动性冲击初期也可能同步下跌。",
            "scenarios": [
                {
                    "label": "实际利率快速下行",
                    "gold": "+",
                    "equities": "0 / +",
                    "bonds": "+",
                    "note": "黄金与债券可能共同受益",
                },
                {
                    "label": "美元流动性收紧",
                    "gold": "-",
                    "equities": "-",
                    "bonds": "0 / +",
                    "note": "先看美元与实际利率谁占主导",
                },
                {
                    "label": "滞胀冲击",
                    "gold": "+",
                    "equities": "-",
                    "bonds": "-",
                    "note": "分散化价值通常更突出",
                },
            ],
        },
        "events": [
            {
                "date": "09/06",
                "type": "宏观",
                "title": "美国非农与失业率",
                "impact": "验证增长降温是否延续",
                "status": "待发生",
            },
            {
                "date": "09/12",
                "type": "通胀",
                "title": "美国 CPI",
                "impact": "更新实际利率与通胀补偿链",
                "status": "待发生",
            },
            {
                "date": "09/18",
                "type": "政策",
                "title": "FOMC 决议",
                "impact": "更新 Fed 周期判断",
                "status": "待发生",
            },
            {
                "date": "周五",
                "type": "持仓",
                "title": "CFTC 周报",
                "impact": "检查价格与净多是否背离",
                "status": "周期性",
            },
        ],
        "evidence": [
            {
                "date": AS_OF,
                "source": "FRED",
                "observation": "实际利率较月内高点回落",
                "use": "支撑定价驱动",
                "quality": "直接指标",
                "url": "https://fred.stlouisfed.org/",
            },
            {
                "date": "2026-08-29",
                "source": "CFTC",
                "observation": "管理基金净多位于偏高分位",
                "use": "提示拥挤风险",
                "quality": "周频",
                "url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            },
            {
                "date": "2026 Q2",
                "source": "Goldhub",
                "observation": "投资需求改善、央行需求保持韧性",
                "use": "支撑资金与实物需求",
                "quality": "季度",
                "url": "https://www.gold.org/goldhub/data",
            },
            {
                "date": "2026-08-29",
                "source": "GLD 期权",
                "observation": "上方执行价未平仓量集中",
                "use": "提示短期压力区",
                "quality": "代理指标",
                "url": "https://www.cboe.com/",
            },
        ],
        "gaps": [
            {
                "id": "central-bank-monthly",
                "label": "央行购金月度序列待更新",
                "severity": "high",
                "next_check": "核验 Goldhub 最新月度数据",
            },
            {
                "id": "otc-options",
                "label": "场外期权敞口不可得，使用 GLD 期权代理",
                "severity": "medium",
                "next_check": "保持代理标签并交叉验证 CFTC",
            },
        ],
    }
    normalized = GoldSnapshot.model_validate(value).model_dump(mode="json")
    normalized["revision"] = compute_revision(normalized)
    return GoldSnapshot.model_validate(normalized)
