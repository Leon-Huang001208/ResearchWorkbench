"""Read existing Hot research artifacts without starting Runtime, tasks or models."""
import asyncio
import hashlib
from pathlib import Path
import re
from uuid import UUID, uuid5

from core.observability import get_logger
from .store import StoreError
from .hot_service import HotWebError

log = get_logger(__name__)


def bound_session(service, run):
    row = service.store.session(run["sessionId"])
    expected = {"runId": run["runId"], "instanceId": run["instanceId"], "manifestHash": run["evidenceManifestHash"]}
    if row.get("created") is not True or row.get("purpose") != "hot_research" or row.get("hot_origin") != expected:
        raise StoreError("研究运行不属于当前会话")
    return row


def artifacts(service, sid, key=None):
    delivery = service.store.data["receipts"].get(f"{sid}:{key}", {}).get("delivery", {}) if key else {}
    recorded = {item["id"]: item for item in delivery.get("files", []) if item.get("valid") is True}
    files = []
    # Recheck current bytes; a saved successful receipt cannot certify later edits.
    for item in service.store.files(sid):
        extension = Path(item["name"]).suffix.lower().lstrip(".")
        if item["kind"] != "outputs" or extension not in {"md", "docx"}:
            continue
        if key and item["id"] not in recorded:
            continue
        if len(files) >= 100 or item["size"] > 16 * 1024 * 1024:
            log.warning("hot_result_verification_limit")
            raise StoreError("报告核验超过每文件 16 MiB 或 100 个文件上限")
        stream, _ = service.store.open_file(sid, item["id"])
        digest = hashlib.sha256()
        size = 0
        with stream:
            while chunk := stream.read(64 * 1024):
                size += len(chunk)
                if size > 16 * 1024 * 1024:
                    raise StoreError("报告超过每文件 16 MiB 上限")
                digest.update(chunk)
        if size != item["size"]:
            raise StoreError("报告大小已变化")
        item = {**item, "format": extension, "sha256": digest.hexdigest()}
        saved = recorded.get(item["id"])
        verified = bool(saved and saved.get("sha256") == item.get("sha256"))
        files.append({name: item[name] for name in ("id", "name", "format", "sha256", "url", "size")})
        files[-1].update(verified=verified, changed=bool(saved and not verified))
    required = delivery.get("required_formats", [])
    verified = bool(required) and all(any(file["verified"] and file["format"] == fmt for file in files) for fmt in required)
    state = "completed" if delivery.get("status") == "completed" and verified else "available" if files else "not_generated"
    return {"deliveryState": state, "recordedDeliveryState": delivery.get("status"), "artifacts": files}


async def research_results(service, hot, *, limit=10, offset=0):
    if type(limit) is not int or not 1 <= limit <= 10 or type(offset) is not int or not 0 <= offset <= 10000:
        raise HotWebError("hot_query_invalid", "研究列表范围不正确。", 400)
    rows = [row for row in service.store.data["sessions"].values()
            if row.get("purpose") == "hot_research" and row.get("hot_origin") and not row.get("deleted_at")]
    rows.sort(key=lambda row: (row.get("updated_at", 0), row["id"]), reverse=True)
    selected = rows[offset:offset + limit]
    semaphore = asyncio.Semaphore(3)

    async def project(row):
        sid = str(UUID(row["id"]))
        origin = row["hot_origin"]
        run_id = str(UUID(origin["runId"]))
        result = {"runId": run_id, "sessionId": sid, "title": row["title"], "targetMode": row["mode"],
                  "runState": "unavailable", "errorCode": None, "stateVerified": False,
                  "manifestHash": origin["manifestHash"], "updatedAt": row["updated_at"]}
        key = row.get("hot_delivery_key")
        async with semaphore:
            try:
                run = await hot.call("research_run", run_id)
                bound_session(service, run)
                key = run.get("deliveryKey")
                result.update(runState=run["state"], errorCode=run.get("errorCode"), stateVerified=True)
            except (HotWebError, StoreError):
                log.warning("hot_result_state_unavailable")
        try:
            result.update(artifacts(service, sid, key))
        except (StoreError, OSError):
            log.warning("hot_result_artifacts_unavailable")
            result.update(deliveryState="unavailable", recordedDeliveryState=None, artifacts=[])
        return result

    tasks = [asyncio.create_task(project(row)) for row in selected]
    try:
        items = await asyncio.wait_for(asyncio.gather(*tasks), timeout=25)
    except asyncio.TimeoutError:
        log.warning("hot_result_deadline")
        raise HotWebError("hot_result_deadline", "研究列表读取超时，请稍后刷新；未启动新研究。") from None
    return {"items": items, "limit": limit, "offset": offset, "hasMore": offset + len(selected) < len(rows)}


async def refresh_research_result(service, hot, run_id):
    """Explicit observation updates PG terminal state, never creates or sends a prompt."""
    async with service.workbench_lock:
        run = await hot.call("research_run", run_id)
        row = bound_session(service, run)
        key = run.get("deliveryKey")
        if key:
            if not re.fullmatch(r"hot:" + re.escape(run_id) + r":[a-f0-9]{64}", key) or row.get("hot_delivery_key") not in {None, key}:
                raise StoreError("研究交付身份冲突")
            row["hot_delivery_key"] = key
            service.store.save()
        files = artifacts(service, run["sessionId"], key)
        if run["state"] in {"running", "execution_outcome_unknown"}:
            from .projection import content_text, project
            await service.ensure_owned()
            entries = await service.client.history(run["sessionId"])
            marker = "[RWB_HOT_EXECUTION:" + str(key) + "]"
            matches = [i for i, entry in enumerate(entries) if entry["event"]["type"] == "user/message" and marker in content_text(entry["event"]["data"].get("content"))]
            if len(matches) != 1:
                log.warning("hot_result_observation_unknown")
                return {**run, **files, "observation": "unknown"}
            start = matches[0]
            end = next((i for i in range(start + 1, len(entries)) if entries[i]["event"]["type"] == "user/message"), len(entries))
            native = project(entries[start:end])["status"]
            if native == "completed" and files["recordedDeliveryState"] not in {"completed", "incomplete", "verification_failed"}:
                await service.delivery.refresh(run["sessionId"], entries[start:end], busy=False, connected=True, key=key)
                files = artifacts(service, run["sessionId"], key)
            terminal = "failed" if native in {"failed", "cancelled", "interrupted", "incomplete", "blocked"} else "completed" if native == "completed" and files["deliveryState"] == "completed" else "failed" if native == "completed" and files["recordedDeliveryState"] in {"completed", "incomplete", "verification_failed"} else None
            if terminal:
                request_id = str(uuid5(UUID(run_id), f"terminal:{run['revision']}:{terminal}"))
                result = await hot.call("advance_research_run", {"runId": run_id, "expectedRevision": run["revision"], "state": terminal,
                                        **({"errorCode": "hot_execution_failed"} if terminal == "failed" else {})}, request_id, request_id=request_id)
                if result.get("state") == "outcome_unknown":
                    return result
                run = result
        log.info("hot_result_observed")
        return {**run, **files}
