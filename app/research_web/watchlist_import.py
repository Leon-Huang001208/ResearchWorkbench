"""Bounded offline CSV decisions and single-Host watchlist import transactions.

Account identity comes only from the existing Store root. No provider, session,
model or secret access belongs here. Store remains a single-process contract.
"""

from __future__ import annotations

import base64
import binascii
import copy
import csv
import hashlib
import io
import json
import re
import time
import unicodedata
from typing import NoReturn
from uuid import uuid4

from core.observability import get_logger

from .store import StoreError

log = get_logger(__name__)
MAX_FILE_BYTES = 1024 * 1024
MAX_ROWS = 1000
MAX_FIELD = 120
MAX_NAMESPACE_BYTES = 8 * 1024 * 1024
MAX_ACTIVE_PREVIEWS = 20
PREVIEW_TTL = 30 * 60
NAMESPACE = "watchlist_imports"


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def reject(code: str, status=409) -> NoReturn:
    log.warning("watchlist_import_rejected", code=code)
    raise StoreError(code, code, status)


def parse_file(body: dict) -> list[dict]:
    encoded = body["file_base64"]
    if len(encoded) > 4 * ((MAX_FILE_BYTES + 2) // 3):
        reject("watchlist_import_file_limit", 413)
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        reject("watchlist_import_encoding_invalid", 422)
    if not raw or len(raw) > MAX_FILE_BYTES:
        reject("watchlist_import_file_limit", 413)
    if hashlib.sha256(raw).hexdigest() != body["file_sha256"]:
        reject("watchlist_import_file_hash_mismatch", 422)
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        if next(reader, None) != ["asset", "asset_type", "name"]:
            reject("watchlist_import_header_invalid", 422)
        rows = []
        for number, fields in enumerate(reader, 1):
            if number > MAX_ROWS:
                reject("watchlist_import_row_limit", 413)
            if len(fields) != 3:
                reject("watchlist_import_columns_invalid", 422)
            for field in fields:
                if len(field) > MAX_FIELD or any(
                    unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in field
                ):
                    reject("watchlist_import_field_invalid", 422)
                if field.strip().startswith(("=", "+", "-", "@")):
                    reject("watchlist_import_formula_rejected", 422)
            rows.append(
                {
                    "row_number": number,
                    "line_number": reader.line_num,
                    "input": dict(zip(("asset", "asset_type", "name"), fields)),
                }
            )
        if not rows:
            reject("watchlist_import_empty", 422)
        return rows
    except (UnicodeError, csv.Error):
        reject("watchlist_import_csv_invalid", 422)


def resolve_rows(rows, catalog, target, selections, skips):
    valid_rows = {str(row["row_number"]) for row in rows}
    if (
        set(selections) - valid_rows
        or len(skips) != len(set(skips))
        or any(type(n) is not int or str(n) not in valid_rows for n in skips)
    ):
        reject("watchlist_import_selection_invalid", 422)
    items = catalog.get("items", ())
    canonical = {row["asset"]: dict(row) for row in items}
    codes, names = {}, {}
    for item in canonical.values():
        codes.setdefault(item["code"], []).append(item)
        names.setdefault(item["name"].casefold(), []).append(item)
    existing = {}
    for item in target["items"]:
        existing.setdefault(str(item.get("asset", "")).upper(), []).append(item)
    seen = set()
    for row in rows:
        number, original = row["row_number"], row["input"]
        value, kind, name = (original[k].strip() for k in ("asset", "asset_type", "name"))
        exact = canonical.get(value.upper())
        candidates = [exact] if exact else codes.get(value, []) or names.get(value.casefold(), [])
        candidate_count = len(candidates)
        candidates = candidates[:50]
        # Only stocks have an authorized canonical identity catalog in this slice.
        if kind != "stock":
            candidates = []
            status = "unsupported_identity_catalog"
        elif catalog["status"] != "ready":
            candidates = []
            status = "catalog_unavailable"
        elif not candidates:
            status = "unresolved"
        elif not exact or name and name != exact["name"]:
            status = "ambiguous" if len(candidates) > 1 else "needs_selection"
        else:
            status = "ready"
        selected = selections.get(str(number))
        if selected is not None and selected not in {item["asset"] for item in candidates}:
            reject("watchlist_import_selection_invalid", 422)
        if selected:
            status = "ready"
        elif status == "ready":
            selected = exact["asset"]
        row.update(
            status=status,
            reason=status,
            candidates=candidates,
            candidate_count=candidate_count if candidates else 0,
            candidates_truncated=candidate_count > len(candidates) if candidates else False,
            selected=selected,
            proposed_action="blocked",
        )
        if number in skips:
            row.update(status="skipped", proposed_action="skip_explicit")
            continue
        if status != "ready":
            continue
        old = existing.get(selected, [])
        if len(old) > 1 or old and old[0].get("asset_type") != "stock":
            row.update(status="target_integrity_conflict", reason="target_integrity_conflict")
        elif old:
            row["proposed_action"] = "skip_existing"
        elif selected in seen:
            row["proposed_action"] = "skip_file_duplicate"
        else:
            row["proposed_action"] = "add"
            seen.add(selected)
    return rows


class WatchlistImports:
    """All entrypoints are synchronous and called under the workspace writer lock."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.store = workspace.store
        self.clock = time.time
        self.scope = hashlib.sha256(str(self.store.root).encode()).hexdigest()

    def _target(self, target_id):
        if (
            not re.fullmatch(r"[a-f0-9-]{36}", target_id)
            or target_id not in self.store.data["watchlists"]
        ):
            reject("watchlist_import_not_found", 404)
        return self.store.data["watchlists"][target_id]

    def _namespace(self):
        value = self.store.data.get(NAMESPACE, {"schema_version": 1, "previews": {}, "keys": {}})
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 1
            or not isinstance(value.get("previews"), dict)
            or not isinstance(value.get("keys"), dict)
        ):
            reject("watchlist_import_storage_invalid", 503)
        return copy.deepcopy(value)

    @staticmethod
    def _budget(namespace):
        if (
            len(json.dumps(namespace, ensure_ascii=False, allow_nan=False).encode())
            > MAX_NAMESPACE_BYTES
        ):
            reject("watchlist_import_storage_limit", 413)

    def _save(self, namespace, target_id=None, target=None):
        self._budget(namespace)
        absent = object()
        old_namespace = self.store.data.get(NAMESPACE, absent)
        old_target = self.store.data["watchlists"].get(target_id)
        self.store.data[NAMESPACE] = namespace
        if target_id is not None:
            self.store.data["watchlists"][target_id] = target
        try:
            self.store.save()
        except Exception as exc:  # Restore references on every pre-replace failure.
            if old_namespace is absent:
                self.store.data.pop(NAMESPACE, None)
            else:
                self.store.data[NAMESPACE] = old_namespace
            if target_id is not None:
                self.store.data["watchlists"][target_id] = old_target
            log.error("watchlist_import_persist_failed", error_type=type(exc).__name__)
            raise StoreError(
                "watchlist_import_persist_failed", "watchlist_import_persist_failed", 503
            ) from exc

    @staticmethod
    def _seal(manifest):
        return digest(
            {
                k: v
                for k, v in manifest.items()
                if k not in {"preview_digest", "superseded", "receipt"}
            }
        )

    def preview(self, target_id, body):
        target = self._target(target_id)
        rows = parse_file(body)
        catalog = self.workspace.directory.offline_snapshot()
        rows = resolve_rows(
            rows, catalog, target, body.get("selections", {}), body.get("skipped_rows", [])
        )
        namespace, now = self._namespace(), self.clock()
        namespace["previews"] = {
            key: value
            for key, value in namespace["previews"].items()
            if value.get("receipt") or value["expires_at"] > now
        }
        # A changed decision for the same original bytes supersedes its earlier freeze.
        for value in namespace["previews"].values():
            if (
                value["target_id"] == target_id
                and value["file_sha256"] == body["file_sha256"]
                and not value.get("receipt")
            ):
                value["superseded"] = True
        if (
            sum(
                not v.get("receipt") and not v.get("superseded")
                for v in namespace["previews"].values()
            )
            >= MAX_ACTIVE_PREVIEWS
        ):
            reject("watchlist_import_preview_limit", 429)
        manifest = {
            "schema_version": 1,
            "import_id": str(uuid4()),
            "scope": self.scope,
            "target_id": target_id,
            "target_digest": digest(target),
            "file_sha256": body["file_sha256"],
            "catalog_digest": catalog["digest"],
            "catalog_status": catalog["status"],
            "catalog_failure": catalog.get("failure_code"),
            "rows": rows,
            "created_at": now,
            "expires_at": now + PREVIEW_TTL,
            "can_confirm": catalog["status"] == "ready"
            and all(r["proposed_action"] != "blocked" for r in rows),
        }
        manifest["preview_digest"] = self._seal(manifest)
        namespace["previews"][manifest["import_id"]] = manifest
        self._save(namespace)
        log.info(
            "watchlist_import_preview_created", import_id=manifest["import_id"], count=len(rows)
        )
        return {k: copy.deepcopy(v) for k, v in manifest.items() if k != "scope"}

    def confirm(self, target_id, import_id, body, key):
        self._target(target_id)
        # Recheck account authorization before serving even a committed receipt.
        catalog = self.workspace.directory.offline_snapshot()
        if catalog.get("failure_code") in {
            "asset_directory_unauthorized",
            "asset_directory_closed",
        }:
            reject("watchlist_import_catalog_unauthorized", 409)
        namespace = self._namespace()
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        binding = {
            "scope": self.scope,
            "target_id": target_id,
            "preview_digest": body["preview_digest"],
            "import_id": import_id,
        }
        prior = namespace["keys"].get(key_hash)
        if prior:
            if prior["binding"] != binding:
                reject("watchlist_import_idempotency_conflict")
            return copy.deepcopy(prior["receipt"])
        manifest = namespace["previews"].get(import_id)
        if not manifest or manifest["target_id"] != target_id or manifest["scope"] != self.scope:
            reject("watchlist_import_not_found", 404)
        if manifest["preview_digest"] != body["preview_digest"]:
            reject("watchlist_import_preview_mismatch")
        if manifest.get("receipt"):
            receipt = manifest["receipt"]
            namespace["keys"][key_hash] = {"binding": binding, "receipt": receipt}
            self._save(namespace)
            return copy.deepcopy(receipt)
        if manifest.get("superseded") or self.clock() >= manifest["expires_at"]:
            reject("watchlist_import_preview_expired")
        if self._seal(manifest) != manifest["preview_digest"]:
            reject("watchlist_import_preview_corrupt")
        if catalog["status"] != "ready" or catalog["digest"] != manifest["catalog_digest"]:
            reject("watchlist_import_catalog_changed")
        old = self._target(target_id)
        if digest(old) != manifest["target_digest"]:
            reject("watchlist_import_target_changed")
        if not manifest["can_confirm"]:
            reject("watchlist_import_unresolved")
        target, added = copy.deepcopy(old), []
        for row in manifest["rows"]:
            if row["proposed_action"] != "add":
                continue
            candidate = next(item for item in row["candidates"] if item["asset"] == row["selected"])
            item = {
                "id": str(uuid4()),
                "asset": candidate["asset"],
                "asset_type": "stock",
                "name": candidate["name"],
                "created_at": self.clock(),
            }
            target["items"].append(item)
            added.append(item["id"])
        if added:
            target["updated_at"] = self.clock()
        receipt = {
            "schema_version": 1,
            "import_id": import_id,
            "target_id": target_id,
            "preview_digest": manifest["preview_digest"],
            "file_sha256": manifest["file_sha256"],
            "before_digest": manifest["target_digest"],
            "after_digest": digest(target),
            "added_item_ids": added,
            "added_count": len(added),
            "skipped_count": len(manifest["rows"]) - len(added),
            "status": "committed" if added else "no_changes",
        }
        # Committed manifests retain decisions/hashes, not the private CSV/candidate bodies.
        namespace["previews"][import_id] = {k: v for k, v in manifest.items() if k != "rows"}
        namespace["previews"][import_id].update(
            receipt=receipt,
            decisions=[
                {
                    "row_number": r["row_number"],
                    "selected": r["selected"],
                    "action": r["proposed_action"],
                }
                for r in manifest["rows"]
            ],
        )
        namespace["keys"][key_hash] = {"binding": binding, "receipt": receipt}
        self._save(namespace, target_id, target)
        log.info("watchlist_import_committed", import_id=import_id, count=len(added))
        return copy.deepcopy(receipt)
