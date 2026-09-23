# Research Web restart and refresh stability evidence

## Scope and truthful boundary

This Task 5 evidence covers the complete feature branch through Task 4 and documents three bounded changes:

```text
restart -> authenticated DSH session/list -> any running session blocks non-force restart
session catalog -> one session.list + all eligible parent-scoped subagent.list calls with concurrency <= 8; failures cancel and await the remaining fan-out before propagating
browser catalogs -> each catalog tracks its own pending count and generation -> per-resource settled render -> latest request wins; only runtime pending is projected as visible connecting, and only settled runtime failure is projected as offline
```

No production source or test is changed by this task. Framework, Tabbit, integrations, capabilities,
data-file, Automation, and information-architecture relationships remain unchanged. Local verification does
not claim browser acceptance, real lifecycle acceptance, publication, or remote CI; those are Task 6 items.

## Task 6: 陈旧运行会话恢复

Task 6 first measured the integration endpoint at **2.161 s**, which failed the `< 2.0 s` live latency hard
gate. That is a failed baseline, not post-fix evidence. The root cause was a second, serial recovery phase:
after the bounded parent/child state fan-out, stored `running` rows whose native parent and children were idle
called `detail()` one at a time to recover terminal status.

`e467f5634c49aefdc99e9907ebe654e70c344f53` moves that recovery behind the existing limit of 8, preserves
directory order, and on any `BaseException` (including caller cancellation) cancels and awaits unfinished
recovery tasks before re-raising. `84d764f63d15571814a6e6938f5c053343a9d232` narrows eligibility: only a
created stored-`running` row with an idle native parent and idle children enters recovery. `created=False`, a
native-running parent, and a child-running parent remain out of `detail()`; their existing summary/running
projection is retained. The 50-parent child fan-out remains capped at 8, and the recovery fan-out is capped at
the same 8. No fixed live latency, browser acceptance, or CI result is claimed here.

## Fix round 1 RED audit

Before editing, a bounded search across all 17 Task 5-owned paths found 10 Task 5-authored locations that
collapsed internal catalog request bookkeeping into a generalized visible `connecting` / `offline` claim.
The expected contract is narrower: every catalog independently owns a pending count and generation, renders
each resource as it settles, and lets the latest request win; only runtime pending reaches UI/Composer/submit as
visible `connecting`, and only a settled runtime failure reaches those surfaces as `offline`. Existing Tabbit
`browser_offline`, MCP stale/offline, delivery pending, and publication pending occurrences are separate
contracts and were not rewritten.

## Local validation evidence

The fixed-point plan covers 29 sorted paths, including the generated Python index and all three durable evidence
files. It selected `full-delivery` / L4, exactly 12 local validation IDs, and no unknown, unclassified, or
uncovered local risk. No dependency was installed. The durations below are observed command wall times; where
the test runner printed a distinct internal duration, that value is included in the result text.

| Plan ID | Level | Command | Observed result | Duration |
| --- | --- | --- | --- | ---: |
| `documentation-governance` | L0 | `node scripts/check_documentation_governance.mjs --project .` | passed; 501 files, 69 current, 0 violations | 0.160 s |
| `python-file-index` | L0 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check` | passed; generated index verified | 1.140 s |
| `verification-policy-contracts` | L1 | `node --test tests/javascript/verification_policy.test.mjs` | passed; 35/35 | 2.040 s |
| `verification-receipt-contracts` | L1 | `node --test tests/javascript/verification_receipt.test.mjs` | passed; 16/16 | 1.550 s |
| `incremental-validation-skill-contracts` | L1 | `node --test tests/javascript/incremental_validation_skill.test.mjs` | passed; 5/5 | 0.100 s |
| `research-web-architecture` | L1 | `node --test tests/javascript/research_web_architecture.test.mjs` | passed; 62/62 | 3.050 s |
| `research-web-api` | L1 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_api.py --confcutdir=tests/research_web -q` | passed; 30/30 in 179.26 s; one Starlette/AnyIO deprecation warning | 179.730 s |
| `research-web-service-manager` | L1 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_service_manager.py -q` | passed; 57/57 in 4.01 s; expected warning/error log-path assertions emitted | 5.280 s |
| `research-web-ui` | L1 | `node --test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs` | passed; 67/67 | 12.680 s |
| `project-constraints-local` | L2 | `node .agents/project-constraints.mjs --project . --changed-file <repeat for all 29 plan paths>` | passed; 29 files, 0 violations | 0.200 s |
| `research-web-critical-smoke` | L3 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_protocol.py` | passed; 19/19 in 3.47 s; pytest warned that `pyproject.toml` config was ignored in favor of `pytest.ini` | 4.710 s |
| `research-web-verification-full` | L4 | `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs` | passed; 80/80 | 2.930 s |

Fix round 1 reran the complete final 12-item local closure after narrowing the visibility language. Its recorded
wall-time total is 213.570 seconds. Every shell invocation also printed the pre-existing
login-shell warning `/Users/leon/.bash_profile: line 57: /Users/leon/.cargo/env: No such file or directory`; it
did not change any command exit status.

The first Python index check failed honestly with exit 1 after 1.115 seconds and reported the index stale.
`/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py` regenerated
only `docs/generated/py_file_index.md`, adding `_runtime_sessions` to the documented `WebServiceManager`
methods. The plan was regenerated to the 29-path fixed point, then documentation governance and the index check
were rerun and passed as recorded above. The initial stale-index failure is not represented as a passed check.

## Receipt validation

The receipt copies the final plan's exact change summary, changed paths, impact list, planned level, and actual
level. All 12 local validations are `passed`; all three external gates are `not_run`; the receipt result remains
`blocked` with one `external_gate_not_run:<id>` risk per gate.

`node scripts/validate_verification_receipt.mjs --project . --plan .ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json --receipt .ai/reports/2026-09-23-research-web-restart-refresh-stability-receipt.json`
exited 0 and returned `valid: true`, `result: blocked`, `plannedLevel: L4`, `actualLevel: L4`,
`executedCount: 12`, and `escalationRequired: false`.

## Task 6 final local verification at `84d764f63`

The fixed plan remains 29 paths, `full-delivery` / L4, 12 local validation IDs, and three external
gates. The final local run used the checkout's pre-existing `.venv` for pytest; no dependency was installed.
The shell's `python` (`/opt/homebrew/opt/python@3.12/libexec/bin/python`) first reported
`No module named pytest` in 0.040 s. That environment observation is not a code-test result, so the planned
Python checks were rerun with the existing checkout environment and their passed wall times below are the
receipt values.

| Plan ID | Result | Count / evidence | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | passed | 501 files, 69 current, 0 violations | 0.160 s |
| `python-file-index` | passed | `docs/generated/py_file_index.md` verified | 1.108 s |
| `verification-policy-contracts` | passed | 35/35 | 2.047 s |
| `verification-receipt-contracts` | passed | 16/16 | 1.586 s |
| `incremental-validation-skill-contracts` | passed | 5/5 | 0.119 s |
| `research-web-architecture` | passed | 62/62 | 3.132 s |
| `research-web-api` | passed | 33/33; one Starlette/AnyIO deprecation warning | 196.602 s |
| `research-web-service-manager` | passed | 57/57; expected test log assertions emitted | 1.885 s |
| `research-web-ui` | passed | 67/67 | 12.298 s |
| `project-constraints-local` | passed | all 29 fixed paths, 0 violations | 0.187 s |
| `research-web-critical-smoke` | passed | 19/19 | 1.498 s |
| `research-web-verification-full` | passed | 80/80 | 2.854 s |

The report and receipt change only evidence and documentation. After those writes, documentation governance,
the Python index check, project constraints over the same 29 paths, receipt validation, and `git diff --check`
must still pass before this documentation closeout can be committed.

## Final diff and ownership check

`git diff --check` exited 0. A separate exact-set check combined the Task 5 commit range from
`dc8c0167884ff09a4d1e3b87bee5a35683b3fd78`, the remaining working-tree diff, and untracked files: all 17
Task 5-owned paths were present, with zero missing and zero unexpected paths. No production source or test was
edited by Task 5.

## External gates

Task 5 intentionally does not publish or run remote gates. The final receipt therefore records Project
Constraints, Research Web Checks, and macOS Bootstrap (`macos-14` only) as `not_run`, with one uncovered risk
per gate, and remains `blocked` even when all local checks pass.

## Architecture review

The implementation changes existing restart authority, bounded catalog reads, and loading semantics without
adding a service, route, persistent store, Automation edge, navigation level, or diagram relationship.

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"Each catalog now owns an independent pending count and generation, renders resources as they settle, and lets the latest request win; only runtime pending or settled runtime failure is projected as visible connecting or offline, while UI modules, routes, navigation, and diagrams remain unchanged.","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Authenticated restart authority and bounded session/subagent catalog reads stay inside the existing service-manager, ResearchService, and DSHClient boundaries with no new API or runtime node.","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Catalog refresh and restart guards do not change Automation targets, schedules, Run persistence, delivery channels, or the existing capability-workspace relationship.","diagrams":[]} -->

## Residual risks

- The three required external gates have not run in Task 5.
- Real browser interaction and real restart/session lifecycle acceptance have not run in Task 5.
- Publication, remote CI inspection, and final delivery closeout belong to Task 6.
