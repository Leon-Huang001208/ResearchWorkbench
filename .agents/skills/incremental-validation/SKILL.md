---
name: incremental-validation
description: Use when planning, escalating, or evidencing acceptance for a Research Workbench code, configuration, test, or documentation change
---

# Incremental Validation

Use the smallest sufficient acceptance closure without weakening fail-closed
gates. The policy decides scope; neither this Skill nor the planner may invent a
downgrade.

## Procedure

1. Build the complete changed set from the current diff. Include generated,
   test, configuration, documentation, and deleted paths; never plan from a
   hand-picked subset.
2. Run `scripts/plan_verification.mjs` with one `--changed-file` per path. Read
   `changeSummary`, `components`, `impact`, `requiredLevel`, `platforms`,
   `validationsByLevel`, `local`, `ci`, `realMachine`, `uncoveredRisks`, and
   `receiptTemplate` before running anything. Verify
   `.agents/runtime/leon-engineering/manifest.json` before trusting the shared kernel.
3. Execute only the returned validation closure, in L0→L4 order. Capture the
   real status, duration, and evidence path for every
   `receiptTemplate.requiredValidationIds` item. Record selected CI merge gates
   in `external` and physical-device release gates in `realMachine`; do not call
   an unobserved gate `PASS`.
4. On a local check failure, replan with `--signal validation_failure`. On any
   unexpected behavior, replan with `--signal unexpected_behavior`. Run the
   expanded closure and retain both attempts in the evidence record.
5. Create a schema-v2 receipt with the exact change summary, components,
   platforms, impact, changed files, planned/actual levels, `executed`,
   `external`, `realMachine`, result, `mergeReady`, `releaseReady`,
   `uncoveredRisks`, and escalation decision. Use only `PASS`, `FAIL`,
   `SKIPPED`, `NOT_REQUIRED`, `NOT_RUN`, `BLOCKED`, or `MANUAL_REQUIRED`.
6. Run `scripts/validate_verification_receipt.mjs --project . --plan <plan>
   --receipt <receipt>`. A nonzero result is incomplete acceptance, not a
   warning to bypass.

## Invariants

- `.agents/verification-policy.json` is the sole routing source.
- Never run a full suite merely by habit; run it when the plan reaches L4.
- Never downgrade L4, unknown impact, a failed check, or an external gate.
- The scripts are read-only validators. They do not run Git, tests, CI,
  publication, or commands stored in JSON.
- A selected merge gate marked `NOT_RUN`, `SKIPPED`, `BLOCKED`, or
  `MANUAL_REQUIRED` must leave `mergeReady=false` and the receipt `BLOCKED`.
- A release-only real-machine gate marked `MANUAL_REQUIRED` may leave a passed
  merge receipt, but it must keep `releaseReady=false`; Windows CI `PASS` never
  implies Windows real-machine `PASS`.
- `NOT_REQUIRED` describes an unselected scope and is invalid for a gate the
  plan selected.
