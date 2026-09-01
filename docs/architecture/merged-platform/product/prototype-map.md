# 产品原型实施映射

可点击原型入口：`outputs/merged-platform-product-prototype/index.html`。它将 8 个产品页面、5 条完整旅程、功能编号、API 编号和详细架构图连接成同一条实施追踪链。

## 页面到实现契约

| 页面 | 产品职责 | 能力编号 | API 范围 | 详细架构 | 旅程 |
|---|---|---|---|---|---|
| `/market-home` | 全球背景、A 股状态、市场主线、重要事件、资产异动 | `CAP-MKT-*` | `API-MKT-001..003` | `D01-*` | `J01`、`J02` |
| `/themes` | Pack 目录、主题快照、KPI、产业链、事件、关联资产、数据健康 | `CAP-THM-*` | `API-THM-001..009` | `D02-*` | `J01` |
| `/assets/:assetId` | 统一资产身份、类型化详情、同类比较、事件与主题暴露 | `CAP-AST-*` | `API-AST-001..004` | `D03-*` | `J01`、`J02`、`J03` |
| `/fingpt` | 即时问答、快速/深度研究、证据抽取、Claim 与 Note 沉淀 | `CAP-FIN-*`、`CAP-RES-*` | `API-RES-001..016` | `D04-*` | `J01`、`J02` |
| `/claw` | Supervisor、Agent Team、Shared Blackboard、预算和 Runtime 阻塞恢复 | `CAP-AGT-*` | `API-AGT-001..004`、`API-RES-*` | `D05-*` | `J04`、`J05` |
| `/watchlists` | 自选、提醒规则、Alert 事件与通知收件箱 | `CAP-ALT-*` | `API-ALT-001..014`、`API-NOT-*` | `D03-*` | `J03` |
| `/research-library` | 项目、来源、Evidence、Claims、Notes 与 Artifacts 统一归档 | `CAP-RES-*` | `API-RES-001..016` | `D04-*`、`D05-*` | `J01`、`J02`、`J04` |
| `/capabilities` | Runtime、Skill、Agent Team、MCP 授权和日程管理 | `CAP-PLT-*`、`CAP-AGT-*` | `API-PLT-*`、`API-SCH-*`、`API-NOT-*` | `D06-*` | `J05` |

每个原型页面均提供功能或 API 追踪标记；完整定义以 `outputs/merged-platform-blueprint/api-atlas.html` 为准。

## 五条完整旅程

1. `J01 发现到研究`：市场首页 → 主题 Pack → 关联资产 → FinGPT → Research Note。
2. `J02 事件验证`：重要事件 → 来源核验 → 资产影响 → FinGPT 深度研究 → Pin Claim。
3. `J03 观察到提醒`：资产详情 → 加入 Watchlist → 创建规则 → 通知收件箱。
4. `J04 多 Agent 研究`：创建 Claw 任务 → Supervisor 编排 → Blackboard 协作 → Quality Gate → Artifact。
5. `J05 Runtime 阻塞恢复`：Claw 运行 → `blocked_runtime` → 修复 Provider → 原 Run 恢复，不降级为单 Agent。

## 原型状态覆盖

原型支持 `default`、`loading`、`empty`、`partial`、`stale`、`unavailable`、`quarantined`、`error`、`permission_denied` 与 `blocked_runtime`。其中提醒在数据过期时展示 `skipped_data_stale`，不会产生误触发；Claw 缺少多 Agent Runtime 时保持阻塞，不进行语义降级。

## 实施方式

原型本身是无构建依赖的静态应用，用来冻结页面职责、导航、状态和接口追踪。生产实现应复用这些路由与状态语义，将 `scripts/data-adapter.js` 中的演示数据逐域替换为 FastAPI 调用和 SSE 失效通知；页面模块不得直接访问数据库或跨域 repository。

Web 直接部署同一前端产物；Tauri 复用相同路由和页面，只在边界接入系统通知、文件选择和本地 Runtime。视觉与交互变更必须同步更新本映射、对应能力编号和浏览器旅程。
