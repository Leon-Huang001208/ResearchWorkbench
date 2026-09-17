# GitHub Actions 免费额度治理

本页是 ResearchWorkbench 的 Actions 额度、触发路由和证据保留权威规则。仓库保持 private + GitHub Free，不配置付费超额预算，也不通过公开仓库或 self-hosted runner 绕过本规则。

## 状态门

GitHub Free 的私有仓库每个计费周期共享 2,000 分钟。内部用量估算采用保守权重：Linux `1`、Windows `2`、macOS `11`。

| 状态 | 条件 | 允许的远端动作 |
| --- | --- | --- |
| normal | 使用量低于 50% | 按路径路由运行自动门禁 |
| watch | 50%–69% | 检查重复运行和最近 5 次耗时 |
| constrained | 70%–84% | 非必要跨平台验证改为手动 |
| critical | 85%–94% | 只运行阻断发布的原生门禁 |
| frozen | ≥95% 或 billing-blocked | 禁止 push、merge、tag、rerun、dispatch、publish 和 cleanup |

`frozen` 期间允许本地只读、本地编辑、本地测试、本地提交和隔离 workspace。恢复条件是当前 Billing 页面或 API 明确显示新计费周期且 included usage 已重置；预计日期、邮件或旧截图都不是恢复证据。安全紧急修复也需要用户重新明确授权。

## 月度分配

- 50%：Ubuntu 日常测试、文档和项目约束。
- 25%：必要的 macOS／Windows 安装及平台合同。
- 25%：发布、修复、失败重跑和不可预期储备。

准备任何原生平台 workflow 前，记录最近 5 次成功运行的实际平台耗时，并使用上述权重估算。达到下一阈值后立即应用更严格状态，不以“本次应该很快”为例外。

## Workflow 路由

| 改动 | 自动门禁 | 不应触发 |
| --- | --- | --- |
| 文档、归档、报告 | Project Constraints（Ubuntu） | Bootstrap、Windows、Desktop、Tabbit |
| 普通 Research Web／CLI | Research Web Checks（Ubuntu） | Bootstrap、Desktop；非 Windows 专属时不跑 Windows Verify |
| 安装器、Web 锁、启动器、固定 DSH/CJPY、服务装配 | Research Web Checks + Bootstrap（macOS/Windows） | Desktop |
| Windows 路径、认证文件、本机集成、服务管理 | Research Web Checks + Windows Verify | Desktop |
| Tabbit 平台合同 | 用户显式 `workflow_dispatch` | 普通 push／PR 自动触发 |
| 桌面专属路径 | Desktop Verify | 普通 Web workflow 不能替代桌面门禁 |
| Desktop Release | tag 或显式 dispatch | 普通 push |

Project Constraints 保持所有 PR 和 `master` push 自动执行；自动 workflow 必须设置 concurrency、`cancel-in-progress: true` 和明确超时。
Research Web Checks 的 Python 部分固定为协议、集成协调、文档服务、文档同步与 CLI 懒加载合同，JavaScript 部分运行 `research_web*.test.mjs`。完整 `tests/research_web/` 仍在本地交付或高风险变更中按影响面运行，不能偷偷扩进日常 workflow；需要扩大自动测试时先以最近 5 次成功耗时重新评估额度。

## Artifact 与保留期

- Bootstrap 成功只上传 `doctor.json` 和 `connections.json`；完整 `logs/setup-web.log` 只在失败时上传。
- Bootstrap 和 Windows Verify 的任务 artifact 保留 3 天。
- GitHub 仓库默认 Actions artifact/log retention 在额度重置后由仓库所有者设为 7 天；该设置不由本地代码自动修改。
- 在 Billing 的 budgets/alerts 中启用 included-usage 90% 与 100% 邮件提醒，但不得创建正额度预算、付款方式或允许付费超额。当前冻结期不修改远端账户设置，恢复后将提醒状态与仓库默认保留期一起记入月度记录。
- 每月记录总用量、各 workflow 次数、失败重跑数、平台耗时、估算权重和剩余额度。

## 当前冻结与恢复顺序

2026-09-17 已观测到 2,000 / 2,000 included minutes，并由 GitHub 返回 billing-blocked；当前状态为 `frozen`。本地可以继续工作，但不得执行任何会创建 Actions run 的操作。

额度重置后按固定顺序恢复：

1. 在 Billing 页面确认新周期和 included usage 已重置。
2. 重跑提交 `f0933ad6d41e824bff9792e3a1d4386b780f9934` 的 Project Constraints 与 Research Web Bootstrap。
3. 两者通过后完成既有 delivery cleanup 和 Harness 硬门。
4. 新建独立受管 delivery，重新基于届时远端 `master` 审核并发布本地 CI 优化提交。
5. 优化提交允许一次旧触发策略下的完整 Bootstrap，作为迁移成本。
6. 下一次真实 docs-only 提交必须只出现 Project Constraints；若出现 macOS/Windows job，回滚触发策略而不是接受额外消耗。

## 月度记录模板

```text
周期：YYYY-MM-DD → YYYY-MM-DD
included usage：____ / 2,000
Ubuntu：____ runs / ____ minutes
Windows：____ runs / ____ minutes
macOS：____ runs / ____ minutes
失败重跑：____
artifact storage：____ / 0.5 GB
当前状态：normal | watch | constrained | critical | frozen
决定与原因：____
```
