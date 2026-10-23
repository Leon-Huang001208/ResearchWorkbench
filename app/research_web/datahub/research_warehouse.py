"""Instance-owned warehouse configuration and reviewed raw stock bindings.

Saving a profile never connects. Initialization is an explicit user action on an
independent rwb_market_* database; the existing local business port is protected.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from core.observability import get_logger

from ..market_store import (
    Batch,
    CoverageProof,
    DatasetIdentity,
    Fact,
    MarketStoreError,
    MarketStoreService,
    PostgresMarketStore,
    RawOriginal,
    StoreScope,
)
from ..market_store.models import parse_batch
from ..market_store.operation import checkpoint, record_committed
from ..store import StoreError
from .contracts import BusinessQuery
from .providers import ProviderError, cn_stock_identity
from .providers_akshare import CHINA_MACRO_SCHEMA
from .providers_baostock import FINANCIAL_SCHEMA as BAOSTOCK_FINANCIAL_SCHEMA
from .providers_external import OFFICIAL_NUMERIC, OFFICIAL_NUMERIC_CONTRACT
from .research_snapshot_store import SnapshotSeries
from .security import atomic_json, directory, read_file
from .warehouse import WarehouseBinding, WarehouseBridge

log = get_logger(__name__)
BAR_METRICS = ("open", "high", "low", "close", "volume", "turnover", "row")
SEMANTICS = hashlib.sha256(b"raw-cn-stock-daily-cny-share-first-observed-v1").hexdigest()
FIELDS: dict[str, dict[str, str | None]] = {
    key: {"unit": "currency_per_share", "currency": "CNY"}
    for key in ("open", "high", "low", "close")
}
FIELDS.update(
    volume={"unit": "share", "currency": None}, turnover={"unit": "currency", "currency": "CNY"}
)


class WarehouseConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=55432, ge=1024, le=65535)
    database: str = Field(pattern=r"^rwb_market_[a-zA-Z0-9_]{1,48}$")
    username: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")
    sslmode: Literal["verify-full", "require", "disable"] = "verify-full"
    password: SecretStr | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def check_endpoint(self):
        if (
            self.port == 5432
            or any(c.isspace() for c in self.host)
            or any(c in self.host for c in "\\@?#%")
        ):
            raise ValueError("protected_or_invalid_warehouse_endpoint")
        local = self.host in {"localhost", "127.0.0.1", "::1"} or self.host.startswith("/")
        if self.host.startswith("/") and (
            ".." in Path(self.host).parts or not Path(self.host).is_absolute()
        ):
            raise ValueError("invalid_warehouse_socket")
        if not local and self.sslmode != "verify-full":
            raise ValueError("remote_warehouse_requires_verified_tls")
        return self


class ResearchWarehouse:
    def __init__(self, root: Path, *, keyring, backend_factory=None):
        self.root, self.keyring = Path(root), keyring
        self._namespace = hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()
        self.credential_service = "ResearchWorkbench.MarketStore." + self._namespace
        self._factory = backend_factory or self._postgres
        self._lock = RLock()
        self._calendars: list[dict] = []
        self._calendar_retry_at = 0.0
        self._last_health = {"health": "untested", "failure_code": None}

    def _profile(self):
        with directory(self.root, (), private=True) as root:
            try:
                if isinstance(root, Path):
                    (root / "warehouse.json").lstat()
                else:
                    os.stat("warehouse.json", dir_fd=root, follow_symlinks=False)
                value = json.loads(read_file(root, "warehouse.json", private=True, limit=16384))
            except FileNotFoundError:
                return None
        if (
            not isinstance(value, dict)
            or set(value) != {"id", "owner", "enabled", "configuration"}
            or not isinstance(value["id"], str)
            or not re.fullmatch(r"[0-9a-f]{32}", value["id"])
            or not isinstance(value["owner"], str)
            or not re.fullmatch(r"warehouse-[0-9a-f]{32}", value["owner"])
            or type(value["enabled"]) is not bool
        ):
            raise MarketStoreError("warehouse_profile_invalid")
        configuration = WarehouseConfiguration.model_validate(value["configuration"])
        if configuration.password is not None:
            raise MarketStoreError("warehouse_profile_contains_secret")
        return value

    @property
    def owner(self):
        profile = self._profile()
        return profile["owner"] if profile else "unconfigured-" + self._namespace

    def capture_identity(self):
        """Non-secret personal profile epoch for trusted sessionless Host readers."""
        # Profiles publish atomically. Do not wait on the database operation lock
        # from the event loop: cancellation must remain able to drain its worker.
        profile = self._profile()
        if profile is None:
            return None
        return {
            "id": profile["id"],
            "owner": profile["owner"],
            "enabled": profile["enabled"],
            "configuration_digest": hashlib.sha256(
                json.dumps(profile["configuration"], sort_keys=True).encode()
            ).hexdigest(),
        }

    def _write(self, value):
        with directory(self.root, (), private=True) as root:
            atomic_json(root, "warehouse.json", value)

    def _secret(self, identifier):
        try:
            return self.keyring.get_password(self.credential_service, identifier)
        except Exception:  # noqa: BLE001 - credential backends must not expose secrets.
            raise MarketStoreError("warehouse_credentials_unavailable") from None

    def status(self):
        with self._lock:
            profile = self._profile()
            return {
                "configured": profile is not None,
                "enabled": bool(profile and profile["enabled"]),
                "profile_id": profile["id"] if profile else None,
                "configuration": profile["configuration"] if profile else {},
                "password_configured": bool(self._secret(profile["id"])) if profile else False,
                "scope": "personal",
                "shared_supported": False,
                "calendar_ready": bool(self._calendars),
                **self._last_health,
            }

    def save(self, value):
        configuration = WarehouseConfiguration.model_validate(value)
        with self._lock:
            previous = self._profile()
            identifier = uuid4().hex
            password = (
                configuration.password.get_secret_value()
                if configuration.password is not None
                else (self._secret(previous["id"]) if previous else None)
            )
            if password:
                try:
                    self.keyring.set_password(self.credential_service, identifier, password)
                    if self._secret(identifier) != password:
                        raise MarketStoreError("warehouse_credentials_unavailable")
                except Exception:  # noqa: BLE001 - never echo vendor keyring details.
                    raise MarketStoreError("warehouse_credentials_unavailable") from None
            profile = {
                "id": identifier,
                "owner": previous["owner"] if previous else "warehouse-" + uuid4().hex,
                "enabled": False,
                "configuration": configuration.model_dump(exclude={"password"}),
            }
            try:
                checkpoint()
                self._write(profile)
            except Exception:
                if password:
                    try:
                        self.keyring.delete_password(self.credential_service, identifier)
                    # Keep the original write error; cleanup must never expose credentials.
                    except Exception:  # noqa: BLE001
                        log.warning("warehouse_uncommitted_secret_cleanup_failed")
                raise
            record_committed(identifier)
            self._calendars.clear()
            self._last_health = {"health": "untested", "failure_code": None}
            log.info("research_warehouse_profile_saved", enabled=False)
            return self.status()

    @staticmethod
    def _postgres(profile, password):
        configuration = profile["configuration"]

        def connect():
            try:
                import psycopg

                return psycopg.connect(
                    host=configuration["host"],
                    port=configuration["port"],
                    dbname=configuration["database"],
                    user=configuration["username"],
                    password=password,
                    sslmode=configuration["sslmode"],
                    connect_timeout=5,
                    options="-c statement_timeout=5000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=10000",
                )
            except Exception:  # noqa: BLE001 - redact driver strings, endpoint and credentials.
                raise MarketStoreError("warehouse_database_unavailable") from None

        return PostgresMarketStore(connect)

    def initialize(self, profile_id, database_confirmation):
        with self._lock:
            profile = self._profile()
            if (
                not profile
                or profile["id"] != profile_id
                or profile["configuration"]["database"] != database_confirmation
            ):
                raise MarketStoreError("warehouse_confirmation_mismatch")
            backend = self._factory(profile, self._secret(profile["id"]))
            backend.bootstrap()
            checkpoint()
            profile["enabled"] = True
            self._write(profile)
            self._last_health = {"health": "healthy", "failure_code": None}
            log.info("research_warehouse_initialized")
            return self.status()

    def disable(self, profile_id):
        with self._lock:
            profile = self._profile()
            if not profile or profile["id"] != profile_id:
                raise MarketStoreError("warehouse_confirmation_mismatch")
            profile["enabled"] = False
            checkpoint()
            self._write(profile)
            record_committed(profile_id)
            log.info("research_warehouse_disabled")
            return self.status()

    def _calendar_service(self, profile, digest):
        scope = StoreScope(self.owner, "personal-research-v1", "akshare", digest)
        dataset = DatasetIdentity(
            "trading_calendar",
            "CN",
            "CN",
            "daily",
            "boolean",
            "none",
            "none",
            hashlib.sha256(b"sina-complete-cn-calendar-first-observed-v1").hexdigest(),
            ("is_trading_day",),
        )

        def authorize(actor, requested, _action):
            current = self._profile()
            return bool(
                current
                and current["id"] == profile["id"]
                and current["enabled"]
                and actor == self.owner
                and requested == scope
            )

        return (
            MarketStoreService(self._factory(profile, self._secret(profile["id"])), authorize),
            scope,
            dataset,
        )

    def _stored_calendar(self, profile, digest, start, end, as_of):
        service, scope, dataset = self._calendar_service(profile, digest)
        result = service.read_range(self.owner, scope, dataset, start, end, as_of=as_of)
        days = {fact.business_date: fact.value for fact in result.facts}
        if len(days) != (end - start).days + 1 or any(
            type(flag) is not bool for flag in days.values()
        ):
            return None
        evidence = hashlib.sha256(
            json.dumps(
                [
                    (fact.business_date.isoformat(), fact.value, fact.raw_hash)
                    for fact in result.facts
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return {
            "start": start,
            "end": end,
            "days": days,
            "hash": evidence,
            "cutoff": as_of.isoformat() if as_of else None,
            "expires": time.monotonic() + 86400,
        }

    def _save_calendar(self, profile, digest, start, end, result):
        service, scope, dataset = self._calendar_service(profile, digest)
        previous = service.read_range(self.owner, scope, dataset, start, end)
        known = {fact.business_date: fact for fact in previous.facts}
        raw = RawOriginal(json.dumps(result.rows, sort_keys=True).encode())
        observed = datetime.now(UTC)
        facts = []
        for row in result.rows:
            day, value = date.fromisoformat(row["date"]), row["is_trading_day"]
            encoded = json.dumps(value)
            old = known.get(day)
            revision = hashlib.sha256(
                (raw.sha256 + observed.isoformat() + (old.identity if old else "")).encode()
            ).hexdigest()
            facts.append(
                old
                if old and old.value_json == encoded
                else Fact(
                    "is_trading_day",
                    day,
                    "daily",
                    encoded,
                    observed,
                    observed,
                    revision,
                    raw.sha256,
                )
            )
        return service.commit_batch(self.owner, scope, dataset, Batch(tuple(facts), (raw,)))

    async def prepare(self, query, *, runner, authorize, configuration_digest, touch_source):
        """Fetch the fixed public calendar only after explicit warehouse activation."""
        profile = self._profile()
        if not profile or not profile["enabled"] or query.capability != "market_bars":
            return
        window = WarehouseBridge._window(query)
        if window is None:
            return
        start, end = window
        if (
            query.capability != "market_bars"
            or query.parameters.get("adjustment") != "none"
            or query.parameters.get("asset_type") != "stock"
            or query.parameters.get("frequency") not in {"daily", "1d", "day"}
            or (end - start).days > 1464
            or start < date(1990, 12, 19)
        ):
            return
        cutoff = query.as_of.isoformat() if query.as_of else None
        if (
            any(
                item["start"] <= start
                and item["end"] >= end
                and item.get("cutoff") == cutoff
                and item["expires"] > time.monotonic()
                for item in self._calendars
            )
            or time.monotonic() < self._calendar_retry_at
        ):
            return
        digest = configuration_digest("akshare")
        try:
            calendar = await runner.run(
                self._stored_calendar, profile, digest, start, end, query.as_of
            )
        except MarketStoreError as exc:
            if str(exc) not in {
                "warehouse_database_unavailable",
                "warehouse_database_operation_failed",
                "warehouse_busy",
            }:
                raise
            calendar = None
        if calendar is not None:
            self._calendars = [*self._calendars[-15:], calendar]
            return
        if query.as_of is not None:
            return
        from .providers_akshare import fetch

        calendar_query = BusinessQuery(
            capability="trading_calendar",
            source="akshare",
            parameters={
                "market": "CN",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )
        try:
            authorize(calendar_query)
        except StoreError as exc:
            if exc.code not in {
                "data_capability_unavailable",
                "data_capability_not_integrated",
                "data_source_unavailable",
                "data_dependency_unavailable",
                "source_scope_excluded",
            }:
                raise
            self._last_health = {
                "health": "degraded",
                "failure_code": "warehouse_calendar_unavailable",
            }
            self._calendar_retry_at = time.monotonic() + 30
            log.warning("warehouse_calendar_not_admitted", code=exc.code)
            return None
        touch_source("akshare")
        result = await fetch(calendar_query)
        authorize(calendar_query)
        if digest != configuration_digest("akshare"):
            raise MarketStoreError("warehouse_calendar_authorization_changed")
        if result.status != "complete" or len(result.rows) != (end - start).days + 1:
            self._calendar_retry_at = time.monotonic() + 30
            self._last_health = {
                "health": "degraded",
                "failure_code": "warehouse_calendar_unavailable",
            }
            return
        days = {date.fromisoformat(row["date"]): row["is_trading_day"] for row in result.rows}
        if set(days) != {
            start + timedelta(days=index) for index in range((end - start).days + 1)
        } or any(type(flag) is not bool for flag in days.values()):
            raise MarketStoreError("warehouse_calendar_invalid")
        self._calendars = [
            *self._calendars[-15:],
            {
                "start": start,
                "end": end,
                "days": days,
                "cutoff": None,
                "hash": hashlib.sha256(
                    json.dumps(result.rows, sort_keys=True).encode()
                ).hexdigest(),
                "expires": time.monotonic() + 86400,
            },
        ]
        try:
            return await runner.run(self._save_calendar, profile, digest, start, end, result)
        except MarketStoreError as exc:
            if str(exc) not in {
                "warehouse_database_unavailable",
                "warehouse_database_operation_failed",
                "warehouse_busy",
            }:
                raise
            log.warning("warehouse_calendar_persistence_unavailable", code=str(exc))
            return None

    def _bridge(self, query, source, digest):
        profile = self._profile()
        if (
            not profile
            or not profile["enabled"]
            or query.capability != "market_bars"
            or source not in {"akshare", "baostock", "wind"}
            or query.parameters.get("asset_type") != "stock"
            or query.parameters.get("adjustment") != "none"
            or query.parameters.get("frequency") not in {"daily", "1d", "day"}
        ):
            return None
        try:
            cn_stock_identity(query.parameters.get("asset"))
        except ProviderError:
            log.warning("warehouse_stock_identity_unverified")
            raise MarketStoreError("warehouse_security_identity_unverified") from None
        window = WarehouseBridge._window(query)
        if window is None:
            return None
        cutoff = query.as_of.isoformat() if query.as_of else None
        calendar = next(
            (
                item
                for item in reversed(self._calendars)
                if item["start"] <= window[0]
                and item["end"] >= window[1]
                and item.get("cutoff") == cutoff
            ),
            None,
        )
        if calendar is None:
            return None
        scope = StoreScope(self.owner, "personal-research-v1", source, digest)
        dataset = DatasetIdentity(
            "market_bars",
            query.parameters["asset"],
            "CN",
            "daily",
            "OHLC:CNY/share;volume:share;turnover:CNY",
            "none",
            "raw",
            SEMANTICS,
            BAR_METRICS,
        )

        def authorize(actor, requested, _action):
            current = self._profile()
            return bool(
                current
                and current["enabled"]
                and current["id"] == profile["id"]
                and actor == self.owner
                and requested == scope
            )

        service = MarketStoreService(self._factory(profile, self._secret(profile["id"])), authorize)
        observed = datetime.now(UTC)

        def decode_original(original):
            try:
                document = json.loads(original.payload)
                if (
                    not isinstance(document, dict)
                    or document.get("format") != "rwb-provider-original-v1"
                    or document.get("provider") != source
                    or document.get("upstream")
                    not in {"sina", "eastmoney", "akshare", "baostock", "wind", "tinysoft"}
                    or not isinstance(document.get("payloads"), list)
                    or not document["payloads"]
                ):
                    raise ValueError("invalid_original")
                for payload in document["payloads"]:
                    if (
                        hashlib.sha256(
                            base64.b64decode(payload["base64"], validate=True)
                        ).hexdigest()
                        != payload["sha256"]
                    ):
                        raise ValueError("invalid_original_hash")
                return document
            except (ValueError, KeyError, TypeError):
                raise MarketStoreError("warehouse_original_provenance_invalid") from None

        def normalize(result, previous):
            if not result.raw:
                raise MarketStoreError("warehouse_original_required")
            for metric in ("open", "high", "low", "close", "volume", "turnover"):
                if any(row.get(metric) is not None for row in result.rows):
                    actual = result.fields.get(metric, {})
                    expected = FIELDS[metric]
                    if any(actual.get(key) != value for key, value in expected.items()):
                        raise MarketStoreError("warehouse_units_unverified")
            upstream = result.metadata.get("upstream_id", source)
            if upstream not in {"sina", "eastmoney", "akshare", "baostock", "wind", "tinysoft"}:
                raise MarketStoreError("warehouse_upstream_unknown")
            previous_rows = {
                fact.business_date: fact for fact in previous.facts if fact.metric == "row"
            }
            previous_origins = {}
            if previous_rows:
                frozen = service.freeze(self.owner, scope, dataset, *window)
                stored = parse_batch(json.loads(frozen.payload)["batch"])
                documents = {
                    original.sha256: decode_original(original)
                    for original in stored.originals
                    if original.sha256 in {fact.raw_hash for fact in previous_rows.values()}
                }
                previous_origins = {
                    day: documents[fact.raw_hash].get("upstream")
                    for day, fact in previous_rows.items()
                }
            incoming = {date.fromisoformat(row["date"]): row for row in result.rows}
            proofs = []
            for prior_origin in set(previous_origins.values()) - {upstream}:
                anchors = [
                    day
                    for day in previous_rows
                    if previous_origins[day] == prior_origin and day in incoming
                ]
                if not anchors:
                    raise MarketStoreError("warehouse_upstream_anchor_missing")
                for day in anchors:
                    old = previous_rows[day].value
                    if any(
                        old.get(metric) != incoming[day].get(metric) for metric in BAR_METRICS[:-1]
                    ):
                        raise MarketStoreError("warehouse_upstream_overlap_conflict")
                proofs.append(
                    {
                        "from": prior_origin,
                        "to": upstream,
                        "dates": [day.isoformat() for day in sorted(anchors)],
                        "originals": sorted({previous_rows[day].raw_hash for day in anchors}),
                    }
                )
            original = RawOriginal(
                json.dumps(
                    {
                        "format": "rwb-provider-original-v1",
                        "provider": source,
                        "upstream": upstream,
                        "observed_at": observed.isoformat(),
                        "fields": result.fields,
                        "verified_overlaps": proofs,
                        "payloads": [
                            {
                                "sha256": hashlib.sha256(value).hexdigest(),
                                "base64": base64.b64encode(value).decode(),
                            }
                            for value in result.raw
                        ],
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode()
            )
            originals = (original,)
            existing = {(fact.metric, fact.business_date): fact for fact in previous.facts}
            facts = []
            for row in result.rows:
                business_date = date.fromisoformat(row["date"])
                if row.get("asset") != dataset.asset:
                    raise MarketStoreError("warehouse_fact_identity_mismatch")
                for metric in BAR_METRICS[:-1]:
                    value = row.get(metric)
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                        or value < 0
                    ):
                        raise MarketStoreError("warehouse_stock_value_invalid")
                    if metric in {"open", "high", "low", "close", "volume"} and value is None:
                        raise MarketStoreError("warehouse_stock_value_missing")
                predecessor = existing.get(("row", business_date))
                row_version = hashlib.sha256(
                    json.dumps(
                        {
                            "row": row,
                            "observed_at": observed.isoformat(),
                            "previous": predecessor.identity if predecessor else None,
                        },
                        sort_keys=True,
                        allow_nan=False,
                    ).encode()
                ).hexdigest()
                for metric in BAR_METRICS:
                    value = row if metric == "row" else row.get(metric)
                    encoded = json.dumps(
                        value,
                        sort_keys=True,
                        allow_nan=False,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    old = existing.get((metric, business_date))
                    if (
                        old is None
                        or old.value_json != encoded
                        or (
                            metric == "row"
                            and previous_origins.get(business_date, upstream) != upstream
                        )
                    ):
                        facts.append(
                            Fact(
                                metric,
                                business_date,
                                "daily",
                                encoded,
                                observed,
                                observed,
                                row_version,
                                originals[0].sha256,
                            )
                        )
            nontrading = tuple(
                day
                for day, flag in calendar["days"].items()
                if window[0] <= day <= window[1] and not flag
            )
            missing = (
                set(service.find_gaps(self.owner, scope, dataset, nontrading))
                if nontrading
                else set()
            )
            coverage = tuple(
                CoverageProof(day, "nontrading", calendar["hash"], observed)
                for day in nontrading
                if day in missing
            )
            return Batch(tuple(facts), originals, coverage) if facts or coverage else None

        def provenance(batch):
            upstreams = set()
            row_hashes = {fact.raw_hash for fact in batch.facts}
            graph: dict[str, set[str]] = {}
            for original in batch.originals:
                if original.sha256 not in row_hashes:
                    continue
                document = decode_original(original)
                upstreams.add(document["upstream"])
                for proof in document.get("verified_overlaps", []):
                    graph.setdefault(proof["from"], set()).add(proof["to"])
                    graph.setdefault(proof["to"], set()).add(proof["from"])
            if len(upstreams) > 1:
                visited = set()
                pending = [next(iter(upstreams))]
                while pending:
                    current = pending.pop()
                    if current not in visited:
                        visited.add(current)
                        pending.extend(graph.get(current, set()) - visited)
                if not upstreams.issubset(visited):
                    raise MarketStoreError("warehouse_upstream_anchor_missing")
            return {"actual_upstreams": sorted(upstreams), "availability_basis": "first_observed"}

        binding = WarehouseBinding(
            self.owner,
            scope,
            dataset,
            tuple(day for day in sorted(calendar["days"]) if window[0] <= day <= window[1]),
            normalize,
            source_url={
                "akshare": "https://akshare.akfamily.xyz/",
                "baostock": "http://www.baostock.com/",
                "wind": "https://www.wind.com.cn/",
                "tinysoft": "https://www.tinysoft.com.cn/",
            }[source],
            render=lambda batch: [fact.value for fact in batch.facts if fact.metric == "row"],
            field_metadata=FIELDS,
            source_metadata=provenance,
        )
        return WarehouseBridge(service, lambda *_args: binding)

    def _snapshot_series(self, query, source, digest):
        """Bind provider-native snapshots to the current private profile epoch.

        DataHub checks source entitlement before and after each operation; this
        boundary additionally rejects profile replacement/revocation mid-query.
        Unknown vendor units never enter the canonical stock-bar dataset.
        """
        profile = self._profile()
        if not profile or not profile["enabled"]:
            return None
        scope = StoreScope(self.owner, "personal-research-v1", source, digest)
        china_macro = source == "akshare" and query.capability == "factor_macro"
        bao_financial = (
            source == "baostock"
            and query.capability == "financials"
            and query.parameters.get("statements") == ["profitability"]
        )
        native_contract = (
            BAOSTOCK_FINANCIAL_SCHEMA
            if bao_financial
            else CHINA_MACRO_SCHEMA if china_macro else None
        )

        def authorize(actor, requested, _action):
            current = self._profile()
            return bool(
                current
                and current["enabled"]
                and current["id"] == profile["id"]
                and current["configuration"] == profile["configuration"]
                and actor == profile["owner"]
                and requested == scope
            )

        service = MarketStoreService(self._factory(profile, self._secret(profile["id"])), authorize)
        series = SnapshotSeries(
            service,
            profile["owner"],
            scope,
            schema_identity="datahub-provider-native-v1:"
            + digest
            + (
                ":" + OFFICIAL_NUMERIC_CONTRACT
                if (source, query.parameters.get("dataset")) in OFFICIAL_NUMERIC
                else ":" + native_contract if native_contract else ""
            ),
            units_identity=(
                OFFICIAL_NUMERIC_CONTRACT
                if (source, query.parameters.get("dataset")) in OFFICIAL_NUMERIC
                else native_contract if native_contract else "vendor-fields-retained-unverified-v1"
            ),
        )
        if query.source not in {"auto", source} and not query.allow_fallback:
            raise MarketStoreError("snapshot_source_mismatch")
        effective = query.model_copy(update={"source": source, "allow_fallback": False})
        return (series, effective) if series.dataset(effective) is not None else None

    def read(self, query, source, digest):
        with self._lock:
            bridge = self._bridge(query, source, digest)
            if bridge is None:
                binding = self._snapshot_series(query, source, digest)
                return binding[0].read(binding[1]) if binding else None
            if query.as_of is None:
                # Trusted complete calendar is evidence for non-trading days;
                # an empty bars response is never used to infer this state.
                context = bridge._context(query, source, digest)
                window = bridge._window(query)
                calendar = next(
                    item
                    for item in reversed(self._calendars)
                    if item["start"] <= window[0]
                    and item["end"] >= window[1]
                    and item.get("cutoff") is None
                )
                days = tuple(
                    day
                    for day, flag in calendar["days"].items()
                    if window[0] <= day <= window[1] and not flag
                )
                gaps = (
                    bridge.service.find_gaps(context.actor, context.scope, context.dataset, days)
                    if days
                    else ()
                )
                if gaps:
                    observed = datetime.now(UTC)
                    raw = RawOriginal(
                        json.dumps([(day.isoformat(), False) for day in gaps]).encode()
                    )
                    bridge.service.commit_batch(
                        context.actor,
                        context.scope,
                        context.dataset,
                        Batch(
                            (),
                            (raw,),
                            tuple(
                                CoverageProof(day, "nontrading", calendar["hash"], observed)
                                for day in gaps
                            ),
                        ),
                    )
            try:
                return bridge.read(query, source, digest)
            except MarketStoreError as exc:
                if str(exc) == "warehouse_upstream_anchor_missing":
                    return None  # A full authorized fetch must establish overlapping anchors.
                raise

    def missing_queries(self, query, source, digest):
        with self._lock:
            bridge = self._bridge(query, source, digest)
            if bridge is None:
                return None
            plans = bridge.missing_queries(query, source, digest)
            if not plans or source != "akshare":
                return plans
            context = bridge._context(query, source, digest)
            previous = bridge.service.read_range(
                context.actor, context.scope, context.dataset, *bridge._window(query)
            )
            known_dates = sorted(
                {fact.business_date for fact in previous.facts if fact.metric == "row"}
            )
            anchored = []
            for plan in plans:
                start, end = bridge._window(plan)
                before = [day for day in known_dates if day < start]
                after = [day for day in known_dates if day > end]
                anchored.append(
                    plan.model_copy(
                        update={
                            "parameters": {
                                **plan.parameters,
                                "start_date": (before[-1] if before else start).isoformat(),
                                "end_date": (after[0] if after else end).isoformat(),
                            }
                        }
                    )
                )
            return tuple(anchored)

    def ingest(self, query, source, digest, result):
        with self._lock:
            bridge = self._bridge(query, source, digest)
            if bridge:
                return bridge.ingest(query, source, digest, result)
            binding = self._snapshot_series(query, source, digest)
            return binding[0].ingest(binding[1], result) if binding else None
