# AIHOT 原页面完整阅读模块

宿主macOS / Web功能开发。用户要求独立模块并完整保留原日报/热点页面功能。
本机个人/内部读取，不部署或更新常驻服务，不新增模型调用、数据库和产品依赖。

## 实现与来源

- 独立AI资讯入口：日报/周报/月报、完整日报合订本、热点榜。
- 原页面报头/期号/日期点阵、统计/阅读时长、封面、看点/版面目录、双栏正文、来源头像、一手/跟进、关联报道、快讯、前后期、按月归档；手机目录dialog、近期chips与对应报刊历史。
- 热点前三卡片、后七名、真实热度/趋势/缺测断线、状态标签、参与者名单和热度说明；文章/事件/原文和RSS打开原站对应内容。
- 固定公开site API恢复完整字段，v1旧路由兼容。不上模型、不调用采编引擎。
- 上游源码 c8704e5313e6b051560365226b3919d7e0ada5ea，15个参考文件逐一SHA-256匹配；报告/热点/曲线结构按MIT适配，许可见docs/research-web-ui.md。不复制原站品牌Logo/字体。

## 实际证据

- 本地路由计划L4；最终本地门记录logs/aihot-local-results.json，所有11项exit0。
- Node 211/211，包含AIHOT目标15项；Python66/66（AIHOT36项及相邻intel30项）。
- Ruff0.17.1 / Black26.10.1 / isort9.0.2通过；mypy2.4.0目标三文件（含main.py）--follow-imports=skip通过（范围如实保留）。pytest9.1.1，Node25.9.0。
- 文档治理、Python索引、架构地图、API Atlas、Project Constraints及git diff --check通过。
- 测试依赖由用户明确授权安装在本任务.venv；产品包读取原本已有环境，不修改主环境。初次pytest缺失属环境NOT_RUN，非产品RED。
- 真实site API日报索引178期、热点10项、周报23期、月报5期、指定月份30期及一张有界JPEG读取成功；源数据样本位于logs/aihot-reference，不硬编码为产品结果。
- 隔离浏览器使用现有fixture研究runtime，AIHOT取数是真实上游；不构成DSH/model验收。
- 浏览器已见完整日报、头像封面；热点3+7卡片、10曲线、参与者弹层、热度说明；周报23期历史、月报、178期合订本、手机目录打开/关闭与跳转、手机无横向溢出。所检查页面console error0。
- 独立Python/JS审查已进行；HTTP-date限流、缓存命中互阻、归档取消恢复、报刊更早导航、正文外看点和错误重试问题已修复并回归。

## 当前交付边界

最终候选SHA/集成验证/PR/CI/合并与资源收尾待补充，不能从上述本地结果认证远端通过。
预览http://127.0.0.1:18089使用任务独立数据与端口，原8088常驻实例不改。
Windows/Linux原生NOT_RUN；不发送其他平台dispatch，不宣称跨平台发布就绪。
预览仍供用户查看；回收前须检查实际进程占用，不能强删运行中的worktree。

<!-- architecture-review {"group": "ui", "structure": "unchanged", "reason": "在既有Host匿名HTTP读取和浏览器模块边界内增加固定来源阅读页面，不新增部署节点、存储schema、研究引擎或调度器。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "在既有Host匿名HTTP读取和浏览器模块边界内增加固定来源阅读页面，不新增部署节点、存储schema、研究引擎或调度器。", "diagrams": []} -->

