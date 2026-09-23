# macOS-only Research Web verification evidence

## Scope and boundary

- Windows automatic validation is paused; no Windows result is claimed for this policy-change delivery.
- Local macOS validation passed before publication.
- GitHub macOS Bootstrap remains a required external gate and is still pending until publish.
- Desktop Windows rules were not changed.

The planner changed set is fixed to the 21 files in
`2026-09-23-mac-only-web-verification-plan.json`. The two carried startup-preflight evidence files are
included because they differ from base `b36fb0ee6be4cd13b19b89311adfed82bc129f9d`. The four documentation
governance files are synchronized because Project Constraints requires the current documentation authority
to describe the same macOS-auto/Windows-manual boundary as the workflows and policy.

## Local macOS evidence

Every local validation emitted by the final L4 plan ran in this worktree with the repository's existing
environment. Python tests used `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python`; no dependency
was installed.

| Plan ID | Level | Observed result | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | L0 | passed; 498 files, 0 violations | 0.18 s |
| `python-file-index` | L0 | passed; generated index verified | 1.15 s |
| `verification-policy-contracts` | L1 | passed; 29/29 | 1.91 s |
| `verification-receipt-contracts` | L1 | passed; 16/16 | 1.66 s |
| `incremental-validation-skill-contracts` | L1 | passed; 5/5 | 0.09 s |
| `research-web-local-integrations` | L1 | passed; 45 passed, 1 skipped | 19.21 s |
| `research-web-architecture` | L1 | passed; 62/62 | 2.98 s |
| `project-constraints-local` | L2 | passed; all 21 files checked, 0 violations | 0.16 s |
| `research-web-critical-smoke` | L3 | passed; 19/19 | 1.50 s |
| `research-web-verification-full` | L4 | passed; 77/77 | 3.09 s |

The local test commands therefore observed 253 passing tests and one declared platform skip. Documentation
governance, the Python index, and the complete 21-file Project Constraints check also passed. Receipt validation
returned `valid: true`, `result: blocked`, L4/L4, and 10 executed local validations in 0.04 s. Both
`git diff --check` and `git diff --check b36fb0ee6be4cd13b19b89311adfed82bc129f9d..HEAD` passed.

## Pre-publication external gates

No external gate ran from this local Task 5 closure:

- `project-constraints`: `not_run`; it requires the published GitHub workflow.
- `research-web-checks`: `not_run`; it requires the published GitHub workflow.
- `research-web-bootstrap`: `not_run`; the required target is GitHub `macos-14`.

Accordingly the receipt result is honestly `blocked`, with one uncovered risk for each pending external gate.
Windows is not an external gate in this plan, was not run, and is not claimed. The retained Windows Web workflow
can only run after a user explicitly dispatches it; desktop Windows rules remain unchanged.

## Architecture review

The workflow routing and evidence policy changed, but the documentation information architecture, authority
topology, runtime/module boundaries, API relationships, and generated diagrams did not change.

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Workflow routing and evidence policy changed from automatic macOS and Windows Web verification to automatic macOS plus explicit manual Windows evidence, while documentation architecture, authority relationships, and diagrams remain unchanged.","diagrams":[]} -->
