"""Real multipart encoding and response parsing for the pinned upload API."""

import asyncio
import base64
import hashlib
import json
from email import policy
from email.parser import BytesParser

import httpx
import pytest

from app.research_web.knowledge_backend.client import WeKnoraClient
from app.research_web.store import StoreError


def client(handler):
    payload = base64.urlsafe_b64encode(b'{"exp":4102444800}').decode().rstrip("=")
    return WeKnoraClient(
        "http://127.0.0.1:18080",
        "e30." + payload + ".c2ln",
        "101",
        transport=httpx.MockTransport(handler),
    )


def document(kb="kb1", content=b"exact original"):
    return {
        "id": "d1",
        "knowledge_base_id": kb,
        "file_name": "report.md",
        "file_hash": hashlib.md5(content).hexdigest(),
        "parse_status": "pending",
        "enable_status": "enabled",
    }


def test_upload_sends_exact_snapshot_and_disables_summary_in_multipart():
    def handle(request):
        assert request.method == "POST"
        assert request.url.path == "/api/v1/knowledge-bases/kb1/knowledge/file"
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: "
            + request.headers["content-type"].encode()
            + b"\r\n\r\n"
            + request.content
        )
        parts = {
            part.get_param("name", header="content-disposition"): part
            for part in message.iter_parts()
        }
        assert parts["file"].get_payload(decode=True) == b"exact original"
        assert parts["fileName"].get_payload(decode=True) == b"folder/report.md"
        assert json.loads(parts["metadata"].get_payload(decode=True)) == {"rwb_sha256": "a" * 64}
        assert (
            json.loads(parts["process_config"].get_payload(decode=True))["summary_enabled"] is False
        )
        return httpx.Response(200, json={"success": True, "data": document()})

    result = asyncio.run(
        client(handle).upload(
            "kb1", "folder/report.md", b"exact original", {"rwb_sha256": "a" * 64}
        )
    )
    assert result["id"] == "d1"
    assert result["kb_id"] == "kb1"


def test_duplicate409_must_have_same_hash_and_kb():
    def handle(request):
        return httpx.Response(
            409, json={"success": False, "code": "duplicate_file", "data": document()}
        )

    assert (
        asyncio.run(client(handle).upload("kb1", "report.md", b"exact original", {}))["id"] == "d1"
    )
    for wrong in (document("foreign"), document(content=b"wrong")):
        with pytest.raises(StoreError) as failure:
            asyncio.run(
                client(
                    lambda request, wrong=wrong: httpx.Response(
                        409, json={"success": False, "code": "duplicate_file", "data": wrong}
                    )
                ).upload("kb1", "report.md", b"exact original", {})
            )
        assert failure.value.code == "weknora_upload_identity_mismatch"


def test_reconcile_listing_is_paginated_and_rejects_other_kb():
    def handle(request):
        assert dict(request.url.params) == {"page": "1", "page_size": "100"}
        return httpx.Response(
            200,
            json={"success": True, "data": [document()], "total": 1, "page": 1, "page_size": 100},
        )

    assert asyncio.run(client(handle).documents_in_base("kb1"))[0]["id"] == "d1"
    with pytest.raises(StoreError):
        asyncio.run(
            client(
                lambda request: httpx.Response(
                    200,
                    json={
                        "success": True,
                        "data": [document("foreign")],
                        "total": 1,
                        "page": 1,
                        "page_size": 100,
                    },
                )
            ).documents_in_base("kb1")
        )
