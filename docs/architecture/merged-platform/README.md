# AlphaFoundry × LSH 合并平台 V1 架构包

> 历史架构基线：不代表当前 Research Web 的运行架构。当前唯一主入口为
> [Research Web 架构](../research-web/README.md)。本目录保留用于历史追溯，不作为恢复旧业务模块的实施要求。

本目录是合并平台的实现基线，不表示所有接口和表已经落地。目标态只有一个 FastAPI 业务内核、一个 PostgreSQL + pgvector 权威存储和四个产品模块；DSH 是可选 `RuntimeProvider` 侧车，不拥有业务数据，也不能直连数据库。

## 固定边界

- 架构形态：模块化单体 + 可选 DSH 侧车，保留现有 Tauri + Python sidecar 交付形态。
- 六个实施域：市场首页、Research Pack、资产观察、FinGPT、Claw、平台能力与调度内核。FinGPT 与 Claw 分开呈现，但共享研究内核。
- 三层隔离：事实层只保存可追溯观察；研究层保存运行、Claim、产物、对话和 Note；个人观察层保存 Watchlist、规则、提醒和通知。
- 单一入口：Web、Tauri 和 DSH 都只调用 FastAPI；跨模块访问必须经过共享契约与应用服务。
- 单一事实源：PostgreSQL + pgvector；HTML、Markdown、SSE、缓存和桌面通知都只是投影。
- 明确排除：不把 LSH 的策略评分、订单、模拟交易、`score_hint`、`driver-summary` 迁入新事实模型；策略、交易和基金审批能力仅冻结为只读归档，不作为重复能力删除。

## 文档导航

完整的功能/API/服务/数据/状态追踪见 [detailed/README.md](detailed/README.md)，可交互架构入口为 `outputs/merged-platform-blueprint/index.html`。可点击产品效果入口为 `outputs/merged-platform-product-prototype/index.html`，页面与接口追踪见 [product/prototype-map.md](product/prototype-map.md)，视觉约束见 [product/brand-spec.md](product/brand-spec.md)。

| 文档 | 实现问题 | 配套图 |
|---|---|---|
| [00-system-overview.md](00-system-overview.md) | 部署、模块边界与全局失败语义 | `01-system-deployment.html`、`02-module-dependencies.html` |
| [01-shared-contracts.md](01-shared-contracts.md) | 共享类型、20 张新表与三层隔离 | `03-core-er.html` |
| [02-fingpt-claw.md](02-fingpt-claw.md) | Workspace、Run、Runtime、Skill、Team | `04-research-request.html`、`05-research-run-lifecycle.html` |
| [03-market-home.md](03-market-home.md) | facts-only 首页、透明主线与 SLA | `06-market-home-dataflow.html` |
| [04-theme-research-packs.md](04-theme-research-packs.md) | 四个 Pack、统一 Observation 与迁移 | `07-pack-lifecycle.html` |
| [05-asset-observation.md](05-asset-observation.md) | 四类资产、Watchlist、Alert、通知 | `08-asset-alert-lifecycle.html` |
| [06-migration-rollout.md](06-migration-rollout.md) | 四段迁移、等价门禁与只读归档 | `09-migration-gate.html` |

HTML 位于仓库根目录 `outputs/merged-platform-architecture/`；可编辑 Archify JSON 位于 `diagrams/`。

## 模块依赖顺序

1. 共享事实核：`AssetRef`、`AssetIdentifier`、`SourceRef`、`ObservationEnvelope`、`DomainEvent`、`ScheduledJob`。
2. 存储迁移：`015` 事实核 → `016` 主题/首页 → `017` 研究运行时 → `018` 资产观察。
3. 资产观察与市场首页：只读现有结构化资产事实并生成自己的投影。
4. Research Pack：把 LSH 可迁移数据标准化为 `theme_observation`，不复制资产事实。
5. FinGPT / Claw：消费前三者的只读 API 与 Research Run，不写事实接口。
6. 兼容适配：旧 LSH 调用经过 capability gate；等价、迁移、回归和零调用证据齐全后才删除。

允许的依赖方向是 `界面/Runtime → FastAPI route → application service → repository → PostgreSQL`。四个产品模块不得直接导入彼此的 repository；DSH、浏览器、Tauri 前端和 Skill 插件不得直连数据库。

## 实现导航

| 阶段 | 主要落点 | 验收重点 |
|---|---|---|
| 共享核 | `core/contracts/`、`data_layer/repositories/models.py`、`storage/migrations/versions/015..018` | 20 张表、唯一键/外键/时间索引、SQLite 测试兼容 |
| 纵切 API | `services/`、`data_layer/repositories/`、`app/api/routes/` | 薄 route、结构化日志、400/404/409 失败映射 |
| Pack | `theme_packs/`、`scripts/migrate_lsh_theme_data.py` | 默认 dry-run、哈希幂等、隔离坏数据 |
| Runtime | Research Workspace/Runtime/Team/Scheduler 服务 | 单一加锁持久 worker；Agent、权威交易日历确认后的 15:05 市场快照、带 backlog 容量门禁的分钟级资产提醒共享租约/围栏 |
| 桌面通知 | Tauri 官方通知插件桥接 | Task 3 添加已授权的官方插件，再跑原生 macOS/Windows CI 与真实 Windows 安装烟测 |
| 删除门禁 | `legacy_capability_gate` 与 capability map | parity、数据迁移、零调用、归档路径、稳定版本观察期 |

## 全局状态与失败契约

- 事实不可用返回 `unavailable`，过期返回 `stale`；两者均不得被包装成 `fresh`。
- 所有事实响应完整包含 `as_of`、`observed_at`、`available_at`、`source_refs`、`freshness_status`、`quality_flags`；模块局部失败额外返回 `error_code`、`retryable`，不把整页变成 500。
- FinGPT 的 DSH 不可用时可回退 LangGraph；Claw 缺少 `agent_team` 能力必须返回 `blocked_runtime`，不得语义回退。
- Research Run 完成后自动归档到 Workspace；用户只能把选中的 Claim 或段落置顶为版本化 Note，不能把整段模型文本提升为事实。
- 告警只在 fresh 数据发生 false→true 边沿时触发；stale/unavailable 跳过，重复真值去重。
- 旧能力删除必须通过全部门禁；失败时继续走旧适配器并记录调用量。

## 可观测性与总体验收

统一日志字段至少包含 `request_id`、`trace_id`、`workspace_id`/`run_id`、`module`、`status`、`latency_ms`，数据路径再包含 `source_ref`、`observed_at`、`freshness_status`。指标覆盖请求耗时、数据新鲜度、降级区块、Run 状态、Runtime 回退、工具拒绝、调度租约、Pack 隔离、Alert 去重和旧 API 调用量。

总体验收要求：契约与迁移单测；PostgreSQL 的迁移、幂等摄入、快照、任务租约、项目隔离、通知持久化；API/SSE 的分页、断线重连、取消、恢复、Provider 故障和部分降级；首页、资产观察、主题研究、FinGPT 和 Claw 五条浏览器旅程；DSH 无数据库权限、未授权 MCP 拒绝和项目记忆隔离；旧能力 parity/零调用；38 张 Archify 图 showcase 与四视口视觉检查。性能门槛为缓存首页 P95≤500ms、资产/主题 P95≤1s、SSE 首状态≤1s、提醒评估≤60s。桌面相关功能还需原生 macOS/Windows CI；发布前在真实 Windows 环境完成安装级烟测。本地 macOS 或文档验证不能替代这些平台证据。
