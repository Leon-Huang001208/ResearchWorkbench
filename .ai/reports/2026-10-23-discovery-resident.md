# 今日发现组合常驻部署准备

本任务为macOS Native/Web固定部署操作员扩展。用户已授权组合主线（今日发现、ETF配置及持续研究仓），产品固定9802af1e6d7fd64bbfa417cfc03c50961ec1e550，现场前驱5343e18d9f203a87f2d958218e4288afa527711f。不包含生产跟踪启用、真实模型、依赖新增、迁移或外盘操作授权。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在原Native操作员的review/idle/CLI路径新增固定组合profile，原v4事务及恢复执行边、wheel/source角色与锁保持；没有新运行节点、进程、安装入口或第二引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"同一idle入口先只读遍历既有primary和用户数据范围，拒绝启用自动化、独立周报日程及活动未知执行；不启动backend、不修改同意、schema或账号路由，原保全/容量/BirthFence拓扑保持。","diagrams":[]} -->

新增apply-discovery/reviewed-discovery-v1沿现有profile安全reader、市场inflight门、固定证据读取器和原manifest锁。旧profile不调用新零后台工作门；发现历史关闭草稿不被删除。首次或恢复前状态变化均重复校验，异常保持deferred/recovery_required。

现场只读预检已记录13份账号业务索引、108个会话，discovery tracks=0、enabled automation=0、active automation runs=0；独立report-workflows catalog有4个workflow，enabled schedules=0，历史状态为blocked_data/completed/delivery_incomplete。此为时间点证据，不能代替持锁切换前复查。摘要保存在logs，未输出正文或凭据。

初版封闭profile全矩阵1373 passed；新增零后台工作门后，原fixture中的primary绑定账号仅有state而没有私有数据目录，产生52个预期成功场景拒绝。修复为按既有运行时语义将未初始化私有数据根视作无工作，保留别名/非目录拒绝和全部活动/未知负例。修后完整结果及独立评审、最终候选Router/原三CI/同候选Mac安装由后续真实回执绑定；尚未执行常驻切换、模型请求或启用计划。

最终本机完整矩阵1381 passed（86.21秒，1个既有Starlette弃用警告）；独立审查109 passed/1272 deselected，ruff/diff通过。原governance四模块113 passed；check_research_architecture、check_doc_sync（含governance/索引）、black/isort/ruff均通过。近处gateway/resident/multiuser回归及精确最终候选CI分别保留日志，不把隔离fixture的deployed当作实际部署。

最新组合追入PR212（9802af1）WGC月度吨数与AK资金流时点守卫；只更新DISCOVERY payload，旧ETF v2及其余profile固定值保持。无新依赖、迁移或启动任务；旧WGC缓存缺新合同需显式重新取数，部署不触发查询。001518候选原三CI已通过，但主线更新后需以当前候选重新取证，旧CI不冒充新证据。
