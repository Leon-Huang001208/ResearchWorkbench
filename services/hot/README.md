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
