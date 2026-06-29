"""Fund data ingestion service for local rows and CSV files."""

import csv
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from core.contracts.funds import FundHolding, FundManagerProfile, FundMaster, FundNavPoint
from core.observability import get_logger

logger = get_logger(__name__)


class FundDataIngestionService:
    """Normalize local fund rows and persist them through FundRepository."""

    def __init__(self, fund_repository, etl_repository: Optional[Any] = None):
        self.fund_repo = fund_repository
        self.etl_repo = etl_repository

    def ingest_csv(self, dataset: str, path: str | Path, source: str = "local_csv") -> dict[str, Any]:
        """Read a UTF-8 CSV file and ingest rows for a supported fund dataset."""
        file_path = Path(path)
        try:
            with file_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            logger.info(
                "fund csv loaded",
                dataset=dataset,
                path=str(file_path),
                row_count=len(rows),
            )
            return self.ingest_rows(dataset, rows, source=source)
        except Exception as exc:
            logger.error(
                "fund csv ingestion failed",
                dataset=dataset,
                path=str(file_path),
                error=str(exc),
            )
            raise

    def ingest_rows(
        self,
        dataset: str,
        rows: Iterable[Mapping[str, Any]],
        source: str = "local_rows",
    ) -> dict[str, Any]:
        """Normalize and persist rows for one fund dataset."""
        dataset_key = dataset.strip().lower()
        rows_list = list(rows)
        run_id = str(uuid.uuid4())
        job_name = f"ingest_fund_{dataset_key}"

        self._start_run(run_id, job_name, source)
        try:
            self.fund_repo.ensure_schema()
            saved = self._persist_rows(dataset_key, rows_list)
            self._finish_run(
                run_id,
                fetched=len(rows_list),
                normalized=saved,
                saved=saved,
            )
            logger.info(
                "fund rows ingested",
                dataset=dataset_key,
                source=source,
                fetched=len(rows_list),
                saved=saved,
            )
            return {"run_id": run_id, "dataset": dataset_key, "fetched": len(rows_list), "saved": saved}
        except Exception as exc:
            self._fail_run(run_id, str(exc))
            logger.error(
                "fund row ingestion failed",
                dataset=dataset_key,
                source=source,
                error=str(exc),
            )
            raise

    def _persist_rows(self, dataset: str, rows: list[Mapping[str, Any]]) -> int:
        if dataset == "master":
            funds = [self._master_from_row(row) for row in rows]
            for fund in funds:
                self.fund_repo.upsert_fund_master(fund)
            return len(funds)
        if dataset == "nav":
            nav_points = [self._nav_from_row(row) for row in rows]
            self.fund_repo.upsert_nav_points(nav_points)
            return len(nav_points)
        if dataset == "holdings":
            holdings = [self._holding_from_row(row) for row in rows]
            self.fund_repo.upsert_holdings(holdings)
            return len(holdings)
        if dataset == "managers":
            grouped: dict[str, list[FundManagerProfile]] = defaultdict(list)
            for row in rows:
                symbol = self._require_text(row, "symbol")
                grouped[symbol].append(self._manager_from_row(row))
            for symbol, managers in grouped.items():
                self.fund_repo.upsert_manager_tenures(symbol, managers)
            return sum(len(managers) for managers in grouped.values())
        raise ValueError(f"unsupported fund dataset: {dataset}")

    def _start_run(self, run_id: str, job_name: str, source: str) -> None:
        if self.etl_repo is not None:
            self.etl_repo.start(run_id, job_name=job_name, source=source)

    def _finish_run(self, run_id: str, fetched: int, normalized: int, saved: int) -> None:
        if self.etl_repo is not None:
            self.etl_repo.finish(
                run_id,
                status="success",
                items_fetched=fetched,
                items_normalized=normalized,
                items_saved=saved,
            )

    def _fail_run(self, run_id: str, error_message: str) -> None:
        if self.etl_repo is not None:
            self.etl_repo.fail(run_id, error_message)

    def _master_from_row(self, row: Mapping[str, Any]) -> FundMaster:
        return FundMaster(
            symbol=self._require_text(row, "symbol"),
            name=self._require_text(row, "name"),
            fund_type=self._optional_text(row, "fund_type"),
            management_company=self._optional_text(row, "management_company"),
            inception_date=self._optional_date(row, "inception_date"),
            benchmark=self._optional_text(row, "benchmark"),
            latest_size=self._optional_float(row, "latest_size"),
        )

    def _nav_from_row(self, row: Mapping[str, Any]) -> FundNavPoint:
        return FundNavPoint(
            symbol=self._require_text(row, "symbol"),
            trading_day=self._require_date(row, "trading_day"),
            unit_nav=self._require_float(row, "unit_nav"),
            accumulated_nav=self._optional_float(row, "accumulated_nav"),
            daily_return=self._optional_float(row, "daily_return"),
        )

    def _holding_from_row(self, row: Mapping[str, Any]) -> FundHolding:
        return FundHolding(
            symbol=self._require_text(row, "symbol"),
            report_date=self._require_date(row, "report_date"),
            stock_symbol=self._require_text(row, "stock_symbol"),
            stock_name=self._optional_text(row, "stock_name"),
            industry=self._optional_text(row, "industry"),
            theme=self._optional_text(row, "theme"),
            weight=self._require_float(row, "weight"),
            market_value=self._optional_float(row, "market_value"),
        )

    def _manager_from_row(self, row: Mapping[str, Any]) -> FundManagerProfile:
        return FundManagerProfile(
            manager_id=self._require_text(row, "manager_id"),
            manager_name=self._require_text(row, "manager_name"),
            institution_name=self._optional_text(row, "institution_name"),
            tenure_start=self._optional_date(row, "tenure_start"),
            tenure_end=self._optional_date(row, "tenure_end"),
        )

    @staticmethod
    def _raw(row: Mapping[str, Any], key: str) -> Any:
        return row.get(key)

    def _require_text(self, row: Mapping[str, Any], key: str) -> str:
        value = self._optional_text(row, key)
        if value is None:
            raise ValueError(f"missing required field: {key}")
        return value

    def _optional_text(self, row: Mapping[str, Any], key: str) -> Optional[str]:
        value = self._raw(row, key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _require_date(self, row: Mapping[str, Any], key: str) -> date:
        value = self._optional_date(row, key)
        if value is None:
            raise ValueError(f"missing required date field: {key}")
        return value

    def _optional_date(self, row: Mapping[str, Any], key: str) -> Optional[date]:
        text = self._optional_text(row, key)
        if text is None:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"invalid date for {key}: {text}") from exc

    def _require_float(self, row: Mapping[str, Any], key: str) -> float:
        value = self._optional_float(row, key)
        if value is None:
            raise ValueError(f"missing required numeric field: {key}")
        return value

    def _optional_float(self, row: Mapping[str, Any], key: str) -> Optional[float]:
        text = self._optional_text(row, key)
        if text is None:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"invalid number for {key}: {text}") from exc
