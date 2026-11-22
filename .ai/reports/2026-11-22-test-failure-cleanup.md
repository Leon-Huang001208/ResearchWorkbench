# 测试失败后的临时根清理

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"复用原Checks作业、依赖与分片runner；真实base/head仅在纯临时根工具及文档修补时选择相关31项，其它产品改动保持原完整路径，没有新增验证节点或业务执行权限。","diagrams":[]} -->

普通 pytest 失败或容量终止后，`run` 保存真实退出码、结果及日志；原身份和无占用检查通过后，沿既有 `retire` 清理可再生根，回执为 `retired`、`outcome: failed`，命令仍非零退出。失败清理不生成完整目录内容摘要。`--keep-failed REASON` 仅用于明确的复现用途，成功验证合同和原容量限制保持。

本机复用既有 Python 环境，相关工具模块 31 项通过；Black、Ruff、单文件 Mypy 通过，独立 Python 审查无未解决 P1/P2。未运行全仓测试、模型、供应商或服务操作；远端 CI 以本 PR 实际结果为准。

原 `rwb-calendar-mcp-cutover-20261108` 第156批临时根已按用户授权清理。原退出 `-15`、无 JUnit 和失败结果仍保留，owner 标记失败已清理，没有补成通过。宿主可用空间前后观察增加 676,089,856 字节；该观察不等同目录逻辑大小。已无用途的旧失败目录清单及接续计划退出，实际成功批次回执保持。
