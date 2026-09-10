"""Immutable session snapshots; private hashes authorize public dataset reads."""

import csv
import hashlib
import io
import json
import os
import re
from datetime import UTC, datetime
from uuid import uuid4

from core.observability import get_logger

from ..store import Store, StoreError
from .contracts import SCHEMA_VERSION, SOURCES
from .security import (
    atomic_json,
    directory,
    json_bytes,
    make_directory,
    read_file,
    remove_directory,
    rename_directory,
    sync_directory,
    unlink_file,
    write_new,
)

log = get_logger(__name__)
UUID = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    columns = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(stream, columns)
    # Header labels from provider tables are untrusted text too.
    for row in [{key: key for key in columns}, *rows]:
        safe = {}
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if (
                isinstance(value, str)
                and not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value)
                and (
                    value.startswith(("\t", "\r", "\n"))
                    or value.lstrip().startswith(("=", "+", "-", "@"))
                )
            ):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return stream.getvalue().encode("utf-8-sig")


class Snapshots:
    def __init__(self, store: Store):
        self.store = store

    def _private(self, sid):
        self.store.session(sid)
        return (".control", "snapshots", sid)

    def _public(self, sid):
        self.store.session(sid)
        return ("sessions", sid, "inputs", "datasets")

    def receipt(self, sid, call_id, value=None):
        parts = (".control", "calls", sid)
        self.store.session(sid)
        name = sha(call_id.encode()) + ".json"
        with directory(self.store.root, parts, create=True, private=True) as fd:
            if value is not None:
                atomic_json(fd, name, value)
            if name not in os.listdir(fd):
                return None
            try:
                return json.loads(read_file(fd, name, private=True))
            except ValueError as exc:
                raise StoreError("资料调用记录不可读取") from exc

    def ids(self, sid):
        self.store.session(sid)
        with directory(self.store.root, (".control",), private=True) as fd:
            if "snapshots" not in os.listdir(fd):
                return []
        with directory(self.store.root, (".control", "snapshots"), private=True) as fd:
            if sid not in os.listdir(fd):
                return []
        with directory(self.store.root, self._private(sid), private=True) as fd:
            return [name for name in os.listdir(fd) if UUID.fullmatch(name)]

    def detail(self, sid, did):
        if not UUID.fullmatch(did):
            raise StoreError("数据集不存在")
        with directory(self.store.root, (*self._private(sid), did), private=True) as fd:
            raw = read_file(fd, "manifest.json", private=True)
        try:
            manifest = json.loads(raw)
            if manifest["dataset_id"] != did:
                raise ValueError("id mismatch")
            with directory(self.store.root, (*self._public(sid), did)) as fd:
                if read_file(fd, "manifest.json") != raw:
                    raise StoreError("资料manifest校验失败")
                for item in manifest["files"]:
                    if item["name"] not in {"rows.json", "rows.csv"}:
                        raise StoreError("资料文件引用非法")
                    if sha(read_file(fd, item["name"])) != item["sha256"]:
                        raise StoreError("资料文件hash校验失败")
            manifest["manifest_sha256"] = sha(raw)
            manifest["files"].append(
                {
                    "name": "manifest.json",
                    "path": f"inputs/datasets/{did}/manifest.json",
                    "sha256": sha(raw),
                    "size": len(raw),
                }
            )
            for item in manifest["files"]:
                item["url"] = f"/api/research/sessions/{sid}/datasets/{did}/files/{item['name']}"
                item["kind"] = "dataset"
            return manifest
        except (ValueError, KeyError, TypeError) as exc:
            raise StoreError("资料manifest不可读取") from exc

    def read(self, sid, did, name):
        detail = self.detail(sid, did)
        item = next((item for item in detail["files"] if item["name"] == name), None)
        if item is None:
            raise StoreError("数据集文件不存在")
        with directory(self.store.root, (*self._public(sid), did)) as fd:
            raw = read_file(fd, name)
        if sha(raw) != item["sha256"]:
            raise StoreError("资料文件hash校验失败")
        return raw

    def publish(self, sid, query, result, *, origin=None, request_query=None):
        did = str(uuid4())
        temporary = ".pending-" + did
        parsed = {"rows.json": json_bytes(result.rows), "rows.csv": csv_bytes(result.rows)}
        dates = sorted(row["date"] for row in result.rows if "date" in row)
        manifest = {
            "id": did,
            "dataset_id": did,
            "name": f"{SOURCES.get(query.source, query.source)} {getattr(query, 'code', None) or ''}".strip(),
            "source": query.source,
            "provider": result.provider_id or query.source,
            "capability": getattr(request_query, "capability", query.source),
            "attempted_sources": result.attempted_sources,
            "source_url": result.source_url,
            "schema_version": SCHEMA_VERSION,
            "query": (request_query or query).model_dump(exclude={"refresh"}),
            "provider_query": query.model_dump(exclude={"refresh"}),
            "query_fingerprint": (request_query or query).fingerprint(),
            "retrieved_at": datetime.now(UTC).isoformat(),
            "as_of": result.as_of,
            "status": result.status,
            "row_count": len(result.rows),
            "provider_total": result.provider_total,
            "pages_fetched": result.pages_fetched,
            "pagination_complete": result.pagination_complete,
            "duplicates_removed": result.duplicates,
            "cache_hit": False,
            "fields": result.fields,
            "requested_range": {
                "start_date": getattr(query, "start_date", None)
                or getattr(query, "parameters", {}).get("start_date"),
                "end_date": getattr(query, "end_date", None)
                or getattr(query, "parameters", {}).get("end_date"),
            },
            "actual_range": {
                "start_date": dates[0] if dates else None,
                "end_date": dates[-1] if dates else None,
            },
            "coverage": "来源响应范围；pagination_complete仅表示来源分页结束，不是市场全量独立验证。",
            "missing": result.missing,
            "limitations": [
                *result.limitations,
                "CSV公式样式文本前置单引号；原始JSON保留原值，合法数值不转义。",
            ],
            "files": [
                {
                    "name": name,
                    "path": f"inputs/datasets/{did}/{name}",
                    "sha256": sha(raw),
                    "size": len(raw),
                }
                for name, raw in parsed.items()
            ],
            "raw_files": [
                {
                    "name": f"raw-{index:04d}.bin",
                    "path": f".control/snapshots/{sid}/{did}/raw-{index:04d}.bin",
                    "sha256": sha(raw),
                    "size": len(raw),
                }
                for index, raw in enumerate(result.raw, 1)
            ],
        }
        if origin is not None:
            manifest.update(
                retrieved_at=origin["retrieved_at"],
                origin_dataset_id=origin["dataset_id"],
                origin_manifest_sha256=origin["manifest_sha256"],
            )
        public_files = {**parsed, "manifest.json": json_bytes(manifest)}
        private_files = {f"raw-{index:04d}.bin": raw for index, raw in enumerate(result.raw, 1)}
        private_files["manifest.json"] = public_files["manifest.json"]
        created = []
        try:
            for parts, files, private in [
                (self._private(sid), private_files, True),
                (self._public(sid), public_files, False),
            ]:
                with directory(self.store.root, parts, create=True, private=private) as parent:
                    make_directory(parent, temporary)
                created.append((parts, files, private))
                with directory(self.store.root, (*parts, temporary), private=private) as fd:
                    for name, content in files.items():
                        write_new(fd, name, content)
                    sync_directory(fd)
            # No await within publication; cancellation is checked immediately before it.
            # Publish public inputs first; the private UUID is the catalog commit marker.
            # A process exit between renames leaves only ignored, uncommitted inputs.
            for parts, _, private in reversed(created):
                with directory(self.store.root, parts, private=private) as fd:
                    rename_directory(fd, temporary, did)
                    sync_directory(fd)
            log.info(
                "datahub_snapshot_published",
                session_id=sid,
                dataset_id=did,
                status=result.status,
                rows=len(result.rows),
            )
            return self.detail(sid, did)
        except (OSError, StoreError):
            log.error("datahub_snapshot_publish_failed", session_id=sid, dataset_id=did)
            # Exact newly-created snapshot only; never remove a pre-existing dataset.
            for parts, files, private in created:
                with directory(self.store.root, parts, private=private) as parent:
                    for name in (temporary, did):
                        if name not in os.listdir(parent):
                            continue
                        with directory(self.store.root, (*parts, name), private=private) as fd:
                            for filename in files:
                                if filename in os.listdir(fd):
                                    unlink_file(fd, filename)
                        remove_directory(parent, name)
            raise

    def copy_for_upgrade(self, old_sid, new_sid):
        """User-triggered copy only, never cross-session caching or file links."""
        return self.copy_selected(old_sid, new_sid, self.ids(old_sid))

    def copy_selected(self, old_sid, new_sid, dataset_ids):
        """Copy an explicit, validated subset into another owned session."""
        from .contracts import BusinessQuery, Query
        from .providers import Result

        self.store.session(new_sid)
        available = set(self.ids(old_sid))
        requested = list(dict.fromkeys(dataset_ids))
        if any(did not in available for did in requested):
            raise StoreError("交接数据集不存在或不属于来源会话")
        copied = []
        for did in requested:
            original = self.detail(old_sid, did)
            raw = []
            with directory(self.store.root, (*self._private(old_sid), did), private=True) as fd:
                for item in original["raw_files"]:
                    content = read_file(fd, item["name"], private=True)
                    if sha(content) != item["sha256"]:
                        raise StoreError("原始资料hash校验失败，未复制")
                    raw.append(content)
            result = Result(
                rows=json.loads(self.read(old_sid, did, "rows.json")),
                raw=raw,
                source_url=original["source_url"],
                status=original["status"],
                pages_fetched=original["pages_fetched"],
                provider_total=original["provider_total"],
                pagination_complete=original["pagination_complete"],
                limitations=original["limitations"],
                missing=original["missing"],
                fields=original["fields"],
                duplicates=original["duplicates_removed"],
                as_of=original["as_of"],
                provider_id=original.get("provider"),
                attempted_sources=original.get("attempted_sources", []),
            )
            request_query = (
                BusinessQuery.model_validate(original["query"])
                if "capability" in original.get("query", {})
                else None
            )
            copied.append(
                self.publish(
                    new_sid,
                    Query.model_validate(original.get("provider_query", original["query"])),
                    result,
                    origin=original,
                    request_query=request_query,
                )
            )
        return copied
