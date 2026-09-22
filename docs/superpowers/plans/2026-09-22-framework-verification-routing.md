# Research Web Framework Verification Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Research Web framework source and its three known test files select the complete framework-specific verification closure without weakening fail-closed routing for unknown or high-risk paths.

**Architecture:** Add one data-only `research-web-frameworks` rule and three test catalog entries to the existing strict JSON policy; keep `scripts/plan_verification.mjs` unchanged and rely on its existing multi-rule, highest-risk, stable-dedup merge semantics. Freeze the behavior with production-policy CLI tests, preserve all desktop and unknown-path hard gates, then deliver the CI-governance change through the managed full-delivery controller.

**Tech Stack:** Node.js ESM and `node:test`, strict JSON policy, Markdown governance, Python pytest for framework verification, Git worktrees, leon-engineering Harness and iteration-delivery controller.

---

## File map

- Modify `.agents/verification-policy.json`: add three framework test commands and the additive framework routing rule.
- Modify `tests/javascript/verification_policy.test.mjs`: add RED/GREEN routing contracts and keep the in-test policy fixture synchronized.
- Modify `docs/AGENT_WORKFLOW.md`: document the component-specific framework closure within minimal verification.
- Modify `docs/DEVELOPMENT_MAP.md`: document known-test routing versus unknown-test fail-closed behavior.
- Create `.ai/reports/framework-verification-routing-PROGRESS.md`: record actual RED, GREEN, feature, integration, CI, cleanup, and Harness evidence.
- Preserve `scripts/plan_verification.mjs`: no parser, schema, execution, or permission change is needed.

### Task 1: Start managed delivery and carry the approved specification forward

**Files:**
- Preserve: `docs/superpowers/specs/2026-09-22-framework-verification-routing-design.md`
- Preserve: `docs/superpowers/plans/2026-09-22-framework-verification-routing.md`

- [ ] **Step 1: Recheck the remote default branch and clean main worktree**

Run:

```bash
git -C /Users/leon/Developer/ResearchWorkbench status --short --branch
git -C /Users/leon/Developer/ResearchWorkbench ls-remote --symref origin HEAD
```

Expected: main worktree has no porcelain entries, and origin HEAD resolves to `refs/heads/master`. If the remote tip differs from the design base, keep the design branch intact and let the controller start from the current remote tip.

- [ ] **Step 2: Start the managed full-delivery task**

Run:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --start \
  --project /Users/leon/Developer/ResearchWorkbench \
  --task-id framework-verification-routing-20260922 \
  --slug framework-verification-routing
```

Expected: JSON receipt with `status: "started"`, a clean feature branch, and a new `featureWorktree`. Record that exact path as `rwb_feature_worktree`; do not invent it.

- [ ] **Step 3: Start Harness in the managed feature worktree**

Run, replacing the path only with the receipt's exact `featureWorktree`:

```bash
node /Users/leon/.agents/leon-engineering/runtime/harness-project.mjs \
  --project "$rwb_feature_worktree" \
  --task-id framework-verification-routing-20260922 \
  --goal "Add precise framework verification routing without weakening fail-closed gates" \
  --acceptance "Framework source selects architecture plus three framework tests" \
  --acceptance "Known framework tests are local-only and unknown tests remain full-delivery" \
  --acceptance "No desktop gates leak into Web-only framework plans" \
  --acceptance "Merged result, remote CI, cleanup, and Harness delivery gates pass" \
  --delivery-required \
  --write-harness
```

Expected: task state is written for `framework-verification-routing-20260922` with delivery required.

- [ ] **Step 4: Merge the approved design and plan into the managed feature branch**

Run:

```bash
git -C "$rwb_feature_worktree" merge --no-ff \
  codex/framework-verification-routing-design \
  -m "merge: add framework verification routing design"
git -C "$rwb_feature_worktree" status --short --branch
```

Expected: merge succeeds without conflict and the managed feature worktree is clean.

### Task 2: Freeze framework routing with RED tests

**Files:**
- Modify: `tests/javascript/verification_policy.test.mjs:161-227`
- Test: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Add the framework test ID constant**

Insert after `gateIds`:

```javascript
const frameworkTestIds = [
  "research-web-frameworks-python",
  "research-web-framework-collectors",
  "research-web-frameworks-ui",
];
```

- [ ] **Step 2: Add five production-policy routing tests**

Insert after the existing pure Research Web test:

```javascript
test("framework source selects architecture and all framework-specific tests", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/frameworks/service.py",
    "app/research_web/ui/frameworks/goldar.mjs",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.deepEqual(plan.tests.map(item => item.id), ["research-web-architecture", ...frameworkTestIds]);
  const ids = gateIds(plan).join(" ").toLowerCase();
  for (const forbidden of ["desktop", "windows", "tauri", "sidecar", "installer"]) {
    assert.equal(ids.includes(forbidden), false, `${forbidden} leaked into framework plan`);
  }
});

test("known framework test files use the framework-specific local closure", () => {
  const plan = success(run(repositoryRoot, [
    "tests/research_web/test_frameworks.py",
    "tests/research_web/test_framework_collectors.py",
    "tests/javascript/research_web_frameworks_ui.test.mjs",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.deepEqual(plan.tests.map(item => item.id), frameworkTestIds);
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
});

test("unmapped test files still fail closed", () => {
  const plan = success(run(repositoryRoot, ["tests/research_web/test_unmapped_component.py"]));
  assert.equal(plan.risk, "full-delivery");
  assert.deepEqual(plan.reasons, [{
    path: "tests/research_web/test_unmapped_component.py",
    rule: "fallback",
    code: "unknown_path",
  }]);
});

test("high-risk paths keep full delivery while retaining framework tests", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/frameworks/service.py",
    "requirements/web.lock",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.deepEqual(plan.tests.map(item => item.id), ["research-web-architecture", ...frameworkTestIds]);
  assert.equal(plan.reasons.some(item => item.code === "dependency_change"), true);
});

test("framework gates remain ordered and deduplicated across repeated paths", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/frameworks/service.py",
    "tests/research_web/test_frameworks.py",
    "app/research_web/frameworks/service.py",
  ]));
  assert.deepEqual(plan.changedFiles, [
    "app/research_web/frameworks/service.py",
    "tests/research_web/test_frameworks.py",
  ]);
  assert.deepEqual(plan.tests.map(item => item.id), ["research-web-architecture", ...frameworkTestIds]);
  for (const collection of [plan.tests, plan.documentation, plan.ci]) {
    const ids = collection.map(item => item.id);
    assert.equal(new Set(ids).size, ids.length);
  }
});
```

- [ ] **Step 3: Run only the new contracts and verify RED**

Run:

```bash
node --test --test-name-pattern "framework|unmapped test" \
  tests/javascript/verification_policy.test.mjs
```

Expected before policy changes: the unmapped-test test passes; the framework source, known tests, high-risk retention, and ordered-dedup tests fail because the three catalog IDs and framework rule do not yet exist. Record exact counts and failure messages in the task report later.

- [ ] **Step 4: Commit the RED contracts**

Run:

```bash
git add tests/javascript/verification_policy.test.mjs
git commit -m "test: freeze framework verification routing"
```

Expected: one commit containing tests only; the known RED result remains documented and intentional.

### Task 3: Implement the minimal data-only policy change

**Files:**
- Modify: `.agents/verification-policy.json:9-11,232-256`
- Modify: `tests/javascript/verification_policy.test.mjs:12-127`
- Test: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Add three test catalog entries to the production policy**

Change `catalogs.tests` to:

```json
"tests": {
  "research-web-architecture": "node --test tests/javascript/research_web_architecture.test.mjs",
  "research-web-frameworks-python": "python -m pytest tests/research_web/test_frameworks.py",
  "research-web-framework-collectors": "python -m pytest tests/research_web/test_framework_collectors.py",
  "research-web-frameworks-ui": "node --test tests/javascript/research_web_frameworks_ui.test.mjs"
}
```

- [ ] **Step 2: Add the framework rule after the general Research Web rule**

Append this rule before the `rules` array closes:

```json
{
  "id": "research-web-frameworks",
  "risk": "local-only",
  "reason": "research_web_framework_change",
  "match": {
    "files": [
      "app/research_web/ui/frameworks.mjs",
      "tests/research_web/test_frameworks.py",
      "tests/research_web/test_framework_collectors.py",
      "tests/javascript/research_web_frameworks_ui.test.mjs"
    ],
    "prefixes": [
      "app/research_web/frameworks/",
      "app/research_web/ui/frameworks/"
    ],
    "segments": [],
    "suffixes": []
  },
  "tests": [
    "research-web-frameworks-python",
    "research-web-framework-collectors",
    "research-web-frameworks-ui"
  ],
  "documentation": [
    "documentation-governance",
    "python-file-index"
  ],
  "ci": [
    "project-constraints",
    "research-web-checks"
  ]
}
```

The rule must stay after `research-web` so source-path output order is architecture first, then the three component tests.

- [ ] **Step 3: Synchronize the test fixture policy**

In `policy()` add the same three catalog IDs and add the same `research-web-frameworks` rule after the fixture's `research-web` rule. Do not add broader `tests/` prefixes or change fallback.

- [ ] **Step 4: Validate JSON and run the focused policy suite**

Run:

```bash
node -e "JSON.parse(require('node:fs').readFileSync('.agents/verification-policy.json', 'utf8'))"
node --test tests/javascript/verification_policy.test.mjs
```

Expected: JSON parse exits 0; policy suite reports 17 passed, 0 failed, 0 skipped, 0 todo.

- [ ] **Step 5: Execute every newly cataloged command**

Run:

```bash
python -m pytest tests/research_web/test_frameworks.py
python -m pytest tests/research_web/test_framework_collectors.py
node --test tests/javascript/research_web_frameworks_ui.test.mjs
```

Expected: every command exits 0 with no skipped tests. Do not install Python packages if the interpreter lacks dependencies; record that as a real blocker instead.

- [ ] **Step 6: Commit policy and fixture GREEN**

Run:

```bash
git add .agents/verification-policy.json tests/javascript/verification_policy.test.mjs
git commit -m "feat: route framework verification precisely"
```

Expected: a focused policy/test commit with no planner implementation changes.

### Task 4: Synchronize workflow documentation

**Files:**
- Modify: `docs/AGENT_WORKFLOW.md:26-40`
- Modify: `docs/DEVELOPMENT_MAP.md:38-62`

- [ ] **Step 1: Extend the minimal-verification explanation**

After the Web-only paragraph in `docs/AGENT_WORKFLOW.md`, add:

```markdown
Research Web 框架源码与三个已登记框架测试文件使用同一个组件专项闭环：框架 Python、采集器和 UI 测试。框架源码仍叠加通用 Research Web 架构测试；已登记测试文件不因位于 `tests/` 而落入未知路径。其他未登记测试继续 fail closed，不能用通用测试目录规则批量降级。
```

- [ ] **Step 2: Extend the Development Map routing contract**

After the minimal-verification paragraph in `docs/DEVELOPMENT_MAP.md`, add:

```markdown
已知组件测试可以在策略中按精确文件映射到对应 `local-only` 专项闭环；当前框架映射覆盖 `test_frameworks.py`、`test_framework_collectors.py` 与 `research_web_frameworks_ui.test.mjs`。未登记测试仍按 `unknown_path` 升级 `full-delivery`，不得仅凭位于 `tests/` 目录推断低风险。
```

- [ ] **Step 3: Run documentation checks**

Run:

```bash
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
```

Expected: documentation governance reports 0 violations; Python index reports verified without rewriting generated files.

- [ ] **Step 4: Commit documentation**

Run:

```bash
git add docs/AGENT_WORKFLOW.md docs/DEVELOPMENT_MAP.md
git commit -m "docs: explain framework verification closure"
```

### Task 5: Run complete feature verification and record evidence

**Files:**
- Create: `.ai/reports/framework-verification-routing-PROGRESS.md`
- Verify: all files changed since `origin/master`

- [ ] **Step 1: Run the four policy/governance Node suites together**

Run:

```bash
node --test \
  tests/javascript/verification_policy.test.mjs \
  tests/javascript/research_web_architecture.test.mjs \
  tests/javascript/documentation_governance.test.mjs \
  tests/javascript/actions_quota_governance.test.mjs
```

Expected after adding five policy tests: 92 passed, 0 failed, 0 skipped, 0 todo.

- [ ] **Step 2: Prove the source and test-only plans directly**

Run:

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file app/research_web/frameworks/service.py \
  --changed-file app/research_web/ui/frameworks/goldar.mjs

node scripts/plan_verification.mjs --project . \
  --changed-file tests/research_web/test_frameworks.py \
  --changed-file tests/research_web/test_framework_collectors.py \
  --changed-file tests/javascript/research_web_frameworks_ui.test.mjs

node scripts/plan_verification.mjs --project . \
  --changed-file tests/research_web/test_unmapped_component.py
```

Expected: source plan is `local-only` with architecture plus three component tests; known-test plan is `local-only` with three component tests and no `unknown_path`; unmapped test is `full-delivery` with `unknown_path`.

- [ ] **Step 3: Run remaining local gates against the complete changed set**

Run:

```bash
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
git diff --check origin/master...HEAD
node scripts/plan_verification.mjs --project . \
  --changed-file .agents/verification-policy.json \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file docs/AGENT_WORKFLOW.md \
  --changed-file docs/DEVELOPMENT_MAP.md \
  --changed-file docs/superpowers/specs/2026-09-22-framework-verification-routing-design.md \
  --changed-file docs/superpowers/plans/2026-09-22-framework-verification-routing.md \
  --changed-file .ai/reports/framework-verification-routing-PROGRESS.md
node .agents/project-constraints.mjs --project . \
  --changed-file .agents/verification-policy.json \
  --changed-file tests/javascript/verification_policy.test.mjs \
  --changed-file docs/AGENT_WORKFLOW.md \
  --changed-file docs/DEVELOPMENT_MAP.md \
  --changed-file docs/superpowers/specs/2026-09-22-framework-verification-routing-design.md \
  --changed-file docs/superpowers/plans/2026-09-22-framework-verification-routing.md \
  --changed-file .ai/reports/framework-verification-routing-PROGRESS.md
```

Expected: documentation governance has 0 violations, Python index is verified, diff check exits 0, and Project Constraints returns `violations: []`. The complete changed set itself must plan as `full-delivery` because it includes `.agents/verification-policy.json` and its policy test.

- [ ] **Step 4: Write the evidence report from actual outputs**

Only after all preceding commands pass, create `.ai/reports/framework-verification-routing-PROGRESS.md` with this exact structure and the observed counts/commits inserted as literal values:

```markdown
# framework-verification-routing PROGRESS

- Scope: additive framework verification policy only; planner implementation and product runtime unchanged.
- RED: focused framework contracts failed before policy data existed; unmapped-test fail-closed contract passed.
- GREEN: verification policy suite passed with 17 tests and zero skipped/todo.
- Component commands: framework Python, collector, and UI commands all exited 0 with zero skipped.
- Routing: framework source is local-only with architecture plus three component tests; known tests are local-only; unmapped tests remain full-delivery.
- Desktop boundary: framework plans contain zero desktop, Windows, Tauri, sidecar, or installer gates.
- Governance: 92 policy/architecture/documentation/Actions tests passed; documentation violations 0; Python index verified; Project Constraints violations 0.
- Delivery: feature commit recorded; integration, publication, CI, cleanup, and Harness evidence will be appended only after each succeeds.

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"仅扩充验收策略的数据路由和对应文档；Research Web 运行架构、产品模块与图清单均未改变。","diagrams":[]} -->
```

If any expected count differs, write the real count and explain the difference instead of copying the expected number.

- [ ] **Step 5: Commit the verified report**

Run:

```bash
git add .ai/reports/framework-verification-routing-PROGRESS.md
git commit -m "docs: record framework routing verification"
git status --short --branch
```

Expected: feature worktree is clean.

### Task 6: Prepare, verify the merged result, publish, and clean up

**Files:**
- Update with real receipts: `.ai/reports/framework-verification-routing-PROGRESS.md`
- Verify: managed integration worktree and live remote default branch

- [ ] **Step 1: Prepare the managed integration result**

Run:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --prepare \
  --project /Users/leon/Developer/ResearchWorkbench \
  --task-id framework-verification-routing-20260922
```

Expected: receipt includes an `integrationWorktree`, integration commit, and status ready for merged-result verification. If the remote default branch advanced, use this new integration result rather than rebasing or force-pushing manually.

- [ ] **Step 2: Repeat the full verification in the integration worktree**

In the receipt's exact `integrationWorktree`, keep one shell session open and run:

```bash
rwb_verification_command='node --test tests/javascript/verification_policy.test.mjs tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs && python -m pytest tests/research_web/test_frameworks.py && python -m pytest tests/research_web/test_framework_collectors.py && node --test tests/javascript/research_web_frameworks_ui.test.mjs && node scripts/check_documentation_governance.mjs --project . && python scripts/generate_py_file_index.py --check && node .agents/project-constraints.mjs --project . --changed-file .agents/verification-policy.json --changed-file tests/javascript/verification_policy.test.mjs --changed-file docs/AGENT_WORKFLOW.md --changed-file docs/DEVELOPMENT_MAP.md --changed-file docs/superpowers/specs/2026-09-22-framework-verification-routing-design.md --changed-file docs/superpowers/plans/2026-09-22-framework-verification-routing.md --changed-file .ai/reports/framework-verification-routing-PROGRESS.md && git diff --check origin/master...HEAD'
rwb_verification_started=$(date +%s)
/bin/bash -c "$rwb_verification_command"
rwb_verification_seconds=$(($(date +%s)-rwb_verification_started))
printf 'verification_seconds=%s\n' "$rwb_verification_seconds"
```

Expected: every command exits 0, Node aggregate is 92/92 with no skipped/todo, component tests have no skipped, governance has no violations, and the index is verified. Record a whole-number duration in seconds and the exact command string.

- [ ] **Step 3: Publish using the merged-result verification receipt**

In the same shell session, publish with the exact command and measured integer duration:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --publish \
  --project /Users/leon/Developer/ResearchWorkbench \
  --task-id framework-verification-routing-20260922 \
  --verification-command "$rwb_verification_command" \
  --verification-status passed \
  --verification-duration-seconds "$rwb_verification_seconds"
```

Expected: direct publication to the live default branch, or a protected-branch PR fallback recorded by the controller. Do not force-push.

- [ ] **Step 4: Wait for authoritative CI status**

Run:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --status \
  --project /Users/leon/Developer/ResearchWorkbench \
  --task-id framework-verification-routing-20260922
```

Expected: `ci.status` becomes `passed` or explicitly `not_configured`. While pending, poll the same receipt with bounded waits; on failure, make at most three evidence-based repair commits through `--publish --repair` and repeat merged-result verification.

- [ ] **Step 5: Append actual delivery evidence and republish if the report changed**

Append the real integration commit, remote commit, CI run/status, and verification duration to the report. If this creates a new feature commit after an earlier publication, run `--prepare`, repeat Step 2, publish the new integration result, and wait for CI again. Never claim the earlier CI covers the later report commit.

- [ ] **Step 6: Clean managed branches and worktrees**

Run only after CI passed or was explicitly not configured:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --cleanup \
  --project /Users/leon/Developer/ResearchWorkbench \
  --task-id framework-verification-routing-20260922
```

Expected: status `cleaned`; managed feature/integration worktrees and local/remote managed branches are gone.

- [ ] **Step 7: Record Harness outcome and enforce full delivery**

Read the final verification receipt back from the Git common directory, then record it in Harness:

```bash
rwb_delivery_receipt='/Users/leon/Developer/ResearchWorkbench/.git/leon-engineering/deliveries/framework-verification-routing-20260922.json'
rwb_verification_command=$(node -e "const r=require(process.argv[1]); process.stdout.write(r.verification.command)" "$rwb_delivery_receipt")
rwb_verification_seconds=$(node -e "const r=require(process.argv[1]); process.stdout.write(String(r.verification.durationSeconds))" "$rwb_delivery_receipt")

node /Users/leon/.agents/leon-engineering/runtime/harness-project.mjs \
  --project /Users/leon/Developer/ResearchWorkbench \
  --task-id framework-verification-routing-20260922 \
  --record-outcome \
  --status completed \
  --clarification-rounds 2 \
  --rework-count 0 \
  --verification-command "$rwb_verification_command" \
  --verification-status passed \
  --verification-duration-seconds "$rwb_verification_seconds"

node /Users/leon/.agents/leon-engineering/runtime/harness-enforce.mjs \
  --project /Users/leon/Developer/ResearchWorkbench \
  --task-id framework-verification-routing-20260922 \
  --require-delivery
```

Expected: Harness records `completed/passed`; enforcement reports cleaned delivery, passing/not-configured CI, and the live remote commit.

- [ ] **Step 8: Remove the temporary design worktree only after ancestry proof**

Run:

```bash
git -C /Users/leon/Developer/ResearchWorkbench fetch origin master
git -C /Users/leon/Developer/ResearchWorkbench merge-base --is-ancestor \
  codex/framework-verification-routing-design origin/master
git -C /Users/leon/Developer/ResearchWorkbench worktree remove \
  /Users/leon/Developer/ResearchWorkbench-worktrees/framework-verification-routing-design
git -C /Users/leon/Developer/ResearchWorkbench branch -d \
  codex/framework-verification-routing-design
```

Expected: ancestry command exits 0; the temporary design worktree and branch are removed without force. Final `git worktree list` contains only the primary worktree and `ResearchWorkbench-local-changes`, and main is clean at the live remote default tip.
