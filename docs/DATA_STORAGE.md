# AlphaFoundry 数据存储设计文档

## 目录

1. [概述](#概述)
2. [PostgreSQL 表结构](#postgresql-表结构)
3. [数据契约](#数据契约)
4. [仓储接口](#仓储接口)
5. [仓储实现](#仓储实现)

---

## 概述

AlphaFoundry 使用 PostgreSQL + pgvector 作为主要数据存储，采用模块化单体架构，通过仓储模式实现数据访问。

### 核心设计原则

1. **JSONB 优先**: 使用 PostgreSQL JSONB 存储复杂对象
2. **向量支持**: 使用 pgvector 存储和搜索嵌入向量
3. **多租户**: 支持 team_id 和 project_id 字段进行多租户隔离
4. **时间戳**: 所有表包含 created_at 和 updated_at 字段
5. **软索引**: 通过索引优化常用查询性能

---

## PostgreSQL 表结构

### 1. 核心事实层

#### entity（实体表）

| 字段 | 类型 | 说明 |
|------|------|------|
| entity_id | TEXT PK | 实体 ID |
| canonical_id | TEXT UNIQUE | 规范 ID |
| entity_type | TEXT | 实体类型 |
| canonical_name | TEXT | 规范名称 |
| aliases | JSONB | 别名列表 |
| vendor_ids | JSONB | 各供应商 ID 映射 |
| properties | JSONB | 属性字典 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**索引**:
- idx_entity_canonical_id: canonical_id
- idx_entity_type: entity_type
- idx_entity_team_project: (team_id, project_id)

---

#### source_document（源文档表）

| 字段 | 类型 | 说明 |
|------|------|------|
| doc_id | TEXT PK | 文档 ID |
| source_type | TEXT | 来源类型 (news/report/...) |
| title | TEXT | 标题 |
| published_at | TIMESTAMPTZ | 发布时间 |
| source_name | TEXT | 来源名称 |
| content_hash | TEXT | 内容哈希 |
| rights_ref | TEXT | 版权引用 |
| parser_version | TEXT | 解析器版本 |
| object_uri | TEXT | 对象存储 URI |
| metadata | JSONB | 元数据 |
| embedding | vector(1536) | 嵌入向量 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_document_source_type: source_type
- idx_document_published_at: published_at
- idx_document_team_project: (team_id, project_id)
- idx_document_embedding: USING hnsw (embedding vector_cosine_ops)

---

#### assertion（断言表）

| 字段 | 类型 | 说明 |
|------|------|------|
| assertion_id | TEXT PK | 断言 ID |
| subject_entity_id | TEXT FK | 主体实体 ID |
| predicate | TEXT | 谓词 |
| object_entity_id | TEXT | 对象实体 ID |
| object_value | JSONB | 对象值 |
| observed_at | TIMESTAMPTZ | 观察时间 |
| valid_from | TIMESTAMPTZ | 有效起始时间 |
| valid_to | TIMESTAMPTZ | 有效结束时间 |
| confidence | NUMERIC | 置信度 |
| source_doc_id | TEXT FK | 源文档 ID |
| source_span | JSONB | 源文本位置 |
| extractor_version | TEXT | 提取器版本 |
| reviewer_status | TEXT | 审核状态 (pending/approved/rejected) |
| reviewer | TEXT | 审核人 |
| reviewed_at | TIMESTAMPTZ | 审核时间 |
| trace_ref | TEXT | 推理追踪引用 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |

**索引**:
- idx_assertion_subject: subject_entity_id
- idx_assertion_source: source_doc_id
- idx_assertion_status: reviewer_status
- idx_assertion_team_project: (team_id, project_id)

---

#### canonical_event（规范事件表）

| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | TEXT PK | 事件 ID |
| event_type | TEXT | 事件类型 |
| summary | TEXT | 摘要 |
| event_time | TIMESTAMPTZ | 事件时间 |
| impact_direction | TEXT | 影响方向 (bullish/bearish/neutral) |
| confidence | NUMERIC | 置信度 |
| needs_review | BOOLEAN | 是否需要审核 |
| source_doc_id | TEXT FK | 源文档 ID |
| payload | JSONB | 完整负载 |
| reviewer_status | TEXT | 审核状态 |
| reviewer | TEXT | 审核人 |
| reviewed_at | TIMESTAMPTZ | 审核时间 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_event_source: source_doc_id
- idx_event_time: event_time
- idx_event_team_project: (team_id, project_id)

---

#### reasoning_trace（推理追踪表）

| 字段 | 类型 | 说明 |
|------|------|------|
| trace_id | TEXT PK | 追踪 ID |
| request_type | TEXT | 请求类型 |
| question | TEXT | 问题 |
| subject_ids | JSONB | 主体 ID 列表 |
| retrieved_doc_ids | JSONB | 检索到的文档 ID 列表 |
| retrieved_assertion_ids | JSONB | 检索到的断言 ID 列表 |
| graph_paths | JSONB | 图路径 |
| intermediate_hypotheses | JSONB | 中间假设列表 |
| final_answer | TEXT | 最终答案 |
| provider | TEXT | 提供商 |
| model_name | TEXT | 模型名称 |
| prompt_version | TEXT | 提示版本 |
| total_latency_ms | INTEGER | 总延迟(ms) |
| total_tokens | INTEGER | 总 token 数 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_trace_request_type: request_type
- idx_trace_created_at: created_at DESC
- idx_trace_team_project: (team_id, project_id)

---

### 2. 资产分析层

#### asset_snapshot（资产分析快照表）

| 字段 | 类型 | 说明 |
|------|------|------|
| snapshot_id | TEXT PK | 快照 ID |
| canonical_id | TEXT | 规范 ID |
| as_of | TIMESTAMPTZ | 快照时间 |
| financial | JSONB | 财务数据 |
| fund_flow | JSONB | 资金流向 |
| price_volume | JSONB | 价量数据 |
| valuation | JSONB | 估值数据 |
| shareholder | JSONB | 股东数据 |
| industry | JSONB | 行业数据 |
| event_impact | JSONB | 事件影响 |
| macro_exposure | JSONB | 宏观敞口 |
| evidence_refs | JSONB | 证据引用列表 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_asset_snapshot_canonical_id: canonical_id
- idx_asset_snapshot_as_of: as_of
- idx_asset_snapshot_canonical_as_of: (canonical_id, as_of DESC)
- idx_asset_snapshot_team_project: (team_id, project_id)

---

#### stock_price_data（股票历史价格表）

| 字段 | 类型 | 说明 |
|------|------|------|
| price_id | TEXT PK | 价格 ID |
| code | TEXT | 股票代码 (如 600519.SH) |
| date | TEXT | 日期 (如 2024-05-01) |
| open | NUMERIC | 开盘价 |
| high | NUMERIC | 最高价 |
| low | NUMERIC | 最低价 |
| close | NUMERIC | 收盘价 |
| volume | NUMERIC | 成交量 |
| turnover | NUMERIC | 成交额 |
| data_source | TEXT | 数据来源 (manual/csv) |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_stock_price_code: code
- idx_stock_price_date: date

---

### 3. 市场结构化事实层 (AF-AUTO-007)

#### stock_master（股票基础信息表）

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | TEXT PK | 股票代码 (如 600519.SH) |
| raw_code | TEXT | 纯数字代码 (如 600519) |
| name | TEXT | 公司名称 |
| exchange | TEXT | 交易所 (SH/SZ/BJ) |
| market | TEXT | 市场 (A-share/HK/US) |
| industry_level1 | TEXT | 一级行业 |
| industry_level2 | TEXT | 二级行业 |
| industry_level3 | TEXT | 三级行业 |
| list_date | TIMESTAMPTZ | 上市日期 |
| source | TEXT | 数据来源 |
| updated_at | TIMESTAMPTZ | 更新时间 |
| created_at | TIMESTAMPTZ | 创建时间 |

#### stock_daily_bar（日行情表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| symbol | TEXT | 股票代码 |
| trade_date | TIMESTAMPTZ | 交易日 |
| open | NUMERIC | 开盘价 |
| high | NUMERIC | 最高价 |
| low | NUMERIC | 最低价 |
| close | NUMERIC | 收盘价 |
| volume | NUMERIC | 成交量 |
| amount | NUMERIC | 成交额 |
| turnover | NUMERIC | 换手率 |
| source | TEXT | 数据来源 |
| raw_payload | JSONB | 原始数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

**唯一约束**: (symbol, trade_date, source) → uq_stock_daily_bar_symbol_date_source

#### stock_quote_snapshot（实时行情快照表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| symbol | TEXT | 股票代码 |
| quote_time | TIMESTAMPTZ | 行情时间 |
| last_price | NUMERIC | 最新价 |
| change_pct | NUMERIC | 涨跌幅 |
| volume | NUMERIC | 成交量 |
| amount | NUMERIC | 成交额 |
| turnover | NUMERIC | 换手率 |
| pe | NUMERIC | 市盈率 |
| pb | NUMERIC | 市净率 |
| source | TEXT | 数据来源 |
| raw_payload | JSONB | 原始数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

#### stock_financial_metric（财务指标表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| symbol | TEXT | 股票代码 |
| report_date | TIMESTAMPTZ | 报告期 |
| report_type | TEXT | 类型 (annual/quarterly) |
| total_revenue | NUMERIC | 营业收入 |
| net_profit | NUMERIC | 净利润 |
| total_assets | NUMERIC | 总资产 |
| total_liabilities | NUMERIC | 总负债 |
| equity | NUMERIC | 净资产 |
| roe | NUMERIC | 净资产收益率 |
| roa | NUMERIC | 总资产收益率 |
| gross_margin | NUMERIC | 毛利率 |
| net_margin | NUMERIC | 净利率 |
| debt_ratio | NUMERIC | 资产负债率 |
| source | TEXT | 数据来源 |
| raw_payload | JSONB | 原始数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

#### stock_valuation（估值指标表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| symbol | TEXT | 股票代码 |
| as_of | TIMESTAMPTZ | 估值日期 |
| pe_ttm | NUMERIC | 市盈率 TTM |
| pe_dynamic | NUMERIC | 动态市盈率 |
| pb | NUMERIC | 市净率 |
| ps | NUMERIC | 市销率 |
| market_cap | NUMERIC | 总市值 |
| float_market_cap | NUMERIC | 流通市值 |
| source | TEXT | 数据来源 |
| raw_payload | JSONB | 原始数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

#### stock_shareholder（股东信息表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| symbol | TEXT | 股票代码 |
| report_date | TIMESTAMPTZ | 报告期 |
| holder_name | TEXT | 股东名称 |
| holder_rank | INTEGER | 排名 |
| shares | NUMERIC | 持股数量 |
| holding_pct | NUMERIC | 持股比例 |
| holder_type | TEXT | 股东类型 |
| source | TEXT | 数据来源 |
| raw_payload | JSONB | 原始数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

#### index_component（指数成分表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| index_symbol | TEXT | 指数代码 |
| component_symbol | TEXT | 成分股代码 |
| component_name | TEXT | 成分股名称 |
| weight | NUMERIC | 权重 |
| as_of | TIMESTAMPTZ | 日期 |
| source | TEXT | 数据来源 |
| raw_payload | JSONB | 原始数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

#### etl_run（ETL 运行记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | TEXT PK | 运行 ID |
| job_name | TEXT | 任务名称 |
| source | TEXT | 数据源 |
| status | TEXT | 状态 (running/success/failed/partial) |
| started_at | TIMESTAMPTZ | 开始时间 |
| finished_at | TIMESTAMPTZ | 完成时间 |
| items_fetched | INTEGER | 获取数量 |
| items_normalized | INTEGER | 标准化数量 |
| items_saved | INTEGER | 保存数量 |
| error_message | TEXT | 错误信息 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

---

### 4. 信号与决策层

#### alpha_signal（Alpha 信号表）

| 字段 | 类型 | 说明 |
|------|------|------|
| signal_id | TEXT PK | 信号 ID |
| discriminator | TEXT | 区分类型 (alpha_signal/event_alpha_signal) |
| subject_id | TEXT | 标的 ID |
| horizon | TEXT | 时间范围 |
| thesis | TEXT | 论点 |
| score | NUMERIC | 评分 |
| confidence | NUMERIC | 置信度 |
| scenario_refs | JSONB | 情景引用列表 |
| evidence_refs | JSONB | 证据引用列表 |
| status | TEXT | 状态 (research_only/...) |
| event_id | TEXT | 事件 ID (EventAlphaSignal) |
| event_type | TEXT | 事件类型 (EventAlphaSignal) |
| event_time | TIMESTAMPTZ | 事件时间 (EventAlphaSignal) |
| impact_path | JSONB | 影响路径 (EventAlphaSignal) |
| industry_impacts | JSONB | 行业影响 (EventAlphaSignal) |
| bullish_companies | JSONB | 看涨公司列表 (EventAlphaSignal) |
| bearish_companies | JSONB | 看跌公司列表 (EventAlphaSignal) |
| diffusion_stage | TEXT | 传播阶段 (EventAlphaSignal) |
| market_regime | TEXT | 市场状态 (EventAlphaSignal) |
| validation_status | TEXT | 验证状态 (EventAlphaSignal) |
| validation_metrics | JSONB | 验证指标 (EventAlphaSignal) |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**索引**:
- idx_alpha_signal_subject_id: subject_id
- idx_alpha_signal_event_id: event_id
- idx_alpha_signal_team_project: (team_id, project_id)

---

#### trade_candidate（交易候选表）

| 字段 | 类型 | 说明 |
|------|------|------|
| candidate_id | TEXT PK | 候选 ID |
| signal_id | TEXT FK | 信号 ID |
| action | TEXT | 动作 (buy/sell/hold) |
| sizing_hint | NUMERIC | 仓位建议 |
| risk_notes | JSONB | 风险提示列表 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_trade_candidate_signal_id: signal_id
- idx_trade_candidate_team_project: (team_id, project_id)

---

#### agent_view（Agent 观点表）

| 字段 | 类型 | 说明 |
|------|------|------|
| view_id | TEXT PK | 观点 ID |
| agent_name | TEXT | Agent 名称 |
| agent_role | TEXT | Agent 角色 |
| target_id | TEXT | 目标 ID |
| view | TEXT | 观点内容 |
| thesis | TEXT | 论点 |
| confidence | NUMERIC | 置信度 |
| event_id | TEXT | 事件 ID |
| reasoning | JSONB | 推理链 |
| evidence_refs | JSONB | 证据引用列表 |
| tool_refs | JSONB | 工具引用列表 |
| memory_refs | JSONB | 记忆引用列表 |
| workflow_id | TEXT | 工作流 ID |
| evaluation | JSONB | 评估结果 |
| metadata | JSONB | 元数据 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_agent_view_agent_role: agent_role
- idx_agent_view_target_id: target_id
- idx_agent_view_event_id: event_id
- idx_agent_view_team_project: (team_id, project_id)

---

#### blackboard_conflict（黑板冲突表）

| 字段 | 类型 | 说明 |
|------|------|------|
| conflict_id | TEXT PK | 冲突 ID |
| target_id | TEXT | 目标 ID |
| event_id | TEXT | 事件 ID |
| view_ids | JSONB | 观点 ID 列表 |
| summary | TEXT | 摘要 |
| severity | TEXT | 严重程度 |
| confidence | NUMERIC | 置信度 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_blackboard_conflict_target_id: target_id
- idx_blackboard_conflict_event_id: event_id
- idx_blackboard_conflict_team_project: (team_id, project_id)

---

#### timing_decision（择时决策表）

| 字段 | 类型 | 说明 |
|------|------|------|
| decision_id | TEXT PK | 决策 ID |
| signal_id | TEXT | 信号 ID |
| action | TEXT | 动作 (buy/sell/wait) |
| readiness_score | NUMERIC | 就绪评分 |
| market_regime | TEXT | 市场状态 |
| model_scores | JSONB | 各模型评分列表 |
| active_weights | JSONB | 活跃权重 |
| blockers | JSONB | 阻止因素列表 |
| rationale | JSONB | 理由列表 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_timing_decision_signal_id: signal_id
- idx_timing_decision_action: action
- idx_timing_decision_created_at: created_at DESC

---

#### signal_outcome（信号结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| outcome_id | TEXT PK | 结果 ID |
| event_id | TEXT | 事件 ID |
| signal_id | TEXT | 信号 ID |
| subject_id | TEXT | 标的 ID |
| event_date | TIMESTAMPTZ | 事件日期 |
| event_type | TEXT | 事件类型 |
| timing_action | TEXT | 择时动作 |
| entry_rule | TEXT | 入场规则 |
| horizon | TEXT | 时间范围 |
| benchmark | TEXT | 基准 |
| outcome_return | NUMERIC | 实际收益 |
| outcome_excess_return | NUMERIC | 超额收益 |
| max_drawdown | NUMERIC | 最大回撤 |
| decay | NUMERIC | 衰减 |
| failure_reason | TEXT | 失败原因 |
| lesson | TEXT | 教训 |
| evaluated_at | TIMESTAMPTZ | 评估时间 |
| metadata | JSONB | 元数据 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_signal_outcome_event_id: event_id
- idx_signal_outcome_signal_id: signal_id
- idx_signal_outcome_subject_id: subject_id
- idx_signal_outcome_event_type: event_type

---

### 4. 记忆与学习层

#### market_episode（市场事件记忆表）

| 字段 | 类型 | 说明 |
|------|------|------|
| episode_id | TEXT PK | 记忆 ID |
| event_id | TEXT | 事件 ID |
| event_type | TEXT | 事件类型 |
| market_regime | TEXT | 市场状态 |
| initial_reaction | TEXT | 初始反应 |
| outcome_horizon | TEXT | 结果时间范围 |
| outcome_return | NUMERIC | 结果收益 |
| outcome_excess_return | NUMERIC | 超额收益 |
| timing_action | TEXT | 择时动作 |
| signal_id | TEXT | 信号 ID |
| timing_decision_id | TEXT | 择时决策 ID |
| failed_reason | TEXT | 失败原因 |
| lesson | TEXT | 教训 |
| evidence_refs | JSONB | 证据引用列表 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_market_episode_event_type: event_type
- idx_market_episode_market_regime: market_regime

---

#### strategy_memory（策略记忆表）

| 字段 | 类型 | 说明 |
|------|------|------|
| strategy_id | TEXT PK | 策略 ID |
| signal_family | TEXT | 信号族 |
| market_regime | TEXT | 市场状态 |
| sample_size | INTEGER | 样本大小 |
| win_rate | NUMERIC | 胜率 |
| average_excess_return | NUMERIC | 平均超额收益 |
| sharpe_ratio | NUMERIC | 夏普比率 |
| notes | JSONB | 笔记列表 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_strategy_memory_signal_family: signal_family
- idx_strategy_memory_market_regime: market_regime

---

#### failure_memory（失败记忆表）

| 字段 | 类型 | 说明 |
|------|------|------|
| failure_id | TEXT PK | 失败 ID |
| source_id | TEXT | 来源 ID |
| failure_type | TEXT | 失败类型 |
| root_cause | TEXT | 根因 |
| corrective_action | TEXT | 纠正措施 |
| evidence_refs | JSONB | 证据引用列表 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_failure_memory_failure_type: failure_type
- idx_failure_memory_source_id: source_id

---

#### outcome_record（交易结果记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| outcome_id | TEXT PK | 结果 ID |
| signal_id | TEXT | 信号 ID |
| candidate_id | TEXT | 候选 ID |
| entry_time | TIMESTAMPTZ | 入场时间 |
| exit_time | TIMESTAMPTZ | 出场时间 |
| entry_price | NUMERIC | 入场价格 |
| exit_price | NUMERIC | 出场价格 |
| return_5d | NUMERIC | 5日收益 |
| return_20d | NUMERIC | 20日收益 |
| return_60d | NUMERIC | 60日收益 |
| benchmark_excess_return | NUMERIC | 基准超额收益 |
| thesis_success | BOOLEAN | 论点是否成功 |
| failure_classification | TEXT | 失败分类 |
| failure_notes | TEXT | 失败笔记 |
| thesis_text | TEXT | 论点文本 |
| propagation_path | JSONB | 传播路径 |
| market_regime | TEXT | 市场状态 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_outcome_record_signal_id: signal_id
- idx_outcome_record_candidate_id: candidate_id

---

### 5. 文档处理层 (v1)

#### document_v1（v1 统一文档表）

| 字段 | 类型 | 说明 |
|------|------|------|
| doc_id | TEXT PK | 文档 ID |
| doc_type | TEXT | 文档类型 |
| source_type | TEXT | 来源类型 |
| title | TEXT | 标题 |
| summary | TEXT | 摘要 |
| content | TEXT | 内容 |
| doc_metadata | JSONB | 文档元数据 |
| source_metadata | JSONB | 来源元数据 |
| classification | JSONB | 分类 |
| quality | JSONB | 质量评分 |
| evidence_profile | JSONB | 证据概况 |
| timeliness | JSONB | 时效性 |
| processing | JSONB | 处理状态 |
| review | JSONB | 审核状态 |
| extra | JSONB | 额外字段 |
| source_name | TEXT | 来源名称 |
| source_url | TEXT | 来源 URL |
| language | TEXT | 语言 |
| content_hash | TEXT | 内容哈希 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**索引**:
- idx_document_v1_doc_type: doc_type
- idx_document_v1_source_type: source_type
- idx_document_v1_content_hash: content_hash

---

#### document_chunk_v1（文档分块表）

| 字段 | 类型 | 说明 |
|------|------|------|
| chunk_id | TEXT PK | 分块 ID |
| doc_id | TEXT FK | 文档 ID |
| chunk_index | INTEGER | 分块索引 |
| chunk_type | TEXT | 分块类型 |
| title | TEXT | 标题 |
| content | TEXT | 内容 |
| start_offset | INTEGER | 起始偏移 |
| end_offset | INTEGER | 结束偏移 |
| token_count | INTEGER | Token 数 |
| topics | JSONB | 主题列表 |
| entities | JSONB | 实体列表 |
| summary | TEXT | 摘要 |
| embedding | TEXT | 嵌入向量 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_document_chunk_v1_doc_id: doc_id

---

#### document_tag_v1（文档标签表）

| 字段 | 类型 | 说明 |
|------|------|------|
| tag_id | TEXT PK | 标签 ID |
| doc_id | TEXT FK | 文档 ID |
| tag | TEXT | 标签 |
| tag_type | TEXT | 标签类型 |
| confidence | NUMERIC | 置信度 |
| source | TEXT | 来源 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_document_tag_v1_doc_id: doc_id
- idx_document_tag_v1_tag: tag

---

#### document_summary_v1（文档摘要表）

| 字段 | 类型 | 说明 |
|------|------|------|
| summary_id | TEXT PK | 摘要 ID |
| doc_id | TEXT FK | 文档 ID |
| summary_type | TEXT | 摘要类型 |
| summary | TEXT | 摘要 |
| bullet_points | JSONB | 要点列表 |
| generator_version | TEXT | 生成器版本 |
| quality_score | NUMERIC | 质量评分 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_document_summary_v1_doc_id: doc_id

---

#### document_entity_mention_v1（实体提及表）

| 字段 | 类型 | 说明 |
|------|------|------|
| mention_id | TEXT PK | 提及 ID |
| doc_id | TEXT FK | 文档 ID |
| chunk_id | TEXT | 分块 ID |
| entity_id | TEXT FK | 实体 ID |
| entity_name | TEXT | 实体名称 |
| entity_type | TEXT | 实体类型 |
| start_offset | INTEGER | 起始偏移 |
| end_offset | INTEGER | 结束偏移 |
| context | TEXT | 上下文 |
| confidence | NUMERIC | 置信度 |
| is_primary | BOOLEAN | 是否主要实体 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_document_entity_mention_v1_doc_id: doc_id
- idx_document_entity_mention_v1_chunk_id: chunk_id
- idx_document_entity_mention_v1_entity_id: entity_id
- idx_document_entity_mention_v1_entity_type: entity_type

---

#### document_event_v1（文档事件表）

| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | TEXT PK | 事件 ID |
| doc_id | TEXT FK | 文档 ID |
| canonical_event_id | TEXT FK | 规范事件 ID |
| event_type | TEXT | 事件类型 |
| event_time | TIMESTAMPTZ | 事件时间 |
| subject_entity | TEXT | 主体实体 |
| object_entity | TEXT | 对象实体 |
| event_summary | TEXT | 事件摘要 |
| impact_direction | TEXT | 影响方向 |
| evidence_text | TEXT | 证据文本 |
| confidence | NUMERIC | 置信度 |
| extra | JSONB | 额外字段 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_document_event_v1_doc_id: doc_id
- idx_document_event_v1_canonical_event_id: canonical_event_id
- idx_document_event_v1_event_type: event_type

---

#### crawl_run_v1（抓取运行记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | TEXT PK | 运行 ID |
| source_type | TEXT | 来源类型 |
| status | TEXT | 状态 |
| started_at | TIMESTAMPTZ | 开始时间 |
| completed_at | TIMESTAMPTZ | 结束时间 |
| success_count | INTEGER | 成功数 |
| failure_count | INTEGER | 失败数 |
| skipped_count | INTEGER | 跳过数 |
| error_log | TEXT | 错误日志 |
| config | JSONB | 配置 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_crawl_run_v1_source_type: source_type

---

#### source_cursor_v1（来源游标表）

| 字段 | 类型 | 说明 |
|------|------|------|
| cursor_id | TEXT PK | 游标 ID |
| source_type | TEXT | 来源类型 |
| source_name | TEXT | 来源名称 |
| last_successful_crawl_time | TIMESTAMPTZ | 上次成功抓取时间 |
| last_source_doc_id | TEXT | 上次源文档 ID |
| lookback_window_minutes | INTEGER | 回溯窗口(分钟) |
| consecutive_failures | INTEGER | 连续失败数 |
| is_paused | BOOLEAN | 是否暂停 |
| config | JSONB | 配置 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**索引**:
- idx_source_cursor_v1_source_type: source_type

---

#### report_run_v1（报告运行记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | TEXT PK | 运行 ID |
| report_type | TEXT | 报告类型 |
| report_template | TEXT | 报告模板 |
| status | TEXT | 状态 |
| config | JSONB | 配置 |
| document_ids | JSONB | 文档 ID 列表 |
| signal_ids | JSONB | 信号 ID 列表 |
| output_path | TEXT | 输出路径 |
| error_log | TEXT | 错误日志 |
| started_at | TIMESTAMPTZ | 开始时间 |
| completed_at | TIMESTAMPTZ | 结束时间 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_report_run_v1_report_type: report_type

---

### 6. 摄取与队列层

#### ingestion_queue_item（摄取队列项表）

| 字段 | 类型 | 说明 |
|------|------|------|
| item_id | TEXT PK | 项 ID |
| source_type | TEXT | 来源类型 |
| source_id | TEXT | 来源 ID |
| raw_content | TEXT | 原始内容 |
| title | TEXT | 标题 |
| url | TEXT | URL |
| priority | INTEGER | 优先级 |
| status | TEXT | 状态 (pending/processing/completed/failed) |
| retry_count | INTEGER | 重试次数 |
| max_retries | INTEGER | 最大重试次数 |
| failure_reason | TEXT | 失败原因 |
| created_at | TIMESTAMPTZ | 创建时间 |
| processed_at | TIMESTAMPTZ | 处理时间 |
| dedup_hash | TEXT | 去重哈希 |

**索引**:
- idx_ingestion_queue_item_source_type: source_type
- idx_ingestion_queue_item_status: status
- idx_ingestion_queue_item_dedup_hash: dedup_hash

---

### 7. 决策与审核层

#### decision_workspace（决策工作表）

| 字段 | 类型 | 说明 |
|------|------|------|
| workspace_id | TEXT PK | 工作区 ID |
| workspace_date | TIMESTAMPTZ | 工作区日期 |
| status | TEXT | 状态 (open/closed) |
| candidate_ids | JSONB | 候选 ID 列表 |
| team_id | TEXT | 团队 ID |
| created_at | TIMESTAMPTZ | 创建时间 |
| created_by | TEXT | 创建人 |
| closed_at | TIMESTAMPTZ | 关闭时间 |
| notes | TEXT | 笔记 |

**索引**:
- idx_decision_workspace_date: workspace_date
- idx_decision_workspace_status: status

---

#### analyst_decision（分析师决策表）

| 字段 | 类型 | 说明 |
|------|------|------|
| decision_id | TEXT PK | 决策 ID |
| workspace_id | TEXT FK | 工作区 ID |
| candidate_id | TEXT | 候选 ID |
| candidate_type | TEXT | 候选类型 |
| previous_status | TEXT | 之前状态 |
| final_action_type | TEXT | 最终动作类型 |
| action_by | TEXT | 操作人 |
| action_at | TIMESTAMPTZ | 操作时间 |
| rationale | TEXT | 理由 |
| changes | JSONB | 变更 |
| revision_history | JSONB | 修订历史 |
| is_closed | BOOLEAN | 是否关闭 |

**索引**:
- idx_analyst_decision_workspace_id: workspace_id
- idx_analyst_decision_candidate_id: candidate_id

---

#### decision_audit（决策审计表）

| 字段 | 类型 | 说明 |
|------|------|------|
| audit_id | TEXT PK | 审计 ID |
| decision_id | TEXT FK | 决策 ID |
| action | TEXT | 动作 |
| actor | TEXT | 操作者 |
| timestamp | TIMESTAMPTZ | 时间戳 |
| before_state | JSONB | 之前状态 |
| after_state | JSONB | 之后状态 |
| ip_address | TEXT | IP 地址 |
| user_agent | TEXT | 用户代理 |

**索引**:
- idx_decision_audit_decision_id: decision_id
- idx_decision_audit_timestamp: timestamp

---

#### post_mortem_record（决策复盘表）

| 字段 | 类型 | 说明 |
|------|------|------|
| post_mortem_id | TEXT PK | 复盘 ID |
| decision_id | TEXT FK | 决策 ID |
| original_decision | TEXT | 原始决策 |
| realized_outcome | TEXT | 实际结果 |
| outcome_metrics | JSONB | 结果指标 |
| learning_points | TEXT | 学习要点 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |
| linked_signal_accuracy | NUMERIC | 关联信号准确率 |

**索引**:
- idx_post_mortem_decision_id: decision_id

---

#### audit_log（审计日志表）

| 字段 | 类型 | 说明 |
|------|------|------|
| log_id | TEXT PK | 日志 ID |
| entity_type | TEXT | 实体类型 |
| entity_id | TEXT | 实体 ID |
| action | TEXT | 动作 |
| actor | TEXT | 操作者 |
| details | JSONB | 详情 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_audit_log_entity_type: entity_type
- idx_audit_log_entity_id: entity_id

---

### 8. 模拟与回测层

#### paper_portfolio（模拟组合表）

| 字段 | 类型 | 说明 |
|------|------|------|
| portfolio_id | TEXT PK | 组合 ID |
| proposal_id | TEXT | 提案 ID |
| name | TEXT | 名称 |
| status | TEXT | 状态 |
| assumptions | JSONB | 假设 |
| current_snapshot | JSONB | 当前快照 |
| snapshots | JSONB | 快照列表 |
| rebalance_events | JSONB | 调仓事件列表 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_paper_portfolio_proposal_id: proposal_id

---

#### simulation_result（模拟结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| result_id | TEXT PK | 结果 ID |
| portfolio_id | TEXT FK | 组合 ID |
| name | TEXT | 名称 |
| mode | TEXT | 模式 (replay/...) |
| assumptions | JSONB | 假设 |
| performance | JSONB | 表现 |
| benchmark_comparisons | JSONB | 基准比较列表 |
| nav_series | JSONB | 净值序列 |
| rebalance_count | INTEGER | 调仓次数 |
| total_turnover | NUMERIC | 总换手率 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_simulation_result_portfolio_id: portfolio_id

---

#### replay_job（回放任务表）

| 字段 | 类型 | 说明 |
|------|------|------|
| job_id | TEXT PK | 任务 ID |
| name | TEXT | 名称 |
| description | TEXT | 描述 |
| event_filter | JSONB | 事件过滤 |
| max_events | INTEGER | 最大事件数 |
| status | TEXT | 状态 |
| created_at | TIMESTAMPTZ | 创建时间 |
| completed_at | TIMESTAMPTZ | 完成时间 |

**索引**:
- idx_replay_job_status: status

---

#### replay_result（回放结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 结果 ID |
| job_id | TEXT FK | 任务 ID |
| event_id | TEXT | 事件 ID |
| signal_id | TEXT | 信号 ID |
| outcome_id | TEXT | 结果 ID |
| event_type | TEXT | 事件类型 |
| source_type | TEXT | 来源类型 |
| signal_score | NUMERIC | 信号评分 |
| signal_confidence | NUMERIC | 信号置信度 |
| timing_action | TEXT | 择时动作 |
| outcome_return | NUMERIC | 结果收益 |
| outcome_excess_return | NUMERIC | 超额收益 |
| max_drawdown | NUMERIC | 最大回撤 |
| decay | NUMERIC | 衰减 |
| error | TEXT | 错误 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_replay_result_job_id: job_id

---

#### portfolio_proposal（组合提案表）

| 字段 | 类型 | 说明 |
|------|------|------|
| proposal_id | TEXT PK | 提案 ID |
| name | TEXT | 名称 |
| candidates | JSONB | 候选列表 |
| allocations | JSONB | 分配方案 |
| constraints_applied | JSONB | 应用的约束列表 |
| excluded_signals | JSONB | 排除的信号列表 |
| rationale | JSONB | 理由 |
| team_id | TEXT | 团队 ID |
| project_id | TEXT | 项目 ID |
| created_at | TIMESTAMPTZ | 创建时间 |

---

### 9. 治理与监控层

#### strategy_version（策略版本表）

| 字段 | 类型 | 说明 |
|------|------|------|
| version_id | TEXT PK | 版本 ID |
| component_type | TEXT | 组件类型 |
| component_name | TEXT | 组件名称 |
| version_number | INTEGER | 版本号 |
| description | TEXT | 描述 |
| config | JSONB | 配置 |
| content_hash | TEXT | 内容哈希 |
| parent_version_id | TEXT | 父版本 ID |
| is_active | BOOLEAN | 是否活跃 |
| created_at | TIMESTAMPTZ | 创建时间 |
| created_by | TEXT | 创建人 |
| tags | JSONB | 标签列表 |

**索引**:
- idx_strategy_version_component_type: component_type
- idx_strategy_version_component_name: component_name

---

#### experiment_record（实验记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| experiment_id | TEXT PK | 实验 ID |
| name | TEXT | 名称 |
| description | TEXT | 描述 |
| strategy_version_ids | JSONB | 策略版本 ID 列表 |
| experiment_type | TEXT | 实验类型 |
| entity_id | TEXT | 实体 ID |
| metrics | JSONB | 指标 |
| status | TEXT | 状态 |
| started_at | TIMESTAMPTZ | 开始时间 |
| completed_at | TIMESTAMPTZ | 完成时间 |
| tags | JSONB | 标签列表 |
| metadata | JSONB | 元数据 |

**索引**:
- idx_experiment_record_entity_id: entity_id
- idx_experiment_record_status: status

---

#### health_metrics（健康指标表）

| 字段 | 类型 | 说明 |
|------|------|------|
| metric_id | TEXT PK | 指标 ID |
| subsystem | TEXT | 子系统 |
| timestamp | TIMESTAMPTZ | 时间戳 |
| throughput | NUMERIC | 吞吐量 |
| error_rate | NUMERIC | 错误率 |
| avg_latency_ms | NUMERIC | 平均延迟(ms) |
| p99_latency_ms | NUMERIC | 99分位延迟(ms) |
| queue_depth | INTEGER | 队列深度 |
| items_processed | INTEGER | 处理项目数 |
| items_failed | INTEGER | 失败项目数 |
| extra | JSONB | 额外字段 |

**索引**:
- idx_health_metrics_subsystem: subsystem
- idx_health_metrics_timestamp: timestamp

---

#### drift_report（漂移报告表）

| 字段 | 类型 | 说明 |
|------|------|------|
| report_id | TEXT PK | 报告 ID |
| dimension | TEXT | 维度 |
| timestamp | TIMESTAMPTZ | 时间戳 |
| baseline_window_start | TIMESTAMPTZ | 基准窗口开始 |
| baseline_window_end | TIMESTAMPTZ | 基准窗口结束 |
| current_window_start | TIMESTAMPTZ | 当前窗口开始 |
| current_window_end | TIMESTAMPTZ | 当前窗口结束 |
| drift_score | NUMERIC | 漂移评分 |
| is_drift | BOOLEAN | 是否漂移 |
| threshold | NUMERIC | 阈值 |
| baseline_distribution | JSONB | 基准分布 |
| current_distribution | JSONB | 当前分布 |
| details | JSONB | 详情 |

**索引**:
- idx_drift_report_dimension: dimension
- idx_drift_report_timestamp: timestamp

---

#### alert_threshold（告警阈值表）

| 字段 | 类型 | 说明 |
|------|------|------|
| threshold_id | TEXT PK | 阈值 ID |
| name | TEXT | 名称 |
| subsystem | TEXT | 子系统 |
| dimension | TEXT | 维度 |
| metric_field | TEXT | 指标字段 |
| operator | TEXT | 操作符 (gte/lte/...) |
| value | NUMERIC | 值 |
| severity | TEXT | 严重程度 (warning/critical) |
| cooldown_minutes | INTEGER | 冷却时间(分钟) |
| enabled | BOOLEAN | 是否启用 |

---

#### alert_payload（告警记录见表）

| 字段 | 类型 | 说明 |
|------|------|------|
| alert_id | TEXT PK | 告警 ID |
| threshold_id | TEXT FK | 阈值 ID |
| severity | TEXT | 严重程度 |
| status | TEXT | 状态 (open/acknowledged/resolved) |
| subsystem | TEXT | 子系统 |
| dimension | TEXT | 维度 |
| title | TEXT | 标题 |
| description | TEXT | 描述 |
| observed_value | NUMERIC | 观察值 |
| threshold_value | NUMERIC | 阈值 |
| triggered_at | TIMESTAMPTZ | 触发时间 |
| acknowledged_at | TIMESTAMPTZ | 确认时间 |
| resolved_at | TIMESTAMPTZ | 解决时间 |
| metadata | JSONB | 元数据 |

**索引**:
- idx_alert_payload_threshold_id: threshold_id
- idx_alert_payload_status: status
- idx_alert_payload_triggered_at: triggered_at

---

#### incident_record（事件记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| incident_id | TEXT PK | 事件 ID |
| alert_id | TEXT FK | 告警 ID |
| subsystem | TEXT | 子系统 |
| severity | TEXT | 严重程度 |
| title | TEXT | 标题 |
| description | TEXT | 描述 |
| detected_at | TIMESTAMPTZ | 检测时间 |
| resolved_at | TIMESTAMPTZ | 解决时间 |
| resolution_notes | TEXT | 解决笔记 |
| metadata | JSONB | 元数据 |

**索引**:
- idx_incident_record_alert_id: alert_id
- idx_incident_record_subsystem: subsystem
- idx_incident_record_detected_at: detected_at

---

### 10. 产业链层

#### temporal_relation（时间化产业链关系表）

| 字段 | 类型 | 说明 |
|------|------|------|
| relation_id | TEXT PK | 关系 ID |
| from_entity_id | TEXT | 起始实体 ID |
| to_entity_id | TEXT | 目标实体 ID |
| relationship_type | TEXT | 关系类型 |
| strength | NUMERIC | 强度 |
| valid_from | TIMESTAMPTZ | 有效起始时间 |
| valid_to | TIMESTAMPTZ | 有效结束时间 |
| chain_position | TEXT | 产业链位置 |
| industry | TEXT | 行业 |
| metadata | JSONB | 元数据 |
| evidence_refs | JSONB | 证据引用列表 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引**:
- idx_temporal_relation_from_entity: from_entity_id
- idx_temporal_relation_to_entity: to_entity_id
- idx_temporal_relation_type: relationship_type
- idx_temporal_relation_industry: industry
- idx_temporal_relation_valid_period: (valid_from, valid_to)

---

#### industry_chain（产业链表）

| 字段 | 类型 | 说明 |
|------|------|------|
| chain_id | TEXT PK | 产业链 ID |
| name | TEXT | 名称 |
| industry | TEXT | 行业 |
| nodes | JSONB | 节点列表 |
| relations | JSONB | 关系列表 |
| as_of | TIMESTAMPTZ | 时间戳 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**索引**:
- idx_industry_chain_industry: industry
- idx_industry_chain_as_of: as_of

---

## 数据契约

### 概述

所有数据契约定义在 `core/contracts/` 目录下，使用 Pydantic v2 实现。

### 核心契约模块

| 模块 | 说明 |
|------|------|
| ids.py | CanonicalId |
| documents.py | DocumentEnvelope |
| documents_v1.py | v1 文档系列契约 (DocumentV1, DocumentChunkV1, 等) |
| assertions.py | Assertion |
| events.py | CanonicalEvent |
| assets.py | AssetAnalysisSnapshot, AssetAnalysisCard, 等 |
| signals.py | AlphaSignal, EventAlphaSignal, TradeCandidate |
| outcomes.py | SignalOutcome |
| outcome_journal.py | TradeOutcome, FailureClassification, SimilarCase, WeeklyReviewReport |
| timing_engine.py | TimingFactors, EventStudyMetrics, ReadinessScore |
| decision_console.py | AnalystDecision, DecisionAudit, DecisionWorkspace, PostMortemRecord |
| review_framework.py | ReviewPosition, EvidenceReference, ReviewCard, CognitiveBlackboard, ConflictDetectionSummary |
| governance.py | StrategyVersion, ExperimentRecord, GovernanceMetadata, GovernanceReport, RollbackRequest, RollbackResult, ExperimentComparison, ExperimentCompareRequest, StrategyVersionCreateRequest, StrategyVersionSummary, ExperimentMetricDiff |
| monitoring.py | HealthMetrics, Subsystem, SubsystemHealthSummary, SystemHealthDashboard, AlertThreshold, AlertThresholdCreateRequest, AlertThresholdUpdateRequest, AlertPayload, AlertSeverity, AlertStatus, DriftCheckRequest, DriftDimension, DriftReport, IncidentRecord, IncidentResolveRequest, HealthMetricsSubmitRequest |
| paper_trading.py | PaperPortfolio, PortfolioSnapshot, PositionSnapshot, SimulationAssumptions, SimulationMode, SimulationResult, BenchmarkComparison, RebalanceEvent, RebalanceTrigger, TransactionCost |
| portfolio.py | PortfolioCandidate, PortfolioConstraints, PortfolioProposal |
| replay.py | ReplayJob, ReplayResult, ReplayAggregate |
| backtest.py | DataTier, TimeAvailability, HistoricalReplayQuery, HistoricalEvent, HistoricalEventStream, NewsFeatureType, NewsFeatureQuery, NewsFeatureValue, NewsFeatureSet, EventTechAlignmentRequest, EventTechAlignment, ViewContext, RetrievalConfig |
| reporting.py | SectionSpec, SectionOutput, FactCard, ValidationResult, ValidationResults, TemplateConfig, ReportTask, ReportRunLog, ChartSpec, TableSpec |
| retrieval.py | RetrievalProfileType, EvidenceType, RecencyDecayConfig, SourceWeightConfig, DocTypeLookbackConfig, RetrievalProfile, RetrievalFilters, RetrievalQuery, EvidenceChunk, EvidenceDocument, EvidencePackage, create_daily_report_profile, create_weekly_report_profile, create_monthly_report_profile, create_deep_dive_profile, create_backtest_replay_profile, get_profile |
| industry_chain.py | IndustryNode, IndustryEdge, IndustryGraph, MappingStrength, PropagationStep, PropagationPath, ThesisCard |
| ingestion.py | IngestionQueueItem, IngestionQueueStats, EnqueueRequest, EnqueueResponse, ProcessResponse, RetryResponse |
| traces.py | ReasoningTrace |
| scenarios.py | ScenarioHypothesis, ScenarioSet |
| raw_storage.py | (原始存储) |

### 契约模式

所有契约遵循以下模式：

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

class ExampleContract(BaseModel):
    """示例契约"""
    
    # 必填字段
    id: str = Field(..., description="唯一 ID")
    
    # 可选字段带默认值
    name: Optional[str] = Field(None, description="名称")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    # 复杂类型
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    items: List[str] = Field(default_factory=list, description="项目列表")
    
    # 验证器
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 100:
            raise ValueError('Name too long')
        return v
```

---

## 仓储接口

### 概述

仓储接口定义在 `core/interfaces/repository.py`，提供抽象的数据访问层。

### Repository 基类

```python
from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")

class Repository(ABC, Generic[T]):
    """仓储基类"""
    
    @abstractmethod
    def save(self, entity: T) -> T:
        """保存实体"""
        pass
    
    @abstractmethod
    def get(self, id: str) -> Optional[T]:
        """根据 ID 获取实体"""
        pass
    
    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        """列出实体"""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """删除实体"""
        pass
```

### 专用仓储接口

#### EntityRepository

```python
class EntityRepository(Repository[CanonicalId]):
    """实体仓储"""
    
    @abstractmethod
    def get_by_symbol(self, symbol: str, venue: str) -> Optional[CanonicalId]:
        """根据代码和交易所获取实体"""
        pass
    
    @abstractmethod
    def search(self, query: str) -> List[CanonicalId]:
        """搜索实体"""
        pass
```

#### DocumentRepository

```python
class DocumentRepository(Repository[DocumentEnvelope]):
    """文档仓储"""
    
    @abstractmethod
    def get_by_source(self, source_type: str, source_name: str) -> List[DocumentEnvelope]:
        """根据来源获取文档"""
        pass
    
    @abstractmethod
    def vector_search(self, query_embedding: List[float], limit: int = 10) -> List[DocumentEnvelope]:
        """向量搜索文档"""
        pass
```

#### AssertionRepository

```python
class AssertionRepository(Repository[Assertion]):
    """断言仓储"""
    
    @abstractmethod
    def get_by_subject(self, subject_entity_id: str) -> List[Assertion]:
        """获取某主体的所有断言"""
        pass
    
    @abstractmethod
    def get_pending_review(self) -> List[Assertion]:
        """获取待审核的断言"""
        pass
```

#### EventRepository

```python
class EventRepository(Repository[CanonicalEvent]):
    """事件仓储"""
    
    @abstractmethod
    def get_by_entity(self, entity_id: str) -> List[CanonicalEvent]:
        """获取关联到某实体的事件"""
        pass
    
    @abstractmethod
    def get_by_time_range(self, start: str, end: str) -> List[CanonicalEvent]:
        """获取时间范围内的事件"""
        pass
    
    @abstractmethod
    def get_pending_review(self) -> List[CanonicalEvent]:
        """获取待审核的事件"""
        pass
    
    @abstractmethod
    def list_by_status(self, status: str, limit: int = 100) -> List[CanonicalEvent]:
        """根据审核状态列出事件"""
        pass
```

#### TraceRepository

```python
class TraceRepository(Repository[ReasoningTrace]):
    """推理追踪仓储"""
    
    @abstractmethod
    def get_by_request_type(self, request_type: str) -> List[ReasoningTrace]:
        """根据请求类型获取追踪"""
        pass
```

#### AssetSnapshotRepository

```python
class AssetSnapshotRepository(Repository[AssetAnalysisSnapshot]):
    """资产分析快照仓储"""
    
    @abstractmethod
    def get_latest_by_canonical_id(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """获取某资产的最新快照"""
        pass
    
    @abstractmethod
    def get_by_canonical_id_and_time_range(
        self, canonical_id: str, start_time: str, end_time: str
    ) -> List[AssetAnalysisSnapshot]:
        """获取某资产在时间范围内的快照"""
        pass
```

---

## 仓储实现

### 概述

仓储实现在 `data_layer/repositories/` 目录下，基于 SQLAlchemy ORM 实现。

### BaseRepository

所有仓储继承自 `BaseRepository`，提供基础的数据库会话管理。

### 主要仓储实现

| 仓储 | 文件 | 说明 |
|------|------|------|
| EntityRepository | entity_repository.py | 实体仓储实现 |
| DocumentRepository | document_repository.py | 文档仓储实现 |
| AssertionRepository | assertion_repository.py | 断言仓储实现 |
| EventRepository | event_repository.py | 事件仓储实现 |
| TraceRepository | trace_repository.py | 推理追踪仓储实现 |
| AssetSnapshotRepository | asset_snapshot_repository.py | 资产快照仓储实现 |
| SignalRepository | signal_repository.py | 信号仓储实现 |
| AgentViewRepository | agent_view_repository.py | Agent 观点仓储实现 |
| TimingRepository | timing_repository.py | 择时仓储实现 |
| OutcomeRepository | outcome_repository.py | 结果仓储实现 |
| MemoryRepository | memory_repository.py | 记忆仓储实现 |
| OutcomeJournalRepository | outcome_journal_repository.py | 结果日志仓储实现 |
| DecisionConsoleRepository | decision_console_repository.py | 决策工作台仓储实现 |
| AuditRepository | audit_repository.py | 审计仓储实现 |
| GovernanceRepository | governance_repository.py | 治理仓储实现 |
| MonitoringRepository | monitoring_repository.py | 监控仓储实现 |
| PaperTradingRepository | paper_trading_repository.py | 模拟交易仓储实现 |
| PortfolioRepository | portfolio_repository.py | 组合仓储实现 |
| ReplayRepository | replay_repository.py | 回测仓储实现 |
| IngestionRepository | ingestion_repository.py | 摄取仓储实现 |

### ORM 模型

所有 ORM 模型定义在 `data_layer/repositories/models.py`，对应 PostgreSQL 表结构。

### 实现模式

```python
from typing import List, Optional
from core.contracts import ExampleContract
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import ExampleDB

class ExampleRepositoryImpl(BaseRepository):
    """示例仓储实现"""
    
    def save(self, entity: ExampleContract) -> ExampleContract:
        """保存实体"""
        existing = self.db.query(ExampleDB).filter_by(id=entity.id).first()
        if existing:
            # 更新现有实体
            existing.name = entity.name
            db_entity = existing
        else:
            # 创建新实体
            db_entity = ExampleDB(
                id=entity.id,
                name=entity.name,
                metadata=entity.metadata
            )
            self.db.add(db_entity)
        self.db.flush()
        return self._to_domain(db_entity)
    
    def get(self, id: str) -> Optional[ExampleContract]:
        """获取实体"""
        db_entity = self.db.query(ExampleDB).filter_by(id=id).first()
        if not db_entity:
            return None
        return self._to_domain(db_entity)
    
    def list(self, limit: int = 100, offset: int = 0) -> List[ExampleContract]:
        """列出实体"""
        db_entities = self.db.query(ExampleDB).limit(limit).offset(offset).all()
        return [self._to_domain(e) for e in db_entities]
    
    def delete(self, id: str) -> bool:
        """删除实体"""
        db_entity = self.db.query(ExampleDB).filter_by(id=id).first()
        if not db_entity:
            return False
        self.db.delete(db_entity)
        self.db.flush()
        return True
    
    def _to_domain(self, db_entity: ExampleDB) -> ExampleContract:
        """转换为领域模型"""
        return ExampleContract(
            id=db_entity.id,
            name=db_entity.name,
            metadata=db_entity.metadata,
            created_at=db_entity.created_at
        )
```

---

## Alembic 迁移

### 迁移文件

迁移文件位于 `storage/migrations/versions/`：

| 版本 | 文件 | 说明 |
|------|------|------|
| 001 | 001_initial_schema.py | 初始 schema |
| 002 | 002_add_asset_snapshot.py | 添加资产快照表 |
| 003 | 003_temporal_industry_graph.py | 添加时间化产业链表 |
| 004 | 004_signal_tables.py | 添加信号相关表 |
| 005 | 005_timing_tables.py | 添加择时相关表 |
| 006 | 006_memory_learning_tables.py | 添加记忆学习表 |
| 007 | 007_add_stock_price_table.py | 添加股票价格表 |
| 008 | 008_add_event_type_column.py | 添加事件类型字段 |

### 常用命令

```bash
# 进入迁移目录
cd storage/migrations

# 创建新迁移
alembic revision -m "description of change" --autogenerate

# 升级到最新版本
alembic upgrade head

# 升级到特定版本
alembic upgrade <revision_id>

# 降级到上一版本
alembic downgrade -1

# 降级到特定版本
alembic downgrade <revision_id>

# 查看当前版本
alembic current

# 查看迁移历史
alembic history --verbose
```

---

## 初始化脚本

### 数据库初始化

项目提供以下脚本在 `scripts/` 目录：

| 脚本 | 说明 |
|------|------|
| bootstrap_db.py | 数据库初始化 |
| backup_db.py | 数据库备份 |
| restore_db.py | 数据库恢复 |
| import_real_data.py | 导入真实数据 |
| minimal_reingest_bootstrap.py | 最小重摄入引导 |
| rebuild_derived_state.py | 重建派生状态 |

---

## 附录

### JSONB 字段规范

所有 JSONB 字段遵循以下规范：

1. **存储格式**: 标准 JSON，日期使用 ISO 8601 字符串
2. **空值**: 使用默认的空结构 ({} 或 []) 而非 NULL
3. **查询**: 使用 PostgreSQL JSONB 操作符 (@>, ?, 等)

### 向量嵌入规范

- **维度**: 1536 (OpenAI text-embedding-ada-002 兼容)
- **存储格式**: PostgreSQL vector 类型
- **索引**: HNSW 索引，使用 cosine 距离度量
