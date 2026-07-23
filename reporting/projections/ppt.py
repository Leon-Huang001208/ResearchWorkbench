"""Static PPTX template projection for report projects."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from core.observability import get_logger

logger = get_logger(__name__)

PPT_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
PPT_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

ET.register_namespace("p", PPT_NS)
ET.register_namespace("a", DRAWING_NS)


@dataclass(frozen=True)
class PPTTemplateProjectionResult:
    """Metadata returned after saving a PPTX template projection."""

    output_path: Path
    replaced_count: int = 0
    missing_placeholders: List[str] = field(default_factory=list)


def extract_pptx_placeholders(path: Path | str) -> List[str]:
    """Extract ``{{placeholder}}`` tokens from PPT slide XML in first-seen order."""
    pptx_path = Path(path)
    placeholders: List[str] = []
    seen: set[str] = set()
    try:
        with zipfile.ZipFile(pptx_path) as archive:
            for name in _ordered_slide_xml_names(archive.namelist()):
                root = ET.fromstring(archive.read(name))
                for paragraph in root.iter(f"{{{DRAWING_NS}}}p"):
                    text = _paragraph_text(paragraph)
                    for match in PPT_PLACEHOLDER_RE.finditer(text):
                        placeholder = match.group(1).strip()
                        if placeholder and placeholder not in seen:
                            placeholders.append(placeholder)
                            seen.add(placeholder)
        return placeholders
    except Exception as exc:
        logger.warning("Failed to extract pptx placeholders", path=str(pptx_path), error=str(exc))
        return []


class PPTTemplateProjection:
    """Render a static PPTX by replacing ``{{placeholder}}`` tokens in slide XML."""

    def save_from_template(
        self,
        *,
        output_path: Path | str,
        template_path: Path | str,
        placeholders: Dict[str, str] | None = None,
    ) -> PPTTemplateProjectionResult:
        """Copy ``template_path`` to ``output_path`` while replacing text placeholders."""
        template = Path(template_path)
        output = Path(output_path)
        if not template.exists():
            raise FileNotFoundError(f"PPT template not found: {template}")

        output.parent.mkdir(parents=True, exist_ok=True)
        placeholder_map = {
            str(key): "" if value is None else str(value)
            for key, value in (placeholders or {}).items()
        }
        configured_names = set(placeholder_map)
        found_names = set(extract_pptx_placeholders(template))
        replaced_count = 0

        try:
            with zipfile.ZipFile(template, "r") as source:
                with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
                    for item in source.infolist():
                        data = source.read(item.filename)
                        if item.filename.startswith("ppt/slides/") and item.filename.endswith(
                            ".xml"
                        ):
                            data, count = self._replace_placeholders(data, placeholder_map)
                            replaced_count += count
                        target.writestr(item, data)
        except Exception:
            logger.exception(
                "Failed to render PPT template",
                template_path=str(template),
                output_path=str(output),
            )
            raise

        missing = sorted(found_names - configured_names)
        logger.info(
            "Rendered PPT template",
            template_path=str(template),
            output_path=str(output),
            replaced_count=replaced_count,
            missing_placeholder_count=len(missing),
        )
        return PPTTemplateProjectionResult(
            output_path=output,
            replaced_count=replaced_count,
            missing_placeholders=missing,
        )

    @staticmethod
    def _replace_placeholders(source: bytes, placeholder_map: Dict[str, str]) -> tuple[bytes, int]:
        root = ET.fromstring(source)
        replaced = 0

        def replace_match(match: re.Match[str]) -> str:
            nonlocal replaced
            placeholder = match.group(1).strip()
            if placeholder not in placeholder_map:
                return match.group(0)
            replaced += 1
            return placeholder_map[placeholder]

        for paragraph in root.iter(f"{{{DRAWING_NS}}}p"):
            text_nodes = list(paragraph.iter(f"{{{DRAWING_NS}}}t"))
            if not text_nodes:
                continue
            original = "".join(node.text or "" for node in text_nodes)
            updated = PPT_PLACEHOLDER_RE.sub(replace_match, original)
            if updated == original:
                continue
            text_nodes[0].text = updated
            for node in text_nodes[1:]:
                node.text = ""

        return ET.tostring(root, encoding="utf-8", xml_declaration=True), replaced


def _paragraph_text(paragraph: ET.Element) -> str:
    """Return visible paragraph text by joining all DrawingML text runs."""
    return "".join(node.text or "" for node in paragraph.iter(f"{{{DRAWING_NS}}}t"))


def _ordered_slide_xml_names(names: List[str]) -> List[str]:
    """Return slide XML paths in user-facing slide order."""
    slide_names = [
        name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")
    ]
    return sorted(slide_names, key=_slide_sort_key)


def _slide_sort_key(name: str) -> tuple[int, str]:
    match = re.search(r"slide(\d+)\.xml$", name)
    if not match:
        return (10**9, name)
    return (int(match.group(1)), name)
