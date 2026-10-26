"""Deterministic quality gates over frozen Host requirements and observed bytes.

The Host owns contracts and observations. Report fields only nominate evidence;
neither model-declared coverage nor model-declared verification is authoritative.
This module does not execute tools, call a model, or persist conversation text.
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .research_arithmetic import check_arithmetic
from .resources.research_report import validate_payload

log = logging.getLogger(__name__)
_NUMBER = re.compile(r"(?<![\w])[-+]?\d+(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?")
_IDENTITY = re.compile(r"[a-zA-Z0-9_-]{1,80}")
_OBSERVATION_ID = re.compile(r"(?:[a-zA-Z0-9_-]{1,80}|(?:web|file|dataset):[a-zA-Z0-9_-]{1,80})")


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _cutoff(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("research_contract_cutoff_invalid")
    if len(value) == 10:
        return date.fromisoformat(value)
    return datetime.fromisoformat(value).date()


def make_contract(task_id, question, requirements, as_of, mode, previous_task_id=None):
    """Copy and hash Host-frozen requirements before accepting a DSH turn."""
    try:
        if not re.fullmatch(r"[a-f0-9]{24}", str(task_id)):
            raise ValueError("research_contract_task_invalid")
        if not isinstance(question, str) or not 1 <= len(question) <= 100000:
            raise ValueError("research_contract_question_invalid")
        _cutoff(as_of)
        if mode not in {"quick", "instant", "deep", "agent"}:
            raise ValueError("research_contract_mode_invalid")
        if previous_task_id is not None and not re.fullmatch(
            r"[a-f0-9]{24}", str(previous_task_id)
        ):
            raise ValueError("research_contract_previous_task_invalid")
        if not isinstance(requirements, list) or not 1 <= len(requirements) <= 100:
            raise ValueError("research_contract_requirements_invalid")
        frozen, ids = [], set()
        for index, requirement in enumerate(requirements, 1):
            row = (
                {"id": "r" + str(index), "text": requirement}
                if isinstance(requirement, str)
                else requirement
            )
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("id"), str)
                or not _IDENTITY.fullmatch(row["id"])
                or row["id"] in ids
                or not isinstance(row.get("text"), str)
                or not 1 <= len(row["text"].strip()) <= 10000
            ):
                raise ValueError("research_contract_requirement_invalid")
            ids.add(row["id"])
            frozen.append({"id": row["id"], "text": row["text"].strip()})
        contract = {
            "schema_version": 1,
            "task_id": task_id,
            "question": question,
            "requirements": frozen,
            "as_of": as_of,
            "mode": mode,
            "previous_task_id": previous_task_id,
        }
        contract["sha256"] = _digest(contract)
        log.info("research_quality_contract_frozen requirements=%d", len(frozen))
        return contract
    except (ValueError, TypeError, OverflowError) as exc:
        log.warning("research_quality_contract_rejected type=%s", type(exc).__name__)
        raise ValueError("research_contract_invalid") from exc


def _valid_contract(contract):
    if not isinstance(contract, dict):
        return False
    content = {key: value for key, value in contract.items() if key != "sha256"}
    expected = make_contract(
        content.get("task_id"),
        content.get("question"),
        content.get("requirements"),
        content.get("as_of"),
        content.get("mode"),
        content.get("previous_task_id"),
    )
    return contract == expected and contract.get("sha256") == _digest(content)


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TypeError("numeric_value_invalid")
    number = Decimal(str(value).replace(",", ""))
    if not number.is_finite() or number.adjusted() > 100:
        raise ValueError("numeric_value_invalid")
    return number


def _numbers(text):
    return [_decimal(match.group()) for match in _NUMBER.finditer(text)]


def _quantity_matches(text, value, period, unit):
    # One isolated observed quantity prevents pairing a revenue value with a
    # different expense's unit, or a different period's value in the same quote.
    context = text.replace(period, "", 1)
    quantities = list(_NUMBER.finditer(context))
    return (
        len(quantities) == 1
        and _decimal(quantities[0].group()) == value
        and re.match(
            r"\s*" + re.escape(unit) + r"(?=$|[\s,，;；。.!！？?、)\]】])",
            context[quantities[0].end() :],
        )
        is not None
    )


def _numeric_label_matches(claim):
    """Only a source-backed metric plus the declared calculation may be elided."""
    text = claim["text"].replace(claim["period"], "").replace(claim["unit"], "")
    operation = claim.get("operation", "identity")
    labels = {
        "identity": (),
        "sum": ("合计", "总计", "总额"),
        "difference": ("差额", "差值"),
        "ratio": ("比值", "比率", "倍"),
        "percent_change": ("增长", "增幅", "下降", "降幅", "变化", "变动", "同比", "环比"),
    }
    if operation == "percent_change":
        value = _decimal(claim["value"])
        if (value > 0 and any(label in text for label in ("下降", "降幅"))) or (
            value < 0 and any(label in text for label in ("增长", "增幅"))
        ):
            return False
    for label in labels[operation]:
        text = text.replace(label, "")
    metric = re.sub(r"[\W\d_]+", "", text)
    return bool(metric) and all(
        metric
        in re.sub(r"[\W\d_]+", "", row["quote"].replace(row["period"], "").replace(row["unit"], ""))
        for row in claim["operands"]
    )


def _observed_parts(content):
    materials = [content]
    if content.lstrip().startswith(("{", "[")):
        try:
            pending, inspected = [json.loads(content)], 0
            while pending and inspected < 1000:
                row = pending.pop()
                inspected += 1
                if isinstance(row, str):
                    materials.append(row)
                elif isinstance(row, list):
                    pending.extend(row[:300])
                elif isinstance(row, dict):
                    pending.extend(list(row.values())[:300])
        except (ValueError, TypeError, RecursionError):
            log.info("research_observed_text_not_json")
    return {
        part.strip(' \t\r\n。，,;；:：!?！？"“”')
        for material in materials
        for part in re.split(r"[。！？\n；;]+", material)
    }


def _narrative_matches(text, contents):
    parts = _observed_parts(text)
    observed = {part for content in contents for part in _observed_parts(content)}
    return all(not part or part in observed for part in parts)


def _observations(observations, known, invalid):
    observed = {}
    if observations is None:
        return observed
    if not isinstance(observations, list) or len(observations) > 300:
        invalid.append("observations_invalid")
        return observed
    for row in observations:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not _OBSERVATION_ID.fullmatch(row["id"])
            or row["id"] in observed
            or row.get("source_id") not in known
            or not isinstance(row.get("content"), str)
            or len(row["content"].encode()) > 2_000_000
            or hashlib.sha256(row["content"].encode()).hexdigest() != row.get("sha256")
        ):
            invalid.append("observation_identity_or_bytes_invalid")
            continue
        observed[row["id"]] = row
    return observed


def _verified_claim(claim, section, observations):
    try:
        quote = claim["text"]
        period, unit = claim["period"], claim["unit"]
        if (
            not quote
            or quote not in section["text"]
            or not period
            or not unit
            or unit not in quote
            or period not in section["text"] + section["heading"]
        ):
            return False
        expected = _decimal(claim["value"])
        # The nominated number must occur in the actual report quote.
        if _numbers(quote.replace(period, "", 1)) != [expected]:
            return False
        values, units = [], []
        for operand in claim["operands"]:
            observation = observations.get(operand["observation_id"])
            if not observation or observation["source_id"] not in section.get("citations", []):
                return False
            text = operand["quote"]
            value = _decimal(operand["value"])
            if (
                not text
                or not _narrative_matches(text, [observation["content"]])
                or not operand["period"]
                or operand["period"] not in text
                or not operand["unit"]
                or not _quantity_matches(text, value, operand["period"], operand["unit"])
            ):
                return False
            values.append(value)
            units.append(operand["unit"])
        operation = claim.get("operation", "identity")
        if not values or len(set(units)) != 1:
            return False
        if operation in {"identity", "sum", "difference"} and any(
            operand["period"] != period for operand in claim["operands"]
        ):
            return False
        if operation == "identity" and len(values) == 1:
            result = values[0]
        elif operation == "sum":
            result = sum(values)
        elif operation == "difference" and len(values) == 2:
            result = values[0] - values[1]
        elif operation == "ratio" and len(values) == 2 and values[1] != 0:
            result = values[0] / values[1]
            if unit == "%":
                result *= 100
        elif operation == "percent_change" and len(values) == 2 and values[1] != 0:
            result = (values[0] - values[1]) / values[1] * 100
        else:
            return False
        if operation in {"identity", "sum", "difference"} and unit != units[0]:
            return False
        if operation == "percent_change" and unit != "%":
            return False
        if operation == "ratio" and unit not in {"ratio", "倍", "%"}:
            return False
        if period != claim["operands"][0]["period"]:
            return False
        return result == expected and _numeric_label_matches(claim)
    except (ValueError, TypeError, KeyError, InvalidOperation, ArithmeticError):
        return False


def assess_quality(contract, report, sources, observations=None):
    """Check structural coverage and evidence; unverified facts remain gaps."""
    invalid, issues, coverage = [], [], []
    try:
        if not _valid_contract(contract):
            raise ValueError("contract_changed")
        if report is None:
            return {
                "status": "incomplete",
                "issues": ["report_missing"],
                "coverage": [
                    {**row, "status": "missing", "section_ids": []}
                    for row in contract["requirements"]
                ],
                "contract_sha256": contract["sha256"],
            }
        validate_payload(report)
        if report["task_id"] != contract["task_id"]:
            invalid.append("report_task_mismatch")
        if report.get("as_of") != contract["as_of"]:
            invalid.append("report_cutoff_mismatch")
        cutoff = _cutoff(contract["as_of"])
        if not isinstance(sources, list) or len(sources) > 300:
            raise ValueError("sources_invalid")
        known = {row["id"]: row for row in sources}
        observed = _observations(observations, known, invalid)
        observed_sources = {row["source_id"] for row in observed.values()}
        for source in report.get("sources", []):
            record = known.get(source["id"])
            if record is None:
                issues.append("source_unverified:" + source["id"])
                continue
            if source["title"] != record.get("title") or source.get("url") != record.get("url"):
                invalid.append("source_identity_mismatch:" + source["id"])
            if not record.get("content") and source["id"] not in observed_sources:
                issues.append("source_content_unverified:" + source["id"])
            if record.get("as_of"):
                try:
                    if _cutoff(record["as_of"]) > cutoff:
                        issues.append("source_after_cutoff:" + source["id"])
                except (ValueError, TypeError):
                    issues.append("source_date_unknown:" + source["id"])
        if not report.get("sources"):
            issues.append("sources_missing")
        sections = report["sections"]
        for requirement in contract["requirements"]:
            matched = []
            for row in report.get("coverage", []):
                if row["requirement_id"] == requirement["id"] and row.get("excerpt", "").strip():
                    matched.extend(
                        s.get("id", "")
                        for s in sections
                        if s.get("id") in row["section_ids"]
                        and row["excerpt"] in s["text"]
                        and s.get("citations")
                        and set(s["citations"]).issubset(
                            {
                                ref
                                for note in report.get("notes", [])
                                if note.get("stage_id") == s.get("id") and note["text"].strip()
                                for ref in note.get("citations", [])
                            }
                        )
                        and all(
                            known.get(ref, {}).get("content") or ref in observed_sources
                            for ref in s["citations"]
                        )
                    )
            matched = list(dict.fromkeys(matched))
            coverage.append(
                {
                    **requirement,
                    "status": "covered" if matched else "missing",
                    "section_ids": matched,
                }
            )
            if not matched:
                issues.append("requirement_uncovered:" + requirement["id"])
        arithmetic_checks = []
        for section in sections:
            checks = check_arithmetic(section["text"])
            arithmetic_checks.extend({**item, "section_id": section.get("id")} for item in checks)
            for state in ("mismatch", "unverified"):
                if any(item["status"] == state for item in checks):
                    issues.append("numeric_arithmetic_" + state + ":" + section.get("id", ""))
            if not section["text"].strip():
                issues.append("section_empty:" + section["heading"])
            refs = section.get("citations", [])
            notes = [
                note
                for note in report.get("notes", [])
                if section.get("id")
                and note.get("stage_id") == section["id"]
                and note["text"].strip()
            ]
            if not refs:
                issues.append("section_uncited:" + section["heading"])
            if not refs or not set(refs).issubset(
                {r for note in notes for r in note.get("citations", [])}
            ):
                issues.append("section_note_lineage_missing:" + section["heading"])
            remaining = section["text"]
            verified_periods = []
            for claim in report.get("numeric_claims", []):
                if claim["section_id"] == section.get("id"):
                    if _verified_claim(claim, section, observed):
                        remaining = remaining.replace(claim["text"], "", 1)
                        verified_periods.append(claim["period"])
                    else:
                        issues.append("numeric_claim_unverified:" + claim["id"])
            # Remove verified statements first: stripping a period earlier could
            # mutate the next valid statement and manufacture unclaimed numbers.
            for period in verified_periods:
                remaining = remaining.replace(period, "", 1)
            if _NUMBER.search(remaining):
                issues.append("numeric_claims_need_independent_review:" + section["heading"])
            contents = [
                known.get(ref, {}).get("content", "")
                for ref in refs
                if isinstance(known.get(ref, {}).get("content", ""), str)
            ]
            contents.extend(row["content"] for row in observed.values() if row["source_id"] in refs)
            if not _narrative_matches(remaining, contents):
                issues.append("narrative_unverified:" + section["heading"])
        issues.extend(report.get("missing", []))
        status = "invalid" if invalid else "incomplete" if issues else "passed"
        log.info(
            "research_quality_assessed status=%s issues=%d", status, len(invalid) + len(issues)
        )
        return {
            "status": status,
            "issues": list(dict.fromkeys(invalid + issues)),
            "arithmetic_checks": arithmetic_checks,
            "coverage": coverage,
            "coverage_scope": "host_requirements_with_report_evidence",
            "verification_scope": "observed_quotes_and_deterministic_numeric_claims",
            "contract_sha256": contract["sha256"],
        }
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        log.warning("research_quality_invalid type=%s", type(exc).__name__)
        return {"status": "invalid", "issues": ["quality_input_invalid"], "coverage": []}
