# Verification Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the managed feature worktree. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 ResearchWorkbench 仅根据项目内策略和改动路径生成 fail-closed、机器可读、绝不执行命令的最小验收计划。

**Architecture:** `.agents/verification-policy.json` 保存唯一规则真源，`scripts/plan_verification.mjs` 负责严格解析、路径安全检查、逐文件匹配、最高风险与门集合合并。Project Constraints 保持独立硬门，兼容命令与文档只引用规划器，不复制路由表。

**Tech Stack:** Node.js ESM、`node:test`、JSON、Markdown、现有 Project Constraints 与受管 iteration-delivery；不新增依赖。

---

### Task 1: 冻结 CLI 与路由合同

**Files:**
- Create: `tests/javascript/verification_policy.test.mjs`
- Update evidence: `.ai/reports/verification-policy-PROGRESS.md`

- [x] **Step 1: 建立真实 CLI fixture**

  用 `fs.mkdtempSync` 创建临时项目，写入策略文件和代表性改动文件；通过 `spawnSync(process.execPath, [plannerPath, '--project', root, ...])` 运行真实规划器。fixture 提供 `run(files)`、`writePolicy(value)` 与 `parseSuccess(result)`，测试退出码、stdout JSON、stderr JSON 和磁盘副作用，不 mock 规划器。

- [x] **Step 2: 覆盖最小与升级路由**

  分别断言：
  - `app/research_web/ui/app.mjs` 与 `app/research_web/service.py` 为 `local-only`，所有门 ID 均不包含 `desktop`、`windows`、`tauri`、`sidecar`、`installer`；
  - `docs/AGENT_WORKFLOW.md` 为 `docs-only`，测试数组为空，文档与 CI 仅包含文档治理、生成索引和 Project Constraints；
  - `contracts/public-api.json`、`schemas/result.schema.json`、`requirements/web.lock`、`.github/workflows/checks.yml`、`security/policy.md`、`release/manifest.json`、`src-tauri/tauri.conf.json` 各自为 `full-delivery`；
  - 桌面样例包含 `desktop-packaging` 与 `native-windows-desktop`，其他高风险样例不因此获得桌面门；
  - `unmapped/new-area.txt` 以 `unknown_path` 原因 fail-closed 到 `full-delivery`；
  - 重复与多文件输入去重，风险取最高档，门 ID 不重复。

- [x] **Step 3: 覆盖安全与只读合同**

  写入破损 JSON，分别把策略文件和改动文件替换为符号链接，并传入 `../outside.txt`、绝对路径、反斜杠路径；断言退出非零且稳定错误码分别为 `POLICY_ERROR` 或 `PATH_ERROR`。向测试策略目录放入命令 `node -e ...writeFileSync(marker)...`，运行规划器后断言 marker 不存在，证明目录中的命令只被复制而未执行。

- [x] **Step 4: 运行测试并记录预期 RED**

  Run: `node --test tests/javascript/verification_policy.test.mjs`

  Expected: FAIL，根因必须是 `scripts/plan_verification.mjs` 尚不存在；若因测试语法、fixture 或无关环境失败，先修正测试直到得到这个预期失败。把命令、tests/pass/fail/skipped/todo 与关键失败原因写入 PROGRESS，随后才允许创建实现。

### Task 2: 实现严格策略与只读规划器

**Files:**
- Create: `.agents/verification-policy.json`
- Create: `scripts/plan_verification.mjs`
- Inspect unchanged: `.agents/project-constraints.json`
- Update evidence: `.ai/reports/verification-policy-PROGRESS.md`

- [x] **Step 1: 写入唯一策略真源**

  顶层固定为：

  ```json
  {
    "schemaVersion": 1,
    "riskOrder": ["docs-only", "local-only", "full-delivery"],
    "catalogs": {"tests": {}, "documentation": {}, "ci": {}},
    "rules": [],
    "fallback": {"risk": "full-delivery", "reason": "unknown_path", "tests": [], "documentation": [], "ci": []}
  }
  ```

  在 catalogs 中登记稳定门 ID；在 rules 中先写高风险与桌面规则，再写 docs 和 Web 规则。规则可以并行命中，最终由 riskOrder 决定最高风险，因此规则顺序不承担降级语义。

- [x] **Step 2: 实现参数、路径与策略校验**

  `parseArgs(args)` 只接受一次 `--project` 与至少一次可重复 `--changed-file`。`normalizeChangedFile` 拒绝控制字符、反斜杠、绝对与越界路径。`safeProjectRoot` 拒绝符号链接项目参数；`assertNoSymlinkComponents` 检查策略与改动路径的所有已存在组件。`loadPolicy` 捕获 JSON 解析失败并逐层执行 exact-key、数组/字符串、唯一 ID、catalog 引用、riskOrder 与 fallback 校验。

- [x] **Step 3: 实现匹配与合并**

  `matches(rule.match, file)` 对 exact file、prefix、完整 path segment 与 suffix 做 OR 匹配。每个文件收集全部命中规则；无匹配时使用 fallback。`planVerification` 按 riskOrder 取最高档，按输入首次出现顺序去重 changedFiles、reason 与各类门，并将 catalog 字符串投影为 `{id, value}`。

- [x] **Step 4: 实现稳定错误输出且不执行命令**

  定义带 `code` 的 `PlannerError`。CLI 只使用 `fs`、`path` 与 `url`；不导入 `child_process`，不写文件。成功只向 stdout 写一份 JSON；已知错误向 stderr 写稳定 JSON 并退出 1，意外错误转换为 `INTERNAL_ERROR`，不暴露堆栈或主机路径。

- [x] **Step 5: 核对 Project Constraints 边界并保持现状**

  首轮全改动检查证明：仅登记新文件也会触发 documentation 模块的五份权威文档同步，而这些路径不在任务白名单内。删除该可选登记，保持 `.agents/project-constraints.json` 无 diff；不伪造 changed-file，不复制任何规则或命令，并由策略测试、当前文档及完整交付保护新增文件。

- [x] **Step 6: 运行策略测试并记录 GREEN**

  Run: `node --test tests/javascript/verification_policy.test.mjs`

  Expected: 所有测试通过，failed=0、skipped=0、todo=0。把完整计数和时长写入 PROGRESS。

### Task 3: 恢复薄入口并同步当前文档

**Files:**
- Create: `.claude/commands/verify-task.md`
- Modify: `docs/AGENT_WORKFLOW.md`
- Modify: `docs/DEVELOPMENT_MAP.md`
- Modify: `docs/superpowers/specs/2026-09-22-verification-policy-design.md`
- Modify: `docs/superpowers/plans/2026-09-22-verification-policy.md`
- Update evidence: `.ai/reports/verification-policy-PROGRESS.md`
- Maintain: `.ai/reports/verification-policy-BLOCKED.md`

- [x] **Step 1: 写薄兼容入口**

  文档只给出 `node scripts/plan_verification.mjs --project . --changed-file <仓库相对路径>`，说明多文件重复参数、读取 JSON 后按实际输出逐项执行、策略真源路径，以及规划器本身不运行命令；不列出路由表。

- [x] **Step 2: 更新工作流与开发地图**

  在 `AGENT_WORKFLOW.md` 增加“先规划再选择验证”的机器入口、Web-only 桌面门为零和高风险/未知升级。`DEVELOPMENT_MAP.md` 将策略与规划器加入规则/交付映射和最小验证示例，明确 Project Constraints 不拥有路由表。

- [x] **Step 3: 自检文档没有漂移**

  Run: `rg -n "verification-policy|plan_verification|full-delivery|Web-only" .claude/commands/verify-task.md docs/AGENT_WORKFLOW.md docs/DEVELOPMENT_MAP.md docs/superpowers/specs/2026-09-22-verification-policy-design.md`

  Expected: 入口只引用规划器；路由合同只在策略/设计中解释；当前文档明确 Web-only 与 fail-closed。

- [x] **Step 4: 合法分类受跟踪的兼容入口**

  用户扩大白名单后，在 `docs/documentation-governance.json` 将 `.claude/commands/` 分类为 `package-internal`，同步 documentation 架构组的五份权威文档，并在本任务 PROGRESS 中记录 `structure: unchanged`；不修改 workflow 或架构图。

### Task 4: Feature worktree 验收与 prepare

**Files:** all changed allowlisted files

- [x] **Step 1: 运行必需验收**

  Run sequentially, stopping a command after three consecutive failures:

  ```bash
  node --test tests/javascript/verification_policy.test.mjs
  node --test tests/javascript/research_web_architecture.test.mjs
  node scripts/plan_verification.mjs --project . --changed-file app/research_web/ui/app.mjs
  node scripts/plan_verification.mjs --project . --changed-file src-tauri/tauri.conf.json
  node scripts/check_documentation_governance.mjs --project .
  python scripts/generate_py_file_index.py --check
  ```

  逐个检查实际输出：Web 计划 desktop/windows/tauri/installer 门为零；desktop 计划为 `full-delivery` 且包含原生 Windows 与 packaging；测试 failed/skipped/todo 均为 0。

- [x] **Step 2: 针对全部改动文件运行 Project Constraints**

  构造一个 `node .agents/project-constraints.mjs --project .` 命令，并为 `git diff --name-only 399e94d...` 中每个白名单文件重复追加 `--changed-file`。Expected: `violations` 为空；若检查器自身写入 `logs/`，不提交该运行产物并保持功能 diff 仅含白名单。

- [x] **Step 3: 检查范围与提交**

  Run: `git status --short`、`git diff --check`、`git diff --stat`、`git diff --name-only`。Expected: 只有允许路径；BLOCKED 存在且内容为“无”或准确阻塞项。提交消息使用 `feat: add verification policy planner`。

- [ ] **Step 4: 受管 prepare**

  Run: `node "$HOME/.agents/leon-engineering/runtime/iteration-delivery.mjs" --prepare --project /Users/leon/Developer/ResearchWorkbench --task-id verification-policy`

  Expected: 返回 integration worktree 与 integration commit；不得手工合并或绕过控制器。

### Task 5: 集成复验、发布、CI 与清理

**Files:** no functional edits unless a verified failure requires an allowlisted repair

- [ ] **Step 1: 在 integration worktree 重跑 Task 4 全部验收**

  必须使用控制器返回的 integration worktree，重新运行全部命令和全改动 Project Constraints。任何失败都回到 feature worktree 做最小修复、提交、再次 prepare；同一验收累计三次失败后停止该项并记录 BLOCKED。

- [ ] **Step 2: 发布前检查 Actions 预算与仓库 visibility**

  读取 `docs/actions-budget.md`，通过当前 GitHub API/CLI 只读查询确认仓库 visibility 与远端默认分支。只有门禁允许时才调用受管 publish。

- [ ] **Step 3: 受管 publish 与 status**

  使用 integration worktree 全部验收的单一 verification command、`--verification-status passed` 和实测秒数调用 `--publish`，再轮询 `--status` 到 `passed` 或 `not_configured`。若远端默认分支漂移，重新 `prepare` 并重复集成复验；禁止 force-push。

- [ ] **Step 4: 安全 cleanup 与 Harness 硬门**

  CI 结论允许后调用受管 `--cleanup`。在 Harness 中记录本轮真实验证命令、passed 和实测时长，再运行 `harness-enforce.mjs --project /Users/leon/Developer/ResearchWorkbench --task-id verification-policy --require-delivery`。最后验证远端默认分支包含交付提交、主仓工作树干净、受管 worktree/分支已安全移除，并更新 PROGRESS/BLOCKED。
