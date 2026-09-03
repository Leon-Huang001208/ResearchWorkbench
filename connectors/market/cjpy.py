"""CJPY connector: bounded SDK batches and shared DataHub persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pandas as pd

from core.connectors.base import DiscoveryItem, MarketDataConnector, ParsedTable, RawObject
from core.contracts.datahub import DATASETS, DataHubSyncRequest
from core.contracts.ingestion_record import AssetType, HealthStatus, IngestionRecord
from core.observability import get_logger
from data_layer.normalizers.cjpy import json_value, normalize_row

logger = get_logger(__name__)


class CjpyMarketConnector(MarketDataConnector):
    def __init__(self, config=None, *, adapter=None):
        super().__init__(config)
        self._adapter_instance = adapter
        self._catalog_cache = {}

    @property
    def source(self):
        return "cjpy"

    @property
    def datasets(self):
        return list(DATASETS)

    @property
    def adapter(self):
        if self._adapter_instance is None:
            from data_layer.adapters.cjpy_adapter import CjpyAdapter

            self._adapter_instance = CjpyAdapter(token=self.config.get("token"))
        return self._adapter_instance

    def health_check(self):
        try:
            self._health = (
                HealthStatus.HEALTHY if self.adapter.is_available() else HealthStatus.UNAVAILABLE
            )
        except ImportError:
            self._health = HealthStatus.DEGRADED
        except Exception as exc:
            logger.warning("cjpy health check failed", error_type=type(exc).__name__)
            self._health = HealthStatus.UNAVAILABLE
        return self._health

    def stream(self, codes, fields=None):
        from services.realtime_bridge import RealtimeBridge

        return RealtimeBridge(codes=codes, fields=fields)

    def discover(self, dataset, **params):
        from data_layer.repositories.datahub_repository import digest

        if dataset not in self.datasets:
            return []
        # Generic CLI limits control discovery, never enter SDK calls or persisted credentials.
        max_items = params.pop("max_items", None)
        params = DataHubSyncRequest(dataset=dataset, params=params).params
        batches = [dict(params)]
        if params.get("codes") and dataset in {
            "daily_quotes",
            "index_constituents",
            "factor_data",
            "table_data",
        }:
            batches = [{**params, "codes": [code]} for code in dict.fromkeys(params["codes"])]
        if dataset == "factor_data" and params.get("dates"):
            batches = [
                {**batch, "dates": params["dates"][i : i + 31]}
                for batch in batches
                for i in range(0, len(params["dates"]), 31)
            ]
        if dataset == "daily_quotes":
            split = []
            for batch in batches:
                start, end = datetime.fromisoformat(batch["start_date"]), datetime.fromisoformat(
                    batch["end_date"]
                )
                span = 31 if batch.get("cycle", "day") not in {"day", "D"} else 366
                while start <= end:
                    last = min(end, start + timedelta(days=span - 1))
                    split.append(
                        {
                            **batch,
                            "start_date": start.date().isoformat(),
                            "end_date": last.date().isoformat(),
                        }
                    )
                    start = last + timedelta(days=1)
            batches = split
        items = [
            DiscoveryItem(item_id=digest([dataset, batch]), item_type=dataset, params=batch)
            for batch in batches
        ]
        if max_items is not None:
            items = items[:max_items]
        if self.config.get("job_id"):
            from data_layer.repositories.base import db_session
            from data_layer.repositories.datahub_repository import DataHubRepository

            with db_session() as db:
                repo = DataHubRepository(db)
                items = [
                    item
                    for item in items
                    if not repo.completed_batch(self.config["job_id"], item.item_id)
                ]
        return items

    def fetch(self, dataset, item, **params):
        try:
            result = self.adapter.query(dataset, **item.params)
            index_metadata = None
            if isinstance(result, pd.DataFrame):
                frame = result.copy()
                index_metadata = {"names": list(frame.index.names), "values": frame.index.tolist()}
                if frame.index.name and frame.index.name not in frame.columns:
                    frame = frame.reset_index()
                rows = frame.to_dict(orient="records")
                columns = list(frame.columns)
            elif isinstance(result, dict):
                rows = [{"code": key, "vendor_code": value} for key, value in result.items()]
                columns = ["code", "vendor_code"]
            elif isinstance(result, list):
                rows = [row if isinstance(row, dict) else {"value": row} for row in result]
                columns = list(dict.fromkeys(key for row in rows for key in row))
            else:
                raise ValueError("Unexpected SDK result type")
            semantics, catalogs = self._semantics(dataset, item.params)
            now = datetime.now(UTC)
            # Preserve the complete vendor values in the raw artifact; strict JSON conversion happens at storage boundaries.
            data = json.dumps(
                {
                    "rows": rows,
                    "columns": columns,
                    "index": index_metadata,
                    "catalogs": catalogs,
                    "semantics": semantics,
                },
                ensure_ascii=False,
                default=str,
            )
            return RawObject(
                data=data,
                content_type="application/json",
                source_uri=f"cjpy://{dataset}/{item.item_id}",
                fetched_at=now,
                metadata={
                    "dataset": dataset,
                    "params": {**item.params, **semantics},
                    "columns": columns,
                    "observed_at": now.isoformat(),
                    "batch_key": item.item_id,
                },
            )
        except Exception as exc:
            self._record_failure(item.item_id, type(exc).__name__)
            raise

    def _semantics(self, dataset, params):
        """Use server metadata; unconfirmed units remain quarantined, not guessed."""
        catalogs, semantics = {}, {}
        if dataset not in {"table_data", "macro_data"}:
            return semantics, catalogs

        def catalog(name, **arguments):
            key = (name, tuple(arguments.items()))
            if key not in self._catalog_cache:
                self._catalog_cache[key] = self.adapter.query(name, **arguments).to_dict("records")
            catalogs[name] = self._catalog_cache[key]
            return catalogs[name]

        try:
            if dataset == "table_data":
                definitions = catalog("table_fields", table_name=params["table_name"])
                tables = catalog("tables")
                matches = [x for x in tables if x.get("表名") == params["table_name"]]
                if len(matches) == 1:
                    semantics["date_field"] = matches[0].get("日期字段") or "__observed_at__"
                units = {x["字段名称"]: x["单位"] for x in definitions if x.get("字段名称") and x.get("单位")}
            else:
                definitions = catalog("macro_indicators")
                selector = params["indicator"].split("@")
                matches = [
                    x
                    for x in definitions
                    if selector[0] in {x.get("名称"), str(x.get("字段ID"))}
                    and (len(selector) == 1 or selector[1] in {x.get("表名"), str(x.get("表ID"))})
                ]
                units = (
                    {x["名称"]: x["单位"] for x in matches if x.get("单位")} if len(matches) == 1 else {}
                )
            semantics["column_units"] = {**units, **params.get("column_units", {})}
            if params.get("date_field"):
                semantics["date_field"] = params["date_field"]
        except Exception as exc:
            logger.warning(
                "cjpy metadata unavailable; retaining raw rows",
                dataset=dataset,
                error_type=type(exc).__name__,
            )
        return semantics, catalogs

    def _record_failure(self, batch_key, error_code):
        if self.config.get("job_id"):
            from data_layer.repositories.base import db_session
            from data_layer.repositories.datahub_repository import DataHubRepository

            with db_session() as db:
                DataHubRepository(db, job_fence=self.config.get("job_fence")).record_batch(
                    self.config["job_id"], batch_key, error_code=error_code
                )

    def parse_table(self, raw):
        content = json.loads(raw.data)
        rows = content["rows"] if isinstance(content, dict) else content
        return ParsedTable(
            columns=raw.metadata.get("columns", list(rows[0]) if rows else []),
            rows=rows,
            table_name=raw.metadata.get("dataset"),
            metadata=raw.metadata,
        )

    def normalize_bars(self, dataset, table, raw_uri, content_hash):
        observed = datetime.fromisoformat(
            table.metadata.get("observed_at", datetime.now(UTC).isoformat())
        )
        return [
            IngestionRecord(
                source="cjpy",
                dataset=dataset,
                asset_type=AssetType.MACRO
                if dataset == "macro_data"
                else AssetType.MARKET
                if dataset == "daily_quotes"
                else AssetType.OTHER,
                entity_id=value["symbol"],
                fetched_at=observed,
                raw_uri=raw_uri,
                content_hash=content_hash,
                payload={
                    **json_value(value["payload"]),
                    **json_value(value),
                    "_params": table.metadata.get("params", {}),
                    "_columns": table.columns,
                },
            )
            for row in table.rows
            for value in [normalize_row(dataset, row, table.metadata.get("params", {}), observed)]
        ]

    def _process_item(self, dataset, item, raw, raw_uri):
        from data_layer.repositories.base import db_session
        from data_layer.repositories.datahub_repository import DataHubRepository

        table = self.parse_table(raw)
        records = self.normalize_bars(
            dataset, table, raw_uri, raw.content_hash or self._compute_hash(raw.data)
        )
        try:
            with db_session() as db:
                DataHubRepository(db, job_fence=self.config.get("job_fence")).save_snapshot(
                    dataset,
                    table.rows,
                    table.columns,
                    table.metadata["params"],
                    raw.content_hash or self._compute_hash(raw.data),
                    raw_uri,
                    raw.fetched_at,
                    job_id=self.config.get("job_id"),
                    batch_key=item.item_id,
                )
            return records
        except Exception as exc:
            self._record_failure(item.item_id, type(exc).__name__)
            raise RuntimeError(f"CJPY persistence failed ({type(exc).__name__})") from None

    def persist(self, records):
        from collections import defaultdict

        from data_layer.repositories.base import db_session
        from data_layer.repositories.datahub_repository import DataHubRepository

        groups = defaultdict(list)
        for record in records:
            groups[(record.dataset, record.content_hash, record.raw_uri)].append(record)
        saved = 0
        with db_session() as db:
            repo = DataHubRepository(db)
            for (dataset, content_hash, raw_uri), batch in groups.items():
                _, count = repo.save_snapshot(
                    dataset,
                    [r.payload["payload"]["source_fields"] for r in batch],
                    batch[0].payload["_columns"],
                    batch[0].payload["_params"],
                    content_hash,
                    raw_uri,
                    batch[0].fetched_at,
                )
                saved += count
        return saved

    def _daily_bar_datasets(self):
        return ("daily_quotes",)
