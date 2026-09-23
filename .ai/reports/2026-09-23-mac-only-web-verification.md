# macOS-only Research Web verification evidence

## Scope and boundary

- Windows automatic validation is paused; no Windows result is claimed for this policy-change delivery.
- Local macOS validation passed before publication.
- The required GitHub external gates passed on the first published commit.
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
was blocked at this prepublication point until the three required remote gates ran; its final status is
`passed`, as documented in the first-publication evidence below.

Temporary raw outputs and exact command arguments existed through prepublication review under:

`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/p0-web-stability-worktrees/p0-web-stability-delivery-integration/.superpowers/sdd/2026-09-23-mac-only-web-verification/final-fix-feature-logs`

Required controller cleanup later deleted that ignored SDD workspace, so it is not a durable raw-log archive
and no stable raw archive is claimed. Durable evidence consists of the committed plan, receipt, and this report,
plus the immutable GitHub run links, IDs, attempts, job counts, and conclusions below. Before cleanup, each
validation had a `<Plan ID>.log`; `results.json` recorded commands and measured durations, and `exact-set.json`
recorded the deterministic 22-file comparison. Python pytest used the existing project Python;
local-integrations additionally used `--confcutdir=tests/research_web -q`. One existing Starlette/AnyIO
deprecation warning and the declared platform skip remain; no dependencies were installed.

## Final review remediation

The three focused `research-web-ci` paths now automatically trigger both Bootstrap and Research Web Checks
for PR and push. Three independent failing routing tests reproduced the finding before the workflow edits;
after the edits, all 11 Actions routing tests pass. Bootstrap still has exactly one `macos-14` job and Windows
Verify remains manual-only. The policy suite now checks each CI path independently and separately checks both
the local-integrations test path and source path as L1/local-only with exactly two focused tests and no external
gates. Task 5/6 initial-delivery commands enumerate all 22 files. The historical P0 receipt schema is unchanged.

## First-publication external gates

The conflict-free replacement integration commit
`810708c41854ef9f4b60170663a3f72f0b225400` was published directly to `origin/master` after its complete
22-file merged result passed locally in 35 measured seconds. All automatically created runs for that exact SHA
were inspected after completion:

| Gate | Run / attempt | Job evidence | Conclusion |
| --- | --- | --- | --- |
| `project-constraints` | [35859438620](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35859438620), attempt 1, push | job `check` (`107175730286`) | `success` |
| `research-web-checks` | [35859438637](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35859438637), attempt 1, push | job `checks` (`107175730559`) | `success` |
| `research-web-bootstrap` | [35859438469](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35859438469), attempt 1, push | exactly one job: `Clean Web install (macos-14)` (`107175730265`) | `success` |

The complete run listing for the commit contained exactly those three push runs. It contained no
`Research Web Windows Verify` run, no Windows job, and no rerun. Windows was not run and is not claimed as
verified. The retained Windows Web workflow remains manual-only; it was not dispatched. Desktop Windows rules
remain unchanged. With the three required external gates passed, the receipt result is `passed` and has no
uncovered external-gate risk.

## Architecture review

The workflow routing and evidence policy changed, but the documentation information architecture, authority
topology, runtime/module boundaries, API relationships, and generated diagrams did not change.

<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"Workflow routing and evidence policy changed from automatic macOS and Windows Web verification to automatic macOS plus explicit manual Windows evidence, while documentation architecture, authority relationships, and diagrams remain unchanged.","diagrams":[]} -->
