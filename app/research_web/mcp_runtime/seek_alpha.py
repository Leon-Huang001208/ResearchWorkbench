"""Closed, disabled-by-default Seek Alpha evaluation candidate; no network I/O."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta

from .authorization import AuthorizationError, _arguments_hash, _canonical_bytes

ENDPOINT = "https://seek-alpha.cn/mcp/rpc"
CREDENTIAL_SLOT = "static_bearer"
SUBJECTS = ("600519.SH", "300750.SZ", "688981.SH")
QUERIES = (
    "supply_chain",
    "institutional_surveys",
    "consensus",
    "earnings_revision",
    "profit_notice_surprise",
    "risk_alerts",
)
MAX_CREDITS = 54
TOOL_NAMES = dict(
    zip(
        QUERIES,
        (
            "query_supply_chain",
            "query_institutional_surveys",
            "query_consensus",
            "query_earnings_revision",
            "query_profit_notice_surprise",
            "query_risk_alerts",
        ),
        strict=True,
    )
)


def fixed_arguments(query, subject, cutoff):
    end = date.fromisoformat(cutoff)
    start = end - timedelta(days=183)
    code = subject.split(".")[0]
    compact, beginning = end.strftime("%Y%m%d"), start.strftime("%Y%m%d")
    return {
        "supply_chain": {"code": code},
        "institutional_surveys": {
            "mode": "by_company",
            "target": subject,
            "start_date": beginning,
            "end_date": compact,
            "include_qa": False,
            "limit": 50,
        },
        "consensus": {"stocks": [code], "date": compact},
        "earnings_revision": {
            "mode": "by_stock",
            "stock": code,
            "months": 6,
            "end_date": compact,
            "report_year": end.year,
        },
        "profit_notice_surprise": {
            "mode": "stock",
            "code": code,
            "startDate": beginning,
            "endDate": compact,
            "minBase": 10000,
            "includeInterim": False,
            "limit": 20,
        },
        "risk_alerts": {
            "query": code,
            "category": "all",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "limit": 20,
        },
    }[query]


def validate_arguments(schema, arguments):
    """Only local schema references; validation must never fetch a URI."""
    from jsonschema import Draft202012Validator
    from referencing import Registry

    def reject_remote(_uri):
        raise AuthorizationError("mcp_external_schema_ref")

    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, registry=Registry(retrieve=reject_remote)).validate(arguments)
    except AuthorizationError:
        raise
    except Exception as exc:
        raise AuthorizationError("mcp_evaluation_schema_incompatible") from exc


def evaluation_preview(tools, cutoff):
    try:
        date.fromisoformat(cutoff)
    except (ValueError, TypeError) as exc:
        raise AuthorizationError("mcp_evaluation_cutoff_invalid") from exc
    entries, bindings = [], []
    for query in QUERIES:
        matches = [
            item
            for item in tools
            if item.get("tool_name") == TOOL_NAMES[query] and item.get("status") == "active"
        ]
        if len(matches) != 1:
            raise AuthorizationError("mcp_evaluation_tool_not_reviewed")
        tool = matches[0]
        bindings.append({"tool_name": tool["tool_name"], "schema_sha256": tool["schema_sha256"]})
        for subject in SUBJECTS:
            arguments = fixed_arguments(query, subject, cutoff)
            validate_arguments(tool["input_schema"], arguments)
            entries.append(
                {
                    "subject": subject,
                    "query": query,
                    "tool_name": tool["tool_name"],
                    "schema_sha256": tool["schema_sha256"],
                    "arguments": arguments,
                    "credits": 3,
                }
            )
    catalog_hash = hashlib.sha256(
        _canonical_bytes(bindings, maximum=64 * 1024, error_code="mcp_budget_invalid")
    ).hexdigest()
    return {
        "entries": entries,
        "cutoff": cutoff,
        "catalog_sha256": catalog_hash,
        "max_credits": MAX_CREDITS,
        "calls": 18,
        "current_only": ["supply_chain"],
        "enabled": False,
        "report_admitted": False,
    }


def candidate():
    """Metadata is a proposal, not a callable tool catalogue or spending grant."""
    return {
        "provider": "seek_alpha",
        "endpoint": ENDPOINT,
        "enabled": False,
        "status": "evaluation_required",
        "subjects": list(SUBJECTS),
        "queries": list(QUERIES),
        "calls": 18,
        "max_credits": MAX_CREDITS,
        "credential_slot": CREDENTIAL_SLOT,
        "report_admitted": False,
    }


def validate_evaluation(entries, catalog_sha256, max_credits):
    if (
        not isinstance(catalog_sha256, str)
        or not re.fullmatch(r"[a-f0-9]{64}", catalog_sha256)
        or type(max_credits) is not int
        or not 0 < max_credits <= MAX_CREDITS
        or not isinstance(entries, list)
        or len(entries) != 18
    ):
        raise AuthorizationError("mcp_budget_invalid")
    expected = {(subject, query) for subject in SUBJECTS for query in QUERIES}
    seen, normalized, cutoffs = set(), [], set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "subject",
            "query",
            "tool_name",
            "schema_sha256",
            "arguments",
            "credits",
        }:
            raise AuthorizationError("mcp_budget_invalid")
        cell = (entry["subject"], entry["query"])
        if (
            cell not in expected
            or cell in seen
            or type(entry["credits"]) is not int
            or entry["credits"] != 3
        ):
            raise AuthorizationError("mcp_budget_invalid")
        if (
            not isinstance(entry["tool_name"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,254}", entry["tool_name"])
            or not isinstance(entry["schema_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", entry["schema_sha256"])
        ):
            raise AuthorizationError("mcp_budget_invalid")
        if entry["tool_name"] != TOOL_NAMES[entry["query"]]:
            raise AuthorizationError("mcp_budget_tool_invalid")
        arguments = entry["arguments"]
        if not isinstance(arguments, dict):
            raise AuthorizationError("mcp_budget_private_arguments_denied")
        if entry["query"] == "supply_chain":
            if arguments != {"code": entry["subject"].split(".")[0]}:
                raise AuthorizationError("mcp_budget_private_arguments_denied")
        else:
            end_key = {"consensus": "date", "profit_notice_surprise": "endDate"}.get(
                entry["query"], "end_date"
            )
            try:
                until = arguments[end_key]
                cutoff = date.fromisoformat(
                    until if "-" in until else until[:4] + "-" + until[4:6] + "-" + until[6:]
                ).isoformat()
                cutoffs.add(cutoff)
                if arguments != fixed_arguments(entry["query"], entry["subject"], cutoff):
                    raise ValueError("fixed arguments changed")
            except (ValueError, KeyError, TypeError) as exc:
                raise AuthorizationError("mcp_budget_private_arguments_denied") from exc
        _arguments_hash(arguments)
        seen.add(cell)
        normalized.append(
            {
                **entry,
                "arguments": dict(arguments),
                "entry_id": entry["subject"] + ":" + entry["query"],
            }
        )
    if seen != expected or len(cutoffs) != 1:
        raise AuthorizationError("mcp_budget_invalid")
    # Separate JSON storage prevents the caller mutating an approved argument object.
    _canonical_bytes(normalized, maximum=256 * 1024, error_code="mcp_budget_invalid")
    return {
        "provider": "seek_alpha",
        "catalog_sha256": catalog_sha256,
        "max_credits": max_credits,
        "entries": json.loads(
            _canonical_bytes(
                sorted(normalized, key=lambda item: item["entry_id"]),
                maximum=256 * 1024,
                error_code="mcp_budget_invalid",
            )
        ),
    }


def assess_result(result):
    """Unreviewed provider semantics cannot become report-grade evidence by success."""
    issues = ["provider_content_not_admitted", "source_publication_time_unverified"]
    if not isinstance(result, dict) or result.get("isError") is True:
        issues.append("provider_result_error")
    if not isinstance(result, dict) or not isinstance(result.get("structuredContent"), dict):
        issues.append("structured_source_provenance_missing")
    return {"status": "clue", "report_admitted": False, "issues": issues}
