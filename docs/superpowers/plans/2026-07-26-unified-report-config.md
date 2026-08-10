# Unified Report Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace V1/V2 report YAML with a single `config/report_config.yaml` while retaining `config/prompt_templates.md` as the Prompt library.

**Architecture:** One normalized Python contract is the only runtime input. An explicit migration utility converts either legacy shape before a project switches. API, preflight, generation, renderer, and browser workbench use the normalized model; rich-text capabilities are optional `rendering` fields, not a second schema or renderer.

**Tech Stack:** Python 3.11, Pydantic, PyYAML, FastAPI, vanilla JavaScript, pytest.

---

## Baseline

The new worktree starts from `a942461`. Focused baseline has `135 passed, 1 failed`:

```bash
/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_projects_api.py tests/unit/test_report_template_workbench_frontend.py -q
```

The failure is `test_report_config_check_uses_collapsed_summary_and_on_demand_details`, expecting `template-project-check-summary`. Treat it as pre-existing until Task 5 restores the contract or replaces it with equal accessible behavior.

### Task 1: Define the one runtime contract

**Files:**
- Create: `reporting/projects/unified_config.py`
- Modify: `core/contracts/reporting.py`
- Create: `tests/unit/test_unified_report_config.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_unified_config_preserves_prompt_and_rendering():
    config = parse_unified_report_config({"name": "周报", "assets": {"prompt_templates": "prompt_templates.md"}, "placeholders": {"市场回顾": {"type": "paragraph", "prompt_template": "市场回顾", "retrieval": {"keywords": ["A股"]}, "rendering": {"paragraph_style": "正文"}}}})
    assert config.placeholders["市场回顾"].prompt_template == "市场回顾"
    assert config.placeholders["市场回顾"].rendering.paragraph_style == "正文"

def test_unified_config_rejects_unmigrated_v2_shape():
    with pytest.raises(UnifiedReportConfigError, match="迁移"):
        parse_unified_report_config({"meta": {}, "template": {}, "placeholders": {}})
```

- [ ] **Step 2: Verify failure**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_unified_report_config.py -q`

Expected: FAIL because `parse_unified_report_config` does not exist.

- [ ] **Step 3: Implement the contract**

```python
@dataclass(frozen=True)
class UnifiedRenderingConfig:
    paragraph_style: str | None = None
    runs: list[dict[str, Any]] = field(default_factory=list)
    visible_if: str | None = None
    chart_grid: dict[str, Any] | None = None

def parse_unified_report_config(raw: Mapping[str, Any]) -> UnifiedReportConfig:
    if "meta" in raw or "template" in raw:
        raise UnifiedReportConfigError("检测到旧 V2 配置，请先迁移")
    return UnifiedReportConfig.from_mapping(raw)
```

Preserve `defaults`, `components`, `retrieval`, `charts`, `tables`, validators and all existing semantic fields; normalize only optional `rendering`. Log config path and exception before raising `UnifiedReportConfigError`.

- [ ] **Step 4: Verify pass and commit**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_unified_report_config.py -q`

Expected: PASS.

Commit: `git add core/contracts/reporting.py reporting/projects/unified_config.py tests/unit/test_unified_report_config.py && git commit -m "feat: add unified report config contract"`

### Task 2: Convert legacy versions through an explicit, atomic migration

**Files:**
- Create: `reporting/projects/config_migration.py`
- Modify: `reporting/projects/project_manager.py`
- Modify: `tests/unit/test_unified_report_config.py`

- [ ] **Step 1: Write the failing migration tests**

```python
def test_migrate_v1_keeps_defaults_and_components(tmp_path):
    result = migrate_report_config(project_dir=tmp_path, legacy_config={"defaults": {"retrieval": {"top_k": 10}}, "placeholders": {"市场回顾": {"type": "composite_market_review", "components": [{"type": "llm_writing"}]}}})
    assert result.config["defaults"]["retrieval"]["top_k"] == 10
    assert result.config["placeholders"]["市场回顾"]["components"][0]["type"] == "llm_writing"

def test_migrate_v2_moves_prompt_and_runs_to_unified_fields(tmp_path):
    result = migrate_report_config(project_dir=tmp_path, legacy_config={"meta": {"name": "周报"}, "template": {}, "placeholders": {"正文": {"type": "rich_text", "generation_config": {"prompt_template_ref": "正文 Prompt"}, "rich_text_spec": {"runs": [{"text": ""}]}}}})
    assert result.config["placeholders"]["正文"]["prompt_template"] == "正文 Prompt"
    assert result.config["placeholders"]["正文"]["rendering"]["runs"] == [{"text": ""}]

def test_failed_migration_does_not_replace_file(tmp_path):
    with pytest.raises(UnifiedReportConfigError):
        migrate_project_config(tmp_path)
    assert not (tmp_path / "config/report_config.yaml").exists()
```

- [ ] **Step 2: Verify failure**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_unified_report_config.py -q`

Expected: FAIL because migration functions do not exist.

- [ ] **Step 3: Implement migration with staged replace**

```python
def migrate_project_config(project_dir: Path) -> MigrationResult:
    source = discover_legacy_report_config(project_dir)
    result = migrate_report_config(project_dir=project_dir, legacy_config=source.data)
    parse_unified_report_config(result.config)
    staged = project_dir / "config/.report_config.yaml.tmp"
    staged.write_text(yaml.safe_dump(result.config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    staged.replace(project_dir / "config/report_config.yaml")
    return result
```

Return source format, converted placeholder count, warnings and destination; log every warning with project and placeholder. Do not delete the old YAML in this task.

- [ ] **Step 4: Verify pass and commit**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_unified_report_config.py -q`

Expected: PASS.

Commit: `git add reporting/projects/config_migration.py reporting/projects/project_manager.py tests/unit/test_unified_report_config.py && git commit -m "feat: migrate report config versions to unified model"`

### Task 3: Make preflight, generation and rendering use one model

**Files:**
- Modify: `reporting/projects/plan.py`
- Modify: `reporting/projects/run.py`
- Modify: `reporting/projects/generation.py`
- Modify: `reporting/rendering/template_renderer.py`
- Create: `tests/unit/test_unified_report_generation.py`

- [ ] **Step 1: Write the failing integration tests**

```python
def test_compiled_plan_uses_unified_config_and_prompt_markdown():
    plan = compile_report_plan_from_unified_config(UNIFIED_CONFIG, "## 市场回顾\n检索 Query：A股\n写作要求：审慎")
    assert plan.ready is True
    assert plan.placeholders[0].prompt_template == "市场回顾"

def test_word_run_has_one_render_dispatch(tmp_path, caplog):
    result = run_unified_project(tmp_path, UNIFIED_CONFIG, PROMPT_MARKDOWN)
    assert result.generated_placeholder_count == 1
    assert "fallback to v1" not in caplog.text.lower()
    assert "v2 renderer" not in caplog.text.lower()
```

- [ ] **Step 2: Verify failure**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_unified_report_generation.py -q`

Expected: FAIL because unified plan/run entry points do not exist.

- [ ] **Step 3: Implement the single runtime entry point**

```python
def compile_report_plan_from_unified_config(config: UnifiedReportConfig, prompt_templates_source: str, **scope_overrides: str | int | None) -> CompiledReportPlan:
    return compile_report_plan(config.to_generation_dict(), prompt_templates_source, **scope_overrides)
```

`ReportProjectRunService` loads only normalized `report_config.yaml`. Keep existing retrieval, tables, charts and projection services; dispatch optional `rendering` fields inside that one flow. Remove `meta/template` detection, `_execute_word_v2`, and fallback logs.

- [ ] **Step 4: Verify pass and commit**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_unified_report_generation.py tests/unit/test_report_projects_api.py -q`

Expected: PASS.

Commit: `git add reporting/projects/plan.py reporting/projects/run.py reporting/projects/generation.py reporting/rendering/template_renderer.py tests/unit/test_unified_report_generation.py && git commit -m "refactor: run reports through unified config"`

### Task 4: Keep one YAML file in each project and one API source

**Files:**
- Modify: `reporting/projects/project_manager.py`
- Modify: `app/api/routes/report_projects.py`
- Modify: `tests/unit/test_report_projects_api.py`
- Modify: `report_projects/华安ETF周报/project.yaml`
- Modify: `report_projects/华安ETF周报/config/report_config.yaml`
- Delete: `report_projects/华安ETF周报/config/section_config.yaml`

- [ ] **Step 1: Write failing API tests**

```python
def test_project_api_returns_one_yaml_and_prompt_markdown(client):
    data = client.get("/api/report-projects/华安ETF周报").json()
    assert data["report_config_filename"] == "report_config.yaml"
    assert "section_config" not in data
    assert data["prompt_templates_filename"] == "prompt_templates.md"

def test_save_only_writes_report_config(client, project_root):
    response = client.put("/api/report-projects/华安ETF周报/source", json={"source_kind": "report_config", "content": "name: 华安ETF周报\nplaceholders: {}\n"})
    assert response.status_code == 200
    assert (project_root / "华安ETF周报/config/report_config.yaml").exists()
    assert not (project_root / "华安ETF周报/config/section_config.yaml").exists()
```

- [ ] **Step 2: Verify failure**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_projects_api.py -q`

Expected: FAIL because API still exposes and writes `section_config`.

- [ ] **Step 3: Implement one source**

Add `report_config_path` to `ReportProject`. Upload bootstrap creates `config/report_config.yaml`; `project.yaml` points to it; source endpoint accepts `report_config` and `prompt_templates` only and validates YAML before replacing it. Migrate the checked-in 华安 ETF project, compile its plan and render it under test, then remove `section_config.yaml` after validation passes.

- [ ] **Step 4: Verify pass and commit**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_projects_api.py tests/unit/test_unified_report_generation.py -q`

Expected: PASS.

Commit: `git add app/api/routes/report_projects.py reporting/projects/project_manager.py tests/unit/test_report_projects_api.py tests/unit/test_unified_report_generation.py report_projects/华安ETF周报/project.yaml report_projects/华安ETF周报/config/report_config.yaml && git rm report_projects/华安ETF周报/config/section_config.yaml && git commit -m "feat: expose one report yaml configuration"`

### Task 5: Remove dual-version workbench state and complete verification

**Files:**
- Modify: `app/web/templates/index.html`
- Modify: `app/web/static/js/templates.js`
- Modify: `app/web/static/style.css`
- Modify: `tests/unit/test_report_template_workbench_frontend.py`
- Modify: `docs/modules/app_api.md`
- Modify: `docs/modules/reporting.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Write failing frontend contract**

```python
def test_workbench_uses_one_report_config_state():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "activeSourceKind" not in source
    assert "v2PlaceholderConfigDrafts" not in source
    assert "v2PlaceholderConfigToMapping" not in source
    assert 'data-template-source-kind="report_config"' in html
    assert 'data-template-source-kind="section_config"' not in html
```

- [ ] **Step 2: Verify failure**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_report_template_workbench_frontend.py -q`

Expected: FAIL because V1/V2 state and source switching remain.

- [ ] **Step 3: Implement one browser state**

Remove section-config switching, V2 drafts, converters and version labels. Use one per-placeholder report-config draft for source preview, summary, readiness, save and preflight. Preserve the existing “需要处理 / 已完成” navigation and preflight handoff. Restore the `template-project-check-summary` contract or an equally accessible summary.

- [ ] **Step 4: Verify targeted suite**

Run: `/Users/leon/opt/anaconda3/bin/python3 -m pytest tests/unit/test_unified_report_config.py tests/unit/test_unified_report_generation.py tests/unit/test_report_project_manager.py tests/unit/test_report_projects_api.py tests/unit/test_report_template_workbench_frontend.py -q`

Expected: all tests PASS.

- [ ] **Step 5: Check syntax, update docs and commit**

Run: `/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check app/web/static/js/templates.js && git diff --check`

Expected: both commands succeed.

Document exactly two config sources—`report_config.yaml` and `prompt_templates.md`—and remove V1/V2 runtime language.

Commit: `git add app/web/templates/index.html app/web/static/js/templates.js app/web/static/style.css tests/unit/test_report_template_workbench_frontend.py docs/modules/app_api.md docs/modules/reporting.md docs/ARCHITECTURE.md && git commit -m "refactor: remove report config version compatibility"`

## Plan self-review

- Tasks 1–2 define and migrate the normalized model; Task 3 unifies runtime behavior; Task 4 leaves one YAML in each project; Task 5 removes version UI and verifies the completed path.
- Every named function is introduced before later tasks use it. The plan contains no deferred implementation markers.
