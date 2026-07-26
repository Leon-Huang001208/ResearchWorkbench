"""The single runtime contract for report project YAML configuration.

The contract keeps the established V1 report-generation semantics intact while
normalizing optional rich rendering settings under each placeholder's
``rendering`` field.  Legacy V2 configurations are deliberately rejected at
this boundary so callers must migrate them before a report run begins.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

logger = logging.getLogger(__name__)


class UnifiedReportConfigError(ValueError):
    """Raised when a report YAML mapping cannot be used as unified config."""


@dataclass(frozen=True)
class UnifiedRenderingConfig:
    """Optional rendering settings attached to one unified placeholder."""

    paragraph_style: str | None = None
    runs: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    visible_if: str | None = None
    chart_grid: Mapping[str, Any] | None = None
    extra: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    present: bool = False
    provided_fields: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "UnifiedRenderingConfig":
        """Parse rendering settings without discarding future rendering fields."""
        paragraph_style = _optional_string(raw.get("paragraph_style"), "rendering.paragraph_style")
        visible_if = _optional_string(raw.get("visible_if"), "rendering.visible_if")
        runs = _list_of_mappings(raw.get("runs", []), "rendering.runs")
        chart_grid = _optional_mapping(raw.get("chart_grid"), "rendering.chart_grid")
        known_fields = {"paragraph_style", "runs", "visible_if", "chart_grid"}
        return cls(
            paragraph_style=paragraph_style,
            runs=tuple(_freeze(run) for run in runs),
            visible_if=visible_if,
            chart_grid=_freeze(chart_grid) if chart_grid is not None else None,
            extra=_freeze({key: value for key, value in raw.items() if key not in known_fields}),
            present=True,
            provided_fields=frozenset(key for key in raw if key in known_fields),
        )

    @property
    def configured(self) -> bool:
        """Whether the source placeholder contained a rendering block."""
        return self.present

    def to_mapping(self) -> dict[str, Any]:
        """Return a lossless serializable rendering mapping."""
        result = _thaw(self.extra)
        if "paragraph_style" in self.provided_fields:
            result["paragraph_style"] = self.paragraph_style
        if "runs" in self.provided_fields:
            result["runs"] = [_thaw(run) for run in self.runs]
        if "visible_if" in self.provided_fields:
            result["visible_if"] = self.visible_if
        if "chart_grid" in self.provided_fields:
            result["chart_grid"] = _thaw(self.chart_grid)
        return result


@dataclass(frozen=True)
class UnifiedPlaceholderConfig:
    """A V1-compatible placeholder with normalized optional rendering fields."""

    key: str
    prompt_template: str | None
    retrieval: Mapping[str, Any]
    rendering: UnifiedRenderingConfig = field(default_factory=UnifiedRenderingConfig)
    rendering_is_null: bool = False
    fields: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_mapping(
        cls, key: str, raw: Mapping[str, Any]
    ) -> "UnifiedPlaceholderConfig":
        """Parse one placeholder and retain every established V1 field."""
        prompt_template = _optional_string(raw.get("prompt_template"), f"placeholders.{key}.prompt_template")
        retrieval = _optional_mapping(raw.get("retrieval"), f"placeholders.{key}.retrieval") or {}
        rendering_is_null = "rendering" in raw and raw["rendering"] is None
        rendering_raw = raw.get("rendering")
        rendering = (
            UnifiedRenderingConfig.from_mapping(
                _required_mapping(rendering_raw, f"placeholders.{key}.rendering")
            )
            if rendering_raw is not None
            else UnifiedRenderingConfig()
        )
        return cls(
            key=key,
            prompt_template=prompt_template,
            retrieval=_freeze(retrieval),
            rendering=rendering,
            rendering_is_null=rendering_is_null,
            fields=_freeze(dict(raw)),
        )

    def to_mapping(self) -> dict[str, Any]:
        """Return V1 fields plus the normalized optional rendering block."""
        result = _thaw(self.fields)
        if "prompt_template" in self.fields:
            result["prompt_template"] = self.prompt_template
        if "retrieval" in self.fields:
            result["retrieval"] = _thaw(self.retrieval)
        if self.rendering_is_null:
            result["rendering"] = None
        elif self.rendering.configured:
            result["rendering"] = self.rendering.to_mapping()
        else:
            result.pop("rendering", None)
        return result


@dataclass(frozen=True)
class UnifiedReportConfig:
    """The only configuration shape accepted by report runtime code."""

    name: str | None
    assets: Mapping[str, Any]
    defaults: Mapping[str, Any]
    components: Mapping[str, Any]
    retrieval: Mapping[str, Any]
    charts: Mapping[str, Any]
    tables: Mapping[str, Any]
    validators: Mapping[str, Any]
    placeholders: Mapping[str, UnifiedPlaceholderConfig]
    fields: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "UnifiedReportConfig":
        """Build a unified runtime model from a V1-shaped configuration mapping."""
        if {"meta", "template", "placeholders"}.issubset(raw):
            raise UnifiedReportConfigError("检测到旧 V2 配置，请先迁移为统一报告配置")

        source = deepcopy(dict(raw))
        placeholders_raw = _optional_mapping(source.get("placeholders"), "placeholders") or {}
        placeholders: dict[str, UnifiedPlaceholderConfig] = {}
        for key, value in placeholders_raw.items():
            if not isinstance(key, str) or not key.strip():
                raise UnifiedReportConfigError("placeholders 的名称必须为非空字符串")
            placeholders[key] = UnifiedPlaceholderConfig.from_mapping(
                key,
                _required_mapping(value, f"placeholders.{key}"),
            )

        return cls(
            name=_optional_string(source.get("name"), "name"),
            assets=_freeze(_optional_mapping(source.get("assets"), "assets") or {}),
            defaults=_freeze(_optional_mapping(source.get("defaults"), "defaults") or {}),
            components=_freeze(_optional_mapping(source.get("components"), "components") or {}),
            retrieval=_freeze(_optional_mapping(source.get("retrieval"), "retrieval") or {}),
            charts=_freeze(_optional_mapping(source.get("charts"), "charts") or {}),
            tables=_freeze(_optional_mapping(source.get("tables"), "tables") or {}),
            validators=_freeze(_optional_mapping(source.get("validators"), "validators") or {}),
            placeholders=MappingProxyType(dict(placeholders)),
            fields=_freeze(source),
        )

    def to_generation_dict(self) -> dict[str, Any]:
        """Serialize the normalized model for existing V1 generation services."""
        result = _thaw(self.fields)
        for field_name in (
            "name",
            "assets",
            "defaults",
            "components",
            "retrieval",
            "charts",
            "tables",
            "validators",
        ):
            if field_name in self.fields:
                result[field_name] = _thaw(getattr(self, field_name))
        result["placeholders"] = {
            key: placeholder.to_mapping() for key, placeholder in self.placeholders.items()
        }
        return result


def parse_unified_report_config(
    raw: Mapping[str, Any], *, source_path: str | Path | None = None
) -> UnifiedReportConfig:
    """Parse the sole runtime YAML model and log failures with their source path."""
    source = str(source_path) if source_path is not None else None
    try:
        if not isinstance(raw, Mapping):
            raise UnifiedReportConfigError("报告配置根节点必须是对象")
        return UnifiedReportConfig.from_mapping(raw)
    except UnifiedReportConfigError as exc:
        logger.error("Failed to parse unified report config source_path=%s error=%s", source, exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected unified report config parsing failure source_path=%s", source)
        raise UnifiedReportConfigError(f"报告配置解析失败：{exc}") from exc


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise UnifiedReportConfigError(f"{field_name} 必须为字符串")
    return value


def _required_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise UnifiedReportConfigError(f"{field_name} 必须是对象")
    return value


def _optional_mapping(value: Any, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    return deepcopy(dict(_required_mapping(value, field_name)))


def _list_of_mappings(value: Any, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise UnifiedReportConfigError(f"{field_name} 必须是列表")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        result.append(deepcopy(dict(_required_mapping(item, f"{field_name}[{index}]"))))
    return result


def _freeze(value: Any) -> Any:
    """Recursively detach and make parsed configuration containers read-only."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


def _thaw(value: Any) -> Any:
    """Return a fresh mutable mapping suitable for generation services."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return deepcopy(value)


__all__ = [
    "UnifiedPlaceholderConfig",
    "UnifiedRenderingConfig",
    "UnifiedReportConfig",
    "UnifiedReportConfigError",
    "parse_unified_report_config",
]
