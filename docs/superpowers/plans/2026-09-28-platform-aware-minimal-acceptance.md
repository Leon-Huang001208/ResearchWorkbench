# Platform-aware Minimal Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Research Workbench's existing fail-closed verification router into a machine-readable `Component × Risk × Platform` model with conditional Windows CI, separate CI/real-machine evidence, stable Git semantics, and authoritative developer workflow documentation.

**Architecture:** Keep `.agents/verification-policy.json` as the only routing source and preserve the current L0-L4 matcher/escalation engine. Upgrade the policy and planner to schema v3, introduce a receipt v2 while retaining a legacy validator path, and project the selected catalog into local, CI, and real-machine lanes. GitHub workflow path filters remain the minimal execution mechanism, protected by representative routing contracts rather than a second router.

**Tech Stack:** Node.js ESM, Node test runner, strict JSON policy, GitHub Actions YAML, Git attributes/ignore rules, Markdown governance, existing Research Workbench Harness.

---

## File responsibility map

- `.agents/verification-policy.json`: only source for component, risk, platform, lane, gate, validation and fallback routing.
- `scripts/plan_verification.mjs`: strict schema-v3 parser and read-only plan projection.
- `scripts/validate_verification_receipt.mjs`: new plan-v3/receipt-v2 validation plus legacy plan-v2/receipt-v1 compatibility.
- `tests/javascript/verification_policy.test.mjs`: policy/planner contracts and representative cases A-F.
- `tests/javascript/verification_receipt.test.mjs`: status, readiness, legacy compatibility and representative cases G-H.
- `tests/javascript/actions_quota_governance.test.mjs`: conditional macOS/Windows workflow path boundaries.
- `tests/javascript/repository_cross_platform_contract.test.mjs`: `.gitattributes` and `.gitignore` behavior.
- `.github/workflows/research-web-bootstrap.yml`: macOS-only and shared platform-sensitive automatic routing.
- `.github/workflows/research-web-windows-verify.yml`: conditional Windows automatic routing plus retained manual dispatch.
- `.gitattributes`, `.gitignore`: repository-wide line-ending and machine-state contracts.
- `AGENTS.md`, `docs/AGENT_WORKFLOW.md`, `docs/DEVELOPMENT_MAP.md`, `docs/actions-budget.md`, `docs/README.md`: authoritative developer, platform, verification and operations guidance.
- `.agents/skills/incremental-validation/SKILL.md`, `.agents/skills/incremental-validation/README.md`: project skill synchronized with the new plan/receipt contract.
- `.ai/reports/2026-09-28-platform-aware-minimal-acceptance*.json|md`: actual plan, receipt and evidence summary.

### Task 1: Freeze platform-aware planner behavior with failing tests

**Files:**
- Modify: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Add schema-v3 and A-F assertions**

Add a helper that checks the new dimensions without duplicating route internals:

```js
function assertDimensions(plan, {components, platforms, local = [], ci = [], realMachine = []}) {
  assert.deepEqual(plan.components, components);
  assert.deepEqual(plan.platforms, platforms);
  assert.deepEqual(plan.local.map(item => item.id), local);
  assert.deepEqual(plan.ci.map(item => item.id), ci);
  assert.deepEqual(plan.realMachine.map(item => item.id), realMachine);
}
```

Add explicit cases for:

```js
const representativeCases = {
  purePython: ["app/research_web/frameworks/goldar/context.py"],
  webUi: ["app/research_web/ui/app.mjs"],
  sharedSetup: ["scripts/setup_web.py"],
  windowsLauncher: ["setup-web.cmd"],
  desktop: ["src-tauri/tauri.conf.json"],
  unknown: ["future/platform/new_adapter.py"],
};
```

Assert generic-only routing for the first two, macOS + Windows for shared setup, Windows-only native CI for the launcher, Desktop macOS + Windows plus real-machine release gate, and L4/cross-platform/unknown risk for the fallback.

- [ ] **Step 2: Add strict schema failure cases**

Extend invalid-policy fixtures so missing/unknown `platformOrder`, `statusOrder`, catalog `lane`, `gate`, `platforms`, rule `platforms`, and rule `realMachine` all return `POLICY_ERROR`.

- [ ] **Step 3: Run the planner contract and capture RED**

Run:

```bash
node --test tests/javascript/verification_policy.test.mjs
```

Expected: existing contracts remain green; new schema/A-F contracts fail because schema v2 has no platform/lane/real-machine fields.

- [ ] **Step 4: Commit the RED contract**

```bash
git add tests/javascript/verification_policy.test.mjs
git commit -m "test: define platform-aware verification routing"
```

### Task 2: Implement policy schema v3 and planner projection

**Files:**
- Modify: `.agents/verification-policy.json`
- Modify: `scripts/plan_verification.mjs`

- [ ] **Step 1: Upgrade strict policy constants**

Define the exact new orders and schema keys:

```js
const PLATFORM_ORDER = [
  "generic", "linux", "macos", "windows", "cross-platform", "real-machine-required",
];
const STATUS_ORDER = [
  "PASS", "FAIL", "SKIPPED", "NOT_REQUIRED", "NOT_RUN", "BLOCKED", "MANUAL_REQUIRED",
];
const CATALOG_KEYS = new Set(["tests", "documentation", "ci", "realMachine"]);
const CATALOG_ITEM_KEYS = new Set(["level", "lane", "gate", "platforms", "value"]);
```

Require `schemaVersion: 3`, exact platform/status order, catalog lane/category consistency, ordered unique platforms, and `realMachine` references.

- [ ] **Step 2: Migrate catalog metadata**

Assign all existing local tests/documentation `lane: "local"`, hosted workflows `lane: "ci"`, and merge gates `gate: "merge"`. Add:

```json
"research-web-windows-verify": {
  "level": "L4",
  "lane": "ci",
  "gate": "merge",
  "platforms": ["windows"],
  "value": ".github/workflows/research-web-windows-verify.yml#windows-2022"
},
"native-macos-desktop": {
  "level": "L4",
  "lane": "ci",
  "gate": "merge",
  "platforms": ["macos"],
  "value": ".github/workflows/desktop-verify.yml#macos-14"
},
"windows-desktop-installation": {
  "level": "L4",
  "lane": "real-machine",
  "gate": "release",
  "platforms": ["windows", "real-machine-required"],
  "value": "docs/desktop_packaging.md#windows-real-machine-smoke"
}
```

- [ ] **Step 3: Split platform-sensitive rules**

Replace the single installation rule with shared, macOS launcher and Windows launcher rules. Add a cross-platform runtime rule and require Windows CI for Windows local integrations. Preserve generic routing for ordinary Web/framework/DataHub/UI rules and existing delegated namespace behavior.

- [ ] **Step 4: Project dimensions and lanes**

Add ordered-union helpers and return:

```js
{
  schemaVersion: 3,
  components,
  platforms,
  local,
  ci,
  realMachine,
  receiptTemplate: {
    plannedLevel: requiredLevel,
    changedFiles: normalizedFiles,
    requiredValidationIds: local.filter(item => item.gate === "merge").map(item => item.id),
    externalGateIds: ci.filter(item => item.gate === "merge").map(item => item.id),
    releaseGateIds: realMachine.filter(item => item.gate === "release").map(item => item.id),
  },
}
```

Keep `tests`, `documentation`, `ci`, `validationsByLevel`, changed-file safety and command non-execution.

- [ ] **Step 5: Run planner GREEN and existing safety contracts**

```bash
node --test tests/javascript/verification_policy.test.mjs
```

Expected: all old and new planner contracts pass with zero skipped/todo tests.

- [ ] **Step 6: Commit policy and planner**

```bash
git add .agents/verification-policy.json scripts/plan_verification.mjs
git commit -m "feat: add platform-aware verification planning"
```

### Task 3: Freeze receipt v2 readiness semantics with failing tests

**Files:**
- Modify: `tests/javascript/verification_receipt.test.mjs`

- [ ] **Step 1: Add a canonical receipt-v2 builder**

Build `executed`, `external`, and `realMachine` from the three receipt-template ID lists. Use `PASS` for executed CI evidence and `MANUAL_REQUIRED` as the default real-machine status. Include computed expectations:

```js
{
  schemaVersion: 2,
  result: "PASS",
  mergeReady: true,
  releaseReady: false,
}
```

- [ ] **Step 2: Add G/H and negative status tests**

Case G changes required Windows CI from `PASS` to `NOT_RUN`, sets `result: "BLOCKED"`, `mergeReady: false`, and requires `external_gate_not_run:research-web-windows-verify`.

Case H keeps Windows CI `PASS` and Windows real machine `MANUAL_REQUIRED`; assert `result: "PASS"`, `mergeReady: true`, `releaseReady: false`.

Reject `NOT_REQUIRED` for selected gates, lowercase status in v2, false positive readiness, missing lane entries, and a real-machine `PASS` without a regular evidence file.

- [ ] **Step 3: Add legacy compatibility coverage**

Retain the current plan-v2/receipt-v1 fixture and assert the validator still returns a valid legacy verdict without rewriting either file.

- [ ] **Step 4: Run receipt contracts and capture RED**

```bash
node --test tests/javascript/verification_receipt.test.mjs
```

Expected: legacy tests pass; new v2 status/readiness tests fail before validator implementation.

- [ ] **Step 5: Commit the RED contract**

```bash
git add tests/javascript/verification_receipt.test.mjs
git commit -m "test: define platform receipt readiness semantics"
```

### Task 4: Implement receipt v2 with legacy compatibility

**Files:**
- Modify: `scripts/validate_verification_receipt.mjs`

- [ ] **Step 1: Split plan parsing by schema**

Keep current plan-v2 exact-key parser as `parseLegacyPlan`; add `parsePlanV3` for components, platforms, lane/gate/platform validation items and three receipt-template ID lists. Dispatch only on schema 2 or 3 and reject every other version.

- [ ] **Step 2: Split receipt parsing by schema**

Keep current receipt-v1 parser as `parseLegacyReceipt`. Add receipt-v2 exact keys including `realMachine`, `mergeReady`, and `releaseReady`; accept only canonical status values.

- [ ] **Step 3: Enforce readiness**

Compute:

```js
const mergeReady = requiredLocal.every(item => item.status === "PASS") &&
  requiredCi.every(item => item.status === "PASS");
const releaseReady = mergeReady &&
  requiredRealMachine.every(item => item.status === "PASS");
```

Require `result === "BLOCKED"` when a merge gate is `NOT_RUN`, `SKIPPED`, `BLOCKED`, or `MANUAL_REQUIRED`; require escalation on `FAIL`; permit release-only `MANUAL_REQUIRED` with `result: "PASS"` only when mergeReady is true and releaseReady is false.

- [ ] **Step 4: Run receipt GREEN**

```bash
node --test tests/javascript/verification_receipt.test.mjs
```

Expected: legacy and v2 contracts all pass.

- [ ] **Step 5: Commit validator implementation**

```bash
git add scripts/validate_verification_receipt.mjs
git commit -m "feat: validate platform and real-machine evidence"
```

### Task 5: Make Windows Web CI conditional and platform-correct

**Files:**
- Modify: `tests/javascript/actions_quota_governance.test.mjs`
- Modify: `.github/workflows/research-web-bootstrap.yml`
- Modify: `.github/workflows/research-web-windows-verify.yml`

- [ ] **Step 1: Add failing workflow routing assertions**

Require Windows workflow triggers `pull_request`, `push`, and `workflow_dispatch`. Positive automatic paths include shared setup/runtime/dependencies, Windows launchers, Windows local integration, the workflow itself and its contract test. Negative paths include docs, ordinary UI, framework business logic and public DataHub providers.

Require macOS Bootstrap not to trigger for `setup-web.cmd` or `rwb.cmd`, while shared setup/runtime still triggers both workflows.

- [ ] **Step 2: Run Actions contracts and capture RED**

```bash
node --test tests/javascript/actions_quota_governance.test.mjs
```

Expected: new Windows automatic-trigger and macOS negative-route assertions fail.

- [ ] **Step 3: Update workflow triggers only**

Add narrow `pull_request.paths` and `push.branches: [master] / paths` to Windows Verify while retaining `workflow_dispatch`, concurrency, timeout, runner, commands and artifacts. Remove pure Windows launcher entries from macOS Bootstrap paths; do not change Desktop workflows.

- [ ] **Step 4: Run Actions GREEN**

```bash
node --test tests/javascript/actions_quota_governance.test.mjs
```

Expected: all workflow routing contracts pass.

- [ ] **Step 5: Commit conditional CI routing**

```bash
git add tests/javascript/actions_quota_governance.test.mjs .github/workflows/research-web-bootstrap.yml .github/workflows/research-web-windows-verify.yml
git commit -m "ci: route Windows verification by changed paths"
```

### Task 6: Establish repository Git file semantics

**Files:**
- Create: `tests/javascript/repository_cross_platform_contract.test.mjs`
- Modify: `.gitattributes`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing Git contract tests**

Use `spawnSync("git", ["check-attr", "text", "eol", "--", ...files])` to assert LF for Python/JS/TS/JSON/YAML/Markdown/shell, CRLF for cmd/bat/PowerShell, and `text: unset` for both vendored hash-sensitive trees. Use `git check-ignore --no-index` to require `.venv`, `.venv.broken-*`, `.codex/config.toml`, logs, data and secrets to be ignored while `.env.example` remains eligible for tracking.

- [ ] **Step 2: Run the new test and capture RED**

```bash
node --test tests/javascript/repository_cross_platform_contract.test.mjs
```

Expected: generic text attributes and repository-level `.venv*`/`.codex/` assertions fail.

- [ ] **Step 3: Add minimal attributes and ignore rules**

Add explicit LF/CRLF globs while retaining vendor `-text` overrides. Add `.venv*/` and `.codex/` without deleting current files or changing `.env.example`.

- [ ] **Step 4: Run Git contract GREEN**

```bash
node --test tests/javascript/repository_cross_platform_contract.test.mjs
```

Expected: all attribute and ignore semantics pass.

- [ ] **Step 5: Commit repository semantics**

```bash
git add .gitattributes .gitignore tests/javascript/repository_cross_platform_contract.test.mjs
git commit -m "chore: standardize cross-platform Git semantics"
```

### Task 7: Synchronize developer and agent documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/AGENT_WORKFLOW.md`
- Modify: `docs/DEVELOPMENT_MAP.md`
- Modify: `docs/actions-budget.md`
- Modify: `docs/README.md`
- Modify: `.agents/skills/incremental-validation/SKILL.md`
- Modify: `.agents/skills/incremental-validation/README.md`

- [ ] **Step 1: Update the authoritative Git/Worktree SOP**

Document GitHub-only source synchronization, `master` as the sole long-lived branch, permitted short-lived prefixes, Mac development flow, Windows verification/fix flow, worktree ownership, full changed-set planning, PR/merge conditions and safe cleanup. State that branch protection is not currently a repository-enforced fact.

- [ ] **Step 2: Document platform-aware validation and status semantics**

Describe component/risk/platform dimensions, local/CI/real-machine lanes, merge versus release gates, all seven statuses, escalation, Case G/H semantics and the rule that unrun evidence is never PASS.

- [ ] **Step 3: Update Actions and skill guidance**

Replace “Windows always manual” with conditional automatic Windows routing plus retained manual dispatch. Keep Desktop separation and public-standard budget facts. Synchronize both files of the modified incremental-validation skill.

- [ ] **Step 4: Run documentation checks**

```bash
node scripts/check_documentation_governance.mjs --project .
node --test tests/javascript/incremental_validation_skill.test.mjs
```

Expected: documentation governance and skill contracts pass.

- [ ] **Step 5: Commit documentation**

```bash
git add AGENTS.md docs/AGENT_WORKFLOW.md docs/DEVELOPMENT_MAP.md docs/actions-budget.md docs/README.md .agents/skills/incremental-validation/SKILL.md .agents/skills/incremental-validation/README.md
git commit -m "docs: define cross-platform development and acceptance"
```

### Task 8: Produce A-H fixtures and real acceptance evidence

**Files:**
- Create: `.ai/reports/2026-09-28-platform-aware-minimal-acceptance.md`
- Create: `.ai/reports/2026-09-28-platform-aware-minimal-acceptance-plan.json`
- Create: `.ai/reports/2026-09-28-platform-aware-minimal-acceptance-receipt.json`

- [ ] **Step 1: Run the six planner representatives**

Run the planner separately for pure Python, UI, shared setup, Windows launcher, Desktop and unknown paths. Record exact components, risk, level, platforms, CI and real-machine gates in the Markdown report.

- [ ] **Step 2: Validate G/H receipts**

Create fixture evidence files and validate a Windows CI `NOT_RUN` receipt as blocked, then a CI `PASS` plus real-machine `MANUAL_REQUIRED` receipt as merge-ready but not release-ready. Record both commands and verdicts without reporting either missing layer as PASS.

- [ ] **Step 3: Plan the actual complete changed set**

Run `scripts/plan_verification.mjs` with one `--changed-file` for every staged/unstaged/new project file and save the exact JSON plan.

- [ ] **Step 4: Execute the returned local closure**

Run every selected local validation from L0 through L4, capturing real duration and evidence. If a check fails, replan with `--signal validation_failure`; on unexpected behavior, replan with `--signal unexpected_behavior`.

- [ ] **Step 5: Write and validate the actual receipt**

Record unrun external CI as `NOT_RUN` and real-machine release evidence as `MANUAL_REQUIRED`; keep the overall receipt blocked when required merge CI has not run. Validate with:

```bash
node scripts/validate_verification_receipt.mjs --project . \
  --plan .ai/reports/2026-09-28-platform-aware-minimal-acceptance-plan.json \
  --receipt .ai/reports/2026-09-28-platform-aware-minimal-acceptance-receipt.json
```

- [ ] **Step 6: Commit evidence**

```bash
git add .ai/reports/2026-09-28-platform-aware-minimal-acceptance.md \
  .ai/reports/2026-09-28-platform-aware-minimal-acceptance-plan.json \
  .ai/reports/2026-09-28-platform-aware-minimal-acceptance-receipt.json
git commit -m "docs: record platform-aware acceptance evidence"
```

### Task 9: Final local review and handoff

**Files:**
- Verify all files changed since `6dee571f53de62faae7ac3bf22dda6b9607c839c`

- [ ] **Step 1: Run focused regression suites**

```bash
node --test tests/javascript/verification_policy.test.mjs
node --test tests/javascript/verification_receipt.test.mjs
node --test tests/javascript/actions_quota_governance.test.mjs
node --test tests/javascript/repository_cross_platform_contract.test.mjs
node --test tests/javascript/incremental_validation_skill.test.mjs
node --test tests/javascript/research_web_architecture.test.mjs
```

- [ ] **Step 2: Run repository integrity checks**

```bash
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
node .agents/project-constraints.mjs --project . \
  --changed-file .agents/verification-policy.json \
  --changed-file .agents/skills/incremental-validation/README.md \
  --changed-file .agents/skills/incremental-validation/SKILL.md \
  --changed-file .ai/reports/2026-09-28-platform-aware-minimal-acceptance-plan.json \
  --changed-file .ai/reports/2026-09-28-platform-aware-minimal-acceptance-receipt.json \
  --changed-file .ai/reports/2026-09-28-platform-aware-minimal-acceptance.md \
  --changed-file .gitattributes \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file .gitignore \
  --changed-file AGENTS.md \
  --changed-file docs/AGENT_WORKFLOW.md \
  --changed-file docs/DEVELOPMENT_MAP.md \
  --changed-file docs/README.md \
  --changed-file docs/actions-budget.md \
  --changed-file docs/superpowers/plans/2026-09-28-platform-aware-minimal-acceptance.md \
  --changed-file docs/superpowers/specs/2026-09-28-platform-aware-minimal-acceptance-design.md \
  --changed-file scripts/plan_verification.mjs \
  --changed-file scripts/validate_verification_receipt.mjs \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/javascript/repository_cross_platform_contract.test.mjs \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file tests/javascript/verification_receipt.test.mjs
git diff --check 6dee571f53de62faae7ac3bf22dda6b9607c839c..HEAD
```

- [ ] **Step 3: Review the complete diff**

Confirm no Desktop workflow body, dependency, secret, generated runtime state, unrelated source or main-checkout file changed. Confirm every A-H requirement has direct test and report evidence.

- [ ] **Step 4: Record Harness outcome**

Record only observed local verification results and measured durations. Because push/PR/CI/real-machine execution is not authorized, do not mark those gates passed and do not call delivery-required enforcement.

- [ ] **Step 5: Hand off PR-ready state**

Report branch, worktree, commits, changed files, actual commands, test counts, unrun external gates, `mergeReady`, `releaseReady`, and the separate authorization needed for push/PR/dispatch/merge/cleanup.
