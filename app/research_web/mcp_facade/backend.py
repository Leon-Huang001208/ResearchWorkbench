"""Fixed frozen GET adapter. No discovery, arbitrary URL, or execution fallback."""

import hashlib
import json
import re
from uuid import UUID

import httpx

from core.observability import get_logger

from ..multiuser.runtime import RuntimeErrorSafe
from .config import MATERIAL_BYTES
from .read_policy import HEADER, VERSION

log = get_logger(__name__)


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
