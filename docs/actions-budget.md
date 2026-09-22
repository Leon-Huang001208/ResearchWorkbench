# GitHub Actions 免费额度治理

本页是 ResearchWorkbench 的 Actions 用量、触发路由和证据保留权威规则。仓库当前为 public；GitHub 官方规则说明，公开仓库使用标准 GitHub-hosted runner 不消耗付费分钟。仓库仍不配置付款方式或付费超额预算，也不使用 self-hosted runner。若仓库以后改回 private、使用 larger runner 或出现其他计费面，立即恢复下述额度状态门。[GitHub Actions 计费规则](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

## 状态门

GitHub Free 的私有仓库每个计费周期共享 2,000 分钟；这不是当前 public 仓库标准 runner 的计费上限。为了控制排队时间、失败重跑和未来转回 private 的风险，内部仍采用保守权重：Linux `1`、Windows `2`、macOS `11`。

| 状态 | 条件 | 允许的远端动作 |
| --- | --- | --- |
| public-standard | public 仓库且只用标准 GitHub-hosted runner | 按路径路由运行自动门禁；仍记录实际耗时 |
| normal | 使用量低于 50% | 按路径路由运行自动门禁 |
| watch | 50%–69% | 检查重复运行和最近 5 次耗时 |
| constrained | 70%–84% | 非必要跨平台验证改为手动 |
| critical | 85%–94% | 只运行阻断发布的原生门禁 |
| frozen | ≥95% 或 billing-blocked | 禁止 push、merge、tag、rerun、dispatch、publish 和 cleanup |

`normal` 至 `frozen` 的百分比阈值只适用于 private／billable 状态。`frozen` 期间允许本地只读、本地编辑、本地测试、本地提交和隔离 workspace。恢复条件是当前 Billing 页面或 API 明确显示新周期额度已重置，或 GitHub API 明确证明仓库已变为 public 且当前标准 runner run 能正常启动；预计日期、邮件或旧截图都不是恢复证据。安全紧急修复也需要用户重新明确授权。

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

验证策略、只读规划器、薄兼容入口及其治理文档属于项目治理变更，只进入 Project Constraints。规划器输出的是待执行计划，不会自行触发 Actions；`full-delivery` 只声明交付强度，实际远端动作仍由受管交付控制器和本页状态门决定。

## Artifact 与保留期

- Bootstrap 成功只上传 `doctor.json` 和 `connections.json`；完整 `logs/setup-web.log` 只在失败时上传。
- Bootstrap 和 Windows Verify 的任务 artifact 保留 3 天。
- GitHub 仓库默认 Actions artifact/log retention 由仓库所有者设为 7 天；该设置不由本地代码自动修改。
- 若账户仍有 private 仓库或其他 included-usage 消耗，在 Billing 的 budgets/alerts 中启用 90% 与 100% 邮件提醒，但不得创建正额度预算、付款方式或允许付费超额。将提醒状态与仓库默认保留期一起记入月度记录。
- 每月记录总用量、各 workflow 次数、失败重跑数、平台耗时、估算权重和剩余额度。

## 当前状态与恢复证据

2026-09-17 先观测到 private 状态下 2,000 / 2,000 included minutes 和 billing-blocked，随后通过 GitHub API 确认仓库已改为 `PUBLIC`。提交 `76d1ea1053187569bb23d30f9a22b894ccbc0675` 的 Project Constraints、Research Web Checks 和 Bootstrap 双平台均正常启动并通过；repair 提交 `de39abcdbf3551c9985615e4cf80cd121a3a16b3` 的 Project Constraints、Research Web Checks 和 Windows Verify 也通过。因此当前状态是 `public-standard`，旧 billing-blocked 只作为历史证据保留，不再冻结标准 runner。

本次文档修正就是计划中的 docs-only 观察性提交：它只能创建 Project Constraints。若出现 Research Web Checks、Bootstrap、Windows、Tabbit 或 Desktop run，视为路由回归并修复后再关闭任务。

## 月度记录模板

```text
周期：YYYY-MM-DD → YYYY-MM-DD
仓库 visibility：public | private
计费状态：public-standard | metered
included usage（不适用时填 N/A）：____ / 2,000
Ubuntu：____ runs / ____ minutes
Windows：____ runs / ____ minutes
macOS：____ runs / ____ minutes
失败重跑：____
artifact storage：____ / 0.5 GB
当前状态：public-standard | normal | watch | constrained | critical | frozen
决定与原因：____
```
