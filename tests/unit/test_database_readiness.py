"""PostgreSQL + pgvector readiness probe tests."""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest
from psycopg.errors import InvalidCatalogName
from sqlalchemy.exc import OperationalError

from services import database_readiness


SECRET_DATABASE_URL = "postgresql+psycopg://alice:top-secret@db.internal:5432/private_db"
EXPECTED_CODES = {
    "ready",
    "invalid_url",
    "connection_failed",
    "database_unavailable",
    "pgvector_missing",
    "btree_gist_missing",
    "unexpected_error",
}


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _Connection:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement):
        self.statements.append(str(statement))
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return _Result(response)


class _Engine:
    def __init__(self, responses):
        self.connection = _Connection(responses)
        self.disposed = False

    def connect(self):
        return self.connection

    def dispose(self):
        self.disposed = True


def _assert_safe_result(result):
    rendered = f"{result!r}|{result.message}|{result.remediation}"
    for sensitive_text in ("alice", "top-secret", "db.internal", "5432", "private_db"):
        assert sensitive_text not in rendered
    assert result.code.value in EXPECTED_CODES
    assert isinstance(result.remediation, tuple)
    assert all(isinstance(item, str) for item in result.remediation)


def test_public_api_exposes_enum_and_frozen_readiness_result():
    """Callers receive the agreed Enum-backed immutable result contract."""
    assert database_readiness.DatabaseReadinessCode.READY.value == "ready"
    assert database_readiness.DatabaseReadiness.__dataclass_params__.frozen is True


def test_probe_reports_ready_after_connectivity_and_pgvector_checks(monkeypatch):
    """A reachable database with pgvector reports the immutable ready result."""
    engine = _Engine([None, 1, "vector", "btree_gist"])
    create_engine = MagicMock(return_value=engine)
    safe_logger = MagicMock()
    monkeypatch.setattr(database_readiness, "create_engine", create_engine)
    monkeypatch.setattr(database_readiness, "logger", safe_logger)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL)

    assert result.code is database_readiness.DatabaseReadinessCode.READY
    assert result.ready is True
    assert result.message == "数据库连接正常，必需扩展已就绪。"
    assert result.remediation == ("无需处理。",)
    assert engine.connection.statements == [
        "SET LOCAL statement_timeout = 5000",
        "SELECT 1",
        "SELECT 1 FROM pg_extension WHERE extname = 'vector'",
        "SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'",
    ]
    assert engine.disposed is True
    assert create_engine.call_args.args == (SECRET_DATABASE_URL,)
    assert create_engine.call_args.kwargs["connect_args"] == {"connect_timeout": 5}
    assert create_engine.call_args.kwargs["pool_pre_ping"] is True
    assert create_engine.call_args.kwargs["poolclass"] is database_readiness.NullPool
    log_args, log_kwargs = safe_logger.info.call_args
    assert log_args
    assert set(log_kwargs) == {"stage", "error_type", "platform"}
    _assert_safe_result(result)
    with pytest.raises(FrozenInstanceError):
        result.code = database_readiness.DatabaseReadinessCode.CONNECTION_FAILED


def test_probe_uses_a_verified_numeric_server_statement_timeout(monkeypatch):
    """The query timeout is generated only from a validated numeric API argument."""
    engine = _Engine([None, 1, "vector", "btree_gist"])
    create_engine = MagicMock(return_value=engine)
    monkeypatch.setattr(database_readiness, "create_engine", create_engine)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL, timeout_seconds=2.5)

    assert result.code is database_readiness.DatabaseReadinessCode.READY
    assert engine.connection.statements[0] == "SET LOCAL statement_timeout = 2500"
    assert create_engine.call_args.kwargs["connect_args"] == {"connect_timeout": 3}


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://alice:top-secret@db.internal:5432/private_db",
        "postgresql+psycopg://alice:top-secret@/private_db",
        "postgresql+psycopg://alice:top-secret@db.internal:5432/",
        "postgresql+psycopg://alice:top-secret@db.internal:not-a-port/private_db",
        "sqlite:///tmp/private.db",
        "not a database url",
    ],
)
def test_probe_rejects_malformed_or_unsupported_urls_before_creating_an_engine(
    monkeypatch, database_url
):
    """SQLAlchemy URL parsing enforces the psycopg3 scheme, host, and database name."""
    create_engine = MagicMock()
    monkeypatch.setattr(database_readiness, "create_engine", create_engine)

    result = database_readiness.probe_postgresql(database_url)

    assert result.code is database_readiness.DatabaseReadinessCode.INVALID_URL
    assert result.ready is False
    assert result.message == "数据库连接地址无效。"
    assert result.remediation == ("请填写 PostgreSQL 连接地址。",)
    create_engine.assert_not_called()
    _assert_safe_result(result)


def test_probe_reports_a_create_engine_exception_without_leaking_details(monkeypatch):
    """Driver or dialect creation errors use the connection-failed response safely."""
    create_engine = MagicMock(
        side_effect=OperationalError("connect", None, ValueError("alice top-secret"))
    )
    monkeypatch.setattr(database_readiness, "create_engine", create_engine)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL)

    assert result.code is database_readiness.DatabaseReadinessCode.CONNECTION_FAILED
    assert result.ready is False
    assert result.message == "无法连接到数据库。"
    assert result.remediation == ("请确认数据库服务已启动且网络配置正确。",)
    _assert_safe_result(result)


def test_probe_reports_connection_failure_and_disposes_engine(monkeypatch):
    """Ordinary SQLAlchemy connectivity failures are safe and recoverable."""
    engine = _Engine([None, OperationalError("connect", None, ValueError("top-secret"))])
    monkeypatch.setattr(database_readiness, "create_engine", lambda *args, **kwargs: engine)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL)

    assert result.code is database_readiness.DatabaseReadinessCode.CONNECTION_FAILED
    assert result.ready is False
    assert engine.disposed is True
    _assert_safe_result(result)


def test_probe_identifies_a_missing_target_database_from_psycopg_sqlstate(monkeypatch):
    """psycopg's SQLSTATE 3D000 maps to the distinct database-unavailable code."""
    engine = _Engine([None, OperationalError("connect", None, InvalidCatalogName("top-secret"))])
    monkeypatch.setattr(database_readiness, "create_engine", lambda *args, **kwargs: engine)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL)

    assert result.code is database_readiness.DatabaseReadinessCode.DATABASE_UNAVAILABLE
    assert result.ready is False
    assert result.message == "目标数据库不可用。"
    assert result.remediation == ("请确认数据库名称已创建且配置正确。",)
    assert engine.disposed is True
    _assert_safe_result(result)


def test_probe_reports_missing_pgvector_and_disposes_engine(monkeypatch):
    """A database without the vector extension receives precise remediation."""
    engine = _Engine([None, 1, None])
    monkeypatch.setattr(database_readiness, "create_engine", lambda *args, **kwargs: engine)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL)

    assert result.code is database_readiness.DatabaseReadinessCode.PGVECTOR_MISSING
    assert result.ready is False
    assert result.message == "数据库未启用 pgvector 扩展。"
    assert result.remediation == ("请在目标数据库中启用 vector 扩展后重试。",)
    assert engine.disposed is True
    _assert_safe_result(result)


def test_probe_reports_missing_btree_gist_and_disposes_engine(monkeypatch):
    """GiST text constraints require btree_gist before schema creation begins."""
    engine = _Engine([None, 1, "vector", None])
    monkeypatch.setattr(database_readiness, "create_engine", lambda *args, **kwargs: engine)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL)

    assert result.code is database_readiness.DatabaseReadinessCode.BTREE_GIST_MISSING
    assert result.ready is False
    assert result.message == "数据库未启用 btree_gist 扩展。"
    assert result.remediation == ("请在目标数据库中启用 btree_gist 扩展后重试。",)
    assert engine.disposed is True
    _assert_safe_result(result)


def test_probe_hides_unexpected_errors_and_disposes_engine(monkeypatch):
    """Unexpected errors remain safe for HTTP callers and still release the engine."""
    engine = _Engine([None, RuntimeError("alice top-secret db.internal:5432/private_db")])
    monkeypatch.setattr(database_readiness, "create_engine", lambda *args, **kwargs: engine)

    result = database_readiness.probe_postgresql(SECRET_DATABASE_URL)

    assert result.code is database_readiness.DatabaseReadinessCode.UNEXPECTED_ERROR
    assert result.ready is False
    assert result.message == "数据库预检发生未知错误。"
    assert result.remediation == ("请检查本地数据库配置后重试。",)
    assert engine.disposed is True
    _assert_safe_result(result)
