# Research Workbench 架构总览

冻结恢复任务显式保留系统与既有Homebrew工具PATH，部署前验证Git LFS可用，保持原Git钩子和身份检查；不安装依赖或改变研究服务拓扑。

保留主实例版本的显式静态网关更新使用 version 3 `static-gateway`，同时核对主实例/旧网关到目标的受限差异与冻结工具身份；不改变原研究进程、自动兼容清单或恢复保护。旧主实例菜单适配保持唯一控制器，详见[网关升级](research-web-gateway-upgrade.md)。

账号资料与管理复用现有网关：菜单顶部身份进入应用内 `#/account`，管理员用户管理归入设置；登录入口保持独立。只改变浏览器路由和共用账号控制器，不新增执行服务、权限接口、数据格式或依赖。

网关界面更新允许已审工具版本与已验收产品版本分离，复用原空池/排空/保全事务。新version 2恢复包从工具Git对象冻结，离线核对两段受限差异和实际primary；旧恢复合同、主研究进程与自动兼容白名单不变，详见[网关升级](research-web-gateway-upgrade.md)。

研究工具向供应商发送根级object参数；code/report_plan互斥仍在执行边界强制。固定DSH的SDK转换成功不等于供应商接受schema，离线检查同时经过实际pi-ai上下文和HTTP请求序列化，不调用真实模型。

系统报告进一步绑定自由分析：数值事实与公式用受控引用插入，Host从实际正文独立重建plan、声明、中文呈现及附件。新网页研究在原receipt冻结bound-analysis-v1，不能回退手工payload；旧receipt/旧报告不迁移。重复英文底稿保存于同版本审计JSON，正文与HTML/Word/PDF实际内容另核对，DSH及原research_quality判据不变。

附接网关的显式安全升级复用既有管理平面：空私有池出生栅栏、优雅 HTTP 排空和持久全请求冻结共同保护切换。主实例持续运行；恢复只处理网关源码和匹配绑定，不写业务数据，不扩大自动兼容白名单。合同见[网关升级](research-web-gateway-upgrade.md)。

Host 复用已有来源读取和证据快照，从完整网页字节提取闭合年度 GDP 布局，并保存全文 SHA、原文 span、期间和初步/最终版本。它只扩展确定性证据，不新增模型循环；不支持的布局、日期冲突和未绑定版本继续保留未核验。

允许网页取证的研究从空索引起统一使用原 research_run_script(report_plan)；后取得数值不切回手写 payload。系统从原始观测执行有界 calculations 配方，生成声明、父来源及同节笔记；Host 从实际输入重建观测并独立重算，原 research_quality 判据不变。自由分析与跨版本可比性不因此通过。仅上传的一般研究和旧 SDK 调用保持兼容，无第二执行循环。

数字与链接修复不新增执行循环：research_arithmetic 只复算有限字面算式，不能替代来源核验；report_delivery 由 Host 将当前规范内容哈希、检查回执和不可变归档绑定。UI 禁用不匹配别名并展示该检查版本，原生历史不改写。

三组FinGPT对照是默认关闭的本机验收控制器，源码快照、Host、凭据namespace及研究数据均隔离；仅测试侧适配模型接入和预算，不合并或部署原Node引擎。详见[实验合同](research-web-fingpt-comparison.md)。

正文读取复用原生研究工具与私有 Host 回调：仅接受本会话登记来源 ID，固定公共 DNS 地址并验证 TLS，有限读取进程在取消或总时限到达时回收。它不执行研究计划；DSH 仍是唯一研究引擎。Host 对规范报告实际字节建立版本与检查结果的精确关联，不能把另一版本的 passed 沿用给当前或历史报告。

AI资讯采用固定原版AIHOT API与worker、独立PostgreSQL和Host私有桥；默认关闭采集、推理和付费源，从自主库重新起刊。隔离验收不导入线上历史，不更新常驻内容；DSH继续是唯一研究执行引擎，Hot宏观及研究证据保留，重叠AI信源在未来真实闭环验收后的显式切换事务中交接。详见[自主资讯合同](research-web-ai-news.md)。

可选私网多用户模式由独立认证网关和 SQLite 账号库组成，管理员邀请用户通过固定 Tailscale HTTPS origin 登录。网关按已认证 UUID 惰性启动独立 Web/DSH pair，各自持有数据根、状态、端口、内部密钥及凭据命名空间；DSH 仍是唯一研究引擎。首版仅 macOS Native，默认最多两个驻留实例且不自动驱逐；同 UID 的受信后端不是 OS 租户安全边界。账号与部署合同见[安装指南](research-web-installation.md#私网邀请制多用户macos-native)及[安全边界](architecture/research-web/05-security-validation.md#私网邀请制账号与执行边界)。

FinGPT 三策略复用唯一 DSH loop、原生历史及现有模型凭据。Host 仅冻结每轮要求、检查实际证据与文件并保存质量回执；补查沿当前原生回合，报告版本保留在会话 outputs，不增加研究引擎或正文库。

Host元数据专项升级通过显式 `resident upgrade-host-metadata` 入口执行；自动兼容清单与固定登录控制器artifact保持。专项只接受预期旧版02c086b16、PR122四个已审Host Git blob及同一受管Git源中的精确最新master。控制源必须干净且通过merged PR/独立评审/三CI实际tree核验；未知模块、依赖、Store或Host内容变化仍拒绝。既有bridge完成空闲栅栏、lifecycle lease、journal-before-stop、健康和回滚；成功后才记录baseline审核并刷新安装基线，不搬迁数据或凭据。

macOS 可选 resident 管理平面在用户登录后监督既有 Native Web/DSH，不增加研究引擎。
控制器使用固定 artifact、GitHub exact-tree 验证、同根 wheel 切换和原生命周期 lease；
研究准入共享锁先于生命周期锁，事务 journal 保证恢复优先。依赖/持久化/未知路径不自动升级。
配置与操作见[安装指南](research-web-installation.md#macos-登录后常驻与自动部署)。


本页只维护系统级边界。Research Web 的模块、协议、数据文件、安全和接口细节统一从 [Research Web 当前架构](architecture/research-web/README.md) 进入；旧平台的完整历史说明已归档。

## 当前产品边界

Mac mini 的 Docker 基座使用管理员 `rwb-docker`，dev/stage/prod 各自有身份账本、
数据/凭据/日志/cache卷和网络。dev挂载worktree，stage/prod固定不可变image ID；
唯一研究引擎与容器内 Web/DSH 回环不变。独立限额 BuildKit 和瞬时管理容器属于管理员平面，
业务与开发容器无 Docker socket。旧 Native/Docker 单实例管理合同保留，不能混用数据和账本。
资源、最短命令及 G2-G6 缺口见 [Docker 手册](research-web-docker.md)。

macOS 已存在的目标产品根可复用标准 OS 用户根中完整且已认证的不同根 Native 私有 pair。
共享 reader 的观察在真实目标 lifecycle lease 内保留目录/记录 FD 并复查，scope 退出失效；
未知与同根 writer 保留拒绝。部署节点、研究引擎、认证交换与持久 schema 不因此改变。

Docker 首装的无启动接受与首次启动分别使用同一现有生命周期入口内的 RAM 证明：前者只确认产品根缺失，后者必须实际私有 mkdir 并 pin 父目录/根 FD。证明不持久化或跨调用转移；已有根、已知容器、Native 记录或未知变化不获得 fresh 权限，部署节点与认证实现不变。

Research Workbench 当前交付的是本地优先的 Research Web，Native 与 Docker 只是同一产品的两种互斥部署：

```text
浏览器原生 UI
    ↓ 同源 HTTP / SSE
Research Web FastAPI Host（8088）
    ├─ 会话、文件、能力、DataHub、框架、集成与运维投影
    ├─ 按需签名桥 → 可选 Hot Node / PostgreSQL（原文、事件、唯一队列）
    └─ 私有 RPC / WebSocket
         ↓
项目专属 DSH Runtime（3081）
    └─ 唯一研究执行循环、历史、Skill、Tool 与子 Agent
```

- 入口：`app.research_web.main:app`。
- DSH 是唯一研究引擎；Research Web 不创建第二套 Agent 编排、聊天正文库或研究事实库。
- Native 以两个宿主进程运行 Web 与 DSH；Docker 以一个非 root 容器运行两者，仅向宿主回环发布 Web 8088，DSH 3081 留在容器内。`rwb runtime` 先按私有模式记录选择，再由 `rwb web` 按进程或容器归属管理；同一数据目录只允许顺序使用。
- Host 与 Runtime 保持回环访问边界；两种模式都不接管未知进程、容器或端口。
- macOS 启动链用私有 `install/endpoints.json` 记录健康后接受的实际回环端口。
  Native/Docker/最终模式选择共用 `run/lifecycle.lock`；元数据写锁在生命周期锁内短时获取。
  Docker 内部端口固定，只有宿主 Web 端口参与分配；可信控制 origin 的成对变更保留原 token。
- Docker 安装摘要绑定不可变 image ID、依赖锁、DSH/CJPY 与 Compose；公开启动和 Doctor 必须验证该已接受构建。构建候选使用独立 tag，启动等待真实健康后才发布选择；失败只回滚本次创建且再次确认归属的容器。
- Docker `/state` 使用私有 tmpfs，`/state/runtime` 在每次启动/重启由原认证链重建；日志单独持久绑定到 `/state/logs`，凭据仍为 `/run/rwb-secrets/private`。旧宿主状态保留，不迁移或自动清理；共享数据与 Native 路径不变。
- 基础研究不要求 PostgreSQL；启用 Hot 时，独立 PostgreSQL schema 承载原文、事件、预算和唯一持久队列。Host 桥是惰性、有界的，Hot 故障不接管基础设置或研究启动。pgvector、Tauri、桌面 sidecar 和旧 `app/api` 生命周期不进入本次 Web 交付。
- 当前阶段为 Web-only；只有修改桌面专属路径或用户重新开启桌面工作时，才应用桌面原生 CI 和安装级烟测。

## 主要子系统

ETF工程模拟由Host内 `portfolio_decisions/` 完成确定性信号、组合裁决和事务账本，真实准入保持BLOCKED。
合同见[数据与文件](architecture/research-web/03-data-files.md#etf-工程模拟与真实准入边界)。


[产品总图与分层图册](../outputs/research-web-architecture/index.html)先展示使用者、Web / DSH 及外部系统边界；各模块卡片继续连接说明、API、源码和测试。

| 子系统 | 源码 | 职责 | 权威文档 |
| --- | --- | --- | --- |
| Web Host 与协议 | `app/research_web/*.py` | API、SSE、会话投影、文件和安全边界 | [系统与运行时](architecture/research-web/README.md) |
| 双运行时入口 | `research_workbench_entrypoint/`、`runtimes/research_web.json`、`scripts/setup_web.py` | stdlib 模式选择、统一依赖合同和两条安装链 | [安装指南](research-web-installation.md) |
| Docker 部署 | `Dockerfile`、`compose.yaml`、`docker/` | 固定镜像、单容器监督、健康和隔离挂载 | [部署与职责](architecture/research-web/01-system.md) |
| 原生 UI | `app/research_web/ui/` | 产品壳、研究、能力、设置和运维页面 | [UI 合同](research-web-ui.md) |
| DataHub | `app/research_web/datahub/`、`integrations/` | 静态目录、Provider、动态选源、探测和会话快照 | [DataHub](research-web-datahub.md) |
| 研究框架 | `app/research_web/frameworks/` | Gold／Dollar 专用定义、采集、快照、评分与 Bot 绑定 | [研究框架](architecture/research-web/08-research-frameworks.md) |
| 能力与方法 | `app/research_web/capabilities/`、`skills/` | Skill、Method、Tool、Workflow 的版本与发现 | [能力管理](architecture/research-web/07-capabilities.md) |
| MCP 与自动化 | `mcp_registry/`、`mcp_runtime/`、`automation/` | 目录、受控安装/调用和定时执行 | [Research Web 架构](architecture/research-web/README.md) |
| 报告 Workflow | `report_workflows/` | 模板、底稿、运行、Excel 刷新和独立交付 | [文件与交付](architecture/research-web/03-data-files.md) |

## 数据与信任边界

- DSH 原生日志持有研究正文和执行事件；产品索引只保存归属、状态、版本、文件和审计指针。
- 用户上传、DataHub 快照、能力资源和产物使用产品数据根内的受控相对路径；普通 API 不接受任意本机路径。
- Native 密钥只进入产品设置和宿主凭据库；Docker 使用独立私有容器凭据目录，不自动跨模式迁移。迁移、日志、快照和浏览器响应均不得回填秘密。
- DataHub 的登记、配置、授权、探测、适配和当前可调用是不同事实；目录存在不等于真实连接已验证。
- 框架快照绑定方法版本和 revision；旧会话不得混用新快照。

## 兼容平台

仓库仍保留 `app/api/`、`app/web/`、`core/`、`services/`、`data_layer/`、`storage/`、`signal_lab/` 等旧模块化单体代码，用于历史兼容、桌面维护和既有数据流程。它们是实际代码，但不是当前 Research Web 的启动链或新增能力默认依赖。

兼容平台的文件级历史说明位于 [归档](archive/README.md)；仍需维护的模块合同位于 `docs/modules/`、`DATA_STORAGE.md` 和各专项文档。任何把兼容代码重新接入当前产品的工作都必须先更新本边界和 Research Web 架构清单。

## 文档与验证

- 双运行时 Python 质量整理只涉及现有文件的格式、导入顺序、显式默认值与内部类型说明。
  进程、目录、认证、控制事务和回滚的原有边界不因此改变；类型检查债务与实际生命周期证据分开记录。
- [Development Map](DEVELOPMENT_MAP.md) 映射源码区域、权威文档和测试。
- [文档门禁](research-web-documentation.md) 校验文档分类、权威唯一性、链接、退役命令、生成索引和 Research Web 架构清单。
- `.ai/reports/` 保存每次任务的真实命令、结果和架构影响；`CHANGELOG.md` 只保留用户可见变化。
