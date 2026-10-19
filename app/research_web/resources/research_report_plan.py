"""Data-only report assembly in the original sandbox; never a quality verdict."""

import hashlib
import json
import logging
import os
import re
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from pathlib import Path
from uuid import uuid4

try:
    from research_report import (
        _bounded_bytes,
        _evidence_decimal,
        archive_report_version,
        canonical_source,
        evidence_section,
        load_business_evidence,
        render_markdown,
        select_business_evidence,
        validate_payload,
        write_research_report,
        write_summary_workbook,
    )
except ImportError:
    from .research_report import (
        _bounded_bytes,
        _evidence_decimal,
        archive_report_version,
        canonical_source,
        evidence_section,
        load_business_evidence,
        render_markdown,
        select_business_evidence,
        validate_payload,
        write_research_report,
        write_summary_workbook,
    )

log = logging.getLogger("research_web.report_plan")
EXTRACTED_METRICS = frozenset(
    {
        "total_revenue",
        "net_income",
        "operating_income",
        "operating_cash_flow",
        "signed_cash_ppe",
        "signed_share_repurchase",
        "signed_cash_dividends",
        "net_financing_cash_flow",
        "target_lower_pct",
        "target_upper_pct",
        "reserve_balance_rate_pct",
        "primary_credit_rate_pct",
        "selected_control_count",
        "function_count",
    }
    | {
        category + "_" + suffix
        for category in ("headline", "core", "energy", "gasoline", "food")
        for suffix in ("mom_sa_pct", "yoy_nsa_pct")
    }
)


def _object(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(
        optional
    ):
        raise ValueError("research_report_plan_fields")


def _text(value, limit):
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise ValueError("research_report_plan_text")


def _resolve(bundle, key):
    _text(key, 200)
    matches = [
        row
        for row in bundle["observations"]
        if isinstance(row, dict)
        and key
        in (
            row.get("id"),
            row.get("metric"),
            str(row.get("metric")) + "@" + str(row.get("period")),
        )
    ]
    if len(matches) != 1:
        raise ValueError("research_report_plan_missing_or_ambiguous_observation")
    return matches[0]


def _input_number(row, bundle):
    """Use extracted primitives; independently recount the two bounded record sets."""
    if row.get("kind") != "business_numeric" or row.get("metric") not in EXTRACTED_METRICS:
        raise ValueError("research_report_plan_calculation_needs_raw_operand")
    if row["metric"] == "selected_control_count":
        records = [
            r
            for r in bundle["observations"]
            if isinstance(r, dict)
            and r.get("metric") == "control_text"
            and set(r["source_ids"]) == set(row["source_ids"])
        ]
        number = Decimal(len({r["heading"] for r in records}))
    elif row["metric"] == "function_count":
        names = {
            m[1]
            for proof in row["proofs"]
            for span in proof["spans"]
            if (m := re.fullmatch(r"5\.[1-4]\s+(Govern|Map|Measure|Manage)", span["text"].strip()))
        }
        number = Decimal(len(names))
    else:
        number = _evidence_decimal(row["value"])
    return number, row["unit"], set(row["source_ids"])


def _summary_calculation(bundle, target, steps, budget, used):
    """Independent bounded arithmetic from primitives, not the target derived value."""
    if steps is None:
        value, unit, parents = _input_number(target, bundle)
        used[target["id"]] = target
        operation = {
            "selected_control_count": "count_control_records",
            "function_count": "count_function_headers",
        }.get(target["metric"], "identity")
        return (
            value,
            unit,
            parents,
            [["extract", operation, target["id"], format(value, "f"), unit, sorted(parents)]],
        )
    if not isinstance(steps, list) or not 1 <= len(steps) <= 16:
        raise ValueError("research_report_plan_calculation_limit")
    values, trace = {}, []
    for step in steps:
        budget[0] += 1
        if budget[0] > 64:
            raise ValueError("research_report_plan_calculation_limit")
        _object(step, {"id", "operation", "operands"})
        sid, operation, operands = step["id"], step["operation"], step["operands"]
        if (
            not isinstance(sid, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", sid)
            or sid in values
            or operation
            not in {
                "identity",
                "abs",
                "sum",
                "difference",
                "ratio",
                "percent_change",
                "basis_points",
            }
            or not isinstance(operands, list)
            or not 1 <= len(operands) <= 8
        ):
            raise ValueError("research_report_plan_calculation_invalid")
        resolved = []
        for ref in operands:
            _text(ref, 200)
            if ref.startswith("$"):
                if ref[1:] not in values:
                    raise ValueError("research_report_plan_calculation_forward_reference")
                resolved.append(values[ref[1:]])
            else:
                row = _resolve(bundle, ref)
                used[row["id"]] = row
                resolved.append(_input_number(row, bundle))
        counts = {
            "identity": 1,
            "abs": 1,
            "difference": 2,
            "ratio": 2,
            "percent_change": 2,
            "basis_points": 1,
        }
        if operation in counts and len(resolved) != counts[operation]:
            raise ValueError("research_report_plan_calculation_arity")
        units = {r[1] for r in resolved}
        if len(units) != 1:
            raise ValueError("research_report_plan_calculation_units")
        unit = resolved[0][1]
        numbers = [r[0] for r in resolved]
        with localcontext(Context(prec=96)):
            if operation == "identity":
                value = numbers[0]
            elif operation == "abs":
                value = abs(numbers[0])
            elif operation == "sum":
                value = sum(numbers)
            elif operation == "difference":
                value = numbers[0] - numbers[1]
                unit = "percentage_points" if unit == "%" else unit
            elif operation == "ratio":
                value = numbers[0] / numbers[1]
                unit = "ratio"
            elif operation == "percent_change":
                value = (numbers[0] - numbers[1]) / numbers[1] * 100
                unit = "%"
            else:
                if unit != "percentage_points":
                    raise ValueError("research_report_plan_calculation_units")
                value = numbers[0] * 100
                unit = "basis_points"
        parents = set().union(*(r[2] for r in resolved))
        values[sid] = value, unit, parents
        trace.append(
            [
                sid,
                operation,
                json.dumps(operands, ensure_ascii=False),
                format(value, "f"),
                unit,
                sorted(parents),
            ]
        )
    return value, unit, parents, trace


def build_business_report_plan(context, plan, bundle):
    """Assemble nominated evidence and unverified analysis, preserving every gap."""
    try:
        _object(context, {"task_id", "contract_sha256", "as_of", "requirement_ids"})
        if (
            not re.fullmatch(r"[a-f0-9]{24}", str(context["task_id"]))
            or not re.fullmatch(r"[a-f0-9]{64}", str(context["contract_sha256"]))
            or not isinstance(context["requirement_ids"], list)
            or not 1 <= len(context["requirement_ids"]) <= 100
            or len(set(context["requirement_ids"])) != len(context["requirement_ids"])
            or any(
                not isinstance(r, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", r)
                for r in context["requirement_ids"]
            )
            or not isinstance(bundle, dict)
            or not isinstance(bundle.get("observations"), list)
            or len(bundle["observations"]) > 200
            or any(bundle.get(k) != context[k] for k in ("task_id", "contract_sha256"))
        ):
            raise ValueError("research_report_plan_binding")
        _text(context["as_of"], 100)
        _object(plan, {"title", "sections", "summary", "missing"}, {"controls"})
        if len(json.dumps(plan, ensure_ascii=False, allow_nan=False).encode()) > 32000:
            raise ValueError("research_report_plan_limit")
        _text(plan["title"], 200)
        if (
            not isinstance(plan["sections"], list)
            or not 1 <= len(plan["sections"]) <= 40
            or not isinstance(plan["summary"], list)
            or not 1 <= len(plan["summary"]) <= 256
            or not isinstance(plan["missing"], list)
            or len(plan["missing"]) > 100
        ):
            raise ValueError("research_report_plan_limit")
        sources = [canonical_source(bundle["sources"], s["id"]) for s in bundle["sources"]]
        result = {"sections": [], "notes": [], "coverage": [], "numeric_claims": []}
        selected, stage_ids, section_rows = {}, set(), {}
        total = 0
        for section in plan["sections"]:
            _object(section, {"id", "heading", "evidence_ids", "requirement_ids"}, {"analysis"})
            sid = section["id"]
            if (
                not isinstance(sid, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", sid)
                or sid in stage_ids
            ):
                raise ValueError("research_report_plan_section")
            stage_ids.add(sid)
            refs, requirements = section["evidence_ids"], section["requirement_ids"]
            if (
                not isinstance(refs, list)
                or not 1 <= len(refs) <= 40
                or not isinstance(requirements, list)
                or not requirements
                or any(r not in context["requirement_ids"] for r in requirements)
            ):
                raise ValueError("research_report_plan_selection")
            total += len(refs)
            if total > 40:
                raise ValueError("research_report_plan_evidence_limit")
            blocks = select_business_evidence(bundle, {ref: requirements for ref in refs})
            if len(blocks["sections"]) != len(refs):
                raise ValueError("research_report_plan_duplicate_selection")
            rows = [_resolve(bundle, ref) for ref in refs]
            selected.update({row["id"]: row for row in rows})
            section_rows[sid] = {row["id"] for row in rows}
            text = "\n\n".join(s["text"] for s in blocks["sections"])
            if "analysis" in section and section["analysis"] != "":
                _text(section["analysis"], 10000)
                text += "\n\n" + section["analysis"]
            parents = list(dict.fromkeys(ref for s in blocks["sections"] for ref in s["citations"]))
            for ref in parents:
                canonical_source(sources, ref)
            group = evidence_section(sid, section["heading"], text, parents, requirements)
            for key, items in result.items():
                items.extend(group[key])
            for claim in blocks["numeric_claims"]:
                identity = hashlib.sha256((sid + ":" + claim["id"]).encode()).hexdigest()[:32]
                result["numeric_claims"].append(
                    {**claim, "id": "claim_" + identity, "section_id": sid}
                )
        metrics, places, calculation_rows, operands_used = {}, {}, [], {}
        calculation_budget = [0]
        for row in plan["summary"]:
            _object(row, {"metric", "observation_id", "decimal_places"}, {"calculation"})
            key, precision = row["metric"], row["decimal_places"]
            observation = _resolve(bundle, row["observation_id"])
            if (
                not isinstance(key, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key)
                or key in metrics
                or observation["id"] not in selected
                or observation["kind"] != "business_numeric"
                or isinstance(precision, bool)
                or not isinstance(precision, int)
                or not 0 <= precision <= 12
            ):
                raise ValueError("research_report_plan_summary")
            value, unit, parents, trace = _summary_calculation(
                bundle, observation, row.get("calculation"), calculation_budget, operands_used
            )
            if unit != observation["unit"] or parents != set(observation["source_ids"]):
                raise ValueError("research_report_plan_calculation_lineage")
            with localcontext(Context(prec=512)):
                quantum = Decimal(1).scaleb(-precision)
                if value.quantize(quantum, rounding=ROUND_HALF_UP) != _evidence_decimal(
                    observation["value"]
                ).quantize(quantum, rounding=ROUND_HALF_UP):
                    raise ValueError("research_report_plan_calculation_mismatch")
            metrics[key], places[key] = value, precision
            calculation_rows.extend([[key, *step, 96] for step in trace])
        facts = {**selected, **operands_used}
        if len(facts) > 40:
            raise ValueError("research_report_plan_evidence_limit")
        sheets = {
            "Facts": [["metric", "period", "value", "unit", "source_ref"]],
            "Calc": [
                [
                    "metric",
                    "step",
                    "operation",
                    "operands",
                    "result_unrounded",
                    "unit",
                    "source_ref",
                    "arithmetic_precision",
                ],
                *calculation_rows,
            ],
        }
        for row in facts.values():
            if row["kind"] == "business_numeric":
                sheets["Facts"].append(
                    [row["metric"], row["period"], row["value"], row["unit"], row["source_ids"]]
                )
        controls = plan.get("controls", [])
        if not isinstance(controls, list) or len(controls) > 40:
            raise ValueError("research_report_plan_controls")
        if controls:
            sheets["Controls"] = [
                [
                    "control_id",
                    "official_requirement",
                    "evidence_needed",
                    "proposed_owner",
                    "status",
                    "source_ref",
                ]
            ]
        control_ids = set()
        for row in controls:
            _object(row, {"observation_id", "evidence_needed", "proposed_owner"})
            observation = _resolve(bundle, row["observation_id"])
            if (
                observation["id"] not in selected
                or observation.get("kind") != "business_quote"
                or observation.get("metric") != "control_text"
                or not re.fullmatch(
                    r"(?:Govern|Map|Measure|Manage) [0-9]+\.[0-9]+", observation.get("heading", "")
                )
                or observation["heading"] in control_ids
            ):
                raise ValueError("research_report_plan_controls")
            control_ids.add(observation["heading"])
            _text(row["evidence_needed"], 2000)
            _text(row["proposed_owner"], 2000)
            section = next(
                s for s in result["sections"] if observation["id"] in section_rows[s["id"]]
            )
            # Never hide unverified proposals in a workbook outside Host-scored text.
            for name in ("evidence_needed", "proposed_owner"):
                if row[name] not in section["text"]:
                    section["text"] += "\n\n" + row[name]
            for note in result["notes"]:
                if note["stage_id"] == section["id"]:
                    note["text"] = section["text"]
            for coverage in result["coverage"]:
                if section["id"] in coverage["section_ids"]:
                    coverage["excerpt"] = section["text"]
            sheets["Controls"].append(
                [
                    observation["heading"],
                    observation["content"].split("\n", 1)[0],
                    row["evidence_needed"],
                    row["proposed_owner"],
                    "not_assessed",
                    section["citations"],
                ]
            )
        if any(len(s["text"]) > 10000 for s in result["sections"]):
            raise ValueError("research_report_plan_section_limit")
        payload = {
            "task_id": context["task_id"],
            "title": plan["title"],
            "as_of": context["as_of"],
            "sources": sources,
            "missing": list(plan["missing"]),
            **result,
        }
        validate_payload(payload)
        log.info(
            "research_report_plan_assembled sections=%d claims=%d",
            len(result["sections"]),
            len(result["numeric_claims"]),
        )
        return {"payload": payload, "metrics": metrics, "decimal_places": places, "sheets": sheets}
    except (ValueError, TypeError, KeyError, ArithmeticError):
        log.warning("research_report_plan_rejected")
        raise


def write_business_report_plan(context, plan, *, output="outputs"):
    """Stage all formats, preserve old canonical versions, publish JSON last."""
    stage, paths, backups, published = None, {}, {}, []
    before, new_hashes = {}, {}
    withheld, quarantined, recovery = None, None, None
    retain_stage = False
    try:
        bundle = load_business_evidence(context["task_id"], context["contract_sha256"])
        result = build_business_report_plan(context, plan, bundle)
        output = Path(output)
        if output.is_symlink():
            raise ValueError("research_report_plan_output_alias")
        output.mkdir(parents=True, exist_ok=True)
        stage = output / (".report-plan-" + uuid4().hex)
        stage.mkdir(mode=0o700)
        paths["xlsx"] = stage / "summary.xlsx"
        write_summary_workbook(
            paths["xlsx"],
            result["metrics"],
            decimal_places=result["decimal_places"],
            sheets=result["sheets"],
        )
        paths.update(write_research_report(stage, result["payload"]))
        paths["md"] = stage / "report.md"
        paths["md"].write_text(render_markdown(result["payload"]), encoding="utf-8")
        for key, path in paths.items():
            target = output / path.name
            if target.is_symlink() or (key in {"html", "docx", "pdf"} and target.exists()):
                raise ValueError("research_report_plan_output_alias")
            new_hashes[key] = hashlib.sha256(
                _bounded_bytes(path, 2_000_000 if key == "json" else 16 * 1024 * 1024)
            ).hexdigest()
        for key in ("xlsx", "md", "json"):
            target = output / paths[key].name
            before[key] = _bounded_bytes(target) if target.exists() else None
            if before[key] is not None:
                backup = stage / ("previous-" + key)
                backup.write_bytes(before[key])
                backups[key] = backup
        recovery = stage / "recovery.json"
        recovery.write_text(
            json.dumps(
                {
                    "task_id": context["task_id"],
                    "canonical_withheld": "withheld-json",
                    "canonical_quarantined": "failed-json",
                    "before": {
                        key: {
                            "name": paths[key].name,
                            "backup": backups[key].name if key in backups else None,
                            "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
                        }
                        for key, raw in before.items()
                    },
                    "new": {
                        key: {"name": path.name, "sha256": new_hashes[key]}
                        for key, path in paths.items()
                    },
                }
            ),
            encoding="utf-8",
        )
        archive_report_version(output)
        # No stale canonical pointer may certify mixed sidecars during publication.
        if before["json"] is not None:
            withheld = stage / "withheld-json"
            os.replace(output / paths["json"].name, withheld)
        for key in ["xlsx", "html", "docx", "pdf", "md", "json"]:
            os.replace(paths[key], output / paths[key].name)
            published.append(key)
        descriptor = os.open(output, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        log.info("research_report_plan_written formats=%d", len(paths))
        return {
            "written": {key: str(output / path.name) for key, path in paths.items()},
            "quality_not_evaluated": True,
            "next": "research_check_quality",
        }
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError):
        log.warning("research_report_plan_write_failed")
        try:
            # Withdraw the new pointer before rolling back any of its artifacts.
            # An interrupted rollback must leave no canonical mixed-version report.
            if "json" in published:
                target = output / paths["json"].name
                if hashlib.sha256(_bounded_bytes(target)).hexdigest() != new_hashes["json"]:
                    raise ValueError("research_report_plan_rollback_changed")
                quarantined = stage / "failed-json"
                if quarantined.exists() or quarantined.is_symlink():
                    raise ValueError("research_report_plan_rollback_changed")
                os.replace(target, quarantined)
            for key in reversed(published):
                if key == "json":
                    continue
                target = output / paths[key].name
                if hashlib.sha256(_bounded_bytes(target)).hexdigest() != new_hashes[key]:
                    raise ValueError("research_report_plan_rollback_changed")
                if key in backups:
                    if _bounded_bytes(backups[key]) != before[key]:
                        raise ValueError("research_report_plan_rollback_changed")
                    os.replace(backups[key], target)
                else:
                    target.unlink()
            if withheld is not None and withheld.exists():
                target = output / paths["json"].name
                if (
                    target.exists()
                    or target.is_symlink()
                    or _bounded_bytes(withheld) != before["json"]
                ):
                    raise ValueError("research_report_plan_rollback_changed")
                os.replace(withheld, target)
            log.info("research_report_plan_rolled_back objects=%d", len(published))
        except (OSError, ValueError):
            retain_stage = True
            log.error("research_report_plan_recovery_required")
            raise RuntimeError("research_report_plan_recovery_required") from None
        raise
    finally:
        if not retain_stage:
            for path in [*paths.values(), *backups.values(), withheld, quarantined, recovery]:
                if path is not None and (path.exists() or path.is_symlink()):
                    path.unlink()
        if stage is not None and not retain_stage:
            try:
                stage.rmdir()
            except OSError:
                log.warning("research_report_plan_staging_retained")
