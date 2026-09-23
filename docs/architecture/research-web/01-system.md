# 部署与模块职责

公开 Web 安装器在运行前创建 checkout 专属 `.venv`，并把固定 DSH 构建发布到用户私有的
`runtime/dsh/<commit>/` 版本目录；运行时仍是既有 3081 DSH 与 8088 FastAPI 两个受管进程。
`rwb web doctor` 读取安装摘要与健康事实，不增加守护进程、端口或数据库。
`rwb web start` 在创建任何子进程前复用同一份 Doctor 安装事实；checkout 专属环境、Web 锁、
CJPY、Node 或固定 DSH 未就绪时直接返回稳定 issue code 和安装器指引，不再先启动 3081 后等待超时。
安装器与 `rwb` 使用同一 Node 选择顺序：显式参数、`RESEARCH_NODE_BINARY`、可执行的 Codex bundled
Node、最后才是 PATH；Node 构建子进程也把选中版本置于 PATH 首位。安装事务只用已经通过固定
提交与闭包校验的 DSH state 原子刷新 Runtime build lock，Doctor 同时核对该锁。POSIX 锁读写逐级
使用 no-follow 目录描述符；Windows 逐级拒绝 reparse point，目录 alias 不会越出产品数据根。
干净用户目录会先从固定 DSH 模板初始化 `web` Profile，再加入 Tabbit 层；Windows Profile 的 pnpm
目录 junction 与 POSIX symlink 一样必须解析回固定源码树。Windows 服务归属使用 CIM 命令行核对、
无 shell PowerShell PID 探针和 `taskkill /T`，POSIX 继续使用进程组并把僵尸状态视为已退出。

研究框架由同一 Research Web 服务内的薄注册表暴露 Gold 与 Dollar；目录、调度生命周期、快照存储和新鲜度协议共享，定义、契约、采集、评分、上下文与前端 renderer 保持领域专属。它不增加独立进程、数据库或资产详情服务，浏览器 GET 只读取已保存快照，不触发外网采集。

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
| 集成协调器 | `app/research_web/integrations/` | 聚合 DataHub、本机诊断与 Tabbit 的五阶段状态，编排启动/手动探测批次、逐来源授权和安全快照；不替代 Provider 或验证器 |
| 本机集成诊断 | `app/research_web/local_integrations/` | 标准应用位置、已知注册信息和 Python 模块的无副作用发现；用户显式触发后，在受管临时目录与可终止子进程中验证 Office/Wind，Workbook 阶段 timeout 明确不超过 180 秒总预算减 10 秒协调余量，安全投影不返回路径或秘密 |
| 受限脚本 | `app/research_web/sandbox.py` | 文件访问、环境和进程终止边界 |
| 运行时组装 | `app/research_web/launch_runtime.py`、`runtime/` | 固定源码闭包、专属目录、私有模块链接校验；常驻注册 15 个 DataHub 业务工具，由 Broker 在调用时按最新状态选源 |
| Tabbit 适配 | `app/research_web/tabbit.py`、`runtime/tabbit-adapter.mjs`、`vendor/dsh-tabbit/0.3.4/` | 固定供应包校验、会话级页面授权、实时标签 claim、一次性内存上下文与写操作审批；只复用唯一 `ctx.tabbit` 执行器 |
| 服务管理 | `app/research_web/service_manager.py` | `rwb web` 的安装前置诊断、进程归属、健康检查、跨平台私有目录校验、项目私有 DSH 源码选择、持久后台启动、停止和失败回滚 |
| 数据迁移 | `app/research_web/data_migration.py` | 会话/附件/能力/数据集/产物的哈希复制；排除凭据并支持只读归档 |
| 能力管理 | `app/research_web/capabilities/`、`app/research_web/skills/` | 草稿、声明式内置种子、受检资源、版本、原生目录投影、版本化证据协议与只读 Tool 声明 |
| 报告 Workflow | `app/research_web/report_workflows/`、`report_workflow_routes.py` | 具体报告的模板/底稿资源、不可变版本、迁移、Claw 运行、Excel 刷新、日程与独立交付 |
| 产品壳、连接中心与输入框 | `ui/shell.mjs`、`ui/connections.mjs`、`ui/composer.mjs` | 双侧栏、会话与能力检索、统一来源配置/诊断、草稿输入；不执行研究或保留密码 |
| 能力前端 | `ui/capabilities.mjs`、`ui/data-catalog.mjs`、`ui/capability-editor.mjs`、`ui/capability-controller.mjs` | Skill/Tool/Workflow/数据卡片与详情、候选表单、步骤编辑、来源矩阵与显式版本/探测操作 |
| 研究台、资产与监控前端 | `ui/workbench.mjs`、`ui/asset-workspace.mjs`、`ui/report-workflows.mjs`、`ui/operations.mjs` | 研究台按需数据入口、独立资产观察、报告 Workflow 目录/详情、显式交接和只读运行指标；不直接执行研究或删除数据 |

数据目录和能力中心 UI 已接入当前源码；上表指源码职责，不表示登记的 22 个来源都已适配、配置或完成真实连接验收。当前东方财富基金与财联社可直接调用；MySQL 与天软仅在本机配置、依赖和权限满足条件时进入各自能力路由。

三十个内置 Skill 和四个 Workflow 继续进入同一能力目录。五个专用研究 Skill 的共享证据协议在种子构建时复制为版本资源，不是独立可调用能力；`framework-research` 只服务用户显式触发的框架深度验证，并受只读 Runtime 预设约束。六个 CPU 有界资讯/事件 Skill 通过相同版本机制封存计算脚本、严格输入输出 schema、运行时 provider/mapping/version/单位/日期/复权契约、来源哈希、synthetic golden 及 `cpu_bounded_v1` 共享资源。共享契约只接受 `YYYY-MM-DD`，验证来源哈希的规范非空 key 与 SHA-256 value，并固定 daily/ETF 的 CNY 口径；显式 null、首尾空白或含 CR/LF/Unicode 行段分隔符的 key 被拒绝，字段缺失时结果明确降级。它们在真实 Wind/Excel 对照未执行时可在能力中心发现但保持 disabled，不进入原生 provider candidates；catalog 只从严格 macOS Wind/Excel evidence artifact 路径派生 receipt，分别重算当前版本 golden 与 comparison run actual 摘要，再以数值容差和非数值严格一致做业务 JSON 比较，并在启用或回滚时复核文件未变。已知初版升级先撤下投影并禁用，异常失败关闭。六 CLI 在 POSIX 从 cwd fd 逐组件 openat/no-follow，Windows 校验最终句柄；dataset refs/source hashes 各限 32 项，完整 JSON envelope 按 UTF-8 不超过 64 KiB，成功 stdout 不附换行且恰好 65,536 字节仍允许，`row_delivery` 不复制顶层 refs。Stage 3 另增加七个基金/组合/行业 CPU Skill；它们复用同一严格 schema/运行时契约、安全 loader、受检算术、预算、envelope 和 comparison receipt verifier，全部可发现但默认 disabled，真实对照缺失时不能进入原生投影。基金穿透对完整输入子图 cycle fail-closed，行业计算器只吃预聚合数据。Stage 4 再增加利率均线、股权风险溢价、风格轮动、平台突破和缠论确认分型与笔五项 CPU 研究 Skill；同样复用严格 loader、预算、不可变版本和 receipt 门禁，并在真实对照证据缺失时保持 disabled。前三项以必填 provider-aware series identity 在输入和输出中绑定 descriptor role、identity、version 和 tenor：synthetic 精确绑定 fixture，`user_input` 可携带并原样回传符合格式的真实业务 identity；角色、期限、版本或风格双序列唯一性错配均失败关闭。Wind/DataHub 未命中 field mapping 精确生产身份白名单时同样失败关闭。平台突破只处理显式有限观察列表，缠论只实现非递归严格分型与交替笔的受限子集，歧义结构失败关闭。研报校验、SVG 重绘、PDF 读取及 CPU JSON 计算均受现有 `research_run_script` 沙箱限制。静态进程入口检查只拒绝不兼容包，不授予脚本新的进程、网络、文件或依赖安装权限。

comparison receipt 当前采用 artifact v2：宿主登记器以 HMAC-SHA256 绑定当前脚本、提交 synthetic
input、独立 Wind/Excel actual input、固定宿主执行器和两侧结果；`research_run_script` sandbox 的显式
最小环境不继承登记密钥，普通 JSON 与被审计算器不能自证。Stage 3 七包提交实际 synthetic source
artifact，未核验 DataHub 映射标为 `callable=false` 并强制 contract/ref provider 一致；基金/组合只接
受单一快照和非杠杆权重，基准偏离逐条匹配顶层报告期/因子日/行业版，行业计算增加全局 128 条嵌套投影、
统一日历/成交总额约束和拥挤度至少两个滚动观测。真实宿主签名对照仍缺失，所以七项继续 disabled。
catalog 初始化时会重新审计全部已启用的 receipt-gated 能力；非 v2、HMAC/绑定证据不可复核或登记器
密钥缺失时，立即撤下原生投影并持久化 disabled。能力选择前再次执行同一门禁，避免重启后的陈旧
enabled 状态绕过证据校验；该收紧不新增服务、接口、执行器或持久节点。

comparison evidence 的 synthetic/actual input 必须同时满足相对路径不同和读取后 SHA-256 不同；仅复制
synthetic 内容到另一文件再由登记器签名仍按 `invalid_comparison_evidence` 失败关闭。缠论计算器继续
要求所有记录属于同一 `asset_id`，并在结果顶层必填回传该唯一身份；改变整组记录身份会改变结果身份，
混合身份仍返回 `data_not_equivalent`。两项均只收紧既有目录与计算器契约。

Stage 2 六包输出 schema 的 parameters、dataset refs 与 provenance 现与 Stage 3/4 采用相同失败关闭
公共契约；event-review 回归在同一计算节点先对齐共同交易日，再计算相邻共同日的配对收益。该修正
不新增 API、状态、执行器或数据源，也不改变能力默认 disabled 与 receipt 门禁。

Research Runtime 固定注册 15 个品牌无关 `datahub_*` 工具。DataHub Broker 在每次调用时读取最新的
配置、授权、探测与 Provider 状态，因此来源可用性变化无需重启 Runtime；没有可调用来源时明确失败，
显式指定来源且禁止回退时不会静默换源。AKShare、天软等同步 Provider 的单次截止时间为 15 秒，
低于桥接层 22 秒；超时保存 `failed` 数据集，并以单线程门闩把仍未返回的第三方调用隔离为
`provider_busy`。

Wind 只以五项具备封闭适配路径的 capability binding 参与 callable 计算；市场活动内部只开放
资金流、融资融券和股东数据，现有龙虎榜方法不作为大宗交易暴露。指数限定实时 `quotes`，没有等价
方法的宏观/利率与基金持仓不登记为 Wind binding。Provider 返回值必须先经过 capability/dataset
固定 schema，并逐行匹配证券身份和请求日期，未知列或越界响应不会进入会话数据集。该 DataHub
Provider 仅实例化 xlwings/Excel `WindAdapter`，故只有 WindPy 或选择 `client_api` 不计为 callable；
所有 Wind binding 的市场范围固定为 `.SH`、`.SZ`、`.BJ` A 股。`market_bars` 与 `market_snapshot`
binding 只声明股票，请求必须显式携带 `asset_type=stock`；指数和 ETF 不由六位代码推断，指数仅走 points 口径的
`index_data`。日线行情、资金流和融资融券在构造或探测 adapter 前完成起止日期类型、正序和最多
60 个日历日跨度检查，避免先执行潜在大查询再依赖返回行数门禁；返回终点不足只标记 partial。

启用研究脚本时，Host 使用当前受管启动解释器执行 readiness 探测：必须是 Python 3.12 且能导入
numpy、pandas、matplotlib、openpyxl；失败投影为稳定的 `runtime_not_ready`，不搜索或回退系统
Python；非对象 JSON 等无效探针响应同样失败关闭。`research_run_script` 在可信 Host Runtime 中共享一条 FIFO 队列，全局只运行一个脚本，
排队最多 60 秒；取消项在获准执行前移除，超时返回 `runtime_busy`。脚本仍受默认 15 秒和 60 秒
hard cap。FIFO 槽只在子进程发出 `close` 后释放；SIGKILL 后仍无法确认关闭时 Host 进入 poisoned
busy 状态，拒绝启动后续脚本。通用 child `error` 只说明执行异常，不证明进程已关闭，因此不能释放
槽或清 poison；恢复只依赖实际 close 或 Runtime 重启。
队列不会把权限或宿主状态授予子进程。

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

研究脚本是本机 CPU-only 能力，无 GPU 依赖；数值库子进程线程上限固定为 4。当前沙箱仍只在
macOS 支持，Windows 只执行不加载 Wind 的 Provider 契约测试，不能作为 Windows 沙箱或真实
Wind 会话的支持证据。

Phase 2A/2B/2C 的 Registry、Runtime 与 Automation 在远端门禁通过后默认初始化；三个保留环境开关仍可显式设为 `0` 独立关闭。数据根、系统凭据库、单 worker 和专属 DSH 边界不变。

2026-09-11 的格式基线维护仅整理本机集成包导入、常量和时间解析表达式，不改变进程、存储或部署拓扑。

仓库 `rwb` 启动器进入自身解析出的项目根后再导入 Python 入口，并在 Codex Desktop 可用时固定其 bundled Node；其他环境可通过 `RESEARCH_NODE_BINARY` 固定已审核 Node，避免调用目录遮蔽和原生模块 ABI 漂移。

2026-09-14 增加的 Method 层仍位于现有 FastAPI 能力目录与同一 DSH Runtime：Research Workbench
拥有结构化 Method 契约和策略，DSH 只读取编译后的原生 Skill 包装。没有新增服务、端口、worker、
数据库或第二研究引擎；Codex／Claude 工程框架不属于本部署拓扑。
