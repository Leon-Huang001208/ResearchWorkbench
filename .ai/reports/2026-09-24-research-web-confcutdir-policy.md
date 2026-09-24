# Research Web focused pytest boundary evidence

## Scope and root cause

The repository root `tests/conftest.py` belongs to the maintained compatibility platform and imports its SQLAlchemy
repository layer. In the main checkout, web-dev settings load the local `.env` with override semantics, so a focused
Research Web test can accidentally require the user's PostgreSQL driver or database configuration before its own
test module is collected. Isolated worktrees and GitHub Research Web Checks do not carry that local `.env`, which
made the same command pass there and fail in the main checkout.

This change updates only verification routing. Every local Python catalog whose command begins with
`python -m pytest tests/research_web/` now appends `--confcutdir=tests/research_web`, matching the existing GitHub
Research Web Checks boundary. The root conftest, local `.env`, compatibility database tests, production runtime,
test membership, risk levels, and CI routing are unchanged.

## TDD and direct evidence

The new policy contract reads the tracked policy, requires exactly eight focused Research Web Python catalogs,
and requires every command to contain the bounded confcutdir. RED produced 35 passes and one expected failure at
`research-web-framework-collectors`, whose command still loaded the root conftest. After changing only the eight
catalog values and their test fixture mirrors, GREEN passed 36/36.

Before implementation, all seven referenced Python files (including the one selected test inside
`test_frameworks.py`) were collected together with the proposed confcutdir: 199 tests collected, with no missing
root fixture. After GREEN, the new installation and critical-smoke commands were run from the main checkout that
contains the user's local `.env`; installation passed 31/31 and protocol passed 19/19 without importing the root
database conftest.

## Incremental validation

The fixed changed set contains six paths: policy, policy contracts, Agent Workflow documentation, and three
evidence files. The project-local planner selected `full-delivery` / L4 with six local validation IDs and one
external gate, Project Constraints. Research Web Checks, macOS Bootstrap, Windows, desktop, Tauri, and sidecar
gates are not selected because no product/runtime/platform path changes.

Final local validation results are recorded in the receipt after running the complete planned closure. Until the
external Project Constraints run is observed, the receipt remains `blocked` with an explicit external-gate risk.

| Plan ID | Level | Result | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | L0 | passed; 503 files, 69 current, 0 violations | 0.147 s |
| `python-file-index` | L0 | passed; generated index verified | 0.909 s |
| `verification-policy-contracts` | L1 | passed; 36/36 | 1.592 s |
| `verification-receipt-contracts` | L1 | passed; 16/16 | 1.208 s |
| `incremental-validation-skill-contracts` | L1 | passed; 5/5 | 0.074 s |
| `research-web-verification-full` | L4 | passed; 80/80 | 2.437 s |

The focused policy RED is retained separately: 35 tests passed and the new catalog-isolation contract failed at
the first unisolated catalog. After the eight command-only changes, the same suite passed 36/36. The 199-test
collection probe and the main-checkout 31/31 plus 19/19 executions are supplementary runtime evidence, not extra
receipt IDs invented outside the planner.

## Architecture review

Only command isolation in the read-only verification policy changes; the Research Web product graph is unchanged.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Focused pytest commands stop at the Research Web test root; product APIs, runtime services, storage, and diagrams are unchanged.","diagrams":[]} -->

## Platform boundary

Windows automatic verification remains paused and is not claimed. The planner does not select macOS Bootstrap for
this policy-only change; the preceding installation delivery already proved the current product bootstrap on local
macOS and GitHub `macos-14`.
