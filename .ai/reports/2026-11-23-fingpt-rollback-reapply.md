# FinGPT 成功回滚后重用已审候选

本轮为 macOS 功能修复，仅修改原 Native 联合操作员及相邻离线回归。原成功显式
`rollback-fingpt` 会写入目标 quarantine，导致同一已审 SHA 再次 `apply-fingpt` 被
`resident_failed_candidate_requires_retry` 拒绝。

`Operations.finish` 仅对 `FINGPT_MODE`、显式完成后回滚标志严格为 `True` 且结果为
`rolled_back` 的终态保留已有 quarantine；完成续接核对该目标未被隔离。真正失败的上线、
未完成回滚及 Local Knowledge 保持原隔离／恢复语义，不清除已有失败隔离。

验证使用项目共享 Python 环境，无依赖安装、模型调用或生产写入：

- `git_safety.mjs check`：原 common 的 fsck PASS，无原生锁。
- 原失败复现：完整 `operate → Operations` 上线／回滚／同 SHA 再上线，4 failed、2 passed；
  4 个失败均为上述隔离拒绝。
- 修复后核心 6 passed（0.60s）。该批次传入未展开的参数化 ID，pytest exit 0，但留存工具
  返回 `batch_result_not_passed`；原回执保留真实状态，核对 owner／inode／nonce 和无占用后
  仅回收其 132470 字节可再生根，另留短清理记录。
- 完整展开用例 ID 的受管批次 `rollback-reapply-focused-20261123`：19 passed（1.07s），
  receipt 为 `retired`／`passed`，临时根已回收。覆盖成功回滚及完成中断后同 SHA 重用、
  不同目标的既有隔离保留、真实失败上线仍隔离并拒绝同 SHA、完成续接拒绝被隔离目标，
  及既有 FinGPT／Local Knowledge 成功、回滚中断和完成中断路径。
- 两个 Python 文件的 `ruff check`、`black --check`、`isort --check-only`，以及
  `git diff --check` 通过；独立 `python-reviewer` 为 APPROVE。
- 文档治理及 Python 文件索引通过；仅传本补丁四个文件的 `check_doc_sync.py` 返回 1，
  原因是架构映射要求两个模块组的其余 16 项文档也在变更集。未扩改这些无关文档，
  原 PR #314 的完整变更集由交付窗口复核；不将该局部检查记为通过。

测试证据位于原任务目录
`/Volumes/WorkDisk/Scratch/ResearchWorkbench/fingpt-release-20261119/rollback-reapply-tests/`。
本轮均为 WIP 本地结果；最终候选 CI、真实本机／私网回滚和最终切换由原 PR #314 交付窗口执行，
此报告不宣称现场已上线或其他平台已验证。

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "仅修正原联合事务成功显式FinGPT回滚的终态隔离语义，无新增运行服务、端口或部署角色。", "diagrams": []} -->

<!-- architecture-review {"group": "private-multiuser", "structure": "unchanged", "reason": "复用原账号保全、三锁和双入口健康核对，无权限或数据模型变化。", "diagrams": []} -->
