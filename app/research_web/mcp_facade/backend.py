"""Fixed frozen GET adapter. No discovery, arbitrary URL, or execution fallback."""

import hashlib
import json
import re
from datetime import date
from types import SimpleNamespace
from uuid import UUID

import httpx

from core.observability import get_logger

from ..datahub.contracts import BusinessQuery
from ..multiuser.runtime import RuntimeErrorSafe
from .config import MATERIAL_BYTES
from .read_policy import HEADER, VERSION

log = get_logger(__name__)
PUBLIC_DATA_SOURCES = frozenset({"ext_fred", "ext_bls"})


def public_data_query(source: str, series_id: str, start_date: str, end_date: str) -> BusinessQuery:
    """Build the two public inventory contracts, never accept caller URL or secrets."""
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if (
        source not in PUBLIC_DATA_SOURCES
        or not isinstance(series_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", series_id)
        or start > end
        or (end - start).days > 366
    ):
        raise ValueError("unsupported_public_data_query")
    arguments = (
        {
            "params": {"series": series_id},
            "query": {"cosd": start.isoformat(), "coed": end.isoformat()},
        }
        if source == "ext_fred"
        else {
            "body": {
                "seriesid": [series_id],
                "startyear": str(start.year),
                "endyear": str(end.year),
            }
        }
    )
    return BusinessQuery(
        capability="external_data",
        source=source,
        allow_fallback=False,
        parameters={"dataset": "series", "arguments_json": json.dumps(arguments), "limit": 500},
        purpose="research",
        quality="strict",
        refresh=True,
    )


class ReadError(Exception):
    """Stable safe error; never carry upstream bodies or credentials."""


def canonical_id(value: str, *, file=False) -> str:
    try:
        valid = bool(re.fullmatch(r"[0-9a-f]{24}", value)) if file else str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ReadError("invalid_material_identifier")
    return value


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode(raw: bytes):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        raise ReadError("frozen_material_invalid") from None


class FrozenBackend:
    def __init__(self, pool, client: httpx.AsyncClient):
        self.pool, self.client = pool, client

    async def _get(self, backend, path, *, probe=False):
        headers = {"Origin": backend.url, HEADER: "probe-v1" if probe else VERSION}
        if backend.key:
            headers["X-RWB-Tenant-Gateway-Key"] = backend.key
        # Direct construction avoids defaults/cookie-jar merging; never mutate
        # shared cookie state while independent accounts are reading.
        request = httpx.Request("GET", backend.url + path, headers=headers)
        try:
            response = await self.client.send(
                request, auth=None, stream=True, follow_redirects=False
            )
            try:
                if response.status_code != 200:
                    raise ReadError("frozen_read_unavailable")
                if response.headers.get(HEADER) != VERSION:
                    raise ReadError("frozen_read_protocol_required")
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > (1024 if probe else MATERIAL_BYTES):
                        raise ReadError("frozen_material_too_large")
                return bytes(raw)
            finally:
                await response.aclose()
        except httpx.HTTPError:
            log.warning("mcp_frozen_backend_unavailable")
            raise ReadError("frozen_read_unavailable") from None

    async def read(self, user_id, material, *, offset=0, limit=100, view="rows"):
        if view not in {"manifest", "rows"}:
            raise ReadError("unsupported_dataset_view")
        sid = canonical_id(material.context_id)
        oid = canonical_id(material.object_id, file=material.kind == "source")
        if material.kind not in {"dataset", "source"}:
            raise ReadError("unsupported_material_kind")
        lookup = getattr(self.pool, "backend_for_readonly", None)
        if not callable(lookup):
            raise ReadError("readonly_runtime_lookup_required")
        try:
            backend = await lookup(user_id)
        except RuntimeErrorSafe as exc:
            log.warning("mcp_runtime_busy", code=exc.code)
            raise ReadError(exc.code) from None
        # An old host can ignore the strict header and write during GET. Probe
        # the existing pure catalog route before ANY material read; never cache.
        probe = decode(await self._get(backend, "/api/research/data/catalog", probe=True))
        if probe != {"frozen_read_protocol": VERSION}:
            raise ReadError("frozen_read_protocol_required")
        base = f"/api/research/sessions/{sid}"
        if material.kind == "source":
            raw = await self._get(backend, f"{base}/files/{oid}/download")
            if digest(raw) != material.sha256:
                raise ReadError("frozen_material_changed")
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeError:
                raise ReadError("source_not_utf8") from None
            if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
                raise ReadError("source_not_text")
            fragment = text[offset : offset + limit]
            return {
                "text": fragment,
                "offset": offset,
                "limit": limit,
                "total_characters": len(text),
                "partial": offset > 0 or offset + len(fragment) < len(text),
                "original_sha256": digest(raw),
                "fragment_sha256": digest(fragment.encode()),
                "representation": "frozen_extracted_utf8_text",
                "provenance": {"status": "missing", "as_of": None, "url": None, "pit": "unknown"},
            }
        base += f"/datasets/{oid}/files"
        manifest_raw = await self._get(backend, base + "/manifest.json")
        if digest(manifest_raw) != material.sha256:
            raise ReadError("frozen_material_changed")
        manifest = decode(manifest_raw)
        if not isinstance(manifest, dict) or manifest.get("dataset_id") != oid:
            raise ReadError("frozen_manifest_invalid")
        if view == "manifest":
            try:
                original = manifest_raw.decode("utf-8", errors="strict")
            except UnicodeError:
                raise ReadError("manifest_not_utf8") from None
            return {
                "view": "manifest",
                "manifest": manifest,
                "original_manifest": original,
                "manifest_sha256": digest(manifest_raw),
                "representation": "original_manifest_json_utf8",
                "original_bytes": len(manifest_raw),
                "partial": False,
            }
        files = manifest.get("files", [])
        entries = (
            [item for item in files if isinstance(item, dict) and item.get("name") == "rows.json"]
            if isinstance(files, list)
            else []
        )
        if len(entries) != 1:
            raise ReadError("frozen_rows_unavailable")
        raw = await self._get(backend, base + "/rows.json")
        if digest(raw) != entries[0].get("sha256"):
            raise ReadError("frozen_rows_changed")
        rows = decode(raw)
        if not isinstance(rows, list):
            raise ReadError("frozen_rows_invalid")
        selected = rows[offset : offset + limit]
        fragment = json.dumps(selected, ensure_ascii=False, separators=(",", ":")).encode()
        return {
            "view": "rows",
            "items": selected,
            "offset": offset,
            "limit": limit,
            "total": len(rows),
            "partial": offset > 0 or offset + len(selected) < len(rows),
            "manifest_sha256": digest(manifest_raw),
            "rows_sha256": digest(raw),
            "fragment_sha256": digest(fragment),
            "fragment_encoding": "utf8_json_compact",
            "manifest": manifest,
        }


class DataHubBackend(FrozenBackend):
    """Opt-in public queries on an already-running account Host/DataHub."""

    async def _backend(self, user_id):
        try:
            return await self.pool.backend_for_readonly(user_id)
        except (RuntimeErrorSafe, AttributeError) as exc:
            code = (
                exc.code
                if isinstance(exc, RuntimeErrorSafe)
                else "readonly_runtime_lookup_required"
            )
            log.warning("mcp_datahub_runtime_unavailable", code=code)
            raise ReadError(code) from None

    async def _request(self, backend, method, path, *, body=None, key=None):
        headers = {"Origin": backend.url}
        if backend.key:
            headers["X-RWB-Tenant-Gateway-Key"] = backend.key
        if key:
            headers["Idempotency-Key"] = key
        request = httpx.Request(method, backend.url + path, headers=headers, json=body)
        try:
            response = await self.client.send(
                request, auth=None, stream=True, follow_redirects=False
            )
            try:
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MATERIAL_BYTES:
                        raise ReadError("data_query_response_too_large")
                value = decode(bytes(raw))
                if response.status_code not in (200, 201, 202):
                    detail = value.get("error", {}) if isinstance(value, dict) else {}
                    code = detail.get("code") if isinstance(detail, dict) else None
                    raise ReadError(
                        code
                        if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,80}", code)
                        else "data_query_unavailable"
                    )
                if not isinstance(value, dict):
                    raise ReadError("data_query_response_invalid")
                return value
            finally:
                await response.aclose()
        except httpx.HTTPError:
            log.warning("mcp_datahub_backend_unavailable")
            raise ReadError("data_query_unavailable") from None

    async def _context(self, backend, record, *, create=False):
        value = await self._request(
            backend,
            "POST",
            "/api/research/data/contexts",
            body={"grant_id": canonical_id(record.grant_id), "create": create},
        )
        if value.get("grant_id") != record.grant_id:
            raise ReadError("data_context_mismatch")
        return canonical_id(value.get("session_id"))

    async def query(self, record, request_id, source, series_id, start_date, end_date):
        if not isinstance(request_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_.:-]{1,64}", request_id
        ):
            raise ValueError("invalid_query_request_id")
        query = public_data_query(source, series_id, start_date, end_date)
        backend = await self._backend(record.user_id)
        sid = await self._context(backend, record, create=True)
        key = hashlib.sha256((record.grant_id + ":" + request_id).encode()).hexdigest()
        result = await self._request(
            backend,
            "POST",
            "/api/research/data/queries",
            key=key,
            body={"session_id": sid, "section": "market", "query": query.model_dump(mode="json")},
        )
        if result.get("session_id") != sid:
            raise ReadError("data_context_mismatch")
        log.info("mcp_public_data_query_submitted", source=source)
        return result

    async def _owned_query(self, record, query_id):
        backend = await self._backend(record.user_id)
        sid = await self._context(backend, record)
        result = await self._request(
            backend, "GET", "/api/research/data/queries/" + canonical_id(query_id)
        )
        if (
            result.get("session_id") != sid
            or result.get("source") not in PUBLIC_DATA_SOURCES
            or result.get("capability") != "external_data"
        ):
            raise ReadError("access_denied")
        return backend, result

    async def status(self, record, query_id, *, offset=0, limit=100):
        backend, result = await self._owned_query(record, query_id)
        result["data_success"] = None if result.get("status") == "running" else False
        dataset = result.get("dataset")
        if (
            result.get("status") == "completed"
            and isinstance(dataset, dict)
            and dataset.get("dataset_id")
        ):
            sid, did = canonical_id(result["session_id"]), canonical_id(dataset["dataset_id"])
            base = f"/api/research/sessions/{sid}/datasets/{did}/files/"
            raw = await self._get(backend, base + "manifest.json")
            material = SimpleNamespace(
                context_id=sid, object_id=did, kind="dataset", sha256=digest(raw)
            )
            # Reuse the original bounded/hash-checked dataset reader. This new
            # scope authorizes only results of this grant's public queries;
            # it does not approve unrelated materials for the four old tools.
            result["result"] = await self.read(record.user_id, material, offset=offset, limit=limit)
            manifest = result["result"]["manifest"]
            result["data_success"] = manifest.get("provider_metadata", {}).get(
                "quality_accepted", manifest["status"] in {"complete", "snapshot", "empty"}
            )
        return result

    async def cancel(self, record, query_id):
        backend, _ = await self._owned_query(record, query_id)
        return await self._request(
            backend, "POST", "/api/research/data/queries/" + canonical_id(query_id) + "/cancel"
        )
