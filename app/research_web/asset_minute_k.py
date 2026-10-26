"""Closed minute-K snapshots, independent of daily history and intraday lines."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .asset_history import HISTORY_VERSION, adjust_rows, factor_map
from .asset_intraday import MINUTE_FIELDS, number
from .datahub.adjustment_contract import DEFINITION_SHA256
from .datahub.contracts import BusinessQuery
from .datahub.providers import Result, cn_stock_identity
from .store import StoreError

log = get_logger(__name__)
# Even if every calendar day traded, these native single batches remain <5000
# records, including a separate auction bar. No truncation or quota splitting.
CYCLE_DAYS = {"1m": 14, "5m": 60, "15m": 180, "30m": 365, "60m": 730, "120m": 1095}
VERSION = "asset-minute-k-v1"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def normalize_bars(rows, asset, cycle, start, end):
    if cycle not in CYCLE_DAYS or len(rows) > 5000:
        raise ValueError("minute_range_invalid")
    period = int(cycle[:-1])
    groups = {}
    for row in rows:
        stamp = datetime.strptime(str(row.get("时间", "")), "%Y-%m-%d %H:%M:%S")
        day = stamp.date().isoformat()
        if not start <= day <= end:
            raise ValueError("minute_out_of_range")
        minute = stamp.hour * 60 + stamp.minute
        if minute != 565:
            session_start = 570 if 570 < minute <= 690 else 780 if 780 < minute <= 900 else None
            if session_start is None or (minute - session_start) % period:
                raise ValueError("minute_interval_boundary_invalid")
        groups.setdefault(day, []).append(row)
    result = []
    expected = cn_stock_identity(asset)
    for day in sorted(groups):
        volume = amount = 0.0
        seen = set()
        for raw in sorted(groups[day], key=lambda r: r["时间"]):
            if str(raw.get("代码", "")).upper() not in {expected, expected[-2:] + expected[:6]}:
                raise ValueError("minute_identity_mismatch")
            stamp = datetime.strptime(raw["时间"], "%Y-%m-%d %H:%M:%S")
            if stamp.second or stamp in seen:
                raise ValueError("minute_duplicate_or_invalid_time")
            seen.add(stamp)
            o, h, low, close, v, a, previous = (number(raw.get(k)) for k in MINUTE_FIELDS[:7])
            cv, ca = number(raw.get("sectional_vol")), number(raw.get("sectional_amount"))
            if min(o, h, low, close, previous) <= 0 or min(v, a, cv, ca) < 0:
                raise ValueError("minute_value_invalid")
            if low > min(o, close) or h < max(o, close) or low > h or (not v and a):
                raise ValueError("minute_ohlcv_invalid")
            volume += v
            amount += a
            flags = []
            if abs(cv - volume) > 0.001 or abs(ca - amount) > 0.01:
                flags.append("source_cumulative_mismatch")
            vwap = a / v if v else None
            if vwap is not None and not low - 0.02 <= vwap <= h + 0.02:
                flags.append("source_vwap_outside_ohlc")
            # Verified dictionary establishes raw units; contradictory auxiliary
            # fields never establish a computed mean. Preserve raw OHLCV/evidence.
            result.append(
                {
                    "asset": asset,
                    "date": stamp.isoformat() + "+08:00",
                    "open": o,
                    "high": h,
                    "low": low,
                    "close": close,
                    "volume": v,
                    "amount": a,
                    "vwap": None if flags else vwap,
                    "quality_flags": flags,
                    "turnover_rate_pct": None,
                }
            )
    return result


def project_prices(rows, factors, mode, anchor, listing):
    daily_keys = [{**r, "date": r["date"][:10]} for r in rows]
    adjusted = adjust_rows(daily_keys, factors, mode, anchor, listing)
    output = []
    for raw, row in zip(rows, adjusted, strict=True):
        ratio = row["close"] / raw["close"]
        output.append(
            {
                **row,
                "date": raw["date"],
                "vwap": raw["vwap"] * ratio if raw.get("vwap") is not None else None,
            }
        )
    return output


def rebase_chip_reference(history, frozen_rows, fresh, mode, anchor, listing):
    old = history.get("factors", {})
    if mode != "none" and (
        not old or any(day in fresh and fresh[day] != value for day, value in old.items())
    ):
        raise ValueError("minute_factor_bridge_conflict")
    combined = {**old, **fresh}
    raw_rows = history.get("raw_rows", [])
    source = {r["date"]: r for r in frozen_rows}
    projected = adjust_rows(raw_rows, combined, mode, anchor, listing)
    output = []
    for raw, row in zip(raw_rows, projected, strict=True):
        original = source.get(row["date"])
        if not original:
            raise ValueError("minute_daily_reference_invalid")
        v, a = raw.get("volume"), raw.get("amount")
        vwap = a / v * row["close"] / raw["close"] if v and a is not None else None
        output.append({**row, "vwap": vwap, "turnover_rate_pct": original.get("turnover_rate_pct")})
    return output


class MinuteK:
    """Account-local coalescence and frozen derivation, without old-block writes."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.cache = {}
        self.pending = {}
        self.closed = False

    @property
    def hub(self):
        return self.workspace.service.datahub

    def _authorize_manifest(self, sid, manifest):
        self.hub._authorize_query(
            sid,
            BusinessQuery.model_validate(manifest["query"]),
            cached=True,
            provider=manifest["provider"],
            authorization_fingerprint=manifest.get("authorization_fingerprint"),
        )

    async def load(self, oid, cycle, adjustment, refresh=False):
        if cycle not in CYCLE_DAYS or adjustment not in {"none", "qfq", "hfq"}:
            raise ValueError("minute_parameters_invalid")
        observation = self.workspace.observation(oid)
        sid = observation["session_id"]
        self.workspace.store.session(sid)
        if self.closed or self.workspace.closed:
            raise ValueError("minute_closed")
        if observation["asset_type"] != "stock":
            raise ValueError("minute_stock_required")
        cn_stock_identity(observation["asset"])
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        fingerprint = self.hub.source_configuration_digest("tinysoft")
        daily_id = (
            observation.get("blocks", {}).get("history", {}).get("dataset", {}).get("dataset_id")
        )
        key = (oid, cycle, adjustment, today, fingerprint, daily_id)
        self.cache = {k: v for k, v in self.cache.items() if time.monotonic() - v[0] < 60}
        if not refresh and key in self.cache:
            _, result, manifests = self.cache[key]
            for manifest in manifests:
                self._authorize_manifest(sid, manifest)
            return copy.deepcopy(result)
        if key not in self.pending:
            task = asyncio.create_task(
                self._bounded(observation, cycle, adjustment, fingerprint, daily_id, key)
            )
            task_key = "minute-k:" + uuid4().hex
            self.pending[key] = task
            self.workspace.tasks[task_key] = task

            def completed(done):
                self.pending.pop(key, None)
                self.workspace.tasks.pop(task_key, None)
                if not done.cancelled():
                    done.exception()

            task.add_done_callback(completed)
        return copy.deepcopy(await asyncio.shield(self.pending[key]))

    async def _bounded(self, *args):
        try:
            async with asyncio.timeout(16):
                return await self._load(*args)
        except TimeoutError as exc:
            log.warning("asset_minute_k_deadline")
            raise StoreError(
                "分钟K读取超时；真实供应商任务继续按原规则排空。", "minute_deadline", 504
            ) from exc

    async def _load(self, observation, cycle, mode, fingerprint, daily_id, cache_key):
        sid, asset = observation["session_id"], observation["asset"]
        uid = uuid4().hex
        inputs = []
        authorized = []

        async def query(capability, parameters):
            q = BusinessQuery(
                capability=capability,
                source="tinysoft",
                parameters=parameters,
                purpose="display",
                refresh=True,
            )
            m = await self.hub.query(sid, f"minute:{uid}:{len(inputs)}", q)
            if (
                m.get("status") not in {"complete", "empty"}
                or m.get("pagination_complete") is not True
            ):
                raise ValueError("minute_source_incomplete")
            rows = json.loads(self.hub.snapshots.read(sid, m["dataset_id"], "rows.json"))
            inputs.append(
                {
                    "dataset_id": m["dataset_id"],
                    "manifest_sha256": m["manifest_sha256"],
                    "rows": rows,
                    "query": q.model_dump(mode="json"),
                }
            )
            authorized.append(m)
            return rows, m

        try:
            end = datetime.now(ZoneInfo("Asia/Shanghai")).date()
            market, _ = await query(
                "market_bars",
                {
                    "asset": "000001.SH",
                    "asset_type": "index",
                    "frequency": "daily",
                    "adjustment": "none",
                    "start_date": (end - timedelta(days=14)).isoformat(),
                    "end_date": end.isoformat(),
                },
            )
            days = [str(r.get("时间", ""))[:10] for r in market]
            if not days or any(datetime.strptime(day, "%Y-%m-%d").date() > end for day in days):
                raise ValueError("minute_market_calendar_invalid")
            market_day = max(days)
            end = datetime.strptime(market_day, "%Y-%m-%d").date()
            start = (end - timedelta(days=CYCLE_DAYS[cycle] - 1)).isoformat()
            native, minute_manifest = await query(
                "market_bars",
                {
                    "asset": asset,
                    "asset_type": "stock",
                    "frequency": cycle,
                    "adjustment": "none",
                    "start_date": start,
                    "end_date": market_day,
                },
            )
            if (
                minute_manifest.get("provider_metadata", {})
                .get("intraday_field_dictionary", {})
                .get("applied")
                is not True
            ):
                raise ValueError("minute_units_unverified")
            raw = normalize_bars(native, asset, cycle, start, market_day)
            anchor = raw[-1]["date"][:10] if raw else None
            frozen = history = daily_manifest = None
            limitations = []
            flagged = sum(bool(row["quality_flags"]) for row in raw)
            if flagged:
                limitations.append(
                    f"来源有{flagged}根柱的累计量额或均价与OHLC不一致；保留原始OHLCV，相关计算均价不展示。"
                )
            if daily_id:
                try:
                    m = self.hub.detail(sid, daily_id)
                    self._authorize_manifest(sid, m)
                    h = m.get("asset_history", {})
                    c = h.get("chip_inputs", {})
                    if (
                        m.get("provider") == "tinysoft"
                        and h.get("asset") == asset
                        and h.get("canonical_version") == HISTORY_VERSION
                        and c.get("status") == "complete"
                        and c.get("turnover_unit") == "percent"
                        and c.get("vwap_unit") == "元/股"
                        and isinstance(h.get("raw_rows"), list)
                    ):
                        history, daily_manifest = h, m
                        frozen = json.loads(self.hub.snapshots.read(sid, daily_id, "rows.json"))
                except StoreError as exc:
                    log.info("minute_daily_reference_denied", code=exc.code)
            factors, listing = {}, None
            if raw and mode != "none":
                listing_rows, _ = await query(
                    "factor_macro", {"series": "listing_date", "assets": [asset]}
                )
                if len(listing_rows) != 1 or listing_rows[0].get("asset") != asset:
                    raise ValueError("minute_listing_unverified")
                listing = listing_rows[0]["listing_date"]
                dates = {r["date"][:10] for r in raw}
                if mode == "hfq":
                    dates.add(listing)
                if history and history.get("anchor_date"):
                    dates.add(history["anchor_date"])
                ordered = sorted(dates)
                for index in range(0, len(ordered), 500):
                    batch = ordered[index : index + 500]
                    rows, factor_manifest = await query(
                        "factor_macro",
                        {"series": "adjustment_factors", "assets": [asset], "dates": batch},
                    )
                    if (
                        factor_manifest.get("provider_metadata", {})
                        .get("adjustment_contract", {})
                        .get("definition_sha256")
                        != DEFINITION_SHA256
                    ):
                        raise ValueError("minute_factor_contract_unverified")
                    factors.update(factor_map(rows, asset, batch, listing))
            adjusted = project_prices(raw, factors, mode, anchor, listing)
            reference = None
            if history and frozen:
                try:
                    rows = rebase_chip_reference(history, frozen, factors, mode, anchor, listing)
                    reference = {
                        "rows": rows,
                        "source_dataset_id": daily_id,
                        "asset_history": {
                            **{
                                k: v
                                for k, v in history.items()
                                if k
                                not in {"raw_rows", "factors", "inputs", "configuration_digest"}
                            },
                            "canonical_version": "minute-chip-reference-v1",
                            "factor_version": digest(
                                [history.get("factor_version"), factors, mode, anchor]
                            ),
                            "adjustment": mode,
                            "anchor_date": anchor if mode == "qfq" else listing,
                            "factor_snapshot_sha256": digest(
                                {**history.get("factors", {}), **factors}
                            ),
                            "bridge_source_dataset_id": daily_id,
                        },
                        "cutoff_policy": "strictly_before_selected_minute_date",
                    }
                    authorized.append(daily_manifest)
                except (ValueError, StoreError):
                    limitations.append("日线因子桥接未通过，分钟筹码暂不绘制；原日线图不受影响。")
            if reference is None:
                limitations.append("未取得可核验的同口径日线筹码底稿。")
            self.workspace.store.session(sid)
            if self.hub.source_configuration_digest("tinysoft") != fingerprint:
                raise ValueError("minute_source_configuration_changed")
            metadata = {
                "canonical_version": VERSION,
                "asset": asset,
                "version": VERSION,
                "cycle": cycle,
                "adjustment": mode,
                "anchor_date": anchor if mode == "qfq" else listing,
                "factor_definition_sha256": DEFINITION_SHA256 if mode != "none" else None,
                "factor_snapshot_sha256": digest(factors) if mode != "none" else None,
                "market_as_of": market_day,
                "requested_range": {"start_date": start, "end_date": market_day},
                "raw_rows": raw,
                "factors": factors,
                "inputs": inputs,
                "daily_reference": reference,
                "bar_time_basis": "vendor_interval_end_label_may_be_forming",
                "price_currency_verified": False,
            }
            result = Result(
                rows=adjusted,
                raw=[json.dumps(metadata, ensure_ascii=False).encode()],
                status="complete" if adjusted else "empty",
                provider_total=len(adjusted),
                pagination_complete=True,
                provider_id="tinysoft",
                fields={
                    "volume": {"unit": "share", "currency": None},
                    "amount": {"unit": "元", "currency": None},
                },
                metadata={"minute_k": {"version": VERSION, "cycle": cycle, "adjustment": mode}},
                limitations=limitations,
            )
            final_query = BusinessQuery(
                capability="market_bars",
                source="tinysoft",
                purpose="display",
                parameters={
                    "asset": asset,
                    "asset_type": "stock",
                    "frequency": cycle,
                    "adjustment": mode,
                    "start_date": start,
                    "end_date": market_day,
                },
            )
            self.hub._authorize_query(sid, final_query)
            manifest = self.hub.snapshots.publish(
                sid,
                final_query,
                result,
                request_query=final_query,
                authorization_fingerprint=fingerprint,
                asset_history=metadata,
            )
            authorized.append(manifest)
            response = {
                "status": result.status,
                "asset": asset,
                "cycle": cycle,
                "adjustment": mode,
                "market_as_of": market_day,
                "anchor_date": metadata["anchor_date"],
                "rows": adjusted,
                "daily_reference": reference,
                "fields": result.fields,
                "limitations": limitations,
                "dataset_id": manifest["dataset_id"],
                "session_id": sid,
                "version": digest(metadata),
                "requested_range": metadata["requested_range"],
                "bar_time_basis": metadata["bar_time_basis"],
            }
            while len(self.cache) >= 64:
                self.cache.pop(next(iter(self.cache)))
            self.cache[cache_key] = (time.monotonic(), response, authorized)
            log.info(
                "asset_minute_k_loaded",
                cycle=cycle,
                adjustment=mode,
                rows=len(adjusted),
                market_as_of=market_day,
            )
            return response
        except Exception as exc:
            log.warning("asset_minute_k_failed", cycle=cycle, error_type=type(exc).__name__)
            raise

    async def close(self):
        self.closed = True
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.cache.clear()
