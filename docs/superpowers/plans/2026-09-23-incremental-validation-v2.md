# Incremental Validation v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Research Workbench verification planning with explicit L0-L4 closures, Change-to-Impact-to-Validation evidence, automatic escalation, and mechanically validated execution receipts.

**Architecture:** Evolve the strict project-local policy and read-only planner to schema v2 while preserving the existing risk and category projections. Add a second read-only validator that compares a generated plan with an execution receipt; keep command execution outside both scripts and document the workflow in a project-local skill.

**Tech Stack:** Node.js ESM and standard library, `node:test`, JSON, Markdown, existing Python/JavaScript tests and project governance commands; no new dependencies.

---

### Task 1: Freeze the v2 planner contract with failing tests

**Files:**
- Modify: `tests/javascript/verification_policy.test.mjs`
- Modify: `.ai/reports/incremental-validation-v2-PROGRESS.md`
- Create: `.ai/reports/incremental-validation-v2-BLOCKED.md`

- [ ] **Step 1: Add a schema-v2 fixture**

  Replace the fixture policy's scalar catalog values with entries such as:

  ```js
  "research-web-frameworks-ui": {
    level: "L1",
    value: "node --test tests/javascript/research_web_frameworks_ui.test.mjs",
  }
  ```

  Add `levelOrder`, `escalation`, and the rule fields `minimumLevel`, `impact`,
  and `coupling`. Keep the fixture structurally identical to the repository
  policy so strict-schema tests exercise the real contract.

- [ ] **Step 2: Add three representative closure tests**

  Add assertions for:

  ```js
  assert.equal(small.requiredLevel, "L1");
  assert.deepEqual(small.validationsByLevel.L1.map(item => item.id), [
    "research-web-frameworks-ui",
  ]);
  assert.equal(small.validationsByLevel.L4.length, 0);

  assert.equal(crossModule.requiredLevel, "L3");
  assert.equal(
    crossModule.escalations.some(item => item.code === "multiple_high_coupling_modules"),
    true,
  );

  assert.equal(highRisk.requiredLevel, "L4");
  assert.equal(highRisk.uncoveredRisks.length, 0);
  ```

  The changed sets are respectively a framework renderer, a framework backend
  plus renderer, and `.agents/verification-policy.json`.

- [ ] **Step 3: Add named escalation coverage**

  Cover public contract, schema, configuration/CI, core abstraction/shared
  utility, data model/migration, dependency, security, desktop, release,
  parser/workflow/agent orchestration, and unknown paths. Assert L4 for the
  high-risk set, at least L3 for known critical-chain paths, and no accidental
  desktop gates for non-desktop paths.

- [ ] **Step 4: Add runtime-signal coverage**

  Extend the test helper to pass repeatable `--signal` arguments. Assert a
  small L1 plan becomes L2 after `validation_failure`, becomes L3 when both
  supported signals are present, deduplicates repeated signals, and rejects an
  unknown signal with `ARGUMENT_ERROR`.

- [ ] **Step 5: Run and record the expected RED**

  Run:

  ```bash
  node --test tests/javascript/verification_policy.test.mjs
  ```

  Expected: new v2 assertions fail because the current planner rejects schema
  version 2 or omits `requiredLevel`; all pre-existing failures must still be
  explained, with no syntax-error failure in the tests. Record counts and the
  decisive error in the PROGRESS report.

### Task 2: Implement the L0-L4 policy and read-only planner

**Files:**
- Modify: `.agents/verification-policy.json`
- Modify: `scripts/plan_verification.mjs`
- Modify: `tests/javascript/verification_policy.test.mjs`
- Modify: `.ai/reports/incremental-validation-v2-PROGRESS.md`

- [ ] **Step 1: Advance the strict policy schema**

  Set:

  ```json
  {
    "schemaVersion": 2,
    "riskOrder": ["docs-only", "local-only", "full-delivery"],
    "levelOrder": ["L0", "L1", "L2", "L3", "L4"],
    "escalation": {"highCouplingImpactThreshold": 2, "targetLevel": "L3"}
  }
  ```

  Every catalog item receives `level` and `value`. Every rule receives
  `minimumLevel`, non-empty `impact`, and `coupling`. Add precise rules for
  framework renderers, framework backend, critical chains, core/shared and
  data-model boundaries. Keep unknown fallback at `full-delivery`/`L4`.

- [ ] **Step 2: Parse and validate v2 fields**

  Add exact-key sets and parsers equivalent to:

  ```js
  const LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4"];

  function assertLevel(value, label) {
    if (!LEVEL_ORDER.includes(value)) fail("POLICY_ERROR", `invalid ${label}`);
    return value;
  }
  ```

  Reject unknown fields, missing impacts, duplicate impacts, invalid coupling,
  catalog entries whose level is unknown, and an escalation target below L1.

- [ ] **Step 3: Parse runtime signals**

  Permit repeatable `--signal validation_failure|unexpected_behavior`,
  deduplicate in first-seen order, and reject all other values. Preserve the
  existing `--project` and repeatable `--changed-file` behavior.

- [ ] **Step 4: Compute impact and levels**

  Extend `planVerification` to emit:

  ```js
  {
    schemaVersion: 2,
    risk,
    requiredLevel,
    changeSummary: {fileCount, ruleIds, impactIds},
    changedFiles,
    impact,
    reasons,
    escalations,
    uncoveredRisks,
    validationsByLevel,
    tests,
    documentation,
    ci,
    receiptTemplate,
  }
  ```

  Use the highest rule/catalog level, raise distinct high-coupling impacts to
  at least the configured target, then raise one step per unique runtime signal
  capped at L4. Group selected gates by their catalog level without duplicating
  IDs.

- [ ] **Step 5: Preserve read-only and compatibility behavior**

  Keep `fs` reads only, do not import `child_process`, and retain stable JSON
  errors. Compatibility arrays continue to contain `{id, value}` plus additive
  `level`; desktop-specific catalog items remain absent unless the desktop rule
  matched.

- [ ] **Step 6: Run planner tests to GREEN**

  Run:

  ```bash
  node --test tests/javascript/verification_policy.test.mjs
  ```

  Expected: all tests pass, with zero failed, skipped, cancelled, or todo.

### Task 3: Add the execution-receipt contract

**Files:**
- Create: `scripts/validate_verification_receipt.mjs`
- Create: `tests/javascript/verification_receipt.test.mjs`
- Modify: `.ai/reports/incremental-validation-v2-PROGRESS.md`

- [ ] **Step 1: Write receipt tests first**

  Build plan and receipt fixtures in temporary real directories. A valid
  receipt contains:

  ```js
  {
    schemaVersion: 1,
    changeSummary: plan.changeSummary,
    changedFiles: plan.changedFiles,
    plannedLevel: plan.requiredLevel,
    actualLevel: plan.requiredLevel,
    impact: plan.impact,
    executed: plan.receiptTemplate.requiredValidationIds.map(id => ({
      id,
      level: validationLevel(plan, id),
      status: "passed",
      durationSeconds: 1,
      evidence: `logs/${id}.log`,
    })),
    result: "passed",
    uncoveredRisks: [],
    escalation: {required: false, targetLevel: null, reasons: []},
  }
  ```

  Test valid success, missing required validation, changed-file mismatch,
  unknown validation, actual level below planned, failed validation reported as
  passed, missing escalation after failure/unexpected behavior, insufficient
  escalation target, symlinked inputs, schema drift, and policy command text
  never being executed.

- [ ] **Step 2: Run receipt tests to RED**

  Run:

  ```bash
  node --test tests/javascript/verification_receipt.test.mjs
  ```

  Expected: fail because `scripts/validate_verification_receipt.mjs` does not
  exist, not because the fixture or test syntax is invalid.

- [ ] **Step 3: Implement strict receipt validation**

  Implement exact-key parsing, safe project-relative plan/receipt paths,
  no-symlink reads, plan schema checks, and semantic comparisons. Use stable
  error codes `ARGUMENT_ERROR`, `PATH_ERROR`, `PLAN_ERROR`, and
  `RECEIPT_ERROR`. The success payload is:

  ```js
  {
    schemaVersion: 1,
    valid: true,
    result: receipt.result,
    plannedLevel: plan.requiredLevel,
    actualLevel: receipt.actualLevel,
    executedCount: receipt.executed.length,
    escalationRequired: receipt.escalation.required,
  }
  ```

- [ ] **Step 4: Run receipt tests to GREEN**

  Run both contract files and record exact counts:

  ```bash
  node --test \
    tests/javascript/verification_policy.test.mjs \
    tests/javascript/verification_receipt.test.mjs
  ```

### Task 4: Make the workflow reusable and current

**Files:**
- Create: `.agents/skills/incremental-validation/SKILL.md`
- Create: `.agents/skills/incremental-validation/README.md`
- Modify: `.claude/commands/verify-task.md`
- Modify: `docs/AGENT_WORKFLOW.md`
- Modify: `docs/DEVELOPMENT_MAP.md`
- Modify: `.ai/reports/incremental-validation-v2-PROGRESS.md`

- [ ] **Step 1: Add the project-local skill**

  Define the trigger as planning or recording acceptance for a Research
  Workbench change. The procedure must: obtain the complete changed set; run
  the planner; execute only the returned closure; replan with a signal after
  failure/unexpected behavior; create a receipt; validate it; and report
  uncovered risks. The skill references the policy and scripts rather than
  copying their routing tables.

- [ ] **Step 2: Add the skill README**

  Document purpose, inputs, output artifacts, safety boundaries, and three
  example invocations. State explicitly that the skill cannot publish, execute
  commands automatically, or downgrade an L4 plan.

- [ ] **Step 3: Update workflow and development map**

  Document L0-L4 semantics, Change-to-Impact-to-Validation fields, runtime
  signals, receipt requirements, and exact ownership of policy/planner/
  validator/tests. Preserve the current Web-only versus desktop boundary.

- [ ] **Step 4: Keep the Claude entrypoint thin**

  Update `verify-task.md` with planner and receipt-validator usage only. Do not
  duplicate matcher lists, gate lists, or level routing decisions.

- [ ] **Step 5: Run documentation and structure checks**

  Run:

  ```bash
  node scripts/check_documentation_governance.mjs --project .
  python scripts/generate_py_file_index.py --check
  node --test tests/javascript/documentation_governance.test.mjs
  ```

  Expected: all checks pass with no documentation violations or stale Python
  index.

### Task 5: Prove the mechanism with real plans and receipts

**Files:**
- Create: `.ai/reports/incremental-validation-v2-small-plan.json`
- Create: `.ai/reports/incremental-validation-v2-small-receipt.json`
- Create: `.ai/reports/incremental-validation-v2-cross-plan.json`
- Create: `.ai/reports/incremental-validation-v2-cross-receipt.json`
- Create: `.ai/reports/incremental-validation-v2-high-risk-plan.json`
- Create: `.ai/reports/incremental-validation-v2-high-risk-receipt.json`
- Modify: `.ai/reports/incremental-validation-v2-PROGRESS.md`
- Maintain: `.ai/reports/incremental-validation-v2-BLOCKED.md`

- [ ] **Step 1: Generate and execute the small-change closure**

  Plan `app/research_web/ui/frameworks/goldar.mjs`. Run exactly its selected
  local commands that are executable in the current environment, capture real
  durations/evidence, create and validate the receipt. Prove no L4 or desktop
  gate was selected.

- [ ] **Step 2: Generate and execute the cross-module closure**

  Plan `app/research_web/frameworks/service.py` plus
  `app/research_web/ui/frameworks/goldar.mjs`. Run the selected unit,
  dependency, and smoke commands, create and validate the receipt, and prove
  the high-coupling rule raised the plan to at least L3.

- [ ] **Step 3: Generate the high-risk closure and complete its real L4 gates**

  Plan all files changed by this implementation, which includes verification
  policy and scripts. Execute the complete L4 closure actually returned by the
  plan, including policy/receipt contracts, existing architecture and
  documentation gates, diff checks, and full relevant Project Constraints.
  Do not mark remote CI or publication passed unless it is actually requested
  and observed; record those as uncovered/external when outside this task.

- [ ] **Step 4: Validate all three receipts**

  Run the receipt validator separately for the three plan/receipt pairs.
  Expected: three `valid: true` verdicts and evidence references that exist.

- [ ] **Step 5: Record cost evidence**

  In PROGRESS compare selected validation counts by level. State the exact
  checks omitted by the small plan and the forced checks retained by the
  high-risk plan. Do not claim Token savings unless measured; the accepted cost
  evidence is reduced command scope with unchanged safety gates.

### Task 6: Final review and Harness closeout

**Files:** all changed files

- [ ] **Step 1: Run final scoped and full policy acceptance**

  Run all commands selected by the high-risk plan, then:

  ```bash
  /usr/bin/git diff --check origin/master...HEAD
  /usr/bin/git status --short
  ```

  Confirm no unrelated main-worktree files are present in the branch.

- [ ] **Step 2: Run Project Constraints for the complete changed set**

  Pass every `git diff --name-only origin/master...HEAD` path as a repeated
  `--changed-file` argument to `.agents/project-constraints.mjs`. Expected:
  `violations` is empty.

- [ ] **Step 3: Record the actual Harness outcome**

  Record only the commands actually run, their real status, and integer
  duration. Run `harness-enforce.mjs` for `incremental-validation-v2`. Do not
  use a delivery-required flag because publication was not requested.

- [ ] **Step 4: Review completion requirement by requirement**

  Check the user objective against current files and command output: explicit
  L0-L4 model, minimal selection, escalation conditions, complete receipts,
  three real iteration types, small-plan savings, high-risk retention, and
  reusable scripts/skill/rules. Leave the Goal active if any item lacks direct
  evidence.
