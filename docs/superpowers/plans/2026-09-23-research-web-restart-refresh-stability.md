# Research Web Restart and Refresh Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make restart use authoritative DSH activity, remove sequential session-list latency, and show truthful progressive browser loading without weakening fail-closed safety.

**Architecture:** The process manager will validate one authenticated DSH `session/list` response and block restart on any running session. The BFF will preserve every parent-scoped child query but run at most eight concurrently. The UI catalog will track pending resources explicitly and render each resource as it settles, distinguishing “connecting” from a real offline result.

**Tech Stack:** Python 3.12, FastAPI/asyncio, DSH loopback RPC, vanilla JavaScript modules, Node test runner, pytest, GitHub Actions, ResearchWorkbench incremental-validation and delivery controller.

---

## File map

- `.agents/verification-policy.json`: focused API/UI test routes and required macOS Bootstrap for service-manager changes.
- `tests/javascript/verification_policy.test.mjs`: planner contracts for the new focused routes and external gate.
- `app/research_web/service_manager.py`: authenticated DSH session snapshot and restart activity guard.
- `tests/research_web/test_service_manager.py`: DSH protocol, idle/running and fail-closed regression tests.
- `app/research_web/service.py`: bounded concurrent `subagent.list` fan-out.
- `tests/research_web/test_api.py`: concurrency, ordering, running-state and error propagation contracts.
- `app/research_web/ui/app.mjs`: pending catalog state and progressive rendering.
- `app/research_web/ui/composer.mjs`: distinct connecting/offline captions.
- `tests/javascript/research_web_capabilities_ui.test.mjs`: composer state contracts.
- `tests/javascript/research_web_ui.test.mjs`: app catalog-loading source/behavior contracts.
- `docs/architecture/research-web/02-research-runtime.md`: authoritative restart and catalog flow.
- `docs/architecture/research-web/05-security-validation.md`: fail-closed and concurrency boundaries.
- `docs/research-web-ui.md`: connecting/offline UI semantics.
- `docs/architecture/research-web/readme-review.json`: required README review receipt for Research Web source changes.
- `docs/research-web-appearance.md`, `docs/architecture/research-web/08-research-frameworks.md`: UI-group unchanged receipts.
- `docs/architecture/research-web/01-system.md`, `04-api.md`, `09-integration-coordinator.md`, `docs/research-web-tabbit.md`: Research API cross-module receipts.
- `docs/architecture/research-web/README.md`, `03-data-files.md`, `docs/research-web-capabilities.md`: shared service/automation boundary receipts.
- `.ai/reports/2026-09-23-research-web-restart-refresh-stability*.json` and `.md`: generated plan, receipt and evidence.

### Task 0: Move the approved design and plan into a managed delivery feature worktree

**Files:**
- Existing: `docs/superpowers/specs/2026-09-23-research-web-restart-refresh-stability-design.md`
- Existing: `docs/superpowers/plans/2026-09-23-research-web-restart-refresh-stability.md`

- [ ] **Step 1: Commit this implementation plan in the audit worktree**

```bash
git add docs/superpowers/plans/2026-09-23-research-web-restart-refresh-stability.md
git commit -m "docs: plan restart and refresh stability"
```

Expected: the audit branch contains exactly the reviewed spec and plan commits above `origin/master`; ignored `.venv` remains untracked.

- [ ] **Step 2: Start the already-created delivery task**

Run from `/Users/leon/Desktop/Projects/ResearchWorkbench`:

```bash
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --start \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id research-web-restart-refresh-stability-delivery \
  --slug restart-refresh-stability
```

Expected feature worktree:

`/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/research-web-restart-refresh-stability-delivery`

- [ ] **Step 3: Fast-forward the managed feature branch to the reviewed commits**

```bash
git -C /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/research-web-restart-refresh-stability-delivery \
  merge --ff-only codex/post-p1-health-audit
git -C /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/research-web-restart-refresh-stability-delivery \
  log -2 --oneline
```

Expected: the exact spec and plan commits are preserved; no patch is recreated and no source file changes yet.

### Task 1: Calibrate incremental validation for service lifecycle, API and UI changes

**Files:**
- Modify: `.agents/verification-policy.json`
- Modify: `tests/javascript/verification_policy.test.mjs`

- [ ] **Step 1: Write failing policy contracts**

Add test catalogs to the policy fixture:

```javascript
"research-web-api": catalog(
  "L1",
  "python -m pytest tests/research_web/test_api.py",
),
"research-web-ui": catalog(
  "L1",
  "node --test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs",
),
```

Add fixture rules equivalent to:

```javascript
rule({
  id: "research-web-api",
  risk: "local-only",
  minimumLevel: "L1",
  reason: "research_web_api_change",
  impact: ["research-web-api"],
  coupling: "low",
  match: {
    files: ["app/research_web/service.py", "tests/research_web/test_api.py"],
    prefixes: [], segments: [], suffixes: [],
  },
  tests: ["research-web-api", "research-web-architecture", "project-constraints-local"],
  documentation: ["documentation-governance", "python-file-index"],
  ci: ["project-constraints", "research-web-checks"],
}),
rule({
  id: "research-web-ui-core",
  risk: "local-only",
  minimumLevel: "L1",
  reason: "research_web_ui_change",
  impact: ["research-web-ui"],
  coupling: "low",
  match: {
    files: [
      "app/research_web/ui/app.mjs",
      "app/research_web/ui/composer.mjs",
      "tests/javascript/research_web_ui.test.mjs",
      "tests/javascript/research_web_capabilities_ui.test.mjs",
    ],
    prefixes: [], segments: [], suffixes: [],
  },
  tests: ["research-web-ui", "research-web-architecture", "project-constraints-local"],
  documentation: ["documentation-governance"],
  ci: ["project-constraints", "research-web-checks"],
}),
```

Add a production-only delivery rule while retaining the existing focused service-manager rule for test-only changes:

```javascript
rule({
  id: "research-web-service-lifecycle-delivery",
  risk: "full-delivery",
  minimumLevel: "L4",
  reason: "research_web_service_lifecycle_delivery",
  impact: ["research-web-service-lifecycle"],
  coupling: "high",
  match: {
    files: ["app/research_web/service_manager.py"],
    prefixes: [], segments: [], suffixes: [],
  },
  tests: [
    "research-web-service-manager",
    "research-web-architecture",
    "project-constraints-local",
    "research-web-critical-smoke",
    "research-web-verification-full",
  ],
  documentation: ["documentation-governance", "python-file-index"],
  ci: ["project-constraints", "research-web-checks", "research-web-bootstrap"],
}),
```

Add three planner tests:

```javascript
test("service lifecycle changes require the focused test and GitHub macOS bootstrap", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/service_manager.py",
    "tests/research_web/test_service_manager.py",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.equal(plan.tests.some(item => item.id === "research-web-service-manager"), true);
  assert.deepEqual(new Set(plan.receiptTemplate.externalGateIds), new Set([
    "project-constraints", "research-web-checks", "research-web-bootstrap",
  ]));
  assert.equal(
    plan.ci.find(item => item.id === "research-web-bootstrap").value,
    ".github/workflows/research-web-bootstrap.yml#macos-14",
  );
});

test("session catalog source and test use the focused API closure", () => {
  const plan = success(run(repositoryRoot, ["app/research_web/service.py", "tests/research_web/test_api.py"]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L1");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.deepEqual(new Set(plan.tests.map(item => item.id)), new Set([
    "research-web-architecture", "research-web-api",
  ]));
  assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
});

test("core UI source and tests use the focused UI closure", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/ui/app.mjs",
    "app/research_web/ui/composer.mjs",
    "tests/javascript/research_web_ui.test.mjs",
    "tests/javascript/research_web_capabilities_ui.test.mjs",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L1");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.deepEqual(new Set(plan.tests.map(item => item.id)), new Set([
    "research-web-architecture", "research-web-ui",
  ]));
  assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
});
```

- [ ] **Step 2: Run RED policy tests**

```bash
node --test tests/javascript/verification_policy.test.mjs
```

Expected: the new tests fail because API/UI paths are unknown and the service-manager route lacks Bootstrap.

- [ ] **Step 3: Implement the production policy entries**

Add JSON equivalents of both catalogs, both focused API/UI rules, and the production-only lifecycle delivery rule. Do not broaden the generic `research-web`, generic `ci`, or test-only `research-web-service-manager` rules.

- [ ] **Step 4: Run GREEN policy tests and focused planner probes**

```bash
node --test tests/javascript/verification_policy.test.mjs
node scripts/plan_verification.mjs --project . \
  --changed-file app/research_web/service_manager.py \
  --changed-file tests/research_web/test_service_manager.py
node scripts/plan_verification.mjs --project . \
  --changed-file app/research_web/service.py \
  --changed-file tests/research_web/test_api.py
node scripts/plan_verification.mjs --project . \
  --changed-file app/research_web/ui/app.mjs \
  --changed-file app/research_web/ui/composer.mjs \
  --changed-file tests/javascript/research_web_ui.test.mjs \
  --changed-file tests/javascript/research_web_capabilities_ui.test.mjs
```

Expected: no unknown paths; lifecycle includes Bootstrap; API and UI-only probes remain local-only L1.

- [ ] **Step 5: Commit policy calibration**

```bash
git add .agents/verification-policy.json tests/javascript/verification_policy.test.mjs
git commit -m "ci: route restart and refresh verification"
```

### Task 2: Make restart read authoritative DSH activity

**Files:**
- Modify: `app/research_web/service_manager.py:392-520,630-639`
- Modify: `tests/research_web/test_service_manager.py`

- [ ] **Step 1: Write the failing DSH activity tests**

Add tests covering the private session snapshot:

```python
def test_active_research_uses_all_authoritative_runtime_sessions(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_runtime_sessions",
        lambda: [
            {"sessionId": "idle-parent", "running": False},
            {"sessionId": "running-child", "running": True},
            {"sessionId": "unknown-running", "running": True},
        ],
    )

    assert manager._active_research() == ["running-child", "unknown-running"]


@pytest.mark.parametrize(
    "items",
    [None, [{}], [{"sessionId": "x", "running": "yes"}], [{"sessionId": "", "running": False}]],
)
def test_active_research_fails_closed_on_invalid_runtime_sessions(manager, monkeypatch, items):
    monkeypatch.setattr(manager, "_runtime_sessions", lambda: items)

    with pytest.raises(ServiceManagerError, match="无法核对活动研究"):
        manager._active_research()
```

Add protocol tests for `_runtime_sessions()` using monkeypatched auth and `_json_request`: valid `server-response`, mismatched `rpcId`, `ok:false`, missing/non-dict `value`, and auth unavailable. Assert `_runtime_healthy()` reuses this helper and converts failures to `False`.

- [ ] **Step 2: Run RED service-manager tests**

```bash
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_service_manager.py -q
```

Expected: new tests fail because `_runtime_sessions` does not exist and `_active_research` still calls Web `/sessions`.

- [ ] **Step 3: Implement the authenticated session snapshot**

Add a helper with this contract:

```python
def _runtime_sessions(self) -> list[dict[str, Any]]:
    rpc_id = str(uuid4())
    auth = self._read_runtime_auth()
    if auth is None:
        token = self._runtime_launch_token()
        cookie = self._exchange_runtime_cookie(token) if token else None
        if cookie is None:
            raise ServiceManagerError("DSH 认证不可用")
        auth = self._write_runtime_auth(cookie)
    value = self._json_request(
        self.runtime_port,
        "POST",
        "/api/session/list",
        {
            "type": "client-request",
            "rpcId": rpc_id,
            "method": "session/list",
            "payload": {"args": {"_request": {}}},
        },
        {"Cookie": auth["cookie"]},
    )
    result = value.get("result")
    if (
        value.get("type") != "server-response"
        or value.get("rpcId") != rpc_id
        or not isinstance(result, dict)
        or result.get("ok") is not True
        or not isinstance(result.get("value"), dict)
        or not isinstance(result["value"].get("items"), list)
    ):
        raise ServiceManagerError("DSH 会话状态响应无效")
    return result["value"]["items"]
```

Make `_runtime_healthy()` call `_runtime_sessions()` and return `True` on success, `False` on `ServiceManagerError`.

Make `_active_research()` strictly validate each item before filtering:

```python
def _active_research(self) -> list[str]:
    try:
        items = self._runtime_sessions()
        active = []
        for item in items:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("sessionId"), str)
                or not item["sessionId"]
                or not isinstance(item.get("running"), bool)
            ):
                raise ServiceManagerError("DSH 会话状态响应无效")
            if item["running"]:
                active.append(item["sessionId"])
        return active
    except ServiceManagerError as exc:
        raise ServiceManagerError("无法核对活动研究；未执行重启，可显式使用 --force") from exc
```

- [ ] **Step 4: Run GREEN service-manager tests**

```bash
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_service_manager.py -q
```

Expected: all service-manager tests pass; existing active-research refusal tests remain green.

- [ ] **Step 5: Commit authoritative restart safety**

```bash
git add app/research_web/service_manager.py tests/research_web/test_service_manager.py
git commit -m "fix: use DSH activity for Web restart"
```

### Task 3: Bound session child-state fan-out without reducing coverage

**Files:**
- Modify: `app/research_web/service.py:20-40,592-630`
- Modify: `tests/research_web/test_api.py`

- [ ] **Step 1: Write failing concurrency and error tests**

Add an async-aware native fixture around the real API test service. Populate 50 created session rows, then instrument `subagent.list`:

```python
active = 0
max_active = 0

async def bounded_rpc(method, payload):
    nonlocal active, max_active
    if method == "session.list":
        return {"items": []}
    if method == "subagent.list":
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {
            "entries": ([{"id": "child", "activity": "running"}]
                        if payload["parentSessionId"] == target else [])
        }
    return await original(method, payload)
```

Assert the `/api/research/sessions` response keeps store order/status semantics, `1 < max_active <= 8`, and the target parent is `running`. Add a second test where one `subagent.list` raises `RuntimeFailure`; assert the endpoint returns the existing safe runtime failure rather than silently using empty children.

- [ ] **Step 2: Run RED API tests**

```bash
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest \
  tests/research_web/test_api.py \
  --confcutdir=tests/research_web -q
```

Expected: concurrency assertion fails with `max_active == 1`.

- [ ] **Step 3: Implement bounded concurrency**

Add:

```python
SUBAGENT_LIST_CONCURRENCY = 8
```

In `list_sessions`, replace the sequential child RPC with:

```python
semaphore = asyncio.Semaphore(SUBAGENT_LIST_CONCURRENCY)

async def children_for(row):
    if row.get("deleted_at") is not None or not row["created"]:
        return {"entries": []}
    async with semaphore:
        return await self.client.rpc("subagent.list", {"parentSessionId": row["id"]})

children_by_row = await asyncio.gather(*(children_for(row) for row in rows))
```

Iterate with `for row, children in zip(rows, children_by_row, strict=True)` and retain the existing running/detail reconciliation unchanged.

- [ ] **Step 4: Run GREEN API tests**

```bash
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest \
  tests/research_web/test_api.py \
  --confcutdir=tests/research_web -q
```

Expected: all API tests pass, maximum observed concurrency is 8 or lower and greater than 1.

- [ ] **Step 5: Commit bounded session listing**

```bash
git add app/research_web/service.py tests/research_web/test_api.py
git commit -m "perf: bound session child-state queries"
```

### Task 4: Render connecting state and catalog results progressively

**Files:**
- Modify: `app/research_web/ui/app.mjs:20-65,160-180,325-370`
- Modify: `app/research_web/ui/composer.mjs:75-90`
- Modify: `tests/javascript/research_web_capabilities_ui.test.mjs`
- Modify: `tests/javascript/research_web_ui.test.mjs`

- [ ] **Step 1: Write failing composer state tests**

Add:

```javascript
test('connecting runtime is distinct from a settled offline runtime', () => {
  const pending = composer.renderComposer({
    draft: '继续准备草稿', runtimeReady: false, runtimePending: true,
  });
  assert.doesNotMatch(pending, /<textarea[^>]*disabled/);
  assert.match(pending, /type="submit"[^>]*disabled/);
  assert.match(pending, /正在连接运行时/);
  assert.doesNotMatch(pending, /离线/);

  const offline = composer.renderComposer({
    draft: '继续准备草稿', runtimeReady: false, runtimePending: false,
  });
  assert.match(offline, /未就绪或离线/);
  assert.doesNotMatch(offline, /正在连接运行时/);
});
```

In `research_web_ui.test.mjs`, read `app.mjs` and assert it initializes pending default catalog names, marks requested names before fetch, clears each name in a `finally` path, renders as each request settles, and passes `runtimePending` to composer. This source contract complements the real browser acceptance and prevents regression to a single post-`Promise.all` render.

- [ ] **Step 2: Run RED UI tests**

```bash
node --test \
  tests/javascript/research_web_ui.test.mjs \
  tests/javascript/research_web_capabilities_ui.test.mjs
```

Expected: pending composer and progressive loader assertions fail.

- [ ] **Step 3: Implement pending catalog state**

Define one default list and initialize the catalog:

```javascript
const defaultCatalogNames = ['runtime', 'models', 'workspaces', 'sessions', 'capabilities', 'tools', 'reportWorkflows'];
const catalog = {
  // existing fields unchanged
  pending: new Set(defaultCatalogNames),
};
```

Update `runtimeLabel()`:

```javascript
if (catalog.pending.has('runtime')) return 'DSH 连接中';
if (!catalog.runtime) return 'DSH 未连接';
```

Pass both state dimensions to composer:

```javascript
runtimeReady: catalog.runtime?.connected === true && catalog.runtime?.credential_configured !== false,
runtimePending: catalog.pending.has('runtime'),
```

Update `loadCatalog` so it marks names and renders before awaiting, then clears and renders in each request's `finally`:

```javascript
async function loadCatalog(names = defaultCatalogNames) {
  names.forEach(name => catalog.pending.add(name));
  render();
  await Promise.all(names.map(async (name) => {
    try {
      // existing fetch and assignment chain unchanged
      delete catalog.errors[name];
    } catch (error) {
      catalog.errors[name] = error.message;
      if (name === 'runtime') catalog.runtime = null;
    } finally {
      catalog.pending.delete(name);
      render();
    }
  }));
  if (names.includes('connections') || names.includes('integrations')) {
    catalog.connections = mergeIntegrationStatuses(catalog.connections, catalog.integrations);
  }
  render();
}
```

Extend composer input and caption:

```javascript
runtimePending = false
```

```javascript
const runtimeCaption = runtimePending
  ? '正在连接运行时；可先准备草稿，连接完成后即可发送。'
  : !runtimeReady
    ? '运行时未就绪或离线：无法核对停止；可准备草稿，连接与授权就绪后才能发送。'
    : '';
```

Use `runtimeCaption` before task-pending/default caption. Sending remains disabled whenever `runtimeReady` is false.

- [ ] **Step 4: Run GREEN UI tests**

```bash
node --test \
  tests/javascript/research_web_ui.test.mjs \
  tests/javascript/research_web_capabilities_ui.test.mjs
```

Expected: all tests pass; offline tests retain their existing wording and pending tests never render “离线”.

- [ ] **Step 5: Commit progressive loading**

```bash
git add \
  app/research_web/ui/app.mjs \
  app/research_web/ui/composer.mjs \
  tests/javascript/research_web_ui.test.mjs \
  tests/javascript/research_web_capabilities_ui.test.mjs
git commit -m "fix: render Research Web catalog progress"
```

### Task 5: Synchronize docs and create the real incremental receipt

**Files:**
- Modify: `docs/architecture/research-web/02-research-runtime.md`
- Modify: `docs/architecture/research-web/05-security-validation.md`
- Modify: `docs/research-web-ui.md`
- Modify: `docs/architecture/research-web/readme-review.json`
- Modify: `docs/research-web-appearance.md`
- Modify: `docs/architecture/research-web/08-research-frameworks.md`
- Modify: `docs/architecture/research-web/01-system.md`
- Modify: `docs/architecture/research-web/04-api.md`
- Modify: `docs/architecture/research-web/09-integration-coordinator.md`
- Modify: `docs/research-web-tabbit.md`
- Modify: `docs/architecture/research-web/README.md`
- Modify: `docs/architecture/research-web/03-data-files.md`
- Modify: `docs/research-web-capabilities.md`
- Modify if generated check requires it: `docs/generated/py_file_index.md`
- Create: `.ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json`
- Create: `.ai/reports/2026-09-23-research-web-restart-refresh-stability-receipt.json`
- Create: `.ai/reports/2026-09-23-research-web-restart-refresh-stability.md`

- [ ] **Step 1: Update authoritative documentation**

Document these exact boundaries:

```text
restart -> authenticated DSH session/list -> any running session blocks non-force restart
session catalog -> one session.list + all parent-scoped subagent.list calls with concurrency <= 8
browser catalog -> pending/connecting -> per-resource settled render -> offline only after real failure
```

Add task-report architecture markers for `ui`, `research-api`, and `automations`, each with a concrete unchanged-structure reason and empty diagram list. Update every mechanically required module document above with a concise current-state receipt: only restart authority, bounded catalog reads and loading semantics changed; framework, Tabbit, integrations, capabilities, data-file, automation and information-architecture relationships remain unchanged. Update `readme-review.json` with the exact current review schema and a concrete unchanged README reason. Do not claim remote CI or final browser acceptance before it runs.

- [ ] **Step 2: Generate the exact changed-file plan**

Run this fixed-point generator from the managed feature worktree:

```bash
node - <<'NODE'
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');
const common = execFileSync('git', ['rev-parse', '--git-common-dir'], { encoding: 'utf8' }).trim();
const delivery = JSON.parse(fs.readFileSync(
  path.join(common, 'leon-engineering/deliveries/research-web-restart-refresh-stability-delivery.json'),
  'utf8',
));
const tracked = execFileSync(
  'git', ['diff', '--name-only', `${delivery.baseCommit}..HEAD`], { encoding: 'utf8' },
).trim().split('\n').filter(Boolean);
const reportPaths = [
  '.ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json',
  '.ai/reports/2026-09-23-research-web-restart-refresh-stability-receipt.json',
  '.ai/reports/2026-09-23-research-web-restart-refresh-stability.md',
];
const changed = [...new Set([...tracked, ...reportPaths])].sort();
const args = ['scripts/plan_verification.mjs', '--project', '.'];
for (const file of changed) args.push('--changed-file', file);
const result = spawnSync(process.execPath, args, { encoding: 'utf8' });
if (result.status !== 0) {
  process.stderr.write(result.stderr);
  process.exit(result.status ?? 1);
}
fs.mkdirSync('.ai/reports', { recursive: true });
fs.writeFileSync(
  '.ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json',
  result.stdout,
);
NODE
```

Save the formatted JSON as:

`.ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json`

Expected: no unknown path or uncovered local risk; selected local tests include policy, API, UI, service-manager, architecture, protocol, documentation and Project Constraints; external gates are exactly Project Constraints, Research Web Checks and macOS Bootstrap.

- [ ] **Step 3: Run every local validation emitted by the plan**

The calibrated plan must execute exactly this local closure:

```bash
node --test tests/javascript/verification_policy.test.mjs
node --test tests/javascript/verification_receipt.test.mjs
node --test tests/javascript/incremental_validation_skill.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_service_manager.py -q
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_api.py --confcutdir=tests/research_web -q
node --test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs
node --test tests/javascript/research_web_architecture.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_protocol.py
node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs
node scripts/check_documentation_governance.mjs --project .
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check
node - <<'NODE'
const { spawnSync } = require('node:child_process');
const plan = require('./.ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json');
const args = ['.agents/project-constraints.mjs', '--project', '.'];
for (const file of plan.changedFiles) args.push('--changed-file', file);
const result = spawnSync(process.execPath, args, { stdio: 'inherit' });
process.exit(result.status ?? 1);
NODE
git diff --check
```

Expected local validation IDs are: `verification-policy-contracts`, `verification-receipt-contracts`, `incremental-validation-skill-contracts`, `research-web-api`, `research-web-ui`, `research-web-service-manager`, `research-web-architecture`, `project-constraints-local`, `research-web-critical-smoke`, `research-web-verification-full`, `documentation-governance`, and `python-file-index`. Record real durations and counts.

- [ ] **Step 4: Write and validate the blocked pre-publication receipt**

Create the receipt from the generated template. Local validations are `passed`; all three external gates are `not_run`; `result` is `blocked`; uncovered risks contain one entry for each pending external gate.

```bash
node scripts/validate_verification_receipt.mjs \
  --project . \
  --plan .ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json \
  --receipt .ai/reports/2026-09-23-research-web-restart-refresh-stability-receipt.json
```

Expected: `valid:true`, L4/L4, honestly blocked only on remote gates.

- [ ] **Step 5: Commit local closure**

```bash
git add \
  docs/architecture/research-web/02-research-runtime.md \
  docs/architecture/research-web/05-security-validation.md \
  docs/research-web-ui.md \
  docs/architecture/research-web/readme-review.json \
  docs/research-web-appearance.md \
  docs/architecture/research-web/08-research-frameworks.md \
  docs/architecture/research-web/01-system.md \
  docs/architecture/research-web/04-api.md \
  docs/architecture/research-web/09-integration-coordinator.md \
  docs/research-web-tabbit.md \
  docs/architecture/research-web/README.md \
  docs/architecture/research-web/03-data-files.md \
  docs/research-web-capabilities.md \
  docs/generated/py_file_index.md \
  .ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json \
  .ai/reports/2026-09-23-research-web-restart-refresh-stability-receipt.json \
  .ai/reports/2026-09-23-research-web-restart-refresh-stability.md
git commit -m "docs: record restart and refresh evidence"
```

If the Python index is byte-identical, do not stage it and omit it from the changed set.

### Task 6: Verify real lifecycle, browser behavior and publish

**Files:**
- Modify after remote CI: `.ai/reports/2026-09-23-research-web-restart-refresh-stability-receipt.json`
- Modify after remote CI: `.ai/reports/2026-09-23-research-web-restart-refresh-stability.md`

- [ ] **Step 1: Prepare and verify the merged result**

```bash
date +%s > /tmp/rwb-restart-refresh-verification-started
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --prepare \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id research-web-restart-refresh-stability-delivery
```

In `/Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/research-web-restart-refresh-stability-delivery-integration`, run this exact deterministic closure before any runtime/browser claim:

```bash
node - <<'NODE'
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const planPath = '.ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json';
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const args = ['scripts/plan_verification.mjs', '--project', '.'];
for (const file of plan.changedFiles) args.push('--changed-file', file);
const result = spawnSync(process.execPath, args, { encoding: 'utf8' });
if (result.status !== 0) {
  process.stderr.write(result.stderr);
  process.exit(result.status ?? 1);
}
if (result.stdout !== fs.readFileSync(planPath, 'utf8')) {
  throw new Error('merged verification plan is not deterministic');
}
NODE
node --test tests/javascript/verification_policy.test.mjs
node --test tests/javascript/verification_receipt.test.mjs
node --test tests/javascript/incremental_validation_skill.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_service_manager.py -q
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_api.py --confcutdir=tests/research_web -q
node --test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs
node --test tests/javascript/research_web_architecture.test.mjs
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python -m pytest tests/research_web/test_protocol.py
node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs
node scripts/check_documentation_governance.mjs --project .
/Users/leon/Desktop/Projects/ResearchWorkbench/.venv/bin/python scripts/generate_py_file_index.py --check
node - <<'NODE'
const { spawnSync } = require('node:child_process');
const plan = require('./.ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json');
const args = ['.agents/project-constraints.mjs', '--project', '.'];
for (const file of plan.changedFiles) args.push('--changed-file', file);
const result = spawnSync(process.execPath, args, { stdio: 'inherit' });
process.exit(result.status ?? 1);
NODE
node scripts/validate_verification_receipt.mjs \
  --project . \
  --plan .ai/reports/2026-09-23-research-web-restart-refresh-stability-plan.json \
  --receipt .ai/reports/2026-09-23-research-web-restart-refresh-stability-receipt.json
git diff --check
```

- [ ] **Step 2: Run the real macOS lifecycle acceptance**

Use the integration worktree's public setup entry, then verify:

```text
setup-web.sh --no-start
doctor ok with services stopped
start --no-open
idempotent start preserves both PIDs
restart --no-open succeeds when DSH reports zero running sessions and replaces both PIDs
terminate the owned Runtime PID
start --no-open recreates only Runtime and preserves Web PID
stop -> start succeeds
final stop leaves both services stopped
```

Measure `/api/research/sessions` with the existing 50-session store; require HTTP 200 and elapsed time below 2.0 seconds.

Use this lifecycle shell contract after setup:

```bash
set -euo pipefail
read_pid() {
  .venv/bin/python -c 'import json, pathlib, sys; print(json.loads((pathlib.Path.home()/".research-workbench"/"run"/(sys.argv[1]+".json")).read_text())["pid"])' "$1"
}
./setup-web.sh --no-start
./rwb web doctor --json > /tmp/rwb-restart-refresh-doctor-stopped.json
./rwb web start --no-open
runtime_before=$(read_pid runtime)
web_before=$(read_pid web)
./rwb web start --no-open
test "$(read_pid runtime)" = "$runtime_before"
test "$(read_pid web)" = "$web_before"
./rwb web restart --no-open
runtime_after_restart=$(read_pid runtime)
web_after_restart=$(read_pid web)
test "$runtime_after_restart" != "$runtime_before"
test "$web_after_restart" != "$web_before"
kill -TERM "$runtime_after_restart"
for attempt in $(seq 1 50); do
  if ! kill -0 "$runtime_after_restart" 2>/dev/null; then break; fi
  sleep 0.1
done
if kill -0 "$runtime_after_restart" 2>/dev/null; then exit 23; fi
web_before_recovery=$(read_pid web)
./rwb web start --no-open
test "$(read_pid runtime)" != "$runtime_after_restart"
test "$(read_pid web)" = "$web_before_recovery"
.venv/bin/python - <<'PY'
import json, time, urllib.request
started = time.monotonic()
with urllib.request.urlopen('http://127.0.0.1:8088/api/research/sessions', timeout=10) as response:
    payload = json.load(response)
elapsed = time.monotonic() - started
assert response.status == 200
assert len(payload['items']) >= 50
assert elapsed < 2.0, elapsed
print({'session_count': len(payload['items']), 'elapsed_seconds': round(elapsed, 3)})
PY
./rwb web stop
./rwb web start --no-open
./rwb web status
./rwb web doctor --json
```

Keep services running for Step 3, then run the final `./rwb web stop` after browser evidence is captured.

- [ ] **Step 3: Run browser acceptance**

Open `http://127.0.0.1:8088/#/fingpt` in the Codex in-app browser. On first load and explicit reload:

```text
pending state contains “正在连接运行时” and never “离线”
settled state shows DeepSeek-V4-Flash, enabled send, capability picker and Skill cards
runtime settled UI becomes available without waiting for the slowest catalog
```

Save DOM/screenshot evidence and timings in the task report. Stop services afterward.

- [ ] **Step 4: Publish the reviewed integration commit**

After broad review passes:

```bash
verification_started=$(sed -n '1p' /tmp/rwb-restart-refresh-verification-started)
measured_verification_seconds=$(( $(date +%s) - verification_started ))
test "$measured_verification_seconds" -ge 0
printf '%s\n' "$measured_verification_seconds" > /tmp/rwb-restart-refresh-verification-seconds
node /Users/leon/.agents/leon-engineering/runtime/iteration-delivery.mjs \
  --publish \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id research-web-restart-refresh-stability-delivery \
  --verification-command "merged L4 plan, service/API/UI tests, real restart/recovery, browser first-load/reload, documentation and receipt checks" \
  --verification-status passed \
  --verification-duration-seconds "$(sed -n '1p' /tmp/rwb-restart-refresh-verification-seconds)"
```

Expected automatic runs for the published SHA:

```text
Project Constraints: success
Research Web Checks: success
Research Web Bootstrap: exactly one macos-14 job, success
Research Web Windows Verify: no automatic run
```

- [ ] **Step 5: Persist actual remote evidence and close the delivery**

Update report/receipt with exact commit SHA, run IDs, URLs, attempts and conclusions. Set external gates/result to passed only after all three required gates pass; explicitly retain Windows as unrun/unclaimed.

Commit the two evidence files on the feature branch, prepare a second evidence-only revision, validate receipt/documentation/Project Constraints/diff, publish it, wait for its expected lightweight CI, then run controller cleanup.

Record the Harness outcome with actual clarification/rework counts and measured verification seconds, then run:

```bash
node /Users/leon/.agents/leon-engineering/runtime/harness-enforce.mjs \
  --project /Users/leon/Desktop/Projects/ResearchWorkbench \
  --task-id research-web-restart-refresh-stability-delivery \
  --require-delivery
```

- [ ] **Step 6: Clean the original audit workspace after evidence is durable**

Only after remote `master` contains the exact spec/plan/source/report commits and all Harness gates pass:

```bash
git worktree remove /Users/leon/Desktop/Projects/ResearchWorkbench/.worktrees/post-p1-health-audit
git branch -d codex/post-p1-health-audit
git worktree prune
```

Expected: main checkout remains on current remote `master`; historical `p0-web-stability` evidence worktree remains untouched.
