# Mac-only Research Web Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pause automatic Windows validation while preserving its manual workflow, and require GitHub `macos-14` bootstrap evidence after successful local Mac verification.

**Architecture:** Keep `research-web-bootstrap` as the stable L4 external gate, but make its workflow a single macOS job and identify that job in the policy catalog. Convert the existing Windows workflow to `workflow_dispatch` only, then enforce both routing decisions with repository contracts and synchronized project guidance.

**Tech Stack:** GitHub Actions YAML, Node.js contract tests, Python pytest contracts, JSON verification policy and project constraints, Markdown project documentation.

---

## File map

- `.github/workflows/research-web-bootstrap.yml`: automatic clean-install and startup acceptance; becomes GitHub macOS-only.
- `.github/workflows/research-web-windows-verify.yml`: retained Windows checks; becomes manual-only.
- `.agents/verification-policy.json`: keeps the stable `research-web-bootstrap` gate and binds it to `#macos-14`.
- `.agents/project-constraints.json`: mechanically requires the macOS bootstrap contents and Windows manual trigger.
- `tests/javascript/actions_quota_governance.test.mjs`: proves automatic workflow routing contains no Windows job.
- `tests/javascript/verification_policy.test.mjs`: proves planner output still requires the GitHub macOS external gate.
- `tests/research_web/test_local_integrations.py`: proves the retained Windows workflow remains manual and keeps its native contracts.
- `AGENTS.md`: updates mandatory Web delivery rules without changing desktop Windows rules.
- `docs/research-web-installation.md`: defines local Mac then GitHub Mac acceptance and user-owned Windows evidence.
- `docs/research-web-documentation.md`: documents the new workflow-routing governance boundary.
- `.ai/reports/2026-09-23-mac-only-web-verification*.json` and `.md`: store the generated plan, executed receipt, and evidence.

### Task 0: Preserve the completed P0 delivery evidence

**Files:**
- Modify: `.ai/reports/2026-09-23-research-web-startup-preflight.md`
- Modify: `.ai/reports/2026-09-23-research-web-startup-preflight-receipt.json`

- [ ] **Step 1: Validate the existing P0 receipt update**

Run:

```bash
node scripts/validate_verification_receipt.mjs \
  --project . \
  --plan .ai/reports/2026-09-23-research-web-startup-preflight-plan.json \
  --receipt .ai/reports/2026-09-23-research-web-startup-preflight-receipt.json
```

Expected: JSON result with `"valid": true`; the receipt records all three completed external gates as passed and has no uncovered risk.

- [ ] **Step 2: Commit only the P0 evidence files**

```bash
git add \
  .ai/reports/2026-09-23-research-web-startup-preflight.md \
  .ai/reports/2026-09-23-research-web-startup-preflight-receipt.json
git commit -m "docs: close Research Web startup delivery"
```

Expected: the design commit remains separate and no workflow file is staged.

- [ ] **Step 3: Start a separate Harness and delivery task for the policy change**

Run from `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability`:

```bash
node /Users/leon/.agents/leon-engineering/runtime/harness-session.mjs \
  --start \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --host codex \
  --session-id 75e0e0f0-2d40-4409-b84d-318f1e045490 \
  --new-task \
  --task-id mac-only-web-verification-delivery \
  --goal "Pause automatic Windows Web validation while keeping it manually runnable and requiring local plus GitHub macOS acceptance" \
  --acceptance "Bootstrap automatically runs exactly one macos-14 job" \
  --acceptance "Windows Web workflow is workflow_dispatch only" \
  --acceptance "Planner keeps the GitHub macOS bootstrap as an external L4 gate" \
  --delivery-required

node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --start \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery \
  --slug mac-only-web-verification
```

Expected: the controller creates feature worktree `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability-worktrees/mac-only-web-verification-delivery` from current `origin/master`.

- [ ] **Step 4: Preserve the exact reviewed commits in the new feature branch**

After this plan itself has been committed and Step 2 has committed the P0 evidence, fast-forward the new feature worktree to the old integration branch:

```bash
git -C /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability-worktrees/mac-only-web-verification-delivery \
  merge --ff-only codex/integrate-p0-web-stability-delivery
git -C /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability-worktrees/mac-only-web-verification-delivery \
  log -3 --oneline
```

Expected: the new feature branch contains the exact design, plan and P0 evidence commits; no patch is recreated and no existing commit is reset.

### Task 1: Lock the new workflow routing with failing contracts

**Files:**
- Modify: `tests/javascript/actions_quota_governance.test.mjs:76-123`
- Modify: `tests/research_web/test_local_integrations.py:210-245`

- [ ] **Step 1: Change the JavaScript routing expectations first**

Replace the installation and platform expectations with:

```javascript
test('installation changes trigger the GitHub macOS bootstrap gate', () => {
  for (const file of [
    'setup-web.sh',
    'setup-web.cmd',
    'scripts/setup_web.py',
    'requirements/web.lock',
    'vendor/cjpy/0.5.2/manifest.json',
  ]) {
    assert.equal(triggersForPath(workflows.bootstrap, 'push', file), true, file);
    assert.equal(triggersForPath(workflows.bootstrap, 'pull_request', file), true, file);
  }
  assert.match(workflows.bootstrap, /macos-14/);
  assert.doesNotMatch(workflows.bootstrap, /windows-2022/);
});

test('ordinary Research Web code uses Linux checks without unnecessary native jobs', () => {
  const ordinary = 'app/research_web/frameworks/service.py';
  assert.equal(triggersForPath(workflows.checks, 'push', ordinary), true);
  assert.equal(triggersForPath(workflows.bootstrap, 'push', ordinary), false);
  assert.equal(triggersForPath(workflows.windows, 'push', ordinary), false);

  const platformSpecific = 'app/research_web/service_manager.py';
  assert.equal(triggersForPath(workflows.checks, 'push', platformSpecific), true);
  assert.equal(triggersForPath(workflows.bootstrap, 'push', platformSpecific), true);
  assert.equal(triggersForPath(workflows.windows, 'push', platformSpecific), false);
});

test('platform workflows retain explicit routing boundaries', () => {
  assert.deepEqual(workflowTriggers(workflows.tabbit), ['workflow_dispatch']);
  assert.deepEqual(workflowTriggers(workflows.windows), ['workflow_dispatch']);
  assert.equal(triggersForPath(workflows.desktop, 'push', 'src-tauri/src/main.rs'), true);
});
```

Change the bounded automatic-workflow loop so it excludes the now-manual Windows workflow:

```javascript
for (const source of [workflows.bootstrap, workflows.checks, workflows.constraints]) {
  assert.match(source, /concurrency:/);
  assert.match(source, /cancel-in-progress: true/);
  assert.match(source, /timeout-minutes:/);
}
```

- [ ] **Step 2: Change the Python Windows-workflow contract first**

Rename the test and replace its routing assertions with:

```python
def test_windows_manual_workflow_retains_native_contracts_and_loopback_probe():
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/research-web-windows-verify.yml"
    ).read_text(encoding="utf-8")
    trigger_block = workflow.split("permissions:", maxsplit=1)[0]

    assert "  workflow_dispatch:" in trigger_block
    assert "  pull_request:" not in trigger_block
    assert "  push:" not in trigger_block
    assert "runs-on: windows-2022" in workflow
    assert 'python-version: "3.11"' in workflow
    assert 'node-version: "20"' in workflow
```

Keep the existing assertions for pytest targets, loopback API, probe completion, evidence upload, and three-day retention. Remove only the assertions that require automatic path filters.

- [ ] **Step 3: Run the focused contracts and observe RED**

Run:

```bash
node --test tests/javascript/actions_quota_governance.test.mjs
python -m pytest \
  tests/research_web/test_local_integrations.py::test_windows_manual_workflow_retains_native_contracts_and_loopback_probe \
  --confcutdir=tests/research_web -q
```

Expected: failures show `windows-2022` is still in Bootstrap and the Windows workflow still has `pull_request`/`push` triggers.

- [ ] **Step 4: Commit the RED contracts**

```bash
git add tests/javascript/actions_quota_governance.test.mjs tests/research_web/test_local_integrations.py
git commit -m "test: require mac-only Web automation"
```

### Task 2: Make Bootstrap macOS-only and Windows verification manual-only

**Files:**
- Modify: `.github/workflows/research-web-bootstrap.yml:57-141`
- Modify: `.github/workflows/research-web-windows-verify.yml:1-42`
- Modify: `.agents/project-constraints.json:131-175`

- [ ] **Step 1: Collapse Bootstrap to a single macOS job**

Replace the matrix/job header and platform-specific install/verify/stop steps with:

```yaml
jobs:
  clean-install:
    name: Clean Web install (macos-14)
    runs-on: macos-14
    timeout-minutes: 60

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Setup Node 22.19
        uses: actions/setup-node@v4
        with:
          node-version: "22.19.0"

      - name: Install Web stack on macOS
        shell: bash
        run: ./setup-web.sh --no-start

      - name: Verify macOS environment and start services
        shell: bash
        run: |
          set -euo pipefail
          test -x .venv/bin/python
          .venv/bin/python -c "import importlib.metadata as m, cjpy, requests, urllib3; assert m.version('cjpy') == '0.5.2'"
          ./rwb web start --no-open
          ./rwb web doctor --json > doctor.json
          .venv/bin/python -c "import json; report=json.load(open('doctor.json', encoding='utf-8')); assert report['ok'], report"
          curl --fail --silent http://127.0.0.1:8088/api/research/data/connections > connections.json
          .venv/bin/python -c "import json; data=json.load(open('connections.json', encoding='utf-8')); item=next(x for x in data['sources'] if x['id']=='tinysoft'); assert item['configured'] is False and item['callable'] is False and item['restart_required'] is False, item"

      - name: Stop macOS services
        if: always()
        shell: bash
        run: ./rwb web stop || true
```

Keep the success/failure artifact steps, but use fixed names:

```yaml
name: research-web-bootstrap-macos-14-${{ github.run_id }}
```

and:

```yaml
name: research-web-bootstrap-failure-macos-14-${{ github.run_id }}
```

- [ ] **Step 2: Make the Windows workflow manual-only**

Replace its trigger block with exactly:

```yaml
on:
  workflow_dispatch:
```

Do not change its job, native contracts, smoke probe, artifact contents, timeout, or retention.

- [ ] **Step 3: Update mechanical project constraints**

Replace the Web Bootstrap constraint with:

```json
{
  "name": "Web 一键安装必须在 GitHub 原生 macOS 持续验证",
  "workflow": ".github/workflows/research-web-bootstrap.yml",
  "requireAll": [
    "Clean Web install (macos-14)",
    "macos-14",
    "setup-web.sh --no-start",
    "web doctor --json",
    "cjpy') == '0.5.2'",
    "tinysoft",
    "callable",
    "scripts/setup_web.py",
    "requirements/web.lock",
    "if: success()",
    "if: failure()",
    "retention-days: 3"
  ]
}
```

Replace the Windows constraint with:

```json
{
  "name": "Windows Web 验证暂停自动触发并保留手动入口与短期证据",
  "workflow": ".github/workflows/research-web-windows-verify.yml",
  "requireAll": [
    "workflow_dispatch:",
    "windows-2022",
    "Run local integration contracts on Windows",
    "Smoke test Windows loopback service and probe",
    "retention-days: 3"
  ]
}
```

- [ ] **Step 4: Run GREEN workflow contracts**

Run:

```bash
node --test tests/javascript/actions_quota_governance.test.mjs
python -m pytest \
  tests/research_web/test_local_integrations.py::test_windows_manual_workflow_retains_native_contracts_and_loopback_probe \
  --confcutdir=tests/research_web -q
node .agents/project-constraints.mjs \
  --project . \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file .agents/project-constraints.json \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/research_web/test_local_integrations.py
```

Expected: all tests pass and Project Constraints returns `"violations": []`.

- [ ] **Step 5: Commit workflow routing**

```bash
git add \
  .github/workflows/research-web-bootstrap.yml \
  .github/workflows/research-web-windows-verify.yml \
  .agents/project-constraints.json \
  tests/javascript/actions_quota_governance.test.mjs \
  tests/research_web/test_local_integrations.py
git commit -m "ci: pause automatic Windows Web verification"
```

### Task 3: Bind workflow files and the planner gate explicitly to GitHub macOS

**Files:**
- Modify: `.agents/verification-policy.json:41-65,115-119,258-318,512-542`
- Modify: `tests/javascript/verification_policy.test.mjs:29-70,130-190,470-510`

- [ ] **Step 1: Write the failing policy expectation**

Add a focused local-integrations catalog entry to the test policy fixture:

```javascript
"research-web-local-integrations": catalog(
  "L1",
  "python -m pytest tests/research_web/test_local_integrations.py",
),
```

Change the Bootstrap catalog entry to:

```javascript
"research-web-bootstrap": catalog(
  "L4",
  ".github/workflows/research-web-bootstrap.yml#macos-14",
  "external",
),
```

Add these two rules to the fixture before the generic `ci` and `research-web` rules respectively:

```javascript
rule({
  id: "research-web-ci",
  risk: "full-delivery",
  minimumLevel: "L4",
  reason: "research_web_ci_change",
  impact: ["research-web-verification"],
  coupling: "high",
  match: {
    files: [
      ".github/workflows/research-web-bootstrap.yml",
      ".github/workflows/research-web-windows-verify.yml",
      "tests/javascript/actions_quota_governance.test.mjs",
    ],
    prefixes: [],
    segments: [],
    suffixes: [],
  },
  tests: [
    "verification-policy-contracts",
    "verification-receipt-contracts",
    "incremental-validation-skill-contracts",
    "research-web-verification-full",
    "research-web-local-integrations",
    "project-constraints-local",
  ],
  documentation: ["documentation-governance"],
  ci: ["project-constraints", "research-web-checks", "research-web-bootstrap"],
}),

rule({
  id: "research-web-local-integrations",
  risk: "local-only",
  minimumLevel: "L1",
  reason: "research_web_local_integrations_change",
  impact: ["research-web-local-integrations"],
  coupling: "low",
  match: {
    files: ["tests/research_web/test_local_integrations.py"],
    prefixes: ["app/research_web/local_integrations/"],
    segments: [],
    suffixes: [],
  },
  tests: ["research-web-local-integrations", "research-web-architecture"],
  documentation: ["documentation-governance", "python-file-index"],
  ci: ["project-constraints", "research-web-checks"],
}),
```

Add a routing test:

```javascript
test("Research Web workflow changes require the GitHub macOS bootstrap gate", () => {
  const plan = success(run(repositoryRoot, [
    ".github/workflows/research-web-bootstrap.yml",
    ".github/workflows/research-web-windows-verify.yml",
    "tests/javascript/actions_quota_governance.test.mjs",
    "tests/research_web/test_local_integrations.py",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.equal(plan.tests.some(item => item.id === "research-web-local-integrations"), true);
  assert.deepEqual(new Set(plan.receiptTemplate.externalGateIds), new Set([
    "project-constraints",
    "research-web-checks",
    "research-web-bootstrap",
  ]));
  const bootstrap = plan.ci.find((item) => item.id === "research-web-bootstrap");
  assert.equal(bootstrap.value, ".github/workflows/research-web-bootstrap.yml#macos-14");
  assert.equal(bootstrap.execution, "external");
});
```

- [ ] **Step 2: Run the policy contract and observe RED**

Run:

```bash
node --test tests/javascript/verification_policy.test.mjs
```

Expected: the new route fails because the repository policy has no focused workflow/local-integration rules and the Bootstrap catalog still points to the unqualified workflow path.

- [ ] **Step 3: Update the policy catalog**

Add the focused local test catalog:

```json
"research-web-local-integrations": {
  "level": "L1",
  "execution": "local",
  "value": "python -m pytest tests/research_web/test_local_integrations.py"
}
```

Use this exact Bootstrap entry:

```json
"research-web-bootstrap": {
  "level": "L4",
  "execution": "external",
  "value": ".github/workflows/research-web-bootstrap.yml#macos-14"
}
```

Add JSON equivalents of the fixture's `research-web-ci` and `research-web-local-integrations` rules. Do not broaden the generic `ci` rule, rename the stable Bootstrap gate ID, or remove it from `research-web-installation`.

- [ ] **Step 4: Run GREEN policy and planner contracts**

Run:

```bash
node --test tests/javascript/verification_policy.test.mjs
node scripts/plan_verification.mjs \
  --project . \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/research_web/test_local_integrations.py
```

Expected: all policy tests pass; planner returns L4/full-delivery, has no unknown path, selects the local-integrations test, and includes Project Constraints, Research Web Checks and `research-web-bootstrap#macos-14` as external gates.

- [ ] **Step 5: Commit the planner contract**

```bash
git add .agents/verification-policy.json tests/javascript/verification_policy.test.mjs
git commit -m "ci: require GitHub macOS Web bootstrap"
```

### Task 4: Synchronize authoritative rules and documentation

**Files:**
- Modify: `AGENTS.md:22-34`
- Modify: `docs/research-web-installation.md:108-121`
- Modify: `docs/research-web-documentation.md:71-75`

- [ ] **Step 1: Update the mandatory project rule**

Replace the two-platform Web delivery bullet in `AGENTS.md` with:

```markdown
- Web 交付必须先完成本机 macOS 相关验证，再等待 GitHub `macos-14` 干净安装、固定 DSH 构建、
  3081/8088 健康检查和 `rwb web doctor --json` 通过；本机成功不能替代 GitHub Mac。Windows Web
  自动验证当前暂停，由用户在 Windows 实机执行并单独提供回执，未提供时不得宣称 Windows 已验证。
  无厂商凭据的 CI 必须把天软显示为“依赖已安装但待配置”，不得伪报可调用。
```

Do not alter the desktop cross-platform section.

- [ ] **Step 2: Update the installation contract**

Replace the platform paragraph with:

```markdown
`.github/workflows/research-web-bootstrap.yml` 对相关 PR 与主分支更新在干净的 GitHub `macos-14`
runner 上运行公开安装入口、构建固定 DSH、启动 3081/8088、检查 Doctor，并验证无凭据天软不会
误报可调用。本机 macOS 验证必须先通过，但不能替代该远端干净环境门。Windows Web 自动验证当前
暂停；`.github/workflows/research-web-windows-verify.yml` 仅保留手动入口，Windows 实机结果由用户
单独提供，未运行时不得标记为通过。该边界不改变桌面/Tauri/sidecar 的独立 Windows 门禁。
```

- [ ] **Step 3: Update documentation governance wording**

Replace the workflow-routing bullet with:

```markdown
- 检查 docs-only、普通 Web、安装面、Windows、Tabbit 与 Desktop 的 workflow 路由；自动 workflow
  必须有 concurrency、取消旧运行和超时，Web artifact 保留期不得超过 3 天。Research Web 安装自动
  门只允许 GitHub macOS，Windows Web 与 Tabbit 暂停期间必须保持 `workflow_dispatch` 手动入口。
```

- [ ] **Step 4: Run documentation and constraint checks**

Run:

```bash
node scripts/check_documentation_governance.mjs --project .
node .agents/project-constraints.mjs \
  --project . \
  --changed-file AGENTS.md \
  --changed-file docs/research-web-installation.md \
  --changed-file docs/research-web-documentation.md \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file .agents/project-constraints.json \
  --changed-file .agents/verification-policy.json \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file tests/research_web/test_local_integrations.py
```

Expected: documentation governance passes and Project Constraints returns zero violations.

- [ ] **Step 5: Commit documentation synchronization**

```bash
git add AGENTS.md docs/research-web-installation.md docs/research-web-documentation.md
git commit -m "docs: record mac-only Web acceptance"
```

### Task 5: Generate the incremental receipt and complete local acceptance

**Files:**
- Create: `.ai/reports/2026-09-23-mac-only-web-verification-plan.json`
- Create: `.ai/reports/2026-09-23-mac-only-web-verification-receipt.json`
- Create: `.ai/reports/2026-09-23-mac-only-web-verification.md`

- [ ] **Step 1: Generate the real changed-file plan**

Run:

```bash
node scripts/plan_verification.mjs \
  --project . \
  --changed-file .agents/project-constraints.json \
  --changed-file .agents/verification-policy.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-receipt.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification.md \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight-receipt.json \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight.md \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-checks.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file AGENTS.md \
  --changed-file docs/README.md \
  --changed-file docs/actions-budget.md \
  --changed-file docs/architecture/research-web/06-documentation-contract.md \
  --changed-file docs/documentation-governance.json \
  --changed-file docs/research-web-documentation.md \
  --changed-file docs/research-web-installation.md \
  --changed-file docs/superpowers/plans/2026-09-23-mac-only-web-verification.md \
  --changed-file docs/superpowers/specs/2026-09-23-mac-only-web-verification-design.md \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file tests/research_web/test_local_integrations.py \
  > .ai/reports/2026-09-23-mac-only-web-verification-plan.json
```

Expected: `risk` is `full-delivery`, `requiredLevel` is `L4`, no path is unknown, and the external gates include Project Constraints, Research Web Checks, and `research-web-bootstrap` bound to `#macos-14`.

- [ ] **Step 2: Run every local validation selected by the generated plan**

Execute the exact local closure emitted by the calibrated policy:

```bash
node --test tests/javascript/verification_policy.test.mjs
node --test tests/javascript/verification_receipt.test.mjs
node --test tests/javascript/incremental_validation_skill.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q
node --test tests/javascript/research_web_architecture.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_protocol.py
node --test \
  tests/javascript/research_web_architecture.test.mjs \
  tests/javascript/documentation_governance.test.mjs \
  tests/javascript/actions_quota_governance.test.mjs
node scripts/check_documentation_governance.mjs --project .
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check
node .agents/project-constraints.mjs \
  --project . \
  --changed-file .agents/project-constraints.json \
  --changed-file .agents/verification-policy.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-receipt.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification.md \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight-receipt.json \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight.md \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-checks.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file AGENTS.md \
  --changed-file docs/README.md \
  --changed-file docs/actions-budget.md \
  --changed-file docs/architecture/research-web/06-documentation-contract.md \
  --changed-file docs/documentation-governance.json \
  --changed-file docs/research-web-documentation.md \
  --changed-file docs/research-web-installation.md \
  --changed-file docs/superpowers/plans/2026-09-23-mac-only-web-verification.md \
  --changed-file docs/superpowers/specs/2026-09-23-mac-only-web-verification-design.md \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file tests/research_web/test_local_integrations.py
git diff --check
git diff --check b36fb0ee6be4cd13b19b89311adfed82bc129f9d..HEAD
```

Expected: every selected local validation passes and Project Constraints returns zero violations. Record actual durations and outcomes; do not copy expected values into the receipt.

- [ ] **Step 3: Write report and receipt**

The report must state:

```markdown
- Windows automatic validation is paused; no Windows result is claimed for this policy-change delivery.
- Local macOS validation passed before publication.
- GitHub macOS Bootstrap remains a required external gate and is still pending until publish.
- Desktop Windows rules were not changed.
```

Create the receipt from the generated template. Before publication, local items are `passed`, external items are `not_run`, `result` is `blocked`, and uncovered risks list each pending external gate.

- [ ] **Step 4: Validate the receipt and commit the local closure**

Run:

```bash
node scripts/validate_verification_receipt.mjs \
  --project . \
  --plan .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  --receipt .ai/reports/2026-09-23-mac-only-web-verification-receipt.json
```

Expected: `"valid": true` with an honestly blocked pre-publication result.

Commit:

```bash
git add \
  .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  .ai/reports/2026-09-23-mac-only-web-verification-receipt.json \
  .ai/reports/2026-09-23-mac-only-web-verification.md
git commit -m "docs: record mac-only verification evidence"
```

### Task 6: Publish and prove the new remote boundary

**Files:**
- Modify after CI: `.ai/reports/2026-09-23-mac-only-web-verification-receipt.json`
- Modify after CI: `.ai/reports/2026-09-23-mac-only-web-verification.md`

- [ ] **Step 1: Prepare the new delivery and verify the merged result**

Run:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --prepare \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery
```

Use the integration worktree returned by the controller for merged-result verification; `--replace-prepared` may return a revision-suffixed path. All initial-delivery changed-file commands below enumerate the exact 22-file set relative to `b36fb0ee6be4cd13b19b89311adfed82bc129f9d`, including the two carried P0 reports and four documentation-governance files. The later evidence-only closeout has its own two-file delta. Run this complete closure:

```bash
cd /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability-worktrees/mac-only-web-verification-delivery-integration
task_mac_verify_started=$(date +%s)
# Use the controller-returned integration path after --replace-prepared.
node scripts/plan_verification.mjs \
  --project . \
  --changed-file .agents/project-constraints.json \
  --changed-file .agents/verification-policy.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-receipt.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification.md \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight-receipt.json \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight.md \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-checks.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file AGENTS.md \
  --changed-file docs/README.md \
  --changed-file docs/actions-budget.md \
  --changed-file docs/architecture/research-web/06-documentation-contract.md \
  --changed-file docs/documentation-governance.json \
  --changed-file docs/research-web-documentation.md \
  --changed-file docs/research-web-installation.md \
  --changed-file docs/superpowers/plans/2026-09-23-mac-only-web-verification.md \
  --changed-file docs/superpowers/specs/2026-09-23-mac-only-web-verification-design.md \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file tests/research_web/test_local_integrations.py \
  > .ai/reports/2026-09-23-mac-only-web-verification-plan.json
node --test tests/javascript/verification_policy.test.mjs
node --test tests/javascript/verification_receipt.test.mjs
node --test tests/javascript/incremental_validation_skill.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q
node --test tests/javascript/research_web_architecture.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_protocol.py
node --test \
  tests/javascript/research_web_architecture.test.mjs \
  tests/javascript/documentation_governance.test.mjs \
  tests/javascript/actions_quota_governance.test.mjs
node scripts/check_documentation_governance.mjs --project .
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check
node .agents/project-constraints.mjs \
  --project . \
  --changed-file .agents/project-constraints.json \
  --changed-file .agents/verification-policy.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-receipt.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification.md \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight-receipt.json \
  --changed-file .ai/reports/2026-09-23-research-web-startup-preflight.md \
  --changed-file .github/workflows/research-web-bootstrap.yml \
  --changed-file .github/workflows/research-web-checks.yml \
  --changed-file .github/workflows/research-web-windows-verify.yml \
  --changed-file AGENTS.md \
  --changed-file docs/README.md \
  --changed-file docs/actions-budget.md \
  --changed-file docs/architecture/research-web/06-documentation-contract.md \
  --changed-file docs/documentation-governance.json \
  --changed-file docs/research-web-documentation.md \
  --changed-file docs/research-web-installation.md \
  --changed-file docs/superpowers/plans/2026-09-23-mac-only-web-verification.md \
  --changed-file docs/superpowers/specs/2026-09-23-mac-only-web-verification-design.md \
  --changed-file tests/javascript/actions_quota_governance.test.mjs \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file tests/research_web/test_local_integrations.py
node scripts/validate_verification_receipt.mjs \
  --project . \
  --plan .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  --receipt .ai/reports/2026-09-23-mac-only-web-verification-receipt.json
git diff --check
git diff --check b36fb0ee6be4cd13b19b89311adfed82bc129f9d..HEAD
task_mac_verify_seconds=$(( $(date +%s) - task_mac_verify_started ))
test "$task_mac_verify_seconds" -ge 0
printf '%s\n' "$task_mac_verify_seconds" > /tmp/rwb-mac-only-verify-seconds
```

Expected: integration is conflict-free, the plan has no unknown/uncovered local risk, and all local validations pass.

- [ ] **Step 2: Publish without force-push**

Run from the P0 project worktree, reusing the measured integer from Step 1:

```bash
task_mac_verify_seconds=$(sed -n '1p' /tmp/rwb-mac-only-verify-seconds)
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --publish \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery \
  --verification-command "merged result: generated L4 plan, workflow and policy contracts, local integrations, protocol, documentation governance, Python index, Project Constraints and diff checks" \
  --verification-status passed \
  --verification-duration-seconds "$task_mac_verify_seconds"
```

Expected: `origin/master` advances to the integration commit and the controller enters `awaiting_ci`.

- [ ] **Step 3: Verify automatic GitHub runs**

Inspect runs for the published commit. Required results:

```text
Project Constraints: success
Research Web Checks: success
Research Web Bootstrap: success, exactly one Clean Web install (macos-14) job
Research Web Windows Verify: no automatically triggered run for the commit
```

If a Windows job starts automatically, treat the delivery as failed even if it passes.

- [ ] **Step 4: Close the receipt with remote evidence on the feature branch**

After the first delivery reaches `ci_passed`, update the report and receipt in `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability-worktrees/mac-only-web-verification-delivery`. Record commit SHA, run IDs, URLs and conclusions. Change the three external gate statuses to `passed`, set `result` to `passed`, and clear external-gate uncovered risks. Explicitly state that Windows was not run and is not claimed.

- [ ] **Step 5: Validate and publish the evidence-only closeout**

Validate the receipt again, run documentation governance and Project Constraints for the two evidence files, and commit them:

```bash
git add \
  .ai/reports/2026-09-23-mac-only-web-verification-receipt.json \
  .ai/reports/2026-09-23-mac-only-web-verification.md
git commit -m "docs: close mac-only Web verification"
```

Prepare a second revision of the same delivery:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --prepare \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery
```

Verify the new merged result and measure its duration:

```bash
task_mac_closeout_started=$(date +%s)
node scripts/validate_verification_receipt.mjs \
  --project . \
  --plan .ai/reports/2026-09-23-mac-only-web-verification-plan.json \
  --receipt .ai/reports/2026-09-23-mac-only-web-verification-receipt.json
node scripts/check_documentation_governance.mjs --project .
node .agents/project-constraints.mjs \
  --project . \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification-receipt.json \
  --changed-file .ai/reports/2026-09-23-mac-only-web-verification.md
git diff --check
task_mac_closeout_seconds=$(( $(date +%s) - task_mac_closeout_started ))
test "$task_mac_closeout_seconds" -ge 0
printf '%s\n' "$task_mac_closeout_seconds" > /tmp/rwb-mac-only-closeout-seconds
```

Then publish with:

```bash
task_mac_closeout_seconds=$(sed -n '1p' /tmp/rwb-mac-only-closeout-seconds)
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --publish \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery \
  --verification-command "evidence closeout: receipt validation, documentation governance, Project Constraints and diff checks" \
  --verification-status passed \
  --verification-duration-seconds "$task_mac_closeout_seconds"
```

Expected: the evidence-only commit lands on `origin/master`, triggers no Windows run, and its required lightweight CI passes.

- [ ] **Step 6: Clean both delivery controllers and enforce Harness completion**

After all CI for the evidence-only commit passes:

```bash
task_mac_verify_seconds=$(sed -n '1p' /tmp/rwb-mac-only-verify-seconds)
task_mac_closeout_seconds=$(sed -n '1p' /tmp/rwb-mac-only-closeout-seconds)
task_mac_total_verify_seconds=$(( task_mac_verify_seconds + task_mac_closeout_seconds ))
test "$task_mac_total_verify_seconds" -ge 0

node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --cleanup \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery

node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --cleanup \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id p0-web-stability-delivery

node /Users/leon/.agents/leon-engineering/runtime/harness-project.mjs \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery \
  --record-outcome \
  --status completed \
  --clarification-rounds 1 \
  --rework-count 0 \
  --verification-command "local Mac plus GitHub macOS workflow, policy, receipt and delivery closure" \
  --verification-status passed \
  --verification-duration-seconds "$task_mac_total_verify_seconds"

node /Users/leon/.agents/leon-engineering/runtime/harness-enforce.mjs \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability \
  --task-id mac-only-web-verification-delivery \
  --require-delivery
```

Expected: both delivery receipts are `cleaned`, temporary controller worktrees/branches are safely removed, remote `master` contains the final receipt, and no unrelated or dirty worktree is deleted. `task_mac_total_verify_seconds` is the non-negative measured sum of the two verification durations; do not invent it.
