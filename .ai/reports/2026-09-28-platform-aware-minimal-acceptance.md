# Platform-aware Minimal Acceptance 验证报告

## 范围与当前状态

- 分支：`codex/platform-aware-minimal-acceptance`。
- 基线：`6dee571f53de62faae7ac3bf22dda6b9607c839c`。
- 实现位于外部 sparse worktree；主 checkout 的历史 untracked 文件未修改或清理。
- Policy / planner：schema v3；receipt：schema v2；历史 plan v2 / receipt v1 继续只读兼容。
- 当前 changed set：30 个精确仓库相对路径；最终 plan 为 `full-delivery / L4`。
- 当前外部状态：4 个 CI merge gate 均尚未运行；不能写成 `PASS`。本次未修改 Desktop-owned path，因此最终 plan 没有 real-machine release gate。

## A-F 真实 Planner 矩阵

以下均为独立执行 `node scripts/plan_verification.mjs --project . --changed-file <path>` 的实际输出摘要。

| Case | changed file | components | risk / level | platforms | CI | real machine | uncovered risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | `app/research_web/frameworks/goldar/context.py` | `research-web, framework-backend` | `local-only / L1` | `generic` | none | none | none |
| B | `app/research_web/ui/app.mjs` | `research-web, research-web-ui` | `local-only / L1` | `generic` | none | none | none |
| C | `scripts/setup_web.py` | `web-installation` | `full-delivery / L4` | `generic, linux, macos, windows, cross-platform` | Project Constraints, Web Checks, macOS Bootstrap, Windows Verify | none | none |
| D | `setup-web.cmd` | `web-installation` | `full-delivery / L4` | `generic, linux, windows` | Project Constraints, Web Checks, Windows Verify | none | none |
| E | `src-tauri/tauri.conf.json` | `desktop-platform` | `full-delivery / L4` | `generic, linux, macos, windows, cross-platform, real-machine-required` | Project Constraints, native macOS Desktop, native Windows Desktop | Windows installation | none |
| F | `future/platform/new_adapter.py` | `unknown-boundary` | `full-delivery / L4` | `generic, linux, cross-platform` | Project Constraints | none | `unknown_impact_boundary` |

Case D 没有 macOS Bootstrap；Case E 的 hosted CI 与 Windows Real Machine 是不同 gate；Case F 没有因为 unknown path 被猜测成某个具体平台。

## G-H Receipt 语义

`node --test tests/javascript/verification_receipt.test.mjs` 实测 21/21 通过，其中：

- G：必需 `research-web-windows-verify=NOT_RUN` 时，validator 返回 `result=BLOCKED`、`mergeReady=false`、`releaseReady=false`，并要求 `external_gate_not_run:research-web-windows-verify`。
- H：`native-windows-desktop=PASS` 且 `windows-desktop-installation=MANUAL_REQUIRED` 时，validator 返回 `result=PASS`、`mergeReady=true`、`releaseReady=false`。它不会输出单一的 “Windows PASS”。
- 非规范小写状态、已选 gate 的 `NOT_REQUIRED`、缺失 lane evidence、false-positive readiness 和没有普通证据文件的 real-machine `PASS` 均被拒绝。
- 历史 plan v2 / receipt v1 fixture 仍通过，旧 JSON 未改写。

## RED → GREEN 证据

| Contract | RED | GREEN |
| --- | --- | --- |
| Policy / planner | `beb1f6f89`：66 total，49 pass / 17 expected fail | `5e68501d8`：66/66 pass |
| Receipt / readiness | `2dd905990`：21 total，2 pass / 19 expected fail；legacy fixture 已通过 | `18b7a812f`：21/21 pass |
| Conditional Actions | 12 total，5 pass / 7 expected fail | `37a20b6f7`：12/12 pass |
| Git semantics | 3 total，1 pass / 2 expected fail | `76a830d6d`：3/3 pass |

## Changed-set Plan 与升级

- 初始 plan：26 files，L4；`documentation-governance=PASS`，第一次 `python-file-index` 在 sparse checkout 中因受管 Python 文件未全部检出而失败。
- 诊断证据：仓库共有 1302 个 tracked Python 文件；生成器声明的 15 个源码目录在补充 sparse patterns 后逐目录 `tracked == actual`。未运行生成命令，没有制造错误索引 diff。
- 按政策用 `--signal validation_failure` 重规划；最终 plan 包含 30 files，仍为 L4，记录 `validation_failure: L4 → L4`，local closure 未缩小。新增两份文件是 Project Constraints 明确要求同步的 documentation group 权威文件。
- 初始 plan 保存在 `2026-09-28-platform-aware-minimal-acceptance-initial-plan.json`，最终 signal plan 保存在 `2026-09-28-platform-aware-minimal-acceptance-plan.json`。

## 本地验证进度

| Level | ID | 当前结果 | 证据 |
| --- | --- | --- | --- |
| L0 | `documentation-governance` | PASS | 511 files、73 current、0 violations |
| L0 | `python-file-index` | PASS after environment correction | `Verified docs/generated/py_file_index.md`；首次 sparse failure 已保留并触发重规划 |
| L1 | `verification-policy-contracts` | PASS | 66/66 |
| L1 | `verification-receipt-contracts` | PASS | 21/21 |
| L1 | `incremental-validation-skill-contracts` | PASS | 5/5 |
| L1 | `repository-cross-platform-contracts` | PASS | 3/3 |
| L1 | `research-web-local-integrations` | PASS after interpreter/environment correction | 45 passed、1 native-Windows skip、1 upstream warning；未安装依赖 |
| L1 | `research-web-architecture` | PASS | 62/62 |
| L2 | `project-constraints-local` | PASS | 30 checked files、0 violations；首次 sparse reference failure 后补检出受跟踪 artifact/vendor/entrypoint，并同步完整 documentation group |
| L3 | `research-web-critical-smoke` | PASS | 19/19 |
| L4 | `research-web-verification-full` | PASS | 84/84；architecture、documentation governance、Actions routing、Git semantics |

第一次 Python suite 使用 Homebrew Python 时因没有 pytest 无法启动；随后复用已有 Python 3.12.13 dev venv（pytest 9.1.1），未安装依赖。首个完整运行暴露旧 manual-only workflow 断言和一次不可复现的 Excel 状态失败；更新已批准的 conditional workflow 合同后，两个失败点定点 2/2 通过，完整 suite 复跑 45 passed / 1 native-Windows skip。没有修改 local-integration 业务代码。

执行技能的 `.superpowers` ledger 最初未被项目忽略；新增真实 `git check-ignore --no-index` RED 后，在 `.gitignore` 增加 `.superpowers/` 并复跑 Git semantics 3/3 GREEN。Ledger 是本机恢复状态，未进入提交。

最终本地 closure 的 11 个 required IDs 均为 `PASS`。Receipt validator 对最终 plan/receipt 实际输出 `valid=true`、`result=BLOCKED`、planned/actual L4、executedCount 11、externalCount 4、realMachineCount 0、`mergeReady=false`、`releaseReady=false`（0.09s）。

## 外部 Gate 与交付状态

最终 plan 选择以下 merge gate，均未获授权运行，且没有被本地结果替代：

| Gate | 状态 | 含义 |
| --- | --- | --- |
| `project-constraints` | `NOT_RUN` | GitHub Ubuntu gate 未运行；本地 Project Constraints 已单独 PASS，但不是远端回执 |
| `research-web-checks` | `NOT_RUN` | GitHub Ubuntu Research Web Checks 未运行 |
| `research-web-bootstrap` | `NOT_RUN` | GitHub `macos-14` clean bootstrap 未运行 |
| `research-web-windows-verify` | `NOT_RUN` | GitHub `windows-2022` conditional verification 未运行 |

因此 receipt 必须保持 `BLOCKED`、`mergeReady=false`、`releaseReady=false`。本次 changed set 没有 Desktop-owned path，`realMachine=[]` 是未选择而不是实机 PASS。

## 架构与平台边界

- 本次改变验证策略、只读 planner/validator、Web workflow triggers、Git 文件语义和开发者文档，不改变 Research Web API、DSH 研究引擎、数据模型或运行时拓扑。
- Desktop Verify/Release job 主体没有修改；Desktop 仅作为代表性路由 fixture。
- GitHub branch protection 当前未配置，本次没有调用 API 修改外部设置；仓库文档只陈述项目契约。
- 没有 push、PR、workflow dispatch、merge、tag 或 release。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"This change formalizes verification, Git workflow and platform evidence contracts without changing Research Web product topology, API ownership, runtime components or data flow.","diagrams":[]} -->
