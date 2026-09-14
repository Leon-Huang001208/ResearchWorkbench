"""Q-P-g-M-X public collectors with independent last-good block updates."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from core.observability import get_logger

from ..sources import (
    clamp,
    fred_series_map,
    get_json,
    get_list,
    latest_change,
    source_record,
    utc_now,
)
from .contracts import DollarSnapshot
from .store import DollarSnapshotStore

log = get_logger(__name__)
FRED = "https://fred.stlouisfed.org/"
NY_RATES = "https://markets.newyorkfed.org/api/rates/all/search.json"
FISCAL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
AUCTIONS = "https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json"
FRED_IDS = (
    "WALCL",
    "WRESBAL",
    "RRPONTSYD",
    "WDTGAL",
    "DFII10",
    "DGS2",
    "DGS10",
    "IORB",
    "DTWEXBGS",
    "DEXJPUS",
    "DEXCHUS",
    "DEXUSEU",
    "BAMLH0A0HYM2",
    "TRESEGUSM052N",
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30, follow_redirects=True)


def _nearest(points: list[dict], date: str) -> float:
    eligible = [item for item in points if item["date"] <= date]
    if not eligible:
        raise ValueError("aligned series history is insufficient")
    return float(eligible[-1]["value"])


def _series(label: str, unit: str, points: list[dict], count: int = 60) -> dict:
    return {"label": label, "unit": unit, "points": points[-count:]}


def _metric(
    label: str, value: str, direction: str, interpretation: str, proxy: bool = False
) -> dict:
    return {
        "label": label,
        "value": value,
        "direction": direction,
        "interpretation": interpretation,
        "proxy": proxy,
    }


def _trend(value: float, epsilon: float) -> str:
    if value > epsilon:
        return "上行"
    if value < -epsilon:
        return "下行"
    return "稳定"


class DollarCollector:
    def __init__(
        self,
        store: DollarSnapshotStore,
        client_factory: Callable[[], httpx.AsyncClient] = _client,
    ) -> None:
        self.store = store
        self.client_factory = client_factory
        self.lock = asyncio.Lock()

    def _finish(self, value: dict) -> DollarSnapshot:
        dimensions = [
            value[name]
            for name in ("quantity_q", "price_p", "fiscal_g", "plumbing_m", "cross_border_x")
        ]
        scores = [item["score"] for item in dimensions if item.get("score") is not None]
        known = sum(float(item) for item in scores) / 5
        missing = 5 - len(scores)
        possible_low = clamp(known - missing / 5)
        possible_high = clamp(known + missing / 5)
        blocked = (
            missing > 0
            or any(item["status"] in {"fixture", "missing", "stale"} for item in dimensions)
            or any(gap["severity"] == "high" for item in dimensions for gap in item.get("gaps", []))
        )
        score = None if blocked else round(known, 3)
        label = (
            "待核验" if blocked else "偏松" if known > 0.15 else "偏紧" if known < -0.15 else "中性"
        )
        gaps = {gap["id"]: gap for block in dimensions for gap in block.get("gaps", [])}
        gaps.update({gap["id"]: gap for gap in value["transmission"].get("gaps", [])})
        value["gaps"] = list(gaps.values())
        coverage = sum(
            18 for item in dimensions if item["status"] not in {"fixture", "missing", "stale"}
        )
        if value["transmission"]["status"] not in {"fixture", "missing", "stale"}:
            coverage += 10
        ranked = sorted(
            (
                (item["label"], item["score"])
                for item in dimensions
                if item.get("score") is not None
            ),
            key=lambda item: item[1],
        )
        value.update(
            as_of=max(str(item["as_of"]) for item in dimensions),
            fetched_at=utc_now(),
            status=label,
            coverage=coverage,
        )
        value["research_state"].update(
            label=label,
            score=score,
            known_subtotal=round(known, 3),
            possible_low=round(possible_low, 3),
            possible_high=round(possible_high, 3),
            confidence=min(95, coverage),
            supports=[f"{name} {score:+.2f}" for name, score in reversed(ranked) if score > 0][:3],
            drags=[f"{name} {score:+.2f}" for name, score in ranked if score < 0][:3],
            next_check=(
                value["gaps"][0]["next_check"] if value["gaps"] else "等待下一次官方数据更新。"
            ),
        )
        return self.store.write(DollarSnapshot.model_validate(value))

    def _mark_failure(self, fields: tuple[str, ...], code: str) -> None:
        value = self.store.read().model_dump(mode="json")
        checked = utc_now()
        for field in fields:
            block = value[field]
            block["checked_at"] = checked
            block["failure_code"] = code
            block["status"] = "missing" if block["status"] == "fixture" else "stale"
        self._finish(value)
        log.warning("dollar_collector_degraded", fields=list(fields), failure_code=code)

    async def collect_core(self) -> None:
        async with self.lock:
            try:
                async with self.client_factory() as client:
                    rows = await fred_series_map(client, FRED_IDS)
                    start = (datetime.now(UTC).date() - timedelta(days=180)).isoformat()
                    end = datetime.now(UTC).date().isoformat()
                    rates = await get_json(client, f"{NY_RATES}?startDate={start}&endDate={end}")
                fred_rows = [rows[item] for item in FRED_IDS]
                walcl = [{**item, "value": item["value"] / 1000} for item in rows["WALCL"]]
                reserves = [{**item, "value": item["value"] / 1000} for item in rows["WRESBAL"]]
                rrp = rows["RRPONTSYD"]
                tga = [{**item, "value": item["value"] / 1000} for item in rows["WDTGAL"]]
                net = [
                    {
                        "date": item["date"],
                        "value": item["value"]
                        - _nearest(tga, item["date"])
                        - _nearest(rrp, item["date"]),
                    }
                    for item in walcl
                ]
                real = rows["DFII10"]
                dollar = rows["DTWEXBGS"]
                hy = rows["BAMLH0A0HYM2"]
                q_score = clamp(latest_change(reserves, 4, percent=True) / 5)
                p_score = clamp(-latest_change(real, 21) / 0.5)
                g_score = clamp(latest_change(net, 4) / 200)
                m_score = clamp(-latest_change(hy, 21) / 0.75)
                x_score = clamp(-latest_change(dollar, 21, percent=True) / 3)
                rate_rows = rates.get("refRates") or []
                sofr_rows = sorted(
                    (
                        {"date": item["effectiveDate"], "value": float(item["percentRate"])}
                        for item in rate_rows
                        if item.get("type") == "SOFR" and item.get("percentRate") is not None
                    ),
                    key=lambda item: item["date"],
                )
                if len(sofr_rows) < 2:
                    raise ValueError("New York Fed SOFR history is insufficient")
                iorb = rows["IORB"]
                spread = [
                    {
                        "date": item["date"],
                        "value": (item["value"] - _nearest(iorb, item["date"])) * 100,
                    }
                    for item in sofr_rows
                ]
                now = utc_now()
                observed = max(item[-1]["date"] for item in fred_rows)
                fred_source = source_record(
                    "FRED · original agencies",
                    FRED,
                    observed,
                    "mixed",
                    "native frequency; 30-day or four-week signal",
                )
                ny_source = source_record(
                    "Federal Reserve Bank of New York",
                    "https://markets.newyorkfed.org/",
                    sofr_rows[-1]["date"],
                    "%",
                    "official reference rates",
                )
                value = self.store.read().model_dump(mode="json")
                common = {"fetched_at": now, "checked_at": now, "failure_code": None}
                value["quantity_q"] = {
                    **common,
                    "as_of": reserves[-1]["date"],
                    "status": "complete",
                    "sources": [fred_source],
                    "gaps": [],
                    "key": "Q",
                    "label": "总量水库",
                    "score": round(q_score, 3),
                    "summary": "准备金变化决定银行体系水位；联储总资产不能单独等同风险资产资金。",
                    "metrics": [
                        _metric(
                            "银行准备金",
                            f"${reserves[-1]['value'] / 1000:.2f}tn",
                            _trend(latest_change(reserves, 4), 25),
                            "四周变化用于Q信号",
                        ),
                        _metric(
                            "ON RRP",
                            f"${rrp[-1]['value']:.0f}bn",
                            _trend(latest_change(rrp, 21), 10),
                            "非银现金缓冲，不直接称为放水",
                        ),
                        _metric(
                            "净流动性代理",
                            f"${net[-1]['value'] / 1000:.2f}tn",
                            _trend(latest_change(net, 4), 25),
                            "WALCL−TGA−ON RRP，仅为代理",
                            True,
                        ),
                    ],
                    "series": [
                        _series("银行准备金", "十亿美元", reserves),
                        _series("净流动性代理", "十亿美元", net),
                    ],
                }
                value["price_p"] = {
                    **common,
                    "as_of": max(real[-1]["date"], sofr_rows[-1]["date"]),
                    "status": "partial",
                    "sources": [fred_source, ny_source],
                    "gaps": [
                        {
                            "id": "mpt-live",
                            "label": "Atlanta Fed MPT与最新SEP尚未结构化",
                            "severity": "medium",
                            "next_check": "下一次官方发布后核验政策路径",
                        }
                    ],
                    "key": "P",
                    "label": "资金价格",
                    "score": round(p_score, 3),
                    "summary": "实际利率与政策走廊共同决定美元资金价格。",
                    "metrics": [
                        _metric(
                            "10Y实际利率",
                            f"{real[-1]['value']:.2f}%",
                            _trend(latest_change(real, 21), 0.05),
                            "30日变化反号进入P信号",
                        ),
                        _metric(
                            "2Y−10Y",
                            f"{rows['DGS10'][-1]['value'] - rows['DGS2'][-1]['value']:+.2f}pct",
                            "曲线",
                            "固定期限美债曲线",
                        ),
                        _metric(
                            "SOFR",
                            f"{sofr_rows[-1]['value']:.2f}%",
                            _trend(latest_change(sofr_rows, 21), 0.05),
                            "官方成交量加权参考利率",
                        ),
                    ],
                    "series": [
                        _series("2Y", "%", rows["DGS2"]),
                        _series("10Y", "%", rows["DGS10"]),
                        _series("SOFR", "%", sofr_rows),
                    ],
                }
                value["fiscal_g"] = {
                    **common,
                    "as_of": tga[-1]["date"],
                    "status": "proxy",
                    "sources": [
                        source_record(
                            "FRED WDTGAL",
                            "https://fred.stlouisfed.org/series/WDTGAL",
                            tga[-1]["date"],
                            "USD billions",
                            "weekly Wednesday fallback",
                            proxy=True,
                        )
                    ],
                    "gaps": [
                        {
                            "id": "daily-tga-pending",
                            "label": "日度TGA等待FiscalData刷新",
                            "severity": "medium",
                            "next_check": "下一次财政日度任务重试",
                        }
                    ],
                    "key": "g",
                    "label": "财政水流",
                    "score": round(g_score, 3),
                    "summary": "TGA与发行结算改变财政资金在政府账户和市场之间的时点分布。",
                    "metrics": [
                        _metric(
                            "TGA周三余额",
                            f"${tga[-1]['value']:.0f}bn",
                            _trend(latest_change(tga, 4), 25),
                            "日度DTS失败时的周频代理",
                            True,
                        )
                    ],
                    "series": [
                        _series("TGA周三余额", "十亿美元", tga),
                        _series("净流动性代理", "十亿美元", net),
                    ],
                }
                value["plumbing_m"] = {
                    **common,
                    "as_of": spread[-1]["date"],
                    "status": "partial",
                    "sources": [fred_source, ny_source],
                    "gaps": [
                        {
                            "id": "dealer-balance-sheet",
                            "label": "一级交易商头寸与交割失败等待周度刷新",
                            "severity": "medium",
                            "next_check": "纽约联储周度发布后补齐",
                        }
                    ],
                    "key": "M",
                    "label": "融资管道",
                    "score": round(m_score, 3),
                    "summary": "SOFR相对IORB与信用利差共同检查融资管道是否偏离政策锚。",
                    "metrics": [
                        _metric(
                            "SOFR−IORB",
                            f"{spread[-1]['value']:+.0f}bp",
                            _trend(latest_change(spread, 5), 2),
                            "隔夜融资相对准备金利率",
                        ),
                        _metric(
                            "高收益信用利差",
                            f"{hy[-1]['value']:.2f}%",
                            _trend(latest_change(hy, 21), 0.1),
                            "30日变化反号进入M信号",
                        ),
                    ],
                    "series": [
                        _series("SOFR−IORB", "bp", spread),
                        _series("高收益信用利差", "%", hy),
                    ],
                }
                custody = [
                    {**item, "value": item["value"] / 1000} for item in rows["TRESEGUSM052N"]
                ]
                value["cross_border_x"] = {
                    **common,
                    "as_of": dollar[-1]["date"],
                    "status": "partial",
                    "sources": [fred_source],
                    "gaps": [
                        {
                            "id": "cross-currency-basis",
                            "label": "稳定跨币种基差序列不可得",
                            "severity": "medium",
                            "next_check": "接入可审计来源前保持显式缺口",
                        }
                    ],
                    "key": "X",
                    "label": "跨境美元",
                    "score": round(x_score, 3),
                    "summary": "广义美元与主要汇率反映跨境价格压力，但不等同资本流量。",
                    "metrics": [
                        _metric(
                            "广义美元",
                            f"{dollar[-1]['value']:.2f}",
                            _trend(latest_change(dollar, 21, percent=True), 0.5),
                            "30日变化反号进入X信号",
                        ),
                        _metric(
                            "USD/JPY",
                            f"{rows['DEXJPUS'][-1]['value']:.2f}",
                            _trend(latest_change(rows["DEXJPUS"], 21, percent=True), 1),
                            "主要汇率代理",
                            True,
                        ),
                        _metric(
                            "外国官方托管美债",
                            f"${custody[-1]['value']:.0f}bn",
                            _trend(latest_change(custody, 1), 10),
                            "不代表全部海外美债持仓",
                            True,
                        ),
                    ],
                    "series": [
                        _series("广义美元", "指数", dollar),
                        _series("USD/JPY", "JPY/USD", rows["DEXJPUS"]),
                        _series("外国官方托管", "十亿美元", custody),
                    ],
                }
                value["transmission"].update(
                    as_of=observed,
                    fetched_at=now,
                    checked_at=now,
                    failure_code=None,
                    status="complete",
                    sources=[fred_source, ny_source],
                    gaps=[],
                    links=[
                        {
                            "source": "Q准备金",
                            "target": "风险资产",
                            "state": "支撑" if q_score > 0 else "约束",
                            "explanation": "总量变化需由资金价格和融资管道确认",
                        },
                        {
                            "source": "P实际利率",
                            "target": "黄金",
                            "state": "支撑" if p_score > 0 else "约束",
                            "explanation": "实际贴现率改变无息资产机会成本",
                        },
                        {
                            "source": "X广义美元",
                            "target": "海外融资",
                            "state": "缓和" if x_score > 0 else "收紧",
                            "explanation": "美元价格影响非美借款人的偿付条件",
                        },
                    ],
                )
                value["evidence"] = [
                    {
                        "date": observed,
                        "source": "FRED",
                        "observation": "Q-P-g-M-X核心公开序列已刷新",
                        "use": "五维状态",
                        "quality": "原始频率",
                        "url": FRED,
                    },
                    {
                        "date": sofr_rows[-1]["date"],
                        "source": "New York Fed",
                        "observation": f"SOFR−IORB为{spread[-1]['value']:+.0f}bp",
                        "use": "融资管道",
                        "quality": "官方参考利率",
                        "url": "https://markets.newyorkfed.org/",
                    },
                ]
                self._finish(value)
                log.info("dollar_core_collected", as_of=observed)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                self._mark_failure(
                    ("quantity_q", "price_p", "fiscal_g", "plumbing_m", "cross_border_x"),
                    "dollar_core_failed",
                )
                log.warning("dollar_core_collect_failed", error_type=type(exc).__name__)

    async def collect_fiscal(self) -> None:
        async with self.lock:
            try:
                start = (datetime.now(UTC).date() - timedelta(days=180)).isoformat()
                params = f"?filter=record_date:gte:{start}&sort=record_date&page[size]=10000"
                async with self.client_factory() as client:
                    fiscal, auctions = await asyncio.gather(
                        get_json(client, FISCAL + params),
                        get_list(client, AUCTIONS),
                    )
                points: list[dict[str, Any]] = []
                for row in fiscal["data"]:
                    account = str(row.get("account_type", ""))
                    raw = row.get("close_today_bal")
                    if raw in {None, "", "null"}:
                        raw = row.get("open_today_bal")
                    if account == "Treasury General Account (TGA) Closing Balance" and raw not in {
                        None,
                        "",
                        "null",
                    }:
                        points.append({"date": row["record_date"], "value": float(raw) / 1000})
                unique = {item["date"]: item for item in points}
                points = [unique[key] for key in sorted(unique)]
                if len(points) < 8:
                    raise ValueError("fiscal source history is insufficient")
                settlement: list[dict[str, Any]] = []
                events: list[dict[str, Any]] = []
                for item in auctions:
                    amount = float(item.get("offeringAmount") or 0) / 1_000_000_000
                    date = str(item.get("issueDate") or "")[:10]
                    if date and amount > 0:
                        settlement.append({"date": date, "value": amount})
                        events.append(
                            {
                                "date": date,
                                "type": "国债结算",
                                "title": f"{item.get('securityTerm', '')} {item.get('securityType', '')}".strip(),
                                "impact": f"计划结算约{amount:.0f}十亿美元",
                                "status": "已公告",
                            }
                        )
                if len(settlement) < 2:
                    settlement = [
                        {"date": points[-2]["date"], "value": 0},
                        {"date": points[-1]["date"], "value": 0},
                    ]
                now = utc_now()
                value = self.store.read().model_dump(mode="json")
                old_score = value["fiscal_g"]["score"]
                value["fiscal_g"] = {
                    "as_of": points[-1]["date"],
                    "fetched_at": now,
                    "checked_at": now,
                    "failure_code": None,
                    "status": "complete",
                    "sources": [
                        source_record(
                            "U.S. Treasury FiscalData",
                            "https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/",
                            points[-1]["date"],
                            "USD billions",
                            "daily closing TGA balance",
                        ),
                        source_record(
                            "TreasuryDirect",
                            "https://www.treasurydirect.gov/auctions/announcements-data-results/",
                            max(item["date"] for item in settlement),
                            "USD billions",
                            "announced offering amount and issue date",
                        ),
                    ],
                    "gaps": [],
                    "key": "g",
                    "label": "财政水流",
                    "score": old_score,
                    "summary": "日度TGA与已公告发行结算共同展示财政水流时点。",
                    "metrics": [
                        _metric(
                            "TGA日终余额",
                            f"${points[-1]['value']:.0f}bn",
                            _trend(latest_change(points, 21), 25),
                            "DTS日度官方余额",
                        ),
                        _metric(
                            "近期开奖结算",
                            f"${sum(item['value'] for item in settlement[-5:]):.0f}bn",
                            "已公告",
                            "发行额不是净财政抽水",
                            True,
                        ),
                    ],
                    "series": [
                        _series("TGA日终余额", "十亿美元", points),
                        _series("国债结算", "十亿美元", settlement),
                    ],
                }
                value["events"] = events[-20:]
                self._finish(value)
                log.info("dollar_fiscal_collected", as_of=points[-1]["date"])
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                self._mark_failure(("fiscal_g",), "dollar_fiscal_failed")
                log.warning("dollar_fiscal_collect_failed", error_type=type(exc).__name__)
