# Hot implementation and acceptance plan

Authority: the goal-objective attachment `6a5d3231-3d08-403b-98cc-a839f4b71aa4`
and `/Users/leon/Downloads/RWB_Hot_Events_Codex_Goal.md`, all stages and completion
criteria. This plan organizes execution; it does not replace or narrow them.
Progress authority: [PROGRESS](2026-10-07-hot-events-PROGRESS.md).

## Fixed route after bounded integration

- One `services/hot/` Node 24 TypeScript internal engine owns SQL migrations,
  material ingestion/versioning, event logic, channel rules, receipts and the
  single pg-boss durable queue. Upstream application/website is not embedded.
- `app/research_web/hot/` will own the FastAPI product adapter: user settings,
  instance/mode control authorization, read projections and existing research
  handoff. No direct browser/Agent SQL. No new research Agent loop.
- DataHub will own source catalog/capability/authorization; background HTTP
  collector executes independently of ResearchService and old Store.
- PostgreSQL 17.11, Docker digest
  `sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826`.
  Node 24.19.0; postgres 3.4.9, pg-boss 12.34.0, fast-xml-parser 5.11.1.
  Compiler-only dependencies: TypeScript 7.0.2 and Node types 24.10.0.
- Store raw responses and versioned evidence in PostgreSQL initially, avoiding
  an extra object-directory publication transaction. Research receives frozen
  copies through the existing session snapshot contract.
- Private internal socket with versioned request envelopes, installation
  identity and mode generation. Host controls this socket; no browser endpoint
  can claim leases or resolve credentials. Revoke old generation on mode switch.
- Runtime roles have DML permission only within explicitly configured schema;
  migration credentials separate. Schema name must be validated and safely
  quoted. The current proof uses superuser only in isolated development PG.

## Stage 0: baseline and reuse

Completed evidence: latest remote master, active PR boundaries, isolated branch,
upstream license/commit, real source probes, stable material identity in PG,
pg-boss enqueue/claim/complete. Four official sources are independently operated:
OpenAI and Google DeepMind for AI; Federal Reserve and ECB for macro.
RSS coverage is a latest source snapshot, not complete daily/world coverage.

Model boundary: pinned DSH `c919b2a...` exposes `ctx.llm.stream(GenerateOptions)`
without a required session. Its existing provider resolves the current model
credential. Add a fixed-purpose authorized Hot bridge plugin using that service,
not HTTP calls with a copied API key. The service method itself is not a remote
generation API; a product-owned authenticated bridge is required. Native model
key resolution is macOS Keychain-only. Docker must show `blocked_model` while
that existing model bridge is unavailable. No live model call has run.

## Stage 1: configuration, lifecycle, persistent task substrate

1. Finish `services/hot/src/database.ts` migrations and pooled config: schema,
   roles, timeout, health, actual schema version, restart and connection failure.
   Existing material tests do not certify user-configurable schemas yet.
2. `services/hot/src/config.ts`, `queue.ts`, `control.ts`, `worker.ts`: strict
   non-secret settings; unique durable scheduling; task input versions; leases,
   attempt state, generation fencing and conditional commit; pause/drain/restart.
3. `app/research_web/hot/` settings and credential-backend references, CLI
   `research_workbench_entrypoint/hot_*.py`, manager integration. Off/unconfigured
   Hot must not start a DB connection during base settings/research reads.
4. `docker/hot/`, Compose profiles, runtime contract, `scripts/setup_web.py`:
   owned managed PG volumes and external PG (never stopped by RWB), private
   network, exact image digest and dependency lock installation. Native and
   Docker share logical database; test old-worker refusal after switch.
5. Formal `rwb hot` setup/start/stop/restart/status/logs/doctor/backup/restore.
   Restore refuses nonempty targets by default; sources/tasks paused. Stage-one
   schema-only proof is not the final research/objects joint recovery.

## Stage 2: real ingestion and source coverage

Register sources through DataHub and implement source-level independent HTTP
collection, ETag/cursor/pagination, bounded backfill, cancellation/deadlines,
rate limiting and backoff. Persist raw page/collection run before parsing;
retain retryable partial entries/failures without advancing watermark. Cross-
channel source reuse, publisher stable IDs, revisions, discovery provenance,
unknown dates, actual range/gaps and last success must be visible. Repeated pages
must not duplicate downstream tasks. Historical imports do not gain fresh heat.

## Stage 3: events and model processing

Implement shared event IDs, direct followups and long-term event-chain retrieval,
composite reports linked to separate events, uncertainty review states. Persist
revision/config/prompt/model identities; event/channel evidence as-of. Separate
heat, incremental information, evidence, research importance and relevance.
Preserve human merge/split/reassignment/title/channel corrections, aliases and
audit through automatic reruns. Configure Gold without core-source changes.

Use a small versioned real AI/macro corpus with event-separated development and
holdout samples. Run actual Native extraction/grouping/channel judgment, inspect
source support and difficult relations per case. Model self-evaluation is not a
human gold standard. Reserve budgets before paid send; save response before
business commit; reuse receipts; unknown outcomes require audited resolution or
one explicitly budgeted retry/termination, never blind retries.

## Stage 4: UI, briefs and research

Add existing-theme navigation, channel/follows, sortable/filterable bounded event
queries, evidence/history, coverage/operations and configuration/correction UI.
Brief versions expose window, evidence versions and gaps; web/Markdown and
existing pure DOCX file delivery. Fixed facts/source opinion/inference labeling.
Freeze Hot evidence into newly owned session snapshots via Workbench handoff.
Persist Hot run → session/report mappings; query accepted runs after uncertain
receipt before resending. At least one real DSH research must deliver an openable,
traceable artifact. Delete research session without deleting Hot evidence.
Hot alone schedules periodic briefs; existing reports consume one-time child
runs. No external sending unless user explicitly enabled a channel.

## Stage 5: full acceptance and reviewable delivery

Execute every behavioral scenario from the goal's section 12 / detailed goal's
section 12. Full database/raw/version/event + selected research snapshot joint
backup/clean restore; verify mappings/hashes and initial pause. Native real
model/research; Mac Docker DB/worker/live collection/read/switch; non-authorized
and stale control identities rejected. Record each platform separately.

Update README, architecture/development maps and generated diagrams, DataHub,
installation, Doctor, security, configuration/data dictionaries, architecture
inventory, changed-file policy owner and same-SHA macOS CI. Preserve L4 database,
installation, concurrency and handoff risks. Use the project planner and full
changed set; do not fabricate coverage from phase-zero tests. Read Actions budget
and current visibility before remote actions. Stop at reviewed branch/candidate
and applicable PR; merge and production deployment need existing authorization.

## Concrete verification commands already usable

From `services/hot`, using Node 24.19.0:

```text
npm ci --ignore-scripts
npm run typecheck
npm test
npm run proof
npm run test:postgres
node scripts/recovery-proof.ts
```

The proof scripts are explicitly isolated development probes, not finished
product installation/restore commands. Logs and raw publisher responses live
under ignored `logs/hot-stage-zero/`; generated secrets are private and are not
committed. Actual next candidate gates come from `scripts/plan_verification.mjs`
over the complete current changed set. Mandatory but unexecuted checks remain
NOT_RUN; missing product interfaces remain incomplete.
