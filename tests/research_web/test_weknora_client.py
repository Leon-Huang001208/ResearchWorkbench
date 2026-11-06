"""Pinned upstream JSON shapes through real httpx parsing, without network access."""

import asyncio
import base64
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from app.research_web.knowledge_backend import client as module
from app.research_web.knowledge_backend.client import JSON_LIMIT, ORIGINAL_LIMIT, WeKnoraClient
from app.research_web.store import StoreError

ORIGIN = "http://127.0.0.1:18080"


def jwt(expiry=4102444800):
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    # Synthetic JWT syntax only. MockTransport does not claim signature verification.
    return encode({"alg": "HS256", "typ": "JWT"}) + "." + encode({"exp": expiry}) + ".c2ln"


def identity():
    return {
        "user": {"id": "u1", "tenant_id": 101, "is_active": True},
        "tenant": {"id": 102, "name": "active"},
        "memberships": [{"tenant_id": 102, "tenant_name": "active", "role": "viewer"}],
        "tenant_required": False,
    }


def chunk(identifier="c1", document="d1", kb="kb1", index=0):
    return {
        "id": identifier,
        "knowledge_id": document,
        "knowledge_base_id": kb,
        "tenant_id": 102,
        "content": "正文",
        "chunk_index": index,
        "start_at": index * 2,
        "end_at": index * 2 + 2,
        "score": 0.2,
    }


def ok(data, **extra):
    return httpx.Response(200, json={"success": True, "data": data, **extra})


def connected(handler, token=None):
    return WeKnoraClient(
        ORIGIN, jwt() if token is None else token, "102", transport=httpx.MockTransport(handler)
    )


def run(awaitable):
    return asyncio.run(awaitable)


def test_identity_uses_current_tenant_and_only_user_bearer():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url == ORIGIN + "/api/v1/auth/me"
        assert request.headers["Authorization"] == "Bearer " + jwt()
        assert request.headers["X-Tenant-ID"] == "102"
        assert "X-API-Key" not in request.headers
        return ok(identity())

    assert run(connected(handle).identity()) == {
        "user_id": "u1",
        "workspace_id": "102",
        "role": "viewer",
    }
    assert len(calls) == 1


def test_identity_rejects_inactive_or_mismatched_membership_and_accepts_contributor():
    for change in ("home", "inactive", "required", "missing", "duplicate", "role"):
        value = identity()
        if change == "home":
            value["tenant"]["id"] = 101
        elif change == "inactive":
            value["user"]["is_active"] = False
        elif change == "required":
            value["tenant_required"] = True
        elif change == "missing":
            value["memberships"] = []
        elif change == "duplicate":
            value["memberships"] *= 2
        else:
            value["memberships"][0]["role"] = "administrator"
        with pytest.raises(StoreError) as failure:
            run(connected(lambda request, value=value: ok(value)).identity())
        assert failure.value.code == "weknora_auth_denied"
    value = identity()
    value["memberships"][0]["role"] = "contributor"
    assert run(connected(lambda request: ok(value)).identity())["role"] == "contributor"


def test_invalid_api_key_expired_and_during_request_expiry_never_fallback(monkeypatch):
    for token, code in (
        ("sk-api-key", "weknora_credentials_invalid"),
        (jwt(1), "weknora_credentials_expired"),
    ):
        with pytest.raises(StoreError) as failure:
            connected(lambda request: pytest.fail("no request allowed"), token)
        assert failure.value.code == code
    for origin in (
        "http://private-server.example",
        "http://192.168.1.2:8080",
        ORIGIN + "/api/v1",
        "https://user:password@example.com",
        "http://127.0.0.1:99999",
    ):
        with pytest.raises(StoreError) as failure:
            WeKnoraClient(origin, jwt(), "102")
        assert failure.value.code == "weknora_configuration_invalid"
    clock = iter([10, 10, 12])
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: next(clock)))
    calls = []

    def handle(request):
        calls.append(request)
        return ok(identity())

    with pytest.raises(StoreError) as failure:
        run(connected(handle, jwt(11)).identity())
    assert failure.value.code == "weknora_credentials_expired"
    assert len(calls) == 1


def test_knowledge_bases_merge_owned_and_explicit_shared_permissions():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/knowledge-bases"):
            return ok([{"id": "kb1", "tenant_id": 102, "name": "own"}])
        assert request.url.path.endswith("/shared-knowledge-bases")
        return ok(
            [
                {
                    "knowledge_base": {"id": "kb-shared", "tenant_id": 202, "name": "shared"},
                    "share_id": "s1",
                    "organization_id": "org1",
                    "org_name": "Org",
                    "permission": "viewer",
                    "source_tenant_id": 202,
                    "shared_at": "2026-11-06",
                }
            ],
            total=1,
        )

    result = run(connected(handle).knowledge_bases())
    assert [item["id"] for item in result] == ["kb1", "kb-shared"]
    assert result[1]["permission"] == "viewer"
    assert result[1]["source_tenant_id"] == "202"
    assert len(calls) == 2


def test_search_sends_document_scope_before_retrieval_and_ranks_across_bases():
    calls = []

    def handle(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.method == "POST"
        assert dict(request.url.params) == {"resource_urls": "handle"}
        assert payload == {
            "query_text": "周报依据",
            "knowledge_ids": ["d1"],
            "match_count": 1,
            "vector_threshold": 0,
            "keyword_threshold": 0,
            "disable_keywords_match": False,
            "disable_vector_match": False,
        }
        kb = request.url.path.split("/")[-2]
        value = chunk("c-" + kb, kb=kb)
        value["score"] = 0.3 if kb == "kb2" else 0.1
        value["resource_url"] = "https://must-not-follow.invalid/secret"
        return ok([value])

    result = run(connected(handle).search("周报依据", ["kb1", "kb2"], ["d1"], limit=1))
    assert result == [
        {
            "chunk_id": "c-kb2",
            "document_id": "d1",
            "kb_id": "kb2",
            "title": "",
            "content": "正文",
            "chunk_index": 0,
            "start_at": 0,
            "end_at": 2,
        }
    ]
    assert len(calls) == 2


def test_search_empty_document_scope_or_unsafe_ids_rejected_before_network():
    client = connected(lambda request: pytest.fail("invalid scope must not query upstream"))
    for bases, documents in (
        (["kb1"], []),
        ([], None),
        (["../kb"], ["d1"]),
        (["kb1"], ["d1", "d1"]),
    ):
        with pytest.raises(StoreError):
            run(client.search("query", bases, documents))
    for identifier in ("../escape", "d1?tenant=other", "d1%2fadmin", "", "d1\n"):
        with pytest.raises(StoreError):
            run(client.original(identifier))


def test_search_ordinary_scope_omits_document_filter_and_refuses_out_of_scope_hits():
    def ordinary(request):
        assert "knowledge_ids" not in json.loads(request.content)
        return ok([])

    assert run(connected(ordinary).search("query", ["kb1"])) == []
    for returned in (chunk(document="d-other"), chunk(kb="kb-other")):
        with pytest.raises(StoreError) as failure:
            run(
                connected(lambda request, returned=returned: ok([returned])).search(
                    "query", ["kb1"], ["d1"]
                )
            )
        assert failure.value.code == "weknora_scope_denied"


def test_document_preserves_md5_source_state_and_never_follows_file_url():
    value = {
        "id": "d1",
        "tenant_id": 202,
        "knowledge_base_id": "kb-shared",
        "type": "file",
        "file_name": "report.pdf",
        "file_hash": "A" * 32,
        "parse_status": "completed",
        "enable_status": "enabled",
        "metadata": {"file_url": "https://forbidden.invalid/a"},
        "custom_metadata": {"period": "2026-10-30"},
    }
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.path == "/api/v1/knowledge/d1"
        return ok(value)

    result = run(connected(handle).document("d1"))
    assert (result["id"], result["kb_id"], result["title"], result["file_type"]) == (
        "d1",
        "kb-shared",
        "report.pdf",
        "pdf",
    )
    assert result["file_hash"] == "a" * 32
    assert result["parse_status"] == "completed" and result["type"] == "file"
    assert result["raw"] == value
    assert len(calls) == 1
    wrong = copy.deepcopy(value)
    wrong["file_hash"] = "b" * 64
    with pytest.raises(StoreError) as failure:
        run(connected(lambda request: ok(wrong)).document("d1"))
    assert failure.value.code == "weknora_response_invalid"


def test_chunks_reads_complete_validated_pagination():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.path == "/api/v1/chunks/d1"
        assert request.url.params["chunk_type"] == "text"
        assert request.url.params["page_size"] == "100"
        page = int(request.url.params["page"])
        indices = range(100) if page == 1 else range(100, 101)
        return ok(
            [chunk("c" + str(index), index=index) for index in indices],
            total=101,
            page=page,
            page_size=100,
        )

    result = run(connected(handle).chunks("d1"))
    assert len(result) == 101 and result[-1]["chunk_index"] == 100
    assert len(calls) == 2


def test_chunks_rejects_partial_pagination_and_wrong_document_identity():
    for value, metadata in (
        ([chunk()], {"total": 2, "page": 1, "page_size": 100}),
        ([chunk(document="other")], {"total": 1, "page": 1, "page_size": 100}),
        ([chunk()], {"total": 1, "page": 2, "page_size": 100}),
    ):
        with pytest.raises(StoreError) as failure:
            run(
                connected(
                    lambda request, value=value, metadata=metadata: ok(value, **metadata)
                ).chunks("d1")
            )
        assert failure.value.code == "weknora_response_invalid"


def test_original_download_is_fixed_authenticated_path_and_shared_viewer_denial_is_final():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url == ORIGIN + "/api/v1/knowledge/d1/download"
        assert request.headers["Authorization"].startswith("Bearer ")
        assert "X-API-Key" not in request.headers
        return httpx.Response(
            200, content=b"%PDF-real-original", headers={"content-type": "application/octet-stream"}
        )

    assert run(connected(handle).original("d1")) == b"%PDF-real-original"
    denied = []

    def forbidden(request):
        denied.append(request)
        return httpx.Response(403, json={"error": "editor_required"})

    with pytest.raises(StoreError) as failure:
        run(connected(forbidden).original("d1"))
    assert failure.value.code == "weknora_scope_denied" and len(denied) == 1
    assert len(calls) == 1


def test_response_limits_apply_to_streamed_json_and_original_bytes():
    for original, maximum in ((False, JSON_LIMIT), (True, ORIGINAL_LIMIT)):

        def handle(request, original=original, maximum=maximum):
            return httpx.Response(
                200,
                headers={
                    "content-type": "application/octet-stream" if original else "application/json"
                },
                stream=httpx.ByteStream(b"x" * (maximum + 1)),
            )

        client = connected(handle)
        with pytest.raises(StoreError) as failure:
            run(client.original("d1") if original else client.identity())
        assert failure.value.code == "weknora_response_too_large"


def test_redirects_and_http_errors_never_retry_or_disclose_server_body(caplog):
    for status in (302, 401, 404, 500):
        calls = []

        def handle(request, calls=calls, status=status):
            calls.append(request)
            return httpx.Response(
                status,
                headers={"Location": "https://must-not-follow.invalid/a"},
                text="private-response-body",
            )

        with pytest.raises(StoreError) as failure:
            run(connected(handle).identity())
        assert len(calls) == 1
        assert "private-response-body" not in str(failure.value) + caplog.text
        assert jwt() not in str(failure.value) + caplog.text


def test_malformed_envelopes_and_json_originals_rejected_even_http_200():
    values = (
        [identity()],
        {"success": False, "data": identity()},
        {"success": 1, "data": identity()},
        {"success": True},
    )
    for value in values:
        with pytest.raises(StoreError) as failure:
            run(connected(lambda request, value=value: httpx.Response(200, json=value)).identity())
        assert failure.value.code == "weknora_response_invalid"
    with pytest.raises(StoreError) as failure:
        run(connected(lambda request: ok({"error": "jwt expired"})).original("d1"))
    assert failure.value.code == "weknora_response_invalid"


def test_transport_timeout_has_bounded_sanitized_failure_without_retry(caplog):
    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout("private transport details " + jwt(), request=request)

    with pytest.raises(StoreError) as failure:
        run(connected(handle).identity())
    assert failure.value.code == "weknora_timeout" and failure.value.status == 504
    assert len(calls) == 1
    assert "private transport details" not in str(failure.value) + caplog.text
    assert jwt() not in str(failure.value) + caplog.text
