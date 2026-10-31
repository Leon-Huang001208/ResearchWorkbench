# 开发产物事件驱动清理

本项目通过 `scripts/resource_lifecycle.mjs` 接入已验证的共用leon-engineering运行时。
没有定时任务，不更新业务服务，不把合并验收当成生产部署。

## 阶段与保护

原Git安全入口仍先完成审查、CI、远端包含、目录归属、占用、恢复备份及完整性验证，
并完成Docker/依赖收尾。Git最终认证完成后，才将本任务已归档的临时验证日志目录
登记进共用生命周期，保留校验摘要后删除完整内容。业务数据、凭据、正式报告和未知文件不纳入。
源码交付不发部署成功事件；实际部署工具必须在其健康验收通过后提交独立的部署事件。

共享运行时须由受管安装器安装并校验，manifest必须包含资源内核。缺失或漂移返回
`cleanup_pending`，不伪报cleaned。该状态保留Git成功信息，后续status/cleanup事件可补清。
全局安装、宿主重载及实际启用需要对应授权；源码存在不等于已启用。

`.agents/resource-lifecycle.json`启用项目接入。共用内核负责每项目100条/10MiB摘要上限、
部署目标当前/上一版本、共享引用和macOS占用检查。RWB向宿主预算报告既有BuildKit收尾
观测量及回执哈希，与已登记文件缓存合计20GiB；它仍用原BuildKit操作锁和LRU回收，
不删除底层snapshot/blob。观测来自最近一次工具回执，未刷新不能当成实时空间证明。
总量超限则记欠账，不停止使用中的资源来达标。

## 备份退出

新任务成功清理时登记其恢复点ID和认证manifest哈希。后续交付/恢复事件使用原正式
backup-prune入口：满足原全部保护条件且不是最新两份有效点时可立即退休，无7天等待。
已登记点的哈希变化、对象缺失、未归并或未提交成果、活动和独有锚点仍拒绝。
共享payload只在没有任何保留点引用时回收；不对活动Git对象库做gc/repack/prune。

公开backup-prune同样默认保留未登记旧点并报告`legacy_policy_review_required`。
历史存量先出清单、逐类批准，不因目录名、年龄或已停止推断可删。
对象修复隔离备份继续受保护，必须单独确认；不会自动迁移或删除。

清理自身不制造永久全量备份；恢复点沿原去重存储复用。私有完整明细留在
Git common dir的`leon-engineering/resource-closeout/<task>/lifecycle.json`，普通CLI仅返回计数和引用。
状态变化才通知，欠账不等于交付失败，也不等于已经清理完成。

## 验收

本机执行原Git安全、prepared修订、原迭代收尾与新增生命周期桥合同。
Project Constraints沿同一Git safety步骤增加桥合同，不新增job、runner或依赖。
共用框架独立覆盖三次迭代、部署轮转、引用、预算、摘要读取、SIGKILL恢复和真实macOS占用。
没有Windows/Linux本机证据时保持NOT_RUN；未更新常驻服务或执行生产部署。
