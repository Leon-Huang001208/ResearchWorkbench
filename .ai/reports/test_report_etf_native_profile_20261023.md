# ETF Native fixed-profile preparation — 2026-10-23

## Scope and authorization

Host: macOS Mac mini. Task: isolated operator feature implementation and offline verification.
Worktree: `etf-native-profile-20261023`; base `6aec2c5bc46295fcd025d078fb41b2a0e4083fc5`.
Only source/test/document preparation is authorized. No apply, service switch, system/configuration
change, dependency installation, credential access, vendor/Office/model call, commit, push or PR
was performed by this subtask. Actual deployment requires separate explicit user authorization.

## Implementation

- Closed `reviewed-etf-weekly-v1` / `apply-etf-weekly` with fixed PREVIOUS
  `0e0022ac792eba88fba0f233524f5c8d66024569`.
- Provisional PAYLOAD `25b399a42d691766d41bcafce5adbdc3b8cc3d74`: root must replace with the
  accepted PR198 product after merge, update identity assertions/docs and re-review. This is
  not a deployment-qualified final pin. Recheck the registered previous version before switching.
- Reuses version4 journals, maintenance locks, BirthFence, Native/Host/private-pool activity,
  full business-index preservation and original forward/recovery phases.
- Explicit safe 64MiB business reader, fixed v6 full-log CI reader hash and market inflight gate.
  Metadata limits, all historical profiles, controller/evidence bytes and automatic policy remain.
- Installation manifest preserves the previous lock hash; no dependency-install exception.
- Existing profile matrix now includes ETF: real temporary Git scope/mode/ancestry checks,
  all-account index preservation, interrupted phases, rollback and completion-failure boundaries.
  New tests cover identity/CLI, explicit Host idle, Native/pool busy or unknown, and manifest lock.

## Actual evidence

- Managed Git safety check: fsck PASS, no native locks; shared common directory verified.
- TDD red: 2 selected tests failed because profile/CLI did not exist;
  `logs/etf-native/profile-red.log`.
- Focused green: 11 passed; `logs/etf-native/profile-green.log`.
- Five-file target suite: 1531 passed, one existing Starlette/AnyIO deprecation warning,
  394.20s; `logs/etf-native/target-tests.log`.
- Final-byte operator-module rerun after test formatting/equivalent fixture cleanup:
  1058 passed, the same existing deprecation warning, 71.29s;
  `logs/etf-native/final-profile-tests.log`.
- Ruff, Black check, isort check: PASS; `logs/etf-native/static-checks.log`.
- Scoped mypy with `--follow-imports=skip`: PASS; `logs/etf-native/mypy.log`.
- `git diff --check`: PASS.

Final SHA256 identities (uncommitted bytes):

- Operator: `0c4f6d28b8b146ba1d0ab0e8ecd325abf35ae2116c3ce966e82e5c7180b95297`.
- Tests: `296a9fe9dc32a8c2fa9acd183df81fc018dbc9fdb834c752fce6adf596986fc9`.
- Unchanged CI reader: `5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb`.

Tests use the existing task-approved test libraries via PYTHONPATH and the original project
runtime interpreter; `--confcutdir=tests/research_web` avoids unrelated root fixtures. No packages
were installed. Test-created Git repos, SQLite fixtures and simulated service operations are
temporary local fixtures, not production state or service changes.

Executed suite command (from this worktree):

```bash
PYTHONPATH=.:/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/etf-excel-first-20261023/.venv/lib/python3.12/site-packages \
RESEARCH_DISABLE_LOCAL_EMBEDDINGS=1 \
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest \
  --confcutdir=tests/research_web \
  tests/research_web/test_model_provider_upgrade.py \
  tests/research_web/test_gateway_upgrade.py tests/research_web/test_resident.py \
  tests/research_web/test_multiuser_resident.py tests/research_web/test_api.py -q
```

## Merge-conflict reconciliation against master 5343e18d (2026-10-23)

The four conflicted files were reconciled while retaining every master asset-v7 and
market-terminal profile, fixed identity, CLI branch and existing test. The ETF additions
were layered on those branches: business-index reader membership, historical-profile and
recovery matrices, complete CI reader selection, and the explicit market inflight gate.
The master test fixture's malformed/unknown evidence-hash mutations remain in place;
ETF selects the v6 evidence constant without bypassing those adversarial checks.

Current ETF PREVIOUS/PAYLOAD remain provisional and are not deployment-qualified.
The parent task reports the registered resident baseline as `5343e18d`; the parent must
provide the actual accepted PR198 merge SHA before the single final identity update.
The old 1531/1058 test evidence and prior file hashes above belong to the earlier bytes
and do not certify this merge reconciliation or the final identity update.

Actual reconciliation checks: AST parse passed for source and tests; all 45 master
source function/class names and 108 master test function/class names remain present
(merged tests have 113 names); no conflict markers remain in the four files;
Black check passed for both Python files; `git diff --check` passed. Full final tests,
static checks, independent review and final source hashes remain pending the final pins.
No Git staging/commit, network, model/vendor/Office call, dependency installation,
service mutation or deployment was performed by this reconciliation subtask.

## Remaining acceptance gates

Final product pin and independent review, complete changed-set Router/integrity checks,
Project Constraints, Research Web Checks and same-candidate macOS bootstrap remain required.
No CI/network request or deployment was executed here. Native Windows/Linux and product Docker
acceptance remain NOT_RUN for this subtask; other-platform work belongs to its device task.
Actual resident/primary-admin binding, authenticated page behavior, real Wind/EDB data, final report
quality and formal report acceptance are not certified by these offline checks.
