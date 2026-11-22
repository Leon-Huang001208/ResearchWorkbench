# 原 PR #284：当前主线围栏内保全复核前移（2026-11-22）

本轮是 macOS 上的 Native 操作员源码开发，沿同一任务
`rwb-calendar-mcp-cutover-20261108` 和原 PR #284 接续，不建立替代任务或部署入口。
目标是前移两处仍有效的配置／前版保全复核；旧财经日历固定部署 profile 不恢复。
代码与文档冲突已在同一隔离工作树解析；未提交阶段176项回归之后，
候选`14707a4c8509a67b2af8fe4ff06bea4d0a7440d7`的完整相关主模块3975项、协议81项实际通过。
后继只增加CI路径和开发文档，Python／runtime／测试输入保持字节一致；执行身份仍为147，
不冒称后继SHA重新运行这些测试。当前候选CI、常驻切换和业务验收仍分别取证。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在既有Native联合操作员的BirthFence SQLite排他锁及安装作用域内前移配置和前版复核，主实例、附接网关、安装入口与唯一DSH职责不变；不增加运行节点、依赖、模式或容器，不需要改动现有部署图。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"沿原账号身份、前版双健康、MCP实际值与账号资料保全读取复核，准备恢复失败保留原journal；数据库、认证边界、业务接口、授权和恢复数据路径均未改变，无新增拓扑或图示节点。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只为既有维护操作员与测试增加两个精确选择器、完整模块catalog及原Bootstrap的PR/push测试路径，并按用户持续授权明确失败证据保全后沿原入口自动接续；L0-L4规划、原三CI作业与runner、回执协议和跨平台交接链保持，未新增验证节点、执行通道、恢复框架或模型比较，不改变08-iteration-docs图的拓扑。","diagrams":[]} -->

Product-Progress: not-required — 本次仅加强既有本机维护操作员的锁内验证顺序，不增加浏览器功能或改变用户产品流程。

## 原任务与历史连续性

| 项目 | 保留事实 |
| --- | --- |
| 当前前移基线 | `92ae4aed9ccc147dcd7241016c740434679b30d9` |
| 原发布 head | `b5380f56ffee3b47a2c3f4f239783cdf94363658` |
| 原任务／PR | `rwb-calendar-mcp-cutover-20261108`／#284 |
| 合并方式 | 当前基线正常合并原 head，保留原 ancestry；文档冲突局部取当前主线后补有效合同 |
| 历史 CI 修复 | 已用 `0`，累计上限 `2`；新 phase 计数不重置或冲销旧历史 |
| 历史模型调用 | `UNKNOWN`，不能写成零 |
| 本次文档操作 | 模型、供应商、服务修改、部署调用均为 `0` |
| 旧工作树未提交状态 | `NOT_INSPECTED_KEEP_OLD`；未检查或退休旧工作树 |

旧 Desktop 交付回执
`/Users/leon/Desktop/Projects/ResearchWorkbench/.git/leon-engineering/deliveries/rwb-calendar-mcp-cutover-20261108.json`
原位保留；本次读回 SHA-256 为
`24a3859125b36dab6c96c763dcfe0d83712ac34df0447da74ef10a571c30780e`，
不改写旧状态、修复次数或验收。原
`2026-11-08-financial-calendar-mcp-cutover.md` 保持历史原件；
其中旧候选测试和部署描述不迁作当前候选或现役验收。
旧日历载荷 `79102a95a267044c4a28b1818a9181f788be77fd` 已在当前主线祖先中，
不因前移有效保护而重新引入其旧 profile。

## 两处有效保护与排除范围

范围仅为当前 `ATTACHED_MCP_PRESERVATION_MODES` 五模式：
`RESEARCH_BOT_MODE`、`RESEARCH_BOT_V2_MODE`、`STORAGE_IDENTITY_MODE`、
`STRATEGY_VALIDATION_MODE`、`LOCAL_KNOWLEDGE_MODE`。
仅适用 forward fresh apply 和非 `post_deploy_rollback(state)` 的 preparing 恢复：

1. fresh forward apply 取得原 BirthFence SQLite EX、安装作用域及 Operations，
   完成原最终 GitHub 候选证据检查后、进入 `execute()` 前，
   执行 `validate_configuration(home, state)` 与真实 `ops.verify(previous=True)`。
2. 限定 preparing 恢复不再沿围栏外的提前返回删除 journal；
   先取得同一围栏／安装作用域，再完成配置和前版复核，成功才删除原准备 journal。
   任一复核失败均保留原记录，不进入 stop、checkpoint 或源码切换。

配置校验独立保留，当前 Attached `verify` 不能替代它。
Trial 特殊模式、完成后回滚和其他模式／恢复阶段保持原语义；
特别是 Local Knowledge 完成后回滚可能已运行目标版，不套用 `previous=True` 方向。
不新增模式、profile、锁、lease、daemon、框架、依赖、数据库或权限。

## 文档与验证证据

17份旧 Calendar 顶部冲突按当前基线内容解析，保留当前知识scope、构建队列、
受管Git交付与现行授权合同，补齐两项保护的当前范围及失败边界。
按 architecture-map 实际触发 `dual-runtime` 与 `private-multiuser` 两组；
两组要求的模块文档已纳入同步，结构不变，无图源／HTML重渲染。
README 复核结论为 `unchanged`，公开安装、CLI／源码入口和依赖未改变。

本机未提交阶段先在真实围栏反例中复现两项失败；同一测试根修复后两项通过，
原始失败输出、回执与哈希保留。其后9个正式批次通过174项，连同前两项去重为
176项：新增31项全部通过，邻接145项通过，0失败、0跳过。
覆盖五模式 fresh／preparing 的锁内顺序、围栏后漂移保留 journal、
Trial／完成后回滚方向、真实中断恢复、dossiers 保全及 finish 失败不二次发信号。
该未提交阶段原失败根及9个新根均经正式身份核验退休，当时任务活动根为空。
这些结果的身份为 `mode=wip`、`exactCheckout=false`；记录在任务外置
`rwb-pr284-current-20261122/wip-neighbors/accepted.json`，不挪作最终候选整模块通过。

## 完整模块与平台门的路由补齐

原实际 Router 计划将操作员和对应测试归为 `fallback/unknown_impact_boundary`，
未登记完整 Python 模块和 Mac Bootstrap。先以 Node 回归复现两项失败后，新增单一
`research-web-native-upgrade` L4/full-delivery 规则，仅匹配这两个确切文件；
完整 `test_model_provider_upgrade.py` catalog 带原 `--confcutdir=tests/research_web`，
没有 nodeid、关键字筛选或替代的局部子集。原通用完整检查、架构／Constraints、
关键 smoke、文档／Python 索引及原三项 CI 保留，Windows 门交对应真机，Mac 不 dispatch。
相邻未知 resident 与测试文件继续为 L4 fallback。完整检查另发现 Bootstrap 的精确测试路径
及 verification-workflow 文档缺项；保留原失败结果后，在原 PR／push 清单各补该测试路径，
同步比较文档与结构不变说明，不改断言、job、runner、安装、依赖、权限或超时。
固定 Node24.19.0 的定点路由回归3项和完整 `verification_policy` 108项均通过，后者包含前者，
不重复相加。原两项RED和通过输出保存在外置 `rwb-pr284-current-20261122/router-mapping/`。
路由回归只认证其所测字节，不能代替后续Python整模块或当前候选CI；
实际整模块结果见下一节及外置回执，模型／服务与发布另证。

## 用户授权的失败保全后自动接续

候选 `14707a4c8509a67b2af8fe4ff06bea4d0a7440d7` 实际完成155批、3100项通过，
每个成功根均已正式退休；第156批因多个约87MB的恢复夹具累计超过512MiB被原守卫终止，
退出码为-15、无JUnit，该批不补通过。原根停止后实测575,869,521B，原owner和全部记录保留。
剩余875项与已通过3100项互补，方案将7个重夹具分别单例运行，其余保持原分组；
原源码、断言及容量门均不改变。该51批实际875项全部通过，与原3100项按nodeid去重，
有序恰好覆盖原冻结3975项，0跳过；原第156批仍为容量中断，不改写为通过。
随后独立执行完整`test_protocol.py`，81项通过、0跳过，不与主模块或WIP重复相加。
原155个成功根及新51+5个成功根全部正式退休；549MiB失败根和原owner继续保留，
原历史PID／PGID未记录仍为UNKNOWN。新56批实际观测的pytest组收尾无成员，
不拿它们的终态倒填原失败批。

执行证据为任务外置`continuation-147-execution/final-verification.json`，SHA-256
`95099d2f0f0a99bd8eb7b3ab0827efc4d32633c4eb9e5548bcf40b2a63a5413b`；
其中保留原冻结3975、155个通过回执、第156批中断、本次用户授权、875补集及协议81项的
独立计划、JUnit、实际退出码、结果和回收身份。WIP176与任何无JUnit片段均未计入最终通过数。

用户已明确允许本次继续，并要求修改`AGENTS.md`，避免今后逐次确认同类情况。
因此同步仓库规则、工作流及存储留存文档：一次只运行一批，但已结束的失败证据根
可在原执行退出／当前占用检查、原因定位和原件保全后，与新的受管测试根并存，
同任务缩小批次或修复候选后自动继续，无需重复索取例外。未知或在途执行不能绕过，
512MiB／64MiB／3GiB及最多20项门保留，旧失败、回执状态和CI／模型累计不清零。
这次文案修改不更改retention实现、不创造新恢复入口，也不授予模型、服务、部署或依赖权限。

本地九个Node模块338项通过；Ruff／Black／isort、聚焦mypy、文档／Python索引、
完整changed-set约束及架构检查均通过。最终集成候选另绑定Python输入树相等证明、
新候选Node／静态检查及独立组合评审，不挪用旧SHA的CI。
本报告冻结时当前基线GitHub CI仍待发布后实际取得；常驻切换、真实模型／供应商
及业务验收均`NOT_RUN`。本次未更新服务、业务数据、账户配置或模型预算。
