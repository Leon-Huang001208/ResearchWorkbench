"""Bounded Host projections from complete owned excerpts, never model report fields.

Only closed layouts/formulas are supported. Canonical quotes retain original spans,
full excerpt digests and session/task scope. No authenticity or semantic judgement
is inferred beyond supplied bytes and deterministic arithmetic.
"""

import hashlib
import html
import json
import logging
import re
from datetime import datetime
from decimal import Context, Decimal, Inexact, localcontext
from itertools import pairwise

log = logging.getLogger(__name__)
ALGORITHM = "business-excerpts-v1"
METHOD = "Normalized from complete supplied excerpts; external authenticity, implementation and forecasts are not verified."
_TAGS = {
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": "total_revenue",
    "us-gaap:NetIncomeLoss": "net_income",
    "us-gaap:OperatingIncomeLoss": "operating_income",
    "us-gaap:NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": "signed_cash_ppe",
    "us-gaap:PaymentsForRepurchaseOfCommonStock": "signed_share_repurchase",
    "us-gaap:PaymentsOfDividendsCommonStock": "signed_cash_dividends",
    "us-gaap:NetCashProvidedByUsedInFinancingActivities": "net_financing_cash_flow",
}
_LABELS = {
    "total_revenue": {"Total revenue"},
    "net_income": {"Net income"},
    "operating_income": {"Operating income"},
    "operating_cash_flow": {"Net cash from operations"},
    "signed_cash_ppe": {"Additions to property and equipment"},
    "signed_share_repurchase": {"Common stock repurchased"},
    "signed_cash_dividends": {"Common stock cash dividends paid"},
    "net_financing_cash_flow": {"Net cash used in financing", "Net cash from financing"},
}
_MONTHS = {
    n.lower(): i
    for i, n in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}


# Closed published-prose layouts. Unknown attribution, prefix or suffix is unsupported.
# Numeric fields, dates and voter names are parsed data, not expected answers.
_STATEMENT_PREFIXES = (
    (
        "Recent indicators suggest that economic activity has continued to expand at a solid pace.",
        "Job gains have moderated, and the unemployment rate has moved up but remains low.",
        "Inflation has eased over the past year but remains somewhat elevated.",
        "In recent months, there has been some further progress toward the Committee's {objective} percent inflation objective.",
        "The Committee seeks to achieve maximum employment and inflation at the rate of {objective} percent over the longer run.",
        "The Committee judges that the risks to achieving its employment and inflation goals continue to move into better balance.",
        "The economic outlook is uncertain, and the Committee is attentive to the risks to both sides of its dual mandate.",
    ),
    (
        "Recent indicators suggest that economic activity has continued to expand at a solid pace.",
        "Job gains have slowed, and the unemployment rate has moved up but remains low.",
        "Inflation has made further progress toward the Committee's {objective} percent objective but remains somewhat elevated.",
        "The Committee seeks to achieve maximum employment and inflation at the rate of {objective} percent over the longer run.",
        "The Committee has gained greater confidence that inflation is moving sustainably toward {objective} percent, and judges that the risks to achieving its employment and inflation goals are roughly in balance.",
        "The economic outlook is uncertain, and the Committee is attentive to the risks to both sides of its dual mandate.",
    ),
)
_STATEMENT_GUIDANCE = (
    (
        "In considering any adjustments to the target range for the federal funds rate, the Committee will carefully assess incoming data, the evolving outlook, and the balance of risks.",
        "The Committee does not expect it will be appropriate to reduce the target range until it has gained greater confidence that inflation is moving sustainably toward {objective} percent.",
        "In addition, the Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage‑backed securities.",
        "The Committee is strongly committed to returning inflation to its {objective} percent objective.",
        "In assessing the appropriate stance of monetary policy, the Committee will continue to monitor the implications of incoming information for the economic outlook.",
        "The Committee would be prepared to adjust the stance of monetary policy as appropriate if risks emerge that could impede the attainment of the Committee's goals.",
        "The Committee's assessments will take into account a wide range of information, including readings on labor market conditions, inflation pressures and inflation expectations, and financial and international developments.",
    ),
    (
        "In considering additional adjustments to the target range for the federal funds rate, the Committee will carefully assess incoming data, the evolving outlook, and the balance of risks.",
        "The Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage‑backed securities.",
        "The Committee is strongly committed to supporting maximum employment and returning inflation to its {objective} percent objective.",
        "In assessing the appropriate stance of monetary policy, the Committee will continue to monitor the implications of incoming information for the economic outlook.",
        "The Committee would be prepared to adjust the stance of monetary policy as appropriate if risks emerge that could impede the attainment of the Committee's goals.",
        "The Committee's assessments will take into account a wide range of information, including readings on labor market conditions, inflation pressures and inflation expectations, and financial and international developments.",
    ),
)
_IMPLEMENTATION_LAYOUT = "Decisions Regarding Monetary Policy Implementation The Federal Reserve has made the following decisions to implement the monetary policy stance announced by the Federal Open Market Committee in its statement on {announcement}: The Board of Governors of the Federal Reserve System voted unanimously to lower the interest rate paid on reserve balances to {quantity} percent, effective {effective}. As part of its policy decision, the Federal Open Market Committee voted to direct the Open Market Desk at the Federal Reserve Bank of New York, until instructed otherwise, to execute transactions in the System Open Market Account in accordance with the following domestic policy directive: \"Effective {effective}, the Federal Open Market Committee directs the Desk to: Undertake open market operations as necessary to maintain the federal funds rate in a target range of {quantity} to {quantity} percent. Conduct standing overnight repurchase agreement operations with a minimum bid rate of {quantity} percent and with an aggregate operation limit of ${quantity} billion. Conduct standing overnight reverse repurchase agreement operations at an offering rate of {quantity} percent and with a per-counterparty limit of ${quantity} billion per day. Roll over at auction the amount of principal payments from the Federal Reserve's holdings of Treasury securities maturing in each calendar month that exceeds a cap of ${quantity} billion per month. Redeem Treasury coupon securities up to this monthly cap and Treasury bills to the extent that coupon principal payments are less than the monthly cap. Reinvest the amount of principal payments from the Federal Reserve's holdings of agency debt and agency mortgage‑backed securities (MBS) received in each calendar month that exceeds a cap of ${quantity} billion per month into Treasury securities to roughly match the maturity composition of Treasury securities outstanding. Allow modest deviations from stated amounts for reinvestments, if needed for operational reasons. Engage in dollar roll and coupon swap transactions as necessary to facilitate settlement of the Federal Reserve's agency MBS transactions.\" In a related action, the Board of Governors of the Federal Reserve System voted unanimously to approve a {quantity} percentage point decrease in the primary credit rate to {quantity} percent, effective {effective}. In taking this action, the Board approved requests to establish that rate submitted by the Board of Directors of the Federal Reserve Bank of Atlanta. This information will be updated as appropriate to reflect decisions of the Federal Open Market Committee or the Board of Governors regarding details of the Federal Reserve's operational tools and approach used to implement monetary policy. More information regarding open market operations and reinvestments may be found on the Federal Reserve Bank of New York's website ."


def _clean(text):
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = html.unescape(re.sub(r"<[^>]*>", " ", text)).strip()
    if text.startswith("**") and text.endswith("**"):
        text = text[2:-2].strip()
    return text


def _number(text):
    value = _clean(text)
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    if value.startswith("$"):
        value = value[1:].strip()
    if negative and value.startswith(("+", "-")):
        raise ValueError("business_quantity_sign_ambiguous")
    if len(value) > 64 or not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", value):
        raise ValueError("business_quantity_unsupported")
    number = Decimal(value.replace(",", ""))
    if not number.is_finite() or number.copy_abs() > Decimal("1e30"):
        raise ValueError("business_quantity_limit")
    return number.copy_negate() if negative else number


def _proof(item, pieces):
    result = []
    for piece in dict.fromkeys(pieces):
        start = item["content"].find(piece)
        if not piece or start < 0 or item["content"].find(piece, start + 1) >= 0:
            raise ValueError("business_span_ambiguous")
        result.append({"start": start, "end": start + len(piece), "text": piece})
    return {
        "source_id": item["id"],
        "sha256": item["sha256"],
        "offset_unit": "unicode_codepoint",
        "spans": result,
    }


def _emit(scope, metric, period, value, unit, proofs, *, method=METHOD, text=None, heading=None):
    if not proofs:
        raise ValueError("business_proof_missing")
    proofs = sorted(proofs, key=lambda p: p["source_id"])
    content = text if text is not None else f'{metric} {period} {format(value,"f")} {unit}'
    content += "\n" + method
    payload = {
        "algorithm": ALGORITHM,
        "scope_sha256": hashlib.sha256(scope.encode()).hexdigest(),
        "metric": metric,
        "period": period,
        "unit": unit,
        "value": format(value, "f") if value is not None else None,
        "content": content,
        "proofs": proofs,
    }
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return {
        "id": "business_" + hashlib.sha256(encoded).hexdigest()[:32],
        "source_id": proofs[-1]["source_id"],
        "source_ids": [p["source_id"] for p in proofs],
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "kind": "business_numeric" if value is not None else "business_quote",
        "heading": heading or metric,
        **payload,
    }


def _annual(item, scope):
    raw = item["content"]
    lines = raw.splitlines()
    tables = []
    if "Year Ended June 30" not in raw:
        return []
    block = [line for line in lines if line.strip()]
    if len(block) < 5 or any(not line.startswith("|") or not line.endswith("|") for line in block):
        raise ValueError("business_annual_table_block")
    title = [
        line
        for line in lines
        if line.startswith("|")
        and re.fullmatch(
            r"\(In millions(?:, except per share amounts)?\)", _clean(line.split("|")[1])
        )
        and len(line.strip("|").split("|")) == 2
        and re.fullmatch(r"Year Ended June 30,?", _clean(line.strip("|").split("|")[1]))
    ]
    years = [
        (line, [_clean(c) for c in line.strip("|").split("|")])
        for line in lines
        if line.startswith("|")
    ]
    years = [
        (line, cells)
        for line, cells in years
        if 2 <= len(cells) <= 5 and all(re.fullmatch(r"(?:19|20)\d{2}", c) for c in cells)
    ]
    if len(title) != 1 or len(years) != 1 or raw.count("Year Ended June 30") != 1:
        raise ValueError("business_annual_header_ambiguous")
    yearline, columns = years[0]
    if (
        title[0] != block[0]
        or yearline != block[2]
        or any(not re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", block[n]) for n in (1, 3))
    ):
        raise ValueError("business_annual_table_order")
    if len(set(columns)) != len(columns) or columns != sorted(columns, reverse=True):
        raise ValueError("business_annual_period_ambiguous")
    data = {}
    phase = None
    financing = []
    financing_header = None
    total_seen = False
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [_clean(c) for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        tag, label = cells[:2]
        if tag == "ElementName" and label in {"Operations", "Financing", "Investing"}:
            if label == "Financing":
                if financing_header is not None:
                    raise ValueError("business_financing_duplicate")
                financing_header = line
            phase = label
            continue
        if not tag.startswith(("us-gaap:", "msft:")):
            if phase == "Financing" and any(cells[2:]):
                raise ValueError("business_financing_row_unsupported")
            continue
        if tag not in _TAGS and phase != "Financing":
            continue
        if len(cells) != len(columns) + 2:
            raise ValueError("business_annual_columns")
        values = [_number(c) for c in cells[2:]]
        if tag in _TAGS:
            metric = _TAGS[tag]
            if label not in _LABELS[metric]:
                raise ValueError("business_annual_label_conflict")
            required_phase = {
                "operating_cash_flow": "Operations",
                "signed_cash_ppe": "Investing",
                "signed_share_repurchase": "Financing",
                "signed_cash_dividends": "Financing",
                "net_financing_cash_flow": "Financing",
            }.get(metric)
            if required_phase is not None and phase != required_phase:
                raise ValueError("business_annual_phase_conflict")
            if metric == "net_income" and phase not in {None, "Operations"}:
                raise ValueError("business_annual_phase_conflict")
            if metric in data:
                raise ValueError("business_annual_duplicate")
            proof = _proof(item, [title[0], yearline, line])
            data[metric] = (values, proof)
            for year, value in zip(columns, values, strict=True):
                tables.append(_emit(scope, metric, year, value, "millions", [proof]))
        if phase == "Financing":
            if tag == "us-gaap:NetCashProvidedByUsedInFinancingActivities":
                total_seen = True
            elif not total_seen:
                financing.append((values, line))
            else:
                raise ValueError("business_financing_after_total")
    if not data:
        raise ValueError("business_annual_empty")
    with localcontext(Context(prec=128)) as context:
        context.traps[Inexact] = True
        for index, year in enumerate(columns):

            def take(metric, index=index):
                return data[metric][0][index]

            def proof_for(names):
                return _proof(
                    item,
                    [
                        title[0],
                        yearline,
                        *[span["text"] for name in names for span in data[name][1]["spans"][2:]],
                    ],
                )

            if {"operating_cash_flow", "signed_cash_ppe"}.issubset(data) and take(
                "signed_cash_ppe"
            ) <= 0:
                fcf = take("operating_cash_flow") + take("signed_cash_ppe")
                tables.append(
                    _emit(
                        scope,
                        "task_defined_fcf",
                        year,
                        fcf,
                        "millions",
                        [proof_for(["operating_cash_flow", "signed_cash_ppe"])],
                        method="Task-defined operating cash flow plus signed cash additions to property and equipment; this does not establish AI investment returns or future performance.",
                    )
                )
                if (
                    {"signed_share_repurchase", "signed_cash_dividends"}.issubset(data)
                    and take("signed_share_repurchase") <= 0
                    and take("signed_cash_dividends") <= 0
                ):
                    returned = -(take("signed_share_repurchase") + take("signed_cash_dividends"))
                    proof = proof_for(
                        [
                            "operating_cash_flow",
                            "signed_cash_ppe",
                            "signed_share_repurchase",
                            "signed_cash_dividends",
                        ]
                    )
                    tables.append(
                        _emit(scope, "cash_shareholder_return", year, returned, "millions", [proof])
                    )
                    if returned:
                        with localcontext(Context(prec=28)):
                            ratio = fcf / returned
                        tables.append(
                            _emit(
                                scope,
                                "fcf_cash_return_coverage",
                                year,
                                ratio,
                                "ratio",
                                [proof],
                                method="Task-defined free cash flow divided by cash dividends plus cash share repurchases; finite Decimal division uses Host claim arithmetic precision.",
                            )
                        )
            if financing and total_seen and "net_financing_cash_flow" in data:
                difference = take("net_financing_cash_flow") - sum(
                    values[index] for values, _line in financing
                )
                proof = _proof(
                    item,
                    [
                        title[0],
                        yearline,
                        financing_header,
                        *[line for _values, line in financing],
                        data["net_financing_cash_flow"][1]["spans"][-1]["text"],
                    ],
                )
                tables.append(
                    _emit(
                        scope,
                        "financing_reconciliation_difference",
                        year,
                        difference,
                        "millions",
                        [proof],
                        method="Reported net financing cash flow minus all signed rows between the explicit Financing heading and its net total; no omitted rows are inferred.",
                    )
                )
        if int(columns[0]) - int(columns[1]) == 1:
            for metric in ("total_revenue", "net_income"):
                if metric in data and data[metric][0][1]:
                    with localcontext(Context(prec=28)):
                        growth = (
                            (data[metric][0][0] - data[metric][0][1]) / data[metric][0][1] * 100
                        )
                    tables.append(
                        _emit(
                            scope,
                            metric + "_growth_pct",
                            columns[0],
                            growth,
                            "%",
                            [data[metric][1]],
                            method="Latest annual value minus prior adjacent annual value, divided by that prior value, expressed in percent; not a forecast.",
                        )
                    )
    return tables


def _cpi(item, scope):
    raw = item["content"]
    title = re.search(r"(?m)^CONSUMER PRICE INDEX - ([A-Z]+) ((?:19|20)\d{2})\s*$", raw)
    if not title:
        return []
    month = _MONTHS.get(title[1].lower())
    header = [
        line
        for line in raw.splitlines()
        if "Seasonally adjusted changes from preceding month" in line
    ]
    if (
        not month
        or len(header) != 1
        or raw.count(
            "Table A. Percent changes in CPI for All Urban Consumers (CPI-U): U.S. city average"
        )
        != 1
    ):
        raise ValueError("business_cpi_header")
    flattened = _clean(header[0]).replace("-", "").replace(" ", "").lower()
    groups = [_clean(cell) for cell in header[0].strip("|").split("|")]
    if (
        len(groups) != 3
        or groups[0]
        or groups[1] != "Seasonally adjusted changes from preceding month"
        or not re.match(r"^Un-?\s*adjusted", groups[2], re.IGNORECASE)
    ):
        raise ValueError("business_cpi_group_order")
    if "unadjusted" not in flattened or "12mos." not in flattened:
        raise ValueError("business_cpi_seasonality")
    ending = re.fullmatch(
        r"Un-?\s*adjusted\s+12-mos\.\s+ended\s+([A-Za-z]{3})\.\s+(\d{4})",
        groups[2],
        re.IGNORECASE,
    )
    if not ending or ending[1].lower() != title[1][:3].lower() or ending[2] != title[2]:
        raise ValueError("business_cpi_trailing_period")
    period = f"{title[2]}-{month:02d}"
    monthline = [
        line
        for line in raw.splitlines()
        if line.startswith("|")
        and re.search(r"\b" + title[1][:3].title() + r"\.", line)
        and re.search(r"\b" + title[2] + r"\b", line)
        and "Seasonally adjusted" not in line
    ]
    if len(monthline) != 1:
        raise ValueError("business_cpi_period_ambiguous")
    lines = raw.splitlines()
    index = lines.index(header[0])
    month_index = lines.index(monthline[0])
    if month_index != index + 2 or any(
        not re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", lines[n]) for n in (index + 1, index + 3)
    ):
        raise ValueError("business_cpi_table_order")
    end = index + 4
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    caption = next(
        (
            i
            for i, line in enumerate(lines)
            if "Table A. Percent changes in CPI for All Urban Consumers (CPI-U): U.S. city average"
            in line
        ),
        -1,
    )
    if (
        caption >= 0
        and lines[caption].strip()
        != "Table A. Percent changes in CPI for All Urban Consumers (CPI-U): U.S. city average"
    ):
        raise ValueError("business_cpi_caption_ambiguous")
    if caption < end or any(line.strip() not in {"", "```"} for line in lines[end:caption]):
        raise ValueError("business_cpi_table_caption")
    monthcells = [_clean(c) for c in monthline[0].strip("|").split("|")]
    parsed = []
    for cell in monthcells:
        match = re.fullmatch(r"([A-Za-z]{3})\.\s*((?:19|20)\d{2})", cell)
        if not match:
            raise ValueError("business_cpi_month_columns")
        number = next((n for name, n in _MONTHS.items() if name.startswith(match[1].lower())), None)
        parsed.append((int(match[2]), number))
    if (
        parsed[-1] != (int(title[2]), month)
        or len(parsed) != 7
        or any(y != int(title[2]) or m is None for y, m in parsed)
        or [m for _y, m in parsed] != list(range(month - 6, month + 1))
    ):
        raise ValueError("business_cpi_period_columns")
    rows = {}
    measured = {}
    result = []
    labels = {
        "All items": "headline",
        "All items less food and energy": "core",
        "Energy": "energy",
        "Gasoline (all types)": "gasoline",
        "Food": "food",
    }
    for line in lines[index + 4 : end]:
        if not line.startswith("|"):
            continue
        cells = [_clean(c) for c in line.strip("|").split("|")]
        if cells[0] not in labels:
            continue
        label = cells[0]
        if label in rows or len(cells) != 9:
            raise ValueError("business_cpi_row_ambiguous")
        rows[label] = line
        values = [_number(c) for c in cells[1:]]
        proof = _proof(item, [title[0].strip(), header[0], monthline[0], line, lines[caption]])
        measured[labels[label]] = (values, proof)
        for metric, value in (
            (labels[label] + "_mom_sa_pct", values[-2]),
            (labels[label] + "_yoy_nsa_pct", values[-1]),
        ):
            result.append(
                _emit(
                    scope,
                    metric,
                    period,
                    value,
                    "%",
                    [proof],
                    method="Table month columns are seasonally adjusted changes; the separately headed trailing twelve-month column is unadjusted. Percent levels are distinct from percentage-point differences. This U.S. city-average consumer index does not measure any individual firm's costs or forecast future inflation.",
                )
            )
    if not {"All items", "All items less food and energy"}.issubset(rows):
        raise ValueError("business_cpi_rows_missing")
    # Preserve the existing latest-period identities; expose the actual earlier
    # columns and deterministic differences instead of asking scripts to invent quotes.
    for label, (values, proof) in measured.items():
        for (year, column_month), value in zip(parsed[:-1], values[:-2]):
            result.append(
                _emit(
                    scope,
                    label + "_mom_sa_pct",
                    f"{year}-{column_month:02d}",
                    value,
                    "%",
                    [proof],
                    method="Actual seasonally adjusted monthly column in Table A; not a twelve-month change.",
                )
            )
        with localcontext(Context(prec=128)) as context:
            context.traps[Inexact] = True
            difference = values[-2] - values[-3]
        result.append(
            _emit(
                scope,
                label + "_mom_change_pp",
                period,
                difference,
                "percentage_points",
                [proof],
                method="Latest seasonally adjusted monthly percent change minus the preceding monthly percent change in the same Table A row. This is a change in rates, not an index contribution or a forecast.",
            )
        )
    for suffix, index in (("mom_sa", -2), ("yoy_nsa", -1)):
        with localcontext(Context(prec=128)) as context:
            context.traps[Inexact] = True
            difference = measured["core"][0][index] - measured["headline"][0][index]
        result.append(
            _emit(
                scope,
                "core_minus_headline_" + suffix + "_pp",
                period,
                difference,
                "percentage_points",
                [
                    _proof(
                        item,
                        [
                            span["text"]
                            for label in ("core", "headline")
                            for span in measured[label][1]["spans"]
                        ],
                    )
                ],
                method="Core rate minus headline rate from the same Table A period and seasonality column. The difference is in percentage points; it is not a weighted contribution or causal attribution.",
            )
        )
    # The prior twelve-month rate is not a monthly table column. Accept only
    # this complete affirmative publication paragraph and cross-check its peers.
    pattern = (
        r"The all items index rose ([0-9]+\.[0-9]+) percent for the 12 months ending ([A-Za-z]+), after rising ([0-9]+\.[0-9]+) percent over the 12 months ending ([A-Za-z]+)\. "
        r"The all items less food and energy index rose ([0-9]+\.[0-9]+) percent over the last 12 months\. "
        r"The energy index decreased ([0-9]+\.[0-9]+) percent for the 12 months ending ([A-Za-z]+)\. "
        r"The food index increased ([0-9]+\.[0-9]+) percent over the last year\."
    )
    paragraphs = [p[0].strip() for p in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", raw)]
    candidates = [
        (p, re.fullmatch(pattern + r"(?: ```)?", re.sub(r"\s+", " ", p))) for p in paragraphs
    ]
    candidates = [(p, m) for p, m in candidates if m]
    if len(candidates) == 1 and {"energy", "food"}.issubset(measured):
        paragraph, match = candidates[0]
        prefix = re.sub(r"\s+", " ", raw[: raw.index(paragraph)].strip())
        release_prefix = (
            r"CONSUMER PRICE INDEX - [A-Z]+ (?:19|20)\d{2} "
            r"The Consumer Price Index for All Urban Consumers \(CPI-U\) increased [0-9]+\.[0-9]+ percent on a seasonally adjusted basis in [A-Za-z]+, after rising [0-9]+\.[0-9]+ percent in [A-Za-z]+, the U\.S\. Bureau of Labor Statistics reported today\. Over the last 12 months, the all items index increased [0-9]+\.[0-9]+ percent before seasonal adjustment\. "
            r"The index for energy rose [0-9]+\.[0-9]+ percent in [A-Za-z]+, accounting for over forty percent of the monthly all items increase\. The gasoline index increased [0-9]+\.[0-9]+ percent over the month\. The index for food also increased in [A-Za-z]+, rising [0-9]+\.[0-9]+ percent as both the index for food at home and the index for food away from home increased [0-9]+\.[0-9]+ percent each\. "
            r"The index for all items less food and energy rose [0-9]+\.[0-9]+ percent in [A-Za-z]+, after increasing [0-9]+\.[0-9]+ percent in each of the previous [0-9]+ months\. Indexes that increased in [A-Za-z]+ include shelter, airline fares, used cars and trucks, new vehicles, motor vehicle insurance, and medical care\. The indexes for personal care, communication, and alcoholic beverages were among the few major indexes that decreased over the month\."
        )
        gap = raw[raw.index(paragraph) + len(paragraph) : raw.index(header[0])]
        if (
            not re.fullmatch(release_prefix, prefix)
            or gap.strip()
            or raw[raw.index(lines[caption]) + len(lines[caption]) :].strip()
        ):
            return result
        if (
            _MONTHS.get(match[2].lower()) == month
            and _MONTHS.get(match[4].lower()) == month - 1
            and _MONTHS.get(match[7].lower()) == month
            and _number(match[1]) == measured["headline"][0][-1]
            and _number(match[5]) == measured["core"][0][-1]
            and -_number(match[6]) == measured["energy"][0][-1]
            and _number(match[8]) == measured["food"][0][-1]
        ):
            proof = _proof(item, [title[0].strip(), paragraph])
            previous = _number(match[3])
            result.append(
                _emit(
                    scope,
                    "headline_yoy_nsa_pct",
                    f"{title[2]}-{month-1:02d}",
                    previous,
                    "%",
                    [proof],
                    method="Previous twelve-month all-items rate explicitly stated in the complete release paragraph; not the seasonally adjusted monthly column.",
                )
            )
            with localcontext(Context(prec=128)) as context:
                context.traps[Inexact] = True
                difference = measured["headline"][0][-1] - previous
            result.append(
                _emit(
                    scope,
                    "headline_yoy_change_pp",
                    period,
                    difference,
                    "percentage_points",
                    [
                        _proof(
                            item,
                            [
                                span["text"]
                                for source in (proof, measured["headline"][1])
                                for span in source["spans"]
                            ],
                        )
                    ],
                    method="Current unadjusted twelve-month rate minus the explicitly published preceding twelve-month rate; percentage-point change, not a forecast or weighted contribution.",
                )
            )
    return result


def _rate(value):
    value = value.replace("‑", "-").replace("–", "-")
    with localcontext(Context(prec=128)) as context:
        context.traps[Inexact] = True
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
            number = _number(value)
        else:
            match = re.fullmatch(r"([0-9]+)-([0-9]+)/([0-9]+)", value)
            if not match or int(match[3]) not in {2, 4} or not 0 < int(match[2]) < int(match[3]):
                raise ValueError("business_rate_fraction")
            number = _number(match[1]) + Decimal(match[2]) / Decimal(match[3])
    if not 0 <= number <= 100:
        raise ValueError("business_rate_limit")
    return number


def _date(value):
    match = re.fullmatch(r"([A-Z][a-z]+) ([0-9]{1,2}), ([0-9]{4})", value)
    month = _MONTHS.get(match[1].lower()) if match else None
    if not match or month is None:
        raise ValueError("business_date_unsupported")
    return datetime(int(match[3]), month, int(match[2])).date().isoformat()


def _sentences(raw):
    for paragraph in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", raw):
        block = paragraph[0]
        boundaries = [0]
        for boundary in re.finditer(r'(?<=[.!?])(?:["”])?\s+(?=[A-Z“"])', block):
            last = block[: boundary.start()].rsplit(None, 1)[-1]
            if re.fullmatch(r"(?:[A-Za-z]\.)+", last) or last in {
                "Mr.",
                "Mrs.",
                "Ms.",
                "Dr.",
                "Prof.",
                "Sr.",
                "Jr.",
                "Inc.",
                "Corp.",
                "No.",
            }:
                continue
            boundaries.append(boundary.end())
        boundaries.append(len(block))
        for start, end in pairwise(boundaries):
            quote = block[start:end].strip()
            if quote:
                yield quote


def _prose_pattern(template):
    return (
        re.escape(template)
        .replace(re.escape("{objective}"), r"(?P<objective>[0-9]+(?:\.[0-9]+)?)")
        .replace("‑", "[‑-]")
    )


def _statement_layout(sentences, target, date):
    """A complete supported publication grammar, not a negation keyword blacklist."""
    if not sentences or sentences[-1] != "Implementation Note issued " + date:
        return False
    index = sentences.index(target)
    name = r"[A-Z][a-z]+(?: [A-Z]\.)? [A-Z][a-z]+"
    vote = (
        r"Voting for the monetary policy action were "
        + name
        + r"(?:, (?:Vice )?Chair)?(?:; "
        + name
        + r"(?:, (?:Vice )?Chair)?){1,14}; and "
        + name
        + r"\."
    )
    alternate = name + r" voted as an alternate member at this meeting\."
    dissent = (
        r"Voting against this action was "
        + name
        + r", who preferred to lower the target range for the federal funds rate by [0-9]+/[24] percentage point at this meeting\."
    )
    media = r"For media inquiries, please email (?:\[email\s+protected\]|[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+) or call [0-9]{3}-[0-9]{3}-[0-9]{4}\."
    for prefix, guidance in zip(_STATEMENT_PREFIXES, _STATEMENT_GUIDANCE, strict=True):
        if len(prefix) != index:
            continue
        tail = sentences[index + 1 :]
        if len(tail) < len(guidance) + 3:
            continue
        objectives = []
        valid = True
        for actual, template in zip(
            sentences[:index] + tail[: len(guidance)], prefix + guidance, strict=True
        ):
            match = re.fullmatch(_prose_pattern(template), actual)
            if not match:
                valid = False
                break
            if match.groupdict().get("objective") is not None:
                objectives.append(_number(match["objective"]))
        if not valid or len(set(objectives)) != 1:
            continue
        remainder = tail[len(guidance) :]
        if not re.fullmatch(vote, remainder[0]) or not re.fullmatch(media, remainder[-2]):
            continue
        if not all(
            re.fullmatch(alternate, row) or re.fullmatch(dissent, row) for row in remainder[1:-2]
        ):
            continue
        return True
    return False


def _implementation_layout(body, announcement, effective):
    pattern = re.escape(_IMPLEMENTATION_LAYOUT)
    replacements = {
        "announcement": re.escape(announcement),
        "effective": re.escape(effective),
        "quantity": r"(?:[0-9]+[‑-][0-9]+/[24]|[0-9]+/[24]|[0-9]+(?:\.[0-9]+)?)",
    }
    for key, value in replacements.items():
        pattern = pattern.replace(re.escape("{" + key + "}"), value)
    return re.fullmatch(pattern, body) is not None


def _fomc(item, scope):
    raw = item["content"]
    first = next((line for line in raw.splitlines() if line.strip()), "")
    header = re.fullmatch(
        r"([A-Z][a-z]+ [0-9]{1,2}, [0-9]{4}) (Federal Reserve issues FOMC statement|Implementation Note issued ([A-Z][a-z]+ [0-9]{1,2}, [0-9]{4}))(?: For release at [0-9:]+ [ap]\.m\. EDT Share)?",
        first,
    )
    if not header:
        return [], None
    if header[3] and header[3] != header[1]:
        raise ValueError("business_fomc_header_dates")
    period = _date(header[1])
    body = raw[raw.index(first) + len(first) :].strip()
    sentences = list(_sentences(body))
    statement = header[2] == "Federal Reserve issues FOMC statement"
    prefix = r"(?:(?:In support of its goals|In light of the progress on inflation and the balance of risks), the|The) Committee decided to "
    number = r"[0-9.\-‑–/]+"
    target_patterns = [
        prefix
        + r"maintain the target range for the federal funds rate at ("
        + number
        + r") to ("
        + number
        + r") percent\.",
        prefix
        + r"(?:lower|raise) the target range for the federal funds rate by [0-9]+/[24] percentage point to ("
        + number
        + r") to ("
        + number
        + r") percent\.",
    ]
    result = []
    target = None
    if statement:
        matches = [
            (sentence, re.fullmatch(pattern, sentence))
            for sentence in sentences
            for pattern in target_patterns
            if re.fullmatch(pattern, sentence)
        ]
        if len(matches) != 1:
            raise ValueError("business_fomc_affirmative_target")
        sentence, match = matches[0]
        if not _statement_layout(sentences, sentence, header[1]):
            raise ValueError("business_fomc_publication_layout")
        lower, upper = _rate(match[1]), _rate(match[2])
        with localcontext(Context(prec=128)) as context:
            context.traps[Inexact] = True
            if upper - lower != Decimal(".25"):
                raise ValueError("business_fomc_target_range")
        proof = _proof(item, [first, sentence])
        for metric, value in (("target_lower_pct", lower), ("target_upper_pct", upper)):
            result.append(_emit(scope, metric, period, value, "%", [proof]))
        target = (period, lower, upper, proof)
        for original in sentences:
            quantities = list(re.finditer(r"([0-9]+(?:\.[0-9]+)?) percent", original))
            if len(quantities) == 1 and len(re.findall(r"[0-9]+(?:\.[0-9]+)?", original)) == 1:
                value = _number(quantities[0][1])
                result.append(
                    _emit(
                        scope,
                        "stated_policy_assessment",
                        period,
                        value,
                        "percent",
                        [_proof(item, [first, original])],
                        text=period + " " + original,
                        heading="Stated policy assessment",
                        method="Statement-date metadata and the complete original source sentence; the stated objective is not a realized inflation reading or a forecast.",
                    )
                )
        dissent = re.compile(
            r"Voting against this action was ([A-Z][a-z]+(?: [A-Z]\.)? [A-Z][a-z]+), who preferred to lower the target range for the federal funds rate by ([0-9]+/[24]) percentage point at this meeting\."
        )
        for original in sentences:
            match = dissent.fullmatch(original)
            if match:
                value = _rate("0-" + match[2]) * 100
                result.append(
                    _emit(
                        scope,
                        "dissent_preferred_cut_bps",
                        period,
                        value,
                        "basis_points",
                        [_proof(item, [first, original])],
                        heading=match[1] + " dissent preference",
                        method="Stated dissent preference of "
                        + match[1]
                        + ", converted from percentage points to basis points; distinct from the Committee decision and not a forecast.",
                    )
                )
    else:
        intro = (
            "Decisions Regarding Monetary Policy Implementation The Federal Reserve has made the following decisions to implement the monetary policy stance announced by the Federal Open Market Committee in its statement on "
            + header[1]
            + ": "
        )
        board = (
            r"(?:"
            + re.escape(intro)
            + r")?The Board of Governors of the Federal Reserve System voted unanimously to "
        )
        patterns = [
            (
                "reserve_balance_rate_pct",
                board
                + r"(?:lower|raise) the interest rate paid on reserve balances to ([0-9]+(?:\.[0-9]+)?) percent, effective ([A-Z][a-z]+ [0-9]{1,2}, [0-9]{4})\.",
            ),
            (
                "primary_credit_rate_pct",
                r"In a related action, the Board of Governors of the Federal Reserve System voted unanimously to approve a [0-9]+/[24] percentage point (?:decrease|increase) in the primary credit rate to ([0-9]+(?:\.[0-9]+)?) percent, effective ([A-Z][a-z]+ [0-9]{1,2}, [0-9]{4})\.",
            ),
        ]
        effective_dates = []
        for metric, pattern in patterns:
            matches = [
                (sentence, re.fullmatch(pattern, sentence))
                for sentence in sentences
                if re.fullmatch(pattern, sentence)
            ]
            if len(matches) != 1:
                raise ValueError("business_fomc_affirmative_instrument")
            sentence, match = matches[0]
            effective_dates.append(match[2])
            result.append(
                _emit(
                    scope,
                    metric,
                    _date(match[2]),
                    _rate(match[1]),
                    "%",
                    [_proof(item, [first, sentence])],
                    method="Affirmative Board instrument decision indexed by its explicit effective date, separate from the announcement and federal funds target range; external authenticity is not verified.",
                )
            )
        if len(set(effective_dates)) != 1 or not _implementation_layout(
            body, header[1], effective_dates[0]
        ):
            raise ValueError("business_fomc_publication_layout")
    return result, target


def _quotes(item, scope):
    raw = item["content"]
    result = []
    if not ("Federal Reserve issues FOMC statement" in raw or "AI RMF" in raw):
        return result
    for quote in _sentences(raw):
        if (
            len(quote) < 40
            or len(quote) > 1500
            or not re.match(r'[A-Z“"]', quote)
            or not re.search(r'[.!?]["”]?$', quote)
            or re.search(r"\d|https?://|\[|\]", quote)
        ):
            continue
        if not re.search(
            r"\b(?:Committee|economic|inflation|risks?|function|govern|organizations?|framework|uncertain|voluntary)\b",
            quote,
            re.IGNORECASE,
        ):
            continue
        proof = _proof(item, [quote])
        result.append(
            _emit(
                scope,
                "source_quote",
                "",
                None,
                "",
                [proof],
                text=quote,
                heading="Original source statement",
            )
        )
        if len(result) >= 24:
            return result
    return result


def business_observations(inputs, *, scope):
    """Project full owned excerpts in a required session/task namespace; fail closed."""
    if not isinstance(scope, str) or not scope or len(scope) > 4096:
        raise ValueError("business_scope_invalid")
    if not isinstance(inputs, list) or len(inputs) > 20:
        return []
    valid = []
    for item in inputs:
        if (
            not isinstance(item, dict)
            or not re.fullmatch(r"file:[a-f0-9]{24}", str(item.get("id", "")))
            or item.get("source_id") != item["id"]
            or not isinstance(item.get("content"), str)
            or len(item["content"].encode()) > 12000
            or hashlib.sha256(item["content"].encode()).hexdigest() != item.get("sha256")
        ):
            return []
        valid.append(item)
    if len({i["id"] for i in valid}) != len(valid):
        return []
    result = []
    targets = []
    functions = {}
    function_sources = []
    for item in valid:
        try:
            current = _annual(item, scope) + _cpi(item, scope)
            rates, target = _fomc(item, scope)
            current += rates
            if target:
                targets.append(target)
            matches = list(
                re.finditer(
                    r"(?m)^(Govern|Map|Measure|Manage) (\d+\.\d+)\s*:\s*([^\n]+)", item["content"]
                )
            )
            if matches:
                ids = [m[1] + " " + m[2] for m in matches]
                # The entire input must consist of the enumerated records, not a partial table or arbitrary supplied list.
                remainder = item["content"]
                for m in reversed(matches):
                    remainder = remainder[: m.start()] + remainder[m.end() :]
                if len(set(ids)) != len(ids) or remainder.strip():
                    raise ValueError("business_controls_incomplete")
                proof = _proof(item, [m[0] for m in matches])
                current.append(
                    _emit(
                        scope,
                        "selected_control_count",
                        "uploaded_sample",
                        Decimal(len(matches)),
                        "count",
                        [proof],
                        method="Count of distinct complete records in the supplied control excerpt only; not the full framework or verified organizational implementation.",
                    )
                )
                for m in matches:
                    body = m[3].strip()
                    if not re.search(r"\d", body):
                        current.append(
                            _emit(
                                scope,
                                "control_text",
                                "",
                                None,
                                "",
                                [_proof(item, [m[0]])],
                                text=body,
                                heading=m[1] + " " + m[2],
                            )
                        )
            headings = list(
                re.finditer(r"(?m)^5\.[1-4]\s+(Govern|Map|Measure|Manage)\s*$", item["content"])
            )
            if headings and "AI RMF" in item["content"]:
                function_sources.append(_proof(item, [m[0] for m in headings]))
                for m in headings:
                    if m[1] in functions:
                        raise ValueError("business_function_duplicate")
                    functions[m[1]] = True
            if target or "AI RMF" in item["content"]:
                current += _quotes(item, scope)
            result += current
        except (ValueError, ArithmeticError, KeyError, TypeError) as exc:
            log.warning("research_business_projection_unavailable type=%s", type(exc).__name__)
            return []
    with localcontext(Context(prec=128)) as context:
        context.traps[Inexact] = True
        if len(targets) >= 2:
            targets.sort(key=lambda r: r[0])
            before, after = targets[-2:]
            if before[0] == after[0]:
                return []
            cut = (before[1] - after[1]) * 100
            result.append(
                _emit(
                    scope,
                    "target_cut_bps",
                    after[0],
                    cut,
                    "basis_points",
                    [before[3], after[3]],
                    method="Earlier target lower bound minus later target lower bound, converted from percentage points to basis points; not a future policy forecast.",
                )
            )
        if set(functions) == {"Govern", "Map", "Measure", "Manage"}:
            result.append(
                _emit(
                    scope,
                    "function_count",
                    "uploaded_sample",
                    Decimal(len(functions)),
                    "count",
                    function_sources,
                    method="Count of explicit distinct core function headings in the complete supplied excerpts; no certification or organizational implementation is assessed.",
                )
            )
    if len(result) > 200 or len(json.dumps(result, ensure_ascii=False).encode()) > 180000:
        log.warning("research_business_projection_limit")
        return []
    log.info(
        "research_business_observations_projected inputs=%d observations=%d",
        len(valid),
        len(result),
    )
    return sorted(result, key=lambda row: (row["kind"], row["metric"], row["period"], row["id"]))


def business_lineage_issues(payload, observations):
    """Every actual parent of a Host-derived fact must be cited in report and notes."""
    known = {
        row["id"]: row
        for row in observations or []
        if row.get("kind") in {"business_numeric", "business_quote"}
    }
    if not known:
        return []
    declared = {row["id"] for row in payload.get("sources", [])}
    sections = {row["id"]: row for row in payload.get("sections", []) if row.get("id") is not None}
    issues = []
    for claim in payload.get("numeric_claims", []):
        for operand in claim.get("operands", []):
            observed = known.get(operand.get("observation_id"))
            if observed is None:
                continue
            parents = set(observed["source_ids"])
            section = sections.get(claim.get("section_id"), {})
            notes = {
                ref
                for note in payload.get("notes", [])
                if note.get("stage_id") == claim.get("section_id")
                for ref in note.get("citations", [])
            }
            if not parents.issubset(declared & set(section.get("citations", [])) & notes):
                issues.append("business_parent_lineage_missing:" + claim["id"])
    if issues:
        log.warning("research_business_parent_lineage_rejected count=%d", len(issues))
    return list(dict.fromkeys(issues))
