# Docker resource queue current-base integration

## Scope and retained history

This is the macOS feature-development continuation of `docker-resource-queue-20261019` and original PR #140. The current phase starts at `466f2d198aa8885ac94180d06551f7dd3fe5a40e`; the published head `95984b9ccf17dcd2228d28c42da3dc7c1bd87e59` and later unpublished prepared head `33d7db6e0f951bb1ab71d5ffff5c51eb8b4851a0` are retained through a normal merge. The latter contains ten subsequent commits, including owned test and CI diagnostics fixes. Upstream changes in that history are not treated as new queue functionality.

The original receipt, refs and old worktrees remain unchanged. Its one historical CI repair remains spent; the new phase's zero counter is not the cumulative total. At most one further CI repair is available under the original two-repair limit. Recovery refs and a verified incremental history bundle preserve the unpublished source; uncommitted old worktree state has not been certified or retired.

## Current contracts

- Retain durable task/worktree/source/refresh identity, FIFO admission, explicit unknown outcomes, committed source archives and lock-held resource rechecks.
- Preserve current stage ownership, owner handoff, registration recovery, immutable image IDs and runtime/development labels. `docker/manage.py` is unchanged. A wrong-role completed cache is invalidated without rebuilding it.
- Frozen source context applies to both builds; preserve the current `rwb-development:development` tag and inspect error handling.
- Distinguish a preflight resource refusal from a failed build. A build-start or owned-cleanup observation takes precedence over resource-like words in build output; a failed build must not become an automatic resource retry.
- No Docker RAM change, global restart, protected-resource stop, new dependency or scheduler is part of this source integration. The historical 12 GiB proposal is not a current configuration claim.

The modern CI partitions, complete existing test selections and sanitized node-ID/JUnit evidence remain intact; only the queue module is added to the existing Python selection. The unpublished deadline regression retains real executor/drain assertions with deterministic fixture timing. The old verbose CI diagnostic is superseded by the current evidence path rather than restored.

## Verification routing

Three exact queue/entrypoint paths now select the existing L4 Docker packaging contract instead of unknown-path fallback. The independent Asset History test path has a focused L2 suite without widening the existing asset-workbench closure. Existing Docker and platform gates remain; the macOS task explicitly supplements the existing Mac Bootstrap and Docker Desktop responsibilities. Linux/Windows product acceptance remains with the respective machines, and Mac does not dispatch their product workflows.

## Evidence status

Development checks are WIP evidence, not final-SHA acceptance. Recorded local checks include a complete 51-case synthetic queue suite on the final WIP module, five selected deadline cases, and their own retirement receipts; 77 policy tests, 43 verification framework tests and 140 static Docker/architecture/governance tests. The final candidate and exact test set are recorded by the managed delivery receipt and bounded task evidence after integration.

Shell syntax, Ruff, Black, isort and the new module's focused mypy check passed. Normal mypy following package imports fails with 16 diagnostics in seven unchanged imported files; the same diagnostics were reproduced by checking the unchanged package entrypoint. This is retained as a failing baseline check, not relabeled as a whole-project typecheck pass.

Actual queue/build execution, cold build, health, mixed load, remote CI, merge, deployment and old-worktree retirement remain NOT_RUN at this report's preparation. Synthetic Docker fixtures do not certify the daemon, image availability or resource headroom. Later acceptance must use the existing resource lock and owned objects; no replacement home, builder or source is used to bypass a reservation or unknown result.
