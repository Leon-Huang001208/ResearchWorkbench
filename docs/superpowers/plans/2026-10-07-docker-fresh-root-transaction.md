# Docker Fresh Root Transaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven-development. One bounded implementer, then specification and code/security review; no nested agents.

**Goal:** Repair actual first Docker installation/start under a new private HOME without stopping unrelated default-port services or requiring Native first.
**Architecture:** Existing lifecycle lease and filesystem identity support RAM-only missing/new-root proof for selection and start. No serialized authority, no new runtime abstraction.
**Tech Stack:** Existing Python3.12 stdlib bootstrap, private filesystem and lifecycle helpers, pytest and Node verification contracts.

## Task: Missing-root selection and genuine first creation

Owner: /Users/leon/.codex/worktrees/docker-fresh-install-proof/ResearchWorkbench.
Allowed source scripts/setup_web.py, research_workbench_entrypoint/{bootstrap,
docker_runtime,runtime_mode,web_contract}.py; existing shared pure helper only if
needed, not generic guard/lifecycle safety weakening. Tests existing setup_web,
docker_runtime,runtime_mode,web_bootstrap/web_contract/cli_lazy modules; logs/report
and matching existing install/architecture/module docs. No primary or managed
feature changes; local merge will follow review. No services/installs/remote writes.

- [ ] Read module source/docs before edits; preserve merged master auth unit.
- [ ] Write genuine closest failing tests for valid venv plus absent root with
  real unrelated default product observations. Assert no-start does not create
  product data/control/endpoints, then actual standard Docker start creates it.
  Example invariant: `assert not controller.data_dir.exists()` after no-start.
  Include pinned-parent/lease and existing unsafe-root refusal negatives.
- [ ] Execute RED with original approved interpreter/PYTHONPATH=current checkout
  and --confcutdir=tests/research_web; keep actual failure cause and counts.
- [ ] Implement exactly the design via existing stdlib and pure helpers. Missing
  root observation cannot authorize a later call; real mkdir/inode/lease proof
  only authorizes this transaction, checked before use and invalidated at spawn.
  Failed-start rollback remains exact attempt-only, not another allocation bypass.
- [ ] GREEN focused and policy-selected dependency closure; full own changed set
  planner with failure/unexpected signals, 11 kernel hashes, docs/index/constraints
  and schema-v2 receipt. Missing external/platform proof stays NOT_RUN/BLOCKED.
- [ ] Commit only owned source/tests/docs/report locally. Report SHA/diff/counts,
  proof of untouched primary/managed feature/actual test HOME, real risks.
- [ ] Independent spec, Python/JS where affected and security reviews; fix findings.
- [ ] Main merges this verified local branch into managed Task14 feature, prepare
  controller once, then executes genuine new-HOME public Docker install/start and
  impacted merged Native/Docker lifecycle. Do not restart unchanged failed builds.

No git reset/rebase/cleanup, synthetic PID/endpoints/manifests, altered global
proxy/Harness/kernel/policy, new dependencies, auth prewrite, port-tool swapping
or default-service shutdown. Other platforms/desktop remain outside Mac scope.
