# Hot internal engine

This package is under implementation. It is not yet a supported product entry.
The authoritative stage record is `.ai/reports/2026-10-07-hot-events-PROGRESS.md`.

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
it reports the actual worker state and `model:not_integrated`. Real child-process startup, SIGTERM,
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
