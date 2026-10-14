# RWB Git 恢复权限补充验收（2026-10-14）

状态：LOCAL_PASS_REMOTE_PENDING；macOS 开发工具修复，无产品运行时或服务变更。

## 问题与修复边界

PR #108 的真实清理前备份恢复验证报 `RESTORE_HASH_MISMATCH`，正确停止在删除前。原主 checkout 的 tracked 文件有 88 个 `0600`，Git checkout 只恢复 Git 的 executable 位，默认普通文件 `0644`；恢复器尚未重设 tracked 文件的完整权限。权限修复后的真实 draft 恢复诊断进一步发现 `scripts/desktop/run_backend.cmd` 工作副本是 LF，checkout 按属性转换为 CRLF，Git status 仍显示干净。恢复器须保存 tracked 文件的真实工作副本字节，不能只依赖 canonical blob 和补丁。这是新增备份恢复器的缺口，不是旧 Git 对象删除者的证据。

修复在独立受管 worktree 中进行，仅修改恢复器、临时仓库回归和操作文档，不修改实际 desktop-owned 路径。字节与权限恢复只针对自己的临时恢复工作区内普通文件，使用 no-follow／文件身份核对，不修改源 checkout；符号链接保持链接文本，不跟随。保留失败备份、原隔离备份和其他任务已认证的备份，不自动删除。

## architecture-review

本次保持 Git 安全入口、锁、清理及 PR gate 不变，修复数据恢复验收；不降低权限、文件哈希、binary patch 或对象完整性检查。失败备份在校验前留存未认证的 draft metadata，认证仍须实际恢复成功。

真实恢复后另一失败为 `BACKUP_RACE`：捕获期间发生的变化均为其他 Codex 聊天的 turn-diff tree 引用，不能等同于本任务工作区被修改。全仓引用按捕获时 SHA 归档并校验完整闭包；目标 HEAD／分支／索引／补丁／文件仍完全绑定。保留性审计仅允许认证备份已保存旧对象且新对象完整的 Codex 快照更新，以及其他提交合法快进；不允许一般引用消失或任意重写，不冻结或回退其他任务。

## 实际状态

- 原任务 PR #108 与合并后 CI：PASS；原任务清理：BLOCKED，任务资源仍保留。
- 补充临时仓库测试：41/41 PASS；语法检查、独立规范和代码质量评审 PASS。完整四文件 changed set 的 Router L4 本地三项和 Project Constraints PASS；最终集成、修复 PR CI 和清理以外部任务回执为准。
- 原仓库真实恢复：PASS；备份 `d6e5ea38-6f5e-4296-b1f7-e31d47cd8a38` 的 `restoreVerified=true`、`fsck=PASS`，提交、快照、补丁、工作副本原始字节、权限均实际核验。失败备份仍保留。
- 修复 PR 和安全清理：尚未执行，本报告是提交前检查点，不冒充后续远端证据。
- 共用 `gc.auto=0`、`maintenance.auto=false` 保持；不安装依赖、不执行 GC／prune、不更新常驻服务。
