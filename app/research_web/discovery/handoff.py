"""Durable native identity and immutable context for a manual discovery handoff."""

import asyncio
import hashlib
import os
import shutil
import time
from pathlib import Path

from core.observability import get_logger

from ..client import RuntimeFailure
from ..datahub.security import directory, json_bytes, read_file, sync_directory, write_new
from ..store import StoreError
from .models import DiscoveryError
from .sources import SOURCE_POLICY

log = get_logger(__name__)
CONTEXT_FILE = "inputs/discovery-context.json"


def context_bytes(record):
    value = {
        "schema_version": "discovery-handoff-1",
        "handoff_id": record["handoff_id"],
        "session_id": record["session_id"],
        "target_mode": record["target_mode"],
        "dataset_id": record["dataset_id"],
        "dataset_manifest_sha256": record["dataset_manifest_sha256"],
        "selection_sha256": record["selection_sha256"],
        "cutoff": record["cutoff"],
        "retrieved_at": record["retrieved_at"],
        "question": record["question"],
        "horizon": record["horizon"],
        "materials": record["materials"],
        "source_policy": SOURCE_POLICY,
    }
    if record.get("source_kind") == "news":
        value.update(
            schema_version="discovery-handoff-2",
            source_kind="news",
            associations=record.get("associations", []),
        )
    if "scenario_context" in record:
        value.update(
            schema_version="discovery-handoff-3", scenario_context=record["scenario_context"]
        )
    return json_bytes(value)


def write_context(research, record):
    raw = context_bytes(record)
    with directory(research.store.root, ("sessions", record["session_id"], "inputs")) as fd:
        if "discovery-context.json" in os.listdir(fd):
            if read_file(fd, "discovery-context.json") != raw:
                raise DiscoveryError("研究上下文已变化", "discovery_context_changed", 409)
        else:
            write_new(fd, "discovery-context.json", raw)
            sync_directory(fd)
    record["context_sha256"] = hashlib.sha256(raw).hexdigest()
    record["context_file"] = CONTEXT_FILE


async def ensure_session(research, record, *, mutate):
    """GETs only observe; a lost create reply can never trigger another create."""
    await research.ensure_owned()
    async with research.lock:
        sid = record["session_id"]
        row = research.store.session(sid)
        expected = {
            "handoff_id": record["handoff_id"],
            "selection_sha256": record["selection_sha256"],
        }
        if row.get("purpose") != "discovery_research" or row.get("discovery_origin") != expected:
            raise DiscoveryError("研究会话归属不一致", "discovery_session_foreign", 409)
        native = await research.client.rpc("session.list", {})
        if (
            not isinstance(native, dict)
            or not isinstance(native.get("items"), list)
            or any(
                not isinstance(item, dict) or not isinstance(item.get("sessionId"), str)
                for item in native["items"]
            )
        ):
            raise RuntimeFailure("原生会话列表不可核验", "discovery_session_list_invalid")
        matches = [item for item in native["items"] if item["sessionId"] == sid]
        if len(matches) > 1:
            raise DiscoveryError("原生会话身份不唯一", "discovery_session_foreign", 409)
        phase = row.get("discovery_creation_state")
        if matches:
            if phase == "reserved" or matches[0].get("cwd") != str(research.store.directory(sid)):
                raise DiscoveryError("原生会话工作区归属不一致", "discovery_session_foreign", 409)
            if phase == "ready" and row.get("created") is True:
                record["state"] = "snapshot_ready"
                record.pop("code", None)
                return True
            if not mutate:
                record["state"] = "session_configuration_required"
                return False
        elif phase != "reserved" or not mutate:
            record["state"] = "session_outcome_unknown"
            return False
        if row.get("model") is None:
            selection = dict(research.default_model)
            row.update(
                model=selection["model"],
                model_provider=selection["provider"],
                model_profile_id=research.model_profile_identity(selection["provider"]),
            )
            if selection["provider"] == "openai-compatible":
                connection = research.compatible_connection()
                row["model_connection_binding"] = {
                    key: connection[key] for key in ("base_url", "protocol", "credential_mode")
                }
            research.store.save()
        if not matches:
            from ..datahub.security import _is_reparse_point

            destination = research.store.directory(sid) / "resources"
            if _is_reparse_point(destination) or (
                destination.exists()
                and any(
                    _is_reparse_point(path) or (path.is_file() and path.stat().st_nlink != 1)
                    for path in destination.rglob("*")
                )
            ):
                raise DiscoveryError("研究资源目录非法", "discovery_session_foreign", 409)
            shutil.copytree(
                Path(__file__).parents[1] / "resources",
                destination,
                ignore=shutil.ignore_patterns("__pycache__"),
                dirs_exist_ok=True,
            )
            row["discovery_creation_state"] = "creating"
            record["state"] = "session_creating"
            research.store.save()
            try:
                await research.client.rpc(
                    "session.create",
                    {
                        "sessionId": sid,
                        "cwd": str(research.store.directory(sid)),
                        "agentPreset": "research-web",
                    },
                )
            except (RuntimeFailure, asyncio.CancelledError):
                row["discovery_creation_state"] = "outcome_unknown"
                record["state"] = "session_outcome_unknown"
                research.store.save()
                log.warning("discovery_session_creation_unknown")
                raise
        row.update(discovery_creation_state="configuring")
        research.store.save()
        research.assert_session_model_profile(row)
        await research.client.rpc(
            "session.selectModel",
            {"sessionId": sid, "provider": row["model_provider"], "model": row["model"]},
        )
        await research.client.rpc("session.rename", {"sessionId": sid, "title": row["title"]})
        row.update(
            created=True, discovery_creation_state="ready", status="idle", updated_at=time.time()
        )
        record["state"] = "snapshot_ready"
        record.pop("code", None)
        research.store.save()
        research.notify()
        log.info("discovery_session_ready", session_id=sid)
        return True


def trusted_context(research, record):
    """Only owned unchanged bytes can authorize the original research contract."""
    sid = record["session_id"]
    row = research.store.session(sid)
    expected = {"handoff_id": record["handoff_id"], "selection_sha256": record["selection_sha256"]}
    if row.get("purpose") != "discovery_research" or row.get("discovery_origin") != expected:
        raise DiscoveryError("研究会话归属不一致", "discovery_session_foreign", 409)
    try:
        manifest = research.datahub.snapshots.detail(sid, record["dataset_id"])
        if (
            manifest["manifest_sha256"] != record["dataset_manifest_sha256"]
            or manifest.get("discovery", {}).get("selection_sha256") != record["selection_sha256"]
        ):
            raise ValueError("snapshot_changed")
        with directory(
            research.store.root, (".control", "snapshots", sid, record["dataset_id"]), private=True
        ) as fd:
            for item in manifest["raw_files"]:
                if (
                    hashlib.sha256(read_file(fd, item["name"], private=True)).hexdigest()
                    != item["sha256"]
                ):
                    raise ValueError("raw_changed")
        with directory(research.store.root, ("sessions", sid, "inputs")) as fd:
            raw = read_file(fd, "discovery-context.json")
        if (
            raw != context_bytes(record)
            or hashlib.sha256(raw).hexdigest() != record["context_sha256"]
        ):
            raise ValueError("context_changed")
    except (OSError, ValueError, KeyError, StoreError) as exc:
        log.warning("discovery_frozen_context_rejected", session_id=sid)
        raise DiscoveryError(
            "冻结研究资料或上下文校验失败", "discovery_context_changed", 409
        ) from exc
    return {
        "handoff_id": record["handoff_id"],
        "dataset_id": record["dataset_id"],
        "dataset_manifest_sha256": record["dataset_manifest_sha256"],
        "context_file": CONTEXT_FILE,
        "context_sha256": record["context_sha256"],
        "cutoff": record["cutoff"],
        "materials": record["materials"],
        "question": record["question"],
        "source_policy": SOURCE_POLICY,
    }
