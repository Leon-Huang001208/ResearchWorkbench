# FinGPT 问答迁移（2026-10-16）

本次把 AlphaDesk 的三模式问答引擎迁入 Research Workbench：quick / deep / agent 由 Host 所有的
Node 有界子进程执行并写会话事件，快速与 Agent 共用实时思考面板，任务与自动化继续走 Claw / DSH。

结构判定按组记录如下。研究执行主链由 DSH 会话改为 Host 引擎属于真实结构变化，对应图源、HTML 与
9/9 交付回执必须由固定 Archify 重新生成；本机没有该工具，也没有新的图源字节，因此该组按未完成记录，
不得把本记录当成已通过，也不得用它替代图册证据。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"新增思考面板与说明文档复用既有 FinGPT 页面、导航、Markdown 与主题变量，没有新增页面、路由或跨模块依赖。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"自动化与能力创建仍保留 DSH 与显式 purpose，只是补记 FinGPT 问答会话不参与调度，没有新增调度节点或授权边。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"回答事件、工作笔记与报告沿用会话目录 outputs 与既有文件 API，没有新增存储介质或权限边界。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"FinGPT 三模式执行从 DSH 会话改为 Host 有界 Node 子进程与独立事件存储，属真实结构变化；受影响图源须用固定 Archify 重新渲染并取得 9/9 回执，本机缺该工具，保持未完成。","diagrams":["02-module-dependencies","03-research-sequence","06-run-state"]} -->
