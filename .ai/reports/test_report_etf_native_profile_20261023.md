# ETF Native fixed-profile preparation — 2026-10-23

## Scope and authorization

Host: macOS Mac mini. Task: isolated operator feature implementation and offline verification.
Worktree: `etf-native-profile-20261023`; base `6aec2c5bc46295fcd025d078fb41b2a0e4083fc5`.
Final identity update starts from parent-integrated HEAD
`37cd4fd54cb3467fbab2d2362e91799b7939bf27`, including master/PR198 merge.
Only source/test/document preparation is authorized. No apply, service switch, system/configuration
change, dependency installation, credential access, vendor/Office/model call, commit, push or PR
was performed by this subtask. Actual deployment requires separate explicit user authorization.

## Implementation

- Closed `reviewed-etf-weekly-v1` / `apply-etf-weekly` with fixed PREVIOUS
  `5343e18d9f203a87f2d958218e4288afa527711f` and PAYLOAD PR198 real merge
  `988046d23f9951f889a3b9d02e355ed59fd6aa65`.
- Parent verified all four registered resident identities remain `5343e18d`, Native project
  `/Users/leon/.local/share/research-workbench/releases/d744029a5` still lacks
  `weeklyExcelProvider`, and no transaction marker exists. This subtask did not query services.
  Fixed pins do not authorize deployment; recheck the registered version before switching.
- Reuses version4 journals, maintenance locks, BirthFence, Native/Host/private-pool activity,
  full business-index preservation and original forward/recovery phases.
- Explicit safe 64MiB business reader, fixed v6 full-log CI reader hash and market inflight gate.
  Metadata limits, all historical profiles, controller/evidence bytes and automatic policy remain.
- Installation manifest preserves the previous lock hash; no dependency-install exception.
- Existing profile matrix now includes ETF: real temporary Git scope/mode/ancestry checks,
  all-account index preservation, interrupted phases, rollback and completion-failure boundaries.
  New tests cover identity/CLI, explicit Host idle, Native/pool busy or unknown, and manifest lock.

## Historical evidence before final pins

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

Historical SHA256 identities (earlier uncommitted bytes; not the final pins):

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

At reconciliation time ETF PREVIOUS/PAYLOAD remained provisional and were not
deployment-qualified. The final identity update below supersedes those old pins.
The old 1531/1058 test evidence and prior file hashes above belong to the earlier bytes
and do not certify this merge reconciliation or the final identity update.

Actual reconciliation checks: AST parse passed for source and tests; all 45 master
source function/class names and 108 master test function/class names remain present
(merged tests have 113 names); no conflict markers remain in the four files;
Black check passed for both Python files; `git diff --check` passed. At that point full
final tests, static checks, review and final hashes remained pending the final pins;
the completed final-pin offline checks and remaining external gates are recorded below.
No Git staging/commit, network, model/vendor/Office call, dependency installation,
service mutation or deployment was performed by this reconciliation subtask.

At merged provisional source commit `b66ddf04c`, the complete operator-module offline
regression passed: **1270 passed, 1 existing deprecation warning, 77.37s**;
`logs/etf-native/merged-provisional-profile-tests.log`. Ruff, Black check, isort check
and scoped mypy (`--follow-imports=skip`) also passed;
`logs/etf-native/merged-provisional-static-checks.log`. The module test command is
the previously recorded approved interpreter/PYTHONPATH invocation restricted to
`tests/research_web/test_model_provider_upgrade.py`; no dependency was installed.
These results cover the reconciled v7/terminal/ETF matrices with provisional ETF pins
only. They do not certify the final pins or replace the required final regression.

## Remaining acceptance gates

Independent operator review, complete changed-set Router/integrity checks,
Project Constraints, Research Web Checks and same-candidate macOS bootstrap remain required.
No CI/network request or deployment was executed here. Native Windows/Linux and product Docker
acceptance remain NOT_RUN for this subtask; other-platform work belongs to its device task.
Actual resident/primary-admin binding, authenticated page behavior, real Wind/EDB data, final report
quality and formal report acceptance are not certified by these offline checks.

## Final fixed identities and acceptance boundary

The parent confirmed PR198 real merge
`988046d23f9951f889a3b9d02e355ed59fd6aa65`, with reviewed head `61f7d1a6d` passing
Project Constraints run `39941890854`, Research Web Checks run `39941890981`
(4488 passed, 70 skipped), and Mac bootstrap run `39942144297` (actual checkout `61f7d1a6d`).
These are parent-supplied product receipts, not new network observations by this subtask,
and do not certify the final operator candidate.

Only ETF PREVIOUS/PAYLOAD changed; all historical asset/market/model profiles, controller,
CI reader, metadata limits, 64MiB business reader, and installation lock contract remain.
Identity regressions now reject old `25b399a4`, old `0e0022ac`, and real PAYLOAD `988046d2`
as journal PREVIOUS values. The exact previous is `5343e18d9f203a87f2d958218e4288afa527711f`.
The schedule remains disabled; real data, formal report quality, authenticated UI,
resident binding/preservation and any eventual deployment require their own evidence.

Final-pin offline verification completed on these uncommitted Python bytes:

- Five-file target suite, including the full operator module: **1745 passed,
  1 existing Starlette/AnyIO deprecation warning, 360.53s**;
  `logs/etf-native/final-pins-target-tests.log`.
- Ruff, Black check, isort check and scoped mypy (`--follow-imports=skip`): PASS;
  `logs/etf-native/final-pins-static-checks.log`.
- AST constant-isolation audit: only `ETF_WEEKLY_PREVIOUS` and `ETF_WEEKLY_PAYLOAD`
  differ from the integrated starting HEAD; `git diff --check`: PASS.
- Operator SHA256: `57d7b8f4b345c7dafd635ddaea91c341137387597c8a5ebb868f8ebe2cd12698`.
- Test SHA256: `b3322cbb18e0690139b14975dfea3eac221dd2d81889a96e4635781c388acbb6`.
- Unchanged CI reader SHA256:
  `5c3077b7fac26f6836384f678514136802bcf2ed03a0a589aaac10e80111eebb`.
- Unchanged web.lock SHA256:
  `7c631d4fa5354170c622225be129a09f7f5890457aa0521bd5f46cecb6bb7102`.

The final suite used the same approved interpreter/PYTHONPATH and five test paths as
the historical command above, through a Python `pytest.main` runner. Before importing
product code, the runner inserted a local fake `xlwings` module into `sys.modules`:
empty engines/apps, no active app, and `App`/`Book` raising
`offline_test_office_access_forbidden`. No real Office bridge was imported. This is
an offline safety fixture, not Office readiness or vendor acceptance evidence.
The parent owns Git staging/managed delivery, Router/integrity checks, review and CI.
No service/apply, dependency installation, credential/model/vendor call or Git mutation
was performed by this final-pin subtask. Deployment remains separately unauthorized.
