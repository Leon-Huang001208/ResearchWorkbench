# CPU-bounded v1

`cpu_bounded_v1` 是 reviewed calculator 的公共执行策略，不是独立 Skill，也不授予新工具权限。
种子构建器应把本文件、`cpu_budget.py`、`cpu-bounded-result-v1.md` 和 `provenance-v1.md`
复制到每个 CPU 计算包的 `resources/`，并将各文件 SHA-256 固定在不可变版本中。

每次 Skill 运行必须在读入或计算前调用 `WorkloadBudget` 验证，不能截断后继续：累计输入最多
50,000 行和 64 MiB；单序列最多 5,000 行；批量最多 50 个标的、每标的最多 1,000 行；
输出制品累计最多 16 MiB。超限固定抛出 `workload_too_large`，元数据只包含对应上限和
`suggestion=reduce_scope`，不得回显输入内容。

计算只依赖 CPU；数值库线程由沙箱固定为 4，不需要也不得探测 GPU。脚本仍受 15 秒默认执行预算、
60 秒 hard cap、macOS Seatbelt 与现有文件/网络/进程边界约束。

CLI 输入只能是当前工作目录内的普通相对 JSON 文件。POSIX 从已打开的 cwd fd 开始逐目录组件
openat/dir_fd，配合 `O_DIRECTORY`、`O_NOFOLLOW` 和 `fstat`，最终文件也只从可信父目录 fd 打开；
Windows 校验打开句柄的最终路径与 reparse 属性，无法确认时失败关闭。计算必须遍历全部已受理输入；
输出采用 `cpu-bounded-result-v1.md` 的有界 `row_delivery` 和完整 UTF-8 envelope，不得先截断输入再计算。
