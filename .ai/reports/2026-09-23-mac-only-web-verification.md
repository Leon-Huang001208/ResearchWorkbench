# macOS-only Research Web verification evidence

## Scope and boundary

- Windows automatic validation is paused; no Windows result is claimed for this policy-change delivery.
- Local macOS validation passed before publication.
- GitHub macOS Bootstrap remains a required external gate and is still pending until publish.
- Desktop Windows rules were not changed.

The planner changed set is fixed to the 22 files in
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
| `documentation-governance` | L0 | passed; 498 files, 0 violations | 0.146 s |
| `python-file-index` | L0 | passed; generated index verified | 1.078 s |
| `verification-policy-contracts` | L1 | passed; 33/33 | 1.838 s |
| `verification-receipt-contracts` | L1 | passed; 16/16 | 1.466 s |
| `incremental-validation-skill-contracts` | L1 | passed; 5/5 | 0.087 s |
| `research-web-local-integrations` | L1 | passed; 45 passed, 1 platform skip | 18.344 s |
| `research-web-architecture` | L1 | passed; 62/62 | 2.81 s |
| `project-constraints-local` | L2 | passed; all 22 files checked, 0 violations | 0.149 s |
| `research-web-critical-smoke` | L3 | passed; 19/19 | 1.463 s |
| `research-web-verification-full` | L4 | passed; 80/80 | 2.779 s |

The local test commands observed 260 passing tests and one declared platform skip (the separate architecture
validation also appears in the L4 suite). The exact 22-file plan matches the diff from base byte-for-byte as a
sorted path set; regeneration is deterministic. Complete local closure took 31 measured seconds. Documentation
governance, the Python index, Project Constraints, and both working-tree/base diff checks passed. The receipt
remains blocked until the three required remote gates run.

Raw outputs and exact command arguments are preserved under:

`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability-worktrees/p0-web-stability-delivery-integration/.superpowers/sdd/2026-09-23-mac-only-web-verification/final-fix-feature-logs`

Each validation has a `<Plan ID>.log`; `results.json` contains commands and measured durations, and
`exact-set.json` records the deterministic 22-file comparison. Python pytest used the existing project Python;
local-integrations additionally used `--confcutdir=tests/research_web -q`. One existing Starlette/AnyIO
deprecation warning and the declared platform skip remain; no dependencies were installed.

## Final review remediation

The three focused `research-web-ci` paths now automatically trigger both Bootstrap and Research Web Checks
for PR and push. Three independent failing routing tests reproduced the finding before the workflow edits;
after the edits, all 11 Actions routing tests pass. Bootstrap still has exactly one `macos-14` job and Windows
Verify remains manual-only. The policy suite now checks each CI path independently and separately checks both
the local-integrations test path and source path as L1/local-only with exactly two focused tests and no external
gates. Task 5/6 initial-delivery commands enumerate all 22 files. The historical P0 receipt schema is unchanged.

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
