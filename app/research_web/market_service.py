"""User-owned, sessionless market snapshots and shared refresh lifecycle."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import math
import os
import re
import time
from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger

log = get_logger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
SECTIONS = frozenset({"quotes", "indices", "industry", "concept", "flows", "calendar", "members"})
DEFAULT_SECTIONS = ("quotes", "indices", "industry", "concept", "calendar")
KINDS = frozenset({"industry", "concept"})
PERIODS = frozenset({"today", "5d", "10d"})
EXCHANGES = frozenset({"all", "SH", "SZ", "BJ"})
BOARDS = frozenset({"all", "main", "star", "chinext", "beijing"})
QUOTE_FIELDS = (
    "asset",
    "code",
    "name",
    "exchange",
    "board",
    "price",
    "change",
    "change_pct",
    "volume",
    "amount",
    "amplitude_pct",
    "turnover_rate_pct",
    "volume_ratio",
    "pe_dynamic",
    "pb",
    "total_market_cap",
    "float_market_cap",
    "change_5m_pct",
    "change_60d_pct",
    "change_ytd_pct",
    "as_of",
    "trade_status",
    "price_basis",
)
MAX_REQUESTS = 128
MAX_KEYS = 64
MAX_MEMBERS = 48
MAX_ROWS = 20000
MAX_RECORD_BYTES = 16 * 1024 * 1024
MAX_CACHE_BYTES = 64 * 1024 * 1024
COLLECTION_TIMEOUT = 90


class MarketError(Exception):
    """A safe product error without upstream payloads, paths or credentials."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=SHANGHAI)
    except ValueError:
        return None


def _safe_error(exc: Exception) -> dict:
    code = getattr(exc, "code", "market_fetch_failed")
    if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code):
        code = "market_fetch_failed"
    messages = {
        "market_partial": "本次数据覆盖不完整，保留上一份完整快照。",
        "market_timeout": "市场数据采集超时，请稍后重试。",
        "market_cache_failed": "市场缓存保存失败，请稍后重试。",
        "market_closed": "市场服务已关闭。",
    }
    return {"code": code, "message": messages.get(code, "市场数据暂不可用，请稍后重试。")}


class MarketService:
    """Cache public market reads inside one authenticated user's data root.

    GET methods never collect data. Each POST owns a reader subscription; cancelling
    one browser must not abort a collector still owned by another browser.
    """

    def __init__(
        self,
        root: Path,
        provider=None,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
    ):
        self.root = Path(root) / "market-cache"
        self.provider = provider
        self.clock = clock
        self.now = now or (lambda: datetime.now(UTC))
        self._snapshots: OrderedDict[str, dict] = OrderedDict()
        self._previous: dict[str, dict] = {}
        self._partials: OrderedDict[str, dict] = OrderedDict()
        self._attempts: dict[str, dict] = {}
        self._requests: OrderedDict[str, dict] = OrderedDict()
        self._idempotency: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self._collectors: dict[str, dict] = {}
        self._last_start: dict[str, float] = {}
        self._slots = asyncio.Semaphore(3)
        self._closed = False
        self._load()

    @staticmethod
    def _interval(key: str) -> int:
        return 3600 if key == "calendar" else 30 if key in {"quotes", "indices"} else 60

    @staticmethod
    def _key(section: str, board_id: str | None, kind: str, period: str) -> str:
        if section == "flows":
            return f"flows:{kind}:{period}"
        if section == "members":
            return f"members:{board_id}"
        return section

    def _path(self, key: str) -> Path:
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def _directory(self) -> None:
        if self.root.is_symlink():
            raise MarketError("market_cache_failed", "市场缓存目录不可用。", 503)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.root.is_dir() or self.root.is_symlink():
            raise MarketError("market_cache_failed", "市场缓存目录不可用。", 503)

    def _load(self) -> None:
        if not self.root.exists():
            return
        if self.root.is_symlink() or not self.root.is_dir():
            log.warning("market_cache_load_failed", code="cache_directory_invalid")
            return
        total = 0
        try:
            paths = sorted(self.root.glob("*.json"))[:MAX_KEYS]
        except OSError:
            log.warning("market_cache_load_failed", code="cache_directory_unreadable")
            return
        for path in paths:
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                size = path.stat().st_size
                if size > MAX_RECORD_BYTES or total + size > MAX_CACHE_BYTES:
                    log.warning("market_cache_load_failed", code="cache_size_limit")
                    continue
                with path.open("rb") as source:
                    raw = source.read(MAX_RECORD_BYTES + 1)
                if len(raw) > MAX_RECORD_BYTES:
                    continue
                record = json.loads(raw)
                if not isinstance(record, dict) or record.get("schema_version") != 1:
                    continue
                key = record.get("key")
                if not isinstance(key, str) or path != self._path(key) or not self._valid_key(key):
                    continue
                current = record.get("current")
                previous = record.get("previous")
                if self._complete_snapshot(current):
                    self._snapshots[key] = current
                    if self._complete_snapshot(previous):
                        self._previous[key] = previous
                    if isinstance(record.get("attempt"), dict):
                        self._attempts[key] = record["attempt"]
                elif self._complete_snapshot(previous):
                    self._snapshots[key] = previous
                    self._attempts[key] = {
                        "status": "recovered",
                        "retrieved_at": self.now().isoformat(),
                        "error": {
                            "code": "market_cache_recovered",
                            "message": "当前缓存损坏，已恢复上一份完整快照，请刷新行情。",
                        },
                    }
                    log.warning("market_cache_recovered", section=key.split(":")[0])
                else:
                    continue
                total += size
            except (OSError, ValueError, TypeError, RecursionError):
                log.warning("market_cache_load_failed", code="cache_invalid")

    @staticmethod
    def _valid_key(key: str) -> bool:
        return key in SECTIONS - {"flows", "members"} or bool(
            re.fullmatch(r"flows:(industry|concept):(today|5d|10d)|members:BK[0-9]{4,6}", key)
        )

    @staticmethod
    def _valid_snapshot(value: object) -> bool:
        return (
            isinstance(value, dict)
            and isinstance(value.get("snapshot_id"), str)
            and bool(re.fullmatch(r"[a-f0-9-]{36}", value["snapshot_id"]))
            and isinstance(value.get("rows"), list)
            and len(value["rows"]) <= MAX_ROWS
            and all(isinstance(row, dict) for row in value["rows"])
            and isinstance(value.get("summary", {}), dict)
        )

    @classmethod
    def _complete_snapshot(cls, value: object) -> bool:
        if not isinstance(value, dict) or not cls._valid_snapshot(value):
            return False
        try:
            json.dumps(value, allow_nan=False)
        except (ValueError, TypeError, RecursionError):
            return False
        return value.get("complete") is True and value.get("pagination_complete") is True

    def _record(self, key: str) -> dict:
        return {
            "schema_version": 1,
            "key": key,
            "current": self._snapshots.get(key),
            "previous": self._previous.get(key),
            "attempt": self._attempts.get(key),
        }

    def _persist(self, key: str) -> None:
        self._directory()
        raw = json.dumps(self._record(key), ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > MAX_RECORD_BYTES:
            raise MarketError("market_cache_failed", "市场快照超过缓存容量。", 503)
        sizes = {
            item: len(
                json.dumps(self._record(item), ensure_ascii=False, allow_nan=False).encode("utf-8")
            )
            for item in self._snapshots
        }
        member_keys = [item for item in self._snapshots if item.startswith("members:")]
        victims = [item for item in member_keys if item != key]
        while (
            len(self._snapshots) > MAX_KEYS
            or len(member_keys) > MAX_MEMBERS
            or sum(sizes.values()) > MAX_CACHE_BYTES
        ) and victims:
            victim = victims.pop(0)
            self._snapshots.pop(victim, None)
            self._previous.pop(victim, None)
            self._attempts.pop(victim, None)
            sizes.pop(victim, None)
            member_keys.remove(victim)
            path = self._path(victim)
            if path.is_file() and not path.is_symlink():
                path.unlink()
        if sum(sizes.values()) > MAX_CACHE_BYTES or len(self._snapshots) > MAX_KEYS:
            raise MarketError("market_cache_failed", "市场缓存容量已满。", 503)
        temporary = self.root / ("." + uuid4().hex + ".tmp")
        try:
            descriptor = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(descriptor, "wb") as target:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self._path(key))
        finally:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()

    def _project(self, key: str, snapshot: dict | None = None) -> dict:
        snapshot = snapshot or self._snapshots.get(key) or self._partials.get(key)
        attempt = self._attempts.get(key, {})
        if snapshot is None:
            return {
                "snapshot_id": None,
                "status": attempt.get("status", "unavailable"),
                "rows": [],
                "summary": {},
                "row_count": 0,
                "complete": False,
                "stale": False,
                "error": deepcopy(attempt.get("error")),
            }
        result = deepcopy(
            {
                name: value
                for name, value in snapshot.items()
                if name != "raw_members" and (key != "quotes" or name != "rows")
            }
        )
        retrieved = _iso(snapshot.get("retrieved_at"))
        stale = (
            retrieved is None or (self.now() - retrieved).total_seconds() > self._interval(key) * 2
        )
        if key in {"quotes", "indices", "industry", "concept"} or key.startswith("flows:"):
            market = self.market_state()
            as_of = _iso(snapshot.get("as_of"))
            if (
                market["state"] not in {"unknown", "preopen"}
                and market["trade_date"]
                and as_of
                and as_of.astimezone(SHANGHAI).date().isoformat() < market["trade_date"]
            ):
                stale = True
        error = attempt.get("error")
        result.update(
            row_count=len(snapshot.get("rows", [])),
            status=(
                "stale"
                if (error or stale) and snapshot.get("complete")
                else "ready" if snapshot.get("complete") else "partial"
            ),
            stale=stale or bool(error),
            error=deepcopy(error),
        )
        if attempt:
            result["last_attempt"] = deepcopy(attempt)
        return result

    def overview(self) -> dict:
        keys = list(
            dict.fromkeys([*DEFAULT_SECTIONS, *self._snapshots, *self._partials, *self._attempts])
        )
        return {
            "sections": {key: self._project(key) for key in keys},
            "market_state": self.market_state(),
            "inflight": [
                {"section": key, "readers": len(value["readers"])}
                for key, value in self._collectors.items()
                if not value["task"].done()
            ],
        }

    def market_state(self) -> dict:
        now = self.now().astimezone(SHANGHAI)
        today = now.date().isoformat()
        quote_date = _iso((self._snapshots.get("quotes") or {}).get("as_of"))
        result = {
            "state": "unknown",
            "trade_date": None,
            "quote_trade_date": (
                quote_date.astimezone(SHANGHAI).date().isoformat() if quote_date else None
            ),
            "timezone": "Asia/Shanghai",
            "auto_refresh": False,
        }
        calendar = self._snapshots.get("calendar")
        if not calendar:
            return result
        summary = calendar.get("summary", {})
        raw_dates = summary.get("trading_dates", [])
        if not raw_dates:
            raw_dates = [row.get("trade_date", row.get("date")) for row in calendar.get("rows", [])]
        dates = sorted(
            {
                item
                for item in raw_dates
                if isinstance(item, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item)
            }
        )
        if not dates:
            return result
        valid_until = summary.get("valid_until") or dates[-1]
        if not isinstance(valid_until, str) or today > valid_until or today < dates[0]:
            return result
        result["trade_date"] = max((item for item in dates if item <= today), default=None)
        if today not in dates:
            result["state"] = "non_trading"
            return result
        minutes = now.hour * 60 + now.minute
        if minutes < 9 * 60 + 15:
            state = "preopen"
        elif minutes < 9 * 60 + 30:
            state = "auction"
        elif minutes < 11 * 60 + 30:
            state = "open"
        elif minutes < 13 * 60:
            state = "lunch"
        elif minutes < 15 * 60:
            state = "open"
        else:
            state = "closed"
        result.update(state=state, auto_refresh=state in {"open", "auction"})
        return result

    def _validate_board(self, board_id: str | None) -> str:
        if not isinstance(board_id, str) or not re.fullmatch(r"BK[0-9]{4,6}", board_id):
            raise MarketError("market_board_invalid", "请选择有效板块。")
        catalogs = [
            key
            for key in ("industry", "concept")
            if any(
                row.get("board_id") == board_id
                for row in (self._snapshots.get(key) or {}).get("rows", [])
            )
        ]
        if len(catalogs) != 1:
            raise MarketError("market_board_unknown", "请先刷新板块目录，再选择板块。", 409)
        return catalogs[0]

    def _trim_requests(self) -> None:
        for key in list(self._requests):
            if len(self._requests) < MAX_REQUESTS:
                break
            if self._requests[key]["status"] not in {"pending", "running"}:
                del self._requests[key]
        if len(self._requests) >= MAX_REQUESTS:
            raise MarketError("market_busy", "市场刷新任务较多，请稍后重试。", 429)

    async def refresh(
        self,
        sections: list[str] | tuple[str, ...] = DEFAULT_SECTIONS,
        *,
        board_id: str | None = None,
        kind: str = "industry",
        period: str = "today",
        idempotency_key: str | None = None,
    ) -> dict:
        if self._closed:
            raise MarketError("market_closed", "市场服务已关闭。", 503)
        if (
            not isinstance(sections, (list, tuple))
            or not 1 <= len(sections) <= 7
            or any(item not in SECTIONS for item in sections)
        ):
            raise MarketError("market_sections_invalid", "请选择有效市场区块。")
        if kind not in KINDS or period not in PERIODS:
            raise MarketError("market_parameters_invalid", "市场查询参数无效。")
        if "members" in sections:
            member_kind = self._validate_board(board_id)
        elif board_id is not None:
            raise MarketError("market_parameters_invalid", "仅板块成分查询接受板块代码。")
        if idempotency_key is not None and not re.fullmatch(
            r"[A-Za-z0-9._:-]{8,128}", idempotency_key
        ):
            raise MarketError("market_idempotency_invalid", "刷新标识无效。")
        keys = {self._key(section, board_id, kind, period): section for section in sections}
        fingerprint = json.dumps([sorted(keys), kind, period, board_id])
        if idempotency_key is not None and idempotency_key in self._idempotency:
            old_fingerprint, old_id = self._idempotency[idempotency_key]
            if old_fingerprint != fingerprint:
                raise MarketError("market_idempotency_conflict", "刷新标识已用于其他查询。", 409)
            if old_id in self._requests:
                return self.request(old_id)
        await self._await_draining(keys)
        if self._closed:
            raise MarketError("market_closed", "市场服务已关闭。", 503)
        if "members" in sections:
            member_kind = self._validate_board(board_id)
        if idempotency_key is not None and idempotency_key in self._idempotency:
            old_fingerprint, old_id = self._idempotency[idempotency_key]
            if old_fingerprint != fingerprint:
                raise MarketError("market_idempotency_conflict", "刷新标识已用于其他查询。", 409)
            if old_id in self._requests:
                return self.request(old_id)
        self._trim_requests()
        request_id = str(uuid4())
        job = {
            "request_id": request_id,
            "status": "running",
            "sections": {},
            "errors": {},
            "pending": set(keys),
            "created_at": self.now().isoformat(),
        }
        self._requests[request_id] = job
        for key, section in keys.items():
            collector = self._collectors.get(key)
            if collector is not None and not collector["task"].done():
                collector["readers"].add(request_id)
                continue
            last = self._last_start.get(key)
            if last is not None and self.clock() - last < self._interval(key):
                self._finish_reader(job, key)
                continue
            if len(self._collectors) >= 16:
                job["errors"][key] = {
                    "code": "market_busy",
                    "message": "市场刷新任务较多，请稍后重试。",
                }
                self._finish_reader(job, key)
                continue
            self._last_start[key] = self.clock()
            collector = {"readers": {request_id}, "task": None, "draining": False}
            self._collectors[key] = collector
            collector["task"] = asyncio.create_task(
                self._collect(
                    key,
                    section,
                    collector=collector,
                    board_id=board_id if section == "members" else None,
                    kind=member_kind if section == "members" else kind,
                    period=period,
                ),
                name=f"market-{section}",
            )
        if idempotency_key:
            self._idempotency[idempotency_key] = (fingerprint, request_id)
            while len(self._idempotency) > MAX_REQUESTS:
                self._idempotency.popitem(last=False)
        log.info("market_refresh_requested", sections=len(keys))
        return self.request(request_id)

    async def _await_draining(self, keys: dict[str, str]) -> None:
        """A cancelled collector cannot acquire new readers while unwinding HTTP."""
        try:
            async with asyncio.timeout(COLLECTION_TIMEOUT):
                while True:
                    draining = {
                        key: collector
                        for key in keys
                        if (collector := self._collectors.get(key)) is not None
                        and (
                            collector.get("draining")
                            or collector["task"].cancelling()
                            or collector["task"].done()
                        )
                    }
                    if not draining:
                        return
                    await asyncio.gather(
                        *(asyncio.shield(value["task"]) for value in draining.values()),
                        return_exceptions=True,
                    )
                    for key, collector in draining.items():
                        if self._collectors.get(key) is collector and collector["task"].done():
                            self._collectors.pop(key)
        except TimeoutError as exc:
            raise MarketError("market_busy", "上一轮市场查询正在释放，请稍后重试。", 503) from exc

    def _finish_reader(self, job: dict, key: str) -> None:
        job["pending"].discard(key)
        job["sections"][key] = self._project(key)
        job["sections"][key].pop("rows", None)
        error = self._attempts.get(key, {}).get("error")
        if error:
            job["errors"][key] = deepcopy(error)
        if not job["pending"] and job["status"] != "cancelled":
            job["status"] = "failed" if job["errors"] else "completed"

    async def _collect(self, key: str, section: str, *, collector: dict, **parameters) -> None:
        try:
            async with asyncio.timeout(COLLECTION_TIMEOUT):
                async with self._slots:
                    if self.provider is None:
                        from .datahub.providers_market import MarketProvider

                        self.provider = MarketProvider()
                    payload = await self.provider.fetch(section, **parameters)
            raw = json.dumps(payload, allow_nan=False)
            if len(raw.encode()) > MAX_RECORD_BYTES:
                raise MarketError("market_response_limit", "市场数据超过容量限制。", 502)
            snapshot = deepcopy(payload)
            if section == "flows":
                current_flow = snapshot.get("summary", {}).get("market_flow")
                old_flow = self._snapshots.get(key, {}).get("summary", {}).get("market_flow")
                if (
                    isinstance(current_flow, dict)
                    and current_flow.get("complete") is False
                    and isinstance(old_flow, dict)
                    and old_flow.get("complete") is True
                ):
                    snapshot["summary"]["market_flow"] = {
                        **deepcopy(old_flow),
                        "stale": True,
                        "error": {
                            "code": "market_flow_unavailable",
                            "message": "本次沪深大盘资金流获取失败，保留上次快照。",
                        },
                        "last_attempt": current_flow.get("retrieved_at"),
                    }
                    if len(json.dumps(snapshot, allow_nan=False).encode()) > MAX_RECORD_BYTES:
                        raise MarketError("market_response_limit", "市场数据超过容量限制。", 502)
                    log.warning("market_flow_cache_preserved", section=key)
            snapshot["snapshot_id"] = str(uuid4())
            if not self._valid_snapshot(snapshot):
                raise MarketError("market_response_invalid", "市场数据结构无效。", 502)
            if section == "members":
                snapshot = self._resolve_members(snapshot)
            if snapshot.get("complete") is True and snapshot.get("pagination_complete") is True:
                previous_current = self._snapshots.get(key)
                previous_previous = self._previous.get(key)
                previous_attempt = self._attempts.get(key)
                if previous_current:
                    self._previous[key] = previous_current
                self._snapshots[key] = snapshot
                self._snapshots.move_to_end(key)
                self._attempts[key] = {
                    "status": "completed",
                    "retrieved_at": self.now().isoformat(),
                    "error": None,
                }
                try:
                    self._persist(key)
                except (OSError, ValueError, TypeError, MarketError) as exc:
                    if previous_current is None:
                        self._snapshots.pop(key, None)
                    else:
                        self._snapshots[key] = previous_current
                    if previous_previous is None:
                        self._previous.pop(key, None)
                    else:
                        self._previous[key] = previous_previous
                    if previous_attempt is None:
                        self._attempts.pop(key, None)
                    else:
                        self._attempts[key] = previous_attempt
                    raise MarketError("market_cache_failed", "市场缓存保存失败。", 503) from exc
                self._partials.pop(key, None)
                log.info("market_refresh_completed", section=section, rows=len(snapshot["rows"]))
            else:
                snapshot["complete"] = False
                self._partials[key] = snapshot
                self._partials.move_to_end(key)
                while len(self._partials) > MAX_KEYS:
                    self._partials.popitem(last=False)
                raise MarketError("market_partial", "本次数据覆盖不完整。", 502)
        except asyncio.CancelledError:
            log.info("market_refresh_cancelled", section=section)
            raise
        except Exception as exc:  # noqa: BLE001 - vendor, JSON and disk failures share safe errors.
            if isinstance(exc, TimeoutError):
                exc = MarketError("market_timeout", "市场数据采集超时。", 504)
            self._attempts[key] = {
                "status": "failed",
                "retrieved_at": self.now().isoformat(),
                "error": _safe_error(exc),
            }
            if key in self._snapshots:
                try:
                    self._persist(key)
                except (OSError, ValueError, TypeError, MarketError):
                    log.warning("market_cache_save_failed", section=section, code="cache_failed")
            log.warning("market_refresh_failed", section=section, code=_safe_error(exc)["code"])
        finally:
            if self._collectors.get(key) is collector:
                self._collectors.pop(key)
            for request_id in collector["readers"]:
                job = self._requests.get(request_id)
                if job and job["status"] != "cancelled":
                    self._finish_reader(job, key)
            self._trim_auxiliary()

    def _trim_auxiliary(self) -> None:
        """Bound failed attempts and partial payloads as well as good disk snapshots."""
        for mapping in (self._attempts, self._last_start):
            for key in list(mapping):
                if len(mapping) <= MAX_REQUESTS:
                    break
                if key not in self._snapshots and key not in self._collectors:
                    del mapping[key]
        sizes = {
            key: len(json.dumps(value, ensure_ascii=False).encode())
            for key, value in self._partials.items()
        }
        while self._partials and (
            len(self._partials) > MAX_KEYS or sum(sizes.values()) > MAX_CACHE_BYTES
        ):
            key, _ = self._partials.popitem(last=False)
            sizes.pop(key, None)

    def _resolve_members(self, snapshot: dict, quotes: dict | None = None) -> dict:
        quotes = quotes or self._snapshots.get("quotes")
        if not quotes:
            raise MarketError("market_quotes_required", "请先刷新完整沪深北行情。", 409)
        if "raw_members" not in snapshot:
            snapshot["raw_members"] = deepcopy(snapshot["rows"])
            snapshot["source_complete"] = snapshot.get("complete") is True
        identities: dict[str, list[dict]] = {}
        for row in quotes["rows"]:
            identities.setdefault(str(row.get("code", "")), []).append(row)
        matched, unmatched = {}, 0
        for row in snapshot["raw_members"]:
            asset = row.get("asset")
            code = str(row.get("code", row.get("f12", str(asset or "").split(".")[0])))
            candidates = identities.get(code, [])
            market = row.get("market", row.get("source_market", row.get("f13")))
            if market in {1, "1"}:
                candidates = [item for item in candidates if item.get("exchange") == "SH"]
            elif market in {0, "0"}:
                candidates = [item for item in candidates if item.get("exchange") in {"SZ", "BJ"}]
            if asset:
                candidates = [item for item in candidates if item.get("asset") == asset]
            if len(candidates) == 1:
                matched[candidates[0]["asset"]] = {"asset": candidates[0]["asset"]}
            else:
                unmatched += 1
        summary = snapshot.setdefault("summary", {})
        summary.update(
            matched=len(matched), unmatched=unmatched, quotes_snapshot_id=quotes["snapshot_id"]
        )
        snapshot["rows"] = list(matched.values())
        snapshot["complete"] = snapshot["source_complete"] and not unmatched
        if unmatched:
            limitation = "部分板块成分未能唯一关联至沪深北证券池。"
            if limitation not in snapshot.setdefault("limitations", []):
                snapshot["limitations"].append(limitation)
        return snapshot

    def request(self, request_id: str) -> dict:
        job = self._requests.get(request_id)
        if job is None:
            raise MarketError("market_request_missing", "刷新任务不存在或已过期。", 404)
        return deepcopy({key: value for key, value in job.items() if key != "pending"})

    async def cancel(self, request_id: str) -> dict:
        job = self._requests.get(request_id)
        if job is None:
            raise MarketError("market_request_missing", "刷新任务不存在或已过期。", 404)
        if job["status"] not in {"pending", "running"}:
            return self.request(request_id)
        job["status"] = "cancelled"
        tasks = []
        for key in list(job["pending"]):
            collector = self._collectors.get(key)
            if collector:
                collector["readers"].discard(request_id)
                if not collector["readers"]:
                    self._last_start.pop(key, None)
                    collector["draining"] = True
                    collector["task"].cancel()
                    tasks.append(collector["task"])
        job["pending"].clear()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            for key, collector in list(self._collectors.items()):
                if not collector["readers"] and collector["task"].done():
                    self._collectors.pop(key, None)
        return self.request(request_id)

    def _quote_snapshot(self, snapshot_id: str | None) -> dict:
        candidates = [
            self._snapshots.get("quotes"),
            self._previous.get("quotes"),
            self._partials.get("quotes"),
        ]
        for snapshot in candidates:
            if snapshot and (snapshot_id is None or snapshot.get("snapshot_id") == snapshot_id):
                return snapshot
        raise MarketError("market_snapshot_missing", "行情快照不存在或已过期，请刷新页面。", 409)

    def _filtered(
        self,
        *,
        exchange="all",
        board="all",
        search="",
        sort="change_pct",
        direction="desc",
        board_id=None,
        snapshot_id=None,
    ) -> tuple[list[dict], dict]:
        if (
            exchange not in EXCHANGES
            or board not in BOARDS
            or sort not in QUOTE_FIELDS
            or direction not in {"asc", "desc"}
        ):
            raise MarketError("market_parameters_invalid", "行情筛选或排序参数无效。")
        if not isinstance(search, str) or len(search) > 80:
            raise MarketError("market_parameters_invalid", "搜索内容过长。")
        snapshot = self._quote_snapshot(snapshot_id)
        rows = snapshot["rows"]
        membership = None
        if board_id is not None:
            self._validate_board(board_id)
            membership = self._snapshots.get(f"members:{board_id}") or self._partials.get(
                f"members:{board_id}"
            )
            if not membership:
                raise MarketError("market_members_required", "请先刷新该板块成分。", 409)
            if membership.get("summary", {}).get("quotes_snapshot_id") != snapshot["snapshot_id"]:
                raw_members = membership.get("raw_members")
                if (
                    not isinstance(raw_members, list)
                    or len(raw_members) > MAX_ROWS
                    or not all(isinstance(row, dict) for row in raw_members)
                ):
                    raise MarketError(
                        "market_members_snapshot_changed",
                        "行情快照已更新，请重新加载板块成分。",
                        409,
                    )
                membership = self._resolve_members(deepcopy(membership), quotes=snapshot)
            allowed = {row.get("asset") for row in membership["rows"]}
            rows = [row for row in rows if row.get("asset") in allowed]
        if exchange != "all":
            rows = [row for row in rows if row.get("exchange") == exchange]
        if board != "all":
            rows = [row for row in rows if row.get("board") == board]
        needle = search.strip().casefold()
        if needle:
            rows = [
                row
                for row in rows
                if needle
                in " ".join(
                    str(row.get(field, "")) for field in ("asset", "code", "name")
                ).casefold()
            ]
        valid: list[dict] = []
        missing: list[dict] = []
        numeric = sort not in {
            "asset",
            "code",
            "name",
            "exchange",
            "board",
            "as_of",
            "trade_status",
            "price_basis",
        }
        for row in rows:
            value = row.get(sort)
            (
                missing
                if value is None
                or (
                    numeric
                    and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    )
                )
                else valid
            ).append(row)
        valid.sort(
            key=lambda row: row[sort] if numeric else str(row.get(sort, "")).casefold(),
            reverse=direction == "desc",
        )
        meta = self._project("quotes", snapshot)
        meta.pop("summary", None)
        if membership:
            meta["membership"] = self._project(f"members:{board_id}", membership)
            meta["membership"].pop("rows", None)
        return valid + missing, meta

    def quotes(self, *, offset=0, limit=50, **filters) -> dict:
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or not 0 <= offset <= MAX_ROWS
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 200
        ):
            raise MarketError("market_parameters_invalid", "行情分页参数无效。")
        rows, meta = self._filtered(**filters)
        return {
            "items": deepcopy(rows[offset : offset + limit]),
            "total": len(rows),
            "snapshot_id": meta["snapshot_id"],
            "meta": meta,
        }

    def export_quotes(self, **filters) -> tuple[str, str]:
        rows, meta = self._filtered(**filters)
        if not meta.get("complete") or not meta.get("membership", {}).get("complete", True):
            raise MarketError(
                "market_partial_export", "当前行情覆盖不完整，暂不能导出全市场文件。", 409
            )
        target = io.StringIO(newline="")
        writer = csv.writer(target)
        writer.writerow(QUOTE_FIELDS)
        for row in rows:
            values = []
            for field in QUOTE_FIELDS:
                value = row.get(field)
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    value = "'" + value
                values.append("" if value is None else value)
            writer.writerow(values)
        return "\ufeff" + target.getvalue(), meta["snapshot_id"]

    async def close(self) -> None:
        self._closed = True
        for job in self._requests.values():
            if job["status"] in {"pending", "running"}:
                job["status"] = "cancelled"
                job["pending"].clear()
        tasks = [value["task"] for value in self._collectors.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._collectors.clear()
        if self.provider is not None:
            try:
                await self.provider.close()
            except Exception:  # noqa: BLE001 - shutdown must not expose vendor details.
                log.warning("market_provider_close_failed", code="close_failed")
        log.info("market_service_closed")
