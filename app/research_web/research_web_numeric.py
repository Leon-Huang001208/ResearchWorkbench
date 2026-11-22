"""Closed GDP layouts from complete Host-owned web bodies, never search snippets.

Canonical quantities retain the full input hash and exact source spans. Publisher
identity, authenticity and unsupported analysis still need the existing gates.
"""

import hashlib
import re
from decimal import Decimal

from core.observability import get_logger

from .research_business_evidence import _emit

log = get_logger(__name__)
GDP_METRICS = frozenset(
    "gdp_" + metric + "_" + version
    for metric in ("current_price", "real_growth")
    for version in ("preliminary", "final")
)
NUMBER = r"[0-9]+(?:\.[0-9]+)?"
TABLE = re.compile(
    r"(?m)^表1\s*(?P<year>\d{4})年四季度和全年GDP初步核算数据\s+"
    r"绝对额（亿元）\s+比上年同期增长（%）\s+四季度\s+全年\s+四季度\s+全年\s+GDP\s+"
    r"(?P<quarter>" + NUMBER + r")\s+(?P<amount>" + NUMBER + r")\s+"
    r"(?P<quarter_growth>" + NUMBER + r")\s+(?P<growth>" + NUMBER + r")(?=\s|$)"
)
FINAL = re.compile(
    r"(?m)^经最终核实，(?P<year>\d{4})年，GDP现价总量为(?P<amount>" + NUMBER + r")亿元，"
    r"比初步核算数减少"
    + NUMBER
    + r"亿元；按不变价格计算，比上年增长(?P<growth>"
    + NUMBER
    + r")%，与初步核算数持平。$"
)
PRELIMINARY = re.compile(
    r"(?m)^一、综合\s*\n初步核算，全年国内生产总值(?:\[\d+\])?(?P<amount>" + NUMBER + r")亿元，"
    r"比上年增长(?P<growth>" + NUMBER + r")%。"
)
PROSE_BASIS = re.compile(
    r"(?m)^\[2\]国内生产总值、三次产业及相关行业增加值、地区生产总值、人均国内生产总值和国民总收入"
    r"绝对数按现价计算，增长速度按不变价格计算。"
    r"(?:根据第五次全国经济普查结果，并同步实施城镇居民自有住房服务核算方法改革，"
    r"对国内生产总值、三次产业及相关行业增加值、全员劳动生产率等历史数据"
    r"（包括图1、图2、图3、图9、图10、图11）进行了修订。)?$"
)


def web_numeric_observations(item, *, scope):
    """Extract only supported unambiguous annual periods, versions and units."""
    try:
        body = item["content"]
        if (
            not isinstance(scope, str)
            or not 0 < len(scope) <= 4096
            or not re.fullmatch(r"web:[a-f0-9]{24}", item["id"])
            or item["id"] != item["source_id"]
            or not isinstance(body, str)
            or len(body.encode()) > 800000
            or hashlib.sha256(body.encode()).hexdigest() != item["sha256"]
        ):
            raise ValueError("web_numeric_scope_or_bytes_invalid")
        candidates = []
        basis = re.search(r"(?m)^(?:注：)?1\.绝对额按现价计算，增长速度按不变价计算[；;]?$", body)
        if basis:
            candidates.extend(
                (m, m["year"], "preliminary", [m, basis]) for m in TABLE.finditer(body)
            )
        titles = list(
            re.finditer(r"中华人民共和国(?P<year>\d{4})年国民经济和社会发展统计公报", body[:1500])
        )
        years = {m["year"] for m in titles}
        prose_basis = PROSE_BASIS.search(body)
        if len(years) == 1 and prose_basis:
            candidates.extend(
                (m, next(iter(years)), "preliminary", [titles[0], m, prose_basis])
                for m in PRELIMINARY.finditer(body)
            )
        candidates.extend((m, m["year"], "final", [m]) for m in FINAL.finditer(body))
        rows = {}
        for match, year, version, spans in candidates:
            if not 1900 <= int(year) <= 2100:
                raise ValueError("web_numeric_period_invalid")
            proof = {
                "source_id": item["id"],
                "sha256": item["sha256"],
                "offset_unit": "unicode_codepoint",
                "spans": [{"start": m.start(), "end": m.end(), "text": m[0]} for m in spans],
            }
            method = (
                "Extracted from the cited annual GDP "
                + version
                + " layout; current-price level and constant-price growth retain separate units. Publisher authenticity and cross-version comparability are not certified."
            )
            for metric, field, unit in (
                ("current_price", "amount", "亿元"),
                ("real_growth", "growth", "%"),
            ):
                name = "gdp_" + metric + "_" + version
                value = Decimal(match[field])
                key = (name, year)
                if key in rows and Decimal(rows[key]["value"]) != value:
                    raise ValueError("web_numeric_conflicting_layout")
                rows.setdefault(key, _emit(scope, name, year, value, unit, [proof], method=method))
        log.info("research_web_numeric_projected", observation_count=len(rows))
        return list(rows.values())
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        log.warning("research_web_numeric_unavailable", error_type=type(exc).__name__)
        return []
