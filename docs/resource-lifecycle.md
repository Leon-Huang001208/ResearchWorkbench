# 开发产物事件驱动清理

本项目通过 `scripts/resource_lifecycle.mjs` 接入已验证的共用leon-engineering运行时。
没有定时任务，不更新业务服务，不把合并验收当成生产部署。

## 阶段与保护

原Git安全入口仍先完成审查、CI、远端包含、目录归属、占用、恢复备份及完整性验证，
并完成Docker/依赖收尾。`iteration_resources` 先按已核验选择清单丢弃获准的成功测试输出，
再以完整 SHA 校验归档必要保留集。Git最终认证完成后，生命周期桥把这一证据根显式标记为
`protection: rwb-required-verification-recovery-originals`。最终、失败、恢复证明等必要原件
继续保存在原归档路径；交付接受事件和缓存报告照常完成，保护本身不算清理欠账。
不得把摘要或原件 hash 当成原件备份。业务数据、凭据、正式报告和未知文件不纳入可删除资源。
源码交付不发部署成功事件；实际部署工具必须在其健康验收通过后提交独立的部署事件。

旧登记未带保护、所有者不符或仍处于隔离回收状态时，桥在任何接受事件前拒绝，保留原件与
原账本。事件会扫描整个 store，因此该保护前置门同时覆盖账本中可由固定路径
`leon-engineering/resource-closeout/<task>/evidence` 明确认定的其他 RWB 任务及项目归档，
不能因本任务已保护而顺带删除另一任务原件。只检查 live resources，不把已退休摘要当作待删除原件。
当前共用 API 不支持保护升级，也不允许已接受任务重新登记，因此不能伪报已升级。
已有正确保护的 active/accepted 登记须通过项目只读指纹复核，才幂等继续；归档缺失不重建。
该指纹以真实内核身份 schema 交叉测试；符号链接、内容/身份漂移均拒绝。其他未保护资源的
真实占用、预算与身份门仍由原内核执行，不以伪造 active owner 或 busy 状态保护必要原件。

`git-finalization.json` 为 `complete` 时沿用原证明认证门；受管恢复保留原 `pending` 时，
桥调用项目 `validateCloseoutRecovery`，复用完整恢复证书校验，核对原证明、epoch、
实际 delivery、独评、v2 备份 manifest 与资源重新验证链，再检查本任务路径及分支仍缺席、
其余保留引用及工作树仍满足原保全审计。缺失、漂移或不匹配证据均在创建生命周期引擎前拒绝，
不改原证明，不递归调用交付入口，也不重放 Git、资源删除或实际恢复。

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
真实临时 Git/v2 备份及正式恢复生成的证书桥回归位于 `tests/javascript/git_safety.test.mjs`；
覆盖 partial cleanup 与历史退休证书、坏/缺/错候选/过期摘要、delivery/资源/备份漂移、
保留引用缺失或倒退及任务路径重现。原 `complete` 桥与保护登记单元回归在 `resource_lifecycle.test.mjs`。
安装了已验证共用运行时的宿主另执行 `node --test tests/javascript/fixtures/resource_lifecycle_kernel_contract.mjs`：
使用全新临时 store 的真实内核，证明原件字节/hash保留、无隔离/删除、接受事件与缓存报告完成，
并覆盖旧未保护登记、隔离中断、身份/符号链接/缺失归档与其他占用资源。该显式宿主合同不增加
通用仓库 CI 的外部运行时依赖；未执行时不能声明真实内核集成已验证。
共用框架独立覆盖三次迭代、部署轮转、引用、预算、摘要读取、SIGKILL恢复和真实macOS占用。
没有Windows/Linux本机证据时保持NOT_RUN；未更新常驻服务或执行生产部署。
