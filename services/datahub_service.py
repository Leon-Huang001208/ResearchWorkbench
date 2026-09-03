"""Shared DataHub application service: source management, facts and durable jobs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from sqlalchemy import func, select

from core.contracts.datahub import CATALOG_DATASETS, DATASETS, DataHubQuery, DataHubSyncRequest
from core.observability import get_logger
from data_layer.normalizers.cjpy import canonical_code, json_value
from data_layer.repositories.datahub_models import (
    DataHubBarDB,
    DataHubRowDB,
    DataHubRunItemDB,
    DataHubSnapshotDB,
)
from data_layer.repositories.datahub_repository import DataHubRepository
from data_layer.repositories.models import FactorDefinitionDB, FactorValueDB, ScheduledJobDB

logger = get_logger(__name__)


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class DataHubService:
    def __init__(self, db):
        self.db = db
        self.repo = DataHubRepository(db)

    def sources(self):
        from core.source_registry import get_all

        result = []
        for spec in get_all():
            source = spec.source_type.value
            entry = {
                "source": source,
                "name": spec.source_name,
                "enabled": spec.enabled,
                "kind": spec.pipeline_kind,
                "health": "unknown",
                "managed_sync": source == "cjpy",
            }
            if source == "cjpy":
                try:
                    entry["version"] = version("cjpy")
                except PackageNotFoundError:
                    entry.update(version=None, health="not_installed")
                entry["datasets"] = list(DATASETS)
            result.append(entry)
        return {"sources": result, "count": len(result)}

    def catalog(self, dataset: str | None = None):
        if dataset is not None:
            if dataset not in CATALOG_DATASETS:
                raise ValueError("Not a catalog dataset")
            return self.query_for_tools(DataHubQuery(dataset=dataset))
        summaries: dict[str, DataHubSnapshotDB] = {}
        for snapshot in self.repo.snapshots(limit=1000):
            summaries.setdefault(snapshot.dataset, snapshot)
        return {
            "source": "cjpy",
            "datasets": [
                {
                    "dataset": key,
                    "name": name,
                    "required": list(required),
                    "is_catalog": key in CATALOG_DATASETS,
                    "last_sync": json_value(summaries[key].last_checked_at)
                    if key in summaries
                    else None,
                    "row_count": summaries[key].row_count if key in summaries else None,
                    "quarantined_count": summaries[key].quarantined_count
                    if key in summaries
                    else None,
                }
                for key, (name, _, required) in DATASETS.items()
            ],
        }

    def _current_snapshots(self, dataset):
        ranked = (
            select(
                DataHubSnapshotDB.snapshot_id,
                func.row_number()
                .over(
                    partition_by=DataHubSnapshotDB.query_hash,
                    order_by=(
                        DataHubSnapshotDB.last_checked_at.desc(),
                        DataHubSnapshotDB.snapshot_id,
                    ),
                )
                .label("rank"),
            )
            .where(DataHubSnapshotDB.source == "cjpy", DataHubSnapshotDB.dataset == dataset)
            .subquery()
        )
        return select(ranked.c.snapshot_id).where(ranked.c.rank == 1)

    def query(self, request: DataHubQuery, *, include_quarantined=False):
        explicit_snapshot = request.snapshot_id or (
            request.fact_id.split(":")[0] if request.fact_id else None
        )
        ids = [explicit_snapshot] if explicit_snapshot else self._current_snapshots(request.dataset)
        snapshots = select(DataHubSnapshotDB).where(
            DataHubSnapshotDB.source == request.source,
            DataHubSnapshotDB.dataset == request.dataset,
            DataHubSnapshotDB.snapshot_id.in_(ids),
        )
        for key in ("table_name", "indicator"):
            value = getattr(request, key)
            if value:
                snapshots = snapshots.where(DataHubSnapshotDB.params[key].as_string() == value)
        if request.dataset == "trading_days" and request.cycle:
            snapshots = snapshots.where(
                func.coalesce(DataHubSnapshotDB.params["cycle"].as_string(), "D") == request.cycle
            )
        selected_ids = snapshots.with_only_columns(DataHubSnapshotDB.snapshot_id)
        query = select(DataHubRowDB).where(DataHubRowDB.snapshot_id.in_(selected_ids))
        if request.fact_id:
            query = query.where(DataHubRowDB.row_id == request.fact_id)
        from data_layer.normalizers.cjpy import parse_time

        if request.start_date:
            query = query.where(DataHubRowDB.as_of >= parse_time(request.start_date))
        if request.end_date:
            query = query.where(
                DataHubRowDB.as_of < parse_time(request.end_date) + timedelta(days=1)
            )
        if request.cycle and request.dataset == "daily_quotes":
            query = query.where(
                DataHubRowDB.payload["cycle"].as_string()
                == ("day" if request.cycle == "D" else request.cycle)
            )
        if request.adjustment:
            query = query.where(
                DataHubRowDB.payload["adjustment"].as_string() == request.adjustment
            )
        if request.symbol:
            query = query.where(DataHubRowDB.symbol == canonical_code(request.symbol))
        all_rows = query.subquery()
        quarantined = self.db.scalar(
            select(func.count())
            .select_from(all_rows)
            .where(all_rows.c.freshness_status == "quarantined")
        )
        if not include_quarantined:
            query = query.where(DataHubRowDB.freshness_status != "quarantined")
        if request.dataset == "daily_quotes" and not explicit_snapshot and not include_quarantined:
            query = query.where(DataHubRowDB.row_id.in_(select(DataHubBarDB.row_id)))
        if request.dataset == "factor_data" and not explicit_snapshot and not include_quarantined:
            query = query.where(
                DataHubRowDB.row_id.in_(
                    select(FactorValueDB.meta["datahub_row_id"].as_string()).where(
                        FactorValueDB.source == "cjpy"
                    )
                )
            )
        filtered = query.subquery()
        total, earliest, latest = self.db.execute(
            select(func.count(), func.min(filtered.c.as_of), func.max(filtered.c.as_of))
        ).one()
        records = list(
            self.db.scalars(
                query.order_by(DataHubRowDB.as_of, DataHubRowDB.snapshot_id, DataHubRowDB.position)
                .offset(request.offset)
                .limit(request.limit)
            )
        )
        snapshot_map = {
            x.snapshot_id: x
            for x in self.db.scalars(
                select(DataHubSnapshotDB).where(
                    DataHubSnapshotDB.snapshot_id.in_({r.snapshot_id for r in records})
                )
            )
        }
        now, output = datetime.now(UTC), []
        from core.contracts.platform_shared import FactResponseBase, ObservationEnvelope

        for row in records:
            snapshot = snapshot_map[row.snapshot_id]
            status = row.freshness_status
            freshness_time = (
                snapshot.last_checked_at if request.dataset in CATALOG_DATASETS else row.as_of
            )
            if status == "fresh" and now - aware(freshness_time) > timedelta(hours=36):
                status = "stale"
            context = FactResponseBase(
                as_of=aware(row.as_of),
                observed_at=aware(row.observed_at),
                available_at=aware(row.available_at),
                source_refs=[self.repo.source_ref(snapshot)],
                freshness_status=status,
                quality_flags=row.quality_flags,
            ).model_dump(mode="json")
            observations = []
            payload = dict(row.payload)
            units = dict(row.units)
            if (
                request.dataset == "factor_data"
                and not explicit_snapshot
                and not include_quarantined
            ):
                current_names = set(
                    self.db.scalars(
                        select(FactorDefinitionDB.name)
                        .join(
                            FactorValueDB, FactorValueDB.factor_id == FactorDefinitionDB.factor_id
                        )
                        .where(FactorValueDB.meta["datahub_row_id"].as_string() == row.row_id)
                    )
                )
                superseded = set(snapshot.params.get("factors", [])) - current_names
                payload["source_fields"] = {
                    k: v for k, v in payload["source_fields"].items() if k not in superseded
                }
                units = {k: v for k, v in units.items() if k not in superseded}
            if request.fields is not None:
                payload["source_fields"] = {
                    k: v for k, v in payload["source_fields"].items() if k in request.fields
                }
            values = payload if request.dataset == "daily_quotes" else payload["source_fields"]
            for key, unit in units.items():
                if request.fields is not None and key not in request.fields:
                    continue
                value = values.get(key)
                if isinstance(value, (dict, list)):
                    continue
                observations.append(
                    ObservationEnvelope(
                        **context,
                        observation_id=row.row_id + ":" + key,
                        subject_ref=row.asset_id or "cjpy:" + request.dataset,
                        metric_key=key,
                        value=value,
                        unit=unit,
                        missing_reason="source_missing" if value is None else None,
                        source_hash=snapshot.content_hash,
                    ).model_dump(mode="json")
                )
            output.append(
                dict(
                    fact_id=row.row_id,
                    snapshot_id=row.snapshot_id,
                    asset_id=row.asset_id,
                    symbol=row.symbol,
                    **context,
                    units=units,
                    payload=payload,
                    observations=observations,
                    evidence_ref="datahub:" + row.row_id,
                )
            )
        # A page outside the result range is unavailable, never an empty 'fresh' result.
        states = {x["freshness_status"] for x in output}
        status = (
            "quarantined"
            if "quarantined" in states or (not total and quarantined)
            else "stale"
            if "stale" in states
            else "fresh"
            if states
            else "unavailable"
        )
        source_refs = [self.repo.source_ref(s) for s in snapshot_map.values()]
        columns = list(dict.fromkeys(c for s in snapshot_map.values() for c in s.columns))
        if request.fields is not None:
            columns = [c for c in columns if c in request.fields]
        snapshot_id = request.snapshot_id or (
            next(iter(snapshot_map)) if len(snapshot_map) == 1 else None
        )
        return {
            "source": request.source,
            "dataset": request.dataset,
            "snapshot_id": snapshot_id,
            "columns": columns,
            "records": output,
            "total": total,
            "offset": request.offset,
            "limit": request.limit,
            "source_refs": source_refs,
            "freshness_status": status,
            "quality_flags": ["contains_quarantined_rows"]
            if quarantined
            else (["not_synced_or_empty"] if not total else []),
            "quarantined_count": quarantined,
            "coverage_start": aware(earliest).isoformat() if earliest else None,
            "coverage_end": aware(latest).isoformat() if latest else None,
            "evidence_ref": "datahub:" + snapshot_id if snapshot_id else None,
        }

    def query_for_tools(self, request):
        """Keep whole facts within the runtime budget; callers resume at next_offset."""
        import json

        result = self.query(request)
        while len(json.dumps(result, ensure_ascii=False)) > 56000 and result["records"]:
            result["records"].pop()
        if len(result["records"]) < min(request.limit, max(0, result["total"] - request.offset)):
            result["quality_flags"].append("response_size_limited")
        result["next_offset"] = request.offset + len(result["records"])
        if not result["records"] and result["total"]:
            result["freshness_status"] = "unavailable"
            result["quality_flags"].append("select_fewer_fields")
            result["source_refs"] = []
            result["columns"] = []
        return result

    def sync(self, request: DataHubSyncRequest):
        from data_layer.repositories.research_workspace_repository import (
            ResearchWorkspaceRepository,
        )
        from services.scheduler_coordinator import SchedulerCoordinator

        payload = {"source": request.source, "dataset": request.dataset, "params": request.params}
        job = SchedulerCoordinator(ResearchWorkspaceRepository(self.db)).enqueue(
            owner="datahub:cjpy",
            job_type="datahub.ingest",
            idempotency_key=request.idempotency_key or uuid4().hex,
            scheduled_for=datetime.now(UTC),
            payload=payload,
        )
        logger.info("datahub sync requested", job_id=job.job_id, dataset=request.dataset)
        return job.model_dump(mode="json")

    def runs(self, job_id=None):
        query = select(ScheduledJobDB).where(ScheduledJobDB.job_type == "datahub.ingest")
        if job_id:
            query = query.where(ScheduledJobDB.job_id == job_id)
        jobs = list(self.db.scalars(query.order_by(ScheduledJobDB.created_at.desc()).limit(50)))
        if job_id and not jobs:
            raise LookupError("DataHub run not found")
        output = []
        for job in jobs:
            items = list(
                self.db.scalars(
                    select(DataHubRunItemDB).where(DataHubRunItemDB.job_id == job.job_id)
                )
            )
            output.append(
                {
                    "job_id": job.job_id,
                    "dataset": job.payload["dataset"],
                    "status": job.status,
                    "attempt": job.attempt,
                    "error_code": job.last_error_code,
                    "saved": sum(x.saved for x in items if x.status == "completed"),
                    "failed_batches": sum(x.status == "failed" for x in items),
                    "batches": [
                        {
                            "batch_key": x.batch_key,
                            "snapshot_id": x.snapshot_id,
                            "status": x.status,
                            "saved": x.saved,
                            "error_code": x.error_code,
                        }
                        for x in items
                    ],
                    "updated_at": aware(job.updated_at).isoformat(),
                }
            )
        return output[0] if job_id else {"runs": output}


def execute_datahub_job(job):
    """Existing durable runtime owns lease renewal and retry; source batches are idempotent."""
    from connectors.market.cjpy import CjpyMarketConnector

    request = DataHubSyncRequest.model_validate(job.payload)
    connector = CjpyMarketConnector(
        {
            "job_id": job.job_id,
            "job_fence": (job.lease_owner, job.fencing_token),
            "retry": {"max_retries": 0},
        }
    )
    result = connector.run(request.dataset, **request.params)
    if result.status.value in {"failed", "partial"}:
        logger.warning(
            "datahub ingestion incomplete", job_id=job.job_id, status=result.status.value
        )
        raise RuntimeError("datahub_ingestion_incomplete")
    return {"job_id": job.job_id, "status": result.status.value}


def register_datahub_scheduler(runtime):
    runtime.register_handler("datahub.ingest", execute_datahub_job)
