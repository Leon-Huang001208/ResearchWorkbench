"""Validate Hot's exact stored originals before DataHub publishes a target-session copy."""
import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import UUID, uuid5

from core.observability import get_logger
from ..store import StoreError
from .contracts import SCHEMA_VERSION

log = get_logger(__name__)
IDENTITY = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"
OBJECT_FILE = re.compile(r"(?:raw-" + IDENTITY + r"\.bin|material-" + IDENTITY + r"-r[1-9][0-9]{0,9}\.json)")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_bundle(bundle):
    try:
        if not isinstance(bundle, dict) or not isinstance(bundle.get("manifestBytes"), bytes):
            raise ValueError()
        raw = bundle["manifestBytes"]
        if not 0 < len(raw) <= 700000 or digest(raw) != bundle.get("manifestHash"):
            raise ValueError()
        manifest = json.loads(raw)
        if manifest != bundle.get("manifest") or type(manifest.get("schemaVersion")) is not int or manifest["schemaVersion"] != 1:
            raise ValueError()
        UUID(manifest["instanceId"])
        selection = manifest["materialIds"]
        if not isinstance(selection, list) or not 1 <= len(selection) <= 20 or len(set(selection)) != len(selection):
            raise ValueError()
        if not isinstance(bundle.get("objects"), dict) or len(manifest["materials"]) != len(selection):
            raise ValueError()
        originals, filenames = {}, set()
        for item in manifest["objects"]:
            key, name = item["key"], item["filename"]
            if not isinstance(name, str) or not OBJECT_FILE.fullmatch(name) or name in filenames or key in originals:
                raise ValueError()
            if re.fullmatch("raw:" + IDENTITY, key):
                expected_name, expected_format = "raw-" + key[4:] + ".bin", "application/octet-stream"
            elif re.fullmatch("material:" + IDENTITY + r":[1-9][0-9]{0,9}", key):
                _, identity, revision = key.split(":")
                expected_name, expected_format = f"material-{identity}-r{revision}.json", "application/json"
            else:
                raise ValueError()
            if name != expected_name or item["format"] != expected_format:
                raise ValueError()
            content = bundle["objects"][key]
            if (not isinstance(content, bytes) or not 0 <= len(content) <= 8 * 1024 * 1024
                    or type(item["bytes"]) is not int or item["bytes"] != len(content)
                    or digest(content) != item["contentHash"]):
                raise ValueError()
            filenames.add(name)
            originals[key] = (name, content)
        if set(originals) != set(bundle["objects"]) or sum(len(data) for _, data in originals.values()) != manifest["totalBytes"] or manifest["totalBytes"] > 32 * 1024 * 1024:
            raise ValueError()
        materials, referenced = {}, set()
        cutoff = datetime.fromisoformat(manifest["cutoff"].replace("Z", "+00:00"))
        if cutoff.tzinfo is None:
            raise ValueError()
        for item in manifest["materials"]:
            identity = item["materialId"]
            if identity not in selection or identity in materials or type(item["revision"]) is not int or item["revision"] < 1:
                raise ValueError()
            if item["normalizedObject"] != f"material:{identity}:{item['revision']}" or not item["rawObject"].startswith("raw:"):
                raise ValueError()
            name, content = originals[item["normalizedObject"]]
            _, raw_body = originals[item["rawObject"]]
            normalized = json.loads(content)
            if (normalized["materialId"] != identity or normalized["revision"] != item["revision"]
                    or normalized["contentHash"] != item["contentHash"] or normalized["raw"]["key"] != item["rawObject"]
                    or normalized["raw"]["contentHash"] != digest(raw_body)):
                raise ValueError()
            acquired = datetime.fromisoformat(normalized["acquiredAt"].replace("Z", "+00:00"))
            if acquired.tzinfo is None or acquired > cutoff:
                raise ValueError()
            materials[identity] = (normalized, name, acquired.astimezone(UTC))
            referenced.update([item["normalizedObject"], item["rawObject"]])
        if referenced != set(originals) or set(materials) != set(selection):
            raise ValueError()
        return manifest, originals, materials
    except (KeyError, ValueError, TypeError, AttributeError):
        log.warning("hot_snapshot_bundle_rejected")
        raise StoreError("冻结原件清单或内容校验失败；未发布") from None


def build_archive(sid, run_id, bundle, prepared_at, *, origin=None):
    """No provider query is fabricated: this is a stored-evidence snapshot kind."""
    UUID(sid)
    UUID(run_id)
    frozen, originals, materials = validate_bundle(bundle)
    did = str(uuid5(UUID(run_id), "hot-evidence:" + sid + ":" + bundle["manifestHash"]))
    files = {name: data for name, data in originals.values()}
    files["evidence-manifest.json"] = bundle["manifestBytes"]
    rows = [{"material_id": identity, "revision": value["revision"], "title": value["title"],
             "original_url": value["originalUrl"], "published_at": value.get("publishedAt"),
             "acquired_at": value["acquiredAt"], "full_stored_material": name}
            for identity, (value, name, _) in materials.items()]
    from .snapshots import csv_bytes
    from .security import json_bytes
    files.update({"rows.json": json_bytes(rows), "rows.csv": csv_bytes(rows)})
    manifest = {"id": did, "dataset_id": did, "name": "Hot冻结研究证据", "source": "hot_archive",
                "provider": "hot_archive", "capability": "frozen_evidence", "snapshot_kind": "hot_evidence",
                "schema_version": SCHEMA_VERSION,
                "query": {"kind": "hot_frozen_evidence", "run_id": run_id, "brief_id": frozen["briefId"], "version": frozen["version"]},
                "query_fingerprint": bundle["manifestHash"], "source_url": "", "attempted_sources": [],
                "retrieved_at": max(value[2] for value in materials.values()).isoformat(),
                "snapshot_prepared_at": prepared_at, "as_of": frozen["cutoff"], "status": "success",
                "row_count": len(rows), "provider_total": len(rows), "pages_fetched": sum(key.startswith("raw:") for key in originals),
                "pagination_complete": False, "duplicates_removed": 0, "cache_hit": False, "fields": {},
                "requested_range": {}, "actual_range": {}, "coverage": "explicit_frozen_selection",
                "missing": [], "limitations": [*frozen.get("limitations", []), "选材快照，不代表来源/频道/全天完整覆盖；原始响应不等于文章网页全文。"],
                "hot": {"runId": run_id, "instanceId": frozen["instanceId"], "manifestHash": bundle["manifestHash"],
                        "briefId": frozen["briefId"], "version": frozen["version"]},
                "files": [{"name": name, "path": f"inputs/datasets/{did}/{name}", "sha256": digest(data), "size": len(data)} for name, data in files.items()],
                "raw_files": []}
    if origin is not None:
        manifest.update(origin_dataset_id=origin["dataset_id"], origin_manifest_sha256=origin["manifest_sha256"])
    public = {**files, "manifest.json": json_bytes(manifest)}
    # Archive files remain duplicated independently of the Hot DB and another session.
    private = {"manifest.json": public["manifest.json"]}
    return did, manifest, public, private
