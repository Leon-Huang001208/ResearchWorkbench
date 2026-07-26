"""无副作用的 PostgreSQL 与 pgvector 就绪预检。"""

from __future__ import annotations

import math
import platform
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from core.observability import get_logger

try:
    from psycopg.errors import InvalidCatalogName

    _PSYCOPG_DATABASE_UNAVAILABLE_ERRORS: tuple[type[BaseException], ...] = (
        InvalidCatalogName,
    )
except ImportError:  # pragma: no cover - psycopg is a project dependency in production.
    _PSYCOPG_DATABASE_UNAVAILABLE_ERRORS = ()


logger = get_logger(__name__)

__all__ = ["DatabaseReadiness", "DatabaseReadinessCode", "probe_postgresql"]

_POSTGRESQL_PSYCOPG_DRIVER = "postgresql+psycopg"
_DATABASE_UNAVAILABLE_SQLSTATE = "3D000"
_DEFAULT_TIMEOUT_SECONDS = 5.0
_MAX_TIMEOUT_SECONDS = 3600.0
_PGVECTOR_QUERY = "SELECT 1 FROM pg_extension WHERE extname = 'vector'"


class DatabaseReadinessCode(str, Enum):
    """数据库预检的稳定、可序列化状态码。"""

    READY = "ready"
    INVALID_URL = "invalid_url"
    CONNECTION_FAILED = "connection_failed"
    DATABASE_UNAVAILABLE = "database_unavailable"
    PGVECTOR_MISSING = "pgvector_missing"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True, slots=True)
class DatabaseReadiness:
    """可直接暴露给 HTTP 调用方的脱敏预检结果。"""

    ready: bool
    code: DatabaseReadinessCode
    message: str
    remediation: tuple[str, ...]


_RESULT_DETAILS: dict[DatabaseReadinessCode, tuple[bool, str, tuple[str, ...]]] = {
    DatabaseReadinessCode.READY: (True, "数据库连接正常，pgvector 已就绪。", ("无需处理。",)),
    DatabaseReadinessCode.INVALID_URL: (
        False,
        "数据库连接地址无效。",
        ("请填写 PostgreSQL 连接地址。",),
    ),
    DatabaseReadinessCode.CONNECTION_FAILED: (
        False,
        "无法连接到数据库。",
        ("请确认数据库服务已启动且网络配置正确。",),
    ),
    DatabaseReadinessCode.DATABASE_UNAVAILABLE: (
        False,
        "目标数据库不可用。",
        ("请确认数据库名称已创建且配置正确。",),
    ),
    DatabaseReadinessCode.PGVECTOR_MISSING: (
        False,
        "数据库未启用 pgvector 扩展。",
        ("请在目标数据库中启用 vector 扩展后重试。",),
    ),
    DatabaseReadinessCode.UNEXPECTED_ERROR: (
        False,
        "数据库预检发生未知错误。",
        ("请检查本地数据库配置后重试。",),
    ),
}


def probe_postgresql(
    database_url: str,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> DatabaseReadiness:
    """验证 psycopg3 PostgreSQL 连接与 pgvector，不写入数据库或修改配置。"""
    if not _is_supported_database_url(database_url):
        return _result(
            DatabaseReadinessCode.INVALID_URL,
            stage="url_validation",
            error_type="InvalidUrl",
        )

    try:
        connect_timeout, statement_timeout_ms = _validated_timeouts(timeout_seconds)
    except (TypeError, ValueError):
        return _result(
            DatabaseReadinessCode.UNEXPECTED_ERROR,
            stage="timeout_validation",
            error_type="InvalidTimeout",
        )

    engine = None
    result: DatabaseReadiness | None = None
    try:
        engine = create_engine(
            database_url,
            connect_args={"connect_timeout": connect_timeout},
            pool_pre_ping=True,
            poolclass=NullPool,
        )
        with engine.connect() as connection:
            connection.execute(text(f"SET LOCAL statement_timeout = {statement_timeout_ms}"))
            connection.execute(text("SELECT 1"))
            has_pgvector = connection.execute(text(_PGVECTOR_QUERY)).scalar() is not None
        result = _result(
            DatabaseReadinessCode.READY
            if has_pgvector
            else DatabaseReadinessCode.PGVECTOR_MISSING,
            stage="pgvector",
            error_type="None",
        )
    except Exception as exc:
        if _is_database_unavailable(exc):
            result = _result(
                DatabaseReadinessCode.DATABASE_UNAVAILABLE,
                stage="connection",
                error_type=type(_root_exception(exc)).__name__,
            )
        elif isinstance(exc, SQLAlchemyError):
            result = _result(
                DatabaseReadinessCode.CONNECTION_FAILED,
                stage="connection",
                error_type=type(exc).__name__,
            )
        else:
            result = _result(
                DatabaseReadinessCode.UNEXPECTED_ERROR,
                stage="unexpected",
                error_type=type(exc).__name__,
            )
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception as exc:  # pragma: no cover - defensive cleanup path.
                _log(stage="dispose", error_type=type(exc).__name__)
                if result is None or result.ready:
                    result = _result(
                        DatabaseReadinessCode.UNEXPECTED_ERROR,
                        stage="dispose",
                        error_type=type(exc).__name__,
                    )

    return result or _result(
        DatabaseReadinessCode.UNEXPECTED_ERROR,
        stage="unexpected",
        error_type="Unknown",
    )


def _is_supported_database_url(database_url: object) -> bool:
    """使用 SQLAlchemy URL 解析严格校验 psycopg3 PostgreSQL 连接地址。"""
    if not isinstance(database_url, str):
        return False
    try:
        parsed_url = make_url(database_url)
        port = parsed_url.port
    except (ArgumentError, TypeError, ValueError):
        return False
    return (
        parsed_url.drivername == _POSTGRESQL_PSYCOPG_DRIVER
        and bool(parsed_url.host and parsed_url.host.strip())
        and bool(parsed_url.database and parsed_url.database.strip())
        and (port is None or port > 0)
    )


def _validated_timeouts(timeout_seconds: object) -> tuple[int, int]:
    """验证超时为有限正数，再生成仅含十进制数字的 SQL 超时值。"""
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise TypeError("timeout_seconds must be numeric")
    seconds = float(timeout_seconds)
    if not math.isfinite(seconds) or not 0 < seconds <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout_seconds is outside the allowed range")
    return math.ceil(seconds), max(1, math.floor(seconds * 1000))


def _is_database_unavailable(exc: BaseException) -> bool:
    """用 psycopg3 类型或 SQLSTATE 3D000 识别不存在的目标数据库。"""
    root = _root_exception(exc)
    if isinstance(root, _PSYCOPG_DATABASE_UNAVAILABLE_ERRORS):
        return True
    return getattr(root, "sqlstate", None) == _DATABASE_UNAVAILABLE_SQLSTATE or getattr(
        root, "pgcode", None
    ) == _DATABASE_UNAVAILABLE_SQLSTATE


def _root_exception(exc: BaseException) -> BaseException:
    """解开 SQLAlchemy 的 ``orig`` 包装，最多三层以避免异常链循环。"""
    current = exc
    for _ in range(3):
        original = getattr(current, "orig", None)
        if not isinstance(original, BaseException) or original is current:
            break
        current = original
    return current


def _result(
    code: DatabaseReadinessCode,
    *,
    stage: str,
    error_type: str,
) -> DatabaseReadiness:
    """构造固定脱敏响应，并以安全的结构化字段记录预检状态。"""
    _log(stage=stage, error_type=error_type)
    ready, message, remediation = _RESULT_DETAILS[code]
    return DatabaseReadiness(
        ready=ready,
        code=code,
        message=message,
        remediation=remediation,
    )


def _log(*, stage: str, error_type: str) -> None:
    """仅记录允许的诊断维度，绝不记录连接地址或异常文本。"""
    logger.info(
        "数据库预检完成",
        stage=stage,
        error_type=error_type,
        platform=platform.system(),
    )
