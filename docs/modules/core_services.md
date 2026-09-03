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

## Merged research orchestration

- `ResearchOrchestrationService` is the aggregate boundary for atomic Session→Run binding and scoped execution. A Run belongs to exactly one project/workspace Session; every bound read, resume, evidence write, export and event stream rechecks that scope.
- `RuntimeProviderService` routes FinGPT and Claw by declared capability. FinGPT may deterministically fall back from an unavailable DSH request to built-in LangGraph; Claw never degrades to a single-agent run and persists `blocked_runtime` when a required team/runtime is absent.
- Provider requests and typed results carry stable correlation IDs, request hashes and Run identity. Altered callback replays are conflicts, and only the correlated Run can consume a terminal result.
- `SkillManifest` remains declarative. Runtime compilation checks the closed platform registry, meaningful JSON Schema constraints, sensitive output and reserved token/cost/deadline limits before a result can enter research state.
- `AgentTeamService` is Supervisor-only orchestration over a typed shared blackboard. Every assignment receives its reservation/deadline context; worker output, usage and blackboard evidence are persisted into the final Claw research result instead of becoming detached side effects.
- `SchedulerCoordinator` leases persistent jobs with fencing and execution-time renewal, supports latest-only coalescing, and dispatches registered handlers for Agent schedules, market close snapshots, and asset alerts. Failed work keeps its job/idempotency identity and error while retrying with deterministic exponential backoff; the third failed attempt is terminal. The process-wide `DurableSchedulerRuntime` is the only production polling thread, with locks around singleton initialization and start/stop; domain materializers run before claim, while each domain handler owns an independent commit/rollback/close Session. Execution is at-least-once, so non-idempotent Agent/tool side effects require a separate durable execution ledger.
- Research stage events are committed through a transaction boundary visible to concurrent SSE readers. `Last-Event-ID` replays durable ordered stage references without exposing prompts, tool payloads or artifacts.

## Research Pack ingestion

- `ThemePackRegistry` only resolves reviewed built-in plugin IDs; manifests cannot name import paths or inject callables.
- `ThemeResearchService` normalizes a complete source row before identity comparison, expands wide LSH rows into one Observation per preserved measure, and only treats payload-equivalent identities as duplicate. Conflicting values are quarantined with audit evidence rather than overwritten.
- Apply writes Observations, ingestion audit/checkpoint state and market-home invalidation events in the caller's transaction. Dry-run never opens the target database; resume validates the source hash before continuing.
- Source tier, verification, availability and freshness are derived from row evidence. Missing or stale facts cannot become official, verified or 100% covered by default.

## Market-home runtime

- `record_market_home_fact_update()` lets authoritative fact writers flush idempotent section invalidations before their own commit; a writer failure rolls back facts and outbox together.
- Stable market callbacks register on the shared `DurableSchedulerRuntime` before startup. The materializer requires an exact positive answer from the authoritative Cjpy A-share calendar before ensuring one persistent Asia/Shanghai 15:05 job; missing/failed calendars and holidays fail closed. The handler writes all five immutable close-section rows in its own transaction. `MarketHomeSchedulerRuntime` remains compatibility-only and has no production lifecycle wiring.

## Asset-alert runtime

- Stable alert callbacks use the same `DurableSchedulerRuntime`. Each tick discovers every profile owning an active Rule and enqueues one idempotent `asset_alert.evaluate` job per UTC minute bucket; the handler calls `evaluate_due_alerts(profile_id, evaluated_at)` in an independent transaction so Rule state, Event and Notification persist atomically.
- The alert handler declares a configurable maximum execution budget (one second by default). Runtime capacity includes polling cadence, batch limit, and serial handler duration; the materializer compares all due backlog with that bound before commit. An observed overrun latches degraded health and blocks later materialization fail-closed. Existing stale/unavailable/quarantined and blocking-quality skip semantics remain authoritative inside the evaluator.

## Update this file when

- The runtime eligibility, cadence, retention, host-history contract, or source-scope taxonomy changes.
- Resource warnings gain a notification channel or a new public data boundary.
- Research Run state, evidence gates, artifact semantics, or export eligibility changes.


## DataHub / CJPY 增量（2026-09-03）

FinGPT/Claw 的 data_catalog 与 data_query 都通过平台 DataHubService 读取已校验事实，可信 tool result sink 写原 Research Run 的证据与产物；研究图启动前刷新这些证据。采集与数据库访问始终留在平台服务内。 详见 [DataHub 模块说明](datahub.md)。

MCP CLI `python -m mcp.server` 现在显式加载已安装 SDK，避免同名项目包遮蔽；使用标准初始化与独立协议 stdout。真实 stdio 验证见 `tests/unit/test_datahub_mcp.py`。
