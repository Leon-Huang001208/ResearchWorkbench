# AlphaFoundry × LSH 详细架构与产品蓝图设计

日期：2026-09-01

状态：已确认设计方向，等待书面规格复核

## 1. 目标

现有九张图保留为平台总览，但不足以直接指导功能实施。本设计新增一套“开发蓝图＋产品原型”双轨交付，使产品功能、页面、HTTP API、Service/Contract、数据表、领域事件、状态机和异常分支可以双向追踪。

最终读者应能回答：

1. 每个功能属于哪个产品模块。
2. 用户从哪个页面触发该功能。
3. 页面调用哪个 HTTP API。
4. API 委托哪个 Service/Contract。
5. 哪个模块拥有相应数据表。
6. 执行过程中产生哪些事件、SSE 状态和调度任务。
7. 失败、过期、阻塞、重试和恢复时产品如何表现。

## 2. 已选方案

采用“开发蓝图＋产品原型”双轨方案。

- 架构侧按领域拆图，避免把全部节点挤进一张不可维护的大图。
- 接口侧提供可筛选 API Atlas，而不是只在架构图中出现路径名称。
- 产品侧提供响应式高保真原型和可点击关键旅程。
- 所有交付物使用统一编号，使功能、页面、接口、服务、表和事件可以相互跳转。

未采用的方案：

- 单一超大型全景图：信息密度过高，无法支持实施和维护。
- API 文档优先、少量效果图：后端可启动，但产品结果不够直观，容易产生模块间重复设计。

## 3. 产品边界

### 3.1 FinGPT 与 Claw

FinGPT 和 Claw 作为两个独立工作区保留，但不建设两套研究平台。

FinGPT 负责：

- 人主导的即时研究会话。
- 关键词、URL、PDF、图片和附件输入。
- 搜索、事实核验、资产比较、图表、一页纸和调研清单。
- 对话式追问和较短研究运行。

Claw 负责：

- 目标驱动的多 Agent 任务。
- Supervisor、Agent Team、Shared Blackboard 和 Skill。
- 白名单 MCP、预算、最大步骤、并发和截止时间。
- 长时运行、日程、阻塞、恢复和 Artifact 汇总。

两者共享 `Shared Research Core`：

- Research Workspace 和 Project。
- Evidence、Claim、Artifact 和 Research Note。
- 附件、来源、引用和项目记忆。
- 统一资产身份和主题事实读取。
- 运行状态基础设施、通知、权限与审计。

FinGPT 提供“升级为 Claw 任务”操作。升级时携带当前 Workspace、Session、输入、附件、已验证 Evidence 和预算提示，不复制历史数据。

### 3.2 事实与研究分区

- 市场首页、主题 Pack 和资产模块只维护事实。
- 研究结果只写入研究区。
- Watchlist、Alert 和 Notification 只写入个人观察区。
- 模型不得写事实区。
- 缺失事实不得以零值或模型猜测补齐。

## 4. 产品信息架构

核心页面编号如下：

| 编号 | 页面 | 核心职责 |
|---|---|---|
| P01 | 全市场首页 | 全球背景、A股状态、市场主线、重要事件、资产异动 |
| P02 | 主题研究 | Pack 目录、主题详情、KPI、产业链、事件、资产暴露和数据健康 |
| P03 | 资产观察 | 统一资产详情、同类比较、事件、主题暴露和研究入口 |
| P04 | FinGPT | 即时研究、历史会话、附件、证据、追问和研究产物 |
| P05 | Claw | Agent Team、任务运行、Blackboard、日程、Skill、预算和恢复 |
| P06 | 自选与提醒 | Watchlist、Alert Rule、Alert Event 和 Notification Inbox |
| P07 | 研究资料库 | Project、Evidence、Claim、Artifact 和版本化 Research Note |
| P08 | 能力中心 | Runtime Provider、Skill、MCP 授权、Agent Team 和 Schedule 配置 |

五条必须可点击的核心旅程：

1. J01 发现到研究：市场首页 → 主题 Pack → 关联资产 → FinGPT → Research Note。
2. J02 事件验证：重要事件 → 来源 → 资产影响 → 深度研究 → Pin Claim。
3. J03 观察到提醒：资产详情 → Watchlist → Alert Rule → Notification → 事件上下文。
4. J04 多 Agent 研究：Claw → Team/Skill → Blackboard → Quality Gate → Artifact。
5. J05 定时与恢复：Schedule → 租约触发 → `blocked_runtime` → 修复 Provider → 恢复运行。

## 5. 响应式产品壳

Web 应用和 Tauri 桌面壳复用同一前端，不维护两套 UI。

### 5.1 布局

- 全局顶栏：Logo、全局搜索、运行任务、通知、主题和账户。
- 产品导航：市场首页、主题、资产、FinGPT、Claw、自选、资料库和能力中心。
- 模块侧栏：当前模块功能、会话或任务、筛选和状态。
- 主工作区：事实浏览、研究对话或 Agent 执行。
- 右侧共享研究空间：来源、Evidence、Claim、Notes 和 Artifact。

### 5.2 断点

| 视口 | 行为 |
|---|---|
| ≥1440px | 产品导航、模块侧栏、主工作区和右侧研究空间同时显示 |
| 1024–1439px | 产品导航收窄，右侧研究空间按需展开 |
| 768–1023px | 模块侧栏和研究空间变为抽屉 |
| <768px | 底部主导航，Composer 固定，详情区域全屏切换 |

### 5.3 视觉语言

现有 AlphaFoundry UI 不作为视觉约束。新设计使用：

- AlphaEngine 的机构级产品壳和信息密度。
- Zhengyan 的统一输入、会话后台运行、右侧研究空间和响应式交互。
- 深海军蓝导航、冷白灰画布、金融蓝操作色和克制金色品牌强调。
- A股红涨、绿跌。
- 小圆角、细边框、低阴影和 8px 间距网格。
- 不照搬 Zhengyan 的紫色渐变和大面积玻璃效果。

正式产品原型必须使用真实 AlphaFoundry Logo，并在 `brand-spec.md` 中记录资产路径和设计 Token。

## 6. 详细架构交付结构

### 6.1 共享平台图

| 编号 | 图 | 解决的问题 |
|---|---|---|
| A01 | 产品能力全景 | 所有功能及保留、合并、删除、新增决策 |
| A02 | Web/Tauri 部署 | 浏览器、Tauri、FastAPI、PostgreSQL、DSH 和通知边界 |
| A03 | 模块依赖 | 允许和禁止的跨模块依赖 |
| A04 | 数据所有权 | 事实区、研究区和个人观察区归属 |
| A05 | 核心 ER | 新增表、复用表、主键和关键关系 |
| A06 | 事件与调度 | Domain Event、Scheduled Job、租约、幂等和通知 |
| A07 | 安全边界 | Runtime、Skill、MCP、URL、文件和数据库权限 |
| A08 | 迁移删除门禁 | LSH 迁移、兼容、归档、停用和回退 |

### 6.2 每个领域的五种视图

以下六个领域分别生成五种视图，共三十张细化图：

- D01 市场首页。
- D02 主题 Research Pack。
- D03 资产观察。
- D04 FinGPT。
- D05 Claw。
- D06 平台内核与能力中心。

每个领域包含：

1. 功能树：用户能力、子功能、页面和状态。
2. 接口地图：HTTP API、Service/Contract、表和事件。
3. 请求序列：正常路径、SSE、取消、重试和恢复。
4. 状态机：状态、守卫、失败、重入和终态。
5. 数据流：来源、规范化、质量门、读模型和消费者。

单张 Archify 图保持一个主路径，主要节点不超过十二个。接口数量超出时通过 API Atlas 展开，而不是破坏图的可读性。

## 7. API Atlas

API Atlas 是可交互 HTML 交付物，支持按模块、方法、同步/异步、状态和数据所有者筛选。

每个接口记录：

- 稳定编号。
- HTTP method 和 path。
- 页面和功能编号。
- 请求模型、响应模型和分页。
- `Idempotency-Key` 要求。
- 成功状态码和错误响应。
- SSE 事件名称及重连语义。
- Service/Contract 所有者。
- 读取和写入的数据表。
- 产生或消费的领域事件。
- Freshness、来源和时间语义。
- 权限与安全限制。

### 7.1 接口组

研究接口组：

- `/api/research-workspaces`
- `/api/research-sessions`
- `/api/research-sessions/{id}/messages`
- `/api/research-runs`
- `/api/research-runs/{id}/events`
- `/api/runtime-providers`
- `/api/research-skills`
- `/api/agent-teams`
- `/api/agent-schedules`

市场首页接口组：

- `/api/market-home`
- 首页区块失效 SSE。
- 交易日 close snapshot 读取。

主题接口组：

- Pack 目录和 Manifest。
- Snapshot、KPI、Value Chain、Events、Related Assets 和 Data Health。
- 从主题创建 Research Workspace。

资产和个人观察接口组：

- 统一资产搜索和 Asset Snapshot Envelope。
- Peer Set、历史、事件和主题暴露。
- Watchlist 和 Watchlist Item。
- Alert Rule 和 Alert Event。
- Notification Inbox 和已读状态。

平台内核中的 Scheduler、Domain Event、任务租约和通知投递优先使用内部 Contract；只有产品确实需要管理的能力才暴露 HTTP API。

## 8. 状态与错误设计

所有核心页面至少覆盖：

- 默认状态。
- 加载状态。
- 空状态。
- 部分数据状态。
- `stale`、`unavailable` 和 `quarantined`。
- 权限拒绝。
- 网络或 Provider 故障。
- 超时、取消和重试。
- SSE 断线重连。

研究运行还覆盖：

- queued、running、waiting、completed、failed、cancelled。
- `blocked_runtime`。
- Budget/step/deadline exceeded。
- Provider 不可用和工具未授权。

Alert 数据为 `stale` 或 `unavailable` 时不触发，记录 `skipped_data_stale`。

## 9. 原型内容策略

- 优先读取当前项目真实数据。
- 缺失但必须展示的状态使用明确标注的“演示状态”。
- 不伪造市场数值、来源、统计结果、Logo、客户或可信度指标。
- Zhengyan 中已有的研究问题可作为交互内容参考，但必须标明来源或转换为真实数据驱动结果。

## 10. 产品原型交付

原型提供：

- 八个高保真核心页面。
- 五条可点击核心旅程。
- 明暗主题。
- 紧凑和舒展两种信息密度。
- 右侧研究空间展开和收起。
- 适用的 hover、focus、active、disabled、loading、empty 和 error 状态。
- 页面到 API Atlas 和详细架构的反向链接。

v0 已确认的界面方向：

- AlphaEngine 式顶栏、产品导航和模块侧栏。
- Zhengyan 式统一 Composer、会话后台运行和右侧研究空间。
- FinGPT 与 Claw 分开呈现，共享研究内核。

## 11. 追踪编号

使用以下编号前缀：

- `CAP-*`：产品能力。
- `PAGE-*`：页面。
- `API-*`：HTTP API。
- `SVC-*`：Service/Contract。
- `DB-*`：数据表或读模型。
- `EVT-*`：领域事件或 SSE 事件。
- `STATE-*`：状态机状态。
- `JOURNEY-*`：用户旅程。

每个页面功能必须能追踪到至少一个 API 或明确标记为本地纯交互。每个写 API 必须能追踪到一个 Service 所有者、数据所有者和幂等策略。

## 12. 输出位置

正式交付使用：

- `docs/architecture/merged-platform/detailed/`：详细架构和 API 文档。
- `docs/architecture/merged-platform/detailed/diagrams/`：Archify JSON 图源。
- `docs/architecture/merged-platform/product/brand-spec.md`：品牌和设计 Token。
- `outputs/merged-platform-blueprint/`：架构 HTML 和 API Atlas。
- `outputs/merged-platform-product-prototype/`：响应式高保真产品原型。

现有 `docs/architecture/merged-platform/` 和 `outputs/merged-platform-architecture/` 保留为总览入口，并增加到详细蓝图的链接。

## 13. 验证

架构交付：

- Archify JSON 逐张通过 `showcase` 校验。
- HTML 使用 `deliver` 生成并冻结规格哈希。
- 每张图完成 1440×900、1600×1000、1920×1080 和 2048×1320 containment 检查。
- API Atlas 检查编号唯一、页面覆盖、数据所有权和事件引用完整。

产品原型：

- 检查真实 Logo 和本地资产路径。
- 检查 1440、1024、768 和小于 768px 的响应式行为。
- 检查键盘焦点、文本溢出、减少动效和语义颜色。
- 检查关键交互的默认、加载、空、错误和禁用状态。
- 不将未执行的浏览器验收、Windows 构建或真实安装测试描述为已通过。

## 14. 非目标

- 本阶段不实现业务后端。
- 不重构策略、因子评分、模拟交易、报告中心和运维体系。
- 不把 DSH 变为数据库客户端。
- 不支持任意代码 Skill、Shell、任意 URL 或未注册 MCP。
- 不为桌面端维护独立的视觉实现。

## 15. 后续计划边界

书面规格通过后，实施计划必须分成可独立验收的批次：

1. 追踪模型、能力矩阵和 API Atlas 骨架。
2. 共享平台详细图。
3. 六个领域详细图。
4. 产品壳、设计 Token 和响应式原型基础。
5. 八个页面和五条用户旅程。
6. 状态覆盖、交叉链接、Archify 校验和原型验证。

业务代码实施仍遵循现有合并平台迁移顺序，不由本视觉蓝图扩大范围。
