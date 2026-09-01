# 05 资产观察、列表与提醒

## 职责

资产观察为 stock、index、etf、active_fund 提供统一身份、详情快照、同类比较、多 Watchlist 和规则提醒。它复用现有结构化资产事实，只拥有个人观察状态；不复制行情/净值/指数/基金主数据，不执行交易。

## 数据归属

- `asset_registry` / `asset_identifier`：跨来源 canonical identity 与代码有效期。
- 既有 stock/index/etf/fund 表：资产事实、行情、净值、持仓与指数结构。
- `watchlist` / `watchlist_item`：本地 profile 下的列表、条目、顺序和注释；Item 只引用 canonical asset ID。
- `alert_rule`：metric、operator、threshold、unit、freshness、cooldown 与 enable 状态。
- `alert_event`：触发边沿、观测引用、去重键、确认与解决；数据库 partial unique index 保证每条 Rule 最多一个 `open|acknowledged` 事件，已 resolved 事件不占用唯一位。
- `notification`：站内通知权威记录；桌面系统通知是其投递投影。

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
| `/api/asset-observation/alert-events` | 查询、acknowledge、resolve |
| `GET /api/asset-observation/notifications` | 站内未读/历史与投递状态 |

公共类型包括 `AssetSnapshotEnvelope`、`PeerSet`、`Watchlist`、`WatchlistItem`、`AlertRule`、`AlertEvaluation`、`AlertEvent`、`Notification`。Alert 固定支持价格/净值、涨跌、资金、估值、持仓、公告和主题事件七类规则；操作符限定 `gt|gte|lt|lte|crosses_above|crosses_below|pct_change`，数值和阈值必须单位兼容。

## 主流程

1. 服务解析 `AssetRef` 和当前有效 identifier；内部保留 scheme/value/market，按显式 scheme 优先级逐个验证现有事实表，命中后组合详情，对外 identifiers 仍为字符串列表。
2. 默认 peer：stock 按申万细分行业，index 按类别，ETF 按跟踪指数/主题，active_fund 按基金分类/基准；响应返回规则、样本和 as_of。
3. 用户以 canonical asset ID 加入一个或多个 Watchlist。
4. 调度器或事实事件触发 Alert Evaluation；同一数据库事务先以 `SELECT ... FOR UPDATE` 锁定 Rule 并重读 state。仅 fresh 且单位一致的 false→true 可生成 `alert_event` 和 `notification`；写冲突在 savepoint 中恢复为 deduplicated，不会遗留半写 notification。持续为 true 始终去重，不因 cooldown 到期重复提醒；转为 false 时当前事件自动 resolved，并重置边沿。下一次 false→true 若仍处于上次触发的 cooldown 窗口则返回 deduplicated，窗口结束后才触发新事件。
5. FastAPI/SSE 告知站内客户端重新拉取；acknowledge/resolved 持久化。
6. Task 3 中前端仅从 `GET /api/asset-observation/notifications?profile_id=local&status=pending` 消费已持久化 notification，并经 `window.__TAURI__.notification` 请求权限与发送 API 返回的 title/body；投递、拒绝和失败分别 PATCH 状态，Web 非 Tauri 环境 no-op，任何结果都保留站内记录。

## 状态与失败

- Alert Rule：`draft → active → paused → retired`。
- Evaluation：`not_matched|triggered|deduplicated|skipped_data_stale|skipped_data_unavailable|failed_unit_mismatch`。
- Alert Event：`open → acknowledged → resolved`；每个 true 周期最多触发一次，持续真值始终去重；条件回到 false 时自动 resolved，下一次 false→true 仍受 cooldown 约束。
- Notification：`pending → in_app_delivered`，获得桌面能力时可进入 `desktop_delivered|desktop_permission_denied|desktop_failed`；后三者不回滚站内记录。
- 写冲突返回 409，非法 operator/unit 返回 422，不存在的资产/列表返回 404。

## 可观测性

日志记录 `asset_id`、`asset_type`、`watchlist_id`、`rule_id`、`observation_id`、`freshness_status`、`evaluation_status`、`event_id`、`notification_channel`，不记录敏感正文。指标覆盖四类资产覆盖、peer 空样本、Alert 跳过/触发/去重、ack/resolved 时延、站内投递和桌面权限/桥接失败。

## 测试与验收

- 四类资产详情与 peer-set metadata 测试；代码标识更新后 Watchlist Item identity 不变。
- 多列表、排序、重复添加幂等和 workspace/profile 隔离测试。
- stale/unavailable 不触发、单位不兼容拒绝、false→true 单次触发、回落后再触发测试。
- API 测试覆盖 400/404/409/422、acknowledge/resolved 与站内通知持久化。
- 桌面通知在 Task 3 使用已获授权的官方插件实施；Node 行为测试覆盖 granted/denied/failed、仅消费 API 持久化记录以及拒绝后站内记录仍可查询。仍必须通过原生 macOS/Windows CI，并在发布前完成真实 Windows 安装级烟测。
- 当前验收结论为“站内通知、最小权限前端桥和 macOS 本地编译已实现”；Windows installed-app 通知与系统投递仍须原生 CI 和真实安装级烟测。
