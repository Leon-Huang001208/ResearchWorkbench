"""Database bootstrap diagnostics tests."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError


@pytest.mark.parametrize(
    ("dialect", "expected_backend", "expected_guidance", "unexpected_backend"),
    [
        ("postgresql", "PostgreSQL", "pgvector", "SQLite"),
        ("sqlite", "SQLite", "数据库文件", "PostgreSQL"),
    ],
)
def test_database_connection_error_is_dialect_specific_and_sanitized(
    monkeypatch, dialect, expected_backend, expected_guidance, unexpected_backend
):
    from data_layer.repositories import base

    engine = MagicMock()
    engine.dialect.name = dialect
    engine.connect.side_effect = OperationalError(
        "SELECT 1",
        {},
        ConnectionError(
            "cannot reach postgresql://secret-user:super-secret@db.internal:5432/alphafoundry"
        ),
    )
    monkeypatch.setattr(base, "engine", engine)

    with pytest.raises(RuntimeError) as exc_info:
        base.check_database_connection()

    message = str(exc_info.value)
    assert expected_backend in message
    assert expected_guidance in message
    assert unexpected_backend not in message
    assert "secret-user" not in message
    assert "super-secret" not in message
    assert "db.internal" not in message


def test_database_connection_opens_engine_connection():
    from data_layer.repositories.base import check_database_connection

    context_manager = MagicMock()
    with patch(
        "data_layer.repositories.base.engine.connect", return_value=context_manager
    ) as connect:
        check_database_connection()

    connect.assert_called_once_with()
