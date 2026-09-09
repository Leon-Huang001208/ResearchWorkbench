"""HTTP contract tests for the Theme Research Pack API."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.theme_research import get_theme_research_service, router
from core.contracts.platform_shared import AssetRef, FreshnessStatus, SourceRef
from core.contracts.theme_research import (
    PackHealth,
    ThemeAssetExposure,
    ThemeAssetProjection,
    ThemeEventProjection,
    ThemeKPIProjection,
    ThemePackManifest,
    ThemeSnapshot,
    ThemeValueChainProjection,
    WorkspacePrefillRequest,
)
from services.theme_pack_registry import ThemePackRegistry
from services.theme_research_service import ThemePackNotFoundError

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
PACK_ROOT = Path(__file__).parents[2] / "resources" / "research_packs"
SOURCE = SourceRef(
    source_id="official",
    name="Official",
    tier="official",
    content_hash="sha256:test",
)


class FakeThemeResearchService:
    def _manifest(self, key: str) -> ThemePackManifest:
        if key == "missing":
            raise ThemePackNotFoundError(key)
        return ThemePackRegistry(PACK_ROOT).get(key)

    def list_catalog(self):
        return [self._manifest("gold")]

    def get_snapshot(self, key: str, as_of=None):
        self._manifest(key)
        return ThemeSnapshot(
            pack_key=key,
            facts={},
            coverage=0,
            as_of=NOW,
            observed_at=NOW,
            available_at=NOW,
            source_refs=[SOURCE],
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=[],
        )

    def get_kpis(self, key: str, as_of=None):
        self._manifest(key)
        return ThemeKPIProjection(pack_key=key, series=[], as_of=NOW)

    def get_value_chain(self, key: str, as_of=None):
        manifest = self._manifest(key)
        return ThemeValueChainProjection(pack_key=key, nodes=manifest.value_chain, as_of=NOW)

    def get_events(self, key: str, as_of=None):
        self._manifest(key)
        return ThemeEventProjection(pack_key=key, verified=[], leads=[], as_of=NOW)

    def get_assets(self, key: str, as_of=None):
        self._manifest(key)
        return ThemeAssetProjection(
            pack_key=key,
            assets=[
                ThemeAssetExposure(
                    asset=AssetRef(asset_id="etf:518880.SH", asset_type="etf"),
                    exposure_type="direct",
                    rationale_ref="manifest:gold",
                )
            ],
            as_of=NOW,
        )

    def get_health(self, key: str, as_of=None):
        self._manifest(key)
        return PackHealth(pack_key=key)

    def create_research_workspace_request(self, key: str, title: str | None = None):
        manifest = self._manifest(key)
        return WorkspacePrefillRequest(
            pack_key=key,
            title=title or f"{manifest.name}研究",
            template_key=manifest.research_template_keys[0],
            context={"theme_pack": key},
        )


def _client() -> TestClient:
    app = FastAPI()
    service = FakeThemeResearchService()
    app.include_router(router)
    app.dependency_overrides[get_theme_research_service] = lambda: service
    return TestClient(app)


def test_catalog_and_six_projection_routes() -> None:
    client = _client()

    assert client.get("/api/themes").status_code == 200
    for suffix in ("snapshot", "kpis", "value-chain", "events", "assets", "health"):
        response = client.get(f"/api/themes/gold/{suffix}")
        assert response.status_code == 200, response.text


def test_create_workspace_entry_returns_prefilled_research_request() -> None:
    response = _client().post(
        "/api/themes/gold/research-workspaces",
        json={"title": "黄金与实际利率"},
    )

    assert response.status_code == 201
    assert response.json()["pack_key"] == "gold"
    assert response.json()["context"] == {"theme_pack": "gold"}


def test_missing_pack_is_safe_404() -> None:
    response = _client().get("/api/themes/missing/snapshot")

    assert response.status_code == 404
    assert response.json() == {"detail": "Theme pack not found"}
