# 研究协议、执行状态与恢复

## 实际端点与公开生命周期

`EndpointStore(home)` 只在私有 `install/endpoints.json` 保存 schema 1 的 `records`，Native
含不同的 `web_port`/`runtime_port`，Docker 仅含宿主 `web_port`，各模式带独立 opaque revision。
`read(mode)` 缺失返回 `None`，纯只读；`publish(mode, web_port, runtime_port=None, expected=...)`
在已有私有锁中按该模式快照 CAS，保留另一模式并返回新快照。损坏/冲突不回落默认值。
`verify_facts()` 仅比较调用方已验证的端口，不证明 PID、监听者或容器归属。
`select_port(preferred, explicit=False, excluded=())` 首选指定端口，再有界 bind 回环 0 获得候选；
socket 关闭后没有预留保证，调用方仍须验证真实监听并有界重试。显式冲突拒绝自动换端口。

`ControlOriginTransaction(data_root, previous_origin, next_origin, quiescent=callback)` 要求调用方
持有生命周期锁。`prepare()` 在 exact `True` 静止证明下同时验证两份既有控制记录，再只修改 URL；
`commit()` 在启动成功后丢弃本事务标记，`rollback()` 在目标停止后恢复内存中的原始字节。
缺失记录留给正常 creator，origin 不变不写入。事务 helper 不启动或停止服务，不迁移业务数据。
公开 start/restart 使用这些接口；Native 健康条件仍包含准确 PID/argv/启动时间、监听者、
认证和页面 readiness，Docker 仍核对不可变镜像、安装/launch label、挂载与实际 Web mapping。
只读后备入口从相同端点或一致的旧 run-state 读取，不创建记录；畸形端点不回退默认值。
旧 state 的私有读取结果在单次 bootstrap 诊断内复用，避免瞬时替换被第二次读取掩盖。

Native/Docker 写生命周期共用原 `run/lifecycle.lock`，模式切换先由旧 public stop 持锁停止，
再获取同一把锁重新验证两模式及原 mode snapshot 后 CAS；持锁区不调用跨进程 public stop。
安装候选通过实际 `LifecycleLock.assert_held()` 对象复核进入内部启动，锁顺序固定为
lifecycle→短时 install/runtime 元数据锁。`EndpointStore.restore(mode, previous, expected=publication)`
只回滚本次仍为当前的发布；恢复已有端口生成新 revision，另一模式不变，首建失败可移除本模式记录。
候选 origin 事务保留到安装摘要和模式发布完成；失败在精确容器清理和静止证明后恢复。

Native 仅在本次日志窗口（保留 inode/偏移、上限64KiB）包含明确 bind 错误，原PID已退出、
新监听可证明不是同安装写者时分类为 bind race；不输出日志原文。Docker 仅解析有界CLI的
明确bind错误为稳定code。两者最多三次尝试；未知归属、协议/认证或回滚失败不重试。
已有停止Docker容器若需改host绑定，当前仍拒绝 `docker_stopped_port_conflict`，该分支未达完整设计验收。

origin commit 失败与健康失败共用精确清理：本次新建容器清除，本次启动的既有停止容器
在重新核对 ID、镜像、安装、挂载和 launch 身份后仅 stop，保留容器。静止证明先于端点 CAS
恢复与 origin 回滚。Native 缺失运行账本仍检查当前端口监听者；未知或同数据根监听者拒绝
分配和模式切换，只有可证明属于其他实例的监听允许避让。缺少 Native 环境时，既有数据根
的监听通过标准库 PID/argv/启动身份与监听复查核验；已证明的外来监听允许继续，未知或同根
写者失败关闭。受管 Docker 仍须独立通过容器身份、实际 mapping 与健康检查。补齐控制文件前先只读验证全部既有记录和一致 origin，MCP-only
动态 origin 不会被默认 DataHub origin 污染。Docker 安装摘要回滚同时核对发布写 FD 的身份
和精确字节，内容相同的新 inode 也保留并报告 recovery_unverified。

`listener_argv_is_foreign` 是既有标准库合同里的共享纯判定，供后备桥、Native 静止检查和
bind-race 分类使用；可识别 Web/DSH 命令缺少数据根证据时拒绝，不能从其他 checkout 推断不同
数据根，也不读取进程环境或配置。缺端点记录的既有根同时观察选定端口和旧默认8088/3081，
显式指定新端口不会绕过旧 writer。fresh 证明仅来自本次持有已验证 lease 时成功 mkdir 的
根 inode，既有根或 inode 替换不认领；证明在首个 spawn 前和 start finally 清除，不用于失败重试。

Native 从有效 fresh 证明捕获本次事务的 RAM-only 恢复基线：原 lease/根 inode、选定与旧默认
端口的监听集合，以及监听 PID/argv/启动身份；已捕获身份不刷新。spawn 后分配证明仍失效，
只有本次所有对象精确退出且基线未变，才可用于端点 CAS/origin 回滚。Popen 后、状态写入和
健康等待前记录 PID，内部清理不丢弃记录；已退出对象不重复停止。恢复未知时保留原始启动
错误，附加受控 recovery_issues/日志并保留 journal；该失败不得触发 bind 重试。

Native 模式切换桥复用服务管理器的 state/PID/精确 argv/启动时间/监听者事实链，停止调用同一
排他生命周期入口；状态查询不隔离或删除 stale/invalid 文件。Native 日志读取也复用精确进程
身份，并在输出前核对状态文件内容和 inode，不能凭命令行子串或重用的 PID 证明归属。

Docker supervisor 的启动顺序先准备 `/state/runtime` 与 `/run/rwb-secrets/private` 私有叶，
再清理本次认证状态、启动 DSH、探测并启动 Web。健康检查复用 `/state/runtime/auth.json`；
重启保留私有叶及凭据内容并重新检查 owner/权限/alias，不修改 Native 状态路径。
固定缺失叶的准备先用保留父FD创建，再由原runtime_state_directory完整重pin；不会捕获
任意校验失败后无条件重试。data-root/logs使用相同首建顺序，自定义目录维持原严格create路径。
启动失败额外记录固定阶段、受控异常类别、数字 errno 与 runtime/web 已知退出码；
日志初始化前后使用同一安全字段，原失败退出及有界清理流程保持不变。
Runtime launcher 失败进一步区分 Node 版本、prepare、模块 fallback、Tabbit 包/adapter、配置写入和 exec 阶段，仍以原退出码 1 失败。

模式选择只决定进程部署：Native 由服务管理器管理两个宿主进程，Docker 由单容器 supervisor 管理 DSH/Web；研究提交、双 WebSocket、SSE、审批与恢复协议共用。`rwb runtime status --json` 读取当前模式与安装身份；`rwb runtime use docker|native` 在旧模式运行时要求 `--stop-current` 且必须验证旧实例归属。两模式不可并发写同一研究数据。Docker `rwb web status|doctor --json` 将稳定 `issues` 返回给操作者，状态或镜像归属不明不自动接管。Windows Docker 凭据 ACL 当前未通过可证安全边界，不作为已验收模式。

Docker 公开 start 与 Doctor 从私有接受摘要读取不可变 image ID，并检查依赖/Compose 合同及
容器实际 image ID；每次安装构建独立候选 tag，不能通过覆盖共享 tag 改变选定镜像。
候选启动仅由安装事务调用，公开 start 每次重新加载接受摘要。启动在默认 120 秒健康等待
预算内轮询（各 Docker 命令仍有独立超时），只在 DSH/Web 健康时返回成功；退出、unhealthy、
超时均失败。本次创建容器的回滚再次验证不可变 ID 和归属；失败回滚不删除既有容器。
up自身失败时，controller单次有界重枚举并校验一次性launch label及候选image；匹配才回滚，
未知归属保留并附加恢复未验证issue。原up错误始终保留，回滚失败不隐式二次删除。
显式离线 repair 可在候选启动前非 force 删除已再次验证的停止容器，但保留旧接受镜像、
摘要、数据及凭据；失败后可按仍匹配的旧合同重新创建旧实例。运行中的容器不会被自动停止或删除。
Doctor 保留 `dsh` 字段，区分健康 ready、摘要构建证据 build_verified、固定 commit 和宿主
不适用项，不填造宿主 DSH/Node 版本。Native `web status --json` 同样输出安全服务投影，
不会序列化日志路径，原有非 JSON 输出保持不变。

合同读取使用 dirfd/no-follow；祖先目录比较节点 identity（设备、inode、mode、uid/gid），
无关祖先 sibling 创建/删除不会被误判为合同替换。合同文件和直接父目录仍比较完整 metadata，
保留瞬时 rename/alias/restore 攻击检测；直接父目录发生内容活动仍保守失败关闭。

一键安装固定 DSH 来源、提交、pnpm 与构建闭包，但不改变消息受理、双 WebSocket、SSE、恢复、
审批或取消协议。安装失败不会启动候选 Runtime，也不会接管当前 3081/8088。
服务管理器在 spawn 前消费 Doctor 的安装 issue；只有安装状态 `ok` 才进入 3081/8088 生命周期。
启动生命周期由排他锁覆盖。管理器先有界读取私有 state，再核对 PID 存活、精确 argv、真实启动时间、
端口监听 PID 与带认证的 DSH `session/list`；任何一个事实无法确认都不会把 PID 或开放端口当作
owned/healthy。死 PID 与关闭端口形成可恢复 stale state；归属明确但不健康时先停止受管 Web，
再重建 DSH 与 Web；foreign/unknown 进程保持原状并返回稳定错误。非强制重启只使用现有认证材料
只读核对活动研究，核对失败即拒绝。Runtime auth 只在安全受管重建时更新。
Web 进程就绪还要求 Runtime API、首页 HTML 与主 ES 模块实际读取成功；随后才打开浏览器。
模型目录或凭据缺失只影响 `model_ready`，不改变 `product_ready` 与设置页可访问性。
这是一条进程前置门，不新增 Runtime 状态，也不改变会话恢复、幂等受理或活动研究重启门禁。
纯 `rwb web status` 不加载 DSH 启动功能图；固定提交来自轻量共享合同，构建闭包扫描仅由 Doctor
和安装诊断延迟加载，因此状态核对不会提前装配 Capability、MCP 或 DataHub Runtime。
安装事务会把已验证 DSH commit、closure SHA、文件数与 build mode 原子写入 Runtime build lock；
锁与当前受管 DSH 不一致时 Doctor 返回 `dsh_runtime_lock_mismatch`，启动不会进入 DSH 执行链。
首次启动会在任何 Tabbit/Profile 变更前由固定 DSH 模板创建 `web` Profile；Windows 用 CIM 核对
PID 命令行、用 PowerShell 探测 PID 存活并按受管进程树停止，POSIX 仍按进程组停止。pnpm 的 Windows
junction 和 POSIX symlink 都只在解析目标仍位于固定源码树时接受。这些平台分支不改变 Runtime 协议。
安装阶段的 Web import readiness 只验证 checkout 入口可加载，不执行 FastAPI lifespan、不启动框架
调度器、集成探测或 3081/8088；实际进程和健康状态仍只由 `rwb web start` 建立。
未安装环境中的顶层 `rwb --help` 仅输出标准库静态帮助，不进入 DSH 会话、认证、启动或恢复链；
`web start/restart/stop` 仍由原安装门拒绝。

Docker 构建先对完整 DSH checkout 执行相同的固定 remote、commit、pnpm 与完整构建闭包验证，
通过后才按已安装的 production dependency graph 和上游 package `files` 字段生成运行资产目录。
开发依赖、测试、fixture、文档、benchmark、website 和 Git 历史不会进入该目录；CLI、profile
模块、上游声明的运行资源及所需第三方生产依赖保留。pnpm 共享 hoist 别名仅在目标已属于所选生产图时保留，确保原生 addon 从跨包加载器基址仍能解析平台实现；不会通过 hoist 扩大开发依赖集合。`.rwb-dsh-runtime.json` 是构建时派生的
资产清单，不是第二份依赖配置：它记录原始固定来源和完整闭包事实，以及目录、普通文件、符号
链接的确定性清单和摘要。镜像 launcher 在创建运行状态前拒绝缺失、额外、篡改、越界链接、
alias、错误 schema 或超限清单，并继续把原始已验证闭包写入既有 build lock。仅镜像环境明确
设置 `RWB_DSH_STAGED=1` 时启用该路径；supervisor 只向 DSH launcher 子进程传递这个精确值。
未设置、空值、`0` 或其他值均不启用，Native 即使存在伪造或损坏的 staged 清单也忽略它，始终
执行原有 Git identity 和 `calculate_build_closure` 路径。最终镜像还以非 root
用户导入 Web、CLI、supervisor、healthcheck 和 iFinD HTTP 路径，避免宿主源码掩盖镜像漏包。

Framework Runtime 在 Research Web 生命周期内只启动和关闭一次，一个 `AsyncIOScheduler` 管理 Gold 与 Dollar 的分频采集。采集器按区块提交最后成功值；单源失败只更新该区块的 `checked_at`、`failure_code` 与 stale/partial 状态。

框架页面 Bot 仍由本运行时承载：`framework-explain` 是无工具的快照解释预设，用户显式触发的 `framework-verify` 才装配只读检索和公共数据工具。验证会话与解释会话分离，并绑定框架 slug、章节、缺口、方法版本和同一精确快照 revision；旧 revision 返回 409，Bot 不修改评分或快照，也没有第二个 Agent Runtime。

Phase 2A 的 Registry 读取仍不进入研究执行链。Phase 2B 只把用户已安装、探测、启用且授权的
MCP 工具加入专属 DSH：Host 生成 `mcp__{installation}__{tool}` 声明和 schema 哈希，DSH adapter
经私有 loopback 回调 Host；Host 每次复核安装版本、schema、会话授权、风险等级与人工审批后才由
官方 SDK 调用 MCP Server。安装/启停会等待当前研究归零并仅重启 DSH，失败恢复旧激活清单；Web
进程与既有提交、SSE、恢复和报告状态契约不变。
本地 PyPI 安装在当前解释器提供 pip 时保持原路径；uv 管理的精简环境没有 pip 时，仅使用宿主已存在
的 uv 执行等价离线安装，并把 uv 配置与缓存限制在 staging 内。两条路径都不使用 shell，不改变
已解析的 `--no-index`、完整哈希、无依赖和目标目录约束；没有 pip 和 uv 时关闭失败。
staging、安装 payload、清单与确认令牌重放目录在 Windows 上校验真实目录、符号链接和重解析点，
但不把 POSIX `st_mode` 投影解释为 ACL；POSIX 继续校验 group/other mode 与当前用户所有权。

Phase 2C 的 Automation 只从锁定的 Skill、普通 Workflow 或报告 Workflow 版本创建独立 Claw
会话。APScheduler 仅持有下一次内存触发，原子索引保存任务与 Run 事实；启动时只合并最近一次遗漏，
重叠触发记录 `skipped_overlap`，无法确认的旧会话记录 `interrupted`。研究失败不自动重试，手动
重试生成带 `retry_of` 的新 Run。无人值守 MCP 调用还须通过任务锁定、只读、明确允许和 schema
哈希复核，不能绕过会话授权或高风险人工审批。

## 集成探测与 DataHub 工具

Research Web Host 启动时先恢复 `IntegrationCoordinator` 的安全快照，再异步运行启动探测批次；
用户在设置页执行“重新检测全部”时创建独立手动批次。协调器只编排既有 DataHub Provider、本机发现
和 Tabbit 状态，不进入 DSH 的研究事件链，也不改变 Automation 会话或恢复语义。

Runtime 常驻 15 个品牌无关 DataHub 工具。每次业务查询由 Broker 按最新配置、授权、探测和 Provider
状态选源；缺少可调用来源时返回明确错误。这个动态路由取代启动时裁剪 `enabledTools` 的旧行为，
但不放宽来源白名单、会话归属、参数校验、取消或禁止回退语义。

## 持久化本地启动边界

`rwb web start|status|stop|restart` 由 `app/research_web/service_manager.py` 管理专属 DSH 3081 与 Web 8088。默认 DSH 源码是 `~/.research-workbench/dsh-source/` 中经过固定提交构建的项目私有副本，避免修改或依赖用户其他 DSH 实例使用的工作树；必要时可用 `RESEARCH_DSH_SOURCE` 显式覆盖。管理器把 PID、进程组、启动命令指纹、最终 Node CLI/overlay 归属签名、项目路径和日志位置写入 `~/.research-workbench/`。新版 Typert Gateway 启动后，管理器从受限日志尾部提取一次性启动令牌，换取 `dsh-auth-*` Cookie，并把 authority、工作目录、固定提交与版本原子写入 `runtime/auth.json`；POSIX 要求文件权限 `0600`，Windows 则拒绝重解析点并核对普通文件、单硬链接、大小及打开前后身份，不把 POSIX mode bit 当作 ACL 证明。健康检查以该 Cookie 调用真实 `session/list`，随后才启动 FastAPI 并检查 `/api/research/runtime`。重复启动是幂等操作；失败回滚只处理本次创建且归属签名匹配的进程，既有 3080 不在其所有权范围内。普通重启发现活动研究时拒绝执行，只有显式 `--force` 才允许中断。备用验收可为管理器指定独立端口，不复用生产状态目录。

`runtime/auth.json` 由客户端和服务管理器通过 `runtime_auth.py` 读取。读取器限制 4 KiB，拒绝非普通文件、硬链接、符号链接、Windows 重解析点及打开前后身份变化；POSIX 要求 group/other 无权限，Windows 不把 `st_mode` 的 POSIX 投影解释为 ACL。

服务管理器创建数据、运行状态和日志目录时采用相同的平台边界：所有平台拒绝非目录、符号链接与 Windows 重解析点，仅 POSIX 使用 group/other mode 位判断目录权限；Windows 不以该投影替代 ACL 结论。

断电或系统重启会结束后台进程，本轮没有安装开机登录项；恢复时重新执行 `rwb web start`。如果状态文件来自先前 checkout 或命令版本，管理器只有在记录的 PID 已确认不存在时才移除该 stale 状态并重建；PID 仍存在、状态损坏或归属无法确认时继续失败关闭，绝不接管或终止未知进程。

研究协议本身仍是下述 DSH RPC、Remote 复用流和 Web SSE 投影。Workbench 兼容桥把既有白名单方法映射到新版斜杠端点与 `{payload:{args}}` 信封；Cookie 只进入 HTTP/WS Header，不进入请求正文、会话记录或浏览器接口。服务管理器只负责本机进程生命周期，不创建第二套研究运行时，也不改变会话、审批或恢复语义。

## Tabbit 实时页面上下文

设置页分别控制浏览器自动化和 Tabbit `web_fetch` 接管。前者默认开启、后者默认关闭；打开 `web_fetch` 必须同时打开浏览器。多实例环境要求选择 16 位实例 ID。配置变更标记 `restart_required=true`，活动研究期间沿用既有重启门禁并保留待应用配置。

Tabbit 配置和 Runtime 锁文件固定按 UTF-8 读写。POSIX 继续使用文件权限位；Windows 在临时文件句柄关闭后执行原子替换并跳过不受支持的目录 `fsync`。供应归档文件名按 tar 的 POSIX 语义比较，adapter 入口在 overlay 中统一为正斜杠。

用户首次展开 `@` 标签菜单时，BFF 才为当前会话申请页面访问授权并读取所选实例的可 claim HTTP(S) 标签页；不会后台预取。消息最多携带 8 个有序 `{tab_id, instance_id}` 引用，且必须带实时接管二次确认。发送前 BFF 重新向 Runtime 读取清单并校验标签、实例、协议及可用状态，不信任浏览器提交的标题或 URL。

`runtime/tabbit-adapter.mjs` 只使用官方插件提供的唯一 `ctx.tabbit` 执行器，以 `rwb-mention-<session4>-<request8>` 原子 claim 所选标签，并在一次只读求值中按选择顺序读取当前 DOM。每页最多 60,000 字符、总计 120,000 字符；总量超限时按标签数公平截断并在折叠上下文中标记。无论成功或失败都在 `finally` 调用 `finishTask(..., {keep:true})`，标签保持打开，但分组可能改变。claim、求值或释放任一失败都会阻止消息提交并保留前端草稿。

正文仅写入 DSH 内存 token：绑定当前会话、只能消费一次、10 分钟过期。消息正文只携带短标记，`agent/pre-step` 再将内容注入默认折叠的插件上下文。会话授权后，声明为 `read_only:true` 的浏览器调用可自动执行；缺失或为 `false` 的调用逐次进入原生审批。该声明来自调用方，不能静态证明 Playwright 代码无写操作，系统提示明确禁止把写操作伪装为只读。日志只记录会话 ID、数量、阶段、耗时和稳定错误码，不记录标题、URL、正文或执行代码。

`GET/PUT /api/research/runtime/tabbit` 提供安全状态与配置；`POST .../tabbit-access` 管理本会话授权；`GET .../tabbit-tabs` 提供候选清单。Runtime 状态只允许 `ready | disabled | launcher_missing | browser_offline | unsupported_version | instance_selection_required | error`。安装器显式禁用；缺失、离线或版本过低时只返回诊断和官方手动安装指引。

`ResearchService` 同时持有进程内本机集成诊断管理器，并在服务关闭时取消未完成的发现或验证任务。发现只读取宿主事实；真实验证必须由设置页显式触发，目标限于 Excel、Word、PowerPoint 与 Wind Excel，并在独立进程组及对应 Office 容器的受管临时目录内执行。PowerPoint 保存后按随机文件名重新绑定本轮对象；Wind 通过 LaunchServices 启动或复用已登录的 Excel 应用，只创建并关闭验证器独占的空白工作簿，绝不把用户既有 Excel 进程登记为清理目标。该管理器只服务设置页的安全主机事实投影，不进入 DSH 会话、工具注册、研究执行或事件恢复链。

`app/research_web/operations.py` 只读取上述原生历史、当前投影和服务管理器状态，生成不含问题正文、审批参数或凭据的监控结果。它不参与提交、恢复或取消；历史事件未提供 usage 时返回未知，不以零替代。研究台通过 `workbench.py` 创建目标 DSH 会话后，后续提交仍完全遵守本页协议。

## 提交与流式

1. `POST /api/research/sessions` 创建真实 DSH 会话和产品归属目录。
2. `POST /api/research/sessions/{sid}/messages` 必须带 `Idempotency-Key`。BFF 先检查连接、运行中任务、附件归属、能力、交付要求和 Tabbit 实时引用；存在标签页时完成再次校验与单次提取后，才由兼容桥调用原生 `session/prompt`，每次请求生成独立 `requestId`。
3. HTTP 202 只表示受理。传输超时不是模型执行超时，且不能自动重发可能已受理的问题。
4. DSH Remote 的 `$events` 与 `session/control` 复用流分别提供 API 事件和控制基线；兼容桥把 `api-session/*`、waterfall 审批／提问及取消事件投影为稳定 BFF 信封。Web 通过 `GET .../{sid}/events` 接收 `snapshot` 或 `runtime_error`，心跳不代表执行进度。
5. 刷新读取同一会话。历史通过 `session/follow` 的 opening snapshot 与 `session/page` 分页恢复，并结合 `session/list` 和 `subagents/list` 恢复真实状态。恢复不另建会话、不重提消息。

会话删除使用 `DELETE /api/research/sessions/{sid}` 做产品内软删除，先写入墓碑并保留 DSH 原生日志与 Workbench 文件；30 天内可通过 `POST /api/research/sessions/{sid}/restore` 恢复。用户主动永久删除，或服务启动／每 6 小时在线任务发现墓碑到期时，BFF 调用 DSH `session/delete`。级联子会话删除由 Session Controller 负责；只有 DSH 明确返回包含根会话 ID 的 `deletedSessionIds`，或明确返回 `session/not-found` 证明原生记录已不存在后，才清理 Workbench 会话目录与索引。其他失败保留墓碑并继续重试，不能把隐藏状态误报为永久删除。所有操作都校验会话归属，不能用于发现、修改或删除其他 DSH 实例的会话。

相同键与相同内容返回原受理收据；同键换内容拒绝。受理结果未知时先查历史中的本任务标记，不能以 UI 重试按钮无限重复执行。

## 运行状态（不是 Workflow 节点状态）

| 状态 | 来源或条件 | 用户可理解的含义 |
|---|---|---|
| `idle` | 原生日志未出现当前执行 | 可准备新问题 |
| `running` | 父回合或真实子 Agent 运行 | 研究仍在进行 |
| `awaiting_approval` | 当前归属内存在原生审批请求 | 等待用户允许或拒绝 |
| `completed` | 原生 `turn/end` completed 且无子任务运行 | 回合结束，文件另行检查 |
| `cancelled` | 原生 aborted | 已记录取消结果，不等于发送取消请求时即结束 |
| `failed` | 原生 error 或受理/执行错误 | 错误必须展示 |
| `interrupted` | interrupted 或历史运行但原生已不运行 | 无正常完成证据；交付仍pending时不能直接发送 |
| `blocked` | 原生 blocked | 原生执行阻塞 |
| `incomplete` | 原生 max-tokens | 本轮未完整执行 |
| `disconnected` | 任一下行通道断开 | 当前状态未知，不能伪报完成 |

`can_cancel` 根据父/子 Agent 的真实运行状态计算。工具失败保留活动级错误，并不必然将整轮改为 failed。子任务历史当前读取最近 100 条；若截断则明确标记，用量和耗时不冒充全量。

## 审批、问题与停止

原生审批通过 `POST .../{sid}/approvals/{aid}` 响应 approve/deny，校验待审批 ID 与会话归属。批准允许原工具继续；拒绝不得发起相应外部请求。原生问题经 `questions/{qid}` 回答，保留单选/多选语义。

停止调用父 `session.cancel` 与本会话真实子 Agent 的 `subagent.interrupt`。请求受理后仍等待原生状态确认。脚本取消需终止实际子进程，不能仅改变前端标签。

已受理且非运行、交付仍pending时，`can_recheck_stop` 提供「重新核对停止」。停止意图绑定当前任务与幂等键；真实受理后，完整历史精确当前标记、唯一空闲父任务、全部空闲子任务及可用父连接、双事件通道和无待处理审批/提问缺一不可。若仅缺原生终止事件，显示failed/结果未确认，独立交付verification_failed；不补造turn/end、不运行解析器。同键不重发，新键可继续，持久化后可冷恢复。证据不全保持等待，普通原生aborted仍正常显示cancelled。

DSH 不可用时明确报错，无 LangGraph、固定答案或第二 Supervisor 回退。已有资料和能力目录的只读可用性与运行能力分开。

本机 Office/Wind 显式验证证据在 TTL 截止时刻即失效；`verification_ttl_seconds=0` 不允许同一时钟刻度继续复用。Workbook 单阶段 timeout 显式不超过 180 秒总预算减 10 秒协调余量，避免平台浮点舍入越界。POSIX 进程组与 Windows `taskkill /T /F` 由各自平台测试独立覆盖。

## 代码与测试

关键来源：`runtime_auth.py`、`client.py`、`service.py`、`projection.py`、`ui/core.mjs`。协议、认证文件与投影回归位于 `tests/research_web/`，前端幂等、路由竞态、刷新、SSE 清理测试位于 `tests/javascript/research_web_ui.test.mjs`。真实模型验收另记，不以传输模拟代替。

MCP Runtime 与 Automation 默认启用后仍按原有探测、授权、版本锁和风险策略运行；默认启用不等于自动安装 Server、自动授予工具或自动创建任务。显式环境开关关闭时继续失败关闭。

2026-09-11 的格式基线维护不改变本机验证 TTL、状态转换、进程清理或 Runtime 调用路径。

CLI 启动前固定项目根与 Node 选择：Codex Desktop 优先使用 bundled Node，其他宿主使用 `RESEARCH_NODE_BINARY` 或 `PATH`。所选绝对路径进入既有进程命令指纹，因此后续 `status/stop/restart` 仍按同一归属失败关闭。

Method 请求在提交前按 `required > user-selected > recommended > model-supplemented` 解析，去重后
最多三个，并锁定产品版本、语义版本、原生名称和来源。DSH 原生加载包装后，实际采用须调用
`rwb_record_method_use`；本轮收据保存提交前的追踪偏移，旧轮记录不能满足新轮完成检查。必需或
用户选择缺记录时完成状态转为失败，推荐或模型补选缺记录时保留结果并降级标记。

## 2026-09-23 重启与刷新稳定性回执

非强制 `rwb web restart` 先通过已认证 DSH 的 `session/list` 获取活动事实；任一会话仍在运行即拒绝
重启，只有显式 `--force` 才进入既有中断路径。会话目录恢复仍先读取一次 `session.list`，再对每个
合格父会话读取 `subagent.list`，50 个父会话的扇出并发上限为 8。仅已创建、存储为 `running`、原生
父会话空闲且子会话均空闲的陈旧行才进入 `detail()` 恢复；恢复复用不超过 8 的上限并保留目录顺序。
未创建、原生运行或子会话运行的行绝不恢复。任一读取、恢复异常或调用方取消都会取消并等待未完成任务
收敛后再传播原异常，避免遗留后台请求。本轮只收紧重启授权和目录读取界限，不改变 DSH、SSE、会话状态、
Automation 或交付拓扑。

## 2026-09-28 Windows 停止升级回执

Windows 受管进程停止现在允许非强制 `taskkill /T` 失败后进入既有等待与 `/F` 升级；只有已通过状态文件、
PID 与命令签名归属核对的进程可进入该路径，强制失败仍返回错误。DSH 会话、SSE、恢复、取消与研究状态
协议均未改变。
