# Module: reporting

## Responsibility

`reporting` provides report composition, templates, markdown/Word/PPT projections, and research outputs.

The project-level report workflow lives under `reporting/projects/` and connects report project folders to evidence retrieval, model generation, Word/PPT projection, chart rendering, readiness plans, and run logs. A single render is orchestrated by `reporting/projects/run.py`; API routes delegate to that module instead of assembling artifacts and run logs inline.

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
- Static PPT template output
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
- Resolve `project.yaml` assets: project type (`word` or `ppt`), active Word/PPT template, active Excel workbook, section config, optional prompt template Markdown, optional data sources, generated output directory, and run-log directory.
- Bootstrap the default `创业板50周报` project package.

Update this section when:
- `project.yaml` schema or project folder conventions change.
- Project asset validation changes.

---

### `reporting/projections/ppt.py`

Purpose:
- Render static PPT projects without requiring `python-pptx`.
- Scan `.pptx` slide XML for `{{placeholder}}` tokens in first-seen slide order.
- Copy a PPT template package and replace configured text placeholders in slide XML.
- Return replacement metadata and missing placeholder warnings for run logs.

Update this section when:
- PPT placeholder syntax changes.
- PPT projection starts supporting image, chart, table, or slide insertion behavior.

---

### `reporting/projects/generation.py`

Purpose:
- Generate Word placeholder values from project config, Markdown prompt templates, database evidence, and `ModelGatewayImpl`.
- Support both current `section_config.yaml` `placeholders` schema and legacy `sections` schema.
- Parse `prompt_templates.md` by second-level heading; `检索 Query` is used to retrieve factual evidence, while `写作要求` constrains final writing.
- Merge report-level `defaults.validators` / `defaults.retrieval` into each text placeholder before generation, while allowing placeholder-specific overrides such as words, evidence count, and keywords.
- Render hard generation constraints from merged `section_config.yaml` settings (`target_words`, `max_words`, `min_news_count`, `validators`) into the final model message so prompt templates do not duplicate字数、禁用词、数据来源等硬参数.
- Retrieve lightweight evidence from `ingestion_queue_item` and `canonical_event` within the requested lookback window.
- Apply report-level retrieval controls from `defaults.retrieval`: keyword or hybrid mode, `top_k`, `candidate_k`, `source_types`, `min_keyword_score`, optional fusion weights, and optional LLM rerank. Placeholder-level `retrieval.keywords` remains the per-section topical keyword override. Legacy `retrieval.query_terms.must_any` / `exclude` is still parsed for compatibility, but the workbench no longer exposes it by default.
- Fill missing placeholder `retrieval.keywords` from `reporting/projects/keyword_profiles.json`, either by placeholder name or explicit `retrieval.keyword_profile`.
- In `mode: hybrid`, merge keyword candidates and recent semantic candidates with RRF, using local n-gram semantic similarity as the phase-2 fallback until pgvector/rerank is enabled.
- Optionally rerank retrieved evidence with the configured LLM (`retrieval.rerank.enabled: true`) before writing, preserving rerank score, rank, and reason in run logs.
- Route model calls through the `reporting` task route when configured, otherwise through the default model route.
- Generate independent configured sections with bounded parallelism while preserving placeholder and run-log order.
- Build `type: composite_market_review` placeholders by combining deterministic Excel-derived market data text with an evidence-grounded model-generated hotspot paragraph.
- Return generated placeholders plus per-section metadata: evidence count, keyword score, semantic score, fusion score/rank, LLM rerank score/rank/reason, matched terms, retrieval config, model/provider, token usage, retrieval query, and warnings.

Update this section when:
- Evidence retrieval sources change.
- Prompt parsing, fallback content, warning, or model routing behavior changes.
- Placeholder config schema changes.

---

### `reporting/projects/run.py`

Purpose:
- Own one report-project render run across Word and PPT outputs.
- Resolve the effective report period and lookback scope before generation.
- Call `ReportProjectGenerationService` for configured placeholder content or accept manual placeholders for static rendering.
- Project generated placeholders into Word/PPT templates, attach deterministic tables/charts for Word projects, write `runs/*.json`, and return artifact metadata plus aggregated warnings.
- Keep `/api/report-projects/{slug}/render` thin: the route reads project/config files, delegates to `ReportProjectRunService`, and maps the result into the existing response model.
- Desktop workbench generation uses `POST /api/report-projects/{slug}/render-jobs` and polls the returned `status_url`; `reporting/projects/jobs.py` owns the in-process queue, same-project deduplication, bounded history, and terminal error/result snapshots.
- The queue has one top-level worker to avoid competing report runs on local MPS resources. Section-level external model calls remain bounded-parallel, while local embedding/reranker model construction and inference are lock-protected.
- Running jobs are process-local and do not resume after an AlphaFoundry restart. Generated artifacts and run logs remain persisted in their project directories.

Update this section when:
- Run-log structure changes.
- Word/PPT render orchestration changes.
- Warning aggregation or artifact naming changes.

---

### `reporting/projects/plan.py`

Purpose:
- Compile report project `section_config.yaml` and `prompt_templates.md` into a pre-render readiness plan.
- Reuse generation helpers for default merging, composite `llm_writing` retrieval overrides, keyword profile expansion, prompt parsing, and retrieval config normalization.
- Mark each placeholder as deterministic or evidence-required, surface missing prompt templates / retrieval query issues, and expose the resolved report period and lookback scope.
- Provide a JSON-friendly `compiled_plan` shape consumed by the report workbench preflight UI before `/render` is called.

Update this section when:
- Placeholder readiness semantics change.
- API `compiled_plan` schema changes.
- Frontend generation preflight starts relying on additional backend plan fields.

---

### `reporting/projects/chart_generation.py`

Purpose:
- Read Excel chart XML caches or worksheet cached cell values from project workbooks.
- Render configured charts with matplotlib in memory.
- Embed generated chart images directly into DOCX packages, either by replacing existing media targets or converting Word chart drawings into images.
- For templates that already contain editable Word charts, sync Excel native chart XML into `word/charts/*.xml` and skip PNG embedding when `replace.kind: native_chart`.
- Emit chart metadata and warnings into the report run log.

Update this section when:
- `charts:` config schema changes.
- Chart types, fallback behavior, worksheet source handling, or DOCX replacement behavior changes.

---

### `reporting/projects/table_generation.py`

Purpose:
- Convert configured project Excel tables into Word `TableSpec` objects without model generation.
- Resolve table workbooks from the project `data/` directory.
- Read configured worksheet columns, apply simple filters such as `重要性=重要`, and preserve source row order.
- Emit table metadata and warnings into the report run log.

Update this section when:
- `tables:` config schema changes.
- Excel table filtering, date formatting, or Word table insertion behavior changes.

---

### `report_projects/*/config/section_config.yaml`

Purpose:
- Project-owned YAML mapping from Word/PPT placeholders to prompt templates, static values, Excel cells/ranges, retrieval controls, and chart replacement rules.
- Report-wide hard generation and retrieval defaults live under `defaults.validators` and `defaults.retrieval`. Text placeholders should only carry section-specific differences such as `target_words`, `max_words`, `min_news_count`, `retrieval.keyword_profile`, `retrieval.keywords`, and Excel/static sources.
- Current `华安ETF周报` uses `placeholders:` plus embedded prompt retrieval queries, `type: report_period` for `开始日期` / `结束日期`, `type: composite_market_review` for `A股市场回顾`, and a `charts:` block for industry performance, gold, and crude-oil visuals.
- `tables:` maps deterministic Word tables to refreshed project Excel files. `华安ETF周报` currently binds `下周全球投资日历` to `data/全球经济日历.xlsx` sheet `经济数据`, reading `日期`、`国家/地区`、`指标名称` rows where `重要性=重要`.
- Text placeholders can set `retrieval.keyword_profile` to reuse a curated keyword profile and `retrieval.keywords` to constrain evidence selection before model generation. `keywords` is presented as “检索关键词” in the workbench and keeps evidence on-topic; shared `top_k` / hybrid fusion / rerank settings are inherited from `defaults.retrieval`.
- The web template workbench presents this file by Word placeholder order: selecting a placeholder shows the matching config form, current YAML fragment, and linked prompt template so users can edit one placeholder at a time instead of scanning the full file. The placeholder form hides report-wide defaults and only exposes per-placeholder fields.

Update this section when:
- A report project changes placeholder mapping or chart config semantics.
- `project_type: ppt` static template conventions change.
- Prompt query mode changes between embedded query and external JSON query sources.
- Report-period semantics change, such as using a manually selected end date or a non-Monday start date.

---

### `report_projects/*/config/prompt_templates.md`

Purpose:
- Markdown prompt template library for project-level generation.
- Each `##` heading is a reusable prompt template name. The template body may include `检索 Query：...`, `写作要求：...`, or `写作格式：...`.
- Prompt templates describe retrieval intent and output structure. Hard constraints such as word limits, minimum evidence count, forbidden phrases, no-Wind/no-daily-data rules, and entity bans belong in `section_config.yaml`.

Update this section when:
- Prompt template naming, parsing rules, or writing constraints change.

---

## Required Tests

- Report generation tests
- Template rendering tests
- Output format verification
- API tests for source persistence, config-driven generation, run logs, chart metadata, and DOCX preview
- PPT template projection tests for placeholder scanning and static replacement
- Chart-generation tests for Excel chart cache reading, worksheet source reading, native Word chart syncing, and legacy DOCX image embedding
- Frontend static tests for report template workbench behavior when UI surfaces change
- Compiled report plan tests for placeholder readiness, prompt detection, and composite retrieval inheritance

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
- 2026-06-29: 报告项目新增 `project_type: ppt` 静态 PPT 模板项目；上传 `.pptx` 后扫描 `{{placeholder}}`，生成时复制模板并替换文本占位符，输出 `.pptx`、写入 run log，并保留旧 Word 项目默认兼容。
- 2026-06-08: 华安 ETF 周报模板图表从 PNG 占位切换为 Word 原生可编辑 chart：`scripts/replace_huaan_word_charts_office.py` 通过 Excel/Word 原生复制粘贴生成 chart parts，`scripts/merge_huaan_layout_with_native_charts.py` 将 chart parts 合并回原模板以保留页眉页脚和版式，`section_config.yaml` 使用 `replace.kind: native_chart`，生成时同步 Excel chart XML 而不再回写 PNG。
- 2026-06-09: `A股市场回顾` 切换为复合生成：指数涨跌和成交额由 `周报数据.xlsx` 确定性计算，市场热点部分继续走 evidence retrieval + DeepSeek/model route，减少手动改“涨/跌”和成交额表述；独立 section 生成改为 4 路有界并行，`WordProjection` 修复短占位符破坏长占位符的问题。
- 2026-06-09: 报告生成接入 Phase 1 关键词检索控制：section 配置可声明 `retrieval.must_any` / `exclude` / `top_k` 等参数，生成前对数据库 evidence 做过滤、评分和排序；run log 和前端预览新增 evidence 检索调试信息，方便定位某个占位符为什么没有内容或引用了错误材料。
- 2026-06-09: 报告生成接入 Phase 2 混合召回：`retrieval.mode: hybrid` 会在关键词候选外追加近期语义候选，使用本地 n-gram 语义相似度和 RRF 融合排序；run log / 前端 Evidence 调试显示 `semantic_score`、`retrieval_score`、`retrieval_rank` 和 `retrieval_method`。
- 2026-06-09: 报告生成接入 Phase 3 LLM rerank：`retrieval.rerank.enabled: true` 时，生成器会先取 `rerank.top_n` 条候选，再调用 reporting/default 模型路由输出 JSON 排序，最终 evidence 记录 `rerank_score`、`rerank_rank` 和 `rerank_reason`；华安 ETF 周报的 `A股市场回顾`、`航天`、`电力设备新能源` 已启用。
- 2026-06-10: 拆分 Prompt 模板与硬性生成参数：`section_config.yaml` 新增/使用 `target_words`、`min_news_count`、`validators`，生成器统一把这些参数渲染进最终模型消息；`prompt_templates.md` 去掉重复的“控制在 X 字”表述，只保留检索 Query 和写作格式。
- 2026-06-10: 新增 `keyword_profiles`：将旧财联社筛选 `params.json` 升级为项目内置关键词 profile，新模板占位符会按占位符名自动继承检索关键词；未知占位符生成可后续维护的关键词草稿。前端将机器字段 `query_terms.must_any` 收敛为业务字段 `keyword_profile` + `keywords`，不再默认展示“排除词”。
- 2026-06-10: 华安 ETF 周报配置收敛为报告级 defaults + 占位符差异项：`defaults.validators` / `defaults.retrieval` 统一承载禁用词、no-Wind/no-daily、hybrid、RRF、LLM rerank 等公共策略；每个占位符表单只维护类型、字数、关键词 Profile、检索关键词、报告周期或 Excel/static 来源。
- 2026-06-04: 收敛 reporting composer/projection 的 mypy 历史债务，补齐模板缓存、fact card 列表、Excel worksheet/chart 数据的显式类型，输出格式保持不变。
- 2026-07-07: 新增 `ReportProjectRunService`，将 `/api/report-projects/{slug}/render` 的 Word/PPT 生成编排、run-log 组装和 warning 聚合从 FastAPI route 收拢到 `reporting/projects/run.py`，保持外部响应不变。
- 2026-07-07: 新增 `CompiledReportPlan`，`GET /api/report-projects/{slug}` 返回 `compiled_plan`，前端生成预检优先使用后端计划判断 prompt / retrieval / deterministic 占位符就绪度。
- 2026-07-12: 报告工作台改为后台任务生成：提交接口立即返回 job ID，前端轮询短状态请求并显示真实阶段/段落进度；同项目活动任务自动去重，本地 embedding/reranker 加载和推理加锁，避免 WebView 长请求 `Load failed` 与 MPS 并发重复加载。
- 2026-07-12: 内置华安 ETF 周报所需 Word/Excel/历史预览资产纳入版本控制；报告配置及工作台默认的 embedding/reranker 使用 `BAAI/...` 模型标识，避免绑定开发机绝对路径。
