# CI 取消后的 worker 进程组收尾

Checks `45064106251` 在原 45 分钟作业上限取消，随后安全证据收集因
`worker-1/pytest.log` 仍变化而拒绝。原 run 没有 artifact，不能据此指定某条测试挂住。

分区执行器已用 `start_new_session=True` 启动自己的 worker，但取消只向 worker PID 发信号，
worker 退出后派生进程仍可持有日志。现仅把取消、启动失败和异常收尾的信号及强制终止
作用于本次 Popen 创建的 worker 进程组，并回收直接 worker；退出后的残留组也被终止。
非 POSIX 保留原 Popen 信号／kill 路径。原 10 秒等待及 5 秒强制回收预算不变，
正常执行没有新增时限，证据收集器和失败分类未放宽。

macOS 本机共享 Python 的实际验证：

- 有效 RED 批次 `ci-cancel-reap-red5`：2 failed，0.77 秒。两种信号均真实复现上述
  `source identity changed before staging: worker-1/pytest.log`。
- 修复后同两项：2 passed，0.90 秒。
- 最终相邻批次 `ci-cancel-reap-focused`：9 passed，1.94 秒。覆盖 SIGINT／SIGTERM、
  忽略信号的派生日志写者、立即安全 staging、日志停止写入、直接 worker 已 wait、
  无关独立 session 保持运行，以及原正常、失败、collection、setup／teardown 和身份负例。
- `ruff check`、`black --check`、`isort --check-only` 及 `git diff --check` 通过。

夹具准备中的转义、固定测试根及 SIGINT 时序失败保留短原始回执，不计为有效 RED。
默认 pytest SIGINT 产生的无 `rwb_nodeid` 半成品 JUnit 仍会严格拒绝；本次回归使用合作的
SIGINT handler 生成合法失败 JUnit，仅验证进程组与日志收尾，不宣称补齐未知执行结果。
本地测试均为 WIP，根目录已由原留存入口退休；未重跑全仓、安装依赖、调用模型或操作生产。

证据位于原任务目录
`/Volumes/WorkDisk/Scratch/ResearchWorkbench/fingpt-release-20261119/ci-cancel-reap-tests/`。
独立评审和新候选 CI 由原 PR #314 交付窗口接续，本报告不认证其已通过。

Product-Progress: not-required — 本次仅修复持续集成取消后的子进程收尾，不改变任何产品入口、研究能力或用户配置。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"仅收口原双worker持续集成执行器创建的进程组，未新增服务、接口、数据库或证据接受规则。","diagrams":[]} -->
