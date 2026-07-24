from datetime import date

import pytest

from services.fund_data_ingestion_service import FundDataIngestionService


class FakeFundRepository:
    def __init__(self):
        self.schema_ensured = False
        self.masters = []
        self.nav_points = []
        self.holdings = []
        self.manager_calls = []

    def ensure_schema(self):
        self.schema_ensured = True

    def upsert_fund_master(self, fund):
        self.masters.append(fund)

    def upsert_nav_points(self, nav_points):
        self.nav_points.extend(nav_points)

    def upsert_holdings(self, holdings):
        self.holdings.extend(holdings)

    def upsert_manager_tenures(self, symbol, managers):
        self.manager_calls.append((symbol, list(managers)))


class FakeEtlRepository:
    def __init__(self):
        self.started = []
        self.finished = []
        self.failed = []

    def start(self, run_id, job_name, source):
        self.started.append((run_id, job_name, source))

    def finish(self, run_id, status="success", items_fetched=0, items_normalized=0, items_saved=0):
        self.finished.append(
            {
                "run_id": run_id,
                "status": status,
                "items_fetched": items_fetched,
                "items_normalized": items_normalized,
                "items_saved": items_saved,
            }
        )

    def fail(self, run_id, error_message):
        self.failed.append((run_id, error_message))


def test_ingest_master_rows_upserts_fund_master_and_finishes_etl():
    fund_repo = FakeFundRepository()
    etl_repo = FakeEtlRepository()
    service = FundDataIngestionService(fund_repo, etl_repo)

    result = service.ingest_rows(
        "master",
        [
            {
                "symbol": "000001.OF",
                "name": "Alpha Growth",
                "fund_type": "equity",
                "management_company": "Alpha Fund",
                "inception_date": "2020-01-01",
                "benchmark": "沪深300",
                "latest_size": "12.5",
            }
        ],
        source="unit-test",
    )

    assert result["fetched"] == 1
    assert result["saved"] == 1
    assert fund_repo.schema_ensured is True
    assert fund_repo.masters[0].inception_date == date(2020, 1, 1)
    assert fund_repo.masters[0].latest_size == pytest.approx(12.5)
    assert etl_repo.finished[0]["items_saved"] == 1


def test_ingest_nav_rows_converts_dates_and_numbers():
    fund_repo = FakeFundRepository()
    service = FundDataIngestionService(fund_repo)

    result = service.ingest_rows(
        "nav",
        [
            {
                "symbol": "000001.OF",
                "trading_day": "2026-06-24",
                "unit_nav": "1.2345",
                "accumulated_nav": "2.3456",
                "daily_return": "0.0123",
            }
        ],
    )

    assert result["saved"] == 1
    assert fund_repo.nav_points[0].trading_day == date(2026, 6, 24)
    assert fund_repo.nav_points[0].daily_return == pytest.approx(0.0123)


def test_ingest_holdings_and_managers_group_manager_rows_by_fund():
    fund_repo = FakeFundRepository()
    service = FundDataIngestionService(fund_repo)

    holding_result = service.ingest_rows(
        "holdings",
        [
            {
                "symbol": "000001.OF",
                "report_date": "2026-03-31",
                "stock_symbol": "688981.SH",
                "stock_name": "SMIC",
                "industry": "Technology",
                "theme": "AI",
                "weight": "0.2",
                "market_value": "120000000",
            }
        ],
    )
    manager_result = service.ingest_rows(
        "managers",
        [
            {
                "symbol": "000001.OF",
                "manager_id": "mgr-1",
                "manager_name": "Jane Chen",
                "institution_name": "Alpha Fund",
                "tenure_start": "2022-01-01",
                "tenure_end": "",
            },
            {
                "symbol": "000002.OF",
                "manager_id": "mgr-2",
                "manager_name": "John Li",
                "institution_name": "Beta Fund",
                "tenure_start": "2021-01-01",
            },
        ],
    )

    assert holding_result["saved"] == 1
    assert fund_repo.holdings[0].market_value == pytest.approx(120000000.0)
    assert manager_result["saved"] == 2
    assert fund_repo.manager_calls[0][0] == "000001.OF"
    assert fund_repo.manager_calls[0][1][0].tenure_start == date(2022, 1, 1)
    assert fund_repo.manager_calls[1][0] == "000002.OF"


def test_ingest_csv_reads_rows_from_file(tmp_path):
    fund_repo = FakeFundRepository()
    service = FundDataIngestionService(fund_repo)
    csv_path = tmp_path / "fund_master.csv"
    csv_path.write_text(
        "symbol,name,fund_type,latest_size\n000001.OF,Alpha Growth,equity,12.5\n",
        encoding="utf-8",
    )

    result = service.ingest_csv("master", csv_path)

    assert result["saved"] == 1
    assert fund_repo.masters[0].symbol == "000001.OF"


def test_ingest_rows_fails_etl_when_row_is_invalid():
    fund_repo = FakeFundRepository()
    etl_repo = FakeEtlRepository()
    service = FundDataIngestionService(fund_repo, etl_repo)

    with pytest.raises(ValueError, match="invalid date"):
        service.ingest_rows(
            "nav",
            [
                {
                    "symbol": "000001.OF",
                    "trading_day": "bad-date",
                    "unit_nav": "1.23",
                }
            ],
        )

    assert etl_repo.failed
    assert "invalid date" in etl_repo.failed[0][1]
