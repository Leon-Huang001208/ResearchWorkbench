"""Owned asset research projections over existing observations and evidence files.

The versioned JSON is inert user material, never a fact database or execution
authority. Every item is rebound to current owned source bytes on every read.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.observability import get_logger

from .datahub.security import directory, json_bytes, sync_directory, write_new
from .dossiers.models import Reference
from .scenario_handoffs import resolve_material, trusted_context
from .store import StoreError

log = get_logger(__name__)
router = APIRouter(prefix="/api/research/assets/research")
UUID_PATTERN = r"^[a-f0-9-]{36}$"
IDENTITY = r"^(?:\d{6}\.(?:SH|SZ|BJ)|\d{4,5}\.HK|[A-Z][A-Z0-9.-]{0,10}\.US|[A-Za-z][A-Za-z0-9_-]*:[\w.-]+)$"
MAX_BYTES = 256 * 1024


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Locator(Closed):
    kind: Literal["json-cell", "text"]
    row: int | None = Field(default=None, ge=0, le=100000)
    field: str | None = Field(default=None, min_length=1, max_length=160)
    start: int | None = Field(default=None, ge=0, le=2000000)
    end: int | None = Field(default=None, ge=1, le=2000000)
    quote: str = Field(min_length=1, max_length=6000)


class Proof(Closed):
    source_session_id: str = Field(pattern=UUID_PATTERN)
    reference: Reference
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    locator: Locator


class Summary(Closed):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=6000)
    evidence: list[Proof] = Field(min_length=1, max_length=4)


class Relation(Closed):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    from_identity: str = Field(pattern=IDENTITY)
    to_identity: str = Field(pattern=IDENTITY)
    relation: str = Field(min_length=1, max_length=160)
    evidence: list[Proof] = Field(min_length=1, max_length=4)


class Bundle(Closed):
    schema_id: Literal["asset-research-workspace/v1"] = Field(alias="schema")
    subject: str = Field(pattern=IDENTITY)
    summaries: list[Summary] = Field(max_length=12)
    relations: list[Relation] = Field(max_length=24)


class Material(Closed):
    source_session_id: str = Field(pattern=UUID_PATTERN)
    file_id: str = Field(pattern=r"^[a-f0-9]{24}$")
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class Preview(Closed):
    observation_id: str = Field(pattern=UUID_PATTERN)
    comparison_observation_ids: list[str] = Field(default_factory=list, max_length=4)
    material: Material | None = None


def reject(code, message, status=409):
    log.warning("asset_research_rejected", code=code)
    raise StoreError(message, code, status)


def observation(service, oid):
    row = service.store.data["asset_observations"].get(oid)
    if not row or row.get("asset_type") != "stock":
        reject("asset_research_observation_unknown", "证券观察不存在或不属于本账号")
    service.store.session(row["session_id"])
    trusted_context(service, row["session_id"], check_capabilities=False)
    return row


def cell_quote(value):
    return (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    )


def evidence_url(metadata):
    return (
        "/api/research/assets/research/evidence/"
        + metadata["source_session_id"]
        + "?"
        + urlencode(
            {
                "type": metadata["reference"]["type"],
                "id": metadata["reference"]["id"],
                "sha256": metadata["sha256"],
            }
        )
    )


def proof_bytes(service, proof):
    reference = proof.reference.model_dump()
    metadata, raw = service.dossiers._resolve(proof.source_session_id, reference)
    if len(raw) > 8 * 1024 * 1024 or metadata["sha256"] != proof.sha256:
        reject("asset_research_evidence_changed", "引用原件哈希已变化或超过核验范围")
    locator = proof.locator
    try:
        if locator.kind == "json-cell":
            if (
                locator.row is None
                or locator.field is None
                or locator.start is not None
                or locator.end is not None
            ):
                raise ValueError("locator")
            rows = json.loads(raw)
            if not isinstance(rows, list):
                raise ValueError("rows")
            actual = cell_quote(rows[locator.row][locator.field])
        else:
            if (
                locator.start is None
                or locator.end is None
                or locator.row is not None
                or locator.field is not None
                or locator.end <= locator.start
            ):
                raise ValueError("locator")
            actual = raw.decode("utf-8")[locator.start : locator.end]
        if actual != locator.quote:
            raise ValueError("quote")
    except (ValueError, KeyError, IndexError, TypeError, UnicodeError):
        reject("asset_research_locator_changed", "引用定位或原文与当前原件不一致")
    return {
        **metadata,
        "locator": locator.model_dump(exclude_none=True),
        "url": evidence_url(metadata),
    }, raw


def parse_bundle(service, raw, asset):
    if len(raw) > MAX_BYTES:
        reject("asset_research_bundle_limit", "研究资料合同最多256KiB", 422)
    try:
        bundle = Bundle.model_validate_json(raw)
    except (ValidationError, ValueError):
        reject("asset_research_bundle_invalid", "研究资料合同字段或版本无效", 422)
    if bundle.subject != asset:
        reject("asset_research_subject_mismatch", "研究资料不属于当前证券")
    ids = [item.id for item in [*bundle.summaries, *bundle.relations]]
    if (
        len(ids) != len(set(ids))
        or sum(len(item.evidence) for item in [*bundle.summaries, *bundle.relations]) > 64
    ):
        reject("asset_research_bundle_limit", "资料条目标识重复或引用超限", 422)
    rows, refs = {"summaries": [], "relations": []}, {}
    for group, entries in rows.items():
        for item in getattr(bundle, group):
            if group == "relations" and (
                asset not in {item.from_identity, item.to_identity}
                or item.from_identity == item.to_identity
            ):
                reject("asset_research_relation_subject", "关系必须明确关联当前证券且不能指向自身")
            evidence = []
            for proof in item.evidence:
                metadata, _raw = proof_bytes(service, proof)
                evidence.append(metadata)
                refs[
                    (
                        metadata["source_session_id"],
                        metadata["reference"]["type"],
                        metadata["reference"]["id"],
                    )
                ] = metadata
            entries.append(
                {
                    **item.model_dump(exclude={"evidence"}),
                    "evidence": evidence,
                    "quality": "not_assessed",
                    "status": "source_claim_unverified",
                }
            )
    return rows, list(refs.values())


def read_bundle(service, material, asset):
    material = material if isinstance(material, Material) else Material.model_validate(material)
    service.store.files(material.source_session_id)
    path = service.store.file_path(material.source_session_id, material.file_id)
    relative = path.relative_to(service.store.directory(material.source_session_id)).as_posix()
    metadata, raw = service.dossiers._resolve(
        material.source_session_id, {"type": "file", "id": relative}
    )
    if material.sha256 is not None and metadata["sha256"] != material.sha256:
        reject("asset_research_bundle_changed", "选定研究资料合同已变化，请重新确认")
    rows, references = parse_bundle(service, raw, asset)
    return rows, [metadata, *references]


def compare_observations(service, oid, comparisons):
    if oid in comparisons or len(comparisons) != len(set(comparisons)):
        reject("asset_research_comparison_duplicate", "比较对象不能重复或包含主体", 422)
    result, seen = [], set()
    for index, selected in enumerate([oid, *comparisons]):
        obs = observation(service, selected)
        if obs["asset"] in seen:
            reject("asset_research_comparison_duplicate", "请为每个不同证券选择一份明确观察", 422)
        seen.add(obs["asset"])
        records, datasets = [], []
        for block in ("financials", "valuation"):
            did = obs["blocks"].get(block, {}).get("dataset", {}).get("dataset_id")
            if not did:
                continue
            metadata, manifest, raw = resolve_material(service, obs["session_id"], did)
            parameters = manifest.get("query", {}).get("parameters", {})
            identities = parameters.get("assets") or [parameters.get("asset")]
            if any(identity != obs["asset"] for identity in identities):
                reject("asset_research_subject_mismatch", "比较快照与对应证券身份不一致")
            if len(raw) > 8 * 1024 * 1024:
                reject("asset_research_comparison_limit", "比较快照超过8MiB读取范围")
            values = json.loads(raw)
            units = {
                field.get("name", field.get("field")): {
                    key: field.get(key) for key in ("unit", "currency", "basis")
                }
                for field in manifest.get("fields", [])
                if isinstance(field, dict)
            }
            for row_number, value in enumerate(values[:100]):
                records.append(
                    {
                        "values": value,
                        "period": value.get("report_period")
                        or value.get("period")
                        or value.get("date"),
                        "units": units,
                        "row": row_number,
                        "dataset_id": did,
                        "source": manifest.get("source"),
                        "manifest_sha256": manifest["manifest_sha256"],
                        "as_of": manifest.get("as_of"),
                        "retrieved_at": manifest.get("retrieved_at"),
                        "truncated_rows": max(0, len(values) - 100),
                        "url": evidence_url(metadata),
                    }
                )
            datasets.append(
                {
                    "source_session_id": obs["session_id"],
                    "dataset_id": did,
                    "manifest_sha256": manifest["manifest_sha256"],
                    "sha256": metadata["sha256"],
                }
            )
        result.append(
            {
                "observation_id": selected,
                "asset": obs["asset"],
                "role": "subject" if index == 0 else "comparison",
                "records": records,
                "datasets": datasets,
            }
        )
    return result


@router.get("/catalog")
async def catalog(request: Request, observation_id: str = Query(pattern=UUID_PATTERN)):
    service = request.app.state.research
    current = observation(service, observation_id)
    observations = sorted(
        service.store.data["asset_observations"].values(),
        key=lambda row: row.get("updated_at", 0),
        reverse=True,
    )
    sessions = sorted(
        (row for row in service.store.data["sessions"].values() if not row.get("deleted_at")),
        key=lambda row: row.get("updated_at", 0),
        reverse=True,
    )
    candidates: list[dict] = []
    for session in sessions[:100]:
        if "uploads" not in session.get("source_scope", ["datahub", "web", "uploads"]):
            continue
        for item in service.store.files(session["id"]):
            relative = service.store.session(session["id"])["files"][item["id"]]
            if (
                item["name"].endswith(".json")
                and item["size"] <= MAX_BYTES
                and len(candidates) < 200
                and (
                    relative.startswith("inputs/asset-research/")
                    or item["name"].endswith(".asset-research.json")
                )
            ):
                try:
                    metadata, raw = service.dossiers._resolve(
                        session["id"], {"type": "file", "id": relative}
                    )
                    bundle = Bundle.model_validate_json(raw)
                    if bundle.subject != current["asset"]:
                        continue
                    saved_at = datetime.fromtimestamp(
                        service.store.file_path(session["id"], item["id"]).stat().st_mtime, UTC
                    ).isoformat()
                    candidates.append(
                        {
                            "source_session_id": session["id"],
                            "file_id": item["id"],
                            "name": item["name"],
                            "sha256": metadata["sha256"],
                            "title": (
                                bundle.summaries[0].title if bundle.summaries else "产业关系资料"
                            ),
                            "subject": bundle.subject,
                            "saved_at": saved_at,
                        }
                    )
                except (StoreError, ValidationError, ValueError, OSError):
                    log.warning("asset_research_candidate_unavailable")
    return {
        "asset": current["asset"],
        "observation_id": observation_id,
        "session_id": current["session_id"],
        "can_import": "uploads"
        in service.store.session(current["session_id"]).get("source_scope", []),
        "observations": [
            {
                "id": row["id"],
                "asset": row["asset"],
                "as_of": row.get("request", {}).get("end_date"),
            }
            for row in observations[:100]
            if row.get("asset_type") == "stock"
        ],
        "materials": candidates,
        "coverage": "当前账号最近100会话／100观察、最多200份JSON候选；选择后逐份核验合同和原件",
    }


@router.get("/evidence/{source_session_id}")
async def read_evidence(
    source_session_id: str,
    request: Request,
    type: Literal["dataset", "file", "source"],
    id: str = Query(min_length=1, max_length=500),
    sha256: str = Query(pattern=r"^[a-f0-9]{64}$"),
):
    metadata, raw = request.app.state.research.dossiers._resolve(
        source_session_id, {"type": type, "id": id}
    )
    if metadata["sha256"] != sha256 or len(raw) > 8 * 1024 * 1024:
        reject("asset_research_evidence_changed", "原件已变化或超过核验范围，不能替换为新版")
    return Response(
        raw,
        media_type="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="research-evidence.txt"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/preview")
async def preview(body: Preview, request: Request):
    service = request.app.state.research
    obs = observation(service, body.observation_id)
    rows, references = (
        read_bundle(service, body.material, obs["asset"])
        if body.material
        else ({"summaries": [], "relations": []}, [])
    )
    # A source file cannot declare its quality: only the exact current canonical
    # report and the Host's current revalidated receipt can supply that state.
    for item in [*rows["summaries"], *rows["relations"]]:
        for proof in item["evidence"]:
            if proof["reference"] == {"type": "file", "id": "outputs/research-report.json"}:
                detail = await service.detail(proof["source_session_id"])
                current = detail.get("research_quality") or {}
                actual = service.dossiers._resolve(
                    proof["source_session_id"], proof["reference"], expected=proof
                )[1]
                task_id = current.get("contract", {}).get("task_id")
                if task_id and json.loads(actual).get("task_id") == task_id:
                    proof.update(
                        source_quality=current.get("status", "not_assessed"),
                        source_contract=current.get("contract", {}).get("sha256"),
                        source_task_id=task_id,
                        source_report_sha256=proof["sha256"],
                    )
    return {
        **rows,
        "asset": obs["asset"],
        "observation_id": body.observation_id,
        "comparisons": compare_observations(
            service, body.observation_id, body.comparison_observation_ids
        ),
        "comparison_policy": "side_by_side_original_values_no_ranking",
        "required_source_scope": sorted(
            {"datahub", *(ref["permission_scope"] for ref in references)}
        ),
        "material": (
            {**body.material.model_dump(), "sha256": references[0]["sha256"]}
            if body.material
            else None
        ),
        "default_as_of": obs.get("request", {}).get("end_date"),
    }


@router.post("/import/{observation_id}", status_code=201)
async def import_bundle(observation_id: str, request: Request, file: UploadFile):
    service = request.app.state.research
    obs = observation(service, observation_id)
    try:
        if not (file.filename or "").lower().endswith(".json"):
            reject("asset_research_bundle_invalid", "此入口只接受版本化JSON资料合同", 422)
        raw = await file.read(MAX_BYTES + 1)
        parse_bundle(service, raw, obs["asset"])
        if "uploads" not in service.store.session(obs["session_id"]).get("source_scope", []):
            reject("asset_research_upload_excluded", "当前观察会话未批准上传资料", 403)
        original_name = re.sub(
            r"[^\w.\-\u4e00-\u9fff]",
            "_",
            (file.filename or "research.json").replace("\\", "/").split("/")[-1],
        )[:100]
        name = uuid4().hex[:12] + "-" + original_name
        with directory(
            service.store.root,
            ("sessions", obs["session_id"], "inputs", "asset-research"),
            create=True,
        ) as fd:
            write_new(fd, name, raw)
            sync_directory(fd)
        item = next(item for item in service.store.files(obs["session_id"]) if item["name"] == name)
        log.info("asset_research_bundle_imported", session_id=obs["session_id"])
        return {
            "material": {
                "source_session_id": obs["session_id"],
                "file_id": item["id"],
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        }
    finally:
        await file.close()


@router.get("/template/{observation_id}")
async def template(observation_id: str, request: Request):
    service = request.app.state.research
    obs = observation(service, observation_id)
    value = {
        "schema": "asset-research-workspace/v1",
        "subject": obs["asset"],
        "summaries": [],
        "relations": [],
    }
    did = obs["blocks"].get("financials", {}).get("dataset", {}).get("dataset_id")
    if did:
        metadata, _manifest, raw = resolve_material(service, obs["session_id"], did)
        rows = json.loads(raw)
        if rows:
            field = next(
                (
                    key
                    for key, cell in rows[0].items()
                    if isinstance(cell, str) and 0 < len(cell) <= 6000
                ),
                None,
            )
            if field:
                quote = rows[0][field]
                value["summaries"] = [
                    {
                        "id": "source-excerpt",
                        "title": "原件字段摘录：" + field,
                        "text": quote,
                        "evidence": [
                            {
                                "source_session_id": obs["session_id"],
                                "reference": {"type": "dataset", "id": did},
                                "sha256": metadata["sha256"],
                                "locator": {
                                    "kind": "json-cell",
                                    "row": 0,
                                    "field": field,
                                    "quote": quote,
                                },
                            }
                        ],
                    }
                ]
    return Response(
        json_bytes(value),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="asset-research-workspace.json"'},
    )
