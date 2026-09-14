"""Deterministic offline Dollar snapshot for tests and first-load disclosure."""

from ..storage import compute_revision
from .contracts import DollarSnapshot

AS_OF = "2026-09-03"
FETCHED_AT = "2026-09-03T16:00:00+08:00"


def _source(name: str, url: str, unit: str, method: str, proxy: bool = False) -> dict:
    return {
        "name": name,
        "url": url,
        "observed_at": AS_OF,
        "unit": unit,
        "method": method,
        "proxy": proxy,
    }


def _points(values: list[float]) -> list[dict]:
    dates = ["04/03", "05/01", "05/29", "06/26", "07/24", "08/21", "09/03"]
    return [{"date": date, "value": value} for date, value in zip(dates, values, strict=True)]


def _block(key: str, label: str, score: float, metrics: list[dict], series: list[dict]) -> dict:
    return {
        "as_of": AS_OF,
        "fetched_at": FETCHED_AT,
        "status": "fixture",
        "sources": [
            _source(
                "Deterministic offline fixture",
                "https://example.invalid/dollar-fixture",
                "mixed",
                "offline fixture",
                True,
            )
        ],
        "gaps": [],
        "key": key,
        "label": label,
        "score": score,
        "summary": metrics[0]["interpretation"],
        "metrics": metrics,
        "series": series,
    }


def build_seed() -> DollarSnapshot:
    value = {
        "schema_version": 1,
        "revision": "0" * 64,
        "as_of": AS_OF,
        "fetched_at": FETCHED_AT,
        "status": "待核验",
        "coverage": 72,
        "quantity_q": _block(
            "Q",
            "总量水库",
            0.2,
            [
                {
                    "label": "准备金",
                    "value": "$3.32tn",
                    "direction": "回升",
                    "interpretation": "银行体系水位边际改善",
                },
                {
                    "label": "ON RRP",
                    "value": "$0.11tn",
                    "direction": "低位",
                    "interpretation": "非银缓冲已明显缩小",
                },
            ],
            [
                {
                    "label": "准备金",
                    "unit": "十亿美元",
                    "points": _points([3120, 3160, 3110, 3180, 3210, 3260, 3320]),
                },
                {
                    "label": "净流动性代理",
                    "unit": "十亿美元",
                    "points": _points([5720, 5780, 5740, 5810, 5890, 5940, 5990]),
                },
            ],
        ),
        "price_p": _block(
            "P",
            "资金价格",
            -0.1,
            [
                {
                    "label": "10Y 实际利率",
                    "value": "1.79%",
                    "direction": "偏高",
                    "interpretation": "长期美元资金价格仍具约束",
                },
                {
                    "label": "SOFR",
                    "value": "4.08%",
                    "direction": "稳定",
                    "interpretation": "隔夜价格仍围绕政策走廊",
                },
            ],
            [
                {
                    "label": "2Y",
                    "unit": "%",
                    "points": _points([4.12, 4.08, 4.01, 3.98, 4.05, 4.11, 4.03]),
                },
                {
                    "label": "10Y",
                    "unit": "%",
                    "points": _points([4.25, 4.31, 4.28, 4.35, 4.29, 4.22, 4.19]),
                },
            ],
        ),
        "fiscal_g": _block(
            "g",
            "财政水流",
            0.1,
            [
                {
                    "label": "TGA",
                    "value": "$0.71tn",
                    "direction": "回落",
                    "interpretation": "财政账户下降对市场形成边际注入",
                    "proxy": False,
                },
                {
                    "label": "未来7日结算",
                    "value": "$126bn",
                    "direction": "集中",
                    "interpretation": "发行结算仍可能造成短期抽水",
                    "proxy": True,
                },
            ],
            [
                {
                    "label": "TGA",
                    "unit": "十亿美元",
                    "points": _points([820, 790, 760, 745, 730, 720, 710]),
                },
                {
                    "label": "国债结算",
                    "unit": "十亿美元",
                    "points": _points([86, 101, 92, 118, 95, 110, 126]),
                },
            ],
        ),
        "plumbing_m": _block(
            "M",
            "融资管道",
            0.0,
            [
                {
                    "label": "SOFR−IORB",
                    "value": "+3bp",
                    "direction": "正常",
                    "interpretation": "隔夜融资尚未显著脱离政策锚",
                },
                {
                    "label": "交割失败",
                    "value": "$48bn",
                    "direction": "抬升",
                    "interpretation": "需要继续核验交易商资产负债表压力",
                },
            ],
            [
                {"label": "SOFR−IORB", "unit": "bp", "points": _points([1, 2, 1, 2, 4, 2, 3])},
                {
                    "label": "国债交割失败",
                    "unit": "十亿美元",
                    "points": _points([22, 27, 24, 31, 29, 35, 48]),
                },
            ],
        ),
        "cross_border_x": _block(
            "X",
            "跨境美元",
            -0.2,
            [
                {
                    "label": "广义美元",
                    "value": "121.4",
                    "direction": "走强",
                    "interpretation": "海外美元条件边际收紧",
                },
                {
                    "label": "外国官方托管",
                    "value": "$3.29tn",
                    "direction": "稳定",
                    "interpretation": "官方美债需求暂未明显恶化",
                    "proxy": True,
                },
            ],
            [
                {
                    "label": "广义美元",
                    "unit": "指数",
                    "points": _points([118.6, 119.2, 118.9, 119.8, 120.3, 120.9, 121.4]),
                },
                {
                    "label": "外国官方托管",
                    "unit": "十亿美元",
                    "points": _points([3260, 3255, 3272, 3280, 3276, 3288, 3290]),
                },
            ],
        ),
        "research_state": {
            "label": "待核验",
            "score": None,
            "known_subtotal": 0.0,
            "possible_low": -0.2,
            "possible_high": 0.2,
            "confidence": 58,
            "supports": ["准备金边际回升", "TGA 回落形成短期注入"],
            "drags": ["实际利率仍高", "广义美元走强"],
            "next_check": "补齐稳定的跨币种基差，并核验财政结算与交易商交割失败是否共振。",
        },
        "transmission": {
            "as_of": AS_OF,
            "fetched_at": FETCHED_AT,
            "status": "fixture",
            "sources": [
                _source(
                    "Dollar method fixture",
                    "https://example.invalid/dollar-fixture",
                    "qualitative",
                    "offline fixture",
                    True,
                )
            ],
            "gaps": [],
            "links": [
                {
                    "source": "准备金",
                    "target": "风险资产",
                    "state": "边际支撑",
                    "explanation": "总量改善但仍需融资价格确认",
                },
                {
                    "source": "实际利率",
                    "target": "黄金",
                    "state": "约束",
                    "explanation": "持有无息资产的机会成本仍高",
                },
                {
                    "source": "广义美元",
                    "target": "海外融资",
                    "state": "偏紧",
                    "explanation": "美元走强放大非美借款人的偿付压力",
                },
            ],
        },
        "events": [
            {
                "date": "每周四",
                "type": "总量",
                "title": "Fed H.4.1",
                "impact": "更新资产负债表、准备金和外国官方账户",
                "status": "周期性",
            },
            {
                "date": "每日",
                "type": "财政",
                "title": "Daily Treasury Statement",
                "impact": "更新TGA日终余额与水流",
                "status": "周期性",
            },
            {
                "date": "FOMC",
                "type": "政策",
                "title": "利率决议与SEP",
                "impact": "更新政策路径和曲线锚",
                "status": "待核验",
            },
        ],
        "evidence": [
            {
                "date": AS_OF,
                "source": "FRED",
                "observation": "准备金边际回升但实际利率仍高",
                "use": "Q与P",
                "quality": "固定样例",
                "url": "https://fred.stlouisfed.org/",
            },
            {
                "date": AS_OF,
                "source": "U.S. Treasury",
                "observation": "TGA回落与发行结算并存",
                "use": "g",
                "quality": "固定样例",
                "url": "https://fiscaldata.treasury.gov/",
            },
            {
                "date": AS_OF,
                "source": "New York Fed",
                "observation": "SOFR仍靠近IORB",
                "use": "M",
                "quality": "固定样例",
                "url": "https://markets.newyorkfed.org/",
            },
        ],
        "gaps": [
            {
                "id": "cross-currency-basis",
                "label": "稳定跨币种基差序列不可得",
                "severity": "high",
                "next_check": "接入可审计来源前保持X维度待核验",
            },
            {
                "id": "mpt-live",
                "label": "Atlanta Fed政策路径尚未实时更新",
                "severity": "medium",
                "next_check": "以官方MPT发布页补齐政策路径",
            },
        ],
    }
    normalized = DollarSnapshot.model_validate(value).model_dump(mode="json")
    normalized["revision"] = compute_revision(normalized)
    return DollarSnapshot.model_validate(normalized)
