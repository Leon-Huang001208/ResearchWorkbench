# Gold / Dollar frameworks and Artifacts repair

## Scope

- Added a thin framework registry, shared atomic snapshot storage and one idempotent scheduler.
- Upgraded Gold to schema v2 with official WGC/SPDR, FRED, Goldhub, Cboe and CFTC collectors.
- Added Dollar schema v1 and Q-P-g-M-X collectors from FRED, New York Fed, FiscalData and TreasuryDirect.
- Added continuous Gold/Dollar renderers, framework-bound DSH explain/verify sessions and Lieflat SVG encodings.
- Excluded soft-deleted sessions from the global Artifacts index and isolated Artifacts errors from Asset Observation.

## Design read

This is an extension of the existing Research Web visual language: variance 3, motion 2, density 8, asset dependence 1 and brand fidelity 10. Both frameworks use one continuous canvas, a sticky semantic anchor rail, sparse borders, low shadow and existing color tokens. Gold uses F2/F9/F6/F5/L4; Dollar uses F9/F3/F12/F6/F2/F8. No external font, CDN, iframe, image or original project brand asset is used.

## Data boundary

Seeds are deterministic offline fixtures for tests and the first server-side no-data state. Production browser errors never substitute fixture values. Blocks preserve the last successful payload and record `checked_at`, `failure_code`, sources and gaps. Dollar labels `WALCL - TGA - ON RRP` only as a net-liquidity proxy.

## Read-only source smoke (2026-09-14)

- Goldhub supply/ETF and SPDR holdings: success; supply observed 2026-03-31.
- Cboe delayed GLD options: success; observed 2026-09-13.
- Gold macro after replacing retired FRED gold/GVZ identifiers: success; official price fix observed 2026-09-11.
- Dollar FRED/New York Fed core: success; all five dimensions calculable, block dates through 2026-09-10.
- FiscalData/TreasuryDirect upcoming auctions: success; fiscal observed 2026-09-10.
- CFTC deterministic ZIP conversion is covered offline; the official annual ZIP URL was checked read-only during implementation.

## Verification status

- Focused backend regression: `21 passed`; focused JavaScript regression: `18 passed`.
- Full Research Web backend suite: `909 passed, 4 skipped`; only the installed Starlette/anyio alias deprecation warning remains.
- Full Research Web JavaScript suite: `279 passed, 1 skipped`.
- Browser acceptance: both routes passed light/dark at 1440, 1280, 1024, 768 and 390 px; both had 44 px anchor targets, no document/main overflow, no page or console error, no iframe or hotlinked resource, and reduced-motion disabled reveal animations. The continuous left anchor rail becomes a single horizontal semantic rail on mobile; no chapter is turned into a separate page. Screenshots and the machine-readable receipt are in `outputs/frameworks-v1/`.
- Manual screenshot review: Hub hierarchy clearly separates framework reasoning from Asset Observation; Gold and Dollar share the same visual grammar while preserving different causal chains and chart encodings. At 390 px, metadata and the chapter rail reflow without hiding state, evidence coverage or the framework Bot.
- Targeted Ruff, Black and isort passed. Framework mypy passed for 22 files with `--follow-imports=silent`; ordinary transitive mypy still reports 13 pre-existing structured-logging typing errors in `core/observability/{tracer,metrics}.py`.
- Architecture integrity, managed integration, CI and deployment are recorded after they run; this report does not predeclare them successful.
- Deployment preflight exposed two launcher drift hazards: invocation from another checkout could shadow the pinned entrypoint, and Homebrew Node 25 was ABI-incompatible with the reviewed DSH native module built for Node 24. The launcher now enters its resolved project root and pins the Codex bundled Node when available; `RESEARCH_NODE_BINARY` remains the explicit override elsewhere.
