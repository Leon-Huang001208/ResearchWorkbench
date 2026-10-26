"""Host-only scenario qualification, immutable evidence and send-time revalidation.

Ordinary page handoffs and Discovery retain their own durable session lifecycle.
This module never obtains providers, credentials or model responses.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .datahub.security import directory, read_file
from .scenarios import get_scenario, read_scenarios, select_scenario
from .scenarios.models import ScenarioError
from .store import StoreError

log = get_logger(__name__)


def fail(code, message, status=409):
    log.warning("scenario_handoff_rejected", code=code)
    raise StoreError(message, code, status)


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def publication_date(value):
    """The UI's declared Asia/Shanghai natural day, never an acquisition time."""
    from .discovery.sources import stamp

    canonical = stamp(value)
    if canonical is None or len(canonical) == 10:
        return canonical
    return (
        datetime.fromisoformat(canonical).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    )


def capability_facts(service, contract):
    """Selection checks enabled version, packages, dependencies and existing gates."""
    result = []
    for cid in contract["capability_ids"]:
        try:
            selected = service.capabilities.selection(cid)
            readiness = service.capability_readiness(cid)
            result.append(
                {
                    "id": cid,
                    "version": selected["version"],
                    "default_formats": selected["default_formats"],
                    "available": True,
                    "execution_admitted": readiness["admitted"],
                    "execution_status": readiness["status"],
                    "execution_missing": readiness["missing"],
                }
            )
        except StoreError as exc:
            result.append({"id": cid, "available": False, "code": exc.code})
    return result


def catalog(service):
    return {
        "items": [
            {**row, "capabilities": capability_facts(service, row)} for row in read_scenarios()
        ]
    }


def selection(service, scenario_id, values, *, evidence=None):
    """Only this Host constructs qualification flags; inputs cannot contain them."""
    try:
        contract = get_scenario(scenario_id)
        capabilities = capability_facts(service, contract)
        owner = fingerprint(str(service.store.root))
        selected = select_scenario(
            scenario_id,
            values,
            capability_qualification={
                row["id"]: {
                    **row,
                    "available": row.get("execution_admitted") is True,
                    "owner_id": owner,
                }
                for row in capabilities
            },
            evidence_eligibility={
                key: {"owner_id": owner, "eligible": True}
                for key in (evidence or [])
                if key in contract["required_data"]
            },
            owner_id=owner,
        )
    except ScenarioError as exc:
        raise StoreError("场景输入或目录无效", exc.code, exc.status) from exc
    selected["capabilities"] = capabilities
    return selected


def requirements(selected):
    contract, values = selected["contract"], selected["inputs"]
    return [
        f"场景 {contract['name']} / {contract['id']} v{contract['version']}；标的 {values['subject']['identity']}；研究截止 {values['as_of']}。",
        *contract["steps"],
        "方法能力版本："
        + "；".join(
            f"{item['id']} v{item.get('version', '不可用')}" for item in selected["capabilities"]
        ),
        "输出覆盖：" + "；".join(contract["coverage"]),
        "产物要求：" + "；".join(contract["expected_artifacts"]),
        "冻结证据缺口："
        + (
            "；".join(f"{item['id']} ({item['code']})" for item in selected["missing"])
            or "无目录级缺口；仍须独立质量核验"
        ),
        contract["missing_data_behavior"],
        "仅使用冻结的已选原件与会话批准来源；历史截止日不证明当时可得性。",
        *(["历史窗口起点：" + values["window_start"]] if "window_start" in values else []),
    ]


def verify_material(service, sid, did, values, *, expected=None, target_sid=None):
    manifest = {}
    metadata, _raw = service.dossiers._resolve(
        sid,
        {"type": "dataset", "id": did},
        expected=expected,
        target_sid=target_sid,
        manifest_out=manifest,
    )
    if manifest.get("snapshot_kind") == "mcp_evidence":
        fail("scenario_material_route_required", "受管MCP资料须使用原档案交接")
    params = manifest.get("query", {}).get("parameters", {})
    identity = params.get("asset") or params.get("code")
    if (
        identity
        and values["subject"]["kind"] == "stock"
        and str(identity).upper() != values["subject"]["identity"]
    ):
        fail("scenario_subject_mismatch", "选定资料与证券身份不一致")
    actual_end = manifest.get("actual_range", {}).get("end_date")
    if not actual_end and manifest.get("capability") in {"market_snapshot", "market_bars"}:
        actual_end = manifest.get("as_of")
    if publication_date(actual_end) and publication_date(actual_end) > values["as_of"]:
        fail("scenario_cutoff_mismatch", "选定快照包含研究截止日之后的数据，请重新选择资料")
    return metadata, manifest


def prepare_context(service, body):
    values = copy.deepcopy(body.scenario_inputs)
    # Validate exact input keys/types before examining any owned evidence.
    chosen = selection(service, body.scenario_id, values)
    if body.context or values["material_ids"] != body.dataset_ids:
        fail("scenario_material_selection_mismatch", "场景资料选择与交接不一致", 422)
    source = (
        service.store.session(body.source_session_id)
        if body.source_session_id
        else {"source_scope": ["datahub"]}
    )
    if "datahub" not in source.get("source_scope", ["datahub", "web", "uploads"]):
        fail("scenario_source_revoked", "来源会话未批准数据资料范围", 403)
    if body.observation_id:
        observation = service.store.data["asset_observations"].get(body.observation_id)
        if not observation or observation["session_id"] != body.source_session_id:
            fail("scenario_observation_foreign", "资产观察不属于来源会话", 403)
        if values["subject"] != {
            "kind": observation["asset_type"],
            "identity": observation["asset"],
        }:
            fail("scenario_subject_mismatch", "场景标的与资产观察身份不一致")
        owned = {
            block["dataset"]["dataset_id"]
            for block in observation["blocks"].values()
            if block.get("dataset")
        }
        if not set(body.dataset_ids).issubset(owned):
            fail("scenario_observation_material_mismatch", "资料不属于选定资产观察")
    evidence, references = set(), []
    for did in body.dataset_ids:
        metadata, manifest = verify_material(service, body.source_session_id, did, values)
        references.append(metadata)
        if manifest.get("status") in {"complete", "snapshot"} and manifest.get("row_count", 0) > 0:
            capability = manifest.get("capability")
            if capability == "financials":
                evidence.add("financials")
            if capability == "news":
                evidence.add("news-source-text")
            # Do not infer PIT, corporate actions, accounting basis, relations or
            # disclosure completeness merely from a source or dataset name.
    chosen = selection(service, body.scenario_id, values, evidence=evidence)
    if any(not row["available"] for row in chosen["capabilities"]):
        fail(
            "scenario_capability_unavailable", "场景所需能力当前不可执行；保留输入并查看能力门状态"
        )
    return {
        "scenario": chosen,
        "references": references,
        "source_session_id": body.source_session_id,
        "observation_id": body.observation_id,
        "source_scope": ["datahub"],
        "requirements": requirements(chosen),
    }


def trusted_context(service, sid, *, check_capabilities=True):
    """Every send checks original authorization and frozen/copy identities again."""
    row = service.store.session(sid)
    if row.get("purpose") == "discovery_research":
        discovery = service.discovery.trusted_context(sid)
        record = service.store.data.get("discovery_handoffs", {}).get(discovery["handoff_id"], {})
        context = record.get("scenario_context")
        if context and row.get("source_scope") != context["source_scope"]:
            fail("scenario_source_revoked", "发现资料来源范围已撤销", 403)
        if context and check_capabilities:
            for capability in context["scenario"]["capabilities"]:
                service.capabilities.selection(capability["id"], capability["version"])
        return copy.deepcopy(context)
    identifier = row.get("scenario_handoff_id")
    if not identifier:
        return None
    record = service.store.data["handoffs"].get(identifier)
    if not record or record.get("session_id") != sid or record.get("state") != "prepared":
        fail("scenario_handoff_unready", "场景冻结尚未完成或不属于此会话")
    context = record["scenario_context"]
    values = context["scenario"]["inputs"]
    if row.get("source_scope") != context["source_scope"]:
        fail("scenario_scope_changed", "场景会话来源范围已变化")
    for reference in context["references"]:
        verify_material(
            service,
            context["source_session_id"],
            reference["reference"]["id"],
            values,
            expected=reference,
            target_sid=sid,
        )
    for material in record["copied"]:
        manifest = service.datahub.snapshots.detail(sid, material["dataset_id"])
        if manifest["manifest_sha256"] != material["manifest_sha256"]:
            fail("scenario_evidence_changed", "冻结资料已变化")
    relative = record["context_file"]["path"].split("/")
    try:
        with directory(service.store.root, ("sessions", sid, *relative[:-1])) as fd:
            raw = read_file(fd, relative[-1])
        if (
            hashlib.sha256(raw).hexdigest() != record["context_file"]["sha256"]
            or json.loads(raw)["context"] != context
        ):
            raise ValueError("context_changed")
    except (OSError, ValueError, KeyError, TypeError):
        fail("scenario_context_changed", "冻结场景上下文已变化")
    if check_capabilities:
        for capability in context["scenario"]["capabilities"]:
            service.capabilities.selection(capability["id"], capability["version"])
    return copy.deepcopy(context)
