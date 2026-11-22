# 静态健康检查测试边界对齐

Checks `45078519836` 的 Web 5365 项（45 skipped）及 unit 55 项均无失败。
随后完整 Node 为1570 passed、4 skipped、1 failed：能力分类测试额外要求 `app.mjs`
在256KiB之外再留2KiB。当前文件为260983字节，和已接受的20d基线完全相同。

实际 `ServiceManager._text_request` 读取 `max_bytes+1`，仅在长度大于上限时拒绝；
`WEB_TEXT_MAX_BYTES` 仍为262144。本次只将Node及既有Python边界测试中的额外预留
对齐该包含上限的合同，未修改生产入口、应用文件或读取上限。保留并重跑既有
product／exact_limit／over_limit三例，覆盖260983、262144可读及262145拒绝。

固定Node24原失败模块RED为7 passed／1 failed；Python三例RED也均被旧预留断言阻断。
修后相关Node两模块43 passed（4.034s），Python三例3 passed（0.28s），临时根均retired，
失败事实与WIP通过归属保持。CI沿既有FinGPT选例增加这三项边界例及两个准确测试路径，
不扩大到完整ServiceManager模块、不重跑已过Python全仓或重构UI。

证据位于原任务根 `fingpt-static-health-{red,green}.retention.json`、相应JUnit／结果，
以及任务日志 `fed-static-health-{red,node-green}.txt`。最终候选CI和实际部署另行接续。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅将静态文件字节测试对齐既有256KiB真实读取合同，未修改应用模块、界面或加载拓扑。","diagrams":[]} -->

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"生产读取上限与limit加一拒绝逻辑未变，复用原三项真实读取边界回归，不新增健康或部署路径。","diagrams":[]} -->
