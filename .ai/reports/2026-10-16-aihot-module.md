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

## 已授权的项目内交付恢复修复

2026-10-16用户明确授权修复基线推进恢复并完成同一PR126交付；不改全局框架、不强推、不删除旧工作树。
原候选a1a5b7265aebc599de328ac8f5858622751daed4的Mac Bootstrap38872423852已成功，实际checkout相同；Doctor installation_ok/product_ready、runtime/web ready和原生空搜索覆盖均通过。
等待期间PR125推进master至1566973375ecb28a5298b356fc7cd28ad2727445；已原位合并并解决15处文档/生成物冲突，保留双方功能。
该合并候选75ec5ac389125747d4db92033581debd57c9a132本地236项JS、105项Python通过，独立评审未发现功能合并问题；这些不认证后续恢复代码或新候选CI。
失败证据：受管publish记录remote_moved，prepare旧实现禁止删除重建路径。新回归首次4项RED均触发PREPARE_REMOVAL_BLOCKED。
修复将remote_moved已发布PR的prepare转为原位候选认证：旧候选/feature/新基线祖先、所有权、干净状态、PR与远端实时身份、双次候选/回执核对；旧回执先归档，CI/验证清空。
旧prepared未发布的再次推进只接受明确钉住的published tip；发布成功后推进该tip，拒绝任意祖先和更老head回退。无push/删引用/删工作树，原修补计数及全部全局策略保持。
独立审查指出的head任意祖先及发布后残留问题均已补反例和修复。完整最终测试、实际原位恢复、最终候选Mac CI、合并与资源回执待下列交付证据补充；不能复用旧候选Mac结果冒充通过。
完整Git安全测试54/54通过（34.14秒，无skip/todo），另验证发布身份门拒绝时不会先改写pin。文档治理与Node语法检查通过；最终候选CI仍待运行。
