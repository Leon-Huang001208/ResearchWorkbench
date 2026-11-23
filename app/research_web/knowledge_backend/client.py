"""Bounded user-JWT reads for the pinned WeKnora 0.9.0 HTTP protocol."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import math
import re
import time
from functools import wraps
from urllib.parse import urlsplit

import httpx

from core.observability import get_logger

from ..store import StoreError

log = get_logger(__name__)
JSON_LIMIT = 2 * 1024 * 1024
ORIGINAL_LIMIT = 8 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_JWT_PART = re.compile(r"[A-Za-z0-9_-]+\Z")
_MD5 = re.compile(r"[a-fA-F0-9]{32}\Z")
_ROLES = frozenset({"owner", "admin", "contributor", "viewer"})


def _fail(code: str, status: int = 502) -> StoreError:
    return StoreError("知识库请求未完成，请核对连接、授权或资料状态", code, status)


def _identifier(value) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise _fail("weknora_identifier_invalid", 422)
    return value


def _workspace(value) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise _fail("weknora_response_invalid")
    text = str(value)
    if not re.fullmatch(r"[1-9][0-9]{0,19}", text):
        raise _fail("weknora_response_invalid")
    return text


def _text(value, *, limit: int = JSON_LIMIT) -> str:
    try:
        valid = isinstance(value, str) and len(value.encode("utf-8")) <= limit
    except UnicodeError:
        valid = False
    if not valid:
        raise _fail("weknora_response_invalid")
    return value


def _integer(value, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 2**63 - 1:
        raise _fail("weknora_response_invalid")
    return value


def _operation(method):
    @wraps(method)
    async def bounded(*args, **kwargs):
        try:
            async with asyncio.timeout(30):
                return await method(*args, **kwargs)
        except TimeoutError:
            log.warning("weknora_operation_timeout", operation=method.__name__)
            raise _fail("weknora_timeout", 504) from None

    return bounded


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _json_constant(_value):
    raise ValueError("nonfinite JSON constant")


class WeKnoraClient:
    """No API-key fallback, refresh, redirects, ambient proxy or automatic retry."""

    @staticmethod
    @_operation
    async def login(origin, email, password, *, transport=None) -> dict:
        """Exchange a user-entered password once; retain only the verified bearer token."""
        from .configuration import checked_origin

        origin = checked_origin(origin)
        try:
            async with (
                asyncio.timeout(25),
                httpx.AsyncClient(
                    transport=transport,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(15, connect=5, pool=5),
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
                    headers={"Accept": "application/json"},
                ) as client,
                client.stream(
                    "POST",
                    origin + "/api/v1/auth/login",
                    json={"email": email, "password": password},
                ) as response,
            ):
                if response.status_code in {400, 401, 403}:
                    raise _fail("weknora_auth_denied", 401)
                if response.status_code != 200:
                    raise _fail("weknora_unavailable", 503)
                if (
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    != "application/json"
                ):
                    raise _fail("weknora_response_invalid")
                length = response.headers.get("content-length")
                if length is not None and (not length.isdecimal() or int(length) > 65536):
                    raise _fail("weknora_response_too_large", 413)
                raw = bytearray()
                async for part in response.aiter_bytes():
                    if len(raw) + len(part) > 65536:
                        raise _fail("weknora_response_too_large", 413)
                    raw.extend(part)
            value = json.loads(raw, object_pairs_hook=_json_object, parse_constant=_json_constant)
            if not isinstance(value, dict):
                raise _fail("weknora_response_invalid")
            # v0.9.0's HTTP DTO is top-level; some authenticated reverse proxies wrap data.
            data = value.get("data", value)
            if (
                not isinstance(data, dict)
                or value.get("success") is not True
                or data.get("success", True) is not True
            ):
                raise _fail("weknora_auth_denied", 401)
            user, tenant, memberships = (
                data.get("user"),
                data.get("active_tenant"),
                data.get("memberships"),
            )
            if (
                not isinstance(user, dict)
                or user.get("is_active") is not True
                or not isinstance(tenant, dict)
                or not isinstance(memberships, list)
            ):
                raise _fail("weknora_auth_denied", 401)
            workspace = _workspace(tenant.get("id"))
            roles = []
            for membership in memberships:
                if not isinstance(membership, dict):
                    raise _fail("weknora_response_invalid")
                if _workspace(membership.get("tenant_id")) == workspace:
                    roles.append(membership.get("role"))
            if len(roles) != 1 or not isinstance(roles[0], str) or roles[0] not in _ROLES:
                raise _fail("weknora_auth_denied", 401)
            token = data.get("token")
            WeKnoraClient(origin, token, workspace, transport=transport)
            result = {
                "token": token,
                "workspace_id": workspace,
                "user_id": _identifier(user.get("id")),
            }
            log.info("weknora_user_login_completed")
            return result
        except StoreError as exc:
            log.warning("weknora_user_login_rejected", code=exc.code)
            raise
        except (httpx.TimeoutException, TimeoutError):
            log.warning("weknora_user_login_timeout")
            raise _fail("weknora_timeout", 504) from None
        except (httpx.HTTPError, httpx.InvalidURL):
            log.warning("weknora_user_login_unavailable")
            raise _fail("weknora_unavailable", 503) from None
        except (ValueError, TypeError, UnicodeError, RecursionError):
            log.warning("weknora_user_login_response_invalid")
            raise _fail("weknora_response_invalid") from None

    def __init__(self, origin, token, workspace_id, *, transport=None):
        try:
            if not isinstance(origin, str):
                raise TypeError
            if len(origin) > 2048:
                raise ValueError
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or (
                    parsed.scheme == "http"
                    and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
                )
                or any(ord(char) < 33 or ord(char) > 126 for char in origin)
            ):
                raise ValueError
            port = parsed.port
            if port is not None and port < 1:
                raise ValueError
            self.workspace_id = _workspace(workspace_id)
        except (ValueError, TypeError, StoreError):
            raise _fail("weknora_configuration_invalid", 422) from None
        self._origin = origin.rstrip("/")
        self._token = token
        self._transport = transport
        self._check_token()

    def _check_token(self) -> None:
        try:
            if not isinstance(self._token, str):
                raise TypeError
            if len(self._token) > 16384:
                raise ValueError
            parts = self._token.split(".")
            if len(parts) != 3 or any(_JWT_PART.fullmatch(part) is None for part in parts):
                raise ValueError
            raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
            payload = json.loads(raw, object_pairs_hook=_json_object, parse_constant=_json_constant)
            expiry = payload.get("exp") if isinstance(payload, dict) else None
            if isinstance(expiry, bool) or not isinstance(expiry, (int, float)):
                raise TypeError
            if not math.isfinite(expiry):
                raise ValueError
        except (ValueError, TypeError, binascii.Error, UnicodeError, OverflowError):
            raise _fail("weknora_credentials_invalid", 401) from None
        if expiry <= time.time():
            raise _fail("weknora_credentials_expired", 401)

    async def _request(
        self, method, path, *, body=None, params=None, original=False, files=None, form=None
    ):
        self._check_token()
        maximum = ORIGINAL_LIMIT if original else JSON_LIMIT
        operation = "original" if original else "json"
        try:
            async with (
                asyncio.timeout(25),
                httpx.AsyncClient(
                    transport=self._transport,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(15, connect=5, pool=5),
                    limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
                    headers={
                        "Authorization": "Bearer " + self._token,
                        "X-Tenant-ID": self.workspace_id,
                        "Accept": "application/octet-stream" if original else "application/json",
                    },
                ) as client,
                client.stream(
                    method,
                    self._origin + "/api/v1" + path,
                    json=body,
                    params=params,
                    files=files,
                    data=form,
                ) as response,
            ):
                if response.status_code in {401, 403, 404}:
                    code = {
                        401: "weknora_auth_denied",
                        403: "weknora_scope_denied",
                        404: "weknora_not_found",
                    }[response.status_code]
                    raise _fail(code, response.status_code)
                duplicate = files is not None and response.status_code == 409
                if response.status_code != 200 and not duplicate:
                    raise _fail("weknora_unavailable")
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
                if original:
                    if content_type.lower() in {"application/json", "text/html"}:
                        raise _fail("weknora_response_invalid")
                elif content_type.lower() != "application/json":
                    raise _fail("weknora_response_invalid")
                length = response.headers.get("content-length")
                if length is not None:
                    if not length.isdecimal():
                        raise _fail("weknora_response_invalid")
                    if int(length) > maximum:
                        raise _fail("weknora_response_too_large", 413)
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(raw) + len(chunk) > maximum:
                        raise _fail("weknora_response_too_large", 413)
                    raw.extend(chunk)
            self._check_token()
            if self._token.encode("ascii") in raw:
                raise _fail("weknora_response_invalid")
            if original:
                if not raw:
                    raise _fail("weknora_response_invalid")
                log.info("weknora_original_read", bytes=len(raw))
                return bytes(raw)
            value = json.loads(raw, object_pairs_hook=_json_object, parse_constant=_json_constant)
            if (
                not isinstance(value, dict)
                or not (
                    value.get("success") is True
                    or (duplicate and value.get("code") == "duplicate_file")
                )
                or "data" not in value
            ):
                raise _fail("weknora_response_invalid")
            log.info("weknora_json_read", bytes=len(raw))
            return value
        except StoreError as exc:
            log.warning("weknora_request_rejected", operation=operation, code=exc.code)
            raise
        except (httpx.TimeoutException, TimeoutError):
            log.warning("weknora_request_timeout", operation=operation)
            raise _fail("weknora_timeout", 504) from None
        except httpx.HTTPError:
            log.warning("weknora_request_unavailable", operation=operation)
            raise _fail("weknora_unavailable", 503) from None
        except httpx.InvalidURL:
            log.warning("weknora_configuration_invalid", operation=operation)
            raise _fail("weknora_configuration_invalid", 422) from None
        except (ValueError, TypeError, UnicodeError, RecursionError):
            log.warning("weknora_response_invalid", operation=operation)
            raise _fail("weknora_response_invalid") from None

    @_operation
    async def identity(self) -> dict:
        data = (await self._request("GET", "/auth/me"))["data"]
        if not isinstance(data, dict):
            raise _fail("weknora_response_invalid")
        user, tenant, memberships = data.get("user"), data.get("tenant"), data.get("memberships")
        if (
            not isinstance(user, dict)
            or not isinstance(tenant, dict)
            or not isinstance(memberships, list)
            or user.get("is_active") is not True
            or data.get("tenant_required") is not False
            or _workspace(tenant.get("id")) != self.workspace_id
        ):
            raise _fail("weknora_auth_denied", 401)
        roles = [
            item.get("role")
            for item in memberships
            if isinstance(item, dict) and _workspace(item.get("tenant_id")) == self.workspace_id
        ]
        if len(roles) != 1 or not isinstance(roles[0], str) or roles[0] not in _ROLES:
            raise _fail("weknora_auth_denied", 401)
        return {
            "user_id": _identifier(user.get("id")),
            "workspace_id": self.workspace_id,
            "role": roles[0],
            **(
                {"sso_email": user["email"]}
                if isinstance(user.get("email"), str)
                and "@" in user["email"]
                and len(user["email"]) <= 254
                else {}
            ),
        }

    @_operation
    async def knowledge_bases(self) -> list[dict]:
        data = (await self._request("GET", "/knowledge-bases"))["data"]
        if not isinstance(data, list) or len(data) > 1000:
            raise _fail("weknora_response_invalid")
        result, seen = [], set()
        for item in data:
            if not isinstance(item, dict):
                raise _fail("weknora_response_invalid")
            identifier = _identifier(item.get("id"))
            if identifier in seen or _workspace(item.get("tenant_id")) != self.workspace_id:
                raise _fail("weknora_response_invalid")
            seen.add(identifier)
            result.append(dict(item))
        shared = (await self._request("GET", "/shared-knowledge-bases"))["data"]
        if not isinstance(shared, list) or len(shared) > 1000:
            raise _fail("weknora_response_invalid")
        for item in shared:
            if not isinstance(item, dict) or not isinstance(item.get("knowledge_base"), dict):
                raise _fail("weknora_response_invalid")
            base = item["knowledge_base"]
            identifier = _identifier(base.get("id"))
            source = _workspace(item.get("source_tenant_id"))
            permission = item.get("permission")
            if (
                source != _workspace(base.get("tenant_id"))
                or not isinstance(permission, str)
                or permission not in {"admin", "editor", "viewer"}
            ):
                raise _fail("weknora_response_invalid")
            if identifier in seen:
                if source == self.workspace_id:
                    continue
                raise _fail("weknora_response_invalid")
            seen.add(identifier)
            result.append(
                {
                    **base,
                    "permission": permission,
                    "source_tenant_id": source,
                    "share_id": _identifier(item.get("share_id")),
                    "organization_id": _identifier(item.get("organization_id")),
                }
            )
        return result

    @staticmethod
    def _ids(values, *, optional=False):
        if values is None and optional:
            return None
        if not isinstance(values, list) or not values or len(values) > 128:
            raise _fail("weknora_scope_invalid", 422)
        identifiers = [_identifier(value) for value in values]
        if len(set(identifiers)) != len(identifiers):
            raise _fail("weknora_scope_invalid", 422)
        return identifiers

    @staticmethod
    def _chunk(item) -> dict:
        if not isinstance(item, dict):
            raise _fail("weknora_response_invalid")
        start, end = _integer(item.get("start_at")), _integer(item.get("end_at"))
        if end < start:
            raise _fail("weknora_response_invalid")
        return {
            "chunk_id": _identifier(item.get("id")),
            "document_id": _identifier(item.get("knowledge_id")),
            "kb_id": _identifier(item.get("knowledge_base_id")),
            "title": _text(item.get("title", ""), limit=4096),
            "content": _text(item.get("content")),
            "chunk_index": _integer(item.get("chunk_index")),
            "start_at": start,
            "end_at": end,
        }

    @_operation
    async def search(self, query, kb_ids, document_ids=None, limit=8) -> list[dict]:
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query.encode("utf-8")) > 16000
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise _fail("weknora_query_invalid", 422)
        bases, documents = self._ids(kb_ids), self._ids(document_ids, optional=True)
        result, seen = [], set()
        for kb_id in bases:
            body = {
                "query_text": query,
                "match_count": limit,
                # The pinned service otherwise appends neighboring chunks after TopK.
                "skip_context_enrichment": True,
                "vector_threshold": 0,
                "keyword_threshold": 0,
                "disable_keywords_match": False,
                "disable_vector_match": False,
            }
            if documents is not None:
                body["knowledge_ids"] = documents
            data = (
                await self._request(
                    "POST",
                    "/knowledge-bases/" + kb_id + "/hybrid-search",
                    body=body,
                    params={"resource_urls": "handle"},
                )
            )["data"]
            if not isinstance(data, list) or len(data) > limit:
                raise _fail("weknora_response_invalid")
            for item in data:
                normalized = self._chunk(item)
                if normalized["kb_id"] != kb_id or (
                    documents is not None and normalized["document_id"] not in documents
                ):
                    raise _fail("weknora_scope_denied", 403)
                key = kb_id, normalized["chunk_id"]
                score = item.get("score", 0)
                if (
                    isinstance(score, bool)
                    or not isinstance(score, (int, float))
                    or abs(score) > 1e100
                    or not math.isfinite(score)
                ):
                    raise _fail("weknora_response_invalid")
                if key not in seen:
                    seen.add(key)
                    result.append((score, {**normalized, "score": score}))
        result.sort(key=lambda item: item[0], reverse=True)
        return [item for _score, item in result[:limit]]

    @_operation
    async def document(self, identifier) -> dict:
        identifier = _identifier(identifier)
        data = (await self._request("GET", "/knowledge/" + identifier))["data"]
        return self._document(data, identifier)

    @staticmethod
    def _document(data, identifier=None) -> dict:
        if not isinstance(data, dict) or (identifier is not None and data.get("id") != identifier):
            raise _fail("weknora_response_invalid")
        identifier = _identifier(data.get("id"))
        digest = data.get("file_hash")
        if (
            digest is not None
            and digest != ""
            and (not isinstance(digest, str) or _MD5.fullmatch(digest) is None)
        ):
            raise _fail("weknora_response_invalid")
        filename = _text(data.get("file_name", ""), limit=4096)
        return {
            "id": identifier,
            "kb_id": _identifier(data.get("knowledge_base_id")),
            "title": _text(data.get("title") or filename, limit=4096),
            "file_type": _text(data.get("file_type") or filename.rpartition(".")[2], limit=128),
            "file_hash": digest.lower() if digest else None,
            "type": _text(data.get("type", ""), limit=128),
            "parse_status": _text(data.get("parse_status", ""), limit=128),
            "enable_status": _text(data.get("enable_status", ""), limit=128),
            "metadata": data.get("metadata"),
            "custom_metadata": data.get("custom_metadata"),
            "raw": data,
        }

    @_operation
    async def upload(self, kb_id, filename, content, metadata) -> dict:
        kb_id = _identifier(kb_id)
        if (
            not isinstance(filename, str)
            or not filename
            or len(filename.encode("utf-8")) > 4096
            or filename.startswith("/")
            or any(part in {"", ".", ".."} for part in filename.split("/"))
            or any(ord(char) < 32 for char in filename)
            or not isinstance(content, bytes)
            or not 0 < len(content) <= ORIGINAL_LIMIT
            or not isinstance(metadata, dict)
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items())
        ):
            raise _fail("weknora_upload_invalid", 422)
        encoded_metadata = json.dumps(metadata, ensure_ascii=False, allow_nan=False)
        if len(encoded_metadata.encode("utf-8")) > 16384:
            raise _fail("weknora_upload_invalid", 422)
        result = self._document(
            (
                await self._request(
                    "POST",
                    "/knowledge-bases/" + kb_id + "/knowledge/file",
                    files={
                        "file": (filename.rsplit("/", 1)[-1], content, "application/octet-stream")
                    },
                    form={
                        "fileName": filename,
                        "metadata": encoded_metadata,
                        "process_config": json.dumps({"summary_enabled": False}),
                    },
                )
            )["data"]
        )
        if result["kb_id"] != kb_id or result["file_hash"] != hashlib.md5(content).hexdigest():
            raise _fail("weknora_upload_identity_mismatch")
        return result

    @_operation
    async def documents_in_base(self, kb_id) -> list[dict]:
        kb_id = _identifier(kb_id)
        rows, seen, total = [], set(), None
        for page in range(1, 65):
            value = await self._request(
                "GET",
                "/knowledge-bases/" + kb_id + "/knowledge",
                params={"page": page, "page_size": 100},
            )
            count, data = _integer(value.get("total")), value["data"]
            if (
                count > 6400
                or not isinstance(data, list)
                or value.get("page") != page
                or value.get("page_size") != 100
                or (total is not None and total != count)
                or len(data) != min(100, max(0, count - (page - 1) * 100))
            ):
                raise _fail("weknora_response_invalid")
            total = count
            for item in data:
                row = self._document(item)
                if row["kb_id"] != kb_id or row["id"] in seen:
                    raise _fail("weknora_scope_denied", 403)
                seen.add(row["id"])
                rows.append(row)
            if len(rows) == total:
                return rows
        raise _fail("weknora_response_too_large", 413)

    @_operation
    async def chunks(self, identifier) -> list[dict]:
        identifier = _identifier(identifier)
        result, seen, total = [], set(), None
        for page in range(1, 65):
            value = await self._request(
                "GET",
                "/chunks/" + identifier,
                params={"page": page, "page_size": 100, "chunk_type": "text"},
            )
            count = _integer(value.get("total"))
            if count > 6400:
                raise _fail("weknora_response_too_large", 413)
            data = value["data"]
            if (
                not isinstance(data, list)
                or value.get("page") != page
                or value.get("page_size") != 100
                or (total is not None and count != total)
                or len(data) != min(100, max(0, count - (page - 1) * 100))
            ):
                raise _fail("weknora_response_invalid")
            total = count
            for item in data:
                normalized = self._chunk(item)
                if normalized["document_id"] != identifier or normalized["chunk_id"] in seen:
                    raise _fail("weknora_response_invalid")
                seen.add(normalized["chunk_id"])
                result.append(normalized)
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > JSON_LIMIT:
                raise _fail("weknora_response_too_large", 413)
            if len(result) == total:
                return result
        raise _fail("weknora_response_too_large", 413)

    @_operation
    async def original(self, identifier) -> bytes:
        identifier = _identifier(identifier)
        return await self._request("GET", "/knowledge/" + identifier + "/download", original=True)
