# 01 共享契约与数据所有权

## 职责

共享核负责跨模块身份、来源、时间、新鲜度、事件和调度语义。它不承载产品页面逻辑，也不把研究结论混入事实。所有跨层数据交换使用 Pydantic v2 类型，持久化使用 SQLAlchemy 2 与 Alembic；PostgreSQL + pgvector 是生产权威存储，SQLite 仅用于兼容的单元测试。

## 数据归属

新增表固定为 20 张，主题六类读模型首版均为查询投影，不新增物化表：

| 迁移 | 分组 | 表 | 所有权与关键约束 |
|---|---|---|---|
| 015 | 共享事实核（5） | `asset_registry` | canonical asset ID；只映射现有 stock/index/etf/fund 事实，不复制行情或主数据 |
| 015 | 共享事实核 | `asset_identifier` | `(scheme, value, market, valid_from)` 唯一；代码变化保留有效期 |
| 015 | 共享事实核 | `theme_observation` | 唯一主题事实表；Observation envelope + typed payload |
| 015 | 共享事实核 | `scheduled_job` | owner、lease、idempotency、single-flight 与 coalesce 状态 |
| 015 | 共享事实核 | `domain_event` | PostgreSQL 持久事件权威记录；SystemEventBus 只做 SSE/进程内投递适配 |
| 016 | 主题/首页（2） | `theme_pack` | Pack manifest 版本、生命周期、校验哈希 |
| 016 | 主题/首页 | `market_home_snapshot` | 交易日/时点/section 快照；历史禁止由 live 重算 |
| 017 | 研究运行时（8） | `research_workspace` | 项目隔离、标题、归档状态 |
| 017 | 研究运行时 | `research_session` | 临时/项目会话，原子升级；可关联现有 Run |
| 017 | 研究运行时 | `research_message` | workspace-scoped 消息与安全内容引用 |
| 017 | 研究运行时 | `research_note` | Claim/段落引用、revision、pinned；旧 revision 不覆盖 |
| 017 | 研究运行时 | `runtime_provider` | LangGraph/DSH 能力、健康、配置引用，不保存密钥 |
| 017 | 研究运行时 | `skill_definition` | `SkillManifest` 的持久化表；声明式模板、allowed_tools、版本和状态 |
| 017 | 研究运行时 | `agent_team` | Supervisor、角色、预算、deadline 与并发上限 |
| 017 | 研究运行时 | `agent_schedule` | 团队/研究计划，委托 `scheduled_job` 获取租约 |
| 018 | 个人观察（5） | `watchlist` | 用户/本地 profile 下多列表与排序 |
| 018 | 个人观察 | `watchlist_item` | 只引用 `asset_registry.asset_id`；标识变化不丢失条目 |
| 018 | 个人观察 | `alert_rule` | 操作符、阈值、freshness 条件、启停状态 |
| 018 | 个人观察 | `alert_event` | false→true 边沿、去重键、ack/resolved 状态 |
| 018 | 个人观察 | `notification` | 站内通知权威记录、投递通道与权限/失败状态 |

复用现有 `research_run`、`research_task`、`research_artifact`、`research_claim`、`research_quality_gate`，以及现有股票、指数、ETF、基金、Evidence、Connector 和来源能力。`SourceRef` 是公共契约，不新增 `source_ref` 表。`domain_event` 是 PostgreSQL 持久权威记录；现有 SystemEventBus 仅作为 SSE/进程内投递适配。

## 禁止依赖

- 不在 JSON payload 中隐藏可索引的主键、来源、observed_at 或状态。
- `research_note` 只能引用现有 Run/Claim 或明确段落定位，不能复制成 `theme_observation`。
- `watchlist_item` 不保存 symbol 作为身份，只保存 canonical asset ID；symbol 是 `asset_identifier` 投影。
- `market_home_snapshot` 不成为资产行情真相；其 payload 必须保留所用事实 ID/版本。
- `theme_observation` 不接收策略分数、目标仓位、订单或 LSH 的 `score_hint`/`driver-summary`。
- 模块不得直接依赖其他模块表；跨模块读取通过 service/repository 定义的共享查询。

## 公共 API 与类型

`platform_shared.py` 的公共类型与不变量：

| 类型 | 必填语义 | 验证规则 |
|---|---|---|
| `AssetRef` | `asset_id`、`asset_type` | `asset_type` 仅 `stock|index|etf|active_fund` |
| `AssetIdentifier` | scheme/value/market/有效期 | 同一 scheme/value/market 的有效期不得重叠 |
| `SourceRef` | source_id、name、tier、content_hash/URL | 必须可追溯，敏感凭据不可进入模型 |
| `ObservationEnvelope` | subject_ref、metric_key、source_ref、observed_at、available_at、freshness | `available_at >= observed_at`；numeric value 必须带 unit |
| `FreshnessStatus` | fresh/stale/unavailable/quarantined | stale/unavailable/quarantined 不得伪装 fresh；冲突写入 quality_flags；缺失值与 0 分开 |
| `DomainEvent` | event_id、type、occurred_at、payload_ref | 先写 PostgreSQL `domain_event`，SSE 只传小型引用 |
| `ScheduledJob` | job_id、owner、idempotency_key、lease | 默认 single-flight；missed runs 合并 latest |

API 模型必须保持“缺失”“不适用”“来源失败”“0”四种语义可区分。金额、比例、点位、数量和价格不得省略单位；所有时间保存带时区值，交易日另有明确 date 字段。

## 主流程

1. 来源适配器生成 `SourceRef` 与 source hash。
2. normalizer 解析 canonical `AssetRef`、观测时间、可用时间、数值/单位和 freshness。
3. validator 拒绝时间逆序、单位缺失、未知资产类型和伪 fresh。
4. repository 在事务内 upsert 身份并插入不可混淆的事实/快照/个人状态。
5. 业务服务从事实 ID 组合 typed projection；API 返回来源与新鲜度。
6. DomainEvent 先持久化到 `domain_event`，SystemEventBus 再投递资源已变化的引用，消费者重新读取权威 API。

## 状态与失败

- Observation：`fresh → stale`；采集失败可为 `unavailable`；隔离数据为 `quarantined`；口径冲突写入 `quality_flags` 或校验结果。新来源验证通过后可生成新的 fresh 记录，旧记录不原地改写历史。
- ScheduledJob：`idle → leased → running → succeeded|failed`；租约过期可由新 owner 接管；重复 idempotency key 返回既有执行。
- 写入冲突使用 409；验证错误使用 422；引用不存在使用 404；数据库未就绪沿用 `setup_required` 健康契约。
- quarantine 保存文件哈希、行号、安全错误码和原始文件引用；不把未校验行塞进事实 payload。

## 可观测性

日志记录 `entity_type`、`entity_id`、`source_id`、`observed_at`、`freshness_status`、`migration_revision`、`idempotency_key_hash`。指标覆盖校验拒绝、单位缺失、身份冲突、stale age、租约争用、重复跳过和事件投递延迟。敏感值、完整消息/附件和运行时凭据不得进入日志。

## 测试与验收

- Pydantic 测试覆盖时间顺序、numeric unit、四类资产、缺失值、Skill 工具白名单、Agent 上限和 Alert 操作符。
- 迁移测试逐字断言 20 张表，revision 为 015→016→017→018，且不创建第二张 `research_run`、股票、指数、ETF 或基金事实表。
- Repository 测试覆盖唯一键、外键、时间索引、幂等、事务回滚及 SQLite 测试兼容。
- 架构测试扫描 DSH、前端和 Pack 插件，确认不存在 ORM/数据库直连或跨模块 repository 导入。
- 数据回放测试确认历史 snapshot/observation 不受 live 数据变化影响。
