"""Private, closed Wind Client API queries for the reviewed weekly report.

This adapter never starts Excel, installs WindPy, logs in, stops a user's Wind
session, or guesses an economic-calendar dataset. General DSH tools retain the
existing broker contracts; this input is only created by the trusted Host.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import importlib
import importlib.util
import json
import threading
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, model_validator

from core.observability import get_logger

from ..report_workflows.weekly_data import (
    MAPPING_SHA256,
    assess_weekly_snapshot,
    load_weekly_mapping,
    sample_snapshot,
    weekly_snapshot_sha256,
)
from .providers import ProviderError

log = get_logger(__name__)
WIND_API_DEADLINE_SECONDS = 18.0
MAX_API_ROWS = 10000
MAX_API_BYTES = 16 * 1024 * 1024
SEMANTICS_REVISION = "wind-client-api-weekly-v1"
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="rwb-wind-api")
_LOCK = threading.Lock()
_OUTSTANDING: concurrent.futures.Future | None = None


class _SeriesRow(TypedDict):
    date: str
    value: int | float | None
    published_at: str | None


class WindAPIQuery(BaseModel):
    """A private Host request, deliberately absent from BUSINESS_TOOLS."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["series", "calendar", "economic_calendar", "weekly"]
    series_id: str | None = None
    market: str | None = None
    start_date: str
    end_date: str
    cutoff: str
    source: Literal["wind"] = "wind"
    capability: Literal["report_weekly"] = "report_weekly"
    refresh: bool = True

    @property
    def parameters(self) -> dict:
        return self.model_dump(exclude={"source", "capability", "refresh"})

    @model_validator(mode="after")
    def valid_scope(self):
        start, end = date.fromisoformat(self.start_date), date.fromisoformat(self.end_date)
        cutoff = datetime.fromisoformat(self.cutoff)
        if cutoff.tzinfo is None or start > end:
            raise ValueError("weekly_api_range_invalid")
        if self.kind != "economic_calendar" and end > cutoff.date():
            raise ValueError("weekly_api_future_range")
        if self.kind == "series" and (not self.series_id or self.market is not None):
            raise ValueError("weekly_api_series_required")
        if self.kind == "calendar" and (not self.market or self.series_id is not None):
            raise ValueError("weekly_api_market_required")
        if self.kind == "economic_calendar" and (
            self.series_id is not None or self.market is not None
        ):
            raise ValueError("weekly_api_calendar_scope_invalid")
        return self

    def fingerprint(self, *, include_refresh=False):
        value = self.model_dump(exclude=set() if include_refresh else {"refresh"})
        return weekly_snapshot_sha256(value)


def activity_witness() -> dict:
    with _LOCK:
        return {"active": _OUTSTANDING is not None and not _OUTSTANDING.done()}


async def wait_for_idle() -> None:
    """Cancellation does not release a synchronous SDK invocation prematurely."""
    with _LOCK:
        outstanding = _OUTSTANDING
    if outstanding is not None:
        try:
            await asyncio.shield(asyncio.wrap_future(outstanding))
        except Exception as exc:  # noqa: BLE001 - preserve drain without vendor text.
            log.warning("wind_api_drain_failed", error_type=type(exc).__name__)


def _sdk_default():
    try:
        return importlib.import_module("WindPy").w
    except (ImportError, AttributeError) as exc:
        raise ProviderError("wind_api_dependency_missing") from exc


def _json_vendor(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_vendor(item) for item in value]
    raise ProviderError("wind_api_response_shape_invalid")


class WindClientAPIProvider:
    """Lazy read-only adapter; readiness is not successful market-data proof."""

    provider_id = "wind_client_api"

    def __init__(
        self,
        *,
        sdk_factory=None,
        calendar_contracts=None,
        economic_contract=None,
        deadline_seconds=18.0,
    ):
        self._sdk_factory = sdk_factory or _sdk_default
        self._injected = sdk_factory is not None
        self._calendars = calendar_contracts or load_weekly_mapping()["calendars"]
        self._economic = economic_contract
        self.deadline_seconds = min(WIND_API_DEADLINE_SECONDS, max(0.01, float(deadline_seconds)))

    def readiness(self) -> dict:
        sdk_identity = None
        try:
            specification = None if self._injected else importlib.util.find_spec("WindPy")
            dependency = self._injected or specification is not None
            if self._injected:
                sdk_identity = hashlib.sha256(b"injected-offline-sdk").hexdigest()
            elif specification is not None and specification.origin:
                sdk_file = Path(specification.origin)
                if (
                    sdk_file.is_file()
                    and not sdk_file.is_symlink()
                    and sdk_file.stat().st_size <= 20 * 1024 * 1024
                ):
                    sdk_identity = hashlib.sha256(sdk_file.read_bytes()).hexdigest()
        except (ImportError, ValueError):
            dependency = False
        except OSError:
            dependency = False
        return {
            "provider": self.provider_id,
            "dependency_ready": dependency,
            "status": "unverified" if dependency else "blocked_dependency",
            "code": None if dependency else "wind_api_dependency_missing",
            "live_verified": False,
            "mapping_sha256": MAPPING_SHA256,
            "sdk_identity_sha256": sdk_identity,
            "adapter_revision": SEMANTICS_REVISION,
            "economic_calendar_status": "verified" if self._economic else "unverified",
            "calendar_status": (
                "verified"
                if all(row.get("semantics_verified") is True for row in self._calendars.values())
                else "unverified"
            ),
        }

    def _spec(self, query: WindAPIQuery) -> dict:
        if query.kind == "weekly":
            raise ProviderError("weekly_query_requires_collector")
        if query.kind == "economic_calendar":
            if (
                not isinstance(self._economic, dict)
                or self._economic.get("method") != "wset"
                or self._economic.get("semantics_verified") is not True
            ):
                raise ProviderError("economic_calendar_contract_unverified")
            return self._economic
        mapping = load_weekly_mapping()
        if query.kind == "series":
            spec = next((item for item in mapping["series"] if item["id"] == query.series_id), None)
            if spec is None:
                raise ValueError("weekly_api_series_unknown")
            return spec
        contract = self._calendars.get(query.market)
        if (
            not isinstance(contract, dict)
            or contract.get("semantics_verified") is not True
            or not isinstance(contract.get("wind_calendar"), str)
        ):
            raise ProviderError("wind_api_calendar_contract_unverified")
        # Calendar codes are reviewed adapter configuration, never user text.
        if not contract["wind_calendar"].isascii() or not contract["wind_calendar"].isalnum():
            raise ProviderError("wind_api_calendar_contract_invalid")
        return contract

    def _fetch_sync(self, query: WindAPIQuery, spec: dict) -> dict:
        sdk = self._sdk_factory()
        connected = getattr(sdk, "isconnected", None)
        if not callable(connected) or connected() is not True:
            raise ProviderError("wind_api_not_logged_in")
        if query.kind == "economic_calendar":
            options = {
                **spec.get("static_options", {}),
                spec["start_parameter"]: query.start_date,
                spec["end_parameter"]: query.end_date,
            }
            response = sdk.wset(
                spec["dataset"],
                ";".join(f"{key}={value}" for key, value in sorted(options.items())),
            )
        elif query.kind == "calendar":
            response = sdk.tdays(
                query.start_date, query.end_date, f"TradingCalendar={spec['wind_calendar']}"
            )
        elif spec["kind"] == "edb":
            response = sdk.edb(spec["asset"], query.start_date, query.end_date, "Fill=Blank")
        else:
            response = sdk.wsd(
                spec["asset"],
                spec["field"],
                query.start_date,
                query.end_date,
                "Period=D;PriceAdj=U;Days=Trading;Fill=Blank",
            )
        error = getattr(response, "ErrorCode", None)
        if isinstance(error, bool) or not isinstance(error, int) or error != 0:
            raise ProviderError("wind_api_vendor_error")
        raw = {
            key: _json_vendor(getattr(response, key, None))
            for key in ("Codes", "Fields", "Times", "Data")
        }
        try:
            encoded = json.dumps(
                raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        except (ValueError, TypeError) as exc:
            raise ProviderError("wind_api_response_nonfinite") from exc
        if len(encoded) > MAX_API_BYTES:
            raise ProviderError("wind_api_response_size_limit")
        if query.kind == "economic_calendar":
            fields, data = raw["Fields"], raw["Data"]
            if (
                not isinstance(fields, list)
                or not isinstance(data, list)
                or len(data) != len(fields)
                or not data
                or any(
                    not isinstance(column, list) or len(column) != len(data[0]) for column in data
                )
                or len(data[0]) > MAX_API_ROWS
            ):
                raise ProviderError("wind_api_economic_shape_invalid")
            if len(set(fields)) != len(fields) or any(
                field not in fields for field in spec["fields"].values()
            ):
                raise ProviderError("wind_api_economic_fields_invalid")
            events = []
            for index in range(len(data[0])):
                event = {
                    key: data[fields.index(field)][index] for key, field in spec["fields"].items()
                }
                if "importance_values" in spec:
                    raw_importance = str(event["importance"])
                    if raw_importance not in spec["importance_values"]:
                        raise ProviderError("wind_api_economic_importance_unmapped")
                    event["importance"] = spec["importance_values"][raw_importance]
                try:
                    event["date"] = date.fromisoformat(str(event["date"])[:10]).isoformat()
                except ValueError as exc:
                    raise ProviderError("wind_api_economic_date_invalid") from exc
                if not query.start_date <= event["date"] <= query.end_date or not all(
                    isinstance(event[key], str) and event[key].strip()
                    for key in ("country", "indicator", "importance")
                ):
                    raise ProviderError("wind_api_economic_row_invalid")
                events.append(event)
            return {
                "source": self.provider_id,
                "coverage_start": query.start_date,
                "coverage_end": query.end_date,
                "coverage_verified": True,
                "events": events,
                "raw_payload": raw,
                "raw_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        if query.kind == "calendar":
            data = raw["Data"]
            if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], list):
                raise ProviderError("wind_api_calendar_shape_invalid")
            dates = [date.fromisoformat(str(value)[:10]).isoformat() for value in data[0]]
            if (
                len(dates) > MAX_API_ROWS
                or dates != sorted(set(dates))
                or any(not query.start_date <= day <= query.end_date for day in dates)
            ):
                raise ProviderError("wind_api_calendar_range_invalid")
            closes = spec.get("session_closes")
            if closes is None and spec.get("close_time"):
                hour, minute = map(int, spec["close_time"].split(":"))
                zone = ZoneInfo(spec["timezone"])
                closes = {}
                for day in dates:
                    session_date = date.fromisoformat(day) + timedelta(
                        days=spec.get("close_day_offset", 0)
                    )
                    close_hour, close_minute = hour, minute
                    if day in spec.get("session_overrides", {}):
                        close_hour, close_minute = map(
                            int, spec["session_overrides"][day].split(":")
                        )
                    closes[day] = datetime.combine(
                        session_date, time(close_hour, close_minute), zone
                    ).isoformat()
            # The SDK's date-only calendar cannot prove when a foreign session
            # ended. A separately reviewed session-close contract is mandatory.
            if not isinstance(closes, dict) or any(day not in closes for day in dates):
                raise ProviderError("wind_api_session_close_unverified")
            cutoff = datetime.fromisoformat(query.cutoff)
            completed = [day for day in dates if datetime.fromisoformat(closes[day]) <= cutoff]
            if not completed:
                raise ProviderError("wind_api_calendar_no_completed_session")
            return {
                "source": self.provider_id,
                "dates": dates,
                "completed_dates": completed,
                "session_closes": {day: closes[day] for day in dates},
                "semantics_verified": True,
                "raw_sha256": hashlib.sha256(encoded).hexdigest(),
                "raw_payload": raw,
            }
        if raw["Codes"] != [spec["asset"]]:
            raise ProviderError("wind_api_identity_mismatch")
        fields, times, data = raw["Fields"], raw["Times"], raw["Data"]
        if (
            not isinstance(fields, list)
            or len(fields) != 1
            or (spec["kind"] != "edb" and str(fields[0]).casefold() != spec["field"])
        ):
            raise ProviderError("wind_api_field_mismatch")
        if (
            not isinstance(times, list)
            or not isinstance(data, list)
            or len(data) != 1
            or len(data[0]) != len(times)
            or not times
            or len(times) > MAX_API_ROWS
        ):
            raise ProviderError("wind_api_response_shape_invalid")
        rows: list[_SeriesRow] = []
        seen: set[str] = set()
        for day, value in zip(times, data[0], strict=True):
            day = date.fromisoformat(str(day)[:10]).isoformat()
            if not query.start_date <= day <= query.end_date or day in seen:
                raise ProviderError("wind_api_dates_invalid")
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                raise ProviderError("wind_api_number_missing")
            seen.add(day)
            rows.append({"date": day, "value": value, "published_at": None})
        rows.sort(key=lambda row: row["date"])
        missing_dates = []
        while rows and rows[-1]["value"] is None:
            missing_dates.append(rows.pop()["date"])
        if not rows or any(row["value"] is None for row in rows):
            raise ProviderError("wind_api_interior_or_all_values_missing")
        log.info("wind_api_series_read", series_id=spec["id"], row_count=len(rows))
        return {
            **{key: spec[key] for key in ("asset", "field", "unit", "currency", "market")},
            "source": self.provider_id,
            "rows": rows,
            "missing_dates": sorted(missing_dates),
            "raw_sha256": hashlib.sha256(encoded).hexdigest(),
            "raw_payload": raw,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "equivalence_verified": False,
            "limitations": [
                "published_at_unknown",
                "requires_same_source_excel_comparison",
                *(["trailing_observations_unavailable"] if missing_dates else []),
            ],
        }

    async def fetch(self, query: WindAPIQuery) -> dict:
        global _OUTSTANDING
        spec = self._spec(query)
        with _LOCK:
            if _OUTSTANDING is not None and not _OUTSTANDING.done():
                raise ProviderError("wind_api_busy")
            future = _EXECUTOR.submit(self._fetch_sync, query, spec)
            _OUTSTANDING = future
        try:
            return await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(future)), self.deadline_seconds
            )
        except TimeoutError as exc:
            log.warning("wind_api_deadline_reached")
            raise ProviderError("wind_api_timeout") from exc
        except asyncio.CancelledError:
            log.info("wind_api_cancellation_requested")
            raise
        except (ProviderError, ValueError):
            raise
        except Exception as exc:
            log.warning("wind_api_read_failed", error_type=type(exc).__name__)
            raise ProviderError("wind_api_query_failed") from exc

    async def collect(
        self, contract: dict, *, baseline_snapshot=None, economic_calendar=None
    ) -> dict:
        """Collect the exact reviewed set, preserving partial results on failure."""
        snapshot = sample_snapshot(contract)
        snapshot["limitations"] = []
        mapping = load_weekly_mapping()
        issues = []
        for market in mapping["calendars"]:
            try:
                earliest = min(
                    [
                        contract["window_start"],
                        *[
                            item["history_start"]
                            for item in mapping["series"]
                            if item["market"] == market and item["history_start"]
                        ],
                    ]
                )
                query = WindAPIQuery(
                    kind="calendar",
                    market=market,
                    start_date=earliest,
                    end_date=contract["period_end"],
                    cutoff=contract["cutoff"],
                )
                snapshot["calendars"][market] = await self.fetch(query)
            except (ProviderError, ValueError) as exc:
                issues.append(f"{market}:{exc!s}")
        # Without verified calendars, do not spend dozens of vendor calls on
        # data that cannot be accepted. Explicit series preflights remain usable.
        if not issues:
            for spec in mapping["series"]:
                try:
                    query = WindAPIQuery(
                        kind="series",
                        series_id=spec["id"],
                        start_date=spec["history_start"] or contract["window_start"],
                        end_date=snapshot["calendars"][spec["market"]]["completed_dates"][-1],
                        cutoff=contract["cutoff"],
                    )
                    snapshot["series"][spec["id"]] = await self.fetch(query)
                except (ProviderError, ValueError) as exc:
                    issues.append(f"{spec['id']}:{exc!s}")
        if economic_calendar is None:
            try:
                query = WindAPIQuery(
                    kind="economic_calendar",
                    start_date=contract["next_calendar_start"],
                    end_date=contract["next_calendar_end"],
                    cutoff=contract["cutoff"],
                )
                snapshot["economic_calendar"] = await self.fetch(query)
            except (ProviderError, ValueError) as exc:
                issues.append(str(exc))
        else:
            snapshot["economic_calendar"] = economic_calendar
        if baseline_snapshot is not None:
            snapshot["equivalence_baseline"] = baseline_snapshot
        snapshot["limitations"].extend(issues)
        assessment = assess_weekly_snapshot(snapshot, contract)
        assessment["issues"] = sorted({*assessment["issues"], *issues})
        if issues:
            assessment["status"] = "blocked_data"
        return {"contract": contract, "snapshot": snapshot, "assessment": assessment}
