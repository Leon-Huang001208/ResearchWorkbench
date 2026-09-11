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
| 运行时认证文件 | `app/research_web/runtime_auth.py` | Web 客户端与服务管理器共用的有界读取、别名拒绝和打开前后身份核对 |
| 事件投影 | `app/research_web/projection.py` | 从真实日志重建消息、活动、状态、用量，不执行研究 |
| 本地索引 | `app/research_web/store.py` | 原子索引、会话目录、文件 ID、安全打开 |
| 文件交付 | `app/research_web/delivery.py` | 本任务基线、有效输出集合、缺失格式和原因 |
| DataHub | `app/research_web/datahub/` | 15 项能力/22 个来源静态目录、统一连接状态、白名单选源、Provider、单源探测、不可变资料和共享分析；MySQL 仅开放逐级 schema 与受控单表查询 |
| MCP Registry | `app/research_web/mcp_registry/` | 在功能开关内聚合官方与私有 Registry，保存原子最后成功缓存并输出只读市场/API；不安装、启用或调用 MCP |
| MCP Runtime Host | `app/research_web/mcp_runtime/` | 不可变安装、官方 SDK 连接、OAuth、schema/风险/授权快照、人工审批及激活回滚；不执行 Registry 发布 |
| Automation | `app/research_web/automation/` | 锁定版本任务、IANA 日程、独立 Claw 会话、运行恢复与研究/投递双状态；不自动升级或重试研究 |
| 连接中心 | `app/research_web/datahub/connection_center.py`、`connections.py`、`probes.py` | 本地非秘密配置、系统凭据引用、平台诊断、旧环境迁移和四维状态；不向浏览器或模型返回秘密 |
| 本机集成诊断 | `app/research_web/local_integrations/` | 标准应用位置、已知注册信息和 Python 模块的无副作用发现；用户显式触发后，在受管临时目录与可终止子进程中验证 Office/Wind，安全投影不返回路径或秘密 |
| 受限脚本 | `app/research_web/sandbox.py` | 文件访问、环境和进程终止边界 |
| 运行时组装 | `app/research_web/launch_runtime.py`、`runtime/` | 固定源码闭包、专属目录、私有模块链接校验；启动时按 DataHub 可调用来源注入 `enabledTools`，查询不逐次审批 |
| Tabbit 适配 | `app/research_web/tabbit.py`、`runtime/tabbit-adapter.mjs`、`vendor/dsh-tabbit/0.3.4/` | 固定供应包校验、会话级页面授权、实时标签 claim、一次性内存上下文与写操作审批；只复用唯一 `ctx.tabbit` 执行器 |
| 服务管理 | `app/research_web/service_manager.py` | `rwb web` 的进程归属、健康检查、跨平台私有目录校验、项目私有 DSH 源码选择、持久后台启动、停止和失败回滚 |
| 数据迁移 | `app/research_web/data_migration.py` | 会话/附件/能力/数据集/产物的哈希复制；排除凭据并支持只读归档 |
| 能力管理 | `app/research_web/capabilities/`、`app/research_web/skills/` | 草稿、声明式内置种子、受检资源、版本、原生目录投影、版本化证据协议与只读 Tool 声明 |
| 报告 Workflow | `app/research_web/report_workflows/`、`report_workflow_routes.py` | 具体报告的模板/底稿资源、不可变版本、迁移、Claw 运行、Excel 刷新、日程与独立交付 |
| 产品壳、连接中心与输入框 | `ui/shell.mjs`、`ui/connections.mjs`、`ui/composer.mjs` | 双侧栏、会话与能力检索、统一来源配置/诊断、草稿输入；不执行研究或保留密码 |
| 能力前端 | `ui/capabilities.mjs`、`ui/data-catalog.mjs`、`ui/capability-editor.mjs`、`ui/capability-controller.mjs` | Skill/Tool/Workflow/数据卡片与详情、候选表单、步骤编辑、来源矩阵与显式版本/探测操作 |
| 研究台、资产与监控前端 | `ui/workbench.mjs`、`ui/asset-workspace.mjs`、`ui/report-workflows.mjs`、`ui/operations.mjs` | 研究台按需数据入口、独立资产观察、报告 Workflow 目录/详情、显式交接和只读运行指标；不直接执行研究或删除数据 |

数据目录和能力中心 UI 已接入当前源码；上表指源码职责，不表示登记的 22 个来源都已适配、配置或完成真实连接验收。当前东方财富基金与财联社可直接调用；MySQL 与天软仅在本机配置、依赖和权限满足条件时进入各自能力路由。

十一个内置 Skill 和四个 Workflow 继续进入同一原生发现目录。五个专用研究 Skill 的共享证据协议在种子构建时复制为版本资源，不是独立可调用能力；研报校验、SVG 重绘和 PDF 读取均受现有 `research_run_script` 沙箱限制。新增静态进程入口检查只拒绝不兼容包，不授予脚本新的进程、网络、文件或依赖安装权限。

Research Runtime 每次启动都从离线 DataHub 能力目录重新计算 `enabledTools`；来源配置变化只有在重启后才改变原生工具注册。缺少可调用来源的工具不暴露给模型。AKShare、天软等同步 Provider 的单次截止时间为 15 秒，低于桥接层 22 秒；超时保存 `failed` 数据集，并以单线程门闩把仍未返回的第三方调用隔离为 `provider_busy`。

Tabbit 由 Profile 私有依赖链按 `base → web-app → dsh-tabbit → research-tabbit-adapter` 顺序加载。供应归档、许可证和文件清单在复制前逐项校验，运行时禁用 `tabbit_browser_install`，不执行下载或自动升级。浏览器自动化默认开启，Tabbit `web_fetch` 接管默认关闭；配置写入 Research Web 数据目录并在下次安全重启生效。页面正文只停留在 DSH 内存的一次性 token 中，不进入产品索引或日志。

跨平台 staging 把 npm tar 成员固定解释为 POSIX 路径，完成越界与链接检查后才映射到宿主文件系统；Windows 原子配置替换先关闭临时文件句柄，adapter overlay 路径固定使用正斜杠。这些兼容修正不增加执行器、下载器或存储节点。

Windows 读取 DSH 认证文件、DataHub 私有控制/收据/快照和会话下载时使用产品根内的规范路径回退，拒绝链接与重解析点并核对普通文件、硬链接数、大小及打开前后身份。快照仍以同目录临时目录和原子改名发布；永久删除只为产品所有树中的真实目录和普通文件恢复所有者写权限。POSIX 继续使用目录描述符、`NOFOLLOW`、私有 mode 与目录 `fsync`。

## 存储归属

- DSH 原生日志是研究正文和执行事件的持久来源。BFF 不另建聊天事实库。
- 产品 `index.json` 保存会话归属、文件标识、默认模型元数据、幂等和交付收据，不保存 API Key。
- 同一索引保存研究台查询、交接收据和安全化操作审计；它们是指向 DSH/manifest 的产品索引，不是第二套研究或指标事实库。
- `sessions/<sid>/inputs/` 是上传资料；`resources/` 是研究脚本可读的审核资源；`outputs/` 是研究可写产物。
- DataHub 私有原始响应与会话可读数据集分开。所有共享资料仍绑定目标会话及原始哈希，不提供任意路径读取接口。
- DataHub 非秘密连接配置位于 `connections/`；密码、Token 和账号池秘密只存运行 8088 的操作系统用户凭据库。API 仅返回 `secret_configured`，浏览器提交后立即清空秘密字段。
- MCP Registry 非秘密配置、ETag、游标与最后成功缓存位于数据根的 `mcp-registry/`；目录元数据是有界 Unicode plain text，API 原样投影，UI 仅在最终 HTML sink 转义。Bearer/OAuth 秘密只进入 Keyring 服务 `ResearchWorkbench.MCPRegistry`。认证 Registry 仅使用 HTTPS，无认证 HTTP 仅限精确 loopback，OAuth 端点始终使用 HTTPS。官方与私有 Registry 的同名服务器按身份三元组隔离。
- MCP 安装清单、隔离 payload、Runtime 状态和激活列表位于数据根的 `mcp-installations/` 与 `mcp-runtime/`；本地环境值和远程 OAuth token 只进入系统凭据库。DSH 只读取 Host 生成的安全工具绑定和私有控制文件，不读取安装秘密。
- Automation 与 Run 事实位于数据根的原子索引；任务锁定目标版本、内容 SHA 与 MCP 工具 schema 快照。投递渠道 JSON 只保存非敏感投影，URL、密码和签名秘密只进入 `ResearchWorkbench.Delivery`。
- 最新本机诊断安全投影原子写入 `local-integrations/local-integrations.json`，权限限制为当前用户；Excel、Word、PowerPoint 的真实验证副本位于各自 Office 容器内。Wind 复用当前 Excel 厂商会话但只持有独占空白工作簿；监督器仅清理本轮真正拥有的进程，用户已有 Excel 不进入清理集合。不持久化探测到的绝对路径、命令参数、环境变量或秘密。
- 本机显式验证结果按 TTL 和上下文指纹读取；TTL 截止时刻即失效，`0` 表示不产生可复用的可调用证据。
- 原生凭据只存在专属 DSH 私有目录，不提供给研究脚本环境。
- Tabbit 页面访问授权只存在于当前 Research Runtime 生命周期；实时正文 token 绑定当前会话、单次消费并在 10 分钟后过期。
- 迁移只复制研究状态和 DSH 会话索引；凭据、运行时 overlay、临时文件、旧控制令牌与日志不复制。新实例需要在设置页重新授权模型。

## 并发与部署限制

当前索引和锁按**单 Web worker**实现，不能启动多个 Uvicorn worker 共写一个数据根。`rwb web start` 默认从 `~/.research-workbench/dsh-source/` 启动经过固定提交构建的项目私有 DSH，只管理 3081/8088；`RESEARCH_DSH_SOURCE` 仅用于显式覆盖。状态文件保存 PID、命令指纹、项目路径和数据根；运行监控和停止命令都要求状态内容与实际 PID 命令签名一致，绝不把任意存活 PID 当成受管进程，也绝不操作用户原有 3080。服务仅回环；无多人权限体系，不应直接暴露公网。

只验证当前 macOS 脚本隔离；不把 Web 本地成功当作 Linux/Windows/桌面支持证据。DSH 固定源码提交为 `c919b2a460753859665db3f60143d525fb9140cf`，基于官方最新版并包含会话原生永久删除协议与持久层实现。
