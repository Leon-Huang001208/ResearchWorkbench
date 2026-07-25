"""Runtime configuration resolution tests."""

from pathlib import Path


def test_desktop_runtime_uses_local_data_directory_and_desktop_backend_url(monkeypatch, tmp_path):
    from core.settings import runtime

    monkeypatch.setenv("ALPHAFOUNDRY_RUN_MODE", "desktop")
    monkeypatch.delenv("ALPHAFOUNDRY_CONFIG_FILE", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_BACKEND_URL", raising=False)
    monkeypatch.setattr(runtime, "app_data_dir", lambda: tmp_path / "Local" / "AlphaFoundry")

    context = runtime.resolve_runtime_context(environ=dict(__import__("os").environ))

    assert context.mode == "desktop"
    assert context.data_dir == tmp_path / "Local" / "AlphaFoundry"
    assert context.env_path == context.data_dir / ".env"
    assert context.backend_url == "http://127.0.0.1:8765"
    assert context.can_write_config is True


def test_explicit_config_file_and_backend_url_override_mode_defaults(monkeypatch, tmp_path):
    from core.settings.runtime import resolve_runtime_context

    config_file = tmp_path / "controlled.env"
    context = resolve_runtime_context(
        environ={
            "ALPHAFOUNDRY_RUN_MODE": "desktop",
            "ALPHAFOUNDRY_CONFIG_FILE": str(config_file),
            "ALPHAFOUNDRY_BACKEND_URL": "https://api.example.invalid/base/",
        },
        project_root=tmp_path / "project",
    )

    assert context.env_path == config_file
    assert context.backend_url == "https://api.example.invalid/base"


def test_web_production_does_not_implicitly_read_project_env(tmp_path):
    from core.settings.runtime import resolve_runtime_context

    context = resolve_runtime_context(
        environ={"ALPHAFOUNDRY_RUN_MODE": "web-prod"},
        project_root=tmp_path,
    )

    assert context.mode == "web-prod"
    assert context.env_path is None
    assert context.backend_url == "http://127.0.0.1:8000"
    assert context.can_write_config is False


def test_web_development_uses_project_env(tmp_path):
    from core.settings.runtime import resolve_runtime_context

    context = resolve_runtime_context(
        environ={"ALPHAFOUNDRY_RUN_MODE": "web-dev"},
        project_root=tmp_path,
    )

    assert context.mode == "web-dev"
    assert context.env_path == tmp_path / ".env"


def test_legacy_desktop_marker_is_supported(monkeypatch, tmp_path):
    from core.settings.runtime import resolve_runtime_context

    monkeypatch.setattr("core.settings.runtime.app_data_dir", lambda: tmp_path / "AlphaFoundry")
    context = resolve_runtime_context(environ={"ALPHAFOUNDRY_DESKTOP": "1"})

    assert context.mode == "desktop"
    assert context.env_path == tmp_path / "AlphaFoundry" / ".env"


def test_runtime_context_rejects_unknown_mode(tmp_path):
    from core.settings.runtime import RuntimeConfigurationError, resolve_runtime_context

    try:
        resolve_runtime_context(
            environ={"ALPHAFOUNDRY_RUN_MODE": "unsupported"}, project_root=tmp_path
        )
    except RuntimeConfigurationError as exc:
        assert "ALPHAFOUNDRY_RUN_MODE" in str(exc)
    else:
        raise AssertionError("Expected RuntimeConfigurationError")


def test_settings_does_not_default_to_known_database_credentials(monkeypatch):
    import core.settings.config as config

    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = config.Settings()

    assert "postgres:postgres" not in settings.DATABASE_URL
    assert "invalid:invalid" in settings.DATABASE_URL


def test_desktop_settings_default_storage_uses_application_data_directory(monkeypatch, tmp_path):
    import core.settings.config as config
    from core.settings.runtime import RuntimeContext

    context = RuntimeContext(
        mode="desktop",
        project_root=tmp_path / "project",
        data_dir=tmp_path / "AlphaFoundry",
        env_path=tmp_path / "AlphaFoundry" / ".env",
        backend_url="http://127.0.0.1:8765",
        can_write_config=True,
    )
    monkeypatch.setattr(config, "RUNTIME_CONTEXT", context)
    monkeypatch.setattr(config, "DEFAULT_LOG_DIR", context.data_dir / "logs")
    monkeypatch.setattr(config, "DEFAULT_OBJECT_STORAGE_PATH", context.data_dir / "objects")
    monkeypatch.setattr(config, "DEFAULT_PDF_MARKDOWN_DIR", context.data_dir / "markdown")
    monkeypatch.setattr(config, "DEFAULT_PDF_RAW_TEXT_DIR", context.data_dir / "raw_text")

    for key in (
        "PROJECT_ROOT",
        "LOG_DIR",
        "OBJECT_STORAGE_PATH",
        "PDF_MARKDOWN_DIR",
        "PDF_RAW_TEXT_DIR",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = config.Settings()

    assert settings.LOG_DIR == context.data_dir / "logs"
    assert settings.OBJECT_STORAGE_PATH == context.data_dir / "objects"
    assert settings.PDF_MARKDOWN_DIR == context.data_dir / "markdown"
    assert settings.PDF_RAW_TEXT_DIR == context.data_dir / "raw_text"


def test_resolve_runtime_env_path_delegates_to_context(tmp_path):
    from core.settings.config import resolve_runtime_env_path

    resolved = resolve_runtime_env_path(
        environ={"ALPHAFOUNDRY_CONFIG_FILE": str(tmp_path / "explicit.env")},
        project_root=tmp_path,
    )

    assert resolved == Path(tmp_path / "explicit.env")
