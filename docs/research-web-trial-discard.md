# Historical trial retirement and configuration preservation

## Controlled operator

The existing Native operator gains `apply-trial-retirement`, fixed to the reviewed
`b800e50366d1a0868372bbf173822976066c143f` previous product and
`db2ae9a48ceca365852072e622aa6627aa7d0b83` target product. Its reviewed executor
revision is separate from the product wheel. The operator requires a private
`--trial-manifest`, its canonical `--trial-manifest-sha256`, and a private
`--trial-backup-parent`, in addition to the existing `--home` and `--source`.
The digest is the maintenance module's canonical JSON digest, not a claim of
approval contained in arbitrary model output. This command is not a research API.

The authorization binds account/root identities, trial session IDs, model settings
and protected non-trial configuration. Normal termination may change only the
recognized trial lifecycle fields. The actual stopped state has a separate exact
backup seal. Known RWB processes are revalidated before signals; an unconfirmed
identity or termination remains fenced. External Wind Terminal is not retired.

`trial_retirement` archives the owned session directories and retires associated
automation/report producers, preserving their exact data for fenced manual
recovery. Ordinary product rollback retains the committed user discard decision;
it does not restore enabled trial producers or replay model requests. Unknown
producer relationships, new work, or replaced directory identities reject mutation.
Complete terminal receipts are retained before active journals are removed.

Recovery uses the existing `recover` command and transaction. A crash after a
spawn but before its identity is durably recorded remains fenced for operator
reconciliation; it does not trigger a second spawn. Manual restoration of trial
data stays offline and fenced. Source tests and CI are not live deployment proof.

## Preservation helper

`research_workbench_entrypoint.resident.trial_discard_backup` provides a bounded preview and an exact-file, same-filesystem backup for a separately authorized retirement of historical trial sessions. It is a library for the existing resident maintenance transaction, not a deploy command or a deletion engine.

The caller must already hold the resident maintenance exclusion fence, establish exact account ownership, and prove that the verified old Host is stopped with no remaining writers before backup or retirement. The helper does not infer this from `active: null` or any other Host status. `preview(home)` reads the primary `research-web/index.json`, `server/accounts.sqlite3`, `server/resident.json`, and every registered account's `server/users/<UUID>/research-web/index.json` when present. For each primary or account data root, it also checks the fixed optional `report-workflows/catalog.json`. Each root's `catalog` result is `{"status":"missing","directory":"missing"}` when no report-workflows directory exists, `{"status":"missing","directory_identity":[dev,ino]}` when the directory exists without the file, or `{"status":"present","directory_identity":[dev,ino],"identity":{dev,ino,size,mode,mtime_ns,sha256},"workflow_count":N,"run_count":N}`. The preview seal covers these states and the full catalog file hash. It returns session IDs, counts, known status labels, file identities and hashes, but no workflow prompt, model values, credentials, or session bodies. It rejects unknown directories, malformed mapping, symlinks, oversized files, more than 64 account roots, more than 512 MiB of aggregate source files including catalogs, and a SQLite journal/WAL. The database query is immutable and read-only after journal exclusion.

`backup(home, backup_parent, expected_seal)` requires a protected `0700` backup parent on the same filesystem, no symlinked ancestor, at least 2 GiB of free space after reserving twice the aggregate source bytes, and an unchanged preview seal. Free space is measured from the pinned backup-parent directory descriptor. Creation uses pinned directory descriptors and no-follow, exclusive file creation. It copies the account database, binding record, each present owned index, and each present owned report-workflows catalog. It verifies every copied byte and mode, then restores each copy into an isolated temporary file and compares bytes and mode again. Files and touched directories, including the manifest and backup parent, are synced before the receipt. The saved `manifest.json` contains expected file hashes, sizes, modes, and the source seal; the receipt includes its SHA-256. A drift, directory swap, low-space condition, failed sync, or partial copy refuses the operation. A partial backup remains protected for inspection and never receives a successful receipt. Because model settings are contained in the business indices, full index bytes preserve them while the preview exposes only a settings hash.

This helper does not remove sessions, clear Wind `UNKNOWN` markers, alter account or model configuration, stop or start processes, take the maintenance fence, establish idle, or grant deployment. It backs up only the database, binding, business indices, and present report-workflows catalogs. It does **not** back up `sessions/`, `runtime/home/sessions/`, dossiers, or other session artifacts covered by the full preservation scope. The caller must bind the sealed backup receipt to its maintenance journal and separately preserve any artifact it plans to retire, with a proven restoration path. A `restore_verified` receipt proves only this backup's byte and mode recovery; it is not live restore, deployment, or product acceptance evidence. The exact live state and actual restored behavior require separate verification.
