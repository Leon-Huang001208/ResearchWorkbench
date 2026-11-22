"""Account-local, bounded portfolio imports with explicit preview confirmation.

No broker credentials or orders are accepted. Values use the actual cached quote
snapshot, and absent risk declarations never become an allocation instruction.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import secrets
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .market_service import MarketError

log = get_logger(__name__)
MAX_IMPORT_BYTES = 256 * 1024
MAX_HOLDINGS = 500
MAX_STORE_BYTES = 4 * 1024 * 1024
SHANGHAI = ZoneInfo("Asia/Shanghai")
RISK_FIELDS = {"risk_tolerance", "equity_min", "equity_max", "single_name_max", "sector_max"}


def finite(value, *, minimum=0, maximum=1e12):
    """Reject boolean, nonfinite, negative and unbounded financial numbers."""
    if isinstance(value, bool):
        raise TypeError("invalid_number")
    if not isinstance(value, (int, float, str)):
        raise TypeError("invalid_number")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError("invalid_number")
    return number


def atomic_json(directory: Path, name: str, value: object, limit: int) -> None:
    """Replace one private bounded document; never follow store symlinks."""
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > limit:
        raise OSError("document_limit")
    if directory.is_symlink() or directory.parent.is_symlink():
        raise OSError("unsafe_directory")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not directory.is_dir() or directory.is_symlink():
        raise OSError("unsafe_directory")
    path = directory / name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise OSError("unsafe_file")
    temporary = directory / ("." + uuid4().hex + ".tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as target:
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def read_json(directory: Path, name: str, limit: int, default):
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("unsafe_directory")
    path = directory / name
    if not path.exists() and not path.is_symlink():
        return default
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("unsafe_file")
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("document_limit")
    return json.loads(raw)


def _normalize(body: object, now: datetime, *, canonical: bool = False) -> dict:
    if not isinstance(body, dict) or set(body) - {
        "as_of",
        "currency",
        "cash",
        "source",
        "holdings",
        "csv_text",
        "risk_profile",
    }:
        raise ValueError("invalid_fields")
    if len(json.dumps(body, allow_nan=False).encode()) > MAX_IMPORT_BYTES:
        raise ValueError("import_limit")
    source = body.get("source")
    if source not in {"manual", "csv"} or body.get("currency") not in {"CNY", "USD", "HKD"}:
        raise ValueError("invalid_source_currency")
    stamp = body.get("as_of")
    if not isinstance(stamp, str) or len(stamp) != 10:
        raise ValueError("invalid_as_of")
    day = date.fromisoformat(stamp)
    if now.tzinfo is None or day > now.astimezone(SHANGHAI).date() or day.year < 1990:
        raise ValueError("invalid_as_of")
    cash = finite(body.get("cash"))
    rows = body.get("holdings")
    if source == "csv" and not canonical:
        if "holdings" in body or not isinstance(body.get("csv_text"), str):
            raise ValueError("invalid_csv")
        reader = csv.DictReader(io.StringIO(body["csv_text"].lstrip("\ufeff")))
        if reader.fieldnames not in (["asset", "quantity"], ["asset", "quantity", "cost"]):
            raise ValueError("invalid_csv_header")
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) > MAX_HOLDINGS:
                raise ValueError("holding_limit")
    elif "csv_text" in body:
        raise ValueError("invalid_csv")
    if not isinstance(rows, list) or not 0 <= len(rows) <= MAX_HOLDINGS:
        raise ValueError("holding_limit")
    normalized, seen = [], set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not {"asset", "quantity"} <= set(row)
            or set(row) - {"asset", "quantity", "cost"}
        ):
            raise ValueError("invalid_holding")
        asset = row.get("asset")
        if (
            not isinstance(asset, str)
            or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", asset)
            or asset in seen
        ):
            raise ValueError("invalid_asset")
        quantity = finite(row.get("quantity"), minimum=0.000001, maximum=1e9)
        holding = {"asset": asset, "quantity": quantity}
        if "cost" in row and not (source == "csv" and row["cost"] == ""):
            holding["cost"] = finite(row["cost"], maximum=1e9)
        normalized.append(holding)
        seen.add(asset)
    profile = body.get("risk_profile", {})
    if not isinstance(profile, dict) or set(profile) - RISK_FIELDS:
        raise ValueError("invalid_risk_profile")
    risk = {}
    for field, value in profile.items():
        if field == "risk_tolerance":
            if value not in {"conservative", "balanced", "aggressive"}:
                raise ValueError("invalid_risk_tolerance")
            risk[field] = value
        else:
            risk[field] = finite(value, maximum=1)
    if "equity_min" in risk and "equity_max" in risk and risk["equity_min"] > risk["equity_max"]:
        raise ValueError("invalid_equity_bounds")
    return {
        "as_of": day.isoformat(),
        "currency": body["currency"],
        "cash": cash,
        "source": source,
        "holdings": normalized,
        "risk_profile": risk,
    }


class PortfolioStore:
    """One private document commits previews and immutable snapshot history together."""

    def __init__(self, root: Path, *, now=None):
        self.directory = Path(root) / "portfolios"
        self.now = now or (lambda: datetime.now(UTC))

    def _load(self):
        try:
            state = read_json(
                self.directory,
                "state.json",
                MAX_STORE_BYTES,
                {"schema_version": 1, "items": [], "previews": {}},
            )
            if (
                not isinstance(state, dict)
                or state.get("schema_version") != 1
                or not isinstance(state.get("items"), list)
                or len(state["items"]) > 20
                or not isinstance(state.get("previews"), dict)
                or len(state["previews"]) > 8
            ):
                raise ValueError("invalid_state")
            # Disk is an input boundary too. Unknown/corrupt records fail closed.
            for item in state["items"]:
                if not isinstance(item, dict) or set(item) != {
                    "snapshot_id",
                    "created_at",
                    "portfolio",
                }:
                    raise ValueError("invalid_snapshot")
                if (
                    not isinstance(item["snapshot_id"], str)
                    or not re.fullmatch(r"[a-f0-9-]{36}", item["snapshot_id"])
                    or not isinstance(item["created_at"], str)
                    or len(item["created_at"]) > 80
                ):
                    raise ValueError("invalid_snapshot_identity")
                item["portfolio"] = _normalize(item["portfolio"], self.now(), canonical=True)
            for key, preview in state["previews"].items():
                if (
                    not isinstance(key, str)
                    or not re.fullmatch(r"[a-f0-9]{64}", key)
                    or not isinstance(preview, dict)
                    or set(preview) != {"portfolio", "expires_at", "snapshot_id"}
                    or not isinstance(preview["expires_at"], (int, float))
                    or isinstance(preview["expires_at"], bool)
                    or not math.isfinite(preview["expires_at"])
                ):
                    raise ValueError("invalid_preview")
                preview["portfolio"] = _normalize(preview["portfolio"], self.now(), canonical=True)
            return state
        except (OSError, ValueError, TypeError, RecursionError, KeyError) as exc:
            log.warning("market_portfolio_read_failed", code="invalid_store")
            raise MarketError("market_portfolio_unavailable", "持仓缓存不可用。", 503) from exc

    def _save(self, state):
        try:
            atomic_json(self.directory, "state.json", state, MAX_STORE_BYTES)
        except (OSError, ValueError, TypeError) as exc:
            log.warning("market_portfolio_write_failed", code="store_failed")
            raise MarketError("market_portfolio_unavailable", "持仓保存失败。", 503) from exc

    def read(self):
        return {"items": self._load()["items"], "integration": self.readiness()}

    @staticmethod
    def readiness():
        return {
            "broker": "jinyuan",
            "client_type": "ordinary",
            "status": "pending_official_api",
            "mode": "manual_csv_only",
            "credentials_accepted": False,
            "trading_enabled": False,
            "reason": "金元普通客户端官方持仓接口尚未确认；仅支持手动录入和CSV预览确认。",
        }

    def preview(self, body):
        try:
            normalized = _normalize(body, self.now())
        except (ValueError, TypeError, OverflowError, csv.Error, RecursionError) as exc:
            log.info("market_portfolio_import_rejected", code="invalid_import")
            raise MarketError(
                "market_portfolio_invalid", "持仓导入格式、范围或风险约束无效。"
            ) from exc
        state = self._load()
        now = self.now().timestamp()
        state["previews"] = {
            key: value
            for key, value in state["previews"].items()
            if isinstance(value, dict)
            and isinstance(value.get("expires_at"), (int, float))
            and value["expires_at"] > now
        }
        token = secrets.token_urlsafe(32)
        key = hashlib.sha256(token.encode()).hexdigest()
        while len(state["previews"]) >= 8:
            del state["previews"][next(iter(state["previews"]))]
        state["previews"][key] = {
            "portfolio": normalized,
            "expires_at": now + 900,
            "snapshot_id": None,
        }
        self._save(state)
        log.info("market_portfolio_preview_created", rows=len(normalized["holdings"]))
        return {
            "confirmation_token": token,
            "expires_in_seconds": 900,
            "snapshot": normalized,
            "warnings": [
                "导入时点由用户声明；尚未与券商对账。",
                "缺少风险约束或经验证的分周期证据时不生成配置金额。",
            ],
        }

    def commit(self, token):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise MarketError("market_portfolio_confirmation_invalid", "请先预览并确认持仓。", 409)
        state = self._load()
        preview = state["previews"].get(hashlib.sha256(token.encode()).hexdigest())
        if not isinstance(preview, dict) or preview.get("expires_at", 0) <= self.now().timestamp():
            raise MarketError(
                "market_portfolio_confirmation_expired", "预览已过期，请重新导入。", 409
            )
        if preview.get("snapshot_id"):
            found = next(
                (row for row in state["items"] if row["snapshot_id"] == preview["snapshot_id"]),
                None,
            )
            if found:
                return found
            raise MarketError("market_portfolio_confirmation_expired", "持仓快照已过期。", 409)
        try:
            normalized = _normalize(preview.get("portfolio"), self.now(), canonical=True)
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise MarketError(
                "market_portfolio_confirmation_invalid", "预览记录无效，请重新导入。", 409
            ) from exc
        saved = {
            "snapshot_id": str(uuid4()),
            "created_at": self.now().isoformat(),
            "portfolio": normalized,
        }
        preview["snapshot_id"] = saved["snapshot_id"]
        state["items"] = [saved, *state["items"]][:20]
        self._save(state)
        log.info("market_portfolio_committed", rows=len(normalized["holdings"]))
        return saved

    @staticmethod
    def project(snapshot, quotes, *, now=None, cache_state=None, market_state=None):
        """Value only fresh, coherent traded quotes; preserve reference-price provenance."""
        portfolio = snapshot["portfolio"]
        now = now or datetime.now(UTC)

        def aware_time(value):
            if not isinstance(value, str):
                return None
            try:
                stamp = datetime.fromisoformat(value)
                return stamp if stamp.tzinfo is not None else None
            except ValueError:
                return None

        snapshot_time = aware_time(quotes.get("as_of")) if quotes else None
        retrieved = aware_time(quotes.get("retrieved_at")) if quotes else None
        declared_day = quotes.get("summary", {}).get("quote_trade_date") if quotes else None
        snapshot_day = (
            snapshot_time.astimezone(SHANGHAI).date().isoformat() if snapshot_time else None
        )
        source_valid = bool(
            quotes
            and isinstance(quotes.get("provider"), str)
            and quotes["provider"]
            and isinstance(quotes.get("source_url"), str)
            and quotes["source_url"].startswith("https://")
        )
        time_valid = bool(
            now.tzinfo
            and snapshot_time
            and retrieved
            and snapshot_time <= retrieved <= now
            and snapshot_day == declared_day
            and snapshot_day == now.astimezone(SHANGHAI).date().isoformat()
        )
        stale = bool(cache_state and cache_state.get("stale") is True)
        if retrieved and now.tzinfo and (now - retrieved).total_seconds() > 60:
            stale = True
        cache_status = (
            cache_state.get("status", "unavailable")
            if cache_state
            else "stale" if stale else "ready" if time_valid else "unavailable"
        )
        cache_valid = bool(
            quotes
            and quotes.get("complete") is True
            and quotes.get("pagination_complete") is True
            and source_valid
            and time_valid
            and not stale
            and cache_status == "ready"
        )
        if (
            market_state
            and market_state.get("trade_date")
            and snapshot_day != market_state["trade_date"]
        ):
            cache_valid = False
        quote_rows = {row.get("asset"): row for row in quotes.get("rows", [])} if quotes else {}
        positions, missing = [], []
        for holding in portfolio["holdings"]:
            quote = quote_rows.get(holding["asset"], {})
            price = quote.get("price")
            row_time = aware_time(quote.get("as_of"))
            numeric_price = (
                not isinstance(price, bool)
                and isinstance(price, (int, float))
                and math.isfinite(price)
                and 0 < price <= 1e9
            )
            row_time_valid = bool(
                row_time
                and snapshot_time
                and retrieved
                and row_time <= snapshot_time <= retrieved
                and row_time.astimezone(SHANGHAI).date().isoformat() == snapshot_day
            )
            suspended = quote.get("trade_status") == "suspended"
            valid = bool(
                cache_valid
                and portfolio["currency"] == "CNY"
                and numeric_price
                and quote.get("trade_status") == "trading"
                and quote.get("price_basis") == "quote"
                and row_time_valid
                and not quote.get("stale", False)
            )
            value = price * holding["quantity"] if valid else None
            if value is None:
                missing.append(holding["asset"])
            positions.append(
                {
                    **holding,
                    "price": price if valid else None,
                    "market_value": value,
                    "trade_status": quote.get("trade_status", "unknown"),
                    "valuation_status": (
                        "observed"
                        if valid
                        else (
                            "suspended_reference"
                            if suspended
                            else "stale" if stale else "unavailable"
                        )
                    ),
                    "reference_price": price if suspended and numeric_price else None,
                    "quote_as_of": quote.get("as_of"),
                    "price_basis": quote.get("price_basis"),
                    "price_provenance": quote.get("price_provenance"),
                    "timestamp_valid": row_time_valid,
                }
            )
        holdings_value = (
            None
            if missing or not cache_valid
            else math.fsum(row["market_value"] for row in positions)
        )
        total = None if holdings_value is None else holdings_value + portfolio["cash"]
        missing_profile = sorted(RISK_FIELDS - set(portfolio["risk_profile"]))
        profile = portfolio["risk_profile"]
        equity_ratio = holdings_value / total if total else None
        checks = []
        if equity_ratio is not None:
            for field, violated in (
                ("equity_min", equity_ratio < profile.get("equity_min", 0)),
                ("equity_max", equity_ratio > profile.get("equity_max", 1)),
            ):
                if field in profile:
                    checks.append(
                        {
                            "constraint": field,
                            "declared": profile[field],
                            "observed": equity_ratio,
                            "status": (
                                "outside_declared_limit" if violated else "within_declared_limit"
                            ),
                        }
                    )
            if "single_name_max" in profile:
                largest = max((row["market_value"] / total for row in positions), default=0)
                checks.append(
                    {
                        "constraint": "single_name_max",
                        "declared": profile["single_name_max"],
                        "observed": largest,
                        "status": (
                            "outside_declared_limit"
                            if largest > profile["single_name_max"]
                            else "within_declared_limit"
                        ),
                    }
                )
        if "sector_max" in profile:
            checks.append(
                {
                    "constraint": "sector_max",
                    "declared": profile["sector_max"],
                    "observed": None,
                    "status": "unavailable",
                    "reason": "缺少同日逐股行业归属，不能以交易板块代替行业。",
                }
            )
        return {
            **snapshot,
            "positions": positions,
            "profile_status": "observed_only" if missing_profile else "declared",
            "missing_profile_fields": missing_profile,
            "valuation": {
                "holdings_value": holdings_value,
                "total_value": total,
                "equity_ratio": holdings_value / total if total else None,
                "currency": portfolio["currency"],
                "missing_assets": missing,
                "quote_snapshot_id": quotes.get("snapshot_id") if quotes else None,
                "source_url": quotes.get("source_url") if quotes else None,
                "as_of": quotes.get("as_of") if quotes else None,
                "basis": "fresh_coherent_traded_cached_quote_not_broker_reconciled",
                "status": "stale" if stale else "unavailable" if total is None else "observed",
                "cache_status": cache_status,
                "stale": stale,
                "timestamp_valid": time_valid,
                "retrieved_at": quotes.get("retrieved_at") if quotes else None,
                "reason": (
                    "缓存过期、时间/来源不明或存在停牌参考价时，不汇总为当前资产总值。"
                    if total is None
                    else "仅为本次新鲜同日行情估值，现金由用户声明。"
                ),
            },
            "risk_checks": checks,
            "risk_check_status": (
                "incomplete"
                if missing
                or missing_profile
                or any(check["status"] == "unavailable" for check in checks)
                else "observed"
            ),
            "allocation": None,
            "allocation_status": "insufficient_horizon_validation",
        }
