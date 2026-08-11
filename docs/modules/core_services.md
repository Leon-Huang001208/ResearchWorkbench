# Module: core services

## Responsibility

This index records cross-cutting service contracts that sit beneath the API routes and above repository persistence. The concrete service catalogue remains in [services.md](services.md).

## Host-capacity resource monitoring

- The page path reads only the API process's in-memory AlphaFoundry snapshot/history: at most five minutes and 150 points. It includes the API process tree and explicitly registered AlphaFoundry Worker PIDs, never a machine-wide process listing.
- The persistent path is `ResourceMonitorRuntime`: when database readiness succeeds and `ALPHAFOUNDRY_PREVIEW` is not `1`, one stoppable thread samples once per minute, records a whitelisted host-capacity point, and retains at most 24 hours. `GET /api/system/resource-usage/host-history?hours=1..24` reads that persisted series; it does not create it.
- `memory_available_bytes` and `memory_available_percent` mean the operating system's `available` memory, not `total - used`.
- Resource events use the existing monitoring state machine. Controlled application-side failures and pressure use `source_scope=alphafoundry`; host CPU or available-memory capacity pressure uses `source_scope=host_capacity`.
- Branch desktop previews intentionally set `ALPHAFOUNDRY_PREVIEW=1`, so they do not start the persistent runtime. Resource warnings are exposed through the API and system-monitor page only; no native desktop notification is emitted.

## Safety and failure handling

- Collection, persistence, and lifecycle failures log a structured error type and leave future runtime cycles available.
- Public API values are whitelisted and omit other process details, command arguments, secrets, request content, raw metric JSON, and internal deduplication keys.

## Evidence-first Research Run

- `ResearchTemplateRegistry` publishes framework-free template metadata and resolves an executor from `template_key + ResearchSubject.subject_type`. Unknown, planned, incompatible, or evidence-category-invalid requests fail before persistence.
- `ResearchRunService` makes PostgreSQL-backed `ResearchRun` the only durable state for every domain template. LangGraph only reconstructs the selected graph from that snapshot and writes results back through the repository; it is not a second fact store. The first executable graph remains A-share company research.
- Every attempt appends versioned `ResearchArtifact` records before refreshing the current claim and quality-gate projections. A blocked run can accept additional normalized evidence and resume from validation without overwriting earlier artifacts.
- Publishing requires citations for every claim, coverage for financial/industry/valuation/risk/consensus, complete numeric context, and no unresolved conflicts. Only `completed` runs can export Markdown or in-memory Word documents.
- The first graph plans sources in `licensed → official → public → user` priority and records the selected/fallback path. Actual source connector authorization remains outside the graph boundary.

## Update this file when

- The runtime eligibility, cadence, retention, host-history contract, or source-scope taxonomy changes.
- Resource warnings gain a notification channel or a new public data boundary.
- Research Run state, evidence gates, artifact semantics, or export eligibility changes.
