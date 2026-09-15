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

CLI 输入只能是当前工作目录内的普通相对 JSON 文件；规范化后仍须位于 cwd，文件和目录链接或
重解析点一律拒绝，并在 no-follow 打开前后复核文件身份。计算必须遍历全部已受理输入；输出明细
采用 `cpu-bounded-result-v1.md` 的有界 `row_delivery`，不得先截断输入再计算。
