# 共享平台详细架构

## 1. 模块化单体边界

Web 与 Tauri 共用同一套响应式前端资源，所有业务请求进入唯一 FastAPI。FastAPI 只调用本模块 Service 或公开 Contract；Repository 只管理所属数据 Owner，禁止跨模块直接读写其他模块表。PostgreSQL + pgvector 是事实、研究、任务和个人配置的唯一持久化存储。

| 模块 | 页面 | Service | 数据 Owner | 关键边界 |
|---|---|---|---|---|
| 市场首页 | `PAGE-P01` | `SVC-MKT-001` | `DATA-MKT-001` | 只维护事实投影和不可变快照 |
| 主题研究 | `PAGE-P02` | `SVC-THM-001` | `DATA-THM-001/002` | 插件只 normalize/validate/derive |
| 资产观察 | `PAGE-P03/P06` | `SVC-AST-001`、`SVC-ALT-001` | `DATA-AST-*`、`DATA-ALT-*` | 事实与个人观察分区 |
| FinGPT | `PAGE-P04` | `SVC-RES-001/002` | `DATA-RES-*` | 即时研究，不调度多 Agent 团队 |
| Claw | `PAGE-P05` | `SVC-RES-002`、`SVC-SCH-001` | `DATA-RES-002`、`DATA-SCH-001` | 任务优先、预算约束、可阻塞运行时 |
| 能力中心 | `PAGE-P08` | `SVC-PLT-001/002` | `DATA-PLT-001` | Runtime、Skill、MCP 和团队白名单 |

## 2. 共享研究内核

FinGPT 与 Claw 分开呈现，但共享 Workspace、Session、Evidence、Claim、Artifact、Research Note、附件、来源和运行记录。`CAP-CLW-004` 删除 Claw 的重复聊天壳和独立历史库，由 `CAP-RES-001` 与 `CAP-RES-004` 替代。

研究结果只进入研究区。完整 Run 自动归档；用户选择 Claim 或段落生成版本化 Note。任何模型输出都不得写入事实区。

## 3. 运行时与安全

- 普通 FinGPT 可在 DSH 不可用时回退 LangGraph。
- Claw 能力不足时进入 `blocked_runtime`，不得伪装降级成功。
- DSH 作为可选 RuntimeProvider 侧车，不持有数据库凭据。
- Skill 只声明提示词、I/O Schema、内置工具、附件、受控网页和注册 MCP。
- 任意 Shell、任意文件系统、任意 URL 和未注册 MCP 默认拒绝。

## 4. 调度与事件

Scheduler Coordinator 将刷新、Agent Schedule 和提醒评估统一存为 PostgreSQL Job。Worker 获取租约后才能执行；默认不允许并发重入。错过多次触发时只合并最近一次，并产生可审计事件。提醒遇到 stale/unavailable 数据只记录 `alert.skipped_data_stale`，不得触发通知。

## 5. 八张共享图

| 图 | 回答的问题 |
|---|---|
| A01 | 产品目标如何落到能力决策和实施追踪？ |
| A02 | Web、Tauri、FastAPI、Runtime 和 PostgreSQL 如何部署？ |
| A03 | 页面、API、Service、Contract、Repository 如何依赖？ |
| A04 | 事实区、研究区、个人区由谁拥有、谁可消费？ |
| A05 | 核心实体如何连接，哪些表继续复用？ |
| A06 | 调度、租约、事件、处理器和通知如何流转？ |
| A07 | 用户输入到 Runtime/MCP 的安全门如何闭合？ |
| A08 | LSH 迁移何时可归档和删除，何时必须回退？ |
