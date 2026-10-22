"""Closed A-share tables, checked against CJPY metadata before every read.

No caller-supplied table, formula, field expression, or global credential is used.
The original vendor rows and metadata remain attached to the frozen snapshot.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_ROWS, ProviderError, Result, numeric

log = get_logger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
SOURCE_URL = "https://www.chinajoin.com/"
FACTORS = {
    "pe_ttm": (
        "PETTM",
        "(StockType(StockID)=-1)?Index_PE(0,0):StockPE_VI(EndT, 0)",
        "市盈率，支持A股和指数",
    ),
    "pb": ("PBLF", "StockPNA_VI(EndT)", "市净率，支持A股，不支持指数"),
    "pb_mrq": (
        "PBMRQ",
        "(StockType(StockID)=-1)?Index_PB(0,0):StockPNA_II(EndT)",
        "市净率，支持A股和指数",
    ),
    "ps_ttm": (
        "PSTTM",
        "(StockType(StockID)=-1)?Index_PSR(0,0):StockPMI_VI(EndT)",
        "市销率，支持A股和指数",
    ),
    "total_shares": ("总股本", "StockTotalShares3()", ""),
    "market_cap": (
        "总市值",
        "(StockType(StockID)=-1)?StocksTotalValue(GetBKByDate(StockId, EndT),EndT,1):StockTotalValue3()",
        "单位：万元；指数算法：成分股市值加总",
    ),
    "turnover_rate_pct": (
        "换手率",
        "(StockType(StockID)=-1)?StocksHSL3(GetBKByDate(StockId, EndT),0,1):StockHsl3()",
        "单位：%；股票算法：成交量/流通股本；指数算法：∑(股票i成交量) /∑(股票i流通股本和)",
    ),
}
TABLES = {
    "股票基本信息": {
        "date_field": None,
        "fields": {
            "公司中文简称": None,
            "股本单位": None,
            "申万一级行业": None,
            "申万二级行业": None,
        },
    },
    "股本结构": {
        "date_field": "变动日",
        "fields": {"变动日": None, "公布日": None, "总股本": "股/份"},
    },
    "主要财务指标": {
        "date_field": "截止日",
        "fields": {
            "截止日": None,
            "公布日": None,
            "净资产收益率(%)": None,
            "销售毛利率(%)": None,
            "报告类型": None,
        },
    },
    "合并利润表": {
        "date_field": "截止日",
        "fields": {
            "截止日": None,
            "公布日": None,
            "营业收入": "元",
            "营业总收入": "元",
            "净利润": "元",
            "归属于母公司所有者净利润": "元",
            "报告类型": None,
        },
    },
    "金融公司利润表": {
        "date_field": "截止日",
        "fields": {
            "截止日": None,
            "公布日": None,
            "营业收入": "元",
            "净利润": "元",
            "归属于母公司所有者净利润": "元",
        },
    },
    "十大股东": {
        "date_field": None,
        "fields": {
            "截止日": None,
            "数据报告期": None,
            "股东序号": None,
            "名称": None,
            "股数": "股/份",
            "占总股本比例(%)": "%",
            "性质": None,
            "股东性质": None,
        },
    },
    "融资融券明细": {
        "date_field": "截止日",
        "fields": {
            "截止日": None,
            "融资余额": "元",
            "融资买入额": "元",
            "融资偿还额": "元",
            "融券余量": "股",
            "融券卖出量": "股",
            "融券偿还量": "股",
        },
    },
    "股票公告": {
        "date_field": "公布日",
        "fields": {
            "公布日": None,
            "公告类型(一级)": None,
            "公告类型(二级)": None,
            "公告标题": None,
        },
    },
}


def _json(value):
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise ProviderError("tinysoft_asset_value_invalid")


def _day(value):
    if value in (None, "", 0) or isinstance(value, bool):
        return None
    text = str(value)
    if re.fullmatch(r"\d{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) is None:
        raise ProviderError("tinysoft_asset_date_invalid")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ProviderError("tinysoft_asset_date_invalid") from exc


def _number(value):
    return None if isinstance(value, bool) else numeric(value)


class Context:
    def __init__(self, sdk, client, token, asset):
        self.sdk, self.client, self.token, self.asset = sdk, client, token, asset
        match = re.fullmatch(r"(\d{6})\.(SH|SZ|BJ)", asset)
        if match is None:
            raise ProviderError("invalid_asset_code")
        self.code = f"{match[2]}{match[1]}"
        stocks = self.sdk.get_stocks(client=self.client)
        if (
            not isinstance(stocks, list)
            or not 1 <= len(stocks) <= 20000
            or any(
                not isinstance(code, str) or re.fullmatch(r"(?:SH|SZ|BJ)\d{6}", code) is None
                for code in stocks
            )
        ):
            raise ProviderError("tinysoft_directory_invalid")
        if self.code not in stocks:
            raise ProviderError("tinysoft_asset_type_unsupported")
        self.today = datetime.now(SHANGHAI).date().isoformat()
        self.result = Result(source_url=SOURCE_URL, provider_id="tinysoft")
        self.table_metadata = None

    def records(self, value):
        if hasattr(value, "to_dict"):
            value = value.to_dict(orient="records")
        if (
            not isinstance(value, list)
            or len(value) > MAX_ROWS
            or any(not isinstance(row, dict) for row in value)
        ):
            raise ProviderError("tinysoft_asset_schema_invalid")
        rows = _json(value)
        encoded = json.dumps(rows, ensure_ascii=False, allow_nan=False).encode()
        if self.token and self.token in encoded.decode():
            raise ProviderError("credential_reflection")
        self.result.raw.append(encoded)
        return rows

    def identities(self, rows, field="CODE"):
        if any(row.get(field) != self.code for row in rows):
            raise ProviderError("tinysoft_asset_identity_invalid")
        return rows

    def table(self, name, *, start=None, end=None):
        spec = TABLES[name]
        if self.table_metadata is None:
            self.table_metadata = self.records(self.sdk.list_tables(client=self.client))
        found = [row for row in self.table_metadata if row.get("表名") == name]
        if len(found) != 1 or found[0].get("日期字段") != spec["date_field"]:
            raise ProviderError("tinysoft_asset_table_unverified")
        metadata = self.records(self.sdk.list_table_fields(name, client=self.client))
        by_name = {row.get("字段名称"): row for row in metadata}
        if len(by_name) != len(metadata) or any(
            field not in by_name or by_name[field].get("单位") != unit
            for field, unit in spec["fields"].items()
        ):
            raise ProviderError("tinysoft_asset_unit_unverified")
        parameters = {"fields": list(spec["fields"]), "client": self.client}
        if start is not None:
            parameters.update(start=start, end=end)
        rows = self.identities(self.records(self.sdk.get_table_data(self.code, name, **parameters)))
        self.result.metadata.setdefault("asset_table_contract", {})[name] = {
            "date_field": spec["date_field"],
            "fields": metadata,
        }
        return rows

    def field(self, name, unit=None, currency=None, **extra):
        self.result.fields[name] = {"unit": unit, "currency": currency, **extra}


def _financials(context, parameters):
    if parameters.get("statements", ["indicators"]) not in (["indicators"], ["metrics"]):
        raise ProviderError("data_not_equivalent")
    requested = parameters.get("periods", [])
    if (
        not isinstance(requested, list)
        or len(requested) > 8
        or any(_day(item) is None for item in requested)
    ):
        raise ProviderError("data_not_equivalent")
    indicators = context.table("主要财务指标")
    profit = context.table("合并利润表")
    profit_table = "合并利润表"
    if not profit:
        profit = context.table("金融公司利润表")
        profit_table = "金融公司利润表"
    grouped = {}
    for table, rows, fields in [
        (
            "主要财务指标",
            indicators,
            {"roe": "净资产收益率(%)", "gross_profit_margin": "销售毛利率(%)"},
        ),
        (
            profit_table,
            profit,
            {
                "revenue": "营业收入",
                "net_profit": "净利润",
                "net_profit_parent": "归属于母公司所有者净利润",
            },
        ),
    ]:
        for source in rows:
            period, publication = _day(source.get("截止日")), _day(source.get("公布日"))
            if (
                not period
                or not publication
                or max(period, publication) > context.today
                or requested
                and period not in requested
            ):
                continue
            key = (period, publication)
            row = grouped.setdefault(
                key,
                {
                    "asset": context.asset,
                    "date": period,
                    "report_period": period,
                    "published_at": publication,
                    "report_type": source.get("报告类型"),
                    "source_tables": [],
                },
            )
            if (
                row.get("report_type")
                and source.get("报告类型")
                and row["report_type"] != source["报告类型"]
            ):
                raise ProviderError("tinysoft_financial_version_conflict")
            row["report_type"] = row.get("report_type") or source.get("报告类型")
            for output, original in fields.items():
                value = _number(source.get(original))
                if output in row and row[output] != value:
                    raise ProviderError("tinysoft_financial_version_conflict")
                row[output] = value
            row["source_tables"].append(table)
    periods = sorted({key[0] for key in grouped})[-8:]
    context.result.rows = [row for key, row in sorted(grouped.items()) if key[0] in periods]
    for name in ["roe", "gross_profit_margin"]:
        context.field(name, "percent")
    for name in ["revenue", "net_profit", "net_profit_parent"]:
        context.field(name, "元", source_unit="元")
    context.result.limitations.extend(
        [
            "财务摘要最多展示最近8个实际报告期，不代表完整三表。",
            "金额单位为来源声明的元；来源未单独标明币种，不另行推断。",
            "仅同报告期、同公布日的来源记录合并；历史表为本次读取版本，不保证当时可得。",
        ]
    )


def _holder_details(context):
    records = context.table("十大股东")
    periods = {}
    for source in records:
        period = _day(source.get("截止日"))
        if not period or period > context.today:
            continue
        rank = _number(source.get("股东序号"))
        if rank is None or rank != int(rank) or not 1 <= rank <= 10:
            raise ProviderError("tinysoft_holder_rank_invalid")
        bucket = periods.setdefault(period, {})
        if rank in bucket and bucket[rank] != source:
            raise ProviderError("tinysoft_holder_identity_conflict")
        bucket[rank] = source
    if not periods:
        return []
    dates = sorted(periods)
    latest = periods[dates[-1]]
    previous = (
        {row.get("名称"): row for row in periods[dates[-2]].values()} if len(dates) > 1 else {}
    )
    result = []
    for rank, source in sorted(latest.items()):
        name = source.get("名称")
        if not isinstance(name, str) or not name.strip() or len(name) > 256:
            raise ProviderError("tinysoft_holder_identity_invalid")
        ratio = _number(source.get("占总股本比例(%)"))
        if ratio is not None and not 0 <= ratio <= 100:
            raise ProviderError("tinysoft_holder_ratio_invalid")
        prior_ratio = _number(previous.get(name, {}).get("占总股本比例(%)"))
        category = source.get("股东性质")
        state_owned = (
            True
            if category in {"国有法人", "国有法人股", "国家股", "国有企业"}
            else (
                False
                if category in {"自然人", "境内自然人", "境外自然人", "境内非国有法人"}
                else None
            )
        )
        result.append(
            {
                "asset": context.asset,
                "report_period": dates[-1],
                "rank": int(rank),
                "shareholder_name": name,
                "share_ratio": ratio,
                "holding_quantity": _number(source.get("股数")),
                "change_ratio": (
                    ratio - prior_ratio if ratio is not None and prior_ratio is not None else None
                ),
                "previous_report_period": dates[-2] if len(dates) > 1 else None,
                "is_state_owned": state_owned,
                "holder_category": category,
            }
        )
    context.field("share_ratio", "percent")
    context.field(
        "change_ratio",
        "百分点",
        derivation="相邻两个已取得报告期，同名股东持股比例之差；不将未进入前十视为零。",
    )
    context.field("holding_quantity", "share")
    context.result.limitations.append(
        "股东表未提供公告日；展示本次读取的最近报告期，国资标志仅使用明确的来源股东性质。"
    )
    return result


def _snapshot(context, parameters):
    requested = parameters.get("fields", [])
    allowed = {
        "close",
        "price",
        "pe_ttm",
        "pb",
        "pb_mrq",
        "ps_ttm",
        "total_shares",
        "turnover_rate_pct",
        "market_cap",
    }
    if not isinstance(requested, list) or any(field not in allowed for field in requested):
        raise ProviderError("data_not_equivalent")
    end = date.fromisoformat(context.today)
    quotes = context.identities(
        context.records(
            context.sdk.get_market_data(
                code=context.code,
                start=(end - timedelta(days=14)).isoformat(),
                end=end.isoformat(),
                cycle="day",
                rate="不复权",
                client=context.client,
            )
        ),
        "代码",
    )
    if not quotes:
        return
    dated = [
        (day, row)
        for row in quotes
        if (day := _day(row.get("时间", row.get("date")))) and day <= context.today
    ]
    if not dated:
        return
    day, quote = max(dated, key=lambda value: value[0])
    metadata = context.records(context.sdk.list_factors(client=context.client))
    found = {row.get("因子名称"): row for row in metadata}
    if any(
        found.get(name, {}).get("公式") != formula or found.get(name, {}).get("说明") != description
        for name, formula, description in FACTORS.values()
    ):
        raise ProviderError("tinysoft_valuation_contract_unverified")
    factors = context.identities(
        context.records(
            context.sdk.get_factor_data(
                code=context.code,
                date=day,
                factors=[spec[0] for spec in FACTORS.values()],
                client=context.client,
            )
        ),
        "代码",
    )
    if len(factors) != 1 or _day(factors[0].get("截止日")) != day:
        raise ProviderError("tinysoft_valuation_date_invalid")
    factor = factors[0]
    basic = context.table("股票基本信息")
    changes = context.table("股本结构")
    valid_changes = [
        row
        for row in changes
        if (d := _day(row.get("变动日")))
        and d <= day
        and (p := _day(row.get("公布日")))
        and p <= day
    ]
    latest_change = max(valid_changes, key=lambda row: _day(row["变动日"]), default={})
    shares = _number(factor.get("总股本"))
    shares_verified = bool(
        basic
        and basic[0].get("股本单位") == "股"
        and shares is not None
        and shares >= 0
        and shares == _number(latest_change.get("总股本"))
    )
    market_fields = context.records(context.sdk.list_market_fields(client=context.client))
    market_units = {row.get("字段名"): row.get("单位/计算规则", "") or "" for row in market_fields}
    price_verified = "股票：股" in market_units.get("vol", "") and "股票：元" in market_units.get(
        "amount", ""
    )
    row = {
        "asset": context.asset,
        "date": day,
        "name": factor.get("名称"),
        "close": _number(quote.get("close")),
    }
    row.update({key: _number(factor.get(spec[0])) for key, spec in FACTORS.items()})
    context.result.rows = [row]
    context.field("close", "元/股" if price_verified else None)
    for key, spec in FACTORS.items():
        unit = (
            "share"
            if key == "total_shares" and shares_verified
            else (
                None
                if key == "total_shares"
                else (
                    "万元"
                    if key == "market_cap"
                    else "percent" if key == "turnover_rate_pct" else "ratio"
                )
            )
        )
        context.field(
            key,
            unit,
            basis=spec[0],
            unit_verified=shares_verified if key == "total_shares" else True,
        )
    context.result.metadata["valuation_definitions"] = {
        key: {"name": spec[0], "formula": spec[1], "description": spec[2]}
        for key, spec in FACTORS.items()
    }
    context.result.limitations.append(
        "PB为天软PBLF，PB-MRQ为PBMRQ；股本单位须经基本信息和同截止日股本结构一致性校验，才用于派生市值。"
    )
    if not shares_verified:
        context.result.limitations.append("股本单位或数量一致性尚未核实，不据此推导市值。")


def structured_query(query: BusinessQuery, sdk, client, token: str) -> Result:
    parameters = query.parameters
    if parameters.get("asset_type", "stock") != "stock":
        raise ProviderError("tinysoft_asset_type_unsupported")
    assets = parameters.get("assets")
    asset = parameters.get("asset") or (
        assets[0] if isinstance(assets, list) and len(assets) == 1 else None
    )
    if not isinstance(asset, str):
        raise ProviderError("single_asset_required")
    context = Context(sdk, client, token, asset)
    if query.capability == "financials":
        _financials(context, parameters)
    elif query.capability == "market_snapshot":
        _snapshot(context, parameters)
    elif query.capability == "market_activity":
        dataset = parameters.get("dataset")
        if dataset in {"holder_details", "holder_data"}:
            details = _holder_details(context)
            if dataset == "holder_details":
                context.result.rows = details
            elif details:
                complete = len(details) == 10 and all(
                    row["share_ratio"] is not None and row["holding_quantity"] is not None
                    for row in details
                )
                context.result.rows = [
                    {
                        "asset": asset,
                        "report_period": details[0]["report_period"],
                        "top10_pct": (
                            sum(row["share_ratio"] for row in details) if complete else None
                        ),
                        "top10_quantity": (
                            sum(row["holding_quantity"] for row in details) if complete else None
                        ),
                    }
                ]
                context.field("top10_pct", "percent", derivation="同一报告期完整前十名比例合计")
                context.field(
                    "top10_quantity", "share", derivation="同一报告期完整前十名持股数量合计"
                )
        elif dataset == "industry":
            basic = context.table("股票基本信息")
            if len(basic) > 1:
                raise ProviderError("tinysoft_asset_identity_conflict")
            context.result.rows = [
                {
                    "asset": asset,
                    "date": context.today,
                    "sw_level_1": row.get("申万一级行业"),
                    "sw_level_2": row.get("申万二级行业"),
                }
                for row in basic
            ]
            context.result.limitations.append(
                "行业为本次静态基本信息，分类版本及行业PE/PB未提供，不代表历史时点分类。"
            )
        elif dataset in {"margin_trading", "events"}:
            start, end = _day(parameters.get("start_date")), _day(parameters.get("end_date"))
            if (
                not start
                or not end
                or start > end
                or end > context.today
                or (date.fromisoformat(end) - date.fromisoformat(start)).days >= 60
            ):
                raise ProviderError("workload_too_large")
            name = "融资融券明细" if dataset == "margin_trading" else "股票公告"
            rows = context.table(name, start=start, end=end)
            mapping = {
                "financing_balance": "融资余额",
                "financing_buy": "融资买入额",
                "financing_repay": "融资偿还额",
                "securities_lending_volume": "融券余量",
                "securities_lending_sell": "融券卖出量",
                "securities_lending_repay": "融券偿还量",
            }
            for source in rows:
                day = _day(source.get("截止日" if dataset == "margin_trading" else "公布日"))
                if not day or not start <= day <= end:
                    continue
                if dataset == "margin_trading":
                    context.result.rows.append(
                        {
                            "asset": asset,
                            "date": day,
                            **{key: _number(source.get(value)) for key, value in mapping.items()},
                        }
                    )
                else:
                    context.result.rows.append(
                        {
                            "asset": asset,
                            "date": day,
                            "publish_date": day,
                            "summary": source.get("公告标题"),
                            "event_type": source.get("公告类型(二级)")
                            or source.get("公告类型(一级)"),
                        }
                    )
            if dataset == "margin_trading":
                for key in mapping:
                    context.field(key, "share" if key.startswith("securities_") else "元")
            else:
                context.result.limitations.append(
                    "事件仅为来源公告标题、分类及公布日；没有生成影响方向、评分或正文。"
                )
        else:
            raise ProviderError("tinysoft_capability_unsupported")
    else:
        raise ProviderError("tinysoft_capability_unsupported")
    required = {
        "financials": ("revenue", "net_profit", "roe", "gross_profit_margin"),
        "market_snapshot": (
            "close",
            "pe_ttm",
            "pb",
            "pb_mrq",
            "ps_ttm",
            "total_shares",
            "market_cap",
        ),
    }.get(query.capability, ())
    if context.result.rows:
        dates = [
            _day(row.get("published_at") or row.get("date") or row.get("report_period"))
            for row in context.result.rows
        ]
        context.result.as_of = max((value for value in dates if value), default=None)
        context.result.missing = sorted(
            {field for row in context.result.rows for field in required if row.get(field) is None}
        )
        if context.result.missing:
            context.result.metadata["quality_partial"] = True
            context.result.limitations.append("部分记录缺少字段；不跨公布日或报告版本补齐。")
    log.info(
        "tinysoft_asset_data_normalized", capability=query.capability, rows=len(context.result.rows)
    )
    return context.result
