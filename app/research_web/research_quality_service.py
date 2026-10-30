"""Host-owned quality receipts around the single DSH research loop."""

import hashlib
import json
import re
from datetime import UTC, datetime

from core.observability import get_logger

from .research_business_evidence import business_observations
from .research_evidence import report_projection
from .research_quality import make_contract
from .research_web_numeric import web_numeric_observations
from .research_web_sources import stored_sources, upload_evidence_files
from .resources.research_report import _version_read, archive_report_version, list_report_versions
from .resources.research_report_plan import EXTRACTED_METRICS
from .store import StoreError

log = get_logger(__name__)


def latest_receipt(service, sid):
    row = service.store.session(sid)
    return service.store.data["receipts"].get(f"{sid}:{row.get('delivery_key', '')}", {})


def prepare_contract(
    service, sid, receipt, question, requirements, as_of, mode, *, execution_context=None
):
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
        execution_context=execution_context,
    )
    receipt["research_contract"] = contract
    if "web" in service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"]):
        receipt["report_binding_policy"] = "bound-analysis-v1"
    receipt["quality_checks"] = {}
    receipt["quality_repair_count"] = 0
    write_business_snapshot(service, sid, contract)
    service.store.save()
    log.info("research_quality_contract_frozen", session_id=sid, requirement_count=len(wanted))
    return contract


def write_business_snapshot(service, sid, contract):
    """Publish a read-only convenience projection; scoring always rereads inputs."""
    from .datahub.security import atomic_json, directory, json_bytes

    try:
        scope = service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
        files = service.store.files(sid) if "uploads" in scope else []
        web = stored_sources(service.store, sid) if "web" in scope else []
        rows = observations(
            service, sid, files, web, task_id=contract["task_id"], contract_sha=contract["sha256"]
        )
        business = [
            row for row in rows if row.get("kind") in {"business_numeric", "business_quote"}
        ]
        sources = source_context(service, sid, files, web)["sources"]
        digests = {source["id"]: source.get("sha256") for source in sources}
        if any(
            digests.get(proof["source_id"]) != proof["sha256"]
            for row in business
            for proof in row["proofs"]
        ):
            raise StoreError("输入在证据准备时发生变化", "research_evidence_snapshot_changed", 409)
        payload = {
            "schema_version": 1,
            "task_id": contract["task_id"],
            "contract_sha256": contract["sha256"],
            "sources": sources,
            "observations": business,
        }
        if len(json_bytes(payload)) > 256000:
            raise StoreError("证据投影超过上限", "research_evidence_snapshot_limit", 409)
        with directory(service.store.directory(sid), ("resources",), create=True) as folder:
            atomic_json(folder, "research_evidence.json", payload)
        log.info("research_evidence_snapshot_prepared", observation_count=len(business))
    except (OSError, ValueError, KeyError, StoreError) as exc:
        log.warning("research_evidence_snapshot_failed", error_type=type(exc).__name__)
        raise StoreError(
            "研究证据投影暂不能安全准备", "research_evidence_snapshot_failed", 409
        ) from None


def business_prompt_index(service, sid, contract):
    """Bounded discovery data from permitted bytes, never a coverage verdict."""
    from .research_quality import _valid_contract

    try:
        if not _valid_contract(contract):
            raise ValueError("business_index_contract_changed")
        scope = service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
        files = service.store.files(sid) if "uploads" in scope else []
        rows = observations(
            service, sid, files, [], task_id=contract["task_id"], contract_sha=contract["sha256"]
        )
        rows = [r for r in rows if r.get("kind") in {"business_numeric", "business_quote"}]
        rows.sort(key=lambda r: r["kind"] != "business_numeric" and r["metric"] != "control_text")
        result = {"observations": [], "total": len(rows), "omitted": 0}
        for row in rows:
            preview = row["content"].split("\n", 1)[0]
            item = {k: row[k] for k in ("id", "metric", "period", "value", "heading", "kind")}
            item["source_ids"] = row["source_ids"]
            item["calculation_required"] = (
                row["kind"] == "business_numeric" and row["metric"] not in EXTRACTED_METRICS
            )
            item.update(preview=preview[:160], preview_truncated=len(preview) > 160)
            result["observations"].append(item)
            if len(json.dumps(result, ensure_ascii=False).encode()) > 23900:
                result["observations"].pop()
                break
        result["omitted"] = len(rows) - len(result["observations"])
        log.info("research_business_index_prepared", observation_count=len(result["observations"]))
        return result
    except (OSError, ValueError, TypeError, KeyError, StoreError) as exc:
        log.warning("research_business_index_failed", error_type=type(exc).__name__)
        raise StoreError(
            "研究证据索引暂不能安全准备", "research_business_index_failed", 409
        ) from None


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
    files = upload_evidence_files(service.store, sid, files)
    if service.store.session(sid).get("report_workflow", {}).get("quality_policy"):
        from .report_workflows.evidence import weekly_research_inputs

        research_inputs = weekly_research_inputs(service, sid)
        if research_inputs is not None:
            identities_by_id = service.store.session(sid).get("files", {})
            files = [
                item
                for item in files
                if not identities_by_id.get(item["id"], "").startswith("inputs/report-workflow/")
                or identities_by_id[item["id"]] in research_inputs
            ]
        files = sorted(
            files,
            key=lambda item: not item.get("name", "").startswith(("weekly-facts", "weekly-news-")),
        )
    scope = service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
    for item in files if "uploads" in scope else []:
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
    # Up to 20 uploads plus 20 acquired web bodies; summaries must not displace
    # a numeric observation's actual parent in the SDK snapshot or Host context.
    ordered = sorted(sources, key=lambda source: not bool(source.get("file_id")))
    dossiers = getattr(service, "dossiers", None)
    if dossiers is not None:
        identities.extend(dossiers.registered_sources(sid))
    for source in ordered:
        if (
            len(identities) >= 140
            or source.get("dossier_handle")
            or source.get("id", "").startswith("file:")
        ):
            continue
        kind = {"web": "web", "dataset": "datahub"}.get(source.get("id", "").split(":", 1)[0])
        if kind not in scope:
            continue
        row = {
            name: source[name]
            for name in ("id", "title", "url", "as_of", "sha256")
            if source.get(name) is not None
        }
        if len(json.dumps([*identities, row], ensure_ascii=False).encode()) <= 200000:
            identities.append(row)
    return {
        "sources": identities,
        "dossier_evidence_gaps": [
            {key: source[key] for key in ("id", "state", "error_code") if key in source}
            for source in identities
            if source.get("dossier_handle") and source.get("state") != "available"
        ],
        "digest_scope": "full_file_for_inputs_only",
        "excerpt_bytes_limit": 12000,
    }


def observations(service, sid, files, sources, *, task_id="", contract_sha=""):
    """Only actual session input/snapshot bytes become numeric evidence."""
    result, complete = [], []
    files = upload_evidence_files(service.store, sid, files)
    scope = service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
    for item in files if "uploads" in scope else []:
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
    for source in sources[:300]:
        if "web" in scope and source.get("id", "").startswith("web:") and source.get("file_id"):
            stream, _ = service.store.open_file(sid, source["file_id"])
            with stream:
                raw = stream.read(800001)
            if len(raw) > 800000 or hashlib.sha256(raw).hexdigest() != source.get("sha256"):
                raise StoreError("来源正文完整性检查失败", "research_source_integrity_failed", 409)
            result.append(
                {
                    "id": source["id"],
                    "source_id": source["id"],
                    "content": raw.decode("utf-8", errors="strict"),
                    "sha256": source["sha256"],
                }
            )
            if task_id and contract_sha:
                result.extend(
                    web_numeric_observations(
                        result[-1],
                        scope=str(service.store.root)
                        + ":"
                        + sid
                        + ":"
                        + task_id
                        + ":"
                        + contract_sha,
                    )
                )
            continue
    for source in sources[:40]:
        if source.get("dossier_handle"):
            continue
        if "datahub" not in scope or not source.get("id", "").startswith("dataset:"):
            continue
        did = source["id"].split(":", 1)[1]
        try:
            metadata = service.datahub.snapshots.detail(sid, did)
            if metadata.get("snapshot_kind") == "mcp_evidence":
                service.mcp_runtime.assert_frozen_result_authorized(sid, did)
                if (
                    metadata.get("provider_metadata", {})
                    .get("admission", {})
                    .get("report_admitted")
                    is not True
                ):
                    continue
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
    dossiers = getattr(service, "dossiers", None)
    if dossiers is not None:
        result.extend(dossiers.observations(sid, task_id=task_id, contract_sha=contract_sha))
    if task_id and contract_sha:
        from .report_workflows.evidence import weekly_business_observations

        result.extend(
            weekly_business_observations(service, sid, task_id=task_id, contract_sha=contract_sha)
        )
    return result


def quality_result(service, sid, receipt, files, sources, delivery=None):
    contract = receipt.get("research_contract")
    if not contract:
        return None
    scenario_issues = []
    scenario_invalid = False
    if contract.get("execution_context") is not None:
        from .scenario_handoffs import verify_execution

        try:
            scenario_issues = verify_execution(service, sid, receipt)
        except (StoreError, ValueError, OSError, KeyError, TypeError):
            scenario_invalid = True
            scenario_issues = ["scenario_execution_changed"]
            log.warning("research_scenario_execution_rejected", session_id=sid)
    scope = service.store.session(sid).get("source_scope", ["uploads", "datahub", "web"])
    kinds = {"file": "uploads", "dataset": "datahub", "web": "web"}
    upload_files = upload_evidence_files(service.store, sid, files)
    web_ids = {item["id"] for item in files} - {item["id"] for item in upload_files}
    sources = [
        source
        for source in sources
        if kinds.get(source.get("id", "").split(":", 1)[0]) in scope
        and source.get("id") not in {"file:" + identifier for identifier in web_ids}
        and source.get("admission", {}).get("report_admitted") is not False
        and (not source.get("dossier_handle") or source.get("state") == "available")
    ]
    evidence_files = (
        upload_files
        if "uploads" in scope
        else [item for item in upload_files if item.get("kind") != "inputs"]
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
    fresh = {
        row["id"]: row.get("sha256")
        for row in context["sources"]
        if not row.get("dossier_handle") or row.get("state") == "available"
    }
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
    from .specialists.service import quality_issues as specialist_quality_issues

    scenario_issues.extend(specialist_quality_issues(service, sid))
    if scenario_issues:
        status = "invalid" if scenario_invalid or status == "invalid" else "incomplete"
        issues = list(dict.fromkeys([*issues, *scenario_issues]))
        if report is not None:
            report.update(
                quality=status,
                issues=issues,
                assessment={**assessment, "status": status, "issues": issues},
            )
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
            "business_calculation_observations": (report or {}).get(
                "business_calculation_observations", []
            ),
            **context,
            "calculation_observations": (report or {}).get("calculation_observations", []),
        },
    }


def receipt_archives(receipt):
    """Each same-turn revision keeps the quality checked by the Host for its bytes."""
    result = []
    for item in receipt.get("quality_archives", {}).values():
        anchor = item["anchor"]
        checked = receipt.get("quality_checks", {}).get(item.get("check_id"), {})
        digest = next(
            (f["sha256"] for f in anchor.get("files", []) if f["name"] == "research-report.json"),
            None,
        )
        quality = (
            checked
            if digest and checked.get("report_content_sha256") == digest
            else {"status": "incomplete", "issues": ["report_version_quality_unbound"]}
        )
        result.append((anchor, quality))
    anchor = receipt.get("quality_archive")
    if anchor and not any(a["version_id"] == anchor["version_id"] for a, _ in result):
        digest = next(
            (f["sha256"] for f in anchor.get("files", []) if f["name"] == "research-report.json"),
            None,
        )
        checked = receipt.get("quality_last_result", {})
        quality = (
            checked
            if digest and checked.get("report_content_sha256") == digest
            else {"status": "incomplete", "issues": ["report_version_quality_unbound"]}
        )
        result.append((anchor, quality))
    return result


def current_report_digest(service, sid):
    fid = hashlib.sha256(b"outputs/research-report.json").hexdigest()[:24]
    if service.store.session(sid).get("files", {}).get(fid) != "outputs/research-report.json":
        return None
    try:
        stream, _ = service.store.open_file(sid, fid)
        with stream:
            raw = stream.read(2_000_001)
        return hashlib.sha256(raw).hexdigest() if len(raw) <= 2_000_000 else None
    except (OSError, StoreError):
        log.warning("research_current_report_digest_unavailable")
        return None


def report_delivery(service, sid, receipt, expected_digest=None):
    """Project immutable checked links; mutable aliases require equal actual bytes."""
    empty = {"status": "unavailable", "files": [], "aliases": {}}
    try:
        archives = receipt_archives(receipt)
        if not archives:
            return empty
        service.store.files(sid)
        digest = current_report_digest(service, sid)
        if not digest or (expected_digest is not None and digest != expected_digest):
            return empty
        matches = [
            (anchor, quality)
            for anchor, quality in archives
            if quality.get("status") in {"passed", "incomplete"}
            and quality.get("report_content_sha256") == digest
        ]
        if not matches:
            return empty
        anchor, quality = matches[-1]
        output = service.store.directory(sid) / "outputs"
        archive = output / "report-versions"
        if (
            output.is_symlink()
            or archive.is_symlink()
            or not re.fullmatch(r"[a-f0-9]{24}-[a-f0-9]{24}-[a-f0-9]{12}", anchor["version_id"])
            or anchor["directory"] != "report-versions/" + anchor["version_id"]
        ):
            raise ValueError("report_delivery_archive_identity")
        actual = _version_read(archive / anchor["version_id"])
        if any(
            actual.get(k) != anchor.get(k)
            for k in ("task_id", "directory", "files", "missing_artifacts", "missing_formats")
        ):
            raise ValueError("report_delivery_archive_changed")
        if anchor.get("task_id") != receipt["research_contract"]["task_id"]:
            raise ValueError("report_delivery_task_mismatch")
        catalog = dict(service.store.session(sid)["files"])
        public, targets = [], {}
        for item in anchor["files"]:
            relative = "outputs/" + anchor["directory"] + "/" + item["stored_name"]
            ids = [fid for fid, path in catalog.items() if path == relative]
            if len(ids) != 1:
                raise ValueError("report_delivery_file_unregistered")
            fid = ids[0]
            url = f"/api/research/sessions/{sid}/files/{fid}/download"
            public.append(
                {
                    "id": fid,
                    "name": item["name"],
                    "path": relative,
                    "sha256": item["sha256"],
                    "url": url,
                }
            )
            targets[item["sha256"]] = url
        aliases = {}
        for item in public:
            aliases[item["path"]] = item["url"]
            aliases[item["url"]] = item["url"]
            aliases[item["url"].removesuffix("download") + "preview"] = item["url"]
        inspected, total = 0, 0
        for fid, relative in catalog.items():
            if (
                not relative.startswith("outputs/")
                or not relative.lower().endswith((".html", ".docx", ".pdf", ".json"))
                or relative.startswith("outputs/report-versions/")
            ):
                continue
            inspected += 1
            if inspected > 64:
                log.info("research_report_alias_scope_limited")
                break
            try:
                stream, _ = service.store.open_file(sid, fid)
                with stream:
                    raw = stream.read(16_000_001)
            except (OSError, StoreError):
                log.info("research_report_optional_alias_unavailable")
                continue
            total += len(raw)
            if len(raw) > 16_000_000 or total > 32_000_000:
                log.info("research_report_alias_scope_limited")
                break
            url = targets.get(hashlib.sha256(raw).hexdigest())
            if url:
                aliases[relative] = url
                aliases[f"/api/research/sessions/{sid}/files/{fid}/download"] = url
                aliases[f"/api/research/sessions/{sid}/files/{fid}/preview"] = url
        if current_report_digest(service, sid) != digest:
            raise ValueError("report_delivery_report_changed")
        return {
            "status": "bound",
            "task_id": receipt["research_contract"]["task_id"],
            "version_id": anchor["version_id"],
            "report_content_sha256": digest,
            "quality_status": quality["status"],
            "files": public,
            "aliases": aliases,
        }
    except (OSError, ValueError, KeyError, TypeError, StoreError):
        log.warning("research_report_delivery_unavailable", session_id=sid)
        return empty


def quality_versions(service, sid):
    versions = list_report_versions(service.store.directory(sid) / "outputs")
    records = {
        item["research_contract"]["task_id"]: item
        for key, item in service.store.data["receipts"].items()
        if key.startswith(sid + ":") and item.get("research_contract")
    }
    trusted = []
    current_digest = current_report_digest(service, sid)
    for version in versions:
        if "task_id" not in version or version.get("quality") == "invalid":
            raise StoreError("历史报告完整性检查未通过", "research_report_version_changed", 409)
        receipt = records.get(version["task_id"], {})
        matched = next(
            (
                (anchor, quality)
                for anchor, quality in receipt_archives(receipt)
                if version.get("version_id") == anchor.get("version_id")
            ),
            None,
        )
        if matched is None:
            if version["task_id"] not in records:
                continue
            digest = next(
                f["sha256"] for f in version["files"] if f["name"] == "research-report.json"
            )
            # Retained SDK revisions are visible, but cannot inherit a passed verdict.
            checks = [
                q
                for q in receipt.get("quality_checks", {}).values()
                if q.get("report_content_sha256") == digest and q.get("status") == "invalid"
            ]
            version["quality"] = {
                "status": "invalid" if checks else "incomplete",
                "issues": [
                    "report_version_quality_unbound",
                    *[issue for q in checks for issue in q.get("issues", [])],
                ],
            }
            version["quality_binding"] = "unbound"
            version["is_current"] = digest == current_digest
            trusted.append(version)
            continue
        anchor, quality = matched
        if any(
            version.get(key) != anchor.get(key)
            for key in ("version_id", "directory", "files", "missing_artifacts", "missing_formats")
        ):
            raise StoreError("历史报告完整性检查未通过", "research_report_version_changed", 409)
        version["is_current"] = any(
            item["name"] == "research-report.json" and item["sha256"] == current_digest
            for item in version.get("files", [])
        )
        version["quality"] = quality
        version["quality_binding"] = "host_check"
        trusted.append(version)
    for item in records.values():
        for anchor, _quality in receipt_archives(item):
            path = service.store.directory(sid) / "outputs" / anchor["directory"]
            if path.is_symlink() or not path.is_dir():
                raise StoreError("历史报告版本缺失", "research_report_version_missing", 409)
    return trusted


def archive_digest(service, sid, relative):
    """Resolve a download against Host-owned hashes, never a model manifest."""
    for key, receipt in service.store.data["receipts"].items():
        if not key.startswith(sid + ":"):
            continue
        for anchor, _quality in receipt_archives(receipt):
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
        result.update(
            repair_count=1 if may_repair else receipt.get("quality_repair_count", 0),
            may_repair=may_repair,
            report_sha256=identity,
            report_content_sha256=(report or {}).get("content_sha256"),
        )
        # A bounded ledger cannot turn repeated checks into renewed repair grants.
        if len(checks) >= 32:
            raise StoreError("本轮质量检查次数已满", "research_quality_check_limit", 409)
        anchor = None
        if report and result["status"] != "invalid" and result["report_content_sha256"]:
            try:
                anchor = archive_report_version(
                    service.store.directory(sid) / "outputs",
                    receipt["research_contract"]["task_id"],
                )
                digest = next(
                    item["sha256"]
                    for item in anchor["files"]
                    if item["name"] == "research-report.json"
                )
                if digest != result["report_content_sha256"]:
                    raise ValueError("research_report_changed_during_binding")
            except (OSError, ValueError, StopIteration, TypeError):
                log.warning("research_report_version_binding_failed", session_id=sid)
                raise StoreError(
                    "报告版本绑定失败，未记录验收通过",
                    "research_report_version_binding_failed",
                    409,
                ) from None
        if may_repair:
            receipt["quality_repair_count"] = 1
        checks[identity] = result
        if anchor:
            receipt.setdefault("quality_archives", {})[anchor["version_id"]] = {
                "anchor": anchor,
                "check_id": identity,
            }
        result["report_delivery"] = report_delivery(
            service, sid, receipt, result.get("report_content_sha256")
        )
        receipt["quality_last_result"] = result
        service.store.save()
        log.info(
            "research_quality_checked",
            session_id=sid,
            status=result["status"],
            may_repair=may_repair,
        )
        return result
