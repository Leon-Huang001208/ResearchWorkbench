# Legacy branch reconciliation

Date: 2026-09-09

## Recovery prerequisite

All ResearchWorkbench refs were captured before reconciliation in the verified bundle `research-workbench/research-workbench-all.bundle` under the external recovery inventory. Dirty worktrees and untracked files were separately archived or moved into the external quarantine before their worktrees were removed. No force-push or forced worktree removal was used.

## Patch-equivalent branches

`git cherry origin/master <branch>` reported every commit below with `-`, which means its patch is already represented in the current default-branch history:

- `codex/dsh-web-ui` at `17407bd4808f0f9ce663f72d13b8eb056598b0f7`
- `codex/dsh-web-runner` at `4f97ba143c18fbd08c8cf1282ce9d1873c0969c0`
- `codex/dsh-web-delivery` at `74b2da4dd75903f5df3566a005b3b81e916185cd`

The retirement merge records those original commits as ancestors without applying their already-present diffs again.

## Superseded DataHub branch

`codex/datahub-cjpy` at `2d9a36e10987a9a1c5efd30dd2512c154c142c75` is not patch-equivalent, but its implementation belongs to the superseded merged-platform monolith. Applying its tree would introduce a second DataHub route/service/repository stack, a conflicting `019_add_datahub` migration, a vendored binary CJPY wheel, and a root dependency pin.

The current master instead contains the later session-isolated Research Web DataHub in `app/research_web/datahub/`, the bounded optional CJPY Provider, safe connection projection, immutable session snapshots, DSH-facing `datahub_*` tools, and tests for catalog, CJPY readiness/query behavior, cancellation, and connection handling. Current migrations `019` and `020` are already assigned to the runtime workflow ledger and FinGPT governance index. The legacy branch's own delivery report also records that its native CI was never run and its Harness hard gate remained blocked.

For those reasons, the branch is retired with an `ours` merge: its commit remains reachable in default-branch ancestry, while none of its obsolete source tree, migration, dependency, or binary artifact replaces the current implementation.

## Verification contract

The retirement merge must leave the working tree identical to current master except for this report and the changelog entry. Project constraints, `git diff --check`, branch ancestry checks, remote CI, delivery cleanup, and Harness delivery enforcement remain mandatory. Desktop sidecar/Tauri validation is outside the current Web-only phase and is not triggered by this documentation-and-history-only delivery.
