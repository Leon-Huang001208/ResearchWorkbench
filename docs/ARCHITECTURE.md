# AlphaFoundry 架构文档

## 系统总览

AlphaFoundry 是一个**本地优先**的 AI-native Investment Operating System，采用**模块化单体**架构设计，使用 **PostgreSQL + pgvector** 作为核心事实存储。

系统的核心定位是 **AI 驱动的事件型量化（Event-driven Quant）**，而不是 tick 高频、K 线深度学习、纯技术指标或 LSTM 收盘价预测。Agent 层负责解释世界，Timing 层负责交易节奏，Quant 层负责统计验证。

### 设计哲学

1. **本地优先**：所有敏感数据本地处理，无需上传第三方，满足企业数据安全要求
2. **模块化单体**：清晰的分层和模块边界，保持单体开发部署的简单性，同时允许未来拆分微服务
3. **事实单一来源**：PostgreSQL 作为唯一权威事实源，Markdown/文档仅作为人类可读的投影输出
4. **可扩展性**：所有外部依赖通过接口隔离，易于替换模型提供商、数据源和存储后端
5. **AI 认知转 Alpha**：LLM 的非结构化理解必须落到结构化事件、产业链路径和可回测信号，不能停留在“AI 讲故事”
6. **先验证再交易**：任何事件型信号进入交易候选前，都必须经过统计验证和风险约束
7. **Agent 是认知插件层**：Agent 不成为架构主体，也不互相自由聊天；所有 Agent 通过统一 schema 写入共享黑板，形成可审计的认知市场
8. **Timing 是市场认知时钟**：择时层不解释产业逻辑，也不做长期统计验证，只判断市场现在是否会认可该逻辑
9. **Memory 让系统演化**：记录 Event → Return、失败原因、策略表现和 Agent 观点演化，避免系统永远只是即时推理机器人
10. **架构复杂度必须小于 Alpha 验证速度**：未来模块进入路线图，但当前优先服务真实可重复 Alpha 的验证
11. **按需懒加载**：模块级导入使用 PEP 562 `__getattr__` 或函数内延迟导入，避免启动时全量加载重型依赖（`sentence_transformers`/`vectorbt`/`torch` 等）。FastAPI 路由文件中的服务类导入放在 `Depends()` 工厂函数内，首次请求时才实例化。包级 `__init__.py` 不 eager re-export，改用 `__getattr__` 按需导入。

**懒加载实现模式**：

- **包级 `__init__.py`**：使用 `__getattr__` + `importlib.import_module`，支持 `from pkg import ClassName` 和 `from pkg import module` 两种用法（参见 `services/__init__.py`、`signal_lab/backtests/__init__.py`）。
- **FastAPI 路由文件**：在 `Depends()` 工厂函数内 `from xxx import HeavyDependency`，不放在模块顶层（参见 `app/api/routes/commentary.py`、`assets.py`、`ingest.py` 等）。
- **Provider 初始化**：仅在运行时调用 provider 相关方法时才导入重型 provider（参见 `core/model_gateway/gateway.py` 的 `LocalEmbeddingProvider`）。

---

## 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  应用层 (app)                                                │
│  ├─ CLI 命令行工具 (app/cli)                                │
│  ├─ API 后端接口 (app/api)                                   │
│  └─ Web 工作台界面 (app/web)                                 │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  核心层 (core)                                              │
│  ├─ 领域契约 (Pydantic v2) (core/contracts)                 │
│  ├─ 接口抽象 (core/interfaces)                               │
│  ├─ 连接器抽象 (BaseConnector/DocumentConnector) (core/connectors)│
│  ├─ Model Gateway 模型网关 (core/model_gateway)              │
│  ├─ 可观测性工具 (logging/metrics/tracer) (core/observability)│
│  ├─ 全局配置 (core/settings)                                 │
│  └─ 业务服务 (services)                                 │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  知识层 (knowledge_layer)                                    │
│  ├─ 实体解析与归一化                                         │
│  ├─ 事实断言管理                                             │
│  ├─ Event Database 事件库                                    │
│  ├─ Temporal Industry Graph 时间化产业链图谱                 │
│  └─ 向量检索服务                                             │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  推理层 (reasoning)                                          │
│  ├─ 事件抽取与分类                                           │
│  ├─ 产业链因果推理                                           │
│  ├─ 认知扩散阶段判断                                         │
│  ├─ 市场阶段识别                                             │
│  └─ 推理追踪 (reasoning/traces)                              │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  认知 Agent 层 (cognitive_agents)                            │
│  ├─ Information Agents                                       │
│  ├─ Cognitive Agents                                         │
│  ├─ Adversarial Agents (Bull/Bear/Skeptic)                  │
│  ├─ Validation Agents                                        │
│  └─ Cognitive Blackboard (认知黑板)                          │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  择时层 (timing_engine)                                      │
│  ├─ Regime Model                                             │
│  ├─ Flow / Sentiment / Theme Diffusion                       │
│  ├─ Crowding / Liquidity / Expectation Gap                   │
│  └─ Meta Timing System                                       │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  量化验证层 / 信号实验室 (signal_lab)                        │
│  ├─ Event Study Backtest Engine                              │
│  ├─ 特征工程 / 标签工程                                      │
│  ├─ 信号评分 / RankIC / Decay                                │
│  └─ 组合、仓位与风险控制                                     │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  记忆与学习层 (memory_learning)                              │
│  ├─ Episodic Memory (MarketEpisode)                         │
│  ├─ Strategy Memory / Agent Memory                          │
│  ├─ Failure Memory (失败记忆)                                │
│  └─ Learning Journal                                         │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  数据层 (data_layer)                                         │
│  ├─ 数据源适配器 (adapters，旧模式，逐步迁移到 connectors)        │
│  ├─ 数据源连接器实现 (顶层 connectors/ 包)                      │
│  ├─ 数据采集器 (crawlers)                                     │
│  │  ├─ AKShare 采集器 (crawlers/akshare)                     │
│  │  ├─ 财联社采集器 (crawlers/cls)                           │
│  │  ├─ 中国证券网采集器 (crawlers/cnstock)                   │
│  │  └─ 知丘采集器 (crawlers/zq)                               │
│  ├─ 解析器 (parsers)                                         │
│  ├─ 数据归一化 (normalizers)                                  │
│  └─ 仓储实现 (repositories)                                   │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  报告层 (reporting)                                          │
│  ├─ 报告模板                                                 │
│  ├─ 内容合成                                                 │
│  └─ 格式投影 (Markdown/Word)                                 │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  存储层 (storage)                                            │
│  ├─ 数据库 Schema (PostgreSQL + pgvector)                    │
│  └─ 迁移管理 (Alembic)                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 每层职责与核心模块

### 1. 应用层 (app)

**职责**：处理用户输入，暴露系统能力，路由请求到业务服务。

**核心模块**：

- **app/cli/**：基于 Click 的命令行工具，支持资产分析、情景分析、数据摄入、信号管理等直接调用
  - `commands/`：各子命令实现（akshare, ingest, memory, review, signal, timing）
  - `main.py`：CLI 入口点

- **app/api/**：FastAPI 后端接口，供前端调用
  - `main.py`：API 入口，路由注册
  - `models.py`：API 请求/响应模型
  - `routes/`：各 API 路由（audit, dashboard, governance, ingest, memory, monitoring, outcome_journal, pipeline, report, scenarios, search, signal_lab）

- **app/web/**：Web 工作台界面

**对外契约**：无，直接对接用户/前端。

---

### 2. 核心层 (core)

**职责**：定义全局契约、接口抽象和基础设施工具，为所有上层提供基础能力。

**核心模块**：

- **core/contracts/**：基于 Pydantic v2 的领域契约，所有跨层数据交换都遵循这些契约
  - `assertions.py`：事实断言结构
  - `assets.py`：资产定义结构
  - `backtest.py`：回测结构
  - `dashboard.py`：仪表盘结构
  - `decision_console.py`：决策控制台结构
  - `documents_v1.py`：文档结构 v1
  - `events.py`：事件结构
  - `governance.py`：治理结构
  - `industry_chain.py`：产业链结构
  - `ingestion.py`：摄入结构
  - `monitoring.py`：监控结构
  - `outcome_journal.py`：结果日志结构
  - `paper_trading.py`：模拟交易结构
  - `pdf_conversion.py`：PDF 转换结构
  - `portfolio.py`：组合结构
  - `replay.py`：回放结构
  - `reporting.py`：报告结构
  - `retrieval.py`：检索结构
  - `review_framework.py`：审查框架结构
  - `signals.py`：信号定义结构
  - `timing_engine.py`：择时引擎结构
  - `traces.py`：推理追踪结构

- **core/interfaces/**：抽象接口定义，隔离具体实现
  - `repository.py`：仓储接口

- **core/model_gateway/**：统一模型访问网关
  - `providers/`：模型提供商实现
    - `volcano.py`：火山引擎提供商

- **core/observability/**：可观测性三件套（日志/指标/追踪）
  - `metrics.py`：指标定义

- **services/**：业务服务，是系统的核心逻辑层
  - `AssetAnalysisService`：资产分析服务
  - `WindAnalysisService`：Wind 数据分析服务（Wind 数据源优先 → AssetAnalysisCard 映射，不可用时降级）
  - `ClosedLoopService`：闭循环服务
  - `CrawlOrchestrator`：采集编排器
  - `CrawlScheduler`：采集调度器
      - `CrawlerIngestionBridge`：采集到摄入队列桥接器
      - `SystemEventBus`：系统事件总线（SSE 实时推送、JSONL 持久化、worker 心跳）
  - `DashboardService`：仪表盘服务
  - `DataTierService`：数据层服务
  - `DecisionConsoleService`：决策控制台服务
  - `DeduplicationService`：去重服务
  - `DocumentChunker`：文档分块
  - `DocumentClassifier`：文档分类
  - `DocumentEnrichment`：文档丰富
  - `EntityExtractor`：实体提取
  - `EventAutoSignalGenerator`：事件自动信号生成
  - `EventExtractor`：事件提取
  - `EventIngestionService`：事件摄入服务
  - `FailureMemoryService`：失败记忆服务
  - `GovernanceService`：治理服务
  - `GraphDataService`：图数据服务
  - `HistoricalReplayService`：历史回放服务
  - `IngestService`：摄入服务
  - `IngestionQueueService`：摄入队列服务
  - `MonitoringService`：监控服务
  - `NewsFeatureService`：新闻特征服务
  - `OutcomeJournalService`：结果日志服务
  - `OutcomeService`：结果服务
  - `PaperTradingService`：模拟交易服务
  - `PDFConversionService`：PDF 转换编排服务
  - `PipelineService`：管道服务
  - `PortfolioService`：组合服务
  - `RAGRetrieval`：RAG 检索
  - `RawStorageService`：原始存储服务
  - `ReplayService`：回放服务
  - `ReportGenerator`：报告生成器
  - `ScenarioService`：情景服务
  - `SearchService`：搜索服务
  - `SignalService`：信号服务
  - `SignalValidatorImpl`：信号验证实现
  - `SummaryGenerator`：摘要生成器
  - `TaxonomyService`：分类服务
  - `ThesisGeneratorService`：论点生成服务
  - `ThesisReviewService`：论点审查服务
  - `TimingEngineService`：择时引擎服务

- **core/settings/**：全局配置管理。`runtime.py` 在业务模块和数据库 engine 初始化前解析运行模式、跨平台用户数据目录、唯一 `.env` 位置及本地后端 URL；桌面端使用 `%LOCALAPPDATA%/AlphaFoundry`（Windows）或 `~/Library/Application Support/AlphaFoundry`（macOS），Web 生产仅接受部署环境变量或显式配置文件。

**关键契约**：所有核心领域对象都定义在 `contracts/` 中，所有跨层交互必须使用这些 Pydantic 模型，保证类型安全和数据验证。

---

### 3. 知识层 (knowledge_layer)

**职责**：知识管理、事实存储、语义检索，构建系统的事实基础。

**核心模块**：

- `entity_resolution/`：实体消歧与归一化，确保同一实体在不同数据源中被统一标识
- `assertions/`：事实断言的增删改查，所有研究结论都以断言形式存储
- `events/`：事件存储与时间线索引
- `graph_projection/`：知识关系图投影，用于可视化和关系推理
- `retrieval/`：基于 pgvector 的向量语义检索，支持知识召回

**关键契约**：遵循 core.contracts 中的断言、实体、事件契约。

---

### 4. 推理层 (reasoning)

**职责**：基于事实知识进行分析推理，生成情景和结论。

**核心模块**：

- `evidence/`：证据链管理，追踪结论的证据来源
- `scenarios/`：多情景分析引擎，对不确定性问题生成多个可能情景
- `router/`：推理路由，选择合适的推理路径
- `skeptic/`：怀疑论验证，对结论进行交叉验证和一致性检查
- `traces/`：完整推理过程追踪，支持审计和复盘
- `state.py`：推理状态管理，基于 LangGraph 状态机

**关键契约**：使用 core.contracts.scenarios 定义情景结构，使用 traces 定义追踪结构。

---

### 5. 认知 Agent 层 (cognitive_agents)

**职责**：提供多视角认知插件和共享黑板，让不同专家视角以统一 schema 参与投资判断。

**核心模块**：

- `contracts.py`：`AgentView`、`BlackboardConflict`、AgentRole、ViewDirection 等统一契约
- `blackboard.py`：`CognitiveBlackboard`，负责观点写入、查询和冲突检测

**Agent 分层**：

- Information Agents：news、social_media、financial_report、industry_data
- Cognitive Agents：fundamental、technical、macro、industry_chain、policy、sentiment
- Adversarial Agents：bull、bear、skeptic
- Validation Agents：alpha_validation、regime、portfolio
- Execution Agent：execution，后续接入执行与滑点模块

**关键约束**：Agent 不直接互聊，不输出自由文本结论作为事实；所有观点必须写入黑板，并携带 evidence_refs、confidence 和 evaluation。

---

### 6. 择时层 (timing_engine)

**职责**：判断市场现在是否会认可某个事件型逻辑，输出交易节奏决策。

**核心模块**：

- `contracts.py`：`TimingModelScore`、`TimingDecision`、MarketRegime、TimingAction 等统一契约
- `meta.py`：`MetaTimingEngine`，融合多模型评分、市场阶段权重和 blocker

**关键约束**：Timing 不负责解释产业链，也不负责历史有效性检验。它消费 Agent/黑板/市场数据的结构化输入，输出 `enter`、`wait`、`reduce`、`exit` 或 `block`。

---

### 7. 量化验证层 / 信号实验室 (signal_lab)

**职责**：将 AI 事件理解转化为可回测的 Alpha 信号，并进行验证评分、组合约束和风险提示。

**核心模块**：

- `features/`：特征工程，从原始数据生成研究特征
  - `base.py`：Feature、FeatureGroup 基类
  - `builder.py`：FeatureBuilder
  - `groups/`：特征组实现（price_volume、valuation、financial、fund_flow、industry、macro）
- `labels/`：标签工程，定义预测目标标签
  - `base.py`：Labeler 基类
  - `relative_return.py`：相对收益标签
  - `event_driven.py`：事件驱动标签
- `scoring/`：信号评分，对候选信号进行有效性评分
  - `scorer.py`：SignalScorer、CompositeScorer
  - `ranker.py`：SignalRanker
- `backtests/`：回测引擎，集成 vectorbt 和 Backtrader 进行历史回测
  - `base.py`：Backtester、BacktestResult 基类
  - `simple.py`：简单回测实现
  - `event_study.py`：事件研究回测

**关键契约**：遵循 core.contracts.signals 中的 `AlphaSignal` 与 `EventAlphaSignal` 信号定义契约。事件型信号必须保留 event_id、event_type、impact_path、industry_impacts、diffusion_stage、market_regime 和 validation_status。

---

### 8. 记忆与学习层 (memory_learning)

**职责**：把市场结果沉淀为长期记忆，让系统从"即时推理"进入"可学习系统"。

**核心模块**：

- `contracts.py`：`MarketEpisode`、`StrategyMemory`、`AgentMemory`、`FailureMemory`
- `journal.py`：`LearningJournal`，记录并查询 episode、strategy、agent 和 failure memory

**关键约束**：Memory 不替代回测，也不直接生成交易建议；它记录真实市场反馈，供 Agent 权重、Timing blocker、策略选择和失败复盘使用。

---

### 9. 数据层 (data_layer)

**职责**：对接外部数据源，清洗归一化数据，实现仓储接口。

**核心模块**：

- **数据源注册中心** (`core/source_registry.py` + `data_sources/`)：每个爬取源通过 `SourceSpec` frozen dataclass 自描述注册，`data_sources/__init__.py` 自动发现。所有下游消费者（调度器、编排器、分类器、仪表盘）动态从注册表读取，不依赖硬编码列表。
  - 添加新爬取源 = 在 `data_sources/` 下新建一个 `.py` 文件

- **adapters/**：各个数据源的适配器实现
  - `akshare_adapter.py`：AKShare 开源数据适配器（集成新的 crawler 模块）

- **crawlers/**：数据采集器
  - `akshare/`：AKShare 采集器
    - `base.py`：BaseAkShareFetcher 基类
    - `config.py`：AkShareConfig 配置
    - `market.py`：市场数据采集器（历史行情、实时行情、股票列表）
    - `financial.py`：财务数据采集器
    - `news.py`：新闻数据采集器
    - `macro.py`：宏观数据采集器
    - `utils.py`：工具函数（clean_symbol, normalize_symbol, parse_date, safe_float 等）
  - `cls/`：财联社采集器
  - `cnstock/`：中国证券网采集器
  - `zq/`：知丘采集器（研报、公众号、会议纪要）

- `parsers/`：非结构化数据解析（PDF、网页、财报）
- `converters/`：PDF 转换策略 (MinerU / MarkItDown / RawText)
  - `base.py`：PDFConversionStrategy 抽象基类
  - `mineru.py`：MinerUStrategy (opendatalab/mineru, 最高质量)
  - `markitdown.py`：MarkItDownStrategy (microsoft/markitdown)
  - `raw_text.py`：RawTextStrategy (pdfplumber, 始终可用)
  - `persistence.py`：磁盘持久化 (data/markdown/, data/raw_text/)
- `normalizers/`：数据归一化，统一不同数据源的格式
  - `symbol.py`：A 股代码标准化（60/68/90→SH, 00/30/20→SZ）
  - `akshare_market.py`：行情/股票信息标准化
  - `akshare_financial.py`：财务数据标准化
- `repositories/`：实现 core.interfaces 中定义的仓储接口，对接存储层
  - `market_data_repository.py`：市场结构化数据 upsert/查询仓储（stock_master, stock_daily_bar 等 7 张表）
  - `etl_run_repository.py`：ETL 运行记录管理

**关键契约**：实现 core 中定义的仓储接口，返回遵循核心契约的数据对象。

---

### 10. 报告层 (reporting)

**职责**：将分析结果合成为人类可读的报告，并输出为不同格式。

**核心模块**：

- `templates/`：各类报告模板（资产分析卡、专题备忘录、情景分析报告）
- `composer/`：内容合成引擎，将碎片化结果组合为完整报告
- `projections/`：格式投影，转换为 Markdown、Word、HTML 等格式输出
- `projects/`：项目级报告生成链路，读取 `report_projects/<项目>/project.yaml`、Word/PPT 模板、Excel 底稿、`report_config.yaml` 和 `prompt_templates.md`；`CompiledReportPlan` 负责生成前 readiness 预检，`ReportProjectRunService` 统一编排 evidence 检索、ModelGateway 生成、Word/PPT 投影、图表/表格渲染和 runs 日志记录，API route 只负责 HTTP 映射与预览/下载入口

**项目级报告数据流**：

```text
Word 占位符
→ report_config.yaml placeholders/charts
→ prompt_templates.md 检索 Query + 写作要求
→ CompiledReportPlan 生成前检查 prompt / retrieval / deterministic 占位符
→ ReportProjectRunService 解析周期并编排单次运行
→ ingestion_queue_item / canonical_event evidence 检索
→ ModelGateway(reporting/default task route)
→ WordProjection 占位符替换
→ ReportProjectChartService 图表图片嵌入
→ generated/*.docx + runs/*.json + HTML 预览
```

当前 `华安ETF周报` 使用 `placeholders:` 映射 Word 占位符到 Markdown Prompt 模板，Prompt 模板内置检索 Query，不再依赖单独 JSON 数据源文件；`charts:` 配置负责把 Excel 图表缓存或 worksheet 缓存数据渲染为图片并写回 DOCX。

**关键契约**：使用 core.contracts.reporting 中的报告结构契约。

---

### 11. 存储层 (storage)

**职责**：数据库 schema 定义和迁移管理。

**核心文件**：

- `migrations/`：Alembic 数据库迁移版本管理

---

## 完整数据流

```
外部数据源 → 数据层(适配器 → 解析 → 归一化) → 知识层(实体解析 → 断言存储 → Event Database → Temporal Industry Graph → 向量编码) 
→ 推理层(知识召回 → 事件理解 → 产业链传播 → 认知扩散/市场阶段识别) → 认知Agent层(多视角观点 → 黑板冲突检测)
→ 择时层(Regime / Flow / Crowding / Market Clock) → 信号实验室(Event Alpha Signal → Event Study → 评分 → 仓位/风险约束)
→ 记忆与学习层(Event → Return → Failure / Strategy Memory)
→ 报告层(内容合成 → 格式投影) → 用户输出
              ↓                          ↓
                    存储层(持久化所有中间结果)
```

### 数据摄入管道详解

1. **原始数据采集**：所有已启用来源先进入 Connector 层；文档源（财联社、中国证券网、巨潮资讯、知丘等）入队到 `ingestion_queue`，市场/结构化源（AKShare、Wind、Yahoo、中证指数、深交所等）写入 market tables
2. **PDF 转换**：PDF 文件通过策略链自动转换为 Markdown/文本 (MinerU → MarkItDown → RawText 自动降级)
3. **Knowledge Worker 消费**：常驻进程并发消费 ingestion_queue，每批 10 条、最多 8 并发处理
4. **KnowledgePipeline 加工**：分块 → 分类 → 实体提取 → 事件提取 → 去重
5. **并发 LLM 提取**：对长文本自动切 chunk + ThreadPoolExecutor 并发提取断言和事件 (ConcurrentLLMExtractor)
   - 短文本 (≤1000字符): 一次 combined LLM 调用
   - 长文本 (>1000字符): chunk 切分 → 8 并发 LLM → 去重 → 质量门
6. **断言提取**：提取事实断言（Assertion）
7. **事件提取**：识别和提取事件（CanonicalEvent）（EventExtractor）
8. **向量化**：将文本转换为向量，存储到 pgvector 中
9. **持久化**：将所有结构化数据存入 PostgreSQL

### Worker 进程架构

```
┌──────────────────────────────────────────────────────────────┐
│  Crawl Scheduler Worker (workers/crawl_scheduler_worker.py) │
│  - 管理 APScheduler 定时抓取任务                              │
│  - 启动时并发回填所有数据源                                    │
│  - PID: logs/scheduler.pid, CLI: af crawl scheduler-start    │
│  - API: POST /api/scheduler/start|stop, GET /api/scheduler/status │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼ Connector.run → document/market 分流
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  IngestionQueue (PostgreSQL)                                  │
│  - 去重 (SHA256 hash)                                        │
│  - 优先级排序 (priority DESC, created_at ASC)                 │
│  - 状态流转: pending → processing → completed/failed          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼ 常驻消费
┌──────────────────────────────────────────────────────────────┐
│  Knowledge Worker (workers/knowledge_worker.py)              │
│  - 并发消费 ingestion_queue (默认 8 并发)                     │
│  - KnowledgePipeline 加工: 分块→分类→实体提取→事件提取→去重   │
│  - PID: logs/knowledge_worker.pid                            │
│  - CLI: af knowledge start|stop|status                       │
│  - API: POST /api/knowledge/start|stop, GET /api/knowledge/status │
│  - 两层并发: item 级 (asyncio.Semaphore, 8) + chunk 级        │
│    (ThreadPoolExecutor, 8)                                    │
└──────────────────────────────────────────────────────────────┘
```

### 市场数据 ETL 管道

```
AKShare 数据源
  → MarketDataIngestionService (ETL 编排)
    → normalizer (纯函数, 确定性, 可单测)
    → MarketDataRepository (PostgreSQL upsert；SQLite 仅保留非权威市场缓存兼容)
    → 结构化 SQL 表 (stock_master, stock_daily_bar, etl_run 等 8 张表)
  → ETLRunRepository (运行追踪, status/fetched/saved/error)
  → AssetAnalysisService (Wind 优先 → 结构化表 → MultiSourceCoordinator 降级)
  → asset_snapshot / API / dashboard (派生结果)
```

**定时执行**（cron_jobs/auto_ingest_service.py）:

- 数据源定时抓取（财联社 15min、中国证券网 30min、知丘研报 1h 等）
- 15:15 → 同步股票列表 (POST /api/market-data/stocks/sync)
- 15:30 → 同步日行情 (POST /api/market-data/daily-bars/sync)
- 15:45 → 生成资产快照 (POST /api/assets/analyze)
- 摄入队列消费由 Knowledge Worker 常驻处理，不再通过 cron_jobs

### 信号生成管道

1. **事件审查**：事件经过审查流程批准
2. **自动信号生成**：批准的事件自动触发信号生成（EventAutoSignalGenerator）
3. **论点生成**：生成投资论点（ThesisGeneratorService）
4. **论点审查**：多视角审查论点（ThesisReviewService）
5. **信号评分**：对信号进行多维度评分（CompositeScorer）
6. **择时评估**：Timing Engine 评估入场时机（MetaTimingEngine）
7. **回测验证**：历史回测验证信号有效性（Backtester）
8. **候选生成**：生成交易候选（SignalService.generate_trade_candidate）

### 结果反馈闭环

1. **记录结果**：记录信号的真实市场结果（OutcomeJournalService）
2. **失败分析**：如果失败，分析失败原因并记录（FailureMemoryService）
3. **市场事件记忆**：记录完整市场事件的后续发展（LearningJournal）
4. **每周回顾**：自动生成每周回顾报告（ReportGenerator）
5. **知识更新**：基于新的市场反馈更新系统认知

---

## 事件型量化闭环

AlphaFoundry 的主线不是"预测明天涨跌"，而是预测**哪些事件会形成持续市场共识**。完整闭环如下：

```
全球事件流
→ 信息层摄入
→ LLM 事件理解
→ 产业链传播路径
→ A股实体映射
→ Agent Swarm / Cognitive Blackboard
→ Event Alpha Signal
→ Timing Engine / Market Clock
→ Event Study / Excess Return / IC / Decay
→ Memory & Learning
→ Portfolio Construction / Risk Control / Position Sizing
→ Paper Trade / Execution-ready Candidate
→ Feedback Learning
```

### 事件数据库

Event Database 是系统从"研究叙事"进入"量化验证"的生死线。每条事件至少沉淀：

| 字段 | 说明 |
|---|---|
| event_id / event_time | 事件唯一标识与可回测时间点 |
| event_type | 政策、产品发布、出口管制、产业价格、财报、订单、技术突破等 |
| industry_impacts | 受影响行业、环节、主题 |
| impact_path | 从全球事件到 A 股映射的因果链 |
| affected_companies | 受益或受损公司 |
| diffusion_stage | 认知扩散阶段，如 discovery、early_awareness、theme_trading、consensus、decay |
| market_regime | 当前市场风格，如 AI 成长、红利、小盘、机构抱团 |
| validation_metrics | 后续收益、超额收益、胜率、Sharpe、Decay、Turnover |

### 时间化产业链图谱

产业链图谱不是静态 Wiki，而是带时间维度的关系系统。它需要回答：

- 谁供应谁、谁依赖谁、谁替代谁
- 某关系从什么时候开始成立，什么时候失效
- 某类事件通常先影响上游、中游、下游还是补涨环节
- 当前市场阶段更偏好龙头、低位补涨、业绩兑现还是主题弹性

### 量化验证层

Signal Lab 对事件型信号的最低验证集合包括：

- event study：事件后 1d / 5d / 20d / 60d 收益
- excess return：相对基准或行业指数的超额收益
- win rate：事件窗胜率
- Sharpe / volatility / max drawdown：收益质量
- decay：事件收益是否快速衰减
- turnover：信号触发频率与交易可行性
- IC / RankIC：横截面排序能力

未通过验证的信号只能停留在 `research_only`，不能升级为交易候选。

---

## AI-native Investment OS

AlphaFoundry 不应继续停留在功能模块集合，而要逐步具备横向操作系统能力。当前必须优先实现能提高 alpha 验证速度的能力，而不是一次性堆满所有未来模块。

| OS 能力 | 作用 | 当前策略 | 状态 |
|---|---|---|---|
| Memory & Learning | 记录事件结果、策略表现、Agent 观点演化、失败原因 | 现在实现最小 `memory_learning/` | ✅ 已实现 |
| Portfolio OS | 风险预算、exposure、factor neutrality、theme exposure、liquidity | 第二阶段，等稳定 signal 后加入 | ⏳ 进行中 |
| Market Simulation | 模拟游资、机构、北向、ETF、散户对事件的反应 | 第四阶段，避免现在过早复杂化 | 📋 计划 |
| Causal Engine | counterfactual、intervention、propagation dynamics | 与 Temporal Industry Graph 成熟后接入 | 📋 计划 |
| Ontology Layer | 行业、事件、因子、regime taxonomy | 先在 contracts 中收敛，后续独立化 | ⏳ 进行中 |
| Evaluation OS | Agent/Signal/Timing/Narrative 系统级评估 | 与 Memory & Learning 打通后扩展 | ⏳ 进行中 |
| Orchestration | DAG workflow、event routing、agent scheduling | 工作流复杂度上升后加入 | 📋 计划 |
| Feedback Learning | 根据市场结果更新权重和模型 | Memory 可用后逐步接入 | ⏳ 进行中 |
| Execution OS | order routing、slippage、liquidity、execution scheduling | 后期模块 | 📋 计划 |
| Alternative Data | 招聘、GPU shipment、GitHub velocity、电力、卫星、海运等 | 数据 OS 成熟后扩展 | 📋 计划 |

真正目标不是静态"最终架构"，而是 **Evolutionary Architecture**：市场非平稳，Alpha 会死亡，参与者会适应，所以系统必须能从市场反馈里学习，而不是固化成某个终局设计。

当前成熟路径：

```
Event Engine + Temporal Industry Graph + Signal Validation
→ Timing + Portfolio
→ Memory + Feedback Learning
→ Market Simulation + Reflexivity
→ Self-Evolving Investment System
```

当前生死线仍然是：

```
Event → Return
```

也就是先证明某类事件在某类 regime 下是否有稳定超额收益，再让 Timing、Portfolio 和 Learning 扩大这个优势。

---

## World Model + Agent Swarm

AlphaFoundry 会走向 Multi-Agent System，但 Agent 只作为横向认知竞争层。系统主体仍是 Data、Knowledge、Event、Signal Validation、Portfolio 和 Risk 这些可审计模块。

```
Data Layer
    ↓
Knowledge Graph / Event Database / Temporal Industry Graph
    ↓
Event Engine
    ↓
Agent Swarm
    ├── Information Agents: news, social_media, financial_report, industry_data
    ├── Cognitive Agents: fundamental, technical, macro, industry_chain, policy, sentiment
    ├── Adversarial Agents: bull, bear, skeptic
    └── Validation Agents: alpha_validation, regime, portfolio
    ↓
Cognitive Blackboard / Shared Memory
    ↓
Signal Validation Engine
    ↓
Portfolio Construction / Risk Engine / Execution
    ↓
Market Feedback / Learning Loop
```

### Blackboard Architecture

Agent 之间不直接互聊。每个 Agent 必须输出 `AgentView`，写入 `CognitiveBlackboard`：

```python
AgentView(
    view_id="view_fundamental_001",
    agent_name="fundamental_agent",
    agent_role="fundamental",
    target_id="300308.SZ",
    event_id="event_ai_inference",
    view="bullish",  # bullish / bearish / neutral / skeptical
    thesis="800G需求超预期，盈利弹性提升",
    reasoning=["订单能见度提高", "产能利用率改善"],
    evidence_refs=["assertion_001"],
    confidence=0.72,
)
```

黑板负责：

- 统一 memory schema 和 Agent ontology
- 汇总同一标的、同一事件的多视角观点
- 检测 Bull / Bear / Flow / Skeptic 等观点冲突
- 为 Alpha Validation Agent 提供结构化输入
- 为报告层保留可审计的认知轨迹

这让 Agent Swarm 更像"AI 投研委员会"，而不是一组聊天机器人。

---

## Timing Layer / Market Clock

Timing Engine 解决的是"逻辑对，但市场什么时候认可"。它是市场行为模型，不是 Agent，也不是 Quant。三者边界如下：

| 层 | 本质 | 作用 |
|---|---|---|
| Agent Layer | 认知 | 解释世界，生成 hypotheses |
| Timing Layer | 市场状态 | 判断现在能不能交易 |
| Quant Layer | 统计验证 | 判断历史上是否真的有 alpha |

Timing Engine 融合多类择时模型：

- Regime Model：AI 成长、红利、防御、风险 off、游资题材、机构趋势、流动性牛市、熊市反弹
- Flow Model：北向、机构、游资、ETF、量化、散户等资金流
- Theme Diffusion Model：主题从龙头、产业链环节到低位补涨的传播时钟
- Sentiment Model：连板高度、炸板率、涨停溢价、高位亏钱效应
- Market Structure Model：波动聚集、突破、趋势持续、流动性枯竭
- Liquidity Model：利率、国债、社融、M2、美债、人民币
- Crowding Model：持仓、研报覆盖、热搜、龙头涨幅、融资余额
- Expectation Gap Model：市场预期与真实产业变化之间的差
- Alpha Decay Model：逻辑是否已经 price in

`MetaTimingEngine` 会根据市场阶段决定更相信哪类模型。例如游资题材阶段更相信情绪和主题扩散，机构趋势阶段更相信 regime、flow 和 expectation gap。它输出 `TimingDecision`，包括 action、readiness_score、blockers 和 rationale。

---

## Model Gateway 设计

Model Gateway 是对大语言模型和嵌入模型访问的抽象层，设计目标：

- 支持切换不同模型提供商，无需修改业务代码
- 统一接口，保持 OpenAI 兼容的调用风格
- 内置重试、日志、追踪等横切关注点

### 核心抽象

```python
class BaseProvider(ABC):
    @abstractmethod
    def chat(messages, model, temperature, max_tokens) -> ModelResponse
    
    @abstractmethod  
    def structured_output(messages, output_schema, model, temperature) -> BaseModel
    
    @abstractmethod
    def embed(text, model) -> EmbeddingResponse
```

### 特性

1. **OpenAI 兼容**：接口设计保持与 OpenAI API 风格一致，易于适配兼容 OpenAI 接口的本地部署模型（如 Llama.cpp、vLLM 等）
2. **结构化输出原生支持**：直接支持输出 Pydantic 模型，强制保证输出结构符合预期
3. **多提供商支持**：可配置同时使用多个模型提供商，根据不同任务选择最合适的模型
4. **可观测性集成**：所有模型调用自动记录日志、指标和追踪，方便成本分析和问题排查

### 当前支持的提供商

- 火山引擎（Volcano）：`core/model_gateway/providers/volcano.py`

---

## 可观测性设计

系统内置了**日志/指标/追踪**三件套，完整覆盖可观测性需求：

### 1. 日志 (logging)

基于 `structlog` 实现结构化日志，所有日志包含上下文信息：

- 请求 ID
- 用户 ID
- 模块名称
- 耗时信息
- 错误堆栈

### 2. 指标 (metrics)

记录关键系统指标：

- 模型调用次数、token 消耗量、耗时
- 数据摄入数量
- 检索命中率
- API 请求延迟和错误率

详见 `core/observability/metrics.py`。

### 3. 追踪 (tracer)

完整追踪单个请求/分析任务的整个生命周期：

- 记录每个步骤的输入输出
- 保留模型调用的完整对话历史
- 追踪证据来源和推理路径
- 支持复盘整个分析过程

---

## 数据治理与审计

### 审计日志

所有关键操作都有审计记录：

- 数据摄入
- 断言/事件/信号的创建、更新、批准、拒绝
- 模型调用
- 配置变更

详见 `services/audit_service.py` 和 `app/api/routes/audit.py`。

### 版本控制

- 配置版本化
- 提示词版本化
- 策略版本化

详见 `core/contracts/governance.py`。

### 监控与告警

- 健康检查端点
- 指标采集与监控
- 可配置阈值告警
- 漂移检测

详见 `services/monitoring_service.py` 和 `app/api/routes/monitoring.py`。

---

## 灾难恢复与备份

### 备份策略

- 数据库完整备份
- 自动压缩
- 保留策略配置

详见 `scripts/backup_db.py`。

### 恢复策略

- 从备份恢复
- 时间点恢复
- 从对象存储回填
- 最小重摄入引导
- 重建派生状态

详见 `scripts/restore_db.py`、`scripts/backfill_from_objects.py`、`scripts/minimal_reingest_bootstrap.py`、`scripts/rebuild_derived_state.py`。

详细文档请参考 `docs/backup_restore.md`。

---

## 技术栈清单

| 领域 | 技术选型 |
|---|---|
| 语言 | Python 3.11+ |
| 数据验证 | Pydantic v2 |
| Web 框架 | FastAPI |
| 命令行 | Click |
| 数据库 | PostgreSQL 15+ / SQLite |
| 向量存储 | pgvector |
| ORM | SQLAlchemy 2.0 |
| 数据库迁移 | Alembic |
| 状态机 | LangGraph |
| 回测 | vectorbt, Backtrader |
| 日志 | structlog |
| 代码格式化 | black, isort, ruff |
| 数据源 | AKShare（开源）、财联社、中国证券网、知丘 |

---

## 扩展点与接口约定

### 如何添加新数据源

**推荐路径（Connector 架构）**：

1. 在 `connectors/document/` 或 `connectors/market/` 中创建新的连接器实现，继承 `DocumentConnector` 或 `MarketDataConnector`
2. 在 `data_layer/adapters/` 中创建或复用已有的适配器实现（Wrapper-first 策略，内部委托）
3. 在 `data_sources/` 中创建新文件调用 `register(SourceSpec(...))`，`connector_class` 指向新连接器的完全限定路径；`adapter_class` 仅作历史兼容别名
4. 连接器将自动被 `ConnectorRegistry` 发现和注册

**旧路径（向后兼容）**：

1. 在 `data_layer/crawlers/` 中创建新的采集器实现
2. 在 `data_layer/adapters/` 中创建新的适配器类，实现 `DataSourceAdapter` 接口
3. 在 `data_layer/normalizers/` 中添加对应的数据归一化器
4. 注册到数据源工厂，即可使用

**约定**：适配器必须返回符合核心契约的数据对象，不得让上层处理数据源特定格式。
连接器产出 `IngestionRecord`（shell + typed payload），不负责 LLM 提取（属于 KnowledgePipeline 职责）。

### 如何添加新模型提供商

1. 在 `core/model_gateway/providers/` 中实现新的提供商类，继承 `BaseProvider`
2. 实现三个抽象方法：`chat()`、`structured_output()`、`embed()`
3. 注册到网关，即可在配置中选择使用

**约定**：所有模型调用都必须经过 Model Gateway，不得直接在业务代码中调用模型 API。

### 如何添加新报告模板

1. 在 `report_projects/<项目名>/` 下创建项目目录。
2. 在 `project.yaml` 中声明：
   - `active_word_template`
   - `active_excel_workbook`
   - `report_config`
   - 可选 `prompt_templates`
   - `output_dir`
   - `run_log_dir`
3. 在 `config/report_config.yaml` 中用 `placeholders:` 绑定 Word 占位符；需要图表时用 `charts:` 声明 Excel/worksheet 数据源和 DOCX 替换目标。
4. 在 `config/prompt_templates.md` 中用 `## 模板名` 定义 Prompt 模板；`检索 Query` 负责找事实材料，`写作要求` 负责约束最终正文。
5. 通过 Web 模板工作台或 `POST /api/report-projects/{slug}/render` 生成 DOCX，并检查 `runs/*.json` 中的 evidence、模型、token、图表和 warning 记录。

**约定**：Word 模板只负责版式和占位符；`report_config.yaml` 负责映射；`prompt_templates.md` 负责检索和写作规则；业务事实必须来自 evidence 检索或显式手工占位符，不允许模型自由补事实。

### 如何添加新信号评分算法

1. 在 `signal_lab/scoring/` 中实现新的评分类，实现 `BaseScorer` 接口
2. 注册到评分工厂，即可选择使用

### 如何添加新特征

1. 在 `signal_lab/features/` 中创建新特征类，继承 `Feature` 基类
2. 实现 `compute()` 方法
3. 添加到对应的 `FeatureGroup` 中

---

## 资源监控第二期数据流

资源监控属于应用层的本地可观测性能力，边界是 AlphaFoundry 自身：API 进程树、项目写入 PID 文件的抓取调度器/知识 Worker，以及这些进程写入的受控任务快照。采样器不会全量枚举系统进程，也不会返回其他应用的进程详情。

`services/resource_task_registry.py` 为抓取、PDF、知识处理、Wind 和报告任务生成每 PID 原子快照；`ResourceMonitoringService` 读取这些快照，并将独立 Worker 标记为精确进程资源、API 内任务标记为共享进程估算。页面路径只读取进程内 5 分钟 AlphaFoundry 快照；运行时路径则由 `ResourceMonitorRuntime` 在数据库就绪且非 `ALPHAFOUNDRY_PREVIEW=1` 时常驻，每分钟汇总安全的主机 CPU/内存容量、写入并保留 24 小时历史，再评估告警。主机“剩余内存”始终指 `psutil.virtual_memory().available`，不是以 `total - used` 推算。`ResourceMonitorAlertService` 将失败、受控 Worker 缺失、采样失败和 AlphaFoundry 压力以 `source_scope=alphafoundry` 映射到已有 Monitoring 告警/事件表；整机 CPU/可用内存容量压力使用 `source_scope=host_capacity`，状态均为 `open → acknowledged → resolved`。实时图只保留内存中的 5 分钟点位；异常事件持久化并默认查询 90 天，任何未恢复事件始终返回。该能力只在系统监控页面和 API 中呈现异常，不发送原生桌面通知。

```text
受控任务/Worker → 每 PID 安全快照
API 进程树 + 明确 PID → 页面 5 分钟 AlphaFoundry 快照
ResourceMonitorRuntime（非预览）→ 每分钟主机容量汇总 → 24 小时历史
资源异常（alphafoundry / host_capacity）→ MonitoringRepository 的告警与事件
/api/system/resource-usage/host-history → 24 小时主机容量曲线
/api/system/resource-events → 系统监控页置顶与历史（无原生通知）
```

系统中心的“系统中心 / 系统配置”是同一 Web 工作台路由内的两个可见状态，而不是两个独立应用。`configuration.js` 仅负责编辑受支持的配置集合：账号与 Key 列表使用可访问的集合语义，高级设置按运行时、LLM 和文本分块分组；已保存的秘密仍不回填，受启动环境管理的字段仍由前端锁定和服务端校验共同保护。

## 相关文档

- **[README.md](../README.md)** - 项目概述与快速开始
- **[REFERENCE.md](REFERENCE.md)** - 完整参考手册
- **[FILE_GUIDE.md](FILE_GUIDE.md)** - 文件指南
- **[CHANGELOG.md](CHANGELOG.md)** - 更新日志
- **[backup_restore.md](backup_restore.md)** - 备份恢复文档
- **[DATA_SOURCES.md](DATA_SOURCES.md)** - 数据源文档
