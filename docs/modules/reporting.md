# Module: reporting

## Responsibility

`reporting` provides report composition, templates, markdown/Word/PPT projections, and research outputs.

The project-level report workflow lives under `reporting/projects/` and connects report project folders to evidence retrieval, model generation, Word/PPT projection, chart rendering, readiness plans, and run logs. A single render is orchestrated by `reporting/projects/run.py`; API routes delegate to that module instead of assembling artifacts and run logs inline.

## Rendering compatibility

The reporting rendering and builder modules are formatted to the repository Black baseline and type-checked by mypy. PPT renderer typing is constrained at `python-pptx` boundaries while preserving fallback rendering when native chart construction cannot use a supplied dataset.

---

## Design Rules

- Reports should be reproducible
- Templates should be versioned
- Output formats should be consistent
- Keep generation logic testable
- Add or update tests when reporting logic changes

---

## Files

### `reporting/compiler/`

Purpose:

- Outline-first + evidence-first 报告编译器，把报告生成从"单次长文生成"重构为多阶段流水线（参考 STORM/RAPID/FoRAG/CRAG/LongCite）。
- 流水线：任务分解 → 来源规划 → 证据检索 → 事实抽取与归一化 → 大纲规划 → 分节写作 → 引用绑定 → 批判 → 渲染。
- 所有进入正文/表格/图表的数字与结论，必须先落到 `FactRecord`（带 `Provenance`），实现句级引用可验证。

关键模块：

- `compiler.py` — `ReportCompiler.compile(task)` 串联 10 步流水线（含 revision 循环），编译器版本 VERSION="2.0"。`_critic_revision_loop` 在 critic 与 revision_pass 之间循环最多 2 轮，PASS/MINOR 收敛后 break，输出 `CompiledReport`。
- `task_decomposer.py` — `ReportTask → ResearchPlan`（research questions、证据需求表、检索预算），用 `structured_output`。
- `source_planner.py` — `ResearchPlan → SourcePlan`，从 `core/source_registry` 读 SourceSpec，按 tier + retrieval_weight 排序，构建 `RetrievalQuery`。
- `evidence_retriever.py` — 统一检索入口，`EvidenceRetrieverProtocol` 使 RAGRetrievalService / DatabaseEvidenceRetriever 可互换；`PassthroughEvidenceRetriever` 消费预检索证据供测试与早期集成。
- `fact_extractor.py` — `EvidencePackage → list[FactRecord]`，每个 fact 绑 `Provenance`（含 `source_tier`），无 LLM 时规则抽取兜底，按 `(claim_text, value, unit, doc_id)` 去重。
- `outline_planner.py` — `list[FactRecord] + ReportTask → ReportOutline`，每节明确 `must_answer` / `required_claim_types` / `counterpoints`，outline 优先于 prose。
- `section_writer.py` — `Outline + Facts → list[CompiledSection]`，用 `chat()` 生成正文，要求 writer 用 `[fact_id]` 标记引用位置。
- `citation_binder.py` — 解析正文 `[fact_id]` → `[N]` + `Citation` 对象（LongCite 式句级引用），检测 orphan citation 与 unsupported claim。
- `critic.py` — 第三阶段完整批判器：六类检查（CLAIM_SUPPORT/CONFLICT/COUNTERPOINT/STRUCTURE/EVIDENCE_SUFFICIENCY/FORBIDDEN_TERM），逐数字支撑验证（值容差±5%）、数字矛盾检测（偏差>20%）、反证覆盖、结构连贯性、证据充分度。输出 `CritiqueReport`（含 `CritiqueIssue` 列表、`overall_severity`、`metrics`），驱动 `RevisionPass` 自动修复。同时保持向后兼容的 `review()` 接口。
- `revision_pass.py` — 按 `CritiqueReport` 自动修复：CONFLICT→替换矛盾数字、CLAIM_SUPPORT→插入引用标记、COUNTERPOINT→追加反证提示、FORBIDDEN_TERM→删除替换。STRUCTURE/EVIDENCE_SUFFICIENCY 标记需人工审核。硬限制 max 2 轮。
- `renderer.py` — `CompiledReport → list[SectionOutput]` 适配器，调用现有 `reporting/projections/`，不改 projections 任何文件。第二阶段新增 `render_tables` / `render_charts`，从 facts store 渲染 `TableSpec` / `ChartSpec`。

第二阶段新增模块（证据工程期）：

- `evidence_retriever.py::AssertionRetriever` — 从 `assertion` 表检索已结构化断言，包成 `EvidencePackage`（每个 assertion 一个 `EvidenceChunk`，`evidence_type=FACT`），按 `source_doc_id` 聚合成 `EvidenceDocument`。实现 `EvidenceRetrieverProtocol`，可注入 `ReportCompiler`。
- `fact_extractor.py::extract_from_assertions` — 快速路径：`list[Assertion] → list[FactRecord]`，跳过 LLM 抽取（assertion 已是结构化事实）。`predicate → claim_type` 启发式分类，`object_value.value → numeric_value`，`source_span.chunk_text → evidence_span`，reliability → tier。
- `table_renderer.py` — 筛 `claim_type==METRIC` 的 facts，按 entity(行) × period(列) 聚合为 `TableSpec`，cell 值携带 `fact_id` 短码，event 类排除。
- `chart_renderer.py` — 数值型 facts → `ChartSpec`，单 entity 走 line、多 entity 走 bar，series 数据 JSON 序列化存 `data_range`。

第三阶段新增模块（质量闭环期）：

- `critic.py::review_full()` — 逐数字支撑验证（值容差±5%）、数字矛盾检测（偏差>20%）、反证覆盖、结构连贯性、证据充分度、禁用词检查。输出 `CritiqueReport`（含 metrics：claim_support_rate/conflict_count/citation_density 等）。`_text_overlap()` 中英文自适应：英文用词重叠，中文用字符二元组重叠。`_CITATION_MARKER_PATTERN` 过滤 `[f1]`/`[1]` 防止引用标记误解析为数字。
- `revision_pass.py` — 消费 `CritiqueReport` 自动修复，修复规则见上文。`RevisionResult` dataclass 追踪 fixed/unfixable/remaining/rounds/converged。
- `compiler.py::_critic_revision_loop()` — 批判→修订→重新批判循环，每次修订后重新绑定引用，PASS/MINOR 收敛后 break。
- `core/contracts/compiler.py` — 新增 `CritiqueSeverity`/`CritiqueCategory` 枚举，`CritiqueIssue`/`CritiqueReport` Pydantic 模型。
- `citation_verifier.py` — Phase 3.2 引用验证器：引用精度检查（fact 数值匹配+文本重叠分数）、孤立引用检测、来源多样性检查（单源 >80% 告警）、全局引用覆盖率计算。全规则驱动，不调用 LLM。输出 `list[CritiqueIssue]`。
- `numeric_checker.py` — Phase 3.2 数字检查器：从正文提取数字（过滤年份/序号/引用标记），±5% 容差匹配 fact 值；检测虚构数字（无匹配 fact）、单位不一致（同义词感知）、期间不一致（相对期间直接放过、绝对期间年/季/半年度比较）。全正则+结构驱动，不调用 LLM。输出 `list[CritiqueIssue]`。
- `citation_verifier.py::_find_sentence_with_citation()` — 按中英文分句点（。/！/？/!/?/\n）定位引用标记 `[N]` 所在句子。
- `numeric_checker.py::_extract_unit_near_number()` — 数字 ±10 字符窗口提取单位文本，按长度降序匹配（亿元 > 元），优先后区间紧邻位置。
- `numeric_checker.py::_extract_period_near_number()` — 数字 ±30 字符窗口查找期间模式，返回距离数字最近的匹配（非首次匹配）。
- `revision_pass.py::_fix_*` — 新增 6 个 Phase 3.2 修复方法：`_fix_citation_precision`（移除低精度引用标记）、`_fix_orphan_citation`（移除孤立引用）、`_fix_unit_mismatch`（替换单位文本）、`_fix_period_mismatch`（替换期间文本）。SOURCE_DIVERSITY/FABRICATED_NUMBER 标记不可自动修复。
- `compiler.py::Step 8.5` — critic revision loop 之后运行 CitationVerifier + NumericChecker，结果 merge 进 compile log。
- `compiler.py::Step 10.5` — Phase 3.3 可选评测：compile() 接受 `auto_grader` 参数，在 CompiledReport 组装后自动运行 AutoGrader.grade()，产出 EvaluationReport（非致命失败仅 log warning 不中断编译）。

Phase 3.3 评测体系（`reporting/compiler/evaluation/`）：

- `claim_extractor.py` — 声明抽取器，从 CompiledSection 中拆解 AtomicClaim。优先 LLM structured_output（`_ClaimExtractionResult` schema），失败或无 gateway 时规则回退（中英文句子拆分 + 数字检测 + fact 匹配）。与 FactExtractor 共用三层 schema 模式。
- `metrics.py` — `MetricsComputer`，五维度加权评分（检索 15% / 事实 35% / 引用 25% / 报告 15% / 效率 10%），分数 0-100 → Grade(A≥85/B≥70/C≥55/D≥40/F)，支持自定义权重。
- `auto_grader.py` — `AutoGrader`，编排 ClaimExtractor → CitationVerifier → NumericChecker → MetricsComputer 管线，产出 `EvaluationReport`（含 ReportMetrics / AtomicClaim[] / CritiqueIssue[]）。
- `benchmark_dataset.py` — `BenchmarkSuite`（任务集合，支持按类别/难度采样）+ `BenchmarkRunner`（编译+评测+聚合统计）+ `create_sample_benchmark_tasks()`（12 个样本任务，覆盖 5 类别 3 难度）。
- `ab_platform.py` — `ABPlatform.compare()`，双报告逐维度对比（9 个可量化维度），判定综合胜者；支持盲评模式（随机交换标签）。全规则驱动。
- `core/contracts/compiler.py` — 新增 7 个 Pydantic 模型：`VerificationStatus`（枚举）/ `AtomicClaim` / `ReportMetrics` / `EvaluationReport` / `BenchmarkTask` / `ABDimensionDiff` / `ABComparison`。

依赖：`core/contracts/compiler.py`（`SourceTier`/`FactRecord`/`Provenance`/`Citation`/`ReportOutline`/`CompiledSection`/`CompiledReport`/`reliability_to_tier`）、`core/model_gateway/structured_output_utils.py`、`core/services/source_grader.py`、`knowledge_layer/retrieval/assertion_search.py`。

迁移状态：第一阶段为骨架 + 单元测试，未接入生产路由；后续通过 `engine: legacy|compiler|shadow` feature flag 逐步切换（见 `deep-research-report.md` 三阶段路线图）。

Update this section when:

- 编译器流水线步骤增减或顺序变化。
- 新增 compiler 契约字段或 `FactRecord`/`Citation` 结构变化。
- `engine` feature flag 接入生产路由。

---

### `reporting/content/`

Purpose:
- 通用内容元素适配器，将旧的 SectionOutput（纯文本）转换为新 Document→Section→ContentBlock→ContentElement 结构。
- `adapter.py` — `section_output_to_section()` / `content_elements_from_string()`，向后兼容所有现有流水线。

Update this section when:
- ContentElement 类型层级发生变化。
- 适配器需支持新的旧格式转换。

---

### `reporting/rendering/`

Purpose:
- 格式无关的文档渲染引擎，统一 Word/PPT/Markdown 的渲染流程。
- `base.py` — `DocumentRenderer` 抽象基类 + `RenderContext`，子类只需实现 `_render_*` 元素方法。
- `word_renderer.py` — Word (.docx) 渲染器，支持所有 12 种 ContentElement、TOC 域代码、页眉页脚、DesignTokens→Word 样式映射。
- `ppt_renderer.py` — PPT (.pptx) 渲染器，支持 Section→Slide、y-offset 智能分页、原生图表、表格填充、模板加载、过渡效果。
- `markdown_renderer.py` — Markdown 渲染器，适合快速预览和 API 响应。
- `style_mapper.py` — `StyleMapper`，将 DesignTokens 映射为 Word 样式字典 / PPT 样式字典。
- `rich_text_injector.py` — v2 富文本注入器，替代扁平 `{{key}}`→str 替换，支持多 Run 段落生成。每个 Run 可以是静态标签（如加粗 "A股方面："）或 LLM 动态生成内容。核心方法 `inject(paragraph, placeholder_key, spec, generated_text, preserve_paragraph_style)`，内部按 `RichTextSpec.runs` 顺序创建多个带格式 Run（bold/italic/font_name/font_size/color_hex）。
- `chart_grid_injector.py` — v2 图表网格注入器，在占位符位置创建无边框 Word 表格实现图表矩阵布局（如 2×2）。支持三种渲染模式：`native_chart`（从 Excel 复制原生图表 XML）、`matplotlib_image`（程序化 matploblib 渲染）、`embedded_image`（直接嵌入图片文件）。表格结构：偶数行=标题行（粗体居中），奇数行=图表行。
- `template_renderer.py` — v2 配置驱动模板渲染器（`ConfigDrivenTemplateRenderer`），协调 RichTextInjector 和 ChartGridInjector。核心流程：打开 .docx 模板 → 遍历 `EnhancedPlaceholder` → 按类型分发处理（TEXT/RICH_TEXT/CHART/CHART_GRID/IMAGE/TABLE_DATA）→ 后处理（清理空 Run）→ 保存。内容生成委托给 `_generate_content()` 支持四种模式：STATIC/LLM_DIRECT/EVIDENCE_GROUNDED/DATA_DRIVEN。条件可见性通过 `visible_if` Jinja2 表达式控制。

Update this section when:
- 新增输出格式渲染器。
- 渲染器接口或 DesignTokens 映射逻辑变化。
- 新增 EnhancedPlaceholder 类型（PlaceholderType 枚举扩展）。
- 渲染器内容生成模式（GenerationMode）变化。

---

### `reporting/builder/`

Purpose:
- 统一报告构建流水线，将 Build→Validate→Render 三阶段串联。
- `content_builder.py` — `ContentBuilder`，4 种输入→Document：from_template / from_sections / from_compiled / from_dict。
- `pipeline.py` — `UnifiedPipeline` + `PipelineResult` + `ValidationResult`，策略模式分发构建策略。
- `strategies/from_template.py` — `TemplateStrategy`，v1/v2 YAML 模板→Document，支持 `{{var}}` 插值和条件渲染。
- `strategies/from_research.py` — `ResearchStrategy`，`CompiledReport`→Document，含附录构建。

Update this section when:
- 新增构建策略。
- 验证规则变化。
- 流水线阶段顺序或接口变化。

---

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

### `core/contracts/reporting.py` (v2 Enhanced Schema)

Purpose:
- v2 配置驱动模板渲染的 Pydantic v2 契约层，与 `reporting/rendering/template_renderer.py` 配合使用。
- `PlaceholderType` — 增强占位符类型枚举：`TEXT` / `RICH_TEXT` / `CHART` / `CHART_GRID` / `IMAGE` / `TABLE_DATA`。
- `GenerationMode` — 内容生成策略枚举：`STATIC` / `LLM_DIRECT` / `EVIDENCE_GROUNDED` / `DATA_DRIVEN`。
- `InlineRunSpec` — 段落内单个 Run 的规格（`text` / `bold` / `italic` / `font_name` / `font_size_pt` / `color_hex` / `is_dynamic`）。`is_dynamic=True` 的 Run 由 LLM 生成内容填充。
- `RichTextSpec` — 多 Run 段落规格，`runs` 列表定义段落内每个 Run 的格式和内容来源。
- `ChartCellSpec` / `ChartGridSpec` — 图表网格布局规格，定义 rows×cols 矩阵中每个 cell 的图表类型、数据源和渲染模式。
- `RetrievalConfig` — 检索配置，含 `keyword_groups`（关键词组）、`exclude_keywords`、`mode`（hybrid/keyword/semantic）、`top_k` 等。
- `GenerationConfig` — 生成配置，含 `prompt_template_ref`（引用 prompt_templates.md 中的模板名）、`target_words`、`max_words`、`output_mode`（single_paragraph/multi_paragraph）。
- `ValidationSpec` — 内容校验规格：`forbidden_terms`（禁用词列表）、`forbid_instruction_leaks`（LLM 指令泄露检测）、`min_chars`、`require_numbers`。
- `EnhancedPlaceholder` — 核心模型，替代扁平 `{{key}}`→str 映射。每个占位符是一个有类型的 `ContentRegion`，携带 `type`、`generation_mode`、`generation_config`、`rich_text_spec`、`chart_grid_spec`、`validation`、`visible`/`visible_if`（条件可见性）、`hide_strategy`（隐藏时处理策略）。
- `ReportTemplateConfig` — v2 报告模板配置根模型，含 `meta`、`template`（引用模板文件路径）、`placeholders`（key→EnhancedPlaceholder 字典）、`defaults`（全局默认生成/检索/校验策略）。`@model_validator` 自动从 YAML dict key 填充 `placeholder.key`。
- 向后兼容：v1 路径（现有 `section_config.yaml` + `WordProjection.save_from_template`）完全保留不变。v2 通过检测 `config/report_config.yaml` 自动启用。

Update this section when:
- EnhancedPlaceholder 或 ReportTemplateConfig 字段增减。
- 新增 PlaceholderType 或 GenerationMode 枚举值。
- RichTextSpec / ChartGridSpec 结构变化。

---

### `report_projects/*/config/report_config.yaml` (v2)

Purpose:
- v2 报告项目配置文件，与 `section_config.yaml`（v1）共存但服务于不同渲染路径。
- 直接定义 `EnhancedPlaceholder` 字典，每个占位符 key 映射到完整的生成策略（类型、检索关键词、prompt 模板引用、输出格式、校验规则）。
- `meta` — 项目元数据（name/version/description/report_type）。
- `template` — 模板文件引用（word_template/excel_workbook/chart_workbook/prompt_templates）。
- `defaults` — 报告级默认策略：`generation_mode`、`evidence_policy`、`retrieval`（hybrid/RRF/rerank 参数）、`validators`（全局禁用词列表）、`report_period`。
- `placeholders` — 占位符字典，每个占位符的 key 必须匹配 .docx 模板中的 `{{key}}`：
  - `type: rich_text` + `generation_mode: evidence_grounded` → 检索证据后 LLM 生成富文本。
  - `type: text` + `generation_mode: static` → 静态替换（如日期）。
  - `type: chart_grid` → 图表网格布局。
  - `rich_text_spec.runs` — 定义段落内静态标签（bold 标题）+ 动态正文（`is_dynamic: true`）。

Update this section when:
- v2 配置 schema 变化。
- 新增 v2 报告项目时。

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

- 2026-07-20: 新增 v2 配置驱动模板渲染框架（模板为主、配置增强）。新增 `core/contracts/reporting.py` 中的 EnhancedPlaceholder/ReportTemplateConfig 等 Pydantic v2 契约、`reporting/rendering/rich_text_injector.py`（多 Run 富文本注入器）、`reporting/rendering/chart_grid_injector.py`（图表网格注入器）、`reporting/rendering/template_renderer.py`（ConfigDrivenTemplateRenderer 主渲染器）。`reporting/projects/run.py` 通过检测 `config/report_config.yaml` 自动选择 v2 路径，v1 路径完全保留。新增华安ETF周报 v2 配置（9 个 EnhancedPlaceholder：7 个 RICH_TEXT + 2 个 TEXT），支持 evidence_grounded LLM 生成、多 Run 富文本格式、条件可见性、后处理清理。ClaimExtractor 从章节拆解 AtomicClaim（LLM structured_output + 规则回退），MetricsComputer 五维度加权评分（检索/事实/引用/报告/效率→0-100），AutoGrader 编排全管线产出 EvaluationReport，BenchmarkSuite+BenchmarkRunner 支持 12 个样本任务跨类别/难度基准测试，ABPlatform 逐维度对比双报告并判定胜者（支持盲评）。新增 7 个 Pydantic 契约（VerificationStatus/AtomicClaim/ReportMetrics/EvaluationReport/BenchmarkTask/ABDimensionDiff/ABComparison）。compiler.py Step 10.5 可选集成 auto_grader。新增 51 个测试，137 个编译器测试全通过。
- 2026-07-16: 报告编译器第三阶段 3.2：新增 CitationVerifier（引用验证器）与 NumericChecker（数字检查器），提供比 critic 更细粒度的引用质量与数字真实性验证。CitationVerifier 四维检查（引用精度/孤立引用/来源多样性/引用覆盖率），NumericChecker 三维检查（虚构数字/单位不一致/期间不一致），全部规则驱动不调用 LLM。扩展 `CritiqueCategory` 六个新枚举值，无缝接入现有 `CritiqueReport`→`RevisionPass` 流程。`revision_pass.py` 新增 6 个 `_fix_*` 方法（精度/孤立/单位/期间可自动修复，来源多样性/虚构数字标记人工）。`compiler.py` Step 8.5 在 critic revision loop 之后运行双验证器。修复 4 个边界问题（句子定位初始化偏移、单位提取长短匹配优先级、期间提取就近选择、引用标记后文本截断）。新增 20 个测试（citation_verifier 10 + numeric_checker 10），86 个编译器测试全通过。
- 2026-07-16: 报告编译器第三阶段 3.1：critic 从简化版升级为完整六类批判器（CLAIM_SUPPORT/CONFLICT/COUNTERPOINT/STRUCTURE/EVIDENCE_SUFFICIENCY/FORBIDDEN_TERM），新增 `CritiqueReport`/`CritiqueIssue`/`CritiqueSeverity`/`CritiqueCategory` 契约，新增 `revision_pass.py` 自动修复引擎（CONFLICT→替换数字、CLAIM_SUPPORT→插入引用、COUNTERPOINT→追加反证、FORBIDDEN_TERM→删除），编译器版本升至 2.0，`_critic_revision_loop` 最多 2 轮批判→修订循环，PASS/MINOR 收敛后 break。中英文自适应文本重叠算法（中文字符二元组/英文词重叠），引用标记过滤防止误解析。新增 23 个测试（critic_full 14 + revision_pass 9），66 个编译器测试全通过。
- 2026-07-15: 新增 `reporting/compiler/` outline-first + evidence-first 报告编译器骨架（第一阶段）。9 步流水线（任务分解→来源规划→检索→事实抽取→大纲→分节写作→引用绑定→批判→渲染），新增 `core/contracts/compiler.py` 契约（`SourceTier`/`FactRecord`/`Provenance`/`Citation`/`ReportOutline`/`CompiledReport`），改造 `core/model_gateway/structured_output_utils.py` 支持 OpenAI strict JSON Schema 与 Anthropic tool use 三级回退。42 个单元测试全通过，未接入生产路由，后续通过 `engine` flag 迁移。
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
