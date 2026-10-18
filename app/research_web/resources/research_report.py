"""Offline research artifacts sharing one payload and an embedded Chinese font."""

import hashlib
import html
import json
import logging
import os
import re
import shutil
import stat
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

log = logging.getLogger("research_web.report")


def source_id(url):
    return "web:" + hashlib.sha256(url.encode()).hexdigest()[:24]


def calculation_evidence(observations, requirement_ids, *, methods_requirement_ids=()):
    """Serialize one calculation's evidence; only the independent Host can verify it.

    Pass the actual four calculation_observations from research_check_quality.
    This creates sections/claims/notes/coverage, never missing or quality status.
    Requirement mappings express the author's intent, not verified coverage.
    """
    metrics = ("total_return", "max_drawdown", "terminal_scenario_return", "row_count")

    def ids(value):
        return (
            isinstance(value, (list, tuple))
            and len(value) <= 40
            and all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", v) for v in value)
            and len(set(value)) == len(value)
        )

    try:
        if (
            not isinstance(observations, list)
            or len(observations) != 4
            or not isinstance(requirement_ids, dict)
            or not set(requirement_ids).issubset(metrics)
            or not all(ids(value) for value in requirement_ids.values())
            or not ids(methods_requirement_ids)
        ):
            raise ValueError("research_calculation_evidence_invalid")
        rows, scope, methods = {}, None, None
        for row in observations:
            if not isinstance(row, dict):
                raise TypeError("research_calculation_evidence_invalid")
            for key in (
                "id",
                "source_id",
                "calculation_id",
                "metric",
                "value",
                "period",
                "unit",
                "content",
                "input_sha256",
                "recipe_sha256",
            ):
                if not isinstance(row.get(key), str) or not 1 <= len(row[key]) <= (
                    8192 if key == "content" else 256
                ):
                    raise ValueError("research_calculation_evidence_invalid")
            current_scope = tuple(
                row[k] for k in ("source_id", "calculation_id", "input_sha256", "recipe_sha256")
            )
            lines = row["content"].split("\n", 1)
            if (
                row["metric"] not in metrics
                or row["metric"] in rows
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", row["calculation_id"])
                or len(lines) != 2
                or not all(line.strip() for line in lines)
                or (scope is not None and scope != current_scope)
                or (methods is not None and methods != lines[1])
            ):
                raise ValueError("research_calculation_evidence_invalid")
            rows[row["metric"]] = row
            scope, methods = current_scope, lines[1]
        result = {"sections": [], "notes": [], "numeric_claims": [], "coverage": []}

        def section(identifier, heading, text, refs, requirements):
            result["sections"].append(
                {"id": identifier, "heading": heading, "text": text, "citations": list(refs)}
            )
            result["notes"].append({"stage_id": identifier, "text": text, "citations": list(refs)})
            result["coverage"].extend(
                {"requirement_id": rid, "section_ids": [identifier], "excerpt": text}
                for rid in requirements
            )

        prefix = "calc_" + rows[metrics[0]]["calculation_id"]
        for metric in metrics:
            row = rows[metric]
            text = row["content"].split("\n", 1)[0]
            identifier = prefix + "_" + metric
            section(identifier, metric, text, [row["source_id"]], requirement_ids.get(metric, []))
            result["numeric_claims"].append(
                {
                    "id": "claim_" + rows[metric]["calculation_id"] + "_" + metric,
                    "section_id": identifier,
                    "text": text,
                    "value": row["value"],
                    "period": row["period"],
                    "unit": row["unit"],
                    "operation": "identity",
                    "operands": [
                        {
                            "observation_id": row["id"],
                            "value": row["value"],
                            "period": row["period"],
                            "unit": row["unit"],
                            "quote": text,
                        }
                    ],
                }
            )
        section(
            prefix + "_methods",
            "计算方法与验证范围",
            methods,
            [rows[metrics[0]]["source_id"]],
            methods_requirement_ids,
        )
        log.info("research_calculation_evidence_assembled metrics=%d", len(metrics))
        return result
    except (ValueError, TypeError, KeyError) as exc:
        log.warning("research_calculation_evidence_failed type=%s", type(exc).__name__)
        raise ValueError("research_calculation_evidence_invalid") from exc


def _evidence_decimal(value):
    from decimal import Decimal

    if isinstance(value, bool) or not isinstance(value, (str, int, float)) or len(str(value)) > 128:
        raise ValueError("research_evidence_number_invalid")
    number = Decimal(str(value).replace(",", ""))
    if not number.is_finite() or abs(number.adjusted()) > 100:
        raise ValueError("research_evidence_number_invalid")
    return number


def canonical_source(sources, identity):
    """Resolve an exact Host ID/title; uploaded filenames are never source IDs."""
    try:
        if (
            not isinstance(sources, list)
            or not 1 <= len(sources) <= 200
            or not isinstance(identity, str)
        ):
            raise ValueError("research_evidence_sources_invalid")
        if any(
            not isinstance(s, dict)
            or not isinstance(s.get("id"), str)
            or not re.fullmatch(r"(?:file|web|dataset):[A-Za-z0-9_-]{1,80}", s["id"])
            or not isinstance(s.get("title"), str)
            for s in sources
        ):
            raise ValueError("research_evidence_sources_invalid")
        if len({s["id"] for s in sources}) != len(sources):
            raise ValueError("research_evidence_source_ambiguous")
        matches = [
            s
            for s in sources
            if (
                s["id"] == identity
                if identity.startswith(("file:", "web:", "dataset:"))
                else s["title"] == identity
            )
        ]
        if len(matches) != 1:
            raise ValueError("research_evidence_source_missing_or_ambiguous")
        result = {k: matches[0][k] for k in ("id", "title", "url", "as_of") if k in matches[0]}
        log.info("research_evidence_source_resolved")
        return result
    except (ValueError, TypeError, KeyError):
        log.warning("research_evidence_source_rejected")
        raise


def evidence_section(identifier, heading, text, citations, requirement_ids):
    """Copy author-nominated text/lineage, never certify it or create observations."""
    try:
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier)
            or not isinstance(heading, str)
            or not 1 <= len(heading) <= 200
            or not isinstance(text, str)
            or not 1 <= len(text) <= 10000
        ):
            raise ValueError("research_evidence_section_invalid")
        for values, pattern in (
            (citations, r"(?:file|web|dataset):[A-Za-z0-9_-]{1,80}"),
            (requirement_ids, r"[A-Za-z0-9_-]{1,80}"),
        ):
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 100
                or any(not isinstance(v, str) or not re.fullmatch(pattern, v) for v in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError("research_evidence_lineage_invalid")
        return {
            "sections": [
                {"id": identifier, "heading": heading, "text": text, "citations": list(citations)}
            ],
            "notes": [{"stage_id": identifier, "text": text, "citations": list(citations)}],
            "coverage": [
                {"requirement_id": rid, "section_ids": [identifier], "excerpt": text}
                for rid in requirement_ids
            ],
        }
    except (ValueError, TypeError):
        log.warning("research_evidence_section_rejected")
        raise


def build_numeric_claim(identifier, section_id, text, period, unit, operation, operands):
    """Preflight exact arithmetic and serialization; Host still verifies source bytes."""
    from decimal import Context, InvalidOperation, localcontext

    try:
        if not all(
            isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", v)
            for v in (identifier, section_id)
        ) or not all(isinstance(v, str) and 1 <= len(v) <= 10000 for v in (text, period, unit)):
            raise ValueError("research_evidence_claim_invalid")
        arities = {
            "identity": (1,),
            "difference": (2,),
            "ratio": (2,),
            "percent_change": (2,),
            "sum": tuple(range(1, 51)),
        }
        if (
            operation not in arities
            or not isinstance(operands, list)
            or len(operands) not in arities[operation]
        ):
            raise ValueError("research_evidence_claim_arity")
        number_pattern = re.compile(r"(?<![\w])[-+]?\d+(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?")
        values = []
        for operand in operands:
            if (
                not isinstance(operand, dict)
                or set(operand) != {"observation_id", "value", "quote", "period", "unit"}
                or not isinstance(operand["observation_id"], str)
                or not re.fullmatch(
                    r"(?:[A-Za-z0-9_-]{1,80}|(?:file|web|dataset):[A-Za-z0-9_-]{1,80})",
                    operand["observation_id"],
                )
            ):
                raise ValueError("research_evidence_operand_invalid")
            if (
                not all(
                    isinstance(operand[k], str) and 1 <= len(operand[k]) <= 10000
                    for k in ("quote", "period", "unit")
                )
                or operand["period"] not in operand["quote"]
            ):
                raise ValueError("research_evidence_operand_context")
            quantity = list(
                number_pattern.finditer(operand["quote"].replace(operand["period"], "", 1))
            )
            value = _evidence_decimal(operand["value"])
            context = operand["quote"].replace(operand["period"], "", 1)
            if (
                len(quantity) != 1
                or _evidence_decimal(quantity[0].group()) != value
                or not re.match(
                    r"\s*" + re.escape(operand["unit"]) + r"(?=$|[\s,，;；。.!！？?、)\]】])",
                    context[quantity[0].end() :],
                )
            ):
                raise ValueError("research_evidence_operand_quantity")
            values.append(value)
        units = {o["unit"] for o in operands}
        if len(units) != 1 or period != operands[0]["period"]:
            raise ValueError("research_evidence_operand_units_or_period")
        if operation in {"identity", "difference", "sum"} and (
            unit not in units or any(o["period"] != period for o in operands)
        ):
            raise ValueError("research_evidence_operand_units_or_period")
        if (
            operation == "ratio"
            and unit not in {"ratio", "倍", "%"}
            or operation == "percent_change"
            and unit != "%"
        ):
            raise ValueError("research_evidence_claim_unit")
        with localcontext(Context(prec=28)):
            if operation == "identity":
                value = values[0]
            elif operation == "sum":
                value = sum(values)
            elif operation == "difference":
                value = values[0] - values[1]
            elif operation == "ratio":
                value = values[0] / values[1] * (100 if unit == "%" else 1)
            else:
                value = (values[0] - values[1]) / values[1] * 100
        if unit not in text or [
            _evidence_decimal(m.group())
            for m in number_pattern.finditer(text.replace(period, "", 1))
        ] != [value]:
            raise ValueError("research_evidence_claim_text_or_rounding")
        log.info("research_evidence_claim_built operation=%s", operation)
        return {
            "id": identifier,
            "section_id": section_id,
            "text": text,
            "value": format(value, "f"),
            "period": period,
            "unit": unit,
            "operation": operation,
            "operands": [dict(o) for o in operands],
        }
    except (ValueError, TypeError, KeyError, ArithmeticError, InvalidOperation) as exc:
        log.warning("research_evidence_claim_rejected type=%s", type(exc).__name__)
        raise ValueError("research_evidence_claim_invalid") from exc


def reconcile_amounts(reported_total, components):
    """Exact reported-total minus all provided signed components, not inferred gaps."""
    from decimal import Context, Inexact, InvalidOperation, localcontext

    try:
        if not isinstance(components, list) or not 1 <= len(components) <= 1000:
            raise ValueError("research_evidence_components_invalid")
        values = [_evidence_decimal(v) for v in components]
        with localcontext(Context(prec=512)) as context:
            context.traps[Inexact] = True
            total = sum(values)
            gap = _evidence_decimal(reported_total) - total
        log.info("research_evidence_reconciliation_calculated components=%d", len(values))
        return {"component_sum": format(total, "f"), "difference": format(gap, "f")}
    except (ValueError, TypeError, ArithmeticError, InvalidOperation):
        log.warning("research_evidence_reconciliation_rejected")
        raise


def rate_difference(before_pct, after_pct):
    """Signed cut magnitude: percentage-point change and basis-point conversion."""
    from decimal import Context, Inexact, InvalidOperation, localcontext

    try:
        with localcontext(Context(prec=512)) as context:
            context.traps[Inexact] = True
            difference = _evidence_decimal(before_pct) - _evidence_decimal(after_pct)
            bps = difference * 100
        log.info("research_evidence_rate_difference_calculated")
        return {"percentage_points": format(difference, "f"), "basis_points": format(bps, "f")}
    except (ValueError, TypeError, ArithmeticError, InvalidOperation):
        log.warning("research_evidence_rate_difference_rejected")
        raise


def numeric_summary(rows, expected, *, decimal_places=None):
    """Independent acceptance oracle; explicit display rounding never changes Host gates."""
    from decimal import ROUND_HALF_UP, InvalidOperation

    try:
        if not isinstance(expected, dict) or not 1 <= len(expected) <= 256:
            raise ValueError("research_summary_expected_invalid")
        places = {} if decimal_places is None else decimal_places
        if (
            not isinstance(places, dict)
            or not set(places).issubset(expected)
            or any(
                isinstance(p, bool) or not isinstance(p, int) or not 0 <= p <= 12
                for p in places.values()
            )
        ):
            raise ValueError("research_summary_precision_invalid")
        iterator = iter(rows)
        header = tuple(next(iterator, ()))
        if header[:2] != ("metric", "value") or any(v is not None for v in header[2:]):
            raise ValueError("research_summary_header_invalid")
        actual = {}
        for row in iterator:
            if len(row) < 2 or any(v is not None for v in row[2:]):
                raise ValueError("research_summary_columns_invalid")
            key, value = row[:2]
            if key is None and value is None:
                break
            if (
                not isinstance(key, str)
                or not 1 <= len(key) <= 80
                or key in actual
                or len(actual) >= 256
                or isinstance(value, bool)
                or not isinstance(value, (float, int))
            ):
                raise ValueError("research_summary_value_invalid")
            _evidence_decimal(value)
            actual[key] = value
        if not set(expected).issubset(actual):
            raise ValueError("research_summary_metric_missing")
        for key, value in expected.items():
            wanted = _evidence_decimal(value)
            if _evidence_decimal(actual[key]) == wanted:
                continue
            if key in places:
                from decimal import Decimal

                wanted = wanted.quantize(Decimal(1).scaleb(-places[key]), rounding=ROUND_HALF_UP)
            if _evidence_decimal(actual[key]) != wanted:
                raise ValueError("research_summary_numeric_mismatch")
        log.info("research_summary_verified metrics=%d", len(expected))
        return actual
    except (ValueError, TypeError, KeyError, ArithmeticError, InvalidOperation) as exc:
        log.warning("research_summary_rejected type=%s", type(exc).__name__)
        raise ValueError("research_summary_invalid") from exc


def validate_calculation_recipes(recipes):
    """Validate data-only calculation requests; never accept paths or executable code."""
    from decimal import Context, Decimal, InvalidOperation, localcontext

    if not isinstance(recipes, list) or len(recipes) > 4:
        raise ValueError("research_calculation_recipes_invalid")
    ids = set()
    for row in recipes:
        if (
            not isinstance(row, dict)
            or set(row)
            != {"id", "source_id", "source_sha256", "operation", "weights", "terminal_shocks"}
            or not isinstance(row["id"], str)
            or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,31}", row["id"])
            or row["id"] in ids
            or row["operation"] != "buy_and_hold"
            or not isinstance(row["source_id"], str)
            or not re.fullmatch(r"file:[a-f0-9]{24}", row["source_id"])
            or not isinstance(row["source_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", row["source_sha256"])
            or not isinstance(row["weights"], dict)
            or not 1 <= len(row["weights"]) <= 8
            or not isinstance(row["terminal_shocks"], dict)
            or not set(row["terminal_shocks"]).issubset(row["weights"])
        ):
            raise ValueError("research_calculation_recipe_invalid")
        ids.add(row["id"])
        try:
            weights = []
            for kind in ("weights", "terminal_shocks"):
                for name, value in row[kind].items():
                    if (
                        not isinstance(name, str)
                        or not 1 <= len(name) <= 80
                        or isinstance(value, bool)
                        or not isinstance(value, (str, int, float))
                        or len(str(value)) > 64
                    ):
                        raise ValueError("research_calculation_number_invalid")
                    if not re.fullmatch(
                        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,3})?", str(value)
                    ):
                        raise ValueError("research_calculation_number_invalid")
                    number = Decimal(str(value))
                    if not number.is_finite() or abs(number.as_tuple().exponent) > 30:
                        raise ValueError("research_calculation_number_invalid")
                    if kind == "weights":
                        if not 0 <= number <= 1:
                            raise ValueError("research_calculation_weight_invalid")
                        weights.append(number)
                    elif not -1 <= number <= 1:
                        raise ValueError("research_calculation_shock_invalid")
            with localcontext(Context(prec=128)):
                if sum(weights) != Decimal(1):
                    raise ValueError("research_calculation_weights_invalid")
        except (InvalidOperation, ArithmeticError) as exc:
            raise ValueError("research_calculation_number_invalid") from exc
    return recipes


def validate_payload(value):
    if not isinstance(value, dict) or not re.fullmatch(
        r"[a-f0-9]{24}", str(value.get("task_id", ""))
    ):
        raise ValueError("research_report_task_invalid")
    if not isinstance(value.get("title"), str) or not 1 <= len(value["title"]) <= 200:
        raise ValueError("research_report_title_invalid")
    sections, sources = value.get("sections"), value.get("sources", [])
    if not isinstance(sections, list) or not 1 <= len(sections) <= 50:
        raise ValueError("research_report_sections_invalid")
    if not isinstance(sources, list) or len(sources) > 200:
        raise ValueError("research_report_sources_invalid")
    ids = set()
    for item in sources:
        if not isinstance(item, dict) or not re.fullmatch(
            r"(?:web|file|dataset):[a-zA-Z0-9_-]{1,80}", str(item.get("id", ""))
        ):
            raise ValueError("research_report_source_invalid")
        if item["id"] in ids or not isinstance(item.get("title"), str) or len(item["title"]) > 1000:
            raise ValueError("research_report_source_duplicate_or_title")
        ids.add(item["id"])
        url = item.get("url")
        if url:
            if not isinstance(url, str) or len(url) > 4000 or any(ord(c) < 33 for c in url):
                raise ValueError("research_report_url_invalid")
            parts = urlsplit(url)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.hostname
                or parts.username
                or parts.password
            ):
                raise ValueError("research_report_url_invalid")
    stage_ids = set()
    for item in sections:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(k), str) for k in ("heading", "text")
        ):
            raise ValueError("research_report_section_invalid")
        if not item["heading"].strip() or len(item["heading"]) > 200 or len(item["text"]) > 100000:
            raise ValueError("research_report_section_size")
        stage = item.get("id")
        if stage is not None:
            if (
                not isinstance(stage, str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", stage)
                or stage in stage_ids
            ):
                raise ValueError("research_report_stage_invalid")
            stage_ids.add(stage)
        refs = item.get("citations", [])
        if (
            not isinstance(refs, list)
            or len(refs) > 200
            or any(not isinstance(ref, str) or ref not in ids for ref in refs)
        ):
            raise ValueError("research_report_citation_unknown")
    for key in ("required_sections", "missing"):
        values = value.get(key, [])
        if (
            not isinstance(values, list)
            or len(values) > 100
            or any(not isinstance(s, str) or len(s) > 10000 for s in values)
        ):
            raise ValueError("research_report_list_invalid")
    notes = value.get("notes", [])
    if not isinstance(notes, list) or len(notes) > 100:
        raise ValueError("research_report_notes_invalid")
    for note in notes:
        if (
            not isinstance(note, dict)
            or not isinstance(note.get("text"), str)
            or len(note["text"]) > 100000
        ):
            raise ValueError("research_report_note_invalid")
        refs = note.get("citations", [])
        if note.get("stage_id") is not None and note["stage_id"] not in stage_ids:
            raise ValueError("research_report_note_stage_unknown")
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or ref not in ids for ref in refs
        ):
            raise ValueError("research_report_note_citation_unknown")
    coverage = value.get("coverage", [])
    if not isinstance(coverage, list) or len(coverage) > 100:
        raise ValueError("research_report_coverage_invalid")
    for row in coverage:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("requirement_id"), str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", row["requirement_id"])
            or not isinstance(row.get("section_ids"), list)
            or len(row["section_ids"]) > 50
            or any(not isinstance(s, str) or s not in stage_ids for s in row["section_ids"])
            or not isinstance(row.get("excerpt"), str)
            or not 1 <= len(row["excerpt"]) <= 10000
        ):
            raise ValueError("research_report_coverage_invalid")
    validate_calculation_recipes(value.get("calculations", []))
    claims = value.get("numeric_claims", [])
    if not isinstance(claims, list) or len(claims) > 200:
        raise ValueError("research_report_numeric_claim_invalid")
    claim_ids = set()
    for claim in claims:
        if (
            not isinstance(claim, dict)
            or not isinstance(claim.get("id"), str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", claim["id"])
            or claim["id"] in claim_ids
            or claim.get("section_id") not in stage_ids
            or any(
                not isinstance(claim.get(key), str) or not 1 <= len(claim[key]) <= 10000
                for key in ("text", "unit", "period")
            )
            or isinstance(claim.get("value"), bool)
            or not isinstance(claim.get("value"), (str, int, float))
            or claim.get("operation", "identity")
            not in {"identity", "sum", "difference", "ratio", "percent_change"}
            or not isinstance(claim.get("operands"), list)
            or not 1 <= len(claim["operands"]) <= 50
        ):
            raise ValueError("research_report_numeric_claim_invalid")
        claim_ids.add(claim["id"])
        for operand in claim["operands"]:
            if (
                not isinstance(operand, dict)
                or any(
                    not isinstance(operand.get(key), str) or not 1 <= len(operand[key]) <= 10000
                    for key in ("observation_id", "quote", "period", "unit")
                )
                or isinstance(operand.get("value"), bool)
                or not isinstance(operand.get("value"), (str, int, float))
            ):
                raise ValueError("research_report_numeric_claim_operand_invalid")
    if len(json.dumps(value, ensure_ascii=False).encode()) > 2_000_000:
        raise ValueError("research_report_size")
    return value


def _bounded_bytes(path, maximum=16 * 1024 * 1024):
    if path.is_symlink() or not path.is_file():
        raise ValueError("research_report_archive_alias_or_missing")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        original = path.lstat()
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            original.st_dev,
            original.st_ino,
        ):
            raise ValueError("research_report_archive_alias")
        body = stream.read(maximum + 1)
    if len(body) > maximum:
        raise ValueError("research_report_archive_size")
    return body


def _version_read(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("research_report_archive_alias")
    version = json.loads(_bounded_bytes(directory / "version.json", 2_000_000))
    if not isinstance(version, dict):
        raise TypeError("research_report_archive_changed")
    rows = version.get("files", [])
    if (
        not isinstance(rows, list)
        or not 1 <= len(rows) <= 4
        or any(not isinstance(row, dict) for row in rows)
    ):
        raise ValueError("research_report_archive_changed")
    for row in rows:
        name = row.get("stored_name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9._-]{1,240}", name):
            raise ValueError("research_report_archive_changed")
        if hashlib.sha256(_bounded_bytes(directory / name)).hexdigest() != row.get("sha256"):
            raise ValueError("research_report_archive_changed")
    manifest = next((row for row in rows if row.get("name") == "research-report.json"), None)
    if not manifest:
        raise ValueError("research_report_archive_changed")
    raw = _bounded_bytes(directory / manifest["stored_name"], 2_000_000)
    report = validate_payload(json.loads(raw))
    archived_hashes = {row.get("name"): row.get("sha256") for row in rows}
    artifacts = report.get("artifacts", [])
    if not isinstance(artifacts, list) or any(not isinstance(row, dict) for row in artifacts):
        raise ValueError("research_report_archive_changed")
    missing = [row.get("name") for row in artifacts if row.get("name") not in archived_hashes]
    missing_formats = sorted(
        {"html", "docx", "pdf"}
        - {name.rsplit(".", 1)[-1] for name in archived_hashes if name != "research-report.json"}
    )
    snapshot = _snapshot_digest(archived_hashes, missing, missing_formats)
    identity = report["task_id"] + "-" + hashlib.sha256(raw).hexdigest()[:24] + "-" + snapshot[:12]
    if (
        report["task_id"] != version.get("task_id")
        or version.get("version_id") != identity
        or version.get("directory") != "report-versions/" + identity
        or (not directory.name.startswith(".pending-") and directory.name != identity)
        or version.get("missing_artifacts") != missing
        or version.get("missing_formats") != missing_formats
        or any(
            archived_hashes.get(row.get("name")) != row.get("sha256")
            for row in artifacts
            if row.get("name") not in missing
        )
    ):
        raise ValueError("research_report_archive_changed")
    return version


def _snapshot_digest(hashes, missing, formats):
    return hashlib.sha256(
        json.dumps(
            {"hashes": hashes, "missing_artifacts": missing, "missing_formats": formats},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def archive_report_version(output, expected_task_id=None):
    """Verify and atomically retain the current payload and all published bytes."""
    output = Path(output)
    if output.is_symlink():
        raise ValueError("research_report_archive_alias")
    current = output / "research-report.json"
    if not current.exists() and not current.is_symlink():
        return None
    try:
        raw = _bounded_bytes(current, 2_000_000)
        payload = validate_payload(json.loads(raw))
        if expected_task_id is not None and payload["task_id"] != expected_task_id:
            raise ValueError("research_report_archive_task_mismatch")
        artifacts = payload.get("artifacts", [])
        if (
            not isinstance(artifacts, list)
            or len(artifacts) > 3
            or any(
                not isinstance(row, dict) or not isinstance(row.get("name"), str)
                for row in artifacts
            )
            or len({row["name"].rsplit(".", 1)[-1] for row in artifacts}) != len(artifacts)
            or not {row["name"].rsplit(".", 1)[-1] for row in artifacts}.issubset(
                {"html", "docx", "pdf"}
            )
        ):
            raise ValueError("research_report_archive_artifact_invalid")
        bodies = {"research-report.json": raw}
        missing = []
        for artifact in artifacts:
            name = artifact.get("name")
            if not isinstance(name, str) or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,149}", name
            ):
                raise ValueError("research_report_archive_artifact_invalid")
            if not (output / name).exists() and not (output / name).is_symlink():
                missing.append(name)
                continue
            body = _bounded_bytes(output / name)
            if hashlib.sha256(body).hexdigest() != artifact.get("sha256"):
                raise ValueError("research_report_archive_artifact_changed")
            bodies[name] = body
        digest = hashlib.sha256(raw).hexdigest()
        hashes = {name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()}
        missing_formats = sorted(
            {"html", "docx", "pdf"}
            - {name.rsplit(".", 1)[-1] for name in bodies if name != "research-report.json"}
        )
        snapshot = _snapshot_digest(hashes, missing, missing_formats)
        version_id = payload["task_id"] + "-" + digest[:24] + "-" + snapshot[:12]
        archive = output / "report-versions"
        if archive.is_symlink():
            raise ValueError("research_report_archive_alias")
        archive.mkdir(exist_ok=True)
        target = archive / version_id
        version = {
            "task_id": payload["task_id"],
            "version_id": version_id,
            "directory": "report-versions/" + version_id,
            "missing_artifacts": missing,
            "missing_formats": missing_formats,
            "files": [
                {
                    "name": name,
                    "stored_name": version_id + "-" + name,
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
                for name, body in bodies.items()
            ],
        }
        if target.exists() or target.is_symlink():
            existing = _version_read(target)
            if existing != version:
                raise ValueError("research_report_archive_changed")
            return existing
        # mkdtemp resolves relative directories through getcwd on Python 3.12.
        # Keep the existing session-relative capability without requiring it.
        pending = archive / (".pending-" + uuid4().hex)
        pending.mkdir(mode=0o700)
        try:
            for row in version["files"]:
                destination = pending / row["stored_name"]
                with destination.open("xb") as stream:
                    stream.write(bodies[row["name"]])
                    stream.flush()
                    os.fsync(stream.fileno())
                destination.chmod(0o444)
            (pending / "version.json").write_text(json.dumps(version), encoding="utf-8")
            (pending / "version.json").chmod(0o444)
            _version_read(pending)
            try:
                pending.rename(target)
            except OSError:
                if not target.exists() or _version_read(target) != version:
                    raise
        finally:
            if pending.exists():
                shutil.rmtree(pending)
        log.info("research_report_version_archived files=%d", len(version["files"]))
        return version
    except OSError as exc:
        log.warning("research_report_archive_failed type=%s", type(exc).__name__)
        raise ValueError("research_report_archive_io_failed") from None
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        log.warning("research_report_archive_failed type=%s", type(exc).__name__)
        raise


def list_report_versions(output, limit=20):
    """Project bounded verified versions; never treat old quality claims as trusted."""
    output = Path(output)
    archive = output / "report-versions"
    if archive.is_symlink() or output.is_symlink():
        raise ValueError("research_report_archive_alias")
    if not archive.exists():
        return []
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("research_report_archive_limit_invalid")
    versions = []
    for path in sorted(archive.iterdir(), key=lambda item: item.name, reverse=True):
        if path.name.startswith("."):
            continue
        try:
            version = _version_read(path)
            manifest = next(
                row for row in version["files"] if row["name"] == "research-report.json"
            )
            versions.append(
                {
                    **version,
                    "report": json.loads(_bounded_bytes(path / manifest["stored_name"], 2_000_000)),
                    "quality": "incomplete",
                }
            )
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            log.warning("research_report_version_invalid type=%s", type(exc).__name__)
            versions.append(
                {
                    "version_id": path.name,
                    "quality": "invalid",
                    "issues": ["report_archive_invalid"],
                }
            )
        if len(versions) >= limit:
            break
    return versions


def report_blocks(payload):
    """The same text/version is consumed by all three renderers."""
    blocks = [(payload["title"], True)]
    if payload.get("as_of"):
        blocks.append(("研究截止时间：" + str(payload["as_of"]), False))
    for section in payload["sections"]:
        blocks.extend([(section["heading"], True), (section["text"], False)])
        if section.get("citations"):
            blocks.append(("引用：" + ", ".join(section["citations"]), False))
    blocks.append(("来源与证据", True))
    for source in payload.get("sources", []):
        blocks.append(
            (source["id"] + " · " + source["title"] + " " + str(source.get("url", "")), False)
        )
    missing = list(payload.get("missing", []))
    headings = {s["heading"] for s in payload["sections"]}
    missing.extend(
        "未覆盖要求：" + s for s in payload.get("required_sections", []) if s not in headings
    )
    if missing:
        blocks.append(("缺口与限制（研究质量未通过）", True))
        blocks.extend((text, False) for text in missing)
    return blocks


def render_pdf(path, payload):
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    try:
        previous_directory = os.getcwd()
    except PermissionError:
        previous_directory = str(Path(__file__).resolve().parent.parent)
    try:
        # ReportLab initializes paths from CWD. Only the already writable output
        # directory is readable under Seatbelt; session-root grants stay closed.
        os.chdir(path.parent)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        font = Path(__file__).with_name("fonts") / "NotoSansSC-Regular.ttf"
        if font.is_symlink() or not font.is_file():
            raise ValueError("research_pdf_font_missing")
        pdfmetrics.registerFont(TTFont("ResearchCJK", str(font)))
        styles = {
            True: ParagraphStyle(
                "heading",
                fontName="ResearchCJK",
                fontSize=15,
                leading=22,
                wordWrap="CJK",
                spaceBefore=12,
                keepWithNext=True,
            ),
            False: ParagraphStyle(
                "body",
                fontName="ResearchCJK",
                fontSize=10,
                leading=17,
                wordWrap="CJK",
                splitLongWords=True,
            ),
        }
        story = []
        for text, heading in report_blocks(payload):
            if any(
                ord(char) not in pdfmetrics.getFont("ResearchCJK").face.charToGlyph
                for char in text
                if char not in "\n\r\t"
            ):
                raise ValueError("research_pdf_glyph_missing")
            story.extend(
                [Paragraph(html.escape(text).replace("\n", "<br/>"), styles[heading]), Spacer(1, 6)]
            )
        SimpleDocTemplate(
            str(path),
            pagesize=A4,
            title=payload["title"],
            leftMargin=42,
            rightMargin=42,
            topMargin=42,
            bottomMargin=42,
        ).build(story)
        log.info("research_pdf_rendered")
        return Path(path)
    except Exception as exc:
        log.error("research_pdf_render_failed type=%s", type(exc).__name__)
        raise
    finally:
        os.chdir(previous_directory)


def write_research_report(output, payload):
    import pdfplumber
    from docx import Document

    try:
        validate_payload(payload)
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        stem = "research-report-" + uuid4().hex[:12]
        paths = {kind: output / (stem + "." + kind) for kind in ("html", "docx", "pdf")}
        paths["json"] = output / "research-report.json"
        if any(p.is_symlink() for p in paths.values()):
            raise ValueError("research_report_output_alias")
        archive_report_version(output)
        blocks = report_blocks(payload)
        doc = Document()
        for text, heading in blocks:
            doc.add_heading(text, level=1) if heading else doc.add_paragraph(text)
        doc.save(paths["docx"])
        body = "".join(
            f'<{"h2" if heading else "p"}>{html.escape(text)}</{"h2" if heading else "p"}>'
            for text, heading in blocks
        )
        paths["html"].write_text(
            '<!doctype html><html lang="zh"><meta charset="utf-8"><title>'
            + html.escape(payload["title"])
            + "</title><body>"
            + body
            + "</body></html>",
            encoding="utf-8",
        )
        render_pdf(paths["pdf"], payload)
        Document(paths["docx"])
        with pdfplumber.open(paths["pdf"]) as pdf:
            if not pdf.pages or not any((p.extract_text() or "").strip() for p in pdf.pages):
                raise ValueError("research_pdf_empty")
        published = {
            **payload,
            "artifacts": [
                {"name": paths[k].name, "sha256": hashlib.sha256(paths[k].read_bytes()).hexdigest()}
                for k in ("html", "docx", "pdf")
            ],
        }
        manifest = output / (stem + ".json")
        manifest.write_text(json.dumps(published, ensure_ascii=False), encoding="utf-8")
        manifest.replace(paths["json"])
        log.info("research_report_rendered formats=3")
        return paths
    except Exception as exc:
        log.error("research_report_failed type=%s", type(exc).__name__)
        raise
