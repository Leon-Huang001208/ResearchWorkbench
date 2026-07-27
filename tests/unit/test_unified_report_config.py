"""Tests for the unified report configuration runtime contract."""

import logging
from pathlib import Path

import pytest
import yaml

from reporting.projects.config_migration import (
    MigrationError,
    discover_legacy_report_config,
    migrate_project_config,
    migrate_report_config,
)
from reporting.projects.unified_config import (
    UnifiedReportConfigError,
    parse_unified_report_config,
)


def test_unified_config_preserves_v1_semantics_and_optional_rendering():
    """The unified V1-shaped config retains generation and rendering semantics."""
    raw = {
        "name": "周报",
        "meta": {"project_note": "V1 extension, not a V2 template"},
        "assets": {"prompt_templates": "prompt_templates.md"},
        "defaults": {"retrieval": {"top_k": 10}},
        "validators": {"forbidden_terms": ["保本"]},
        "components": {"disclaimer": {"type": "static"}},
        "retrieval": {"mode": "hybrid"},
        "charts": {"市场走势": {"type": "line"}},
        "tables": {"重要日程": {"columns": ["日期"]}},
        "placeholders": {
            "市场回顾": {
                "type": "paragraph",
                "prompt_template": "市场回顾",
                "retrieval": {"keywords": ["A股"]},
                "rendering": {
                    "paragraph_style": "正文",
                    "runs": [{"text": "市场：", "bold": True}],
                    "visible_if": "{{ include_market_review }}",
                    "chart_grid": {"rows": 2, "cols": 2},
                },
            }
        },
    }
    config = parse_unified_report_config(raw)

    placeholder = config.placeholders["市场回顾"]
    assert placeholder.prompt_template == "市场回顾"
    assert placeholder.retrieval == {"keywords": ("A股",)}
    assert placeholder.rendering.paragraph_style == "正文"
    assert tuple(placeholder.rendering.runs) == ({"text": "市场：", "bold": True},)
    assert placeholder.rendering.visible_if == "{{ include_market_review }}"
    assert placeholder.rendering.chart_grid == {"rows": 2, "cols": 2}
    assert config.defaults == {"retrieval": {"top_k": 10}}
    assert config.validators == {"forbidden_terms": ("保本",)}
    assert config.components == {"disclaimer": {"type": "static"}}
    assert config.charts == {"市场走势": {"type": "line"}}
    assert config.tables == {"重要日程": {"columns": ("日期",)}}

    serialized = config.to_generation_dict()
    assert serialized["defaults"] == raw["defaults"]
    assert serialized["validators"] == raw["validators"]
    assert serialized["components"] == raw["components"]
    assert serialized["retrieval"] == raw["retrieval"]
    assert serialized["charts"] == raw["charts"]
    assert serialized["tables"] == raw["tables"]
    assert serialized["placeholders"]["市场回顾"] == raw["placeholders"]["市场回顾"]
    assert "## 市场回顾" not in str(serialized)


def test_unified_config_isolates_input_and_serialized_output():
    """Parsed config is immutable and detached from both input and returned mappings."""
    raw = {
        "defaults": {"retrieval": {"top_k": 10}},
        "placeholders": {"市场回顾": {"retrieval": {"keywords": ["A股"]}}},
    }
    config = parse_unified_report_config(raw)

    raw["defaults"]["retrieval"]["top_k"] = 99
    raw["placeholders"]["市场回顾"]["retrieval"]["keywords"].append("港股")
    first_output = config.to_generation_dict()
    first_output["defaults"]["retrieval"]["top_k"] = 88
    first_output["placeholders"]["市场回顾"]["retrieval"]["keywords"].append("美股")

    assert config.defaults["retrieval"]["top_k"] == 10
    assert config.placeholders["市场回顾"].retrieval["keywords"] == ("A股",)
    assert config.to_generation_dict() == {
        "defaults": {"retrieval": {"top_k": 10}},
        "placeholders": {"市场回顾": {"retrieval": {"keywords": ["A股"]}}},
    }
    with pytest.raises(TypeError):
        config.defaults["retrieval"]["top_k"] = 1


@pytest.mark.parametrize("rendering", [{}, {"paragraph_style": None}, None])
def test_unified_config_preserves_explicit_empty_rendering_blocks(rendering):
    """Present rendering blocks are retained even when all optional values are empty."""
    config = parse_unified_report_config(
        {"placeholders": {"正文": {"type": "paragraph", "rendering": rendering}}}
    )

    assert config.to_generation_dict()["placeholders"]["正文"]["rendering"] == rendering


def test_unified_config_logs_source_path_for_invalid_raw(caplog):
    """Parse errors include the supplied YAML source path in project logs."""
    source_path = "/tmp/broken-report-config.yaml"
    caplog.set_level(logging.ERROR, logger="reporting.projects.unified_config")

    with pytest.raises(UnifiedReportConfigError, match="根节点"):
        parse_unified_report_config([], source_path=source_path)

    assert source_path in caplog.text


@pytest.mark.parametrize(
    "legacy_root",
    [
        {"meta": {}, "template": {}},
        {"meta": {}, "template": {}, "placeholders": {}},
    ],
)
def test_unified_config_rejects_unmigrated_v2_root_shape(legacy_root):
    """The runtime rejects V2 roots even when their placeholders field is absent."""
    with pytest.raises(UnifiedReportConfigError, match="迁移"):
        parse_unified_report_config(legacy_root)


@pytest.mark.parametrize(
    "legacy_field",
    [
        "generation_config",
        "rich_text_spec",
        "generation_mode",
        "visible_if",
        "prompt_template_inline",
    ],
)
def test_unified_config_rejects_v2_only_placeholder_fields(legacy_field):
    """V2-only generation and rendering fields cannot round-trip through runtime config."""
    with pytest.raises(UnifiedReportConfigError, match=legacy_field):
        parse_unified_report_config(
            {
                "placeholders": {
                    "正文": {legacy_field: {} if legacy_field.endswith("config") else "legacy-value"}
                }
            }
        )


def test_unified_config_requires_placeholder_mapping_instead_of_legacy_sections():
    """The runtime model accepts only the unified placeholders collection."""
    with pytest.raises(UnifiedReportConfigError, match="placeholders"):
        parse_unified_report_config({"sections": []})


def test_migration_copies_v1_config_without_changing_generation_settings(tmp_path):
    """V1 defaults, retrieval and components stay byte-for-byte equivalent semantically."""
    project_dir = tmp_path / "weekly"
    source_path = project_dir / "config" / "section_config.yaml"
    source_path.parent.mkdir(parents=True)
    v1_config = {
        "assets": {"prompt_templates": "prompts.md"},
        "defaults": {"retrieval": {"top_k": 8}},
        "components": {"footer": {"type": "static", "text": "免责声明"}},
        "placeholders": {
            "市场回顾": {
                "prompt_template": "market_review",
                "retrieval": {"keywords": ["A股"], "top_k": 5},
            }
        },
    }
    source_path.write_text(yaml.safe_dump(v1_config, allow_unicode=True), encoding="utf-8")

    result = migrate_project_config(project_dir)
    migrated = yaml.safe_load(result.destination.read_text(encoding="utf-8"))

    assert result.source_format == "v1"
    assert result.converted_placeholder_count == 0
    assert migrated["defaults"] == v1_config["defaults"]
    assert migrated["components"] == v1_config["components"]
    assert (
        migrated["placeholders"]["市场回顾"]["retrieval"]
        == v1_config["placeholders"]["市场回顾"]["retrieval"]
    )
    assert source_path.exists()
    assert parse_unified_report_config(migrated).to_generation_dict() == migrated


def test_migration_converts_true_v2_placeholders_and_template_reference(tmp_path):
    """A true V2 report_config becomes the unified model without losing metadata."""
    project_dir = tmp_path / "weekly"
    source_path = project_dir / "config" / "report_config.yaml"
    source_path.parent.mkdir(parents=True)
    v2_config = {
        "meta": {
            "name": "周报",
            "version": "2.0",
            "description": "保留的迁移元数据",
            "report_type": "word",
            "custom": {"owner": "research"},
            "extras": {"source": "v2 meta"},
        },
        "template": {"word_template": "templates/weekly.docx", "prompt_templates": "prompts.md"},
        "defaults": {"retrieval": {"top_k": 8}},
        "custom_top_level": {"retention": "metadata extras"},
        "placeholders": {
            "市场回顾": {
                "title": "市场回顾",
                "type": "rich_text",
                "generation_config": {
                    "prompt_template_ref": "market_review",
                    "retrieval": {"keywords": ["A股"], "top_k": 5},
                },
                "rich_text_spec": {
                    "runs": [{"text": "市场：", "bold": True}, {"is_dynamic": True}],
                    "default_font": "微软雅黑",
                },
                "visible_if": "{{ include_market_review }}",
            }
        },
    }
    source_path.write_text(yaml.safe_dump(v2_config, allow_unicode=True), encoding="utf-8")
    discovered = discover_legacy_report_config(project_dir)
    assert discovered is not None
    result = migrate_report_config(project_dir, discovered)
    migrated = yaml.safe_load(result.destination.read_text(encoding="utf-8"))

    placeholder = migrated["placeholders"]["市场回顾"]
    assert result.source_format == "v2"
    assert result.converted_placeholder_count == 1
    assert migrated["name"] == "周报"
    assert migrated["metadata"] == {
        "version": "2.0",
        "description": "保留的迁移元数据",
        "report_type": "word",
        "custom": {"owner": "research"},
        "extras": {
            "meta": {"source": "v2 meta"},
            "top_level": {"custom_top_level": {"retention": "metadata extras"}},
        },
    }
    assert migrated["assets"]["word_template"] == "templates/weekly.docx"
    assert placeholder["prompt_template"] == "market_review"
    assert placeholder["retrieval"] == {"keywords": ["A股"], "top_k": 5}
    assert (
        placeholder["rendering"]["runs"]
        == v2_config["placeholders"]["市场回顾"]["rich_text_spec"]["runs"]
    )
    assert placeholder["rendering"]["visible_if"] == "{{ include_market_review }}"
    assert source_path.exists()
    parsed = parse_unified_report_config(migrated)
    assert parsed.metadata == migrated["metadata"]
    assert parsed.to_generation_dict() == migrated


def test_migration_rejects_nonempty_v2_inline_prompt_without_replacing_destination(tmp_path):
    """Inline Markdown prompt bodies require an explicit external prompt template migration."""
    project_dir = tmp_path / "weekly"
    config_dir = project_dir / "config"
    config_dir.mkdir(parents=True)
    destination = config_dir / "report_config.yaml"
    destination.write_text("sentinel: preserve\n", encoding="utf-8")
    v2_config = {
        "meta": {"name": "周报"},
        "template": {"word_template": "templates/weekly.docx"},
        "placeholders": {
            "市场回顾": {"generation_config": {"prompt_template_inline": "这是 Markdown Prompt 正文"}}
        },
    }

    with pytest.raises(MigrationError, match="prompt_template_inline.*prompt_templates.md"):
        migrate_report_config(project_dir, v2_config)

    assert destination.read_text(encoding="utf-8") == "sentinel: preserve\n"


@pytest.mark.parametrize(
    "source",
    [
        None,
        {"meta": {}, "template": {}, "placeholders": {"坏配置": {"generation_config": []}}},
        {"placeholders": {"坏配置": {"retrieval": []}}},
    ],
)
def test_migration_never_creates_or_replaces_destination_when_source_is_invalid(tmp_path, source):
    """Discovery and conversion failures leave report_config.yaml untouched."""
    project_dir = tmp_path / "weekly"
    config_dir = project_dir / "config"
    config_dir.mkdir(parents=True)
    destination = config_dir / "report_config.yaml"
    destination.write_text("sentinel: preserve\n", encoding="utf-8")

    if source is None:
        with pytest.raises(MigrationError, match="未找到"):
            migrate_project_config(project_dir)
    else:
        with pytest.raises(MigrationError):
            migrate_report_config(project_dir, source)

    assert destination.read_text(encoding="utf-8") == "sentinel: preserve\n"
    assert not (config_dir / "section_config.yaml").exists()


def test_migration_validates_a_temporary_file_before_atomic_replace(tmp_path, monkeypatch):
    """The existing destination remains intact until a parseable temporary file is replaced."""
    import reporting.projects.config_migration as migration

    project_dir = tmp_path / "weekly"
    config_dir = project_dir / "config"
    config_dir.mkdir(parents=True)
    destination = config_dir / "report_config.yaml"
    destination.write_text("sentinel: preserve\n", encoding="utf-8")
    source = {"placeholders": {"正文": {"prompt_template": "body"}}}
    observed: dict[str, Path] = {}
    original_replace = migration.os.replace

    def assert_before_replace(temp_path, target_path):
        observed["temporary"] = Path(temp_path)
        assert Path(target_path) == destination
        assert destination.read_text(encoding="utf-8") == "sentinel: preserve\n"
        parse_unified_report_config(yaml.safe_load(Path(temp_path).read_text(encoding="utf-8")))
        original_replace(temp_path, target_path)

    monkeypatch.setattr(migration.os, "replace", assert_before_replace)

    result = migrate_report_config(project_dir, source)

    assert result.destination == destination
    assert "temporary" in observed
    assert not observed["temporary"].exists()
    assert destination != project_dir / "config" / "section_config.yaml"


def test_migration_removes_temporary_file_when_atomic_replace_fails(tmp_path, monkeypatch):
    """A failed replacement leaves neither a temporary file nor a changed destination."""
    import reporting.projects.config_migration as migration

    project_dir = tmp_path / "weekly"
    config_dir = project_dir / "config"
    config_dir.mkdir(parents=True)
    destination = config_dir / "report_config.yaml"
    destination.write_text("sentinel: preserve\n", encoding="utf-8")
    monkeypatch.setattr(
        migration.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed"))
    )

    with pytest.raises(MigrationError, match="replace failed"):
        migrate_report_config(project_dir, {"placeholders": {"正文": {"prompt_template": "body"}}})

    assert destination.read_text(encoding="utf-8") == "sentinel: preserve\n"
    assert not list(config_dir.glob(".report_config.yaml.*.tmp"))
