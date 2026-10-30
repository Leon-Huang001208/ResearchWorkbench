# Backup copy and admission — bounded primitive checkpoint

Date: 2026-10-30. Host: macOS. Task:
`backup-cow-admission-20261030-7c9d4f2a`.
Status: SNAPSHOT_INTEGRATION_LOCAL_GREEN; exact integration reviews and routed
closure pending. Complete backup phase admission remains unimplemented/unverified.

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

The primitive checkpoint `6d5ada52` received independent SPEC, JavaScript/TypeScript
and Python quality approval, limited to that primitive. A basename diagnosis based
on escaped tool text was rechecked against the actual source and withdrawn; no
correct regex was changed. The review retains Node's loss of helper errno as a
P3 diagnostic limitation. Windows/Linux native evidence remains NOT_RUN.

## Snapshot integration checkpoint

The owned existing snapshot caller now has a clone fast path and an explicit
single-file stream admission using actual destination statfs available blocks,
BigInt accounting, block rounding, a stated metadata allowance and the unchanged
run reserve. This is not a mathematical bound for checkout, pack, index-pack,
APFS metadata or other concurrent writers. A growing source cannot write more
than its admitted pinned size through the snapshot-only stream branch.

The generic strict Python resolver remains strict. Homebrew's group-writable
ancestor and CLT's root/wheel group-writable ancestors were not silently trusted,
repermissioned or treated as interpreter certification. The narrow alternative
inherits the existing managed CLI toolchain TCB: only a same-operation, originally
necessary and successful real resourcePhase invocation of the preselected exact
absolute Python may issue a process-private repository/task/operation record.
Lexical link bytes/lstat and canonical launcher facts/hash are checked before and
after. Standalone, skipped, failed, probe and injected-controller paths do not mint
records. No extra real resourcePhase was run to acquire one. These launcher facts
are not proc_pidpath, kernel Python.app or standard-library/ACL attestation; the
existing host-toolchain management principals remain an explicit TCB assumption.

Before-invocation drift loses the optimization; potentially-after-invocation drift
remains unknown and cannot retry through stream. Only unsupported with no target
may use the original stream after sufficient single-file admission. Existing source
FD/path/mode/identity/race/hash and private-target/fsync checks remain required.

The final direct integration sample ran with exact Node 24.19.0: 20 PASS and one
explicit NOT_RUN for real production toolchain inheritance. Earlier Node25 runs
were retained as auxiliary evidence and were not relabelled Node24. All 23 tiny
fixture roots were reclaimed; total logical sample bytes were 25,901, maximum
retained bytes 2,400, and the test/worker PIDs exited. Source and runtime files
outside this isolated fix were not changed. Logs are under
`logs/backup-cow-admission/integration/`.

Independent exact integration SPEC and quality, complete changed-set Router,
full backup capacity admission, production inheritance and PR250 cleanup remain
open. No claim of a completed whole-backup fix is made from these local results.

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
