"""Host-rebuilt weekly facts for the existing report-plan and quality protocol."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation

from core.observability import get_logger

from ..datahub.security import directory, read_file, write_new
from ..research_business_evidence import _emit, _proof
from .models import WorkflowError

log = get_logger(__name__)
FACTS_PATH = "inputs/report-workflow/weekly-facts.txt"


def weekly_fact_rows(bundle: dict) -> list[dict]:
    """Only independently reassessed observations become calculation operands."""
    if bundle.get("assessment", {}).get("status") != "passed":
        raise WorkflowError("周报数据尚未通过", "weekly_evidence_invalid", 409)
    facts = []
    for row in bundle["assessment"].get("observations", []):
        if row.get("group") == "industry":
            continue  # Chart data is independently projected in full, not repeated as prose operands.
        identity = row["id"]
        period = row["as_of"]
        unit = row.get("unit")
        if row.get("kind") == "price_return":
            values = [
                ("weekly_close", period, row["close"], unit),
                ("weekly_close", row["baseline_date"], row["baseline_close"], unit),
                ("weekly_return_pct", period, row["return_pct"], "%"),
            ]
        elif row.get("kind") == "turnover":
            values = [
                ("weekly_daily_mean_amount", period, row["value"], unit),
                ("weekly_previous_daily_mean_amount", period, row["previous_value"], unit),
                ("weekly_trading_days", period, row["trading_days"], "days"),
                ("weekly_previous_trading_days", period, row["previous_trading_days"], "days"),
            ]
            for point in [*row.get("current_rows", []), *row.get("previous_rows", [])]:
                values.append(("weekly_raw_daily_amount", point["date"], point["value"], unit))
        elif row.get("kind") == "history":
            values = [("weekly_history_count", period, row["count"], "rows")]
        else:
            continue
        for metric, date, value, units in values:
            number = Decimal(str(value))
            if not number.is_finite() or not isinstance(units, str) or not units:
                raise WorkflowError("周报数值或单位不完整", "weekly_evidence_invalid", 409)
            facts.append(
                {
                    "series_id": identity,
                    "heading": row.get("display_name") or identity,
                    "metric": metric,
                    "period": date,
                    "value": format(number, "f"),
                    "unit": units,
                }
            )
    contract = bundle.get("data_contract")
    if contract:
        if any(row.get("group") == "industry" for row in bundle["assessment"]["observations"]):
            facts.append(
                {
                    "series_id": "industry_chart",
                    "heading": "申万一级行业周涨跌幅",
                    "metric": "weekly_industry_chart_status",
                    "period": contract["cutoff"][:10],
                    "value": None,
                    "unit": "status",
                    "statement": "申万行业图使用本期已核验的全部行业序列。",
                }
            )
        for identity, title, value in (
            ("report_start", "开始日期", contract["period_start"]),
            ("report_end", "结束日期", contract["cutoff"][:10]),
        ):
            facts.append(
                {
                    "series_id": identity,
                    "heading": title,
                    "metric": "weekly_report_period",
                    "period": value,
                    "value": None,
                    "unit": "date",
                    "statement": f"{title}：{value}",
                }
            )
        calendar = bundle["snapshot"].get("economic_calendar", {})
        if calendar.get("coverage_verified") is True:
            facts.append(
                {
                    "series_id": "economic_calendar",
                    "heading": "下周全球投资日历",
                    "metric": "weekly_economic_calendar",
                    "period": contract["next_calendar_start"],
                    "value": None,
                    "unit": "events",
                    "statement": json.dumps(
                        calendar.get("events", []), ensure_ascii=False, sort_keys=True
                    ),
                }
            )
    return facts


def _verified(service, sid):
    from .weekly_quality import weekly_verified_evidence

    return weekly_verified_evidence(service, sid)


def _empty_news_records(service, sid):
    from .weekly_quality import trusted_weekly_context

    frozen = trusted_weekly_context(service, sid)
    if frozen is None:
        return []
    start = frozen["data_contract"]["period_start"]
    end = frozen["as_of"]
    titles = {
        item["id"]: item["text"]
        for item in frozen["requirements"]
        if item["id"] in frozen["news_block_ids"]
    }
    result, seen = [], set()
    for item in service.datahub.list(sid):
        parameters = item.get("query", {}).get("parameters", {})
        if (
            item.get("capability") != "search_news"
            or parameters.get("start_date") != start
            or parameters.get("end_date") != end
        ):
            continue
        matches = [
            identifier
            for identifier, title in titles.items()
            if parameters.get("query") == title and identifier not in seen
        ]
        seen.update(matches)
        if (
            item.get("capability") != "search_news"
            or item.get("status") != "complete"
            or item.get("row_count") != 0
            or item.get("pagination_complete") is not True
            or item.get("missing")
            or item.get("provider_metadata", {}).get("requested_range_verified") is not True
        ):
            continue
        if not matches:
            continue
        raw = service.datahub.snapshots.read(sid, item["dataset_id"], "rows.json")
        if json.loads(raw) != []:
            raise WorkflowError("新闻快照计数不一致", "weekly_news_evidence_invalid", 409)
        for identifier in matches:
            result.append(
                {
                    "block_id": identifier,
                    "title": titles[identifier],
                    "dataset_id": item["dataset_id"],
                    "query": parameters,
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "statement": "本期未取得足够可核验材料。",
                }
            )
    return result


def refresh_weekly_news_evidence(service, sid: str) -> None:
    """Only completed, exact-period, zero-result queries authorize a gap statement."""
    for record in _empty_news_records(service, sid):
        name = _news_file_name(record)
        raw = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode()
        with directory(service.store.directory(sid), ("inputs", "report-workflow")) as folder:
            if (service.store.directory(sid) / "inputs/report-workflow" / name).exists():
                if read_file(folder, name, limit=16_000) != raw:
                    raise WorkflowError("新闻缺口证据已变化", "weekly_news_evidence_changed", 409)
            else:
                write_new(folder, name, raw)
    service.store.files(sid)
    service.store.save()


def _news_business_observations(service, sid, scope):
    result = []
    for record in _empty_news_records(service, sid):
        name = _news_file_name(record)
        reference = "inputs/report-workflow/" + name
        fid = hashlib.sha256(reference.encode()).hexdigest()[:24]
        expected = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        stream, _ = service.store.open_file(sid, fid)
        with stream:
            actual = stream.read(16_001)
        if actual != expected.encode():
            raise WorkflowError("新闻缺口证据已变化", "weekly_news_evidence_changed", 409)
        source = {
            "id": "file:" + fid,
            "sha256": hashlib.sha256(actual).hexdigest(),
            "content": expected,
        }
        result.append(
            _emit(
                scope,
                "weekly_news_material_status",
                record["query"]["end_date"],
                None,
                "status",
                [_proof(source, [record["statement"]])],
                method="huaan-weekly-news-status-v1",
                text=record["statement"],
                heading=record["title"],
            )
        )
    return result


def _news_file_name(record):
    key = record["block_id"] + ":" + record["dataset_id"]
    return "weekly-news-" + hashlib.sha256(key.encode()).hexdigest()[:24] + ".txt"


def _content(bundle: dict) -> tuple[list[dict], str]:
    facts = weekly_fact_rows(bundle)
    content = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in facts) + "\n"
    if not facts or len(content.encode()) > 192_000:
        raise WorkflowError("周报事实索引不完整或超过上限", "weekly_evidence_limit", 409)
    return facts, content


def prepare_weekly_evidence(service, sid: str) -> None:
    bundle = _verified(service, sid)
    if bundle is None:
        return
    try:
        _, content = _content(bundle)
        with directory(service.store.directory(sid), ("inputs", "report-workflow")) as folder:
            path = service.store.directory(sid) / FACTS_PATH
            if path.exists():
                if read_file(folder, "weekly-facts.txt", limit=192_000) != content.encode():
                    raise ValueError("weekly_facts_changed")
            else:
                write_new(folder, "weekly-facts.txt", content.encode())
        service.store.files(sid)
        service.store.save()
        log.info("report_weekly_facts_prepared", session_id=sid)
    except (OSError, ValueError, KeyError, InvalidOperation) as exc:
        log.warning("report_weekly_facts_failed", error_type=type(exc).__name__)
        raise WorkflowError("周报事实索引无法准备", "weekly_evidence_invalid", 409) from None


def weekly_business_observations(
    service, sid: str, *, task_id: str, contract_sha: str
) -> list[dict]:
    bundle = _verified(service, sid)
    if bundle is None:
        return []
    try:
        facts, content = _content(bundle)
        fid = hashlib.sha256(FACTS_PATH.encode()).hexdigest()[:24]
        stream, _ = service.store.open_file(sid, fid)
        with stream:
            actual = stream.read(192_001)
        if actual != content.encode():
            raise ValueError("weekly_fact_bytes_changed")
        source = {
            "id": "file:" + fid,
            "content": content,
            "sha256": hashlib.sha256(actual).hexdigest(),
        }
        scope = str(service.store.root) + ":" + sid + ":" + task_id + ":" + contract_sha
        result = []
        for row, line in zip(facts, content.splitlines(), strict=True):
            proof = _proof(source, [line])
            result.append(
                _emit(
                    scope,
                    row["metric"],
                    row["period"],
                    Decimal(row["value"]) if row["value"] is not None else None,
                    row["unit"],
                    [proof],
                    method="huaan-weekly-data-v1",
                    text=row.get("statement")
                    or f"{row['series_id']} {row['metric']} {row['period']} {row['value']} {row['unit']}",
                    heading=row["heading"],
                )
            )
        result.extend(_news_business_observations(service, sid, scope))
        return result
    except (OSError, ValueError, KeyError, InvalidOperation) as exc:
        log.warning("report_weekly_facts_rejected", error_type=type(exc).__name__)
        raise WorkflowError(
            "周报事实索引与已核验数据不一致", "weekly_evidence_invalid", 409
        ) from None
