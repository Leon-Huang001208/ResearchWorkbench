# Runtime-agnostic core reconciliation

Date: 2026-09-09

## Recovery and scope

The former `AlphaFoundry-runtime-agnostic-core` worktree is being reconciled as a ResearchWorkbench branch. Before changes, all repository refs were captured in a verified Git bundle and all 1,830 Git-untracked paths were captured in a separate archive. Only the three Python DSH adapter/deployment files and the six TypeScript plugin source/metadata files were promoted from the untracked set; Graphify output, caches, build output, and unrelated generated artifacts remain in the external recovery quarantine.

## Merge decisions

- Kept the current ResearchWorkbench Workspace/Session/Provider/Skill/Agent routes and added the runtime-neutral workflow and legacy FinGPT bridge routes alongside them.
- Kept desktop notification initialization and the recovered FinGPT initialization.
- Preserved both the current platform contract documentation and the runtime-neutral contract documentation.
- Rebased the recovered runtime ledger migrations after the existing ResearchWorkbench `015`–`018` chain: runtime workflow ledger is now `019`, and FinGPT governance index is `020`.
- Kept the current fail-closed Alembic configuration test and changed the expected single head to `020`.
- Added `**/graphify-out/` to `.gitignore` so generated Graphify caches do not return as untracked source candidates.

## Local verification

- Python compilation passed for the recovered API, contracts, repositories, services, DSH adapter/deployer, and migrations.
- JavaScript syntax checks passed for the merged application entry point and commentary module.
- The existing DSH plugin TypeScript compiler completed with no errors.
- `git diff --cached origin/master --check` passed for the reconciled changes.
- Python unit tests could not run locally because no project virtual environment exists and the system Python does not include `pytest`; no dependency was installed. Native GitHub CI remains mandatory before this branch can be cleaned up.

The first project-constraints CI run rejected two recovered service modules because their earlier implementation did not meet the repository's explicit logging and exception-boundary rule. The repair adds validated descriptor registration logging and a workflow execution boundary that records a safe failed status, logs both execution and failure-status persistence errors, and re-raises the original exception. A regression test asserts the durable failed status.

## Platform boundary

This reconciliation changes runtime, migrations, web behavior, and desktop packaging inputs. macOS and Windows native CI evidence is therefore required. A real Windows installation-level smoke test remains a release prerequisite and is not claimed by this branch reconciliation.
