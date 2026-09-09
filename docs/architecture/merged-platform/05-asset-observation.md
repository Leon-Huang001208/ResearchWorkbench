# 05 资产观察、列表与提醒

## 职责

资产观察为 stock、index、etf、active_fund 提供统一身份、详情快照、同类比较、多 Watchlist 和规则提醒。它复用现有结构化资产事实，只拥有个人观察状态；不复制行情/净值/指数/基金主数据，不执行交易。

## 数据归属

- `asset_registry` / `asset_identifier`：跨来源 canonical identity 与代码有效期。
- 既有 stock/index/etf/fund 表：资产事实、行情、净值、持仓与指数结构。
- `watchlist` / `watchlist_item`：本地 profile 下的列表、条目、顺序和注释；Item 只引用 canonical asset ID。
- `alert_rule`：metric、operator、threshold、unit、freshness、cooldown 与 enable 状态。
- `alert_event`：触发边沿、观测引用、去重键、确认与解决；数据库 partial unique index 保证每条 Rule 最多一个 `open|acknowledged` 事件，已 resolved 事件不占用唯一位。
- `notification`：站内通知权威记录；`delivery_claim_token`、`delivery_claimed_at`、`delivery_attempt` 持久化桌面投递租约，桌面系统通知是其投递投影。

## 禁止依赖

- Watchlist 不以 symbol 作外键，不因代码变更创建重复资产。
- Alert 不读取 Research Claim/Note、模型文本或策略评分作为事实条件。
- stale、unavailable、quarantined 数据不得触发；冲突 `quality_flags` 必须阻断评估；0 不得被当作缺失。
- 通知不得包含密钥、完整研究文本、附件正文或未脱敏来源 payload。
- Task 3 已添加官方 `tauri-plugin-notification` 与三项最小 capability；独立 `notification-remote` 只把这三项通知权限授予 packaged bootstrap 使用的 `http://127.0.0.1:8765/*`，default capability 无 remote scope，dialog/process/shell/sidecar 保持本地权限。不允许 localhost、其他 host 或通配端口。站内记录仍是权威。原生 Windows CI 与真实 Windows 安装级烟测完成前不得宣称 Windows 系统通知已验证。
- 权限拒绝、桌面桥接失败不得丢失站内通知或改变 Alert 状态。

## 公共 API 与类型

| API | 契约 |
|---|---|
| `GET /api/asset-observation/assets/{asset_id}` | 统一详情、事实引用、新鲜度与 peer metadata |
| `GET /api/asset-observation/assets/{asset_id}/peers` | 默认/自定义同类组与规则说明 |
| `/api/asset-observation/watchlists` | 多列表 CRUD、排序、Item 幂等 |
| `/api/asset-observation/alert-rules` | 规则 CRUD、启停与校验 |
| `POST /api/asset-observation/alert-rules/evaluate-due` | 仅从服务端权威事实评估当前 profile 的 active rules；请求不接受 Observation/value/unit payload，返回批次计数 |
| `/api/asset-observation/alert-events` | 查询、acknowledge、resolve |
| `GET /api/asset-observation/notifications` | 站内未读/历史与投递状态 |

公共类型包括 `AssetSnapshotEnvelope`、`PeerSet`、`Watchlist`、`WatchlistItem`、`AlertRule`、`AlertEvaluation`、`AlertEvent`、`Notification`。Alert 固定支持价格/净值、涨跌、资金、估值、持仓、公告和主题事件七类规则；操作符限定 `gt|gte|lt|lte|crosses_above|crosses_below|pct_change`，数值和阈值必须单位兼容。

## 主流程

1. 服务解析 `AssetRef` 和当前有效 identifier；内部保留 scheme/value/market，按显式 scheme 优先级逐个验证现有事实表，命中后组合详情，对外 identifiers 仍为字符串列表。active_fund NAV 同时满足 `trading_day <= as_of.date()` 与 `updated_at <= as_of`，未来观测或未来可用事实不进入投影。
2. 默认 peer：stock 按申万细分行业，index 按类别，ETF 按跟踪指数/主题，active_fund 按基金分类/基准；响应返回规则、样本和 as_of。
3. 用户以 canonical asset ID 加入一个或多个 Watchlist。
4. `evaluate_due_alerts(profile_id, evaluated_at)` 是可执行生产入口：active 列表只提供候选 Rule ID；每条规则进入独立 savepoint 后以 `SELECT ... FOR UPDATE` 锁定并完整刷新权威 Rule，再校验 `status=active` 和 `state.profile_id`。不再符合条件时返回 `skipped_rule_not_eligible`，不生成 Event/Notification；符合条件时才按锁内 asset/metric/operator/threshold/unit/state 从现有资产事实投影构造 ObservationEnvelope。缺 metric/unit 或未来事实一律 unavailable/skip，不接受调用方自带 value/unit。单条失败记录结构化日志但不中断批次。
5. API 在进程级唯一 `DurableSchedulerRuntime` 启动前注册 `asset_alert.evaluate`。Materializer 查询所有拥有 active Rule 的 profile，以 UTC 分钟桶为每个 profile 幂等持久化一条任务；handler 从任务中读取受控的 `profile_id/evaluated_at`，使用独立 Session 调用上述入口，并原子提交 Event、Notification 和 Rule state。任何回调异常均回滚并关闭 Session。Alert handler 有可配置的 `max_execution_seconds`（默认 1 秒）；runtime 用 poll cadence、batch limit 和该串行执行上界共同计算 60 秒保守容量。materializer 统计该分钟截止前所有 job type 的 due backlog，只有 backlog 不超过容量才提交；实际 handler 超时会锁存 `degraded_execution_budget`，后续物化以 `blocked_execution_budget` fail closed，直至运行时重启/人工恢复。失败提醒保留同一 job/idempotency key 并退避重试；stale/unavailable/quarantined 的 skip 语义不因调度接线改变。
6. Alert Evaluation 仅使用完整锁内 Rule 和 state。仅 fresh 且单位一致的 false→true 可生成 `alert_event` 和 `notification`；写冲突在 savepoint 中恢复为 deduplicated，不会遗留半写 notification。持续为 true 始终去重，不因 cooldown 到期重复提醒；转为 false 时当前事件自动 resolved，并重置边沿。下一次 false→true 若仍处于上次触发的 cooldown 窗口则返回 deduplicated，窗口结束后才触发新事件。
7. acknowledge/resolved 持久化；Task 4/DomainEvent SSE 后续可触发即时 notification 失效。
8. 首版桌面前端以不超过 60 秒的 durable polling 从 `GET /api/asset-observation/notifications?profile_id=local&status=pending` 消费已持久化记录。权限批准后，服务端以不可预测 token 原子抢占 `pending → desktop_delivering`，持久化 claimed_at 并递增 attempt；最终 `desktop_delivering → desktop_delivered|desktop_failed` 必须携带同一 token。120 秒未完成的 claim 会在下一次 pending GET 前原子回收，新 attempt 获得新 token，旧 token 永远返回 409。轮询 single-flight 且只安装一次，权限拒绝/检查失败同样使用 expected status 条件更新；Web 非 Tauri 环境 no-op，任何结果都保留站内记录。原生通知是 at-least-once：系统已发送但最终 ACK 丢失时，租约回收后可能重复显示，不承诺 exactly-once。

## 状态与失败

- Alert Rule：`draft → active → paused → retired`。
- Evaluation：`not_matched|triggered|deduplicated|skipped_data_stale|skipped_data_unavailable|skipped_rule_not_eligible|failed_unit_mismatch`。
- Alert Event：`open → acknowledged → resolved`；每个 true 周期最多触发一次，持续真值始终去重；条件回到 false 时自动 resolved，下一次 false→true 仍受 cooldown 约束。
- Notification：桌面路径为 `pending → desktop_delivering → desktop_delivered|desktop_failed`；权限拒绝/检查失败可由 `pending` 条件进入 `desktop_permission_denied|desktop_failed`。抢占生成 120 秒租约，超时后回到 pending；完成必须匹配当前 claim token，旧 token 或条件冲突返回 409，不回滚或删除站内记录。
- 写冲突返回 409，非法 operator/unit 返回 422，不存在的资产/列表返回 404。

## 可观测性

日志记录 `asset_id`、`asset_type`、`watchlist_id`、`rule_id`、`observation_id`、`freshness_status`、`evaluation_status`、`event_id`、`notification_channel`，不记录敏感正文。指标覆盖四类资产覆盖、peer 空样本、Alert 跳过/触发/去重、ack/resolved 时延、站内投递和桌面权限/桥接失败。

## 测试与验收

- 四类资产详情与 peer-set metadata 测试；代码标识更新后 Watchlist Item identity 不变。
- 多列表、排序、重复添加幂等和 workspace/profile 隔离测试。
- stale/unavailable 不触发、单位不兼容拒绝、false→true 单次触发、回落后再触发测试；真实 SQLite 批次入口覆盖 trigger、stale/missing skip、单规则失败继续执行，以及候选列出后暂停的 Rule 不触发。PostgreSQL 方言测试确认锁语句包含 `FOR UPDATE`。
- API 测试覆盖 400/404/409/422、acknowledge/resolved 与站内通知持久化。
- 调度测试覆盖全部 active profile、同分钟重复物化、下一分钟新任务、handler 提交通知、失败回滚/关闭，以及市场与提醒由同一个 runtime tick 消费；耗时 fake 以 `poll=30s/batch=2/max_execution=50ms` 证明 3-profile backlog 在两个 tick 内完成，并以超预算 handler 验证 `degraded_execution_budget → blocked_execution_budget` fail-closed 门禁。
- 桌面通知在 Task 3 使用已获授权的官方插件实施；真实 SQLite 与 Node 行为测试覆盖 granted/denied/failed、并发 claim、崩溃后租约回收、新旧 token 隔离、仅消费 API 持久化记录以及拒绝后站内记录仍可查询。仍必须通过原生 macOS/Windows CI，并在发布前完成真实 Windows 安装级烟测。
- 当前验收结论为“站内通知、最小权限前端桥和 macOS 本地编译已实现”；Windows installed-app 通知与系统投递仍须原生 CI 和真实安装级烟测。
