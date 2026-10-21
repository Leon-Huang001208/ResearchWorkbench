# 模型服务商常驻联合升级

宿主 macOS Mac mini，Web 功能部署安全修复；Windows/Linux 产品验收 NOT_RUN。
用户明确授权部署并保全配置、凭据、会话，活动/未知等待，失败自动回滚。不调用付费模型、不读取 Key 正文。

原 UI-only 升级器不允许模型后端差异，因此新增精确旧基线与受审产品 blob 的独立操作员，不扩大自动清单。
全局 preparing 意图先于 BirthFence，HTTPS 根 503 先于旧主实例 journal；联合停止、安装、绑定、保全与恢复。
实际原 controller 源码与物理 pyz 摘要分别验证，旧恢复 peer 保持原样。

RED：新测试在缺少模块时导入失败；早期 75 项通过后，独立审查仍发现终态撤门后再次回滚和出生占槽中断恢复盲区。
两处已修复；新增 20 项 finish 内 atomic/record/unlink/fsync 前后故障及 4 项真实 BirthFence 部分发布/释放中断。
独立评审复跑 99 passed，关闭两项 HIGH 并批准代码；格式与最终候选平台门仍须执行。
测试使用真实文件/journal/BirthFence 与真实旧 controller fixture，OS 信号、生产配置及模型全部隔离。

本机部署/旧恢复/协议合跑 357 passed（25.40 秒、1 项既有 Starlette 弃用警告）；Router 选出的治理、架构与验证合同 JS 229 passed。
Ruff、Black、isort、目标 mypy、Python 索引与文档治理通过；L4 是未知操作员/CI路径的保守路由，没有缩减要求。
主线后来合并 PR166，仅三份登录 HTML/CSS/JS 外观与忙碌反馈变化；已阅读其完整差异，受限产品 blob 固定到 0d73c034，后端、认证请求与依赖无新变化。
首轮 CI Constraints 失败：新增操作员归属 dual-runtime/private-multiuser 及工作流后，缺少对应模块文档变更和 verification-workflow 结构审查。补齐合同说明，保留失败日志，不降低门禁；源码测试通过不能替代这项架构检查。
其他 CI 与常驻切换证据尚未产生，不能宣称部署通过。
日志在任务 logs/model-provider-upgrade-green.log；私有真实部署回执将绑定最终 SHA 与部署后 revision。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"复用原主实例、单DSH、准入锁和服务管理器，新增受限操作员协调既有主实例与网关恢复；不新增研究执行拓扑或修改自动兼容范围。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"复用原网关、用户池、出生栅栏及恢复节点；同步既有primary绑定revision，全局持久冻结先于占槽，不变更账号或业务数据格式。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只向既有Research Web Checks Python步骤增加联合部署定点测试；保持原runner、安装流程、质量分层、平台归属与原Mac Bootstrap，没有新增执行节点或依赖。","diagrams":[]} -->
