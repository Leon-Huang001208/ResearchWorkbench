# 更新日志

所有 notable 项目变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Desktop baseline fixes

- **桌面基线与打包契约恢复**：恢复根目录 `package.json` / `package-lock.json` 及 `build_sidecar.py` 的自包含 `backend_launcher.py` PyInstaller 打包输入；冻结桌面首次启动不再由自动生成 `.env` 强制 PostgreSQL，未配置时回退到用户数据目录下的 SQLite，同时保留进程环境变量和已有用户 `.env` 的优先级。
- **桌面静态回归测试对齐**：测试改为覆盖 Node 跨平台启动桥接、当前 `20260722flowfix` 缓存版本、Word/PPT 必填模板分支及非 Word 资产可选行为。
- **ESM 桌面后端桥接**：将 `scripts/desktop/run_backend.js` 转为 ESM，使 Tauri `beforeDevCommand` 在桌面 `package.json` 声明 `"type": "module"` 时仍可执行，并保留平台启动器选择、参数转发和子进程退出状态传播。

### Added

- **通用报告框架 Phase 1-4（通用内容模型 + 渲染引擎 + 统一流水线 + PPT/Word 增强）**: 将 `reporting/` 模块重构为通用文档生成框架，任何内容结构都通过统一的 `Document` 模型描述，并渲染为 Word/PPT/Markdown。
  - **Phase 1 通用内容模型**: 新建 `core/contracts/content_element.py`（12 种 ContentElement 类型 + TextRun 富文本 + ContentBlock 容器）和 `core/contracts/document.py`（Section/Document/DesignTokens/TemplateSlot）。新建 `reporting/content/adapter.py`（SectionOutput→Section 向后兼容适配）。58 个测试。
  - **Phase 2 渲染引擎抽象**: 新建 `reporting/rendering/` 子包（`base.py` DocumentRenderer 抽象基类 + RenderContext、`word_renderer.py`、`ppt_renderer.py`、`markdown_renderer.py`、`style_mapper.py` DesignTokens→格式样式映射）。66 个测试。
  - **Phase 3 统一流水线 + 模板系统升级**: 新建 `reporting/builder/` 子包（`content_builder.py` 4种输入→Document、`pipeline.py` Build→Validate→Render 三阶段、`strategies/from_template.py` v1/v2 YAML 模板驱动、`strategies/from_research.py` CompiledReport→Document）。TemplateConfig 新增 `is_v2`/`get_design_tokens()`，TemplateManager 新增 `upgrade_to_v2()`。61 个测试。
  - **Phase 4 PPT/Word 增强 + DesignTokens 扩展**: PPT 渲染器重写——智能 y 坐标分页、原生 ChartData 图表、表格单元格背景填充、自定义模板加载、幻灯片过渡效果、双栏布局。Word 渲染器增强——自动 TOC 域代码、页眉（文档标题）、页脚（PAGE 域代码）。DesignTokens 新增 `ppt_template_path`/`ppt_transition` 字段。修复 `ppt_renderer.py` 模块级常量在未安装 pptx 时的 NameError。26 个测试（18 个 PPT 测试待安装 python-pptx 后运行）。
  - **测试**: 全量 211 passed, 19 skipped, 0 failed ✅。ruff/black/isort 全部通过。

### Changed

- **Desktop Workbench refresh shortcuts**: `app/web/static/js/app.js` now captures `F5`, macOS `Cmd+R`, and Windows/Linux `Ctrl+R` during `DOMContentLoaded`; each prevents the browser default and performs only `window.location.reload()`, including from focused inputs. The app script cache token is `20260723refresh1`; no Tauri native shortcut, sidecar restart, or HMR behavior was added.

- **桌面端启动加速（97s → 25s，-75%）**: 通过 PEP 562 `__getattr__` 懒加载和函数内延迟导入，消除启动时不必要的全量模块导入链。
  - **P0 修复（阻断启动的主链）**: 6 个路由文件（`app/api/routes/commentary.py`、`assets.py`、`ingest.py`、`ingestion_queue.py`、`pipeline.py`、`event_ingestion.py`）的重型依赖（`ModelGatewayImpl`、`KnowledgePipeline`、`ResearchPipeline`、`IngestService`、`StructuredEventIngestor`）从模块顶层移入 Dependency 函数体内，首次请求时才加载。
  - **P1 加固（防止后续回归）**: `core/model_gateway/gateway.py` 的 `LocalEmbeddingProvider` 导入从模块顶层移入 `_init_providers()` 方法内（`protocol == "local"` 分支）；`core/model_gateway/providers/__init__.py` 移除 `LocalEmbeddingProvider` 的模块级导出；`services/signal_validator_impl.py` 的 `signal_lab.*` 导入移入 `__init__` 方法内；`services/commentary_news_selector.py` 的 `reporting.*` 导入移入 `select()` 方法内。
  - **P2 优化（CLI 加速）**: `signal_lab/backtests/__init__.py` 的 `VectorBTBacktester` 改为 PEP 562 `__getattr__` 懒加载，CLI `af backtest` 首次运行前不再卡 ~10s。
  - **包级懒加载**: `services/__init__.py` 和 `data_layer/__init__.py` 清空所有模块级 re-export，改为 `__getattr__` 按需导入。
  - **关键导入链分析**: 三条主要瓶颈链——`sentence_transformers`（~52s，通过 `ModelGatewayImpl` → `LocalEmbeddingProvider`）、`ingestion` 全链（~77s 累积）、`vectorbt`（~10s，通过 `signal_lab.backtests.__init__`）。
  - 剩余 25s 由 `anthropic`/`openai` SDK（~8s）、`akshare`（~3s）、基础设施（EventLog、MarketDataCache、timing models）构成，可进一步优化但不再阻塞桌面启动。

### Added

- **报告编译器第三阶段 3.3（评测体系）**: 新增 `reporting/compiler/evaluation/` 子包，建立从原子声明抽取到多维度评分再到 A/B 对比的完整评测闭环。
  - **声明抽取器**: 新建 `claim_extractor.py`，从 `CompiledSection` 拆解 `AtomicClaim`。优先 LLM `structured_output`（`_ClaimExtractionResult` schema），失败或无 gateway 时规则回退（中英文句子拆分 + 数字检测 + fact 交叉验证）。与 `FactExtractor` 共用三层 schema 模式。
  - **指标计算器**: 新建 `metrics.py`，`MetricsComputer` 五维度加权评分：检索质量（Tier A+B 占比+多样性）、事实质量（声明支撑率+虚构惩罚）、引用品质（覆盖率+孤儿率+集中度）、报告质量（结构+反证）、生产效率（耗时+token+修订轮数），加权聚合为 0-100 综合评分，映射 Grade(A≥85/B≥70/C≥55/D≥40/F)。支持自定义维度权重。
  - **自动评分器**: 新建 `auto_grader.py`，`AutoGrader` 编排 ClaimExtractor → CitationVerifier → NumericChecker → MetricsComputer 完整管线，产出 `EvaluationReport`（含 `ReportMetrics`/`AtomicClaim[]`/`CritiqueIssue[]`）。支持复用预计算的 verifier issues。
  - **基准测试框架**: 新建 `benchmark_dataset.py`，`BenchmarkSuite`（按类别/难度筛选与采样）+ `BenchmarkRunner`（编译+评测+聚合统计：mean/median/std/grade distribution/per-category averages）+ `create_sample_benchmark_tasks()`（12 个样本任务，覆盖 5 类别（公司研究/行业分析/竞品对比/市场格局/技术路线）×3 难度）。
  - **A/B 对比平台**: 新建 `ab_platform.py`，`ABPlatform.compare()` 双报告逐维度对比（9 个可量化维度），判定综合胜者；支持盲评模式（随机交换标签，揭示后报告）。全规则驱动，不调用 LLM。
  - **契约扩展**: `core/contracts/compiler.py` 新增 7 个 Pydantic 模型：`VerificationStatus`（verified/contradicted/unverifiable/irrelevant）、`AtomicClaim`（含 claim_type/fact_ids/verification/confidence）、`ReportMetrics`（五维度 19 个显式字段）、`EvaluationReport`（聚合 metrics+claims+issues）、`BenchmarkTask`（task_id/prompt/expected_sections/category/difficulty）、`ABDimensionDiff`（dimension/value_a/value_b/diff/pct_change/winner）、`ABComparison`（report_id_a/b/label_a/b/blind_mode/dimensions/overall_winner/win_count/summary）。
  - **Compiler 集成**: `compiler.py` Step 10.5 可选集成 `auto_grader`（`__init__` 接受 `auto_grader` 参数），在 `CompiledReport` 组装后自动运行评测。非致命失败仅 log warning，不中断编译。
  - **StubModelGateway 扩展**: `tests/unit/reporting/compiler/conftest.py` 新增 `_ClaimExtractionResult` 预设返回（3 条样本声明）。
  - **测试**: 新增 51 个测试——`test_metrics.py`（10 个：维度填充/tier ratio/虚构计数/孤儿计数/等级阈值/空报告/自定义权重/效率透传/修订轮数/覆盖计算）、`test_claim_extractor.py`（12 个：LLM 抽取/规则回退/空内容/claim_type/多章节/置信度/数字标记/短句过滤/引用清理/LLM 故障回退/section_id 校验/交叉验证）、`test_auto_grader.py`（10 个：烟雾测试/critique 复用/无 critique/无 gateway/issues 聚合/precomputed 复用/metrics 填充/规则抽取/自定义权重/等级映射）、`test_benchmark.py`（11 个：工厂返回/字段完整/类别覆盖/难度覆盖/suite 构建/过采样/筛选/采样/add/空套件降级/完整集成）、`test_ab_platform.py`（8 个：返回类型/维度数量/A 胜出/盲评/tie/摘要/delta 计算/非盲评标签）。137 个编译器测试全通过。
  - **质量门**: ruff/black/isort/mypy 全部通过（仅涉及变更文件）。`docs/modules/reporting.md` + `docs/CHANGELOG.md` 已更新。

- **提问优先联网查询**: 新增「始终先联网再综合」的问答能力，覆盖 CLI 与 API 两个入口。无论内部是否有资料，每次提问都先上网搜索，把搜索结果（摘要+正文）注入 prompt，模型生成带 `[n]` 引用的答案。未配置搜索 API key 时降级为不联网直答，答案前标注 `[未联网]`，不报错。不引入 tool-calling 循环（用户要求"始终先联网"是确定性检索增强，不需要模型自主决定搜不搜）。
  - **抽象接口**: `core/interfaces/web_search.py`——`WebSearchProvider` / `WebSearchResult`，统一搜索结果模型。
  - **Provider 实现**: `data_layer/web_search/`——`TavilyProvider`（默认，专为 LLM 设计，直接返回正文）、`BingProvider`（返回摘要+URL，正文由 `page_fetcher` 补抓）、`page_fetcher`（httpx 抓 HTML + trafilatura 抽正文，抓取失败优雅降级）、`factory`（按 `WEB_SEARCH_PROVIDER` 切换）。
  - **服务内核**: `services/web_search_service.py`（搜索+补抓+格式化）、`services/ask_service.py`（联网搜索→注入 prompt→`ModelGateway` 生成）、`services/ask_factory.py`（`build_ask_service()` 装配，单例 ModelGateway）。
  - **入口**: CLI `af ask "问题"`（`-n/--max-results`、`--no-fetch-content`）；API `POST /api/llm/ask`（返回 `{answer, online, model, sources}`）。
  - **配置**: `core/settings/config.py` 新增 `WEB_SEARCH_PROVIDER`/`TAVILY_API_KEY`/`BING_API_KEY`/`WEB_SEARCH_MAX_RESULTS`/`WEB_SEARCH_FETCH_CONTENT`/`WEB_SEARCH_MAX_CHARS`/`WEB_SEARCH_TIMEOUT`。
  - **测试**: `tests/unit/test_web_search.py`——13 个测试覆盖 format 编号、正文补抓与降级、ask 注入与无 key 降级、provider 切换、kwargs 不泄漏。全通过。
  - **认知代理接入（阶段 3）**: `cognitive_agents/workflow.py`——`AgentWorkflowRunner` 支持可选的 `web_search_service` 参数，在信息收集阶段（`news`/`financial_report`/`industry_data`/`social_media`）evidence 不足（< 2 条）时自动调 `_enrich_evidence_from_web()` 联网补充，搜索结果转为 `EvidenceItem`（新格式）和 legacy dict（旧格式），双注入 `context.evidence_bundle` 和 `context.evidence`，兼容四种信息 Agent 的 `_build_prompt` 直接引用 `context.evidence` 的风格。
  - **报告生成接入（阶段 3）**: `reporting/projects/generation.py`——`ReportProjectGenerationService` 支持可选的 `web_search_service` 参数，在 `_generate_configured_placeholder()` 中 DB 检索无结果时，调 `_enrich_evidence_from_web()` 联网搜索补充，搜索结果转为 `EvidenceSnippet` 追加到 evidence 列表，走同一 `format_evidence_context` → `build_generation_messages` 路径。
  - **测试（阶段 3）**: `tests/unit/test_web_search_phase3.py`——14 个测试覆盖 EvidenceItem/EvidenceSnippet 转换、`_enrich_evidence_from_web` 注入、角色过滤（信息触发/非信息跳过）、空结果降级、异常优雅处理。
  - **文档**: `docs/modules/services.md` 新增 `web_search_service` / `ask_service` 段；`docs/modules/app_cli.md` 新增 `af ask` 段；`docs/DATA_SOURCES.md` 新增「联网搜索」小节；`docs/generated/py_file_index.md` 已更新。

- **报告编译器第三阶段 3.2（Citation Verifier + Numeric Checker）**: 新增两个独立验证模块，提供比 critic 更细粒度的引用质量与数字真实性验证，全规则驱动不调用 LLM。
  - **引用验证器**: 新建 `citation_verifier.py`，四维检查：引用精度（fact 所在句子的数值+文本重叠分数，<0.5 告警）、孤立引用（fact_ids 指向不存在的 fact → error）、来源多样性（单源 >80% 标记 info）、引用覆盖率（<80% 标记 info）。`_find_sentence_with_citation()` 按中英文分句点定位引用标记所在句子，`_compute_precision_score()` 值匹配 + 文本重叠双因子评分。
  - **数字检查器**: 新建 `numeric_checker.py`，三维检查：虚构数字（±5% 容差无匹配 fact → error）、单位不一致（同义词感知匹配 → warning）、期间不一致（相对期间放过、绝对期间年/季/半年度比较 → info）。`_extract_numbers_from_content()` 过滤年份/序号/引用标记，`_extract_unit_near_number()` 按长度降序遍历已知单位，`_extract_period_near_number()` 返回距离数字最近的期间匹配。
  - **契约扩展**: `CritiqueCategory` 枚举新增 6 个值：CITATION_PRECISION、ORPHAN_CITATION、SOURCE_DIVERSITY、FABRICATED_NUMBER、UNIT_MISMATCH、PERIOD_MISMATCH。两个 verifier 输出 `list[CritiqueIssue]`，无缝接入现有 `CritiqueReport`→`RevisionPass` 流程。
  - **RevisionPass 扩展**: `revision_pass.py` 新增 6 个 `_fix_*` 方法：`_fix_citation_precision`（移除低精度引用标记）、`_fix_orphan_citation`（移除孤立引用）、`_fix_unit_mismatch`（替换单位文本）、`_fix_period_mismatch`（替换期间文本）。SOURCE_DIVERSITY/FABRICATED_NUMBER 不可自动修复，标记需人工审核。
  - **Compiler 集成**: `compiler.py` Step 8.5 在 critic revision loop 之后运行两验证器，结果 merge 进 compile log。编译器版本保持 2.0（minor extension）。
  - **边界问题修复**: 修复 4 个边界问题——`_find_sentence_with_citation` 的 `sent_start` 从 `idx`（错误偏移）改为 0、`_extract_unit_near_number` 按长度降序匹配单位并优先检查后区间、`_extract_period_near_number` 选择距离数字最近的期间匹配而非首次匹配、测试中 coverage issue 的 fact_id 出现在 `suggested_fix` 而非 `description`。
  - **测试**: 新增 20 个测试——`test_citation_verifier.py`（10 个：精度/孤立/多样性/覆盖率/空章节/多章节）、`test_numeric_checker.py`（10 个：匹配/虚构/单位/期间/年份过滤/引用标记过滤/混合结果/空内容/无数字/多章节）。86 个编译器测试全通过。
  - **质量门**: ruff/black/isort/mypy 全部通过（0 errors）。

- **报告编译器第三阶段 3.1（Critic 升级 + Revision Pass）**: 将第一阶段简化批判器升级为完整六类批判器，新增自动修复引擎与 revision 循环。
  - **完整批判器**: `critic.py` 从三检查（forbidden_terms/numeric_consistency/citation_coverage）升级为六类完整检查：CLAIM_SUPPORT（逐数字支撑验证，值容差±5%）、CONFLICT（数字矛盾检测，偏差>20%）、COUNTERPOINT（反证覆盖检查）、STRUCTURE（字数偏差/必答问题覆盖）、EVIDENCE_SUFFICIENCY（引用密度/事实密度）、FORBIDDEN_TERM（禁用词）。新增 `CritiqueReport`/`CritiqueIssue` 模型（Pydantic v2）替换旧 `ValidationResults`，输出 metrics 包含 claim_support_rate/conflict_count/citation_density 等。保持向后兼容 `review()` 接口。
  - **中英文自适应 NLP**: `_text_overlap()` 方法英文用词重叠（≥2 公共非短词）、中文用字符二元组重叠（≥2 公共二元组）。`_CITATION_MARKER_PATTERN` 过滤 `[f1]`/`[1]` 防止引用标记误解析为内容数字。
  - **自动修复引擎**: 新建 `revision_pass.py`，按 `CritiqueIssue.category` 自动修复：CONFLICT→替换矛盾数字为事实表值、CLAIM_SUPPORT→插入最佳匹配 fact 的引用标记（按值接近度×3+文本重叠×2 评分）、COUNTERPOINT→节尾追加反证提示句、FORBIDDEN_TERM→替换为"（已删除违规表述）"。STRUCTURE/EVIDENCE_SUFFICIENCY 不可自动修复，标记需人工审核。`RevisionResult` dataclass 追踪 fixed/unfixable/remaining/rounds/converged。
  - **Revision 循环**: `compiler.py` 编译器版本升至 2.0，新增 `_critic_revision_loop()`：批判→修订→重新批判→重新绑定引用，最多 2 轮。severity∈{PASS,MINOR} 且所有 error 级别问题已修复后 converge 并 break。
  - **契约扩展**: `core/contracts/compiler.py` 新增 `CritiqueSeverity`（PASS/MINOR/MAJOR/CRITICAL）、`CritiqueCategory`（六类枚举）、`CritiqueIssue`（含 location/conflicting_fact_id/suggested_fix）、`CritiqueReport`（含 overall_severity/issues/metrics/revision_suggestions）。
  - **测试**: 新增 23 个测试——`test_critic_full.py`（14 个：覆盖六类检查、PASS/MINOR/MAJOR/CRITICAL 严重度判定、metrics、向后兼容）、`test_revision_pass.py`（9 个：覆盖四种修复、不可修复标记、max 2 轮限制、追踪计数、missing section_id 跳过）。修复旧 test_compiler.py 中 2 个因契约变更失败的测试（version 1.0→2.0、check names 灵活断言）。66 个编译器测试全通过。
  - **质量门**: ruff/black/isort/mypy 全部通过（0 errors）。

- **报告编译器骨架（第一阶段）**: 新增 outline-first + evidence-first 报告编译器 `reporting/compiler/`，把报告生成从"单次长文生成"重构为多阶段流水线（参考 STORM/RAPID/FoRAG/CRAG/LongCite）。本阶段为骨架 + 单元测试，未接入生产路由，后续通过 `engine: legacy|compiler|shadow` feature flag 迁移。
  - **编译器流水线**: `ReportCompiler.compile(task)` 串联 9 步——任务分解 → 来源规划 → 证据检索 → 事实抽取与归一化 → 大纲规划 → 分节写作 → 引用绑定 → 批判 → 渲染。所有进入正文的数字与结论必须先落到 `FactRecord`（带 `Provenance`），实现 LongCite 式句级引用可验证。
  - **编译器契约**: 新增 `core/contracts/compiler.py`——`SourceTier`（A/B/C/D 四级）、`ClaimType`（metric/event/spec/guidance/risk）、`FactRecord`、`Provenance`、`Citation`/`CitationAnchor`、`OutlineSection`/`ReportOutline`、`CompiledSection`/`CompiledReport`、`ResearchPlan`、`reliability_to_tier()`。向后兼容扩展 `core/contracts/reporting.py`：`FactCard` 增 `fact_records`/`provenance_summary`，`SectionOutput` 增 `compiled_section`/`citations`，`ReportRunLog` 增 `compiler_version`/`outline`。
  - **structured_output 改造（关键前置）**: 新增 `core/model_gateway/structured_output_utils.py`——`pydantic_to_openai_json_schema`（展开 `$ref`、注入 `additionalProperties:false`，兼容 OpenAI strict mode）、`pydantic_to_anthropic_tool_schema`（转 tool use）、`retry_structured_parse`（重试 + 兜底 `model_construct`）。`openai_compatible.py` / `anthropic.py` 的 `structured_output` 改为三级回退：原生 response_format/tool_use → prompt 注入 + json.loads + 重试 → 空 construct。
  - **编译器模块**: `task_decomposer`（ReportTask→ResearchPlan）、`source_planner`（按 tier+weight 排序来源）、`evidence_retriever`（`EvidenceRetrieverProtocol` + `PassthroughEvidenceRetriever`）、`fact_extractor`（LLM 抽取 + 规则兜底 + 去重）、`outline_planner`（facts→大纲）、`section_writer`（`[fact_id]` 标注引用）、`citation_binder`（`[fact_id]`→`[N]` + orphan/unsupported 检测）、`critic`（数字一致性+引用覆盖+禁用词）、`renderer`（CompiledReport→SectionOutput 适配器，不改 projections）。
  - **测试**: `tests/unit/core/model_gateway/test_structured_output.py`（schema 转换/重试/兜底）、`tests/unit/reporting/compiler/`（fact_extractor/citation_binder/outline_planner/compiler 端到端，含 StubModelGateway + PassthroughEvidenceRetriever）。42 个测试全通过。
  - **修复**: `fact_extractor` 的 `generate_id(prefix="fact")` 让 fact_id 形如 `fact_xxx`，与 section_writer 的 `[fact_xxx]` 正则、citation_binder 解析、stub 一致，打通引用链路。
  - **文档**: `docs/modules/reporting.md` 新增 `reporting/compiler/` 段；`docs/generated/py_file_index.md` 已更新。

- **报告编译器证据工程期（第二阶段）**: 打通 facts store、来源分级落地、PGVectorStore 实现、检索统一消费 chunk+assertion、表格/图表从 facts store 渲染。本阶段未接入生产路由，engine feature flag 迁移留待第三阶段后。
  - **打通 facts store（2.1）**: `ingestion/knowledge_pipeline.py` 的 `PipelineResult` 新增 `assertions` 字段（不再丢弃），`process()` 把并发抽取的 assertions 挂回结果；`_enrich_assertion_spans` 用 `chunk_text` + `offset_start/offset_end` 精确化 `source_span`。`workers/knowledge_worker.py` 新增 `_persist_extraction_artifacts`：在 `source_document` 保存后持久化 chunks / entity_mentions / assertions（用 `DocumentChunkV1Repository.bulk_create` / `EntityMentionV1Repository.bulk_create` / `AssertionRepositoryImpl.save`，全部失败降级为 warning）。`process_one` 返回 dict 增 `assertions` / `chunks` 计数与 `assertion_list` / `chunk_list`。
  - **来源分级落地（2.2）**: `core/contracts/documents_v1.py` 的 `DocumentQuality` 新增 `source_tier` / `trust_score`（0-1）/ `freshness_score`（0-1）（JSONB 列，无需迁移）。`core/source_registry.py` 新增 `reliability_to_tier`（OFFICIAL→tier_a、ESTABLISHED_MEDIA/RESEARCH_INSTITUTE→tier_b、SPECIALIZED_MEDIA/OPINION_LEADER→tier_c、SOCIAL_MEDIA/UNKNOWN→tier_d）。新建 `core/services/source_grader.py`：`SourceGrader.grade/grade_inplace` 计算 tier 基础分 ± is_fact_source/UNKNOWN 微调的 trust_score，与半衰期衰减的 freshness_score（无 publish_time 给 0.5）。`knowledge_worker._create_document_v1` 后调 `SourceGrader.grade_inplace` 回填 quality。
  - **PGVectorStore 实现（2.3，两步走）**: `knowledge_layer/retrieval/vector_store.py` 的 `PGVectorStore` 第一步 DB-backed brute-force（embedding 以 JSON 存入 `document_chunk_v1.embedding` TEXT 列，search 加载到内存算余弦 top_k，<10 万文档可用）；第二步 pgvector 原生 `<=>` cosine distance 路径就绪，`_check_pgvector_once` 惰性检测扩展，当前环境 pgvector 系统级不可用则自动降级到第一步。`add_document` 仅 upsert 已存在 chunk 的 embedding（不自行 INSERT，避免 FK 冲突）。
  - **检索统一（2.4）**: 新建 `knowledge_layer/retrieval/assertion_search.py`——`AssertionSearchService` 按 predicate / object_value 关键词匹配检索 assertion 表，关联 `document_v1.quality` 取来源分级，内存精排按命中数×0.5+confidence×0.5。`reporting/compiler/evidence_retriever.py` 新增 `AssertionRetriever`（实现 `EvidenceRetrieverProtocol`，assertion→EvidenceChunk→按 source_doc_id 聚合 EvidenceDocument）。`reporting/compiler/fact_extractor.py` 新增 `extract_from_assertions` 快速路径（assertion→FactRecord，跳过 LLM）。
  - **表格/图表从 facts store 渲染（2.5）**: 新建 `reporting/compiler/table_renderer.py`（METRIC facts 按 entity×period 聚合为 `TableSpec`，cell 携带 fact_id 短码，event 类排除）与 `reporting/compiler/chart_renderer.py`（数值 facts→`ChartSpec`，单 entity line / 多 entity bar）。`renderer.py` 新增 `render_tables` / `render_charts` 并默认实例化两个 renderer。
  - **端到端验证**: `scripts/e2e_phase2_facts_store.py` 用本地 PG 实跑 2.1+2.2（grader tier_b/trust=0.80/fresh=1.00，chunks=1/mentions=1/assertions=1 落库）；2.3 暴力破解 add/search/delete 语义匹配；2.4 search→retriever→fact 快速路径 value=100.0/tier_a；2.5 table cell 带 fact 短码 + event 排除 + chart=line。
  - **测试**: 新增 5 个测试文件 38 个用例（`test_source_grader` / `test_assertion_search` / `test_pgvector_store` / `test_table_chart_renderer` / `test_fact_extractor_assertions`）；修复 `test_process_one_publishes_events` 回归（mock_result 补 `assertions=[]` / `chunks=[]`）。38 个新测试 + 170 个相关目录测试全通过。
  - **文档**: `docs/modules/reporting.md` 补第二阶段模块描述；`docs/generated/py_file_index.md` 已更新。

- **PDF 入库管线统一与配置补齐**: 收敛四类遗留问题——删除旧版死代码、统一 cninfo 旁路入口、补齐配置、验证策略可用性。
  - **清理旧版死代码**: 删除 `data_layer/parsers/pdf_parser.py`（PDFParser）和 `data_layer/adapters/pdf_adapter.py`（PDFAdapter）——早期 pdfplumber 封装，已被 `ingestion/converters/` 三策略管线完全取代，全项目零业务引用。同步移除 `data_layer/parsers/__init__.py` 和 `data_layer/adapters/__init__.py` 的导出。
  - **CNINFO 附件路径统一到路径 A**: `data_layer/adapters/cninfo_adapter.py` 的 `_append_attachment_text` 不再就地调 MarkItDown/RawText 转换，改为下载附件 PDF → 计算 SHA-256 → `get_pdf_by_hash` 去重 → 注册 `PDFArtifactV1DB(parse_status="pending")`，由 CrawlScheduler 异步走 `PDFConversionService` 三级降级。移除 `_convert_attachment_to_text` / `_candidate_converter_strategies` / `_conversion_to_dict`。行为变化：PDF 正文不再内联到公告 `raw_text`，延迟约 5 分钟通过独立 DocumentV1 入队。`metadata.attachment_text_status` 新增 `registered_pending` / `already_registered` 值。
  - **配置补齐**: `core/settings/config.py` 新增 `PDF_PREFERRED_STRATEGY`（默认 `auto`）、`PDF_QUALITY_MIN_SCORE`（默认 `0.0`）、`MINERU_ALLOW_MODEL_DOWNLOAD`（默认 `0`）。`.env` / `.env.example` 新增 PDF 转换配置段。
  - **策略选择增强**: `services/pdf_conversion_service.py` 的 `convert_pdf` 在调用方未传 `preferred_strategy` 时回退到 `settings.PDF_PREFERRED_STRATEGY`；新增质量分阈值过滤——成功但 `quality_score < PDF_QUALITY_MIN_SCORE` 的结果降级到下一策略。
  - **MinerU 配置统一**: `ingestion/converters/mineru.py` 的 `_model_cache_ready` 改为优先读 `settings.MINERU_ALLOW_MODEL_DOWNLOAD`，环境变量作 fallback。
  - **测试**: 重写 `tests/unit/test_cninfo_adapter_attachment_text.py` 覆盖新注册流程 + 哈希去重；`tests/unit/test_pdf_conversion_service.py` 新增 preferred_strategy 配置解析、质量分阈值降级、阈值禁用 3 个测试。
  - **依赖**: 安装 `markitdown[pdf]>=0.1.0`（中质量策略现已可用）。MinerU 因本机无 GPU 暂不启用（`is_available()` 会自动降级）。

### Fixed

- **knowledge_worker watchdog + Windows Job Object 自愈**: 解决 worker 崩溃后无自动恢复、以及 Windows 强杀导致 worker 孤儿残留两个遗留风险。
  - `workers/_process_tree.py` — 新增模块，通过 ctypes 实现 Windows Job Object（`KILL_ON_JOB_CLOSE`），`ensure_child_dies_with_parent(child_pid)` 把子进程绑定到 Job，Job handle 关闭/父进程退出时内核自动终止子进程，即使父进程被 `TerminateProcess` 强杀也不会孤儿残留。非 Windows 返回 None（靠 POSIX 进程组）。
  - `workers/watchdog.py` — `run_worker()` 调 `ensure_child_dies_with_parent(proc.pid)` 并持有 `_job_handle` 全局引用，确保 worker 随 watchdog 生命周期终止。
  - `workers/knowledge_worker.py` — `_parse_args()` 在 `--worker-id` 缺省时 fallback 读 `ALPHAFOUNDRY_WORKER_ID` 环境变量（frozen 子进程无法传 CLI 参数）。
  - `scripts/desktop/backend_launcher.py` — `_start_knowledge_worker()` 改为启动 watchdog（frozen: `ALPHAFOUNDRY_WATCHDOG_MODE=1`；dev: `python -m workers.watchdog`），`__main__` 新增 watchdog 模式分支。
  - `tests/unit/workers/test_process_tree.py` / `test_watchdog.py` / `test_knowledge_worker.py` — 覆盖 Job Object 端到端（`CloseHandle` 杀子进程）、frozen/dev 命令构造、PID 自愈、worker_id 透传。

- **知丘账号配置链路断裂修复**：系统配置工作台保存 5 个知丘账号后，`.env` 只剩 2 个、且运行时 `AccountManager` 读不到任何账号（5 个账号被连续失败误杀到全部永久禁用）。
  - 根因：`services/configuration_service.py::_build_zhiqiu_changes` 保存时写 `ZQ_ACCOUNTS_JSON` 并删除旧版 `ZQ_ACCOUNTS`，但 `data_layer/crawlers/zq/zhiqiu/account_manager.py::_load_config` 只读旧版 `ZQ_ACCOUNTS`、不认 JSON 格式 → 账号池为空 → 认证全失败 → 连续失败 10 次触发 `is_disabled`。
  - `account_manager.py` — `_load_config` 重构为优先解析 `ZQ_ACCOUNTS_JSON`（新增 `_load_accounts_from_env` / `_parse_accounts_json`），回退到 `ZQ_ACCOUNTS`，最后兜底 `config.yaml`，与 `ConfigurationService._parse_zhiqiu_accounts` 优先级对齐。
  - 恢复 `.env` 的 `ZQ_ACCOUNTS_JSON` 为完整 5 个账号（huangyongjia/zhanzhengkai/sunhaoxiang/majingyi/wanghao）。
  - 解禁重置 `.config_account_state.json`：5 个账号 `is_disabled=false`、`consecutive_failures=0`，保留历史统计。
  - `tests/unit/test_connectors/test_zq_account_manager.py` — 新增 14 个测试覆盖 JSON 解析、优先级、系统配置保存后往返闭环、解禁可租借。

### Fixed

- **全量 lint/mypy 债务清零**: 修复 44 个 mypy 类型错误、686 个 black 格式、27 个 isort 排序、11 个 ruff 错误。`mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/ services/` 现报 `Success: no issues found in 457 source files`。
  - `reporting/projects/generation.py` — 24 个 mypy 错误：ternary `isinstance` 守卫无法让 mypy 缩窄类型，拆成两步赋值 + 显式 `Dict[str, Any]` 注解（`report_defaults`/`source`/`market_field` 等）；`_semantic_similarity_scores` 返回类型 `List[float | None]` → `List[float]`。
  - `services/commentary_context_service.py` — 4 个 union-attr：`SectorChangeItem | dict` 联合类型上 `.get()` 调用加 `isinstance(item, dict)` 守卫。
  - `services/dashboard_service.py` — `params` 加 `dict[str, str | int]` 注解；`_previous_trading_date_yyyymmdd` 补 `@staticmethod`。
  - `services/crawl_feed_content_service.py` — `metadata` 加 `dict[str, Any]` 注解；`doc.source_url` 经 `str` 中间变量传入 `re.search`。
  - `services/configuration_service.py` — 删除 `ZhiQiuClient` 已移除的 `request_timeout`/`failure_dump_path` 参数。
  - `services/wind_realtime_workbook.py` — `_parse_float` 在 `float(value)` 前加 `isinstance` 守卫缩窄 `object` 类型。
  - `services/official_index_structure_ingestion.py` — `cleaned` 加 `dict[str, Any]` 注解。
  - `services/asset_search_index_service.py` — generator 函数 `return []` 改裸 `return`。
  - `services/commentary_draft_service.py` — `preferences.get("audience")` 改 `preferences.get("audience", "")` 避免 `str | None` 传入 `dict.get` key。
  - `data_layer/crawlers/akshare/board.py` — `assert _cache is not None` 移到 `_cache.fetched_at` 使用前。
  - `data_layer/adapters/pdf_adapter.py` — `pdf_files` 经 `list[Path | str | bytes]` 中间变量传入 `fetch_batch`（`list` 不协变）。
  - `data_layer/repositories/ingestion_repository.py` — `db_item.item_id` 经 `str()` 转换传入 `set.add`。
  - `data_layer/repositories/dashboard_data.py` — `_normalize_crawl_document_text` 返回类型 `Dict[str, str]` → `Dict[str, Any]`（含 `has_content: bool`）。
  - `pyproject.toml` — 新增 `black.extend-exclude`、`isort.extend_skip`、`ruff.extend-exclude` 排除 `backups/build/dist`。

- **实时监控数据源状态区分**: 数据源列表的状态圆点按是否已启动抓取区分颜色。
  - `app/web/static/js/monitor.js` — `monitorSourceButton` 新增 `running` 参数，依据 `lastCrawledAt` / `items` / `totalToday` 判定数据源是否已抓取到数据，未启动抓取的行圆点附加 `idle` class。
  - `app/web/static/style.css` — 新增 `.monitor-status-dot.idle` 样式（红色 `#ff453a`），已启动抓取保持绿色 `#30d158`，"全部来源"聚合行始终为绿色。

- **报告项目运行编排 seam**: 新增 `ReportProjectRunService`，把 `/api/report-projects/{slug}/render` 的 Word/PPT 生成编排从 FastAPI route 收拢到 reporting module，保持外部响应字段不变。
  - `reporting/projects/run.py` — 新增单次报告项目运行 module，统一解析报告周期、调用占位符生成、Word/PPT 投影、Word 表格/图表嵌入、run-log 写入和 warning 聚合。
  - `app/api/routes/report_projects.py` — `POST /render` 改为读取项目/config 后委托 `ReportProjectRunService`，route 只保留 HTTP 异常映射和响应模型转换。
  - `tests/unit/test_report_projects_api.py` — 新增 service 级测试，覆盖 Word 项目运行的占位符、run log、evidence、图表/表格元数据和 warning 聚合。

- **报告项目生成预检计划**: 新增 `CompiledReportPlan`，把 prompt / retrieval / deterministic 占位符就绪度从前端猜测升级为后端编译结果。
  - `reporting/projects/plan.py` — 新增生成计划 module，复用 defaults 合并、composite `llm_writing` retrieval 覆盖、keyword profile、prompt 解析和 retrieval config 规范化，输出报告周期、lookback、warnings 和每个占位符的 readiness。
  - `app/api/routes/report_projects.py` — `GET /api/report-projects/` 和 `GET /api/report-projects/{slug}` 响应新增 `compiled_plan`，供模板工作台生成前检查使用。
  - `app/web/static/js/templates.js` / `app/web/static/style.css` — 生成中心预检优先使用后端 `compiled_plan`，并按 Prompt 覆盖、Evidence 覆盖、输出资产三组展示检查结果；新增“优先处理”任务队列，把阻断/警告/建议按使用者下一步动作排列；Evidence 覆盖区展示生成前检索配置抽样，生成后可从 run log 显示真实 evidence 标题与命中词；首屏新增“本期设置”条，可直接调整报告日期、开始/结束日期、证据窗口和查看输出格式/最近版本；最近生成区新增“交付检查”卡，汇总生成段落、缺失段落、Evidence 总数、Warnings、空占位符和图表/表格状态。
  - `tests/unit/test_report_project_plan.py` / `tests/unit/test_report_template_workbench_frontend.py` — 覆盖 composite retrieval 继承、缺 prompt 预警、前端 preflight 接入、任务队列和 Evidence 抽样入口。

- **Fund Intelligence MVP backend slice**: 新增基金智能研究后端最小闭环，支持基金主数据、净值、持仓、经理任职的仓储访问，以及基金详情、单基金暴露和基金组合穿透 API。
  - `core/contracts/funds.py` — 新增基金主数据、净值、持仓、经理、收益风险指标、暴露项和组合穿透结果契约。
  - `data_layer/repositories/fund_repository.py` — 新增 `fund_master`、`fund_nav_daily`、`fund_holding_stock`、`fund_manager_tenure` MVP 表的 schema ensure、upsert 和查询方法。
  - `services/fund_intelligence_service.py` — 新增基金详情组装、NAV 收益风险指标计算、行业/股票/主题暴露聚合和组合加权穿透。
  - `app/api/routes/funds.py` / `app/api/main.py` — 新增 `/api/funds/{symbol}`、`/api/funds/{symbol}/exposure`、`/api/funds/portfolio/exposure` 和 `POST /api/funds/ingest`。
  - `app/web/templates/index.html` / `app/web/static/js/funds.js` / `app/web/static/style.css` — 新增基金情报前端入口、详情/持仓/暴露/组合穿透/结构化 rows 导入界面。
  - `tests/unit/test_fund_contracts.py` / `tests/unit/data_layer/repositories/test_fund_repository.py` / `tests/unit/test_fund_intelligence_service.py` / `tests/unit/test_fund_data_ingestion_service.py` / `tests/unit/test_funds_api.py` / `tests/unit/test_funds_frontend_static.py` — 补充基金契约、仓储、服务、API 和前端 wiring 覆盖。

- **指数结构数据库底座**: 新增中证、国证、恒生、Wind 发布指数的结构化存储基础，支持指数主数据、成分权重快照、个股所属指数反查、指数 ETF 产品和 ETF 日度规模/资金流指标落库。
  - `data_layer/repositories/models.py` — 新增 `IndexProviderDB`、`IndexMasterDB`、`IndexComponentSnapshotDB`、`ETFMasterDB`、`IndexETFLinkDB`、`ETFDailyMetricDB`。
  - `data_layer/repositories/market_data_repository.py` — 新增指数/ETF upsert 与查询方法；旧 `upsert_index_components()` 入参自动归一化后写入 `index_component_snapshot`。
  - `storage/migrations/versions/011_add_index_structure_tables.py` — 新增结构表迁移，并将旧 `index_component` 数据复制为 legacy snapshot。
  - `tests/unit/data_layer/repositories/test_market_data_repository.py` — 补充指数 provider/master、成分快照幂等、个股指数反查、ETF 链接和 ETF 指标 upsert 测试。

- **Wind 指数结构字段探针**: 新增固定 Excel 函数模板，用于后台静默验证指数全成分、成分权重、ETF 跟踪指数、净值、份额和规模等候选 Wind 字段。
  - `services/wind_index_structure_probe.py` — 生成 `AlphaFoundry_Wind_Index_Structure_Probe.xlsx`，维护 `FormulaCatalog`、`ProbeTargets`、`ProbeResults` 和 `Health`，支持隐藏 Excel 计算并读取缓存结果。
  - `services/wind_index_structure_ingestion.py` — 将成功探针结果写入指数主表、ETF 主表、指数 ETF 关系和 ETF 日度指标；当前已验证 `fund_trackindexcode`、`nav`、`unit_total`、`netasset_total` / `fund_fundscale`。
  - `scripts/run_wind_index_structure_probe.py` — 新增 CLI，可生成模板、可选 `--prime` 隐藏刷新、可选 `--read` 输出 JSON 结果、可选 `--persist` 写入结构表；`--skip-build` 用于读取/落库现有缓存，避免覆盖刚刷新的工作簿。
  - `tests/unit/test_wind_index_structure_probe.py` / `tests/unit/test_wind_index_structure_ingestion.py` — 验证探针工作簿结构、候选公式、结果解析和落库映射。

- **中证/国证官方成分股摄入**: 新增官方源成分股补数任务，通过 AKShare 包装的中证/国证官网下载接口写入 `index_component_snapshot`，并在调用时临时绕开不可用代理环境变量。
  - `services/official_index_structure_ingestion.py` — 归一化中证 `index_stock_cons_weight_csindex` 和国证 `index_detail_hist_cni` 返回列，按权重生成 rank，写入指数主表与完整成分快照；新增 `discover_official_index_codes()` 从官方 catalog 发现 active 指数列表。
  - `services/market_data_scheduler.py` — 新增每日 18:10 指数结构日更任务，默认从中证/国证 official catalog 发现 active 指数代码并限量批量写入，状态统计记录最近运行和错误数。
  - `workers/market_data_scheduler_worker.py` — standalone worker 默认关闭旧 gap check 回补链路，保留日行情与指数结构定时任务，避免启动后立即进入不稳定回补流程。
  - `scripts/run_official_index_structure_ingestion.py` — 新增后台脚本，默认静默摄入中证 `000300/000905/000852` 与国证 `399001/399006`，支持 `--provider`、重复 `--index-code`、`--discover-active` 和 `--max-count`。
  - `tests/unit/test_official_index_structure_ingestion.py` — 覆盖中证权重快照、国证成分落库和个股指数反查。
  - `tests/unit/test_market_data_scheduler_index_structure.py` / `tests/unit/test_official_index_structure_script.py` — 覆盖调度器批量 job 和脚本 active discovery 参数解析。

- **Tauri 桌面壳 Phase 1**: 新增 AlphaFoundry 桌面化骨架，保留现有 FastAPI Web 工作台不变，通过 Tauri 外壳承载本地 `127.0.0.1:8765` 服务，并为后续 macOS/Windows/Linux 安装包、sidecar 后端和自动更新发布链路铺路。
  - `scripts/desktop/backend_launcher.py` — 新增桌面后端启动器，负责以桌面端默认端口运行 `app.api.main:app` 并写入 `logs/desktop-backend.log`。
  - `src-tauri/` / `package.json` — 新增 Tauri 2 配置、Rust shell、sidecar 进程管理骨架和桌面构建命令。
  - `desktop/dist/` — 新增桌面启动页，轮询 `/health` 后跳转到现有工作台。
  - `docs/desktop_packaging.md` / `docs/superpowers/plans/2026-06-16-desktop-shell-phase-1.md` / `tests/unit/test_desktop_shell_scaffold.py` — 记录桌面打包路线并补充静态 wiring 测试。

- **Tauri 桌面发布流水线 Phase 2**: 新增 macOS/Windows/Linux GitHub Actions draft release 工作流，并将 Python sidecar 构建改为跨平台脚本。
  - `.github/workflows/desktop-release.yml` — 新增手动触发 / `v*` tag 触发的桌面发布流水线，按 macOS ARM、Windows x64、Linux x64 矩阵构建并上传 Tauri bundle。
  - `scripts/desktop/build_sidecar.py` / `prepare_tauri_sidecar.py` / `write_tauri_release_config.py` — 新增跨平台 sidecar 构建、Tauri externalBin 准备、updater release config 生成脚本；`build_sidecar.sh` 保留为本地 shell 入口。
  - `package.json` / `docs/desktop_packaging.md` / `tests/unit/test_desktop_shell_scaffold.py` — 补充桌面 sidecar、release config、发布构建命令、CI Secrets 文档和静态回归测试。

- **报告项目工作台配置驱动生成**: `report_projects` 工作台从静态占位符渲染升级为项目配置驱动生成，支持源码保存、evidence 检索、LLM 生成、图表嵌入、运行日志和 Word HTML 预览。
  - `app/api/routes/report_projects.py` — 新增 `PUT /api/report-projects/{slug}/source` 保存 `section_config.yaml` / `prompt_templates.md`；`POST /render` 默认执行 `section_config.yaml` + `prompt_templates.md` 的 evidence-grounded 生成；响应增加 `preview_url`、生成占位符数、evidence 数和 warnings；新增 `GET /preview/{file_name}` 轻量 DOCX HTML 预览；run log 记录本期报告周期。
  - `reporting/projects/generation.py` — 新增项目级报告生成服务，解析 Markdown Prompt 模板二级标题、提取 `检索 Query` / `写作要求`、从 `ingestion_queue_item` 和 `canonical_event` 检索证据，并通过 `ModelGatewayImpl` reporting/default task route 生成 Word 占位符正文；`type: report_period` 占位符由生成器统一计算，开始日期为报告日所在周周一，结束日期为报告日；`type: composite_market_review` 支持先从 `周报数据.xlsx` 生成确定性的 A 股指数涨跌和成交额句子，再只让模型基于 evidence 生成市场热点归纳；独立 section 默认使用 4 路有界并行生成，最终结果仍按配置顺序写入 run log 和 Word。
  - `reporting/projects/generation.py` / `report_projects/华安ETF周报/config/section_config.yaml` / `report_projects/华安ETF周报/config/prompt_templates.md` — 明确 Prompt 与参数分工：`section_config.yaml` 的 `defaults.validators` / `defaults.retrieval` 负责报告级硬性生成约束、hybrid/RRF 检索和 LLM rerank；单个占位符只保留目标字数、最少新闻条数、检索关键词、Excel/static 来源等差异项，最终模型消息统一渲染这些规则；`prompt_templates.md` 只保留检索 Query、写作要求和写作格式，不再重复写字数、禁用词等硬参数。
  - `reporting/projects/generation.py` / `app/api/routes/report_projects.py` — 接入 Phase 1 关键词检索配置：每个 section 可配置 `retrieval.top_k`、`candidate_k`、`must_any`、`exclude`、`source_types` 和 `min_keyword_score`，生成前先过滤、评分、排序 evidence；run log 记录每段的检索配置、命中词和 keyword score，并提供 `run_log_url` 供前端调试。
  - `reporting/projects/keyword_profiles.py` / `reporting/projects/keyword_profiles.json` / `app/web/static/js/templates.js` — 将旧财联社筛选 `params.json` 升级为内置 `keyword_profiles`，新模板占位符按名称或显式 `retrieval.keyword_profile` 自动继承检索关键词；未知占位符生成可后续维护的关键词草稿。前端将机器字段 `query_terms.must_any` 收敛为业务字段 `keyword_profile` + `keywords`，并不再默认展示“排除词”。
  - `reporting/projects/generation.py` / `report_projects/华安ETF周报/config/section_config.yaml` — 接入 Phase 2 混合召回：`retrieval.mode: hybrid` 会在关键词候选外追加近期语义候选，使用本地 n-gram 语义相似度与 RRF 融合排序；华安 ETF 周报的 `A股市场回顾`、`航天`、`电力设备新能源` 已切换为 hybrid，并配置 keyword/semantic 权重。
  - `reporting/projects/generation.py` / `report_projects/华安ETF周报/config/section_config.yaml` — 接入 Phase 3 LLM rerank：`retrieval.rerank.enabled: true` 时先保留 `rerank.top_n` 条候选，再通过 reporting/default 模型路由要求模型输出 JSON 排序，最终进入写作 prompt 的 evidence 会记录 `rerank_score`、`rerank_rank` 和 `rerank_reason`；华安 ETF 周报的三个重点 section 已启用 DeepSeek/LLM rerank。
  - `reporting/projects/chart_generation.py` — 新增 Excel chart cache / worksheet 缓存读取、matplotlib 图表渲染和 DOCX 图片嵌入服务，支持 media 替换和 chart drawing 转图片。
  - `reporting/projects/table_generation.py` / `reporting/projections/word.py` / `app/api/routes/report_projects.py` — 新增项目级 Excel 表格确定性生成：`tables:` 配置可从项目 `data/` 下的 Excel 读取指定 sheet、列和过滤条件，生成 Word `TableSpec`，并以 `{{占位符}}` 原位替换为真实 Word 表格；若模板没有占位符，则回退替换同名标题后的旧表格。华安 ETF 周报的“下周全球投资日历”已绑定 `全球经济日历.xlsx` 的 `经济数据` sheet。
  - `scripts/replace_huaan_word_charts_office.py` / `scripts/merge_huaan_layout_with_native_charts.py` / `report_projects/华安ETF周报/templates/report_template.docx` — 华安 ETF 周报三张图通过 Excel/Word 原生复制粘贴切换为可编辑 Word chart，并将 chart parts 合并回原 Word 模板版式，保留页眉页脚；生成配置改为 `replace.kind: native_chart`，后续生成只同步 Excel chart XML，不再降级为 PNG。
  - `app/web/templates/index.html` / `app/web/static/js/templates.js` / `app/web/static/style.css` — 模板工作台拆分 YAML 占位符映射与 Markdown Prompt 源码视图，改为按 Word 占位符逐项展示配置详情；右侧表单只维护占位符差异项（类型、字数、最少新闻条数、关键词 Profile、检索关键词、报告周期或 Excel/static 来源），报告级硬性生成约束、检索参数和 rerank 策略由 `defaults` 统一继承；源码区只显示当前 YAML 片段 / Prompt 模板作为对照；生成后显示下载、预览和 Evidence 检索调试，包含命中词、关键词分、语义分、融合分、检索 rank、rerank 分数和重排理由；上传按钮移到模板页顶部工具栏。
  - `report_projects/华安ETF周报/config/section_config.yaml` — 切换为 `placeholders:` + `charts:` 配置，绑定 Word 占位符、报告周期占位符、A 股市场回顾复合生成、内置检索 Query Prompt 模板和黄金/原油/行业图表替换规则。
  - `report_projects/华安ETF周报/config/section_config.yaml` — 所有 `type: prompt` 占位符补齐主题 `keyword_profile` 和 `keywords` 检索关键词，避免未配置段落因召回过宽或无 evidence 而空缺；公共 hybrid 检索、RRF 融合和 LLM rerank 已收敛到报告级 `defaults.retrieval`。
  - `report_projects/华安ETF周报/config/prompt_templates.md` — 重写为 Markdown Prompt 模板库，每个 `##` 标题对应一个 Word 占位符/Prompt 模板，并内置检索 Query。
  - `tests/unit/test_report_projects_api.py` / `tests/unit/test_report_template_workbench_frontend.py` / `tests/unit/test_report_project_chart_generation.py` / `tests/unit/test_word_projection.py` — 补充源码保存、占位符顺序、并行生成、配置生成、run-log、预览、图表读取/嵌入、占位符包含关系替换和前端静态回归测试。

### Fixed

- **Worker 监控孤儿 PID 误计数**: 实时监控把残留的 `logs/knowledge_worker*.pid` 文件全部算作存活 worker，导致显示 3 个 `knowledge_worker` 而实际进程早已退出（强杀/未走 shutdown 路径时 `_remove_pid()` 不会执行）。
  - `workers/knowledge_worker.py` — `get_all_worker_statuses()` 检测到 PID 文件存在但进程已死亡时，自动删除孤儿 PID 文件并跳过，不再返回死进程条目；所有调用方（CLI 启停、`/api/system/workers/status`）本就按 `alive=True` 过滤，行为不受影响。
  - `tests/unit/workers/test_knowledge_worker.py` — 新增 `TestWorkerStatusSelfHealing`，覆盖孤儿文件清理、存活 worker 保留、混合场景。
- **Knowledge Worker watchdog 自动启动**: desktop backend launcher 改为启动 watchdog 进程，由 watchdog 拉起并守护 `knowledge_worker`，worker 崩溃时按指数退避自动重启（上限 10 次/小时），避免队列消费因 worker 单次崩溃长时间中断。
  - `workers/watchdog.py` — 重写：支持 frozen 模式（复用 exe + `ALPHAFOUNDRY_WORKER_MODE=1` 启动 worker 子进程，而非 `python -m`）、新增 `_build_worker_cmd`/`_build_worker_env`、`--worker-id` 透传、PID 文件管理、改用 `core.observability` 日志。
  - `workers/knowledge_worker.py` — `_parse_args()` 在 `--worker-id` 缺省时 fallback 到 `ALPHAFOUNDRY_WORKER_ID` 环境变量，使 frozen 模式下 watchdog 注入的 worker_id 能被读取。
  - `scripts/desktop/backend_launcher.py` — `_start_knowledge_worker()` 改为启动 watchdog（frozen: `ALPHAFOUNDRY_WATCHDOG_MODE=1`；dev: `python -m workers.watchdog`）；`__main__` 入口新增 watchdog 模式分支；终止逻辑更新为终止 watchdog（watchdog 信号 handler 负责终止 worker，孤儿残留由 PID 自愈兜底）。
  - `tests/unit/workers/test_watchdog.py` — 新增 `TestWatchdogCmdBuild`，覆盖 frozen/dev 模式命令构造、`ALPHAFOUNDRY_WORKER_MODE`/`ALPHAFOUNDRY_WORKER_ID` 环境变量注入。
  - `tests/unit/workers/test_knowledge_worker.py` — 新增 `TestParseArgsWorkerId`，覆盖 worker_id 从环境变量读取、CLI 优先、缺省、非法值忽略。
- **资产观察首屏加载过慢**: 资产分析页首次请求从全历史改为近一年，并 bump `asset.js` 静态资源版本，保留 K 线“全部”按钮供用户主动查看全历史，避免首屏等待超大分析响应时看起来像页面打不开。
- **资产观察搜索被 CDN 阻塞**: Chart.js、ECharts 和 D3 改为异步加载，避免 `cdn.jsdelivr.net` 超时阻塞本地工作台启动和资产搜索；ECharts 未就绪时 K 线区域显示“图表资源仍在加载，基础数据已显示”。
- **资产观察搜索后卡住**: `MultiSourceCoordinator` 在本地行情缓存只缺当天少量尾部数据时直接返回最近缓存，避免 `688981.SH` 等资产进入外部行情实时补数链路后被代理、BaoStock 或 Wind 超时拖住。
- **实时行情补齐**: `CjpyAdapter` 调用天软接口时临时绕开本机代理环境变量并修复 logger 初始化；`WindAdapter` 新增 WSS `rt_*` 个股实时行情读取，指数行情也改用 Wind 实时字段；资产卡片按 Cjpy → Wind Excel → 本地缓存短窗口降级，实时源可快速返回时使用实时数据，否则首屏立即回退缓存。

- **Word 占位符包含关系替换**: `WordProjection.save_from_template()` 改为长占位符优先，并限制裸占位符只在整段文本等于占位符时替换，避免 `{{黄金市场回顾}}` 被 `{{黄金}}` / `市场回顾` 这类短占位符提前拆坏。

- **Full gate remaining-risk cleanup**: 清理文档同步后的剩余门禁风险，消除 full mypy 报告的类型问题并修正静态资源版本回归断言。
  - `cognitive_agents/workflow.py` — `AgentWorkflowRunner` 接受协议型 `AgentFactoryLike`，支持资产委员会的 deterministic agents 复用 staged workflow。
  - `services/asset_agent_committee_service.py` — `AssetAnalysisCardService` protocol 对齐实际 `generate_analysis_card()` 可选参数。
  - `data_layer/repositories/agent_view_repository.py` — 在 JSONB/ORM 边界显式收窄 `view_metadata` 类型。
  - `reporting/projects/chart_generation.py` / `reporting/projects/generation.py` — 对配置字典、整数选项、图表维度和 worksheet 数值行做显式收窄。
  - `signal_lab/labels/event_driven.py` — 使用 `Series.mask()` 保持事件标签分类语义并通过 pandas 类型检查。
  - `tests/unit/test_asset_kline_interaction.py` — 更新 `app.js` bundle 版本断言到 `20250606e`。
- **Connector-first ingestion architecture hardening**: all enabled `data_sources` now point to `BaseConnector` subclasses with explicit `connector_dataset` and `pipeline_kind`; `CrawlOrchestrator` uses connector-first execution, document sources enqueue per-document records for `KnowledgeWorker`, and `source_document` / `document_v1` persistence is completed before queue items are marked done.
  - `DocumentRepositoryImpl` now updates `content_hash`, `parser_version`, and `object_uri` on existing `source_document` rows.
  - `KnowledgeWorker` stuck-item recovery now handles legacy `processing` rows where `processed_at` is NULL.
  - CLI/docs examples use the actual CLS dataset `telegram`.
  - `SourceSpec.connector_class` is now the canonical connector path; legacy `adapter_class` remains as a compatibility alias and is normalized in `SourceSpec.__post_init__()`.
  - Full-gate isolation now disables local embedding model loading during tests by default and skips live API/E2E smoke tests unless `ALPHAFOUNDRY_RUN_LIVE_API_TESTS=1` or `ALPHAFOUNDRY_RUN_LIVE_E2E_TESTS=1` is set.
  - Local sentence-transformers loading is now local-first: `ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH` points to a downloaded model directory, Hugging Face model ids are cache-only by default, and `ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD=1` is required for first-time downloads.
  - `pyproject.toml` replaces the package-level mypy `ignore_errors` baseline with an explicit error-code debt list plus `ignore_missing_imports` for third-party stub gaps, so mypy still walks every checked project source file.
  - Script-level mypy debt was reduced for operational recovery/data seeding scripts: backup restore pipes now narrow subprocess streams before use, object backfill/import paths coerce ORM fields at runtime boundaries, derived-state rebuild supplies complete timing model score fields, and factor seeding normalizes pandas/DB scalars before arithmetic. `mypy --explicit-package-bases app cognitive_agents connectors core data_layer ingestion knowledge_layer reporting services signal_lab storage workers tests scripts` now passes across 669 files.

- **crawl_scheduler 诊断与恢复**: 调度器于 2026-05-26 收到 shutdown signal 后停止运行，宕机约 9 天（5/26→6/4）。根因为调度器缺乏持久化进程管理，手动 kill 或系统事件导致退出后无法自动恢复。2026-06-04 手动重启 `python3 -m workers.crawl_scheduler_worker`（PID 75941），启动后自动执行 gap backfill，所有新闻源（CLS/CNStock/ZQ）已恢复数据采集。
  - **CLS "不再更新"根因确认**: CLS 爬虫代码中已有 `updateTelegraphList` 404 的 workaround（`_crawl_incremental()` 降级到稳定历史 API `POST /api/sw`）。CLS 数据中断的真实原因是调度器宕机，而非 API 问题。

- **CNStock 爬虫 WAF 绕过修复**: 中国证券网在 2026年5月升级了 WAF 验证，导致 `requests` 直接调用 API 返回 `10304`（"未登录"）。修复方案使用 Playwright 无头浏览器导航到频道页面，拦截页面自身 JavaScript 发起的 API 响应来获取数据。
  - 快讯（node_id=10004）：通过提取页面 `__NEXT_DATA__` 中的 SSR 数据获取
  - 常规频道（证券/金融/公司等）：通过拦截页面 JS 发起的 `channelNewsList` API 响应获取
  - 支持跨频道浏览器复用，减少资源消耗
  - 保留 `requests` 方案作为 Playwright 不可用时的回退
  - `data_layer/crawlers/cnstock/cnstock.py` — 新增 `_crawl_channel_via_playwright()`、`_extract_ssr_data()`、`_create_playwright_browser()` 方法；重构 `crawl_news_list()` 支持双路径

### Added

- **Wind 风格 K 线终端面板**: 资产分析页 K 线区域改为高密度终端式布局，保留时间范围和均线切换，新增顶部行情信息条、左侧竖向指标栏、右侧筹码分布窄栏；筹码图明确标注筹码峰、筹码峰上界、筹码峰下界、现价和均本。
  - `app/web/templates/index.html` — K 线区域重排为终端工具栏、行情条、指标栏、主图和筹码侧栏结构。
  - `app/web/static/style.css` — 新增 `.kline-terminal-*` 终端式布局样式，筹码统计区改为紧凑表格样式。
  - `app/web/static/js/asset.js` — 行情条复用资产分析数据；K 线图改为固定暗色终端配色；筹码图增加上/下边界清晰 `markLine` 标签并按现价上下分色。
  - 迭代修正：K 线默认请求全量数据，不再显示 1月/3月/6月等截断范围按钮；各副图直接显示 BOLL、VOL、MACD、KDJ、RSI 标题和值；筹码分布高度对齐主 K 线价格区，并按当前可见区间起点到当前激活 K 线动态重算普通筹码分布，鼠标移出后回到当前可见最右侧交易日。
  - 可视化细节修正：MA60 改为更醒目的绿色以区别 MA250；顶部行情条的开/高/低/均按相对昨收动态显示红绿；BOLL 上/MID/下轨调整为 Wind 风格的黄、浅灰、品红实线配色。
  - 交互响应修正：普通筹码跟随鼠标切换 K 线时不再使用 120ms 定时防抖，改为下一帧合并渲染，减少筹码图滞后感。
  - 继续完善：新增 MA120、MA250 均线开关和前端均线计算；日 K 初始窗口只展示最近 120 根 K 线，保留滑块查看更早数据；新增周 K、月 K 前端聚合切换；左侧竖向标签按主图/成交量/MACD/KDJ/RSI 分区比例对齐。
  - 覆盖线和筹码图修正：筹码分布从分类价格桶改为连续价格轴自定义横条，并与主 K 线价格轴共享 y 轴范围，现价/均本/筹码峰/上界/下界位置与 K 线价格位置对齐；右上角 MA 按钮使用对应均线颜色；覆盖线切换改为 MA / BOLL / 裸K 三种互斥模式。
  - 最新交互修正：K 线缩放或拖动后按当前可见 K 线和当前覆盖模式自动重算主图价格轴，避免放大全量区间时蜡烛线超出画布；主图左上角 MA/BOLL 数值跟随鼠标所在交易日更新并按对应线条颜色显示；右上角覆盖线控制收敛为 `MA均线`、`BOLL布林带`、`裸K` 三个模式按钮。
  - 指标读数修正：统一 MA250 线条、tooltip 和主图读数颜色；VOL、MACD、KDJ、RSI 副图标题值随鼠标所在 K 线位置同步更新。

- **K线技术指标增强 (KDJ/RSI/筹码峰)**: 资产分析页 K 线图从 3 面板升级为 5 面板专业图表，新增筹码分布独立图表
  - `services/asset_analysis_service.py` — `_build_price_bars_from_dataframe()` 新增 KDJ(9,3,3) 和 RSI(14) 全序列计算，填充每个 `PriceBar` 的 `kdj_k`/`kdj_d`/`kdj_j`/`rsi` 字段；新增 `_calculate_chip_distribution()` 基于输入 K 线区间的价格-成交量分布计算高密度普通筹码（筹码集中度、平均持仓成本、筹码峰价格）
  - `core/contracts/assets.py` — 新增 `ChipDistributionPoint` 模型（price/volume/concentration_pct）；`AssetAnalysisCard` 新增 `chip_distribution`、`avg_cost`、`chip_peak_price` 字段
  - `app/web/static/js/asset.js` — K 线图 ECharts 从 3 面板（K 线+成交量 40%+9%、MACD 9%）扩展为 5 面板（+KDJ 10%、+RSI 9%），所有面板共享 `dataZoom` 联动缩放；KDJ 面板显示 K/D/J 三线及 20/50/80 超买超卖参考线；RSI 面板显示 RSI 线及 30/70 参考线；新增筹码分布水平柱状图独立 ECharts 实例，带现价和均本 `markLine` 标注
  - `app/web/templates/index.html` — 新增筹码分布面板，显示筹码峰价格、平均成本、获利/套牢比例
  - `app/web/static/style.css` — 新增 `.chip-distribution-card`、`.chip-stats` 样式

- **宏观敏感性计算**: 通过时间序列回归计算个股对宏观因子的敏感度
  - `services/macro_sensitivity.py` — 新增 `MacroSensitivityCalculator`，通过 Cjpy 批量获取标的+5 个代理 ETF 日线，用 `numpy.linalg.lstsq` 执行 OLS 回归，返回 `interest_rate_sensitivity`、`inflation_sensitivity` 等 5 个 Beta 系数
  - `services/asset_analysis_service.py` — `_enrich_from_coordinator()` 中集成 `_compute_macro_sensitivity()`，替代之前的空 `MacroSensitivity()`
  - 数据源：Cjpy 天软批量行情（`rate="不复权"`），一次调用包含所有代码，速度约 0.5s
  - 代理 ETF 映射：利率=511010.SH（国债ETF）、通胀=510880.SH（红利ETF）、汇率=510050.SH（上证50ETF）、商品=159980.SZ（有色ETF）、流动性=510300.SH（沪深300ETF）
  - 错误处理：Cjpy 不可用/数据不足/回归异常时均返回空 `MacroSensitivity()`

- **前十大股东明细**: 实现 4 级数据源优先级，支持逐项股东名称
  - `data_layer/adapters/akshare_adapter.py` — `fetch_top_shareholders()` 从 mock 数据改为真实 AKShare `stock_gdfx_top_10_em` 接口，返回股东名称/持股比例/数量/类型/排名
  - `data_layer/adapters/wind/formulas.py` — 新增 `s_info_top10_holdername`、`s_info_top10_holderratio`、`s_info_top10_holderquantity` 三个按排名公式
  - `data_layer/adapters/wind/wind_adapter.py` — 新增 `fetch_top10_holder_details()` 遍历排名 1-10 调用 Wind Excel，返回含股东名称的逐项明细
  - `services/asset_analysis_service.py` — `_fill_shareholder_data()` 改为 async，4 级优先级：StockShareholderDB → Wind 逐项 → Wind 聚合 → AKShare 开源数据
  - `tests/unit/test_asset_analysis_service.py` — 修复测试为 async，增加新 fallback 路径 mock

- **近期事件多源 fallback**: `_fill_recent_events()` 3 级数据源
  - `services/asset_analysis_service.py` — 新增 CanonicalEvent (Tier 2) 和 AKShare 个股公告 (Tier 3) fallback；新增 `_map_to_event_impact()` 静态方法统一映射
  - `data_layer/adapters/akshare/akshare_client.py` — 新增 `get_stock_notice_report()` 封装 `ak.stock_individual_notice_report`

- **ETF 搜索支持**: `AssetSearchIndexService` 新增 ETF 候选源
  - `services/asset_search_index_service.py` — 新增模块级 ETF 缓存（AKShare `fund_etf_spot_em()`，24h TTL），`_fund_candidates()` 方法，`_etf_suffix()` 代码到交易所映射
  - `data_layer/normalizers/symbol.py` — `normalize_a_share_symbol` 新增 ETF 前缀识别：159/16/399→SZ，51/58→SH
  - 搜索 `159267` 可精确匹配 `159267.SZ 航天ETF华安`

### Changed

- **资产分析 K 线交互升级**: 资产分析页 K 线图从静态 Canvas 升级为 ECharts 专业图表
  - `app/web/static/js/asset.js` — 新增 K 线/成交量/MACD 多面板渲染，支持 `dataZoom` 缩放、拖动平移、十字光标 tooltip、时间范围切换和 MA/BOLL 显隐
  - `app/api/routes/assets.py` / `services/asset_analysis_service.py` — `analysis-card` 支持 `time_range` 参数（`1M`/`3M`/`6M`/`1Y`/`2Y`/`3Y`/`5Y`/`ALL`）
  - `core/contracts/assets.py` — `PriceBar` 补充 BOLL、MACD、VWAP、涨跌幅和振幅字段，避免技术指标在 Pydantic 序列化时丢失
  - `tests/unit/test_asset_analysis_service.py` — 增加时间范围透传和技术指标字段保留回归测试
- **资产分析服务数据填充**: `AssetAnalysisService._enrich_from_coordinator()` 实现 Phase 2-4 数据填充
  - `_fill_industry_data()` — 从 StockMasterDB / Wind 填充行业分类
  - `_fill_shareholder_data()` — 从 StockShareholderDB 填充前十大股东
  - `_fill_recent_events()` — 从 DocumentEventV1DB 填充近期事件（按 subject_entity 匹配，最多 20 条）
  - 宏观敏感性通过 Cjpy + OLS 回归实现实时计算（详见新增 Added 中"宏观敏感性计算"）
	- **资产分析 Wind 直连补齐**: 服务端用 Wind Excel 实时数据补齐数据库空字段（Phase 1-3）
	  - `data_layer/adapters/wind/wind_adapter.py` — 新增 `fetch_market_snapshot()` 轻量市场快照（收盘价、换手率、PE/PB/PCF、总股本）
	  - `services/asset_analysis_service.py` — 新增 `_fill_wind_market_snapshot()` 补齐估值/换手率/市值；`_fill_industry_data()` 行业 level2/3 缺失时 Wind fallback；`_fill_shareholder_data()` 股东表空时 Wind 聚合 fallback
	  - `services/asset_analysis_service.py` — 新增 `_get_available_wind_adapter()` 懒初始化+缓存；`_fetch_wind_price_bars()` 复用该方法去重
	  - `_build_basic_info()` stock 和 fallback 分支从 valuation dict 读取 `total_shares`/`market_cap`
	  - `tests/unit/test_asset_analysis_service.py` — 新增 3 个测试 + 修复时间依赖测试

### Fixed

- **Wind Excel `execute_batch` 无限轮询修复**: `data_layer/adapters/wind/client.py` — `execute_batch()` 将 Excel 错误值（#N/A, #VALUE! 等）视为已完成结果而非"未就绪"状态，防止轮询循环无限等待；最终结果收集时 None=超时、error string=Wind 错误、其他=有效值
- **Wind Excel COM 阻塞事件循环修复**: `services/asset_analysis_service.py` — `fetch_top10_holder_details` 调用包装在 `loop.run_in_executor` + `asyncio.wait_for(timeout=30.0)` 中，防止同步 Excel COM 调用阻塞整个 asyncio 事件循环
- **筹码分布 markLine 显示修复**: `app/web/static/js/asset.js` — 筹码峰图表从不可见的 `graphic` 元素改为 ECharts `markLine`，新增 `closestBucketPrice()` 辅助函数匹配最近价格桶，现价和均本线正确显示
- **Mypy 类型注解修复**: 修复 6 个文件的 mypy `no-untyped-def` 错误
  - `app/api/main.py` — 添加 `startup()`, `shutdown()`, `get_response()`, `index()`, `health_check()` 返回类型注解
  - `app/api/routes/ingestion_queue.py` — 添加 5 个路由处理器返回类型，`get_recent()` 使用 `cast()`
  - `app/api/routes/scenarios.py` — 添加路由处理器返回类型
  - `app/api/routes/event_ingestion.py` — 添加 TypedDict 响应类型，`db_session` 参数注入
  - `app/cli/main.py` — 修复 `log_path` 类型从 `Path` 到 `str`
  - `app/cli/commands/analyze.py` — `get_db()`→`db_session` 上下文管理器，`asyncio.run()` 包裹异步调用，移除不存在的 `list_available_assets()` 调用，重构内联 MarkdownProjection 避免类型重赋值
- **EventAutoSignalGenerator 审查修复**:
  - `data_layer/repositories/event_repository.py` — `list_approved_pending_signal` NULL coalesce 修复（`func.coalesce(signal_generated, false()).is_(false())`）
  - `services/event_auto_signal_generator.py` — `__enter__`/`__exit__` session 生命周期管理，`model_dump()`+重构替代 `model_copy(update=...)` 以触发 Pydantic 验证
- **CLI analyze 测试修复**: `tests/unit/test_cli_analyze.py` — 替换 `get_db`→`db_session`，添加 `asyncio.run` mock，修复 MarkdownProjection 内联构造后的 mock 断言

- **zhiqiu_wechat / zhiqiu_transcript 绕过 IngestionQueue**: 公众号和纪要内容抓取后未进入 LLM 提取管道
  - 根因: `CrawlerIngestionBridge.SOURCE_TYPE_TO_CATEGORY` 将 `zhiqiu_wechat` → `"wechat"`、`zhiqiu_transcript` → `"transcript"`，但 `DocumentEnvelope.source_type` 的 Pydantic Literal 不包含这两个值，导致 `ValidationError` 被 `_enqueue_items()` 的 `except Exception` 静默吞掉
  - `core/contracts/documents.py` — `DocumentEnvelope.source_type` Literal 增加 `"wechat"` 和 `"transcript"`
  - `data_sources/zhiqiu_wechat.py` / `data_sources/zhiqiu_reports.py` / `data_sources/zhiqiu_transcript.py` — 后续已统一切换为 `connectors.document.zq.ZQDocumentConnector`，由 connector-first 路径保留单文档粒度并进入 `KnowledgeWorker`
- **Scheduler 启动回补 ZQ 爬虫卡住**: ZQ 爬虫在 `_startup_gap_backfill` 阶段挂起导致 scheduler 无法开始正常调度
  - `workers/crawl_scheduler_worker.py` — 启动回补改为 `asyncio.create_task()` 异步后台任务，不再阻塞 scheduler 主循环；`_startup_gap_backfill` 增加 900s 全局超时 (`asyncio.wait(timeout=...)`)；`ThreadPoolExecutor` 使用 `shutdown(wait=False)` 避免等待卡死线程；线程池上限从 `len(source_types)` 改为 `min(len(source_types), 8)`
  - `services/crawl_scheduler.py` — `check_and_backfill_gap()` 中阻塞的 `orchestrator.backfill_source()` 改为 `await loop.run_in_executor(None, lambda: ...)`，让 per-source 600s 超时可以真正生效（之前 event loop 被同步 I/O 卡住无法处理取消信号）
- **Mypy 错误修复**: 修复合同文件中的 Pydantic `default_factory` 类型签名
  - `core/contracts/retrieval.py` — 修复 `default_factory=ModelClass` → `default_factory=lambda: ModelClass()`（或 `# type: ignore[arg-type]`），Profile 工厂函数添加 `min_source_reliability=None, available_time_cutoff=None`
  - `core/contracts/assets.py` — 修复 `default_factory=dict` → `default_factory=lambda: {}`（Optional union 类型字段）
  - `core/contracts/documents_v1.py` — 修复 6 处 `default_factory=ModelClass` → `default_factory=lambda: ModelClass()`
  - `core/contracts/ingestion_record.py` — 修复 `default_factory=IngestionStats` → `default_factory=lambda: IngestionStats()`
  - `core/contracts/outcome_journal.py` — 修复 `default_factory=list` → `default_factory=lambda: []`（Optional 类型字段）

### Changed

- **Cninfo (巨潮资讯网) 数据源重构**: Phase 1 直接 HTTP 实现升级为完整的三层架构
  - `data_layer/crawlers/cninfo/cninfo.py` — **新建**：CninfoCrawler 爬虫类，从 Connector 层提取 HTTP 逻辑（session 管理、分页、限速）
  - `data_layer/adapters/cninfo_adapter.py` — **新建**：CninfoAdapter，包装 Crawler 输出为 DocumentEnvelope
  - `connectors/document/cninfo.py` — 重构为 wrapper-first 模式，委托 CninfoAdapter
  - `data_layer/adapters/__init__.py` — 导出 CninfoAdapter
  - `tests/unit/test_connectors/test_cninfo_connector.py` — **新建**：13 个单元测试覆盖完整生命周期
- **Connector fallback 路由修复**: `SourceSpec` 补齐 `fallback_group` / `fallback_priority`，并新增 `get_fallback_groups()` 供 `DatasetRouter` 构建多源降级链
  - `core/source_registry.py` — `SourceSpec` 接受 data_sources 中已声明的 fallback 元数据，按优先级排序返回 fallback groups
  - `core/connectors/registry.py` — `DatasetRouter.build()` 对输入 spec 再按 `fallback_priority` 排序，避免依赖调用方顺序
  - `tests/unit/test_connectors/test_registry.py` — 新增 fallback 链顺序回归测试
- **Wind Excel 自动启动回归覆盖**: 验证没有运行中的 Excel 时 `WindExcelClient._connect()` 会主动启动 Excel，而不是跳过或 mock 掉真实行为
  - `tests/unit/test_wind_adapter.py` — 新增无运行实例时调用 `xw.App(visible=False, add_book=True)` 的回归测试
- **文档重构**: 更新所有 markdown 文档以反映 Connector 架构
  - `docs/modules/core_connectors.md` — **新建**：完整的连接器子系统文档
  - `docs/ARCHITECTURE.md` — 核心层增加 `core/connectors/`，数据层增加 `connectors/` 连接器实现，更新"如何添加新数据源"章节
  - `docs/FILE_GUIDE.md` — 新增 `core/connectors/` 和 `connectors/` 目录条目，目录导航增加连接器章节
  - `docs/DATA_SOURCES.md` — 更新数据源表格，适配器→连接器列名，代码示例改为 Connector 路径
  - `docs/DEVELOPMENT_MAP.md` — 新增子系统 #19 "Connector System"
  - `docs/modules/` — 更新 8 个模块文档以反映连接器架构变更
  - `docs/generated/py_file_index.md` — 重新生成，包含 `connectors/` 和 `workers/` 目录

- **数据源架构重构 Direction A 完成**: 统一 BaseConnector → CLI → Skill 全链路
  - **BaseConnector 重构** (`core/connectors/base.py`): 消除 6 个子类中约 549 行重复代码
    - `DocumentConnector.persist()`: 从 abstract 改为 concrete（~80 行），3 个子类各自约 65-70 行的 persist() 全部移除
    - `MarketDataConnector.persist()`: Template Method 模式 + Hook 方法
      - 子类覆盖轻量 hook（`_daily_bar_datasets()` / `_build_daily_bar_row()` / `_persist_extra_records()`），不用覆盖整个 persist()
      - 静态工具方法 `_format_date()` / `_to_decimal()` / `_parse_date()` 从 3 个子类各约 55-65 行合并到基类
    - 净减少约 329 行代码，100% 向后兼容，1526 测试全通过
  - **统一 CLI**: 新增 `af data` 命令组 (`app/cli/commands/data.py`) 替代分散的 ingest/crawl/knowledge
    - `af data list` — 列出所有可用数据源及 datasets
    - `af data ingest -s <src> -d <dataset>` — 统一数据摄入入口
    - `af data backfill -s <src>` — 历史数据回填
    - `af data validate -s <src> -d <dataset>` — 数据校验（新增）
    - `af data status [--source <s>]` — 聚合 connector 健康 + Worker + Scheduler 状态
    - `af data file -f <path>` — 摄入单个文件
    - `af data schedule start|stop|status` — 采集调度器管理
    - `af data workers start|stop|status` — 知识加工 Worker 管理
    - 旧命令 `af crawl` / `af ingest` / `af knowledge` 保留为向后兼容别名
  - **Skill**: 新增 data-connector-development Skill 文档
    - Template Method + Hook 模式说明
    - Wrapper-first 策略指南
    - 完整开发检查清单

- **Wind 公式验证与清理**: 43 个新增公式全部通过 Mac Wind Excel 函数浏览器逐个验证
  - 日行情 `s_dq_*` (非 s_pq_*)，OHLC 增加 adj_type，移除 adj_close
  - 财务 TTM 参数不统一（trade_date vs report_date），fin_equity MRQ 无日期参数
  - 行业三函数合并为 `s_info_industry_sw_2021` + level 参数
  - 资金流向保留主力三时段，北向改用 s_share_n/pct_n
  - 指数 `i_dq_*` 前缀，index_weight 增加 trade_date
  - 删除 8 个未验证 placeholder（total_liabilities/operating_cf/industry_pe_pb/fund_hold_pct 等）
  - `wind_adapter.py` 所有 fetch 方法签名更新

### Added

- **天软 (Tinysoft) 数据源集成**: 通过 cjpy 包接入天软行情、因子、表格数据
  - `data_layer/adapters/cjpy_adapter.py` — CjpyAdapter 数据适配器
  - `data_sources/cjpy.py` — 数据源注册
  - 支持功能: 股票/基金列表、交易日查询、日线/分钟线行情、因子数据、表格数据、实时订阅
  - 69 个系统因子、21 张数据表格
- **Wind Excel 适配器**: 通过 xlwings → AppleScript → Excel Wind 插件获取专业金融数据，macOS 原生支持
  - `data_layer/adapters/wind/client.py` — `WindExcelClient`：xlwings 连接管理、心跳检测、批量公式执行、后台保活线程（30min 间隔防自动登出）
  - `data_layer/adapters/wind/formulas.py` — 35 个 Wind 公式生成器，覆盖一致预期（净利润/EPS/营收/目标价/评级，支持 fy1/fy2/fy3/ftm/avg）、融资融券（余额/买入/偿还/卖出/偿还）、龙虎榜（净买入/买入额/卖出额/上榜次数）
  - `data_layer/adapters/wind/wind_adapter.py` — `WindAdapter` 继承 `BaseDataAdapter`，提供 `fetch_consensus_estimates`、`fetch_margin_trading`、`fetch_block_trades` 三个高层接口
  - `data_layer/adapters/wind/exceptions.py` — 5 个自定义异常：`WindError`、`WindSessionExpiredError`、`WindNotConnectedError`、`WindFormulaError`、`WindTimeoutError`
  - `data_layer/adapters/wind/__init__.py` — 模块导出
  - `tests/unit/test_wind_adapter.py` — 43 个单元测试覆盖异常、公式生成、适配器结构、客户端逻辑
  - 所有 35 个公式名已通过 Mac 版 Wind Excel 函数浏览器逐个验证并实测通过
- **动态多因子 MVP**: 新增事件型量化的第一版动态因子研究层
  - `core/contracts/factors.py` — 因子 taxonomy、因子定义、点时因子值、因子评估记录、动态因子权重契约
  - `signal_lab/factors/matrix.py` — `FactorMatrixBuilder`，将点时 `FactorValue` pivot 为横截面因子矩阵
  - `signal_lab/factors/evaluation.py` — `FactorEvaluator`，支持 IC、RankIC、decile spread、coverage、sample size
  - `signal_lab/factors/models.py` — `RollingICWeightedModel`，基于滚动 IC/RankIC 学习 signed dynamic weights 并输出横截面 alpha score
  - `signal_lab/factors/fusion.py` — `EventFactorFusion`，融合事件 alpha、动态因子 alpha、Timing readiness 和风险惩罚
  - `tests/unit/test_dynamic_factors.py` — 覆盖矩阵构建、因子评估、动态权重、事件-因子融合
- **Signal Lab 动态因子可视化**: 在不修改 dashboard 与模板文件的前提下，为现有 WebUI 增加动态多因子 Alpha Control Room
  - `services/dynamic_factor_visualization_service.py` — 构建闭环步骤、因子矩阵、IC/RankIC、动态权重、事件-因子融合 payload
  - `app/api/routes/signal_lab.py` — 新增 `GET /api/signal-lab/dynamic-factors/overview`
  - `app/web/static/js/signal-lab.js` — 运行时注入“动态因子”页签和面板
  - `app/web/static/style.css` — 追加动态因子面板样式
  - `tests/unit/test_dynamic_factor_visualization_service.py` — 覆盖可视化 payload 结构
- **Wind Excel 适配器 ⭐ 重大扩展**: 公式覆盖从 35 个扩展到 78 个（43 个新增均已通过 Mac Wind Excel 函数浏览器验证），新增 API 端点 + Web UI + Signal Lab 因子 + 数据持久化
  - `data_layer/adapters/wind/formulas.py` — 新增 43 个已验证公式（日行情 11、财务/估值 20、行业/指数 6、资金流向/北向 5、股东结构 8）；移除未验证 placeholder（总负债/经营现金流/行业PE/PB/散户资金流等）
  - `data_layer/adapters/wind/wind_adapter.py` — 新增 5 个 fetch 方法：`fetch_daily_quotes`、`fetch_financial_statements`、`fetch_industry_data`、`fetch_fund_flow`、`fetch_holder_data`；实现 `parse()` 方法；source_type 改为 `vendor_snapshot`
  - `app/api/routes/wind.py` — 新增 8 个 REST API 端点：health/prices/financials/industry/fund-flow/holders（含 Pydantic 请求/响应模型）
  - `app/web/static/js/wind.js` — 新增 Wind 数据面板模块（fetch/渲染/健康检查）
  - `app/web/templates/index.html` — 新增 Wind 面板（代码输入、数据类型选择器、日期选择、结果显示表格）
  - `app/web/static/style.css` — 新增 Wind 面板样式
  - `signal_lab/features/groups/wind_consensus.py` — WindConsensusFeatures：一致预期因子（9 个特征：净利润 fy1/fy2/ftm、EPS fy1/fy2/ftm、目标价上涨空间、评级分数、评级机构数）
  - `signal_lab/features/groups/wind_margin.py` — WindMarginFeatures：融资融券因子（5 个特征：融资余额、融券余额、融资净买入、融资净流入、融券占比）
  - `signal_lab/features/groups/wind_block.py` — WindBlockFeatures：龙虎榜因子（3 个特征：LHB 净买入、买卖比、密集度）
  - `data_layer/adapters/data_source_router.py` — 新增 9 个 Wind 类型方法：`is_wind_available`、`fetch_wind_consensus`、`fetch_wind_margin_trading`、`fetch_wind_block_trades`、`fetch_wind_daily_quotes`、`fetch_wind_financials`、`fetch_wind_industry`、`fetch_wind_fund_flow`、`fetch_wind_holders`
  - `storage/migrations/versions/010_add_wind_data_tables.py` — 创建 4 张表：`wind_consensus_estimate`、`wind_margin_trading`、`wind_block_trade`、`wind_daily_bar`（含索引和唯一约束）
  - `data_layer/repositories/models.py` — 新增 4 个 ORM 模型：`WindConsensusEstimateDB`、`WindMarginTradingDB`、`WindBlockTradeDB`、`WindDailyBarDB`
  - `data_layer/repositories/wind_repository.py` — `WindRepository`：基于 PostgreSQL upsert 的持久化层（4 类数据的批量保存和查询）
  - `data_layer/adapters/base.py` — 修复 `_create_document_envelope` 字段名（id→doc_id、content→raw_text、source_path→source_name、created_at→published_at）
  - `tests/unit/test_wind_adapter.py` — 新增 102 个测试（价格 12、财务 17、行业 6、资金流向 5、持有人 8、适配器方法 10、异常 8、公式基础 16、客户端逻辑 4、解析 2）
  - `tests/unit/test_wind_api.py` — 新增 13 个 API 测试（健康检查、一致预期、两融、龙虎榜、行情、财务、行业、资金流向、持有人）
  - `tests/unit/test_wind_features.py` — 新增 15 个特征测试（一致预期 6、融资融券 4、龙虎榜 4、集成 2）
  - `tests/unit/test_wind_repository.py` — 新增 14 个仓储测试（空记录、upsert、查询、初始化）
- **WebUI 导航收敛**: 在不修改 dashboard 与模板文件的前提下，将低频/历史页面归档隐藏，保留”更多”按钮随时展开
  - `app/web/static/js/navigation-curation.js` — 新增导航归档配置和显示/隐藏状态管理
  - `app/web/static/js/app.js` — 初始化导航收敛模块
  - `app/web/static/style.css` — 新增归档导航按钮样式
  - 默认归档页面：情景分析、产业链、审核队列、回测结果、文档摄入
  - 资产分析保留在主导航，避免常用资产入口被隐藏
- **7 层管线可观测性 + 全自动闭环**: 实时管线监控页面、SSE 事件推送、自动定时闭环运行
  - `services/pipeline_monitor.py` — 管线状态追踪单例，9 阶段线程安全活动日志（200 条上限），DB 统计聚合（DocumentV1DB / CanonicalEvent / AlphaSignalDB / SignalOutcomeDB），北京时间对齐
  - `app/web/static/js/pipeline-monitor.js` — 管线监控前端模块，5 阶段流程可视化（数据采集→知识提取→信号生成→择时回测→学习反馈），SSE 实时日志 + 15s 轮询，手动触发闭环
  - `app/api/routes/pipeline.py` — `GET /api/pipeline/status` 完整管线状态，`POST /api/pipeline/closed-loop` 手动触发闭环
  - `services/crawl_scheduler.py` — `_run_closed_loop_job()` 每 10 分钟自动运行闭环（60s jitter）
  - 12 种管线事件类型覆盖全 7 层：`pipeline.*`, `knowledge.*`, `reasoning.*`, `agent.*`, `timing.*`
  - 事件发布接入：`ClosedLoopService`, `PipelineService`, `EntityResolver`, `PropagationAnalyzer`, `KnowledgeWorker`
  - Dashboard 精简：移除 Workbench 标签页，保留 Market Overview + Live Monitor
  - `core/adapters/event_adapter.py` — 事件标准化适配器
  - `knowledge_layer/graph_projection/seed_data.py` — 产业链种子数据
- **所有文档创建路径强制入队 LLM 提取**: CLS deep backfill 和 PDF 转换保存文档后通过 CrawlerIngestionBridge 入队，确保 KnowledgePipeline 做 LLM 提取
  - `services/crawl_orchestrator.py` — `deep_backfill_step()` 保存后调用 `_enqueue_to_bridge()`
  - `services/pdf_conversion_service.py` — `_create_document_from_conversion()` 创建后调用 `_enqueue_document()`
  - 提取 `_enqueue_items()` 静态方法，供回补脚本和 `_enqueue_to_bridge()` 复用
- **回补脚本: 缺失 LLM 提取文档**: `scripts/backfill_missing_llm_extraction.py`，找到缺少 `canonical_event` 的文档并批量入队 (首次运行回补 2056 条)
- **爬虫去重文件自动同步**: 每次抓取前将文件级去重状态与 `document_v1` 表同步，防止已删除文档永久被跳过
  - `data_layer/crawlers/cls/utils/deduplication.py` — `DeduplicationStore.remove_stale()` 方法
  - `services/crawl_orchestrator.py` — `_sync_dedup_state()` 方法，`crawl_source()` 步骤 4 调用
- **回补脚本: 去重孤儿清理**: `scripts/cleanup_dedup_orphans.py`，对比去重文件和数据库，移除孤儿条目 (首次运行清理 10 条)
- **ZQ PDF 下载后自动注册到数据库**: `ReportProcessor._download_and_record_pdf()` 下载成功后在 `pdf_artifact_v1` 创建记录
  - `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py` — 新增 DB 注册逻辑
- **PDF 转换自动调度**: `CrawlScheduler` 新增每 5 分钟 PDF 转换任务，自动调用 `convert_pending(limit=5)` 并重试失败项
  - `services/crawl_scheduler.py` — `_run_pdf_conversion_job()` 方法
- **回补脚本: PDF 制品注册**: `scripts/backfill_pdf_artifacts.py`，扫描磁盘 PDF 文件并批量注册到 `pdf_artifact_v1` (首次运行注册 287 个)
- **LLM 提取 flash→pro 自动回退**: 所有提取器先用 deepseek-v4-flash，失败时自动用 deepseek-v4-pro 重试
  - `services/event_extractor.py` — `_extract_via_llm()` 添加 flash→pro 两级调用
  - `knowledge_layer/events/extractor.py` — `_extract_by_llm()` 添加 flash→pro 两级调用
  - `knowledge_layer/assertions/extractor.py` — `_extract_by_llm()` 添加 flash→pro 两级调用
- **ZQ 账号永久禁用机制**: 连续失败 N 次后自动永久禁用该账号，不再无限重试
  - `data_layer/crawlers/zq/zhiqiu/account_manager.py` — `AccountStats` 新增 `consecutive_failures`、`is_disabled` 字段，`record_failure()` 达到阈值后自动禁用
  - `data_layer/crawlers/zq/.config_account_state.json` — `max_consecutive_failures: 10`
- **EventRepository 空 source_doc_id 校验守卫**: `save()` 方法拒绝空 source_doc_id，直接抛 `ValueError` 而非产生 FK 约束违反
- **进程监管 watchdog**: `workers/watchdog.py` 外部 watchdog 进程，SIGKILL/SIGTERM 下自动重启 worker，信号处理中同步终止子进程避免孤儿残留
- **HTTP 请求超时**: `core/model_gateway/providers/openai_compatible.py` LLM 调用添加 120s 超时；`data_layer/crawlers/zq/zhiqiu/client.py` 所有 HTTP 请求添加 30s/60s 超时
- **仪表盘状态栏动态数据**: 新增 `GET /api/system/status-bar` 端点，返回 git 分支、数据库类型、LLM provider、文档数、错误/警告数等实时数据
  - `app/api/routes/system.py` — `_get_git_branch()`、`_get_db_type()`、`_get_llm_provider()` 辅助函数
  - `app/web/templates/index.html` — 状态栏动态值添加 `<span id="status-XXX">`
  - `app/web/static/app.js` — `updateStatusBar()` 函数，页面加载 + 30s 轮询 + SSE 事件联动

### Changed
- **移除关键词/规则提取 fallback**: 所有提取器 LLM 失败时返回空结果，不再产生低质量数据
  - `services/event_extractor.py` — 移除 `_extract_via_keywords()` 及 5 个关键词字典（~150 行死代码）
  - `knowledge_layer/events/extractor.py` — 移除 `_extract_by_rules()` 及 4 个辅助方法（~120 行死代码）
  - `knowledge_layer/assertions/extractor.py` — 移除 `_extract_by_rules()`
- **LLM 提取 max_tokens 提升**: `services/event_extractor.py` 从 1024 → 4096，避免 JSON 截断
- **`.env` 模型配置**: `TASK_EXTRACTION_MODEL` 使用 `deepseek-v4-flash` 为主，pro 为 fallback
- **Knowledge Worker 可靠性加固**: `__main__` 改为指数退避重启循环；新增 `_recover_stuck_items()` 自动将超时 processing item 重置为 pending
- **移除爬虫层 PDF 转换器 (死代码)**: 删除 `data_layer/crawlers/utils/pdf_converter.py` (347 行)，其依赖的 `enable_pdf_conversion` 参数在所有 SourceSpec 中默认为 False
  - `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py` — 移除 6 个方法中的 `enable_pdf_conversion`/`markdown_dir`/`raw_text_dir` 参数及 2 处转换代码块
  - `data_layer/crawlers/utils/__init__.py` — 移除 8 个 PDF 相关导出
- **`_enqueue_to_bridge()` 委托给 `_enqueue_items()`**: 消除重复代码，两个方法共享同一入队逻辑
- **`get_pending_conversions()` 修复**: 从查询 `PDFConversionV1DB` 改为查询 `PDFArtifactV1DB.parse_status='pending'`
  - `data_layer/repositories/pdf_artifact_repository.py` + `services/pdf_conversion_service.py`
- **`list_by_time_range()` 修复**: `available_time` → `created_at`，消除不存在的列引用
  - `data_layer/repositories/documents_v1.py`

### Fixed
- **PDF 转换后文档创建失败静默吞掉**: `_create_document_from_conversion()` 异常现在写入 `conversion.error_log`，运维可发现
  - `services/pdf_conversion_service.py`
- **知丘纪要日增量极少**: `days_per_crawl` 默认为 1 天，kanzhiqiu.com 日发布量本身就少 → 改为 `days_per_crawl=3`，每次增量抓取覆盖最近 3 天
  - `data_sources/zhiqiu_transcript.py` — 新增 `days_per_crawl=3` 参数
- **ZQ 爬虫无限挂起**: `majingyi` 账号 0/54 成功率仍被重复调度 → 已永久禁用
- **DeepSeek JSON 截断**: max_tokens=1024 不足以完成事件提取 → 提升至 4096
- **事件静默丢失**: `source_doc_id` 为空字符串导致 FK 约束违反而插入失败
  - `services/crawl_orchestrator.py` — 修复 `str(None)` → `"None"` bug
  - `ingestion/structured_event_ingestion.py` — `normalize_event()` 传递 `source_doc_id`
- **Knowledge Worker 崩溃**: `SessionLocal()` 移入 try 块内；`asyncio.run(main())` 添加 try/except；关闭超时延长至 60s
- **Scheduler 启动回补阻塞**: 单个来源挂起不再阻塞全部，添加超时保护
- **类型统一**: 共享类型集中到 `core/contracts/`
  - 新建 `core/contracts/timing_types.py` — `TimingAction`, `OutcomeHorizon`, `FailureType`
  - 新建 `core/contracts/agent_types.py` — `AgentRole`, `AgentView`, `ViewDirection`, `BlackboardConflict`
  - 消除 `TimingAction` 重复定义（原`timing_engine/contracts.py`和`memory_learning/contracts.py`）
  - `data_layer/repositories/agent_view_repository.py` 改为从 `core.contracts.agent_types` 导入，消除 data_layer → cognitive_agents 依赖
- **模块化重构**: 拆分 `core/services/` → `services/` 顶层包
  - 将 47 个服务文件从 `core/services/` 移动到顶层 `services/`，消除 `core/` ↔ `data_layer/` 循环依赖
  - 所有导入路径从 `core.services.xxx` 更新为 `services.xxx`
  - `core/services/__init__.py` 保留为废弃重导出兼容层
  - 修复 4 个 `__file__` 路径计算（从 `.parent.parent.parent` 到 `.parent.parent`）
  - 文档更新：`docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_MAP.md`, `docs/FILE_GUIDE.md`, `docs/modules/services.md`
- **内容净化**: `data_layer/` 内部不相干模块迁移
  - `data_layer/indicators/` → `signal_lab/features/indicators/`：技术指标引擎属于信号研究
  - `data_layer/converters/` → `ingestion/converters/`：PDF转换策略链属于内容处理
  - `cron_jobs/auto_generate_signals.py` → `app/cli/commands/auto_generate_signals.py`

- **knowledge-worker-concurrency**: Knowledge Worker item 级并发 + 完整生命周期管理
  - `workers/knowledge_worker.py` — 重写为 PID 管理 + 信号处理 + `asyncio.Semaphore` item 级并发（默认 8 并发）
  - 两层并发架构：item 级 (asyncio.Semaphore, 8) + chunk 级 (ThreadPoolExecutor, 8)
  - CLI 命令：`af knowledge start|stop|status` (app/cli/commands/ingest.py)
  - API 端点：`POST /api/knowledge/start|stop`, `GET /api/knowledge/status` (app/api/routes/knowledge.py)
  - 配置项：`KNOWLEDGE_WORKER_POLL_INTERVAL`, `BATCH_SIZE`, `MAX_CONCURRENCY`, `SHUTDOWN_TIMEOUT` (core/settings/config.py)
- **source-registry**: 数据源注册中心 — 可插拔源模块架构
  - 新建 `core/source_registry.py` — `SourceSpec` frozen dataclass + `register()`/`get()`/`get_all()`/`get_enabled()`/`get_by_family()` API
  - 新建 `data_sources/__init__.py` — `pkgutil.iter_modules` 自动发现，无需手动 import
  - 新建 6 个源注册模块：`data_sources/cls.py` (财联社), `data_sources/cnstock.py` (中国证券网), `data_sources/cnstock_flash.py` (快讯), `data_sources/zhiqiu_reports.py`, `data_sources/zhiqiu_wechat.py`, `data_sources/zhiqiu_transcript.py`
  - `CrawlOrchestrator._fetch_from_adapter()` 从 if/elif 链 (65 行) 改为动态 import；当前 canonical 路径为 `spec.connector_class`，`spec.adapter_class` 仅保留为历史兼容别名
  - `CrawlScheduler.DEFAULT_CRAWL_CONFIGS` 从硬编码列表改为 `_get_default_configs()` 从注册表自动生成
  - `CrawlScheduler._add_jobs_for_source()` 深度回补逻辑从硬编码 `SourceType` 检查改为 `backfill_family` 字段
  - `workers/crawl_scheduler_worker.py` 启动源列表从硬编码改为 `source_registry.get_enabled()`
  - `services/dashboard_service.py` 6 个硬编码 `crawl_source()` 调用改为 `get_enabled()` 循环
  - `cron_jobs/auto_ingest_service.py` 3 个独立 `ingest_*` 函数改为 `ingest_all_sources()` 单循环 + 向后兼容别名
  - `services/document_classifier.py` 硬编码 `reliability_map` 改为注册表查找 + 非爬取源 fallback
  - `services/pdf_conversion_service.py` 硬编码 `type_map` 改为注册表自动生成 + 遗留别名
  - **添加新爬取源 = 在 `data_sources/` 下新建一个 `.py` 文件，不再需要修改 13+ 个文件**

### Changed
- **knowledge-worker-optimization**: Knowledge Worker 四项优化
  - Pipeline 实例复用：`process_one()` 接受共享 `KnowledgePipeline`，Worker 启动时创建单例（含 `ModelGateway`），不再每个 item 创建全套组件
  - 空队列指数退避：连续空轮询时 sleep 从 3s 指数增长到 60s cap，有数据时立即重置
  - 长文档并发 LLM 提取：`KnowledgePipeline` 注入 `ModelGateway` 后，>1000 字符自动走 `ConcurrentLLMExtractor` 分块并发提取
  - 多进程水平扩展：`af knowledge start --workers N` 启动 N 个独立 Worker 进程，各自独立 PID 文件和 polling，DB 层原子状态转换天然支持多消费者
  - `workers/knowledge_worker.py` — `--worker-id` 参数，`_create_pipeline()` 单例，指数退避，`get_all_worker_statuses()`
  - `app/cli/commands/ingest.py` — `knowledge start --workers N`，`stop`/`status` 支持多 worker
  - `app/api/routes/knowledge.py` — `start?workers=N`（最大 16），`stop`/`status` 多 worker 聚合
  - `ingestion/knowledge_pipeline.py` — 移除未使用的 `AssertionPrompts` import
- **knowledge-worker-consolidation**: 移除 cron_jobs 中的冗余队列消费
  - `cron_jobs/auto_ingest_service.py` — 删除 `process_ingestion_queue()` 及对应 scheduler job
  - Knowledge Worker 成为 ingestion_queue 的唯一消费者
- **source-type-rename**: SourceType 枚举重命名和数据库迁移
  - `SourceType.CAILIAN_SHE = "cailian_she"` → `SourceType.CLS = "cls"`
  - `SourceType.CHINA_SECURITY_JOURNAL = "china_security_journal"` → `SourceType.CNSTOCK = "cnstock"`
  - 数据源文件重命名：`cailian_she.py` → `cls.py`, `china_security_journal.py` → `cnstock.py`
  - 数据库迁移：9 张表 `source_type` 列更新 (~5000 行)，后端/frontend 全面对齐
- **startup-backfill-parallel**: 启动间隔回填从串行改为并行 — 每个源独立线程 + 独立 event loop，6 个源同时回填
- **backfill-3-missing-sources**: 启动回填新增 3 个源（cnstock_flash, zhiqiu_wechat, zhiqiu_transcript），之前仅 cls/cnstock/zhiqiu_reports

### Fixed
- **cnstock 爬虫 API 错误时注入虚构新闻**: `cnstock.py` `_crawl_page()` 在 API 返回业务错误码（如 "未登录" 10304）或 `data=null` 时，异常处理 fallback 到 `_generate_sample_news()`，可能将虚构新闻注入数据库
  - `data_layer/crawlers/cnstock/cnstock.py` — `_crawl_page()` 添加 API 业务错误码检查（`code not in (None, 0, 200) and data is None`），返回空列表
  - `data_layer/crawlers/cnstock/cnstock.py` — `_parse_response_common()` 返回空列表而非 `_generate_sample_news()`
  - `data_layer/crawlers/cnstock/cnstock.py` — `_parse_api_response()` 和 `_parse_search_api_response()` 添加 None-safety：`data.get("data")` 返回 None 时安全处理
- **Scheduler 事件循环阻塞导致非 CLS 作业被跳过**: `_run_crawl_job()` 等 5 个 async 方法内同步调用 `CrawlOrchestrator`，阻塞 asyncio 事件循环。CLS（先注册）执行期间（~11s），其他作业的 `next_run_time` 超过 APScheduler 默认 `misfire_grace_time=1s` 被跳过
  - `services/crawl_scheduler.py` — 5 个 async 方法全部改为 `loop.run_in_executor(None, sync_fn)` 在线程池中运行同步抓取代码
  - 影响方法：`_run_crawl_job`、`_run_backfill_job`、`_run_deep_backfill_job`、`_run_cnstock_deep_backfill_job`、`_run_zq_deep_backfill_job`
  - 修复后全部 6 个定时作业同时触发（10:37:07 同一秒），不再排队等待
- **worker-heartbeat-cross-process**: Worker 心跳数据跨进程不可见修复
  - `workers/knowledge_worker.py` — 新增 `_write_heartbeat()` 将心跳写入 `logs/{worker_label}.heartbeat.json`
  - `workers/crawl_scheduler_worker.py` — 新增 `_write_heartbeat()` 将心跳写入 `logs/scheduler.heartbeat.json`
  - `app/api/routes/system.py` — 新增 `_read_heartbeat_files()` 扫描文件心跳，文件优先于进程内 event_bus；修复 `PROJECT_DIR` 路径计算（4 层 parent）
  - 修复 `Path.stem` 只剥离 `.json` 的问题：`Path(hb_path.stem).stem` 同时剥离 `.heartbeat` 和 `.json`
- **scheduler-process-separation**: 拆分爬虫调度器为独立进程 + 修复多源并发线程安全问题
  - 新建 `workers/crawl_scheduler_worker.py` — 独立调度器进程，通过 PID 文件管理生命周期，SIGTERM/SIGINT 优雅退出
  - `CrawlScheduler` 线程安全修复：`_run_crawl_job` / `_run_backfill_job` / `trigger_crawl` / `trigger_backfill` 每次创建独立 `CrawlOrchestrator`（独立 DB session），支持 CLS/CNStock/ZQ 多源并行抓取
  - 新增 `build_scheduler_status()` — 纯函数从 DB 读取抓取状态（CrawlRun + SourceCursor）
  - 新增 `get_scheduler_process_status()` — 通过 PID 文件检查调度器进程存活
  - `app/api/routes/scheduler.py` 全部 5 个端点重写为跨进程操作（start 用 subprocess.Popen, stop 用 os.kill, status 读 DB+PID, trigger/backfill 用临时 CrawlOrchestrator）
  - `scripts/start_all.sh`：调度器从 `curl POST /api/scheduler/start` 改为独立 `nohup python -m workers.crawl_scheduler_worker`
  - `scripts/stop_all.sh`：新增 `stop_by_pid "scheduler"`
  - `app/cli/commands/ingest.py`：`crawl status` 改用 `build_scheduler_status()` + `get_scheduler_process_status()`；`crawl scheduler-start` 改用 subprocess 启动独立进程
- **crawl-dedup-title-fk**: 修复爬虫三大问题 — CLS 标题显示 "财联社电报 XXX" 而非真实标题、断言/事件 FK 约束冲突（source_document 缺失）、ZQ 适配器返回 0 条文档
  - CLS 标题修复：从内容首句提取标题（`cls_adapter.py`）
  - FK 约束修复：共享 DB 会话 + 文档优先保存顺序（`ingest.py`, `ingest_service.py`）
  - ZQ 适配器修复：惰性导入 pdf_converter + 修复返回值解包 + 补充 viewpoint 字段作为内容源（`report_processor.py`, `report.py`, `zq_adapter.py`）
  - 去重系统增强：source_doc_id/content_hash/doc_id 三重去重 + upsert（`crawl_orchestrator.py`, `documents_v1.py`）
  - Knowledge Worker doc_id 一致性修复（`knowledge_worker.py`）
- **test-suite-regression**: 修复 52 个测试失败和 5 个 mypy 错误 — 全流程验证通过 (1243 passed, 1 skipped)
  - 修复 `CanonicalEvent` (Pydantic contract) 新增必填字段 `source_type`/`source_name`/`title` 导致的 ~30 个测试失败 — 在 `ingestion_queue_service.py` 和所有测试 fixture 中补充必填字段
  - 修复 `GlobalSearchService` 构造函数变更 (session → search_repo) — 重写 `test_search.py` 和 `test_signal_detail.py` 搜索测试
  - 修复 `DashboardService` 内部使用 `DashboardDataRepository` — 重写 `test_dashboard.py` mock 策略
  - 修复 `SectionOutput` 新增必填 `title` 字段 — 在 `app/cli/commands/analyze.py` 和 `test_markdown_projection.py` 中补充
  - 修复 `HybridSearcher.search()` API 参数不匹配 — `rag_retrieval.py` 中 `query_text`→`query`, `limit`→`top_k`
  - 修复 `SignalOutcome` 默认值变更 (max_drawdown/decay: 0.0→None) — 更新 `test_outcome_protocol.py` 断言
  - 修复 `VectorBT` 不可用时的回退测试 — `test_signal_lab.py` 适配 SimpleBacktester 回退
  - 修复 `test_closed_loop_service.py` ORM model 不支持新字段 — 移除不存在的 `source_type`/`source_name`/`title`
  - 修复 `test_scenario_graph_data.py` API 返回值断言 (data_source: disabled→placeholder)

### Added
- **end-to-end-orchestration**: 端到端自动化第一阶段 — 爬虫→队列→KnowledgePipeline 全自动打通 + 实时前端
  - 新增 `services/crawler_ingestion_bridge.py`：CrawlerIngestionBridge (爬虫输出统一转 DocumentEnvelope → EnqueueRequest → 入队)
  - 新增 `services/system_event_bus.py`：SystemEventBus (内存事件总线, SSE 推送, worker heartbeat)
  - 新增 `workers/knowledge_worker.py`：常驻后台 worker (asyncio, 自动消费 ingestion_queue, 调用 KnowledgePipeline)
  - 新增 `app/api/routes/system.py`：GET /api/system/health 和 /api/system/health/minimal 端点
  - 新增 `app/api/routes/realtime.py`：GET /api/realtime/stream SSE 实时推送端点
  - 新增 `scripts/start_all.sh` + `scripts/stop_all.sh`：一键启动/停止全系统 (API + scheduler + knowledge worker)
  - 新增 `ingestion/__init__.py`：ingestion 包初始化
  - **修复**: DataSourceRouter 中 AKShareAdapter 缺失 import + 名称不匹配 (AkShareAdapter → AKShareAdapter)
  - **增强**: CrawlOrchestrator._fetch_from_adapter() 从 stub 升级为真实适配器调用 (CLSAdapter/CNStockAdapter/ZQAdapter) + 自动 enqueue
  - **增强**: 前端 app.js 接入 EventSource SSE 实时流 (document_parsed/event_created/signal_generated/queue_update/error_alert)
  - 新增 `tests/unit/services/test_crawler_ingestion_bridge.py`：6 个 bridge 测试
  - 新增 `tests/unit/data_layer/adapters/test_akshare_adapter.py`：6 个 adapter/router 测试
  - 新增 `tests/unit/services/test_system_event_bus.py`：4 个 event bus 测试
  - 新增 `tests/unit/app/api/routes/test_system_realtime.py`：2 个 API 端点测试
  - 新增 `tests/unit/workers/test_knowledge_worker.py`：3 个 worker 测试
- **concurrent-llm-extraction**: 数据提取管道升级 — 从单次串行 LLM 调用升级为 chunk 切分 + ThreadPoolExecutor 并发 + 去重
  - 新增 `knowledge_layer/extraction/text_chunker.py`：轻量级滑动窗口文本切分器 (split_text)
  - 新增 `knowledge_layer/extraction/concurrent_extractor.py`：ConcurrentLLMExtractor (并发 LLM 抽取, 重试, 统计)
  - 重构 `services/ingest_service.py`：所有入口统一走 ingest_envelope() 管道，长文本自动切 chunk 并发提取
  - 新增配置项：LLM_EXTRACT_MAX_WORKERS, LLM_EXTRACT_CHUNK_SIZE, LLM_EXTRACT_CHUNK_OVERLAP, LLM_EXTRACT_MAX_RETRIES, LLM_EXTRACT_LONG_TEXT_THRESHOLD
  - **修复**: `_extract_combined()` 传入 EXTRACTION_MODEL 代替默认模型
  - **修复**: `EventExtractor._extract_by_rules()` 补充 source_type/source_name/title 必填字段
  - **修复 (风险处置)**: 并发路径 `_extract_one_chunk()` 传入 `model=self.model`，消除并发/非并发路径结果不一致
  - **改进**: `ConcurrentLLMExtractor` 补 Protocol / Callable 精确类型，targeted mypy 通过
  - **改进**: 去重 key 从 `str(dict)` 升级为 `json.dumps(sort_keys=True)` + 空白归一化
  - 新增 `tests/unit/knowledge_layer/extraction/test_text_chunker.py`：8 个切分测试
  - 新增 `tests/unit/knowledge_layer/extraction/test_concurrent_extractor.py`：16 个并发提取器测试 (含 model 透传、32 chunk 全量、并发加速验证、retry 成功计数)
  - 新增 `tests/unit/test_ingest_service.py`：4 个新测试 (去重、委托、统计)
- **market-data-pipeline**: 数据全流程升级 — 从 crawler → JSON 快照 升级为 crawler → normalizer → 结构化 SQL 表 → 派生 snapshot
  - 新增 `data_layer/repositories/models.py`：8 张结构化 SQL 表 (StockMasterDB, StockDailyBarDB, StockQuoteSnapshotDB, StockFinancialMetricDB, StockValuationDB, StockShareholderDB, IndexComponentDB, ETLRunDB)
  - 新增 `data_layer/repositories/market_data_repository.py`：MarketDataRepository (PostgreSQL upsert + SQLite fallback)
  - 新增 `data_layer/repositories/etl_run_repository.py`：ETLRunRepository (ETL 运行记录管理)
  - 新增 `data_layer/normalizers/common.py`：通用 normalizer 工具 (to_decimal)
  - 新增 `data_layer/normalizers/symbol.py`：A 股代码标准化 (normalize_a_share_symbol)
  - 新增 `data_layer/normalizers/akshare_market.py`：行情/股票信息标准化
  - 新增 `data_layer/normalizers/akshare_financial.py`：财务数据标准化
  - 新增 `services/market_data_ingestion_service.py`：ETL 编排服务 (fetcher → normalizer → repository → etl_run)
  - 新增 `app/api/routes/market_data.py`：Market Data API (stocks/sync, daily-bars/sync, daily-bars query, etl-runs)
  - 重构 `services/asset_analysis_service.py`：优先从结构化表生成 snapshot，回退到 coordinator
  - 更新 `cron_jobs/auto_ingest_service.py`：分步执行 15:15 股票列表 → 15:30 日行情 → 15:45 资产快照
  - 新增 `tests/unit/data_layer/normalizers/`：12 个 normalizer 单测
  - 新增 `tests/unit/data_layer/repositories/test_market_data_repository.py`：8 个 repository 测试
  - 新增 `tests/unit/data_layer/repositories/test_etl_run_repository.py`：5 个 ETL run 测试
  - 新增 `tests/unit/services/test_market_data_ingestion_service.py`：4 个 ingestion service 测试
  - 新增 `storage/migrations/versions/009_add_structured_market_data_tables.py`：Alembic 迁移 (8 张市场数据表)
  - 新增 `scripts/check_market_data_schema.py`：Schema 验证脚本 (检查 8 张表是否存在)
  - 新增 `scripts/bootstrap_market_data.py`：初始化数据填充脚本
  - **修复**: `app/api/routes/assets.py` 中 `get_asset_service()` 注入 `MarketDataRepository`，使结构化表路径可用
  - **修复**: `services/asset_analysis_service.py` 增加 `_has_enough_structured_data` 数据质量检查，防止空表数据被错误当作"结构化路径已启用"
  - **修复**: `tests/unit/test_asset_analysis_service.py` 适配新的构造函数签名和 async 接口
- **pdf-conversion-pipeline**: 完整的 PDF 到 Markdown 转换管道
  - 新增 `core/contracts/pdf_conversion.py`：Pydantic 契约 (ConversionResult, StrategyType, ConversionStatus)
  - 新增 `data_layer/converters/base.py`：PDFConversionStrategy 抽象基类
  - 新增 `data_layer/converters/raw_text.py`：RawTextStrategy (pdfplumber, 始终可用)
  - 新增 `data_layer/converters/markitdown.py`：MarkItDownStrategy (microsoft/markitdown)
  - 新增 `data_layer/converters/mineru.py`：MinerUStrategy (opendatalab/mineru)
  - 新增 `data_layer/converters/persistence.py`：磁盘持久化工具 (data/markdown/, data/raw_text/)
  - 新增 `services/pdf_conversion_service.py`：PDFConversionService 核心编排
  - 新增 `core/settings/config.py`：PDF 输出目录和阈值配置
  - 新增 `app/api/routes/pdf_admin.py`：Admin API (convert/stats/pending/retry)
  - 新增 `docs/modules/pdf_conversion_pipeline.md`：模块文档
  - 新增 `tests/unit/services/test_pdf_conversion_service.py`：27 个服务层测试
  - 新增 `tests/unit/data_layer/converters/test_persistence.py`：12 个持久化测试
  - 新增 `tests/unit/test_pdf_admin_api.py`：7 个 API 测试
  - 新增 `tests/integration/test_pdf_conversion_integration.py`：4 个集成测试
  - 安装方式：`pip install -e ".[pdf]"` (MarkItDown) / `pip install -e ".[pdf-full]"` (MinerU)
- **dev-governance**: 完整的开发治理系统与 Claude 工作流程
  - 新增 `CLAUDE.md`：精简的最高优先级入口文档，定义必须加载的规则
  - 新增 `.claude/rules/`：详细的规则目录
  - 新增 `.claude/commands/`：可复用的任务命令模板
  - 新增 `docs/DEVELOPMENT_MAP.md`：开发地图，任务到子系统的路由表
  - 新增 `docs/modules/`：模块级详细文档（完整的17个模块文档）
  - 新增 `scripts/generate_py_file_index.py`：Python 文件索引生成脚本
  - 新增 `scripts/check_task_completion.py`：任务完成检查脚本
  - 新增 `scripts/check_doc_sync.py`：文档同步检查脚本
  - 新增 `.ai/reports/test_report_TEMPLATE.md`：测试报告模板
  - 新增 `docs/generated/py_file_index.md`：生成的文档目录
- **ingestion**: 创建 KnowledgePipeline 深模块，统一知识加工流程
  - 新增 `ingestion/knowledge_pipeline.py`：提供单一 `process(doc)` 接口，内部协调分块、分类、实体提取、事件提取、丰富、去重、保存等步骤
  - 新增 `data_layer/repositories/search_repository.py`：SearchRepository 接口和 SQLAlchemy 实现，隐藏 session 依赖
    - `00-core-rules.md`：核心行为规则
    - `01-task-workflow.md`：任务工作流程
    - `02-test-policy.md`：测试策略
    - `03-doc-sync-policy.md`：文档同步策略
    - `04-git-workflow.md`：Git 工作流程
    - `05-blocking-policy.md`：阻塞策略
    - `06-final-response.md`：最终响应格式
  - 新增 `.claude/commands/`：可复用的任务命令模板
    - `start-task.md`：任务启动命令
    - `verify-task.md`：任务验证命令
    - `finish-task.md`：任务完成命令
  - 新增 `docs/DEVELOPMENT_MAP.md`：开发地图，任务到子系统的路由表
  - 新增 `docs/modules/`：模块级详细文档
    - `core_services.md`：核心服务模块文档
    - `app_api.md`：API 模块文档
    - `data_layer_crawlers.md`：数据爬虫模块文档
  - 新增 `scripts/generate_py_file_index.py`：Python 文件索引生成脚本
  - 新增 `scripts/check_task_completion.py`：任务完成检查脚本
  - 新增 `scripts/check_doc_sync.py`：文档同步检查脚本
  - 新增 `.ai/reports/test_report_TEMPLATE.md`：测试报告模板
  - 新增 `docs/generated/`：生成的文档目录
- **ingestion**: 创建 KnowledgePipeline 深模块，统一知识加工流程
- **ingestion**: 创建 KnowledgePipeline 深模块，统一知识加工流程
  - 新增 `ingestion/knowledge_pipeline.py`：提供单一 `process(doc)` 接口，内部协调分块、分类、实体提取、事件提取、丰富、去重、保存等步骤
  - 新增 `data_layer/repositories/search_repository.py`：SearchRepository 接口和 SQLAlchemy 实现，隐藏 session 依赖
- **docs**: 更新项目文档与实际结构保持一致
  - 更新 `README.md` 项目结构：添加 `ingestion/`、`cron_jobs/` 目录，更新契约和服务列表
  - 更新 `docs/FILE_GUIDE.md`：添加 `ingestion/` 模块说明，调整目录顺序
- **worker-monitoring-panel**: WebUI 实时 Worker 监控面板
  - 新增 `GET /api/system/workers/status` 端点 — 聚合 Knowledge Worker / Crawl Scheduler PID 活性 + 心跳 + 队列统计
  - `services/system_event_bus.py` — `record_worker_heartbeat()` 扩展支持 `activity` 描述字段
  - `workers/knowledge_worker.py` — 心跳调用增加活动描述（处理中/空闲/启动/关闭）
  - `workers/crawl_scheduler_worker.py` — 新增完整心跳机制（启动/运行中/停止），30 秒定期心跳
  - 前端 Dashboard 新增"系统工作进程"卡片 — 状态指示灯（绿色脉冲/红色）+ 队列统计（待处理/处理中/已完成/失败）
  - 前端 15 秒自动轮询 + SSE `worker_heartbeat` 事件预留（Phase 2 零延迟推送）

### Changed
- **refactor**: 深化搜索服务模块，隐藏 SQLAlchemy session 依赖
  - 重构 `services/search_service.py`：GlobalSearchService 现在依赖 SearchRepository 接口而非直接依赖 session
  - 更新 `app/api/routes/search.py`：创建 SearchRepositoryImpl 并注入 GlobalSearchService
- **refactor**: 深化事件摄入模块，移除冗余的服务层
  - 删除 `services/event_ingestion_service.py`：该服务只是对 `StructuredEventIngestor` 和仓储的简单包装
  - 将自动断言提取功能直接集成到 `ingestion/structured_event_ingestion.py`：`StructuredEventIngestor` 现在会在 `ingest()` 和 `bulk_ingest()` 时自动提取断言
  - 更新 `app/api/routes/event_ingestion.py`：直接使用 `StructuredEventIngestor` 和 `EventRepositoryImpl`，移除中间服务层
  - 添加 `EventQueryResponse` 数据类到 API 路由模块
  - 添加测试用例验证自动断言提取功能
- **refactor**: 深化时序引擎模块，移除冗余的服务层
  - 删除 `services/timing_engine_service.py`：该服务只是对数据类的简单包装
  - 将阻塞检查逻辑直接集成到 `core/contracts/timing_engine.py`：`ReadinessScore` 现在有 `should_block()` 和 `get_blocking_reason()` 方法
  - 更新 `app/api/routes/timing_engine.py`：直接使用 `TimingFactors`、`EventStudyMetrics` 和 `ReadinessScore` 数据类
  - 更新 `scripts/rebuild_derived_state.py` 和 `scripts/minimal_reingest_bootstrap.py`：移除对已删除服务的依赖
  - 重写并增加测试用例验证新的集成架构
- **docs**: 完整更新项目文档（README、REFERENCE、ARCHITECTURE、FILE_GUIDE、CHANGELOG、DATA_STORAGE）
  - 新增 `docs/DATA_STORAGE.md`：数据存储设计文档，包含 PostgreSQL 表结构、数据契约、仓储接口说明
- **refactor**: 清理项目根目录，移除重复配置
  - 移除根目录重复的 `alembic.ini` 和 `alembic/` 目录，统一使用 `storage/migrations/`
  - 移动临时脚本到标准目录：`view_db.py` → `scripts/`，`auto_ingest_service.py` → `cron_jobs/`
  - 移除冗余临时脚本：`insert_real_data.py`、`report_cli.py`、`smoke_runner.py`（功能已存在于标准位置）
- **refactor**: 清理 AKShare 集成，移除重复代码，统一使用 crawler 模块的 utils
  - `data_layer/crawlers/akshare/utils.py`: 新增工具函数（clean_symbol, normalize_symbol, parse_date, parse_datetime, safe_float）
  - `data_layer/crawlers/akshare/market.py`: 重构为使用 utils 中的工具函数
  - `data_layer/crawlers/akshare/financial.py`: 重构为使用 utils 中的工具函数
  - `data_layer/crawlers/akshare/news.py`: 重构为使用 utils 中的工具函数
  - `data_layer/adapters/akshare_adapter.py`: 更新为集成新的 crawler 模块
- **Issue #42-47**: 统一文档 Schema、多源采集、知识加工、RAG 检索、模板报告和回测视角
  - 新增完整知识加工管道（DocumentChunker, DocumentClassifier, EntityExtractor, EventExtractor）
  - 新增 RAG 检索服务（RAGRetrieval）
  - 新增报告生成器（ReportGenerator）支持资产分析、估值、每周回顾等多类型报告
  - 新增采集编排器和调度器（CrawlOrchestrator, CrawlScheduler）
  - 新增闭循环服务（ClosedLoopService）
  - 新增去重服务（DeduplicationService）
  - 新增文档丰富服务（DocumentEnrichment）
  - 新增摘要生成器（SummaryGenerator）
  - 新增论点生成和审查服务（ThesisGeneratorService, ThesisReviewService）
  - 新增分类服务（TaxonomyService）
  - 新增图数据服务（GraphDataService）
- **Web Workbench v1**: 完整股票分析 UI，包含 K 线图、资金流向、五面板展示
  - 仪表盘页面：展示研究进度、信号统计、市场状态
  - 股票分析页面：五面板展示，包含行情、资金、财务、新闻、研报
  - 信号实验室页面：特征工程、标签工程、信号评分、回测分析
  - 决策控制台页面：每日候选审核、决策记录、复盘视图
  - 结果日志页面：Outcome Journal、失败记忆、每周回顾
- **Memory Learning Layer**: 完整的记忆与学习层实现
  - Outcome Journal：结果日志持久化存储
  - Failure Memory：标准化失败分类（wrong_thesis / timing_error / crowding_error / regime_misread / mapping_error / evidence_weakness / execution_error / risk_error）
  - Market Episode：市场事件记忆
  - Learning Journal：学习日志，自动检索相似历史案例
  - 每周回顾报告：自动统计成功率和失败分布
- **Signal Lab Enhancements**: 信号实验室功能完善
  - 完整特征工程框架（Feature、FeatureGroup、FeatureBuilder）
  - 特征组实现（price_volume、valuation、financial、fund_flow、industry、macro）
  - 标签工程框架（Labeler、RelativeReturnLabeler、EventDrivenLabeler）
  - 信号评分系统（SignalScorer、CompositeScorer、ConfidenceScorer、StrengthScorer、HistoricalWinRateScorer、MarketTimingScorer）
  - 信号排名（SignalRanker）
  - 回测引擎（SimpleBacktester、EventStudyBacktester、BacktestResult）
- **Governance & Audit**: 治理与审计系统
  - 版本控制（配置、提示词、策略）
  - 审计日志（所有关键操作记录）
  - 审查工作流（断言、事件、信号的批准/拒绝）
- **Monitoring & Alerting**: 监控与告警系统
  - 健康检查端点
  - 指标采集与监控
  - 可配置阈值告警
  - 漂移检测
- **Paper Trading & Portfolio**: 模拟交易与组合管理
  - 模拟交易服务（PaperTradingService）
  - 组合服务（PortfolioService）
  - 基准比较
- **Decision Console**: 分析师人在回路决策控制台
  - 每日候选审核
  - 决策动作记录
  - 理由捕获
  - 复盘视图
  - 审计追踪
- **AKShare Integration**: 新增 AKShare 开源数据源作为 macOS 降级数据源
  - 自动降级链：iFinD → AKShare → Local → Mock
  - 完整的 AKShare 采集器（市场、财务、新闻、宏观）
  - 统一的工具函数库
  - 数据适配器集成
- **Real Data Ingestion**: 真实数据集成
  - 财联社电报：292条 + 608条30天存档（共900条）
  - 中国证券网新闻：24条
  - 知丘研报：A股、AI、市场、策略、成长、价值、指数等专题（共约747条）
  - 知丘公众号：53条
  - 知丘会议纪要：92条
  - 示例真实事件：5条精选事件
- **Auto Ingest Service**: 全自动数据抓取服务
  - 定时自动抓取财联社、中国证券网、知丘研报、股票数据
  - 内置防爬机制
  - 守护进程模式支持
- **Disaster Recovery**: 灾难恢复系统
  - `scripts/backup_db.py`: 数据库备份脚本
  - `scripts/restore_db.py`: 数据库恢复脚本
  - `scripts/bootstrap_db.py`: 数据库初始化脚本
  - `scripts/import_real_data.py`: 导入真实数据脚本
  - `scripts/minimal_reingest_bootstrap.py`: 最小重摄入引导脚本
  - `scripts/backfill_from_objects.py`: 从对象存储回填脚本
  - `scripts/rebuild_derived_state.py`: 重建派生状态脚本
  - `scripts/smoke_runner.py`: 冒烟测试脚本
- **FastAPI Backend**: 完整的后端 API
  - `/health`: 健康检查
  - `/api/dashboard`: 仪表盘 API
  - `/api/search`: 全局搜索 API
  - `/api/asset`: 资产分析 API
  - `/api/ingest`: 数据摄入 API
  - `/api/events`: 事件 API
  - `/api/signals`: 信号 API
  - `/api/backtest`: 回测 API
  - `/api/signal-lab`: 信号实验室 API
  - `/api/outcomes`: 结果日志 API
  - `/api/memory`: 记忆 API
  - `/api/governance`: 治理 API
  - `/api/monitoring`: 监控 API
- **Alembic Integration**: 数据库迁移系统
  - 初始化 Alembic 配置
  - 初始迁移脚本
- **CLI Enhancements**: 增强的命令行工具
  - `akshare`: AKShare 数据管理命令
  - `ingest`: 数据摄入命令
  - `memory`: 记忆管理命令
  - `review`: 审核管理命令
  - `signal`: 信号管理命令
  - `timing`: 择时分析命令
- **utils**: 修复所有数据源时间解析逻辑，确保所有发布日期精确到秒，只有日期的默认补 00:00:00

### Changed
- **db**: 移除导入时数据库连接副作用，启动检查显式化
  - 数据库连接检查现在在 API 启动和引导/恢复脚本中显式执行，而不是在模块导入时无条件执行
  - 这允许测试、脚本和离线工具导入仓储模块而不需要活动的实时数据库连接，同时在启动入口点保留相同的可操作错误检查
- **docs**: 组织文档到 docs/ 目录
  - `ARCHITECTURE.md` 移到 docs/
  - `CHANGELOG.md` 移到 docs/
  - 新增 `FILE_GUIDE.md`
  - 新增 `backup_restore.md`
  - 新增 `DATA_SOURCES.md`
- **default persistence**: 默认持久化从 SQLite 迁移到 PostgreSQL，SQLite 保留为零配置演示选项
- **mock removed**: 移除模拟数据逻辑，默认使用真实数据，仪表盘显示真实新闻数据，降级情况返回演示数据
- **ingest pipeline**: ingest API 现在对接持久化的文档/断言/事件仓库和共享向量库，所有摄入数据自动持久化并索引到向量库
- **pull sources**: 所有实时源拉取接口现在走完整 envelope ingestion 流程，不再返回原始拉取计数，而是经过完整摄入管道后返回实际成功摄入的文档数量
- **auto signal generation**: 实现已批准事件自动生成候选信号功能，支持审批即时触发和定时扫描自动生成，不需要手动调用流水线
- **outcomes API**: outcomes API 默认使用持久化仓储，新增带信号详情的查询接口，关联信号评估记录和信号详情
- **core contracts**: 大幅扩展核心契约，新增 20+ 契约文件
- **core services**: 核心服务从几个扩展到 40+ 个
- **crawler refactor**: 重构 AKShare 采集器，分离 utils 到独立模块，避免代码重复

### Fixed
- **dashboard**: 修复仪表盘数据问题，给 SignalOutcomeDB 添加 event_type 字段，dashboard 添加空数据降级返回模拟演示数据
- **service startup**: 修复服务启动错误，补全 Query 导入，修改 AssetAnalysisService 参数为可选，现在 Web 可以正常打开
- **asset analysis**: 修复资产分析功能，自动数据源降级，前端隐藏数据源选择
- **signal list**: 修复信号列表 500 错误，修复资产/情景/图按钮绑定
- **AKShare financial**: 修复 AKShare 财务数据解析（新浪财经接口）
- **frontend**: 添加 AKShare 选项到资产源选择器，默认为自动降级
- **Word export**: 修复 Word 文档投影错误
- **Pydantic v2**: 修复 Pydantic v2 弃用接口警告
- **CLI error handling**: 修复 CLI 错误处理
- **vector search ordering**: 修复向量搜索结果排序问题
- **import errors**: 修复导入错误和字段名冲突
- **db initialization**: 修复数据库初始化流程
- **ruff issues**: 修复 ruff 检查问题（未使用导入等）
- **500 errors**: 修复多个 500 错误

## [v0.4.0] - 2025-05-10

### Added
- Web Workbench v1 完整实现
- Memory Learning Layer（记忆与学习层）
- 完整的数据采集管道（AKShare、财联社、中国证券网、知丘）
- RAG 检索服务
- 报告生成器
- 闭循环服务
- 灾难恢复系统
- 监控与告警系统
- 治理与审计系统
- 模拟交易与组合管理
- 决策控制台
- Alembic 数据库迁移

### Changed
- 默认数据库从 SQLite 改为 PostgreSQL
- 移除模拟数据，默认使用真实数据
- 重构数据摄入管道
- 重构 AKShare 集成

## [v0.3.0] - 2025-05-01

### Added
- 信号实验室完整功能
  - 特征工程框架
  - 标签工程框架
  - 信号评分系统
  - 回测引擎集成（vectorbt + Backtrader）
- 候选信号管理与回测说明文档

### Changed
- 完成第三个里程碑：信号验证与核心功能闭环

## [v0.2.0] - 2025-04-01

### Added
- 事件模型与事件存储
- 事实断言模型
- 多情景分析引擎
  - 支持 3-4 个情景输出
  - 每个情景包含概率、关键假设、触发条件、失效信号
- 推理状态机基于 LangGraph 实现
- 怀疑论验证模块

### Changed
- 完成第二个里程碑：事件、断言与多情景分析

## [v0.1.0] - 2025-03-22

### Added
- 🎉 初始提交
- 模块化单体分层架构
- 核心领域契约（Pydantic v2）
- PostgreSQL + pgvector 事实存储
- 资产分析卡功能（覆盖八大维度：财务、资金、量价、估值、股东、产业、事件、宏观）
- 专题研究备忘录功能
- 数据层适配器框架
- Model Gateway 抽象（支持多模型提供商）
- 可观测性三件套（logging/metrics/tracer）
- CLI 命令行工具
- 基础测试用例
- 快速开始文档

### Changed
- 完成第一个里程碑：事实层与报告骨架

---

## 开发路线图

### ✅ 已完成
- [x] v0.1.0: 事实层与报告骨架
- [x] v0.2.0: 事件、断言与多情景分析
- [x] v0.3.0: 信号验证与核心功能闭环
- [x] v0.4.0: Web Workbench v1 + Memory Learning + 完整数据采集

### 🔄 进行中
- [ ] Portfolio OS：风险预算、exposure、factor neutrality、theme exposure、liquidity
- [ ] Evaluation OS：Agent/Signal/Timing/Narrative 系统级评估
- [ ] Feedback Learning：根据市场结果更新权重和模型
- [ ] Ontology Layer：行业、事件、因子、regime 分类体系

### 📋 计划中
- [ ] Market Simulation：模拟游资、机构、北向、ETF、散户对事件的反应
- [ ] Causal Engine：counterfactual、intervention、propagation dynamics
- [ ] Orchestration：DAG workflow、event routing、agent scheduling
- [ ] Execution OS：order routing、slippage、liquidity、execution scheduling
- [ ] Alternative Data：招聘、GPU shipment、GitHub velocity、电力、卫星、海运等
- [ ] Temporal Industry Graph：时间化产业链图谱

---

## 相关文档

- **[README.md](../README.md)** - 项目概述与快速开始
- **[REFERENCE.md](REFERENCE.md)** - 完整参考手册
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 架构文档
- **[FILE_GUIDE.md](FILE_GUIDE.md)** - 文件指南
- **[backup_restore.md](backup_restore.md)** - 备份恢复文档
- **[DATA_SOURCES.md](DATA_SOURCES.md)** - 数据源文档
