# Research Workbench 架构映射

> **文档版本**: 1.0  
> **审计日期**: 2026-05-10  
> **描述**: Research Workbench 系统架构的完整映射和分析

---

## 执行摘要

Research Workbench 是一个**AI 原生的投资操作系统**，采用**模块化单体架构**设计。系统将 AI 的信息理解能力转化为可交易、可回测、可审计、可学习的事件型 Alpha 信号。

### 架构核心原则

1. **本地优先** - 所有敏感数据本地处理，满足企业数据安全要求
2. **模块化单体** - 清晰的模块边界，保持单体开发部署简单性的同时，允许未来拆分为微服务
3. **事实单一来源** - PostgreSQL 作为唯一权威事实源
4. **接口隔离** - 所有外部依赖通过接口抽象隔离
5. **可审计** - 所有操作都可追溯，支持审计流程
6. **AI 认知转 Alpha** - LLM 的非结构化理解必须落到可验证的量化信号上

---

## 架构层次映射

### 1. 层次结构图

```
┌───────────────────────────────────────────────────────────────────────┐
│                        应用层 (Application Layer)                       │
│  ┌─────────────────────────┐  ┌───────────────────────────────────┐  │
│  │   CLI (Click)          │  │      Web UI (FastAPI + HTML)      │  │
│  └─────────────────────────┘  └───────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │         FastAPI REST API (28+ endpoints)                        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                         核心层 (Core Layer)                            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Pydantic v2 领域契约 (25+ 模块)                                │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │  接口抽象 + 业务服务 (40+ 服务)                                  │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │  模型网关 (Model Gateway) + 可观测性 (Logging/Metrics/Tracing)   │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                      知识层 (Knowledge Layer)                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  实体解析 ──► 事实断言 ──► 事件数据库 ──► 时序产业链图谱          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  向量检索 (pgvector)                                             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                       推理层 (Reasoning Layer)                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  证据链 ──► 情景分析 ──► 怀疑论验证 ──► 推理追踪                  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  LangGraph 状态机                                                │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                   认知 Agent 层 (Cognitive Agent Layer)               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Information Agents ──► Cognitive Agents                         │  │
│  │  └─► Adversarial Agents (Bull/Bear/Skeptic)                      │  │
│  │  └─► Validation Agents                                           │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │  认知黑板 (Cognitive Blackboard)                                 │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                     择时引擎层 (Timing Engine Layer)                  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Regime ──► Flow ──► Sentiment ──► Theme Diffusion               │  │
│  │  Crowding ──► Liquidity ──► Expectation Gap ──► Alpha Decay      │  │
│  ├─────────────────────────────────────────────────────────────────┤  │
│  │  Meta Timing Engine (综合所有模型)                                │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                    信号实验室层 (Signal Lab Layer)                    │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  特征工程 (6+ 特征组) ──► 标签生成 ──► 信号评分 ──► 回测验证      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                   记忆与学习层 (Memory & Learning Layer)               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  市场情景记忆 ──► 策略记忆 ──► Agent 记忆 ──► 失败记忆            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                        数据层 (Data Layer)                            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  爬虫 (AKShare/财联社/中证网/知丘) ──► 适配器 ──► 归一化器        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  解析器 ──► 仓储实现 ──► 数据库                                   │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                       报告层 (Reporting Layer)                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  模板 ──► 合成器 ──► 投影器 (Markdown/Word/Excel)                │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                       存储层 (Storage Layer)                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL + pgvector (7+ 迁移)                                  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 核心模块架构映射

### 1. 应用层 (Application Layer)

#### FastAPI 架构

```
app/api/
├── main.py                      # FastAPI 应用入口
│   ├── 初始化 FastAPI 应用
│   ├── 配置 CORS
│   ├── 注册所有路由
│   └── 健康检查端点
├── models.py                    # API 请求/响应模型
└── routes/                      # 路由模块 (28+)
    ├── assets.py               # 资产分析端点
    ├── audit.py                # 审计日志端点
    ├── dashboard.py            # 仪表盘数据端点
    ├── decision_console.py     # 决策控制台端点
    ├── event_ingestion.py      # 事件摄入端点
    ├── governance.py           # 治理端点
    ├── graph.py                # 图数据端点
    ├── ingest.py               # 通用摄入端点
    ├── ingestion_queue.py      # 摄入队列端点
    ├── memory.py               # 记忆层端点
    ├── monitoring.py           # 监控端点
    ├── outcome_journal.py      # 结果日志端点
    ├── outcomes.py             # 结果跟踪端点
    ├── paper_trading.py        # 模拟交易端点
    ├── portfolio.py            # 投资组合端点
    ├── replay.py               # 回放端点
    ├── report.py               # 报告生成端点
    ├── review.py               # 审核端点
    ├── scenarios.py            # 情景分析端点
    ├── search.py               # 搜索端点
    ├── signal_lab.py           # 信号实验室端点
    ├── signals.py              # 信号管理端点
    ├── thesis_generator.py     # 论点生成端点
    └── timing.py               # 择时引擎端点
```

**架构特点**:
- RESTful API 设计
- 路由模块化组织
- Swagger/OpenAPI 自动文档
- 健康检查端点

#### CLI 架构

```
app/cli/
├── main.py                      # Click 命令组入口
│   └── 注册所有子命令
└── commands/
    ├── akshare.py              # AKShare 相关命令
    ├── ingest.py               # 数据摄入命令
    ├── memory.py               # 记忆相关命令
    ├── review.py               # 审核命令
    ├── signal.py               # 信号管理命令
    └── timing.py               # 择时命令
```

**架构特点**:
- 基于 Click 的命令组设计
- 子命令模块化组织
- 参数验证与帮助文档

#### Web UI 架构

```
app/web/
├── templates/                   # HTML 模板
└── static/                      # 静态资源 (CSS, JS, images)
```

**状态**: 基础结构存在，具体实现待验证

---

### 2. 核心层 (Core Layer)

#### 领域契约架构

```
core/contracts/
├── 基础契约
│   ├── assertions.py           # 事实断言模型
│   ├── events.py               # 规范事件模型
│   ├── signals.py              # Alpha 信号模型
│   └── documents_v1.py         # 文档信封模型
├── 资产与组合
│   ├── assets.py               # 资产分析快照
│   └── portfolio.py            # 投资组合模型
├── 回测与验证
│   ├── backtest.py             # 回测结果模型
│   └── review_framework.py     # 审核框架模型
├── 推理与情景
│   ├── scenarios.py            # 情景分析模型
│   └── traces.py               # 推理追踪模型
├── 治理与审计
│   ├── governance.py           # 治理与版本控制
│   ├── monitoring.py           # 监控模型
│   └── decision_console.py     # 决策控制台模型
├── 记忆与学习
│   ├── outcome_journal.py      # 结果日志模型
│   └── outcomes.py             # 结果跟踪模型
├── 报告与输出
│   └── reporting.py            # 报告合成模型
├── 基础设施
│   ├── ingestion.py            # 摄入管道模型
│   ├── raw_storage.py          # 原始存储模型
│   ├── replay.py               # 回放模型
│   └── retrieval.py            # 检索模型
└── 特定领域
    ├── industry_chain.py       # 产业链模型
    ├── timing_engine.py        # 择时引擎模型
    └── paper_trading.py        # 模拟交易模型
```

**契约设计原则**:
- 所有跨层数据交换使用 Pydantic 模型
- 类型安全与数据验证
- 序列化/反序列化支持
- 示例数据内置

#### 业务服务架构

```
core/services/
├── 数据管理服务
│   ├── ingest_service.py                # 数据摄入服务
│   ├── ingestion_queue_service.py       # 摄入队列服务
│   ├── raw_storage_service.py           # 原始存储服务
│   └── deduplication_service.py         # 去重服务
├── 知识加工服务
│   ├── document_chunker.py              # 文档分块
│   ├── document_classifier.py           # 文档分类
│   ├── document_enrichment.py           # 文档丰富
│   ├── entity_extractor.py              # 实体提取
│   └── event_extractor.py               # 事件提取
├── 资产分析服务
│   ├── asset_analysis_service.py        # 资产分析服务
│   └── news_feature_service.py          # 新闻特征服务
├── 信号生成服务
│   ├── signal_service.py                # 信号服务
│   ├── signal_validator_impl.py         # 信号验证实现
│   ├── event_auto_signal_generator.py   # 事件自动信号生成
│   ├── thesis_generator_service.py      # 论点生成服务
│   └── thesis_review_service.py         # 论点审核服务
├── 情景分析服务
│   ├── scenario_service.py              # 情景服务
│   └── scenario_data_service.py         # 情景数据服务
├── 报告生成服务
│   ├── report_generator.py              # 报告生成器
│   └── summary_generator.py             # 摘要生成器
├── 搜索与检索服务
│   ├── search_service.py                # 搜索服务
│   └── rag_retrieval.py                 # RAG 检索服务
├── 治理与审计服务
│   ├── governance_service.py            # 治理服务
│   └── [audit service implied]          # 审计服务
├── 监控与运维服务
│   ├── monitoring_service.py            # 监控服务
│   ├── dashboard_service.py             # 仪表盘服务
│   ├── data_tier_service.py             # 数据层服务
│   ├── crawl_orchestrator.py            # 爬虫编排器
│   └── crawl_scheduler.py               # 爬虫调度器
├── 记忆与学习服务
│   ├── failure_memory_service.py        # 失败记忆服务
│   ├── outcome_journal_service.py       # 结果日志服务
│   └── outcome_service.py               # 结果服务
├── 回放与模拟服务
│   ├── replay_service.py                # 回放服务
│   ├── historical_replay_service.py     # 历史回放服务
│   └── paper_trading_service.py         # 模拟交易服务
├── 投资组合服务
│   └── portfolio_service.py             # 投资组合服务
├── 管道与编排服务
│   ├── pipeline_service.py              # 管道服务
│   └── closed_loop_service.py           # 闭循环服务
├── 图数据服务
│   ├── graph_data_service.py            # 图数据服务
│   └── taxonomy_service.py              # 分类服务
└── 决策控制台服务
    └── decision_console_service.py      # 决策控制台服务
```

**服务架构原则**:
- 单一职责原则 (SRP)
- 依赖注入友好
- 通过契约与其他层交互
- 可观测性内置

#### 模型网关架构

```
core/model_gateway/
├── __init__.py
└── providers/
    ├── __init__.py
    └── volcano.py             # 火山引擎提供商
```

**设计模式**:
- 策略模式 - 支持切换不同提供商
- 适配器模式 - 统一接口
- OpenAI 兼容接口设计

**核心抽象**:
- `chat()` - 聊天完成
- `structured_output()` - 结构化输出 (Pydantic)
- `embed()` - 嵌入生成

---

### 3. 知识层 (Knowledge Layer)

```
knowledge_layer/
├── entity_resolution/         # 实体解析
│   └── [实体消歧与归一化实现]
├── assertions/                # 断言管理
│   └── [事实断言增删改查]
├── events/                    # 事件数据库
│   └── [事件存储与时间线索引]
├── graph_projection/          # 图投影
│   └── [知识图谱可视化与推理]
└── retrieval/                 # 向量检索
    └── [pgvector 语义检索实现]
```

**知识流向**:
```
原始文档 ──► 文档分块 ──► 实体提取 ──► 断言提取 ──► 事件提取 ──► 向量化存储
                                                          ↓
                                                   语义检索可用
```

---

### 4. 推理层 (Reasoning Layer)

```
reasoning/
├── evidence/                  # 证据链管理
│   └── [追踪结论的证据来源]
├── scenarios/                 # 情景分析引擎
│   └── [不确定性问题生成多个情景]
├── skeptic/                   # 怀疑论验证
│   └── [交叉验证与一致性检查]
├── router/                    # 推理路由
│   └── [选择合适的推理路径]
├── traces/                    # 推理追踪
│   └── [完整推理过程审计]
├── graph.py                   # 图推理
└── state.py                   # LangGraph 状态管理
```

**推理流程**:
```
输入问题 ──► 知识召回 ──► 推理路由 ──► 情景生成 ──► 怀疑验证 ──► 结论输出
              ↓                    ↓              ↓              ↓
            证据链              多路径分析     交叉检查      完整追踪
```

---

### 5. 认知 Agent 层 (Cognitive Agent Layer)

```
cognitive_agents/
├── contracts.py               # Agent 契约
│   ├── AgentView              # Agent 观点模型
│   ├── BlackboardConflict     # 冲突检测
│   ├── AgentRole              # Agent 角色枚举
│   └── ViewDirection          # 观点方向枚举
├── blackboard.py              # 认知黑板
│   ├── write_view()           # 写入观点
│   ├── query_views()          # 查询观点
│   ├── detect_conflicts()     # 检测冲突
│   └── aggregate_views()      # 聚合观点
└── agents/
    ├── information/           # 信息 Agent
    │   ├── news_agent.py
    │   ├── social_media_agent.py
    │   ├── financial_report_agent.py
    │   └── industry_data_agent.py
    ├── cognitive/             # 认知 Agent
    │   ├── fundamental_agent.py
    │   ├── technical_agent.py
    │   ├── macro_agent.py
    │   ├── industry_chain_agent.py
    │   ├── policy_agent.py
    │   └── sentiment_agent.py
    ├── adversarial/           # 对抗 Agent
    │   ├── bull_agent.py
    │   ├── bear_agent.py
    │   └── skeptic_agent.py
    └── validation/            # 验证 Agent
        ├── alpha_validation_agent.py
        ├── regime_agent.py
        └── portfolio_agent.py
```

**黑板架构模式**:
- Agent 不直接对话
- 所有观点写入共享黑板
- 冲突检测与解决机制
- 可审计的认知轨迹

---

### 6. 择时引擎层 (Timing Engine Layer)

```
timing_engine/
├── contracts.py               # 择时契约
│   ├── TimingDecision         # 择时决策
│   ├── TimingModelScore       # 模型评分
│   ├── MarketRegime           # 市场风格枚举
│   └── TimingAction           # 择时动作枚举
├── meta.py                    # Meta 择时引擎
│   ├── register_model()       # 注册模型
│   ├── evaluate_all()         # 评估所有模型
│   ├── combine_scores()       # 组合评分
│   ├── apply_blockers()       # 应用阻断器
│   └── make_decision()        # 生成决策
└── models/
    ├── base.py                # BaseTimingModel
    ├── registry.py            # 模型注册表
    ├── regime_model.py        # 市场风格模型
    ├── flow_model.py          # 资金流模型
    ├── sentiment_model.py     # 情绪模型
    ├── theme_diffusion_model.py # 主题扩散模型
    ├── crowding_model.py      # 拥挤度模型
    ├── liquidity_model.py     # 流动性模型
    ├── expectation_gap_model.py # 预期差模型
    ├── alpha_decay_model.py   # Alpha 衰减模型
    └── market_structure_model.py # 市场结构模型
```

**择时决策流程**:
```
市场数据 ──► 所有模型评估 ──► 评分组合 ──► 阻断检查 ──► 最终决策
            (10+ 模型)        (权重融合)   (风险检查)   (Enter/Wait/Reduce/Exit/Block)
```

---

### 7. 信号实验室层 (Signal Lab Layer)

#### 特征工程架构

```
signal_lab/features/
├── base.py                    # 基类定义
│   ├── Feature                # 抽象特征基类
│   │   ├── name               # 特征名称
│   │   ├── description        # 特征描述
│   │   └── compute()          # 计算方法
│   └── FeatureGroup           # 特征组基类
│       ├── add_feature()      # 添加特征
│       ├── compute_all()      # 计算所有特征
│       └── get_feature_names() # 获取特征名
├── builder.py                 # FeatureBuilder
│   ├── add_group()            # 添加特征组
│   ├── compute_features()     # 计算所有特征
│   └── get_feature_names()    # 获取所有特征名
└── groups/                    # 特征组实现
    ├── price_volume.py        # 价量特征
    │   ├── PriceChangeFeature
    │   ├── MovingAverageFeature
    │   ├── VolatilityFeature
    │   └── VolumeFeature
    ├── valuation.py           # 估值特征
    │   ├── PERatioFeature
    │   ├── PBRatioFeature
    │   ├── PSRatioFeature
    │   └── DividendYieldFeature
    ├── financial.py           # 财务特征
    │   ├── ROEFeature
    │   ├── ROAFeature
    │   ├── RevenueGrowthFeature
    │   └── ProfitMarginFeature
    ├── fund_flow.py           # 资金流特征
    │   ├── NorthboundFlowFeature
    │   ├── InstitutionalFlowFeature
    │   └── RetailFlowFeature
    ├── industry.py            # 行业特征
    │   ├── IndustryRelativeFeature
    │   └── IndustryMomentumFeature
    └── macro.py               # 宏观特征
        ├── InterestRateFeature
        ├── InflationFeature
        └── LiquidityFeature
```

#### 标签生成架构

```
signal_lab/labels/
├── base.py                    # Labeler 基类
│   └── compute()              # 计算标签
├── relative_return.py         # 相对收益标签
│   └── RelativeReturnLabeler
└── event_driven.py            # 事件驱动标签
    └── EventDrivenLabeler
```

#### 信号评分架构

```
signal_lab/scoring/
├── scorer.py                  # 评分器
│   ├── SignalScorer           # 基类
│   ├── ConfidenceScorer       # 置信度评分
│   ├── StrengthScorer         # 强度评分
│   ├── QualityScorer          # 质量评分
│   └── CompositeScorer        # 组合评分器
│       ├── add_scorer()       # 添加评分器
│       ├── score()            # 综合评分
│       └── weights            # 权重配置
└── ranker.py                  # 排名器
    └── SignalRanker
        ├── rank()             # 信号排名
        └── filter()           # 信号过滤
```

#### 回测引擎架构

```
signal_lab/backtests/
├── base.py                    # 基类定义
│   ├── Backtester             # 回测器基类
│   │   ├── run()              # 运行回测
│   │   └── analyze()          # 分析结果
│   └── BacktestResult         # 回测结果
│       ├── total_return       # 总收益
│       ├── annual_return      # 年化收益
│       ├── volatility         # 波动率
│       ├── sharpe_ratio       # 夏普比率
│       ├── max_drawdown       # 最大回撤
│       ├── win_rate           # 胜率
│       ├── num_trades         # 交易次数
│       ├── returns            # 收益序列
│       ├── positions          # 持仓序列
│       ├── equity_curve       # 净值曲线
│       └── metadata           # 元数据
├── simple.py                  # 简单回测
│   └── SimpleBacktester
└── event_study.py             # 事件研究回测
    └── EventStudyBacktester
        ├── event_window       # 事件窗口
        ├── estimation_window  # 估计窗口
        └── calculate_car()    # 计算累计异常收益
```

**信号验证流程**:
```
事件 ──► 特征工程 ──► 信号生成 ──► 信号评分 ──► 回测验证 ──► 风险评估
                        ↓              ↓           ↓            ↓
                    6+ 特征组      多维度评分    事件研究      仓位约束
```

---

### 8. 记忆与学习层 (Memory & Learning Layer)

```
memory_learning/
├── contracts.py               # 记忆契约
│   ├── MarketEpisode          # 市场情景
│   ├── StrategyMemory         # 策略记忆
│   ├── AgentMemory            # Agent 记忆
│   └── FailureMemory          # 失败记忆
├── journal.py                 # 学习日志
│   └── LearningJournal
│       ├── record_episode()   # 记录情景
│       ├── record_strategy()  # 记录策略
│       ├── record_agent()     # 记录 Agent
│       ├── record_failure()   # 记录失败
│       ├── query_similar()    # 查询相似案例
│       └── learn_patterns()   # 学习模式
├── persistent_journal.py      # 持久化实现
│   └── PersistentLearningJournal
└── pattern_learner.py         # 模式学习器
    └── PatternLearner
        ├── extract_patterns() # 提取模式
        ├── find_anomalies()   # 发现异常
        └── update_weights()   # 更新权重
```

**记忆闭环**:
```
信号执行 ──► 结果记录 ──► 失败分析 ──► 模式学习 ──► 未来决策改进
                        ↓
                    失败记忆库
```

---

### 9. 数据层 (Data Layer)

#### 爬虫架构

```
data_layer/crawlers/
├── akshare/                   # AKShare 爬虫
│   ├── base.py                # BaseAkShareFetcher
│   ├── config.py              # AkShareConfig
│   ├── market.py              # 市场数据
│   │   ├── 历史行情
│   │   ├── 实时行情
│   │   └── 股票列表
│   ├── financial.py           # 财务数据
│   │   ├── 财报数据
│   │   ├── 指标数据
│   │   └── 业绩预告
│   ├── news.py                # 新闻数据
│   ├── macro.py               # 宏观数据
│   └── utils.py               # 工具函数
│       ├── clean_symbol()
│       ├── normalize_symbol()
│       ├── parse_date()
│       └── safe_float()
├── cls/                       # 财联社爬虫
│   └── [实时电报采集]
├── cnstock/                   # 中国证券网爬虫
│   └── [新闻公告采集]
└── zq/                        # 知丘爬虫
    ├── [研报采集]
    ├── [公众号文章采集]
    └── [会议纪要采集]
```

#### 适配器架构

```
data_layer/adapters/
├── akshare/                   # AKShare 适配器
├── china_stock/               # 中国股票适配器
└── ifind/                     # iFind 适配器
```

#### 仓储架构

```
data_layer/repositories/
└── [仓储接口实现 - 对接数据库]
```

**数据流向**:
```
外部源 ──► 爬虫 ──► 适配器 ──► 解析器 ──► 归一化器 ──► 仓储 ──► 数据库
```

---

### 10. 报告层 (Reporting Layer)

```
reporting/
├── templates/                 # 报告模板
│   ├── template_manager.py    # 模板管理器
│   └── [模板定义]
├── composer/                  # 报告合成
│   ├── report_composer.py     # 主合成器
│   ├── report_pipeline.py     # 生成管道
│   ├── section_generator.py   # 章节生成
│   ├── fact_card_builder.py   # 事实卡构建
│   ├── evidence_binder.py     # 证据绑定
│   └── validator.py           # 报告验证
└── projections/               # 输出投影
    ├── markdown.py            # Markdown 输出
    ├── word.py                # Word (.docx) 输出
    └── excel.py               # Excel 输出
```

**报告生成流程**:
```
数据收集 ──► 模板选择 ──► 章节生成 ──► 事实卡构建 ──► 证据绑定 ──► 验证 ──► 输出
                                                                  ↓
                                                        Markdown/Word/Excel
```

---

## 数据流架构映射

### 1. 数据摄入管道

```
外部数据源
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  爬虫层 (4 个爬虫)                                  │
│  AKShare | 财联社 | 中国证券网 | 知丘              │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  适配器层                                           │
│  统一数据格式转换                                   │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  解析层                                             │
│  PDF 解析 | 网页解析 | 财报解析                     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  归一化层                                           │
│  数据清洗 | 格式统一 | 实体对齐                     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  知识加工层                                         │
│  文档分块 ──► 文档分类 ──► 实体提取 ──► 事件提取  │
└─────────────────────────────────────────────────────┘
    │
    ├─────────────────────┬─────────────────────┐
    ▼                     ▼                     ▼
┌───────────┐      ┌───────────┐      ┌──────────────────┐
│ 向量化   │      │ 事实断言  │      │ 规范事件        │
│ 存储     │      │ 数据库    │      │ 数据库          │
└───────────┘      └───────────┘      └──────────────────┘
    │                     │                     │
    └─────────────────────┴─────────────────────┘
                          │
                          ▼
                ┌──────────────────┐
                │  PostgreSQL      │
                │  + pgvector      │
                └──────────────────┘
```

### 2. 信号生成管道

```
事件数据库
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  事件审核流程                                       │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  事件自动信号生成器                                 │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  论点生成服务                                       │
│  (基于事件、知识、市场环境生成投资论点)              │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  论点审核服务                                       │
│  (多视角交叉验证)                                   │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  信号评分 (CompositeScorer)                         │
│  置信度 | 强度 | 质量 | ...                         │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  择时引擎评估                                       │
│  MetaTimingEngine + 10+ 模型                       │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  回测验证                                           │
│  事件研究 | 简单回测 | 风险指标                     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  交易候选生成                                       │
│  (通过验证的信号进入候选队列)                       │
└─────────────────────────────────────────────────────┘
```

### 3. 结果反馈闭环

```
交易执行 (或模拟)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  结果记录 (OutcomeJournalService)                   │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  结果分析                                           │
│  成功/失败判断 | 归因分析                           │
└─────────────────────────────────────────────────────┘
    │
    ├─────────────────────────────────────────────────┐
    │                                                 │
    ▼                                                 ▼
┌──────────────────┐                     ┌───────────────────────┐
│  成功案例       │                     │  失败分析            │
│  存入记忆库     │                     │  (FailureMemory)     │
└──────────────────┘                     └───────────────────────┘
    │                                                 │
    └─────────────────────┬───────────────────────────┘
                          │
                          ▼
                ┌─────────────────────────────┐
                │  模式学习                  │
                │  (PatternLearner)         │
                └─────────────────────────────┘
                          │
                          ▼
                ┌─────────────────────────────┐
                │  系统改进                  │
                │  Agent 权重 | 信号模板   │
                │  择时规则 | 风险约束      │
                └─────────────────────────────┘
                          │
                          ▼
                ┌─────────────────────────────┐
                │  未来决策改进              │
                └─────────────────────────────┘
```

---

## 核心设计模式映射

| 模式 | 应用位置 | 实现 |
|------|---------|------|
| **仓储模式 (Repository)** | 数据层 | `data_layer/repositories/` |
| **策略模式 (Strategy)** | 模型网关、择时模型 | `model_gateway/providers/`, `timing_engine/models/` |
| **适配器模式 (Adapter)** | 数据层 | `data_layer/adapters/` |
| **工厂模式 (Factory)** | 择时模型注册表 | `timing_engine/models/registry.py` |
| **组合模式 (Composite)** | 信号评分器 | `signal_lab/scoring/scorer.py` (CompositeScorer) |
| **建造者模式 (Builder)** | 特征构建 | `signal_lab/features/builder.py` |
| **黑板模式 (Blackboard)** | 认知 Agent 层 | `cognitive_agents/blackboard.py` |
| **管道模式 (Pipeline)** | 报告生成、摄入 | `reporting/composer/report_pipeline.py` |
| **状态机模式 (State Machine)** | 推理层 | `reasoning/state.py` (LangGraph) |

---

## 依赖关系映射

### 1. 层级依赖

```
应用层 (app)
    │
    ├─► 核心层 (core)
    │       ├─► 核心契约 (contracts)
    │       ├─► 业务服务 (services)
    │       ├─► 模型网关 (model_gateway)
    │       └─► 可观测性 (observability)
    │
    ├─► 知识层 (knowledge_layer)
    ├─► 推理层 (reasoning)
    ├─► 认知 Agent 层 (cognitive_agents)
    ├─► 择时引擎层 (timing_engine)
    ├─► 信号实验室层 (signal_lab)
    ├─► 记忆学习层 (memory_learning)
    ├─► 数据层 (data_layer)
    ├─► 报告层 (reporting)
    └─► 存储层 (storage)

所有层都依赖: core/contracts (领域契约)
```

### 2. 模块依赖

```
信号实验室 (signal_lab)
    ├─► 核心契约 (core/contracts)
    └─► 数据层 (data_layer) [价格数据]

择时引擎 (timing_engine)
    ├─► 核心契约 (core/contracts)
    └─► 数据层 (data_layer) [市场数据]

认知 Agent (cognitive_agents)
    ├─► 核心契约 (core/contracts)
    ├─► 知识层 (knowledge_layer)
    └─► 推理层 (reasoning)

记忆学习 (memory_learning)
    ├─► 核心契约 (core/contracts)
    └─► 信号实验室 (signal_lab) [信号结果]
```

---

## 接口契约映射

### 1. 核心接口

| 接口 | 位置 | 目的 |
|------|------|------|
| Repository | `core/interfaces/` | 仓储抽象 |
| Feature | `signal_lab/features/base.py` | 特征抽象 |
| FeatureGroup | `signal_lab/features/base.py` | 特征组抽象 |
| Labeler | `signal_lab/labels/base.py` | 标签器抽象 |
| SignalScorer | `signal_lab/scoring/scorer.py` | 评分器抽象 |
| Backtester | `signal_lab/backtests/base.py` | 回测器抽象 |
| BaseProvider | `core/model_gateway/` | 模型提供商抽象 |
| BaseTimingModel | `timing_engine/models/base.py` | 择时模型抽象 |

---

## 部署架构映射

### 当前部署: 单体部署

```
┌─────────────────────────────────────────────────────────────┐
│                   Research Workbench 应用                         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  FastAPI 应用进程                                     │ │
│  │  - API 端点 (28+)                                    │ │
│  │  - Web UI 服务                                        │ │
│  │  - 后台任务 (可选)                                   │ │
│  └───────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  CLI 命令行工具 (独立进程)                            │ │
│  └───────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  定时任务服务 (cron_jobs/)                            │ │
│  │  - auto_ingest_service.py                             │ │
│  │  - auto_generate_signals.py                           │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────┐
        │   PostgreSQL 数据库 (本地)        │
        │   - 主事实存储                    │
        │   - pgvector 向量存储             │
        └───────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────┐
        │   文件系统存储                    │
        │   - data/ 目录                   │
        │   - logs/ 目录                   │
        │   - backups/ 目录                │
        └───────────────────────────────────┘
```

### 未来可能的演进: 模块化微服务

```
┌─────────────────────────────────────────────────────────────────┐
│                          API Gateway                            │
└─────────────────────────────────────────────────────────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
┌───────────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐
│  摄入服务    │ │ 分析服务  │ │ 信号服务  │ │ 报告服务    │
│  (Ingestion) │ │ (Analysis)│ │ (Signals) │ │ (Reporting)  │
└───────────────┘ └───────────┘ └───────────┘ └───────────────┘
          │              │              │              │
          └──────────────┴──────────────┴──────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │   共享 PostgreSQL + pgvector      │
        └───────────────────────────────────┘
```

---

## 架构健康评估

### 1. 架构优势

| 方面 | 评估 | 说明 |
|------|------|------|
| **模块化** | ✅ 优秀 | 清晰的模块边界，职责明确 |
| **抽象层次** | ✅ 优秀 | 良好的接口隔离，依赖倒置 |
| **可扩展性** | ✅ 优秀 | 插件式设计，易于扩展 |
| **可测试性** | ✅ 良好 | 模块化设计利于单元测试 |
| **可观测性** | ✅ 良好 | 日志、指标、追踪基础设施 |
| **可审计性** | ✅ 优秀 | 完整的审计追踪设计 |
| **数据完整性** | ✅ 良好 | 事实单一来源设计 |
| **本地优先** | ✅ 优秀 | 满足数据安全要求 |

### 2. 潜在架构风险

| 风险 | 影响 | 缓解建议 |
|------|------|---------|
| **单体复杂性** | 中 | 保持模块边界，考虑按功能拆分 |
| **服务耦合** | 低/中 | 持续关注服务间依赖关系 |
| **测试覆盖** | 未知 | 建议评估测试覆盖率，补充关键路径测试 |
| **性能优化** | 未知 | 建议进行性能基准测试 |
| **Web UI 状态** | 未知 | 建议评估 Web UI 实现状态 |

---

## 架构演进路径

### 当前状态: v1.0 (模块化单体)

### 短期演进 (v1.1 - v1.5)
1. 完善 Web UI
2. 补充测试覆盖
3. 性能优化
4. 文档完善

### 中期演进 (v2.0)
1. 引入事件驱动架构
2. 可能的微服务拆分
3. 增强学习能力
4. 更丰富的 Agent 生态

### 长期愿景 (v3.0+)
1. 真正的演进式架构
2. 自适应系统
3. 更强大的 World Model
4. 完整的 Agent Swarm

---

*最后更新: 2026-05-10*
