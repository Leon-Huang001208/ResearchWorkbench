# 阶段一：架构生成同步与分层阅读

## 当前状态（2026-10-07）

- 阶段一：未完成；阶段二、三未启动。
- hostPlatform: macOS (Darwin)；taskKind: 功能开发。
- taskId: task-20261006-992c74ec267b。
- worktree: `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/task-20261006-992c74ec267b`。
- branch: `codex/task-20261006-992c74ec267b-architecture-reading-stage1`。
- 开始基线与图示源码：`211703cca660172b524eff804cc547458529858e`；新观察远端 master：`ddcdd9784d8eda2918b8987ca8b679375e67291d`。PR #80 已由独立任务合并，本任务未修改该 PR；送审前仍需集成最新主线。
- 1A/1B/1C 实现已落地，清单 186 个唯一 Method + Path / 188 项声明；数字不是验收常量。
- 本轮新增验证：架构 72 项（新增悬空链接及登记/允许列表 fixture）；相关 L4 Node 合同 100/100 PASS；生成完整内容一致性 PASS；实际 HTTP 安全边界 10/10 PASS；Python 语法编译 PASS。
- 真实浏览器：Settings → 架构文档分类 → 新页图册 → 总图/分图/返回 → 框架及协调器正确 API 分类 PASS；固定基线版本的说明、源码、测试均实际点击并 HTTP 200。独立 Web 18088 禁用 lifespan，验证的是阅读面，不是 Runtime 产品 ready。
- 独立审查：生成器悬空符号链接 P2 和外部导航错误误报 BLOCKED 的 P2 均已修复并获只读复核；无新增具体问题。详见独立审查报告。
- 总图图源/HTML/四视口/四截图与用户确认仍匹配；用户人工审阅 PASS；自动 visualReview 保持 pending。既有图只复用同哈希证据。
- Python pytest、Ruff、Black、isort、mypy：NOT_RUN。安装早已获用户授权，但本轮正常 pip 路径仍被已加载的 leon-engineering Guard 拒绝；配置 enabled=false 尚未成为当前宿主实际行为。未绕过 Hook，未将环境错误当测试 RED。
- hostAcceptance: BLOCKED（Python 验证与同平台 CI 未完成）；aggregateAcceptance: NOT_READY；Windows/Linux NOT_RUN 保留。
- PR/CI/merge/生产实例：本任务均未执行。仓库当前 PUBLIC，Actions 预算门不是阻塞。需要本地候选及最新主线集成后，沿既有送审入口取得本候选 macOS Bootstrap 实际 checkout 证据；不得借旧提交/Ubuntu run 认证 Mac。
- 授权：独立测试依赖安装与 Guard 禁用已获明确授权，不能再次要求用户安装同一包；远端具体候选动作按本轮 Goal 与已有授权边界执行。

<!-- architecture-review {"group":"documentation","structure":"changed","reason":"清单派生首页和API图册，新增产品边界视图并登记安全只读入口与返回导航。","diagrams":["00-system-overview"]} -->

## 移出的过程记录

下列段落原先置于现役说明开头或日期型尾节，本轮移到任务报告保留追溯；现役说明先解释职责与边界。

### docs/architecture/research-web/08-research-frameworks.md 原开头

模型设置更新只影响新建Bot会话的默认模型，已有Gold/Dollar会话保留选模；活动父/子任务阻止共享凭据变化。模型生成测试复用无研究工具的框架解释preset，但不绑定业务快照、不改变确定性评分或框架采集。测试通过只证明指定模型生成，不证明框架数据能力。

Native 和 Docker 复用 Gold/Dollar 的定义、快照 revision、评分、renderer 和 Bot 请求合同。
模式只改变同一 3081/8088 服务的部署位置；Docker 单容器健康检查同时要求两项服务 ready，
但框架采集是否取得真实外部数据仍由各自来源与缺口规则判断。Docker 健康通过不证明宿主
Office/Wind 等可选集成可用，也不构成 Windows Docker 验收。

2026-09-29 启动稳定性变更只调整 Research Web/DSH 的进程归属、恢复与页面 ready 判定。
Gold/Dollar 仍由同一 3081 Runtime 和 8088 Host 执行；定义、采集器、调度、快照 schema/revision、
评分、renderer、Bot 会话绑定和框架图源均未改变。模型未配置时 Web 设置页可访问，不代表框架
解释或深度验证已经可调用；该能力继续由真实 Runtime、模型及快照状态决定。
未安装环境的顶层 `rwb --help` 只输出静态诊断指引，不加载 Gold/Dollar 定义、采集器、快照
或 Bot；本轮 CI 修复不改变框架版本和页面合同。

Web 一键安装只统一运行依赖和固定 DSH 构建；Gold/Dollar 的定义、采集、快照 schema、评分、
renderer 与 Bot 会话绑定均未变化。框架仍由同一 3081 Runtime 和 8088 Host 执行。
启动前 Doctor 门只阻止未完成安装的 checkout 创建共享 Runtime；通过后仍沿用同一框架注册表、
调度器和快照协议，不增加框架进程或改变评分、renderer 与 Bot 会话绑定。
Runtime build lock 只绑定同一已验证 DSH 闭包；锁修复不修改 Gold/Dollar 定义、快照 revision 或调度频率。
全新 DSH `web` Profile 初始化、Windows junction containment 和 PowerShell PID 探针只保证这条唯一 Runtime 可启动/停止，不改变
Gold、Dollar 的注册、采集、评分、快照或页面协议。
Office/Wind 验证 timeout 的跨平台浮点上界修正只作用于本机集成验证器，不进入框架采集、评分、
renderer 或 Bot 会话。
`rwb web status` 不再因服务管理器导入而加载 Runtime Capability/MCP 功能图；这只缩短停止态诊断
路径，不改变 Gold/Dollar 注册、调度、快照、评分、renderer 或 Bot 预设。
安装阶段的 Web import readiness 可以加载框架定义以证明入口完整，但不进入 FastAPI lifespan，
因此不会启动采集调度、读取外部来源、写快照或创建 Bot 会话。


### docs/architecture/research-web/08-research-frameworks.md 日期型尾节

## 2026-09-23 稳定性变更回执

本轮重启活动授权、会话目录有界读取和各目录独立的 pending count/generation、逐资源 settled、
latest-request-wins 只作用于既有服务管理、目录聚合与 UI 状态；runtime-only 的可见
connecting/offline 不进入框架状态。Gold/Dollar 的定义、采集器、调度、快照 schema/revision、
评分、renderer、Bot 会话绑定及页面信息架构均未变化；不需要修改框架图源或制造新的运行节点。

## 2026-09-28 Windows 停止兼容回执

服务管理器对已归属 Windows 进程的非强制停止失败增加既有 `/F` 升级路径；Gold/Dollar 的定义、
采集、调度、快照、评分、renderer 和 Bot 绑定均未改变，框架仍不拥有独立服务进程。

### docs/architecture/research-web/09-integration-coordinator.md 原开头

模型配置页的保存、Runtime应用、凭据与真实生成结果来自既有ResearchService，不加入第二套来源注册或五阶段协调器。模型生成成功不改变任何数据来源/本机能力的授权与可调用投影；模型凭据回执未知时阻断模型请求，来源探测仍按原合同独立报告。

Native 使用宿主 keyring；Docker 在显式配置的私有凭据目录中保存 DataHub 秘密，协调器只读取
DataHub 的安全状态投影，仍以登记、授权、探测、适配、可调用五阶段判定结果。两模式顺序共享
产品数据，但凭据不自动迁移；Docker 容器无法仅凭可见目录证明宿主 Wind、Office、Tabbit
或系统会话可用。Windows Docker 凭据目录 ACL 未能证明时安装失败关闭，不能把来源提升为
`runtime_callable`。

2026-09-29 的启动恢复只影响受管 3081/8088 的进程与页面可访问状态，不改变协调器五阶段状态、
责任桶、来源授权、批次并发、快照或 DataHub 动态选源。Doctor 的 `product_ready` 证明 Web 壳与
Runtime 协议可访问，不证明 Wind、天软、MySQL 或其他来源当前可调用；各来源仍须按现有配置、
授权与真实探测结果单独投影。
未安装环境的顶层 `rwb --help` 不初始化协调器、不恢复快照或发起来源探测；本轮 CI 修复
不改变五阶段状态和责任归因。

一键安装为协调器提供可复现的 Web 依赖与 CJPY 0.5.2，但不把“已安装”当成探测或可调用成功。
没有 `CJ_KEY` 时天软保持待用户配置；保存后的秘密由凭据库在每次探测/查询时动态读取，协调器仍
按既有五阶段模型和责任归因记录结果。
安装器对 Windows DSH checkout 启用命令级长路径，Runtime 首次启动先初始化固定 `web` Profile；
Profile junction containment 与 PowerShell PID 探针仅保证 Windows 3081 安全启动和回收；
这些修复只保证协调器所在 8088/3081 可复现启动，不把任何来源状态提升为可调用。
服务管理器在 spawn 前校验 Doctor 安装事实；安装未就绪时协调器和启动探测都不会创建。
该前置门不把 CJPY 已安装、数据源已登记或历史探测快照误报为当前可调用。
Node 选择与 Runtime build lock 的一致性只决定 3081 是否可安全启动，不改变协调器五阶段状态、
授权或 Provider 可调用结论。
纯 `rwb web status` 的导入不创建协调器，也不加载 Capability、MCP 或 DataHub Runtime 功能图；
Doctor、start 与 8088 Host 仍在各自既有边界内加载并验证这些组件。
安装阶段的 Web import readiness 不运行 lifespan 或协调器启动探测，不读取凭据，也不把任何来源
从已安装提升为已配置、已验证或当前可调用。


### docs/architecture/research-web/09-integration-coordinator.md 日期型尾节

## 2026-09-23 稳定性变更回执

本轮服务重启活动门禁、会话/子 Agent 目录有界读取和浏览器目录加载呈现均不进入
`IntegrationCoordinator`。五阶段状态、五类责任桶、探测授权、批次并发、快照持久化、DataHub
动态选源和 Tabbit 双状态关系均未变化；无需修改协调器 API、Automation 关系或架构图。

## 2026-09-28 Windows 停止兼容回执

Windows 服务管理器只对已经归属核对的进程在非强制停止失败后升级 `/F`；该变化不改变协调器五阶段
状态、责任归因、探测/授权、Provider callable 或本机集成真实验证结果。

### 架构 README 原日期型尾节


本轮只收紧非强制重启的活动会话授权、会话/子 Agent 目录的并发有界读取，以及前端每个目录独立的
pending count、generation、逐资源 settled 与 latest-request-wins 账本。只有 runtime pending 和
settled runtime failure 分别投影为可见 connecting/offline。阅读顺序、文档权威关系、十图清单、
模块边界、Automation 与信息架构均未变化；外部 CI 和真实浏览器验收另由后续交付阶段记录。

## 后续进展（2026-10-07）

- 1A 架构合同扩展至 68/68；删除、等量替换、Method/路径/领域、缺产物、稳定生成、只读和文本/URL安全均有独立 fixture。
- 产品总图 showcase 9/9，四视口与四截图通过；用户明确确认已查看最终浅色/深色截图并通过人工审阅。
- 架构 changed-set 检查当前 violations=[]；治理检查通过。
- 测试依赖安装已获用户授权，但 PreToolUse Hook 拒绝 pip 操作且要求用户手动执行，未安装。该错误不计作测试 RED，Python 验收仍 NOT_RUN。
- 对 Bootstrap workflow 的候选修改被 Hook 拒绝，未改动 workflow；后续使用已有入口，远端动作须单独明确授权。

## 重启交接

- 原始 Goal 保持 active，阶段一未完成，阶段二/三不启动。
- 工作区：`/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/task-20261006-992c74ec267b`。
- 分支：`codex/task-20261006-992c74ec267b-architecture-reading-stage1`。
- 已完成：生成器/只读检查与 fixture、产品总图、登记视图门禁、安全返回导航、分层模块入口与现役说明整理。
- 94 项 Node 合同 PASS；完整 changed-set Project Constraints violations=[]；生成一致性、文档同步和 Python 索引 PASS。实际输出保留在 `logs/stage1/`。
- CUA 浏览器验证：总图加载 → 固定模块返回入口 → 研究框架 API 分类显示正确且只显示框架条目。外部 GitHub 源码点击超时，没有声称通过。完整 Settings 起点和 E2E 仍待继续。
- Python pytest、ruff/black/isort/mypy：NOT_RUN，现有环境缺少测试工具。用户已授权独立测试环境安装。
- 用户明确要求关闭自动审批 Hook；仅 `/Users/leon/.codex/config.toml` 的 `leon-engineering@leon-local:hooks/hooks.json:pre_tool_use:0:0` 加 `enabled=false`。Harness 保留；TOML 解析 PASS。备份为同目录 `config.toml.backup-guard-20261007`。当前会话再次拒绝安装，证明宿主仍使用旧已加载 Hook；需要重启或新会话。
- 已创建空测试 venv `/private/tmp/rwb-stage1-test-992c74ec`；包未安装。新会话正常安装已授权 pytest/pytest-asyncio/pytest-cov/ruff/black/isort/mypy，不修改产品依赖。
- GitHub CI：NOT_RUN；PR/merge/运行实例更新均未执行。远端动作必须先读取 Actions 预算并核对 public，再对具体候选取得授权。不得直接改写 PR #80。
- 下一步：完成 Python 目标测试与格式检查、完整 Settings/E2E、安全路由和允许列表一致性、独立代码审查；用完整 changed set 更新 plan/receipt；固定被说明源码与生成物提交身份；再取得实际 macOS CI 和最终交付回执。
- 本平台验收 IN_PROGRESS，总体验收 NOT_READY，Windows/Linux NOT_RUN 交接保留。

- 收尾追加：policy 选中的本地 L4 Node 合同 96/96 PASS（含 repository cross-platform contracts）；这不是 Windows/Linux 真机证据。独立 18088 验证服务已停止，不更新生产实例。

## 创建时的状态（历史，不作为当前结论）

# 阶段一：架构生成同步与分层阅读

- hostPlatform: macOS (Darwin)
- taskKind: 功能开发
- baseCommit: 211703cca660172b524eff804cc547458529858e
- taskId: task-20261006-992c74ec267b
- 范围：1A 生成一致性、1B 总览与视图登记、1C 安全导航；阶段二、三未激活。
- 决策：复用 architecture-map、Archify 2.14 和现有门禁，不建立第二套文档框架。固定源码版本的仓库链接承担 Markdown/源码/测试阅读，不开放任意本地文件服务。
- 1A RED：新增两项 fixture 均失败，复现 check 写日志和等量错误集合未检出；GREEN：架构 65/65。
- 统计：当前完整 inventory 为 186 个唯一 Method + Path / 188 项声明，不作为测试常量。
- Python 验证准备失败：现有 Web .venv 无 pytest；未将环境错误算作测试 RED，正在等待独立测试依赖安装授权。
- 视觉：新图实际查看由 Codex Agent 记录；不是用户或人工签字。自动 visualReview 保持 pending。既有图复用基线同哈希证据。
- hostAcceptance: IN_PROGRESS；CI 与最终候选待记录。
- platformHandoffs: Windows / Linux NOT_RUN，本任务不启动对应适配。
- aggregateAcceptance: NOT_READY；本平台通过不推导跨平台支持。


## 本轮独立审查修复与证据

- RED：`logs/stage1/dangling-red.log` 实际复现 index 输出悬空链接被错误放行；GREEN：`architecture-after-review.log`、`registry-and-dangling-green.log` 与最终 98/98 合同。
- 生成器逐级 lstat，仅 ENOENT 允许待创建；输出与日志统一预检，不跟随悬空链接。
- checker 对静态 DOCUMENT_NAMES 与 index、API Atlas、全部登记视图作实际集合等价；缺失、额外、重复、非字面量不能作为有效允许列表。
- 浏览器脚本按当前 Settings 分类导航，覆盖两领域筛选和真实仓库点击；导航阶段网络/服务阻塞与断言、404、截图写入失败分开计账，failed 优先。
- HTTP smoke 初次因脚本 header 名大小写处理错误失败；改为规范化 header 后 10/10。未把脚本错误记为产品缺陷。
- 使用已存在的 bundled Playwright 完成浏览器验证，无安装新 Node 包。测试环境包未安装，产品依赖和生产实例未变更。
- 后续：在实际停用 Guard 的新宿主继续已授权 Python 工具安装及 pytest/lint/type；按完整 changed set 更新回执；最新主线集成；固定源码→生成物候选；本候选送审及 macOS CI；最终完整性/交付审计。

## 当前本地收口回执

- 完整 changed set 的 planner/receipt 已更新。validator 输出 valid=true、result=BLOCKED、mergeReady=false、releaseReady=false，表示真实未完成状态结构有效，不表示验收完成。
- 最新相关 Node 合同 100/100；生产生成物 --check、治理、Python 索引与 Project Constraints 同步通过。
- E2E 回执绑定当前脚本与清单真实 SHA-256，Settings 起点、图页返回、两领域分类及三种仓库链接实际点击均通过。Agent 查看了实际 Settings 与 Web 服务下的总图截图；离线阅读服务的 Runtime 错误状态已如实保留，不认证产品 ready。
- 新总图与基线图形证据保持原哈希，无重复人工审批。后续 source 文档版本与候选提交将分开记录，不要求产物嵌入包含自身的 SHA。
- 正常安装仍被同一 Guard 拒绝；查看 Codex App 当前设置的 native UI 也被 Computer Use 的安全策略禁止，未使用其他方式绕过。测试包安装授权继续有效，但宿主行为未改变。
- 远端仓库 PUBLIC，master 已前进到 ddcdd9784d8eda2918b8987ca8b679375e67291d；PR #80 已合并，本任务未操作；PR #81 是另一任务，保持不动。
