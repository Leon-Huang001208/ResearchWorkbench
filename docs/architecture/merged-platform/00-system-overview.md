# 00 系统总览

## 职责

合并平台把 AlphaFoundry 的模块化单体、FastAPI、Research Run、结构化资产事实和 PostgreSQL + pgvector 作为主干，只迁入 LSH 中有来源、有时间语义、可确定性校验的数据集与受限研究运行时能力。FastAPI 是唯一业务 API，PostgreSQL 是唯一权威存储；DSH 仅以可选侧车实现 `RuntimeProvider`。

四个产品模块的职责如下：

| 模块 | 职责 | 不负责 |
|---|---|---|
| FinGPT / Claw | 单 Agent 研究、团队研究、Workspace、Skill、Run 与 Note | 生成或改写事实、策略评分、订单执行 |
| 市场首页 | facts-only 市场态势、透明主线、历史快照和钻取 | 自动 AI 摘要、投资结论 |
| Research Pack | 主题数据声明、统一观测、产业链/KPI/事件/资产暴露投影 | 自建数据库、直接联网插件、主题评分 |
| 资产观察 | stock/index/etf/active_fund 详情、同类比较、Watchlist、Alert | 复制资产主数据、交易或组合执行 |

## 数据归属

- 事实层：现有股票、指数、ETF、基金、Evidence 与 Connector 数据，以及新增 `asset_registry`、`theme_observation`、`domain_event`、`market_home_snapshot`；`SourceRef` 是公共契约并复用现有来源能力，不单独建表。
- 研究层：现有 `research_run`、`research_task`、`research_artifact`、`research_claim`、`research_quality_gate`，以及新增 Workspace/Session/Message/Note、Runtime、Skill、Team、Schedule。
- 个人观察层：`watchlist`、`watchlist_item`、`alert_rule`、`alert_event`、`notification`。
- HTML、Word、SSE、浏览器缓存和系统通知只保存标识或渲染结果，不成为权威事实源。

## 禁止依赖

- DSH 不得使用数据库凭据、ORM、repository 或直连 PostgreSQL；只能调用白名单 FastAPI/MCP 工具。
- Tauri/浏览器不得绕过 FastAPI 读写数据库。
- 四个产品模块不得导入彼此的 repository，不得通过对方私有表耦合。
- Research Run、Claim、Note 不得反向写入事实表；首页和资产页面不得触发 AI 自动摘要。
- Pack 插件只允许 `normalize`、`validate`、`derive`，禁止网络、数据库、Shell、文件任意写和外部 MCP URL。
- 不新增第二套 Flask API、SQLite 业务库、资产主表、Research Run 或调度权威状态。

## 公共 API 与类型

所有外部接口位于 `/api`：

- `/api/market-home/*`：live、snapshot、events、drill-down。
- `/api/themes/*`：catalog、snapshot、kpis、value-chain、events、assets、health。
- `/api/asset-observation/*`：assets、watchlists、alert-rules、alert-events、notifications。
- `/api/research-workspaces/*`、`/api/research-sessions/*`、现有 `/api/research-runs/*`。
- `/api/runtime-providers/*`、`/api/research-skills/*`、`/api/agent-teams/*`、`/api/agent-schedules/*`。

共享类型为 `AssetRef`、`AssetIdentifier`、`SourceRef`、`ObservationEnvelope`、`FreshnessStatus`、`DomainEvent`、`ScheduledJob`。所有事实响应必须完整携带 `as_of`、`observed_at`、`available_at`、`source_refs`、`freshness_status`、`quality_flags`；异步创建接口支持 `Idempotency-Key`，冲突键返回现有资源而不是重复创建。

## 主流程

1. Connector/迁移器采集来源，标准化为带来源、观测时间、可用时间、单位和哈希的事实。
2. Repository 将事实写入 PostgreSQL；服务按模块组合只读投影。
3. FastAPI 向 Web/Tauri 返回快照，并通过 SSE 只发送小型失效事件。
4. 用户从主题/资产/首页显式发起研究请求，Research Run 只读取事实。
5. Runtime Router 选择本地 LangGraph 或 DSH；DSH 经白名单工具回调 FastAPI。
6. 完成 Run 自动归档，用户可把选中的 Claim/段落置顶为版本化 Note。

后台任务只由进程级 `DurableSchedulerRuntime` 消费。默认单例创建与 `start()` 均有进程内锁，启动线程前注册 Agent Schedule、每日市场收盘快照和资产提醒三类 handler/materializer；每个领域回调自行创建数据库 Session，并在成功时提交、失败时回滚、最终关闭。失败任务保留同一 job/idempotency key、attempt 与 error，以 5 秒起始的确定性指数退避重回 idle，三次后进入 terminal failed。市场任务只在权威 Cjpy A 股日历明确返回交易日时固定于 Asia/Shanghai 15:05；日历缺失或失败时 fail closed。资产提醒按 UTC 分钟桶为每个 active profile 幂等入队，并用全局 due backlog 对 runtime 每分钟批处理容量做门禁和结构化健康记录。领域运行时不得再创建平行调度线程。

## 状态与失败

系统健康以模块独立状态表达：`ready`、`degraded`、`setup_required`、`unavailable`。数据库或 pgvector 未就绪时 API 使用既有 `setup_required` 语义；DSH 不可用不影响 facts-only 页面。`FreshnessStatus` 固定为 `fresh|stale|unavailable|quarantined`；口径冲突进入 `quality_flags` 或校验结果，不替代 freshness。研究、Pack、Alert 和迁移使用各自的显式状态机，不共享模糊的 `success` 布尔值。

单区块数据源失败只降级该区块；DSH/模型错误只失败或阻断 Run；通知权限被拒不影响站内通知；迁移校验失败进入 quarantine/rejected，不覆盖目标事实。所有内部异常记录详细日志，对客户端返回稳定错误码和安全摘要。

## 可观测性

- 统一追踪：`request_id` 从 Web/Tauri/DSH 贯穿 FastAPI、服务、repository 和外部源。
- 关键指标：API p50/p95、数据库就绪、各 section freshness、SSE 延迟、Run 吞吐/阻断/回退、Pack 数据隔离、Alert 触发/去重、旧 API 调用量。
- 审计：写操作记录 actor、scope、幂等键和 before/after 摘要；禁止记录密钥、完整 Prompt、附件正文和系统通知全文。
- 日志：沿用 `core.observability` 和 `logs/`，DSH 侧车只回传受限工具摘要与 Runtime 状态。

## 测试与验收

- 架构契约测试断言唯一 FastAPI、唯一 PostgreSQL、DSH 无数据库依赖和模块禁止依赖。
- 迁移测试断言 20 张新表及 015→018 单线图，不创建重复资产/Run 表。
- API 测试覆盖局部降级、幂等冲突、SSE 小载荷和错误码。
- 端到端测试覆盖“事实 → 页面 → 研究 → 自动归档 → 置顶 Note”，并断言研究结果没有写回事实。
- 桌面交付必须跑原生 macOS/Windows sidecar、Tauri、PostgreSQL ready/setup-required CI；真实 Windows 安装烟测是发布门禁。
