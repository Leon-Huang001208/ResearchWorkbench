"""Bounded session evidence/report projections; DSH and file bytes remain authoritative."""

import hashlib
import json
import logging
import re
from datetime import date
from urllib.parse import urlsplit

from .resources.research_report import source_id, validate_payload
from .store import StoreError

log = logging.getLogger(__name__)


def evidence_index(files, datasets, activities):
    sources = {}
    for item in files:
        if item.get("kind") == "inputs":
            key = "file:" + item["id"]
            sources[key] = {
                "id": key,
                "title": item["name"],
                "state": "available",
                "file_id": item["id"],
            }
    for item in datasets:
        key = "dataset:" + str(item.get("id", ""))
        sources[key] = {
            "id": key,
            "title": item.get("name", key),
            "state": item.get("status", "unknown"),
            "as_of": item.get("as_of"),
            "dataset_id": item.get("id"),
        }
    for activity in activities:
        if (
            activity.get("title")
            not in {"web_search", "datahub_search_web", "datahub_search_research"}
            or activity.get("status") != "completed"
        ):
            continue
        detail = activity.get("detail", "")
        if not isinstance(detail, str) or len(detail) > 200000:
            continue
        try:
            result = json.loads(detail)
        except (ValueError, TypeError, RecursionError):
            log.info("research_search_shape_unavailable")
            continue
        pending, inspected = [result], 0
        while pending and inspected < 1000 and len(sources) < 300:
            row = pending.pop()
            inspected += 1
            if isinstance(row, list):
                pending.extend(row[:200])
            elif isinstance(row, dict):
                url = row.get("url")
                if isinstance(url, str) and len(url) <= 4000 and not any(ord(c) < 33 for c in url):
                    try:
                        parts = urlsplit(url)
                        safe = (
                            parts.scheme in {"http", "https"}
                            and parts.hostname
                            and not parts.username
                            and not parts.password
                        )
                    except ValueError:
                        safe = False
                    if safe:
                        key = source_id(url)
                        sources[key] = {
                            "id": key,
                            "title": str(row.get("title", url))[:1000],
                            "url": url,
                            "state": "search_summary",
                            "call_id": activity.get("id"),
                            "as_of": row.get("publishedAt"),
                            "excerpt": str(row.get("snippet", ""))[:10000],
                        }
                pending.extend(v for v in row.values() if isinstance(v, (dict, list)))
    return list(sources.values())[:300]


def report_projection(store, sid, files, sources, task_id, delivery=None):
    candidates = [
        f for f in files if f.get("kind") == "outputs" and f.get("name") == "research-report.json"
    ]
    if not candidates:
        return None
    if len(candidates) != 1:
        return {"quality": "invalid", "issues": ["report_identity_ambiguous"]}
    try:
        stream, _ = store.open_file(sid, candidates[0]["id"])
        with stream:
            raw = stream.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("report_size")
        payload = validate_payload(json.loads(raw))
        if not task_id or payload["task_id"] != task_id:
            return {"quality": "stale", "issues": ["report_task_mismatch"]}
        known = {s["id"]: s for s in sources}
        issues = list(payload.get("missing", []))
        verified = {
            row.get("name"): row.get("sha256")
            for row in (delivery or {}).get("files", [])
            if row.get("valid")
        }
        artifacts = payload.get("artifacts", [])
        if not isinstance(artifacts, list) or len(artifacts) != 3:
            issues.append("report_artifacts_missing")
        else:
            names = [
                a["name"]
                for a in artifacts
                if isinstance(a, dict) and isinstance(a.get("name"), str)
            ]
            if len(set(names)) != 3 or {name.rsplit(".", 1)[-1] for name in names} != {
                "html",
                "docx",
                "pdf",
            }:
                issues.append("report_artifact_formats_invalid")
            for artifact in artifacts:
                if (
                    not isinstance(artifact, dict)
                    or not isinstance(artifact.get("name"), str)
                    or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,149}", artifact["name"])
                ):
                    issues.append("report_artifact_invalid")
                    continue
                owned = [
                    f for f in files if f.get("kind") == "outputs" and f["name"] == artifact["name"]
                ]
                if len(owned) != 1:
                    issues.append("report_artifact_missing:" + artifact["name"])
                    continue
                stream, _ = store.open_file(sid, owned[0]["id"])
                with stream:
                    body = stream.read(16 * 1024 * 1024 + 1)
                if len(body) > 16 * 1024 * 1024 or hashlib.sha256(body).hexdigest() != artifact.get(
                    "sha256"
                ):
                    issues.append("report_artifact_changed:" + artifact["name"])
                if verified.get(artifact["name"]) != artifact.get("sha256"):
                    issues.append("report_artifact_delivery_unverified:" + artifact["name"])
        if not payload.get("sources"):
            issues.append("sources_missing")
        issues.extend(
            "section_uncited:" + s["heading"] for s in payload["sections"] if not s.get("citations")
        )
        for section in payload["sections"]:
            linked = [
                note
                for note in payload.get("notes", [])
                if section.get("id")
                and note.get("stage_id") == section["id"]
                and note.get("text", "").strip()
            ]
            note_refs = {ref for note in linked for ref in note.get("citations", [])}
            if (
                not linked
                or not section.get("citations")
                or not set(section["citations"]).issubset(note_refs)
            ):
                issues.append("section_note_lineage_missing:" + section["heading"])
        for source in payload.get("sources", []):
            record = known.get(source["id"])
            if record is None or (source.get("url") and source["url"] != record.get("url")):
                issues.append("source_unverified:" + source["id"])
            elif source.get("title") != record.get("title"):
                issues.append("source_title_unverified:" + source["id"])
        if any(re.search(r"\d", section["text"]) for section in payload["sections"]):
            issues.append("numeric_claims_need_independent_review")
        headings = {s["heading"] for s in payload["sections"]}
        required = payload.get("required_sections", [])
        if not required:
            issues.append("coverage_not_declared")
        issues.extend("section_missing:" + h for h in required if h not in headings)
        try:
            cutoff = date.fromisoformat(payload.get("as_of", ""))
        except (ValueError, TypeError, RecursionError):
            cutoff = None
            issues.append("research_cutoff_unknown")
        for source in payload.get("sources", []):
            record = known.get(source["id"], {})
            observed = record.get("as_of")
            if cutoff and isinstance(observed, str):
                try:
                    if date.fromisoformat(observed[:10]) > cutoff:
                        issues.append("source_after_cutoff:" + source["id"])
                except ValueError:
                    issues.append("source_date_unknown:" + source["id"])
        log.info("research_report_projected issues=%d", len(issues))
        return {
            **payload,
            "quality": "incomplete" if issues else "checked",
            "issues": issues,
            "coverage_scope": "declared_sections",
            "file_id": candidates[0]["id"],
        }
    except (OSError, ValueError, TypeError, KeyError, StoreError, RecursionError) as exc:
        log.warning("research_report_projection_invalid type=%s", type(exc).__name__)
        return {"quality": "invalid", "issues": ["report_invalid"]}
