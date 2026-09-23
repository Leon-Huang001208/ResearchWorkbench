# Incremental Validation v2 Design

## Objective

Extend the existing read-only verification planner into a project-local L0-L4
incremental acceptance framework. The framework must select the smallest
sufficient closure for the complete changed-file set, fail closed when impact
cannot be bounded, and preserve evidence that distinguishes planned checks from
checks actually executed.

The current v1 planner remains the migration base: it already validates paths,
deduplicates gates, separates Web-only work from desktop delivery, and escalates
unknown or high-risk paths. v2 adds explicit levels, impact metadata, dynamic
escalation signals, and a mechanical receipt contract without turning the
planner into a command runner.

## Boundaries

- `.agents/verification-policy.json` remains the only routing source of truth.
- `scripts/plan_verification.mjs` remains read-only: it reads policy and
  repository-relative paths, then emits JSON. It never runs Git, tests, CI,
  release, or commands stored in the policy.
- A separate `scripts/validate_verification_receipt.mjs` validates evidence
  produced after execution. It does not run commands or manufacture results.
- No dependency is added. Both scripts use Node.js standard-library modules.
- Existing `risk`, `tests`, `documentation`, and `ci` output fields remain so
  current callers can migrate additively. The policy and plan schema advance to
  version 2 because level and receipt semantics are new contracts.
- This work changes verification policy and therefore requires L4 acceptance
  for its own delivery. It does not authorize publication or remote mutation.

## L0-L4 model

| Level | Meaning | Typical evidence |
| --- | --- | --- |
| L0 | Static validity | syntax, JSON/config parsing, formatting/lint, documentation and generated-index consistency |
| L1 | Local unit closure | tests directly mapped to the changed component |
| L2 | Dependency closure | structural rules plus direct upstream/downstream contract tests |
| L3 | Critical-path smoke | the shortest API/runtime/user path that crosses the changed boundary |
| L4 | Full acceptance | full relevant suite/build/delivery and required platform or CI gates |

The selected `requiredLevel` is the highest minimum level contributed by any
matched rule, validation item, coupling escalation, runtime signal, or fallback.
Levels are cumulative as an acceptance obligation: a plan at L3 must preserve
the applicable L0-L3 validations selected by its rules. A higher level does not
silently invent unrelated platform gates; for example, a non-desktop L4 change
does not claim native Windows desktop acceptance unless a desktop rule matched.

## Policy schema

The v2 policy adds:

- `levelOrder`: exactly `L0` through `L4`;
- `escalation`: the high-coupling module threshold and target level;
- catalog entries shaped as `{ "level": "Lx", "value": "command-or-gate" }`;
- rule fields `minimumLevel`, `impact`, and `coupling`;
- the same fields on the fail-closed fallback.

`impact` is a non-empty list of stable module or boundary IDs. `coupling` is
`low` or `high`. When the complete changed set reaches the configured number of
distinct high-coupling impacts, the planner raises the plan to at least L3 and
records `multiple_high_coupling_modules`.

High-risk rules force L4 for public contracts, schema, configuration owned by
the verification/CI system, core abstractions, shared utilities, data models or
database migrations, dependencies, CI, security, desktop, and release paths.
Known parser, workflow, and agent-orchestration paths require at least L3.
Unknown paths remain L4 with `unknown_path` and never inherit desktop gates.

## Change to impact to validation flow

For every invocation the planner:

1. validates and deduplicates the complete changed-file list;
2. maps every path to all matching rules;
3. emits stable impact records connecting path, rule, reason, module IDs,
   coupling, and minimum level;
4. merges validations in first-seen order and groups them by L0-L4;
5. computes the highest required level and every escalation reason;
6. emits a change summary, uncovered-risk list, and receipt template.

The plan contains both a flat compatibility projection (`tests`,
`documentation`, `ci`) and `validationsByLevel`. The latter is authoritative for
incremental execution. A validation appears once even when several rules select
it.

## Runtime escalation

The planner accepts repeatable `--signal validation_failure` and
`--signal unexpected_behavior`. Each unique signal raises the computed level by
one step, capped at L4, and is recorded in `escalations`. This supports the loop:

1. execute the current minimal plan;
2. if a check fails or behavior is unexpected, rerun planning with the signal;
3. execute the expanded plan;
4. record both attempts in the final receipt.

The receipt validator independently enforces this rule. A receipt containing a
failed or unexpected execution is invalid unless `escalation.required` is true
and `targetLevel` is at least the next level after the plan's required level.
This prevents a caller from reporting a local failure as a completed low-level
acceptance.

## Receipt contract

A receipt is JSON with these required facts:

- change summary and the exact changed-file set;
- planned and actual acceptance levels;
- impact assessment copied from the plan;
- every actually executed validation with ID, level, status, duration, and
  evidence reference;
- every selected external CI/platform/document gate with an explicit observed,
  not-run, or not-required state;
- overall result;
- uncovered risks;
- escalation decision, target, and reasons.

The validator receives both plan and receipt paths. It rejects symbolic links,
unsafe paths, schema drift, changed-file mismatches, missing required
validations, unknown validation IDs, an actual level below the plan, false
success when a check failed, and missing escalation after failure or unexpected
behavior. Success writes one stable JSON verdict to stdout; failures write one
stable error object to stderr and exit non-zero.

For `full-delivery`, an external gate cannot be `not_required`. A `not_run`
external gate forces a `blocked` receipt and a named uncovered risk, preserving
the boundary between local evidence and CI/platform evidence.

The receipt may contain extra executed checks only when their IDs exist in the
plan. This keeps evidence review bounded and prevents an unrelated full-suite
run from disguising a missing targeted check.

## Representative closures

1. Small UI renderer change: `app/research_web/ui/frameworks/goldar.mjs`
   selects static policy/config checks and the framework UI unit test, with no
   desktop gates and no full suite.
2. Cross-module framework change: backend plus UI framework paths merge unit,
   architecture/dependency, and the targeted framework API smoke path; distinct
   high-coupling impacts raise the closure to at least L3.
3. Core/high-risk change: verification policy, public contract, schema,
   dependency, CI, core/shared, database, security, desktop, release, or unknown
   paths select L4. Desktop checks appear only for desktop-owned paths.

These are contract scenarios and must also be executed against the real v2
planner during delivery. Their generated plans and valid receipts are preserved
in `.ai/reports/incremental-validation-v2-PROGRESS.md` with real command output,
not merely described as expected behavior.

## Error handling and safety

- Strict exact-key parsing remains fail closed.
- Repository paths remain relative POSIX paths and reject traversal,
  backslashes, control characters, and symbolic-link components.
- Commands in policy or receipt data are never executed.
- Planner and receipt errors expose stable codes without stack traces or host
  paths.
- No failure, skipped test, uncovered risk, or required escalation may be
  converted into a passing receipt.
- Existing main-worktree changes remain untouched; implementation and evidence
  are confined to the isolated v2 worktree.

## Documentation and reusable workflow

- `docs/AGENT_WORKFLOW.md` defines when Codex plans, executes, escalates, and
  records evidence.
- `docs/DEVELOPMENT_MAP.md` maps policy, planner, validator, tests, and reports.
- `.agents/skills/incremental-validation/` provides a project-local skill and
  README that invoke the scripts without duplicating the policy table.
- `.claude/commands/verify-task.md` remains a thin compatibility entrypoint and
  documents the L0-L4/receipt flow.

## Acceptance

The design is complete only when tests prove: schema strictness; all five
levels; minimal small-change closure; cross-module merging and coupling
escalation; every named high-risk trigger; failure/unexpected escalation;
read-only behavior; receipt completeness; and three real representative plans
whose evidence shows that the small change omits L4 while the high-risk change
cannot fall below L4.
