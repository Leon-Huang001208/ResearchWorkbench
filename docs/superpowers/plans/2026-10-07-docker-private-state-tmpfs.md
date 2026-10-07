# Docker Private State Tmpfs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement the single tightly coupled repair with specification then quality review. Do not spawn nested agents.

**Goal:** Make Docker runtime authentication state identity stable without weakening its safety guard or changing persistent research/credential/log storage.
**Architecture:** Fixed /state private tmpfs plus original host logs child bind at /state/logs; retain all existing controller ownership and auth protocols. Remove the failed state-write initialization. No named volume or migration.
**Tech Stack:** Existing Python3.12 stdlib/controller, Docker Desktop/Compose, fixed image, pytest/Node contracts and current verification v3/v2.

## Task 1: One isolated mount/state repair

Owner: one fresh implementer in the existing macos-dual-runtime-acceptance worktree.
Allowed source: compose.yaml, research_workbench_entrypoint/docker_runtime.py,
docker/supervisor.py; Dockerfile/entrypoint only if exact configuration needs it.
Existing .github/workflows/research-web-docker.yml fixture preparation may only
add "$root/state/logs" to its existing private10001:10001/0700 install command,
because direct Compose intentionally cannot create the bind source. No trigger,
runner, matrix or remote workflow execution changes.
Tests: existing test_docker_runtime.py, test_container_supervisor.py,
test_docker_packaging.py and docker_runtime_contract.test.mjs.
Docs: README state/storage bullets and existing readme-review.json only as
required to remove stale host-auth-state claims; ARCHITECTURE/DEVELOPMENT_MAP,
research-web-installation, architecture
01/02/03/05, generated index only when needed, one .ai/reports task report.
No edits to main's three macos-port-allocation report/plan/receipt files.

- [ ] Read related module contracts and current source before edits. Confirm HEAD
  981e20f10 and preserve all existing untracked work. No installs or real services.
- [ ] Add closest failing tests: exact tmpfs spec, logs source child binding,
  mandatory state/tmp/home mounts; inspector refuses missing/duplicate/wrong
  type/source/RW and wrong state uid/gid/mode/options. Existing data and credential
  binds unchanged. Use existing inspector fixture and public controller tests.
  Example new expected contract:

```python
assert state_mount == {"Type": "tmpfs", "Source": "", "Destination": "/state", "RW": True}
assert logs_mount["Source"] == str(controller.state_dir / "logs")
assert logs_mount["Destination"] == "/state/logs"
```

- [ ] Execute focused RED with the existing interpreter, retaining actual failure:

```sh
PYTHONPATH=. /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest tests/research_web/test_docker_runtime.py tests/research_web/test_container_supervisor.py --confcutdir=tests/research_web -q
node --test tests/javascript/docker_runtime_contract.test.mjs
```

- [ ] Implement the exact approved spec. Compose state bind becomes logs-child
  bind; state tmpfs is appended, fixed option string below. Inspector captures RW
  and HostConfig.Tmpfs; compare semantic options strictly, reject unknown or
  duplicate contradictory options, preserve image/install/launch checks. Host
  preparation validates/creates only the private logs child with existing APIs.

```text
/state:rw,nosuid,nodev,noexec,uid=10001,gid=10001,mode=700,size=1m
${RWB_STATE_DIR:?Set RWB_STATE_DIR}/logs → /state/logs (bind/create_host_path=false)
```

- [ ] Remove ineffective initialize_state feature and its live call, replacing
  obsolete tests with strict state preparation/no exceptional ownership change
  tests. Do not modify generic runtime_state.py or auth/health protocol. Preserve
  credential/data first-creation checks. No chmod/chown repairs or auth prewrite.
- [ ] GREEN and relevant dependency closure: existing Docker/controller/mode/setup,
  supervisor/launch/auth/credential/packaging tests; Docker and L4 architecture,
  governance/quota/repository JS. Generate changed-set plan with original failure
  signals, execute selected local gates, validate honest blocked external receipt.
  Read docs/index/constraints; document old state retention and restart reauth.
- [ ] Commit only owned files locally, report exact SHA/diff/hash, measured results,
  retained RED/failures, limitations and parent checkout preservation. No push.
- [ ] Independent spec review, then specialized Python/JS and security quality
  review of the immutable patch; fix confirmed findings before physical testing.

## Task 2: Main-owned physical acceptance and existing goal closeout

- [ ] Wait all writes/commits and reviews before switching the stopped task test
  checkout; preserve existing successful session106746f3-4612-4192-a69f-b49b6bea2743
  and CSV075d5a82d5196171ba5590fd/SHA47ad7335dab05dd4668880628ab1fdbee1f1fd9642a4cd160484f167353912eb.
- [ ] Public approved locked setup Docker --no-start, one exact-source build; record
  terminal accepted image. No repeated unchanged failure or global environment fix.
- [ ] Real start/status/Doctor/health/root/static, restart/stop/listener release,
  start-again/reauth; inspect tmpfs/logs/data/credential metadata without secret
  values. Dummy credential via existing file backend only, no vendor call/Keychain.
- [ ] Real healthy Native→Docker→Native same session/CSV roundtrip and in-memory
  control token/extra-field comparisons; final owned test stop, no data deletion.
- [ ] Update complete original4d6a4eff and feature05326b606 changed sets/current
  planner, 19 local evidence reuse/affected reruns, schema-v2 receipt and full
  branch review. Latest-master integration follows original Task14, preserving
  upstream authentication unit and feature branches. No old evidence rewrites.
- [ ] Mac CI only after concentrated exact remote authorization and budget/visibility
  preflight; no push/PR/merge/tag/dispatch/rerun/cleanup is authorized by this plan.
  Entire goal stays incomplete until applicable evidence is genuine.
