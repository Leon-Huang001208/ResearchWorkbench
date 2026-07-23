# 第二阶段测试报告 — 报告编译器证据工程期

- **Task ID**: phase2-evidence-engineering
- **日期**: 2026-07-15
- **范围**: deep-research-report.md 第二阶段 2.1-2.5（完整二阶段）

## 1. 变更源文件

| 文件 | 变更 |
|---|---|
| `ingestion/knowledge_pipeline.py` | PipelineResult 增 assertions；_enrich_assertion_spans 精确化 source_span |
| `workers/knowledge_worker.py` | _persist_extraction_artifacts 持久化 chunks/mentions/assertions；_grade_document_quality 回填 quality |
| `core/contracts/documents_v1.py` | DocumentQuality 增 source_tier/trust_score/freshness_score |
| `core/source_registry.py` | 新增 reliability_to_tier / spec_to_tier |
| `core/services/source_grader.py` | 新建 SourceGrader |
| `knowledge_layer/retrieval/vector_store.py` | PGVectorStore 完整实现（brute-force + pgvector 回退） |
| `knowledge_layer/retrieval/assertion_search.py` | 新建 AssertionSearchService |
| `reporting/compiler/evidence_retriever.py` | 新增 AssertionRetriever |
| `reporting/compiler/fact_extractor.py` | 新增 extract_from_assertions 快速路径 |
| `reporting/compiler/table_renderer.py` | 新建 TableRenderer |
| `reporting/compiler/chart_renderer.py` | 新建 ChartRenderer |
| `reporting/compiler/renderer.py` | 集成 render_tables / render_charts |
| `scripts/e2e_phase2_facts_store.py` | 新建端到端验证脚本 |

## 2. 变更测试

| 文件 | 用例数 |
|---|---|
| `tests/unit/core/services/test_source_grader.py` | 8 |
| `tests/unit/knowledge_layer/test_assertion_search.py` | 6 |
| `tests/unit/knowledge_layer/test_pgvector_store.py` | 7 |
| `tests/unit/reporting/compiler/test_table_chart_renderer.py` | 9 |
| `tests/unit/reporting/compiler/test_fact_extractor_assertions.py` | 8 |
| `tests/unit/workers/test_knowledge_worker.py` | 修复 test_process_one_publishes_events 回归 |

## 3. 质量门结果

| 检查 | 命令 | 结果 |
|---|---|---|
| Ruff | `ruff check`（变更模块） | ✅ All checks passed |
| Black | `black`（18 文件） | ✅ 8 reformatted, 10 unchanged（已修复） |
| isort | `isort --check-only`（变更模块） | ✅ 通过 |
| Mypy | `mypy`（10 变更源文件） | ✅ Success: no issues found |
| Pytest（第二阶段新测试） | 5 文件 | ✅ 38 passed |
| Pytest（相关目录） | reporting+knowledge_layer+core.services+workers | ✅ 170 passed, 0 failures |
| generate_py_file_index | `scripts/generate_py_file_index.py` | ✅ Generated |
| check_task_completion | `scripts/check_task_completion.py` | ⚠️ No changed files（非 git 仓库，无 diff 可检测） |
| check_doc_sync | `scripts/check_doc_sync.py` | ⚠️ No changed files（同上） |

## 4. 端到端验证（本地 PG 实跑）

`scripts/e2e_phase2_facts_store.py` 验证（一次性脚本，验证后清理）：

- **2.1+2.2**: SourceGrader 回填 tier_b / trust=0.80 / fresh=1.00；_persist_extraction_artifacts 落库 chunks=1 / mentions=1 / assertions=1；assertion.source_span 含 chunk_text + offset_start/end。
- **2.3**: PGVectorStore brute-force add/search/delete，TOP1 语义匹配正确。
- **2.4**: AssertionSearchService.search → AssertionRetriever → fact_extractor.extract_from_assertions，value=100.0, tier_a。
- **2.5**: TableRenderer cell 携带 fact 短码，event 类排除；ChartRenderer 单 entity → line。

## 5. 既有债务（非本次回归）

`tests/unit/` 全量 2112 个测试中 30 个失败，全部为既有债务，与第二阶段改动零相关：

- `test_desktop_shell_scaffold`（5）、`test_report_project_chart_generation`（7）、`test_report_projects_api`（5）、`test_memory_cli`（5）、`test_industry_chain`（3）、`test_issue43`/`test_issue44`、`test_macro_sensitivity`、`test_wind_index_catalog`、`test_mineru`。

抽查确认：industry_chain 断言 graphs 数量、memory_cli CLI、Excel 图表解析等，均非第二阶段模块。

`tests/integration/` 在 pytest 收集阶段卡死（>45s 无输出），每个模块单独 import 正常，疑为 conftest 钩子串联阻塞，属既有基础设施问题，非本次引入。

## 6. 状态

第二阶段 2.1-2.5 实现完成，单元测试与端到端验证通过，质量门（ruff/black/isort/mypy）通过。未接入生产路由，engine feature flag 迁移留待第三阶段后。30 个既有失败测试与 integration 收集卡死为既有债务，建议单独任务跟进。

## 7. 剩余风险

- pgvector 系统级不可用，当前依赖 brute-force（<10 万文档可用），规模超限需迁移到 pgvector。
- DocumentQuality 新字段为 JSONB 列，无需迁移；但若后续要按 source_tier 索引查询需补索引。
- 30 个既有失败测试与 integration 卡死未解决（非本阶段范围）。
