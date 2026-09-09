# Research Workbench 架构文档

## 系统总览

Research Workbench 是一个**本地优先**的 AI-native Investment Operating System，采用**模块化单体**架构设计，使用 **PostgreSQL + pgvector** 作为核心事实存储。

系统的核心定位是 **AI 驱动的事件型量化（Event-driven Quant）**，而不是 tick 高频、K 线深度学习、纯技术指标或 LSTM 收盘价预测。Agent 层负责解释世界，Timing 层负责交易节奏，Quant 层负责统计验证。

### 设计哲学

1. **本地优先**：所有敏感数据本地处理，无需上传第三方，满足企业数据安全要求
2. **模块化单体**：清晰的分层和模块边界，保持单体开发部署的简单性，同时允许未来拆分微服务
3. **事实单一来源**：PostgreSQL 作为唯一权威事实存储，Markdown/文档仅作为人类可读的投影输出
4. **可扩展性**：所有外部依赖通过接口隔离，易于替换模型提供商、数据源和存储后端
5. **AI 认知转 Alpha**：LLM 的非结构化理解必须落到结构化事件、产业链路径和可回测信号，不能停留在“AI 讲故事”
6. **先验证再交易**：任何事件型信号进入交易候选前，都必须经过统计验证和风险约束
7. **Agent 是认知插件层**：Agent 不成为架构主体，也不互相自由聊天；所有 Agent 通过统一 schema 写入共享黑板，形成可审计的认知市场
8. **Timing 是市场认知时钟**：择时层不解释产业逻辑，也不做长期统计验证，只判断市场现在是否会认可该逻辑
9. **Memory 让系统演化**：记录 Event → Return、失败原因、策略表现和 Agent 观点演化，避免系统永远只是即时推理机器人
10. **架构复杂度必须小于 alpha 验证速度**：未来模块进入路线图，但当前优先服务真实可重复 alpha 的验证

---

## 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  应用层 (app)                                                │
│  ├─ CLI 命令行接口                                           │
│  ├─ API 后端接口                                             │
│  └─ Web 工作台界面                                           │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  核心层 (core)                                               │
│  ├─ 领域契约 (Pydantic)                                      │
│  ├─ 接口抽象                                                 │
│  ├─ Model Gateway 模型网关                                   │
│  ├─ 可观测性工具 (logging/metrics/tracer)                     │
│  └─ 全局配置                                                 │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  知识层 (knowledge_layer)                                    │
│  ├─ 实体解析与归一化                                          │
│  ├─ 事实断言管理                                              │
│  ├─ Event Database 事件库                                     │
│  ├─ Temporal Industry Graph 时间化产业链图谱                   │
│  └─ 向量检索服务                                              │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  推理层 (reasoning)                                          │
│  ├─ 事件抽取与分类                                            │
│  ├─ 产业链因果推理                                            │
│  ├─ 认知扩散阶段判断                                          │
│  ├─ 市场阶段识别                                              │
│  └─ 推理追踪                                                 │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  认知 Agent 层 (cognitive_agents)                            │
│  ├─ Information Agents                                       │
│  ├─ Cognitive Agents                                         │
│  ├─ Adversarial Agents                                       │
│  ├─ Validation / Regime / Portfolio Agents                   │
│  └─ Cognitive Blackboard                                     │
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
│  量化验证层 / 信号实验室 (signal_lab)                         │
│  ├─ Event Backtest Engine                                    │
│  ├─ 特征工程 / 标签工程                                       │
│  ├─ 信号评分 / RankIC / decay                                 │
│  └─ 组合、仓位与风险控制                                      │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  记忆与学习层 (memory_learning)                              │
│  ├─ Episodic Memory                                          │
│  ├─ Strategy / Agent / Failure Memory                        │
│  └─ Learning Journal                                         │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  数据层 (data_layer)                                         │
│  ├─ 数据源适配器                                              │
│  ├─ 解析器                                                   │
│  ├─ 数据归一化                                               │
│  └─ 仓储实现                                                 │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  报告层 (reporting)                                          │
│  ├─ 报告模板                                                 │
│  ├─ 内容合成                                                 │
│  └─ 格式投影 (Markdown/Word/HTML)                            │
└─────────────┴───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│  存储层 (storage)                                            │
│  ├─ 数据库 Schema                                            │
│  └─ 迁移管理                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 每层职责与核心模块

## 事件型量化闭环

Research Workbench 的主线不是“预测明天涨跌”，而是预测**哪些事件会形成持续市场共识**。完整闭环如下：

```text
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

Event Database 是系统从“研究叙事”进入“量化验证”的生死线。每条事件至少沉淀：

| 字段 | 说明 |
|---|---|
| event_id / event_time | 事件唯一标识与可回测时间点 |
| event_type | 政策、产品发布、出口管制、产业价格、财报、订单、技术突破等 |
| industry_impacts | 受影响行业、环节、主题 |
| impact_path | 从全球事件到 A 股映射的因果链 |
| affected_companies | 受益或受损公司 |
| diffusion_stage | 认知扩散阶段，如 discovery、early_awareness、theme_trading、consensus、decay |
| market_regime | 当前市场风格，如 AI 成长、红利、小盘、机构抱团 |
| validation_metrics | 后续收益、超额收益、胜率、Sharpe、decay、turnover |

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

## AI-native Investment OS

Research Workbench 不应继续停留在功能模块集合，而要逐步具备横向操作系统能力。当前必须优先实现能提高 alpha 验证速度的能力，而不是一次性堆满所有未来模块。

| OS 能力 | 作用 | 当前策略 |
|---|---|---|
| Memory & Learning | 记录事件结果、策略表现、Agent 观点演化、失败原因 | 现在实现最小 `memory_learning/` |
| Portfolio OS | 风险预算、exposure、factor neutrality、theme exposure、liquidity | 第二阶段，等稳定 signal 后加入 |
| Market Simulation | 模拟游资、机构、北向、ETF、散户对事件的反应 | 第四阶段，避免现在过早复杂化 |
| Causal Engine | counterfactual、intervention、propagation dynamics | 与 Temporal Industry Graph 成熟后接入 |
| Ontology Layer | 行业、事件、因子、regime taxonomy | 先在 contracts 中收敛，后续独立化 |
| Evaluation OS | Agent/Signal/Timing/Narrative 系统级评估 | 与 Memory & Learning 打通后扩展 |
| Orchestration | DAG workflow、event routing、agent scheduling | 工作流复杂度上升后加入 |
| Feedback Learning | 根据市场结果更新权重和模型 | Memory 可用后逐步接入 |
| Execution OS | order routing、slippage、liquidity、execution scheduling | 后期模块 |
| Alternative Data | 招聘、GPU shipment、GitHub velocity、电力、卫星、海运等 | 数据 OS 成熟后扩展 |

真正目标不是静态“最终架构”，而是 **Evolutionary Architecture**：市场非平稳，alpha 会死亡，参与者会适应，所以系统必须能从市场反馈里学习，而不是固化成某个终局设计。

当前成熟路径：

```text
Event Engine + Temporal Industry Graph + Signal Validation
→ Timing + Portfolio
→ Memory + Feedback Learning
→ Market Simulation + Reflexivity
→ Self-Evolving Investment System
```

当前生死线仍然是：

```text
Event → Return
```

也就是先证明某类事件在某类 regime 下是否有稳定超额收益，再让 Timing、Portfolio 和 Learning 扩大这个优势。

## World Model + Agent Swarm

Research Workbench 会走向 Multi-Agent System，但 Agent 只作为横向认知竞争层。系统主体仍是 Data、Knowledge、Event、Signal Validation、Portfolio 和 Risk 这些可审计模块。

```text
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

```json
{
  "view_id": "view_fundamental_001",
  "agent_name": "fundamental_agent",
  "agent_role": "fundamental",
  "target_id": "300308.SZ",
  "event_id": "event_ai_inference",
  "view": "bullish",
  "thesis": "800G需求超预期，盈利弹性提升",
  "reasoning": ["订单能见度提高", "产能利用率改善"],
  "evidence_refs": ["assertion_001"],
  "confidence": 0.72
}
```

黑板负责：

- 统一 memory schema 和 Agent ontology
- 汇总同一标的、同一事件的多视角观点
- 检测 Bull / Bear / Flow / Skeptic 等观点冲突
- 为 Alpha Validation Agent 提供结构化输入
- 为报告层保留可审计的认知轨迹

这让 Agent Swarm 更像“AI 投研委员会”，而不是一组聊天机器人。

## Timing Layer / Market Clock

Timing Engine 解决的是“逻辑对，但市场什么时候认可”。它是市场行为模型，不是 Agent，也不是 Quant。三者边界如下：

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

### 1. 应用层 (app)

**职责**：处理用户输入，暴露系统能力，路由请求到业务服务

**核心模块**：

- `cli/` - 基于 Click 的命令行接口，支持资产分析、情景分析等直接调用
- `api/` - FastAPI 后端 API，供前端调用
- `web/` - 简单的 Web 工作台界面

**对外契约**：无，直接对接用户/前端

---

### 2. 核心层 (core)

**职责**：定义全局契约、接口抽象和基础设施工具，为所有上层提供基础能力

**核心模块**：

- `contracts/` - 基于 Pydantic v2 的领域契约，所有跨层数据交换都遵循这些契约
  - `assertions.py` - 事实断言结构
  - `assets.py` - 资产定义结构
  - `documents.py` - 文档结构
  - `events.py` - 事件结构
  - `ids.py` - 全局ID定义
  - `reporting.py` - 报告结构
  - `scenarios.py` - 情景分析结构
  - `signals.py` - 信号定义结构
  - `traces.py` - 推理追踪结构
- `interfaces/` - 抽象接口定义，隔离具体实现
- `model_gateway/` - 统一模型访问网关
- `observability/` - 可观测性三件套
- `services/` - 核心领域服务
- `settings/` - 全局配置管理

**关键契约**：所有核心领域对象都定义在 `contracts/` 中，所有跨层交互必须使用这些 Pydantic 模型，保证类型安全和数据验证。

---

### 3. 知识层 (knowledge_layer)

**职责**：知识管理、事实存储、语义检索，构建系统的事实基础

**核心模块**：

- `entity_resolution/` - 实体消歧与归一化，确保同一实体在不同数据源中被统一标识
- `assertions/` - 事实断言的增删改查，所有研究结论都以断言形式存储
- `events/` - 事件存储与时间线索引
- `graph_projection/` - 知识关系图投影，用于可视化和关系推理
- `retrieval/` - 基于 pgvector 的向量语义检索，支持知识召回

**关键契约**：遵循 core.contracts 中的断言、实体、事件契约

---

### 4. 推理层 (reasoning)

**职责**：基于事实知识进行分析推理，生成情景和结论

**核心模块**：

- `evidence/` - 证据链管理，追踪结论的证据来源
- `scenarios/` - 多情景分析引擎，对不确定性问题生成多个可能情景
- `router/` - 推理路由，选择合适的推理路径
- `skeptic/` - 怀疑论验证，对结论进行交叉验证和一致性检查
- `traces/` - 完整推理过程追踪，支持审计和复盘
- `state.py` - 推理状态管理，基于 LangGraph 状态机

**关键契约**：使用 core.contracts.scenarios 定义情景结构，使用 traces 定义追踪结构

---

### 5. 认知 Agent 层 (cognitive_agents)

**职责**：提供多视角认知插件和共享黑板，让不同专家视角以统一 schema 参与投资判断。

**核心模块**：

- `contracts.py` - `AgentView`、`BlackboardConflict`、AgentRole、ViewDirection 等统一契约
- `blackboard.py` - `CognitiveBlackboard`，负责观点写入、查询和冲突检测

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

- `contracts.py` - `TimingModelScore`、`TimingDecision`、MarketRegime、TimingAction 等统一契约
- `meta.py` - `MetaTimingEngine`，融合多模型评分、市场阶段权重和 blocker

**关键约束**：Timing 不负责解释产业链，也不负责历史有效性检验。它消费 Agent/黑板/市场数据的结构化输入，输出 `enter`、`wait`、`reduce`、`exit` 或 `block`。

---

### 7. 量化验证层 / 信号实验室 (signal_lab)

**职责**：将 AI 事件理解转化为可回测的 Alpha 信号，并进行验证评分、组合约束和风险提示

**核心模块**：

- `backtests/event_study.py` - 事件研究回测器，计算事件窗收益、超额收益、胜率和衰减
- `features/` - 特征工程，从原始数据生成研究特征
- `labels/` - 标签工程，定义预测目标标签
- `scoring/` - 信号评分，对候选信号进行有效性评分
- `backtests/` - 回测框架，集成 vectorbt 和 Backtrader 进行历史回测

**关键契约**：遵循 core.contracts.signals 中的 `AlphaSignal` 与 `EventAlphaSignal` 信号定义契约。事件型信号必须保留 event_id、event_type、impact_path、industry_impacts、diffusion_stage、market_regime 和 validation_status。

---

### 8. 记忆与学习层 (memory_learning)

**职责**：把市场结果沉淀为长期记忆，让系统从“即时推理”进入“可学习系统”。

**核心模块**：

- `contracts.py` - `MarketEpisode`、`StrategyMemory`、`AgentMemory`、`FailureMemory`
- `journal.py` - `LearningJournal`，记录并查询 episode、strategy、agent 和 failure memory

**关键约束**：Memory 不替代回测，也不直接生成交易建议；它记录真实市场反馈，供 Agent 权重、Timing blocker、策略选择和失败复盘使用。

---

### 9. 数据层 (data_layer)

**职责**：对接外部数据源，清洗归一化数据，实现仓储接口

**核心模块**：

- `adapters/` - 各个数据源的适配器实现（万得、同花顺、Tushare、Yahoo Finance 等）
- `parsers/` - 非结构化数据解析（PDF、网页、财报）
- `normalizers/` - 数据归一化，统一不同数据源的格式
- `repositories/` - 实现 core.interfaces 中定义的仓储接口，对接存储层

**关键契约**：实现 core 中定义的仓储接口，返回遵循核心契约的数据对象

---

### 10. 报告层 (reporting)

**职责**：将分析结果合成为人类可读的报告，并输出为不同格式

**核心模块**：

- `templates/` - 各类报告模板（资产分析卡、专题备忘录、情景分析报告）
- `composer/` - 内容合成引擎，将碎片化结果组合为完整报告
- `projections/` - 格式投影，转换为 Markdown、Word、HTML 等格式输出

**关键契约**：使用 core.contracts.reporting 中的报告结构契约

---

### 11. 存储层 (storage)

**职责**：数据库 schema 定义和迁移管理

**核心文件**：

- `schema.sql` - 完整数据库 schema 定义
- `migrations/` - Alembic 数据库迁移版本管理

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

1. **摄入阶段**：外部数据进入系统，经过适配器、解析、归一化后转换为标准领域对象
2. **知识沉淀**：经过实体消歧后，存储为断言和事件，构建向量索引，完成知识沉淀
3. **推理分析**：根据用户问题，召回相关知识，抽取事件，推导产业链影响路径，判断认知扩散阶段和市场风格
4. **认知竞争**：Fundamental、Macro、Industry Chain、Policy、Sentiment、Bull、Bear、Skeptic 等 Agent 写入黑板，形成结构化多视角冲突
5. **市场择时**：Timing Engine 融合 regime、flow、crowding、sentiment、theme diffusion 等模型，判断市场现在是否会买单
6. **信号验证**：如果生成事件型投资信号，进入信号实验室进行事件研究、超额收益、胜率、衰减和有效性评分
7. **学习沉淀**：把事件结果、策略表现、失败原因和 Agent 观点演化写入 Memory & Learning
8. **报告输出**：将所有分析结果合成，按照对应模板生成最终报告，输出给用户
9. **持久化**：所有中间结果（知识、推理轨迹、黑板观点、择时决策、信号、学习记忆、报告）都持久化到数据库，支持审计和复盘

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

- OpenAI
- Anthropic
- 兼容 OpenAI API 的本地模型服务

---

## 可观测性设计

系统内置了**日志/指标/追踪**三件套，完整覆盖可观测性需求：

### 1. 日志 (logging)

基于 `structlog` 实现结构化日志，所有日志包含上下文信息：

- 请求ID
- 用户ID
- 模块名称
- 耗时信息
- 错误堆栈

### 2. 指标 (metrics)

记录关键系统指标：

- 模型调用次数、token 消耗量、耗时
- 数据摄入数量
- 检索命中率
- API 请求延迟和错误率

### 3. 追踪 (tracer)

完整追踪单个请求/分析任务的整个生命周期：

- 记录每个步骤的输入输出
- 保留模型调用的完整对话历史
- 追踪证据来源和推理路径
- 支持复盘整个分析过程

---

## 技术栈清单

| 领域       | 技术选型                |
| ---------- | ----------------------- |
| 编程语言   | Python 3.11+            |
| 数据验证   | Pydantic v2             |
| Web 框架   | FastAPI                 |
| 命令行     | Click                   |
| 数据库     | PostgreSQL 15+ / SQLite |
| 向量存储   | pgvector                |
| ORM        | SQLAlchemy 2.0          |
| 数据库迁移 | Alembic                 |
| 状态机     | LangGraph               |
| 回测       | vectorbt, Backtrader    |
| 日志       | structlog               |
| 代码格式化 | black, isort, ruff      |

---

## 扩展点与接口约定

### 如何添加新数据源

1. 在 `data_layer/adapters/` 中实现新的适配器类，实现 `DataSourceAdapter` 接口
2. 在 `data_layer/normalizers/` 中添加对应的数据归一化器
3. 注册到数据源工厂，即可使用

**约定**：适配器必须返回符合核心契约的数据对象，不得让上层处理数据源特定格式。

### 如何添加新模型提供商

1. 在 `core/model_gateway/providers/` 中实现新的提供商类，继承 `BaseProvider`
2. 实现三个抽象方法：`chat()`、`structured_output()`、`embed()`
3. 注册到网关，即可在配置中选择使用

**约定**：所有模型调用都必须经过 Model Gateway，不得直接在业务代码中调用模型API。

### 如何添加新报告模板

1. 在 `reporting/templates/` 中添加新模板类
2. 实现 `ReportTemplate` 接口
3. 在报告合成器中注册即可使用

**约定**：模板只负责内容结构，不负责业务逻辑，业务数据由上层传入。

### 如何添加新信号评分算法

1. 在 `signal_lab/scoring/` 中实现新的评分类，实现 `BaseScorer` 接口
2. 注册到评分工厂，即可选择使用

---
