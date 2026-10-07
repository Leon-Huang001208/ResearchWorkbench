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
production worker on an isolated schema and scoped roles. The latest proof
collected 1389 stable materials/versions and 8 originals, with zero pending items;
its receipt includes implementation hashes. This does not certify model/research,
Mac Docker product deployment, continuous uptime or complete source history.

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
