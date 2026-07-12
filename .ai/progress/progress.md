# AlphaFoundry 任务进度总索引

本文件为所有任务集的总索引。各任务集的详细进度请查看对应的专用文件。

---

## 任务集列表

| 任务集ID | 状态 | 开始日期 | 完成日期 | 进度文件 |
| --- | --- | --- | --- | --- |
| **AF-AUTO-000** | ✅ 已完成 | 2026-05-10 | 2026-05-11 | [progress_af_auto_000.md](progress_af_auto_000.md) |
| **AF-AUTO-001** | ✅ 已完成 | 2026-05-11 | 2026-05-11 | [progress_af_auto_001.md](progress_af_auto_001.md) |
| **AF-AUTO-002** | ✅ 已完成 | 2026-05-11 | 2026-05-11 | [progress_af_auto_002.md](progress_af_auto_002.md) |
| **AF-AUTO-003** | ✅ 已完成 | 2026-05-13 | 2026-05-13 | [progress_af_auto_003.md](progress_af_auto_003.md) |
| **AF-AUTO-004** | ✅ 已完成 | 2026-05-13 | 2026-05-13 | [progress_af_auto_004.md](progress_af_auto_004.md) |
| **AF-AUTO-005** | ✅ 已完成 | 2026-05-13 | 2026-05-14 | [progress_af_auto_005.md](progress_af_auto_005.md) |
| **AF-AUTO-006** | ✅ 已完成 | 2026-05-14 | 2026-05-18 | [progress_af_auto_006.md](progress_af_auto_006.md) |
| **AF-AUTO-007** | ✅ 已完成 | 2026-05-19 | 2026-05-19 | [progress_af_auto_007.md](progress_af_auto_007.md) |
| **AF-AUTO-009** | ✅ 已完成 | 2026-05-19 | 2026-05-19 | [progress_af_auto_009.md](progress_af_auto_009.md) |
| **cninfo_connector** | ⚠️ 阻塞 / 部分完成 | 2026-06-02 | - | [progress_cninfo_connector.md](progress_cninfo_connector.md) |
| **AF-AUTO-010** | 🔄 进行中 | 2026-06-02 | - | [progress_af_auto_010.md](progress_af_auto_010.md) |
| **AF-AUTO-013** | ✅ 已完成 | 2026-05-30 | 2026-06-03 | [progress_af_auto_013.md](progress_af_auto_013.md) |
| **report-projects-doc-sync-2026-06-08** | ✅ 已完成 | 2026-06-08 | 2026-06-08 | [progress_report_projects_doc_sync.md](progress_report_projects_doc_sync.md) |
| **system-configuration-center** | 🔄 进行中 | 2026-07-12 | - | [progress_system_configuration_center.md](progress_system_configuration_center.md) |

---

## 各任务集摘要

### AF-AUTO-000: 初始仓库审计和验证 ✅

- **目标**: 理解项目当前状态、验证核心功能、建立基线
- **成果**: 20/20 任务全部完成
- **关键**: 仓库基线测试、核心服务验证、数据库初始化、API健康检查、自主控制层标准化
- **测试**: 840 个测试，91% 通过率，49% 覆盖率

### AF-AUTO-001: 测试修复和覆盖提升 ✅

- **目标**: 修复失败的测试、提高测试覆盖率、完成推理层剩余TODO项
- **成果**: 12/12 任务全部完成
- **关键**: API测试修复、数据库测试修复、Signal Lab测试、新增58个测试
- **测试**: 836 个测试通过 (93.1%)，覆盖率提升至 51%

### AF-AUTO-002: 数据摄入和报告模板 ✅

- **目标**: 持续市场数据摄入系统、模板驱动的报告生成系统 (DOCX/PPTX)
- **成果**: 16/16 任务全部完成
- **关键**: CrawlScheduler、增量摄入、反爬虫策略、PDF摄入、模板管理API、Web UI
- **测试**: 新增 189 个测试，全部通过

### AF-AUTO-003: UI设计规范落地和Playwright调试 ✅

- **目标**: 根据docs/design/和docs/frontend/中的设计规范实现终端美学风格
- **成果**: 15/15 任务全部完成 + 1个后续修复
- **关键**: 设计令牌CSS变量、终端美学配色、JetBrains Mono字体、信息密度优化、Playwright验证
- **修复**: Dark Mode 循环引用问题已修复

### AF-AUTO-004: 集成真实新闻和板块变化数据 ✅

- **目标**: 从DocumentV1、CanonicalEvent和AlphaSignal中提取真实数据用于市场概览仪表盘
- **成果**: 8/10 任务已完成 + 1 个跳过
- **关键**: 新增DashboardDataRepository、真实数据优先 + 智能回退机制、板块/概念分类
- **测试**: 10/10 dashboard相关测试全部通过
- **未完成**: UI增强和自动刷新功能（留作未来迭代）

### AF-AUTO-005: 全面实现Web UI真实数据接入 ✅

- **目标**: 全面实现Web UI真实数据接入,自动实时获取所有数据源,移除对模拟数据的依赖
- **成果**: 9/9 任务已完成（100%）
- **关键**: 修复DashboardService回退逻辑Bug、资产分析默认使用真实数据、所有板块添加模拟数据回退机制、产业链图谱添加默认数据、调度器API集成、端到端验证通过
- **测试**: scripts/test_fix.py 验证所有板块正常工作,Playwright浏览器测试通过

### AF-AUTO-006: PDF to Markdown 转换管道 ✅

- **目标**: 完整实现 PDF 到 Markdown 的转换管道，支持三策略自动降级
- **成果**: 12/12 任务已完成（100%）
- **关键**: MinerU/MarkItDown/RawText 三策略、自动降级、磁盘持久化、DocumentV1 自动创建、Admin API、50 个测试全部通过

### cninfo_connector: 巨潮资讯三层数据源与预存问题修复 ⚠️

- **目标**: 将巨潮资讯公告接入升级为 crawler / adapter / connector 三层结构，并修复 source registry / fallback route / Wind Excel 自动启动回归问题
- **成果**: 实现、测试、文档和报告已完成；因全量 mypy 门禁失败，状态保持阻塞 / 部分完成
- **关键**: CNINFO wrapper-first 实现、`daily_quotes_cn -> cjpy -> wind -> baostock` 降级链排序、Wind Excel 未运行时自动启动回归覆盖
- **测试**: 全量 pytest 通过（1556 passed, 1 skipped, 31 warnings）；ruff/black/isort/doc/task checks 通过；全量 mypy 失败
- **阻塞**: repository-wide mypy 类型债和缺失 vendor SDK/stub 问题，详见 [blocking_report_cninfo_connector.md](../reports/blocking_report_cninfo_connector.md)

---

## 文件结构

```text
.ai/progress/
├── progress.md                    # 本文件 - 总索引
├── progress_af_auto_000.md        # AF-AUTO-000 详细进度
├── progress_af_auto_001.md        # AF-AUTO-001 详细进度
├── progress_af_auto_002.md        # AF-AUTO-002 详细进度
├── progress_af_auto_003.md        # AF-AUTO-003 详细进度
├── progress_af_auto_004.md        # AF-AUTO-004 详细进度
├── progress_af_auto_005.md        # AF-AUTO-005 详细进度
├── progress_af_auto_006.md        # AF-AUTO-006 详细进度
├── progress_af_auto_007.md        # AF-AUTO-007 详细进度
├── progress_af_auto_009.md        # AF-AUTO-009 详细进度
└── progress_cninfo_connector.md   # cninfo_connector 详细进度
```

---

## 规则

每个新任务集必须：

1. 创建对应的 `progress_af_auto_XXX.md` 文件
2. 在本总索引中添加条目
3. 任务完成后更新状态和完成日期

---

### AF-AUTO-010: 仓库级 mypy 类型修复 🔄

- **目标**: 系统性修复全量 mypy 失败，清理类型债
- **成果**: Session 1 — 修复 transformers INTERNAL ERROR、建立基线（~2219 errors）。Session 2 — 修复 20 个文件、core/contracts 和 core/observability 清零、signal_lab 类型修正、全部验证命令通过
- **关键**: pyproject.toml mypy overrides、Pydantic Field() 兼容、np.asarray() 类型安全、Literal 返回类型
- **剩余**: 2065 errors（585 no-untyped-def、359 assignment、352 arg-type、254 attr-defined、216 no-any-return、165 call-arg）
- **阻塞**: 无 — 任务持续进行中，预计需要多会话完成

---

### AF-AUTO-013: 资产分析页面 ETF 搜索 + 数据空字段修复 ✅

- **目标**: 修复 ETF 搜索 404 + 补齐资产分析卡全空字段（估值、换手率、行业、股东、事件、宏观）
- **成果 - ETF 搜索**: AKShare `fund_etf_spot_em` 24h 缓存，ETF 前缀→交易所映射，搜索 159267 可匹配
- **成果 - Wind 直连 (Phase 1-3)**: `fetch_market_snapshot()` 补齐 PE/PB/PCF/市值/换手率；行业 level2/3 Wind fallback；股东聚合指标 Wind fallback
- **成果 - 前十大股东明细**: 4 级数据源优先级 (DB→Wind 逐项→Wind 聚合→AKShare)，AKShare adapter 从 mock 改为真实 API，Wind 按排名公式新增
- **成果 - 近期事件**: 3 级 fallback (DocumentEventV1DB→CanonicalEvent→AKShare 公告)，`_map_to_event_impact()` 统一映射
- **成果 - 宏观敏感性**: `MacroSensitivityCalculator` + OLS 回归，Cjpy 批量获取+`numpy.linalg.lstsq`，5 个 Beta 系数，优雅降级
- **测试**: 25/25 passed（9 资产分析 + 16 宏观敏感性）
- **质量门**: ruff ✅ black ✅ isort ✅ mypy (0 new) ✅ pytest ✅ doc sync ✅

---

### report-projects-doc-sync-2026-06-08: 报告项目 Markdown 文档同步与剩余风险清理 ✅

- **目标**: 按 `CLAUDE.md` 文档同步规范更新长期未同步的 Markdown 文档，覆盖 `report_projects` API、模板工作台、项目级报告生成、图表嵌入和华安 ETF 周报配置。
- **成果**: 已读取规则和相关文档，扫描 Markdown 文件，更新 README、ARCHITECTURE、DEVELOPMENT_MAP、REFERENCE、FILE_GUIDE、CHANGELOG、数据源/存储文档和模块文档；后续清理 full-gate mypy/静态测试风险。
- **验证**: `generate_py_file_index`、`check_doc_sync`、`check_task_completion`、ruff、black、isort、mypy 均通过；全量 pytest `1680 passed, 4 skipped`。

---

### report_project_run_module: 报告项目运行编排 seam 🔄

- **目标**: 将 `/api/report-projects/{slug}/render` 的 Word/PPT 生成编排、run-log 写入和 warning 聚合从 FastAPI route 收拢到 reporting module。
- **成果**: 新增 `ReportProjectRunService`；route 改为读取项目和配置后委托 service；补充 service 级测试、实施计划、模块文档、架构文档、文件指南、changelog 和 Python 文件索引。
- **验证**: focused render tests 5/5 passed；`ruff`、`black --check`、`isort --check-only`、targeted `mypy` 通过。
- **剩余**: broader report suite 78 passed / 1 failed，失败为现有华安 ETF 配置缺少测试期待的 `type: prompt` 占位符；full repository gate 未运行。

---

### report_project_compiled_plan: 报告项目生成预检计划 ✅

- **目标**: 把报告项目生成前的 prompt / retrieval / deterministic 占位符就绪度抽成后端 `CompiledReportPlan`，并让前端生成中心优先使用该计划。
- **成果**: 新增 `reporting/projects/plan.py`；report projects API 返回 `compiled_plan`；模板工作台 preflight 接入后端计划，并按 Prompt 覆盖、Evidence 覆盖、输出资产分组展示；新增“优先处理”任务队列、Evidence 抽样、本期设置条和交付检查卡；修正华安配置漂移测试；补充模块/API/架构/文件指南/changelog 和测试报告。
- **验证**: backend plan tests、focused API test、focused frontend static test、ruff、black --check、isort --check-only、targeted mypy 通过；broader focused report-project suite 132 passed / 22 warnings；模板工作台静态回归 59 passed。

---

### system-configuration-center: 系统配置中心 🔄

- **目标**: 在桌面工作台集中、安全地管理 LLM、知秋、iFinD、数据库和高级运行参数。
- **成果**: 五分区配置 API/Web 页面、秘密脱敏与显式清除、路径级线程/进程锁和原子 dotenv 写入、可安全字段热更新、数据库重启提示、真实非持久化连接探针，以及旧知秋账号兼容均已实现。
- **验证**: 后端 `65 passed`；配置前端 `13 passed`；合并前端回归 `96/98`，2 项为既有基线失败。
- **剩余**: 浏览器交互验证与全仓门禁未运行，任务和 metadata 保持 `doing`。

---

**最后更新**: 2026-07-12（system-configuration-center 文档与审计同步）
