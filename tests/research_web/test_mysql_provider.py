"""Strict MySQL schema and single-table provider contracts."""

import ssl
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.research_web.datahub.connections import MySQLConfiguration
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_mysql import (
    _build_select,
    _connect,
    _invoke,
    _json_value,
    _validate_grants,
)


def table_query(**parameters):
    values = {
        "database": "factor_db",
        "table": "daily_factor",
        "columns": ["trade_date", "code", "bp"],
    }
    values.update(parameters)
    return BusinessQuery(capability="table_query", source="mysql", parameters=values)


@pytest.mark.parametrize(
    "parameters",
    [
        {"sql": "SELECT * FROM factor_db.daily_factor"},
        {"database": "factor_db", "table": "daily_factor", "columns": []},
        {
            "database": "factor_db",
            "table": "daily_factor",
            "columns": ["bp"],
            "filters": [{"column": "bp", "operator": "raw", "value": "1=1"}],
        },
        {
            "database": "factor_db",
            "table": "daily_factor",
            "columns": ["bp"],
            "filters": [{"column": "bp", "operator": "in", "value": list(range(101))}],
        },
        {
            "database": "factor_db",
            "table": "daily_factor",
            "columns": ["bp"],
            "order_by": [{"column": "bp", "direction": "sideways"}],
        },
        {"database": "factor_db", "table": "daily_factor", "columns": ["bp"], "limit": 5001},
        {"database": "factor_db", "table": "daily_factor", "columns": ["bp"], "offset": 100001},
    ],
)
def test_table_query_contract_rejects_raw_or_unbounded_inputs(parameters):
    with pytest.raises(ValueError):
        BusinessQuery(capability="table_query", source="mysql", parameters=parameters)


def test_schema_contract_requires_database_before_table_and_rejects_extra_fields():
    with pytest.raises(ValueError):
        BusinessQuery(capability="database_schema", source="mysql", parameters={"table": "x"})
    with pytest.raises(ValueError):
        BusinessQuery(
            capability="database_schema", source="mysql", parameters={"database": "x", "sql": "x"}
        )


def test_select_builder_quotes_verified_identifiers_and_binds_every_value():
    query = table_query(
        filters=[
            {"column": "bp", "operator": "between", "value": [0.1, 0.5]},
            {"column": "code", "operator": "in", "value": ["600519", "000001"]},
            {"column": "deleted_at", "operator": "is_null"},
        ],
        order_by=[{"column": "trade_date", "direction": "desc"}],
        offset=10,
        limit=20,
    )
    sql, values = _build_select(
        query.parameters, allowed_columns={"trade_date", "code", "bp", "deleted_at"}
    )
    assert sql == (
        "SELECT `trade_date`, `code`, `bp` FROM `factor_db`.`daily_factor` "
        "WHERE `bp` BETWEEN %s AND %s AND `code` IN (%s, %s) AND `deleted_at` IS NULL "
        "ORDER BY `trade_date` DESC LIMIT %s OFFSET %s"
    )
    assert values == [0.1, 0.5, "600519", "000001", 20, 10]


@pytest.mark.parametrize(
    "grant",
    [
        "GRANT INSERT ON factor_db.* TO 'reader'@'%'",
        "GRANT ALL PRIVILEGES ON *.* TO 'reader'@'%'",
        "GRANT SELECT ON factor_db.* TO 'reader'@'%' WITH GRANT OPTION",
        "GRANT PROCESS ON *.* TO 'reader'@'%'",
    ],
)
def test_unsafe_privileges_are_rejected(grant):
    with pytest.raises(ProviderError, match="unsafe_privileges"):
        _validate_grants([(grant,)])


def test_only_usage_select_and_show_view_are_allowed():
    _validate_grants(
        [
            ("GRANT USAGE ON *.* TO 'reader'@'%'",),
            ("GRANT SELECT, SHOW VIEW ON `factor_db`.* TO 'reader'@'%'",),
        ]
    )


def test_stable_json_conversion_preserves_unicode_and_numeric_meaning():
    assert _json_value(Decimal("1.2300")) == "1.2300"
    assert _json_value(date(2026, 9, 8)) == "2026-09-08"
    assert _json_value(datetime(2026, 9, 8, 10, 11, 12, tzinfo=UTC)) == "2026-09-08T10:11:12+00:00"
    assert _json_value(bytes.fromhex("d2f2d7d3")) == "因子"


class FakeCursor:
    def __init__(self, grants):
        self.grants = grants
        self.executed = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, values=None):
        self.executed.append((sql, values))
        if sql == "SHOW GRANTS":
            self.rows = self.grants
        elif "information_schema.SCHEMATA" in sql:
            self.rows = [{"database_name": "factor_db"}, {"database_name": "mysql"}]
        elif "information_schema.TABLES" in sql:
            self.rows = [{"table_name": "daily_factor", "table_type": "BASE TABLE"}]
        elif "information_schema.COLUMNS" in sql:
            self.rows = [
                {
                    "column_name": "code",
                    "column_type": "varchar(6)",
                    "is_nullable": "NO",
                    "column_key": "PRI",
                },
                {
                    "column_name": "bp",
                    "column_type": "decimal(10,4)",
                    "is_nullable": "YES",
                    "column_key": "",
                },
            ]
        elif sql.startswith("SELECT `code`, `bp`"):
            self.rows = [{"code": "600519", "bp": Decimal("0.1234")}]

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, grants):
        self.cursor_value = FakeCursor(grants)
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def local_config():
    return MySQLConfiguration(
        label="因子库",
        host="db.test",
        port=3306,
        user="reader",
        charset="gbk",
        tls_mode="required_no_verify",
    )


def test_connection_requires_tls_without_certificate_verification(monkeypatch):
    import pymysql

    captured = {}
    marker = object()

    def connect(**kwargs):
        captured.update(kwargs)
        return marker

    monkeypatch.setattr(pymysql, "connect", connect)
    assert _connect(local_config(), "secret") is marker
    context = captured.pop("ssl")
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE
    assert captured["password"] == "secret"
    assert captured["charset"] == "gbk"
    assert captured["autocommit"] is False
    assert (
        captured["connect_timeout"] == captured["read_timeout"] == captured["write_timeout"] == 15
    )


def test_query_checks_grants_before_information_schema_or_business_data(monkeypatch):
    import app.research_web.datahub.providers_mysql as provider

    connection = FakeConnection([("GRANT INSERT ON factor_db.* TO 'reader'@'%'",)])
    monkeypatch.setattr(provider, "_connect", lambda *_args: connection)
    with pytest.raises(ProviderError, match="unsafe_privileges"):
        _invoke(table_query(columns=["code", "bp"]), local_config(), "secret")
    assert connection.cursor_value.executed == [("SHOW GRANTS", None)]
    assert connection.rolled_back and connection.closed


def test_single_table_query_uses_verified_schema_and_always_rolls_back(monkeypatch):
    import app.research_web.datahub.providers_mysql as provider

    connection = FakeConnection([("GRANT SELECT, SHOW VIEW ON factor_db.* TO 'reader'@'%'",)])
    monkeypatch.setattr(provider, "_connect", lambda *_args: connection)
    result = _invoke(
        table_query(
            columns=["code", "bp"], filters=[{"column": "bp", "operator": "gte", "value": 0.1}]
        ),
        local_config(),
        "secret",
    )
    assert result.status == "complete"
    assert result.rows == [{"code": "600519", "bp": "0.1234"}]
    assert result.source_url == "mysql://factor_db/daily_factor"
    assert "tls_certificate_unverified" in result.limitations
    business = [
        item
        for item in connection.cursor_value.executed
        if item[0].startswith("SELECT `code`, `bp`")
    ]
    assert business[0][1] == [0.1, 500, 0]
    assert connection.rolled_back and connection.closed


def test_schema_result_above_global_row_limit_is_rejected(monkeypatch):
    import app.research_web.datahub.providers_mysql as provider

    connection = FakeConnection([("GRANT SELECT ON factor_db.* TO 'reader'@'%'",)])
    monkeypatch.setattr(provider, "_connect", lambda *_args: connection)
    monkeypatch.setattr(
        provider, "_fetch_databases", lambda _cursor: [f"db_{index}" for index in range(5001)]
    )
    query = BusinessQuery(capability="database_schema", source="mysql", parameters={})
    with pytest.raises(ProviderError, match="row_limit"):
        _invoke(query, local_config(), "secret")
    assert connection.rolled_back and connection.closed
