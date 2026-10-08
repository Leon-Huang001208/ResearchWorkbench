# Hot internal engine

This package is under implementation. It is not yet a supported product entry.
The authoritative stage record is `.ai/reports/2026-10-07-hot-events-PROGRESS.md`.

## Web Host and workspace checkpoint

`app/research_web/hot_service.py` lazily bridges Host calls to the owned manager,
with four admitted threads and a bounded deadline. Timeout/cancellation retains
capacity until the actual thread finishes; closing refuses waiting admissions.
No Hot daemon/database/model is started by Web lifespan or GET. Existing Host
same-origin controls apply; explicit writes also require X-Research-User-Action,
JSON <=64 KiB, typed operation fields and a UUID for conditional writes. Keys and
database passwords stay in the Host's current-mode credential backend.

The same UI now provides #/workbench/hot (events/sources/channels) and
#/settings/hot (non-secret config and explicit lifecycle). It escapes publisher
text, validates external URLs, separates scores, shows unknown dates/timezone,
origin revisions and coverage, and offers existing correction types. Material
selection persists across report pages by canonical id/revision; detail pages
reuse their own cutoff. Unknown writes keep the exact body/UUID for explicit
retry; page changes, filters and late details cannot replace newer results.
Config edits remain advanced JSON; initial setup still uses the documented CLI.

Host/renderer tests and an actual browser disabled-settings journey are recorded.
That journey intentionally uses an offline research-runtime fixture because its
isolated data root has no DSH auth installation; it proves Hot-unconfigured UI
availability, not a clean installation, real event browsing or research. Native
model readiness/cache replay now uses the normal worker factory; follows, briefs,
frozen research handoff and installed authorized-worker acceptance remain pending.

## Authenticated event/channel API

The existing signed `rwb-hot/v1` loopback transport now exposes these internal
operations to the authorized Host. Instance/mode/generation, deadline, request UUID
and read/control keys remain mandatory. Browsers do not receive these keys.

| Operation | Permission | Parameters |
| --- | --- | --- |
| `channels` | read | optional cutoff |
| `events.list` | read | channelId, cutoff, q/topic/institution/asset, from/to, sort, limit/offset, minRelevance |
| `event.detail` | read | eventId, cutoff, reportLimit/reportOffset |
| `channel.configure` | control | channelId, expectedVersion, config |
| `event.correct` | control | reason, change (existing title/merge/split/reassign/channels contract) |

Lists are bounded to 50 entries, details to 50 material versions per page and 20
history entries. First responses return a fixed cutoff; pagination beyond offset
zero must reuse it. Publication ranges use trusted publication times, not event
acquisition/update times. Topic/institution/asset/keyword filters are literal text
matching against the event title and frozen reports; they do not claim structured
entity tags. Percent/underscore are literal, never wildcard or SQL instructions.
Sorting supports recent observation, heat, importance, increment or relevance.
Channel lists default to relevance >=1; zero/pending scores remain inspectable with
minRelevance=0 or the all-event list. Manual membership can include an event by
default, but never overrides a user-specified relevance threshold.

Reads use only evidence/configuration/judgments available at the cutoff, resolve
merged IDs to their historical canonical event and return explicit origin score
versions for inherited human decisions. Detail contains immutable material id,
revision/hash, original URL, publication/acquisition/source-update times and
declared partial excerpts. It never fetches, schedules or generates. Web/CLI
mounting is implemented; real event browser acceptance and richer full-history navigation remain pending.

Migration 13 adds immutable channel-control audit. Only the controller can make
conditional changes or replay its UUID; identical canonical parameters return the
original response, conflicting reuse rejects. Corrections reuse the same protected
event audit. After transport timeout/untrusted response/late owner guard failure,
the Host preserves the UUID and retries identical parameters rather than inventing
a new request.

## Native CLI projections and corrections

After Hot setup/start, the public entry supports:

```sh
./rwb hot channels --json
./rwb hot events --channel macro --sort importance --json
./rwb hot event <event-id> --json
./rwb hot channel-configure gold --expected-version 0 --file services/hot/channels.example.json --json
./rwb hot event-correct --file correction.json --reason "Operator review" --json
```

Use actual versions from the read response; version zero is only for a new channel.
The channel file may be a direct configuration object or the version-1 channels
bundle; the command selects its named channel. Correction files use the existing
title/merge/split/reassign/channels contract, including source expected revision
and target expected revision when applicable. Files are bounded, regular and
alias-free, read locally, and contain no credential fields. For example a title
file is `{"type":"title","id":"<event UUID>","expected":1,"title":"Reviewed title"}`.

Events accept --query/--topic/--institution/--asset, publication --from/--to,
--cutoff, --limit/--offset and --min-relevance; material pages use --report-limit
and --report-offset. Preserve the returned cutoff on later pages. Queries only
use reader credentials. Conditional changes use the controller and validate cheap
structure/size before credential lookup; Node remains the authority for source
existence, revisions, manual locks and graph integrity. Successful receipts check
the requested operation's known effects, including title locks, channel membership,
merge canonical target and moved material protection/exclusion.

Timeout, unauthenticated/malformed reply, incomplete receipt or late owner guard
returns outcome_unknown with requestId and nonzero CLI exit. Retry with
--request-id and exactly the original parameters. Known version/request conflicts
remain explicit rejections, not unknown writes. Runtime/model faults do not cause
an automatic paid retry. Stdlib tests and the real PG/Node manager/dispatch fixture
verify the flow; the latter isolates the credential backend and interpreter
selector, and does not certify actual Keychain lifecycle or clean installation.

## Shared events and versioned channels

Migration 10 and `src/events.ts` persist shared event identities, immutable
snapshots/material associations, direct followups, related/pending-review links,
channel configuration versions and independent relevance/importance/increment/heat
judgments. Composite material may support multiple events without duplicating the
original. Occurrence/effective times currently remain unknown; publication and
acquisition times are not substituted. Similar text never triggers an automatic merge.
Direct-followup cycle checks use a distinct-node breadth-first traversal bounded
to 100 layers/1000 vertices; oversized graphs fail visibly rather than expand paths.

Controller-only corrections support title, channel membership, merge, split and
material reassignment to an existing event. Expected revisions, canonical request
hashes and immutable before/after audit make identical UUID retries reusable.
Merged IDs resolve to the canonical event at the requested cutoff. Moved/protected
materials and human titles survive automatic reruns. Historical queries exclude
later versions/configuration/judgments. Human judgments remain effective after an
event/channel upgrade, with `inherited`, original versions and applied versions
explicitly returned; an explicit channel exclusion takes precedence.

Ordinary workers cannot configure channels, correct events or insert human scores,
including through direct SQL. Model judgments require an immutable model receipt
and matching result fingerprint/output, verified by both API and database trigger.
The positive receipt-binding test uses a SYNTHETIC response, not a paid call.
`tests/events.integration.ts` exercises real PostgreSQL, scoped roles, corrections,
historical cutoffs, a layered diamond graph and configuration of a third channel.
Scores in this test are fixtures, not research quality evidence. Native model
factory and Web Host/UI mounting are implemented; grouping follows below.

## Durable grouping worker

Migration 11 registers one processing item per immutable material revision and
group prompt version in the same parse transaction. `src/processing.ts` schedules
the existing `hot.process` queue only when a grouping capability is available.
The service accepts that capability internally; public Native bootstrap/Settings
wiring is still pending. Without it, status reports `blocked_model`, collection
continues and pending materials remain visible. Budget-blocked, unknown, rejected
and stale inputs are retained and never automatically requeued.

The exact granted claim freezes a packet before model dispatch. Candidate lookup
is bounded to 20 events across all history, searching both event titles and the
original associated reports (including English reports behind Chinese event
titles). This is bounded retrieval, not exhaustive chain recall. Partial material
excerpts and three representative reports are declared. DSH input serialization
is canonical across JSONB reload, so receipt reuse survives process/generation
replacement. `src/dsh-grouping.ts` uses the existing prepared-call ledger and
credential-safe output filter; it never starts research sessions or tools.

Model decisions distinguish same occurrence, direct followup, separate event and
uncertain relationship, with multiple parts for composite material. Publication
verifies the saved receipt, current material/candidate revisions and manual locks.
Event updates, immutable processing result and queue acknowledgement share the
claim transaction. A savepoint rolls back every event change on a deterministic
publication rejection; the retained receipt and terminal state prevent retry
loops. Late/candidate-changed results are accurately reported as stale.

`tests/processing.integration.ts` uses synthetic responses with real PG/pg-boss,
including receipt-before-crash recovery, unchanged counters, cross-language
candidates, human changes during dispatch, budget pause, publication rollback and
exact-revision result lookup. These tests do not prove live model grouping quality.
The controlled `model-live-proof.ts group` acceptance shares the earlier fixed
human-authorized scope, copies two frozen source records into that schema, and
uses the production worker handler. It never creates a fresh quota. Its outputs
report origin/target versions and evidence hashes; regular product activation and
channel rules remain separate pending work.

## Versioned domain rules

`channels.example.json` configures AI, macro and Gold without changing the engine.
Each optional structured rule contains a stable id, literal keywords, an official
source requirement, and independent relevance/importance weights (0–100).
Keywords match titles and bounded excerpts; Latin words respect boundaries.
Legacy topics provide a relevance-70/importance-40 baseline. `importanceRules`
holds explanatory notes; only structured `rules` execute scoring. Scores are
transparent ordering heuristics, not calibrated probabilities or investment advice.

`src/channel-rules.ts` runs on the existing worker heartbeat, evaluating at most
20 event/channel pairs with a persistent round-robin cursor. It uses the current
event/config versions and an hourly observation fingerprint; refreshing or
reading a page does not evaluate or call a model. Migration 12 stores immutable
rule evidence: matched clauses/material IDs, original version hashes/times/URLs,
report/source/independent-operator counts, source enabled/error/coverage state,
publication range and parsed count, scoring algorithm and observation time.

Known publication within the hourly 24-hour window contributes heat; acquisition
time, old imports and unknown publication never supply freshness. Content hash
differences from the previous observation supply information increment, explicitly
not independently verified new facts. Reposts with equal content do not add that
increment, and aliases of one operator do not become independent operators.
Official provenance requires catalog id/operator and original URL host agreement.
The evidence state does not claim automatic independent corroboration. Human
overrides and channel exclusions remain effective; historical reads never use a
later configuration or score. Changes in source configuration, errors, coverage
range/count/gaps mark heat trends as not directly comparable.

`channel-rules.test.ts` and real PG integration verify these rules, immutable
evidence, history, scoped worker grants, repeat reuse and human priority. Fixtures
are synthetic. `scripts/channel-live-proof.ts` instead reads the two genuinely
grouped frozen AI/macro events in the fixed acceptance schema, loads the same JSON
channel configuration and records six real-event judgments. It starts no model,
checks cumulative budget unchanged and preserves existing different configs.
Gold's bank-stability example is explicitly indirect (40/35); it does not claim
direct Gold-price evidence. Public CLI/Settings channel editing is still pending.

## Continuous public collection

Migration 5 adds collection attempts and a durable material inbox. DataHub owns
`app/research_web/datahub/hot_public_sources.json`; Hot setup registers its four
verified official feeds without overriding existing source settings. The internal
service runs the actual finite-concurrency worker and source scheduler. Source
acquisition uses 25-second HTTP deadlines, rejects redirects, bounds raw bodies
to 4 MiB, preserves invalid UTF-8 bytes, and honors numeric Retry-After/backoff.
Original bytes and every parsed pending entry are committed together before the
acquisition watermark. Parse jobs drain at most collection.maxItems per batch,
share the original raw_page and retain immutable versions; new collection waits
for unfinished parsing. Source admission checks pending/active jobs and leases,
and handlers bind their exact granted attempt rather than adopting a later claim.
Interrupted attempts and bad raw XML remain visible; errors do not advance the
success watermark. Read RPC and `rwb hot sources --json` expose recent success,
errors, pending counts and actual snapshot coverage without triggering collection.

These feeds provide latest snapshots, not complete historical ranges. Pagination
and configured backfillDays are not supported by this first adapter; status
explicitly returns backfill:not_supported. Event/channel inference and DataHub
Broker/UI registration are still pending; channelHint is catalog metadata only.
`node scripts/collection-proof.ts` tests two real scheduled cycles through the
production worker on an isolated schema and scoped roles. An earlier proof
collected 1389 stable materials/versions and 8 originals, with zero pending items;
the latest current-code proof is FAIL due to connect timeouts. Receipts include
implementation hashes; older PASS does not certify the current revision. This does not certify model/research,
Mac Docker product deployment, continuous uptime or complete source history.

## Source configuration

`rwb hot sources --json` returns source config_revision and frequency_seconds.
`rwb hot source-configure fed --expected-revision <current> --disable --json`
pauses a source; `--enable` resumes it and `--frequency-seconds 60` sets a bounded
60–86400 second override. Zero clears the override and inherits collection.frequencySeconds.
These operations use the controller key, never the reader key. Migration 6 stores
immutable before/after audit records with actor local_host and a request UUID.
The source update, conditional revision and audit commit in the active owner fence.
Replay with the same request ID and unchanged parameters returns the original
receipt; changed parameters fail. A stale revision requires reading the current
source state before creating a new change. Transport timeout, untrusted response
or incomplete receipt returns outcome_unknown plus the requestId and nonzero CLI
exit status. Retry the same request with --request-id and identical parameters.
Pause cancels registered acquisition, blocks subsequent parse commits and retains
the inbox for resume. The cancellation registration exists before preflight;
the in-flight test deliberately simulates slow HTTP on a real service/PG instance,
and does not replace live-source acceptance. Web Settings wiring is still pending.

Same-content duplicate feed listings are coalesced into one material. Contradictory
timestamp declarations remain in the raw response and as a sorted JSON array in
the version's raw-time field; parsed time is unknown, never chosen arbitrarily.
The page metadata and gap projection record the ambiguity. Different-content
duplicates still quarantine the response instead of silently merging material.

## Cumulative model authorization substrate

Migration 7 and `src/model-budget.ts` persist explicitly authorized scope limits,
reservations, dispatch state, immutable provider receipts and reusable responses.
Calls/tokens/USD micro-units are cumulative, with no calendar reset. Provisioning
requires migration-owner privileges; worker cannot create authorization or edit limits.
Reservations charge conservative upper bounds before dispatch. Duplicate pending
inputs return busy; cached inputs reuse. Dispatch rechecks the locked budget,
including pause after provider overrun. Unknown sends remain charged and never
automatically retry. Only reserved unsent attempts can be cancelled/refunded.
Late receipts survive the old runtime lease but share the reservation fence;
business publication still requires current task claim/generation. Unexpected
actual overrun is recorded honestly and pauses the scope.

A fixed Native acceptance runner now uses the existing DSH model service and
Keychain resolver. The persistent acceptance scope is hot_events_goal_01a11684
in hot_acceptance_model; do not create fresh scopes to reset the task allowance.
Normal product worker generation and formal research integration remain pending.
The authorized cumulative cap is 20 calls / 20,000 tokens / US$1. Two real calls
used 386 tokens and 222 micro-USD conservative tariff ceiling (not an invoice).
The cache replay kept all counters unchanged. Synthetic tests remain separate.

## Prepared DSH text adapter

`src/dsh-text.ts` binds the pinned prepareCall/stream vocabulary to an explicit
ledger port. It sends text only, with no tools/session, requires zero retries,
reserves before dispatch, and saves usage before returning business output.
Token totals include the disjoint input/cache-read/cache-write/output counters;
reasoning is already a subset of output. Pricing uses integer micro-USD rates
and BigInt ceiling arithmetic. The local input byte+2048 floor is conservative
for the fixed text projection, not an independent tokenizer verification.
Caller safety filtering is synchronous; rejected/truncated complete replies
still keep billing facts. Late complete usage survives cancellation, while
business return is denied. Missing usage remains outcome_unknown. The successful
pinned stream omits HTTP request id, so migration 8 allows NULL rather than a
fabricated id; requestedModel also does not claim the undisclosed backend version.

Native read-only probes confirm system-keychain configured and the installed
DSH model catalog/prepared off-reasoning, no-retry call. They did not generate.
`pricing.deepseek.2026-10-08.json` records the official legacy-name mapping and
peak-rate ceiling, not an invoice or automatic activation. Migration 9 adds daily
admission by explicit timezone; reservations count unknown sends and dispatch
rechecks/rebuckets across midnight. Cumulative limits never reset. Older scopes
migrate daily limits to zero, failing closed until explicitly provisioned.
Receipt cost_basis distinguishes provider, synthetic and tariff-ceiling amounts.
The Native context uses pinned libraries and a fixed-ref, read-only credential
service; no .env or inherited-key fallback. Raw and decoded JSON keys/strings are
checked for credential reflection. The two real extraction calls use public
AI/macro material/version/hash, with declared excerpt truncation; they are not
event grouping, domain importance evaluation or completed DSH research.

Node 24.11+ in the 24 series is required. Install the exact dependencies with
`npm ci` in this directory after the project-isolated infrastructure authorization.
Run `npm test`; `npm run proof` is the bounded stage-zero integration check.
The proof uses an isolated PostgreSQL Docker container and volume, does not touch
the user's databases, and does not delete any volume. Evidence goes under the
repository's ignored `logs/hot-stage-zero/`. Credentials never enter the report.
Use the project's installed Node selection rather than a floating global Node.

The formal engine route, runtime lifecycle and production configuration are not
certified by the stage-zero probe. No paid calls or external messages are sent.

See `THIRD_PARTY_NOTICES.md` for upstream commit, license and modification scope.

## Implemented stage-one substrate

`config.example.json` is a non-secret example for `parseConfig`. `rwb hot configure
--file services/hot/config.example.json` now saves the normalized non-secret
configuration. `rwb hot status/doctor` are read-only and do not start services.
Native `rwb hot setup/start/stop/restart` now own the standalone service process.
Setup installs locked project Node dependencies and provisions the selected schema.
Managed PostgreSQL uses the pinned digest, an instance-labelled data volume and
loopback-only binding; cold startup checks ownership before starting the container.
Secrets live in the system credential backend, with a private 0600 password-file
export for the owned PG container. External roles remain administrator-provided.
Native `rwb hot backup` creates a new private schema archive under the configured
data-home-relative backupDirectory. `rwb hot restore --from <directory>
--target-database <new-name>` restores only into a different database where the
selected schema is absent. It never drops or overwrites an existing schema.
The manager requires a stopped service; backup also requires the DB runtime paused.
It holds the generation fence before establishing a repeatable-read exported
snapshot, and pg_dump imports that same snapshot. The authenticated manifest
includes SHA-256, per-table counts, database-resident raw objects and scope.
Restore verifies the exact bytes passed to pg_restore and uses one transaction;
inventory is checked before source collection is disabled and scoped grants restored.
Managed mode uses the pinned image's PG17 tools. External mode requires PG17
pg_dump/pg_restore already installed and uses an ephemeral private pgpass file.
The present host has PG18 tools, so external-tool acceptance is NOT_RUN.
Container tools have an internal deadline, SQL timeouts and a unique application
name for backend cancellation. Cancellation uses a separate pool, including when
poolMax=1. Unknown outcomes remain in private archive-attempt.json and block repeat
archives; automatic reconciliation of that journal is still pending. Ctrl-C and
outer timeouts signal and reap the owned child. Archives are limited to 256 MiB;
larger datasets fail explicitly, with streaming archives still pending.
After a verified restore, configure database.name to the returned target before
starting it; sources remain disabled until explicitly re-enabled by future source
configuration. Research snapshots are not integrated and cannot be claimed restored.
Settings and Docker product lifecycle remain unfinished.
Disabled Hot performs no credential lookup or DB connection. Secrets are passed
only by an authorized Host resolver; the JSON schema rejects passwords and DSNs.
Managed connections are restricted to loopback or the fixed private service
name; remote external connections require verified TLS, and an explicitly chosen
loopback external connection may disable TLS. Pools use bounded connection,
statement and lock timeouts. Schema names are validated and safely quoted.

All Hot business **and pg-boss tables use the same explicitly selected schema**.
Migration files retain immutable checksums. Initial adoption refuses nonempty
foreign namespaces, including views and functions. A queue binding ties the
pg-boss installation to the initialized instance. Worker provisioning grants
specific DML permissions and rejects admin roles. Workers cannot migrate, change
runtime control, delete evidence or enable/disable sources. `checkDatabase`
checks the actual schema, version and required permissions; it is DB readiness,
not proof of a running product service or model capability.

The Host initializes the identity, activates a generation, and heartbeats the
runtime lease. `runWorker` bounds concurrency, polls the one durable backend and
joins lanes on cancellation. Completion and business writes share a transaction.
Commit/claim/failure operations verify current runtime and attempt leases. Only
the valid generation supervises expired pg-boss jobs; stale generations cannot
settle them. Public outcomes reuse the same stage/input identity across restarts.
Paid processing/research queues have no automatic retries; budgeted unknown-call
resolution is a later stage and remains unimplemented.

AbortSignal is passed to each handler and waiting is bounded even if a handler
ignores it. A late returned commit callback is never executed. This does not
forcibly stop arbitrary network side effects already started inside a handler;
future adapters must implement cancellation and their receipt contracts. The
Native manager verifies PID start identity and a launch nonce before signalling
its process. Actual Native/Docker switching still requires integration and acceptance.

After `npm run proof`, `npm run test:postgres` executes the real PostgreSQL
schema, restricted-role, runtime-generation, queue transaction/crash and worker
tests. `npm test` is the offline unit suite; `npm run typecheck` checks both.

## Private service entry

`scripts/serve.ts` accepts one bounded private stdin bootstrap supplied by the
owned Host. No passwords are placed in argv/environment or returned on stdout.
The initialized control/read service exposes status, sources and task projections;
it reports the actual worker state and `model:ready|blocked_model` with a stable
`modelCode`. Real child-process startup, SIGTERM,
restart and database/material retention are covered by `service.integration.ts`.

The only formal internal transport is a `127.0.0.1` single-frame protocol with
HMAC requests and responses, distinct reader/controller keys, current instance,
mode and generation checks. Keys never travel over the connection. It has fixed
wire limits, absolute deadlines and bounded connection/in-flight counts, passes
cancellation to handlers and checks decoded values for credential reflection.
No Unix socket pathname is created or removed. This avoids libuv's automatic
path unlink on pipe close ([upstream source](https://github.com/libuv/libuv/blob/v1.x/src/unix/pipe.c)).
Native manager start/status/restart/stop and PG cold recovery have real local
process/database evidence using an isolated credential backend. Actual Keychain
persistence and Docker product service management remain pending; these tests do
not certify the whole product.

## Native model configuration and recovery

`model.enabled` defaults to false; `model.scopeId` selects an existing persisted
authorization in the explicitly selected schema. Settings do not create, enlarge
or reset authorization. Existing daily policy must fit the configured budget and
timezone. A missing/paused policy or credential yields `blocked_model`; collection
and projections stay available. Explicit offline authorization/query/termination CLI
is described below; manual pricing import is available; installed-worker acceptance remains pending.

The Native Host passes the existing managed interpreter, fixed credential bridge,
actual data home and pinned DSH source on private stdin. DSH text context uses the
fixed provider/model catalog, no sessions/tools/retry. Shutdown drains worker then
closes context. Docker remains blocked until a supported credential path exists.

Official conservative tariff files are immutable dated records. Mount requires the
current local day; run, reserve and dispatch recheck that day. Missing/new-day pricing
blocks model work without stopping collection. After an official refresh and restart,
input-v2 cache identity uses input/prompt/model parameters independently of tariff.
The two pre-mount tariff identities remain compatible: cache/unknown lookup and new
admission share the receipt fence, and a reused result retains its original key.
The manual daily pricing import workflow is described below; automatic refresh remains pending.

## Explicit model budget and uncertain attempts

After stopping Hot, run setup to apply migration 14. A model scope is a cumulative
authorization, shared by Hot and any formal research using it; changing channels,
dates or runtime modes never creates a new authorization. Copy the zero-cap
`model-budget.example.json` to a private configuration file and explicitly choose
the cumulative/daily limits. `maxCostMicros` uses USD micro-units; 1,000,000 is US$1.
The example authorizes no requests. The configured model scope/timezone/daily limits
must match this authorization before activation.

```sh
./rwb hot stop --json
./rwb hot setup --json
./rwb hot model-authorize --file budget.json --authorize-paid --reason "Explicit budget approval" --json
./rwb hot model-attempts --scope hot --limit 50 --json
./rwb hot model-terminate --attempt <attempt-UUID> --reason "Stop uncertain work; retain charges" --json
```

Authorization and termination use the existing migration credential reference plus
the installation control identity, require stopped/expired database ownership and
write immutable UUID audits. They are separate private-stdin management processes,
not worker or Agent RPC capabilities. The managed database is verified and can be
cold-started for explicit controls; external databases are not started. Attempt reads
use the ordinary scoped role and never start PG, daemon or model. Credentials remain
in the configured backend; list responses omit dispatch-token hashes and model text.

An identical authorization cannot reset counters, enlarge immutable limits or clear
a paused budget. Reusing a UUID with different parameters rejects. Unknown/timeout
responses retain their original UUID and return nonzero; repeat that exact request
after verification rather than generating another ID. An uncertain local journal
blocks daemon start until replay confirms it. Post-dispatch journal/log errors preserve
the confirmed/uncertain UUID receipt and report persistence/logging unavailable.

Termination marks an already possibly sent attempt `abandoned`, retaining its maximum
reservation and blocking automatic resubmission. Ordinary workers cannot revert that
state or refund it. A genuine late receipt may still arrive, settle actual usage and
remain cached; transition to received requires that receipt. Reads report current
attempt status, original reservation, budget caps/counters and cost basis separately.
Synthetic tests and tariff ceilings are not provider invoices. Receipt import and
explicit controlled retry workflows remain pending; termination does not pretend a
missing response was never sent. Migration holds the same fence and refuses a live
owner, keeping management writes out of an active worker transaction.

`native-model-readiness-proof.ts` exercises the normal factory with actual configured
macOS credentials and reads two real grouping packets under a read-only DB session.
A cache miss cannot dispatch a paid request; exact legacy result keys and unchanged
cumulative counters are required. Separate missing-credential proof uses an isolated
empty data home. These prove readiness and unpaid recovery, not a full installed
authorized worker run, fresh event grouping, browser journey or formal research.

## User price catalog

Stop Hot, review the official provider page and update a non-secret dated record matching the packaged pricing JSON format. Then run `./rwb hot model-pricing-import --file pricing.json --verify-official-pricing --reason "Reviewed official peak rates" --json` and restart. The command uses the current configured timezone, accepts only the fixed official provider/model/currency and rates at least as conservative as the bundled known peak floor. It does not fetch/verify the source automatically, resolve credentials, create quota, connect to PG or invoke a model. The explicit flag records operator attestation, not independently validated billing.

Private `hot/pricing/YYYY-MM-DD.json` is the current catalog, with immutable content-hash objects beside it. UID/0700 directory, UID/0600 regular single-link files, instance/project/date and operator metadata are checked. Same input reuses the prior object and rechecks durability. Complete fsynced objects are atomically published under the manager lock; post-publication directory-fsync failure returns the visible hash with durability unavailable and nonzero exit. Retry repairs the durability acknowledgement. Existing objects are retained across price revisions.

Normal Native loading prefers a valid private catalog; invalid or dangling-symlink records block instead of falling back. Bundled current-day pricing remains a bootstrap fallback only when no private record exists. Each run, reserve and dispatch checks the loaded date and fingerprint, so changed/imported catalog requires restart and never changes input-v2 result identity or accumulated budget. Price controls are CLI only; automatic refresh, vendor invoice verification and pricing/data-directory backup policy remain pending.

Browser acceptance now includes two actual stored model events through real Host/Node/PG with isolated Hot credentials and an offline research client. AI/macro/gold share identity and distinguish importance from zero historical heat; original versions/times and partial source coverage are visible. It proves reads, not new model/research, installed credential lifecycle, continuous collection or production readiness. Fixture source pauses were restored and original budget unchanged.
