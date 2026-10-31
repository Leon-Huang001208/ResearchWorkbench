# Trial recovery successor: exact handoff and fresh retry

This is the versioned successor to the existing Native trial-retirement operator,
not another controller, research engine, or recovery loop. The product remains
fixed to `b800e50366d1a0868372bbf173822976066c143f` →
`db2ae9a48ceca365852072e622aa6627aa7d0b83`. Old v1 profiles and their limits remain
unchanged. Account deletion is a separate operation: the active retirement keeps
the original frozen account set and consent; it does not implement account cleanup.

## Exact predecessor

`handoff-trial-retirement` accepts only predecessor executor
`1529c3189b008b9861a2bee1511f051feefa76eb`, transaction
`90e13d10-96c2-4115-a062-c79d760b8fdd`, phase
`restore_sources_and_wheel`, version 4 / trial v1, with no retirement record or
terminal intent. Its original source, pyz/module map, consent, root transaction,
and private configuration are checked before handoff. The operator requires the
exact original journal SHA-256 **and** device/inode, not a prefix or a current
same-content replacement.

```sh
"$RWB_OPERATOR_PYTHON" -m research_workbench_entrypoint.resident.model_provider_upgrade \
  handoff-trial-retirement --home "$RWB_RESIDENT_HOME" --source "$RWB_QUALIFIED_SOURCE" \
  --handoff-journal-sha256 "$RWB_PREDECESSOR_SHA256" \
  --handoff-journal-dev "$RWB_PREDECESSOR_DEV" \
  --handoff-journal-ino "$RWB_PREDECESSOR_INO"
```

These variables bind an already qualified deployment and a controlled fresh
observation. This document does not authorize a deployment or supply live values.
The command has no arbitrary target, capacity, process, or source-common override.

## Small executor and durable handoff

The existing operator owns the supervisor/admission/operator EX locks, the real
installation lease, and the transaction's BirthFence/SQLite EX boundary. A clean
source revision must pass the real executor-byte check and `GitHubEvidence` for
both executor and fixed payload. The stage packages the resident Python closure
into the existing content-addressed recovery pyz/job family. Its manifest binds
executor version/revision, product source, and Git module blobs. Recovery verifies
the complete artifact, every module's Git blob, bounded zip membership, private
plist hash/arguments, and immutable stage receipt.

The new provenance directory is
`resident/artifacts/<db2>/executors/<executor-sha>/`; it does not reuse or change
the old `artifacts/<db2>/executor`. Stage reuse verifies qualification and reuses
the same immutable pyz instead of regenerating timestamp-dependent zip bytes.
The development checkout is not a runtime dependency; app dependencies continue
to come from the preserved, clean fixed-db2 product source. A staged-pyz manual
handoff authenticates that source before importing an older installed app wheel.

Under `resident/handoffs/<90e>/`, immutable files retain the staged candidate,
original journal bytes and identity, per-job stop intent/observation, and the
handoff intent. The old recovery job is quiesced before the old supervisor so it
cannot rewrite the frozen journal during a pre-CAS interruption. Only exact
known launchd jobs are considered; ambiguous PID/birth/argv/image/UID/children
or job observations reject the action. A durable stop intent is never permission
to resend an uncertain signal.

Current managed primary PIDs may differ from the old journal's original PID map.
The CLI verifies their actual managed identity under the lease, including birth,
argv, image, UID, PGID and listener ownership. It uses the existing
`_graceful_stop_owned_once` primitive for a single-PID TERM, persists a separate
intent, and waits for actual process and bind release, bounded at 90 seconds.
It does not edit the predecessor PID map, call public `stop`, send a process-group
signal, or infer idle from `active: null`. External Wind Terminal is not stopped;
native settlement remains `UNKNOWN`.

The new recovery backstop is verified before compare-and-replace publishes the
version-5 journal with the fixed `operator-authorized-trial-retirement-v2` mode.
The original root-candidate proof and reviewed product remain unchanged; fresh
executor/payload qualification is retained in the stage. This preserves the old
root transaction contract rather than bypassing its equality check.

## Resume and terminal ownership

Before CAS, invoke the same handoff command with the same original journal binding.
It reads the original immutable stage rather than requalifying/rebuilding it,
observes existing job/primary intents, and does not repeat bootout or TERM when the
outcome is uncertain. After CAS, the same command verifies the predecessor reference
in the v5 handoff and resumes the existing `execute(recovering=True)` transaction.
The scheduled new pyz uses the existing `recover` entry. A qualified staged pyz may
also run the handoff command without `--source`; its invocation, bundle, and stage
must match exactly. No developer checkout is adopted implicitly.

The first continuation is still BACKWARD: retire the authorized historical trial
data, preserve accounts/models/protected business data, and restore b800 code.
Only the new fixed mode, authenticated by the successor stage/handoff, passes
`archive_policy='rename-only-v2'` to the existing retirement engine. The frozen
v1 consent profile/digest remains unchanged. The versioned archive budget and
pre-copy manifest/full-journal checks are described in
[the retirement contract](research-web-trial-discard.md).

The old supervisor remains quiesced throughout recovery. Restoring it immediately
after acceptance would allow its old tick/bridge to recreate a primary after a
later crash. It is restored from its exact original plist only after a complete
immutable terminal receipt is verified and the root recovery-trigger journal has
been removed, before the gateway journal is removed. Failure preserves recoverable
ownership. Terminal recovery keeps the original result, performs no BACKWARD or
new spawn, and releases only its own verified BirthFence namespace.

Spawn intents remain fail-closed: an unconfirmed spawn is not adopted from a
temporarily missing PID file or free port. Pending acceptance requires manual
reconciliation; it is not a second-spawn retry.

## Fresh deployment after completed retirement

An explicit `apply-trial-retirement-v2 --trial-terminal-receipt ...` is a new
transaction. It requires the exact immutable completed original successor receipt
with b800 code rollback and committed retirement, actual no-new-work validation,
new qualified executor/payload, unchanged explicit authorization binding, and the
fixed db2 quarantine marker's raw hash. It does not delete quarantine or invoke
the old controller's retry/tick path. Ordinary automatic rejection remains intact.

Fresh control records live only under `resident/handoffs/<fresh-uuid>/`. Their
context freezes stage/previous receipt/consent/quarantine/configuration identities;
mutable spawn attempts and PID maps are not part of that context. Each gateway
or managed primary generation has its own precise durable stop intent. Fresh
gateway retirement first preserves the new recovery backstop, quiesces the exact
legacy supervisor, then boots out the exact recorded gateway generation and proves
job/listener/bind closure. Primary retirement reuses the same single-PID primitive.
An unloaded supervisor with a matching durable intent is an observable interrupted
state, not a reason to bypass validation or replay a stop.

The b800 recovery receipt and later db2 deployment receipt represent separate real
outcomes. Local synthetic tests, source/CI success, and staged artifacts do not
prove the live site, authenticated entry parity, native cleanup acknowledgment,
model output quality, or account-cleanup completion. Those remain separate evidence.
