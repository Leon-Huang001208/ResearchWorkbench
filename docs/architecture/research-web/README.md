# Research Workbench Research Web 当前架构

公开来源正文和报告修订继续沿原 DSH 工具、Host 证据与规范文件链路运行。真实取证、不可核验摘要和完整性错误分开；同回合补查报告与历史报告均绑定具体字节及原检查回执，详见 02–05 章。

业务脚本修复仍沿同一DSH执行与Host质量链：选择器统一实际观测/要求映射，工作簿按固定Summary结构原子写入，CPI与NIST证据扩展只来自实际上传字节。脚本、文件与严格拒绝边界分别见02、03、05；离线回归不能代替真实四用户业务验收。

实际报告恢复仍沿现有resources、冻结合同及Host独立评分链；派生只读投影格式见03-data-files，安全及来源定位边界见05-security-validation。

实际业务报告的来源、算术和引用预检查复用原报告资源与DSH回合，独立工作簿验收器的展示规则不传入Host。执行状态、研究质量与下载交付仍分开，详见[数据合同](03-data-files.md#实际业务证据预检查)。

受限业务摘录的表头/分数/计数规范化扩展既有Host观测适配，保留原文及作用域，不建立另一研究引擎；不认证外部真实性或模型的中文推断。原逐句/精确算术门与一次补查保持，新增跨父来源与输入变化拒绝。

CSV报告可在原DSH回合使用显式证据格式helper，章节/claim/notes/coverage按实际观测组装；验收、缺口和原文件交付仍由既有Host独立负责，见[数据合同](03-data-files.md#受限csv计算证据)。Automation不增加执行节点或权限。

报告修订沿原会话归档与质量边界运行：相对输出路径无需 getcwd，当前报告由规范文件映射确定，备用同名文件与历史归档分别保留。

质量核验仍由同一Host和DSH研究回合完成：规范来源元数据、受限全量CSV独立复算和输出变化后的严格重验不增加执行引擎。Automation、公开安装入口和模型配置合同保持。

可选[私网邀请制多用户](../../research-web-installation.md#私网邀请制多用户macos-native)在原研究 UI 前增加账号网关；每个已认证用户独立 Web/DSH、文件和凭据，账号数据库不保存聊天正文。首版仅 macOS Native、管理员开账号、默认两实例；同 UID 后端仍受信任，不宣称公网或 OS 多租户隔离。详细授权、账号 API 和存储分别见 05、04、03 章。

FinGPT 快速/深入/Agent 共用原生 DSH、模型设置及历史，Host 质量回执与报告版本仍属于既有会话文件和验收边界。执行、质量及文件状态分别呈现；Claw/Automation 执行机制保持原合同。

Host元数据专项升级通过显式 `resident upgrade-host-metadata` 入口执行；自动兼容清单与固定登录控制器artifact保持。专项只接受预期旧版02c086b16、PR122四个已审Host Git blob及同一受管Git源中的精确最新master。控制源必须干净且通过merged PR/独立评审/三CI实际tree核验；未知模块、依赖、Store或Host内容变化仍拒绝。既有bridge完成空闲栅栏、lifecycle lease、journal-before-stop、健康和回滚；成功后才记录baseline审核并刷新安装基线，不搬迁数据或凭据。

会话侧栏和逐题问答统一到现有原生UI；导航元数据只由Host按模式隔离保存。日程/自动化执行仍走原DSH与显式授权，置顶、项目排序或跳过问题不授权试跑。

搜索继续由原生 DSH 派生索引处理，Host 限定授权范围，UI 明示未搜索记录计数；保持唯一 Automation 调度层。

macOS登录常驻沿用同一Native部署节点与研究引擎；短时管理程序处理空闲切换和恢复，
不增加第二Automation scheduler。操作与授权边界见[安装指南](../../research-web-installation.md#macos-登录后常驻与自动部署)。

Claw 的 Codex 式执行流仍只投影原生消息、活动与 Automation Run。显式试跑语法修复与有界错误码传播不增加调度器、研究引擎、接口或数据库；提问回执、输入表面及逐步详情见[UI合同](../../research-web-ui.md)。

正文搜索通过只读 Host POST 接口复用固定 DSH 的 `session.search` 与首次搜索打开的派生内存索引；只返回本产品已成功创建且未删除的会话片段，不将结果自动注入其他研究。协议与归属边界见[研究运行时](02-research-runtime.md)和[接口清单](04-api.md)。

本轮融合外部来源、兼容模型协议与交互修复，仍以 DSH 为唯一执行循环。
认证 HTTPS、秘密反射拒绝、明确脚本成功及精确工具准入见[安全边界](05-security-validation.md)；
Claw 项目、研究深度/资料范围、原生 Todo 和 HTML/Word/中文 PDF 合同保持。

Hot周期简报的Automation管理aliases由Hot自己的配置/签名权限控制，独立于旧`RESEARCH_AUTOMATIONS_ENABLED`开关。关闭旧调度不隐藏Hot计划，也不启动旧Store、付费研究或外发；站内唯一Hot scheduler与原ResearchService/DSH归属保持。

Hot关注/周期计划复用现有Node、PostgreSQL与唯一队列。Automation仅适配用户管理入口；周期调度不写旧Store，也不创建第二研究引擎。schema19/20、权限、回放与截止资料合同见Hot组件README；正常Native已产出宏观周期简报，AI旧材料超窗如实为空；完整Goal仍须当前AI事件、恢复复验、最终Docker与当前候选Mac CI/完整审核证据。

Hot模型流预算桥已接入overlay和私有Host API，准备会话与预算准入分开。
离线SSE只证明SDK机制与回执顺序；正常Runtime零重试及真实研究尚未跑通，完整Goal继续。

Hot 的持久研究映射与受控交接准备现在适配同一 ResearchService/DataHub：固定目标身份、
完整原件副本及目录核验可恢复。它尚不启动付费研究或报告；既有 Automation 调度与
create/send 路径保持，Hot 周期任务的 Automation 适配仍待实现，见图11和权威进度报告。

显式文本验收预算复用已有私有模型桥与受管 AES 身份，持久票据不退款。旧政策过期，真实验收未启用；预算不是运行实例管理或产品推理 PASS。

原生研究计划复用既有 DSH 与 FinGPT 计划标签；历史分页和 SSE 缓存保留同序号冲突证据，
坏快照不显示已确认计划。此内存恢复改动不新增 Automation 调度或改变日程草稿确认边界。

G2A 为受管 Docker 增加固定模型 ref 的实例加密后端及主密钥只读卷，仍由原 Web→DSH
私有 stdio 桥调用。生成、重建和隔离证据分别记录，Native Keychain 与原 Automation 合同保留。

研究台增加ETF工程模拟切片，确定性策略、约束、事务账本及回放均在同一Host内，真实链路保持BLOCKED。
合同见[数据与文件](03-data-files.md#etf-工程模拟与真实准入边界)。

Claw工作区只替换侧栏，中央聊天/草稿保持；文件MD预览复用Host原端点并以纯文本供沙箱显示。Host受理后附加当前时钟但不作为来源/交易日证据；DataHub未适配来源返回明确503。它们不新增服务、调度层、存储schema或研究执行器，详细合同见下列UI、运行时、文件和API模块。

Claw 全页面调查与回答修复继续复用原生事件、版本化 Run 与能力中心。工具目录、执行快照和安全活动投影见[运行时](02-research-runtime.md)、[API](04-api.md)与[安全](05-security-validation.md)；参考站点未观察的接口和状态单独保留未知，不构成本产品行为证据。

本轮 Claw 日程采用直接 `research_task`（schema_version=1），锁定研究描述、模型、输出要求、资料与工具白名单。用户确认创建并启用后才生效，创建不立即运行；旧 Skill/Workflow/报告任务保持兼容。修改以同一 ID、expected_version 和变更确认卡生成新定义版本，Run 保留不可变 definition_snapshot；手动试跑与 schedule 触发分别记录，不改下一次计划时间。能力与连接管理统一在能力中心，Claw 仅选择能力，Agent 日程使用独立表格。DSH 仍是唯一研究引擎，Automation 仍是唯一调度层。


模型空闲检查区分已核实活动与历史执行模式；详情/执行仍按原严格模式校验。内部查询范围及失败关闭条件见[运行时](02-research-runtime.md)与[安全验证](05-security-validation.md)，无公开协议或持久格式变化。

Claw 本地研究项目和可确认日程草稿复用现有 Host 索引、文件目录、Automation 与 DSH。项目归属不改变执行目录，跨会话文件必须显式引用；详见[文件](03-data-files.md)、[API](04-api.md)和[UI](../../research-web-ui.md)。

Automation 对普通原生会话和报告 Run 的关联现在在已知后立即原子保存；恢复只监控同一已证明任务，不重新 create/send。报告归属、版本与校验状态仍由既有报告 Runtime 决定；提交未知或关联持久化失败保留失败状态。本次不新增执行器、调度器、API 或持久 schema。

这是当前研究产品的唯一架构主入口。Research Web 组织研究页面、框架、能力与文件，专属 DSH 是唯一研究执行循环。当前任务按 macOS Native / Mac Docker Desktop 与 Windows/Linux 对应设备分工验收；源码同时保留 `app/research_web/`、`research_workbench_entrypoint/`、`docker/` 与共用运行合同，Docker 实现按运行宿主与镜像架构分别验收；未验证项见 [支持矩阵](../../research-web-platform-support.md)。Native 双宿主进程与 Docker 单容器是互斥运行方式，顺序共享产品数据。旧 `app/api`、量化业务和 merged-platform 图文保持历史身份，不作为本入口依赖。

当前固定 DSH 为 Fork 提交 `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`（0.2.1-alpha.1），版本以 `runtimes/research_web.json` 为唯一来源。owned overlay 通过原生声明式 preset registry 挂载既有 research-web、framework-explain、framework-verify；仍由同一 Host、Runtime、DataHub 和协调器执行，Automation 不另建调度路径。升级验收针对独立 macOS Native 实例，不表示生产实例已经更新。

设置中的模型服务只展示固定DSH实际支持目录，保存与显式生成分别验收。配置和测试共用ResearchService串行边界；既有Automation仍通过相同create/send执行，新会话采用新默认值，活动任务阻止共享凭据变化。macOS Native 的固定模型 ref 由产品 provider/私有进程桥接存入系统 Keychain；Host 认证 record 保留固定 DSH 的独立文件实现。没有新增执行器、调度器或凭据中心。

内部控制 parser 提取为标准库基础接口，DataHub/MCP 原 wrappers 保持读写、异常与权限合同；
macOS实际端点/origin事务现接入公开CLI启动链；同一产品部署和业务调用图保持，HTTP API不变。
停止Docker容器换绑定与真实平台验收的未完成项见安装文档及本轮任务报告。

这是当前研究产品的唯一架构主入口。现役源码覆盖 `app/research_web/`、`research_workbench_entrypoint/`、`docker/` 与共用运行合同；旧 `app/api`、量化业务和 merged-platform 图文属于历史，不是此入口的依赖。Native 双宿主进程与 Docker 单容器是同一 Research Web/DSH 产品的互斥运行方式，顺序共享产品数据，不创建第二个研究引擎。

研究布局、能力中心与架构更新检查已实施。当前 Web 包含研究台按需数据入口、独立资产观察、Claw 具体报告 Workflow、会话快照交接、实际产物及只读“运行与用量”聚合；DataHub 同时迁入天软 CJPY 的四项已实现能力，并加入只复用现有 WindAdapter 封闭方法的受限 Wind binding，缺少本机依赖、登录或等价字段口径时仍失败关闭。东方财富基金和财联社是当前无需专业配置即可真实调用的来源。研究脚本由宿主 FIFO 串行、Python 3.12 readiness 和 `cpu_bounded_v1` 公共预算约定共同约束；不依赖 GPU，Seatbelt 仍仅支持 macOS。Phase 2A 提供只读 MCP Registry；Phase 2B 增加不可变安装、官方 SDK Host、OAuth、工具分级、会话授权、人工审批和 DSH 原子激活回滚；Phase 2C 增加锁定版本的通用 Automation、独立 Claw Run 与研究/投递双状态。当前限制见 [架构状态](status.md)，逐任务证据进入 `.ai/reports/`。图形通过不替代产品、数据覆盖或真实连接审查。

## 阅读顺序

Docker 模型凭据由 owned overlay 显式绑定加密文件桥，固定 ref、私有目录守卫和 Host
认证边界沿用既有合同；Native 不回退到该后端。密钥存储、重启恢复和真实模型输出分别验收，
细节见[运行时](02-research-runtime.md)、[文件](03-data-files.md)与[安全验证](05-security-validation.md)。

首次阅读先打开[交互图册](../../../outputs/research-web-architecture/index.html)：产品/系统总览 → 运行结构与部署 → 子系统分图 → 关键业务流程 → API 与代码细节。重要模块的阅读卡片使用稳定标识，将职责、分图、说明、API、源码和测试放在同一入口。

前端外观以 [Research Web 外观与主题](../../research-web-appearance.md) 为准：Codex 风格、Light/Dark 与用户原图符号；不改变下述服务部署和研究契约。

1. [部署与职责](01-system.md)：启动路径、模块边界和存储归属。
2. [研究协议与状态](02-research-runtime.md)：提交、SSE、恢复、审批、停止及页面交接。
3. [数据与文件](03-data-files.md)：研究台、DataHub 静态目录、路由、资料快照、附件、产物和独立交付。
4. [接口清单](04-api.md)：当前路由与请求边界。
5. [安全与验证](05-security-validation.md)：可执行边界、测试层次与未覆盖部署。
6. [文档清单契约](06-documentation-contract.md)：仓库内门禁、更新标记与负向验收。
7. [能力管理](07-capabilities.md)：Skill、Tool、Workflow、数据目录，及包、版本、原生发现和会话只读资源。
8. [运行与用量](../../research-web-operations.md)：真实 usage、Agent、工具、DataHub、服务健康和项目存储聚合。
9. [研究框架](08-research-frameworks.md)：Gold/Dollar Hub、连续专属画布、真实采集、快照 Bot 与渐进抽象边界。
10. [统一集成协调器](09-integration-coordinator.md)：数据源与本机能力的五阶段状态、启动/手动探测、授权和持久证据。
11. [Web Native/Docker 安装](../../research-web-installation.md)：共用依赖合同、模式切换、固定 DSH/CJPY、Doctor 与分模式平台门禁。

可交互图文位于仓库 `outputs/research-web-architecture/`，也可从 Web 设置的「架构文档」打开。JSON 图源在本目录 `diagrams/`。既有十图与新增 `00-system-overview` 均以实际源码为依据；`01-deployment` 展示单一源码与数据模型下的 Native/Docker 分支。各图的自动 showcase、四视口和人工截图结论以各自当前哈希回执为准；图形证据与产品、镜像和平台验收分开保存。

## 不在本轮范围

不新增 PostgreSQL 前置条件、Evidence/Claim、第二研究引擎、线上 Skill 商店或桌面适配。MCP Registry 身份保持 `(registry_id, server_name, version)`；第三方字段按有界纯文本处理且不热链图标。Publisher 只生成外部 CLI 交接材料并明确 `executed:false`。MCP 不实现 sampling、elicitation、实验性 Tasks、任意 shell、版本范围、隐式环境继承或无人值守高风险调用；Automation 不静默升级目标、不自动重试研究，也不批量追赶遗漏。研究台市场页是按需查询和快照入口，不是旧市场首页或后台行情管线。

## 启动与验收基线

新用户可优先运行 `./setup-web.sh --runtime docker`；`./setup-web.sh --runtime native` 与无参数入口保留 Native。Windows 对应 `setup-web.cmd --runtime native|docker`，但真实 Windows Docker 生命周期未在本轮验证。安装器不会写入全局 Python/Node。随后从仓库根目录使用项目命令。管理器仅处理所有权可证实的项目进程或容器，端口已有其他服务时直接失败：

```bash
./rwb runtime status --json
./rwb runtime use docker
./rwb web start
./rwb web status
./rwb web restart
./rwb web stop
```

模型仅在产品设置中授权。Native 专属运行时与 Web 的默认宿主回环端口为 3081/8088；macOS 自动启动可选择空闲端口，并在真实健康后写入私有端点账本。Docker 内部 Web/DSH 固定为 8088/3081，只发布宿主回环 Web 端口。用户原 3080 不被更改。后台状态、凭据和日志按运行模式隔离；研究数据位于共用 `~/.research-workbench/research-web/`。切换前需安全停止旧模式，不在两个模式下并发访问数据。

旧研究目录先用 `rwb migrate-research-data --dry-run` 查看迁移摘要，再执行复制。凭据不会迁移；新实例需在设置页重新填写。Web 恢复验证通过后可使用 `--archive-source` 将旧目录改为只读迁移备份。

日期型验收、具体会话和任务命令位于 `.ai/reports/`；历史 Research Web 验收已进入 [归档](../../archive/acceptance/research-web-acceptance-2026-09-02.md)。这些记录只证明当时的环境和路径，不能替代当前任务复验。

## 当前验收原则

- 文件结构有效不等于报告内容合同完整；运行、交付和内容质量分别记录。
- 外部数据、模型、Office/Wind、浏览器和平台支持只对本次实际验证的环境成立。
- 旧分支、会话、产物或验收记录不决定当前 Git 交付状态；每次交付以本次 Harness、CI 和任务报告为准。

## 历史证据

日期型稳定性核对已移至[阶段一任务报告](../../../.ai/reports/2026-10-06-architecture-reading-stage1.md)。

## 设置闭环阶段3：当前能力范围

现有Host/DataHub私有通道同时承担能力准入；DSH通过工具执行与原生用户技能注入的既有事件重检。没有新增研究引擎、来源注册中心或Vault。


## 单一兼容模型连接

单一兼容文本/流式模型适配位于既有Runtime，私有非秘密配置沿同一Host/DataHub通道读取，系统ref仍沿原进程桥接；没有新增研究引擎、模型代理daemon或Vault。Native macOS合成冷启动与真实供应商验收分别记录；本模型连接任务未执行其他平台验收，项目总平台范围以支持矩阵为准。

Hot FinGPT冻结研究采用research-hot-frozen的轻量DSH composition，仅本地脚本/文档工具；Claw与普通研究保持research-web。原预算/guard/沙箱/回执不变，不新增研究引擎或Automation调度。

## FinGPT 研究融合 · 2026-10-13

FinGPT 研究深度、原生计划与会话底稿参见 02-research-runtime、03-data-files、04-api 和 05-security-validation。Automation 继续调用同一会话/报告运行服务；本次新增 PDF 格式，不改变调度、投递或生命周期成功判定。

## 历史子会话模式兼容 · 2026-10-13

历史子模式兼容只调整读取投影，原生协议与控制边界见02-research-runtime和05-security-validation；服务与模块结构不变。
