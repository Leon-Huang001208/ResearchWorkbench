"""Closed Huaan weekly input contract and independently reproducible arithmetic.

Only Host-created, hash-verified snapshots belong here. Model-created claims,
cached worksheet totals and a provider's ``passed`` flag are not data evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

from core.observability import get_logger

log = get_logger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
POLICY_ID = "huaan-etf-weekly-v1"
MAPPING_SHA256 = "f0337d4564749ba2fe97ae029fede7b71834edb635bd62d68206995319da98ce"
_HASH = re.compile(r"^[a-f0-9]{64}$")
_SOURCES = {"wind_client_api", "wind_excel"}


def weekly_snapshot_sha256(value: dict) -> str:
    """Bind every normalized input byte, refusing JSON non-finite extensions."""
    try:
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("weekly_snapshot_not_json") from exc
    return hashlib.sha256(raw).hexdigest()


def load_weekly_mapping() -> dict:
    """Return the reviewed resource; changes require an explicit new identity."""
    try:
        raw = Path(__file__).with_name("huaan_weekly_mapping.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != MAPPING_SHA256:
            raise ValueError("weekly_mapping_hash_mismatch")
        return json.loads(raw)
    except (OSError, ValueError) as exc:
        log.error("report_weekly_mapping_unavailable", error_type=type(exc).__name__)
        raise ValueError("weekly_mapping_unavailable") from exc


def _aware(value: str | datetime) -> datetime:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as exc:
        raise ValueError("weekly_datetime_invalid") from exc
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("weekly_timezone_required")
    return parsed


def _day(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("weekly_date_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("weekly_date_invalid") from exc


def _number(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError("weekly_number_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("weekly_number_invalid") from exc
    if not parsed.is_finite():
        raise ValueError("weekly_number_invalid")
    return parsed


def _mean(values: dict, days: list[str]) -> str:
    with localcontext() as context:
        context.prec = 96
        return format(sum((values[day] for day in days), Decimal(0)) / len(days), "f")


def _percent_change(initial: Decimal, final: Decimal) -> str:
    with localcontext() as context:
        context.prec = 96
        return format((final / initial - 1) * 100, "f")


def build_weekly_data_contract(cutoff: datetime | str, calendars: dict | None = None) -> dict:
    """Freeze the most recent scheduled period; never ask for future Friday data."""
    requested = _aware(cutoff).astimezone(SHANGHAI)
    friday = requested.date() - timedelta(days=(requested.weekday() - 4) % 7)
    frozen = datetime.combine(friday, time(15, 30), SHANGHAI)
    if frozen > requested:
        frozen -= timedelta(days=7)
    monday = frozen.date() - timedelta(days=4)
    contract = {
        "schema_version": 1,
        "policy_id": POLICY_ID,
        "workflow_id": "huaan-etf-weekly",
        "mapping_sha256": MAPPING_SHA256,
        "cutoff": frozen.isoformat(),
        "period_start": monday.isoformat(),
        "period_end": frozen.date().isoformat(),
        "previous_period_start": (monday - timedelta(days=7)).isoformat(),
        "window_start": (monday - timedelta(days=21)).isoformat(),
        "next_calendar_start": (monday + timedelta(days=7)).isoformat(),
        "next_calendar_end": (monday + timedelta(days=13)).isoformat(),
        "max_lag_sessions": 1,
        "required_series": [row["id"] for row in load_weekly_mapping()["series"]],
    }
    if calendars is not None:
        contract["calendar_input_sha256"] = weekly_snapshot_sha256(calendars)
    contract["contract_sha256"] = weekly_snapshot_sha256(contract)
    return contract


def _calendar(value: dict, cutoff: datetime) -> list[str]:
    if (
        not isinstance(value, dict)
        or value.get("source") not in _SOURCES
        or not _HASH.fullmatch(str(value.get("raw_sha256", "")))
        or value.get("semantics_verified") is not True
    ):
        raise ValueError("weekly_calendar_unverified")
    dates = value.get("dates")
    completed = value.get("completed_dates")
    if not isinstance(dates, list) or not isinstance(completed, list) or not completed:
        raise ValueError("weekly_calendar_missing")
    if dates != sorted(set(dates)) or completed != sorted(set(completed)):
        raise ValueError("weekly_calendar_conflict")
    for day in dates:
        _day(day)
    if not set(completed).issubset(dates):
        raise ValueError("weekly_calendar_conflict")
    # Full trading dates are not enough: the collector must supply the actual
    # close timestamp for each completed session, including overseas sessions.
    closes = value.get("session_closes", {})
    for day in completed:
        if _day(day) > cutoff.date() or day not in closes or _aware(closes[day]) > cutoff:
            raise ValueError("weekly_calendar_future_session")
    return completed


def _series_rows(value: dict, spec: dict, cutoff: datetime, completed: list[str]) -> dict:
    if not isinstance(value, dict) or value.get("source") not in _SOURCES:
        raise ValueError("weekly_series_missing")
    for key in ("asset", "field", "unit", "currency", "market"):
        if value.get(key) != spec.get(key):
            raise ValueError("weekly_series_not_equivalent")
    if not _HASH.fullmatch(str(value.get("raw_sha256", ""))):
        raise ValueError("weekly_raw_hash_missing")
    rows = value.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > 10000:
        raise ValueError("weekly_series_rows_missing")
    values = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("weekly_series_row_invalid")
        day = row.get("date")
        _day(day)
        if day not in completed or (
            row.get("published_at") is not None and _aware(row["published_at"]) > cutoff
        ):
            raise ValueError("weekly_series_future_or_unclosed")
        numeric = _number(row.get("value"))
        if day in values and values[day] != numeric:
            raise ValueError("weekly_series_date_conflict")
        values[day] = numeric
    return values


def compare_weekly_sources(api: dict, excel: dict, *, groups: set[str] | None = None) -> dict:
    """Recompute a comparison from both inputs; never trust a stored pass flag."""
    issues = []
    if (
        api.get("source") != "wind_client_api"
        or excel.get("source") != "wind_excel"
        or api.get("cutoff") != excel.get("cutoff")
        or api.get("mapping_sha256") != MAPPING_SHA256
        or excel.get("mapping_sha256") != MAPPING_SHA256
        or not excel.get("evidence")
    ):
        issues.append("weekly_comparison_identity_invalid")
    mapping = load_weekly_mapping()["series"]
    allowed_groups = {item["group"] for item in mapping}
    if groups is not None and (not groups or not groups <= allowed_groups):
        raise ValueError("weekly_comparison_groups_invalid")
    for spec in mapping:
        if groups is not None and spec["group"] not in groups:
            continue
        left = api.get("series", {}).get(spec["id"], {})
        right = (
            excel.get("comparisons", {})
            if excel.get("baseline_kind") == "excel_workbooks"
            else excel.get("series", {})
        ).get(spec["id"], {})
        identity = ("asset", "field", "unit", "currency", "market")
        if any(
            left.get(key) != right.get(key) or left.get(key) != spec.get(key) for key in identity
        ):
            issues.append(f"comparison_semantics:{spec['id']}")
            continue
        try:
            if excel.get("baseline_kind") == "excel_workbooks":
                cutoff = _aware(api["cutoff"])
                contract = build_weekly_data_contract(cutoff)
                sessions = _calendar(api.get("calendars", {}).get(spec["market"]), cutoff)
                values = _series_rows(left, spec, cutoff, sessions)
                last = max(values)
                current = [day for day in sessions if contract["period_start"] <= day <= last]
                if not current or any(day not in values for day in current):
                    raise ValueError("incomplete")
                if spec["group"] == "history":
                    b = {
                        row["date"]: _number(row["value"])
                        for row in excel["series"][spec["id"]]["rows"]
                    }
                    if (
                        not b
                        or set(values) != set(b)
                        or any(not _near(values[day], b[day]) for day in b)
                    ):
                        raise ValueError("history")
                elif spec["group"] == "turnover":
                    previous = [
                        day
                        for day in sessions
                        if contract["previous_period_start"] <= day < contract["period_start"]
                    ]
                    if not previous or any(day not in values for day in previous):
                        raise ValueError("incomplete")
                    if not _near(
                        sum((values[day] for day in current), Decimal(0)),
                        _number(right["current_total"]),
                    ) or not _near(
                        sum((values[day] for day in previous), Decimal(0)),
                        _number(right["previous_total"]),
                    ):
                        raise ValueError("totals")
                else:
                    previous = [day for day in sessions if day < contract["period_start"]]
                    if not previous or previous[-1] not in values or values[previous[-1]] <= 0:
                        raise ValueError("baseline")
                    change = _number(_percent_change(values[previous[-1]], values[last]))
                    if not _near(change, _number(right["return_pct"])):
                        raise ValueError("return")
                    if "close" in right and not _near(values[last], _number(right["close"])):
                        raise ValueError("close")
                    if "baseline_close" in right and not _near(
                        values[previous[-1]], _number(right["baseline_close"])
                    ):
                        raise ValueError("baseline")
                continue
            a = {row["date"]: _number(row["value"]) for row in left["rows"]}
            b = {row["date"]: _number(row["value"]) for row in right["rows"]}
            if (
                not a
                or a.keys() != b.keys()
                or any(
                    abs(a[day] - b[day])
                    > max(Decimal("0.00000001"), abs(b[day]) * Decimal("1e-10"))
                    for day in a
                )
            ):
                issues.append(f"comparison_values:{spec['id']}")
        except (KeyError, TypeError, ValueError):
            issues.append(f"comparison_values:{spec['id']}")
    return {
        "status": "passed" if not issues else "blocked_data",
        "issues": issues,
        "mapping_sha256": MAPPING_SHA256,
        "api_snapshot_sha256": weekly_snapshot_sha256(api),
        "excel_snapshot_sha256": weekly_snapshot_sha256(excel),
    }


def _near(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= max(Decimal("0.00000001"), abs(right) * Decimal("1e-10"))


def build_equivalence_proof(
    api: dict,
    excel: dict,
    *,
    configuration_sha256: str,
    source_contract_sha256: str,
    sdk_identity_sha256: str,
) -> dict:
    """Create reusable evidence from real inputs; never create proof from a flag."""
    groups = []
    for group in sorted({item["group"] for item in load_weekly_mapping()["series"]}):
        if compare_weekly_sources(api, excel, groups={group})["status"] == "passed":
            groups.append(group)
    if not groups or any(
        not _HASH.fullmatch(str(value))
        for value in (configuration_sha256, source_contract_sha256, sdk_identity_sha256)
    ):
        raise ValueError("weekly_equivalence_not_verified")
    # Persist detached actual inputs. Attaching this proof to the current
    # snapshot must neither mutate the evidence nor create a JSON cycle.
    frozen_api = json.loads(json.dumps(api, ensure_ascii=False, allow_nan=False))
    frozen_excel = json.loads(json.dumps(excel, ensure_ascii=False, allow_nan=False))
    proof = {
        "schema_version": 1,
        "mapping_sha256": MAPPING_SHA256,
        "configuration_sha256": configuration_sha256,
        "source_contract_sha256": source_contract_sha256,
        "sdk_identity_sha256": sdk_identity_sha256,
        "groups": groups,
        "api_input": frozen_api,
        "excel_input": frozen_excel,
    }
    proof["proof_sha256"] = weekly_snapshot_sha256(proof)
    return proof


def _assess_equivalence_proof(snapshot: dict, proof: dict) -> list[str]:
    try:
        unsigned = {key: value for key, value in proof.items() if key != "proof_sha256"}
        if (
            proof.get("schema_version") != 1
            or proof.get("mapping_sha256") != MAPPING_SHA256
            or proof.get("proof_sha256") != weekly_snapshot_sha256(unsigned)
        ):
            raise ValueError("weekly_equivalence_proof_invalid")
        for key in ("configuration_sha256", "source_contract_sha256", "sdk_identity_sha256"):
            if not _HASH.fullmatch(str(proof.get(key))) or proof[key] != snapshot.get(key):
                raise ValueError("weekly_equivalence_configuration_changed")
        groups = {
            spec["group"]
            for spec in load_weekly_mapping()["series"]
            if snapshot.get("series", {}).get(spec["id"], {}).get("source") == "wind_client_api"
        }
        if not groups or not groups <= set(proof.get("groups", [])):
            raise ValueError("weekly_equivalence_group_unverified")
        result = compare_weekly_sources(proof["api_input"], proof["excel_input"], groups=groups)
        return result["issues"]
    except (KeyError, TypeError, ValueError) as exc:
        return [str(exc) if isinstance(exc, ValueError) else "weekly_equivalence_proof_invalid"]


def merge_weekly_sources(api: dict, excel: dict) -> dict:
    """Switch only independently matching whole groups, retaining the Excel input."""
    import copy

    merged = copy.deepcopy(excel)
    if merged.get("source") != "wind_excel":
        raise ValueError("weekly_excel_baseline_required")
    switched = []
    comparisons = []
    for group in sorted({item["group"] for item in load_weekly_mapping()["series"]}):
        receipt = compare_weekly_sources(api, excel, groups={group})
        comparisons.append({"group": group, **receipt})
        if receipt["status"] != "passed":
            continue
        for spec in load_weekly_mapping()["series"]:
            if spec["group"] == group:
                merged["series"][spec["id"]] = copy.deepcopy(api["series"][spec["id"]])
        switched.append(group)
    if switched:
        # Keep a true source identity per series. The top-level label means only
        # that at least one group is served by Client API, never all coverage.
        merged["source"] = "wind_client_api"
        merged["equivalence_baseline"] = copy.deepcopy(excel)
        merged["migration_groups"] = switched
        merged["comparison_receipts"] = comparisons
    return merged


def assess_weekly_snapshot(snapshot: dict, contract: dict) -> dict:
    """Validate source evidence and independently derive the report's numbers."""
    issues: list[str] = []
    observations: list[dict] = []
    try:
        snapshot_hash = weekly_snapshot_sha256(snapshot)
        frozen = {key: value for key, value in contract.items() if key != "contract_sha256"}
        if (
            contract.get("policy_id") != POLICY_ID
            or contract.get("mapping_sha256") != MAPPING_SHA256
            or contract.get("contract_sha256") != weekly_snapshot_sha256(frozen)
        ):
            raise ValueError("weekly_contract_invalid")
        if (
            snapshot.get("schema_version") != 1
            or snapshot.get("workflow_id") != "huaan-etf-weekly"
            or snapshot.get("cutoff") != contract["cutoff"]
            or snapshot.get("mapping_sha256") != MAPPING_SHA256
            or snapshot.get("source") not in _SOURCES
        ):
            raise ValueError("weekly_snapshot_schema_invalid")
        cutoff = _aware(contract["cutoff"])
        if contract.get("calendar_input_sha256") and contract[
            "calendar_input_sha256"
        ] != weekly_snapshot_sha256(snapshot.get("calendars", {})):
            raise ValueError("weekly_calendar_input_changed")
        start = contract["period_start"]
        previous_start = contract["previous_period_start"]
        if snapshot["source"] == "wind_client_api":
            proof = snapshot.get("equivalence_proof")
            baseline = snapshot.get("equivalence_baseline")
            if isinstance(proof, dict):
                issues.extend(_assess_equivalence_proof(snapshot, proof))
            elif not isinstance(baseline, dict):
                issues.append("weekly_api_equivalence_unverified")
            else:
                comparison_input = {
                    key: val for key, val in snapshot.items() if key != "equivalence_baseline"
                }
                groups = set(snapshot.get("migration_groups", [])) or None
                actual_groups = {
                    spec["group"]
                    for spec in load_weekly_mapping()["series"]
                    if snapshot.get("series", {}).get(spec["id"], {}).get("source")
                    == "wind_client_api"
                }
                if groups is not None and groups != actual_groups:
                    issues.append("weekly_migration_groups_mismatch")
                comparison = compare_weekly_sources(comparison_input, baseline, groups=groups)
                issues.extend(comparison["issues"])
        calendars = snapshot.get("calendars", {})
        for spec in load_weekly_mapping()["series"]:
            try:
                sessions = _calendar(calendars.get(spec["market"]), cutoff)
                values = _series_rows(
                    snapshot.get("series", {}).get(spec["id"]), spec, cutoff, sessions
                )
                available = sorted(values)
                as_of = available[-1]
                if len([day for day in sessions if day > as_of]) > contract["max_lag_sessions"]:
                    raise ValueError("weekly_series_stale")
                current = [day for day in sessions if start <= day <= as_of]
                if not current:
                    raise ValueError("weekly_current_period_empty")
                if spec["kind"] == "edb":
                    expected = [day for day in sessions if spec["history_start"] <= day <= as_of]
                    if not expected or any(day not in values for day in expected):
                        raise ValueError("weekly_history_incomplete")
                    observations.append(
                        {
                            "id": spec["id"],
                            "kind": "history",
                            "as_of": as_of,
                            "count": len(expected),
                            "unit": spec["unit"],
                            "currency": spec["currency"],
                            "source_sha256": snapshot["series"][spec["id"]]["raw_sha256"],
                        }
                    )
                elif spec["group"] == "turnover":
                    previous = [day for day in sessions if previous_start <= day < start]
                    if not previous or any(day not in values for day in [*previous, *current]):
                        raise ValueError("weekly_turnover_incomplete")
                    this_mean = _mean(values, current)
                    last_mean = _mean(values, previous)
                    observations.append(
                        {
                            "id": spec["id"],
                            "kind": "turnover",
                            "as_of": as_of,
                            "value": this_mean,
                            "previous_value": last_mean,
                            "trading_days": len(current),
                            "previous_trading_days": len(previous),
                            "current_rows": [
                                {"date": day, "value": format(values[day], "f")} for day in current
                            ],
                            "previous_rows": [
                                {"date": day, "value": format(values[day], "f")} for day in previous
                            ],
                            "unit": spec["unit"],
                            "currency": spec["currency"],
                            "source_sha256": snapshot["series"][spec["id"]]["raw_sha256"],
                        }
                    )
                else:
                    prior = [day for day in sessions if day < start]
                    if (
                        not prior
                        or prior[-1] not in values
                        or any(day not in values for day in current)
                    ):
                        raise ValueError("weekly_price_endpoints_missing")
                    initial, final = values[prior[-1]], values[as_of]
                    if initial <= 0 or final <= 0:
                        raise ValueError("weekly_price_invalid")
                    observations.append(
                        {
                            "id": spec["id"],
                            "kind": "price_return",
                            "as_of": as_of,
                            "baseline_date": prior[-1],
                            "close": format(final, "f"),
                            "baseline_close": format(initial, "f"),
                            "return_pct": _percent_change(initial, final),
                            "unit": spec["unit"],
                            "currency": spec["currency"],
                            "source_sha256": snapshot["series"][spec["id"]]["raw_sha256"],
                        }
                    )
            except (TypeError, KeyError, ValueError, InvalidOperation) as exc:
                issues.append(
                    f"{spec['id']}:{str(exc) if isinstance(exc, ValueError) else 'weekly_input_invalid'}"
                )
        calendar = snapshot.get("economic_calendar", {})
        try:
            if (
                calendar.get("source") not in _SOURCES
                or calendar.get("coverage_start") != contract["next_calendar_start"]
                or calendar.get("coverage_end") != contract["next_calendar_end"]
                or not _HASH.fullmatch(str(calendar.get("raw_sha256", "")))
                or calendar.get("coverage_verified") is not True
                or not isinstance(calendar.get("events"), list)
            ):
                raise ValueError("weekly_economic_calendar_incomplete")
            for event in calendar["events"]:
                day = _day(event["date"])
                if (
                    not _day(contract["next_calendar_start"])
                    <= day
                    <= _day(contract["next_calendar_end"])
                ):
                    raise ValueError("weekly_economic_calendar_wrong_period")
                if not all(
                    isinstance(event.get(key), str) and event[key].strip()
                    for key in ("country", "indicator", "importance")
                ):
                    raise ValueError("weekly_economic_calendar_event_invalid")
        except (KeyError, TypeError, ValueError) as exc:
            issues.append(
                str(exc) if isinstance(exc, ValueError) else "weekly_economic_calendar_invalid"
            )
    except (KeyError, TypeError, ValueError) as exc:
        issues.append(str(exc) if isinstance(exc, ValueError) else "weekly_snapshot_schema_invalid")
        snapshot_hash = None
    status = "passed" if not issues else "blocked_data"
    specifications = {item["id"]: item for item in load_weekly_mapping()["series"]}
    for observation in observations:
        specification = specifications[observation["id"]]
        observation["display_name"] = specification["display_name"]
        observation["group"] = specification["group"]
    log.info(
        "report_weekly_data_assessed",
        status=status,
        issue_count=len(issues),
        observation_count=len(observations),
    )
    return {
        "status": status,
        "issues": sorted(set(issues)),
        "observations": observations,
        "contract_sha256": contract.get("contract_sha256"),
        "snapshot_sha256": snapshot_hash,
    }


def sample_snapshot(contract: dict) -> dict:
    """Return a schema example, explicitly empty and incapable of passing gates."""
    return {
        "schema_version": 1,
        "workflow_id": "huaan-etf-weekly",
        "cutoff": contract["cutoff"],
        "mapping_sha256": MAPPING_SHA256,
        "source": "wind_client_api",
        "series": {},
        "calendars": {},
        "economic_calendar": {},
        "evidence": [],
        "limitations": ["schema_example_not_market_data"],
    }


def materialize_weekly_workbooks(snapshot: dict, run_root: Path, manifest) -> dict:
    """Project validated data into Run copies while preserving Office package parts."""
    from .weekly_workbooks import materialize_weekly_workbooks as project

    return project(snapshot, run_root, manifest)
