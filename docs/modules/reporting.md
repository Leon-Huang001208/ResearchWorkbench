# Module: reporting

## Responsibility

`reporting` provides report composition, templates, markdown/Word projections, and research outputs.

The project-level report workflow lives under `reporting/projects/` and connects report project folders to evidence retrieval, model generation, chart rendering, DOCX projection, and run logs.

---

## Design Rules

- Reports should be reproducible
- Templates should be versioned
- Output formats should be consistent
- Keep generation logic testable
- Add or update tests when reporting logic changes

---

## Files

### `reporting/*.py`

Purpose:
- Report generator implementations
- Template management
- Markdown and Word output
- Report section composition

Update this section when:
- New report types are added
- Templates change
- Output format changes
- Report section composition changes

---

### `reporting/projects/project_manager.py`

Purpose:
- Load report project folders under `report_projects/`.
- Resolve `project.yaml` assets: active Word template, active Excel workbook, section config, optional prompt template Markdown, optional data sources, generated output directory, and run-log directory.
- Bootstrap the default `创业板50周报` project package.

Update this section when:
- `project.yaml` schema or project folder conventions change.
- Project asset validation changes.

---

### `reporting/projects/generation.py`

Purpose:
- Generate Word placeholder values from project config, Markdown prompt templates, database evidence, and `ModelGatewayImpl`.
- Support both current `section_config.yaml` `placeholders` schema and legacy `sections` schema.
- Parse `prompt_templates.md` by second-level heading; `检索 Query` is used to retrieve factual evidence, while `写作要求` constrains final writing.
- Retrieve lightweight evidence from `ingestion_queue_item` and `canonical_event` within the requested lookback window.
- Route model calls through the `reporting` task route when configured, otherwise through the default model route.
- Return generated placeholders plus per-section metadata: evidence count, model/provider, token usage, retrieval query, and warnings.

Update this section when:
- Evidence retrieval sources change.
- Prompt parsing, fallback content, warning, or model routing behavior changes.
- Placeholder config schema changes.

---

### `reporting/projects/chart_generation.py`

Purpose:
- Read Excel chart XML caches or worksheet cached cell values from project workbooks.
- Render configured charts with matplotlib in memory.
- Embed generated chart images directly into DOCX packages, either by replacing existing media targets or converting Word chart drawings into images.
- Emit chart metadata and warnings into the report run log.

Update this section when:
- `charts:` config schema changes.
- Chart types, fallback behavior, worksheet source handling, or DOCX replacement behavior changes.

---

### `report_projects/*/config/section_config.yaml`

Purpose:
- Project-owned YAML mapping from Word placeholders to prompt templates, static values, Excel cells/ranges, and chart replacement rules.
- Current `华安ETF周报` uses `placeholders:` plus embedded prompt retrieval queries and a `charts:` block for industry performance, gold, and crude-oil visuals.

Update this section when:
- A report project changes placeholder mapping or chart config semantics.
- Prompt query mode changes between embedded query and external JSON query sources.

---

### `report_projects/*/config/prompt_templates.md`

Purpose:
- Markdown prompt template library for project-level generation.
- Each `##` heading is a reusable prompt template name. The template body may include `检索 Query：...` and `写作要求：...`.

Update this section when:
- Prompt template naming, parsing rules, or writing constraints change.

---

## Required Tests

- Report generation tests
- Template rendering tests
- Output format verification
- API tests for source persistence, config-driven generation, run logs, chart metadata, and DOCX preview
- Chart-generation tests for Excel chart cache reading, worksheet source reading, and DOCX image embedding
- Frontend static tests for report template workbench behavior when UI surfaces change

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/reporting.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Recent Changes

- 2026-06-08: 报告项目生成链路升级为配置驱动：`section_config.yaml` 的 `placeholders` 绑定 Word 占位符，`prompt_templates.md` 的二级标题提供内置检索 Query 和写作规则；`/api/report-projects/{slug}/render` 默认检索 evidence、调用 ModelGateway 生成正文、嵌入 Excel/worksheet 生成图表、写入 runs JSON，并返回下载和预览 URL。
- 2026-06-04: 收敛 reporting composer/projection 的 mypy 历史债务，补齐模板缓存、fact card 列表、Excel worksheet/chart 数据的显式类型，输出格式保持不变。
