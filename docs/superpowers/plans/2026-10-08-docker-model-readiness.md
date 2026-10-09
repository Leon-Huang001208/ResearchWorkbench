# Docker Model Readiness Implementation Plan

> **For agentic workers:** Use subagent-driven-development task-by-task, one implementer at a time with spec review before quality review. Preserve this one real task identity and worktree; no nested agents.

**Goal:** Deliver the approved macOS Docker model-credential and text-research/recovery scope, with true live evidence only after separate authorization.
**Architecture:** Add a model-purpose adapter over existing safe file primitives; keep Native Keychain, fixed DSH, existing Service uncertainty and one runtime product. Bind Docker backend/root/stable installation identity through the owned launcher and private cross-language bridge.
**Tech Stack:** Existing Python3.12, Node24, fixed DSH, FastAPI, Compose; no dependency additions.

Base b352ffa304c0b17c3260ed9417f083aac0fedf64. Worktree `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/docker-text-research-20261008-a1`. Python tests use existing `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python`, not a new install. Node tests use `/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`.

## Task 1: Model-only private file store and Python bridge

**Files:** Create `app/research_web/model_file_store.py`; modify `app/research_web/model_credentials.py`; extend `tests/research_web/test_model_credentials.py`. Read `credential_backend.py`, `runtime_state.py` and `05-security-validation.md`; shared backend remains unchanged.

- [ ] Add closest RED tests for a Docker store factory, fixed namespace, same-install persistence, distinct-install isolation, Native describe compatibility, forbidden request extras/refs, modes/owner/symlink/hardlink/oversize rejection.
- [ ] Use actual temp POSIX roots and real file operations; inject OS faults only for otherwise nondeterministic pre/post-replace errors. Test complete records rather than mock existence.

```python
def test_docker_model_factory_exists():
    bridge = load_bridge()
    assert callable(getattr(bridge, "docker_backend", None))
```

- [ ] Run `python -m pytest tests/research_web/test_model_credentials.py --confcutdir=tests/research_web -q --junitxml=logs/model-readiness/task1-red.xml`; inspect actual missing-feature failures before implementation.
- [ ] Implement `docker_backend(root, installation_id)` and a fixed-purpose `DockerModelStore`: reuse pinned directory/lock/read validation, write a staged0600 inode and replace only after old-inode recheck; preserve old record on precommit failure; do not unlink published destination on postcommit uncertainty. New namespace is model-only and install-ID-bound, not DataHub or dataHome-derived.
- [ ] Extend `execute(data_home, request, backend=None)` so default Native behavior is byte-compatible and factory-selected Docker describe reports `docker-private-file`. Keep the exact request allowlist and private resolve result. Private bridge CLI accepts explicit controlled backend/root/ID; Docker requires Linux and the exact managed model leaf, Native rejects Docker-only binding. Isolated -I import of shared primitives uses only the trusted product source root, not ambient PYTHONPATH.
- [ ] Run the full nearest module and `test_credential_backend.py`; record RED→GREEN, concurrency, serialization failure and pre/postcommit negative evidence. Update fixed model namespace/source/error docs and report, then commit only this reviewed slice.
- [ ] Spec review then Python/security quality review; implementer fixes findings before dependent tasks.

## Task 2: Cross-language and owned launcher binding

**Files:** `runtime/model-credentials.mjs`, `launch_runtime.py`, `docker/supervisor.py`, `compose.yaml`, `research_workbench_entrypoint/docker_runtime.py`; tests `research_web_model_credentials.test.mjs`, `test_runtime_launch.py`, `test_container_supervisor.py`, `test_docker_runtime.py`, `docker_runtime_contract.test.mjs`.

- [ ] Add RED cases where a Docker describe source currently rejects, unknown sources remain denied and the bridge receives only nonsecret fixed binding fields.

```js
assert.deepEqual(await provider.describe(MODEL_REF), {
  configured: false, source: 'docker-private-file', writable: true,
});
```

- [ ] Pass stable `RWB_INSTALLATION_ID` explicitly as nonsecret container configuration. Validate it against the accepted installation and owned inspect contract; supervisor binds model leaf/source/ID, launcher writes private overlay fields. No inference from containerID/fixeddata path, no mount/permission guard relaxation.
- [ ] JS accepts only the two approved sources and verifies launcher-selected source; private spawn remains -I/-B with stripped environment, pipe and output bounds. Key never in argv/env; keep Host record implementation delegated.
- [ ] Run the exact affected Python/JS modules with XML/logs, then spec and TypeScript/Python/security review. No image reuse claim until current source image is actually built.

## Task 3: Service, settings, Doctor and free application recovery

**Files:** `app/research_web/service.py`, `research_workbench_entrypoint/platform_capabilities.py`, `app/research_web/ui/settings.mjs`; existing `tests/research_web/test_api.py` model configuration/recovery cases, `test_protocol.py`, `test_platform_capabilities.py`, `tests/javascript/research_web_ui.test.mjs` and nearest existing navigation/settings renderer cases. No parallel model-configuration test framework.

- [ ] RED-test public storage enum `docker_private_file`, missing/backend-unavailable settings access, blank retention, explicit replacement/delete, parent/child active-task denial, uncertainty marker and no secret in public output.
- [ ] Add only corresponding source/status projection; do not alter existing configuration uncertainty transaction or introduce a second state framework.
- [ ] Using existing fake-backed tests, execute setting→research task→persist→fresh service restoration; include auth/network errors, cancellation and repeat submission. No production dummy Provider or paid call.
- [ ] Run selected closure and document test-only versus actual evidence; review before physical tests.

## Task 4: Existing verification and live-control integration

**Files:** `.agents/verification-policy.json`, `.github/workflows/research-web-checks.yml`, existing launch/live-acceptance guard; closest policy/workflow/live-control tests.

- [ ] RED-test that actual ordinary runner commands include model credential Python tests and appropriate runtime tests, not merely matching paths. Unknown/high-risk and other-device gates remain selected as policy requires.
- [ ] Extend existing controls only for an explicitly bound isolated Docker text acceptance installation. Preserve ordinary3081 denial, retry limits and actual request count; cap tokens/fees within independently approved budget across restart/recreation. Do not enable model calls from health/status/settings save.
- [ ] Validate full changed set through current Git-bound planner and manifest hashes. Run selected policy/workflow/guard tests; no Windows/Linux dispatch or expensive matrix.

## Task 5: Current-image and bounded real acceptance

**Files:** task logs/reports only; existing public installation, CLI, settings/API and live-acceptance entrances.

- [ ] Obtain any required locked test-directory install/build authorization before package installation. Create new private test data/credential/HOME, installation identity, image and ports, separate from old task resources.
- [ ] Build current-source image using public installer; record SHA/imageID/architecture/host/identity/ports, then verify DSH/Web/HTML/static/Doctor and setting availability without Key.
- [ ] With canary credentials, verify set/retain/replace/delete, install isolation, permissions and reboot/recreation using public API; never store raw canary in evidence output surfaces.
- [ ] Request separate real-Key/live budget authorization when ready. User enters Key in the task settings page, not chat/command/log. Run research, cold read, controlled restart, same-session continuation, same-image recreation and final stop/release. Missing authorization leaves live items NOT_RUN/PARTIAL, not overall PASS.
- [ ] Browser no-open/open-idle/actual-stream scenes each once; one targeted same-failure repeat maximum. Record exact stage/state and safe remediation, no client kills or timeout/ownership bypass. Preserve unresolved scene limitation as a follow-up rather than fabricated fix.

## Task 6: Docs, complete acceptance and genuine delivery

**Files:** README, installation/support/security/runtime/data/API docs and inventory, generated index, `.ai/reports/2026-10-08-docker-model-readiness.md` and plan/receipt.

- [ ] Record distinctions among healthy container, backend available, configured, real request, text recovery, sandbox, integration and platform. File permissions are not encrypted vault security. Native file fallback, Linux script sandbox, Windows ACL, host bridge and registry release remain excluded.
- [ ] Replan the full actual changed set with failure signals when triggered; execute fixed required local doors and macOS install CI when authorized, retaining all other-platform handoffs. Do not change old receipts.
- [ ] Read actions-budget and visibility before any push/PR/merge. Use this same managed task ID; do not infer new publication/paid/cleanup authority from design confirmation. Preserve partial actual model status if no live evidence.
- [ ] Only after authorized real integration/CI and safe evidence archive, use managed cleanup and actual same-ID require-delivery hard gate. Goal completion requires the original live-text Done criteria, not only free tests.

## Self-review

Tasks1–3 implement GoalA/B free-chain, Task4 covers C and bounded acceptance controls, Task5 covers B live and D, Task6 covers E/Done. Sources/ref names/backend strings and stable identity are consistent. Unsafe filesystem/postcommit paths, private stdio, lack of secret output, Native no-fallback, actual test execution, live budgets and unchanged owned lifecycle are explicit; no second framework or original-goal redo.
