"""Health endpoint persistence status tests."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app


def test_health_hides_database_exception_details():
    session = MagicMock()
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    session.execute.side_effect = RuntimeError(
        "postgresql://user:secret@db.internal:5432/alphafoundry"
    )

    with patch("data_layer.repositories.base.SessionLocal", return_value=session):
        response = TestClient(app).get("/health")

    persistence = response.json()["persistence"]
    assert persistence["database_connected"] is False
    assert persistence["status"] == "unavailable"
    assert "secret" not in response.text
    assert "db.internal" not in response.text
