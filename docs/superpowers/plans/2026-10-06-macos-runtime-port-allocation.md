# macOS Runtime Port Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Execute sequential tasks with TDD and scoped review; never parallelize implementation edits.

**Goal:** Implement the approved macOS Native/Docker automatic port allocation and token-preserving trusted-origin transaction, then physically verify both runtimes without stopping daily instances.

**Architecture:** Keep the existing runtime managers, shared product data and fixed Docker internal ports. Add small stdlib endpoint persistence/allocation and private control-origin transaction helpers, integrate them into existing owned lifecycle locks, and keep old schema-v1 mode records unchanged.

**Tech Stack:** Python3.12 stdlib, existing private filesystem APIs/logging, existing Typer/bootstrap, Docker Compose, fixed DSH and the current v3 verification planner/v2 receipt.

**Spec:** `docs/superpowers/specs/2026-10-06-macos-runtime-port-allocation-design.md` (user confirmed the trusted-origin scope).

## Global Constraints

- Only edit `/Users/leon/.codex/worktrees/macos-dual-runtime-acceptance/ResearchWorkbench`, branch `codex/macos-runtime-port-allocation-20261006`; original source base05326b606, approved spec commit02f3ce5b1.
- macOS only. Windows/Linux host acceptance is deferred, not passed. Do not delete historical gates or rewrite old evidence; do not start desktop/Tauri work.
- No push/PR change/merge/tag/release/dispatch/rerun, global proxy/DNS/Docker/Harness change, package installation, user credential reads/migrations, unrelated cleanup or nested agents.
- Existing fixed Web Python/Node/DSH/CJPY inputs must not change. Actual base-image pulls have already succeeded; this does not prove final image build or health.
- Preserve precise native PID/argv/start-time/listener ownership, private/no-follow/one-link checks, lifecycle locks, immutable image/install/mount/launch ownership, current error propagation and bounded cleanup. Never kill by port.
- Same product data must not be written concurrently by Native/Docker. Retain control tokens and all other fields. Control changes occur only after verified quiescence, with exact ownership/content rollback; no raw control content or secret-derived diagnostics in logs/artifacts.
- No implementation in the parent/main/old feature worktrees. You are not alone: main writes plan/ledger and later acceptance artifacts; do not revert others' edits.
- Use the existing approved test interpreter `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python` with cwd/PYTHONPATH targeting this worktree, `--confcutdir=tests/research_web`. No dependency installation; report unavailable format/type tools truthfully.

## Task 1: Private endpoint and control-origin transaction foundations

**Files:**
- Create: `research_workbench_entrypoint/runtime_endpoints.py`, `tests/research_web/test_runtime_endpoints.py`.
- Create: `app/research_web/control_origin.py`, `tests/research_web/test_control_origin.py`.
- Modify only if required to reuse private APIs: `research_workbench_entrypoint/runtime_mode.py`, `app/research_web/datahub/security.py`, `app/research_web/mcp_runtime/control.py`.
- Synchronize new source/test inventory and helper contracts in `docs/architecture/research-web/architecture-map.json`, `docs/DEVELOPMENT_MAP.md`, `docs/architecture/research-web/02-research-runtime.md`, `05-security-validation.md`, `docs/generated/py_file_index.md`, `.ai/reports/2026-10-06-runtime-endpoint-foundations.md`.

- [ ] **Step 1: Read the approved spec, root rules, module docs and current private filesystem helpers before editing.** Reuse the original readers/writers; do not create a generic settings or migration framework.
- [ ] **Step 2: Add failing tests for the concrete new contracts.** The stdlib helper provides `EndpointStore(home)` at private `install/endpoints.json`, strict schema1, independent `native` and `docker` records. Public helper interface: `read(mode)` returns `None` for a missing mode, otherwise selected integer ports; `publish(mode, web_port, runtime_port=None, expected=<previous snapshot>)` performs a compare-and-swap private atomic update and returns the new snapshot. Native requires distinct Web/DSH ports; Docker stores only host Web port. Boolean, zero, negative, greater-than65535, unknown keys/modes, unsafe aliases/permissions/links, conflicting snapshots and inconsistent recorded process facts fail closed. The exact class internal representation is worker-owned, but these interface semantics are binding.

Concrete round-trip test (complete test body; add imports for the new helper):

```python
def test_endpoint_store_round_trip(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    store = EndpointStore(home)
    assert store.read("native") is None
    native = store.publish("native", web_port=18088, runtime_port=13081, expected=None)
    assert native.web_port == 18088
    assert native.runtime_port == 13081
    docker = store.publish("docker", web_port=18089, expected=None)
    assert docker.web_port == 18089
    assert docker.runtime_port is None
    assert store.read("native") == native
    assert store.read("docker") == docker
```

Concrete strict-type case:

```python
@pytest.mark.parametrize("value", [True, False, 0, -1, 65536, "8088", 8088.0])
def test_endpoint_store_rejects_invalid_port(tmp_path, value):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    store = EndpointStore(home)
    with pytest.raises(EndpointError):
        store.publish("docker", web_port=value, expected=None)
    assert store.read("docker") is None
```

For origin tests, create only test-owned `.control` files with DataHub shape `{"token":"x" * 43,"url":"http://127.0.0.1:8088"}` and MCP shape `{"version":1,"token":"y" * 43,"url":"http://127.0.0.1:8088"}`, both0600 under0700 directories. Use `ControlOriginTransaction(data_root, previous_origin, next_origin, quiescent=<proof callback>)`, explicit `prepare()`, `commit()`, `rollback()`; the caller owns lifecycle lock and quiescence proof. Successful prepare updates both existing origins while preserving original token/other fields; missing files remain missing for the normal trusted creators, unchanged origin makes no writes. Commit discards only owned transaction metadata; rollback restores only exact transaction-owned writes, and refuses foreign replacement. Tests cover both URLs, token equality, unchanged data fixture, malformed token/schema, unsafe file/parent/link, old-origin mismatch, live/unknown quiescence, second write failure, failed target startup, content-identical inode replacement, and interrupted journal detection. Validators such as existing `load_control()` continue rejecting drift absent this explicit transaction.

- [ ] **Step 3: Run RED and save the actual failure log.**

```bash
PYTHONPATH=$PWD /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest tests/research_web/test_runtime_endpoints.py tests/research_web/test_control_origin.py --confcutdir=tests/research_web -q --tb=short
```

Expected initial missing helpers/behavior failures, not skipped tests or shell/permission errors relabeled RED.

- [ ] **Step 4: Implement the exact two helper contracts.** Endpoint records are runtime-owned metadata, not second dependency facts. Use stable path-free error codes and existing logs. Port selection tries preferred value first; ephemeral candidates come from real loopback bind, cannot be represented as guaranteed reservations after closing the socket. The integration task must prove actual listeners and perform bounded collision recovery. Origin prepare validates both old records before writes; pins file/parent identity and schema; never moves/rotates tokens. Keep original bytes only in private process memory for ordinary rollback. Persistent interruption metadata contains fixed filenames, old/new loopback origins, phases and guarded identities/fingerprints, not token snapshots or arbitrary paths. A crash gap whose publication identity cannot be proven must return interrupted/recovery-unverified instead of overwriting current records. Preserve absent files, roll back owned newly created files only if integration actually created them, and refuse concurrent substitutions.
- [ ] **Step 5: Run GREEN, covering existing private boundary tests once.** Include `test_runtime_mode.py`, `test_runtime_auth.py`, `test_datahub.py`, `test_mcp_authorization.py` as applicable to actual edited helper paths, preserving old negative assertions. Regenerate/check Python index, update the new source/test inventory, run documentation governance/full task changed-set Constraints and diff checks. Commit only this task's files. Write the full RED/GREEN/commands/source/risks report to the assigned scratch report and the `.ai` task report. Do not claim integration or physical lifecycle completion.

## Task 2: Integrate port policy into public Native/Docker lifecycle

**Depends on Task1 reviewed interfaces.**

**Files:** `app/cli/main.py`, `app/research_web/service_manager.py`, `app/research_web/process_spec.py`, `research_workbench_entrypoint/bootstrap.py`, `web_bootstrap.py`, `docker_runtime.py`, `scripts/setup_web.py`; Task1 helpers only if integration exposes a load-bearing defect; `compose.yaml` only if needed for runtime-owned ephemeral host binding. Tests: `test_service_manager.py`, `test_runtime_mode.py`, `test_docker_runtime.py`, `test_setup_web.py`, `test_cli_lazy.py`, `test_web_bootstrap.py`, helper tests. Update installation/README/module/architecture docs, index/inventory and `.ai/reports/2026-10-06-runtime-port-lifecycle.md`.

- [ ] **Step 1: Write public-entrypoint and lifecycle RED tests.** Add `--web-port` and Native-only `--runtime-port` to setup and rwb web start/restart. Docker runtime-port override returns a stable unsupported-option error; its internal3081 stays fixed. Explicit occupied port fails; implicit preferred/default occupied by a proven foreign installation or fresh isolated root selects a bounded alternative. Legacy current instance stays at its recorded actual port. Read-only diagnostics do not allocate ports, rebind origins or modify mode. Unknown/foreign live same-data-root records remain refused.
- [ ] **Step 2: Add the cross-component RED seams.** Cover a real busy default socket, candidate bind race, existing ready/stopped/stale/foreign PID records, persisted non-default status/Doctor/logs/stop/restart, fixed Docker3081 occupied by another host service, actual inspect Web mapping mismatch, original accepted image preserved on candidate/endpoint publication failure, Native dynamic origin→Docker internal8088→Native with both control token values preserved. Mode selection and `--no-start` must not change control files; only actual quiescent startup may invoke the approved transaction.
- [ ] **Step 3: Integrate under existing locks and ownership checks.** Resolve validated endpoint metadata before constructing managers; legacy fallback is permitted only for missing metadata with consistent verified old records, never corruption. Reuse a healthy existing instance before allocation. Select real candidate(s) in the lifecycle transaction, rebind controls only after exact old/new installation quiescence, start actual services, verify listener+authentication+Web readiness, then publish successful actual endpoint metadata. On bind race, clean only this attempt's owned objects, prove absence, roll back its control changes and retry within a shared bounded budget (maximum3 attempts); unknown ownership or non-port failure does not trigger blind retries. Preserve old successful endpoints on restart failure. A default-port failure must not require stopping unrelated services.
- [ ] **Step 4: Fix Docker host-vs-container semantics.** `_ports_free`, stop release checks, mode switching and setup selection gates must concern selected host Web publication, not host3081. Keep installation/image/mount/launch-label checks, immutable accepted image and strict no-recreate/recovery behavior. Actual host mapping must match verified selected loopback endpoint; status/Doctor/browser URL report it. Native cross-mode probe uses the actual Native endpoint record and run-state identity rather than checking global default listeners. Explicit users sharing the same data root still need verified old-mode shutdown.
- [ ] **Step 5: Run focused GREEN, preserve old tests, then complete the source changed-set closure.** Use the project's existing planner and required gates, not a hand-picked claim. New CLI/docs/security configuration must appear in Doctor, installation docs and security/module references. Record commands, real outputs and non-run format/platform/remote gates; commit task files and return the short report contract. Do not perform external publishing or real service startup outside test-owned fixtures.

## Task 3: Current-source macOS acceptance, documentation and final review

**Files:** `.ai/reports/2026-10-06-macos-port-allocation-{plan.json,receipt.json,acceptance.md}`, docs/index closure; no product-source fixes in the controller session.

- [ ] Build the exact `05326b606..HEAD` complete delivered changed set plus these three evidence files; verify project runtime manifest hashes, execute current v3 planner and preserve its complete L0–L4/lane sets. Selected postponed platform gates retain their real status; separately record the human macOS phase scope.
- [ ] Reuse source-bound successful evidence only when code/input equivalence actually proves applicability. Run newly selected/uncovered gates; do not mechanically redo original Tasks1–12. Full branch/task review occurs via an immutable review package and no rerun of already reported same-source tests by the reviewer.
- [ ] Main session owns all actual macOS public-entrypoint tests, Docker build/run and test state. Use fresh task data/state/home with installed Docker Desktop plugin discovery preserved without copying credentials or changing the minimal environment filter. Never use daily data, OS Keychain or kill foreign8088/3081 listeners. Already successful locked base-image pulls justify one current-source build; any new build failure is classified by exact stage before retry.
- [ ] Native/Docker real installation,start,status,Doctor,health,restart,stop,start-again use selected free ports; inspect persisted endpoint records and both controls with secret values reduced to equality assertions, never printed. Nonsecret fixture survives Native→Docker→Native, private runtime state stays independent, Docker host3081 remains irrelevant, and ending/failure proves exact-owned listeners/container cleanup. Preserve old default behavior coverage; no mocked result substitutes for this lifecycle.
- [ ] Missing environment/Hook authority is recorded as the exact blocked step, not bypassed. User authenticates real vendor/model credentials only through normal setup; absence remains pending configuration.
- [ ] Validate schema-v2 receipt and record actual results. Local source acceptance/physical Mac phase and full global merge/release readiness are separate claims. No pushes, CI reruns/dispatch or branch/worktree/scratch deletion under this plan.

## Self-review

Tasks1→2 share endpoint/origin interfaces; Task2→3 shares implemented public entrypoints and immutable tested HEAD. Both relations are sequential, so no competing edit owners. Explicit requested ports remain strict while implicit defaults allow bounded fallback. Private controls retain old validators and token values; journal interruption is fail-closed rather than an invented successful recovery. Docker runtime port is internal only. Default compatibility does not require occupying daily default ports in physical tests. Same-data exclusivity and foreign-state refusal are not removed to satisfy auto-allocation.
