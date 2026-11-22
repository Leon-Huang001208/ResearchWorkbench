# 原 PR #284：当前主线围栏内保全复核前移（2026-11-22）

本轮是 macOS 上的 Native 操作员源码开发，沿同一任务
`rwb-calendar-mcp-cutover-20261108` 和原 PR #284 接续，不建立替代任务或部署入口。
目标是前移两处仍有效的配置／前版保全复核；旧财经日历固定部署 profile 不恢复。
代码与文档冲突已在同一隔离工作树解析；未提交阶段的回归实际通过176个独立用例。
最终候选整模块测试、评审、当前候选 CI、常驻切换和业务验收仍分别取证，
不把未提交阶段结果当作 exact-SHA 或线上验收。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在既有Native联合操作员的BirthFence SQLite排他锁及安装作用域内前移配置和前版复核，主实例、附接网关、安装入口与唯一DSH职责不变；不增加运行节点、依赖、模式或容器，不需要改动现有部署图。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"沿原账号身份、前版双健康、MCP实际值与账号资料保全读取复核，准备恢复失败保留原journal；数据库、认证边界、业务接口、授权和恢复数据路径均未改变，无新增拓扑或图示节点。","diagrams":[]} -->

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
原失败根及9个新根均经正式身份核验退休，任务活动根为空。
这些结果的身份为 `mode=wip`、`exactCheckout=false`；记录在任务外置
`rwb-pr284-current-20261122/wip-neighbors/accepted.json`，不挪作最终候选整模块通过。

最终候选完整相关测试、独立评审和当前基线 CI 由后续交付原件绑定，当前为
`NOT_RUN/PENDING`。常驻切换、真实模型／供应商及业务验收均 `NOT_RUN`；
本次未更新任何服务、业务数据、账户配置或模型预算。
