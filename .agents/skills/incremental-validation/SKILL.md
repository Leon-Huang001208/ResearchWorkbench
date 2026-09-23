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
   `changeSummary`, `impact`, `requiredLevel`, `validationsByLevel`,
   `uncoveredRisks`, and `receiptTemplate` before running anything.
3. Execute only the returned validation closure, in L0→L4 order. Capture the
   real status, duration, and evidence path for every
   `receiptTemplate.requiredValidationIds` item. Record every selected external
   gate in `external`; do not call an unobserved gate passed.
4. On a local check failure, replan with `--signal validation_failure`. On any
   unexpected behavior, replan with `--signal unexpected_behavior`. Run the
   expanded closure and retain both attempts in the evidence record.
5. Create the receipt with the exact change summary, impact, changed files,
   planned/actual levels, executed checks, `external`, result,
   `uncoveredRisks`, and escalation decision.
6. Run `scripts/validate_verification_receipt.mjs --project . --plan <plan>
   --receipt <receipt>`. A nonzero result is incomplete acceptance, not a
   warning to bypass.

## Invariants

- `.agents/verification-policy.json` is the sole routing source.
- Never run a full suite merely by habit; run it when the plan reaches L4.
- Never downgrade L4, unknown impact, a failed check, or an external gate.
- The scripts are read-only validators. They do not run Git, tests, CI,
  publication, or commands stored in JSON.
- A `full-delivery` external gate marked `not_run` must leave the receipt
  `blocked` with a named uncovered risk.
