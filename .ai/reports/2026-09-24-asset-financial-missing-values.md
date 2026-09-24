# Asset financial missing-value evidence

## Scope and live reproduction

On current `master`, the real `#/workbench/assets` page loaded the latest 600519 observation and rendered AKShare
financial cells as the literal text `false`, for example `净利润同比增长率=false` and `扣非净利润=false`.
The corresponding dataset rows API confirmed that the immutable historical snapshot itself contains boolean
`false` values in those financial metric columns. This is a missing-value sentinel from the AKShare financial
abstract, not a financial reading.

The repair is deliberately capability-specific. New AKShare `financials` rows map boolean sentinel values to
JSON `null` at the Provider normalization boundary. Generic AKShare normalization remains unchanged, so a real
boolean supplied by another capability remains a boolean. The asset renderer additionally treats booleans as
missing only inside the financial block, allowing already-persisted immutable snapshots to display `—` without
rewriting historical data.

## TDD and browser evidence

Two tests were added before production edits. RED observed 9/10 JavaScript tests with the financial cell still
rendered as `<td>false</td>`, and the focused Python test failed because both `False` and `True` remained in the
normalized financial row. After the two narrow implementation changes, GREEN passed 10/10 JavaScript tests and
the focused Python test passed 1/1. The same JavaScript test proves a boolean in the non-financial activity block
continues to render as `false`; the Python test proves generic Provider normalization still preserves `False`.

The already-running local Research Web was reloaded without creating a new query. Its existing 103-row AKShare
financial snapshot then rendered all affected cells as `—` while preserving real values such as `1.47亿` and
`46.84%`. This verifies backward-compatible presentation for immutable historical snapshots. A new-Provider
normalization path is covered by the Python regression; no external data request is required for that contract.

## Incremental validation

The complete 14-path set includes Provider/UI code, focused Python/JavaScript tests, all mapped UI/DataHub
documents, README review, and plan/receipt/report evidence. The planner failed closed to L4 because
`tests/research_web/test_datahub_catalog.py` currently falls through to `unknown_path`; no gate is bypassed or
downgraded. This is a verification-policy calibration candidate for the next task, not a reason to game the test
location.

The complete escalated local closure passed:

| Plan ID | Level | Result | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | L0 | passed; 521 files, 69 current, 0 violations | 0.13 s |
| `python-file-index` | L0 | passed; generated index verified | 1.01 s |
| `research-web-architecture` | L1 | passed; 62/62 | 2.35 s |
| `research-web-frameworks-ui` | L1 | passed; 12/12 | 0.13 s |
| `project-constraints-local` | L2 | passed; 15 paths, 0 violations | 0.15 s |
| `research-web-frameworks-python` | L2 | passed; 9/9 | 25.31 s |
| `research-web-framework-smoke` | L3 | passed; 1/1 | 6.05 s |
| `research-web-verification-full` | L4 | passed; 80/80 | 2.38 s |

Supplemental direct coverage also passed: `research_web_workbench.test.mjs` 10/10 in 0.10 s and the full
`test_datahub_catalog.py` 27/27. Targeted Ruff, Black check, and isort check also passed after Black mechanically
formatted the new Python test. The first L0 attempt found the generated Python index stale and the
first Project Constraints attempt found the missing `workbench` architecture marker; both failures were kept,
corrected, and replanned with `validation_failure`. The first L4 combination was polluted by the unrelated
untracked `.venv.broken-20260911/`; the exact directory was excluded only for the verification process and the
same 80-test command then passed.

## Publication and external evidence

Integration commit `3c5115e69776e1442467f871d36d90803d3bb91c` was published to remote `master`. The selected
[Project Constraints run 35952862863](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35952862863)
and [Research Web Checks run 35952862823](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35952862823)
both completed with `success`.

The user's standing Mac rule was satisfied by manually dispatching the Mac-only
[Research Web Bootstrap run 35952879895](https://github.com/Leon-Huang001208/ResearchWorkbench/actions/runs/35952879895)
against the same commit. Its single `Clean Web install (macos-14)` job completed install, environment checks,
service start, Doctor, connection API smoke, stop, and evidence upload with `success`. The workflow containing a
Windows matrix was not dispatched. Windows, desktop, Tauri, sidecar, and installer-release behavior remain
unrun and unclaimed.

## Architecture review

The DataHub topology, Broker routing, immutable snapshot layout, service graph, API routes, and UI navigation are
unchanged. The Provider transformation becomes more truthful for one declared capability, and the existing asset
table gains a backward-compatible display guard.

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"AKShare financial missing-value normalization changes one existing Provider result transform without adding routes, storage, services, Broker edges, or snapshot topology.","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"The asset workspace keeps its existing component and DOM contracts while formatting legacy financial boolean sentinels as missing cells.","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"Asset observation continues to use the existing Workbench route, dataset rows API, immutable snapshots, and handoff path; only financial cell normalization and display change.","diagrams":[]} -->
