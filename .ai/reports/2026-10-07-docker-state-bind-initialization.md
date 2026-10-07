# Docker state bind initialization — implementation prerequisite

Host: macOS. Task: Web Docker functional repair in the existing isolated worktree.
Base: `2a137b4244db24030bd5d21ab827e66bf38d50be`.
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Add only a scoped ephemeral state bind initialization before existing authentication consumers; deployment nodes, persistent state schemas, auth protocol, dependency graph, host ownership checks and global runtime guard remain unchanged.","diagrams":[]} -->

## Current state

Parent approved using the existing managed host controller and fixed
Compose/image/private-layout chain as the initialization trust prerequisite.
The production implementation is local and pending final gates/review. No Docker
operation, dependency install, remote write or real state mutation has been
performed. The existing unrelated untracked parent reports are preserved.

The proposed initialization must be restricted to the fixed state leaf under a
verified Docker configuration and existing controller ownership/single-instance
checks. The guest supervisor currently receives paths but no explicit mount
identity proof. Its `_prepare_private_leaf` uses a fixed-path allowlist plus
retained directory FD checks. Those checks cannot independently prove a bind
mount or absence of another writer. The host controller checks immutable image,
known containers and Native inactivity before Compose up; actual new-container
mount inspection occurs after up. The approved prerequisite is the existing
managed Compose/controller chain, not a new guest-consumable mount proof. No
new proof protocol, mount checker or public initialization switch is introduced.

## Actual RED evidence

Closest regression added to `tests/research_web/test_container_supervisor.py`:
existing legal 0700 leaf; first file creation deterministically changes only
its immediate parent's projected UID/GID from root pair to runtime pair.
The unchanged guard rejects the reproduction. The current preparation returns
without settling the mapping, and subsequent strict access rejects again.

Command (cwd is the isolated worktree):

```sh
PYTHONPATH=. /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest --confcutdir=tests/research_web tests/research_web/test_container_supervisor.py -k existing_state_leaf_initializes -q
```

Result: `1 failed, 74 deselected in 0.50s`; `RuntimeStateError`, diagnostic
`identity_changed/post_yield/ancestor/changed=uid,gid/root_pair_to_runtime_pair/parent`.
Earlier exploratory expected-keyword seam failed with TypeError; replaced with
the original API and actual strict guard failure before any production edit.
These deterministic failures do not identify the real Docker write or prove
that the proposed initialization cures the actual startup failure.

## Existing baseline acceptance

```sh
PYTHONPATH=. /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/native-docker-dual-runtime-20260929/.venv/bin/python -m pytest --confcutdir=tests/research_web tests/research_web/test_container_supervisor.py tests/research_web/test_runtime_launch.py -k 'not existing_state_leaf_initializes' -q
```

Result: `205 passed, 1 deselected in 24.08s`. This is the existing baseline only;
the final changed implementation was subsequently checked separately below.

Planner was run for supervisor, closest test and this report with
`--signal unexpected_behavior`: L4/full-delivery, unknown-boundary preserved,
Linux CI gates selected. No platform/CI PASS is inferred. Both original RED and
later architecture gate failure are retained, with validation_failure and
unexpected_behavior signals in the final complete changed-set plan.

## Implementation and local evidence

`_prepare_private_leaf` now accepts internal `initialize_state=False`; only normal
`run`, after timeout/config validation and before controls/auth/Popen/probe,
enables it when data/state/credential/project/DSH source match the fixed managed
layout. Existing leaf must have current UID/GID and exact 0700, be a real pinned
directory, and match its initial named inode. Default calls, custom paths,
existing credential/data/log leaves, prepare-only and health do not initialize.

Existing ancestor walking and parent verification are reused. One random empty
file is created with O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC and 0600 under the retained
leaf FD. Held/named temp must have the same dev/inode/mode/UID/GID, zero content,
regular type and nlink=1 before unlink. Only the fixed parent complete root pair
to different runtime pair may be rebased during creation; all other nodes and
dev/inode/mode remain strict. Failure attempts cleanup only of the exact safe
empty inode and keeps unknown replacements; cleanup failure has a fixed warning
without replacing the original validation failure. After cleanup the original
unmodified runtime_state_directory repins and checks the stable baseline.

Actual checks:

- Focused GREEN: 32 passed, 74 deselected in 0.28s. Includes stable/mapped,
  dev/inode/mode, reverse/foreign/mixed pair, held/named mismatch, ancestor/leaf
  changes, wrong leaf GID, root-pair overlap, actual node replacement, temp
  replacement/hardlink/non0600/content, create/cleanup failure, after-init
  strict rejection, custom/credential/log/default-readonly no-create, run order,
  invalid timeout, prepare-only and readonly probes.
- Six-module Python closure: 387 passed in 26.36s. Exact modules:
  test_container_supervisor, test_runtime_launch, test_credential_backend,
  test_runtime_auth, test_docker_packaging, test_runtime_contract; invoked with
  the same Python/PYTHONPATH/--confcutdir and `-q --tb=short` as above.
- L4 JS/Docker-static closure: 104 passed, 0 failed, 2354.565417ms:
  docker_runtime_contract, research_web_architecture, documentation_governance,
  actions_quota_governance, repository_cross_platform_contract (`node --test`).
- Documentation governance initially PASS: 552 files, 79 current, no violations.
- Python file index PASS (0.967s wall), git diff --check PASS.
- Initial five-path Constraints/architecture/doc-sync FAIL: missing installation,
  02/03 module documentation and meaningful review marker. Requirements were
  satisfied with concise matching contract notes and this task's marker; no
  gate was weakened. Final eight-path Constraints PASS (0.034s wall),
  architecture/governance/index all PASS in the subsequent doc-sync PASS command.
- ruff/black/isort/mypy are absent in the authorized interpreter: NOT_RUN;
  no dependency was installed.
- Managed verification manifest: 11 files, zero hash mismatches.
- Final complete eight-path Planner: L4 with both preserved signals. Seven local
  validation IDs covered; three selected external merge gates remain NOT_RUN.
  Durations for Python and JS validation IDs refer to their shared composite
  command, not separately measured per-module/per-ID times; do not sum them.
- Receipt validator initially rejected escalationRequired=true for a non-failing
  local result and missing per-gate risk IDs. Receipt metadata was corrected to
  no further escalation at L4 and explicit external_gate_not_run IDs, preserving
  the prior failure signals in the plan. Final schema-v2 validator exit 0:
  valid=true, result=BLOCKED, planned/actual=L4, mergeReady/releaseReady=false,
  executedCount=7, externalCount=3, realMachineCount=0.

Exact local plan/receipt artifacts (outside the source changed set):
`/Users/leon/Desktop/Projects/ResearchWorkbench/.git/state-init-evidence.Fd7aav/plan.json` and `/Users/leon/Desktop/Projects/ResearchWorkbench/.git/state-init-evidence.Fd7aav/receipt.json`.

Unverified: real Docker rebuild/start, real mount mapping, cookie exchange,
macOS clean installation/GitHub CI, Windows/Linux actual runtime acceptance,
and independent security review. Deterministic GREEN establishes only the
scoped initialization behavior; it does not certify the actual startup root
cause or that the real failure is cured. Selected external gates remain NOT_RUN,
mergeReady=false and releaseReady=false.
