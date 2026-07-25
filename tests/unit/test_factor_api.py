"""Factor API 端点单元测试"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_factor_store():
    """Mock FactorStore to avoid database dependency"""
    with patch("app.api.routes.factors._get_store") as mock_get:
        mock_store = MagicMock()
        mock_store.get_definitions.return_value = []
        mock_store.register_definitions.return_value = 3
        mock_store.get_all_categories.return_value = ["value", "momentum"]
        mock_store.store_values.return_value = 100
        mock_store.load_values.return_value = []
        mock_store.load_values_range.return_value = []
        mock_store.store_evaluations.return_value = 5
        mock_store.load_evaluations.return_value = []
        mock_store.load_latest_weights.return_value = None
        mock_store.store_weights.return_value = 1
        mock_store.load_weights_history.return_value = []
        mock_store.get_available_dates.return_value = [date(2024, 12, 31)]
        mock_get.return_value = mock_store
        yield mock_store


class TestFactorDefinitions:
    def test_list_definitions(self):
        resp = client.get("/api/factors/definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "data" in data

    def test_list_definitions_with_category(self):
        resp = client.get("/api/factors/definitions?category=value")
        assert resp.status_code == 200

    def test_list_definitions_with_factor_ids(self):
        resp = client.get("/api/factors/definitions?factor_ids=pe_ttm,momentum_20d")
        assert resp.status_code == 200

    def test_register_definitions(self):
        payload = [
            {
                "factor_id": "pe_ttm",
                "name": "PE TTM",
                "category": "value",
                "direction": "negative",
                "description": "Trailing PE",
            }
        ]
        resp = client.post("/api/factors/definitions", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_register_definitions_invalid_category(self):
        payload = [
            {
                "factor_id": "bad_factor",
                "name": "Bad",
                "category": "nonexistent",
                "direction": "positive",
            }
        ]
        resp = client.post("/api/factors/definitions", json=payload)
        assert resp.status_code == 422


class TestFactorValues:
    def test_query_values_by_date(self):
        resp = client.get("/api/factors/values?as_of_date=2024-12-31")
        assert resp.status_code == 200

    def test_query_values_by_range(self):
        resp = client.get("/api/factors/values?start_date=2024-01-01&end_date=2024-12-31&limit=100")
        assert resp.status_code == 200

    def test_store_values(self):
        payload = {
            "values": [
                {
                    "factor_id": "pe_ttm",
                    "subject_id": "600519.SH",
                    "as_of_date": "2024-12-31",
                    "value": 25.5,
                    "source": "wind",
                }
            ]
        }
        resp = client.post("/api/factors/values", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestFactorEvaluations:
    def test_query_evaluations(self):
        resp = client.get("/api/factors/evaluations?factor_ids=pe_ttm")
        assert resp.status_code == 200

    def test_store_evaluations(self):
        payload = {
            "evaluations": [
                {
                    "factor_id": "pe_ttm",
                    "as_of_date": "2024-12-31",
                    "horizon_days": 20,
                    "sample_size": 100,
                    "coverage": 0.95,
                    "ic": 0.05,
                    "rank_ic": 0.06,
                    "decile_spread": 0.02,
                }
            ]
        }
        resp = client.post("/api/factors/evaluations", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestDynamicWeights:
    def test_get_latest_weights_empty(self):
        resp = client.get("/api/factors/weights/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] is None

    def test_save_weights(self):
        payload = {
            "as_of_date": "2024-12-31",
            "lookback_periods": 12,
            "metric": "rank_ic",
            "weights": {"pe_ttm": -0.4, "momentum_20d": 0.6},
            "raw_scores": {"pe_ttm": -0.03, "momentum_20d": 0.05},
        }
        resp = client.post("/api/factors/weights", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_get_weights_history(self):
        resp = client.get("/api/factors/weights/history?metric=rank_ic&limit=10")
        assert resp.status_code == 200


class TestUtilityEndpoints:
    def test_get_available_dates(self):
        resp = client.get("/api/factors/available-dates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == ["2024-12-31"]

    def test_get_categories(self):
        resp = client.get("/api/factors/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == ["value", "momentum"]
