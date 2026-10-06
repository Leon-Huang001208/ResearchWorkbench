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
| 安装器、Web 锁、启动器、固定 DSH/CJPY、服务装配 | Research Web Checks + Bootstrap（自动 `macos-14`） | Windows Web 自动验证、Desktop |
| Docker 打包、共享运行时契约/控制器、容器认证与凭据边界 | Research Web Docker（Ubuntu，amd64/arm64）；共享 Native 合同仍进入 Bootstrap | 普通文档/UI 不触发 Docker；不代替 Native 或 Desktop |
| Windows 路径、认证文件、本机集成、服务管理 | Research Web Checks；Windows Verify 仅用户显式 `workflow_dispatch` | Desktop |
| Tabbit 平台合同 | 用户显式 `workflow_dispatch` | 普通 push／PR 自动触发 |
| 桌面专属路径 | Desktop Verify | 普通 Web workflow 不能替代桌面门禁 |
| Desktop Release | tag 或显式 dispatch | 普通 push |

Project Constraints 保持所有 PR 和 `master` push 自动执行；自动 workflow 必须设置 concurrency、`cancel-in-progress: true` 和明确超时。Research Web Bootstrap 当前只自动运行 `macos-14`；Windows Web workflow 保留原生 `windows-2022` 任务与 3 天证据，但仅在用户显式手动触发时运行。未执行的 Windows 任务不得写成已通过，且这一 Web 路由边界不改变 Desktop Verify 的独立 Windows 规则。
Research Web Checks 的 Python 部分固定为协议、集成协调、文档服务、文档同步与 CLI 懒加载合同，JavaScript 部分运行 `research_web*.test.mjs`。完整 `tests/research_web/` 仍在本地交付或高风险变更中按影响面运行，不能偷偷扩进日常 workflow；需要扩大自动测试时先以最近 5 次成功耗时重新评估额度。

验证策略、只读规划器、薄兼容入口及其治理文档属于项目治理变更，只进入 Project Constraints。规划器输出的是待执行计划，不会自行触发 Actions；`full-delivery` 只声明交付强度，实际远端动作仍由受管交付控制器和本页状态门决定。

Docker 路由的专项例外是 `.agents/verification-policy.json`、`tests/javascript/verification_policy.test.mjs` 及 Docker/额度契约测试：它们同时触发容器门，防止门禁 ID 与实际工作流脱节。门禁 ID 为 `.github/workflows/research-web-docker.yml#docker-runtime`。普通治理文档、产品文档和 UI 仍不触发 Docker。

Research Web Docker 使用标准 `ubuntu-24.04`，两个矩阵项 `linux/amd64`、`linux/arm64` 串行执行（`max-parallel: 1`），每项最多 60 分钟；仅 arm64 设置 QEMU，Buildx 只加载本机镜像、不推送 registry。按提交与架构唯一标记镜像，构建前验证 Dockerfile 与共享运行时版本锁一致。只对相关路径触发，取消同 ref 的旧运行；两个矩阵项最多使用 120 Linux runner 分钟，不配置外部缓存或扩大 runner。

容器门执行 Compose 校验、镜像构建、8088 Web 与容器内 3081 认证健康、重启、非秘密数据跨 down/up 持久化、最终 down 与宿主端口释放；每项使用独立临时 data/state/credential 挂载，最后清理。它证明 Linux 镜像行为，不能替代 GitHub macOS Native Bootstrap，也不证明 Windows Native、Docker Desktop 集成或桌面产品。首次远端运行前，本地静态合同通过不等同于两架构构建和运行已通过。

## Artifact 与保留期

- Bootstrap 成功上传 `doctor.json`、`connections.json`、首页 `root.html` 和主静态模块 `app.mjs`，证明干净 runner 的安装/产品 ready 与页面资源可读取；完整 `logs/setup-web.log` 只在失败时上传。
- Bootstrap 和 Windows Verify 的任务 artifact 保留 3 天。
- Docker 成功 artifact 只含固定字段的健康摘要、Compose 服务名及固定阶段/数字退出码；失败 artifact 保留经过秘密模式扫描的固定事件分类计数，并附同样的阶段/退出码 JSON。启动失败还可保留最多 16 条精确五字段摘要（固定阶段、受控异常类别、errno、runtime/web 退出码），只接受白名单与有界整数。全部原始行被省略，原始 build/runtime/container 日志和凭据目录不上传。Docker artifact 保留 3 天。
- GitHub 仓库默认 Actions artifact/log retention 由仓库所有者设为 7 天；该设置不由本地代码自动修改。
- 若账户仍有 private 仓库或其他 included-usage 消耗，在 Billing 的 budgets/alerts 中启用 90% 与 100% 邮件提醒，但不得创建正额度预算、付款方式或允许付费超额。将提醒状态与仓库默认保留期一起记入月度记录。
- 每月记录总用量、各 workflow 次数、失败重跑数、平台耗时、估算权重和剩余额度。

## 当前状态与恢复证据

2026-09-17 先观测到 private 状态下 2,000 / 2,000 included minutes 和 billing-blocked，随后通过 GitHub API 确认仓库已改为 `PUBLIC`。提交 `76d1ea1053187569bb23d30f9a22b894ccbc0675` 的 Project Constraints、Research Web Checks 和 Bootstrap 双平台均正常启动并通过；repair 提交 `de39abcdbf3551c9985615e4cf80cd121a3a16b3` 的 Project Constraints、Research Web Checks 和 Windows Verify 也通过。因此当前状态是 `public-standard`，旧 billing-blocked 只作为历史证据保留，不再冻结标准 runner。

docs-only 提交只能创建 Project Constraints。若出现 Research Web Checks、Bootstrap、Windows、Tabbit 或 Desktop run，视为路由回归。平台敏感提交则以 verification policy 与 workflow 路径合同共同决定验收责任，不从历史 run 推断当前 gate 已通过。

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
