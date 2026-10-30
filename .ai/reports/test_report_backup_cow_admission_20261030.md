# Backup copy and admission — bounded primitive checkpoint

Date: 2026-10-30. Host: macOS. Task:
`backup-cow-admission-20261030-7c9d4f2a`.
Status: SOURCE_LOG_REPAIR_UNVERIFIED; the original Git contract suite exposed
regressions after the earlier local slice passed. New execution is capacity-blocked.
Complete backup phase admission remains unimplemented/unverified.

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

## Integration SPEC correction and real regression

The b84 checkpoint's independent SPEC found a P2: the inherited launcher check
preceded the primitive's complete source hash, leaving an observable pre-spawn
drift window. The fixed primitive now invokes a trusted rejection-only
`beforeSpawn` guard after that hash and immediately before spawning. Only literal
true proceeds; an explicit veto occurs before helper execution and may lose the
optimization, while possibly executed outcomes retain post-check unknown and no
retry. The callback cannot create toolchain records or grant authority.

Two plain-data RED cases used a nonexistent interpreter path, so no helper or
changed executable ran. The former API ignored the new veto, producing the
wrong unavailable classification; those failures remain in `p2-red-node24.log`.
GREEN ran with exact Node 24.19.0 over the two direct suites: 29 PASS, one explicit
NOT_RUN for production inheritance. Test/worker PIDs exited, 35 tiny fixtures
were retired, retained logical bytes totalled 44,800 and peak retained bytes were
3,072. Python helper/test blobs did not change and their earlier exact evidence
is retained, not relabelled as newly rerun Python acceptance.

The RED/GREEN tool call completed before a later pause message was delivered.
That ordering is recorded exactly; no log was rewritten to imply a subsequent
window ACK preceded execution, and no repeat was performed merely to change the
timestamp. The prior bounded-data authorization and actual free-space floors
remained satisfied. The independent execution-sentinel lane blocked by provider
safety review remains stopped and is not substituted by these refusal tests.

## Same-candidate CI registration

The original Project Constraints Git safety step retains all existing files and
adds the two direct Node suites. The original macOS Bootstrap environment step
runs those small suites using its own freshly installed venv Python, plus the
standard-library unittest helper checks. Relevant maintenance file paths select
that existing Mac workflow. No job, runner, dependency, timeout or other-platform
product dispatch was added. New test-only `RWB_BACKUP_TEST_PYTHON` is explicit
and absolute; no Homebrew path is treated as portable or as production TCB input.
The successful execution of these edited workflows is still NOT_RUN.

The first full changed-set Project Constraints invocation retained four failures:
three missing verification-workflow module documents and its missing structure
decision. Those documents and this explicit decision were then supplied without
removing any changed path or altering the policy. Final constraint execution and
exact-candidate quality remain separate from the earlier failed invocation.

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"This slice adds optional FD-backed data copying and explicit single-file admission within the existing managed Git delivery toolchain. It retains all existing backup/restoration gates and reuses existing CI steps; no service, research engine, workflow runner, model authorization or deployment topology is added. Whole-phase capacity and real cleanup remain unqualified.","diagrams":[]} -->

## Remaining design gate

The additional unchanged three-file Git suite actually executed 219 cases with
exact Node 24.19.0: 199 PASS, 20 FAIL, zero skips, 425.97 seconds. Nineteen
failures exposed a real regression: per-file snapshot events wrote into the
source worktree before the final capture comparison, producing BACKUP_RACE.
The other failure exposed an incomplete real Python-boundary fixture copy after
new static imports were added. Logs and source hashes are retained under
`logs/backup-cow-admission/old-git-contracts-b74/`; the peak synthetic footprint
was 780,661 bytes and the owned process group was confirmed absent afterwards.

The narrow repair directs snapshot events into the current private backup
point's logs directory, preserving the original repository/HEAD metadata. The
internal destination is not accepted through CLI/options. Root/directory/file
identities, privacy and no-alias checks apply, writes are fsynced and closed,
then the journal hash enters manifest.files. Existing V2 migration imports those
bytes into its shared store and restore/hash chain. Original source capture,
restoration and final project PASS/FAIL logging remain in place. The fixture
copies its three new static dependencies; original assertions remain, with
additional journal isolation and migration checks.

The attempted focused pre-repair rerun was refused before spawning: free space
had fallen below the 3 GiB start floor, then below the 2 GiB run reserve. Test
child count was zero. This source repair and its new assertions are NOT_RUN;
neither the earlier 11 local gates nor static reviews certify the changed code.
No full backup, protected point 51b, shared pool or production operation was run.

Existing store copyChecked already uses a clone hint, which can silently fall
back. The V1 snapshot now attempts an optional pinned-FD clone and admits its
single-file stream fallback. It retains the FD/path/hash/mode/race/fsync checks,
fsck and actual restoration. Unknown checkout transforms/hooks/templates, pack growth
or temporary allocation cannot become a guessed total from pack/payload length.

Independent b74 JavaScript quality found one P2 in the new tests: Darwin-only
clone branch assertions had also been registered in Ubuntu CI. The test-only
repair marks those five branch cases NOT_RUN outside Darwin, preserves the
portable stream/arithmetic/capacity/TCB tests, and asserts the platform's actual
unavailable classification. No product guard, CI step or old test was removed.
The exact Node 24.19.0 Mac integration rerun passed 20 cases with one explicit
production-inheritance NOT_RUN; all 23 fixtures and both owned PIDs finished,
maximum fixture size 2,400 bytes. Linux/Node20 execution remains NOT_RUN until
the unchanged standard Ubuntu CI actually runs the new candidate.

Read-only audits are under the canonical project's
`logs/controlled-recovery-coordination/backup-cow-admission/`. This checkpoint
does not claim V2 peak admission, PR250 cleanup, full Native, deployment or
research-model acceptance is fixed.
