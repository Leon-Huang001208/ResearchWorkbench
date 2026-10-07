# Hot internal engine

This package is under implementation. It is not yet a supported product entry.
The authoritative stage record is `.ai/reports/2026-10-07-hot-events-PROGRESS.md`.

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
Settings and full lifecycle CLI wiring remain unfinished.
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
product manager's owned-process termination and actual Native/Docker switching
still require integration and real acceptance.

After `npm run proof`, `npm run test:postgres` executes the real PostgreSQL
schema, restricted-role, runtime-generation, queue transaction/crash and worker
tests. `npm test` is the offline unit suite; `npm run typecheck` checks both.

## Private service entry

`scripts/serve.ts` accepts one bounded private stdin bootstrap supplied by the
owned Host. No passwords are placed in argv/environment or returned on stdout.
The initialized control/read service exposes status, sources and task projections;
it truthfully reports `worker:not_configured` and `model:not_integrated` until
the corresponding adapters are completed. Real child-process startup, SIGTERM,
restart and database/material retention are covered by `service.integration.ts`.

The only formal internal transport is a `127.0.0.1` single-frame protocol with
HMAC requests and responses, distinct reader/controller keys, current instance,
mode and generation checks. Keys never travel over the connection. It has fixed
wire limits, absolute deadlines and bounded connection/in-flight counts, passes
cancellation to handlers and checks decoded values for credential reflection.
No Unix socket pathname is created or removed. This avoids libuv's automatic
path unlink on pipe close ([upstream source](https://github.com/libuv/libuv/blob/v1.x/src/unix/pipe.c)).
Actual Docker service management, signed process-state ownership and product
manager termination remain pending; these tests do not certify the whole product.
