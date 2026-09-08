# 部署与模块职责

## 当前启动链

`ui/index.html` → 原生 ES 模块 → 同源 FastAPI `app.research_web.main:app` → `ResearchService` → `DSHClient` → 产品专属 DSH。原生下行双 WebSocket 归一为 Web SSE 快照。模型调用、执行循环、原生日志、工具、Skill 与子 Agent 均由 DSH 完成。

独立入口不导入旧 FastAPI 生命周期、后台爬虫、知识处理或数据库迁移。轻量模块只复用项目日志设施等实用基础组件。

| 模块 | 实际源码 | 所负责的边界 |
|---|---|---|
| Web API | `app/research_web/main.py` | 同源/回环访问约束、产品路由、上传下载、SSE |
| 研究适配 | `app/research_web/service.py` | 会话归属、幂等受理、运行投影、审批与子任务状态 |
| 研究台 API | `app/research_web/workbench.py` | 页面按需查询、查询状态、快照交接与实际产物索引 |
| 运行聚合 | `app/research_web/operations.py` | 从 DSH 历史、DataHub manifest、服务状态和项目数据根生成只读指标 |
| 原生传输 | `app/research_web/client.py` | 有限 RPC 名称、关联 ID、历史分页、双 WS |
| 事件投影 | `app/research_web/projection.py` | 从真实日志重建消息、活动、状态、用量，不执行研究 |
| 本地索引 | `app/research_web/store.py` | 原子索引、会话目录、文件 ID、安全打开 |
| 文件交付 | `app/research_web/delivery.py` | 本任务基线、有效输出集合、缺失格式和原因 |
| DataHub | `app/research_web/datahub/` | 15 项能力/22 个来源静态目录、统一连接状态、白名单选源、Provider、单源探测、不可变资料和共享分析；MySQL 仅开放逐级 schema 与受控单表查询 |
| 连接中心 | `app/research_web/datahub/connection_center.py`、`connections.py`、`probes.py` | 本地非秘密配置、系统凭据引用、平台诊断、旧环境迁移和四维状态；不向浏览器或模型返回秘密 |
| 受限脚本 | `app/research_web/sandbox.py` | 文件访问、环境和进程终止边界 |
| 运行时组装 | `app/research_web/launch_runtime.py`、`runtime/` | 固定源码闭包、专属目录、私有模块链接校验；启动时按 DataHub 可调用来源注入 `enabledTools`，查询不逐次审批 |
| 服务管理 | `app/research_web/service_manager.py` | `rwb web` 的进程归属、健康检查、项目私有 DSH 源码选择、持久后台启动、停止和失败回滚 |
| 数据迁移 | `app/research_web/data_migration.py` | 会话/附件/能力/数据集/产物的哈希复制；排除凭据并支持只读归档 |
| 能力管理 | `app/research_web/capabilities/` | 草稿、受检资源、版本、原生目录投影与只读 Tool 声明 |
| 报告 Workflow | `app/research_web/report_workflows/`、`report_workflow_routes.py` | 具体报告的模板/底稿资源、不可变版本、迁移、Claw 运行、Excel 刷新、日程与独立交付 |
| 产品壳、连接中心与输入框 | `ui/shell.mjs`、`ui/connections.mjs`、`ui/composer.mjs` | 双侧栏、会话与能力检索、统一来源配置/诊断、草稿输入；不执行研究或保留密码 |
| 能力前端 | `ui/capabilities.mjs`、`ui/data-catalog.mjs`、`ui/capability-editor.mjs`、`ui/capability-controller.mjs` | Skill/Tool/Workflow/数据卡片与详情、候选表单、步骤编辑、来源矩阵与显式版本/探测操作 |
| 研究台、资产与监控前端 | `ui/workbench.mjs`、`ui/asset-workspace.mjs`、`ui/report-workflows.mjs`、`ui/operations.mjs` | 研究台按需数据入口、独立资产观察、报告 Workflow 目录/详情、显式交接和只读运行指标；不直接执行研究或删除数据 |

数据目录和能力中心 UI 已接入当前源码；上表指源码职责，不表示登记的 22 个来源都已适配、配置或完成真实连接验收。当前东方财富基金与财联社可直接调用；MySQL 与天软仅在本机配置、依赖和权限满足条件时进入各自能力路由。

Research Runtime 每次启动都从离线 DataHub 能力目录重新计算 `enabledTools`；来源配置变化只有在重启后才改变原生工具注册。缺少可调用来源的工具不暴露给模型。AKShare、天软等同步 Provider 的单次截止时间为 15 秒，低于桥接层 22 秒；超时保存 `failed` 数据集，并以单线程门闩把仍未返回的第三方调用隔离为 `provider_busy`。

## 存储归属

- DSH 原生日志是研究正文和执行事件的持久来源。BFF 不另建聊天事实库。
- 产品 `index.json` 保存会话归属、文件标识、默认模型元数据、幂等和交付收据，不保存 API Key。
- 同一索引保存研究台查询、交接收据和安全化操作审计；它们是指向 DSH/manifest 的产品索引，不是第二套研究或指标事实库。
- `sessions/<sid>/inputs/` 是上传资料；`resources/` 是研究脚本可读的审核资源；`outputs/` 是研究可写产物。
- DataHub 私有原始响应与会话可读数据集分开。所有共享资料仍绑定目标会话及原始哈希，不提供任意路径读取接口。
- DataHub 非秘密连接配置位于 `connections/`；密码、Token 和账号池秘密只存运行 8088 的操作系统用户凭据库。API 仅返回 `secret_configured`，浏览器提交后立即清空秘密字段。
- 原生凭据只存在专属 DSH 私有目录，不提供给研究脚本环境。
- 迁移只复制研究状态和 DSH 会话索引；凭据、运行时 overlay、临时文件、旧控制令牌与日志不复制。新实例需要在设置页重新授权模型。

## 并发与部署限制

当前索引和锁按**单 Web worker**实现，不能启动多个 Uvicorn worker 共写一个数据根。`rwb web start` 默认从 `~/.research-workbench/dsh-source/` 启动经过固定提交构建的项目私有 DSH，只管理 3081/8088；`RESEARCH_DSH_SOURCE` 仅用于显式覆盖。状态文件保存 PID、命令指纹、项目路径和数据根；运行监控和停止命令都要求状态内容与实际 PID 命令签名一致，绝不把任意存活 PID 当成受管进程，也绝不操作用户原有 3080。服务仅回环；无多人权限体系，不应直接暴露公网。

只验证当前 macOS 脚本隔离；不把 Web 本地成功当作 Linux/Windows/桌面支持证据。DSH 固定源码提交为 `c919b2a460753859665db3f60143d525fb9140cf`，基于官方最新版并包含会话原生永久删除协议与持久层实现。
