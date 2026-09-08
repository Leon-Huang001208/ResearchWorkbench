"""Bounded read-only MySQL provider for user-owned local connection profiles."""

from __future__ import annotations

import asyncio
import json
import ssl
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from core.observability import get_logger

from .contracts import BusinessQuery, DatabaseSchemaParameters, TableQueryParameters
from .providers import MAX_QUERY_BYTES, MAX_ROWS, ProviderError, Result

log = get_logger(__name__)
DEADLINE = 15
SYSTEM_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datahub-mysql")
_CAPACITY = threading.BoundedSemaphore(1)


def _release_capacity(_future: Future) -> None:
    try:
        _CAPACITY.release()
    except ValueError:
        log.error("datahub_mysql_capacity_release_failed")


def _quote(identifier: str) -> str:
    if not identifier or "`" in identifier or "\x00" in identifier:
        raise ProviderError("unknown_identifier")
    return f"`{identifier}`"


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        try:
            return value.decode("gbk")
        except UnicodeDecodeError as exc:
            raise ProviderError("invalid_gbk_value") from exc
    return str(value)


def _validate_grants(rows) -> None:
    allowed = {"USAGE", "SELECT", "SHOW VIEW"}
    if not rows:
        raise ProviderError("unsafe_privileges")
    for row in rows:
        text = str(next(iter(row.values())) if isinstance(row, dict) else row[0]).upper()
        if "GRANT OPTION" in text or "ALL PRIVILEGES" in text or not text.startswith("GRANT "):
            raise ProviderError("unsafe_privileges")
        before_on = text[6:].split(" ON ", 1)[0]
        privileges = {item.strip() for item in before_on.split(",")}
        if not privileges or not privileges.issubset(allowed):
            raise ProviderError("unsafe_privileges")


def _build_select(parameters: dict, *, allowed_columns: set[str]) -> tuple[str, list]:
    request = TableQueryParameters.model_validate(parameters)
    requested = [*request.columns]
    referenced = (
        requested
        + [item.column for item in request.filters]
        + [item.column for item in request.order_by]
    )
    if any(column not in allowed_columns for column in referenced):
        raise ProviderError("unknown_identifier")
    sql = (
        f"SELECT {', '.join(_quote(column) for column in requested)} "
        f"FROM {_quote(request.database)}.{_quote(request.table)}"
    )
    clauses: list[str] = []
    values: list[Any] = []
    comparisons = {"eq": "=", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
    for item in request.filters:
        column = _quote(item.column)
        if item.operator in comparisons:
            clauses.append(f"{column} {comparisons[item.operator]} %s")
            values.append(item.value)
        elif item.operator == "in":
            clauses.append(f"{column} IN ({', '.join('%s' for _ in item.value)})")
            values.extend(item.value)
        elif item.operator == "between":
            clauses.append(f"{column} BETWEEN %s AND %s")
            values.extend(item.value)
        else:
            clauses.append(f"{column} IS {'NOT ' if item.operator == 'not_null' else ''}NULL")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if request.order_by:
        sql += " ORDER BY " + ", ".join(
            f"{_quote(item.column)} {item.direction.upper()}" for item in request.order_by
        )
    sql += " LIMIT %s OFFSET %s"
    values.extend([request.limit, request.offset])
    return sql, values


def _fetch_databases(cursor) -> list[str]:
    cursor.execute(
        "SELECT SCHEMA_NAME AS database_name FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME"
    )
    return [
        str(row["database_name"])
        for row in cursor.fetchall()
        if str(row["database_name"]) not in SYSTEM_DATABASES
    ]


def _fetch_tables(cursor, database: str) -> list[dict]:
    cursor.execute(
        "SELECT TABLE_NAME AS table_name, TABLE_TYPE AS table_type "
        "FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
        (database,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _fetch_columns(cursor, database: str, table: str) -> list[dict]:
    cursor.execute(
        "SELECT COLUMN_NAME AS column_name, COLUMN_TYPE AS column_type, "
        "IS_NULLABLE AS is_nullable, COLUMN_KEY AS column_key "
        "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
        "ORDER BY ORDINAL_POSITION",
        (database, table),
    )
    return [dict(row) for row in cursor.fetchall()]


def _connect(configuration, password):
    try:
        import pymysql
    except ImportError as exc:
        raise ProviderError("dependency_unavailable") from exc
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return pymysql.connect(
        host=configuration.host,
        port=configuration.port,
        user=configuration.user,
        password=password,
        charset=configuration.charset,
        ssl=context,
        connect_timeout=DEADLINE,
        read_timeout=DEADLINE,
        write_timeout=DEADLINE,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _invoke(query: BusinessQuery, configuration, password) -> Result:
    connection = None
    result = Result(
        provider_id="mysql",
        limitations=["tls_certificate_unverified"],
        pages_fetched=1,
        pagination_complete=True,
    )
    try:
        connection = _connect(configuration, password)
        with connection.cursor() as cursor:
            cursor.execute("SHOW GRANTS")
            _validate_grants(cursor.fetchall())
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("START TRANSACTION READ ONLY")
            databases = _fetch_databases(cursor)
            if query.capability == "database_schema":
                request = DatabaseSchemaParameters.model_validate(query.parameters)
                if request.database is None:
                    result.rows = [{"database": value} for value in databases]
                    result.source_url = "mysql://"
                else:
                    if request.database in SYSTEM_DATABASES or request.database not in databases:
                        raise ProviderError("unknown_identifier")
                    tables = _fetch_tables(cursor, request.database)
                    if request.table is None:
                        result.rows = [
                            {
                                "database": request.database,
                                **{key: _json_value(value) for key, value in row.items()},
                            }
                            for row in tables
                        ]
                        result.source_url = f"mysql://{request.database}"
                    else:
                        if request.table not in {str(row["table_name"]) for row in tables}:
                            raise ProviderError("unknown_identifier")
                        columns = _fetch_columns(cursor, request.database, request.table)
                        result.rows = [
                            {
                                "database": request.database,
                                "table": request.table,
                                **{key: _json_value(value) for key, value in row.items()},
                            }
                            for row in columns
                        ]
                        result.source_url = f"mysql://{request.database}/{request.table}"
            else:
                request = TableQueryParameters.model_validate(query.parameters)
                if request.database in SYSTEM_DATABASES or request.database not in databases:
                    raise ProviderError("unknown_identifier")
                tables = _fetch_tables(cursor, request.database)
                if request.table not in {str(row["table_name"]) for row in tables}:
                    raise ProviderError("unknown_identifier")
                columns = _fetch_columns(cursor, request.database, request.table)
                allowed = {str(row["column_name"]) for row in columns}
                sql, values = _build_select(query.parameters, allowed_columns=allowed)
                cursor.execute(sql, values)
                result.rows = [
                    {str(key): _json_value(value) for key, value in row.items()}
                    for row in cursor.fetchall()
                ]
                result.source_url = f"mysql://{request.database}/{request.table}"
            if len(result.rows) > MAX_ROWS:
                raise ProviderError("row_limit")
            raw = json.dumps(result.rows, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(raw) > MAX_QUERY_BYTES:
                raise ProviderError("query_size_limit")
            result.raw = [raw]
            result.raw_bytes = len(raw)
            result.status = "complete" if result.rows else "empty"
            for row in result.rows:
                for key in row:
                    result.fields.setdefault(key, {"unit": None, "currency": None})
            log.info(
                "datahub_mysql_query_completed",
                capability=query.capability,
                row_count=len(result.rows),
            )
            return result
    finally:
        if connection is not None:
            try:
                connection.rollback()
            except Exception as exc:  # noqa: BLE001 - third-party drivers vary by platform
                log.warning("datahub_mysql_rollback_failed", error_type=type(exc).__name__)
            try:
                connection.close()
            except Exception as exc:  # noqa: BLE001 - third-party drivers vary by platform
                log.warning("datahub_mysql_close_failed", error_type=type(exc).__name__)


def _submit(query, configuration, password):
    if not _CAPACITY.acquire(blocking=False):
        return None
    try:
        future = _EXECUTOR.submit(_invoke, query, configuration, password)
    except Exception:
        _CAPACITY.release()
        raise
    future.add_done_callback(_release_capacity)
    return future


async def fetch(query: BusinessQuery, configuration, password) -> Result:
    future = _submit(query, configuration, password)
    if future is None:
        return Result(
            provider_id="mysql",
            status="failed",
            limitations=["provider_busy", "tls_certificate_unverified"],
        )
    try:
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout=DEADLINE)
    except asyncio.CancelledError:
        log.info("datahub_mysql_cancelled")
        raise
    except TimeoutError:
        log.warning("datahub_mysql_incomplete", reason="deadline")
        return Result(
            provider_id="mysql",
            status="failed",
            limitations=["deadline", "tls_certificate_unverified"],
        )
    except ProviderError as exc:
        reason = str(exc)
        log.warning("datahub_mysql_incomplete", reason=reason)
        return Result(
            provider_id="mysql", status="failed", limitations=[reason, "tls_certificate_unverified"]
        )
    except Exception as exc:  # noqa: BLE001 - normalize driver errors without exposing details
        log.warning(
            "datahub_mysql_incomplete", reason="provider_error", error_type=type(exc).__name__
        )
        return Result(
            provider_id="mysql",
            status="failed",
            limitations=["provider_error", "tls_certificate_unverified"],
        )


async def probe(configuration, password) -> dict:
    query = BusinessQuery(capability="database_schema", source="mysql", parameters={})
    result = await fetch(query, configuration, password)
    if result.status == "failed":
        return {"health": "unavailable", "failure_code": result.limitations[0]}
    return {"health": "healthy", "failure_code": None}
