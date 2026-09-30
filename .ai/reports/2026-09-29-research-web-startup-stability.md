# Research Web startup stability

## Scope and current-state reproduction

On 2026-09-29 the main checkout had a `.venv` directory without an executable Python. `./rwb web status` and `./rwb web doctor --json` exited before the CLI loaded; neither 3081 nor 8088 was listening. A retained environment could invoke the manager directly, which removed confirmed-dead stale PID state and reported an unowned environment. This established the entrypoint and diagnostic gap. No conclusion about sustained browser availability follows from that stopped-state observation.

The implementation is isolated on `codex/research-web-startup-stability`, based on `4d6a4eff6`. It does not change DSH source, model credentials, desktop sidecars, or the paused Windows Web automation policy. The design and implementation plan are in `docs/superpowers/specs/2026-09-29-research-web-startup-diagnostics-stability-design.md` and `docs/superpowers/plans/2026-09-29-research-web-startup-diagnostics-stability.md`.

## Changes and RED/GREEN evidence

- The public installer repaired the worktree runtime environment with `./setup-web.sh --repair --no-start` (exit 0, 61.49 s, `started=false`). Product `.venv` reported Python 3.12.13, CJPY 0.5.2, requests 2.34.2 and urllib3 2.8.0. It intentionally does not contain pytest. A pre-existing Python 3.12.13 development environment was used only as test runner against this worktree's source; the initial service-manager/setup/CLI baseline was 97 passed.
- Task 2 introduced the shared standard-library environment, Node, proxy, process and safe control-file contracts. RED caught fake ownership markers, malformed Node versions, Unicode decoding, and disagreement between installer `check()` and its real marker; the final focused contract/setup suite was 114 passed. Later process and safe-reader work extended this coverage.
- Task 3 added diagnostic-only status/Doctor fallback for missing or damaged `.venv`. RED exposed traceback on huge/deep JSON, an incomplete-marker launcher bypass, Windows common-worktree classification, unsafe state aliases, and overclaimed ownership. The final Task 3 suite was 211 passed. Native Windows execution has not been observed.
- Task 4 made normal status/Doctor use independent state → process → ownership → listener → protocol facts. RED exposed unsafe state reads, PID reuse, token collisions, a foreign listener, stage-failure fact loss, and macOS `ps` losing argv boundaries. Exact macOS `KERN_PROCARGS2` argv was verified with a short child process containing a spaced argument. The final shared/Task 4 suite was 344 passed.
- Task 5 added an advisory lifecycle guard and owned-process reconciliation. RED reproduced stale-lock ABA with forked contenders, old Runtime auth after safe recovery, orphaning after `Popen`/state-write failure, Windows directory fsync, ancestor alias handling, and `/var` system-alias over-rejection. Real fork contention and a real macOS `/var` temp path passed after repair. Final service-manager suite was 176 passed; shared/protocol suite 270 passed.
- Task 6 required Runtime API, root HTML and `/static/app.mjs` to pass before opening a browser. Model and proxy failures are separate warnings. RED was 31 failures across readiness, browser, Node, model and proxy cases; the focused suite became 219 passed, with 264 shared/protocol cases and 80 JS cases. Subsequent JSON boundary review reproduced 14 failures for size/media type/close behavior, then passed 362 related cases. The final quality fix isolated an installation-contract unit test from the real 8088 port and restored safe internal exception chaining: five targeted RED failures became five passes; service-manager/CLI/protocol suite was 260 passed. Ruff, Black, isort and diff checks passed for that fix.

These are source and controlled-test results. They do not yet establish that the changed services remain reachable after the terminal exits or across refresh and restart on this machine.

## Service-state fault matrix

| Case | Expected action | Current evidence |
| --- | --- | --- |
| Ready owned Runtime and Web | Idempotent start, preserve PID | Unit contract passed; live acceptance not run |
| Dead PID and closed port | Remove stale state under lock, start | Unit contract passed; live acceptance not run |
| Damaged state with no live PID/listener | Quarantine exact file, rebuild | Unit contract passed; live acceptance not run |
| Owned but unhealthy Runtime | Stop owned Web then Runtime, rebuild | Unit contract passed; live acceptance not run |
| Unknown/foreign PID or listener | Refuse without termination | Unit contract passed; live fault injection not run |
| Competing lifecycle commands | One OS guard owner | Real forked contender test passed; product lifecycle not run |
| Browser open failure | Keep ready services, emit warning and URL | Unit contract passed; visible browser acceptance not run |

## Local macOS installation and lifecycle

The public installer repair with `--no-start` passed. The real default `./rwb web start|status|restart|stop` sequence on this branch is not_run. Terminal detachment, stale PID fault injection, external port conflict and sustained 3081/8088 health remain not_run.

## Browser and refresh acceptance

First load, reload, restart reload, setting page access without a model credential, static asset stability and a bounded observation window remain not_run. The app browser has not been used to certify this branch.

## Incremental validation

The final changed set will be planned with `scripts/plan_verification.mjs`; its L0–L4 closure and `scripts/validate_verification_receipt.mjs` remain pending. The macOS Bootstrap workflow contract was added test-first: the new JS assertion failed against the old workflow, then `node --test tests/javascript/actions_quota_governance.test.mjs` passed 12/12 after the workflow began checking schema 2, installation/product/service ready, root HTML and the main ES module. On 2026-09-30, the complete committed and working changed set passed Project Constraints with `violations: []`, documentation governance with 512 files / 73 current / 0 violations, the generated Python index check, and 62/62 Research Web architecture tests. These local checks do not certify remote CI.

## Publication and external gates

Publication is not_run. Project Constraints, Research Web Checks and GitHub `macos-14` clean Bootstrap are not_run on a published SHA. Windows Web native verification remains paused by current project policy and is not claimed.

## Unverified items and residual risks

The product runtime environment currently has no pytest by design; source tests used the separate pre-existing development interpreter. Native Windows behavior is supported by static/model contracts only. No live Web/DSH lifecycle, terminal-detachment or browser evidence has yet been collected for this branch. Remote delivery requires the current Actions budget/visibility check and user authorization.

## Architecture review

The deployed topology remains one loopback DSH Runtime on 3081 and one FastAPI Host on 8088, with DSH as the sole research engine. New modules isolate the standard-library fallback, safe runtime contracts, service facts and lifecycle guard. They add no daemon, database, route, research engine, framework, integration state or Tabbit authority. The public CLI diagnostic JSON advances to schema 2 while retaining `ok`, `running`, `healthy`, `pid` and `port`; `status` and Doctor reflect observed facts. The installation and browser readiness contract changes, so the root README, installation guide, architecture, security and macOS Bootstrap workflow were updated. Gold/Dollar, IntegrationCoordinator and Tabbit module documents record their unchanged boundaries.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"The new fallback, service facts and lifecycle guard refine existing process management. The deployment nodes, DSH-to-Host edge, HTTP routes and diagrammed module relationships remain the same; no diagram topology changes are required.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"The macOS Bootstrap now asserts Doctor schema 2 and reads root/static assets, while the existing Project Constraints workflow, documentation service, ten diagrams and 08 documentation flow retain their nodes and relationships; no diagram topology changed.","diagrams":[]} -->
