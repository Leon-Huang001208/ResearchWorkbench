# Docker resource lifecycle and bounded cleanup

Host: macOS / Docker Desktop. Task: feature development and local cleanup; no remote publication.
Base: f32d6993a (origin/master at task start). Isolated branch: codex/docker-resource-lifecycle.

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Resource inventory and disposal are host-side developer tooling using the existing Engine CLI and lifecycle/install locks; no product service, port, data schema or Web/DSH deployment topology changes.","diagrams":[]} -->

## Implementation

- Readable development/test resource names and full revision/build/ownership labels; verified legacy Compose identities remain compatible.
- Default-preview, exact-ID disposal with policy/reference rechecks, shared installation locks, durable item journal and fail-stop errors.
- Offline readonly/no-copy source backup, SHA-256, actual temporary-volume restore and tar content comparison before original volume deletion.
- Current installation and previous accepted image protection; failed publication restores the prior rollback receipt.
- Task-owned helper creation/build/run/finally disposal; explicit image VOLUME tmpfs prevents implicit anonymous volume leaks.

## Verification and current execution

Resource policy and opt-in live catalog: 16 pytest cases and 9 subtests PASS, including real content restore, failed helper, interrupted create, task image naming/disposal, malformed preview rejection and unconfirmed-create timeout handling.
Python reviewer: deletion/publication lock and rollback recovery reviewed; no remaining HIGH/CRITICAL findings after no-copy mount repair.
The initial broader Python catalog found absent Web dependencies plus two obsolete name assertions. All packages were separately user-authorized and installed only in the task verification environment, using the existing Web lock. Final frozen-source Python catalog: 936 cases and 9 subtests PASS (186.29 seconds). Node catalog: 126 PASS. Ruff/Black/isort: PASS.
Host Git remains optional: missing Git or archive checkouts explicitly produce unknown revision with warning, preserving the stdlib host installation contract; targeted naming/build tests: 7 PASS.
Cleanup: PASS, 38 containers, 32 volumes and 30 images deleted. All 32 archives restored/file-compared before deletion and SHA-256 rechecked afterwards; archive files are private. Both disposal plans were replayed with already-absent outcomes and no new deletion.
Remaining: 1 unidentified probe container and its volume, 2 conservatively retained application image candidates, 3 base images and 2 images of unconfirmed provenance. Build cache is retained. Docker-reported image storage moved from 28.4 GB to 4.628 GB; this is not a measurement of host filesystem space reclaimed.
Mypy is NOT GREEN: focused baseline and changed legacy modules have the same five existing errors; broader imported closure reports 59 errors. The new resource module passes its focused check. No inherited error suppressions or mandatory checks were removed.

## Evidence and boundaries

Evidence: worktree `logs/`; user deliverables under `/Users/leon/Documents/Codex/2026-10-12/doc/outputs/`.
Backups: `/Users/leon/.research-workbench/migration-backups/docker-cleanup-20261012/`, private and retained.
Build cache ownership cannot be isolated and is retained. Unknown resource provenance is retained.
The standard Native installation was already stopped with stale state before this task; no claim of healthy startup is inferred from status or cleanup.
New application-image full rebuild, macOS CI, Windows/Linux verification and remote publication: NOT_RUN.
