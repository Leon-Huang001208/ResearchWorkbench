"""Schema and Alembic tests for the merged platform's 20 additive tables."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Column, MetaData, Table, Text, create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex

from data_layer.repositories.base import Base

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "storage" / "migrations" / "versions"
EXPECTED_BY_REVISION = {
    "015": {
        "asset_registry",
        "asset_identifier",
        "theme_observation",
        "scheduled_job",
        "domain_event",
    },
    "016": {"theme_pack", "market_home_snapshot"},
    "017": {
        "research_workspace",
        "research_session",
        "research_message",
        "runtime_provider",
        "skill_definition",
        "agent_team",
        "agent_schedule",
        "research_note",
    },
    "018": {
        "watchlist",
        "watchlist_item",
        "alert_rule",
        "alert_event",
        "notification",
    },
}
MIGRATION_FILES = {
    "015": MIGRATIONS / "015_add_platform_fact_core.py",
    "016": MIGRATIONS / "016_add_theme_and_market_home.py",
    "017": MIGRATIONS / "017_add_research_workspace_runtime.py",
    "018": MIGRATIONS / "018_add_asset_observation.py",
}


def _load_migration(revision: str):
    path = MIGRATION_FILES[revision]
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_four_migrations_create_exactly_the_approved_twenty_tables():
    found: set[str] = set()
    for revision, expected in EXPECTED_BY_REVISION.items():
        source = MIGRATION_FILES[revision].read_text(encoding="utf-8")
        created = set(re.findall(r'op\.create_table\(\s*"([^"]+)"', source))
        assert created == expected
        found.update(expected)

    assert len(found) == 20
    assert not {
        "source_ref",
        "research_run_v2",
        "stock_fact",
        "index_fact",
        "etf_fact",
        "fund_fact",
        "theme_kpi_series",
        "theme_value_chain",
    }.intersection(found)


def test_merged_migrations_form_a_single_015_to_018_chain():
    expected_down = {"015": "014", "016": "015", "017": "016", "018": "017"}
    for revision, down_revision in expected_down.items():
        module = _load_migration(revision)
        assert module.revision == revision
        assert module.down_revision == down_revision


def test_orm_metadata_contains_exact_merged_table_set_and_builds_on_sqlite():
    expected = set().union(*EXPECTED_BY_REVISION.values())
    assert expected.issubset(Base.metadata.tables)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    try:
        assert expected.issubset(set(inspect(engine).get_table_names()))
    finally:
        Base.metadata.drop_all(bind=engine)


def test_identity_note_and_watchlist_foreign_keys_are_explicit():
    identifiers = Base.metadata.tables["asset_identifier"]
    watchlist_items = Base.metadata.tables["watchlist_item"]
    notes = Base.metadata.tables["research_note"]

    assert {fk.target_fullname for fk in identifiers.foreign_keys} == {"asset_registry.asset_id"}
    assert {fk.target_fullname for fk in watchlist_items.foreign_keys} == {
        "asset_registry.asset_id",
        "watchlist.watchlist_id",
    }
    assert {fk.target_fullname for fk in notes.foreign_keys} == {
        "research_claim.claim_id",
        "research_run.run_id",
        "research_workspace.workspace_id",
    }
    assert "workspace_id" not in Base.metadata.tables["research_message"].c
    assert any(
        constraint.name == "ck_research_note_source_shape" for constraint in notes.constraints
    )
    assert any(
        constraint.name == "ck_asset_identifier_valid_window"
        for constraint in identifiers.constraints
    )
    assert any(
        constraint.name == "ex_asset_identifier_no_overlap"
        for constraint in identifiers.constraints
    )


def test_new_tables_define_identity_constraints_and_time_indexes():
    asset_identifier = Base.metadata.tables["asset_identifier"]
    observation = Base.metadata.tables["theme_observation"]
    domain_event = Base.metadata.tables["domain_event"]
    notification = Base.metadata.tables["notification"]

    identifier_unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in asset_identifier.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("scheme", "value", "market", "valid_from") in identifier_unique_columns
    assert observation.c.observed_at.index is True
    assert domain_event.c.occurred_at.index is True
    assert notification.c.created_at.index is True


def test_active_alert_event_partial_unique_index_is_declared_for_sqlite_and_postgresql():
    alert_event = Base.metadata.tables["alert_event"]
    index = next(item for item in alert_event.indexes if item.name == "uq_alert_event_rule_active")

    assert index.unique is True
    assert [column.name for column in index.columns] == ["rule_id"]
    assert "status IN ('open', 'acknowledged')" in str(index.dialect_options["sqlite"]["where"])
    postgresql_ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "CREATE UNIQUE INDEX uq_alert_event_rule_active" in postgresql_ddl
    assert "WHERE status IN ('open', 'acknowledged')" in postgresql_ddl


def test_scheduler_and_research_invariants_have_named_database_constraints():
    expected_by_table = {
        "scheduled_job": {
            "ck_scheduled_job_allow_concurrent_false",
            "ck_scheduled_job_coalesce_latest",
            "ck_scheduled_job_lease_pair",
        },
        "agent_schedule": {
            "ck_agent_schedule_allow_concurrent_false",
            "ck_agent_schedule_coalesce_latest",
        },
        "research_session": {"ck_research_session_scope"},
        "research_message": {"ck_research_message_content_source"},
    }
    for table_name, expected_names in expected_by_table.items():
        actual_names = {
            constraint.name for constraint in Base.metadata.tables[table_name].constraints
        }
        assert expected_names.issubset(actual_names)


def test_015_to_018_upgrade_and_downgrade_on_sqlite(tmp_path: Path):
    database_path = tmp_path / "merged.sqlite"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url)
    prerequisite_metadata = MetaData()
    Table("research_run", prerequisite_metadata, Column("run_id", Text, primary_key=True))
    Table(
        "research_claim",
        prerequisite_metadata,
        Column("claim_id", Text, primary_key=True),
        Column("run_id", Text, nullable=False),
    )
    prerequisite_metadata.create_all(engine)

    config = Config(str(ROOT / "storage" / "migrations" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "storage" / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.stamp(config, "014")
    command.upgrade(config, "018")

    expected = set().union(*EXPECTED_BY_REVISION.values())
    assert expected.issubset(set(inspect(engine).get_table_names()))

    with engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO asset_registry (asset_id, asset_type, canonical_name)
                VALUES ('asset-1', 'stock', 'Asset 1')
                """))
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-1', 'asset-1', 'wind', '600000.SH', 'CN',
                    '2026-01-01T00:00:00+00:00', '2026-02-01T00:00:00+00:00'
                )
                """))
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-adjacent', 'asset-1', 'wind', '600000.SH', 'CN',
                    '2026-02-01T00:00:00+00:00', '2026-03-01T00:00:00+00:00'
                )
                """))

    with (
        pytest.raises(IntegrityError, match="asset_identifier validity overlap"),
        engine.begin() as connection,
    ):
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-overlap', 'asset-1', 'wind', '600000.SH', 'CN',
                    '2026-01-15T00:00:00+00:00', '2026-01-20T00:00:00+00:00'
                )
                """))

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-reversed', 'asset-1', 'wind', '600001.SH', 'CN',
                    '2026-02-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
                )
                """))

    with (
        pytest.raises(IntegrityError, match="asset_identifier validity overlap"),
        engine.begin() as connection,
    ):
        connection.execute(text("""
                UPDATE asset_identifier
                SET valid_from = '2026-01-15T00:00:00+00:00'
                WHERE identifier_id = 'identifier-adjacent'
                """))

    with engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO scheduled_job (
                    job_id, owner, job_type, idempotency_key, scheduled_for
                ) VALUES (
                    'job-valid', 'scheduler', 'refresh', 'job-valid-key',
                    '2026-08-31T09:30:00+00:00'
                )
                """))
        connection.execute(text("""
                INSERT INTO scheduled_job (
                    job_id, owner, job_type, idempotency_key, scheduled_for,
                    lease_owner, lease_expires_at
                ) VALUES (
                    'job-leased', 'scheduler', 'refresh', 'job-leased-key',
                    '2026-08-31T09:30:00+00:00', 'worker-1',
                    '2026-08-31T09:35:00+00:00'
                )
                """))

    invalid_job_sql = [
        """
        INSERT INTO scheduled_job (
            job_id, owner, job_type, idempotency_key, scheduled_for, allow_concurrent
        ) VALUES (
            'job-concurrent', 'scheduler', 'refresh', 'job-concurrent-key',
            '2026-08-31T09:30:00+00:00', 1
        )
        """,
        """
        INSERT INTO scheduled_job (
            job_id, owner, job_type, idempotency_key, scheduled_for, coalesce_policy
        ) VALUES (
            'job-coalesce-all', 'scheduler', 'refresh', 'job-coalesce-key',
            '2026-08-31T09:30:00+00:00', 'all'
        )
        """,
        """
        INSERT INTO scheduled_job (
            job_id, owner, job_type, idempotency_key, scheduled_for, lease_owner
        ) VALUES (
            'job-half-lease', 'scheduler', 'refresh', 'job-half-lease-key',
            '2026-08-31T09:30:00+00:00', 'worker-1'
        )
        """,
    ]
    for invalid_sql in invalid_job_sql:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(invalid_sql))

    with engine.begin() as connection:
        connection.execute(text("INSERT INTO research_run (run_id) VALUES ('run-1')"))
        connection.execute(text("""
                INSERT INTO research_claim (claim_id, run_id)
                VALUES ('claim-1', 'run-1')
                """))
        connection.execute(text("""
                INSERT INTO research_workspace (
                    workspace_id, project_id, title, status
                ) VALUES ('workspace-1', 'project-1', 'Workspace', 'active')
                """))
        connection.execute(text("""
                INSERT INTO research_session (
                    session_id, workspace_id, mode, idempotency_key
                ) VALUES (
                    'session-workspace', 'workspace-1', 'workspace', 'session-workspace-key'
                )
                """))
        connection.execute(text("""
                INSERT INTO research_session (
                    session_id, mode, idempotency_key
                ) VALUES (
                    'session-temporary', 'temporary', 'session-temporary-key'
                )
                """))
        connection.execute(text("""
                INSERT INTO research_message (
                    message_id, session_id, role, content, idempotency_key
                ) VALUES (
                    'message-content', 'session-temporary', 'user', 'hello',
                    'message-content-key'
                )
                """))
        connection.execute(text("""
                INSERT INTO research_message (
                    message_id, session_id, role, content_ref, idempotency_key
                ) VALUES (
                    'message-ref', 'session-temporary', 'user', 'attachment:1',
                    'message-ref-key'
                )
                """))
        connection.execute(text("""
                INSERT INTO agent_team (
                    team_id, workspace_id, name, supervisor_role
                ) VALUES (
                    'team-1', 'workspace-1', 'Team', 'supervisor'
                )
                """))
        connection.execute(text("""
                INSERT INTO agent_schedule (
                    schedule_id, team_id, cron_expression, status
                ) VALUES (
                    'schedule-valid', 'team-1', '0 9 * * 1-5', 'active'
                )
                """))
        connection.execute(text("""
                INSERT INTO research_note (
                    note_id, note_key, workspace_id, claim_id, revision,
                    source_kind, summary
                ) VALUES (
                    'note-claim', 'claim-note', 'workspace-1', 'claim-1', 1,
                    'claim', 'valid claim note'
                )
                """))
        connection.execute(text("""
                INSERT INTO research_note (
                    note_id, note_key, workspace_id, run_id, revision,
                    source_kind, paragraph_ref, summary
                ) VALUES (
                    'note-paragraph', 'paragraph-note', 'workspace-1', 'run-1', 1,
                    'paragraph', 'artifact:1#p2', 'valid paragraph note'
                )
                """))

    invalid_research_sql = [
        """
        INSERT INTO research_session (
            session_id, workspace_id, mode, idempotency_key
        ) VALUES (
            'session-workspace-blank-scope', '   ', 'workspace',
            'session-invalid-blank-workspace-key'
        )
        """,
        """
        INSERT INTO research_session (
            session_id, mode, idempotency_key
        ) VALUES (
            'session-workspace-without-scope', 'workspace', 'session-invalid-workspace-key'
        )
        """,
        """
        INSERT INTO research_session (
            session_id, workspace_id, mode, idempotency_key
        ) VALUES (
            'session-temporary-with-scope', 'workspace-1', 'temporary',
            'session-invalid-temporary-key'
        )
        """,
        """
        INSERT INTO research_message (
            message_id, session_id, role, content, content_ref, idempotency_key
        ) VALUES (
            'message-both', 'session-temporary', 'user', 'hello', 'attachment:1',
            'message-both-key'
        )
        """,
        """
        INSERT INTO research_message (
            message_id, session_id, role, idempotency_key
        ) VALUES (
            'message-neither', 'session-temporary', 'user', 'message-neither-key'
        )
        """,
        """
        INSERT INTO research_message (
            message_id, session_id, role, content, idempotency_key
        ) VALUES (
            'message-empty', 'session-temporary', 'user', '   ', 'message-empty-key'
        )
        """,
        """
        INSERT INTO agent_schedule (
            schedule_id, team_id, cron_expression, status, allow_concurrent
        ) VALUES (
            'schedule-concurrent', 'team-1', '0 9 * * 1-5', 'active', 1
        )
        """,
        """
        INSERT INTO agent_schedule (
            schedule_id, team_id, cron_expression, status, coalesce_policy
        ) VALUES (
            'schedule-coalesce-all', 'team-1', '0 9 * * 1-5', 'active', 'all'
        )
        """,
    ]
    for invalid_sql in invalid_research_sql:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(invalid_sql))

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO research_note (
                    note_id, note_key, workspace_id, run_id, claim_id, revision,
                    source_kind, summary
                ) VALUES (
                    'note-invalid', 'note-key', 'workspace-1', 'run-1', 'claim-1', 1,
                    'claim', 'invalid dual source'
                )
                """))

    with engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO alert_rule (
                    rule_id, asset_id, metric_type, metric_key, operator,
                    threshold, status, state
                ) VALUES (
                    'rule-active-unique', 'asset-1', 'price', 'last', 'gt',
                    '100', 'active', '{}'
                )
                """))
        connection.execute(text("""
                INSERT INTO alert_event (
                    event_id, rule_id, observation_id, dedupe_key, status, triggered_at
                ) VALUES (
                    'event-open', 'rule-active-unique', 'obs-open', 'dedupe-open',
                    'open', '2026-09-01T09:30:00+00:00'
                )
                """))

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO alert_event (
                    event_id, rule_id, observation_id, dedupe_key, status, triggered_at
                ) VALUES (
                    'event-ack', 'rule-active-unique', 'obs-ack', 'dedupe-ack',
                    'acknowledged', '2026-09-01T09:31:00+00:00'
                )
                """))

    with engine.begin() as connection:
        connection.execute(text("""
                UPDATE alert_event
                SET status = 'resolved', resolved_at = '2026-09-01T09:32:00+00:00'
                WHERE event_id = 'event-open'
                """))
        connection.execute(text("""
                INSERT INTO alert_event (
                    event_id, rule_id, observation_id, dedupe_key, status, triggered_at
                ) VALUES (
                    'event-ack', 'rule-active-unique', 'obs-ack', 'dedupe-ack',
                    'acknowledged', '2026-09-01T09:33:00+00:00'
                )
                """))

    command.downgrade(config, "014")
    assert expected.isdisjoint(set(inspect(engine).get_table_names()))
