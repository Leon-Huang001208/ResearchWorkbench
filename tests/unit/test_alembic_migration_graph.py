"""Alembic migration graph integrity tests."""


def test_alembic_migrations_have_unique_revisions_and_single_head():
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    migrations_dir = Path(__file__).resolve().parents[2] / "storage" / "migrations"
    config = Config(str(migrations_dir / "alembic.ini"))
    config.set_main_option("script_location", str(migrations_dir))

    script = ScriptDirectory.from_config(config)

    revision_ids = [revision.revision for revision in script.walk_revisions()]
    assert len(revision_ids) == len(set(revision_ids))
    assert script.get_heads() == ["020"]


def test_checked_in_alembic_url_is_fail_closed_and_env_override_is_supported():
    from pathlib import Path

    migrations_dir = Path(__file__).resolve().parents[2] / "storage" / "migrations"
    config_text = (migrations_dir / "alembic.ini").read_text(encoding="utf-8")
    env_text = (migrations_dir / "env.py").read_text(encoding="utf-8")

    assert "invalid:invalid@127.0.0.1:1" in config_text
    assert "DATABASE_URL" in env_text
    assert 'config.set_main_option("sqlalchemy.url"' in env_text
