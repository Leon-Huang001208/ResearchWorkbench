"""Tests for runtime-configured auto-ingest API endpoints."""

import importlib


def test_backend_endpoint_uses_runtime_override(monkeypatch):
    monkeypatch.setenv("ALPHAFOUNDRY_BACKEND_URL", "http://127.0.0.1:8765/")

    from cron_jobs import auto_ingest_service

    module = importlib.reload(auto_ingest_service)

    assert module.backend_endpoint("/health") == "http://127.0.0.1:8765/health"
    assert (
        module.backend_endpoint("api/assets/analyze") == "http://127.0.0.1:8765/api/assets/analyze"
    )


def test_backend_endpoint_defaults_to_web_development_url(monkeypatch):
    monkeypatch.delenv("ALPHAFOUNDRY_BACKEND_URL", raising=False)

    from cron_jobs import auto_ingest_service

    module = importlib.reload(auto_ingest_service)

    assert module.backend_endpoint("/health") == "http://127.0.0.1:8000/health"
