# PR104：G2B 发布链前移当前主线

沿原 `codex/docker-release-g2b` 的 `99a784e` 历史，在 WorkDisk 独立分支普通合入主线 `dc3ce6b7`。旧源码和原 PR 保留，不以旧草稿的“不发布”终点覆盖本轮持续交付授权。

- 25 处合并冲突已处理。保留当前 DSH、Hot、插件、报告 Workflow、源日历、stage 预留与 owner handoff 实现，仅加入原 G2B 管理器/维护门接点。
- 发布 Dockerfile 同步当前 QA 前端构建、资源清单与最终镜像导入检查；DSH 仍由已封存 payload 提供，不在发布阶段重建另一份 DSH。
- `release_idle` 补入当前 DataHub 的 SDK Future、Wind API、storage runner、目录任务及插件执行活动，避免旧发布器遗漏后来新增的在途工作。
- 保留当前主线文档与图件，再补 Docker 发布/维护合同；API Atlas 增加受管镜像的只读发布身份端点，不新增外部维护写 API。

## 已执行检查

发布合同 19 项通过；共享维护门 7 项通过。QA 制品配方定点 1 项通过，当前 DataHub/插件活动 5 项通过；原发布 API 与 Manager 相关 79 项通过；110 项相关检查全部通过，另对配方改动只补跑对应 1 项，不重复未变验证。上述均为源码工作树检查，不认证镜像构建或现场晋级。

最初发布合同的 pytest 已 19/19 通过，但旧临时工具把未展开的参数化选择器与实际 JUnit 条目数比较而拒绝收尾；后续使用真实 collect nodeid。已结束且可重建的该自有临时根直接清理，保留真实 JUnit 与短说明，没有重跑未改变的 19 项或保存完整失败树。

## 后续

同 PR 的必要 CI、独立源码评审及最新基线完成后交付源码。现场 release 镜像、同镜像 stage 接受、晋级与回退由原维护窗口执行，不以 #140 构建或历史 r0d/r1a/r2 记录替代；不启动新模型、变更现役服务或迁移数据库。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"复用现有Docker管理员入口、Manager、Host和唯一DSH，只前移冻结制品与私有维护合同；没有新增常驻节点或数据库，当前QA资源及运行源码按主线保留。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有Host内加入受管镜像只读身份和维护排空检查，沿原HTTP/Unix管理边界，不新增外部维护写接口或另一研究执行器。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"复用现有Automation调度和任务，只在Docker发布期间以原MaintenanceGate暂缓新执行，已接纳任务与来源/预算不重置。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"保留当前周报准备和恢复实现，在已有运行方法上接入同一维护门，不新增报告调度、数据层或研究引擎。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅将两份新增release与维护离线合同加入原Research Web Checks测试清单，不增加workflow、runner、依赖、产品dispatch或新的验证框架。","diagrams":[]} -->
