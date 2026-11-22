# 交付运行时固定与 CI 结构复核

RWB 的 Git 安全入口从仓库加载 leon-engineering 0.19.4 固定依赖，校验来源提交、路径和完整文件哈希。历史任务与资源继续使用原有回执和账本。

PR #299 的 `6f44162c0096ae7485b114d5192471801b77cd9f` 在 Project Constraints run `42954579365` 通过 Git 安全测试步骤，最终项目约束步骤报告缺少 FinGPT 模块说明和验证工作流结构复核。本机以同一基线和完整 19 路径复现三项违规。

补充 FinGPT 比较的验证边界及本结构复核。修复候选的项目约束结果以完整 Git 变更集为输入，GitHub CI 以该候选自身的回执为准。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"固定版本隔离与真实内核合同由既有 Project Constraints Git 安全步骤运行。08 图的源码映射、项目验证、离线约束和 CI 关系适用于这两个合同，项目回执继续使用既有交付与资源账本。","diagrams":[]} -->
