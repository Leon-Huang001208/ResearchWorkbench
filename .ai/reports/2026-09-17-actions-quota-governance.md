# GitHub Actions 免费额度治理

## 范围与状态

- 基线内容对应远端提交 `f0933ad6d41e824bff9792e3a1d4386b780f9934`。
- 当前 GitHub Free included usage 已耗尽，GitHub-hosted jobs 返回 billing-blocked。
- 本任务只在无 GitHub remote 的本地隔离仓库实施和提交；未 push、merge、rerun、dispatch、publish 或 cleanup。
- 现有文档治理 delivery receipt、feature/integration worktree 和失败 CI 证据保持不变。

## 架构影响

本轮只改变 CI 触发、平台路由、超时、并发和 artifact 保留，不改变 Research Web HTTP API、DSH、DataHub、文件合同或产品运行拓扑。新的 Ubuntu 日常检查和额度门禁仍属于既有 Documentation Gate／CI 验证边界，图 08 无需新增节点或关系。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"新增 Actions 免费额度路由、Linux 日常检查和短期 artifact 策略，但不改变 Research Web 文档服务或产品运行拓扑。","diagrams":[]} -->

## 验证

- 有界 Python 合同集：77 passed，1 warning，9.70s（协议、集成协调、文档服务、文档同步、CLI 懒加载）。
- Research Web JavaScript：292 passed，1 skipped，0 failed。
- Actions 路由／治理／架构／Tabbit 快速测试：76 passed，0 failed。
- 文档治理：473 files、59 current、0 violations；Python 文件索引与 doc sync 通过。
- Project Constraints 使用完整 16 文件 changed set：0 violations；无参数空变更输出未作为通过证据。
- 7 份 workflow YAML、3 份治理 JSON、Node 测试语法与 `git diff --check` 通过。
- 探索性全量 `tests/research_web/` 在 9m22s、95 passed 时人工停止；它不是通过证据，测量结果用于确认不应放入日常廉价 workflow。
- 第一版抽样因包含 API／capabilities 初始化在 127.68s 人工停止；第二版 112 passed、1 warning、83.88s，但仍移除了慢速 DataHub／framework 组。只有最终 77-test 合同集进入 workflow。

额度重置前不执行远端 Actions，因此 macOS、Windows、GitHub-hosted Ubuntu 与观察性 docs-only 路由结果均保持 `pending`，不能写成通过。
GitHub 账户的 90%／100% included-usage 邮件提醒与仓库默认 7 天保留期也属于重置后的管理员动作；本轮没有修改账户设置、预算或付款方式。

## CI repair

首次公开仓库 CI 中 Project Constraints、Research Web Checks 与 Bootstrap macOS 通过；Windows Verify 的原生测试发现旧断言仍要求宽泛的 `app/research_web/**` 触发器。修复只把该测试更新为新的窄路径白名单及明确拒绝宽泛触发器，不改变 workflow 或运行时代码。repair 提交应只重跑 Project Constraints、Research Web Checks 与 Windows Verify，不再触发 Bootstrap。

## 公开仓库交付收口

- GitHub API 已确认 `Leon-Huang001208/ResearchWorkbench` 为 `PUBLIC`，默认分支为 `master`。
- `76d1ea1053187569bb23d30f9a22b894ccbc0675`：Project Constraints、Research Web Checks、Research Web Bootstrap 的 macOS／Windows 均通过。
- `de39abcdbf3551c9985615e4cf80cd121a3a16b3`：Project Constraints、Research Web Checks、Research Web Windows Verify 均通过。
- 受管 delivery 状态为 `cleaned`，Harness 硬门返回 delivery `cleaned`、CI `passed`。
- 当前权威政策已从 private 额度冻结切换为 `public-standard`；若以后转回 private 或使用 billable runner，2,000 分钟阈值策略自动重新生效。
