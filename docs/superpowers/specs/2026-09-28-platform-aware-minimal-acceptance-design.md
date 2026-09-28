# Platform-aware Minimal Acceptance Design

## 目标与边界

Research Workbench 在现有只读 Verification Router、L0-L4 风险分层和 fail-closed fallback 上增量建立 `Component × Risk × Platform` 三维验收模型。GitHub 是 Git-managed source code 的唯一真相源，`master` 是唯一长期集成分支；macOS 是主要开发与本地验证环境，Windows 是原生兼容、安装、运行、集成和实机验证环境。设备、Git 分支和发布产物保持为三个不同维度。

本次不重写已经通过合同测试的匹配、风险合并、升级信号、路径安全或 Desktop workflow。普通 Research Web UI 和纯业务逻辑仍使用最小 generic closure；未知路径、公开契约、schema、依赖、CI、安全、桌面和发布边界继续 fail closed。规划器仍然只读，不运行 Git、测试、CI、发布或策略中的命令。

## 已确认现状

- 当前远端仓库为 public，默认分支和唯一远端长期分支均为 `master`；本地 tracked `master` 与 `origin/master` 同步。
- 当前 policy schema v2 有 25 条规则，已有 L0-L4、风险升级、delegated namespace、严格路径校验和外部门回执，但没有正式 platform 维度。
- 当前 planner 对 pure Python、普通 UI、setup/runtime、Windows launcher、Desktop 和 unknown path 均不输出 `platforms`。
- Research Web macOS Bootstrap 按路径自动运行；当前 Windows Web workflow 仅有 `workflow_dispatch`。
- Desktop Verify 和 Desktop Release 已在原生 macOS/Windows runner 上构建，保持现状。
- 当前历史证据包含 plan schema v2 和 receipt schema v1；迁移不得使这些证据失去只读复核能力。
- 根 `.gitattributes` 只保护 vendor 字节与三个 launcher，普通源码和文档没有显式换行合同；`.venv` 只被本机 `.git/info/exclude` 忽略，仓库规则未覆盖 `.venv.broken-*` 和 `.codex/`。
- GitHub `master` 当前未设置 branch protection；本次只建立仓库内契约，不在未获独立授权时修改 GitHub 设置。

## Policy schema v3

`.agents/verification-policy.json` 继续是唯一策略真源。schema v3 顶层只允许：

- `schemaVersion`
- `riskOrder`
- `levelOrder`
- `platformOrder`
- `statusOrder`
- `escalation`
- `catalogs`
- `rules`
- `fallback`

`riskOrder` 和 `levelOrder` 保持现有语义。`platformOrder` 固定为：

1. `generic`
2. `linux`
3. `macos`
4. `windows`
5. `cross-platform`
6. `real-machine-required`

`statusOrder` 固定为 `PASS`、`FAIL`、`SKIPPED`、`NOT_REQUIRED`、`NOT_RUN`、`BLOCKED`、`MANUAL_REQUIRED`。这些是新 plan/receipt 的唯一规范状态；旧 receipt 的小写状态只通过 legacy 解析分支读取，不进入新输出。

Catalog 分为 `tests`、`documentation`、`ci`、`realMachine`。每个条目严格包含：

- `level`：L0-L4；
- `lane`：`local`、`ci` 或 `real-machine`；
- `gate`：`merge` 或 `release`；
- `platforms`：按 `platformOrder` 去重排列的平台列表；
- `value`：命令、workflow 定位或实机验收文档定位，仅复制、不执行。

每条 rule 和 fallback 增加 `platforms` 与 `realMachine` 引用。现有 `impact` IDs 继续作为策略中的 component IDs；planner 额外输出去重的 `components`，不复制另一套 component 表。Fallback 固定为 L4/`full-delivery`/`unknown_path`/`cross-platform` 并保留 `unknown_impact_boundary`，不得臆测具体原生平台已经通过。

## Planner schema v3

新 planner 输出保留现有 changed set、impact、reasons、escalations、uncovered risks 和逐级验证，同时增加：

- `components`：从命中规则的 `impact` IDs 得到的稳定组件列表；
- `platforms`：规则平台与实际选中 catalog 平台的有序并集；
- `local`：lane 为 `local` 的选中项；
- `ci`：lane 为 `ci` 的选中项；
- `realMachine`：lane 为 `real-machine` 的选中项；
- `receiptTemplate.requiredValidationIds`：本地 merge validations；
- `receiptTemplate.externalGateIds`：CI merge gates；
- `receiptTemplate.releaseGateIds`：实机 release gates。

Validation item 固定包含 `id`、`level`、`lane`、`gate`、`platforms`、`category`、`value`。Planner 仍按完整 changed set 取最高风险和最高等级，按 L0→L4 累积验证；platform 不得降低 risk 或 level。

## Receipt schema v2 与状态语义

新 receipt 使用规范大写状态，并分为：

- `executed`：本地 validation；
- `external`：CI merge gate；
- `realMachine`：真实设备 release gate；
- `result`：`PASS`、`FAIL` 或 `BLOCKED`；
- `mergeReady`：所有 merge gate 是否满足；
- `releaseReady`：所有 release gate 是否满足。

对 plan 中已选中的必需项：

- `PASS` 是唯一正向证明；
- `FAIL` 触发失败与升级；
- `BLOCKED`、`NOT_RUN`、`SKIPPED` 或 `MANUAL_REQUIRED` 不能产生 merge-ready；
- `NOT_REQUIRED` 对已选中的必需项非法。

对 release-only real-machine gate，`MANUAL_REQUIRED` 或 `NOT_RUN` 不否定已通过的 PR merge gate，但必须令 `releaseReady=false`，且不能显示为 Windows 实机 PASS。Windows CI `PASS` 与 Windows Real Machine `MANUAL_REQUIRED` 必须同时保留，不能合并成单一 “Windows PASS”。

Validator 保留 legacy 分支，继续验证现有 plan schema v2 + receipt schema v1，不修改历史 JSON。新 planner 只生成 schema v3，新实现任务只生成 receipt schema v2。

## 平台路由

代表性路由固定为：

- Pure Python 业务逻辑：`generic`，focused local tests；不触发原生 macOS/Windows full CI。
- 普通 Research Web UI：`generic`，focused Web tests；不触发 Windows native CI。
- `scripts/setup_web.py`、共享依赖或跨平台 runtime：`cross-platform + macos + windows`，要求 macOS Bootstrap 与 Windows Verify。
- `setup-web.sh` / `rwb`：`macos`，要求 macOS Bootstrap。
- `setup-web.cmd` / `rwb.cmd`：`windows`，要求 Windows Verify，不因文件名而伪加 macOS 证明。
- Windows local integration、path、encoding、subprocess 或 Windows runtime adapter：`windows`，要求 Windows Verify。
- Desktop/Tauri/sidecar：`cross-platform + macos + windows + real-machine-required`，保留原生 Desktop Verify；真实 Windows 安装作为 release gate。
- Unknown path：L4/`full-delivery`/`cross-platform`，保留未覆盖风险，不伪报任何具体平台通过。

## Conditional Platform CI

`.github/workflows/research-web-windows-verify.yml` 保留 `workflow_dispatch`，增加 `pull_request` 和 `master` push 的窄路径触发。正向路径覆盖共享 Web 安装、依赖、runtime、service lifecycle、Windows launcher、Windows local integration、Windows workflow 和其契约测试；普通 UI、文档、纯 framework/DataHub 业务代码不触发 Windows runner。

Windows workflow 保留既有 local-integration test、loopback smoke 和三天证据，同时对 platform-sensitive changed set 从 clean checkout 执行公开 `setup-web.cmd --no-start`、`rwb.cmd` start/doctor/stop 与 setup contracts，确保 launcher 触发的是相关验证。macOS Bootstrap 移除纯 Windows launcher 路径，继续覆盖 macOS launcher、共享安装、依赖和跨平台 runtime。Actions 合同从 policy 机械枚举确定性 matcher，并同时验证正向与负向代表路径，防止两个 workflow 的 path filters 漂移。

Desktop Verify/Release 的 job、runner、sidecar、数据库和打包逻辑不修改；policy 只显式投影既有 macOS 与 Windows gate，并新增真实 Windows 安装 release gate。

## Git、Worktree 与文件语义

`docs/AGENT_WORKFLOW.md` 成为设备、branch、worktree、verification、PR、merge 与 cleanup 的权威 SOP：

`master → short-lived branch/worktree → local minimal acceptance → PR → routed CI → merge → cleanup`

远端长期只保留 `master`；短期分支使用 `feat/*`、`fix/*`、`refactor/*`、`codex/*`、`platform/windows/*`、`platform/macos/*`。Mac/Windows 之间只通过 GitHub 同步 Git-managed source；Windows 默认 fast-forward 最新 `master` 并验证，发现 Windows-only 缺陷后才创建 `platform/windows/*`。

`.gitattributes` 增量加入 Python、JavaScript、TypeScript、JSON、YAML、Markdown 和 shell 的 LF 规则，以及 `.cmd`、`.bat`、`.ps1` 的 CRLF 规则；现有 vendor `-text` 规则保留并优先保护 hash-sensitive 字节。`.gitignore` 增加仓库级 `.venv*` 与 `.codex/` 机器状态规则，不清理现有用户文件。

Branch protection 是 GitHub 外部状态。仓库内文档会明确“原则上禁止直接在 master 开发”，但本任务不调用 GitHub API 修改 protection/ruleset，也不把文档约定伪称为远端机械强制。

## 验证与代表性场景

实现采用 TDD，先添加失败合同再修改 policy/planner/validator/workflow。至少覆盖：

- A：pure Python → generic focused；
- B：普通 Research Web UI → generic focused，无 Windows；
- C：shared setup/runtime → macOS + Windows；
- D：Windows launcher → Windows required；
- E：Desktop → 原生 macOS + Windows merge gates，真实 Windows release gate；
- F：unknown path → L4 fail closed；
- G：Windows CI `NOT_RUN` → `mergeReady=false`，不得 PASS；
- H：Windows CI `PASS` + Windows Real Machine `MANUAL_REQUIRED` → `mergeReady=true`、`releaseReady=false`。

同时验证 legacy plan/receipt 仍可读取、非法 platform/status/schema fail closed、planner 不执行 catalog 命令、workflow 正负路径、Git attributes/ignore 语义、文档治理、Python 生成索引、Research Web 架构和 Project Constraints。任何外部 CI 或真实 Windows 未执行时必须保留实际状态，不得用本地 macOS 结果替代。

## 非目标与授权边界

- 不新增长期 macOS/Windows/develop 分支。
- 不维护两套业务源码。
- 不重构 Desktop job 主体。
- 不安装新的 Python、Node 或系统依赖。
- 不修改 GitHub branch protection、仓库设置、密钥、账单或 runner 设置。
- 不在未获发布授权时 push、创建/合并 PR、dispatch workflow、tag 或 release。
- 不删除主 checkout 的历史 untracked 文件、旧 branch、旧报告或用户环境。
