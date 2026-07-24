from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.funds import get_fund_ingestion_service, get_fund_service, router
from core.contracts.funds import (
    FundDetail,
    FundExposureBreakdown,
    FundMaster,
    FundNavPoint,
    FundPerformanceMetrics,
    PortfolioFundExposure,
)


class FakeFundService:
    def get_fund_detail(self, symbol):
        if symbol == "missing":
            return None
        return FundDetail(
            master=FundMaster(symbol=symbol, name="Alpha Growth"),
            latest_nav=FundNavPoint(
                symbol=symbol,
                trading_day=date(2026, 6, 24),
                unit_nav=1.2,
                accumulated_nav=1.5,
            ),
            performance=FundPerformanceMetrics(total_return=0.2, max_drawdown=-0.05),
        )

    def get_fund_exposure(self, symbol):
        return PortfolioFundExposure(
            positions={symbol: 1.0},
            industry_exposure=[FundExposureBreakdown(label="Technology", weight=0.2)],
            stock_exposure=[FundExposureBreakdown(label="688981.SH", weight=0.2)],
        )

    def calculate_portfolio_exposure(self, positions):
        return PortfolioFundExposure(
            positions=positions,
            industry_exposure=[FundExposureBreakdown(label="Technology", weight=0.22)],
            stock_exposure=[FundExposureBreakdown(label="688981.SH", weight=0.22)],
        )


class FakeFundIngestionService:
    def __init__(self):
        self.calls = []

    def ingest_rows(self, dataset, rows, source="api"):
        self.calls.append((dataset, rows, source))
        return {
            "run_id": "run-1",
            "dataset": dataset,
            "fetched": len(rows),
            "saved": len(rows),
        }


def make_client():
    app = FastAPI()
    ingestion_service = FakeFundIngestionService()
    app.include_router(router)
    app.dependency_overrides[get_fund_service] = lambda: FakeFundService()
    app.dependency_overrides[get_fund_ingestion_service] = lambda: ingestion_service
    return TestClient(app), ingestion_service


def test_get_fund_detail_returns_detail_payload():
    client, _ = make_client()

    response = client.get("/api/funds/000001.OF")

    assert response.status_code == 200
    body = response.json()
    assert body["master"]["symbol"] == "000001.OF"
    assert body["latest_nav"]["trading_day"] == "2026-06-24"
    assert body["performance"]["total_return"] == 0.2


def test_get_fund_detail_returns_404_for_missing_fund():
    client, _ = make_client()

    response = client.get("/api/funds/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Fund not found"


def test_get_fund_exposure_returns_exposure_payload():
    client, _ = make_client()

    response = client.get("/api/funds/000001.OF/exposure")

    assert response.status_code == 200
    body = response.json()
    assert body["positions"] == {"000001.OF": 1.0}
    assert body["industry_exposure"][0]["label"] == "Technology"


def test_portfolio_exposure_returns_weighted_payload():
    client, _ = make_client()

    response = client.post(
        "/api/funds/portfolio/exposure",
        json={"positions": {"000001.OF": 0.6, "000002.OF": 0.4}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["positions"] == {"000001.OF": 0.6, "000002.OF": 0.4}
    assert body["stock_exposure"][0]["weight"] == 0.22


def test_ingest_fund_rows_delegates_to_ingestion_service():
    client, ingestion_service = make_client()

    response = client.post(
        "/api/funds/ingest",
        json={
            "dataset": "master",
            "source": "api-test",
            "rows": [{"symbol": "000001.OF", "name": "Alpha Growth"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-1",
        "dataset": "master",
        "fetched": 1,
        "saved": 1,
    }
    assert ingestion_service.calls == [
        ("master", [{"symbol": "000001.OF", "name": "Alpha Growth"}], "api-test")
    ]


def test_main_app_registers_fund_routes():
    from app.api.main import app as main_app

    main_app.dependency_overrides[get_fund_service] = lambda: FakeFundService()
    main_app.dependency_overrides[get_fund_ingestion_service] = lambda: FakeFundIngestionService()
    client = TestClient(main_app)

    try:
        response = client.get("/api/funds/000001.OF")
        assert response.status_code == 200
        assert response.json()["master"]["name"] == "Alpha Growth"
    finally:
        main_app.dependency_overrides.pop(get_fund_service, None)
        main_app.dependency_overrides.pop(get_fund_ingestion_service, None)
