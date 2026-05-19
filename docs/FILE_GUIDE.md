# AlphaFoundry 文件指南

本指南详细说明项目中每个主要文件和目录的作用，帮助新开发者快速理解项目结构。

---

## 目录

1. [项目根目录文件](#项目根目录文件)
2. [app/ - 应用层](#app---应用层)
3. [core/ - 核心层](#core---核心层)
4. [data_layer/ - 数据层](#data_layer---数据层)
5. [knowledge_layer/ - 知识层](#knowledge_layer---知识层)
6. [reasoning/ - 推理层](#reasoning---推理层)
7. [cognitive_agents/ - 认知 Agent 层](#cognitive_agents---认知-agent-层)
8. [timing_engine/ - 择时层](#timing_engine---择时层)
9. [memory_learning/ - 记忆与学习层](#memory_learning---记忆与学习层)
10. [reporting/ - 报告层](#reporting---报告层)
11. [signal_lab/ - 信号实验室](#signal_lab---信号实验室)
12. [storage/ - 存储层](#storage---存储层)
13. [ingestion/ - 结构化摄入模块](#ingestion---结构化摄入模块)
14. [cron_jobs/ - 定时任务](#cron_jobs---定时任务)
15. [scripts/ - 脚本工具](#scripts---脚本工具)
16. [tests/ - 测试](#tests---测试)
17. [docs/ - 文档](#docs---文档)

---

## 项目根目录文件

| 文件/目录 | 说明 |
|---|---|
| `README.md` | 项目主文档，包含概述、快速开始、核心特性、使用指南 |
| `pyproject.toml` | 项目配置文件，包含 black、isort、ruff、pytest 等工具配置 |
| `pytest.ini` | Pytest 测试框架配置 |
| `.env.example` | 环境变量模板，复制为 `.env` 后使用 |
| `.gitignore` | Git 忽略文件配置 |
| `.claude/` | Claude 配置目录，包含项目特定的 rules |
| `app/` | 应用层，包含 API、CLI、Web 界面 |
| `core/` | 核心层，包含契约、接口、服务等 |
| `data_layer/` | 数据层，包含仓储实现和数据访问 |
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
| `data/` | 数据目录，存放 SQLite 数据库、原始数据等 |
| `logs/` | 日志目录，存放应用日志、Web 服务日志等 |
| `backups/` | 备份目录，存放数据库备份 |
| `benchmarks/` | 基准数据目录，存放真实数据存档 |
| `examples/` | 示例代码目录 |

---

## app/ - 应用层

### app/api/ - FastAPI 后端接口

| 文件/目录 | 说明 |
|---|---|
| `app/api/main.py` | API 入口点，初始化 FastAPI 应用，注册所有路由 |
| `app/api/models.py` | API 请求/响应模型（Pydantic） |
| `app/api/routes/audit.py` | 审计 API：查询审计日志 |
| `app/api/routes/dashboard.py` | 仪表盘 API：获取仪表盘汇总数据 |
| `app/api/routes/governance.py` | 治理 API：版本控制、配置管理 |
| `app/api/routes/ingest.py` | 数据摄入 API：上传文件、拉取实时源 |
| `app/api/routes/market_data.py` | 市场数据 API：同步股票列表、同步日行情、查询日行情、查询 ETL 运行记录 |
| `app/api/routes/memory.py` | 记忆 API：查询失败记忆、市场事件记忆 |
| `app/api/routes/monitoring.py` | 监控 API：健康检查、指标、告警 |
| `app/api/routes/outcome_journal.py` | 结果日志 API：记录结果、查询相似案例 |
| `app/api/routes/pipeline.py` | 管道 API：运行数据处理管道 |
| `app/api/routes/report.py` | 报告 API：生成各类报告 |
| `app/api/routes/scenarios.py` | 情景 API：生成多情景分析 |
| `app/api/routes/search.py` | 搜索 API：全局跨对象搜索 |
| `app/api/routes/signal_lab.py` | 信号实验室 API：特征、标签、评分、回测 |
| `app/api/routes/system.py` | 系统 API：健康检查、队列深度、Worker 心跳 |
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

| 目录 | 说明 |
|---|---|
| `app/web/` | Web 前端界面目录 |

---

## core/ - 核心层

### core/contracts/ - Pydantic 领域契约

所有跨层数据交换都遵循这些契约，保证类型安全和数据验证。

| 文件 | 说明 |
|---|---|
| `core/contracts/__init__.py` | 导出所有契约，方便导入 |
| `core/contracts/assertions.py` | 事实断言结构：Assertion、AssertionStatus |
| `core/contracts/assets.py` | 资产定义结构：Asset、AssetType、AssetSnapshot |
| `core/contracts/backtest.py` | 回测结构：BacktestResult、BacktestMetrics |
| `core/contracts/dashboard.py` | 仪表盘结构：DashboardSummary、RecentNews、MarketStatus |
| `core/contracts/decision_console.py` | 决策控制台结构：DailyCandidate、DecisionRecord |
| `core/contracts/documents_v1.py` | 文档结构 v1：DocumentEnvelope、DocumentType、DocumentMetadata |
| `core/contracts/events.py` | 事件结构：CanonicalEvent、EventType、DiffusionStage、MarketRegime |
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
| `core/model_gateway/providers/` | 模型提供商实现 |
| `core/model_gateway/providers/volcano.py` | 火山引擎提供商实现 |

### core/observability/ - 可观测性

| 文件 | 说明 |
|---|---|
| `core/observability/__init__.py` | 可观测性模块初始化 |
| `core/observability/metrics.py` | 指标定义和记录：counter、gauge、histogram |

### core/services/ - 业务服务（40+ 个服务）

这是系统的核心逻辑层，所有业务功能都在这里实现。

| 文件 | 说明 |
|---|---|
| `core/services/__init__.py` | 导出所有服务 |
| **资产分析** | |
| `asset_analysis_service.py` | 资产分析服务：生成资产分析快照 |
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
| `crawl_orchestrator.py` | 采集编排器：协调多个采集器运行 |
| `crawl_scheduler.py` | 采集调度器：定时任务调度、后台运行 |
| `crawler_ingestion_bridge.py` | 采集摄入桥接：将采集器输出转为 DocumentEnvelope → 摄入队列 |
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
| `dashboard_service.py` | 仪表盘服务：汇总和聚合仪表盘数据 |
| `decision_console_service.py` | 决策控制台服务：每日候选、决策记录、复盘视图 |
| **监控与治理** | |
| `monitoring_service.py` | 监控服务：健康检查、指标采集、告警管理 |
| `governance_service.py` | 治理服务：版本控制、配置管理、审计 |
| `audit_service.py` | 审计服务：审计日志查询和管理 |
| **回放与历史** | |
| `replay_service.py` | 回放服务：历史回放、模拟交易回放 |
| `historical_replay_service.py` | 历史回放服务：历史场景重放 |
| **闭循环** | |
| `closed_loop_service.py` | 闭循环服务：协调从数据摄入到结果反馈的完整闭环 |
| **支持服务** | |
| `data_tier_service.py` | 数据层服务：数据分层管理 |
| `raw_storage_service.py` | 原始存储服务：原始文件存储和管理 |
| `news_feature_service.py` | 新闻特征服务：从新闻提取特征 |
| `pipeline_service.py` | 管道服务：数据处理管道编排 |
| **市场数据 ETL** | |
| `market_data_ingestion_service.py` | 市场数据摄入服务：编排 ETL 流程（爬取 → normalizer → 结构化表 → ETL 运行记录） |

---

## data_layer/ - 数据层

### data_layer/adapters/ - 数据适配器

| 文件 | 说明 |
|---|---|
| `data_layer/adapters/akshare_adapter.py` | AKShare 开源数据适配器：集成 crawler 模块，提供行情、财务、新闻、股东数据获取 |
| `data_layer/adapters/data_source_router.py` | 数据源路由器：iFinD → AKShare → ChinaStock 三级降级策略，统一管理所有数据适配器 |

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

#### data_layer/crawlers/cnstock/ - 中国证券网采集器

| 目录 | 说明 |
|---|---|
| `data_layer/crawlers/cnstock/` | 中国证券网新闻采集器 |

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

### data_layer/repositories/ - 仓储实现

| 文件 | 说明 |
|---|---|
| `data_layer/repositories/base.py` | 仓储基类：BaseRepository，提供通用数据库操作方法 |
| `data_layer/repositories/models.py` | SQLAlchemy ORM 模型：定义所有数据库表模型 |
| `data_layer/repositories/market_data_repository.py` | 市场数据仓储：PostgreSQL upsert / SQLite fallback，管理股票主表、日行情、估值、财务、股东等结构化表 |
| `data_layer/repositories/etl_run_repository.py` | ETL 运行记录仓储：记录 ETL 运行开始、成功、失败，查询运行历史 |

---

## knowledge_layer/ - 知识层

| 目录 | 说明 |
|---|---|
| `knowledge_layer/entity_resolution/` | 实体解析与归一化 |
| `knowledge_layer/assertions/` | 断言管理 |
| `knowledge_layer/events/` | 事件存储与时间线索引 |
| `knowledge_layer/extraction/` | 并发 LLM 提取 (文本切分 + 并发抽取器) |
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

| 目录 | 说明 |
|---|---|
| `reporting/templates/` | 报告模板：资产分析卡、专题备忘录、情景分析报告等 |
| `reporting/composer/` | 报告合成：内容合成引擎 |
| `reporting/projections/` | 格式投影：Markdown、Word、HTML 等格式输出 |

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
| `workers/knowledge_worker.py` | 知识处理 Worker：持续消费摄入队列，通过 KnowledgePipeline 处理文档，发布 SSE 事件 |

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
| `scripts/restore_db.py` | 数据库恢复脚本：支持从备份恢复、时间点恢复 |
| `scripts/bootstrap_db.py` | 数据库初始化脚本：验证连接、创建表、验证 schema、植入默认配置 |
| `scripts/import_real_data.py` | 导入真实数据脚本：导入 benchmarks/ 中的真实数据存档 |
| `scripts/minimal_reingest_bootstrap.py` | 最小重摄入引导脚本：从零重建系统，使用基准样本和上游连接器 |
| `scripts/backfill_from_objects.py` | 从对象存储回填脚本：从幸存的原始制品重建源文档和事实层 |
| `scripts/rebuild_derived_state.py` | 重建派生状态脚本：从恢复的事实记录重建派生系统状态（信号、择时决策、结果、回放） |
| `scripts/smoke_runner.py` | 冒烟测试脚本：端到端一键 MVP 验证 |
| `scripts/start_all.sh` | 一键启动脚本：启动 API → 调度器 → Knowledge Worker |
| `scripts/stop_all.sh` | 一键停止脚本：读取 PID 文件，停止所有后台服务 |
| `scripts/check_market_data_schema.py` | 结构化行情数据表 Schema 检查：验证 8 张市场数据表是否存在 |
| `scripts/bootstrap_market_data.py` | 结构化行情数据初始化脚本：同步股票列表和核心股票日行情 |
| `scripts/view_db.py` | 数据库查看工具：方便查询统计、事件、文档等 |
| `scripts/test_*.py` | 各种测试脚本：测试功能模块 |

---

## tests/ - 测试

| 目录 | 说明 |
|---|---|
| `tests/unit/` | 单元测试目录 |
| `tests/unit/core/` | 核心层单元测试 |
| `tests/unit/data_layer/` | 数据层单元测试 |
| `tests/unit/data_layer/crawlers/test_akshare.py` | AKShare 采集器单元测试（14 个测试用例 ✅） |
| `tests/integration/` | 集成测试目录 |

---

## docs/ - 文档

### 核心文档（活跃使用）

| 文件 | 说明 |
|---|---|
| `docs/REFERENCE.md` | 完整参考手册：CLI、API、信号实验室、项目结构详解 |
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
所有业务服务在 `core/services/`，文件名 = 服务名 + `_service.py`，例如：
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

