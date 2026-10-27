"""Frozen static references and pure selection; no provider, model or write path.

Like runtime_contract.py, use the standard logger before optional dependencies
exist. The Host's existing logs/ handlers own persistence; there is no new sink.
Qualification must come from current authenticated Host facts, never HTTP input.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import NoReturn

from .models import ScenarioError

log = logging.getLogger(__name__)
_ROOT = Path(__file__).parent
BASELINE_SHA256 = "92a0c404c7e11ed109b5ad8c4bd43b719fa7a170e054a91088592fd07f379abc"
CONTRACTS_SHA256 = "d97fccf19a542e301e3209e00f3f6ab8bbf4941cadb01d2a9cfc65b0ab94b626"
MAX_REFERENCE_BYTES = 512 * 1024
SCENARIO_IDS = (
    "company-onepager",
    "industry-onepager",
    "fundamentals",
    "technicals",
    "news-query",
    "news-transmission",
    "research-prep",
    "historical-review",
)


def _fail(code: str) -> NoReturn:
    log.warning("research_scenario_error code=%s", code)
    raise ScenarioError(code) from None


def _read(path: Path, expected_hash: str) -> dict:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_REFERENCE_BYTES + 1)
    except (OSError, ValueError, TypeError):
        _fail("scenario_catalog_unreadable")
    if len(raw) > MAX_REFERENCE_BYTES or hashlib.sha256(raw).hexdigest() != expected_hash:
        _fail("scenario_baseline_invalid")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        _fail("scenario_baseline_invalid")
    if not isinstance(result, dict) or result.get("version") != "1.0.0":
        _fail("scenario_baseline_invalid")
    return result


def read_catalog(path: Path | str | None = None) -> dict:
    """Return a fresh static-only snapshot, bound to reviewed bytes and identities.

    Optional path is an internal deployment/test hook, never a request parameter.
    Exact bytes are mandatory even for an alternate path; callers cannot rehash.
    """
    try:
        target = _ROOT / "baseline.json" if path is None else Path(path)
    except TypeError:
        _fail("scenario_catalog_unreadable")
    result = _read(target, BASELINE_SHA256)
    skills, tools = result.get("skills"), result.get("tools")
    if (
        not isinstance(skills, list)
        or not isinstance(tools, list)
        or len(skills) != 62
        or len(tools) != 78
        or len({row["id"] for row in skills + tools}) != 140
        or sum(row["group"] == "pack" for row in tools) != 9
        or result.get("authority") != "static_reference_only"
    ):
        _fail("scenario_baseline_invalid")
    return result


def read_scenarios() -> list[dict]:
    """Return eight fresh contracts; reading does not qualify or execute them."""
    rows = _read(_ROOT / "contracts.json", CONTRACTS_SHA256).get("scenarios")
    if not isinstance(rows, list) or tuple(row["id"] for row in rows) != SCENARIO_IDS:
        _fail("scenario_baseline_invalid")
    return rows


def get_scenario(scenario_id: str) -> dict:
    """Select an exact stable ID, without guessing from free text."""
    for row in read_scenarios():
        if row["id"] == scenario_id:
            return row
    _fail("scenario_unknown")


def _iso_date(value: object) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _fail("scenario_inputs_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail("scenario_inputs_invalid")


def _valid_text(value: object, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value.strip()) <= maximum
        and not any(ord(char) < 32 and char not in "\n\t" for char in value)
    )


def _validate_inputs(contract: dict, values: object) -> dict:
    allowed = set(contract["required_inputs"] + contract["optional_inputs"])
    if (
        not isinstance(values, dict)
        or set(values) - allowed
        or set(contract["required_inputs"]) - set(values)
    ):
        _fail("scenario_inputs_invalid")
    subject = values["subject"]
    if (
        not isinstance(subject, dict)
        or set(subject) - {"kind", "identity", "name"}
        or subject.get("kind") not in contract["subject_kinds"]
        or not _valid_text(subject.get("identity"), 160)
        or ("name" in subject and not _valid_text(subject["name"], 160))
    ):
        _fail("scenario_inputs_invalid")
    identity, kind = subject["identity"], subject["kind"]
    if kind == "stock" and not re.fullmatch(
        r"(?:\d{6}\.(?:SH|SZ|BJ)|\d{4,5}\.HK|[A-Z][A-Z0-9.-]{0,10}\.US)", identity
    ):
        _fail("scenario_inputs_invalid")
    if kind == "industry" and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*:[\w.-]+", identity):
        _fail("scenario_inputs_invalid")
    if kind == "topic" and any(char in identity for char in ("/", "\\", ":", "\n", "\t")):
        _fail("scenario_inputs_invalid")
    cutoff = _iso_date(values["as_of"])
    if "window_start" in values and _iso_date(values["window_start"]) > cutoff:
        _fail("scenario_inputs_invalid")
    if not _valid_text(values["question"], 6000):
        _fail("scenario_inputs_invalid")
    material_ids = values["material_ids"]
    if (
        not isinstance(material_ids, list)
        or len(material_ids) > 100
        or any(
            not isinstance(key, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key)
            or ".." in key
            for key in material_ids
        )
        or len(set(material_ids)) != len(material_ids)
    ):
        _fail("scenario_inputs_invalid")
    return copy.deepcopy(values)


def _qualification_inputs(capabilities: object, evidence: object, owner_id: object) -> None:
    if (
        not isinstance(capabilities, Mapping)
        or not isinstance(evidence, Mapping)
        or not _valid_text(owner_id, 160)
    ):
        _fail("scenario_qualification_invalid")
    catalog = read_catalog()
    known_caps = {
        key for row in catalog["skills"] + catalog["tools"] for key in row["capability_ids"]
    }
    known_data = {key for row in read_scenarios() for key in row["required_data"]}
    if set(capabilities) - known_caps or set(evidence) - known_data:
        _fail("scenario_qualification_invalid")


def _check_facts(
    keys: list[str], facts: Mapping, owner_id: str, family: str, flag: str
) -> list[dict]:
    missing = []
    for key in keys:
        fact = facts.get(key)
        if not isinstance(fact, Mapping):
            code = family + "_missing"
        elif fact.get("owner_id") != owner_id:
            code = family + "_foreign"
        elif fact.get(flag) is not True:
            code = family + "_unverified"
        else:
            continue
        missing.append({"code": code, "id": key})
    return missing


def select_scenario(
    scenario_id: str,
    inputs: dict,
    *,
    capability_qualification: Mapping,
    evidence_eligibility: Mapping,
    owner_id: str,
) -> dict:
    """Prepare a contract only; eligibility is not freeze, send or quality approval.

    Host constructs both qualification tables from current authenticated catalog
    and evidence facts. Never expose those tables or owner_id as HTTP inputs.
    """
    contract = get_scenario(scenario_id)
    values = _validate_inputs(contract, inputs)
    _qualification_inputs(capability_qualification, evidence_eligibility, owner_id)
    missing = _check_facts(
        contract["capability_ids"], capability_qualification, owner_id, "capability", "available"
    ) + _check_facts(
        contract["required_data"], evidence_eligibility, owner_id, "evidence", "eligible"
    )
    if contract["materials_required"] and not values["material_ids"]:
        missing.append({"code": "materials_missing", "id": "material_ids"})
    return {
        "scenario_id": contract["id"],
        "version": contract["version"],
        "contract": contract,
        "inputs": values,
        "missing": missing,
        "eligible_for_draft": not missing,
        "status": "ready_for_draft" if not missing else "incomplete",
        "auto_send": False,
        "frozen": False,
        "send_authorized": False,
        "runtime_verified": False,
        "quality_passed": False,
    }
