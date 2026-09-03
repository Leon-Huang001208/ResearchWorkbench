"""Transactional persistence and bounded reads for the shared DataHub fact owner."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core.contracts.datahub import CATALOG_DATASETS
from core.contracts.platform_shared import SourceRef, SourceTier
from core.observability import get_logger
from data_layer.normalizers.cjpy import canonical_code, json_value, normalize_row
from data_layer.repositories.datahub_models import (
    DataHubBarDB,
    DataHubRowDB,
    DataHubRunItemDB,
    DataHubSnapshotDB,
)
from data_layer.repositories.models import (
    AssetIdentifierDB,
    AssetRegistryDB,
    DomainEventDB,
    FactorDefinitionDB,
    FactorValueDB,
    IndexComponentSnapshotDB,
    IndexMasterDB,
    ScheduledJobDB,
    StockDailyBarDB,
)

logger = get_logger(__name__)


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def query_identity(dataset, params):
    """Equivalent vendor spellings share a current query; raw parameters remain intact."""
    from data_layer.normalizers.cjpy import parse_time

    identity = dict(params)
    if identity.get("codes"):
        identity["codes"] = sorted({canonical_code(c) or c for c in identity["codes"]})
    for key in ("date", "start_date", "end_date"):
        if identity.get(key) and identity[key] != "all":
            identity[key] = parse_time(identity[key]).date().isoformat()
    if dataset == "factor_data":
        dates = identity.pop("dates", None) or [identity.pop("date", None)]
        identity.pop("date", None)
        identity["dates"] = sorted({parse_time(d).date().isoformat() for d in dates if d})
    if dataset == "index_constituents":
        identity = {key: identity[key] for key in ("codes", "date")}
    if identity.get("cycle") == "D" and dataset == "daily_quotes":
        identity["cycle"] = "day"
    return digest(identity)


class DataHubRepository:
    def __init__(self, db, *, job_fence=None):
        self.db = db
        self.job_fence = job_fence

    def _check_fence(self, job_id, *, lock=True):
        if not job_id or self.job_fence is None:
            return
        query = (
            select(ScheduledJobDB)
            .where(ScheduledJobDB.job_id == job_id)
            .execution_options(populate_existing=True)
        )
        job = self.db.scalar(query.with_for_update() if lock else query)
        expires = job.lease_expires_at if job else None
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if (
            not job
            or job.lease_owner != self.job_fence[0]
            or job.attempt != self.job_fence[1]
            or job.status not in {"leased", "running"}
            or not expires
            or expires <= datetime.now(UTC)
        ):
            raise ValueError("DataHub lease fencing rejected stale worker")

    def upsert(self, model, values, keys, *, replace=True):
        insert = pg_insert if self.db.bind.dialect.name == "postgresql" else sqlite_insert
        values = {model.__mapper__.column_attrs[k].columns[0].name: v for k, v in values.items()}
        stmt = insert(model.__table__).values(**values)
        changes = {k: stmt.excluded[k] for k in values if k not in keys}
        stmt = (
            stmt.on_conflict_do_update(index_elements=keys, set_=changes)
            if replace and changes
            else stmt.on_conflict_do_nothing(index_elements=keys)
        )
        self.db.execute(stmt)

    def completed_batch(self, job_id, batch_key):
        return self.db.scalar(
            select(DataHubRunItemDB).where(
                DataHubRunItemDB.job_id == job_id,
                DataHubRunItemDB.batch_key == batch_key,
                DataHubRunItemDB.status == "completed",
            )
        )

    def record_batch(self, job_id, batch_key, *, snapshot_id=None, saved=0, error_code=None):
        if not job_id:
            return
        self._check_fence(job_id)
        self.upsert(
            DataHubRunItemDB,
            dict(
                item_id=digest([job_id, batch_key]),
                job_id=job_id,
                batch_key=batch_key,
                snapshot_id=snapshot_id,
                saved=saved,
                error_code=error_code,
                status="failed" if error_code else "completed",
                updated_at=datetime.now(UTC),
            ),
            ["job_id", "batch_key"],
        )

    def _asset_id(self, symbol, at, dataset):
        if not symbol:
            return None
        identifiers = list(
            self.db.scalars(
                select(AssetIdentifierDB).where(
                    AssetIdentifierDB.value.in_([symbol, symbol[-2:] + symbol[:6]]),
                    AssetIdentifierDB.valid_from <= at,
                    (AssetIdentifierDB.valid_to.is_(None) | (AssetIdentifierDB.valid_to > at)),
                )
            )
        )
        ids = {entry.asset_id for entry in identifiers}
        if len(ids) == 1:
            asset_id = ids.pop()
            expected_type = {"stock_list": "stock", "fund_list": "fund"}.get(dataset)
            asset = self.db.get(AssetRegistryDB, asset_id)
            return (
                asset_id
                if asset and (not expected_type or asset.asset_type == expected_type)
                else None
            )
        # Only typed provider lists can bootstrap identity; arbitrary universes cannot.
        if not ids and dataset in {"stock_list", "fund_list"}:
            asset_type = "stock" if dataset == "stock_list" else "fund"
            previous = list(
                self.db.scalars(
                    select(AssetIdentifierDB).where(
                        AssetIdentifierDB.scheme == "cjpy", AssetIdentifierDB.value == symbol
                    )
                )
            )
            if previous:
                if len(previous) != 1 or previous[0].valid_to is not None:
                    return None
                previous[0].valid_from = min(
                    previous[0].valid_from.replace(tzinfo=UTC)
                    if previous[0].valid_from.tzinfo is None
                    else previous[0].valid_from,
                    at,
                )
                return previous[0].asset_id
            # Existing identity outside its documented validity cannot be silently duplicated.
            historical = self.db.scalar(
                select(AssetIdentifierDB.identifier_id)
                .where(AssetIdentifierDB.value.in_([symbol, symbol[-2:] + symbol[:6]]))
                .limit(1)
            )
            if historical is not None:
                return None
            asset_id = asset_type + ":" + symbol
            self.upsert(
                AssetRegistryDB,
                dict(
                    asset_id=asset_id,
                    asset_type=asset_type,
                    canonical_name=symbol,
                    registry_metadata={"source": "cjpy"},
                ),
                ["asset_id"],
                replace=False,
            )
            self.upsert(
                AssetIdentifierDB,
                dict(
                    identifier_id=digest([asset_id, "cjpy", symbol]),
                    asset_id=asset_id,
                    scheme="cjpy",
                    value=symbol,
                    market=symbol[-2:],
                    valid_from=at,
                ),
                ["identifier_id"],
                replace=False,
            )
            return asset_id
        return None

    def save_snapshot(
        self,
        dataset,
        rows,
        columns,
        params,
        content_hash,
        raw_uri,
        observed_at,
        *,
        job_id=None,
        batch_key=None,
    ):
        self._check_fence(job_id, lock=False)
        if observed_at.tzinfo is None:
            raise ValueError("CJPY observation time must be timezone aware")
        # Serialize CJPY projections, including retries with overlapping query windows.
        # The lock is transaction-scoped and never held during an upstream request.
        if self.db.bind.dialect.name == "postgresql":
            self.db.execute(text("SELECT pg_advisory_xact_lock(746280192)"))
        query_hash = query_identity(dataset, params)
        snapshot_id = digest(["cjpy", dataset, query_hash, content_hash])
        existing = self.db.get(DataHubSnapshotDB, snapshot_id)
        revalidating = bool(existing and existing.quarantined_count)
        previous_quarantined = existing.quarantined_count if existing else 0
        if existing and not revalidating:
            checked = existing.last_checked_at
            checked = checked.replace(tzinfo=UTC) if checked.tzinfo is None else checked
            if observed_at > checked:
                existing.last_checked_at = observed_at
                if dataset == "index_constituents" and not existing.quarantined_count:
                    index = self._index_master(params["codes"][0])
                    if index is not None:
                        from data_layer.normalizers.cjpy import parse_time

                        at = parse_time(params["date"])
                        newer = self.db.scalar(
                            select(DataHubSnapshotDB.snapshot_id)
                            .where(
                                DataHubSnapshotDB.dataset == dataset,
                                DataHubSnapshotDB.query_hash == query_hash,
                                DataHubSnapshotDB.last_checked_at > observed_at,
                            )
                            .limit(1)
                        )
                        if newer is None:
                            self.db.execute(
                                delete(IndexComponentSnapshotDB).where(
                                    IndexComponentSnapshotDB.source == "cjpy",
                                    IndexComponentSnapshotDB.index_id == index.index_id,
                                    IndexComponentSnapshotDB.trade_date == at,
                                )
                            )
                for stored in self.db.scalars(
                    select(DataHubRowDB).where(
                        DataHubRowDB.snapshot_id == snapshot_id,
                        DataHubRowDB.freshness_status == "fresh",
                    )
                ):
                    self._project(
                        dataset,
                        stored.row_id,
                        {
                            "symbol": stored.symbol,
                            "as_of": stored.as_of,
                            "available_at": stored.available_at,
                            "observed_at": observed_at,
                            "payload": stored.payload,
                            "units": stored.units,
                        },
                        params,
                    )
            self.record_batch(job_id, batch_key, snapshot_id=snapshot_id, saved=existing.row_count)
            return snapshot_id, existing.row_count
        if revalidating:
            checked = existing.last_checked_at
            checked = checked.replace(tzinfo=UTC) if checked.tzinfo is None else checked
            if observed_at <= checked:
                self.record_batch(
                    job_id, batch_key, snapshot_id=snapshot_id, saved=existing.row_count
                )
                return snapshot_id, existing.row_count
            existing.last_checked_at = observed_at
        # PostgreSQL unique insertion serializes concurrent retries before projections.
        self.upsert(
            DataHubSnapshotDB,
            dict(
                snapshot_id=snapshot_id,
                source="cjpy",
                dataset=dataset,
                query_hash=query_hash,
                content_hash=content_hash,
                params=json_value(params),
                columns=columns,
                raw_uri=raw_uri,
                observed_at=observed_at,
                available_at=datetime.now(UTC),
                last_checked_at=observed_at,
                row_count=len(rows),
                quarantined_count=0,
            ),
            ["snapshot_id"],
            replace=False,
        )
        quarantined = 0
        valid_rows = []
        for position, original in enumerate(rows):
            row_id = f"{snapshot_id}:{position}"
            stored = self.db.get(DataHubRowDB, row_id) if revalidating else None
            if stored is not None and stored.freshness_status != "quarantined":
                # Already published facts keep their content and observation timestamps.
                valid_rows.append(
                    (
                        row_id,
                        {
                            key: getattr(stored, key)
                            for key in (
                                "symbol",
                                "as_of",
                                "available_at",
                                "observed_at",
                                "payload",
                                "units",
                            )
                        },
                    )
                )
                continue
            original_observed = stored.observed_at if stored is not None else observed_at
            if original_observed.tzinfo is None:
                original_observed = original_observed.replace(tzinfo=UTC)
            value = normalize_row(dataset, original, params, original_observed)
            # Promotion is available only after the current platform validation succeeds.
            value["available_at"] = max(observed_at, datetime.now(UTC))
            asset_id = (
                self._asset_id(value["symbol"], value["as_of"], dataset)
                if dataset not in CATALOG_DATASETS
                else None
            )
            if dataset not in CATALOG_DATASETS and value["symbol"] and not asset_id:
                value["quality_flags"].append("asset_identity_unresolved")
                value["freshness_status"] = "quarantined"
            if dataset == "daily_quotes" and asset_id:
                asset = self.db.get(AssetRegistryDB, asset_id)
                if asset.asset_type == "stock" and not value["symbol"].startswith(("200", "900")):
                    value["units"].update(
                        {
                            "open": "CNY",
                            "high": "CNY",
                            "low": "CNY",
                            "close": "CNY",
                            "volume": "share",
                            "amount": "CNY",
                        }
                    )
                elif not all(
                    value["units"].get(key)
                    for key in ("open", "high", "low", "close", "volume", "amount")
                ):
                    value["quality_flags"].append("unconfirmed_market_units")
                    value["freshness_status"] = "quarantined"
            if dataset == "index_constituents":
                index = self._index_master(params["codes"][0])
                if index is None:
                    value["quality_flags"].append("index_identity_unresolved")
                    value["freshness_status"] = "quarantined"
            quarantined += value["freshness_status"] == "quarantined"
            self.upsert(
                DataHubRowDB,
                dict(
                    row_id=row_id,
                    snapshot_id=snapshot_id,
                    position=position,
                    asset_id=asset_id,
                    **value,
                ),
                ["row_id"],
                replace=revalidating,
            )
            if value["freshness_status"] != "quarantined":
                valid_rows.append((row_id, value))
                if dataset != "index_constituents":
                    self._project(dataset, row_id, {**value, "observed_at": observed_at}, params)
        if dataset == "index_constituents" and not quarantined:
            index = self._index_master(params["codes"][0])
            if index is not None:
                from data_layer.normalizers.cjpy import parse_time

                at = parse_time(params["date"])
                newer = self.db.scalar(
                    select(DataHubSnapshotDB.snapshot_id)
                    .where(
                        DataHubSnapshotDB.dataset == dataset,
                        DataHubSnapshotDB.query_hash == query_hash,
                        DataHubSnapshotDB.last_checked_at > observed_at,
                    )
                    .limit(1)
                )
                if newer is None:
                    self.db.execute(
                        delete(IndexComponentSnapshotDB).where(
                            IndexComponentSnapshotDB.source == "cjpy",
                            IndexComponentSnapshotDB.index_id == index.index_id,
                            IndexComponentSnapshotDB.trade_date == at,
                        )
                    )
                    for row_id, value in valid_rows:
                        self._project(
                            dataset, row_id, {**value, "observed_at": observed_at}, params
                        )
        snapshot = self.db.get(DataHubSnapshotDB, snapshot_id)
        snapshot.quarantined_count = quarantined
        self.record_batch(job_id, batch_key, snapshot_id=snapshot_id, saved=len(rows))
        event_key = "datahub:" + snapshot_id
        event_sequence = 1
        if revalidating and previous_quarantined != quarantined:
            event_key += ":validated:" + str(quarantined)
            event_sequence = 1 + (
                self.db.scalar(
                    select(func.max(DomainEventDB.sequence)).where(
                        DomainEventDB.aggregate_type == "datahub_snapshot",
                        DomainEventDB.aggregate_id == snapshot_id,
                    )
                )
                or 0
            )
        self.upsert(
            DomainEventDB,
            dict(
                event_id=event_key,
                event_type="datahub.snapshot.updated",
                aggregate_type="datahub_snapshot",
                aggregate_id=snapshot_id,
                sequence=event_sequence,
                occurred_at=datetime.now(UTC),
                payload_ref="datahub:" + snapshot_id,
                payload={
                    "snapshot_id": snapshot_id,
                    "dataset": dataset,
                    "saved": len(rows),
                    "quarantined": quarantined,
                },
                idempotency_key=event_key,
            ),
            ["idempotency_key"],
            replace=False,
        )
        self.db.flush()
        logger.info(
            "datahub snapshot stored",
            snapshot_id=snapshot_id,
            dataset=dataset,
            saved=len(rows),
            quarantined=quarantined,
        )
        return snapshot_id, len(rows)

    def _index_master(self, code):
        symbol = canonical_code(code)
        matches = (
            list(self.db.scalars(select(IndexMasterDB).where(IndexMasterDB.wind_code == symbol)))
            if symbol
            else []
        )
        return matches[0] if len(matches) == 1 else None

    def _project(self, dataset, row_id, row, params):
        from core.contracts.market_home import MarketHomeSectionKey
        from data_layer.normalizers.cjpy import SHANGHAI
        from data_layer.repositories.market_data_repository import MarketDataRepository
        from services.market_home_invalidation import record_market_home_fact_update

        p = row["payload"]
        symbol, at = row["symbol"], row["as_of"]
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        at = at.astimezone(SHANGHAI)
        if dataset == "daily_quotes":
            identity = ["cjpy", symbol, at.astimezone(UTC).isoformat(), p["cycle"], p["adjustment"]]
            existing_time = self.db.scalar(
                select(DataHubSnapshotDB.last_checked_at)
                .join(DataHubRowDB, DataHubRowDB.snapshot_id == DataHubSnapshotDB.snapshot_id)
                .join(DataHubBarDB, DataHubBarDB.row_id == DataHubRowDB.row_id)
                .where(
                    DataHubBarDB.source == "cjpy",
                    DataHubBarDB.symbol == symbol,
                    DataHubBarDB.timestamp == at,
                    DataHubBarDB.cycle == p["cycle"],
                    DataHubBarDB.adjustment == p["adjustment"],
                )
            )
            if existing_time:
                existing_time = (
                    existing_time.replace(tzinfo=UTC)
                    if existing_time.tzinfo is None
                    else existing_time
                )
                if existing_time > row["observed_at"]:
                    return
            self.upsert(
                DataHubBarDB,
                dict(
                    bar_id=digest(identity),
                    source="cjpy",
                    symbol=symbol,
                    timestamp=at,
                    cycle=p["cycle"],
                    adjustment=p["adjustment"],
                    row_id=row_id,
                    **{k: p[k] for k in ("open", "high", "low", "close", "volume", "amount")},
                ),
                ["source", "symbol", "timestamp", "cycle", "adjustment"],
            )
            asset_id = self._asset_id(symbol, at, dataset)
            asset = self.db.get(AssetRegistryDB, asset_id) if asset_id else None
            if (
                p["cycle"] in {"day", "D"}
                and p["adjustment"] == "forward"
                and asset
                and asset.asset_type == "stock"
            ):
                # Legacy date keys were UTC midnight. Never rewrite unknown adjustment history.
                from data_layer.normalizers.cjpy import SHANGHAI

                legacy_date = at.astimezone(SHANGHAI).replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC
                )
                legacy = self.db.scalar(
                    select(StockDailyBarDB).where(
                        StockDailyBarDB.symbol == symbol,
                        StockDailyBarDB.source == "cjpy",
                        StockDailyBarDB.trade_date == legacy_date,
                    )
                )
                if legacy is None or (legacy.raw_payload or {}).get("adjustment") == "forward":
                    MarketDataRepository(self.db).upsert_daily_bars(
                        [
                            dict(
                                symbol=symbol,
                                trade_date=legacy_date,
                                source="cjpy",
                                raw_payload=json_value(p),
                                **{
                                    k: p[k]
                                    for k in ("open", "high", "low", "close", "volume", "amount")
                                },
                            )
                        ]
                    )
            record_market_home_fact_update(
                self.db,
                [MarketHomeSectionKey.ASSET_MOVES],
                as_of=at,
                idempotency_key="datahub:" + row_id,
            )
        elif dataset == "factor_data":
            for name in params["factors"]:
                factor_value = p["source_fields"].get(name)
                if factor_value is not None and not isinstance(factor_value, (int, float)):
                    continue
                formula = (params.get("repo") or {}).get(name)
                factor_id = "cjpy:" + name + (":" + digest(formula)[:16] if formula else "")
                definition = self.db.get(FactorDefinitionDB, factor_id)
                unit = row["units"].get(name)
                if definition and (definition.meta or {}).get("unit") != unit:
                    factor_id += ":" + digest(unit)[:12]
                current = self.db.scalar(
                    select(FactorValueDB).where(
                        FactorValueDB.factor_id == factor_id,
                        FactorValueDB.subject_id == symbol,
                        FactorValueDB.as_of_date == at.date(),
                    )
                )
                if current and current.available_at:
                    previous_at = (
                        current.available_at.replace(tzinfo=UTC)
                        if current.available_at.tzinfo is None
                        else current.available_at
                    )
                    if (current.meta or {}).get("observed_at"):
                        previous_at = datetime.fromisoformat(current.meta["observed_at"])
                    if previous_at > row["observed_at"]:
                        continue
                self.upsert(
                    FactorDefinitionDB,
                    dict(
                        factor_id=factor_id,
                        name=name,
                        category="cjpy",
                        meta={"unit": row["units"].get(name), "formula": formula},
                    ),
                    ["factor_id"],
                    replace=False,
                )
                self.upsert(
                    FactorValueDB,
                    dict(
                        factor_id=factor_id,
                        subject_id=symbol,
                        as_of_date=at.date(),
                        value=factor_value,
                        available_at=row["available_at"],
                        source="cjpy",
                        meta={
                            "datahub_row_id": row_id,
                            "observed_at": row["observed_at"].isoformat(),
                        },
                    ),
                    ["factor_id", "subject_id", "as_of_date"],
                )
        elif dataset == "index_constituents":
            newer = self.db.scalar(
                select(DataHubSnapshotDB.snapshot_id)
                .where(
                    DataHubSnapshotDB.dataset == dataset,
                    DataHubSnapshotDB.query_hash == query_identity(dataset, params),
                    DataHubSnapshotDB.last_checked_at > row["observed_at"],
                )
                .limit(1)
            )
            if newer is not None:
                return
            index_symbol = canonical_code(params["codes"][0])
            index = self._index_master(index_symbol)
            if index is None:
                raise ValueError("Index identity no longer resolves")
            MarketDataRepository(self.db).upsert_index_components(
                [
                    dict(
                        index_id=index.index_id,
                        index_symbol=index_symbol,
                        provider_code=index.provider_code,
                        component_symbol=symbol,
                        trade_date=at,
                        as_of=at,
                        source="cjpy",
                        raw_payload=p,
                        source_scope="full",
                    )
                ]
            )

    def snapshots(self, dataset=None, *, limit=100):
        query = select(DataHubSnapshotDB)
        if dataset:
            query = query.where(DataHubSnapshotDB.dataset == dataset)
        return list(
            self.db.scalars(
                query.order_by(
                    DataHubSnapshotDB.last_checked_at.desc(), DataHubSnapshotDB.snapshot_id
                ).limit(limit)
            )
        )

    def source_ref(self, snapshot):
        return SourceRef(
            source_id="cjpy",
            name="CJPY / Tinysoft",
            tier=SourceTier.LICENSED,
            content_hash=snapshot.content_hash,
        ).model_dump(mode="json")
