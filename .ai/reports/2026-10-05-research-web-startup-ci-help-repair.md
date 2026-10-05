# Research Web bootstrap help CI repair

## Scope and failure evidence

PR #75 was merged as `4048c35e5e2d976d8abc0608f79a11de2d8901f4` before its checks completed. The `master` Research Web Checks run `37262750756` failed in `Run Research Web Python contracts`: 76 passed, 2 failed. Both failures were `tests/research_web/test_cli_lazy.py` invoking `./rwb --help` from the repository with a clean test-only `.venv`; the launcher returned `python_environment_incomplete` and exit 1. The independent `master` macOS clean Bootstrap run `37262750716` passed. Windows Web Verify was not run by user instruction.

The launcher correctly routes an unowned or incomplete environment to the standard-library `web_bootstrap` module. That module's exact allowlist admitted `web status` and `web doctor`, but rejected `--help`. This is a help-path contract omission, not evidence that uninstalled `start` should be allowed.

## Minimal repair and RED/GREEN

Two new tests first failed against the merged source: direct bootstrap `--help` returned 1 instead of 0, and a real copied POSIX launcher in a checkout without `.venv` returned `python_environment_missing`. The targeted RED command was `python -m pytest tests/research_web/test_web_bootstrap.py --confcutdir=tests/research_web -q -k 'bootstrap_help_requires_no_installation_or_service_probe or posix_launcher_help_works_without_an_installed_environment' --disable-warnings --maxfail=2`, with 2 expected failures. The launcher test now also covers a present but incomplete `.venv`, which matches the CI runner's test environment.

The bootstrap now returns static, dependency-free help for the exact top-level `--help` command before any installation or service probe. The rejection path for `web start/restart/stop` and unknown arguments is unchanged. The targeted GREEN bootstrap/rejection selection passed 10 tests; the final help-specific selection passed 3 cases; `tests/research_web/test_cli_lazy.py` passed 6 tests. No new dependency or secret handling was added. `docs/research-web-installation.md` records that help remains available before installation. The root README remains unchanged because the current-product entry and install commands did not change.

## Verification and delivery state

The complete fourteen-file changed set, including this report, its plan/receipt and seven module-boundary receipts required by Project Constraints, routes to L4 / `full-delivery` with `unknown_impact_boundary`; the local policy closure is documentation governance, Python file index and the four-file JavaScript verification suite. The module notes affirm that static bootstrap help does not change HTTP routes, DSH sessions, Gold/Dollar, integration state, security authority or Tabbit. `readme-review.json` records why the root README remains unchanged. Actual results after the fix:

| Check | Command | Result |
| --- | --- | --- |
| Documentation governance | `node scripts/check_documentation_governance.mjs --project .` | exit 0; 514 files, 73 current, 0 violations |
| Python index | `python scripts/generate_py_file_index.py --check` | exit 0; index verified |
| L4 architecture/governance | `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs tests/javascript/repository_cross_platform_contract.test.mjs` | exit 0; 81 passed |
| Exact Linux CI Python catalog | `python -m pytest tests/research_web/test_protocol.py tests/research_web/test_integration_coordinator.py tests/research_web/test_documentation.py tests/research_web/test_doc_sync.py tests/research_web/test_cli_lazy.py --confcutdir=tests/research_web -q --disable-warnings` | exit 0; 78 passed, 1 warning |
| Bootstrap/contract/installation | `python -m pytest tests/research_web/test_web_bootstrap.py tests/research_web/test_web_contract.py tests/research_web/test_setup_web.py --confcutdir=tests/research_web -q --disable-warnings` | exit 0; 249 passed after final test change |
| Project Constraints | `node .agents/project-constraints.mjs --project . --changed-file <all 14 changed paths>` | exit 0; 0 violations after documentation receipts |
| Python style | `python -m ruff check research_workbench_entrypoint/web_bootstrap.py tests/research_web/test_web_bootstrap.py`; corresponding `black --check` and `isort --check-only` | Ruff and Black exit 0 after replacing a static string join; isort exit 0 before the final constant-only edit |

The Web contract suite requires local loopback sockets; its first restricted-sandbox attempt had 5 failures and 2 errors caused by denied socket access. The same complete command passed 249/249 in the normal macOS permission boundary. This is an environment limitation, not hidden passing evidence. The first Project Constraints run rejected missing README and module-document review receipts; the fourteen-path rerun passed with 0 violations. Documentation governance, Python index, L4 JavaScript and diff checks also passed after those receipts. The schema-3 plan and schema-2 receipt validator returned `valid=true`, `result=BLOCKED`, `mergeReady=false`: all three selected local checks passed, while Project Constraints is `NOT_RUN` on this repair revision. No new push, PR, workflow rerun, Windows run or merge has been executed for this repair branch. The existing macOS Bootstrap success belongs to merged commit `4048c35e5` and cannot certify the new repair revision. On the next PR, Research Web Checks and macOS Bootstrap must run even though the project planner currently lists only Project Constraints for this unknown path.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Only the existing standard-library fallback help branch changes; service topology, routes, and dependencies are unchanged.","diagrams":[]} -->
