"""Goldar public-source collectors with block-level last-good preservation."""

from __future__ import annotations

import asyncio
import csv
import io
import math
import re
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from core.observability import get_logger

from ..sources import (
    clamp,
    fred_series_map,
    get_bytes,
    get_json,
    latest_change,
    source_record,
    utc_now,
    zscore,
)
from .contracts import GoldSnapshot
from .store import GoldSnapshotStore

log = get_logger(__name__)
WGC_SUPPLY = "https://fsapi-china.gold.org/api/v11/charts/supply-and-demand/41"
WGC_ETF = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/flows-chart2"
SPDR = "https://api.spdrgoldshares.com/api/v1/data?product=gld&exchange=NYSE&lang=en"
CBOE = "https://cdn.cboe.com/api/global/delayed_quotes/options/GLD.json"
CFTC_PAGE = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"
FRED_IDS = ("DFII10", "DTWEXBGS", "T5YIFR", "EXPINF10YR", "GVZCLS")
WEIGHTS = {"fundamental": 35, "flow": 30, "trading": 20, "derivatives": 15}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30, follow_redirects=True)


def _direction(change: float, epsilon: float = 0.02) -> str:
    if change > epsilon:
        return "上行"
    if change < -epsilon:
        return "下行"
    return "稳定"


def _factor(dimension: str, score: float, raw_value: str) -> dict:
    labels = {"fundamental": "基本面", "flow": "资金流", "trading": "交易", "derivatives": "衍生品"}
    normalized = clamp(score, -2.5, 2.5)
    return {
        "dimension": dimension,
        "label": labels[dimension],
        "value": round(normalized * WEIGHTS[dimension] / 100, 3),
        "score": round(normalized, 3),
        "weight": WEIGHTS[dimension],
        "raw_value": raw_value,
        "monitor_only": False,
    }


def _first_number(value: str) -> float:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group()) if match else 0.0


class GoldCollector:
    def __init__(
        self,
        store: GoldSnapshotStore,
        client_factory: Callable[[], httpx.AsyncClient] = _client,
    ) -> None:
        self.store = store
        self.client_factory = client_factory
        self.lock = asyncio.Lock()

    def _replace_factor(self, value: dict, factor: dict) -> None:
        factors = value["pricing_drivers"]["factors"]
        value["pricing_drivers"]["factors"] = [
            factor if item["dimension"] == factor["dimension"] else item for item in factors
        ]

    def _finish(self, value: dict) -> GoldSnapshot:
        blocks = [
            value["market_context"],
            value["pricing_drivers"],
            value["supply_demand"],
            value["cycle_macro"],
            value["options"],
            value["allocation_context"],
        ]
        gaps = {gap["id"]: gap for block in blocks for gap in block.get("gaps", [])}
        value["gaps"] = list(gaps.values())
        factors = value["pricing_drivers"]["factors"]
        score = round(sum(float(item["value"]) for item in factors), 3)
        critical = blocks[:5]
        unresolved_fixture = any(
            str(item.get("raw_value", "")).startswith("样例") for item in factors
        )
        blocked = (
            unresolved_fixture
            or any(block["status"] in {"fixture", "missing", "stale"} for block in critical)
            or any(gap["severity"] == "high" for gap in value["gaps"])
        )
        label = (
            "待核验" if blocked else "偏强" if score >= 0.3 else "偏弱" if score <= -0.3 else "中性"
        )
        ordered = sorted(factors, key=lambda item: item["value"])
        coverage_weights = [15, 20, 20, 10, 20, 15]
        coverage = sum(
            weight
            for block, weight in zip(blocks, coverage_weights, strict=True)
            if block["status"] not in {"fixture", "missing", "stale"}
        )
        next_check = value["gaps"][0]["next_check"] if value["gaps"] else "等待下一次官方数据更新。"
        value.update(
            as_of=max(str(block["as_of"]) for block in blocks),
            fetched_at=utc_now(),
            status=label,
            coverage=coverage,
        )
        value["research_state"].update(
            label=label,
            score=score,
            confidence=min(95, coverage),
            supports=[
                f"{item['label']} {item['value']:+.2f}"
                for item in reversed(ordered)
                if item["value"] > 0
            ][:3],
            drags=[
                f"{item['label']} {item['value']:+.2f}" for item in ordered if item["value"] < 0
            ][:3],
            next_check=next_check,
            model_weights=WEIGHTS,
        )
        return self.store.write(GoldSnapshot.model_validate(value))

    def _mark_failure(self, fields: tuple[str, ...], code: str) -> None:
        value = self.store.read().model_dump(mode="json")
        checked = utc_now()
        for field in fields:
            block = value[field]
            block["checked_at"] = checked
            block["failure_code"] = code
            block["status"] = "missing" if block["status"] == "fixture" else "stale"
        self._finish(value)
        log.warning("gold_collector_degraded", fields=list(fields), failure_code=code)

    async def collect_macro(self) -> None:
        async with self.lock:
            try:
                async with self.client_factory() as client:
                    series, wgc_etf, spdr = await asyncio.gather(
                        fred_series_map(client, FRED_IDS),
                        get_json(client, WGC_ETF),
                        get_json(client, SPDR),
                    )
                rows: list[list[dict[str, Any]]] = [series[item] for item in FRED_IDS]
                real, dollar, inflation5, inflation10, gvz = (series[item] for item in FRED_IDS)
                monthly = wgc_etf["chartData"]["data"]["Monthly"]["series"]["tonnes"]
                gold_raw = next(
                    item["data"] for item in monthly if item["name"] == "Gold Price (rhs)"
                )
                gold: list[dict[str, Any]] = [
                    {
                        "date": datetime.fromtimestamp(float(item[0]) / 1000, UTC)
                        .date()
                        .isoformat(),
                        "value": float(item[1]),
                    }
                    for item in gold_raw[-72:]
                ]
                fixing = spdr["data"]["pm_fix_usd"]
                fixing_value = _first_number(str(fixing["value"]))
                fixing_date = (
                    datetime.strptime(str(fixing["date"]), "%B %d, %Y")
                    .replace(tzinfo=UTC)
                    .date()
                    .isoformat()
                )
                if fixing_date > gold[-1]["date"]:
                    gold.append({"date": fixing_date, "value": fixing_value})
                real_changes = [
                    real[index]["value"] - real[index - 63]["value"]
                    for index in range(63, len(real))
                ]
                dollar_changes = [
                    (dollar[index]["value"] / dollar[index - 63]["value"] - 1) * 100
                    for index in range(63, len(dollar))
                ]
                fundamental = (
                    -zscore(real_changes)
                    - zscore(dollar_changes)
                    + zscore([item["value"] for item in inflation5])
                    + zscore([item["value"] for item in inflation10])
                ) / 4
                momentum_1m = latest_change(gold, 1, percent=True)
                momentum_6m = latest_change(gold, 6, percent=True)
                deviations = []
                for index in range(19, len(gold)):
                    average = sum(item["value"] for item in gold[index - 19 : index + 1]) / 20
                    deviations.append((gold[index]["value"] / average - 1) * 100)
                trading = (
                    zscore(
                        [
                            latest_change(gold[: index + 1], 1, percent=True)
                            for index in range(1, len(gold))
                        ]
                    )
                    + zscore(
                        [
                            latest_change(gold[: index + 1], 6, percent=True)
                            for index in range(6, len(gold))
                        ]
                    )
                    + zscore(deviations)
                ) / 3
                now = utc_now()
                value = self.store.read().model_dump(mode="json")
                latest_gold = gold[-1]
                recent_gold = gold[-24:]
                value["market_context"] = {
                    "as_of": latest_gold["date"],
                    "fetched_at": now,
                    "checked_at": now,
                    "failure_code": None,
                    "status": "complete",
                    "sources": [
                        source_record(
                            "World Gold Council · Gold Price",
                            "https://www.gold.org/goldhub/data/gold-prices",
                            latest_gold["date"],
                            "USD/oz",
                            "monthly Goldhub history; SPDR PM fix latest cross-check",
                        )
                    ],
                    "gaps": [],
                    "price": latest_gold["value"],
                    "change_percent": latest_change(gold, 1, percent=True),
                    "range_low": min(item["value"] for item in gold[-12:]),
                    "range_high": max(item["value"] for item in gold[-12:]),
                    "series": [
                        {"label": item["date"][5:], "value": item["value"]} for item in recent_gold
                    ],
                }
                fred_sources = [
                    source_record(
                        "FRED",
                        "https://fred.stlouisfed.org/",
                        max(item[-1]["date"] for item in rows),
                        "mixed",
                        "official series; rolling five-year normalization",
                    )
                ]
                self._replace_factor(
                    value,
                    _factor(
                        "fundamental",
                        fundamental,
                        f"实际利率{latest_change(real, 63):+.2f}pct · 美元{latest_change(dollar, 63, percent=True):+.1f}%",
                    ),
                )
                self._replace_factor(
                    value,
                    _factor("trading", trading, f"1M {momentum_1m:+.1f}% · 6M {momentum_6m:+.1f}%"),
                )
                value["pricing_drivers"].update(
                    as_of=max(real[-1]["date"], dollar[-1]["date"]),
                    fetched_at=now,
                    checked_at=now,
                    failure_code=None,
                    status="partial",
                    sources=fred_sources,
                    relationships=[
                        {
                            "label": "10Y 实际利率",
                            "value": f"{real[-1]['value']:.2f}%",
                            "direction": _direction(latest_change(real, 21)),
                            "interpretation": "机会成本的核心观察值",
                        },
                        {
                            "label": "广义美元",
                            "value": f"{dollar[-1]['value']:.2f}",
                            "direction": _direction(latest_change(dollar, 21, percent=True), 0.25),
                            "interpretation": "贸易加权美元约束",
                        },
                        {
                            "label": "5Y5Y 通胀",
                            "value": f"{inflation5[-1]['value']:.2f}%",
                            "direction": _direction(latest_change(inflation5, 3)),
                            "interpretation": "市场长期通胀补偿",
                        },
                        {
                            "label": "GVZ",
                            "value": f"{gvz[-1]['value']:.2f}",
                            "direction": _direction(latest_change(gvz, 21), 0.5),
                            "interpretation": "仅监控黄金尾部波动",
                        },
                    ],
                )
                value["cycle_macro"].update(
                    as_of=real[-1]["date"],
                    fetched_at=now,
                    checked_at=now,
                    failure_code=None,
                    status="complete",
                    sources=fred_sources,
                    policy_phase="实际利率与美元机制切换",
                )
                self._finish(value)
                log.info("gold_macro_collected", as_of=latest_gold["date"])
            except (httpx.HTTPError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
                self._mark_failure(
                    ("market_context", "pricing_drivers", "cycle_macro"), "gold_macro_failed"
                )
                log.warning("gold_macro_collect_failed", error_type=type(exc).__name__)

    async def collect_goldhub(self) -> None:
        async with self.lock:
            try:
                async with self.client_factory() as client:
                    supply, etf, spdr = await asyncio.gather(
                        get_json(client, WGC_SUPPLY),
                        get_json(client, WGC_ETF),
                        get_json(client, SPDR),
                    )
                chart = supply["chartData"]
                demand = chart["Demand_Annually"]
                wanted = {
                    "Jewellery fabrication": "珠宝",
                    "Technology": "科技",
                    "Investment": "投资",
                    "Central banks": "央行",
                }
                categories = []
                for item in demand["series"]:
                    if item.get("name") in wanted and len(item.get("data", [])) >= 2:
                        categories.append(
                            {
                                "label": wanted[item["name"]],
                                "current": item["data"][-1],
                                "previous": item["data"][-2],
                            }
                        )
                central_bank = next(item for item in categories if item["label"] == "央行")
                monthly = etf["chartData"]["data"]["Monthly"]["series"]["tonnes"]
                fund_series = [item for item in monthly if item.get("name") != "Gold Price (rhs)"]
                latest_flows = [float(item["data"][-1][1]) for item in fund_series]
                etf_flow = sum(latest_flows)
                tonnes = spdr["data"]["total_tonnes"]
                observed = str(chart.get("asOfDate") or demand["categories"][-1])
                now = utc_now()
                value = self.store.read().model_dump(mode="json")
                value["supply_demand"] = {
                    "as_of": observed,
                    "fetched_at": now,
                    "checked_at": now,
                    "failure_code": None,
                    "status": "complete",
                    "sources": [
                        source_record(
                            "World Gold Council Goldhub",
                            "https://www.gold.org/goldhub/data",
                            observed,
                            "tonnes",
                            "annual demand and monthly ETF flows",
                        ),
                        source_record(
                            "SPDR Gold Shares",
                            "https://www.spdrgoldshares.com/usa/gld/",
                            str(tonnes.get("date")),
                            "tonnes",
                            "published GLD holdings cross-check",
                        ),
                    ],
                    "gaps": [
                        {
                            "id": "goldhub-quarterly-lag",
                            "label": "供需数据低于市场价格频率",
                            "severity": "low",
                            "next_check": "Goldhub更新后重算",
                        }
                    ],
                    "categories": categories,
                    "flows": [
                        {
                            "label": "全球黄金ETF月度净流",
                            "value": f"{etf_flow:+.1f} t",
                            "note": "按Goldhub区域合计",
                        },
                        {
                            "label": "SPDR GLD持仓",
                            "value": f"{tonnes.get('value')!s} t",
                            "note": str(tonnes.get("date")),
                        },
                        {
                            "label": "年度央行需求",
                            "value": f"{central_bank['current']:.1f} t",
                            "note": "WGC年度需求口径",
                        },
                    ],
                }
                flow_score = clamp(
                    etf_flow / 50 + (central_bank["current"] - central_bank["previous"]) / 500,
                    -2.5,
                    2.5,
                )
                self._replace_factor(
                    value,
                    _factor(
                        "flow",
                        flow_score,
                        f"ETF {etf_flow:+.1f}t · 央行 {central_bank['current']:.0f}t",
                    ),
                )
                pricing_sources = [
                    *value["pricing_drivers"].get("sources", []),
                    *value["supply_demand"]["sources"],
                ]
                value["pricing_drivers"]["sources"] = list(
                    {item["url"]: item for item in pricing_sources}.values()
                )
                self._finish(value)
                log.info("gold_goldhub_collected", as_of=observed)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                self._mark_failure(("supply_demand",), "gold_goldhub_failed")
                log.warning("gold_goldhub_collect_failed", error_type=type(exc).__name__)

    async def collect_options(self) -> None:
        async with self.lock:
            try:
                async with self.client_factory() as client:
                    payload = await get_json(client, CBOE)
                data = payload["data"]
                spot = float(data["current_price"])
                pattern = re.compile(r"^GLD(\d{6})([CP])(\d{8})$")
                aggregate: dict[float, dict[str, float]] = {}
                call_oi = put_oi = 0.0
                for row in data["options"]:
                    match = pattern.match(str(row.get("option", "")))
                    if not match:
                        continue
                    strike = int(match.group(3)) / 1000
                    if not spot * 0.75 <= strike <= spot * 1.25:
                        continue
                    oi = float(row.get("open_interest") or 0)
                    side = "call" if match.group(2) == "C" else "put"
                    aggregate.setdefault(strike, {"call": 0, "put": 0})[side] += oi
                    call_oi += oi if side == "call" else 0
                    put_oi += oi if side == "put" else 0
                selected = sorted(
                    aggregate.items(), key=lambda item: sum(item[1].values()), reverse=True
                )[:6]
                selected.sort()
                strikes = [
                    {
                        "label": f"GLD {strike:g}",
                        "value": round((sides["call"] + sides["put"]) / 1000, 1),
                        "side": "pressure" if sides["call"] > sides["put"] else "support",
                    }
                    for strike, sides in selected
                ]
                ratio = put_oi / call_oi if call_oi else 0
                derivatives = clamp(-math.log2(ratio) / 3 if ratio > 0 else 0, -2.5, 2.5)
                now = utc_now()
                observed = str(payload.get("timestamp") or data.get("last_trade_time") or now)
                value = self.store.read().model_dump(mode="json")
                positioning = [
                    item
                    for item in value["options"]["positioning"]
                    if item["label"] == "管理基金净多"
                ]
                retained_sources = [
                    item
                    for item in value["options"].get("sources", [])
                    if "cftc" in item["url"].casefold()
                ]
                value["options"] = {
                    "as_of": observed[:10],
                    "fetched_at": now,
                    "checked_at": now,
                    "failure_code": None,
                    "status": "proxy",
                    "sources": [
                        *retained_sources,
                        source_record(
                            "Cboe delayed GLD options",
                            CBOE,
                            observed[:10],
                            "contracts",
                            "listed GLD option proxy",
                            proxy=True,
                        ),
                    ],
                    "gaps": [
                        {
                            "id": "otc-options",
                            "label": "场外期权敞口不可得",
                            "severity": "medium",
                            "next_check": "继续用GLD上市期权交叉验证CFTC",
                        }
                    ],
                    "positioning": [
                        *positioning,
                        {
                            "label": "GLD Put/Call OI",
                            "value": f"{ratio:.2f}",
                            "note": "全到期日、现价上下25%",
                        },
                        {
                            "label": "GLD 30日隐波",
                            "value": f"{float(data.get('iv30') or 0) * 100:.1f}%",
                            "note": "Cboe延迟行情",
                        },
                    ],
                    "strikes": strikes,
                }
                self._replace_factor(
                    value, _factor("derivatives", derivatives, f"GLD Put/Call OI {ratio:.2f}")
                )
                self._finish(value)
                log.info("gold_options_collected", as_of=observed[:10])
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                self._mark_failure(("options",), "gold_options_failed")
                log.warning("gold_options_collect_failed", error_type=type(exc).__name__)

    async def collect_cftc(self) -> None:
        async with self.lock:
            try:
                year = datetime.now(UTC).year
                urls = [
                    f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{item}.zip"
                    for item in range(year - 4, year + 1)
                ]
                async with self.client_factory() as client:
                    archives = await asyncio.gather(*(get_bytes(client, url) for url in urls))
                rows = []
                for payload in archives:
                    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                        name = next(
                            item for item in archive.namelist() if item.lower().endswith(".txt")
                        )
                        reader = csv.DictReader(
                            io.TextIOWrapper(archive.open(name), encoding="utf-8-sig")
                        )
                        for row in reader:
                            if str(row.get("CFTC_Contract_Market_Code", "")).strip() == "088691":
                                rows.append(row)
                rows.sort(key=lambda item: str(item["Report_Date_as_YYYY-MM-DD"]))
                nets = [
                    float(item["M_Money_Positions_Long_All"])
                    - float(item["M_Money_Positions_Short_All"])
                    for item in rows
                ]
                latest = nets[-1]
                percentile = sum(item <= latest for item in nets) / len(nets) * 100
                now = utc_now()
                observed = str(rows[-1]["Report_Date_as_YYYY-MM-DD"])
                value = self.store.read().model_dump(mode="json")
                retained = [
                    item
                    for item in value["options"]["positioning"]
                    if item["label"] != "管理基金净多"
                ]
                value["options"]["positioning"] = [
                    {
                        "label": "管理基金净多",
                        "value": f"{latest / 1000:.0f}k",
                        "note": f"五年 {percentile:.0f}% 分位",
                    },
                    *retained,
                ]
                value["options"]["sources"] = [
                    *[
                        item
                        for item in value["options"].get("sources", [])
                        if "cftc" not in item["url"].casefold()
                    ],
                    source_record(
                        "CFTC Disaggregated COT",
                        CFTC_PAGE,
                        observed,
                        "contracts",
                        "COMEX gold money manager long minus short",
                    ),
                ]
                value["options"]["checked_at"] = now
                etf_flow = next(
                    (
                        _first_number(item["value"])
                        for item in value["supply_demand"].get("flows", [])
                        if "ETF" in item["label"]
                    ),
                    0.0,
                )
                central_bank = next(
                    (
                        item
                        for item in value["supply_demand"].get("categories", [])
                        if item["label"] == "央行"
                    ),
                    {"current": 0.0, "previous": 0.0},
                )
                base_flow = (
                    etf_flow / 50
                    + (float(central_bank["current"]) - float(central_bank["previous"])) / 500
                )
                flow_score = clamp(base_flow + clamp((nets[-1] - nets[-5]) / 100000), -2.5, 2.5)
                self._replace_factor(
                    value,
                    _factor(
                        "flow", flow_score, f"CFTC净多 {latest / 1000:.0f}k · {percentile:.0f}%分位"
                    ),
                )
                self._finish(value)
                log.info("gold_cftc_collected", as_of=observed)
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                IndexError,
                StopIteration,
                zipfile.BadZipFile,
            ) as exc:
                value = self.store.read().model_dump(mode="json")
                options = value["options"]
                options["checked_at"] = utc_now()
                options["failure_code"] = "gold_cftc_failed"
                if options["status"] == "fixture":
                    options["status"] = "missing"
                options["gaps"] = [
                    *[gap for gap in options.get("gaps", []) if gap["id"] != "cftc-refresh"],
                    {
                        "id": "cftc-refresh",
                        "label": "CFTC周度持仓刷新失败",
                        "severity": "medium",
                        "next_check": "下一次周度任务重试；保留最后成功持仓",
                    },
                ]
                self._finish(value)
                log.warning("gold_cftc_collect_failed", error_type=type(exc).__name__)
