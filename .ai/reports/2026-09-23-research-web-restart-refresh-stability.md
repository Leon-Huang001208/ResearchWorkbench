# Research Web restart and refresh stability evidence

## Scope and truthful boundary

This Task 5 evidence covers the complete feature branch through Task 4 and documents three bounded changes:

```text
restart -> authenticated DSH session/list -> any running session blocks non-force restart
session catalog -> one session.list + all eligible parent-scoped subagent.list calls with concurrency <= 8; failures cancel and await the remaining fan-out before propagating
browser catalog -> pending/connecting -> per-resource settled render -> offline only after real failure
```

No production source or test is changed by this task. Framework, Tabbit, integrations, capabilities,
data-file, Automation, and information-architecture relationships remain unchanged. Local verification does
not claim browser acceptance, real lifecycle acceptance, publication, or remote CI; those are Task 6 items.

## Local validation evidence

The fixed-point plan covers 29 sorted paths, including the generated Python index and all three durable evidence
files. It selected `full-delivery` / L4, exactly 12 local validation IDs, and no unknown, unclassified, or
uncovered local risk. No dependency was installed. The durations below are observed command wall times; where
the test runner printed a distinct internal duration, that value is included in the result text.

| Plan ID | Level | Command | Observed result | Duration |
| --- | --- | --- | --- | ---: |
| `documentation-governance` | L0 | `node scripts/check_documentation_governance.mjs --project .` | passed; 501 files, 69 current, 0 violations | 0.129 s |
| `python-file-index` | L0 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check` | passed; generated index verified | 1.102 s |
| `verification-policy-contracts` | L1 | `node --test tests/javascript/verification_policy.test.mjs` | passed; 35/35 | 1.995 s |
| `verification-receipt-contracts` | L1 | `node --test tests/javascript/verification_receipt.test.mjs` | passed; 16/16 | 1.457 s |
| `incremental-validation-skill-contracts` | L1 | `node --test tests/javascript/incremental_validation_skill.test.mjs` | passed; 5/5 | 0.044 s |
| `research-web-architecture` | L1 | `node --test tests/javascript/research_web_architecture.test.mjs` | passed; 62/62 | 2.849 s |
| `research-web-api` | L1 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_api.py --confcutdir=tests/research_web -q` | passed; 30/30 in 176.15 s; one Starlette/AnyIO deprecation warning | 177.720 s |
| `research-web-service-manager` | L1 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_service_manager.py -q` | passed; 57/57 in 3.88 s; expected warning/error log-path assertions emitted | 5.375 s |
| `research-web-ui` | L1 | `node --test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs` | passed; 67/67 | 11.889 s |
| `project-constraints-local` | L2 | `node .agents/project-constraints.mjs --project . --changed-file <repeat for all 29 plan paths>` | passed; 29 files, 0 violations | 0.151 s |
| `research-web-critical-smoke` | L3 | `/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_protocol.py` | passed; 19/19 in 0.28 s; pytest warned that `pyproject.toml` config was ignored in favor of `pytest.ini` | 1.408 s |
| `research-web-verification-full` | L4 | `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs` | passed; 80/80 | 2.935 s |

Final passing local closure duration was 207.054 seconds. Every shell invocation also printed the pre-existing
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

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"Per-resource catalog loading now preserves pending or connecting until settlement and shows offline only after a real failure; UI modules, routes, navigation, and diagram relationships are unchanged.","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Authenticated restart authority and bounded session/subagent catalog reads stay inside the existing service-manager, ResearchService, and DSHClient boundaries with no new API or runtime node.","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Catalog refresh and restart guards do not change Automation targets, schedules, Run persistence, delivery channels, or the existing capability-workspace relationship.","diagrams":[]} -->

## Residual risks

- The three required external gates have not run in Task 5.
- Real browser interaction and real restart/session lifecycle acceptance have not run in Task 5.
- Publication, remote CI inspection, and final delivery closeout belong to Task 6.
