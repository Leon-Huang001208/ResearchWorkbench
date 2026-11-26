"""Static delivery contract: compressible assets are gzipped and CSS tokens resolve."""

import gzip
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app

UI = Path(__file__).resolve().parents[2] / "app" / "research_web" / "ui"


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


@pytest.mark.parametrize("asset", ["/static/app.mjs", "/static/styles.css"])
def test_large_static_assets_are_gzipped(client, asset):
    response = client.get(asset, headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    # TestClient transparently decodes, so measure the compression ratio from
    # the payload itself rather than the decoded body length.
    assert len(gzip.compress(response.content, 9)) < len(response.content) * 0.5


def test_event_stream_is_never_compressed():
    from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES

    assert "text/event-stream" in DEFAULT_EXCLUDED_CONTENT_TYPES


def test_css_custom_properties_resolve():
    """Every referenced token must be defined or have a fallback.

    A missing token with no fallback silently renders as nothing, which is how
    ported modules end up with invisible text or borders.
    """
    defined: set[str] = set()
    references: list[tuple[str, bool, str]] = []
    for sheet in UI.rglob("*.css"):
        css = sheet.read_text(encoding="utf-8", errors="replace")
        defined |= set(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", css))
        for match in re.finditer(r"var\((--[a-zA-Z0-9_-]+)\s*(,)?", css):
            references.append((match.group(1), bool(match.group(2)), sheet.name))

    runtime_set = "".join(
        script.read_text(encoding="utf-8", errors="replace") for script in UI.rglob("*.mjs")
    )
    unresolved = {
        name
        for name, has_fallback, _ in references
        if not has_fallback and name not in defined and name not in runtime_set
    }
    assert unresolved == set()
