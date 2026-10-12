# Foreign Native Ledger Lifecycle Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven-development. One bounded implementer, then independent specification and Python/security quality review; no nested agents.

**Goal:** Complete the original macOS Native/Docker lifecycle with authenticated
different-root product listeners, without stopping the daily instance.
**Architecture:** Existing stdlib private PID reader and real target lifecycle lease
retain/recheck a call-local different-root observation. No serialized authority,
new runtime framework, network probe or permissive flag.
**Tech Stack:** Python 3.12 stdlib, existing private filesystem/lifecycle helpers,
current pytest/Node policy and v2 receipt.

## Task 1: Capture and validate the existing foreign pair

Owner: the isolated foreign-native-root-ledger worktree, baseline d2a0015c.
Production scope: research_workbench_entrypoint/{web_bootstrap,web_contract,
bootstrap,docker_runtime}.py; app/research_web/service_manager.py;
scripts/setup_web.py only if the install selection integration requires it.
Prefer a small shared internal unit in existing stdlib modules; no new public
interface or independent verifier. Closest tests are test_web_bootstrap,
test_web_contract, test_service_manager, test_runtime_mode, test_docker_runtime,
test_setup_web and test_cli_lazy. Existing docs, generated index and .ai report
must describe this real boundary, not an environment-root attestation.

- [ ] Read those source/module contracts and the approved spec before edits.
- [ ] Extend existing private-state fixtures to form a complete different-root
  pair using their actual existing version/command/fingerprint/signature schema.
  Keep target Native records absent and product root existing; preserve the
  current default product listener observations. Add the closest expected case:

  ```python
  first = controller.start(open_browser=False)
  assert first["ok"] is True
  second = controller.start(open_browser=False)
  assert second["ok"] is True
  assert second["ownership"] == "verified"
  ```

  The fixture must drive the existing reader, not mock Native.status to idle;
  normal container execution remains the existing explicit subprocess fixture.
- [ ] Execute RED with approved existing test Python and current PYTHONPATH:

  ```bash
  PYTHONPATH=. /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest tests/research_web/test_docker_runtime.py tests/research_web/test_web_bootstrap.py --confcutdir=tests/research_web -q
  ```

  Record real failures and matching cause, not an environment error as RED.
- [ ] Add only bounded OS-standard-root discovery and shared capture/recheck
  using existing reader, validators and private descriptor helpers. Never spawn
  another checkout to prove facts. Preserve current private-record/argv/start
  validation and reject every candidate if complete binding cannot be obtained.
  The mutation predicate remains this conjunction:

  ```python
  lease.assert_held()
  allowed = different_canonical_roots and exact_private_pair and unchanged_process_facts
  ```

  These are validated captured facts, not caller-supplied booleans. Ownership,
  scope and lease identity are mandatory; cleanup is bound to the scope's finally.
- [ ] Add actual negative fixture interleavings: same root, alias, malformed or
  missing role, record/root replacement, extra listener, PID reuse, argv/start
  changes, false/external/lost lease and transfer to another controller.
- [ ] Rerun GREEN with the same module boundary and retain output/duration.

## Task 2: Close public lifecycle integration

- [ ] Reuse the shared observation in Native absence/quiescence, its stdlib
  fallback and normal bridge, Docker control/selection and runtime switching.
  All old same-root and unknown-writer negative assertions remain.
- [ ] Add closest lifecycle regressions, including pre-stop refusal when safety
  cannot be re-established:

  ```python
  assert controller.start(open_browser=False)["ok"] is True
  assert controller.restart(force=True, open_browser=False)["ok"] is True
  assert controller.stop()["ok"] is True
  assert controller.start(open_browser=False)["ok"] is True
  ```

  Use existing controller fixture semantics, no fabricated Native endpoint.
  Add first switch to Native only after its genuine installation preflight;
  insufficient facts must leave the healthy Docker object untouched.
- [ ] Preserve original error/rollback/CAS and secret redaction. Do not remove
  or recreate existing stopped containers to get a new binding.
- [ ] Generate the complete actual changed set via existing planner, with
  unexpected_behavior/validation_failure retained. Verify all 11 kernel hashes,
  run L0→selected L4 gates, scoped Ruff/Black/isort and related mypy attribution.
  Report original baseline debt separately; never fake PASS or omit selected gates.
- [ ] Update existing installation/runtime/security/module docs, index and task
  report, then validate the new v2 receipt. Needed CI stays NOT_RUN/BLOCKED.
- [ ] Commit only owned implementation/tests/docs locally; report immutable SHA,
  changed set, exact tests/durations and remaining concerns. No real services,
  package installs, global modifications, remote operation or other worktree edits.
- [ ] Main independently verifies spec first, then Python/security quality;
  repair findings before integration or physical acceptance.

## Task 3: Main-owned real acceptance and closeout

- [ ] Freeze the reviewed source; keep all previous branches/worktrees/records.
- [ ] Run public locked install/normal CLI in task-only HOME/checkouts. Confirm
  default daily processes remain owned and untouched while Docker allocates a
  free host port. Check install/start/status/Doctor/root/static, idempotence,
  authorized force restart, stop/start, actual state/credential permissions.
- [ ] Create only non-secret fixture through public API and verify same session,
  attachment/content after Docker→Native→Docker and Native→Docker→Native, with
  token/extra fields preserved and auth re-established by normal startup.
- [ ] Wait for every command terminal result before dependent mutations. On
  a repeated unchanged failure stop retries; preserve exact failure and blocker.
- [ ] Update whole integration/original-goal plans from c24a8a16 and 4d6a4eff
  to final HEAD, documenting source-affinity reuse rather than editing old proof.
- [ ] Read actions-budget/current visibility only before a focused remote
  authorization request, after independent local work ends. Do not push/PR/merge/
  dispatch/rerun/tag/release or clean preserved worktrees without authorization.

Self-review: one product/lock, no desktop or other host adaptation; the approved
different-root proof is distinct from fresh creation and cannot grant same-root
writer access. All safety, negative testing, public lifecycle and evidence boundaries
map to the tasks above; no optional downgrade of the original necessary gates.
