"""Health endpoint persistence status tests."""

from fastapi.testclient import TestClient

from app.api.main import app
from services.database_readiness import DatabaseReadiness, DatabaseReadinessCode


def test_health_reports_setup_required_without_rechecking_database():
    """Configuration mode remains healthy without revealing or retrying the URL."""
    previous = getattr(app.state, "database_readiness", None)
    app.state.database_readiness = DatabaseReadiness(
        ready=False,
        code=DatabaseReadinessCode.CONNECTION_FAILED,
        message="无法连接到数据库。",
        remediation=("请确认数据库服务已启动且网络配置正确。",),
    )
    try:
        response = TestClient(app).get("/health")
    finally:
        if previous is None:
            delattr(app.state, "database_readiness")
        else:
            app.state.database_readiness = previous

    assert response.status_code == 200
    assert response.json()["persistence"] == {
        "database_connected": False,
        "status": "setup_required",
    }
    assert "secret" not in response.text
    assert "db.internal" not in response.text
