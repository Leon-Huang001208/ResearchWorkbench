# 全自动化闭环迭代与动态多因子路线图

日期：2026-05-28

本文档回答三个问题：

1. AlphaFoundry 距离“全自动化闭环迭代”还差什么。
2. 哪些部分已经有骨架，哪些部分需要继续工程化。
3. 量化动态多因子模型能不能做、怎么做、如何与事件信号结合。

核心结论：

- 当前系统已经不是单纯 AI 投研助手，已经具备 `事件 → 认知 → 择时 → 组合 → 模拟 → 结果 → 记忆` 的研究闭环骨架。
- 但它还不是无人值守的生产级交易闭环，最大短板是：稳定数据、点时一致特征、动态多因子验证、自动反馈权重更新、真实组合风险模型和生产级编排。
- 动态多因子模型可以做，而且应该做；它不替代事件驱动 alpha，而是作为 Quant Validation / Portfolio OS 中的横截面定价与风险解释层。
- 事件信号不应该只作为“买卖建议”，而应该被因子化为稀疏 alpha、主题暴露、产业链传播暴露、预期差暴露和叙事扩散状态，再与传统多因子、资金流、择时模型融合。

当前实现状态：

- 已落地动态多因子 MVP 代码：`core/contracts/factors.py` 与 `signal_lab/factors/`。
- 已支持点时因子矩阵、IC / RankIC / decile spread、滚动 IC 动态权重、事件-因子-择时融合。
- 尚未实现持久化 Factor Store、API 服务层、生产调度和数据库迁移，这些仍属于后续阶段。

---

## 1. 目标定义

### 1.1 目标不是“自动预测股价”

AlphaFoundry 的目标应保持为：

```text
AI 驱动的事件型量化系统
```

而不是：

```text
K 线预测系统
LSTM 收盘价预测系统
纯技术指标系统
```

系统真正要自动化的是：

```text
发现事件
→ 理解产业链和预期差
→ 生成可交易事件信号
→ 用量化方法验证
→ 判断当前市场是否买单
→ 构建组合
→ 模拟/执行
→ 记录结果
→ 从失败和成功中更新模型
```

### 1.2 全自动化闭环的最低标准

一个可称为“全自动化闭环迭代”的版本，至少要满足：

| 环节 | 最低要求 |
| --- | --- |
| 数据摄入 | 定时采集、去重、失败重试、质量监控、可回放 |
| 事件生成 | 统一事件 taxonomy、实体映射、影响路径、置信度、证据引用 |
| Agent 认知 | 多视角观点写入黑板，观点可审计、可评分、可回放 |
| 信号生成 | 事件信号结构化，带 horizon、方向、subject、score、confidence |
| 量化验证 | Event study、IC、RankIC、decay、win rate、turnover、容量/成本 |
| 择时判断 | Regime、flow、sentiment、crowding、liquidity 等在线评分 |
| 动态多因子 | 点时一致特征、横截面标签、因子 IC、动态权重、组合输入 |
| 组合构建 | 风险预算、行业/主题/个股集中度、流动性、换手、相关性约束 |
| 模拟交易 | 调仓、成本、滑点、净值、基准比较、归因 |
| 结果记录 | Signal outcome、失败原因、经验教训、相似案例检索 |
| 反馈学习 | 自动更新模型权重、Agent 权重、事件类型先验、择时阈值 |
| 治理监控 | 版本管理、实验追踪、漂移告警、回滚、kill switch |

---

## 2. 当前实现盘点

以下盘点基于当前代码结构，而不是理想架构图。

| 模块 | 当前状态 | 已具备能力 | 主要缺口 |
| --- | --- | --- | --- |
| Data / Ingestion | 部分实现 | 多类爬虫、摄入、原始存储、去重、队列和调度骨架 | 点时一致数据、数据质量 SLA、因子级数据版本、生产级失败恢复不足 |
| Event Engine | 部分实现 | 事件抽取、事件信号生成、实体/产业链映射能力 | 事件 taxonomy 还需更稳定，事件去重/合并/相似事件检索需要增强 |
| Knowledge Graph | 部分实现 | 实体解析、图投影、行业链关系和事件映射 | Temporal Industry Graph 仍需形成可回测的时序关系版本 |
| Cognitive Agents | 骨架较完整 | AgentFactory、Orchestrator、黑板、多角色 Agent、集成测试 | Agent 观点长期绩效评分、Agent 权重动态调整、黑板持久化和冲突裁决还需加强 |
| Timing Engine | 骨架较完整 | 9 类择时模型、MetaTimingEngine、regime 权重、blocker 逻辑 | 模型多为规则/启发式，缺少真实市场数据校准、择时 overlay 回测和在线漂移反馈 |
| Signal Lab | 部分实现 | FeatureBuilder、特征组、event backtest、信号评分/排序 | 动态多因子 OS 尚未实现，IC/RankIC/decile spread/因子归因仍需系统化 |
| Closed Loop Service | 研究闭环骨架 | 事件生成信号、回测、Outcome、LearningJournal、PatternLearner | 仍偏 rule-driven，缺少生产级 job 编排、自动调参、异常恢复、审计状态机 |
| Portfolio Service | 初步实现 | 组合提案、冲突解决、持仓约束、主题/行业集中度约束 | 缺少风险模型、协方差、因子暴露中性、优化器、换手预算、流动性容量模型 |
| Paper Trading | 初步实现 | 模拟组合、调仓、交易成本、滑点、净值和绩效指标 | 缺少真实价格流自动更新、订单级模拟、A 股交易限制、停牌/涨跌停处理 |
| Outcome / Memory | 部分实现 | SignalOutcome、OutcomeService、LearningJournal、PatternLearner、FailureMemory | 经验还没有自动稳定地反哺策略权重、Agent 权重、择时阈值和因子权重 |
| Governance | 部分实现 | 策略版本、实验追踪、回滚 | 需要接入每次闭环 run 的实验元数据和可复现实验包 |
| Monitoring | 部分实现 | 健康指标、漂移检测、告警阈值 | 需要覆盖数据漂移、因子漂移、Agent 失准、信号分布漂移、实盘偏离 |

---

## 3. 与目标的差距评估

下面是面向目标状态的工程成熟度估计。它不是收益能力承诺，只是按“代码骨架 + 可运行闭环 + 生产可用性”的综合判断。

| 目标能力 | 当前成熟度 | 判断 |
| --- | ---: | --- |
| AI 投研自动化 | 65% | 事件、知识、Agent、报告和信号链路已有较多基础 |
| 事件信号研究闭环 | 50% | `Event → Signal → Backtest → Outcome → Memory` 有骨架，但仍需稳定数据和自动编排 |
| 择时研究闭环 | 45% | 模型齐全度不错，但缺少真实校准、择时 overlay 验证和权重学习 |
| 组合模拟闭环 | 40% | 组合提案和 paper trading 已有，风险模型和价格流接入不足 |
| 动态多因子模型 | 35% | 已有 MVP：因子契约、点时矩阵、IC/RankIC、滚动 IC 权重、事件融合；仍缺 Factor Store、服务层、持久化和真实数据校准 |
| 生产级无人值守 | 25% | 服务和路由很多，但缺少统一 job 状态机、重试、审计、回放、监控联动 |
| 可投入实盘交易 | 15% | 还需要大量风控、执行、合规、异常处理和真实环境验证 |
| 自演化反馈学习 | 10% | Memory 有雏形，但自动更新策略结构和模型权重仍未形成闭环 |

如果目标是“研究平台 + 模拟交易闭环”，当前大约走到 45%-55%。

如果目标是“生产级自动交易闭环”，当前大约走到 20%-30%。

最重要的差距不是“少几个 Agent”，而是：

```text
稳定可验证 alpha
点时一致数据
动态多因子验证系统
自动反馈学习
生产级编排和监控
```

---

## 4. 还没有实现的关键部分

### 4.1 Point-in-Time Feature Store

动态多因子和事件回测都依赖点时一致数据。

目前缺口：

- 特征没有统一注册、版本、依赖、刷新频率和有效时间。
- 财报、持仓、研报、新闻、价格等数据还没有统一 `as_of_date` 语义。
- 还需要避免未来函数、幸存者偏差、复权口径不一致。
- 缺少按交易日生成横截面 feature matrix 的标准接口。

目标能力：

```text
任意交易日 T
→ 只能读取 T 当时已知的数据
→ 生成股票横截面特征
→ 绑定特征版本和数据快照
→ 可回放、可审计、可复现
```

### 4.2 Factor Registry

当前已新增 `signal_lab/factors` 的 MVP，但还不是完整 Factor OS。

需要新增：

- 因子定义：名称、方向、数据源、刷新频率、滞后规则、适用市场。
- 因子分组：价值、质量、成长、动量、反转、波动、流动性、资金流、情绪、事件、主题、拥挤。
- 因子变换：winsorize、standardize、neutralize、rank、decay。
- 因子版本：参数变化要可追踪。
- 因子依赖：计算依赖哪些原始表和中间特征。

### 4.3 IC / RankIC / Decile Spread 引擎

当前已实现第一版 `FactorEvaluator`，支持 IC / RankIC / decile spread。下一步要把它扩展成系统级评估引擎。

必须支持：

- 横截面 IC。
- RankIC。
- 分组收益。
- 多 horizon：1d、3d、5d、10d、20d、60d。
- 行业中性/市值中性后的 IC。
- regime 分层 IC。
- turnover 和 decay。
- 多重检验控制。
- out-of-sample / walk-forward。

### 4.4 Dynamic Factor Weight Model

动态多因子的核心不是“因子越多越好”，而是：

```text
不同市场阶段，应该相信不同因子
```

目前缺口：

- 没有统一的因子权重学习器。
- 没有 regime-conditioned factor weights。
- 没有把 Timing Engine 的 regime / crowding / flow 作为动态权重条件。
- 没有对因子失效进行自动降权。

### 4.5 Event-Factor Fusion Layer

当前已实现第一版 `EventFactorFusion`，但事件信号和生产组合链路仍需要更深集成。

需要新增融合层：

```text
Event Alpha
+ Factor Alpha
+ Timing Readiness
+ Memory Prior
+ Risk Constraint
→ Final Expected Alpha
```

### 4.6 自动反馈学习

Outcome 和 LearningJournal 已经能记录结果，但还不够。

还需要：

- 失败自动分类。
- 从失败类别更新模型参数。
- Agent 观点按长期绩效动态加权。
- 事件类型按历史胜率和 regime 表现动态设先验。
- 择时模型按 mistake type 调整权重。
- 因子模型按滚动 IC 和 decay 调整权重。

### 4.7 生产级 Orchestration

当前有 PipelineService、ClosedLoopService 和系统事件总线，但还需要更硬的任务编排。

目标是每个闭环 run 都有：

- run id。
- 输入快照。
- 任务 DAG。
- 每步状态。
- 重试策略。
- 失败原因。
- 输出 artifacts。
- 实验版本。
- 可回放入口。

---

## 5. 需要改进的部分

### 5.1 Event Engine

改进方向：

- 建立更严格的事件 taxonomy：政策、技术突破、价格变化、供需冲击、订单、财报、监管、海外映射、产业链事故。
- 对同一事件做合并、去重、强度更新，而不是重复生成信号。
- 增加事件新颖度：首次出现、重复强化、反转、市场已知程度。
- 增加事件生命周期：early discovery、diffusion、consensus、crowded、decay。
- 将事件映射到 Temporal Industry Graph，而不是仅用静态行业标签。

### 5.2 Cognitive Agents

改进方向：

- Agent 观点必须结构化：direction、confidence、evidence、counter_evidence、invalidation、horizon。
- Agent 不直接决定交易，只贡献可审计认知变量。
- Bull/Bear/Skeptic 要记录历史命中率。
- Skeptic Agent 要强制调用历史相似事件和失败记忆。
- Agent 输出进入黑板后要有 conflict resolver 和 evidence scorer。

### 5.3 Timing Engine

改进方向：

- 用历史数据校准每个 timing model 的阈值。
- 对每个 event type 评估 timing overlay 是否提升收益/回撤。
- 把 `enter/wait/reduce/block` 的结果纳入 outcome。
- 增加 regime transition 模型，判断风格切换概率。
- 增加 timing model 的滚动绩效归因。

### 5.4 Portfolio OS

改进方向：

- 从“分数排序 + 简单权重”升级到“预期收益 + 风险约束 + 优化器”。
- 增加协方差矩阵和风险模型。
- 增加行业、主题、风格、事件类型、流动性、拥挤度暴露约束。
- 增加组合级 drawdown guard、turnover budget、capacity check。
- 对事件信号和因子信号做归因，知道 PnL 来自哪里。

### 5.5 Paper Trading

改进方向：

- 接入真实价格流。
- 支持 A 股涨跌停、停牌、T+1、最小交易单位、手续费和印花税。
- 支持定时再平衡、事件触发再平衡和风险触发再平衡。
- 每次调仓输出交易原因、信号版本、择时决策和风险解释。

### 5.6 Monitoring / Governance

改进方向：

- 数据质量监控：缺失率、延迟、异常值、源变化。
- 因子漂移监控：分布漂移、IC 漂移、覆盖率变化。
- 信号漂移监控：事件类型分布、方向偏差、行业偏差、置信度偏移。
- Agent 漂移监控：某 Agent 观点长期偏多/偏空、证据弱化、错误率升高。
- 组合监控：实际暴露 vs 目标暴露，成交偏离，回撤触发。

---

## 6. 动态多因子模型能做吗

能做，而且应该做。

但它的定位必须清楚：

```text
动态多因子不是替代事件驱动
动态多因子是把事件 alpha 放进可验证、可比较、可组合的横截面框架
```

事件模型负责回答：

```text
发生了什么？
哪些公司受益？
逻辑链是什么？
市场可能如何扩散？
```

动态多因子负责回答：

```text
这些股票在当前横截面里是否真的更有优势？
这个事件 alpha 是否已经拥挤？
当前 regime 下应该给事件因子多大权重？
与价值、成长、动量、流动性、资金流等因子相比，它的边际贡献是多少？
```

---

## 7. 动态多因子的核心设计

### 7.1 因子 universe

建议先做 A 股日频横截面模型，不做高频。

基础股票池：

- 剔除 ST。
- 剔除长期停牌。
- 剔除上市时间过短。
- 按流动性过滤。
- 可选：按沪深 300 / 中证 500 / 中证 1000 / 全 A 分池建模。

### 7.2 标签定义

必须先定义清楚模型要预测什么。

推荐标签：

| 标签 | 用途 |
| --- | --- |
| `fwd_return_5d` | 短周期事件扩散 |
| `fwd_excess_return_5d` | 相对行业或指数的短期超额 |
| `fwd_return_20d` | 主题持续性 |
| `fwd_excess_return_20d` | 中期 alpha 验证 |
| `max_drawdown_20d` | 风险惩罚 |
| `hit_20d` | 分类式命中率 |

事件信号不要只看绝对收益，必须看超额收益：

```text
excess_return = stock_forward_return - benchmark_or_industry_forward_return
```

### 7.3 因子分类

第一版动态多因子不需要追求复杂，建议分成 8 大类：

| 因子组 | 示例 |
| --- | --- |
| Value | PE、PB、PS、EV/EBITDA、股息率 |
| Quality | ROE、毛利率、现金流、资产负债率、盈利稳定性 |
| Growth | 营收增速、净利增速、订单增速、CAPEX 增速 |
| Momentum | 20d/60d 动量、突破、相对强度 |
| Reversal / Risk | 短期反转、波动率、最大回撤、beta |
| Liquidity / Flow | 成交额、换手率、北向、融资、ETF、主力资金 |
| Sentiment / Crowding | 热度、涨停、研报覆盖、基金持仓、融资拥挤 |
| Event / Narrative | 事件强度、产业链距离、预期差、传播阶段、Agent 分歧 |

### 7.4 事件因子化

事件信号要拆成可量化因子，而不是只保留一句 thesis。

建议事件因子：

| 事件因子 | 含义 |
| --- | --- |
| `event_intensity` | 事件强度，来自事件类型、来源可靠性、证据数量 |
| `event_novelty` | 新颖度，越少被市场讨论越高 |
| `event_confidence` | LLM / Agent / 证据综合置信度 |
| `industry_chain_distance` | 公司距离事件源头的产业链距离 |
| `propagation_stage` | early、diffusion、consensus、crowded、decay |
| `beneficiary_directness` | 直接受益 vs 间接受益 |
| `expectation_gap_score` | 市场预期与系统判断的差距 |
| `agent_consensus` | 多 Agent 一致性 |
| `agent_conflict` | 多 Agent 分歧程度 |
| `skeptic_risk_score` | Skeptic Agent 识别出的逻辑风险 |
| `historical_event_prior` | 相似事件历史胜率/超额收益 |
| `timing_readiness` | Timing Engine 输出的当前可交易性 |
| `crowding_blocker` | 是否已经过度拥挤 |
| `alpha_decay_score` | 是否已经 price in |

这些因子可以进入动态多因子模型，也可以作为事件专属 alpha 子模型。

### 7.5 动态权重

静态多因子：

```text
score_i,t = Σ w_k * factor_k,i,t
```

动态多因子：

```text
score_i,t = Σ w_k,t(regime, flow, crowding, volatility, memory) * factor_k,i,t
```

关键差别是权重随市场状态变化。

例如：

| 市场状态 | 更应相信 | 更应降低 |
| --- | --- | --- |
| AI 成长主线 | event、growth、momentum、theme diffusion | value、dividend |
| 红利/防御 | quality、dividend、low volatility | high beta event |
| 游资题材 | sentiment、theme diffusion、flow、limit-up structure | long horizon fundamental |
| 机构趋势 | growth、quality、earnings revision、northbound flow | short-term noise |
| risk-off | liquidity、low volatility、crowding risk | high beta theme |
| 流动性牛市 | momentum、beta、breadth | defensive |

### 7.6 推荐模型路线

第一阶段不要直接上复杂深度学习。推荐从可解释模型开始：

1. 因子标准化 + 线性加权 baseline。
2. Rolling IC 动态权重。
3. Regime-conditioned 因子权重。
4. Ridge / ElasticNet 横截面回归。
5. LightGBM / XGBoost ranking。
6. Meta learner 融合 event alpha、factor alpha、timing alpha。

不要第一步就做：

- LSTM 预测收盘价。
- 端到端黑盒深度模型。
- 无约束强化学习实盘交易。

---

## 8. 动态多因子与事件信号如何结合

### 8.1 三种结合方式

#### 方式一：事件作为稀疏 alpha

事件发生时才激活：

```text
event_alpha_i,t = event_score_i,t * timing_readiness_t * memory_prior_event_type
```

适合：

- 政策。
- 海外科技事件。
- 产业链价格变化。
- 订单和财报催化。

#### 方式二：事件作为因子特征

把事件变量放进横截面特征矩阵：

```text
X_i,t = [
  value_i,t,
  quality_i,t,
  growth_i,t,
  momentum_i,t,
  flow_i,t,
  event_intensity_i,t,
  expectation_gap_i,t,
  propagation_stage_i,t,
  agent_consensus_i,t
]
```

适合训练动态多因子模型。

#### 方式三：事件作为 portfolio overlay

多因子给出基础排名，事件信号只做 overlay：

```text
base_factor_score
+ event_boost
- crowding_penalty
× timing_gate
→ final_alpha_score
```

适合事件较少但强度很高的情况。

### 8.2 推荐融合公式

第一版可以使用透明公式：

```text
event_score =
  0.20 * event_intensity
+ 0.15 * beneficiary_directness
+ 0.15 * expectation_gap_score
+ 0.10 * agent_consensus
+ 0.10 * historical_event_prior
+ 0.10 * timing_readiness
+ 0.10 * event_novelty
- 0.10 * skeptic_risk_score
- 0.10 * crowding_blocker
```

多因子得分：

```text
factor_score_i,t = Σ w_k,t * zscore(factor_k,i,t)
```

最终 alpha：

```text
final_alpha_i,t =
  λ_event,t * event_score_i,t
+ λ_factor,t * factor_score_i,t
+ λ_timing,t * timing_readiness_t
- λ_risk,t * risk_penalty_i,t
```

其中：

```text
λ_event,t + λ_factor,t + λ_timing,t = 1
```

并且 `λ_event,t` 应由 regime 决定：

| regime | 事件权重 |
| --- | ---: |
| 主题扩散/成长风格 | 高 |
| 游资题材 | 高，但 horizon 更短 |
| 机构趋势 | 中 |
| 红利防御 | 低 |
| risk-off | 很低或 block |
| 过度拥挤 | 降低或 block |

### 8.3 事件信号进入组合的流程

```text
EventSignal
    ↓
Event Feature Extractor
    ↓
Event Alpha Score
    ↓
Dynamic Factor Model
    ↓
Timing Gate
    ↓
Risk / Crowding / Liquidity Penalty
    ↓
Portfolio Optimizer
    ↓
Paper Trading / Execution
    ↓
Outcome
    ↓
Memory & Weight Update
```

### 8.4 与 Timing Engine 的关系

Timing 不应该被塞进 Agent，也不应该只作为技术指标。

正确关系：

```text
Agent Layer：解释事件为什么重要
Factor Layer：判断横截面里谁更优
Timing Layer：判断现在能不能交易
Portfolio Layer：判断买多少、如何分散
Memory Layer：判断过去这种组合是否有效
```

事件逻辑很强，但 Timing Engine 输出 `block` 时：

```text
final_action = wait / block
```

事件逻辑一般，但多因子、资金流、regime 都支持时：

```text
final_action = small enter / watchlist
```

---

## 9. 建议新增模块结构

第一版建议在现有 `signal_lab` 下新增因子系统，不另起一个过大的顶层架构。

```text
signal_lab/
  factors/
    __init__.py
    contracts.py
    registry.py
    transforms.py
    neutralization.py
    factor_matrix.py
    factor_store.py
    groups/
      value.py
      quality.py
      growth.py
      momentum.py
      risk.py
      liquidity.py
      sentiment.py
      event.py
    evaluation/
      ic.py
      rank_ic.py
      decile_spread.py
      decay.py
      attribution.py
    models/
      static_linear.py
      rolling_ic_weighted.py
      regime_conditioned.py
      ranker.py
    fusion/
      event_factor_fusion.py
      timing_overlay.py
      portfolio_inputs.py
```

配套契约建议：

```text
core/contracts/factors.py
core/contracts/factor_evaluation.py
core/contracts/factor_model.py
core/contracts/alpha_fusion.py
```

配套仓储建议：

```text
data_layer/repositories/factor_repository.py
data_layer/repositories/factor_evaluation_repository.py
data_layer/repositories/factor_model_repository.py
```

配套服务建议：

```text
services/factor_service.py
services/factor_evaluation_service.py
services/dynamic_factor_model_service.py
services/alpha_fusion_service.py
```

---

## 10. 实施路线

### Phase 0：统一闭环定义与审计包

目标：让每次自动闭环 run 都可追踪、可回放、可复现。

任务：

- 为 Pipeline / ClosedLoop 增加统一 `run_id`。
- 保存输入事件快照、信号版本、择时版本、组合版本、价格数据版本。
- 输出 run summary。
- 每一步状态可查询：pending、running、succeeded、failed、skipped。
- 失败时写入 FailureMemory。

验收：

- 任意一次闭环 run 能回答：用了什么数据、生成了什么信号、为什么买/不买、结果如何。

### Phase 1：Event → Return 验证强化

目标：先证明某些事件类型是否长期有 alpha。

任务：

- 固化事件 taxonomy。
- 建立事件相似度和事件合并机制。
- 对每类事件跑 event study。
- 输出 per event type 的 win rate、avg excess return、Sharpe、decay、max drawdown。
- 按 regime 分层评估。

验收：

- 能回答：GPU 禁令、AI 模型发布、HBM 涨价、政策刺激等事件过去是否赚钱，在哪些 horizon 和 regime 有效。

### Phase 2：Factor Registry + Point-in-Time Feature Matrix

目标：让动态多因子有可靠数据底座。

任务：

- 实现 `FactorDefinition`、`FactorValue`、`FactorSnapshot`。
- 每个因子定义数据延迟规则和可用时间。
- 建立横截面 feature matrix 生成器。
- 实现 winsorize、standardize、industry neutralize、market cap neutralize。
- 对至少 30 个基础因子生成日频矩阵。

验收：

- 输入交易日 T 和股票池，输出点时一致 `N stocks × K factors` 矩阵。
- 任意因子值可追溯到数据源和计算版本。

### Phase 3：Factor Evaluation OS

目标：知道哪些因子真的有效。

任务：

- 实现 IC / RankIC。
- 实现 decile spread。
- 实现 decay 和 turnover。
- 实现 regime slicing。
- 实现行业/市值中性后的因子评估。
- 实现滚动窗口评估。

验收：

- 每个因子都有最近 3m、6m、12m 的 IC、RankIC、ICIR、分层收益、turnover。
- 能自动发现因子失效、反转或 regime 依赖。

### Phase 4：Dynamic Multi-Factor Model

目标：生成稳定、可解释的横截面 alpha。

任务：

- 实现 baseline static factor model。
- 实现 rolling IC weighted model。
- 实现 regime-conditioned factor model。
- 可选实现 LightGBM ranking model。
- 输出 `factor_alpha_score`、`factor_contribution`、`factor_risk_exposure`。

验收：

- 对 out-of-sample 数据产生正向 RankIC。
- 相比静态权重，动态权重在至少部分 regime 下提升 ICIR 或降低回撤。
- 每天能解释：今天为什么这个股票排名靠前。

### Phase 5：Event-Factor Fusion

目标：让事件信号和多因子不再分裂。

任务：

- 实现事件因子组。
- 将事件强度、产业链距离、预期差、Agent 一致性、Timing readiness 写入 factor matrix。
- 实现 `final_alpha = event + factor + timing - risk`。
- 做 ablation：只用事件、只用因子、事件+因子、事件+因子+择时。

验收：

- 能证明事件信号加入后是否提升 RankIC、超额收益、胜率或回撤。
- 能按事件类型、主题和 regime 解释边际贡献。

### Phase 6：Portfolio OS 强化

目标：把 alpha 变成组合，而不是简单选股列表。

任务：

- 建立风险模型和协方差估计。
- 约束行业、主题、风格、事件类型、个股和流动性暴露。
- 增加 turnover budget。
- 增加 risk parity / mean-variance / heuristic optimizer。
- 输出组合级归因。

验收：

- 同一批 alpha 输入，组合层能降低集中度和回撤。
- 组合输出能解释每个持仓的 alpha、风险、约束和权重原因。

### Phase 7：Paper Trading 自动闭环

目标：无人值守跑模拟组合。

任务：

- 定时生成信号。
- 自动计算择时和多因子得分。
- 自动生成组合。
- 自动调仓模拟。
- 自动记录 outcome。
- 自动写入 memory。
- 自动生成日报/周报。

验收：

- 连续运行至少 30 个交易日。
- 每天可输出：新事件、候选信号、被 block 的信号、持仓变化、PnL、归因、失败案例。

### Phase 8：Feedback Learning

目标：系统开始真正迭代，而不是只记录历史。

任务：

- 用 Outcome 更新事件类型先验。
- 用 rolling IC 更新因子权重。
- 用 timing mistake 更新 MetaTimingEngine 权重。
- 用 Agent 观点历史表现更新 Agent 权重。
- 用失败记忆生成下次信号的 risk penalty。

验收：

- 系统参数能从历史结果中自动更新。
- 所有自动更新都有治理版本和回滚能力。

---

## 11. 动态多因子 MVP 规格

第一版不要做大而全，建议做一个最小闭环：

### 11.1 输入

- 股票日频行情。
- 行业分类。
- 市值。
- 基础财务和估值。
- 资金流或成交活跃度。
- 事件信号。
- Timing decision。

### 11.2 因子

先做 12-20 个基础因子：

- 估值：PE/PB/PS。
- 成长：营收增速、净利增速。
- 质量：ROE、毛利率、负债率。
- 动量：20d、60d。
- 波动：20d volatility、max drawdown。
- 流动性：成交额、换手率。
- 事件：event intensity、expectation gap、timing readiness、historical event prior。

### 11.3 标签

- `fwd_excess_return_5d`
- `fwd_excess_return_20d`

### 11.4 模型

第一版：

```text
rolling_ic_weighted + regime override
```

不要一开始上复杂黑盒模型。

### 11.5 输出

每个股票每天输出：

```json
{
  "subject_id": "300750.SZ",
  "as_of_date": "2026-05-28",
  "factor_alpha_score": 0.73,
  "event_alpha_score": 0.68,
  "timing_readiness": 0.61,
  "final_alpha_score": 0.70,
  "top_contributors": [
    "event.expectation_gap",
    "momentum.20d",
    "quality.roe"
  ],
  "risk_flags": [
    "crowding_medium"
  ]
}
```

---

## 12. 关键评估指标

### 12.1 Event Signal 指标

- 平均超额收益。
- 胜率。
- 最大回撤。
- Sharpe / Information Ratio。
- decay。
- event type 分层表现。
- regime 分层表现。
- 从事件发生到收益兑现的 lag。

### 12.2 Factor 指标

- IC。
- RankIC。
- ICIR。
- decile spread。
- long-short return。
- turnover。
- factor decay。
- coverage。
- missing rate。
- industry-neutral IC。
- size-neutral IC。

### 12.3 Fusion 指标

- 事件 + 因子是否优于事件单独。
- 事件 + 因子 + Timing 是否优于事件 + 因子。
- 每个模块的边际贡献。
- final_alpha 的分层收益。
- 被 Timing block 的信号是否避免亏损。
- 被 crowding penalty 降权的信号是否降低回撤。

### 12.4 Portfolio 指标

- 年化收益。
- 超额收益。
- 最大回撤。
- Sharpe。
- Information Ratio。
- turnover。
- 成本后收益。
- 行业暴露。
- 主题暴露。
- 个股集中度。
- 流动性容量。

### 12.5 Learning 指标

- 事件类型先验是否改善。
- 因子权重是否随 regime 合理变化。
- Agent 权重是否与历史绩效一致。
- 失败记忆是否降低重复错误。
- 自动更新是否造成过拟合。

---

## 13. 风险和约束

### 13.1 最大风险：对不存在的 alpha 做复杂择时

正确顺序必须是：

```text
先验证有没有 alpha
再讨论什么时候交易 alpha
最后讨论怎么放大 alpha
```

动态多因子也一样，必须先看 IC / RankIC，再做动态权重。

### 13.2 未来函数风险

这是动态多因子的生死线。

所有数据必须有：

- 数据发布日期。
- 系统采集时间。
- 可交易生效时间。
- 修订版本。

### 13.3 过拟合风险

必须控制：

- 因子数量。
- 参数搜索次数。
- 事件类型切分粒度。
- regime 切分粒度。
- 回测窗口选择。

每个模型都要有 out-of-sample 和 walk-forward。

### 13.4 LLM 幻觉风险

Agent 输出不能直接交易。

必须经过：

```text
证据引用
结构化 schema
历史验证
择时检查
风险约束
```

### 13.5 A 股交易约束

需要显式处理：

- 涨跌停。
- 停牌。
- T+1。
- ST。
- 流动性不足。
- 一字板无法成交。
- 印花税和佣金。
- 指数/行业基准选择。

---

## 14. 近期优先级

不要继续无节制加层。最近最重要的是把研究闭环变成可验证闭环。

### P0

1. 固化 `Event → Return` 验证。
2. 建立 factor registry 和 point-in-time feature matrix。
3. 实现 IC / RankIC / decile spread。
4. 把事件信号因子化。

### P1

1. 实现 rolling IC dynamic factor model。
2. 实现 event-factor fusion。
3. 接入 Timing Engine 作为 gate 和 weight condition。
4. 做 ablation 和 regime slicing。

### P2

1. 强化 Portfolio OS。
2. 强化 Paper Trading 自动闭环。
3. 接入 Outcome → Memory → Weight Update。
4. 接入 governance 和 monitoring。

### P3

1. Market simulation。
2. Reflexivity model。
3. Agent Darwinism。
4. Self-evolving architecture。

P3 现在只进路线图，不应成为近期主线。

---

## 15. 目标差距的最终判断

AlphaFoundry 当前已经有：

```text
AI 投研系统的主体骨架
事件型量化的方向
Agent / Timing / Memory / Portfolio / Paper Trading 的基础模块
```

但距离真正的全自动化闭环还差：

```text
稳定数据底座
动态多因子验证层
事件信号与因子信号融合
生产级编排和可回放
自动反馈权重学习
组合级风险和执行约束
```

下一阶段最关键的不是再设计更大的架构，而是把下面这条链打通并量化证明：

```text
Event
→ Event Factor
→ Dynamic Multi-Factor Score
→ Timing Gate
→ Portfolio
→ Paper Trading
→ Outcome
→ Memory
→ Weight Update
```

只要这条链能持续运行，并且每个环节都能回答“是否提升了超额收益或降低了风险”，AlphaFoundry 才会从 AI 投研系统真正进入 AI-native Investment Operating System。
