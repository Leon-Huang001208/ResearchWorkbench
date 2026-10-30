# Verified backup copy and capacity admission

Host: macOS functional recovery fix. Base: `e732918a`. Task:
`backup-cow-admission-20261030-7c9d4f2a`.

## Observed failure and limits

PR250 is merged, but final managed cleanup failed with `COMMAND_FAILED` after
the v1 backup stage, while disk space became critical. The underlying errno was
not captured; ENOSPC is not a proven root cause. Point 51b remains a protected,
restore-verified v1 point. It is not a completed v2 point. No live cleanup replay
or mutation of that point/shared pool is part of this implementation.

Existing `copyChecked` already requests a clone hint, which may silently fall
back to a physical copy. `snapshotRegularFile` uses an identity-pinned source FD
and a streaming exclusive target FD. A path-based clone must not replace that
identity boundary. The verified source payload is approximately 1.17 GB, in
addition to a 244 MB pack; repeated source/staging/verification copies overlap.
Logical bytes alone do not certify the physical peak.

## Minimal implementation contract

1. Add a narrow optional Darwin FD-clone primitive using the system-provided
   `fclonefileat` interface through existing Python standard-library ctypes.
   Pass only inherited source-file/private-directory descriptors and a single
   destination basename. No dynamic source, arbitrary command or dependency is
   accepted. Missing/unsupported capability preserves the existing FD-stream
   fallback, subject to its full capacity admission.
2. Preserve every existing source FD/path/inode/owner/mode/timestamp/race check,
   independently validate the new target as a regular non-alias file, verify full
   bytes, and retain fsync and exact restoration. Neither hardlinks nor live Git
   alternates are an acceptable substitute for an independent copy.
3. Distinguish confirmed clone from stream fallback. Never treat a clone hint,
   sparse-file logical size or a single free-space sample as proof of physical
   availability. A failed or ambiguous operation must not silently become a
   second write attempt.
4. Add phase admission using explicit measured inputs on the actual destination
   filesystem. Known file sizes are accumulated without unsafe numeric
   conversion. Uncertified checkout transforms/hooks/templates, unknown expansion
   or missing measurement remain fail closed; the implementation must not invent
   a complete bound from pack length or payload length alone.
5. Restore semantics, original bytes/modes/index/dirty state, hash, fsck and actual
   restoration remain mandatory. Platform fallback is verified separately;
   unexecuted Windows/Linux native evidence remains NOT_RUN.

## Verification and delivery

- Reproduce missing clone/admission contracts with bounded synthetic files only.
- Test exact FD identity, source independence, exclusive destination, unsupported
  clone and sufficient/insufficient fallback budgets, race/error retention,
  integer overflow/unknown measurements and phase refusal before large writes.
- Keep each local sample below the coordinated 20 MB budget and check the real
  3 GiB start / 2 GiB run floors. Stop rather than weakening resource gates.
- Independent SPEC followed by TypeScript/JavaScript and Python quality reviews
  cover the exact final diff. Execute the actual changed-set Router closure.
- Use the original managed Git delivery chain for this new isolated fix. No hot
  patching, system configuration, new package installation, production/SDK/Office
  operation, PR250 receipt edits or full backup replay is permitted here.

The capacity design must explicitly document its proved bounds and remaining
unknowns before integrating any admission that could authorize a large phase.
