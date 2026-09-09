# 03 全市场首页

## 职责

市场首页只展示可追溯事实、透明计算和历史快照，回答“市场发生了什么、数据截至何时、主线如何计算”。它不生成 AI 自动摘要、投资建议或隐藏权重评分。任一区块失败只降级该区块。

## 数据归属

- 页面固定五个 section：全球背景、A 股状态、市场主线、重要事件、资产异动；不得以其它区块替代或省略。
- 输入归现有行情、指数结构、事件和 Connector 事实表所有。
- 交易状态固定为 `pre_open|open|lunch_break|closed|non_trading_day`。
- `market_home_snapshot` 只拥有按 `trading_day + snapshot_kind + section_key + formula_version` 固化的页面快照与输入事实引用；盘中只读取 live 投影，盘后只生成不可变 close 快照。
- Live 读模型可缓存，但缓存不是权威历史；历史查询必须读取 snapshot，禁止用当前 live 数据重算。
- 主线组件保存 `return_percentile`、`turnover_change_percentile`、`breadth_percentile`、`event_density_percentile`、样本量和口径版本。

## 禁止依赖

- 不调用 LLM、Research Runtime、Skill 或 Agent 生成首页内容。
- 不读取 Research Run、Claim、Note、Watchlist 或 Alert 来改变市场事实排序。
- 不把 ETF 价格混称指数点位，不把缺失值当 0，不在来源失败时显示上一帧为 fresh。
- 前端不拼接隐藏公式，不从多个旧 API 自行重建主线。
- SSE 不传完整 section payload，只发送失效引用。

## 公共 API 与类型

| API | 契约 |
|---|---|
| `GET /api/market-home/live` | 分 section 返回 facts、freshness、as_of、`age_seconds`、source refs 和 degradation |
| `GET /api/market-home/snapshots/{trading_day}` | 只读对应交易日不可变 close 快照 |
| `GET /api/market-home/drill-down/{section_key}` | 返回组成事实、样本、单位和来源 |
| `GET /api/market-home/events` | SSE：只含 `event_id`、`section_key`、`as_of`；`Last-Event-ID` 从持久 outbox 恢复 |

公共类型为 `MarketHomeEnvelope`、`MarketHomeSection`、`MainlineRank`、`MainlineComponents`、`MarketHomeSnapshot` 和 `SectionDegradation`。`MarketHomeEnvelope` 校验 section key 集合严格等于五个枚举全集，每项恰好一次；所有 section 都有独立 `freshness_status`，整页不使用单一 fresh 标志。

## 主流程

1. Repository 按请求 `as_of` 查询事实。A 股状态和异动为每个活跃标的选取 `<= as_of` 的最新行情，返回覆盖率与最小/最大水位，不要求所有标的时间戳完全相同。
2. 主线质量门只接收同一主题、同一 `as_of` 水位、单位匹配且 `available_at <= as_of` 的四项 fresh 事实；`stale|unavailable|quarantined`、非空 quality flags、未来可用时间和单位冲突均被排除并进入 `missing_components`。
3. Service 对通过质量门的候选板块计算 percentile；`mainline-v1 = return×0.35 + turnover_change×0.30 + breadth×0.25 + event_density×0.10`。
4. 返回每项 component、sample_size、formula_version 和输入事实时间，不只返回总分；任何候选缺项或冲突都将区块标为 `partial`，不得静默删除失败原因。
5. API 生产启动时把稳定的 market materializer/handler 注册到进程级唯一 `DurableSchedulerRuntime`，不启动市场专用线程。Materializer 使用 Cjpy 交易日序列对当天做精确权威查询；只有明确返回交易日才幂等确保一条 Asia/Shanghai 15:05 的 `market_home.close_snapshot` 持久任务，日历未配置、异常或返回非交易日一律 fail closed，不用 weekday 猜测。handler 使用独立 Session 在一个事务内生成五条不可变 section 快照，成功提交、失败回滚并关闭 Session。同一交易日重复注册返回既有任务，快照并发唯一冲突后重读完整既有五条记录；失败 job 按共享退避策略重试且快照唯一键使重复执行安全。
6. 权威行情和 `DocumentEvent` 写入方在提交前、同一数据库事务中调用 `record_market_home_fact_update`，以来源批次幂等键写入 `market_home.section_invalidated` outbox；异常向上抛出并使整笔事实事务回滚。Theme Pack 写入方复用同一 helper：`market_home_global` 映射 `global_context`，`market_home_mainline` 及其四项组件映射 `market_mainlines`，未被首页消费的 observation 不发送首页失效事件。客户端收到 SSE 引用后重新获取受影响区块。
7. 历史日期始终读取存档，不访问 live provider。

重要事件区块不得返回 `DocumentEvent` 的模型 enrichment 字段（例如摘要、影响方向和置信度）。它只公开原始 `DocumentV1` 的标题、来源名、来源 URL、内容哈希、文档时间和文档锚点。明确 unavailable 的区块及其 close snapshot 允许 `source_refs=[]`，不得伪造 OFFICIAL 来源或假哈希；任何 ready/stale/partial 事实仍必须有真实来源。

## 状态与失败

Section 状态为 `ready|stale|unavailable|partial`。来源超时、空样本、单位/口径冲突分别使用稳定错误码；`partial` 必须列出缺失 component，且不生成不可解释总分。单区块异常被捕获并结构化记录，其余区块仍返回 200；只有请求本身非法返回 4xx，核心存储不可用才沿用全局 setup/health 语义。

SLA 以数据可用时间为起点：行情到达 30 秒内可见；市场聚合 60 秒内可见；事件到达系统后 15 秒内可见。SSE 仍只发送区块失效事件，客户端收到后重新读取聚合 API。每个事实 section 通过 `age_seconds` 报告 `as_of` 到响应时刻的实际年龄；未达 SLA 时标记 stale/unavailable，不静默使用旧值。

## 可观测性

日志记录 `snapshot_kind`、`section_key`、`trading_day`、`formula_version`、`sample_size`、`source_count`、`freshness_status` 和 `latency_ms`。指标覆盖 section p95、SLA breach、空样本、partial/unavailable、snapshot 幂等命中、SSE 延迟与历史误触 live provider（应为 0）。

## 测试与验收

- 公式测试固定四项权重并断言 component/sample_size/version 全部返回。
- Envelope 测试覆盖五个 section 完整集合、重复 key 和遗漏 key。
- 历史测试使用 spy 断言 snapshot 查询从不调用 live provider。
- 单区块故障注入确认整页非 500、错误码与 freshness 准确。
- SSE 测试确认小载荷、有序重连和客户端重新读取聚合 API。
- 权威行情与 `DocumentEvent` writer 测试确认事实和幂等 outbox 在一次提交中完成，并通过真实 HTTP `Last-Event-ID` 只恢复游标后的事件。
- 调度集成测试确认 API 在唯一 runtime 启动前注册 handler/materializer、持久化 15:05 收盘任务、通用 Coordinator 消费任务并生成五区 close snapshot；关闭时只停止这一条共享消费线程。
- SLA 测试分别覆盖 30s 行情到达、60s 市场聚合、15s 事件到达；过期值不可标 fresh。
- 静态前端契约断言首页无 AI 自动摘要入口，钻取展示来源、时间、单位与公式。
