"""Generated architecture documents are a read-only, opaque-origin surface."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app


def test_documentation_route_is_mounted_without_research_runtime():
    paths = create_app().openapi()["paths"]
    assert "/api/research/documentation/{name}" in paths


def test_api_atlas_is_a_fixed_read_only_document(docs):
    client, root = docs
    (root / "api-atlas.html").write_text("<h1>Research Web API Atlas</h1>", encoding="utf-8")
    response = client.get("/api/research/documentation/api-atlas.html")
    assert response.status_code == 200
    assert "Research Web API Atlas" in response.text


def test_registered_product_overview_has_safe_return_navigation(docs):
    client, root = docs
    (root / "00-system-overview.html").write_text(
        "<!doctype html><body><h1>产品边界</h1></body>", encoding="utf-8"
    )
    response = client.get("/api/research/documentation/00-system-overview.html")
    assert response.status_code == 200
    assert 'href="index.html"' in response.text
    assert 'href="index.html#modules"' in response.text
    assert "allow-same-origin" not in response.headers["content-security-policy"]
    assert "access-control-allow-origin" not in response.headers


@pytest.fixture
def docs(tmp_path, monkeypatch):
    from app.research_web import documentation

    root = tmp_path / "outputs" / "research-web-architecture"
    root.mkdir(parents=True)
    (root / "index.html").write_text("<h1>Architecture</h1>", encoding="utf-8")
    (root / "01-deployment.html").write_text(
        "<script>window.viewer=true</script>", encoding="utf-8"
    )
    monkeypatch.setattr(documentation, "ARTIFACT_ROOT", root)
    return TestClient(create_app()), root


def test_generated_html_works_but_remains_opaque_and_offline(docs):
    client, _ = docs
    response = client.get("/api/research/documentation/01-deployment.html")
    assert response.status_code == 200
    policy = response.headers["content-security-policy"]
    assert "sandbox allow-scripts;" in policy
    assert "script-src 'unsafe-inline'" in policy
    for expected in ("connect-src 'none'", "form-action 'none'", "base-uri 'none'"):
        assert expected in policy
    assert "allow-same-origin" not in policy
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    product_policy = client.get("/").headers["content-security-policy"]
    assert "script-src 'self'" in product_policy
    assert "sandbox allow-scripts" not in product_policy
    assert (
        client.get("/api/research/documentation/index.html", headers={"Origin": "null"}).status_code
        == 403
    )


@pytest.mark.parametrize(
    "name",
    [
        "missing.html",
        "architecture-map.json",
        "SKILL.md",
        "../../AGENTS.md",
        "%2e%2e%2fAGENTS.md",
        "%252e%252e%252fAGENTS.md",
        "..%5cAGENTS.md",
        "runtime%2fhome%2fcredentials.json",
    ],
)
def test_documentation_never_browses_repository_or_runtime(docs, name):
    client, _ = docs
    assert client.get(f"/api/research/documentation/{name}").status_code == 404


def test_documentation_rejects_symlink_file_and_root(docs, tmp_path, monkeypatch):
    from app.research_web import documentation

    client, root = docs
    outside = tmp_path / "private.html"
    outside.write_text("SECRET", encoding="utf-8")
    (root / "index.html").unlink()
    (root / "index.html").symlink_to(outside)
    assert client.get("/api/research/documentation/index.html").status_code == 404
    link = tmp_path / "linked-root"
    link.symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(documentation, "ARTIFACT_ROOT", link)
    assert client.get("/api/research/documentation/01-deployment.html").status_code == 404


def test_missing_artifact_returns_explicit_non_sensitive_error(docs):
    client, _ = docs
    response = client.get("/api/research/documentation/08-iteration-docs.html")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "documentation_unavailable"
    assert str(Path.cwd()) not in response.text


def test_documentation_rejects_hardlink_to_non_document_file(docs, tmp_path):
    import os

    client, root = docs
    private = tmp_path / "private-data"
    private.write_text("private data", encoding="utf-8")
    (root / "index.html").unlink()
    os.link(private, root / "index.html")
    assert client.get("/api/research/documentation/index.html").status_code == 404


def test_oversize_document_is_rejected(docs):
    from app.research_web.documentation import MAX_HTML_BYTES

    client, root = docs
    with (root / "index.html").open("wb") as stream:
        stream.truncate(MAX_HTML_BYTES + 1)
    assert client.get("/api/research/documentation/index.html").status_code == 404


def test_unsupported_document_reader_fails_explicitly_without_unsafe_fallback(docs, monkeypatch):
    from app.research_web import documentation

    client, _ = docs
    monkeypatch.setattr(documentation, "documentation_reader_available", lambda: False)

    def unexpected_open(*_args, **_kwargs):
        pytest.fail("unsupported reader must not open a path")

    monkeypatch.setattr(documentation.os, "open", unexpected_open)
    response = client.get("/api/research/documentation/index.html")
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "documentation_platform_unsupported"
    assert str(Path.cwd()) not in response.text
    assert client.get("/api/research/documentation/unlisted.html").status_code == 404


def test_user_navigation_from_opaque_index_can_read_fixed_public_diagram(docs):
    client, _ = docs
    headers = {
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-User": "?1",
    }
    for origin in (None, "null", "https://elsewhere.invalid"):
        request_headers = headers | ({"Origin": origin} if origin else {})
        response = client.get(
            "/api/research/documentation/01-deployment.html", headers=request_headers
        )
        assert response.status_code == 200
        assert "sandbox allow-scripts" in response.headers["content-security-policy"]
        assert "connect-src 'none'" in response.headers["content-security-policy"]
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "method,path,override",
    [
        ("GET", "/api/research/runtime", {}),
        ("POST", "/api/research/documentation/index.html", {}),
        ("HEAD", "/api/research/documentation/index.html", {}),
        ("GET", "/api/research/documentation/unlisted.html", {}),
        ("GET", "/api/research/documentation/index.html", {"Sec-Fetch-Mode": "cors"}),
        ("GET", "/api/research/documentation/index.html", {"Sec-Fetch-Dest": "iframe"}),
        ("GET", "/api/research/documentation/index.html", {"Sec-Fetch-User": ""}),
        ("GET", "/api/research/sessions/private/files/private/preview", {}),
    ],
)
def test_documentation_navigation_exception_does_not_expand_other_boundaries(
    docs, method, path, override
):
    client, _ = docs
    headers = {
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-User": "?1",
        "Origin": "null",
    } | override
    assert client.request(method, path, headers=headers).status_code == 403
