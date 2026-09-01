# Merged Platform Detailed Architecture Blueprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付可从产品功能追踪到页面、HTTP API、Service/Contract、数据表、领域事件和状态机的详细架构包及可交互 API Atlas。

**Architecture:** 现有九张 Archify 图继续承担总览职责；新增详细目录使用三个 JSON Catalog 作为追踪真相源，并按共享平台加六个业务领域拆成三十八张可读图。API Atlas 由无外部依赖的 Node 脚本从 Catalog 生成自包含 HTML，避免手写 HTML 与接口清单漂移。

**Tech Stack:** Markdown、JSON、Node.js 内置模块、`node:test`、Archify、HTML/CSS/JavaScript。

---

## File map

### Canonical documentation

- `docs/architecture/merged-platform/detailed/README.md`：详细蓝图索引、阅读顺序和交付状态。
- `docs/architecture/merged-platform/detailed/00-traceability-contract.md`：编号、数据字段和完整性规则。
- `docs/architecture/merged-platform/detailed/01-shared-platform.md`：部署、依赖、数据、事件、安全和迁移边界。
- `docs/architecture/merged-platform/detailed/02-market-home.md`：市场首页功能、接口、状态和数据流。
- `docs/architecture/merged-platform/detailed/03-theme-research.md`：Research Pack 功能、接口、状态和数据流。
- `docs/architecture/merged-platform/detailed/04-asset-observation.md`：资产、同类、Watchlist、Alert 和通知。
- `docs/architecture/merged-platform/detailed/05-fingpt.md`：FinGPT 即时研究工作区。
- `docs/architecture/merged-platform/detailed/06-claw.md`：Claw 多 Agent 工作区。
- `docs/architecture/merged-platform/detailed/07-platform-core.md`：Runtime、Skill、MCP、Schedule 和通知内核。

### Catalogs and generated artifacts

- `docs/architecture/merged-platform/detailed/catalog/capabilities.json`：`CAP-*` 和 `PAGE-*`。
- `docs/architecture/merged-platform/detailed/catalog/api-atlas.json`：`API-*`、请求、响应、错误、Owner、表和事件。
- `docs/architecture/merged-platform/detailed/catalog/traceability.json`：跨 Catalog 的稳定映射。
- `scripts/architecture/build_merged_platform_atlas.mjs`：校验 Catalog 并生成自包含 API Atlas 和导航首页。
- `tests/javascript/merged_platform_blueprint.test.mjs`：Catalog 和生成器的确定性测试。
- `outputs/merged-platform-blueprint/index.html`：蓝图入口。
- `outputs/merged-platform-blueprint/api-atlas.html`：可筛选 API Atlas。

### Diagram source and output

- `docs/architecture/merged-platform/detailed/diagrams/*.json`：三十八份 Archify 图源。
- `outputs/merged-platform-blueprint/diagrams/*.html`：三十八份冻结 HTML。
- `outputs/merged-platform-blueprint/diagrams/*.visual-check.*`：四视口证据。

## Task 1: Establish the traceability contract and failing tests

**Files:**

- Create: `tests/javascript/merged_platform_blueprint.test.mjs`
- Create: `docs/architecture/merged-platform/detailed/00-traceability-contract.md`
- Create: `docs/architecture/merged-platform/detailed/catalog/capabilities.json`
- Create: `docs/architecture/merged-platform/detailed/catalog/api-atlas.json`
- Create: `docs/architecture/merged-platform/detailed/catalog/traceability.json`

- [ ] **Step 1: Write the failing Catalog test**

Create `tests/javascript/merged_platform_blueprint.test.mjs` with these assertions:

```js
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../docs/architecture/merged-platform/detailed/catalog/', import.meta.url);
const load = async (name) => JSON.parse(await readFile(new URL(name, root), 'utf8'));

test('blueprint identifiers are unique and typed', async () => {
  const capabilities = await load('capabilities.json');
  const atlas = await load('api-atlas.json');
  const traceability = await load('traceability.json');
  const ids = [
    ...capabilities.capabilities.map((item) => item.id),
    ...capabilities.pages.map((item) => item.id),
    ...atlas.interfaces.map((item) => item.id),
    ...traceability.services.map((item) => item.id),
    ...traceability.data_owners.map((item) => item.id),
    ...traceability.events.map((item) => item.id),
  ];
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(capabilities.capabilities.every((item) => /^CAP-[A-Z]+-\d{3}$/.test(item.id)));
  assert.ok(capabilities.pages.every((item) => /^PAGE-P\d{2}$/.test(item.id)));
  assert.ok(atlas.interfaces.every((item) => /^API-[A-Z]+-\d{3}$/.test(item.id)));
});

test('every capability and write API has an implementation trace', async () => {
  const capabilities = await load('capabilities.json');
  const atlas = await load('api-atlas.json');
  const traceability = await load('traceability.json');
  const traces = new Map(traceability.traces.map((item) => [item.capability_id, item]));
  for (const capability of capabilities.capabilities) {
    const trace = traces.get(capability.id);
    assert.ok(trace, `missing trace for ${capability.id}`);
    assert.ok(trace.page_ids.length > 0 || trace.local_interaction === true);
    assert.ok(trace.api_ids.length > 0 || trace.local_interaction === true);
  }
  for (const api of atlas.interfaces.filter((item) => item.method !== 'GET')) {
    assert.ok(api.idempotency.required, `${api.id} must declare idempotency`);
    assert.ok(api.service_id);
    assert.ok(api.write_data_owner_ids.length > 0 || api.effect === 'control-only');
  }
});

test('all fact responses expose provenance and freshness', async () => {
  const atlas = await load('api-atlas.json');
  for (const api of atlas.interfaces.filter((item) => item.response_kind === 'fact')) {
    assert.deepEqual(api.fact_envelope_fields, [
      'as_of', 'observed_at', 'available_at', 'source_refs',
      'freshness_status', 'quality_flags',
    ]);
  }
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
node --test tests/javascript/merged_platform_blueprint.test.mjs
```

Expected: FAIL with `ENOENT` because the three Catalog files do not exist.

- [ ] **Step 3: Define the exact Catalog shapes**

Create `00-traceability-contract.md` and the three JSON files with these root shapes:

```json
{
  "schema_version": "merged-platform-blueprint-v1",
  "capabilities": [],
  "pages": []
}
```

```json
{
  "schema_version": "merged-platform-blueprint-v1",
  "interfaces": []
}
```

```json
{
  "schema_version": "merged-platform-blueprint-v1",
  "services": [],
  "data_owners": [],
  "events": [],
  "traces": []
}
```

`00-traceability-contract.md` must make these fields mandatory:

- Capability: `id`, `domain`, `name`, `decision`, `description`, `page_ids`.
- Page: `id`, `route`, `name`, `domain`, `states`.
- Interface: `id`, `method`, `path`, `request_model`, `response_model`, `response_kind`, `success_statuses`, `errors`, `idempotency`, `service_id`, `read_data_owner_ids`, `write_data_owner_ids`, `event_ids`, `security`, `fact_envelope_fields`.
- Trace: `capability_id`, `page_ids`, `api_ids`, `service_ids`, `data_owner_ids`, `event_ids`, `local_interaction`.

Allowed `decision` values are exactly `retain`, `merge`, `remove`, and `add`. Allowed freshness states are exactly `fresh`, `stale`, `unavailable`, and `quarantined`.

- [ ] **Step 4: Populate the page inventory**

Add these exact pages to `capabilities.json`:

```text
PAGE-P01 /market-home        全市场首页
PAGE-P02 /themes             主题研究
PAGE-P03 /assets/:assetId    资产观察
PAGE-P04 /fingpt             FinGPT
PAGE-P05 /claw               Claw
PAGE-P06 /watchlists         自选与提醒
PAGE-P07 /research-library   研究资料库
PAGE-P08 /capabilities       能力中心
```

Every page declares `default`, `loading`, `empty`, `partial`, `error`, and `permission_denied`. Fact pages additionally declare `stale`, `unavailable`, and `quarantined`; Claw declares `blocked_runtime`.

- [ ] **Step 5: Populate capability decisions**

Add capabilities under the domains `market`, `theme`, `asset`, `fingpt`, `claw`, `research-core`, and `platform-core`. At minimum include:

```text
CAP-RES-001 shared-workspace        merge
CAP-RES-002 shared-evidence         merge
CAP-RES-003 shared-research-notes   merge
CAP-FIN-001 instant-research        retain
CAP-FIN-002 report-distillation     retain
CAP-FIN-003 upgrade-to-claw         add
CAP-CLW-001 supervisor              retain
CAP-CLW-002 agent-team              retain
CAP-CLW-003 agent-schedule          retain
CAP-CLW-004 duplicated-chat-shell   remove
CAP-MKT-001 five-section-home       add
CAP-THM-001 pack-catalog            add
CAP-AST-001 unified-asset-snapshot  add
CAP-AST-002 peer-comparison         add
CAP-ALT-001 alert-state-machine     add
CAP-PLT-001 runtime-provider        add
CAP-PLT-002 allowlisted-mcp         add
```

Add a trace for every capability. Removed capabilities use `local_interaction: false`, empty page/API lists, and a non-empty `replacement_capability_ids` field.

- [ ] **Step 6: Run the contract subset and commit**

Run:

```bash
node --test --test-name-pattern "blueprint identifiers are unique and typed" tests/javascript/merged_platform_blueprint.test.mjs
```

Expected: the identifier contract test PASS; the two inventory-dependent tests are reported as skipped by the name filter.

```bash
git add docs/architecture/merged-platform/detailed/00-traceability-contract.md docs/architecture/merged-platform/detailed/catalog/capabilities.json docs/architecture/merged-platform/detailed/catalog/api-atlas.json docs/architecture/merged-platform/detailed/catalog/traceability.json tests/javascript/merged_platform_blueprint.test.mjs
git commit -m "docs: establish merged platform traceability contract"
```

## Task 2: Complete the API Atlas inventory and generator

**Files:**

- Modify: `docs/architecture/merged-platform/detailed/catalog/api-atlas.json`
- Modify: `docs/architecture/merged-platform/detailed/catalog/traceability.json`
- Create: `scripts/architecture/build_merged_platform_atlas.mjs`
- Modify: `tests/javascript/merged_platform_blueprint.test.mjs`
- Create: `outputs/merged-platform-blueprint/api-atlas.html`
- Create: `outputs/merged-platform-blueprint/index.html`

- [ ] **Step 1: Inventory every public endpoint**

Create entries for these method/path pairs; paths are additive and must not introduce `/api/v2`:

```text
GET,POST              /api/research-workspaces
GET,PATCH             /api/research-workspaces/{workspace_id}
GET,POST              /api/research-sessions
GET,PATCH              /api/research-sessions/{session_id}
GET,POST              /api/research-sessions/{session_id}/messages
GET,POST              /api/research-runs
GET                   /api/research-runs/{run_id}
POST                  /api/research-runs/{run_id}/cancel
POST                  /api/research-runs/{run_id}/retry
GET                   /api/research-runs/{run_id}/events
GET,POST              /api/runtime-providers
GET,PATCH              /api/runtime-providers/{provider_id}
GET,POST              /api/research-skills
GET,PATCH              /api/research-skills/{skill_id}
GET,POST              /api/agent-teams
GET,PATCH              /api/agent-teams/{team_id}
GET,POST              /api/agent-schedules
GET,PATCH,DELETE       /api/agent-schedules/{schedule_id}
GET                   /api/market-home
GET                   /api/market-home/snapshots/{trading_day}
GET                   /api/market-home/events
GET                   /api/theme-packs
GET                   /api/theme-packs/{pack_key}
GET                   /api/theme-packs/{pack_key}/snapshot
GET                   /api/theme-packs/{pack_key}/kpis
GET                   /api/theme-packs/{pack_key}/value-chain
GET                   /api/theme-packs/{pack_key}/events
GET                   /api/theme-packs/{pack_key}/assets
GET                   /api/theme-packs/{pack_key}/data-health
POST                  /api/theme-packs/{pack_key}/research-workspaces
GET                   /api/assets/search
GET                   /api/assets/{asset_id}
GET                   /api/assets/{asset_id}/peers
GET                   /api/assets/{asset_id}/events
GET,POST              /api/watchlists
GET,PATCH,DELETE       /api/watchlists/{watchlist_id}
POST                  /api/watchlists/{watchlist_id}/items
DELETE                /api/watchlists/{watchlist_id}/items/{item_id}
GET,POST              /api/alert-rules
GET,PATCH,DELETE       /api/alert-rules/{rule_id}
GET                   /api/alert-events
POST                  /api/alert-events/{event_id}/acknowledge
GET                   /api/notifications
POST                  /api/notifications/{notification_id}/read
```

Split comma-separated methods into separate entries and assign stable `API-*` identifiers. GET has `idempotency.required: false`; POST/PATCH/DELETE has `true` except acknowledgement/read endpoints, which declare deterministic resource idempotency.

- [ ] **Step 2: Define errors and event contracts**

Every interface declares relevant errors from this closed set:

```json
{
  "400": "validation_error",
  "401": "authentication_required",
  "403": "permission_denied",
  "404": "not_found",
  "409": "conflict_or_idempotency_mismatch",
  "422": "semantic_validation_error",
  "429": "budget_or_rate_limit",
  "503": "provider_or_data_unavailable"
}
```

SSE entries declare `Last-Event-ID`, heartbeat, reconnect delay, terminal event, and replay boundary. Register these event ids in `traceability.json`:

```text
EVT-RES-001 research.run.queued
EVT-RES-002 research.run.progress
EVT-RES-003 research.run.completed
EVT-RES-004 research.run.failed
EVT-RES-005 research.run.blocked_runtime
EVT-MKT-001 market_home.section_invalidated
EVT-ALT-001 alert.triggered
EVT-ALT-002 alert.resolved
EVT-ALT-003 alert.skipped_data_stale
EVT-SCH-001 scheduled_job.leased
EVT-SCH-002 scheduled_job.coalesced
EVT-NOT-001 notification.created
```

- [ ] **Step 3: Implement the deterministic generator**

Create `scripts/architecture/build_merged_platform_atlas.mjs` with this interface:

```js
export function validateCatalogs({ capabilities, atlas, traceability }) {
  // Return an array of human-readable errors; never silently repair data.
}

export function renderApiAtlas({ capabilities, atlas, traceability }) {
  // Return a complete self-contained HTML document with embedded JSON.
}

export function renderBlueprintIndex({ diagramGroups, atlasPath }) {
  // Return the navigation HTML for outputs/merged-platform-blueprint/index.html.
}
```

The CLI accepts:

```bash
node scripts/architecture/build_merged_platform_atlas.mjs \
  --catalog-dir docs/architecture/merged-platform/detailed/catalog \
  --output-dir outputs/merged-platform-blueprint
```

It must log the number of capabilities, pages, APIs and traces, exit non-zero on validation errors, write atomically through a same-directory temporary file, and never modify the Catalog input. The command wrapper creates `logs/` when absent and tees structured execution output to `logs/merged-platform-blueprint.log`; caught errors must include the failed phase and input path without swallowing the original message.

- [ ] **Step 4: Add generator tests**

Append tests that import the two render functions and assert:

```js
test('API Atlas renders filters and embedded trace links', async () => {
  const html = renderApiAtlas(await loadAllCatalogs());
  assert.match(html, /data-filter="domain"/);
  assert.match(html, /data-filter="method"/);
  assert.match(html, /API-RES-001/);
  assert.match(html, /CAP-RES-001/);
  assert.doesNotMatch(html, /TODO|TBD|FIXME/);
});
```

- [ ] **Step 5: Run tests, build, and commit**

Run:

```bash
node --test tests/javascript/merged_platform_blueprint.test.mjs
mkdir -p logs
node scripts/architecture/build_merged_platform_atlas.mjs --catalog-dir docs/architecture/merged-platform/detailed/catalog --output-dir outputs/merged-platform-blueprint 2>&1 | tee logs/merged-platform-blueprint.log
```

Expected: tests PASS; build logs exact counts and creates `api-atlas.html` and `index.html`.

Commit:

```bash
git add docs/architecture/merged-platform/detailed/catalog docs/architecture/merged-platform/detailed/00-traceability-contract.md scripts/architecture/build_merged_platform_atlas.mjs tests/javascript/merged_platform_blueprint.test.mjs outputs/merged-platform-blueprint/api-atlas.html outputs/merged-platform-blueprint/index.html
git commit -m "docs: add merged platform API atlas"
```

## Task 3: Author the eight shared-platform diagrams

**Files:**

- Create: `docs/architecture/merged-platform/detailed/01-shared-platform.md`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A01-capability-landscape.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A02-web-tauri-deployment.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A03-module-dependencies.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A04-data-ownership.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A05-core-er.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A06-events-scheduler.dataflow.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A07-security-boundaries.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/A08-migration-deletion-gate.workflow.json`

- [ ] **Step 1: Read only the required Archify contracts**

Read `schemas/common.schema.json`, the schema matching each diagram type, one matching example, and `references/authoring-contract.md`. Do not inspect renderer internals before authoring the first candidate.

- [ ] **Step 2: Author the exact semantic coverage**

Use `meta.quality_profile: "showcase"`, Chinese reader-facing labels, no more than twelve primary nodes, and these main paths:

```text
A01: user goal → product domain → capability decision → implementation trace
A02: browser/Tauri → FastAPI → modular services → PostgreSQL; optional DSH and native notification as side branches
A03: page/API → owning service → shared contracts → owned repository; forbidden cross-table access shown as boundary note
A04: source → fact zone / research zone / personal zone → allowed consumers
A05: canonical asset/workspace/theme/watchlist roots → dependent tables → reused Research Run and fact tables
A06: scheduler request → persisted job → lease → domain event → handler → notification; retry/coalesce branches
A07: user input → API validation → tool allowlist → MCP registry → Runtime Provider; DSH cannot reach database
A08: dry-run → accepted/quarantined/rejected → equivalence gate → read-only archive → deletion; rollback before deletion
```

- [ ] **Step 3: Validate each source immediately**

Run for every file using its actual type:

```bash
node /Users/leon/.codex/skills/archify/bin/archify.mjs validate architecture docs/architecture/merged-platform/detailed/diagrams/A01-capability-landscape.architecture.json --quality showcase --json
```

Expected: nine artifact checks, zero composition errors, zero warnings. Repair only the reported subject.

- [ ] **Step 4: Commit the shared sources**

```bash
git add docs/architecture/merged-platform/detailed/01-shared-platform.md docs/architecture/merged-platform/detailed/diagrams/A0*.json
git commit -m "docs: add shared platform detail diagrams"
```

## Task 4: Author the Market Home and Theme domain sets

**Files:**

- Create: `docs/architecture/merged-platform/detailed/02-market-home.md`
- Create: `docs/architecture/merged-platform/detailed/03-theme-research.md`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D01-01-market-capabilities.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D01-02-market-interfaces.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D01-03-market-request.sequence.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D01-04-market-state.lifecycle.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D01-05-market-dataflow.dataflow.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D02-01-theme-capabilities.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D02-02-theme-interfaces.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D02-03-theme-request.sequence.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D02-04-pack-state.lifecycle.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D02-05-theme-dataflow.dataflow.json`

- [ ] **Step 1: Author Market Home diagrams**

Cover the five fixed sections, trading session enum, live projection, close snapshot, transparent mainline components, section invalidation SSE, historical snapshot-only reads, and stale/unavailable degradation. The lifecycle main path is `pre_open → open → lunch_break → open → closed`; `non_trading_day` is an alternate terminal day state.

- [ ] **Step 2: Author Theme diagrams**

Cover Manifest, registry, normalize/validate/derive plugin boundary, Observation, Quality Gate, typed read models, the four initial Packs, related assets, data health, and `discovered → validated → enabled → degraded/disabled`.

- [ ] **Step 3: Validate and commit**

Run `archify validate` for all ten sources using the suffix type. Expected: ten showcase passes.

```bash
git add docs/architecture/merged-platform/detailed/02-market-home.md docs/architecture/merged-platform/detailed/03-theme-research.md docs/architecture/merged-platform/detailed/diagrams/D01-*.json docs/architecture/merged-platform/detailed/diagrams/D02-*.json
git commit -m "docs: detail market and theme domains"
```

## Task 5: Author the Asset Observation and FinGPT domain sets

**Files:**

- Create: `docs/architecture/merged-platform/detailed/04-asset-observation.md`
- Create: `docs/architecture/merged-platform/detailed/05-fingpt.md`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D03-01-asset-capabilities.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D03-02-asset-interfaces.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D03-03-alert-request.sequence.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D03-04-alert-state.lifecycle.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D03-05-asset-dataflow.dataflow.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D04-01-fingpt-capabilities.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D04-02-fingpt-interfaces.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D04-03-fingpt-request.sequence.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D04-04-fingpt-run.lifecycle.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D04-05-fingpt-dataflow.dataflow.json`

- [ ] **Step 1: Author Asset diagrams**

Cover canonical identity, four asset types, type payload, peer-set rules, Watchlist, false-to-true trigger, cooldown dedupe, resolved transition, `skipped_data_stale`, persistent inbox and Tauri notification bridge.

- [ ] **Step 2: Author FinGPT diagrams**

Cover unified input routing for text/URL/PDF/image, Workspace/Session/Message, retrieval, Evidence/Claim/Artifact, Note pinning, SSE, background session switching, cancellation, LangGraph fallback and upgrade-to-Claw handoff.

- [ ] **Step 3: Validate and commit**

Run `archify validate` for all ten sources. Expected: ten showcase passes.

```bash
git add docs/architecture/merged-platform/detailed/04-asset-observation.md docs/architecture/merged-platform/detailed/05-fingpt.md docs/architecture/merged-platform/detailed/diagrams/D03-*.json docs/architecture/merged-platform/detailed/diagrams/D04-*.json
git commit -m "docs: detail asset and FinGPT domains"
```

## Task 6: Author the Claw and Platform Core domain sets

**Files:**

- Create: `docs/architecture/merged-platform/detailed/06-claw.md`
- Create: `docs/architecture/merged-platform/detailed/07-platform-core.md`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D05-01-claw-capabilities.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D05-02-claw-interfaces.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D05-03-claw-request.sequence.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D05-04-claw-run.lifecycle.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D05-05-claw-dataflow.dataflow.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D06-01-core-capabilities.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D06-02-core-interfaces.architecture.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D06-03-schedule-request.sequence.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D06-04-scheduled-job.lifecycle.json`
- Create: `docs/architecture/merged-platform/detailed/diagrams/D06-05-core-dataflow.dataflow.json`

- [ ] **Step 1: Author Claw diagrams**

Cover Supervisor, Team Definition, Shared Blackboard, Skill, allowlisted MCP, Runtime Provider, maximum steps/concurrency/token/cost/deadline, `blocked_runtime`, resume, Quality Gate and Artifact return to the shared research core.

- [ ] **Step 2: Author Platform Core diagrams**

Cover Runtime registry, Skill validation, Scheduler Coordinator, job lease, missed-run coalescing, Domain Event, notification persistence and desktop delivery. Show internal Contracts separately from public HTTP APIs.

- [ ] **Step 3: Validate and commit**

Run `archify validate` for all ten sources. Expected: ten showcase passes.

```bash
git add docs/architecture/merged-platform/detailed/06-claw.md docs/architecture/merged-platform/detailed/07-platform-core.md docs/architecture/merged-platform/detailed/diagrams/D05-*.json docs/architecture/merged-platform/detailed/diagrams/D06-*.json
git commit -m "docs: detail Claw and platform core domains"
```

## Task 7: Deliver all diagrams and collect bounded visual evidence

**Files:**

- Create: `outputs/merged-platform-blueprint/diagrams/*.html`
- Create: `outputs/merged-platform-blueprint/diagrams/*.visual-check.*`

- [ ] **Step 1: Deliver from frozen sources**

For each of the thirty-eight validated sources run:

```bash
node /Users/leon/.codex/skills/archify/bin/archify.mjs deliver <type> <source.json> <output.html> --quality showcase --json
```

Expected: exit zero with source/artifact SHA-256 and byte counts. Never edit a source after its successful delivery without revalidating and redelivering it.

- [ ] **Step 2: Run visual-check**

For each delivered HTML run:

```bash
node /Users/leon/.codex/skills/archify/bin/archify.mjs visual-check <output.html> --json
```

Expected: containment passes at 1440×900, 1600×1000, 1920×1080 and 2048×1320. Inspect smallest and largest light/dark contact sheets; record any unresolved visual issue truthfully.

- [ ] **Step 3: Commit outputs**

```bash
git add outputs/merged-platform-blueprint/diagrams
git commit -m "docs: deliver detailed architecture diagrams"
```

## Task 8: Build the detailed index and enforce coverage

**Files:**

- Create: `docs/architecture/merged-platform/detailed/README.md`
- Modify: `docs/architecture/merged-platform/README.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `outputs/merged-platform-blueprint/index.html`
- Modify: `tests/javascript/merged_platform_blueprint.test.mjs`

- [ ] **Step 1: Add full coverage tests**

Assert exactly eight shared and thirty domain sources, a matching delivered HTML for each, unique identifiers, no orphan API, no orphan event, and no capability without a page/API trace unless explicitly local or removed.

```js
assert.equal(sharedDiagrams.length, 8);
assert.equal(domainDiagrams.length, 30);
assert.deepEqual(sourceStems, deliveredStems);
```

- [ ] **Step 2: Generate and update indexes**

Run the generator again after diagrams exist. `index.html` must group artifacts by Shared, Market, Theme, Asset, FinGPT, Claw and Platform Core and link the API Atlas. Documentation indexes must state dependency order and point product prototype implementers to Catalog identifiers.

- [ ] **Step 3: Run final checks**

```bash
node --test tests/javascript/merged_platform_blueprint.test.mjs
node scripts/architecture/build_merged_platform_atlas.mjs --catalog-dir docs/architecture/merged-platform/detailed/catalog --output-dir outputs/merged-platform-blueprint
rg -n "TODO|TBD|FIXME|待定" docs/architecture/merged-platform/detailed outputs/merged-platform-blueprint
git diff --check
```

Expected: tests PASS; `rg` has no output; diff check passes.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/merged-platform/detailed docs/architecture/merged-platform/README.md docs/FILE_GUIDE.md docs/CHANGELOG.md scripts/architecture/build_merged_platform_atlas.mjs tests/javascript/merged_platform_blueprint.test.mjs outputs/merged-platform-blueprint
git commit -m "docs: publish merged platform implementation blueprint"
```
