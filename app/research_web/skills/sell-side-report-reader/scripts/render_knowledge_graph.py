"""Render a small, sourced knowledge graph as deterministic portable SVG."""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("research.skill.sell_side.graph")
MAX_NODES = 12
NODE_WIDTH = 184
NODE_HEIGHT = 64
GAP = 72
MARGIN = 48


def _source_locators(edge: dict[str, Any]) -> list[str]:
    citations = edge.get("citations")
    if not isinstance(citations, list) or not citations:
        raise ValueError("Every relationship needs a source locator")
    values: list[str] = []
    for citation in citations:
        locator = citation.get("locator") if isinstance(citation, dict) else None
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError("Every relationship needs a source locator")
        locator = locator.strip()
        if locator not in values:
            values.append(locator)
    return values


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", value) or "node"


def _build_svg(digest: dict[str, Any], title: str) -> str:
    framework = digest.get("knowledgeFramework")
    if not isinstance(framework, dict):
        raise TypeError("knowledgeFramework must be an object")
    nodes = framework.get("nodes")
    edges = framework.get("edges")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= MAX_NODES:
        raise ValueError(f"knowledgeFramework needs 2-{MAX_NODES} nodes")
    if not isinstance(edges, list) or not edges:
        raise ValueError("knowledgeFramework needs at least one reliable relationship")

    node_map: dict[str, dict[str, str]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise TypeError("Every node must be an object")
        node_id, label = node.get("id"), node.get("label")
        if (
            not isinstance(node_id, str)
            or not node_id.strip()
            or not isinstance(label, str)
            or not label.strip()
        ):
            raise ValueError("Every node needs a non-empty id and label")
        if node_id in node_map:
            raise ValueError("Node ids must be unique")
        node_map[node_id] = {"id": node_id, "label": label}

    locators: list[str] = []
    for edge in edges:
        if not isinstance(edge, dict):
            raise TypeError("Every relationship must be an object")
        source, target, relation = edge.get("from"), edge.get("to"), edge.get("relation")
        if source not in node_map or target not in node_map or source == target:
            raise ValueError("Every relationship needs two distinct declared nodes")
        if not isinstance(relation, str) or not relation.strip():
            raise ValueError("Every relationship needs a type")
        for locator in _source_locators(edge):
            if locator not in locators:
                locators.append(locator)

    width = MARGIN * 2 + len(nodes) * NODE_WIDTH + (len(nodes) - 1) * GAP
    height = 290 + max(0, len(edges) - 1) * 28
    positions = {
        str(node["id"]): (MARGIN + index * (NODE_WIDTH + GAP), 112)
        for index, node in enumerate(nodes)
    }
    graph_title = title.strip() or str(framework.get("scope") or "关键传导关系")
    graph_title = f"据研报重绘｜{graph_title}"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(graph_title)}</title>',
        '<desc id="desc">仅包含有来源定位的研报关系。</desc>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#496078"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{MARGIN}" y="44" font-family="sans-serif" font-size="23" font-weight="600" fill="#17212b">{html.escape(graph_title)}</text>',
    ]

    for index, edge in enumerate(edges):
        source_x, source_y = positions[str(edge["from"])]
        target_x, target_y = positions[str(edge["to"])]
        start_x = source_x + NODE_WIDTH
        end_x = target_x
        route_y = 215 + index * 28
        if end_x <= start_x:
            start_x = source_x + NODE_WIDTH / 2
            end_x = target_x + NODE_WIDTH / 2
        path = (
            f"M {start_x:.1f} {source_y + NODE_HEIGHT / 2:.1f} "
            f"C {(start_x + end_x) / 2:.1f} {route_y:.1f}, "
            f"{(start_x + end_x) / 2:.1f} {route_y:.1f}, "
            f"{end_x:.1f} {target_y + NODE_HEIGHT / 2:.1f}"
        )
        relation = html.escape(str(edge["relation"]))
        parts.append(
            f'<path d="{path}" fill="none" stroke="#496078" stroke-width="1.7" marker-end="url(#arrow)"/>'
        )
        parts.append(
            f'<text x="{(start_x + end_x) / 2:.1f}" y="{route_y - 7:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#496078">{relation}</text>'
        )

    for node in nodes:
        node_id = str(node["id"])
        x, y = positions[node_id]
        parts.extend(
            [
                f'<g id="node-{_safe_id(node_id)}">',
                f'<rect x="{x}" y="{y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="10" fill="#eef6ff" stroke="#2774ae"/>',
                f'<text x="{x + NODE_WIDTH / 2:.1f}" y="{y + NODE_HEIGHT / 2:.1f}" text-anchor="middle" dominant-baseline="middle" font-family="sans-serif" font-size="14" fill="#17212b">{html.escape(str(node["label"]))}</text>',
                "</g>",
            ]
        )
    source_line = "来源定位：" + "、".join(locators)
    parts.append(
        f'<text x="{MARGIN}" y="{height - 24}" font-family="sans-serif" font-size="12" fill="#496078">{html.escape(source_line)}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def build_svg(digest: dict[str, Any], title: str = "") -> str:
    """Build SVG or fail when the source does not support a reliable relation."""

    try:
        svg = _build_svg(digest, title)
        LOGGER.info("knowledge_graph_rendered")
        return svg
    except (KeyError, TypeError, ValueError) as exc:
        LOGGER.warning("knowledge_graph_rejected error_type=%s", type(exc).__name__)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an evidence-linked SVG")
    parser.add_argument("digest", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--title", default="")
    args = parser.parse_args()
    try:
        if args.out.suffix.lower() != ".svg":
            raise ValueError("output must use .svg")
        digest = json.loads(args.digest.read_text(encoding="utf-8"))
        if not isinstance(digest, dict):
            raise TypeError("digest must be an object")
        svg = build_svg(digest, args.title)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(svg, encoding="utf-8")
        print(json.dumps({"status": "completed", "output": str(args.out)}, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        LOGGER.error("knowledge_graph_failed error_type=%s", type(exc).__name__)
        print(json.dumps({"status": "failed", "error": "visual evidence unavailable"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
