# Research Web status import and owned-environment recovery

## Scope and reproduction

The P0 audit found that the first `./rwb web status` invocation could take about 30 seconds even when both
managed services were stopped. The interrupted stack was reading capability packages through this eager chain:

```text
service_manager -> launch_runtime -> capabilities.catalog -> capabilities.packages
```

The status path does not prepare DSH, enumerate capabilities, or calculate the DSH build closure. It only needs
the pinned commit to derive the default runtime path and validate owned state. Warm measurements still showed
`service_manager` import at about 0.59 seconds, including about 0.28 seconds inside `launch_runtime` and its
FastAPI, MCP, DataHub, and capability dependencies.

## Repairs

- Move the shared pinned DSH commit to the lightweight `app.research_web` package root while preserving the
  existing `PINNED_COMMIT` exports in both consumers.
- Keep `calculate_build_closure()` at the existing service-manager seam, but import its implementation only when
  Doctor or installation diagnosis requests the DSH closure.
- Add a fresh-subprocess regression proving `service_manager` import does not load `launch_runtime`, capability
  packages, or MCP routes.
- Make explicit `--repair` test pip responsiveness for 15 seconds before reusing an installer-owned `.venv`.
  An unresponsive environment is preserved as `.venv.failed-<id>` and replaced through the existing staging
  transaction; unowned environments remain fail-closed.
- Before writing an `installed` manifest, use the new environment to import the checkout's
  `app.research_web.main:app` with a 300-second bound. This materializes cold FileProvider source reads during
  installation and returns `python_web_import_failed` instead of deferring the failure to `start`.

Service ownership, PID checks, ports, HTTP/DSH health, Doctor build attestation, public commands, and response
formats remain unchanged. The existing repair/install transaction is stronger before service lifecycle execution.

## TDD and observed behavior

- RED: importing `service_manager` loaded `app.research_web.launch_runtime`; GREEN keeps the entire runtime
  feature graph absent. Direct import improved from about 0.59 seconds to 0.18 seconds.
- Three stopped-service status calls completed in 0.34, 0.28, and 0.25 seconds with the existing output contract.
- The authorized first `setup-web --no-start` attempt reproduced the owned-environment gap: pip could not respond
  within the existing 120-second uninstall step and returned `python_root_uninstall_failed`, while Doctor still
  projected the old manifest as ready.
- RED proved `prepare_environment(repair=True)` reused an environment whose Python existed but whose pip was
  unresponsive. GREEN preserves that environment and creates a replacement; the full setup suite passed 32/32.
- The first Web start after dependency repair exposed a second gap: Runtime became healthy, but cold checkout
  imports exceeded the 35-second Web window. A diagnostic import advanced through real source modules and
  completed in 235.68 seconds, proving FileProvider cold reads rather than a deadlock.
- RED proved installation had no Web entrypoint readiness step. GREEN added the bounded source import and install
  orchestration contract; the full setup suite passed 33/33.
- Targeted Ruff, Black, isort, and `git diff --check` passed for both Python repair slices.

## Incremental validation

The complete set is routed to L4 because `service_manager.py` owns the service lifecycle and `setup_web.py` owns
the public clean-install contract. Earlier validation correctly found a stale Python index and missing
documentation/architecture receipts; both failures were preserved and replanned with `validation_failure`.
Live Mac acceptance then exposed the two installation failures above, so the final plan also records
`unexpected_behavior`.

The original 16-path status-only closure passed before live Mac acceptance. The final 19-path plan additionally
includes `scripts/setup_web.py`, its focused test, and the installation document. The expanded local closure
passed:

| Plan ID | Level | Result | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | L0 | passed; 509 files, 71 current, 0 violations | 0.15 s |
| `python-file-index` | L0 | passed; generated index verified | 1.04 s |
| `research-web-architecture` | L1 | passed; 62/62 | 2.66 s |
| `research-web-service-manager` | L1 | passed; 58/58 | 0.72 s |
| `research-web-installation` | L1 | passed; 33/33 | 3.81 s |
| `project-constraints-local` | L2 | passed; 19 paths, 0 violations | 0.13 s |
| `research-web-critical-smoke` | L3 | passed; 19/19 | 0.40 s |
| `research-web-verification-full` | L4 | passed; 80/80 | 2.62 s |

The receipt remains blocked until all required external gates pass.

## Local macOS installation and lifecycle

- `./setup-web.sh --repair --no-start` preserved the broken environment as
  `.venv.failed-99733fec859740e896fbf76d6c78f375`, recreated `.venv`, installed the hash-locked Web closure,
  verified CJPY 0.5.2 and the pinned DSH closure, and completed with `started:false`.
- Re-running the same public repair entry after the Web import gate landed completed successfully and wrote an
  installation manifest for code commit `fe3d8d1bc61fd28ca9c9d286d65dc2d40f2d13f2`.
- Doctor returned `ok:true`, no issues, `dsh.ready=true`, and `runtime_lock_matches=true`.
- Start completed in 10.03 seconds; restart in 9.97 seconds; stop removed both owned processes and closed
  3081/8088; the subsequent start completed in 9.39 seconds.
- Every running state returned Runtime API `connected=true` and `health_check_passed=true`.
- The visible in-app browser opened FinGPT, rendered navigation, composer, model catalog, and Skill entries,
  survived normal refresh and managed-restart refresh, showed connection refusal after stop, and recovered on
  the next start.

Windows Web automation is paused by project policy and is not part of this change's claims.

## Review boundary

Independent Python review found no Critical or Important issue and declared the complete code Ready. Its only
Minor noted that the unresponsive-pip test returned a nonzero code rather than raising the real timeout; the test
now raises `subprocess.TimeoutExpired`, and the 33/33 setup suite passed again. The earlier status review also
confirmed the real CLI keeps the runtime feature graph unloaded, traced Doctor and start through the lazy seam,
and passed Runtime launch plus protocol tests 46/46. A supplemental mypy run produced no output for more than two
minutes and was interrupted, so it is not reported as passed.

## Architecture and documentation review

The Research Web process topology, loopback ports, public CLI and HTTP contracts, DSH launch contract, health
model, and capability graph are unchanged. Installation keeps the same public entrypoints, locks, ownership
marker, staging transaction, and fixed DSH; explicit repair now detects an unresponsive owned environment, and
installation proves the Web entrypoint before publishing success. The generated Python index reflects the new
installer probes and service-manager lazy seam. The root README remains accurate because user-visible commands
did not change; detailed repair semantics live in the installation document.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"The service manager keeps the existing CLI, process ownership, health, and Doctor contracts; installer repair and Web import readiness run before service creation and add no API, service, storage, or topology edge.","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"The DSH launcher retains the same pinned commit, capability, MCP, and execution behavior; repair preserves the existing environment transaction and the install import probe does not run Runtime or lifespan services.","diagrams":[]} -->
