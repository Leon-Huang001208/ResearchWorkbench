# DataHub 与 Asset Workbench 验证路由证据

## 状态与范围

- 本地证据状态：计划要求的 6 个 local validation 全部通过；5 个新增 direct catalog 均真实可执行并通过。
- 接受状态：`blocked`。唯一外部门 `project-constraints` 尚未运行；本任务不执行 prepare、publish、cleanup、GitHub dispatch 或 CI。
- 验证开始：`2026-09-24T06:49:13Z`。
- 工作树基线：在 `origin/master` 之后保留既有 17 个提交；本任务只新增 plan、receipt、report。Python 索引验证一致，未生成索引差异。
- 完整 changed set：11 个路径；plan 的 `risk=full-delivery`、`requiredLevel=L4`，原因是 verification policy、planner、policy contracts 与 skill workflow 属于 `verification-system`。

## 问题证据与批准设计

修复前存在三个方向相反的问题：`test_datahub_catalog.py` 会落入 `unknown_path` 并把已知 AKShare 改动误升到 L4；AKShare provider 源码会被通用 Research Web 规则缩到 L1；Workbench 测试会误选 framework catalog，而未登记的敏感 DataHub 源码又可能被通用低级规则接住。批准设计不是目录整体降级，而是：

1. 把 `app/research_web/datahub/` 设为 delegated namespace。
2. 只有 namespace 内正向 `files` / `prefixes` 可建立 owner；全局 `segments`、`suffixes` 和 namespace 外父 prefix 不能越界。
3. 只为 AKShare public provider 与 Asset Workbench UI/backend 建立精确 allowlist；未登记路径必须回到 L4 fallback。
4. 多个 delegated prefix 取最长命中；多高耦合组件按现有合同升至 L3；CI/schema/dependency/security/desktop/release 仍保留最高风险及全部门禁。
5. planner 仍只读，catalog 命令由执行阶段运行，receipt 独立证明真实结果。

## RED / GREEN 提交证据

| Task | RED | GREEN / 修复 |
| --- | --- | --- |
| 1：delegated match schema | `6061b8fa4`：38 total，37 pass / 1 expected fail（invalid match keys） | Task 2 实现后闭合 |
| 2：可选 `excludePrefixes` | `1ab4c290a` 首次 GREEN：policy 38/38、receipt 16/16；规格审查发现显式 `null` 被 `?? []` 接受。`d1cf5c3e1` 补测试后先为 37/38 | `d1cf5c3e1` 最终 policy 38/38、receipt 16/16；仅 `undefined` 使用缺省值 |
| 3：路由矩阵 | `e76d63314` 43 total=38/5；`301e8037a` 48=38/10；`9a2139801` 51=38/13；`d33094851` 54=38/16；`b4410e8e1` 56=38/18。失败均来自新增合同，既有 38 始终通过 | Task 4 policy 实现后闭合 |
| 4：catalog 与规则 | `59f4f1edd` 初始 policy 56/56，但独立质量审查发现 nested counterexample。`e9da5537a` 全局 namespace RED：60 total=56 pass / 4 expected fail | `3afc27f0a` policy 60/60；合并 Node policy+receipt+skill 81/81，full local 80/80；`f250f5fa1` 修正文案 |
| 5：文档 | 规格审查先后发现 longest/owner 定义不足、architecture map 与 verification policy 权威冲突、backend closure 漏 JS test | `2c8b6db06`、`f71d86010`、`463cf394d` 闭合；最终 governance 0 violation、index verified、skill 5/5、policy 60/60、diff clean |

## Global namespace blocker 与修复

初版 `excludePrefixes` 只让声明排除字段的当前规则退出。独立质量审查用
`app/research_web/datahub/workflows/new_provider.py` 复现：全局 critical-chain 的 `workflows` segment 仍能跨入 DataHub，导致未知路径错误地停在 L3，而不是 L4 fallback。这是安全 blocker，不是文案问题。

用户批准扩展为全局 namespace delegation 后，`e9da5537a` 加入 4 个 expected RED，覆盖 nested workflow/parser/README、owner collision 和 longest-prefix；`3afc27f0a` 在策略加载时汇总、去重并按长度降序 delegated prefixes，匹配前只保留正向 owner rules。最终这四类反例与原有 per-rule exclude 同时通过。

## Task 1-5 双审结论

- Task 1：规格审查 compliant；质量审查无 Critical/Important/Minor，Ready。确认 exact allowlist、unknown fallback、unsafe/null/unknown-field 覆盖。
- Task 2：规格初审发现 `null` 宽松接受；补 RED 并修复后规格通过。质量审查无问题，Ready。
- Task 3：规格/质量多轮补齐联合 changed-set 掩盖、逐文件路径、`asset_routes.py`、L0-L3 累积、动态 DataHub fallback、精确命令、高风险组合、每规则 signal smoke、UI/backend L4 gate retention；最终规格通过、质量 Ready。
- Task 4：初始规格通过；质量审查复现 global namespace blocker。批准并完成全局修复后，最终规格通过，质量 Ready/merge、无 file issues；确认 longest prefix、files/prefixes-only owner、nested fallback、owner collision、per-rule exclude 与高风险 gate union。
- Task 5：规格审查发现并闭合 owner/longest 定义、权威冲突和 backend closure 缺口；最终规格通过。质量 Ready；保留两个非阻塞建议：未来可增加新增文档语义断言，`DEVELOPMENT_MAP` 的重复映射还可继续降重。两项均未伪报为本次已实现。

## 代表性真实 planner 矩阵

下表均为独立运行真实 `scripts/plan_verification.mjs` 的输出摘要。`validations` 按 L0→L4 列出；未列层级为空。

| 路径 | risk / level | ruleIds / impactIds | validations | escalation / risk / external |
| --- | --- | --- | --- | --- |
| `app/research_web/datahub/providers_akshare.py` | local-only / L2 | `research-web-datahub-public-provider` / `datahub-public-provider` | L0 `documentation-governance, python-file-index`; L1 `research-web-architecture, research-web-datahub-public-provider`; L2 `project-constraints-local, research-web-datahub-core` | none / none / none |
| `app/research_web/ui/asset-workspace.mjs` | local-only / L1 | `research-web, research-web-asset-workbench-ui` / `research-web, asset-workbench-ui` | L0 `documentation-governance, python-file-index`; L1 `research-web-architecture, research-web-asset-workbench-ui` | none / none / none |
| AKShare + Asset UI | local-only / L3 | `research-web-datahub-public-provider, research-web, research-web-asset-workbench-ui` / `datahub-public-provider, research-web, asset-workbench-ui` | L0 docs+index；L1 architecture+provider+UI；L2 `project-constraints-local, research-web-datahub-core, research-web-asset-workspace-python`; L3 `research-web-asset-workspace-smoke` | `multiple_high_coupling_modules` L2→L3 / none / none |
| `app/research_web/asset_workspace.py` | local-only / L2 | `research-web, research-web-asset-workbench-backend` / `research-web, asset-workbench-backend` | L0 docs+index；L1 `research-web-architecture, research-web-asset-workbench-ui`; L2 `project-constraints-local, research-web-asset-workspace-python` | none / none / none |
| `providers_wind.py` | full-delivery / L4 | `fallback` / `unknown-boundary` | L0 `documentation-governance`; L4 `research-web-verification-full, project-constraints` | none / `unknown_impact_boundary` / `project-constraints` |
| `security.py` | full-delivery / L4 | `fallback` / `unknown-boundary` | 同上 | none / `unknown_impact_boundary` / `project-constraints` |
| `future_provider.py` | full-delivery / L4 | `fallback` / `unknown-boundary` | 同上 | none / `unknown_impact_boundary` / `project-constraints` |
| `.agents/verification-policy.json` | full-delivery / L4 | `ci` / `verification-system` | L0 docs；L1 `verification-policy-contracts, verification-receipt-contracts, incremental-validation-skill-contracts`; L4 full + external Project Constraints | none / none / `project-constraints` |
| `datahub/workflows/new_provider.py` | full-delivery / L4 | `fallback` / `unknown-boundary` | L0 docs；L4 full + external Project Constraints | none / `unknown_impact_boundary` / `project-constraints` |
| `datahub/parsers/new_provider.py` | full-delivery / L4 | `fallback` / `unknown-boundary` | 同上 | none / `unknown_impact_boundary` / `project-constraints` |
| `datahub/README.md` | full-delivery / L4 | `fallback` / `unknown-boundary` | 同上 | none / `unknown_impact_boundary` / `project-constraints` |

## 完整 changed set 与 plan

`git diff --name-only origin/master...HEAD` 的 8 个既有路径，加上本次 3 个证据路径，组成以下 11 个精确路径：

1. `.agents/skills/incremental-validation/README.md`
2. `.agents/verification-policy.json`
3. `docs/AGENT_WORKFLOW.md`
4. `docs/DEVELOPMENT_MAP.md`
5. `docs/superpowers/plans/2026-09-24-datahub-workbench-verification-routing.md`
6. `docs/superpowers/specs/2026-09-24-datahub-workbench-verification-routing-design.md`
7. `scripts/plan_verification.mjs`
8. `tests/javascript/verification_policy.test.mjs`
9. `.ai/reports/2026-09-24-datahub-workbench-routing-plan.json`
10. `.ai/reports/2026-09-24-datahub-workbench-routing-receipt.json`
11. `.ai/reports/2026-09-24-datahub-workbench-routing.md`

真实 plan 的 `changeSummary` 为 `fileCount=11`、`ruleIds=[ci, documentation]`、`impactIds=[verification-system, documentation]`；无 plan escalation、无预先 uncovered risk。required local IDs 是 policy、receipt、skill、full、documentation-governance、python-file-index；外部门是 `project-constraints`。

## Plan 要求的本地验证

| Level | ID | 结果 | 时长 | 实证摘要 |
| --- | --- | --- | ---: | --- |
| L0 | `documentation-governance` | passed | 0.16s | 507 files、71 current、`violations: []` |
| L0 | `python-file-index` | passed | 1.17s | `Verified docs/generated/py_file_index.md`，无生成差异 |
| L1 | `verification-policy-contracts` | passed | 4.01s | 60 passed、0 failed/skipped/todo |
| L1 | `verification-receipt-contracts` | passed | 1.53s | 16 passed、0 failed/skipped/todo |
| L1 | `incremental-validation-skill-contracts` | passed | 0.10s | 5 passed、0 failed/skipped/todo |
| L4 | `research-web-verification-full` | passed | 2.92s | 80 passed、0 failed/skipped/todo |

L2/L3 在本任务完整 plan 中为空。所有 required local IDs 都以本报告作为 receipt evidence。外部 `project-constraints` 记为 `not_run`，因此 receipt 结果必须是 `blocked`。

## 五个 direct catalog 实跑

Python 命令统一使用既有 `/Users/leon/Desktop/Projects/ResearchWorkbench-dev-venv-backup-20260924/bin/python`，并为测试进程清除 `ALL_PROXY/all_proxy/HTTP_PROXY/http_proxy/HTTPS_PROXY/https_proxy`；未安装依赖。

| Catalog | 结果 | 时长 |
| --- | --- | ---: |
| `test_datahub_catalog.py` | 27 passed，1 warning | 10.29s |
| `test_datahub.py` | 51 passed | 20.97s |
| `research_web_workbench.test.mjs` | 10 passed，0 skipped/todo | 0.12s |
| `test_asset_workspace.py` | 3 passed，1 warning | 18.98s |
| L3 `test_asset_observation_tracks_each_block_and_freezes_handoff_context` | 1 passed，1 warning | 6.96s |

附加静态检查：`node --check scripts/plan_verification.mjs` 通过（0.03s）；首次 `git diff --check` 通过（0.02s）。

最终证据闭环中，完整 11 路径的本地 Project Constraints 检查通过（0.16s，`violations: []`）。这只是本地约束执行，不等于外部 `.github/workflows/project-constraints.yml` 已运行；receipt 中该 external gate 仍如实为 `not_run`。receipt validator 通过（0.03s），输出 `valid=true`、`result=blocked`、planned/actual L4、executedCount 6、escalationRequired false。最终 governance、index、JSON/Node 语法与 diff 格式会在提交前再跑一次。

## 失败、重规划与工具环境

- 第一次矩阵摘要命令使用了环境不存在的 `jq`，planner 因下游提前关闭收到 `EPIPE`；没有产生或执行 plan。改用 Node 解析 stdout 后，全部矩阵成功。
- macOS 自带 Bash 不支持 `mapfile`；完整 changed set 采集改为 Bash 3 兼容的数组循环后成功。
- 两项均属于证据脚本/格式化工具兼容问题，不是产品 validation failure，也没有失败的本地 validation，因此未伪造 `validation_failure` 或 `unexpected_behavior` signal 重规划。保存的 plan 与所有执行项均来自成功的真实 planner 输出。

## 架构、平台边界、P4 收益与未知风险

- 架构边界：本次只改变 verification policy、只读 planner、合同测试与治理文档；不改变 Research Web API、运行时、数据模型、数据库或用户界面。delegated namespace 是候选规则隔离，不是风险覆盖或优先级捷径。
- 平台边界：L1-L3 专项闭包只服务 Web；不会凭空加入 desktop、Tauri、sidecar、installer 或 native Windows 门。当前任务因验证系统自身变更仍正确到 L4。
- P4 收益：已知 AKShare / Asset Workbench 改动现在获得与组件耦合匹配的 L1-L3 快环，减少误触发 L4 和无关 framework catalog；同时未知 DataHub 边界从可能被通用规则缩窄，改为机械 L4 fail-closed。收益是更快且更可信的反馈，不以削弱硬门换速度。
- 未知风险：GitHub `project-constraints` 尚未运行，receipt 因此外部阻塞；真实 CI runner 与远端集成状态不在本任务证据内。Windows 没有运行，也不得宣称 Windows 已验证。direct tests 的两条依赖 deprecation warning 未影响通过，但仍是上游环境债务。Task 5 两个非阻塞文档建议仍待未来处理。

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"This evidence records verification-policy routing and local acceptance without changing Research Web product topology, APIs, runtime components, or platform ownership.","diagrams":[]} -->
