"""Host-owned quality receipts around the single DSH research loop."""

import hashlib
import json
import re
from datetime import UTC, datetime

from core.observability import get_logger

from .research_business_evidence import business_observations
from .research_evidence import report_projection
from .research_quality import make_contract
from .resources.research_report import archive_report_version, list_report_versions
from .store import StoreError

log = get_logger(__name__)


def latest_receipt(service, sid):
    row = service.store.session(sid)
    return service.store.data["receipts"].get(f"{sid}:{row.get('delivery_key', '')}", {})


def prepare_contract(service, sid, receipt, question, requirements, as_of, mode):
    """Freeze requirements before sending; continuation preserves original obligations."""
    previous_receipt = next(
        (
            item
            for key, item in reversed(list(service.store.data["receipts"].items()))
            if key.startswith(sid + ":") and item is not receipt and item.get("research_contract")
        ),
        None,
    )
    previous = (previous_receipt or {}).get("research_contract")
    wanted = list(requirements or [question[i : i + 10000] for i in range(0, len(question), 10000)])
    if previous:
        wanted = list(dict.fromkeys([r["text"] for r in previous["requirements"]] + wanted))
        current = next(
            (
                item
                for item in service.store.files(sid)
                if item["kind"] == "outputs" and item["name"] == "research-report.json"
            ),
            None,
        )
        archived = None
        if current:
            stream, _name = service.store.open_file(sid, current["id"])
            with stream:
                current_report = json.loads(stream.read(2_000_001))
            if current_report.get("task_id") == previous["task_id"]:
                archived = archive_report_version(
                    service.store.directory(sid) / "outputs", previous["task_id"]
                )
        if archived:
            previous_receipt["quality_archive"] = archived
    contract = make_contract(
        receipt["delivery"]["task_id"],
        question,
        wanted,
        as_of or (previous or {}).get("as_of") or datetime.now(UTC).date().isoformat(),
        mode,
        previous_task_id=(previous or {}).get("task_id"),
    )
    receipt["research_contract"] = contract
    receipt["quality_checks"] = {}
    receipt["quality_repair_count"] = 0
    service.store.save()
    log.info("research_quality_contract_frozen", session_id=sid, requirement_count=len(wanted))
    return contract


def ensure_quality_scope(service, sid, key, contract):
    """A read-only worker cannot publish a verdict for a superseded task."""
    current = service.store.session(sid).get("delivery_key")
    receipt = service.store.data["receipts"].get(f"{sid}:{current}", {})
    if current != key or receipt.get("research_contract") != contract:
        log.warning("research_quality_scope_changed")
        raise StoreError(
            "研究回合已切换，请重新读取当前状态", "research_quality_scope_changed", 409
        )


def source_context(service, sid, files, sources=()):
    """Return canonical owned identities and whole-file hashes, not guessed aliases."""
    identities = []
    total = 0
    for item in files:
        if item.get("kind") != "inputs":
            continue
        if len(identities) >= 20:
            break
        row = {"id": "file:" + item["id"], "title": item["name"], "digest_scope": "full_file"}
        try:
            stream, _ = service.store.open_file(sid, item["id"])
            with stream:
                raw = stream.read(16 * 1024 * 1024 + 1)
            total += len(raw)
            if len(raw) > 16 * 1024 * 1024 or total > 64 * 1024 * 1024:
                row.update(sha256=None, unavailable="input_observation_limit")
            else:
                row["sha256"] = hashlib.sha256(raw).hexdigest()
        except (OSError, StoreError):
            row.update(sha256=None, unavailable="input_unavailable")
            log.warning("research_source_context_unavailable")
        identities.append(row)
    for source in sources:
        if len(identities) >= 20 or source.get("id", "").startswith("file:"):
            continue
        row = {
            name: source[name]
            for name in ("id", "title", "url", "as_of")
            if source.get(name) is not None
        }
        if len(json.dumps([*identities, row], ensure_ascii=False).encode()) <= 16384:
            identities.append(row)
    return {
        "sources": identities,
        "digest_scope": "full_file_for_inputs_only",
        "excerpt_bytes_limit": 12000,
    }


def observations(service, sid, files, sources, *, task_id="", contract_sha=""):
    """Only actual session input/snapshot bytes become numeric evidence."""
    result, complete = [], []
    for item in files:
        if item.get("kind") != "inputs" or not item.get("name", "").endswith(
            (".txt", ".md", ".csv", ".json")
        ):
            continue
        stream, _name = service.store.open_file(sid, item["id"])
        with stream:
            raw = stream.read(12001)
            content = raw[:12000].decode("utf-8", errors="replace")
        result.append(
            {
                "id": "file:" + item["id"],
                "source_id": "file:" + item["id"],
                "content": content,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
            }
        )
        if len(raw) <= 12000:
            try:
                raw.decode("utf-8", errors="strict")
                complete.append(result[-1])
            except UnicodeDecodeError:
                log.warning("research_business_input_encoding_unsupported")
        if len(result) >= 20:
            break
    if (
        complete
        and isinstance(contract_sha, str)
        and re.fullmatch(r"[a-f0-9]{64}", contract_sha)
        and isinstance(task_id, str)
        and re.fullmatch(r"[a-f0-9]{24}", task_id)
    ):
        result.extend(
            business_observations(
                complete,
                scope=str(service.store.root) + ":" + sid + ":" + task_id + ":" + contract_sha,
            )
        )
    for source in sources[:40]:
        if not source.get("id", "").startswith("dataset:"):
            continue
        did = source["id"].split(":", 1)[1]
        try:
            metadata = service.datahub.snapshots.detail(sid, did)
            raw = service.datahub.snapshots.read(sid, did, "rows.json")
            if len(raw) > 512000:
                continue
            content = json.dumps(
                {"metadata": metadata, "rows": json.loads(raw)}, ensure_ascii=False
            )
            result.append(
                {
                    "id": source["id"],
                    "source_id": source["id"],
                    "content": content,
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                }
            )
        except (OSError, ValueError, KeyError, StoreError):
            log.warning("research_quality_snapshot_unavailable", session_id=sid)
    return result


def quality_result(service, sid, receipt, files, sources, delivery=None):
    contract = receipt.get("research_contract")
    if not contract:
        return None
    scope = service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
    kinds = {"file": "uploads", "dataset": "datahub", "web": "web"}
    sources = [
        source for source in sources if kinds.get(source.get("id", "").split(":", 1)[0]) in scope
    ]
    evidence_files = (
        files if "uploads" in scope else [item for item in files if item.get("kind") != "inputs"]
    )
    observation_error = False
    try:
        actual_observations = observations(
            service,
            sid,
            evidence_files,
            sources,
            task_id=contract["task_id"],
            contract_sha=contract.get("sha256", ""),
        )
    except (OSError, StoreError) as exc:
        log.warning("research_quality_input_observation_unavailable", error_type=type(exc).__name__)
        actual_observations = []
        observation_error = True
    report = report_projection(
        service.store,
        sid,
        files,
        sources,
        contract["task_id"],
        delivery,
        contract=contract,
        observations=actual_observations,
    )
    assessment = (report or {}).get("assessment", {})
    if observation_error:
        assessment = {
            **assessment,
            "status": "invalid",
            "issues": list(
                dict.fromkeys([*assessment.get("issues", []), "input_observation_unavailable"])
            ),
        }
        if report is not None:
            report.update(quality="invalid", assessment=assessment, issues=assessment["issues"])

    context = source_context(service, sid, evidence_files, sources)
    business = [
        row
        for row in actual_observations
        if row.get("kind") in {"business_numeric", "business_quote"}
    ]
    fresh = {row["id"]: row.get("sha256") for row in context["sources"]}
    if any(
        fresh.get(proof["source_id"]) != proof["sha256"]
        for row in business
        for proof in row["proofs"]
    ):
        assessment = {
            **assessment,
            "status": "invalid",
            "issues": list(
                dict.fromkeys(
                    [*assessment.get("issues", []), "business_input_changed_during_verification"]
                )
            ),
        }
        business = []
        if report is not None:
            report.update(quality="invalid", assessment=assessment, issues=assessment["issues"])
        log.warning("research_business_input_changed_during_verification")
    status = assessment.get("status", "incomplete")
    issues = assessment.get("issues", ["report_missing"])
    return {
        **assessment,
        "status": status,
        "issues": issues,
        "requirements": contract["requirements"],
        "as_of": contract["as_of"],
        "repair_count": receipt.get("quality_repair_count", 0),
        "contract": contract,
        "report": report,
        "evidence_context": {
            "business_observations": business,
            **context,
            "calculation_observations": (report or {}).get("calculation_observations", []),
        },
    }


def quality_versions(service, sid):
    versions = list_report_versions(service.store.directory(sid) / "outputs")
    records = {
        item["research_contract"]["task_id"]: item
        for key, item in service.store.data["receipts"].items()
        if key.startswith(sid + ":") and item.get("research_contract")
    }
    trusted = []
    for version in versions:
        if "task_id" not in version or version.get("quality") == "invalid":
            raise StoreError("历史报告完整性检查未通过", "research_report_version_changed", 409)
        receipt = records.get(version["task_id"], {})
        anchor = receipt.get("quality_archive")
        if not anchor or version.get("version_id") != anchor.get("version_id"):
            continue
        if any(
            version.get(key) != anchor.get(key)
            for key in ("version_id", "directory", "files", "missing_artifacts", "missing_formats")
        ):
            raise StoreError("历史报告完整性检查未通过", "research_report_version_changed", 409)
        version["quality"] = receipt.get("quality_last_result", {"status": "incomplete"})
        trusted.append(version)
    for item in records.values():
        anchor = item.get("quality_archive")
        if anchor:
            path = service.store.directory(sid) / "outputs" / anchor["directory"]
            if path.is_symlink() or not path.is_dir():
                raise StoreError("历史报告版本缺失", "research_report_version_missing", 409)
    return trusted


def archive_digest(service, sid, relative):
    """Resolve a download against Host-owned hashes, never a model manifest."""
    for key, receipt in service.store.data["receipts"].items():
        if not key.startswith(sid + ":"):
            continue
        anchor = receipt.get("quality_archive") or {}
        for item in anchor.get("files", []):
            if relative == "outputs/" + anchor["directory"] + "/" + item["stored_name"]:
                return item["sha256"]
    raise StoreError("历史报告归属未确认", "research_report_version_unverified", 409)


async def check_quality(service, sid):
    """Authenticated native check, with one durable repair authorization per task."""
    async with service.lock:
        service.store.session(sid)
        receipt = latest_receipt(service, sid)
        if not receipt.get("research_contract"):
            raise StoreError("本轮没有固定研究要求", "research_quality_contract_missing", 409)
        detail = await service.detail(sid)
        result = dict(detail["research_quality"])
        result.pop("report", None)
        report = detail.get("research_report")
        identity = hashlib.sha256(
            json.dumps(
                {
                    "report": report,
                    "issues": result["issues"],
                    "evidence_context": result.get("evidence_context"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        checks = receipt.setdefault("quality_checks", {})
        if identity in checks:
            return checks[identity]
        substantive = [
            issue
            for issue in result["issues"]
            if not issue.startswith("report_artifact_delivery_unverified:")
        ]
        may_repair = (
            result["status"] == "incomplete"
            and bool(substantive)
            and receipt.get("quality_repair_count", 0) == 0
        )
        if may_repair:
            receipt["quality_repair_count"] = 1
        result.update(
            repair_count=receipt.get("quality_repair_count", 0),
            may_repair=may_repair,
            report_sha256=identity,
        )
        # A bounded ledger cannot turn repeated checks into renewed repair grants.
        if len(checks) >= 32:
            raise StoreError("本轮质量检查次数已满", "research_quality_check_limit", 409)
        checks[identity] = result
        receipt["quality_last_result"] = result
        service.store.save()
        log.info(
            "research_quality_checked",
            session_id=sid,
            status=result["status"],
            may_repair=may_repair,
        )
        return result
