"""Closed Host-web capture projection; neither source identity nor rights are inputs.

Only scenario_pack_inputs calls this after current-owner resolve_reference readback.
A full saved capture is distinct from upstream completeness and the model preview.
"""

from __future__ import annotations

from datetime import date

from core.observability import get_logger

from .research_web_sources import MAX_TEXT, capture_proof
from .scenarios.packs.contracts import PackError, instant, validate_inputs
from .store import StoreError

log = get_logger(__name__)


def project_source_version(service, metadata, raw, cutoff, as_of):
    """Map the exact saved capture, preserving unknown semantic qualifications."""
    identifier = metadata["reference"]["id"]
    missing = []

    def gap(code):
        missing.append({"code": code, "id": identifier})

    source = (
        service.store.session(metadata["source_session_id"]).get("web_evidence", {}).get(identifier)
    )
    if not isinstance(source, dict):
        gap("source_capture_mapping_unsupported")
        return None, None, missing
    try:
        observed = instant(metadata.get("acquired_at"))
    except (PackError, ValueError, TypeError):
        gap("source_observation_instant_unknown")
        return None, None, missing
    if cutoff is None or observed > cutoff:
        gap("source_observed_after_cutoff")
        return None, None, missing
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        gap("source_capture_utf8_required")
        return None, None, missing
    if not text.strip() or len(text) > MAX_TEXT:
        gap("source_capture_body_unavailable")
        return None, None, missing
    published = metadata.get("published_at")
    if published:
        try:
            published_day = date.fromisoformat(published)
        except (TypeError, ValueError):
            gap("source_publication_date_unknown")
        else:
            if published_day > date.fromisoformat(as_of):
                log.warning("research_source_version_rejected code=source_after_cutoff")
                raise StoreError("原文公开日期晚于研究截止", "pack_source_after_cutoff", 409)
    # Only an immutable Host producer proof may certify a complete saved capture.
    complete_capture = (
        capture_proof(service.store.root, metadata["source_session_id"], source, raw) is not None
    )
    if not complete_capture:
        gap("source_capture_completeness_unknown")
    for code in (
        "source_language_unknown",
        "source_region_unknown",
        "source_role_unknown",
        "source_publication_instant_unknown",
        "upstream_completeness_unverified",
    ):
        gap(code)
    digest = metadata["sha256"]
    version_id = f"{metadata['source_session_id']}:{identifier}:{digest}"
    record = {
        "kind": "source-version",
        "row_id": version_id,
        "origin": {
            "locator": {
                "source_ref": digest,
                "resource_id": f"{metadata['source_session_id']}:{identifier}",
                "record_id": digest,
                "location": f"bytes:0-{len(raw)}",
            },
            "observed_at": metadata["acquired_at"],
            "published_at": None,
        },
        "document_id": identifier,
        "version_id": version_id,
        "content_sha256": digest,
        "url_ref": metadata["source"],
        "language": "unknown",
        "region": "unknown",
        "event_at": None,
        "source_role": "unknown",
        "parent_version_id": None,
        "full_text_available": complete_capture,
    }
    try:
        validate_inputs({"source-version": [record]}, {"as_of": cutoff.isoformat()})
    except PackError:
        gap("source_version_contract_invalid")
        return None, None, missing
    transformation = {
        "mapping": "host-web-capture-source-version-v2",
        "source_id": identifier,
        "source_session_id": metadata["source_session_id"],
        "source_sha256": digest,
        "publication_date": published,
        "publication_time": "unknown_preserved",
        "full_text_semantics": "complete_saved_capture_only",
        "upstream_completeness": "unverified",
        "historical_pit": "NOT_RUN",
    }
    log.info(
        "research_source_version_projected capture_complete=%s gaps=%d",
        complete_capture,
        len(missing),
    )
    return record, transformation, missing
