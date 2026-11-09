# 生命周期桥恢复证书与必要证据保全修复

- 宿主：macOS；任务类型：项目管理面缺陷修复，隔离 worktree 实现。本平台验收为 Node 24.22.1 本机合同回归及后续同候选通用 CI；不涉及 Web/桌面运行时、依赖、部署或产品平台适配。
- 根因：生命周期桥只接受原 `git-finalization.json.status=complete`。正式恢复合同保留原 pending 字节、另写 hash 绑定的恢复 epoch 与证书，因此已完整恢复的任务仍被桥拒绝。
- 最小改动：桥在 pending 路径调用项目只读 `validateCloseoutRecovery`，复用完整恢复校验与原保全审计。校验实际 delivery/独评、原 proof、epoch、备份 manifest、资源复核、任务路径/分支缺席及保留引用/工作树；原 complete 证明认证语义保持。保留底层错误为 cause，只读验证器不执行 fetch、删除、恢复、交付入口递归或生命周期事件。
- 架构复核：仅原 Git 管理边界与生命周期桥互调只读函数；没有新产品服务、研究引擎、数据库、权限、共享框架修改或依赖。模块合同、架构和开发定位已同步。

## 实际验证

- RED：Node 24.22.1，`node --test --test-name-pattern='lifecycle accepts a valid partial cleanup recovery' tests/javascript/git_safety.test.mjs`，1 项失败，实际为 `LIFECYCLE_RECOVERY_UNVERIFIED`。临时真实 Git/v2 备份经现有正式恢复 API 生成证书，没有整体替换恢复验证器。日志：`logs/lifecycle-recovery-node24-red.log`。
- GREEN：同一目标变为通过。日志：`logs/lifecycle-recovery-node24-green.log`。
- 只读评审发现历史恢复证书路径也须重新检查缺席；新增回归先观察 `Missing expected rejection`，再统一复用缺席检查。日志：`logs/lifecycle-recovery-historical-red.log`。
- 聚焦回归：15 项通过、0 失败，含部分恢复与历史退休证书正例、12 项坏/缺/错/漂移证据和引用/路径反例。日志：`logs/lifecycle-recovery-node24-focused.log`。
- 最终 JavaScript 只读评审未发现新 P1/P2；Node 24.22.1 对两源码及测试文件语法检查通过。评审没有代替完整回归、候选评审回执或远端 CI。
- 恢复证书首轮相邻完整回归：Node 24.22.1 执行 `node --test tests/javascript/git_safety.test.mjs tests/javascript/git_safety_amend_prepared.test.mjs tests/javascript/iteration_closeout.test.mjs tests/javascript/resource_lifecycle.test.mjs`，257 项通过、0 失败，实际退出码 0，用时 259950.536 ms。日志：`logs/lifecycle-recovery-node24-neighbors.log`。后续保全补强使用独立结果，不沿用此候选验收。

## 必要原件保全补强

- 实际缺口：共用内核会将未保护的 temporary 归档在 delivery-accepted 后隔离并递归删除，只留摘要/hash。该行为会丢失最终/失败/恢复原件；没有复制型备份，不能作为必要证据的合法退出。
- API 事实：显式 `register.protection` 是现有保护合同；保护字段不可原位升级，accepted 任务也不能重新 register。内核对 protected 跳过指纹，因此已有正确保护登记由项目桥按内核身份 schema 只读复核；不写全局 ledger，不扩全局 API。
- 修复：新必要归档登记 `protection: rwb-required-verification-recovery-originals`，继续完成原接受事件和缓存报告。已有未保护、所有者不符、隔离中或必需归档缺失的记录在事件前明确拒绝；不伪造升级、不重建归档。原 `iteration_resources` 对已获准成功 stdout/stderr 的选择/丢弃规则保持不变，此层只保守保护其已验证归档的保留集。
- 真内核 RED：Node 24.22.1 显式执行 `node --test tests/javascript/fixtures/resource_lifecycle_kernel_contract.mjs`，真实已装内核、全新临时 store/project；旧桥事件后归档已不存在，断言失败，exit 1。日志：`logs/lifecycle-required-archive-kernel-red.log`。
- 同一路径 GREEN：原件字节/hash保持、接受任务和 BuildKit 报告完成，结果 cleaned 且 retained/protected，没有隔离rename或回收。日志：`logs/lifecycle-required-archive-kernel-green.log`。
- 最终只读评审另发现事件扫描整个 store，会在保护本任务时删除另一 accepted RWB 任务/项目的旧未保护原件。双任务与双项目真实内核回归先观察 `Missing expected rejection`（`logs/lifecycle-required-archive-cross-task-red.log`、`logs/lifecycle-required-archive-cross-project-red.log`），再将 live resources 中固定路径 `leon-engineering/resource-closeout/<task>/evidence` 精确认定的必要归档保护/状态/归属检查统一放到事件前；不修改或升级其他任务记录，不把已退休摘要当作潜在可删原件。
- 当前聚焦合同 22 项通过、0 失败：包含真实内核 15 项及项目桥单元；active/accepted 正确保护幂等、旧未保护 active/accepted/quarantined 及跨任务/跨项目保全拒绝、身份/符号链接/缺失原件及其他 busy 资源原门。日志：`logs/lifecycle-required-archive-focused.log`。
- 最终源码恢复证书目标 15 项通过、0 失败：原坏证书、实际 delivery、manifest/资源、保留引用与任务路径门保持。日志：`logs/lifecycle-required-archive-recovery-gates.log`。
- 跨项目门补齐前的中间版本完整相邻回归 261 项通过、0 失败，exit 0、270628.520417 ms（`logs/lifecycle-required-archive-node24-neighbors.log`）；不冒充最终版本验收。
- 最终 JavaScript 只读复核确认跨任务/项目 P1 已解决，无新 P1/P2；三文件 Node 24.22.1 语法检查通过。最终源码四套完整相邻回归 **262 项通过、0 失败，exit 0，273987.149958 ms**，日志：`logs/lifecycle-required-archive-node24-final-neighbors.log`。显式真实内核合同需要已安装的验证运行时，不是通用 CI 的新安装依赖。

## 边界

- 全部 Git 写入/恢复/删除只发生在测试拥有的临时合成仓库；没有操作旧任务资源、旧 pending proof、真实备份或生产服务，没有安装依赖。
- Node 本机为已安装 24.22.1；固定 24.19 的 CI、远端交付/合并与旧任务实际生命周期重试由主代理另行记录，当前未执行。
- Windows/Linux Native、真实 Docker、宿主真实 store/旧任务生命周期清理和现场恢复为 NOT_RUN；真实内核只操作测试拥有的临时 store/合成目录，本补丁不宣称这些平台或现场已经验收。
