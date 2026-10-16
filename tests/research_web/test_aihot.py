"""AIHOT fixed-origin transport, cache and public response contracts."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_web import aihot_routes


def test_article_body_preserves_reading_structure_without_active_html():
    from app.research_web.aihot_content import reading_tree

    nodes = reading_tree(
        '<h2 id="sec-1" onclick="evil()">章节</h2><p>全文<strong>重点</strong><a href="/items/abc">下一篇</a></p><script>evil()</script><img src="https://evil.test/pixel"><iframe src="https://evil.test"></iframe>',
        lambda value: None,
    )
    assert nodes[0] == {"tag": "h2", "attrs": {"id": "sec-1"}, "children": [{"text": "章节"}]}
    assert nodes[1]["children"][-1]["attrs"]["href"] == "#/aihot/item/abc"
    encoded = str(nodes)
    assert "evil" not in encoded and "iframe" not in encoded and "onclick" not in encoded


def test_blocked_void_media_does_not_swallow_later_body():
    from app.research_web.aihot_content import reading_tree

    nodes = reading_tree('<p>before</p><embed src="movie.swf"><p>after</p>', lambda _: None)
    assert [row["children"][0]["text"] for row in nodes] == ["before", "after"]


def test_related_source_list_respects_no_store(adapter):
    browser, calls, replies, _ = adapter
    replies[:] = [
        httpx.Response(
            200, json={"factId": "fact_1", "reports": []}, headers={"cache-control": "no-store"}
        )
        for _ in range(2)
    ]
    for _ in range(2):
        assert browser.get("/api/research/aihot/groups/fact_1/reports").status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize(
    "suffix,endpoint",
    [
        ("items/article_1", "/api/site/items/article_1"),
        ("items/article_1/original", "/api/site/items/article_1/original"),
    ],
)
def test_article_detail_projects_html_and_verifies_identity(adapter, suffix, endpoint):
    browser, calls, replies, _ = adapter
    replies[:] = [
        httpx.Response(
            200,
            json={
                "id": "article_1",
                "title": "正文",
                "readingMode": "full",
                "body": {"zh": "<p>真实正文</p>", "original": None, "complete": True},
                "outline": [],
                "relatedStories": [],
                "topics": [],
            },
        )
    ]
    result = browser.get("/api/research/aihot/" + suffix)
    assert result.status_code == 200
    assert calls[0].url.path == endpoint
    assert result.json()["body"]["content"][0]["children"] == [{"text": "真实正文"}]
    assert "zh" not in result.json()["body"]


def test_story_and_topic_contracts_and_merge_are_local(adapter):
    browser, calls, replies, _ = adapter
    identity = "2f0270d6-fc22-4747-af7c-a4f488d3cd16"
    replies[:] = [
        httpx.Response(308, json={"mergedInto": identity}),
        httpx.Response(
            200, json={"topic": {"slug": "meta"}, "items": [], "page": 2, "pageCount": 4}
        ),
    ]
    assert browser.get("/api/research/aihot/stories/" + identity).json() == {"mergedInto": identity}
    assert browser.get("/api/research/aihot/topics/meta?page=2").json()["page"] == 2
    assert str(calls[-1].url).endswith("/api/site/topics/meta?page=2")
    assert browser.get("/api/research/aihot/topics/meta?page=0").status_code == 422


def test_detail_identity_mismatch_fails_closed(adapter):
    browser, _, replies, _ = adapter
    replies[:] = [httpx.Response(200, json={"id": "other", "title": "wrong"})]
    assert browser.get("/api/research/aihot/items/article_1").status_code == 502


@pytest.fixture
def adapter(monkeypatch):
    calls = []
    replies = [httpx.Response(200, json={"schemaVersion": 1, "items": [], "count": 0})]
    real_client = httpx.AsyncClient

    def respond(request):
        calls.append(request)
        result = replies.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(aihot_routes.httpx, "AsyncClient", client)
    clock = [0.0]
    app = FastAPI()
    app.state.aihot = aihot_routes.AihotReader(clock=lambda: clock[0])
    app.include_router(aihot_routes.router)
    with TestClient(app) as browser:
        yield browser, calls, replies, clock


@pytest.mark.parametrize("path", ["dailies", "hot-topics"])
def test_fixed_get_and_cache_do_not_forward_credentials(adapter, path):
    browser, calls, _, _ = adapter
    url = "/api/research/aihot/" + path
    response = browser.get(url, headers={"Authorization": "Bearer private", "Cookie": "key=secret"})
    assert response.status_code == 200
    assert browser.get(url).json() == response.json()
    assert len(calls) == 1
    assert calls[0].url.host == "aihot.news"
    assert calls[0].url.path == "/api/v1/" + path
    assert "authorization" not in calls[0].headers
    assert "cookie" not in calls[0].headers


def test_etag_revalidation_and_upstream_ttl(adapter):
    browser, calls, replies, clock = adapter
    replies[:] = [
        httpx.Response(
            200,
            headers={"ETag": '"one"', "Cache-Control": "s-maxage=120"},
            json={"schemaVersion": 1, "count": 0, "items": []},
        )
    ]
    url = "/api/research/aihot/hot-topics"
    assert browser.get(url).status_code == 200
    clock[0] = 80
    assert browser.get(url).status_code == 200
    assert len(calls) == 1
    replies.append(httpx.Response(304))
    clock[0] = 121
    assert browser.get(url).status_code == 200
    assert calls[-1].headers["if-none-match"] == '"one"'


@pytest.mark.parametrize("status,local", [(404, 404), (429, 429), (503, 503), (302, 502)])
def test_upstream_errors_and_retry_after(adapter, status, local):
    browser, calls, replies, _ = adapter
    replies[:] = [httpx.Response(status, headers={"Retry-After": "120"})]
    response = browser.get("/api/research/aihot/hot-topics")
    assert response.status_code == local
    assert "aihot_" in response.json()["detail"]["code"]
    if status in (429, 503):
        assert response.headers["retry-after"] == "120"
        assert browser.get("/api/research/aihot/hot-topics").status_code == local
        assert len(calls) == 1


@pytest.mark.parametrize(
    "body", [{}, {"schemaVersion": 2, "items": []}, {"schemaVersion": 1, "items": "bad"}]
)
def test_invalid_json_shape_is_not_empty_success(adapter, body):
    browser, _, replies, _ = adapter
    replies[:] = [httpx.Response(200, json=body)]
    assert browser.get("/api/research/aihot/hot-topics").status_code == 502


def test_dates_and_methods_reject_before_network(adapter):
    browser, calls, _, _ = adapter
    for path in ("2026-02-30", "latest", "bad"):
        assert browser.get("/api/research/aihot/dailies/" + path).status_code == 422
    assert browser.post("/api/research/aihot/hot-topics").status_code == 405
    assert browser.get("/api/research/aihot/proxy?url=http://example.org").status_code == 404
    assert not calls


def test_edition_identity_and_structure(adapter):
    browser, _, replies, _ = adapter
    report = {"date": "2026-10-15", "lead": {}, "sections": [], "flashes": []}
    replies[:] = [httpx.Response(200, json={"schemaVersion": 1, "report": report})]
    assert browser.get("/api/research/aihot/dailies/2026-10-16").status_code == 502
    report["date"] = "2026-10-16"
    replies.append(httpx.Response(200, json={"schemaVersion": 1, "report": report}))
    assert browser.get("/api/research/aihot/dailies/2026-10-16").json()["report"] == report


def test_invalid_content_and_timeout(adapter):
    browser, _, replies, _ = adapter
    replies[:] = [httpx.Response(200, text="<html>bad</html>")]
    assert browser.get("/api/research/aihot/hot-topics").status_code == 502
    replies.append(httpx.ReadTimeout("offline"))
    assert browser.get("/api/research/aihot/hot-topics").status_code == 504


def test_body_limit(adapter, monkeypatch):
    browser, _, replies, _ = adapter
    monkeypatch.setattr(aihot_routes, "RESPONSE_LIMIT", 32)
    replies[:] = [httpx.Response(200, json={"schemaVersion": 1, "items": [], "padding": "a" * 100})]
    assert browser.get("/api/research/aihot/hot-topics").status_code == 502


def test_retry_after_http_date_is_honoured(adapter):
    browser, _, replies, _ = adapter
    browser.app.state.aihot.wall_clock = lambda: 0.0
    replies[:] = [httpx.Response(503, headers={"Retry-After": "Thu, 01 Jan 1970 00:05:00 GMT"})]
    response = browser.get("/api/research/aihot/hot-topics")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "300"


@pytest.mark.asyncio
async def test_cached_endpoint_does_not_wait_on_other_network_reads():
    reader = aihot_routes.AihotReader(clock=lambda: 0.0)
    payload = {"schemaVersion": 1, "items": []}
    reader.cache["/hot-topics"] = {"until": 60.0, "payload": payload}
    async with reader.lock:
        assert await asyncio.wait_for(reader.read("/hot-topics"), timeout=0.1) == payload


@pytest.mark.parametrize(
    "local,remote,payload",
    [
        ("pages/hot", "/site/hot", {"entries": []}),
        (
            "reports/daily/latest-page",
            "/site/reports/daily/latest-page",
            {"index": [], "report": None},
        ),
        (
            "reports/weekly/latest-page",
            "/site/reports/weekly/latest-page",
            {"index": [], "report": None},
        ),
        (
            "reports/monthly/latest-page",
            "/site/reports/monthly/latest-page",
            {"index": [], "report": None},
        ),
        ("reports/daily", "/site/reports/daily", {"kind": "daily", "items": []}),
        ("reports/daily/months/2026-09", "/site/reports/daily/months/2026-09", {"items": []}),
        (
            "reports/daily/navigation/2026-10-15",
            "/site/reports/daily/navigation/2026-10-15",
            {"items": []},
        ),
        (
            "reports/weekly/2026-W41",
            "/site/reports/weekly/2026-W41",
            {"kind": "weekly", "key": "2026-W41", "sections": [], "highlights": [], "flashes": []},
        ),
    ],
)
def test_full_site_page_routes(adapter, local, remote, payload):
    browser, calls, replies, _ = adapter
    replies[:] = [httpx.Response(200, json=payload)]
    response = browser.get("/api/research/aihot/" + local)
    assert response.status_code == 200
    assert response.json() == payload
    assert str(calls[0].url) == "https://aihot.news/api" + remote


@pytest.mark.parametrize(
    "path",
    [
        "reports/daily/2026-02-30",
        "reports/weekly/2026-W54",
        "reports/monthly/2026-13",
        "reports/daily/months/2026-99",
        "reports/unknown/latest-page",
    ],
)
def test_full_site_parameters_reject_before_network(adapter, path):
    browser, calls, _, _ = adapter
    assert browser.get("/api/research/aihot/" + path).status_code == 422
    assert not calls


def test_site_requested_report_identity_cannot_change(adapter):
    browser, _, replies, _ = adapter
    replies[:] = [
        httpx.Response(
            200,
            json={
                "kind": "daily",
                "key": "2026-10-14",
                "sections": [],
                "flashes": [],
                "highlights": [],
            },
        )
    ]
    assert browser.get("/api/research/aihot/reports/daily/2026-10-15").status_code == 502


def test_only_upstream_issued_images_are_read_and_no_credentials_forwarded(adapter):
    browser, calls, replies, _ = adapter
    url = "/api/img-proxy?u=https%3A%2F%2Fexample.org%2Fimage.png&mode=full&exp=1799999999&sig=abcdef0123456789"
    payload = {
        "index": [],
        "report": {
            "kind": "daily",
            "key": "2026-10-15",
            "sections": [],
            "highlights": [],
            "flashes": [],
            "cover": {"url": url},
        },
    }
    replies[:] = [
        httpx.Response(200, json=payload),
        httpx.Response(200, content=b"image", headers={"Content-Type": "image/png"}),
    ]
    result = browser.get("/api/research/aihot/reports/daily/latest-page").json()
    media = result["report"]["cover"]["url"]
    assert media.startswith("/api/research/aihot/media/")
    assert (
        browser.get(
            media, headers={"Authorization": "Bearer secret", "Cookie": "private=value"}
        ).status_code
        == 200
    )
    assert calls[1].url.host == "aihot.news"
    assert calls[1].url.path == "/api/img-proxy"
    assert "authorization" not in calls[1].headers
    assert "cookie" not in calls[1].headers
    assert browser.get("/api/research/aihot/media/" + "a" * 64).status_code == 404
    assert len(calls) == 2


def test_cached_pages_reissue_evicted_media_mapping(adapter):
    browser, calls, replies, _ = adapter
    url = "/api/img-proxy?u=https%3A%2F%2Fexample.org%2Fx.png&mode=full&exp=1799999999&sig=abcdef0123456789"
    replies[:] = [
        httpx.Response(
            200, json={"entries": [{"rank": 1, "story": {}, "spark": [], "cover": {"url": url}}]}
        )
    ]
    result = browser.get("/api/research/aihot/pages/hot").json()
    key = result["entries"][0]["cover"]["url"].rsplit("/", 1)[1]
    browser.app.state.aihot.media.urls.clear()
    assert browser.get("/api/research/aihot/pages/hot").status_code == 200
    assert key in browser.app.state.aihot.media.urls
    assert len(calls) == 1


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example/api/img-proxy?sig=abcdef0123456789",
        "http://aihot.news/api/img-proxy?u=x&mode=full&exp=1&sig=abcdef0123456789",
        "/api/img-proxy?u=x&mode=full&exp=1&sig=bad",
        "//evil.example/api/img-proxy?u=x&mode=full&exp=1&sig=abcdef0123456789",
    ],
)
def test_media_cannot_register_external_or_unsigned_paths(value):
    from app.research_web.aihot_media import AihotMedia

    media = AihotMedia()
    assert media.project({"iconUrl": value})["iconUrl"] is None
    assert not media.urls
