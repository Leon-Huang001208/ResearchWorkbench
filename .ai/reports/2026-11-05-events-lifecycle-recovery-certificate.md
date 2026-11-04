# 生命周期桥恢复证书兼容修复

- 宿主：macOS；任务类型：项目管理面缺陷修复，隔离 worktree 实现。本平台验收为 Node 24.22.1 本机合同回归及后续同候选通用 CI；不涉及 Web/桌面运行时、依赖、部署或产品平台适配。
- 根因：生命周期桥只接受原 `git-finalization.json.status=complete`。正式恢复合同保留原 pending 字节、另写 hash 绑定的恢复 epoch 与证书，因此已完整恢复的任务仍被桥拒绝。
- 最小改动：桥在 pending 路径调用项目只读 `validateCloseoutRecovery`，复用完整恢复校验与原保全审计。校验实际 delivery/独评、原 proof、epoch、备份 manifest、资源复核、任务路径/分支缺席及保留引用/工作树；原 complete 路径保持原合同。保留底层错误为 cause，不执行 fetch、删除、恢复、交付入口递归或生命周期事件。
- 架构复核：仅原 Git 管理边界与生命周期桥互调只读函数；没有新产品服务、研究引擎、数据库、权限、共享框架修改或依赖。模块合同、架构和开发定位已同步。

## 实际验证

- RED：Node 24.22.1，`node --test --test-name-pattern='lifecycle accepts a valid partial cleanup recovery' tests/javascript/git_safety.test.mjs`，1 项失败，实际为 `LIFECYCLE_RECOVERY_UNVERIFIED`。临时真实 Git/v2 备份经现有正式恢复 API 生成证书，没有整体替换恢复验证器。日志：`logs/lifecycle-recovery-node24-red.log`。
- GREEN：同一目标变为通过。日志：`logs/lifecycle-recovery-node24-green.log`。
- 只读评审发现历史恢复证书路径也须重新检查缺席；新增回归先观察 `Missing expected rejection`，再统一复用缺席检查。日志：`logs/lifecycle-recovery-historical-red.log`。
- 聚焦回归：15 项通过、0 失败，含部分恢复与历史退休证书正例、12 项坏/缺/错/漂移证据和引用/路径反例。日志：`logs/lifecycle-recovery-node24-focused.log`。
- 最终 JavaScript 只读评审未发现新 P1/P2；Node 24.22.1 对两源码及测试文件语法检查通过。评审没有代替完整回归、候选评审回执或远端 CI。
- 相邻完整回归：Node 24.22.1 执行 `node --test tests/javascript/git_safety.test.mjs tests/javascript/git_safety_amend_prepared.test.mjs tests/javascript/iteration_closeout.test.mjs tests/javascript/resource_lifecycle.test.mjs`，257 项通过、0 失败，实际退出码 0，用时 259950.536 ms。日志：`logs/lifecycle-recovery-node24-neighbors.log`。

## 边界

- 全部 Git 写入/恢复/删除只发生在测试拥有的临时合成仓库；没有操作旧任务资源、旧 pending proof、真实备份或生产服务，没有安装依赖。
- Node 本机为已安装 24.22.1；固定 24.19 的 CI、远端交付/合并与旧任务实际生命周期重试由主代理另行记录，当前未执行。
- Windows/Linux Native、真实 Docker、真实生命周期资源删除和现场恢复为 NOT_RUN；本补丁不宣称这些平台或现场已经验收。
