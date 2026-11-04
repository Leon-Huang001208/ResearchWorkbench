"""Explicit account-owned DataHub imports are research inputs, never historical PIT grants."""

import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from core.observability import get_logger

from .datahub.snapshots import Snapshots
from .dossiers.lock import retention_lock
from .event_studies.registry import INDICES
from .store import StoreError

log = get_logger(__name__)
router = APIRouter(prefix="/api/research/event-studies/sources")
ALIASES = {
    "SSE": {"000001", "000001.SS", "000001.SH", "sh000001", "1.000001"},
    "CSI300": {"000300", "000300.SH", "000300.SS", "sh000300", "1.000300"},
    "CHINEXT": {"399006", "399006.SZ", "sz399006", "0.399006"},
    "SP500": {"^GSPC", "SPX", ".INX"},
    "NASDAQ": {"^IXIC", "NASDAQCOM"},
    "DJI": {"^DJI", "DJI"},
    "HSI": {"^HSI", "HSI"},
    "HSCEI": {"^HSCE", "HSCEI"},
    "HSTECH": {"^HSTECH", "HSTECH"},
}


def reject(code):
    log.warning("event_datahub_import_rejected", code=code)
    raise StoreError("资料无法登记为该指数的研究输入，请核对身份、日线口径与来源", code, 422)


class ImportReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    dataset_id: str
    index_id: str


class FrozenRecordReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: int = Field(ge=1, strict=True)


class NativeInputReference(ImportReference):
    kind: str = Field(pattern=r"^(calendar|proxy|prices|factor_inputs)$")
    links: dict[str, FrozenRecordReference] = Field(default_factory=dict, max_length=6)


class LinkInputReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle_ref: FrozenRecordReference
    links: dict[str, FrozenRecordReference] = Field(min_length=1, max_length=6)


async def host_operation(request, operation):
    def tracked():
        with request.app.state.research.event_inputs.activity():
            return operation()

    return await run_in_threadpool(tracked)


def snapshot_identity(manifest):
    query = manifest.get("query", {})
    provider = manifest.get("provider_query", {})
    parameters = query.get("parameters", {})
    identity = (
        query.get("asset")
        or query.get("code")
        or parameters.get("index")
        or parameters.get("asset")
        or parameters.get("code")
        or provider.get("code")
    )
    kind = query.get("asset_type") or parameters.get("asset_type") or provider.get("asset_type")
    frequency = query.get("frequency") or parameters.get("frequency") or provider.get("frequency")
    if kind != "index" and manifest.get("capability") != "index_data":
        return None
    if frequency not in {"day", "daily", "1d"}:
        return None
    return next((key for key, aliases in ALIASES.items() if identity in aliases), None)


def available_sources(research):
    """Bounded catalogue of retained account data, not a source/PIT acceptance claim."""
    snapshots = Snapshots(research.store)
    from .market_scoring.native_inputs import SCHEMAS

    native_schemas = {schema: kind for kind, schema in SCHEMAS.items()}
    result, failed, visited = [], 0, 0
    sessions = list(research.store.data.get("sessions", {}).items())[-20:]
    for sid, session in reversed(sessions):
        if not isinstance(session, dict) or session.get("deleted_at"):
            continue
        try:
            identities = snapshots.ids(sid)[-20:]
            for did in reversed(identities):
                visited += 1
                manifest = snapshots.detail(sid, did)
                index = snapshot_identity(manifest)
                native_kind = native_schemas.get(
                    manifest.get("provider_metadata", {}).get("event_input_schema")
                )
                if native_kind:
                    declared = manifest.get("provider_metadata", {}).get(
                        "index_id"
                    ) or manifest.get("query", {}).get("parameters", {}).get("index")
                    result.append(
                        {
                            "session_id": sid,
                            "dataset_id": did,
                            "kind": "native",
                            "native_kind": native_kind,
                            "index_id": declared if declared in INDICES else None,
                            "title": f"{session.get('title', '研究资料')} · {manifest.get('name', '原生输入')}",
                            "source": manifest.get("source"),
                            "as_of": manifest.get("as_of"),
                        }
                    )
                elif index:
                    result.append(
                        {
                            "session_id": sid,
                            "dataset_id": did,
                            "index_id": index,
                            "kind": "prices",
                            "title": f"{session.get('title', '研究资料')} · {manifest.get('name', INDICES[index]['name'])}",
                            "source": manifest.get("source"),
                            "as_of": manifest.get("as_of"),
                        }
                    )
                elif manifest.get("query", {}).get("capability") == "trading_calendar":
                    result.append(
                        {
                            "session_id": sid,
                            "dataset_id": did,
                            "kind": "calendar",
                            "title": f"{session.get('title', '研究资料')} · 交易日历",
                            "source": manifest.get("source"),
                            "as_of": manifest.get("as_of"),
                        }
                    )
                if visited >= 20:
                    break
        except (StoreError, OSError, ValueError, TypeError):
            failed += 1
            log.warning("event_source_catalog_entry_unavailable")
        if visited >= 20:
            break
    return {
        "items": result,
        "unavailable_scopes": failed,
        "coverage": "recent_account_snapshots_only",
    }


def normalize_rows(raw):
    """Preserve native values; reject ambiguous/missing/duplicate dates rather than filling."""
    try:
        native = json.loads(raw)
        if not isinstance(native, list) or not 2 <= len(native) <= 20000:
            reject("event_price_rows_invalid")
        rows = []
        for row in native:
            if not isinstance(row, dict):
                reject("event_price_rows_invalid")
            days = [
                str(row[key]) for key in ("date", "Date", "day", "日期") if row.get(key) is not None
            ]
            if not days or len(set(days)) != 1:
                reject("event_price_date_ambiguous")
            day = date.fromisoformat(days[0]).isoformat()
            entry = {"day": day}
            for field, aliases in {
                "close": ("close", "Close", "收盘", "收盘价"),
                "open": ("open", "Open", "开盘", "开盘价"),
            }.items():
                values = [row[key] for key in aliases if row.get(key) is not None]
                if not values and field == "close":
                    reject("event_price_close_missing")
                if values:
                    if any(isinstance(value, bool) for value in values):
                        reject("event_price_number_invalid")
                    numbers = [Decimal(str(value)) for value in values]
                    if len(set(numbers)) != 1 or not numbers[0].is_finite() or numbers[0] <= 0:
                        reject("event_price_number_invalid")
                    entry[field] = str(numbers[0])
            rows.append(entry)
        rows.sort(key=lambda row: row["day"])
        if len({row["day"] for row in rows}) != len(rows):
            reject("event_price_duplicate_day")
        return rows
    except (ValueError, TypeError, InvalidOperation) as exc:
        log.warning("event_datahub_rows_invalid", error_type=type(exc).__name__)
        reject("event_price_rows_invalid")


def import_reference(research, reference: ImportReference, key: str):
    if reference.index_id not in INDICES:
        reject("event_index_unknown")
    with retention_lock(research.store.root):
        snapshots = Snapshots(research.store)
        manifest = snapshots.detail(reference.session_id, reference.dataset_id)
        query = manifest.get("query", {})
        provider_query = manifest.get("provider_query", {})
        parameters = query.get("parameters", {})
        if snapshot_identity(manifest) != reference.index_id:
            reject("event_index_identity_unverified")
        frequency = (
            query.get("frequency") or parameters.get("frequency") or provider_query.get("frequency")
        )
        if frequency not in {"day", "daily", "1d"}:
            reject("event_daily_frequency_unverified")
        if manifest.get("status") not in {"success", "ok", "complete", "completed"}:
            reject("event_source_not_successful")
        raw = snapshots.read(reference.session_id, reference.dataset_id, "rows.json")
        if len(raw) > 8 * 1024 * 1024:
            reject("event_price_import_budget")
        rows = normalize_rows(raw)
        intent = {**reference.model_dump(), "source_sha256": hashlib.sha256(raw).hexdigest()}
        cached = research.event_timeline.records.cached("datahub-price-import", key, intent)
        if cached is not None:
            return cached[0]
        original = research.event_timeline.archive_evidence(
            raw,
            source="datahub_snapshot",
            url=manifest.get("source_url") or "",
            metadata={
                "snapshot_manifest_sha256": manifest["manifest_sha256"],
                **reference.model_dump(),
            },
        )
        normalized = json.dumps(
            {"index_id": reference.index_id, "rows": rows},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        ref = research.event_timeline.archive_evidence(
            normalized,
            source="datahub_snapshot",
            url=manifest.get("source_url") or "",
            metadata={
                "original": original,
                "historical_eligible": False,
                "basis": "observed_daily_rows",
            },
        )
        value = {
            "title": f"{INDICES[reference.index_id]['name']} · {rows[0]['day']}—{rows[-1]['day']}",
            "index_id": reference.index_id,
            "evidence_ref": ref,
            "price_role": "index",
            "source_kind": "datahub_snapshot",
            "original_ref": original,
            "historical_eligible": False,
            "calendar_verified": False,
            "source_snapshot": reference.model_dump(),
            "source_manifest_sha256": manifest["manifest_sha256"],
            "limitations": [
                "今日取得不认证历史可得性",
                "观测日线不证明交易日历完整性",
                "指数点位不是可交易代理收益",
            ],
        }
        result = research.event_timeline.records.batch(
            [{"kind": "prices", "payload": value}], key, intent=intent, scope="datahub-price-import"
        )[0]
        log.info("event_datahub_prices_registered", rows=len(rows), index=reference.index_id)
        return result


class CalendarReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    dataset_id: str
    bundle_ref: dict
    holiday_freeze_ref: dict | None = None


def import_calendar(research, reference: CalendarReference, key: str):
    """Native trading-day facts support descriptive holiday studies, not PIT certification."""
    from .event_studies.contracts import Calendar

    with retention_lock(research.store.root):
        records = research.event_timeline.records
        ref = reference.bundle_ref
        if set(ref) != {"id", "revision"}:
            reject("event_bundle_reference_invalid")
        bundle = records.get("prices", ref["id"], revision=ref["revision"])
        index = bundle["payload"]["index_id"]
        snapshots = Snapshots(research.store)
        manifest = snapshots.detail(reference.session_id, reference.dataset_id)
        query = manifest.get("query", {})
        market = query.get("parameters", {}).get("market")
        if query.get("capability") != "trading_calendar" or market != INDICES[index]["market"]:
            reject("event_calendar_market_unverified")
        if manifest.get("status") != "complete" or manifest.get("pagination_complete") is not True:
            reject("event_calendar_coverage_incomplete")
        raw = snapshots.read(reference.session_id, reference.dataset_id, "rows.json")
        try:
            rows = json.loads(raw)
            if not isinstance(rows, list) or not 2 <= len(rows) <= 20000:
                reject("event_calendar_rows_invalid")
            days, all_days = [], []
            for row in rows:
                if row.get("market") != market or type(row.get("is_trading_day")) is not bool:
                    reject("event_calendar_rows_invalid")
                day = date.fromisoformat(row["date"])
                all_days.append(day)
                if row["is_trading_day"]:
                    days.append(day)
            if days != sorted(set(days)):
                reject("event_calendar_rows_invalid")
            if (
                all_days != sorted(set(all_days))
                or len(all_days) != (all_days[-1] - all_days[0]).days + 1
            ):
                reject("event_calendar_coverage_incomplete")
            captured = manifest["retrieved_at"]
            zone = ZoneInfo(
                {"CN": "Asia/Shanghai", "US": "America/New_York", "HK": "Asia/Hong_Kong"}[market]
            )
            closing = time(15) if market == "CN" else time(16)
            sessions = [
                {
                    "day": day.isoformat(),
                    "opens": datetime.combine(day, time(9, 30), zone).isoformat(),
                    "closes": datetime.combine(day, closing, zone).isoformat(),
                }
                for day in days
            ]
            calendar_value = {
                "exchange": INDICES[index]["exchange"],
                "timezone": str(zone),
                "version": manifest["manifest_sha256"],
                "source_ref": f"datahub:{reference.dataset_id}",
                "known_at": captured,
                "sessions": sessions,
            }
            Calendar.model_validate(calendar_value)
        except (ValueError, TypeError, KeyError) as exc:
            log.warning("event_calendar_import_invalid", error_type=type(exc).__name__)
            reject("event_calendar_rows_invalid")
        holidays = []
        if reference.holiday_freeze_ref:
            frozen = records.get(
                "freeze",
                reference.holiday_freeze_ref["id"],
                revision=reference.holiday_freeze_ref["revision"],
            )
            for event in frozen["payload"]["events"]:
                value = event["payload"]
                if (
                    value.get("category") != "calendar"
                    or value.get("date_precision") != "day"
                    or market not in value.get("markets", [])
                ):
                    reject("event_holiday_definition_invalid")
                holidays.append(
                    {
                        "id": event["id"],
                        "name": value["title"],
                        "start": value["occurrence_start"],
                        "end": value.get("occurrence_end") or value["occurrence_start"],
                    }
                )
        intent = reference.model_dump(mode="json")
        cached = records.cached("datahub-calendar-import", key, intent)
        if cached is not None:
            return cached[-1]
        original = research.event_timeline.archive_evidence(
            raw,
            source="datahub_calendar_native",
            url=manifest.get("source_url") or "",
            metadata={"source_manifest_sha256": manifest["manifest_sha256"]},
        )
        archive = research.event_timeline.archive_evidence(
            json.dumps({**calendar_value, "holidays": holidays}, separators=(",", ":")).encode(),
            source="datahub_calendar",
            url=manifest.get("source_url") or "",
            metadata={
                "original": original,
                "native_rows_sha256": hashlib.sha256(raw).hexdigest(),
                "source_manifest_sha256": manifest["manifest_sha256"],
                "session_times": "standard_hours_assumption_not_native_half_day_proof",
                "historical_eligible": False,
            },
        )
        from uuid import uuid4

        calendar_id = uuid4().hex
        payload = {
            **bundle["payload"],
            "calendar_ref": {"id": calendar_id, "revision": 1},
            "calendar_verified": False,
            "calendar_basis": "provider_declared_days_standard_hours_unverified",
        }
        operations = [
            {
                "kind": "calendar",
                "new_id": calendar_id,
                "payload": {
                    "evidence_ref": archive,
                    "historical_eligible": False,
                    "source_kind": "provider_calendar_projection",
                    "index_id": index,
                    "calendar_exchange": INDICES[index]["exchange"],
                    "source_snapshot": {
                        "session_id": reference.session_id,
                        "dataset_id": reference.dataset_id,
                    },
                    "source_manifest_sha256": manifest["manifest_sha256"],
                },
            },
            {
                "kind": "prices",
                "id": bundle["id"],
                "expected_revision": bundle["revision"],
                "payload": payload,
            },
        ]
        result = records.batch(operations, key, intent=intent, scope="datahub-calendar-import")[-1]
        log.info("event_calendar_registered", sessions=len(sessions), holidays=len(holidays))
        return result


@router.post("/calendar")
async def register_calendar(
    body: CalendarReference,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    if request.headers.get("X-Research-User-Action") != "?1":
        raise StoreError("需要明确用户操作", "explicit_user_action_required", 403)
    return await host_operation(
        request, lambda: import_calendar(request.app.state.research, body, idempotency_key)
    )


@router.post("/native")
async def register_native_input(
    body: NativeInputReference,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    if request.headers.get("X-Research-User-Action") != "?1":
        raise StoreError("需要明确用户操作", "explicit_user_action_required", 403)
    return await host_operation(
        request,
        lambda: request.app.state.research.event_inputs.register_native(
            body.kind,
            {"session_id": body.session_id, "dataset_id": body.dataset_id},
            body.index_id,
            idempotency_key,
            links={name: value.model_dump() for name, value in body.links.items()},
        ),
    )


@router.get("/choices")
async def input_choices(request: Request):
    return await host_operation(request, request.app.state.research.event_inputs.choices)


@router.post("/link")
async def link_inputs(
    body: LinkInputReference,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    if request.headers.get("X-Research-User-Action") != "?1":
        raise StoreError("需要明确用户操作", "explicit_user_action_required", 403)
    return await host_operation(
        request,
        lambda: request.app.state.research.event_inputs.link_bundle(
            body.bundle_ref.model_dump(),
            {name: reference.model_dump() for name, reference in body.links.items()},
            idempotency_key,
        ),
    )


@router.post("")
async def register_source(
    body: ImportReference,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128),
):
    if request.headers.get("X-Research-User-Action") != "?1":
        raise StoreError("需要明确用户操作", "explicit_user_action_required", 403)
    return await host_operation(
        request, lambda: import_reference(request.app.state.research, body, idempotency_key)
    )
