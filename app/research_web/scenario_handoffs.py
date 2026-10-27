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
                    "sha256": selected["sha256"],
                    "native_name": selected["native_name"],
                    "resource_path": selected["resource_path"],
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


def resolve_reference(
    service, sid, reference, *, expected=None, target_sid=None, visited=(), verified=None
):
    """Follow the owned parent chain before reading a copied snapshot."""
    trusted_context(service, sid, check_capabilities=False, _visited=visited, _verified=verified)
    manifest = {}
    metadata, raw = service.dossiers._resolve(
        sid,
        reference,
        expected=expected,
        target_sid=target_sid,
        manifest_out=manifest,
        _lineage_checked=True,
    )
    row = service.store.session(sid, include_deleted=True)
    if manifest.get("origin_dataset_id") and not (
        row.get("scenario_handoff_id")
        or row.get("evidence_handoff_id")
        or row.get("purpose") == "discovery_research"
    ):
        fail("scenario_ancestor_unknown", "复制资料缺少可核验的原始归属链")
    return metadata, manifest, raw


def resolve_material(service, sid, did, **options):
    return resolve_reference(service, sid, {"type": "dataset", "id": did}, **options)


def freeze_lineage(service, sid, dataset_ids):
    return [resolve_material(service, sid, did)[0] for did in dataset_ids]


def assert_handoff_deletable(store, sid):
    """Called under the existing retention fence, before native or local purge."""
    for record in store.data["handoffs"].values():
        if record.get("session_id") == sid:
            continue
        references = record.get("lineage") or (record.get("scenario_context") or {}).get(
            "references", []
        )
        if any(reference.get("source_session_id") == sid for reference in references):
            fail(
                "session_referenced_by_handoff",
                "会话仍是已冻结交接的原始证据；请保留原件，不能永久删除",
            )


def execution_context(context, capabilities):
    """Immutable requirements, distinct from native callbacks proving actual load."""
    return {
        "kind": "research-scenario",
        "scenario_id": context["scenario"]["scenario_id"],
        "scenario_version": context["scenario"]["version"],
        "context_sha256": fingerprint(context),
        "capabilities": [
            {key: item[key] for key in ("id", "version", "sha256", "native_name", "resource_path")}
            for item in capabilities
        ],
    }


def bound_capabilities(service, context):
    result = []
    for frozen in context["scenario"]["capabilities"]:
        actual = service.capabilities.selection(frozen["id"], frozen["version"])
        if any(
            frozen.get(key) != actual[key] for key in ("sha256", "native_name", "resource_path")
        ):
            fail("scenario_capability_changed", "冻结能力的资源身份缺失或已变化")
        result.append(actual)
    return result


def verify_execution(service, sid, receipt):
    context = trusted_context(service, sid)
    if context is None:
        fail("scenario_execution_changed", "质量合同的场景归属已缺失")
    required = bound_capabilities(service, context)
    if (
        receipt.get("scenario_required_capabilities") != required
        or receipt["research_contract"].get("execution_context")
        != execution_context(context, required)
        or receipt.get("scenario_discovered_capabilities")
        != [item["native_name"] for item in required]
        or receipt["research_contract"]["as_of"] != context["scenario"]["inputs"]["as_of"]
        or not set(context["requirements"]).issubset(
            {row["text"] for row in receipt["research_contract"]["requirements"]}
        )
    ):
        fail("scenario_execution_changed", "必需能力、版本或原生发现证明已变化")
    for item in required:
        version = service.capabilities.row(item["id"])["versions"][str(item["version"])]
        expected = {
            "SKILL.md": item["sha256"],
            **{file["path"]: file["sha256"] for file in version["files"]},
        }
        for relative, digest in expected.items():
            parts = (*item["resource_path"].split("/"), *relative.split("/"))
            with directory(service.store.root, ("sessions", sid, *parts[:-1])) as fd:
                if hashlib.sha256(read_file(fd, parts[-1])).hexdigest() != digest:
                    fail("scenario_execution_changed", "场景必需能力资源字节已变化")
    loaded = {
        (item["id"], item["version"], item["sha256"])
        for item in receipt.get("native_capabilities", [])
    }
    return [
        "scenario_capability_not_loaded:" + item["id"]
        for item in required
        if (item["id"], item["version"], item["sha256"]) not in loaded
    ]


def verify_material(
    service, sid, did, values, *, expected=None, target_sid=None, visited=(), verified=None
):
    metadata, manifest, raw = resolve_material(
        service,
        sid,
        did,
        expected=expected,
        target_sid=target_sid,
        visited=visited,
        verified=verified,
    )
    if manifest.get("snapshot_kind") == "mcp_evidence":
        fail("scenario_material_route_required", "受管MCP资料须使用原档案交接")
    params = manifest.get("query", {}).get("parameters", {})
    identities = []
    if params.get("asset") or params.get("code"):
        identities.append(params.get("asset") or params.get("code"))
    if manifest.get("capability") in {"market_snapshot", "factor_macro"}:
        assets = params.get("assets", [])
        if not isinstance(assets, list):
            fail("scenario_subject_unknown", "行情资料主体字段不可核验")
        identities.extend(assets)
    if values["subject"]["kind"] == "stock" and any(
        not isinstance(identity, str) or identity.upper() != values["subject"]["identity"]
        for identity in identities
    ):
        fail("scenario_subject_mismatch", "资料包含另一证券，须明确作为比较对象选择")
    metadata["date_gaps"] = validate_dates(manifest, raw, values["as_of"])
    return metadata, manifest


def validate_dates(manifest, raw, as_of):
    rows = json.loads(raw)
    gaps = set()
    if manifest.get("capability") == "financials":
        # The current financial providers normalize actual statement periods to
        # report_period, and disclosure dates to publication_date or published_at.
        # Forecast horizons and collection/update clocks are different fields.
        for row in rows:
            period = publication_date(row.get("report_period"))
            published = [
                publication_date(row.get(field)) for field in ("publication_date", "published_at")
            ]
            if period and period > as_of:
                fail("scenario_cutoff_mismatch", "实际财务报告期晚于研究截止日")
            if any(day and day > as_of for day in published):
                fail("scenario_cutoff_mismatch", "财务资料明确公开日期晚于研究截止日")
            if period is None:
                gaps.add("financial_report_period_unknown")
            if not any(published):
                gaps.add("financial_publication_date_unknown")
    if manifest.get("capability") in {
        "search_news",
        "search_announcements",
        "search_research",
    } and any(
        publication_date(row.get("published_at")) and publication_date(row["published_at"]) > as_of
        for row in rows
        if isinstance(row, dict)
    ):
        fail("scenario_cutoff_mismatch", "选定资料的已知公开日期晚于研究截止日")
    actual_end = manifest.get("actual_range", {}).get("end_date")
    if not actual_end and manifest.get("capability") in {"market_snapshot", "market_bars"}:
        actual_end = manifest.get("as_of")
    if publication_date(actual_end) and publication_date(actual_end) > as_of:
        fail("scenario_cutoff_mismatch", "选定快照包含研究截止日之后的数据，请重新选择资料")
    return sorted(gaps)


def prepare_context(service, body):
    values = copy.deepcopy(body.scenario_inputs)
    # Validate exact input keys/types before examining any owned evidence.
    chosen = selection(service, body.scenario_id, values)
    expected_materials = [*body.dataset_ids]
    if body.workspace_material:
        expected_materials.append("file:" + str(body.workspace_material.get("file_id", "")))
    if body.context or values["material_ids"] != expected_materials:
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
        if not body.comparison_observation_ids and not set(body.dataset_ids).issubset(owned):
            fail("scenario_observation_material_mismatch", "资料不属于选定资产观察")
    scope = body.source_scope or ["datahub"]
    if len(scope) != len(set(scope)) or "datahub" not in scope:
        fail("scenario_source_scope_invalid", "请选择明确且不重复的数据范围", 422)
    owners = (
        {
            did: (body.source_session_id, "subject", values["subject"])
            for did in (
                owned
                if body.observation_id
                else service.datahub.snapshots.ids(body.source_session_id)
            )
        }
        if body.source_session_id
        else {}
    )
    comparisons = []
    if body.comparison_observation_ids:
        from .asset_research import observation as owned_observation

        if not body.observation_id or len(set(body.comparison_observation_ids)) != len(
            body.comparison_observation_ids
        ):
            fail("scenario_comparison_invalid", "比较需要当前主体观察和互不重复的对照", 422)
        seen = {values["subject"]["identity"]}
        for oid in body.comparison_observation_ids:
            peer = owned_observation(service, oid)
            if peer["asset"] in seen:
                fail("scenario_comparison_invalid", "比较对象不能重复主体或其他对照", 422)
            seen.add(peer["asset"])
            peer_datasets = {
                block["dataset"]["dataset_id"]
                for block in peer["blocks"].values()
                if block.get("dataset")
            }
            if not peer_datasets.intersection(body.dataset_ids):
                fail("scenario_comparison_material_missing", "比较对象未选择真实快照", 422)
            subject = {"kind": "stock", "identity": peer["asset"]}
            for did in peer_datasets:
                owners[did] = (peer["session_id"], "comparison", subject)
            comparisons.append(
                {
                    "observation_id": oid,
                    "subject": subject,
                    "dataset_ids": sorted(peer_datasets.intersection(body.dataset_ids)),
                }
            )
    evidence, references = set(), []
    for did in body.dataset_ids:
        if did not in owners:
            fail("scenario_material_selection_mismatch", "材料不属于明确选择的主体或比较观察", 422)
        source_sid, role, subject = owners[did]
        metadata, manifest = verify_material(
            service, source_sid, did, {**values, "subject": subject}
        )
        references.append({**metadata, "role": role, "subject": subject})
        if (
            role == "subject"
            and manifest.get("status") in {"complete", "snapshot"}
            and manifest.get("row_count", 0) > 0
        ):
            capability = manifest.get("capability")
            if capability == "financials":
                evidence.add("financials")
            if capability == "search_news":
                rows = json.loads(service.datahub.snapshots.read(source_sid, did, "rows.json"))
                if rows and all(
                    isinstance(row.get("content"), str) and row["content"].strip() for row in rows
                ):
                    evidence.add("news-source-text")
                if rows and all(publication_date(row.get("published_at")) for row in rows):
                    evidence.add("publication-time")
            # Do not infer PIT, corporate actions, accounting basis, relations or
            # disclosure completeness merely from a source or dataset name.
    workspace = None
    if body.workspace_material:
        from .asset_research import read_bundle

        if not body.workspace_material.get("sha256"):
            fail("scenario_workspace_unconfirmed", "请先核对选定研究资料的版本", 422)
        workspace, selected_refs = read_bundle(
            service, body.workspace_material, values["subject"]["identity"]
        )
        for ref in selected_refs:
            if ref["reference"]["type"] == "dataset":
                _meta, manifest, raw = resolve_reference(
                    service, ref["source_session_id"], ref["reference"], expected=ref
                )
                ref["date_gaps"] = validate_dates(manifest, raw, values["as_of"])
            if (
                publication_date(ref.get("published_at"))
                and publication_date(ref["published_at"]) > values["as_of"]
            ):
                fail("scenario_cutoff_mismatch", "引用资料晚于研究截止日")
            references.append({**ref, "role": "supporting_evidence"})
    if any(ref["permission_scope"] not in scope for ref in references):
        fail("scenario_source_scope_invalid", "所选资料需要额外来源范围，请明确勾选后重新确认", 422)
    unique_references = {}
    for ref in references:
        if ref.get("snapshot_kind") == "mcp_evidence":
            fail("scenario_material_route_required", "受管MCP资料请沿既有档案交接")
        unique_references.setdefault(
            (ref["source_session_id"], ref["reference"]["type"], ref["reference"]["id"]), ref
        )
    references = list(unique_references.values())
    chosen = selection(service, body.scenario_id, values, evidence=evidence)
    date_gaps = [
        {"code": code, "id": ref["reference"]["id"]}
        for ref in references
        for code in ref.get("date_gaps", [])
    ]
    if date_gaps:
        chosen["missing"].extend(date_gaps)
        chosen.update(status="incomplete", eligible_for_draft=False)
    if any(not row["available"] for row in chosen["capabilities"]):
        fail(
            "scenario_capability_unavailable", "场景所需能力当前不可执行；保留输入并查看能力门状态"
        )
    return {
        "scenario": chosen,
        "references": references,
        "source_session_id": body.source_session_id,
        "observation_id": body.observation_id,
        "source_scope": scope,
        "comparisons": comparisons,
        "workspace": workspace,
        "requirements": [
            *requirements(chosen),
            *(
                [
                    "比较对象仅作原值并列，不自动认定同业、归并口径或排名："
                    + "；".join(item["subject"]["identity"] for item in comparisons)
                ]
                if comparisons
                else []
            ),
        ],
    }


def trusted_context(service, sid, *, check_capabilities=True, _visited=(), _verified=None):
    """Validate every ancestor for scene and legacy copies, with cycle protection."""
    if sid in _visited or len(_visited) >= 64:
        fail("scenario_lineage_cycle", "资料来源链循环或过深，不能读取或继续交接")
    verified = {} if _verified is None else _verified
    if sid in verified:
        return copy.deepcopy(verified[sid])
    if len(verified) >= 128:
        fail("scenario_lineage_limit", "资料来源链超过核验上限")
    visited = (*_visited, sid)
    try:
        row = service.store.session(sid, include_deleted=True)
    except StoreError:
        fail("scenario_ancestor_unknown", "原始来源会话已缺失，不能用副本获得授权")
    if row.get("purpose") == "discovery_research":
        discovery = service.discovery.trusted_context(sid)
        record = service.store.data.get("discovery_handoffs", {}).get(discovery["handoff_id"], {})
        context = record.get("scenario_context")
        if context and row.get("source_scope") != context["source_scope"]:
            fail("scenario_source_revoked", "发现资料来源范围已撤销", 403)
        if context and check_capabilities:
            bound_capabilities(service, context)
        verified[sid] = context
        return copy.deepcopy(context)
    identifier = row.get("scenario_handoff_id") or row.get("evidence_handoff_id")
    if not identifier:
        if any(
            record.get("session_id") == sid for record in service.store.data["handoffs"].values()
        ):
            fail("scenario_ancestor_unknown", "旧交接缺少可证明的来源链，不能用副本重建授权")
        verified[sid] = None
        return None
    record = service.store.data["handoffs"].get(identifier)
    if not record or record.get("session_id") != sid or record.get("state") != "prepared":
        fail("scenario_handoff_unready", "冻结交接尚未完成或不属于此会话")
    context = record.get("scenario_context")
    references = context["references"] if context else record.get("lineage")
    if not isinstance(references, list):
        fail("scenario_ancestor_unknown", "交接缺少可核验的原始归属链")
    if context and row.get("source_scope") != context["source_scope"]:
        fail("scenario_scope_changed", "场景会话来源范围已变化")
    for reference in references:
        source_sid = reference.get("source_session_id")
        if not source_sid:
            fail("scenario_ancestor_unknown", "交接来源身份缺失")
        if (
            context
            and reference["reference"]["type"] == "dataset"
            and reference.get("role") != "supporting_evidence"
        ):
            values = context["scenario"]["inputs"]
            verify_material(
                service,
                source_sid,
                reference["reference"]["id"],
                {**values, "subject": reference.get("subject", values["subject"])},
                expected=reference,
                target_sid=sid,
                visited=visited,
                verified=verified,
            )
        else:
            resolve_reference(
                service,
                source_sid,
                reference["reference"],
                expected=reference,
                target_sid=sid,
                visited=visited,
                verified=verified,
            )
    for material in record["copied"]:
        from .datahub.snapshots import Snapshots
        from .dossiers import RetainedStore

        manifest = Snapshots(RetainedStore(service.store)).detail(sid, material["dataset_id"])
        if manifest["manifest_sha256"] != material["manifest_sha256"]:
            fail("scenario_evidence_changed", "冻结资料已变化")
    for item in record.get("copied_files", []):
        parts = item["path"].split("/")
        with directory(service.store.root, ("sessions", sid, *parts[:-1])) as fd:
            if hashlib.sha256(read_file(fd, parts[-1])).hexdigest() != item["sha256"]:
                fail("scenario_evidence_changed", "冻结原件副本已变化")
    relative = record["context_file"]["path"].split("/")
    try:
        with directory(service.store.root, ("sessions", sid, *relative[:-1])) as fd:
            raw = read_file(fd, relative[-1])
        payload = json.loads(raw)
        if (
            hashlib.sha256(raw).hexdigest() != record["context_file"]["sha256"]
            or context
            and payload["context"] != context
            or "lineage" in record
            and payload.get("lineage") != record["lineage"]
        ):
            raise ValueError("context_changed")
    except (OSError, ValueError, KeyError, TypeError):
        fail("scenario_context_changed", "冻结交接上下文已变化")
    if context and check_capabilities:
        bound_capabilities(service, context)
    verified[sid] = context
    return copy.deepcopy(context)
