"""Validate a structured report digest without network or host-process access."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("research.skill.sell_side.validator")
MAX_NODES = 12
LAYERS = ("facts", "sourceOpinions", "newEvidence", "inferences")
ATTRIBUTIONS = {"研报明示", "研报隐含", "无明确操作含义"}
ACTION_LABELS = {
    "现在行动",
    "等待催化",
    "等待验证",
    "继续跟踪",
    "风险上升",
    "降低暴露",
    "退出条件触发",
    "无明确行动",
}
READABLE_ACCESS = {"full_text", "user_supplied_text"}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)


def _xml_compatible(value: str) -> bool:
    return all(
        character in "\t\n\r"
        or "\x20" <= character <= "\ud7ff"
        or "\ue000" <= character <= "\ufffd"
        or "\U00010000" <= character <= "\U0010ffff"
        for character in value
    )


def _check_xml_text(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, str):
        if not _xml_compatible(value):
            errors.append(f"{location} contains text forbidden by XML 1.0")
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_xml_text(item, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_xml_text(item, f"{location}[{index}]", errors)


def _check_citations(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{location}.citations must contain source locators")
        return
    for index, citation in enumerate(value):
        if not isinstance(citation, dict):
            errors.append(f"{location}.citations[{index}] must be an object")
            continue
        if not _text(citation.get("source")):
            errors.append(f"{location}.citations[{index}].source is required")
        if not _text(citation.get("locator")):
            errors.append(f"{location}.citations[{index}].locator is required")


def _check_claims(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{location} must be a non-empty array")
        return
    for index, claim in enumerate(value):
        item_location = f"{location}[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{item_location} must be an object")
            continue
        if not _text(claim.get("text")):
            errors.append(f"{item_location}.text is required")
        _check_citations(claim.get("citations"), item_location, errors)
        if location.endswith("inferences") and not _text_list(claim.get("premises")):
            errors.append(f"{item_location}.premises must identify cited premises")


def _check_named_items(
    value: Any,
    location: str,
    required_fields: tuple[str, ...],
    errors: list[str],
) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{location} must be a non-empty array")
        return
    for index, item in enumerate(value):
        item_location = f"{location}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_location} must be an object")
            continue
        for field in required_fields:
            current = item.get(field)
            valid = _text_list(current) if isinstance(current, list) else _text(current)
            if not valid:
                errors.append(f"{item_location}.{field} is required")


def validate_digest(digest: Any) -> dict[str, Any]:
    """Return deterministic validation evidence; never repair missing research."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(digest, dict):
        errors.append("digest must be an object")
    else:
        if type(digest.get("schemaVersion")) is not int or digest.get("schemaVersion") != 1:
            errors.append("schemaVersion must be integer 1")
        _check_xml_text(digest, "digest", errors)

        source = digest.get("source")
        if not isinstance(source, dict):
            errors.append("source must be an object")
        else:
            for field in ("title", "publishedAt", "accessStatus", "locatorScheme"):
                if not _text(source.get(field)):
                    errors.append(f"source.{field} is required")
            if source.get("accessStatus") not in READABLE_ACCESS:
                errors.append(
                    "source.accessStatus requires full text; snippets or inaccessible sources "
                    "are insufficient"
                )

        baseline = digest.get("baseline")
        if not isinstance(baseline, dict):
            errors.append("baseline must be an object")
        else:
            for field in ("type", "asOf", "description"):
                if not _text(baseline.get(field)):
                    errors.append(f"baseline.{field} is required")

        layers = digest.get("claimLayers")
        if not isinstance(layers, dict):
            errors.append("claimLayers must be an object")
        else:
            for layer in LAYERS:
                _check_claims(layers.get(layer), f"claimLayers.{layer}", errors)

        counter = digest.get("counterEvidence")
        if not isinstance(counter, list) or not counter:
            errors.append("counterEvidence must be a non-empty array")
        else:
            for index, item in enumerate(counter):
                location = f"counterEvidence[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{location} must be an object")
                    continue
                for field in ("text", "effect"):
                    if not _text(item.get(field)):
                        errors.append(f"{location}.{field} is required")
                _check_citations(item.get("citations"), location, errors)

        scenarios = digest.get("scenarios")
        _check_named_items(
            scenarios,
            "scenarios",
            ("name", "conditions", "window", "signals", "invalidationSignals"),
            errors,
        )

        action = digest.get("actionAssessment")
        if not isinstance(action, dict):
            errors.append("actionAssessment must be an object")
        else:
            if action.get("label") not in ACTION_LABELS:
                errors.append("actionAssessment.label is invalid")
            if action.get("attribution") not in ATTRIBUTIONS:
                errors.append("actionAssessment.attribution is invalid")
            for field in ("audience", "horizon"):
                if not _text(action.get(field)):
                    errors.append(f"actionAssessment.{field} is required")
            for field in (
                "conditions",
                "keyAssumptions",
                "validationIndicators",
                "invalidationSignals",
            ):
                if not _text_list(action.get(field)):
                    errors.append(f"actionAssessment.{field} must be a non-empty text array")
            _check_citations(action.get("citations"), "actionAssessment", errors)

        if not _text_list(digest.get("limitations")):
            errors.append("limitations must be a non-empty text array")

        framework = digest.get("knowledgeFramework")
        if framework is not None:
            if not isinstance(framework, dict):
                errors.append("knowledgeFramework must be an object")
            else:
                nodes = framework.get("nodes")
                edges = framework.get("edges")
                if not isinstance(nodes, list) or not 2 <= len(nodes) <= MAX_NODES:
                    errors.append(f"knowledgeFramework.nodes needs 2-{MAX_NODES} nodes")
                    node_ids: set[str] = set()
                else:
                    node_ids = set()
                    for index, node in enumerate(nodes):
                        location = f"knowledgeFramework.nodes[{index}]"
                        if not isinstance(node, dict):
                            errors.append(f"{location} must be an object")
                            continue
                        node_id = node.get("id")
                        if not isinstance(node_id, str) or not node_id.strip():
                            errors.append(f"{location}.id is required")
                        elif node_id in node_ids:
                            errors.append("knowledgeFramework node ids must be unique")
                        else:
                            node_ids.add(node_id)
                        if not _text(node.get("label")):
                            errors.append(f"{location}.label is required")
                if not isinstance(edges, list) or not edges:
                    errors.append("knowledgeFramework.edges needs at least one sourced relation")
                else:
                    for index, edge in enumerate(edges):
                        location = f"knowledgeFramework.edges[{index}]"
                        if not isinstance(edge, dict):
                            errors.append(f"{location} must be an object")
                            continue
                        for field in ("from", "to", "relation"):
                            if not _text(edge.get(field)):
                                errors.append(f"{location}.{field} is required")
                        source, target = edge.get("from"), edge.get("to")
                        if (
                            not isinstance(source, str)
                            or not source.strip()
                            or not isinstance(target, str)
                            or not target.strip()
                        ):
                            continue
                        if source not in node_ids or target not in node_ids:
                            errors.append(f"{location} endpoints must reference a declared node")
                        elif source == target:
                            errors.append(f"{location} endpoints must be distinct")
                        _check_citations(edge.get("citations"), location, errors)

    result = {"valid": not errors, "errors": errors, "warnings": warnings}
    if errors:
        LOGGER.warning("digest_validation_failed errors=%d", len(errors))
    else:
        LOGGER.info("digest_validation_passed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a report digest JSON file")
    parser.add_argument("digest", type=Path)
    args = parser.parse_args()
    try:
        digest = json.loads(args.digest.read_text(encoding="utf-8"))
        result = validate_digest(digest)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["valid"] else 1
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        LOGGER.error("digest_validation_unreadable error_type=%s", type(exc).__name__)
        print(
            json.dumps(
                {"valid": False, "errors": ["digest could not be read"], "warnings": []},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
