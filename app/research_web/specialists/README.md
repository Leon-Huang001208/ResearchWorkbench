# Specialist collaboration business ledger

This module holds account-scoped role definitions, validated research plans, and
durable attempt/budget records. DSH remains the only execution and transcript
engine. `SpecialistLedger` accepts an existing `Store`; browser/model inputs
cannot choose its account root or session directory.

State lives in private `Store.root/specialists/<owned-session>/ledger.json`,
outside the model-writable session workspace. Descriptor-relative file access,
exclusive process/thread locking, fsync and atomic replacement reuse existing
DataHub storage primitives. Corruption, symlinks and failed writes fail closed.
No PostgreSQL, provider connection, new dependency, scheduler or execution loop
is introduced.

The Host binds current verification, reconciliation, cancellation and report
projection to the active receipt's `specialist_run_id`. After a completed run
hands off to an ordinary delivery, its retained ledger is historical; ordinary
cancellation cannot mutate it or block that ordinary report. Switching a UI mode
alone does not detach a still-bound unresolved run or authorize a new send.

The persisted envelope and projected control response are both checked against
the fixed 4 MiB capacity before a new write. The specialist bridge uses that
same bounded limit; ordinary DataHub responses keep their 1 MiB default. Full
legal plan histories remain complete rather than silently truncated.

## Contracts

- `create(sid, budget, as_of, model, request_id, skills=...)` freezes explicitly confirmed
  token/request/concurrency/time/revision limits, non-secret model identity,
  cutoff date, immutable maintainer role digest and actual published Skill
  versions. Each Skill entry is the Host-resolved public selection subset
  (`id`, `version`, `kind`, `native_name`, `sha256`, `resource_path`) plus
  `resource_snapshot_sha256`. Node prompts name the effective selected/default
  native Skills and snapshot paths and require loading via the native Skill
  tool. The Host separately verifies actual native tool traces; a prompt is not
  proof of loading. Missing frozen methods prevent dispatch.
- `read(sid)` returns business state without receipts or filesystem paths.
- `apply(sid, operation, payload, agent_id=..., call_id=...)` applies one
  idempotent trusted operation. A replay returns `replayed: true`; it never
  authorizes sending another native/provider request.
- `resume(sid, confirmed=True)` grants a one-use continuation permit only after
  live/unknown attempts and unknown provider usage have been reconciled. The
  next `create` records a linked run; previous runs and consumed usage survive.

The graph requires industry, descriptive quant and independent review. Review
must transitively depend on both other roles. At most two revisions invalidate
changed nodes and their downstream results. Invalidation/cancel receipts never
prove native termination: replacement remains blocked until trusted terminal
observations. Late results are retained but excluded from the current plan.

`reserve` persists the child identity before native submission. A separate
`dispatch` operation fsyncs intent immediately before the actual native call,
allowing an interrupted sender to distinguish a reservation from an attempted
submission. Host-only `confirm_not_submitted` requires actual idle/terminal
parent and complete child-catalog absence evidence, and accepts only reserved
attempts with no dispatch intent or child model requests. Dispatching, accepted
or unknown attempts never become safe to retry merely because a child is absent.
Cancellation preserves the previous submission phase. A cancellation requested
while still reserved may use the same strict absence proof only when
`cancelled_from_status` remains `reserved` and no dispatch/model evidence exists;
repeated cancellation and recovery cannot erase or upgrade that phase proof.
`accepted`,
`submission_unknown` and `terminal` are trusted-adapter operations, never public
model completion claims. Native terminal observations carry the actual lifecycle
`run_id`; restart reconciliation instead supplies a separately named history
observation (`kind`, child id, turn/end sequence, event SHA-256 and turn). A
history digest is never relabeled as a native run identity. Corroborating
observations cannot overwrite an existing result or its original provenance.
Completed outcomes also require a Host-qualified `evidence_snapshot` mapping
every referenced evidence/artifact id to the SHA-256 of its canonical current
bytes or dataset manifest. The Host rechecks these bytes before reuse,
admission, resume and final validation. `invalidate_evidence(sid, attempt_ids)`
invalidates the affected dependency closure, preserves historical outputs,
requests cancellation of live dependents and blocks automatic replay. A
matching reference name alone never proves that its content is unchanged.
`model_request` reserves a caller-proven safe total
token bound for every actual root/child provider request; only measured native
`model_usage` settles that reservation. Missing usage remains unknown. Node
dispatches are not counted as provider calls. A confirmed continuation does not
renew the original token or request allowance.

The six-field node result is structurally checked here. Actual source/manifest
and artifact qualification belongs to the Host's existing evidence and research
quality gates. `ready_for_validation`/`finalization_ready` mean ready to enter
those gates, never an accepted final report. Source availability and model text
alone do not establish PIT or backtest eligibility.

The execution deadline applies to admission and completion, not later reading
of an already finished report. Once every current node has a qualified result
and every actual model request has measured usage within the deadline,
`completed_at` is persisted. Later reads and observe-only recovery retain that
ready state; first qualification after the deadline cannot retroactively claim
timely completion. Missing or partial usage stays `null` with its reservation;
only explicit measured zero counts are recorded as zero. The root and every
successful child must each have an actual measured native model request; a
missing child request record is never interpreted as zero usage. Linked reuse
retains the prior verified requests under the same original child identity.

Offline regression: `python -m pytest tests/research_web/test_specialists.py`.
Native cancellation/settlement, model spending, browser and platform evidence
remain separate acceptance layers.

## Evidence content versions

`evidence.evidence_snapshot(service, sid, result)` returns a SHA-256 map keyed by
the original evidence/artifact reference. The trusted terminal handler stores
this map as `attempt.evidence_snapshot`; the model does not supply it.
`verify_snapshots(service, sid, state)` re-reads successful attempts and returns
the IDs whose references can no longer be proven. The Host must invalidate
those attempts and their downstream closure before reuse or finalization, and
request native cancellation for any affected live descendants.

Upload and output references use actual bounded `Store.open_file` reads, not
file IDs (which identify paths). Fetched web bodies cannot be relabeled as
uploads: `stored_sources` rechecks their Host-owned content hash and provenance,
and the snapshot also binds title, URL, publication/acquisition metadata and
retained body bytes. Conflicting publication dates or dates after the frozen
cutoff fail closed; acquisition time never becomes historical publication proof.

Dataset references use the actual scoped `Snapshots.detail/read` interfaces to
verify the private/public manifest binding, then hash every declared public
file and private raw response through descriptor-relative reads. Any changed or
missing raw response, manifest/provenance change, clue-only admission, unknown
account ownership, or source-scope exclusion rejects reuse. Ordinary dataset
captures require retained raw originals; Hot's archive kind retains originals
as declared public archive objects instead. Total evidence bytes are bounded
at 64 MiB per node and dataset lists at 512 files. These limits are explicit
failure states, not truncated evidence.

These fingerprints prove identity of retained bytes and provenance only. They
do not certify the truth of a source, numerical correctness, completeness,
historical PIT, or strategy backtest eligibility. Those decisions remain with
the existing Host research quality gates. Missing legacy fingerprints invalidate
old successes rather than silently assigning today's bytes to an old result.

Offline regression: `python -m pytest tests/research_web/test_specialist_evidence.py`.
