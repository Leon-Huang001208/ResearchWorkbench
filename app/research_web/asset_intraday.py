"""Account-owned, bounded intraday display over immutable DataHub snapshots.

Minute timestamps are independent of the daily/weekly/monthly history pipeline.
No synthetic bars, implicit source fallback, or adjustment-factor mixing.
"""

from __future__ import annotations

import asyncio
import copy
import json
import math
import time
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .datahub.contracts import BusinessQuery
from .datahub.providers import cn_stock_identity

log = get_logger(__name__)
REQUEST_SECONDS = 16
MINUTE_FIELDS = (
    "open",
    "high",
    "low",
    "close",
    "vol",
    "amount",
    "sectional_yclose",
    "sectional_vol",
    "sectional_amount",
)


def number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("intraday_value_missing")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("intraday_value_invalid")
    return result


def normalize_minutes(rows: list[dict], asset: str, trading_date: str) -> dict:
    """Validate native per-minute volume and a fixed previous-day reference.

    Mean is offered only when independently cumulative fields and per-bar OHLC
    confirm the numeric price/amount/share scale for this exact returned sample.
    """
    expected = cn_stock_identity(asset)
    output, seen = [], set()
    volume = amount = 0.0
    previous = None
    for raw in sorted(rows, key=lambda row: str(row.get("时间", ""))):
        identity = str(raw.get("代码", "")).upper()
        if identity not in {expected, expected[-2:] + expected[:6]}:
            raise ValueError("intraday_identity_mismatch")
        stamp = datetime.strptime(str(raw.get("时间", "")), "%Y-%m-%d %H:%M:%S")
        clock = stamp.strftime("%H:%M:%S")
        if (
            stamp.second != 0
            or stamp.date().isoformat() != trading_date
            or not (
                clock == "09:25:00"
                or "09:30:00" <= clock <= "11:30:00"
                or "13:00:00" <= clock <= "15:00:00"
            )
        ):
            raise ValueError("intraday_time_invalid")
        if clock in seen:
            raise ValueError("intraday_duplicate_time")
        seen.add(clock)
        o, h, low, close, v, a, reference = (number(raw.get(k)) for k in MINUTE_FIELDS[:7])
        if min(o, h, low, close, reference) <= 0 or v < 0 or a < 0:
            raise ValueError("intraday_value_invalid")
        if low > min(o, close) or h < max(o, close) or low > h:
            raise ValueError("intraday_ohlc_invalid")
        if previous is not None and reference != previous:
            raise ValueError("intraday_daily_reference_conflict")
        previous = reference
        volume += v
        amount += a
        if (
            abs(number(raw.get("sectional_vol")) - volume) > 0.001
            or abs(number(raw.get("sectional_amount")) - amount) > 0.01
        ):
            raise ValueError("intraday_cumulative_conflict")
        if (v == 0 and a != 0) or (v > 0 and not low - 0.02 <= a / v <= h + 0.02):
            raise ValueError("intraday_price_scale_unverified")
        output.append(
            {
                "timestamp": stamp.isoformat() + "+08:00",
                "time": clock[:5],
                "open": o,
                "high": h,
                "low": low,
                "price": close,
                "volume_shares": v,
                "volume_lots": v / 100,
                "amount": a,
                "cumulative_volume": volume,
                "cumulative_amount": amount,
                "mean": amount / volume if volume else None,
            }
        )
    return {
        "asset": expected,
        "trading_date": trading_date,
        "previous_close": previous,
        "rows": output,
        "units": {"volume": "手", "amount": "元"},
        "adjustment": "none",
        "mean_basis": "sample_verified_cumulative_amount_per_share",
    }


class Intraday:
    """Per-workspace cache and coalescence; the workspace is account isolated."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.cache = {}
        self.pending = {}
        self.closed = False

    async def load(self, observation_id: str, *, refresh: bool = False):
        workspace = self.workspace
        observation = workspace.observation(observation_id)
        workspace.store.session(observation["session_id"])
        if self.closed or workspace.closed:
            raise ValueError("intraday_closed")
        if observation["asset_type"] != "stock":
            raise ValueError("intraday_stock_required")
        cn_stock_identity(observation["asset"])
        hub = workspace.service.datahub
        fingerprint = hub.source_configuration_digest("tinysoft")
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        self.cache = {
            key: value for key, value in self.cache.items() if time.monotonic() - value[0] < 60
        }
        key = (observation_id, fingerprint, today)
        cached = self.cache.get(key)
        authorized_day = cached[1]["trading_date"] if cached and not refresh else today
        hub._authorize_query(
            observation["session_id"],
            BusinessQuery(
                capability="market_bars",
                source="tinysoft",
                purpose="display",
                parameters={
                    "asset": observation["asset"],
                    "asset_type": "stock",
                    "frequency": "1m",
                    "adjustment": "none",
                    "start_date": authorized_day,
                    "end_date": authorized_day,
                },
            ),
        )
        if not refresh and cached and time.monotonic() - cached[0] < 60:
            return copy.deepcopy(cached[1])
        if key not in self.pending:
            task = asyncio.create_task(self._bounded_load(observation, key))
            self.pending[key] = task
            task_key = "intraday:" + uuid4().hex
            workspace.tasks[task_key] = task

            def completed(done):
                self.pending.pop(key, None)
                workspace.tasks.pop(task_key, None)
                if not done.cancelled():
                    done.exception()  # Observe errors even after an HTTP client disconnects.

            task.add_done_callback(completed)
        return copy.deepcopy(await asyncio.shield(self.pending[key]))

    async def _bounded_load(self, observation, key):
        from .store import StoreError

        try:
            async with asyncio.timeout(REQUEST_SECONDS):
                return await self._load(observation, key)
        except TimeoutError as exc:
            log.warning("asset_intraday_deadline")
            raise StoreError(
                "分时读取超时；供应商任务仍按原规则排空，请稍后重试。", "intraday_deadline", 504
            ) from exc

    async def _load(self, observation, key):
        hub = self.workspace.service.datahub
        sid = observation["session_id"]
        token = uuid4().hex
        end = datetime.now(ZoneInfo("Asia/Shanghai")).date()

        async def query(asset, frequency, start, stop):
            result = await hub.query(
                sid,
                f"intraday:{token}:{asset}:{frequency}",
                BusinessQuery(
                    capability="market_bars",
                    source="tinysoft",
                    purpose="display",
                    refresh=True,
                    parameters={
                        "asset": asset,
                        "asset_type": "index" if asset == "000001.SH" else "stock",
                        "frequency": frequency,
                        "adjustment": "none",
                        "start_date": start,
                        "end_date": stop,
                    },
                ),
            )
            if (
                result.get("status") not in {"complete", "empty"}
                or result.get("pagination_complete") is not True
            ):
                known = {
                    "intraday_field_definition_changed",
                    "vendor_permission_denied",
                    "vendor_auth_failed",
                    "vendor_rate_limited",
                    "vendor_unreachable",
                }
                failure = next(
                    (item for item in result.get("limitations", []) if item in known), None
                )
                if failure:
                    raise ValueError(
                        failure if failure.startswith("intraday_") else "intraday_" + failure
                    )
                raise ValueError("intraday_source_incomplete")
            rows = json.loads(hub.snapshots.read(sid, result["dataset_id"], "rows.json"))
            return rows, result

        try:
            market, market_manifest = await query(
                "000001.SH", "daily", (end - timedelta(days=14)).isoformat(), end.isoformat()
            )
            days = [str(row.get("时间", ""))[:10] for row in market]
            # Use actual returned market data, not a weekday or calendar prediction.
            day = max(value for value in days if len(value) == 10 and value <= end.isoformat())
            rows, manifest = await query(observation["asset"], "1m", day, day)
            evidence = manifest.get("provider_metadata", {}).get("intraday_field_dictionary", {})
            if evidence.get("applied") is not True:
                raise ValueError("intraday_units_unverified")
            result = normalize_minutes(rows, observation["asset"], day)
            if hub.source_configuration_digest("tinysoft") != key[1]:
                raise ValueError("intraday_source_configuration_changed")
            result.update(
                status="complete" if rows else "empty",
                dataset_id=manifest["dataset_id"],
                session_id=sid,
                market_dataset_id=market_manifest["dataset_id"],
                retrieved_at=manifest.get("retrieved_at"),
                source="tinysoft",
            )
            result["coverage"] = {
                "returned_points": len(rows),
                "synthetic_points": 0,
                "full_session_verified": False,
            }
            while len(self.cache) >= 64:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = (time.monotonic(), result)
            log.info("asset_intraday_loaded", rows=len(rows), trading_date=day)
            return result
        except Exception as exc:
            log.warning("asset_intraday_failed", error_type=type(exc).__name__)
            raise

    async def close(self):
        self.closed = True
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.cache.clear()
