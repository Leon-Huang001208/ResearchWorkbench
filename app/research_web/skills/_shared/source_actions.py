"""Frozen stdlib source checks; the Host owns selection and authorization.

These functions consume a Host-bound context, reopen every listed original and
produce an analytical ledger. Calling them with a self-authored context does not
establish authority, source rights, execution, or accepted research quality.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
from datetime import date
from pathlib import Path, PurePosixPath

log = logging.getLogger(__name__)
METHODS = {
    "owned-company-evidence": (
        "company-disclosures",
        "financials",
        "business",
        "competition",
        "valuation",
    ),
    "owned-news-evidence": ("news-body", "publication-time", "counter-evidence"),
    "owned-research-prep": ("company-disclosures", "counter-evidence", "interview-material"),
}
MAX_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


def _fail(code):
    log.warning("research_method_source_rejected code=%s", code)
    raise ValueError(code)


def _closed(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or set(value) - set(required) - set(optional)
        or set(required) - set(value)
    ):
        _fail("method_source_context_invalid")


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _fail("method_source_date_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail("method_source_date_invalid")


def _read(root, relative, expected):
    if (
        not isinstance(relative, str)
        or not relative.startswith("inputs/")
        or any(not p or p.startswith(".") for p in relative.split("/"))
        or any(c in relative for c in "\\:\x00")
        or PurePosixPath(relative).is_absolute()
        or not isinstance(expected, str)
        or not re.fullmatch(r"[a-f0-9]{64}", expected)
    ):
        _fail("method_source_path_invalid")
    root = Path(root)
    path = root / relative
    if root.resolve(strict=True) != root or path.resolve(strict=True) != path:
        _fail("method_source_path_invalid")
    if any(p.is_symlink() for p in (path, *path.parents)):
        _fail("method_source_path_invalid")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_BYTES:
        _fail("method_source_file_invalid")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    if (
        identity(before) != identity(opened)
        or identity(opened) != identity(after)
        or identity(after) != identity(path.lstat())
    ):
        _fail("method_source_file_changed")
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != expected:
        _fail("method_source_hash_mismatch")
    try:
        return raw.decode("utf-8", errors="strict"), len(raw)
    except UnicodeError:
        _fail("method_source_reader_required")


def _inspect(root, context, method):
    _closed(context, {"schema", "method_id", "method_version", "subject", "as_of", "sources"})
    if (
        context["schema"] != "research_method_source_context_v1"
        or context["method_id"] != method
        or context["method_version"] != "1.0.0"
    ):
        _fail("method_source_context_invalid")
    _closed(context["subject"], {"kind", "identity"}, {"name"})
    if (
        context["subject"]["kind"] not in {"stock", "industry", "topic"}
        or not isinstance(context["subject"]["identity"], str)
        or not context["subject"]["identity"].strip()
        or len(context["subject"]["identity"]) > 160
    ):
        _fail("method_subject_invalid")
    cutoff = _day(context["as_of"])
    sources = context["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        _fail("method_source_selection_missing")
    checked, missing, seen, covered, total = [], [], set(), set(), 0
    financial_conventions = {}
    for descriptor in sources:
        _closed(
            descriptor,
            {"source_id", "path", "sha256", "locator", "publication_date", "category", "full_text"},
            {"security", "report_period", "unit", "currency", "basis", "manifest_sha256"},
        )
        sid = descriptor["source_id"]
        if not isinstance(sid, str) or not sid or len(sid) > 256 or sid in seen:
            _fail("method_source_duplicate_or_invalid")
        seen.add(sid)
        if not isinstance(descriptor["category"], str) or descriptor["category"] not in (
            *METHODS[method],
            "unclassified",
        ):
            _fail("method_source_category_invalid")
        if type(descriptor["full_text"]) is not bool:
            _fail("method_source_context_invalid")
        for name in ("security", "unit", "currency", "basis"):
            if name in descriptor and (
                not isinstance(descriptor[name], str)
                or not descriptor[name].strip()
                or len(descriptor[name]) > 160
            ):
                _fail("method_source_context_invalid")
        if "manifest_sha256" in descriptor and (
            not isinstance(descriptor["manifest_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", descriptor["manifest_sha256"])
        ):
            _fail("method_source_context_invalid")
        published = descriptor["publication_date"]
        if published is None:
            missing.append({"code": "publication_date_unknown", "source_id": sid})
        elif _day(published) > cutoff:
            _fail("method_source_after_cutoff")
        text, size = _read(root, descriptor["path"], descriptor["sha256"])
        total += size
        if total > MAX_TOTAL_BYTES:
            _fail("method_source_limit")
        locator = descriptor["locator"]
        if not isinstance(locator, str) or locator != f"bytes:0-{size}":
            _fail("method_source_locator_invalid")
        if not descriptor["full_text"] or not text.strip():
            missing.append({"code": "source_full_text_unavailable", "source_id": sid})
        else:
            covered.add(descriptor["category"])
        if method == "owned-company-evidence" and descriptor["category"] == "financials":
            if descriptor.get("security") != context["subject"]["identity"]:
                _fail("method_company_security_mismatch")
            if not descriptor.get("report_period"):
                missing.append({"code": "financial_period_unknown", "source_id": sid})
            elif _day(descriptor["report_period"]) > cutoff:
                _fail("method_source_after_cutoff")
            elif descriptor["report_period"][:4] not in text:
                missing.append({"code": "financial_period_unverified", "source_id": sid})
            for field in ("unit", "currency", "basis"):
                value = descriptor.get(field)
                # Metadata alone is not evidence of the accounting convention.
                if (
                    not isinstance(value, str)
                    or not value.strip()
                    or (
                        value.casefold() not in text.casefold()
                        and not (
                            field == "basis" and value == "annual" and "Year Ended June 30" in text
                        )
                    )
                ):
                    missing.append({"code": "financial_" + field + "_unverified", "source_id": sid})
            period = descriptor.get("report_period")
            convention = tuple(descriptor.get(field) for field in ("unit", "currency", "basis"))
            if period and all(convention):
                if period in financial_conventions and financial_conventions[period] != convention:
                    missing.append({"code": "financial_convention_conflict", "source_id": sid})
                financial_conventions[period] = convention
        checked.append({key: descriptor[key] for key in descriptor if key != "path"})
    for category in METHODS[method]:
        if category not in covered:
            missing.append({"code": "required_material_missing", "category": category})
    if method in {"owned-news-evidence", "owned-research-prep"}:
        missing.append({"code": "source_version_dedup_not_run"})
    result = {
        "schema": "research_method_source_ledger_v1",
        "method_id": method,
        "method_version": "1.0.0",
        "subject": dict(context["subject"]),
        "as_of": context["as_of"],
        "authority": "analytical_output_only",
        "research_quality": "NOT_RUN",
        "status": "incomplete" if missing else "checked",
        "sources": checked,
        "covered_categories": sorted(covered),
        "missing": missing,
        "rejected": [],
        "counts": {
            "input_sources": len(sources),
            "checked_sources": len(checked),
            "input_bytes": total,
        },
        "input_sha256": hashlib.sha256(_canonical(context)).hexdigest(),
        "numeric_derivation": "existing_business_observations_and_report_plan_required",
        "deduplication": "existing_source_version_artifact_required",
        "comparability": "unverified_until_business_observations_match_security_period_unit_currency_basis",
    }
    log.info(
        "research_method_sources_checked method=%s sources=%d missing=%d",
        method,
        len(checked),
        len(missing),
    )
    return result


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def inspect_company_sources(root, context):
    """Check original company materials without guessing financial facts."""
    return _run(root, context, "owned-company-evidence")


def inspect_news_sources(root, context):
    """Check acquired event bodies; transmission narratives remain conditional."""
    return _run(root, context, "owned-news-evidence")


def inspect_research_materials(root, context):
    """Inventory original research material; no invented interviews or answers."""
    return _run(root, context, "owned-research-prep")


def _run(root, context, method):
    try:
        return _inspect(root, context, method)
    except OSError:
        log.warning("research_method_source_unavailable method=%s", method)
        raise ValueError("method_source_unavailable") from None


def save_ledger(root, ledger, execution_id):
    """Create a new analytical artifact; it is never an execution receipt."""
    if not isinstance(execution_id, str) or not re.fullmatch(r"[a-f0-9]{32}", execution_id):
        _fail("method_execution_id_invalid")
    if ledger.get("method_id") not in METHODS:
        _fail("method_source_context_invalid")
    root = Path(root)
    if root.resolve(strict=True) != root or any(p.is_symlink() for p in (root, *root.parents)):
        _fail("method_output_path_invalid")
    folder = root
    for component in ("outputs", "method-results", execution_id):
        folder = folder / component
        if folder.is_symlink():
            _fail("method_output_path_invalid")
        folder.mkdir(exist_ok=True)
        if folder.resolve(strict=True) != folder or not folder.is_dir():
            _fail("method_output_path_invalid")
    target = folder / "ledger.json"
    raw = _canonical(ledger)
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if target.read_bytes() != raw:
            _fail("method_output_readback_failed")
    except OSError:
        log.warning("research_method_ledger_write_failed")
        raise
    log.info("research_method_ledger_saved method=%s", ledger["method_id"])
    return {
        "path": target.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
