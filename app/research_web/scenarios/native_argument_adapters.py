"""Closed compatibility inputs for existing Native tools, without execution.

Only authenticated Host code may supply selection. This module neither discovers
subjects nor grants source access, and never registers supplier tool aliases.
"""

from __future__ import annotations

import re
from datetime import date

from core.observability import get_logger

log = get_logger(__name__)
QUESTION_METHODS = {
    "company_one_pager": "owned-company-evidence",
    "fundamental_analysis": "owned-company-evidence",
    "research_outline": "owned-research-prep",
}


class ArgumentAdapterError(ValueError):
    """Stable adapter rejection; no original input appears in logs."""


def _fail(code):
    log.warning("research_argument_adapter_rejected", code=code)
    raise ArgumentAdapterError(code)


def _arguments(value, keys):
    if not isinstance(value, dict) or set(value) - set(keys):
        _fail("execution_parameter_unsupported")


def _text(value, *, required=False):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
        _fail("execution_parameter_invalid")
    value = value.strip()
    if (required and not value) or "://" in value or value.casefold().startswith("www."):
        _fail("execution_parameter_invalid")
    return value


def adapt_query_news(arguments):
    """Return only existing datahub_search_news inputs, never a source URL.

    CLS limits its latest snapshot before substring filtering; these arguments
    provide neither historical search nor market-wide absence evidence.
    """
    _arguments(arguments, {"query", "limit"})
    result = {}
    if "query" in arguments:
        result["query"] = _text(arguments["query"])
    if "limit" in arguments:
        limit = arguments["limit"]
        if type(limit) is not int or not 1 <= limit <= 100:
            _fail("execution_parameter_invalid")
        result["limit"] = limit
    log.info("research_news_arguments_adapted")
    return result


def adapt_research_question(tool_id, arguments, host_selection):
    """Prepare an owned-method preset from a current Host selection.

    The caller must obtain the selection through existing current-owner and
    capability selection checks. Returning a preset is not an execution receipt.
    """
    if tool_id not in QUESTION_METHODS:
        _fail("execution_parameter_unsupported")
    _arguments(arguments, {"query"})
    if "query" not in arguments:
        _fail("execution_parameter_invalid")
    question = _text(arguments["query"], required=True)
    method = QUESTION_METHODS[tool_id]
    selection = host_selection
    if not isinstance(selection, dict) or set(selection) != {
        "subject",
        "as_of",
        "material_ids",
        "capability",
    }:
        _fail("missing_selection")
    subject, capability = selection["subject"], selection["capability"]
    if (
        not isinstance(subject, dict)
        or set(subject) - {"kind", "identity", "name"}
        or subject.get("kind") != "stock"
        or not isinstance(subject.get("identity"), str)
        or not subject["identity"].strip()
        or not isinstance(selection["material_ids"], list)
        or not selection["material_ids"]
        or any(not isinstance(v, str) or not v for v in selection["material_ids"])
        or not isinstance(capability, dict)
        or capability.get("id") != method
        or type(capability.get("version")) is not int
        or capability["version"] < 1
        or not isinstance(capability.get("sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", capability["sha256"])
    ):
        _fail("missing_selection")
    try:
        date.fromisoformat(selection["as_of"])
    except (ValueError, TypeError, KeyError):
        _fail("missing_selection")
    log.info("research_question_arguments_adapted", method_id=method)
    return {"capability_id": method, "question": question}
