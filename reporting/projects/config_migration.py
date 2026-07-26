"""Explicit, safe migration from legacy report configuration formats.

This module is intentionally separate from report execution.  Runtime code only
consumes :mod:`reporting.projects.unified_config`; callers migrate a legacy V1
or true V2 file before handing it to that parser.
"""

from __future__ import annotations

import os
import tempfile
import logging
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

from reporting.projects.unified_config import UnifiedReportConfigError, parse_unified_report_config

logger = logging.getLogger(__name__)


class MigrationError(ValueError):
    """Raised when no legacy configuration can be safely migrated."""


@dataclass(frozen=True)
class LegacyReportConfig:
    """A discovered, explicitly classified legacy report configuration."""

    source_format: Literal["v1", "v2"]
    source_path: Path
    config: Mapping[str, Any]


@dataclass(frozen=True)
class MigrationResult:
    """The immutable result of one atomic configuration migration."""

    source_format: Literal["v1", "v2"]
    converted_placeholder_count: int
    warnings: tuple[str, ...]
    destination: Path


def discover_legacy_report_config(project_dir: str | Path) -> LegacyReportConfig | None:
    """Find a migratable source without relying on any runtime fallback.

    A true V2 ``report_config.yaml`` takes precedence.  A unified V1-shaped
    ``report_config.yaml`` is deliberately not considered a source: it is
    already the destination model.  ``section_config.yaml`` remains the V1
    source and is never changed by this module.
    """
    project_path = Path(project_dir)
    config_dir = project_path / "config"
    report_config = config_dir / "report_config.yaml"
    section_config = config_dir / "section_config.yaml"

    if report_config.exists():
        raw = _load_yaml_mapping(report_config)
        if _is_true_v2(raw):
            return LegacyReportConfig("v2", report_config, raw)

    if section_config.exists():
        raw = _load_yaml_mapping(section_config)
        return LegacyReportConfig("v2" if _is_true_v2(raw) else "v1", section_config, raw)

    logger.warning("No legacy report config discovered project_path=%s", project_path)
    return None


def migrate_project_config(project_dir: str | Path) -> MigrationResult:
    """Discover and migrate one project's legacy report configuration."""
    project_path = Path(project_dir)
    legacy_config = discover_legacy_report_config(project_path)
    if legacy_config is None:
        raise MigrationError(f"未找到可迁移的报告配置：{project_path}")
    return migrate_report_config(project_path, legacy_config)


def migrate_report_config(
    project_dir: str | Path,
    legacy_config: LegacyReportConfig | Mapping[str, Any],
) -> MigrationResult:
    """Validate, serialize and atomically install one unified report config.

    The destination is only replaced after the YAML in a same-directory
    temporary file has been parsed by the unified runtime parser.  Consequently
    an invalid source cannot create or overwrite ``config/report_config.yaml``.
    """
    project_path = Path(project_dir)
    destination = project_path / "config" / "report_config.yaml"
    try:
        source_format, raw_config, source_path = _coerce_legacy_config(legacy_config)
        if source_format == "v1":
            unified_config = deepcopy(dict(raw_config))
            converted_count = 0
            warnings: list[str] = []
        else:
            unified_config, converted_count, warnings = _convert_v2(raw_config, project_path)

        _validate_unified_mapping(unified_config, source_path or project_path)
        _atomic_write_validated_yaml(destination, unified_config)
        logger.info(
            "Migrated report configuration project_path=%s source_format=%s destination=%s "
            "converted_placeholder_count=%s",
            project_path,
            source_format,
            destination,
            converted_count,
        )
        return MigrationResult(
            source_format=source_format,
            converted_placeholder_count=converted_count,
            warnings=tuple(warnings),
            destination=destination,
        )
    except MigrationError as exc:
        logger.error(
            "Report configuration migration rejected project_path=%s destination=%s error=%s",
            project_path,
            destination,
            exc,
        )
        raise
    except (OSError, yaml.YAMLError, UnifiedReportConfigError, TypeError, ValueError) as exc:
        logger.exception(
            "Report configuration migration failed project_path=%s destination=%s error=%s",
            project_path,
            destination,
            exc,
        )
        raise MigrationError(f"报告配置迁移失败：{exc}") from exc


def _coerce_legacy_config(
    legacy_config: LegacyReportConfig | Mapping[str, Any],
) -> tuple[Literal["v1", "v2"], Mapping[str, Any], Path | None]:
    if isinstance(legacy_config, LegacyReportConfig):
        return legacy_config.source_format, legacy_config.config, legacy_config.source_path
    if not isinstance(legacy_config, Mapping):
        raise MigrationError("待迁移报告配置必须是对象")
    raw_config = deepcopy(dict(legacy_config))
    return ("v2" if _is_true_v2(raw_config) else "v1"), raw_config, None


def _convert_v2(
    raw_config: Mapping[str, Any], project_path: Path
) -> tuple[dict[str, Any], int, list[str]]:
    meta = _required_mapping(raw_config.get("meta"), "meta")
    template = _required_mapping(raw_config.get("template"), "template")
    placeholders = _required_mapping(raw_config.get("placeholders"), "placeholders")
    word_template = template.get("word_template")
    if not isinstance(word_template, str) or not word_template.strip():
        raise MigrationError("V2 template.word_template 必须是非空字符串")

    result: dict[str, Any] = {}
    name = meta.get("name")
    if name is not None:
        result["name"] = name
    metadata = {key: deepcopy(value) for key, value in meta.items() if key != "name"}
    reserved_top_level_fields = {
        "meta",
        "template",
        "placeholders",
        "defaults",
        "components",
        "retrieval",
        "charts",
        "tables",
        "validators",
    }
    top_level_extras = {
        key: deepcopy(value)
        for key, value in raw_config.items()
        if key not in reserved_top_level_fields
    }
    if top_level_extras:
        existing_extras = metadata.get("extras")
        metadata["extras"] = (
            {"meta": existing_extras, "top_level": top_level_extras}
            if existing_extras is not None
            else top_level_extras
        )
    if metadata:
        result["metadata"] = metadata
    for field_name in ("defaults", "components", "retrieval", "charts", "tables", "validators"):
        if field_name in raw_config:
            result[field_name] = deepcopy(raw_config[field_name])
    result["assets"] = deepcopy(dict(template))

    converted: dict[str, Any] = {}
    warnings: list[str] = []
    for key, raw_placeholder in placeholders.items():
        if not isinstance(key, str) or not key.strip():
            raise MigrationError("V2 placeholders 的名称必须是非空字符串")
        placeholder, placeholder_warnings = _convert_v2_placeholder(key, raw_placeholder)
        converted[key] = placeholder
        for warning in placeholder_warnings:
            warnings.append(warning)
            logger.warning(
                "Report config migration warning project_path=%s placeholder=%s warning=%s",
                project_path,
                key,
                warning,
            )
    result["placeholders"] = converted
    return result, len(converted), warnings


def _convert_v2_placeholder(key: str, raw_placeholder: Any) -> tuple[dict[str, Any], list[str]]:
    source = _required_mapping(raw_placeholder, f"placeholders.{key}")
    result = deepcopy(dict(source))
    warnings: list[str] = []

    generation = result.pop("generation_config", None)
    if generation is not None:
        generation_mapping = _required_mapping(generation, f"placeholders.{key}.generation_config")
        prompt_ref = generation_mapping.get("prompt_template_ref")
        prompt_inline = generation_mapping.get("prompt_template_inline")
        if prompt_inline is not None and not isinstance(prompt_inline, str):
            raise MigrationError(f"placeholders.{key}.generation_config.prompt_template_inline 必须是字符串")
        if isinstance(prompt_inline, str) and prompt_inline.strip():
            raise MigrationError(
                f"placeholders.{key}.generation_config.prompt_template_inline 包含未迁移的 Markdown 正文；"
                "请先将内容移至 prompt_templates.md，并改用 prompt_template_ref"
            )
        if prompt_ref is not None:
            result["prompt_template"] = prompt_ref
        for field_name in ("retrieval", "target_words", "max_words", "writing_structure", "output_mode"):
            if field_name in generation_mapping:
                result[field_name] = deepcopy(generation_mapping[field_name])

    rich_text_spec = result.pop("rich_text_spec", None)
    if rich_text_spec is not None:
        rich_text = _required_mapping(rich_text_spec, f"placeholders.{key}.rich_text_spec")
        rendering = result.get("rendering", {})
        rendering_mapping = _required_mapping(rendering, f"placeholders.{key}.rendering")
        merged_rendering = deepcopy(dict(rendering_mapping))
        for field_name, value in rich_text.items():
            merged_rendering[field_name] = deepcopy(value)
        result["rendering"] = merged_rendering

    if "visible_if" in result:
        rendering = result.get("rendering", {})
        rendering_mapping = _required_mapping(rendering, f"placeholders.{key}.rendering")
        merged_rendering = deepcopy(dict(rendering_mapping))
        merged_rendering["visible_if"] = result.pop("visible_if")
        result["rendering"] = merged_rendering

    return result, warnings


def _atomic_write_validated_yaml(destination: Path, config: Mapping[str, Any]) -> None:
    """Write a validated YAML file then replace destination atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            yaml.safe_dump(dict(config), temporary_file, allow_unicode=True, sort_keys=False)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        reloaded = _load_yaml_mapping(temporary_path)
        _validate_unified_mapping(reloaded, temporary_path)
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to remove migration temporary file temporary_path=%s", temporary_path)


def _validate_unified_mapping(config: Mapping[str, Any], source_path: Path) -> None:
    try:
        parse_unified_report_config(config, source_path=source_path)
    except UnifiedReportConfigError as exc:
        raise MigrationError(f"统一报告配置校验失败：{exc}") from exc


def _load_yaml_mapping(path: Path) -> Mapping[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.exception("Failed to read legacy report config path=%s error=%s", path, exc)
        raise MigrationError(f"无法读取报告配置：{path}") from exc
    if not isinstance(raw, Mapping):
        raise MigrationError(f"报告配置根节点必须是对象：{path}")
    return deepcopy(dict(raw))


def _required_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MigrationError(f"{field_name} 必须是对象")
    return value


def _is_true_v2(raw: Mapping[str, Any]) -> bool:
    return {"meta", "template", "placeholders"}.issubset(raw)


__all__ = [
    "LegacyReportConfig",
    "MigrationError",
    "MigrationResult",
    "discover_legacy_report_config",
    "migrate_project_config",
    "migrate_report_config",
]
