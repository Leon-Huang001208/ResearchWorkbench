# Research Web status lazy runtime import

## Scope and reproduction

The P0 audit found that the first `./rwb web status` invocation could take about 30 seconds even when both
managed services were stopped. The interrupted stack was reading
`app/research_web/capabilities/packages.py` through this eager import chain:

```text
service_manager -> launch_runtime -> capabilities.catalog -> capabilities.packages
```

The `status()` path does not prepare the DSH runtime, enumerate capabilities, or calculate the DSH build
closure. It only needs the pinned commit to derive the default runtime path and validate owned runtime state.
Warm measurements still showed `service_manager` import at about 0.59 seconds, including about 0.28 seconds
inside `launch_runtime` and its FastAPI, MCP, DataHub, and capability dependencies.

## Minimal repair

- Move the shared pinned DSH commit to the lightweight `app.research_web` package root while preserving the
  existing `PINNED_COMMIT` exports in both consumers.
- Keep `calculate_build_closure()` available at the existing service-manager seam, but import its implementation
  only when Doctor or installation diagnosis actually requests the DSH closure.
- Add a subprocess regression test proving that importing `service_manager` does not load `launch_runtime`,
  capability packages, or MCP routes.

The change does not alter service ownership checks, PID handling, ports, HTTP health, DSH health, Doctor build
attestation, start/stop/restart behavior, public commands, or response formatting.

## TDD and observed behavior

- RED: the new subprocess assertion failed because `app.research_web.launch_runtime` was present in
  `sys.modules` immediately after importing `service_manager`.
- GREEN: the same assertion passed after the import boundary change.
- Direct import improved from about 0.59 seconds to 0.18 seconds in the observed warm-cache comparison.
- Three real stopped-service status invocations completed in 0.34, 0.28, and 0.25 seconds and continued to
  report Runtime 3081 and Web 8088 as stopped.
- No Python package or runtime dependency was installed; an existing development environment backup supplied
  the local pytest runner.

## Incremental validation

The complete changed set is routed to L4 because `service_manager.py` owns the Research Web service lifecycle.
The first L0 attempt correctly found the generated Python index stale after the import boundary changed. The
index was regenerated and the plan was rerun with `validation_failure`. The next L2 attempt correctly required
this task report and an updated README review receipt; both failures remain part of the evidence trail.

The complete 16-path plan includes source, focused test, mapped architecture documents, README review, generated
index, report, plan, and receipt. The final local closure passed:

| Plan ID | Level | Result | Duration |
| --- | --- | --- | ---: |
| `documentation-governance` | L0 | passed; 509 files, 71 current, 0 violations | 0.16 s |
| `python-file-index` | L0 | passed; generated index verified | 1.18 s |
| `research-web-architecture` | L1 | passed; 62/62 | 3.06 s |
| `research-web-service-manager` | L1 | passed; 58/58 | 1.12 s |
| `project-constraints-local` | L2 | passed; 16 paths, 0 violations | 0.13 s |
| `research-web-critical-smoke` | L3 | passed; 19/19 | 0.47 s |
| `research-web-verification-full` | L4 | passed; 80/80 | 3.05 s |

Targeted Ruff, Black, isort, and `git diff --check` also passed. A worktree Doctor run still performed the full
DSH closure check (`dsh.ready=true`, `runtime_lock_matches=true`) in 11.91 seconds; it correctly reported the
isolated worktree checkout as not installed (`environment_not_owned`, `cjpy_not_ready`) rather than claiming the
shared main-checkout environment. The receipt remains `blocked` until all three required external gates pass.
Windows Web automation is paused by project policy and is not part of this change's claims.

An independent Python review found no Critical, Important, or Minor issue. It separately confirmed that the real
CLI status path keeps the runtime feature graph unloaded, traced Doctor and start through the lazy closure seam,
and passed Runtime launch plus protocol tests 46/46. A supplemental mypy run produced no output for more than two
minutes and was interrupted, so it is explicitly not reported as passed; mypy is not in this plan's required
validation closure.

## Architecture and documentation review

The Research Web process topology, loopback ports, public CLI and HTTP contracts, DSH launch contract, health
model, capability graph, and installation flow are unchanged. The existing architecture documents therefore
remain accurate. The generated Python index is updated because `service_manager` no longer has a top-level
`launch_runtime` import and now exposes the lazy closure seam. The root README remains accurate for the same
reason: user-visible setup and lifecycle commands did not change.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"The service manager keeps the existing CLI, process ownership, health, and Doctor contracts while deferring the DSH build scanner until installation diagnosis requests it; no API, service, storage, or topology edge changes.","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"The DSH launcher retains the same pinned commit, preparation, capability, MCP, and execution behavior; only the service-manager import boundary stops loading the runtime feature graph during status-only commands.","diagrams":[]} -->
