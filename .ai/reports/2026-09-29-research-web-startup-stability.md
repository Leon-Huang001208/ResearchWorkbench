# Research Web startup stability

## Scope and current-state reproduction

On 2026-09-29 the main checkout had a `.venv` directory without an executable Python. `./rwb web status` and `./rwb web doctor --json` exited before the CLI loaded; neither 3081 nor 8088 was listening. A retained environment could invoke the manager directly, which removed confirmed-dead stale PID state and reported an unowned environment. This established the entrypoint and diagnostic gap. No conclusion about sustained browser availability follows from that stopped-state observation.

The implementation is isolated on `codex/research-web-startup-stability`, originally based on `4d6a4eff6` and locally integrated with remote `master` at `e39b6e2cc`. It does not change DSH source, model credentials, desktop sidecars, or the paused Windows Web automation policy. The design and implementation plan are in `docs/superpowers/specs/2026-09-29-research-web-startup-diagnostics-stability-design.md` and `docs/superpowers/plans/2026-09-29-research-web-startup-diagnostics-stability.md`.

## Changes and RED/GREEN evidence

- The public installer repaired the worktree runtime environment with `./setup-web.sh --repair --no-start` (exit 0, 61.49 s, `started=false`). Product `.venv` reported Python 3.12.13, CJPY 0.5.2, requests 2.34.2 and urllib3 2.8.0. It intentionally does not contain pytest. A pre-existing Python 3.12.13 development environment was used only as test runner against this worktree's source; the initial service-manager/setup/CLI baseline was 97 passed.
- Task 2 introduced the shared standard-library environment, Node, proxy, process and safe control-file contracts. RED caught fake ownership markers, malformed Node versions, Unicode decoding, and disagreement between installer `check()` and its real marker; the final focused contract/setup suite was 114 passed. Later process and safe-reader work extended this coverage.
- Task 3 added diagnostic-only status/Doctor fallback for missing or damaged `.venv`. RED exposed traceback on huge/deep JSON, an incomplete-marker launcher bypass, Windows common-worktree classification, unsafe state aliases, and overclaimed ownership. The final Task 3 suite was 211 passed. Native Windows execution has not been observed.
- Task 4 made normal status/Doctor use independent state → process → ownership → listener → protocol facts. RED exposed unsafe state reads, PID reuse, token collisions, a foreign listener, stage-failure fact loss, and macOS `ps` losing argv boundaries. Exact macOS `KERN_PROCARGS2` argv was verified with a short child process containing a spaced argument. The final shared/Task 4 suite was 344 passed.
- Task 5 added an advisory lifecycle guard and owned-process reconciliation. RED reproduced stale-lock ABA with forked contenders, old Runtime auth after safe recovery, orphaning after `Popen`/state-write failure, Windows directory fsync, ancestor alias handling, and `/var` system-alias over-rejection. Real fork contention and a real macOS `/var` temp path passed after repair. Final service-manager suite was 176 passed; shared/protocol suite 270 passed.
- Task 6 required Runtime API, root HTML and `/static/app.mjs` to pass before opening a browser. Model and proxy failures are separate warnings. RED was 31 failures across readiness, browser, Node, model and proxy cases; the focused suite became 219 passed, with 264 shared/protocol cases and 80 JS cases. Subsequent JSON boundary review reproduced 14 failures for size/media type/close behavior, then passed 362 related cases. The final quality fix isolated an installation-contract unit test from the real 8088 port and restored safe internal exception chaining: five targeted RED failures became five passes; service-manager/CLI/protocol suite was 260 passed. Ruff, Black, isort and diff checks passed for that fix.

The source tests were followed by default-port macOS lifecycle and browser observations below. The first live start and two stop attempts exposed timing defects absent from simulated probes. Targeted RED tests preceded the launcher-transition, termination-transition and macOS trusted-root fixes. The resulting contract/setup/bootstrap/service-manager/CLI/protocol subset passed 515/515; Ruff, Black and isort passed on affected files.

The final read-only review found two further startup races. RED tests reproduced that ordinary `start` would stop an owned but temporarily unhealthy DSH without checking active research, and that a final `product_ready=false` could still return success. `start` now checks activity before any Runtime/Web stop, refuses an active or unverified session, and retries final product readiness for a bounded interval before returning a service-specific nonzero error. The service-manager suite passed 247 cases after this fix; Ruff and isort passed. Black formatting was applied through the existing Python module because the old `black` executable's shebang pointed to a removed interpreter. No dependency was installed.

## Service-state fault matrix

| Case | Expected action | Current evidence |
| --- | --- | --- |
| Ready owned Runtime and Web | Idempotent start, preserve PID | Live repeat start kept Runtime 91275 and Web 91393 |
| Dead PID and closed port | Remove stale state under lock, start | Live Web SIGTERM produced stale Web; start kept Runtime 53941 and started Web 60510. DSH SIGTERM produced stale Runtime; restart recovered both services |
| Damaged state with no live PID/listener | Quarantine exact file, rebuild | Clean checkout first startup left a state invalid after the `/tmp` signature correction; the next `start` quarantined it and reached healthy 3081/8088 |
| Owned but unhealthy Runtime | Read-only activity check first; refuse active/unknown research, otherwise stop owned Web then Runtime and rebuild | RED/GREEN guard tests passed; live restart after confirmed-dead DSH stopped old Web 60510 before new Runtime/Web became ready |
| Unknown/foreign PID or listener | Refuse without termination | Real external socket on isolated alternate port 54392 returned `runtime_port_in_use_unknown`; socket stayed open |
| Competing lifecycle commands | One OS guard owner | Real forked contender test passed; product lifecycle not run |
| Browser open failure | Keep ready services, emit warning and URL | Unit contract passed; successful default `./rwb web start` returned ready without warning |

## Local macOS installation and lifecycle

The public installer repair with `--no-start` passed. Before live correction, the first default `start --no-open` returned `runtime_process_exited` in 1.75 s while its Python launcher was still becoming Node; Runtime subsequently listened on 3081. The wait path now recognizes only the exact PID, state, start time and launcher/final argv during that bounded transition. The next start stopped that owned unhealthy Runtime and reached both healthy services in 11.80 s. A first normal stop exposed transient probe loss after Web SIGTERM; a traced stop observed the legitimate `valid/alive/port closed` → `stale/missing/port closed` sequence. The stop wait now tolerates an already-signalled PID only while it waits for listener closure; it never force-kills an unverified PID.

After fixes, a complete live start created Runtime 44878 and Web 44993; stop exited 0, removed both states and closed both ports. A later start created 48452/48558; ordinary restart verified zero active research, stopped both, and created 53941/54592. `ps` returned no old PIDs. Web SIGTERM left a stale Web state; `start --no-open` preserved DSH 53941 and created Web 60510. DSH SIGTERM left Runtime stale and Web not ready with `web_runtime_api_failed`; ordinary `restart --no-open` stopped Web 60510, created DSH 70035 and Web 70502, and returned both healthy. All these child services had PPID 1 after the launching shell exited.

One bounded observation window sampled Runtime API, root HTML and `/static/app.mjs` six times over about 50 seconds; all 18 direct loopback requests passed, and Runtime API returned `connected=true` and `health_check_passed=true` each time. The main module was read completely at 136,029 bytes after an earlier pipeline check using `rg -q` prematurely closed curl's pipe; that earlier curl error is not counted as a resource failure. `./rwb web doctor --json` while running reported schema 2, `installation_ok=true`, `product_ready=true`, no issues, and both service probes ready.

An isolated detached checkout began at `1cf4cd5d5` with a separate temporary data root. The first fixed-DSH pnpm install attempt reached 1,246/1,265 packages but returned exit 23 after a network fetch timeout, yielding `dsh_build_step_1_failed`. A repair retry hit a transient Git clone `curl 56` / “Can't assign requested address” and returned `dsh_clone_failed`. After a read-only `git ls-remote` succeeded, the next bounded repair attempt completed the exact pinned DSH build and wrote `status=installed`, `started=false`. This sequence demonstrates recovery by retry; it does not prove a first-attempt installation under unreliable network conditions.

The clean checkout's first public `start --no-open` then exposed a macOS `/tmp` versus `/private/tmp` overlay argv mismatch. The manager correctly refused to treat the resulting process as owned, but the command returned `runtime_process_exited` after 16.77 s and left its newly created Runtime listening. A focused RED confirmed the signature mismatch; the Runtime overlay signature now uses the resolved path. The exact leftover PID 14710 was verified against its command and 3081 listener, then terminated. After switching the clean checkout to commit `cb5540742`, `status` identified the old dead-PID state as invalid with port closed. `start --no-open` quarantined that state, started Runtime 2382 and Web 3067, and returned both healthy in 12.94 s. The clean checkout's Doctor returned schema 2, `installation_ok=true`, `product_ready=true`, `model_ready=false`, warning `model_credential_missing`, and both service probes ready. Runtime API reported `connected=true`, `health_check_passed=true`, `credential_configured=false`; root HTML (948 bytes) and `/static/app.mjs` (136,029 bytes) passed complete direct-loopback reads. Both processes remained alive with PPID 1 after the launcher exited. Public `stop` then stopped both, cleared the ports and state, and returned success.

The detached checkout had no tracked changes. After the exact test PIDs were absent, `git worktree remove` removed the checkout. The temporary data root held only this test's install, runtime, logs and generated read-only capabilities; ordinary `rm -r` removed its writable portion but stopped on read-only Skill directories. Their directories were made owner-writable within that exact 1.8 MiB residual test root, then the root was removed. Both temporary paths were confirmed absent; these disposable test artifacts are not recoverable after cleanup.

## Browser and refresh acceptance

The in-app browser opened `http://127.0.0.1:8088/#/fingpt` and rendered navigation, composer, DeepSeek-V4-Flash selection and Skill cards. An explicit reload briefly displayed “正在连接运行时” and a disabled send control, then settled to the configured model and enabled send without a false offline state. The settings and model-service pages loaded and showed DSH connected. With the same tab open, an ordinary managed restart changed the Runtime/Web PIDs; reloading the model page again moved from “DSH 连接中” to “DSH 已连接” and restored the selected model. The browser-specific plugin could not initialize because macOS rejected its native module signature; the app's alternate computer-use browser surface provided these visible observations. In the isolated clean data root with no model credential, a fresh browser tab loaded `#/settings/model` and visibly showed “需要配置模型 / DSH 待授权” with the API Key input while Doctor still reported `product_ready=true`. No credential was entered or changed.

## Incremental validation

The complete 40-path changed set was routed by the prior schema-2 `scripts/plan_verification.mjs` to L4 / `full-delivery`. The plan retains `validation_failure` and `unexpected_behavior` escalation signals from live discovery and names `unknown_impact_boundary`; no gate was downgraded. The macOS Bootstrap workflow contract was added test-first: the new JS assertion failed against the old workflow, then passed after the workflow began checking schema 2, installation/product/service ready, root HTML and the main ES module. All 12 selected local validations in the table below passed before the final review fix and remote integration. They are historical evidence, not a claim that the newly integrated schema-3 closure has passed. Generic `python` test commands used the pre-existing Python 3.12 development interpreter; product `.venv` supplied runtime and installation facts. The local integration skip remains a skip, not a pass.

| Level | Validation | Command | Result | Duration |
| --- | --- | --- | --- | ---: |
| L0 | documentation-governance | `node scripts/check_documentation_governance.mjs --project .` | exit 0; 512 files; 73 current; 0 violations | 0.20 s |
| L0 | python-file-index | `python scripts/generate_py_file_index.py --check` | exit 0; index verified | 1.22 s |
| L1 | verification-policy-contracts | `node --test tests/javascript/verification_policy.test.mjs` | exit 0; 64 passed | 4.87 s |
| L1 | verification-receipt-contracts | `node --test tests/javascript/verification_receipt.test.mjs` | exit 0; 16 passed | 1.91 s |
| L1 | incremental-validation-skill-contracts | `node --test tests/javascript/incremental_validation_skill.test.mjs` | exit 0; 5 passed | 0.16 s |
| L1 | research-web-local-integrations | `python -m pytest tests/research_web/test_local_integrations.py --confcutdir=tests/research_web -q` | exit 0; 45 passed; 1 skipped; 1 warning | 22.40 s |
| L1 | research-web-architecture | `node --test tests/javascript/research_web_architecture.test.mjs` | exit 0; 62 passed | 3.94 s |
| L1 | research-web-service-manager | `python -m pytest tests/research_web/test_service_manager.py --confcutdir=tests/research_web -q` | exit 0; 244 passed | 2.15 s |
| L1 | research-web-installation | `python -m pytest tests/research_web/test_setup_web.py --confcutdir=tests/research_web -q` | exit 0; 47 passed | 15.72 s |
| L2 | project-constraints-local | `node .agents/project-constraints.mjs --project . --changed-file <all 40 paths>` | exit 0; 0 violations | 0.50 s |
| L3 | research-web-critical-smoke | `python -m pytest tests/research_web/test_protocol.py --confcutdir=tests/research_web -q` | exit 0; 19 passed | 1.84 s |
| L4 | research-web-verification-full | `node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs` | exit 0; 81 passed | 3.45 s |

The prior schema-2 plan and receipt validator accepted all 12 executed local items. That historical receipt remains `blocked` because its three required GitHub workflows were `not_run` on a published SHA; this is not a local test failure. The integrated schema-3 policy selects four CI merge gates, including native Windows Web verification; none has run for this branch.

## Post-review and remote integration follow-up

The remote `master` merge completed without conflict and brought in the shared schema-3 verification planner and schema-2 receipt validator. Its 11-file project runtime manifest matched all managed SHA-256 checks. The new policy still routes the complete 40-path branch change set to L4 / `full-delivery`, with 12 local checks, four CI merge gates and `unknown_impact_boundary`. The old schema-2 receipt is retained only as an earlier evidence snapshot. The complete schema-3 local closure passed in L0→L4 order:

| Level | Validation | Observed result | Duration |
| --- | --- | --- | ---: |
| L0 | documentation-governance | exit 0; 513 files, 73 current, 0 violations | 0.43 s |
| L0 | python-file-index | exit 0; generated index verified | 1.40 s |
| L1 | verification-policy-contracts | exit 0; 67 passed | 5.61 s |
| L1 | verification-receipt-contracts | exit 0; 21 passed | 2.44 s |
| L1 | incremental-validation-skill-contracts | exit 0; 5 passed | 0.27 s |
| L1 | research-web-local-integrations | exit 0; 45 passed, 1 skipped, 1 warning | 21.56 s |
| L1 | research-web-architecture | exit 0; 62 passed | 3.08 s |
| L1 | research-web-service-manager | exit 0; 248 passed | 1.94 s |
| L1 | research-web-installation | exit 0; 47 passed | 15.33 s |
| L2 | project-constraints-local | exit 0; complete 40-path set, 0 violations | 0.13 s |
| L3 | research-web-critical-smoke | exit 0; 19 passed | 1.08 s |
| L4 | research-web-verification-full | exit 0; 81 passed | 2.72 s |

The selected Python checks used the existing Python 3.12 development interpreter with `--confcutdir=tests/research_web`; no product dependency was installed for testing. Beyond the planned closure, the six-suite Web startup regression set passed 520/520 in 23.25 seconds. Ruff, Black and isort checks passed on all 12 changed Python files. The one local-integration skip and warning remain recorded as such.

After the merge, `./rwb web doctor --json` reported `installation_ok=true`, both services missing and both ports closed. `./rwb web start --no-open` exited 0 in about 13 seconds, with owned ready DSH PID 74536 and Web PID 75078. `./rwb web status` confirmed both ready; direct loopback GET returned HTTP 200 for root HTML (948 bytes) and `/static/app.mjs` (136,029 bytes). `./rwb web stop` exited 0, stopped those exact PIDs and reported both ports closed. No service was left running by this smoke test.

## Publication and external gates

Publication is not_run. Project Constraints, Research Web Checks, GitHub `macos-14` clean Bootstrap and schema-3-selected Windows Web Verify are not_run on a published SHA. The project's Windows Web native-verification pause remains in force until a user decision; Windows behavior is not claimed.

## Unverified items and residual risks

The product runtime environment has no pytest by design; source tests used the separate pre-existing development interpreter. Native Windows behavior is supported by static/model contracts only. The local clean installer needed retries after npm fetch timeout and Git connection failure; GitHub's clean `macos-14` Bootstrap remains the required independent installation gate. Remote delivery requires the current Actions budget/visibility check and user authorization.

## Architecture review

The deployed topology remains one loopback DSH Runtime on 3081 and one FastAPI Host on 8088, with DSH as the sole research engine. New modules isolate the standard-library fallback, safe runtime contracts, service facts and lifecycle guard. They add no daemon, database, route, research engine, framework, integration state or Tabbit authority. The public CLI diagnostic JSON advances to schema 2 while retaining `ok`, `running`, `healthy`, `pid` and `port`; `status` and Doctor reflect observed facts. The installation and browser readiness contract changes, so the root README, installation guide, architecture, security and macOS Bootstrap workflow were updated. Gold/Dollar, IntegrationCoordinator and Tabbit module documents record their unchanged boundaries.

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"The new fallback, service facts and lifecycle guard refine existing process management. The deployment nodes, DSH-to-Host edge, HTTP routes and diagrammed module relationships remain the same; no diagram topology changes are required.","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"The macOS Bootstrap now asserts Doctor schema 2 and reads root/static assets, while the existing Project Constraints workflow, documentation service, ten diagrams and 08 documentation flow retain their nodes and relationships; no diagram topology changed.","diagrams":[]} -->
