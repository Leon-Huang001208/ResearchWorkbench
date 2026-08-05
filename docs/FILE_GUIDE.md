# AlphaFoundry 文件指南

本指南详细说明项目中每个主要文件和目录的作用，帮助新开发者快速理解项目结构。

---

## 目录

1. [项目根目录文件](#项目根目录文件)
2. [app/ - 应用层](#app---应用层)
3. [core/ - 核心层](#core---核心层)
4. [connectors/ - 数据源连接器实现](#connectors---数据源连接器实现)
5. [data_layer/ - 数据层](#data_layer---数据层)
6. [knowledge_layer/ - 知识层](#knowledge_layer---知识层)
7. [reasoning/ - 推理层](#reasoning---推理层)
8. [cognitive_agents/ - 认知 Agent 层](#cognitive_agents---认知-agent-层)
9. [timing_engine/ - 择时层](#timing_engine---择时层)
10. [memory_learning/ - 记忆与学习层](#memory_learning---记忆与学习层)
11. [reporting/ - 报告层](#reporting---报告层)
12. [signal_lab/ - 信号实验室](#signal_lab---信号实验室)
13. [storage/ - 存储层](#storage---存储层)
14. [ingestion/ - 结构化摄入模块](#ingestion---结构化摄入模块)
15. [cron_jobs/ - 定时任务](#cron_jobs---定时任务)
16. [scripts/ - 脚本工具](#scripts---脚本工具)
17. [tests/ - 测试](#tests---测试)
18. [docs/ - 文档](#docs---文档)

---

## 项目根目录文件

| 文件/目录 | 说明 |
|---|---|
| `README.md` | 项目主文档，包含概述、快速开始、核心特性、使用指南 |
| `pyproject.toml` | 项目配置文件，包含 black、isort、ruff、pytest、mypy error-code debt list 等工具配置 |
| `pytest.ini` | Pytest 测试框架配置 |
| `.env.example` | 环境变量模板，复制为 `.env` 后使用 |
| `.gitignore` | Git 忽略文件配置 |
| AGENTS.md | 已跟踪的跨工具 Agent 规则入口 |
| .agents/skills/ | 已跟踪的项目工作流与金融数据 skills |
| .claude/ | 本机 Claude 可选配置；被 Git 忽略，不作为共享规则来源 |
| `app/` | 应用层，包含 API、CLI、Web 界面 |
| `core/` | 核心层，包含契约、接口、服务等 |
| `data_layer/` | 数据层，包含仓储实现和数据访问 |
| `data_sources/` | 数据源注册模块，每个 .py 文件自动发现并注册一个数据源 |
| `connectors/` | 数据源连接器实现，分 document/ 和 market/ 子包 |
| `knowledge_layer/` | 知识层，包含知识处理和图谱 |
| `reasoning/` | 推理层，包含推理引擎和 Agent |
| `cognitive_agents/` | 认知 Agent 层，包含多 Agent 协作 |
| `timing_engine/` | 择时层，包含择时引擎和回测 |
| `memory_learning/` | 记忆与学习层，包含结果日志和失败记忆 |
| `reporting/` | 报告层，包含报告生成和模板 |
| `signal_lab/` | 信号实验室，包含特征工程、标签生成、回测 |
| `storage/` | 存储层，包含 Alembic 迁移和数据库架构 |
| `ingestion/` | 结构化摄入模块，包含结构化事件摄入器 |
| `cron_jobs/` | 定时任务目录，包含自动数据摄入服务等 |
| `scripts/` | 脚本工具，包含数据初始化、备份、测试等脚本 |
| `tests/` | 测试目录，包含单元测试、集成测试等 |
| `docs/` | 文档目录，包含项目文档、架构设计、文件指南等 |
| `data/` | 运行时数据目录；其中受版本控制的 `data/industry_graphs/` 提供内置产业链图谱，其余缓存和原始数据通常不提交 |
| `logs/` | 日志目录，存放应用日志、Web 服务日志等 |
| `backups/` | 备份目录，存放数据库备份 |
| `benchmarks/` | 基准数据目录，存放真实数据存档 |
| `examples/` | 示例代码目录 |

---

## app/ - 应用层

### app/api/ - FastAPI 后端接口

| 文件/目录 | 说明 |
|---|---|
| `app/api/main.py` | API 入口点，初始化 FastAPI 应用，注册所有路由；显式分支预览模式只保留就绪检查，不执行数据库初始化或自动后台服务 |
| `app/api/models.py` | API 请求/响应模型（Pydantic） |
| `app/api/routes/audit.py` | 审计 API：查询审计日志 |
| `app/api/routes/dashboard.py` | 仪表盘 API：获取仪表盘汇总数据 |
| `app/api/routes/funds.py` | 基金智能 API：基金详情、单基金暴露、基金组合穿透、结构化 rows 导入 |
| `app/api/routes/governance.py` | 治理 API：版本控制、配置管理 |
| `app/api/routes/ingest.py` | 数据摄入 API：上传文件、拉取实时源 |
| `app/api/routes/ingest_admin.py` | 摄入管理 API：手动触发、暂停/恢复、重置和来源配置；`dry_run` 不访问数据库 |
| `app/api/routes/market_data.py` | 市场数据 API：同步股票列表、同步日行情、查询日行情、查询 ETL 运行记录 |
| `app/api/routes/memory.py` | 记忆 API：查询失败记忆、市场事件记忆 |
| `app/api/routes/monitoring.py` | 监控 API：健康检查、指标、告警 |
| `app/api/routes/outcome_journal.py` | 结果日志 API：记录结果、查询相似案例 |
| `app/api/routes/pipeline.py` | 管道 API：运行数据处理管道 |
| `app/api/routes/report.py` | 报告 API：生成各类报告 |
| `app/api/routes/report_projects.py` | 报告项目 API：列出/重命名/排序项目，保存 `report_config.yaml` / `prompt_templates.md` 源码，返回 `compiled_plan` 生成预检计划，委托 `ReportProjectRunService` 配置驱动生成 DOCX/PPTX，返回下载和 HTML 预览入口 |
| `app/api/routes/scenarios.py` | 情景 API：生成多情景分析 |
| `app/api/routes/search.py` | 搜索 API：全局跨对象搜索 |
| `app/api/routes/signal_lab.py` | 信号实验室 API：特征、标签、评分、回测 |
| `app/api/routes/system.py` | 系统 API：健康检查、队列深度、Worker 心跳，以及仅限 API 根进程树的资源快照与历史；资源服务按请求懒加载，异常降级仅返回稳定公开码 |
| `app/api/routes/realtime.py` | 实时 API：SSE 事件推送、实时数据流 |

### app/cli/ - 命令行工具

| 文件/目录 | 说明 |
|---|---|
| `app/cli/main.py` | CLI 入口点，定义主命令组和子命令 |
| `app/cli/commands/akshare.py` | AKShare 数据管理命令：获取行情、财务、新闻、股票列表 |
| `app/cli/commands/ingest.py` | 数据摄入命令：从文件或源摄入数据 |
| `app/cli/commands/memory.py` | 记忆管理命令：记录事件、记录失败、搜索相似、生成回顾 |
| `app/cli/commands/review.py` | 审核管理命令：列出待审核、批准、拒绝、查看统计 |
| `app/cli/commands/signal.py` | 信号管理命令：创建、列出、验证、升级、生成候选 |
| `app/cli/commands/timing.py` | 择时分析命令：运行择时评估 |

### app/web/ - Web 工作台界面

| 文件/目录 | 说明 |
|---|---|
| `app/web/templates/index.html` | Web 工作台主页面，包含侧边栏导航和所有 section 面板 |
| `app/web/static/style.css` | 全局样式表，包含管线监控、仪表盘等所有页面样式 |
| `app/web/static/js/app.js` | 主入口模块：导航路由、SSE 连接、全局状态管理 |
| `app/web/static/js/configuration.js` | 系统配置模块：加载并保存工作台配置、保护秘密字段、处理环境变量锁定和配置模态框事件绑定；该模块由主入口静态导入，必须保持可解析和可执行 |
| `app/web/static/js/core.js` | 核心工具模块：apiCall、toast、esc 等公共函数 |
| `app/web/static/js/dashboard.js` | 仪表盘模块：Market Overview + Live Monitor 标签页 |
| `app/web/static/js/funds.js` | 基金情报模块：基金详情查询、经理/持仓/行业暴露渲染、基金组合穿透计算、结构化 rows 导入 |
| `app/web/static/js/templates.js` | 模板工作台模块：报告项目选择、Word 占位符映射、YAML/Markdown Prompt 源码切换与保存、后端 `compiled_plan` 生成预检、配置驱动生成、下载和 Word HTML 预览 |
| `app/web/static/js/pipeline-monitor.js` | 管线监控模块：5 阶段流程可视化、实时活动日志（SSE + 15s 轮询）、累计统计、手动触发闭环 |
| `app/web/static/js/monitor.js` | 系统监控模块：Worker 心跳、队列深度、服务状态 |
| `app/web/static/js/resource-monitor.js` | AlphaFoundry 受控资源监控：页面可见且激活时轮询快照/300 秒历史（最多 150 点）与持久化异常（默认 90 天）；展示独立 Worker 精确资源、API 内任务共享估算、置顶异常、确认/解决和安全历史筛选 |
| `app/web/static/js/asset.js` | 资产分析模块：Wind 风格 5 面板 K 线图（K 线+成交量/MACD/KDJ/RSI，首次加载默认请求近一年数据，支持日/周/月聚合与 MA120/MA250）、筹码分布图（筹码峰及上/下界标注）、资产搜索、分析卡渲染 |

---

## core/ - 核心层

### core/contracts/ - Pydantic 领域契约

所有跨层数据交换都遵循这些契约，保证类型安全和数据验证。

| 文件 | 说明 |
|---|---|
| `core/contracts/__init__.py` | 导出所有契约，方便导入 |
| `core/contracts/assertions.py` | 事实断言结构：Assertion、AssertionStatus |
| `core/contracts/assets.py` | 资产定义结构：Asset、AssetType、AssetSnapshot、ChipDistributionPoint、PriceBar（含 KDJ/RSI/BOLL/MACD 技术指标字段） |
| `core/contracts/backtest.py` | 回测结构：BacktestResult、BacktestMetrics |
| `core/contracts/dashboard.py` | 仪表盘结构：DashboardSummary、RecentNews、MarketStatus |
| `core/contracts/decision_console.py` | 决策控制台结构：DailyCandidate、DecisionRecord |
| `core/contracts/documents_v1.py` | 文档结构 v1：DocumentEnvelope、DocumentType、DocumentMetadata |
| `core/contracts/events.py` | 事件结构：CanonicalEvent、EventType、DiffusionStage、MarketRegime |
| `core/contracts/funds.py` | 基金智能结构：基金主数据、日净值、持仓、经理、收益风险指标和穿透暴露 |
| `core/contracts/governance.py` | 治理结构：VersionRecord、ConfigRecord、AuditLog |
| `core/contracts/industry_chain.py` | 产业链结构：IndustryNode、IndustryRelation、IndustryChain |
| `core/contracts/ingestion.py` | 摄入结构：IngestionRequest、IngestionResult |
| `core/contracts/monitoring.py` | 监控结构：HealthStatus、MetricRecord、AlertRecord |
| `core/contracts/outcome_journal.py` | 结果日志结构：SignalOutcome、OutcomeType、FailureRecord |
| `core/contracts/outcomes.py` | 结果结构：Outcome、OutcomeMetrics |
| `core/contracts/paper_trading.py` | 模拟交易结构：PaperAccount、PaperOrder、PaperTrade |
| `core/contracts/portfolio.py` | 组合结构：Portfolio、Position、PortfolioMetrics |
| `core/contracts/raw_storage.py` | 原始存储结构：RawFile、RawStorageMetadata |
| `core/contracts/replay.py` | 回放结构：ReplaySession、ReplayStep、ReplayResult |
| `core/contracts/reporting.py` | 报告结构：Report、ReportType、ReportSection、ReportTemplate |
| `core/contracts/retrieval.py` | 检索结构：SearchQuery、SearchResult、RAGContext |
| `core/contracts/review_framework.py` | 审查框架结构：ReviewTask、ReviewComment、ReviewStatus |
| `core/contracts/scenarios.py` | 情景结构：ScenarioSet、Scenario、ScenarioProbability |
| `core/contracts/signals.py` | 信号结构：AlphaSignal、EventAlphaSignal、SignalStatus、TradeCandidate |
| `core/contracts/timing_engine.py` | 择时引擎结构：TimingFactors、EventStudyMetrics、ReadinessScore。ReadinessScore 包含 should_block() 和 get_blocking_reason() 方法用于阻塞检查 |
| `core/contracts/traces.py` | 推理追踪结构：ReasoningTrace、TraceStep、EvidenceLink |

### core/interfaces/ - 核心接口定义

| 文件 | 说明 |
|---|---|
| `core/interfaces/repository.py` | 仓储接口：Repository、CrudRepository、QueryRepository |

### core/model_gateway/ - 模型网关

| 目录/文件 | 说明 |
|---|---|
| `core/model_gateway/local_embedding_config.py` | 本地 embedding 模型解析：支持 `ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH`，默认 Hugging Face cache-only，只有 `ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD=1` 才允许联网下载 |
| `core/model_gateway/providers/` | 模型提供商实现 |
| `core/model_gateway/providers/volcano.py` | 火山引擎提供商实现 |

### core/observability/ - 可观测性

| 文件 | 说明 |
|---|---|
| `core/observability/__init__.py` | 可观测性模块初始化 |
| `core/observability/metrics.py` | 指标定义和记录：counter、gauge、histogram |

### core/connectors/ - 统一数据源连接器抽象

| 文件 | 说明 |
|---|---|
| `core/connectors/__init__.py` | 导出所有连接器组件 |
| `core/connectors/base.py` | 基础连接器：`BaseConnector`、`DocumentConnector`、`MarketDataConnector` ABC |
| `core/connectors/registry.py` | 连接器注册表：`ConnectorRegistry`、模块级单例 |

### core/adapters/ - 核心适配器

| 文件 | 说明 |
|---|---|
| `core/adapters/__init__.py` | 适配器包初始化 |
| `core/adapters/event_adapter.py` | 事件适配器：将系统事件转换为标准化格式，用于跨层通信 |

### core/source_registry.py - 数据源注册中心

| 文件 | 说明 |
|---|---|
| `core/source_registry.py` | `SourceSpec` frozen dataclass + `register()`/`get()`/`get_all()`/`get_enabled()`/`get_by_family()`。所有消费者从此读取；`connector_class` 是 canonical 连接器路径，`adapter_class` 仅为历史兼容别名。 |
| `data_sources/__init__.py` | `pkgutil.iter_modules` 自动发现目录下所有 `.py` 模块 |
| `data_sources/cls.py` | 财联社 (CLS) 源注册 |
| `data_sources/cnstock.py` | 中国证券网 (CNSTOCK) 源注册 |
| `data_sources/cnstock_flash.py` | 中国证券网·快讯 源注册 |
| `data_sources/zhiqiu_reports.py` | 知丘研报 源注册 |
| `data_sources/zhiqiu_wechat.py` | 知丘公众号 源注册 |
| `data_sources/zhiqiu_transcript.py` | 知丘纪要 源注册 |

### services/ - 业务服务（40+ 个服务）

这是系统的核心逻辑层，所有业务功能都在这里实现。

| 文件 | 说明 |
|---|---|
| `services/__init__.py` | 导出所有服务 |
| **资产分析** | |
| `asset_analysis_service.py` | 资产分析服务：生成资产分析快照、K线技术指标计算（KDJ/RSI）、筹码分布计算、Wind 直连数据补齐 |
| `fund_data_ingestion_service.py` | 基金数据接入服务：从本地 rows/CSV 规范化导入基金主数据、净值、持仓和基金经理任职 |
| `fund_intelligence_service.py` | 基金智能服务：基金详情组装、收益风险指标计算、单基金/组合持仓穿透 |
| `macro_sensitivity.py` | 宏观敏感性计算：通过时间序列回归计算个股对宏观因子的敏感度 |
| **数据摄入与处理** | |
| `ingest_service.py` | 摄入服务：处理文档摄入、提取断言和事件 |
| `document_chunker.py` | 文档分块：将长文档切分为适合处理的小块 |
| `document_classifier.py` | 文档分类：自动识别文档类型（研报、新闻、公告等） |
| `document_enrichment.py` | 文档丰富：为文档添加元数据和标签 |
| `entity_extractor.py` | 实体提取：从文本中提取实体（公司、行业、产品等） |
| `event_extractor.py` | 事件提取：识别和提取事件 |
| `deduplication_service.py` | 去重服务：检测和去除重复文档/事件 |
| `ingestion_queue_service.py` | 摄入队列服务：管理异步摄入任务 |
| **数据采集** | |
| `crawl_orchestrator.py` | 采集编排器：协调多源采集（fetch→normalize→dedup→store→enqueue），含去重同步和深度回填 |
| `crawl_scheduler.py` | 采集调度器：APScheduler 定时爬取 + PDF 转换。`check_and_backfill_gap()` 将阻塞回补委托到线程执行器 (`loop.run_in_executor`)，支持 per-source 超时 |
| `crawler_ingestion_bridge.py` | 采集摄入桥接：将采集器输出转为 DocumentEnvelope → 摄入队列 |
| `pdf_conversion_service.py` | PDF 转换服务：MinerU→MarkItDown→RawText 多策略降级，创建 DocumentV1 + 分块 |
| `system_event_bus.py` | 系统事件总线：SSE 实时推送、Worker 心跳追踪 |
| **知识与检索** | |
| `search_service.py` | 搜索服务：全局跨对象搜索 |
| `rag_retrieval.py` | RAG 检索服务：向量检索 + 增强生成 |
| `graph_data_service.py` | 图数据服务：知识图谱数据查询 |
| `taxonomy_service.py` | 分类服务：实体、事件、行业等分类管理 |
| **信号与投资** | |
| `signal_service.py` | 信号服务：创建、查询、验证、升级信号 |
| `signal_validator_impl.py` | 信号验证实现：验证信号逻辑和历史表现 |
| `event_auto_signal_generator.py` | 事件自动信号生成：批准的事件自动触发信号生成 |
| `factor_store_service.py` | 动态因子持久化服务：桥接 Pydantic 契约 ↔ ORM 记录，提供因子定义/值/评估/权重的完整持久化能力 |
| `factor_computation_service.py` | 动态因子计算服务：编排因子定义加载 → 值加载 → 矩阵构建 → 评估 → 动态权重拟合 → 持久化的日终流程 |
| `thesis_generator_service.py` | 论点生成服务：生成投资论点 |
| `thesis_review_service.py` | 论点审查服务：多视角审查论点 |
| `paper_trading_service.py` | 模拟交易服务：创建账户、下单、管理持仓 |
| `portfolio_service.py` | 组合服务：组合构建、风险管理、绩效分析 |
| **择时与情景** | |
| `scenario_service.py` | 情景服务：生成多情景分析 |
| `scenario_data_service.py` | 情景数据服务：情景相关数据查询 |
| **结果与学习** | |
| `outcome_service.py` | 结果服务：记录和查询信号结果 |
| `outcome_journal_service.py` | 结果日志服务：记录结果、查询相似案例 |
| `failure_memory_service.py` | 失败记忆服务：记录失败、分析原因、查询相似失败 |
| **报告与摘要** | |
| `report_generator.py` | 报告生成器：生成资产分析、估值、每周回顾等报告 |
| `summary_generator.py` | 摘要生成器：生成文档、事件、信号的摘要 |
| **仪表盘与控制台** | |
| `dashboard.js` / `dashboard_service.py` | 仪表盘市场刷新：前端轮询与 Wind 工作簿后端缓存均为 30 秒；Excel 超时/读取错误不会自动触发公式重写 |
| `wind_realtime_workbook.py` | Wind 实时工作簿：生成批量 `=wss()` 公式、通过 xlwings 读取已打开工作簿的快照；实时值更新由 Wind 插件负责 |
| `wind_workbook_manager.py` | Wind 工作簿生命周期：仅在新建、重建或显式手动修复时激活公式；已有工作簿快照为空时保留状态而不自动重写公式 |
| `decision_console_service.py` | 决策控制台服务：每日候选、决策记录、复盘视图 |
| **监控与治理** | |
| `monitoring_service.py` | 监控服务：健康检查、指标采集、告警管理 |
| `resource_monitor_service.py` | 资源监控服务：采集 API 进程树与项目既有调度器/知识 Worker PID，并只通过主机级 psutil API 汇总整机 CPU/内存容量；读取受控任务快照并标识精确进程或共享估算，维护 150 点内存历史并将字段权限/平台问题降级记录 |
| `resource_monitor_runtime.py` | 资源监控运行时：以单一可停止后台线程每分钟采集资源快照，并在一个数据库会话内写入主机容量历史和评估既有资源告警；异常只记录安全错误类型并继续下一周期 |
| `resource_host_history_service.py` | 整机容量历史服务：把安全白名单后的 CPU/内存整机汇总写入既有健康指标 JSON，每 UTC 分钟至多一条，公开查询最多 1500 点并仅保留 24 小时 |
| `resource_task_registry.py` | 资源任务登记器：为抓取、PDF、知识处理、Wind 与报告任务写入每 PID 原子安全快照，失败记录不含异常原文 |
| `resource_monitor_alert_service.py` | 资源异常协调器：复用 Monitoring 告警/事件状态机，去重并处理任务失败、受控 PID 缺失、采样失败、持续进程压力及整机 CPU/可用内存容量压力；通过共享 `ResourceAlertState` 保留跨周期压力/恢复计数，主机事件以稳定键原地升级，未恢复事件始终可查询 |
| `configuration_service.py` | 本地配置服务：跨平台文件锁与原子 `.env` 写入、配置分区验证、秘密掩码和受控热刷新；生产 Web 模式禁用控制面，数据库修改要求重启 |
| `governance_service.py` | 治理服务：版本控制、配置管理、审计 |
| `audit_service.py` | 审计服务：审计日志查询和管理 |
| **回放与历史** | |
| `replay_service.py` | 回放服务：历史回放、模拟交易回放 |
| `historical_replay_service.py` | 历史回放服务：历史场景重放 |
| **闭循环** | |
| `closed_loop_service.py` | 闭循环服务：协调从数据摄入到结果反馈的完整闭环 |
| **管线监控** | |
| `pipeline_monitor.py` | 管线监控服务：内存单例追踪 9 个管线阶段（数据采集→知识提取→信号生成→择时回测→学习反馈），聚合 DB 统计，线程安全活动日志（最多 200 条），SSE 实时推送 |
| **支持服务** | |
| `data_tier_service.py` | 数据层服务：数据分层管理 |
| `raw_storage_service.py` | 原始存储服务：原始文件存储和管理 |
| `news_feature_service.py` | 新闻特征服务：从新闻提取特征 |
| `pipeline_service.py` | 管道服务：数据处理管道编排 |
| **市场数据 ETL** | |
| `market_data_ingestion_service.py` | 市场数据摄入服务：编排 ETL 流程（爬取 → normalizer → 结构化表 → ETL 运行记录） |
| `official_index_structure_ingestion.py` | 中证/国证官方成分股摄入服务：通过 AKShare 包装的官网成分/权重下载接口，归一化写入指数主表和 `index_component_snapshot`，并支持 official catalog active 指数发现 |
| `wind_index_structure_probe.py` | Wind 指数结构字段探针：生成固定 Excel 函数模板、后台静默触发计算、读取指数成分/ETF 规模等候选字段验证结果 |
| `wind_index_structure_ingestion.py` | Wind 指数结构探针落库服务：将已验证探针结果归一化写入指数主表、ETF 主表、指数 ETF 关系和 ETF 日度指标 |

---

## connectors/ - 数据源连接器实现

顶层 `connectors/` 包存放所有具体连接器实现，分两个子包：

### connectors/document/ — 文档连接器

| 文件 | 说明 |
|---|---|
| `cls.py` | `CLSDocumentConnector`：财联社电报文档连接器，委托 `CLSAdapter` |
| `cninfo.py` | `CninfoDocumentConnector`：巨潮资讯网公告文档连接器，委托 `CninfoAdapter` |
| `cnstock.py` | `CNStockDocumentConnector`：中国证券网新闻文档连接器，委托 `CNStockAdapter` |
| `zq.py` | `ZQDocumentConnector`：知丘（研报/微信/纪要）文档连接器，委托 `ZQAdapter` |

### connectors/market/ — 市场数据连接器

| 文件 | 说明 |
|---|---|
| `akshare.py` | `AkShareMarketConnector`：AKShare 市场数据连接器，委托 `AKShareAdapter` |
| `wind.py` | `WindMarketConnector`：Wind 市场数据连接器，委托 `WindAdapter` |
| `baostock.py` | `BaostockMarketConnector`：BaoStock 市场数据连接器，委托 `BaoStockAdapter` |
| `cjpy.py` | `CjpyMarketConnector`：天软市场数据连接器，委托 `CjpyAdapter` |
| `yahoo.py` | `YahooMarketConnector`：Yahoo Finance 市场数据连接器，委托 `YahooAdapter` |

---

## data_layer/ - 数据层

### data_layer/adapters/ - 数据适配器

| 文件 | 说明 |
|---|---|
| `data_layer/adapters/akshare_adapter.py` | AKShare 开源数据适配器：集成 crawler 模块，提供行情、财务、新闻、股东数据获取 |
| `data_layer/adapters/cjpy_adapter.py` | 天软 Cjpy 适配器：获取股票/基金列表、交易日、日线/分钟行情、因子、表格和实时订阅；调用天软 HTTP 接口时临时绕开本机代理变量 |
| `data_layer/adapters/cninfo_adapter.py` | 巨潮资讯网公告适配器：包装 CninfoCrawler，输出 DocumentEnvelope（source_type=filing） |
| `data_layer/adapters/data_source_router.py` | 数据源路由器：iFinD → AKShare → ChinaStock 三级降级策略，统一管理所有数据适配器 |
| `data_layer/adapters/wind/wind_adapter.py` | Wind Excel 适配器：8 个 fetch 方法（一致预期/两融/龙虎榜/日行情/财务/行业/资金流向/持有人）和 WSS 实时行情读取 + parse() + fetch() dispatch |
| `data_layer/adapters/wind/client.py` | Wind Excel 客户端：xlwings 连接管理（遍历所有 Excel 实例检测 Wind 插件）、心跳检测（TTL 30s 缓存）、WSD 时间序列查询（3 次指数退避重试 + 动态超时）、批量公式执行、后台保活（30min 间隔防自动登出） |
| `data_layer/adapters/wind/formulas.py` | Wind 公式生成器：78 个公式（43 个已验证），覆盖一致预期/融资融券/龙虎榜/日行情/财务TTM+MRQ/估值/行业/资金流向/北向/股东/指数 |
| `data_layer/adapters/wind/exceptions.py` | Wind 自定义异常：会话过期、未连接、公式错误、超时 |
| `data_layer/repositories/wind_repository.py` | Wind 数据仓储：基于 PostgreSQL upsert 的持久化层，支持 4 类 Wind 数据批量保存和查询 |
| `data_layer/repositories/factor_repository.py` | 因子仓储：基于 PostgreSQL upsert 的持久化层，支持因子定义/值/评估/权重的批量保存和查询 |
| `app/api/routes/wind.py` | Wind REST API：8 个端点（health/prices/financials/industry/fund-flow/holders） |
| `app/api/routes/factors.py` | 动态多因子 REST API：10 个端点（definitions GET/POST, values GET/POST, evaluations GET/POST, weights/latest GET, weights POST, weights/history GET, available-dates GET, categories GET） |
| `app/web/static/js/wind.js` | Wind Web UI 模块：数据查询、结果渲染、健康检查 |
| `signal_lab/features/groups/wind_consensus.py` | WindConsensusFeatures：一致预期因子组（9 特征） |
| `signal_lab/features/groups/wind_margin.py` | WindMarginFeatures：融资融券因子组（5 特征） |
| `signal_lab/features/groups/wind_block.py` | WindBlockFeatures：龙虎榜因子组（3 特征） |

### data_layer/crawlers/ - 数据采集器

#### data_layer/crawlers/akshare/ - AKShare 采集器

| 文件 | 说明 |
|---|---|
| `data_layer/crawlers/akshare/__init__.py` | 导出 AkShareAdapter 和 AkShareConfig |
| `data_layer/crawlers/akshare/base.py` | BaseAkShareFetcher 基类：采集器基类，提供公共方法 |
| `data_layer/crawlers/akshare/config.py` | AkShareConfig 配置类：采集配置 |
| `data_layer/crawlers/akshare/market.py` | 市场数据采集器：股票列表、历史行情、实时行情、指数历史数据 |
| `data_layer/crawlers/akshare/financial.py` | 财务数据采集器：财务摘要、财务指标、利润表、资产负债表、现金流量表 |
| `data_layer/crawlers/akshare/news.py` | 新闻数据采集器：新浪财经新闻、东方财富新闻、个股新闻 |
| `data_layer/crawlers/akshare/macro.py` | 宏观数据采集器 |
| `data_layer/crawlers/akshare/utils.py` | 工具函数：clean_symbol、normalize_symbol、parse_date、parse_datetime、safe_float 等（⚠️ 被其他模块复用） |

#### data_layer/crawlers/cls/ - 财联社采集器

| 目录 | 说明 |
|---|---|
| `data_layer/crawlers/cls/` | 财联社电报采集器 |

#### data_layer/crawlers/cninfo/ - 巨潮资讯网采集器

| 目录 | 说明 |
|---|---|
| `data_layer/crawlers/cninfo/` | 巨潮资讯网上市公司公告采集器 |

#### data_layer/crawlers/cnstock/ - 中国证券网采集器

| 文件/目录 | 说明 |
|---|---|
| `data_layer/crawlers/cnstock/` | 中国证券网新闻采集器（快讯 + 普通频道） |
| `data_layer/crawlers/cnstock/cnstock.py` | CNStock 爬虫核心 (~1740行)：双路径架构（Playwright 优先 / requests 回退），支持快讯（fastNews/10004）和 5 个普通频道（证券/公司/产经/金融/时政），浏览器跨频道复用 |
| `data_layer/crawlers/cnstock/utils/` | 反爬/去重/缓存工具（`AntiScrapeKit`、`UserAgentRotator`、`DeduplicationStore`、`NetUtils`）|

**关键设计**：2026年5月 cnstock.com 升级阿里云 WAF，`requests` API 调用返回 `10304`（"未登录"）。修复方案使用 Playwright 无头浏览器导航 → 拦截页面 JS 发起的 XHR 响应获取数据。快讯通过提取 `__NEXT_DATA__` SSR 数据，普通频道通过拦截 `channelNewsList` API 响应。浏览器在 `crawl_news_list()` 中创建一次，跨频道复用。

#### data_layer/crawlers/zq/ - 知丘采集器

| 目录 | 说明 |
|---|---|
| `data_layer/crawlers/zq/` | 知丘研报、公众号、会议纪要采集器 |

### data_layer/parsers/ - 解析器

| 目录 | 说明 |
|---|---|
| `data_layer/parsers/` | 非结构化数据解析（PDF、网页、财报） |

### data_layer/normalizers/ - 归一化器

| 文件 | 说明 |
|---|---|
| `data_layer/normalizers/common.py` | 通用工具：to_decimal 安全数值转换 |
| `data_layer/normalizers/symbol.py` | A 股代码标准化：60/68/90→SH，00/30/20→SZ，43/83/87/88→BJ |
| `data_layer/normalizers/akshare_market.py` | AKShare 行情数据 normalizer：MarketData / StockInfo → dict |
| `data_layer/normalizers/akshare_financial.py` | AKShare 财务数据 normalizer：FinancialData → dict |

### data_layer/coordinator/ - 多源行情协调

| 文件 | 说明 |
|---|---|
| `data_layer/coordinator/cache_manager.py` | SQLite 行情缓存：保存 K 线、维护缓存元数据、计算请求区间缺口 |
| `data_layer/coordinator/multi_source_coordinator.py` | 多源行情协调器：缓存优先，按 AKShare / BaoStock / Yahoo 降级补数；当缓存只缺当天少量尾部数据时优先返回缓存，避免资产观察页被实时补数阻塞 |

### data_layer/repositories/ - 仓储实现

| 文件 | 说明 |
|---|---|
| `data_layer/repositories/base.py` | 仓储基类：BaseRepository，提供通用数据库操作方法 |
| `data_layer/repositories/models.py` | SQLAlchemy ORM 模型：定义所有数据库表模型 |
| `data_layer/repositories/market_data_repository.py` | 市场数据仓储：PostgreSQL upsert / SQLite fallback，管理股票主表、日行情、估值、财务、股东、指数发布方、指数主表、成分权重快照、指数 ETF 关系和 ETF 日度规模/资金流表 |
| `data_layer/repositories/monitoring_repository.py` | 监控仓储：持久化健康指标、告警与事件；支持仅更新未解决告警详情的条件更新，保留确认和解决状态 |
| `data_layer/repositories/fund_repository.py` | 基金智能仓储：管理基金主数据、日净值、股票持仓和基金经理任职 MVP 表 |
| `data_layer/repositories/etl_run_repository.py` | ETL 运行记录仓储：记录 ETL 运行开始、成功、失败，查询运行历史 |

---

## knowledge_layer/ - 知识层

| 目录 | 说明 |
|---|---|
| `knowledge_layer/entity_resolution/` | 实体解析与归一化 |
| `knowledge_layer/assertions/` | 断言管理 |
| `knowledge_layer/events/` | 事件存储与时间线索引 |
| `knowledge_layer/extraction/` | 并发 LLM 提取 (文本切分 + 并发抽取器) |
| `knowledge_layer/graph_projection/` | 产业链图谱投影：实体关系图构建、传播路径分析、种子数据 |
| `knowledge_layer/graph_projection/propagation.py` | 传播分析器：基于事件类型和产业链拓扑推导影响传播路径 |
| `knowledge_layer/graph_projection/graph_store.py` | 图存储：管理 IndustryChain 的 CRUD 和下游关系查询 |
| `knowledge_layer/graph_projection/seed_data.py` | 种子数据：A 股核心产业链预置数据（锂电、光伏、半导体、白酒） |
| `knowledge_layer/graph_projection/contracts.py` | 图谱契约：IndustryChain、RelationshipType、SupplyChainPosition |
| `knowledge_layer/retrieval/` | 向量检索 |

---

## reasoning/ - 推理层

| 目录 | 说明 |
|---|---|
| `reasoning/evidence/` | 证据链管理 |
| `reasoning/scenarios/` | 情景分析引擎 |
| `reasoning/skeptic/` | 怀疑论验证 |
| `reasoning/traces/` | 推理追踪 |
| `reasoning/router/` | 推理路由 |

---

## cognitive_agents/ - 认知 Agent 层

| 文件 | 说明 |
|---|---|
| `cognitive_agents/__init__.py` | 模块初始化 |
| `cognitive_agents/contracts.py` | 统一观点契约：AgentView、BlackboardConflict、AgentRole、ViewDirection |
| `cognitive_agents/blackboard.py` | 认知黑板：CognitiveBlackboard，负责观点写入、查询和冲突检测 |

---

## timing_engine/ - 择时层

| 文件 | 说明 |
|---|---|
| `timing_engine/__init__.py` | 模块初始化 |
| `timing_engine/contracts.py` | 择时契约：TimingModelScore、TimingDecision、MarketRegime、TimingAction、TimingBlocker |
| `timing_engine/meta.py` | Meta 择时引擎：融合多模型评分、市场阶段权重和 blocker |

---

## memory_learning/ - 记忆与学习层

| 文件 | 说明 |
|---|---|
| `memory_learning/__init__.py` | 模块初始化 |
| `memory_learning/contracts.py` | 记忆契约：MarketEpisode、StrategyMemory、AgentMemory、FailureMemory |
| `memory_learning/journal.py` | 学习日志：LearningJournal，记录并查询 episode、strategy、agent 和 failure memory |

---

## reporting/ - 报告层

| 文件/目录 | 说明 |
|---|---|
| `reporting/templates/` | 报告模板：资产分析卡、专题备忘录、情景分析报告等 |
| `reporting/composer/` | 报告合成：内容合成引擎 |
| `reporting/projections/` | 格式投影：Markdown、Word、HTML 等格式输出 |
| `reporting/projects/project_manager.py` | 报告项目管理：加载 `report_projects/<项目>/project.yaml`，解析 Word、Excel、section config、prompt templates、生成目录和 runs 目录；`scan_projects()` 在保留可用项目的同时返回缺失资产诊断，并按 `display_order` 排序 |
| `reporting/projects/plan.py` | 报告项目生成计划：在渲染前编译 section config 与 prompt templates，输出占位符 prompt/retrieval/deterministic 就绪度和报告周期 |
| `reporting/projects/run.py` | 报告项目运行编排：解析报告周期，调用占位符生成、Word/PPT 投影、表格/图表嵌入，写入 run log 并聚合 warnings |
| `reporting/projects/generation.py` | 项目级报告生成：解析 Markdown Prompt 模板，检索 `ingestion_queue_item` / `canonical_event` evidence，通过 ModelGateway 生成 Word 占位符正文，并返回证据/模型/token 元数据 |
| `reporting/projects/chart_generation.py` | 报告图表生成：读取 Excel chart cache 或 worksheet 缓存数据；旧模板可用 matplotlib 渲染图片并嵌入 DOCX，新模板可同步 Excel 原生 chart 到 Word chart parts |

## report_projects/ - 报告项目资产

| 文件/目录 | 说明 |
|---|---|
| `report_projects/<项目>/project.yaml` | 项目资产索引：声明模板、Excel 底稿、统一 report config、必需的 Markdown prompt templates、输出目录、run-log 目录和可选 `display_order` |
| `report_projects/<项目>/templates/` | Word 模板目录，模板中的 `{{占位符}}` 由报告项目 API 提取和替换 |
| `report_projects/<项目>/data/` | Excel 数据和图表底稿目录 |
| `report_projects/<项目>/config/report_config.yaml` | 统一占位符配置：静态值、Excel 来源、图表替换规则和 Markdown Prompt 模板引用 |
| `report_projects/<项目>/config/prompt_templates.md` | Markdown Prompt 模板库；每个 `##` 标题是模板名，模板内的 `检索 Query` 用于 evidence 检索 |
| `report_projects/<项目>/generated/` | 生成的 DOCX 输出 |
| `report_projects/<项目>/runs/` | 生成运行日志，记录占位符、evidence、模型、token、图表和 warnings |

---

## signal_lab/ - 信号实验室

### signal_lab/features/ - 特征工程

| 文件/目录 | 说明 |
|---|---|
| `signal_lab/features/base.py` | Feature、FeatureGroup 基类：特征抽象 |
| `signal_lab/features/builder.py` | FeatureBuilder：特征构建器，管理多个特征组 |
| `signal_lab/features/groups/` | 特征组实现 |
| `signal_lab/features/groups/price_volume.py` | 价量特征：价格变化、移动平均、RSI、MACD、波动率等 |
| `signal_lab/features/groups/valuation.py` | 估值特征：PE、PB、PS、股息率等 |
| `signal_lab/features/groups/financial.py` | 财务特征：营收、利润、ROE、ROA 等 |
| `signal_lab/features/groups/fund_flow.py` | 资金流特征：北向、机构、游资等资金流向 |
| `signal_lab/features/groups/industry.py` | 行业特征：行业相对强弱、行业轮动等 |
| `signal_lab/features/groups/macro.py` | 宏观特征：利率、汇率、通胀等 |

### signal_lab/labels/ - 标签工程

| 文件 | 说明 |
|---|---|
| `signal_lab/labels/base.py` | Labeler 基类：标签抽象 |
| `signal_lab/labels/relative_return.py` | RelativeReturnLabeler：相对收益标签 |
| `signal_lab/labels/event_driven.py` | EventDrivenLabeler：事件驱动标签 |

### signal_lab/scoring/ - 信号评分

| 文件 | 说明 |
|---|---|
| `signal_lab/scoring/scorer.py` | SignalScorer、CompositeScorer：信号评分基类和组合评分器 |
| `signal_lab/scoring/ranker.py` | SignalRanker：信号排名器 |

### signal_lab/backtests/ - 回测引擎

| 文件 | 说明 |
|---|---|
| `signal_lab/backtests/base.py` | Backtester、BacktestResult 基类：回测抽象 |
| `signal_lab/backtests/simple.py` | SimpleBacktester：简单回测实现 |
| `signal_lab/backtests/event_study.py` | EventStudyBacktester：事件研究回测 |

---

## storage/ - 存储层

| 文件/目录 | 说明 |
|---|---|
| `storage/schema.sql` | 数据库架构文件：包含所有表、索引、触发器的完整定义 |
| `storage/migrations/` | Alembic 数据库迁移版本管理 |
| `storage/migrations/alembic.ini` | Alembic 配置文件 |
| `storage/migrations/env.py` | Alembic 环境配置 |
| `storage/migrations/versions/` | 迁移版本文件目录 |
| `storage/migrations/versions/011_add_factor_store_tables.py` | 迁移 011：创建 factor_definition、factor_value、factor_evaluation、dynamic_factor_weight 四张表 |

---

## ingestion/ - 结构化摄入模块

| 文件 | 说明 |
|---|---|
| `ingestion/__init__.py` | 摄入模块初始化：导出 KnowledgePipeline、PipelineConfig、PipelineResult |
| `ingestion/knowledge_pipeline.py` | 知识管道：6 步处理管道（切块→分类→实体提取→事件提取→去重→保存） |
| `ingestion/structured_event_ingestion.py` | 结构化事件摄入器：标准化的结构化事件摄入管道，用于 A 股 Alpha 事件的摄入、去重和自动断言提取。包含 AssertionExtractor 用于从原始文本中提取断言。 |

---

## workers/ - 后台 Worker

| 文件 | 说明 |
|---|---|
| `workers/crawl_scheduler_worker.py` | 爬虫调度 Worker：独立进程管理 APScheduler 定时抓取任务，启动时后台并行回填可调度数据源（每源 600s 超时，全局 900s 超时）；当前通过 `CrawlOrchestrator` 的 connector-first 路径分流，文档源入队给 KnowledgePipeline，市场源写入结构化表 |
| `workers/knowledge_worker.py` | 知识处理 Worker：持续消费摄入队列，通过 KnowledgePipeline 处理文档（LLM 提取），发布 SSE 事件 |

---

## core/settings/ - 运行时配置

| 文件 | 说明 |
|---|---|
| `core/settings/runtime.py` | 运行时配置唯一入口：解析 desktop / web-dev / web-prod、跨平台数据目录、`.env` 路径和 backend URL |
| `core/settings/config.py` | Pydantic Settings：在 RuntimeContext 初始化后校验有效配置，并为桌面输出目录提供统一默认值 |
| `core/settings/registry.py` | 桌面首启配置模板与字段元数据：集中 PostgreSQL、LLM 并发和爬虫静默配置 |
| `core/settings/paths.py` | Windows/macOS/Linux 应用数据目录与 Wind 缓存路径 |

---

## cron_jobs/ - 定时任务

| 文件 | 说明 |
|---|---|
| `cron_jobs/auto_ingest_service.py` | 自动数据摄入服务：定时采集财联社、中国证券网、知丘研报、股票数据，支持守护进程模式 |
| `cron_jobs/auto_generate_signals.py` | 自动信号生成：从批准的事件自动生成候选信号 |

---

## scripts/ - 脚本工具

| 文件 | 说明 |
|---|---|
| `scripts/backup_db.py` | 数据库备份脚本：支持 PostgreSQL 完整备份、自动压缩、保留策略 |
| `scripts/desktop/build_sidecar.py` | 桌面 sidecar 打包：纳入后端、前端、报告资源和 `data/industry_graphs/` 内置图谱 |
| `scripts/restore_db.py` | 数据库恢复脚本：支持从备份恢复、时间点恢复；压缩恢复路径显式校验解压命令和管道句柄 |
| `scripts/backfill_pdf_artifacts.py` | PDF 制品回补：扫描磁盘 PDF 并注册到 pdf_artifact_v1 以触发自动转换 |
| `scripts/seed_factor_data.py` | 因子数据播种管线：双数据源（AKShare + Wind WSD）、限流重试（指数退避 + 关键词检测）、JSON 断点续传、3 Phase 流水线（市场数据摄入 → 技术因子 → 财务因子）；pandas/DB 标量先标准化再参与收益和财务因子计算 |
| `scripts/backfill_missing_llm_extraction.py` | LLM 提取回补：将缺少 canonical_event 的文档入队让 KnowledgePipeline 补做提取 |
| `scripts/cleanup_dedup_orphans.py` | 去重孤儿清理：移除爬虫去重文件中 DB 已不存在的条目，防止永久跳过 |
| `scripts/bootstrap_db.py` | 数据库初始化脚本：验证连接、创建表、验证 schema、植入默认配置 |
| `scripts/import_real_data.py` | 导入真实数据脚本：导入 benchmarks/ 中的真实数据存档，返回运行时字符串 doc_id |
| `scripts/minimal_reingest_bootstrap.py` | 最小重摄入引导脚本：从零重建系统，使用基准样本和上游连接器 |
| `scripts/backfill_from_objects.py` | 从对象存储回填脚本：从幸存的原始制品重建源文档和事实层；抽取前将 ORM 文档字段规整为字符串边界值 |
| `scripts/rebuild_derived_state.py` | 重建派生状态脚本：从恢复的事实记录重建派生系统状态（信号、择时决策、结果、回放），并按 `TimingModelScore` 完整契约重建择时评分 |
| `scripts/smoke_runner.py` | 冒烟测试脚本：端到端一键 MVP 验证 |
| `scripts/start_all.sh` | 一键启动脚本：启动 API → 调度器 → Knowledge Worker |
| `scripts/stop_all.sh` | 一键停止脚本：读取 PID 文件，停止所有后台服务 |
| `scripts/check_market_data_schema.py` | 结构化行情数据表 Schema 检查：验证 8 张市场数据表是否存在 |
| `scripts/bootstrap_market_data.py` | 结构化行情数据初始化脚本：同步股票列表和核心股票日行情 |
| `scripts/run_official_index_structure_ingestion.py` | 中证/国证官方指数成分摄入脚本：默认静默抓取核心指数，或用 `--discover-active --max-count` 从 official catalog 发现 active 指数并批量写入结构表 |
| `scripts/run_wind_index_structure_probe.py` | Wind 指数结构探针脚本：生成 `AlphaFoundry_Wind_Index_Structure_Probe.xlsx`，可选隐藏 Excel prime、读取缓存结果并持久化到结构表 |
| `workers/market_data_scheduler_worker.py` | 市场数据调度 Worker：后台运行日行情与 18:10 指数结构日更任务；默认关闭旧 gap check 回补链路 |
| `scripts/view_db.py` | 数据库查看工具：方便查询统计、事件、文档等 |
| `scripts/replace_huaan_word_charts_office.py` | 华安 ETF 周报图表替换脚本：通过 Excel/Word 原生复制粘贴生成可编辑 Word chart parts |
| `scripts/merge_huaan_layout_with_native_charts.py` | 华安 ETF 周报模板修复脚本：以原 Word 模板为母版，仅移植原生 chart drawing 和 chart parts，保留页眉页脚与版式 |
| `scripts/test_*.py` | 各种测试脚本：测试功能模块 |

---

## tests/ - 测试

| 目录 | 说明 |
|---|---|
| `tests/unit/` | 单元测试目录 |
| `tests/unit/core/` | 核心层单元测试 |
| `tests/unit/data_layer/` | 数据层单元测试 |
| `tests/unit/data_layer/crawlers/test_akshare.py` | AKShare 采集器单元测试（14 个测试用例 ✅） |
| `tests/unit/test_factor_repository.py` | 因子仓储单元测试：13 个测试覆盖空记录、upsert 委托、查询方法、session 生命周期 |
| `tests/unit/test_factor_store_service.py` | 因子存储服务单元测试：27 个测试覆盖 Pydantic 契约 ↔ ORM 双向转换、CRUD 路径、端到端流程 |
| `tests/unit/test_factor_api.py` | 因子 API 单元测试：13 个测试覆盖所有端点、请求验证、空数据处理 |
| `tests/unit/test_factor_computation_service.py` | 因子计算服务单元测试：11 个测试覆盖空定义/空值/完整循环/资源关闭 |
| `tests/unit/test_resource_monitor_service.py` | 资源监控服务测试：受控 PID 边界、预热、I/O 差分、历史上限、字段/子进程降级、Worker 精确归因和 API 共享估算 |
| `tests/unit/test_resource_host_history_service.py` | 整机容量历史测试：分钟去重、24 小时精确清理、类型隔离、安全字段白名单和受控坏快照处理 |
| `tests/unit/test_resource_monitor_runtime.py` | 资源监控运行时测试：采样、历史/告警协调、共享状态、失败续跑与线程生命周期 |
| `tests/unit/test_resource_task_registry.py` | 资源任务登记器测试：原子快照、并发、失败脱敏、任务类别与损坏文件降级 |
| `tests/unit/test_resource_monitor_alert_service.py` | 资源事件协调器测试：AlphaFoundry 事件来源标记、持续进程压力去重/恢复、整机 CPU/可用内存三级阈值、原地升级、缺失字段安全降级及未恢复事件历史 |
| `tests/unit/data_layer/repositories/test_monitoring_repository.py` | 监控仓储单元测试：未解决告警详情的条件更新保留确认状态，并不改写已解决告警 |
| `tests/unit/app/api/routes/test_resource_monitoring.py` | 资源事件 API 测试：历史查询、确认和人工解决响应契约 |
| `tests/unit/app/api/routes/test_system_resource_usage.py` | 系统资源 API 测试：只读快照/历史契约、窗口边界、脱敏降级和懒加载依赖 |
| `tests/unit/test_resource_monitor_frontend_static.py` | 资源监控前端静态契约：导航生命周期、轮询取消、150 点限制、安全 DOM 渲染、详情抽屉和响应式样式 |
| `tests/unit/test_dynamic_factors.py` | 动态多因子核心测试：覆盖矩阵构建、因子评估、动态权重、事件-因子融合 |
| `tests/integration/` | 集成测试目录 |

---

## docs/ - 文档

### 核心文档（活跃使用）

| 文件 | 说明 |
|---|---|
| `docs/REFERENCE.md` | 完整参考手册：CLI、API、信号实验室、项目结构详解 |
| `docs/AGENT_WORKFLOW.md` | Agent 任务路由、隔离与交付证据规范 |
| `docs/ARCHITECTURE.md` | 架构文档：系统总览、分层架构、数据流、设计理念 |
| `docs/CHANGELOG.md` | 更新日志：记录所有 notable 项目变更 |
| `docs/FILE_GUIDE.md` | 本文件：文件指南，详细说明每个主要文件的作用 |
| `docs/DATA_STORAGE.md` | 数据存储文档：PostgreSQL 表结构、数据契约、仓储接口 |
| `docs/DATA_SOURCES.md` | 数据源文档：各数据源说明、配置、使用方法 |
| `docs/backup_restore.md` | 备份恢复文档：备份策略、恢复策略、季度恢复演练 |

### 归档文档（归档目录

| 目录 | 说明 |
|---|---|
| `docs/issues/` | Issue 实现摘要：各个 Issue 的实现摘要文档 |
| `docs/research/` | 研究文档：相关研究材料 |
| `docs/archive/` | 旧文档归档：历史版本文档、临时报告、旧设计文档等 |

---

## 附录：快速查找

### 查找契约
所有契约定义在 `core/contracts/`，按功能分类命名，文件名清晰说明内容。

### 查找服务
所有业务服务在 `services/`，文件名 = 服务名 + `_service.py`，例如：
- 信号服务 → `signal_service.py`
- 报告生成器 → `report_generator.py`

### 查找采集器
采集器在 `data_layer/crawlers/`，按源分类：
- AKShare → `akshare/`
- 财联社 → `cls/`
- 中国证券网 → `cnstock/`
- 知丘 → `zq/`

### 查找 API
API 路由在 `app/api/routes/`，文件名 = 功能 + `.py`，例如：
- 仪表盘 API → `dashboard.py`
- 信号实验室 API → `signal_lab.py`

### 查找 CLI
CLI 命令在 `app/cli/commands/`，文件名 = 功能 + `.py`，例如：
- 信号命令 → `signal.py`
- AKShare 命令 → `akshare.py`

---

## 相关文档

- **[README.md](../README.md)** - 项目概述与快速开始
- **[REFERENCE.md](REFERENCE.md)** - 完整参考手册
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 架构文档
- **[CHANGELOG.md](CHANGELOG.md)** - 更新日志
- **[backup_restore.md](backup_restore.md)** - 备份恢复文档
- **[DATA_SOURCES.md](DATA_SOURCES.md)** - 数据源文档
