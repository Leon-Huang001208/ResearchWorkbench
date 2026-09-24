# DataHub Provider and Asset Workbench Verification Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route known AKShare Provider and Asset Workbench changes through a direct L1-L3 acceptance closure while keeping every unregistered DataHub path fail-closed at L4.

**Architecture:** Treat the union of optional negative prefixes as delegated namespaces in the read-only planner. For a path in such a namespace, only rules with positive files or prefixes inside that namespace may participate; global segments, suffixes, and parent prefixes are isolated. Exact allowlist rules then recognize only AKShare and Asset Workbench boundaries; every other DataHub source falls through to the existing L4 fallback. Direct catalogs cover Provider, DataHub core, Workbench UI/API, and a single L3 asset-observation smoke path.

**Tech Stack:** Node.js ESM planner and `node:test`; JSON verification policy; Python 3.12/`pytest`; Markdown governance; managed Git worktrees and GitHub Actions.

---

## File map

- Modify `scripts/plan_verification.mjs`: parse and enforce optional `match.excludePrefixes`.
- Modify `.agents/verification-policy.json`: delegate DataHub from the generic rule, add five catalogs and three exact component rules, remove the Workbench test from framework UI.
- Modify `tests/javascript/verification_policy.test.mjs`: mirror catalogs/rules and prove schema, routing, escalation, and fail-closed behavior.
- Modify `docs/AGENT_WORKFLOW.md`: explain delegated DataHub allowlists and L1-L3 Workbench closure.
- Modify `docs/DEVELOPMENT_MAP.md`: map AKShare/Asset Workbench sources to direct catalogs.
- Modify `.agents/skills/incremental-validation/README.md`: document behavior without copying the path table.
- Create `.ai/reports/2026-09-24-datahub-workbench-routing-plan.json`.
- Create `.ai/reports/2026-09-24-datahub-workbench-routing-receipt.json`.
- Create `.ai/reports/2026-09-24-datahub-workbench-routing.md`.
- Existing design: `docs/superpowers/specs/2026-09-24-datahub-workbench-verification-routing-design.md`.
- This plan: `docs/superpowers/plans/2026-09-24-datahub-workbench-verification-routing.md`.

### Task 1: Add RED contracts for namespace delegation safety

**Files:**
- Modify: `tests/javascript/verification_policy.test.mjs`
- Test: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Add real-policy nested-path fail-closed contracts**

Prove each of these paths produces `full-delivery` / L4, `ruleIds=["fallback"]`, `unknown_path`, and
`unknown_impact_boundary`:

```text
app/research_web/datahub/workflows/new_provider.py
app/research_web/datahub/parsers/new_provider.py
app/research_web/datahub/README.md
```

- [ ] **Step 2: Add fixture collision and owner contracts**

With generic DataHub delegation active, add global low-level parent-prefix, `workflows` / `parsers` segment, and
`.md` suffix rules. Nested DataHub paths must still fall back. Then add a namespace owner prefix
`app/research_web/datahub/public/`; `public/workflows/provider.py` must select only that owner even though a global
segment rule also matches.

- [ ] **Step 3: Add longest-prefix contract**

Declare both `app/research_web/datahub/` and `app/research_web/datahub/public/` delegated. Add one owner for each
namespace and prove a public path selects only the more specific owner.

- [ ] **Step 4: Run RED**

Run:

```bash
node --test tests/javascript/verification_policy.test.mjs
```

Expected: new namespace tests fail because current planner only applies exclusions to the declaring rule; the
existing 56 contracts remain green.

- [ ] **Step 5: Commit design, plan, and RED**

```bash
git add docs/superpowers/specs/2026-09-24-datahub-workbench-verification-routing-design.md \
  docs/superpowers/plans/2026-09-24-datahub-workbench-verification-routing.md \
  tests/javascript/verification_policy.test.mjs
git commit -m "test: define namespace delegation safety"
```

### Task 2: Enforce global delegated namespaces

**Files:**
- Modify: `scripts/plan_verification.mjs`
- Test: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Return normalized delegated prefixes from policy loading**

After parsing all rules, collect every rule's `match.excludePrefixes`, deduplicate, and sort longest first. Return
the result as `delegatedPrefixes` alongside `rules`:

```javascript
const delegatedPrefixes = [...new Set(
  rules.flatMap(rule => rule.match.excludePrefixes),
)].sort((left, right) => right.length - left.length);
```

- [ ] **Step 2: Define namespace ownership**

Only positive files and prefixes inside the delegated namespace establish ownership:

```javascript
function ownsDelegatedPrefix(match, prefix) {
  return match.files.some(file => file.startsWith(prefix)) ||
    match.prefixes.some(candidate => candidate.startsWith(prefix));
}
```

- [ ] **Step 3: Restrict candidates before ordinary matching**

For each changed path, select the longest matching delegated prefix, limit candidates to owner rules, then call
the unchanged ordinary `matches` function. Preserve the existing per-rule exclusion check inside `matches`:

```javascript
const delegatedPrefix = policy.delegatedPrefixes.find(prefix => changedFile.startsWith(prefix));
const candidateRules = delegatedPrefix
  ? policy.rules.filter(rule => ownsDelegatedPrefix(rule.match, delegatedPrefix))
  : policy.rules;
const matchedRules = candidateRules.filter(rule => matches(rule.match, changedFile));
```

If no owner rule matches, use the existing fallback unchanged. Do not make segments, suffixes, or parent prefixes
owners, and do not change risk merging, receipt construction, or signal escalation.

- [ ] **Step 4: Run GREEN and regression tests**

```bash
node --test tests/javascript/verification_policy.test.mjs
node --test tests/javascript/verification_receipt.test.mjs
```

Expected: all tests pass; old fixture rules without `excludePrefixes` remain valid.

- [ ] **Step 5: Commit planner support**

```bash
git add scripts/plan_verification.mjs tests/javascript/verification_policy.test.mjs
git commit -m "fix: enforce delegated verification namespaces"
```

### Task 3: Add RED routing matrix contracts

**Files:**
- Modify: `tests/javascript/verification_policy.test.mjs`
- Test: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Add real-policy route expectations**

Add:

```javascript
test("AKShare provider uses the bounded L2 DataHub closure", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/datahub/providers_akshare.py",
    "tests/research_web/test_datahub_catalog.py",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L2");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-datahub-public-provider",
  ]);
  assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
    "project-constraints-local",
    "research-web-datahub-core",
  ]);
  assert.deepEqual(plan.validationsByLevel.L3, []);
  assert.deepEqual(plan.validationsByLevel.L4, []);
});

test("asset Workbench UI no longer selects framework validation", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/ui/asset-workspace.mjs",
    "tests/javascript/research_web_workbench.test.mjs",
  ]));
  assert.equal(plan.requiredLevel, "L1");
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
  ]);
  assert.equal(plan.changeSummary.impactIds.includes("framework-ui"), false);
  assert.equal(plan.tests.some(item => item.id.startsWith("research-web-framework")), false);
});

test("AKShare plus asset UI escalates to the bounded L3 user path", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/datahub/providers_akshare.py",
    "app/research_web/ui/asset-workspace.mjs",
  ]));
  assert.equal(plan.requiredLevel, "L3");
  assert.deepEqual(plan.escalations, [{
    code: "multiple_high_coupling_modules",
    fromLevel: "L2",
    toLevel: "L3",
    impacts: ["datahub-public-provider", "asset-workbench-ui"],
  }]);
  assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
    "project-constraints-local",
    "research-web-datahub-core",
    "research-web-asset-workspace-python",
  ]);
  assert.deepEqual(plan.validationsByLevel.L3.map(item => item.id), [
    "research-web-asset-workspace-smoke",
  ]);
  assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
});

test("unregistered DataHub boundaries remain L4 fallback paths", () => {
  for (const changedFile of [
    "app/research_web/datahub/providers_wind.py",
    "app/research_web/datahub/providers_mysql.py",
    "app/research_web/datahub/providers_cjpy.py",
    "app/research_web/datahub/broker.py",
    "app/research_web/datahub/contracts.py",
    "app/research_web/datahub/security.py",
    "app/research_web/datahub/snapshots.py",
    "app/research_web/datahub/future_provider.py",
    "app/research_web/datahub/workflows/new_provider.py",
    "app/research_web/datahub/parsers/new_provider.py",
    "app/research_web/datahub/README.md",
    "tests/research_web/test_datahub_wind.py",
  ]) {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.requiredLevel, "L4", changedFile);
    assert.equal(plan.reasons.some(item => item.code === "unknown_path"), true, changedFile);
    assert.deepEqual(plan.uncoveredRisks, ["unknown_impact_boundary"], changedFile);
  }
});
```

Fixture coverage must also include a specialized prefix owner colliding with a global `workflows` segment rule;
the exact `ruleIds` must contain only the owner. Add an overlapping broad and narrow namespace case to prove the
longest delegated prefix wins.

- [ ] **Step 2: Add backend-only expectation**

```javascript
test("asset Workbench backend uses L2 and selects its direct contracts", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/asset_workspace.py",
    "tests/research_web/test_asset_workspace.py",
  ]));
  assert.equal(plan.requiredLevel, "L2");
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
  ]);
  assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
    "project-constraints-local",
    "research-web-asset-workspace-python",
  ]);
});

for (const {name, changedFiles} of [
  {
    name: "AKShare provider",
    changedFiles: ["app/research_web/datahub/providers_akshare.py"],
  },
  {
    name: "Asset Workbench backend",
    changedFiles: ["tests/research_web/test_asset_workspace.py"],
  },
]) {
  test(`${name} retains full validation after two runtime signals`, () => {
    const plan = success(run(repositoryRoot, changedFiles, ["validation_failure", "unexpected_behavior"]));
    assert.equal(plan.requiredLevel, "L4");
    assert.equal(plan.validationsByLevel.L4.some(item => item.id === "research-web-verification-full"), true);
  });
}

test("Provider plus Workbench UI retains full validation after a validation failure", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/datahub/providers_akshare.py",
    "app/research_web/ui/asset-workspace.mjs",
  ], ["validation_failure"]));
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.validationsByLevel.L4.some(item => item.id === "research-web-verification-full"), true);
});

test("three specialized rules declare the full validation catalog", () => {
  const actual = JSON.parse(fs.readFileSync(
    path.join(repositoryRoot, ".agents/verification-policy.json"),
    "utf8",
  ));
  const rules = new Map(actual.rules.map(item => [item.id, item]));
  for (const id of [
    "research-web-datahub-public-provider",
    "research-web-asset-workbench-ui",
    "research-web-asset-workbench-backend",
  ]) {
    assert.equal(rules.get(id)?.tests.includes("research-web-verification-full"), true, id);
  }
});
```

- [ ] **Step 3: Run RED**

```bash
node --test tests/javascript/verification_policy.test.mjs
```

Expected: failures show AKShare/catalog still unknown or generic, Workbench still selects framework catalogs, and
DataHub sensitive source paths still stop at L1.

- [ ] **Step 4: Commit RED**

```bash
git add tests/javascript/verification_policy.test.mjs
git commit -m "test: define DataHub Workbench verification matrix"
```

### Task 4: Add catalogs and exact component rules

**Files:**
- Modify: `.agents/verification-policy.json`
- Modify: `tests/javascript/verification_policy.test.mjs`
- Test: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Add five test catalogs to production and fixture policy**

Insert these production JSON catalog entries, with identical IDs/levels/commands in the fixture via `catalog(...)`:

```json
"research-web-datahub-public-provider": {
  "level": "L1",
  "execution": "local",
  "value": "python -m pytest tests/research_web/test_datahub_catalog.py --confcutdir=tests/research_web"
},
"research-web-datahub-core": {
  "level": "L2",
  "execution": "local",
  "value": "python -m pytest tests/research_web/test_datahub.py --confcutdir=tests/research_web"
},
"research-web-asset-workbench-ui": {
  "level": "L1",
  "execution": "local",
  "value": "node --test tests/javascript/research_web_workbench.test.mjs"
},
"research-web-asset-workspace-python": {
  "level": "L2",
  "execution": "local",
  "value": "python -m pytest tests/research_web/test_asset_workspace.py --confcutdir=tests/research_web"
},
"research-web-asset-workspace-smoke": {
  "level": "L3",
  "execution": "local",
  "value": "python -m pytest tests/research_web/test_asset_workspace.py::test_asset_observation_tracks_each_block_and_freezes_handoff_context --confcutdir=tests/research_web"
}
```

Fixture entries:

```javascript
"research-web-datahub-public-provider": catalog(
  "L1",
  "python -m pytest tests/research_web/test_datahub_catalog.py --confcutdir=tests/research_web",
),
"research-web-datahub-core": catalog(
  "L2",
  "python -m pytest tests/research_web/test_datahub.py --confcutdir=tests/research_web",
),
"research-web-asset-workbench-ui": catalog(
  "L1",
  "node --test tests/javascript/research_web_workbench.test.mjs",
),
"research-web-asset-workspace-python": catalog(
  "L2",
  "python -m pytest tests/research_web/test_asset_workspace.py --confcutdir=tests/research_web",
),
"research-web-asset-workspace-smoke": catalog(
  "L3",
  "python -m pytest tests/research_web/test_asset_workspace.py::test_asset_observation_tracks_each_block_and_freezes_handoff_context --confcutdir=tests/research_web",
),
```

Update the focused-Python catalog count contract from 8 to 12 and keep the assertion that every matching command
contains `--confcutdir=tests/research_web`.

- [ ] **Step 2: Delegate the DataHub subtree from the generic rule**

Add only to the production and fixture `research-web` match:

```json
"excludePrefixes": ["app/research_web/datahub/"]
```

Do not add exclusions to any other rule.

- [ ] **Step 3: Add the public Provider rule**

```json
{
  "id": "research-web-datahub-public-provider",
  "risk": "local-only",
  "minimumLevel": "L2",
  "reason": "research_web_datahub_public_provider_change",
  "impact": ["datahub-public-provider"],
  "coupling": "high",
  "match": {
    "files": [
      "app/research_web/datahub/providers_akshare.py",
      "tests/research_web/test_datahub_catalog.py"
    ],
    "prefixes": [],
    "segments": [],
    "suffixes": []
  },
  "tests": [
    "research-web-architecture",
    "research-web-datahub-public-provider",
    "project-constraints-local",
    "research-web-datahub-core",
    "research-web-asset-workspace-smoke",
    "research-web-verification-full"
  ],
  "documentation": ["documentation-governance", "python-file-index"],
  "ci": ["project-constraints", "research-web-checks"]
}
```

- [ ] **Step 4: Add the Asset Workbench UI rule**

```json
{
  "id": "research-web-asset-workbench-ui",
  "risk": "local-only",
  "minimumLevel": "L1",
  "reason": "research_web_asset_workbench_ui_change",
  "impact": ["asset-workbench-ui"],
  "coupling": "high",
  "match": {
    "files": [
      "app/research_web/ui/asset-workspace.mjs",
      "tests/javascript/research_web_workbench.test.mjs"
    ],
    "prefixes": [],
    "segments": [],
    "suffixes": []
  },
  "tests": [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
    "project-constraints-local",
    "research-web-asset-workspace-python",
    "research-web-asset-workspace-smoke",
    "research-web-verification-full"
  ],
  "documentation": ["documentation-governance"],
  "ci": ["project-constraints", "research-web-checks"]
}
```

Remove `tests/javascript/research_web_workbench.test.mjs` from
`research-web-framework-ui.match.files` in production and fixture policy.

- [ ] **Step 5: Add the Asset Workbench backend rule**

```json
{
  "id": "research-web-asset-workbench-backend",
  "risk": "local-only",
  "minimumLevel": "L2",
  "reason": "research_web_asset_workbench_backend_change",
  "impact": ["asset-workbench-backend"],
  "coupling": "high",
  "match": {
    "files": [
      "app/research_web/asset_workspace.py",
      "app/research_web/asset_routes.py",
      "tests/research_web/test_asset_workspace.py"
    ],
    "prefixes": [],
    "segments": [],
    "suffixes": []
  },
  "tests": [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
    "project-constraints-local",
    "research-web-asset-workspace-python",
    "research-web-asset-workspace-smoke",
    "research-web-verification-full"
  ],
  "documentation": ["documentation-governance", "python-file-index"],
  "ci": ["project-constraints", "research-web-checks"]
}
```

- [ ] **Step 6: Mirror rules in the fixture**

Insert these objects via the existing `rule({...})` helper:

```javascript
rule({
  id: "research-web-datahub-public-provider",
  risk: "local-only",
  minimumLevel: "L2",
  reason: "research_web_datahub_public_provider_change",
  impact: ["datahub-public-provider"],
  coupling: "high",
  match: {
    files: [
      "app/research_web/datahub/providers_akshare.py",
      "tests/research_web/test_datahub_catalog.py",
    ],
    prefixes: [],
    segments: [],
    suffixes: [],
  },
  tests: [
    "research-web-architecture",
    "research-web-datahub-public-provider",
    "project-constraints-local",
    "research-web-datahub-core",
    "research-web-asset-workspace-smoke",
    "research-web-verification-full",
  ],
  documentation: ["documentation-governance", "python-file-index"],
  ci: ["project-constraints", "research-web-checks"],
}),
rule({
  id: "research-web-asset-workbench-ui",
  risk: "local-only",
  minimumLevel: "L1",
  reason: "research_web_asset_workbench_ui_change",
  impact: ["asset-workbench-ui"],
  coupling: "high",
  match: {
    files: [
      "app/research_web/ui/asset-workspace.mjs",
      "tests/javascript/research_web_workbench.test.mjs",
    ],
    prefixes: [],
    segments: [],
    suffixes: [],
  },
  tests: [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
    "project-constraints-local",
    "research-web-asset-workspace-python",
    "research-web-asset-workspace-smoke",
    "research-web-verification-full",
  ],
  documentation: ["documentation-governance"],
  ci: ["project-constraints", "research-web-checks"],
}),
rule({
  id: "research-web-asset-workbench-backend",
  risk: "local-only",
  minimumLevel: "L2",
  reason: "research_web_asset_workbench_backend_change",
  impact: ["asset-workbench-backend"],
  coupling: "high",
  match: {
    files: [
      "app/research_web/asset_workspace.py",
      "app/research_web/asset_routes.py",
      "tests/research_web/test_asset_workspace.py",
    ],
    prefixes: [],
    segments: [],
    suffixes: [],
  },
  tests: [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
    "project-constraints-local",
    "research-web-asset-workspace-python",
    "research-web-asset-workspace-smoke",
    "research-web-verification-full",
  ],
  documentation: ["documentation-governance", "python-file-index"],
  ci: ["project-constraints", "research-web-checks"],
}),
```

Do not share mutable arrays between rules.

- [ ] **Step 7: Run GREEN**

```bash
node --test tests/javascript/verification_policy.test.mjs
```

Expected: all policy tests pass; the four matrix tests show L2/L1/L3/L4 exactly as specified.

- [ ] **Step 8: Commit policy routing**

```bash
git add .agents/verification-policy.json tests/javascript/verification_policy.test.mjs
git commit -m "ci: route DataHub and asset Workbench verification"
```

### Task 5: Synchronize workflow documentation

**Files:**
- Modify: `docs/AGENT_WORKFLOW.md`
- Modify: `docs/DEVELOPMENT_MAP.md`
- Modify: `.agents/skills/incremental-validation/README.md`
- Test: `tests/javascript/incremental_validation_skill.test.mjs`

- [ ] **Step 1: Update Agent Workflow**

Add under component routing:

```markdown
DataHub 默认从通用 Research Web 规则排除：只有策略中显式 allowlist 的公共 Provider 才能使用
L1-L3 专项闭包，未登记的 Broker、契约、安全、快照、专业 Provider 或未来文件继续 L4
`unknown_path`。Asset Workbench UI 与 backend 使用独立规则；Provider+UI 的两个高耦合 impact
自动升到 L3，并运行资产观察 API/快照/呈现 smoke。
```

- [ ] **Step 2: Update Development Map**

Extend the DataHub and UI rows so they name:

```markdown
`providers_akshare.py` → `test_datahub_catalog.py` + `test_datahub.py`;
`ui/asset-workspace.mjs` → `research_web_workbench.test.mjs`;
`asset_workspace.py` / `asset_routes.py` → `test_asset_workspace.py`.
未登记 DataHub 路径继续 fail closed，不从目录位置推断低风险。
```

- [ ] **Step 3: Update the incremental-validation README**

Add a behavior-only note:

```markdown
命中 delegated namespace 后仅 namespace owner rules 参与；无 owner 必须 fallback；不能跳过 fallback 或直接降低风险。
```

Do not copy the production file list into the skill README.

- [ ] **Step 4: Run documentation and skill contracts**

```bash
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
node --test tests/javascript/incremental_validation_skill.test.mjs
git diff --check
```

Expected: zero documentation violations, generated index verified, skill contracts pass, no whitespace errors.

- [ ] **Step 5: Commit docs**

```bash
git add docs/AGENT_WORKFLOW.md docs/DEVELOPMENT_MAP.md .agents/skills/incremental-validation/README.md
git commit -m "docs: explain DataHub verification delegation"
```

### Task 6: Produce real plans, evidence, receipt, and delivery

**Files:**
- Create: `.ai/reports/2026-09-24-datahub-workbench-routing-plan.json`
- Create: `.ai/reports/2026-09-24-datahub-workbench-routing-receipt.json`
- Create: `.ai/reports/2026-09-24-datahub-workbench-routing.md`
- Modify if required by generated output: `docs/generated/py_file_index.md`

- [ ] **Step 1: Run representative planner matrix**

Run the real planner separately for:

```text
app/research_web/datahub/providers_akshare.py
app/research_web/ui/asset-workspace.mjs
app/research_web/datahub/providers_akshare.py + app/research_web/ui/asset-workspace.mjs
app/research_web/asset_workspace.py
app/research_web/datahub/providers_wind.py
app/research_web/datahub/security.py
app/research_web/datahub/future_provider.py
.agents/verification-policy.json
```

Record exact risk, level, validation IDs, escalation and uncovered risks in the task report. Expected results are
L2, L1, L3, L2, L4, L4, L4 and L4 respectively.

- [ ] **Step 2: Generate the complete changed-set plan**

Run `scripts/plan_verification.mjs` with one `--changed-file` for every actual source, test, doc, generated and
evidence path. Save stdout exactly as the plan JSON. Read `requiredLevel`, `validationsByLevel`,
`uncoveredRisks`, and `receiptTemplate` before running checks.

Expected: because the policy and planner themselves changed, the task is `full-delivery/L4`; this self-delivery
does not demonstrate the future L1-L3 savings.

- [ ] **Step 3: Execute the selected L0-L4 closure**

At minimum, run the exact selected commands for:

Before the first validation, record the start time:

```bash
date +%s > /tmp/verification-datahub-workbench-routing-started
```

```text
documentation-governance
python-file-index
verification-policy-contracts
verification-receipt-contracts
incremental-validation-skill-contracts
research-web-verification-full
project-constraints-local
```

Also run direct provider/workbench catalogs once to prove their commands are executable:

```bash
python -m pytest tests/research_web/test_datahub_catalog.py --confcutdir=tests/research_web
python -m pytest tests/research_web/test_datahub.py --confcutdir=tests/research_web
node --test tests/javascript/research_web_workbench.test.mjs
python -m pytest tests/research_web/test_asset_workspace.py --confcutdir=tests/research_web
```

Use an existing approved development environment; do not install dependencies. On any failure, rerun the planner
with `--signal validation_failure`; on unexpected output, use `--signal unexpected_behavior`.

After the last required local validation succeeds, record the measured duration:

```bash
verification_started=$(sed -n '1p' /tmp/verification-datahub-workbench-routing-started)
verification_seconds=$(( $(date +%s) - verification_started ))
test "$verification_seconds" -ge 0
printf '%s\n' "$verification_seconds" > /tmp/verification-datahub-workbench-routing-seconds
```

- [ ] **Step 4: Create and validate the receipt**

The pre-CI receipt must list every selected local ID with real status/duration/evidence and every ID from the
actual plan's `externalGateIds` as `not_run`. For the expected policy changed set this includes
`project-constraints`; record `external_gate_not_run:project-constraints`, keep the overall result `blocked`, and
add any additional external ID emitted by the real plan rather than assuming it away. Validate with:

```bash
node scripts/validate_verification_receipt.mjs --project . \
  --plan .ai/reports/2026-09-24-datahub-workbench-routing-plan.json \
  --receipt .ai/reports/2026-09-24-datahub-workbench-routing-receipt.json
```

- [ ] **Step 5: Commit implementation evidence**

```bash
git add scripts/plan_verification.mjs .agents/verification-policy.json \
  tests/javascript/verification_policy.test.mjs \
  docs/AGENT_WORKFLOW.md docs/DEVELOPMENT_MAP.md \
  .agents/skills/incremental-validation/README.md \
  docs/superpowers/specs/2026-09-24-datahub-workbench-verification-routing-design.md \
  docs/superpowers/plans/2026-09-24-datahub-workbench-verification-routing.md \
  .ai/reports/2026-09-24-datahub-workbench-routing-plan.json \
  .ai/reports/2026-09-24-datahub-workbench-routing-receipt.json \
  .ai/reports/2026-09-24-datahub-workbench-routing.md
git commit -m "ci: specialize DataHub Workbench verification"
```

- [ ] **Step 6: Prepare and verify the integration result**

Use the existing managed delivery task `verification-datahub-workbench-routing`:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs --prepare \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id verification-datahub-workbench-routing
```

In the returned integration worktree rerun the complete plan, representative matrix, direct catalogs, receipt
validator, documentation governance, Project Constraints, and `git diff --check`. The integration worktree must
remain clean.

- [ ] **Step 7: Publish and wait for required CI**

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs --publish \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id verification-datahub-workbench-routing \
  --verification-command "L4 policy contracts representative routing matrix and direct catalogs" \
  --verification-status passed \
  --verification-duration-seconds "$(sed -n '1p' /tmp/verification-datahub-workbench-routing-seconds)"
```

Poll the same delivery until Project Constraints and every workflow selected by the actual plan are conclusive.
After local Mac success, manually dispatch the Mac-only Research Web Bootstrap on the published SHA. Do not
dispatch Research Web Tabbit Verify because it also launches Windows.

- [ ] **Step 8: Persist external evidence and clean up**

Update the report and receipt with the exact published SHA, run IDs, URLs and conclusions; change external gates
and result to `passed` only after observation. Commit the evidence-only revision, prepare/publish it, wait for its
lightweight CI, then run controller cleanup.

Record the Harness outcome and enforce delivery:

```bash
node /Users/leon/.agents/leon-engineering/runtime/harness-enforce.mjs \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id verification-datahub-workbench-routing \
  --require-delivery
```

Finally back up the main-checkout task paths, fast-forward `master` to `origin/master`, and verify one worktree,
tracked-clean status, local/origin/remote SHA equality, passed receipt, stopped services, and no Windows run.
