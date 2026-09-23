# Incremental Validation

Project-local workflow for choosing and evidencing the minimum sufficient
Research Workbench acceptance closure. Read [SKILL.md](SKILL.md) before use.

## Inputs

- The complete repository-relative changed-file set.
- Optional runtime escalation signals: `validation_failure` or
  `unexpected_behavior`.
- Actual command, CI, platform, duration, and evidence results.

## Outputs

- A schema-v2 JSON plan from `scripts/plan_verification.mjs`.
- A JSON receipt containing actual executions, external gates, uncovered risks,
  and escalation decisions.
- A validator verdict from `scripts/validate_verification_receipt.mjs`.

## Safety boundaries

This Skill cannot publish, cannot execute planned commands automatically, and
cannot downgrade an L4 plan. The scripts never execute command strings stored
in policy, plan, or receipt JSON. Missing impact mappings fail closed.

## Examples

### Example 1: Small change

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file app/research_web/ui/frameworks/goldar.mjs
```

### Example 2: Cross-module change

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file app/research_web/frameworks/goldar/store.py \
  --changed-file app/research_web/ui/frameworks/goldar.mjs
```

### Example 3: Escalate and validate evidence

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file app/research_web/ui/frameworks/goldar.mjs \
  --signal validation_failure
node scripts/validate_verification_receipt.mjs --project . \
  --plan .ai/reports/example-plan.json \
  --receipt .ai/reports/example-receipt.json
```
