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
from .external_sources import source_label
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
                    from .frozen_archive import OBJECT_FILE

                    archive_file = manifest.get("snapshot_kind") == "hot_evidence" and (
                        item["name"] == "evidence-manifest.json"
                        or OBJECT_FILE.fullmatch(item["name"])
                    )
                    if (
                        item["name"] not in {"rows.json", "rows.csv", "asset-history.json"}
                        and not archive_file
                    ):
                        raise StoreError("资料文件引用非法")
                    if sha(read_file(fd, item["name"])) != item["sha256"]:
                        raise StoreError("资料文件hash校验失败")
                if manifest.get("snapshot_kind") == "asset_history" and read_file(
                    fd, "asset-history.json"
                ) != json_bytes(manifest.get("asset_history")):
                    raise StoreError("历史资料独立 manifest 与快照不一致")
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

    def publish(
        self,
        sid,
        query,
        result,
        *,
        origin=None,
        request_query=None,
        authorization_fingerprint=None,
        asset_history=None,
    ):
        did = str(uuid4())
        parsed = {"rows.json": json_bytes(result.rows), "rows.csv": csv_bytes(result.rows)}
        if asset_history is not None:
            # Subsequent chunks must not mutate an earlier published manifest's
            # in-memory metadata through shared list/dict references.
            asset_history = json.loads(json_bytes(asset_history))
            parsed["asset-history.json"] = json_bytes(asset_history)
        dates = sorted(row["date"] for row in result.rows if "date" in row)
        label = SOURCES.get(query.source) or source_label(query.source) or query.source
        manifest = {
            "id": did,
            "dataset_id": did,
            "name": f"{label} {getattr(query, 'code', None) or ''}".strip(),
            "source": query.source,
            "provider": result.provider_id or query.source,
            "capability": getattr(request_query, "capability", query.source),
            "attempted_sources": result.attempted_sources,
            "source_url": result.source_url,
            "schema_version": SCHEMA_VERSION,
            "query": (request_query or query).model_dump(mode="json", exclude={"refresh"}),
            "provider_query": query.model_dump(mode="json", exclude={"refresh"}),
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
            "provider_metadata": result.metadata,
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
        if asset_history is not None:
            manifest["asset_history"] = asset_history
            manifest["snapshot_kind"] = "asset_history"
            manifest["transformation"] = {
                "owner": "research_web",
                "version": asset_history["canonical_version"],
                "input_count": len(asset_history.get("inputs", [])),
                "provider_query_is_logical_aggregate": True,
            }
        if authorization_fingerprint is not None:
            manifest["authorization_fingerprint"] = authorization_fingerprint
        if origin is not None:
            manifest.update(
                retrieved_at=origin["retrieved_at"],
                origin_dataset_id=origin["dataset_id"],
                origin_manifest_sha256=origin["manifest_sha256"],
            )
        public_files = {**parsed, "manifest.json": json_bytes(manifest)}
        private_files = {f"raw-{index:04d}.bin": raw for index, raw in enumerate(result.raw, 1)}
        private_files["manifest.json"] = public_files["manifest.json"]
        return self._publish_files(sid, did, manifest, public_files, private_files)

    def _publish_files(self, sid, did, manifest, public_files, private_files, *, recover=False):
        temporary = ".pending-" + did
        created = []
        published = set()
        owned_temporary = set()
        committed = False
        try:
            for parts, files, private in [
                (self._private(sid), private_files, True),
                (self._public(sid), public_files, False),
            ]:
                with directory(self.store.root, parts, create=True, private=private) as parent:
                    if temporary not in os.listdir(parent):
                        make_directory(parent, temporary)
                        owned_temporary.add(parts)
                    elif not recover:
                        raise StoreError("资料暂存目录已存在")
                created.append((parts, files, private))
                with directory(self.store.root, (*parts, temporary), private=private) as fd:
                    entries = set(os.listdir(fd))
                    if entries - files.keys():
                        raise StoreError("资料暂存目录内容未知")
                    for name, content in files.items():
                        if name in entries:
                            existing = read_file(fd, name, private=private)
                            if existing == content:
                                continue
                            if (
                                not recover
                                or len(existing) >= len(content)
                                or not content.startswith(existing)
                            ):
                                raise StoreError("资料暂存内容校验失败")
                            unlink_file(fd, name)
                        write_new(fd, name, content)
                    sync_directory(fd)
            # Public bytes first; the private UUID is the only catalog commit marker.
            for parts, files, private in reversed(created):
                with directory(self.store.root, parts, private=private) as parent:
                    if did in os.listdir(parent):
                        if not recover:
                            raise StoreError("资料标识已存在")
                        with directory(self.store.root, (*parts, did), private=private) as fd:
                            if set(os.listdir(fd)) != set(files) or any(
                                read_file(fd, name, private=private) != content
                                for name, content in files.items()
                            ):
                                raise StoreError("已有资料与固定选材不一致")
                        with directory(self.store.root, (*parts, temporary), private=private) as fd:
                            for name in files:
                                unlink_file(fd, name)
                        remove_directory(parent, temporary)
                    else:
                        rename_directory(parent, temporary, did)
                        published.add(parts)
                    if private:
                        committed = True
                    sync_directory(parent)
            log.info(
                "datahub_snapshot_published",
                session_id=sid,
                dataset_id=did,
                status=manifest["status"],
                rows=manifest["row_count"],
            )
            return self.detail(sid, did)
        except (OSError, StoreError):
            log.error("datahub_snapshot_publish_failed", session_id=sid, dataset_id=did)
            # Recovery may encounter somebody else's conflicting bytes. Keep all
            # staged bytes for inspection/retry; the private marker is irreversible.
            if recover or committed:
                raise
            for parts, files, private in created:
                with directory(self.store.root, parts, private=private) as parent:
                    for name in [
                        *([temporary] if parts in owned_temporary else []),
                        *([did] if parts in published else []),
                    ]:
                        if name not in os.listdir(parent):
                            continue
                        with directory(self.store.root, (*parts, name), private=private) as fd:
                            entries = set(os.listdir(fd))
                            if entries - files.keys():
                                raise StoreError("未知暂存内容保留，无法自动清理")
                            for filename in entries:
                                unlink_file(fd, filename)
                        remove_directory(parent, name)
            raise

    def admit_hot_script(self, sid, did):
        """Grant only this owned Hot run's fully verified, immutable evidence copy."""
        from .frozen_archive import OBJECT_FILE, validate_bundle

        row = self.store.session(sid)
        origin = row.get("hot_origin")
        snapshot = self.detail(sid, did)
        binding = snapshot.get("hot")
        if (
            row.get("created") is not True
            or row.get("purpose") != "hot_research"
            or not isinstance(origin, dict)
            or snapshot.get("snapshot_kind") != "hot_evidence"
            or not isinstance(binding, dict)
            or binding.get("runId") != origin.get("runId")
            or binding.get("instanceId") != origin.get("instanceId")
            or binding.get("manifestHash") != origin.get("manifestHash")
        ):
            raise StoreError("冻结资料不属于当前Hot研究会话")
        try:
            # detail already verified the private manifest and all public hashes.
            # One safe directory read avoids revalidating the entire archive per file.
            with directory(self.store.root, ("sessions", sid, "inputs", "datasets", did)) as fd:
                canonical = read_file(fd, "evidence-manifest.json")
                frozen = json.loads(canonical)
                if frozen["instanceId"] != origin["instanceId"]:
                    raise ValueError("hot_instance_mismatch")
                if not isinstance(frozen["objects"], list) or len(frozen["objects"]) > 40:
                    raise ValueError("hot_object_limit")
                values = {}
                for item in frozen["objects"]:
                    if not OBJECT_FILE.fullmatch(item["filename"]):
                        raise ValueError("hot_object_name")
                    values[item["key"]] = read_file(fd, item["filename"])
            validate_bundle(
                {
                    "manifest": frozen,
                    "manifestBytes": canonical,
                    "manifestHash": origin["manifestHash"],
                    "objects": values,
                }
            )
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("hot_script_snapshot_denied")
            raise StoreError("冻结资料校验失败") from exc
        log.info("hot_script_snapshot_admitted", session_id=sid, dataset_id=did)
        return f"inputs/datasets/{did}"

    def publish_hot(self, sid, run_id, bundle, *, origin=None):
        from .frozen_archive import build_archive, validate_bundle

        row = self.store.session(sid)
        if row.get("created") is not True:
            raise StoreError("目标研究会话尚未获得原生创建回执")
        frozen, _, _ = validate_bundle(bundle)
        expected = {
            "runId": run_id,
            "instanceId": frozen["instanceId"],
            "manifestHash": bundle["manifestHash"],
        }
        if origin is None and row.get("hot_origin") != expected:
            raise StoreError("冻结证据不属于目标研究交接")
        key = "hot-publication:" + run_id + ":" + bundle["manifestHash"]
        prepared = self.receipt(sid, key)
        if prepared is None:
            prepared = {"manifestHash": bundle["manifestHash"], "at": datetime.now(UTC).isoformat()}
            self.receipt(sid, key, prepared)
        if prepared.get("manifestHash") != bundle["manifestHash"]:
            raise StoreError("资料准备记录与选材不一致")
        did, manifest, public, private = build_archive(
            sid, run_id, bundle, prepared["at"], origin=origin
        )
        if did in self.ids(sid):
            found = self.detail(sid, did)
            if found.get("hot") != manifest["hot"]:
                raise StoreError("已有资料与固定交接不一致")
            return found
        return self._publish_files(sid, did, manifest, public, private, recover=True)

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
            if original.get("snapshot_kind") == "hot_evidence":
                canonical = self.read(old_sid, did, "evidence-manifest.json")
                frozen = json.loads(canonical)
                values = {
                    item["key"]: self.read(old_sid, did, item["filename"])
                    for item in frozen["objects"]
                }
                copied.append(
                    self.publish_hot(
                        new_sid,
                        original["hot"]["runId"],
                        {
                            "manifest": frozen,
                            "manifestBytes": canonical,
                            "manifestHash": original["hot"]["manifestHash"],
                            "objects": values,
                        },
                        origin=original,
                    )
                )
                continue
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
                metadata=original.get("provider_metadata", {}),
            )

            def parse_query(value):
                if value.get("capability") == "report_weekly":
                    from .providers_wind_api import WindAPIQuery

                    return WindAPIQuery.model_validate(value)
                return (BusinessQuery if "capability" in value else Query).model_validate(value)

            request_query = (
                parse_query(original["query"])
                if "capability" in original.get("query", {})
                else None
            )
            copied.append(
                self.publish(
                    new_sid,
                    parse_query(original.get("provider_query", original["query"])),
                    result,
                    origin=original,
                    request_query=request_query,
                    authorization_fingerprint=original.get("authorization_fingerprint"),
                    asset_history=original.get("asset_history"),
                )
            )
        return copied
