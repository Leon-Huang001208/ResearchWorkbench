# Backup copy and admission — bounded primitive checkpoint

Date: 2026-10-30. Host: macOS. Task:
`backup-cow-admission-20261030-7c9d4f2a`.
Status: FD_PRIMITIVE_LOCAL_GREEN; independent reviews and capacity integration pending.

This task does not replay PR250 cleanup, modify its receipt or alter recovery
point 51b/shared storage. The earlier COMMAND_FAILED lacks an observed underlying
errno. Disk pressure and copy amplification are observed; ENOSPC is not certified.

## Implemented primitive only

The new Node/Python helper invokes Darwin's existing fclonefileat with inherited
source/private-directory descriptors and a single destination basename. It uses
isolated standard-library Python, no dynamic source, arbitrary command, path-based
source copy, fallback or removal. Unsupported differs from error/unknown. The
future caller retains source-path race checks and must admit stream capacity.

ACLs/xattrs/flags that cannot be safely preserved are rejected. Full source/target
bytes, FD identity, private target mode, owner, nlink and fsync are checked. This
does not certify a whole backup, physical peak or stronger Node openat semantics.

## Actual local verification

- Initial missing-API RED and OS/environment corrections are retained under
  `logs/backup-cow-admission/fd-primitive/`.
- Node: 7/7 passed, including actual small Darwin clone, independence, exclusive
  targets and error-result retention.
- Python: 7 pytest cases plus 5 subtests passed. An unknown asyncio config warning
  from disabling unrelated plugins remains visible; no overall gate is claimed.
- Ruff, Black, isort and normal mypy with explicit package bases passed.
- Final test PIDs were waited and independently absent. Largest source sample:
  1,536 bytes; conservative per-run sample bound below 100 KB, under 20 MB.

Independent SPEC, JavaScript/TypeScript and Python quality remain pending.
No existing backup caller changed. Windows/Linux native evidence is NOT_RUN.

## Remaining design gate

Existing store copyChecked already uses a clone hint, which can silently fall
back. The V1 snapshot still streams pinned FD bytes. Integration must preserve
all FD/path/hash/mode/race/fsync checks, fsck and actual restoration, and explicitly
admit fallback capacity. Unknown checkout transforms/hooks/templates, pack growth
or temporary allocation cannot become a guessed total from pack/payload length.

Read-only audits are under the canonical project's
`logs/controlled-recovery-coordination/backup-cow-admission/`. This checkpoint
does not claim V2 peak admission, PR250 cleanup, full Native, deployment or
research-model acceptance is fixed.
