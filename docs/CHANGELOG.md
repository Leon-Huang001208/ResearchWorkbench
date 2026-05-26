# 更新日志

所有 notable 项目变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Fixed
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
  - 新增 `core/services/crawler_ingestion_bridge.py`：CrawlerIngestionBridge (爬虫输出统一转 DocumentEnvelope → EnqueueRequest → 入队)
  - 新增 `core/services/system_event_bus.py`：SystemEventBus (内存事件总线, SSE 推送, worker heartbeat)
  - 新增 `workers/knowledge_worker.py`：常驻后台 worker (asyncio, 自动消费 ingestion_queue, 调用 KnowledgePipeline)
  - 新增 `app/api/routes/system.py`：GET /api/system/health 和 /api/system/health/minimal 端点
  - 新增 `app/api/routes/realtime.py`：GET /api/realtime/stream SSE 实时推送端点
  - 新增 `scripts/start_all.sh` + `scripts/stop_all.sh`：一键启动/停止全系统 (API + scheduler + knowledge worker)
  - 新增 `ingestion/__init__.py`：ingestion 包初始化
  - **修复**: DataSourceRouter 中 AKShareAdapter 缺失 import + 名称不匹配 (AkShareAdapter → AKShareAdapter)
  - **增强**: CrawlOrchestrator._fetch_from_adapter() 从 stub 升级为真实适配器调用 (CLSAdapter/CNStockAdapter/ZQAdapter) + 自动 enqueue
  - **增强**: 前端 app.js 接入 EventSource SSE 实时流 (document_parsed/event_created/signal_generated/queue_update/error_alert)
  - 新增 `tests/unit/core/services/test_crawler_ingestion_bridge.py`：6 个 bridge 测试
  - 新增 `tests/unit/data_layer/adapters/test_akshare_adapter.py`：6 个 adapter/router 测试
  - 新增 `tests/unit/core/services/test_system_event_bus.py`：4 个 event bus 测试
  - 新增 `tests/unit/app/api/routes/test_system_realtime.py`：2 个 API 端点测试
  - 新增 `tests/unit/workers/test_knowledge_worker.py`：3 个 worker 测试
- **concurrent-llm-extraction**: 数据提取管道升级 — 从单次串行 LLM 调用升级为 chunk 切分 + ThreadPoolExecutor 并发 + 去重
  - 新增 `knowledge_layer/extraction/text_chunker.py`：轻量级滑动窗口文本切分器 (split_text)
  - 新增 `knowledge_layer/extraction/concurrent_extractor.py`：ConcurrentLLMExtractor (并发 LLM 抽取, 重试, 统计)
  - 重构 `core/services/ingest_service.py`：所有入口统一走 ingest_envelope() 管道，长文本自动切 chunk 并发提取
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
  - 新增 `core/services/market_data_ingestion_service.py`：ETL 编排服务 (fetcher → normalizer → repository → etl_run)
  - 新增 `app/api/routes/market_data.py`：Market Data API (stocks/sync, daily-bars/sync, daily-bars query, etl-runs)
  - 重构 `core/services/asset_analysis_service.py`：优先从结构化表生成 snapshot，回退到 coordinator
  - 更新 `cron_jobs/auto_ingest_service.py`：分步执行 15:15 股票列表 → 15:30 日行情 → 15:45 资产快照
  - 新增 `tests/unit/data_layer/normalizers/`：12 个 normalizer 单测
  - 新增 `tests/unit/data_layer/repositories/test_market_data_repository.py`：8 个 repository 测试
  - 新增 `tests/unit/data_layer/repositories/test_etl_run_repository.py`：5 个 ETL run 测试
  - 新增 `tests/unit/core/services/test_market_data_ingestion_service.py`：4 个 ingestion service 测试
  - 新增 `storage/migrations/versions/009_add_structured_market_data_tables.py`：Alembic 迁移 (8 张市场数据表)
  - 新增 `scripts/check_market_data_schema.py`：Schema 验证脚本 (检查 8 张表是否存在)
  - 新增 `scripts/bootstrap_market_data.py`：初始化数据填充脚本
  - **修复**: `app/api/routes/assets.py` 中 `get_asset_service()` 注入 `MarketDataRepository`，使结构化表路径可用
  - **修复**: `core/services/asset_analysis_service.py` 增加 `_has_enough_structured_data` 数据质量检查，防止空表数据被错误当作"结构化路径已启用"
  - **修复**: `tests/unit/test_asset_analysis_service.py` 适配新的构造函数签名和 async 接口
- **pdf-conversion-pipeline**: 完整的 PDF 到 Markdown 转换管道
  - 新增 `core/contracts/pdf_conversion.py`：Pydantic 契约 (ConversionResult, StrategyType, ConversionStatus)
  - 新增 `data_layer/converters/base.py`：PDFConversionStrategy 抽象基类
  - 新增 `data_layer/converters/raw_text.py`：RawTextStrategy (pdfplumber, 始终可用)
  - 新增 `data_layer/converters/markitdown.py`：MarkItDownStrategy (microsoft/markitdown)
  - 新增 `data_layer/converters/mineru.py`：MinerUStrategy (opendatalab/mineru)
  - 新增 `data_layer/converters/persistence.py`：磁盘持久化工具 (data/markdown/, data/raw_text/)
  - 新增 `core/services/pdf_conversion_service.py`：PDFConversionService 核心编排
  - 新增 `core/settings/config.py`：PDF 输出目录和阈值配置
  - 新增 `app/api/routes/pdf_admin.py`：Admin API (convert/stats/pending/retry)
  - 新增 `docs/modules/pdf_conversion_pipeline.md`：模块文档
  - 新增 `tests/unit/core/services/test_pdf_conversion_service.py`：27 个服务层测试
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

### Changed
- **refactor**: 深化搜索服务模块，隐藏 SQLAlchemy session 依赖
  - 重构 `core/services/search_service.py`：GlobalSearchService 现在依赖 SearchRepository 接口而非直接依赖 session
  - 更新 `app/api/routes/search.py`：创建 SearchRepositoryImpl 并注入 GlobalSearchService
- **refactor**: 深化事件摄入模块，移除冗余的服务层
  - 删除 `core/services/event_ingestion_service.py`：该服务只是对 `StructuredEventIngestor` 和仓储的简单包装
  - 将自动断言提取功能直接集成到 `ingestion/structured_event_ingestion.py`：`StructuredEventIngestor` 现在会在 `ingest()` 和 `bulk_ingest()` 时自动提取断言
  - 更新 `app/api/routes/event_ingestion.py`：直接使用 `StructuredEventIngestor` 和 `EventRepositoryImpl`，移除中间服务层
  - 添加 `EventQueryResponse` 数据类到 API 路由模块
  - 添加测试用例验证自动断言提取功能
- **refactor**: 深化时序引擎模块，移除冗余的服务层
  - 删除 `core/services/timing_engine_service.py`：该服务只是对数据类的简单包装
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

