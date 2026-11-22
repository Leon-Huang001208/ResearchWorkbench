# Git backup v2 delivery — 2026-10-19

## Scope and authorization

macOS local Git safety tooling. Approved: independent deduplicated recovery points, seven-day retention plus newest two valid points, v1 compatibility/migration and daily automatic closeout. Source is isolated from the primary checkout. No business service, credentials, dependencies, live Git GC/repack, Docker image or data migration is changed.

## Implementation

- New shared immutable Git packs and SHA-256 file payloads; recovery points contain sealed metadata. No alternates, symlinks or hardlinks into the live repository. Unchanged state reuses an independently reverified point.
- Actual restoration preserves refs, explicit preservation anchors, index, binary staged/unstaged patches, raw tracked bytes, untracked files, symlinks and non-Git permissions. Other tasks' legitimate ref advancement is allowed; target state changes fail closed.
- Preview/apply maintenance uses a dedicated private backup lock. v1 migration retains the UUID path, validates original payloads, restores solely from shared data, commits durable metadata atomically, then rechecks and removes duplicate originals. Pending transactions protect payloads and can resume.
- Rotation preserves newest two/seven days and all unique unmerged or protected roots, unsaved/active content, isolated evidence and unknown records. Only unreferenced shared payloads are collected.
- Earliest v1 manifests without an index digest are readable under their original contract but retained, not falsely upgraded. Certified failed v1 evidence is preserved independently.

## Observed verification

- Initial red run failed because new maintenance exports did not exist.
- Focused tests grew from 7 to 18 scenarios. Final Git safety/closeout group passed 81/81 in 77.60 seconds, including concurrent bundle-only object preservation.
- Routing L4/full-delivery retained the unknown-boundary risk and required the existing Project Constraints CI. Full selected architecture/documentation/quota/cross-platform contract group passed 112/112.
- Documentation governance, Python file index, project constraints and syntax/diff checks passed locally.
- Independent TypeScript/JavaScript reviewer identified preservation-proof, metadata seal, unique unmerged refs, pending replay/GC and durability boundaries. Fixes and deterministic failure regressions added; final code review found no remaining blocking issues; fixed-SHA attestation follows the commit.

## Live operations

Read-only migration preview: 36 certified normal points eligible; 3 earliest index-less points, 2 failed v1 evidence directories and 2 unknown records retained. This is a changing live inventory, not a deletion receipt. No real backup migration has run yet. Legacy bundle-only concurrent objects are also retained and independently checked before original deletion.

## Remaining delivery

Final review, integration validation, PR/checks/merge and safe task closeout. Then use the merged entrypoint for actual local migration, record measured space and retained reasons, and update the existing daily automation to the seven-day policy. Do not report those phases as passed at this checkpoint.
