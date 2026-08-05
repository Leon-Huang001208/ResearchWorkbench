"""Desktop database readiness startup and read-only API tests."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.api.routes import setup
from core.settings.runtime import RuntimeContext
from services.database_readiness import DatabaseReadiness, DatabaseReadinessCode

SECRET_DATABASE_URL = "postgresql+psycopg://alice:top-secret@db.internal:5432/private_db"


def _context(mode: str) -> RuntimeContext:
    return RuntimeContext(
        mode=mode,  # type: ignore[arg-type]
        project_root=Path("/tmp/alphafoundry"),
        data_dir=Path("/tmp/alphafoundry") if mode == "desktop" else None,
        env_path=None,
        backend_url="http://127.0.0.1:8765",
        can_write_config=mode != "web-prod",
    )


def _readiness(code: DatabaseReadinessCode) -> DatabaseReadiness:
    details = {
        DatabaseReadinessCode.READY: (True, "数据库连接正常，pgvector 已就绪。", ("无需处理。",)),
        DatabaseReadinessCode.CONNECTION_FAILED: (
            False,
            "无法连接到数据库。",
            ("请确认数据库服务已启动且网络配置正确。",),
        ),
        DatabaseReadinessCode.PGVECTOR_MISSING: (
            False,
            "数据库未启用 pgvector 扩展。",
            ("请在目标数据库中启用 vector 扩展后重试。",),
        ),
    }
    ready, message, remediation = details[code]
    return DatabaseReadiness(ready, code, message, remediation)


@pytest.fixture
def preserve_database_readiness():
    previous = getattr(main.app.state, "database_readiness", None)
    yield
    if previous is None:
        if hasattr(main.app.state, "database_readiness"):
            delattr(main.app.state, "database_readiness")
    else:
        main.app.state.database_readiness = previous


def test_desktop_startup_enters_setup_required_without_schema_or_schedulers(
    monkeypatch, preserve_database_readiness
):
    ensure_schema = MagicMock()
    start_schedulers = MagicMock()
    start_wind = MagicMock()
    start_runtime = MagicMock()
    monkeypatch.setattr(
        main, "probe_postgresql", lambda *_: _readiness(DatabaseReadinessCode.PGVECTOR_MISSING)
    )
    monkeypatch.setattr(main, "ensure_schema", ensure_schema)
    monkeypatch.setattr(main, "_start_data_acquisition_schedulers", start_schedulers)
    monkeypatch.setattr(main, "_start_wind_workbook_background", start_wind)
    monkeypatch.setattr(main, "_start_resource_monitor_runtime", start_runtime)
    monkeypatch.setattr(main, "RUNTIME_CONTEXT", _context("desktop"))

    asyncio.run(main.startup())

    assert main.app.state.database_readiness.code is DatabaseReadinessCode.PGVECTOR_MISSING
    ensure_schema.assert_not_called()
    start_schedulers.assert_not_called()
    start_wind.assert_not_called()
    start_runtime.assert_not_called()


@pytest.mark.parametrize("mode", ["web-dev", "web-prod"])
def test_web_startup_reraises_database_readiness_failure(
    monkeypatch, preserve_database_readiness, mode
):
    monkeypatch.setattr(
        main, "probe_postgresql", lambda *_: _readiness(DatabaseReadinessCode.CONNECTION_FAILED)
    )
    monkeypatch.setattr(main, "RUNTIME_CONTEXT", _context(mode))

    with pytest.raises(RuntimeError, match="无法连接 PostgreSQL"):
        asyncio.run(main.startup())


def test_desktop_startup_initializes_schema_and_automatic_services_when_ready(
    monkeypatch, preserve_database_readiness
):
    ensure_schema = MagicMock()
    start_schedulers = MagicMock()
    start_wind = MagicMock()
    start_runtime = MagicMock()
    monkeypatch.setattr(
        main, "probe_postgresql", lambda *_: _readiness(DatabaseReadinessCode.READY)
    )
    monkeypatch.setattr(main, "ensure_schema", ensure_schema)
    monkeypatch.setattr(main, "_start_data_acquisition_schedulers", start_schedulers)
    monkeypatch.setattr(main, "_start_wind_workbook_background", start_wind)
    monkeypatch.setattr(main, "_start_resource_monitor_runtime", start_runtime)
    monkeypatch.setattr(main, "RUNTIME_CONTEXT", _context("desktop"))

    asyncio.run(main.startup())

    assert main.app.state.database_readiness.ready is True
    ensure_schema.assert_called_once_with()
    start_schedulers.assert_called_once_with()
    start_wind.assert_called_once_with()
    start_runtime.assert_called_once_with()


def test_desktop_preview_skips_database_initialization_and_automatic_services(
    monkeypatch, preserve_database_readiness
):
    ensure_schema = MagicMock()
    start_schedulers = MagicMock()
    start_wind = MagicMock()
    start_runtime = MagicMock()
    monkeypatch.setattr(
        main, "probe_postgresql", lambda *_: _readiness(DatabaseReadinessCode.READY)
    )
    monkeypatch.setattr(main, "ensure_schema", ensure_schema)
    monkeypatch.setattr(main, "_start_data_acquisition_schedulers", start_schedulers)
    monkeypatch.setattr(main, "_start_wind_workbook_background", start_wind)
    monkeypatch.setattr(main, "_start_resource_monitor_runtime", start_runtime)
    monkeypatch.setattr(main, "RUNTIME_CONTEXT", _context("desktop"))
    monkeypatch.setenv("ALPHAFOUNDRY_PREVIEW", "1")

    asyncio.run(main.startup())

    assert main.app.state.database_readiness.ready is True
    ensure_schema.assert_not_called()
    start_schedulers.assert_not_called()
    start_wind.assert_not_called()
    start_runtime.assert_not_called()


def test_shutdown_stops_resource_monitor_before_other_schedulers(monkeypatch) -> None:
    call_order: list[str] = []
    monkeypatch.setattr(
        main, "_stop_resource_monitor_runtime", lambda: call_order.append("runtime")
    )
    monkeypatch.setattr(
        main,
        "_stop_data_acquisition_schedulers",
        lambda: call_order.append("schedulers"),
    )

    main.shutdown()

    assert call_order == ["runtime", "schedulers"]


def test_setup_readiness_returns_safe_restart_required_status(
    monkeypatch, preserve_database_readiness
):
    main.app.state.database_readiness = _readiness(DatabaseReadinessCode.PGVECTOR_MISSING)
    monkeypatch.setattr(setup, "RUNTIME_CONTEXT", _context("desktop"))
    monkeypatch.setattr(
        setup, "probe_postgresql", lambda *_: _readiness(DatabaseReadinessCode.READY)
    )

    response = TestClient(main.app).get(
        "/api/setup/readiness",
        headers={"Origin": "tauri://localhost"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "runtime_status": "setup_required",
        "database": {
            "ready": True,
            "code": "ready",
            "message": "数据库连接正常，pgvector 已就绪。",
            "remediation": ["无需处理。"],
        },
        "restart_required": True,
    }
    for sensitive_text in ("alice", "top-secret", "db.internal", "5432", "private_db"):
        assert sensitive_text not in response.text


def test_setup_readiness_is_disabled_in_web_production(monkeypatch):
    monkeypatch.setattr(
        "core.settings.runtime.resolve_runtime_context", lambda: _context("web-prod")
    )

    response = TestClient(main.app).get("/api/setup/readiness")

    assert response.status_code == 404
