# Merged Platform Responsive Product Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付同时适用于 Web 和 Tauri 桌面壳的八页高保真响应式产品原型，并可点击完成五条核心用户旅程。

**Architecture:** 原型是无构建依赖的静态 SPA，使用共享设计 Token、产品壳、Hash Router、页面注册表和演示状态 Store。页面从详细架构 Catalog 读取稳定编号并链接 API Atlas；数据适配器优先访问真实 FastAPI，失败时只使用明确标注的演示状态，不伪造市场事实。

**Tech Stack:** HTML、CSS、浏览器原生 JavaScript、Node.js 内置测试、`playwright-core` 浏览器回归、Tauri 复用 Web 资源。

---

## File map

### Product artifact

- `outputs/merged-platform-product-prototype/index.html`：应用入口和无脚本提示。
- `outputs/merged-platform-product-prototype/brand-spec.md`：Logo、Token、引用和禁止漂移规则。
- `outputs/merged-platform-product-prototype/assets/research-workbench-logo.png`：真实品牌资产副本。
- `outputs/merged-platform-product-prototype/styles/tokens.css`：颜色、字体、间距、圆角、阴影和断点 Token。
- `outputs/merged-platform-product-prototype/styles/base.css`：Reset、可访问性、字体和通用状态。
- `outputs/merged-platform-product-prototype/styles/shell.css`：顶栏、产品导航、模块侧栏、主区和研究空间。
- `outputs/merged-platform-product-prototype/styles/components.css`：Composer、卡片、表格、图表容器、抽屉和反馈。
- `outputs/merged-platform-product-prototype/styles/pages.css`：八个页面的领域布局。
- `outputs/merged-platform-product-prototype/styles/responsive.css`：四个响应式区间。

### Runtime modules

- `outputs/merged-platform-product-prototype/scripts/store.js`：唯一原型状态 Store。
- `outputs/merged-platform-product-prototype/scripts/router.js`：Hash 路由和页面生命周期。
- `outputs/merged-platform-product-prototype/scripts/data-adapter.js`：真实 API 优先、演示状态回退。
- `outputs/merged-platform-product-prototype/scripts/shell.js`：产品壳、导航、抽屉和研究空间。
- `outputs/merged-platform-product-prototype/scripts/tweaks.js`：主题、密度、面板和状态切换。
- `outputs/merged-platform-product-prototype/scripts/journeys.js`：五条用户旅程编排。
- `outputs/merged-platform-product-prototype/scripts/pages/*.js`：八个独立页面渲染器。
- `outputs/merged-platform-product-prototype/scripts/app.js`：启动、错误边界和日志。

### Tests and docs

- `tests/javascript/merged_platform_product_prototype.test.mjs`：静态结构、路由、状态和追踪检查。
- `tests/e2e/merged_platform_product_prototype_playwright_core.js`：真实浏览器旅程和响应式检查。
- `docs/architecture/merged-platform/product/brand-spec.md`：正式品牌与设计系统记录。
- `docs/architecture/merged-platform/product/prototype-map.md`：页面、功能、API 和旅程映射。

## Task 1: Scaffold the artifact, brand asset, and failing structure tests

**Files:**

- Create: `tests/javascript/merged_platform_product_prototype.test.mjs`
- Create: `outputs/merged-platform-product-prototype/index.html`
- Create: `outputs/merged-platform-product-prototype/brand-spec.md`
- Create: `outputs/merged-platform-product-prototype/assets/research-workbench-logo.png`

- [ ] **Step 1: Write the failing static structure test**

```js
import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../outputs/merged-platform-product-prototype/', import.meta.url);
const text = (path) => readFile(new URL(path, root), 'utf8');

const requiredFiles = [
  'index.html', 'brand-spec.md', 'assets/research-workbench-logo.png',
  'styles/tokens.css', 'styles/base.css', 'styles/shell.css',
  'styles/components.css', 'styles/pages.css', 'styles/responsive.css',
  'scripts/store.js', 'scripts/router.js', 'scripts/data-adapter.js',
  'scripts/shell.js', 'scripts/tweaks.js', 'scripts/journeys.js',
  'scripts/pages/market-home.js', 'scripts/pages/theme-research.js',
  'scripts/pages/asset-observation.js', 'scripts/pages/fingpt.js',
  'scripts/pages/claw.js', 'scripts/pages/watchlists.js',
  'scripts/pages/research-library.js', 'scripts/pages/capability-center.js',
  'scripts/app.js',
];

test('prototype contains every focused artifact file', async () => {
  await Promise.all(requiredFiles.map((file) => access(new URL(file, root))));
});

test('prototype loads assets in deterministic order', async () => {
  const html = await text('index.html');
  for (const file of requiredFiles.filter((item) => item.endsWith('.css') || item.endsWith('.js'))) {
    assert.match(html, new RegExp(file.replaceAll('.', '\\.')));
  }
  assert.doesNotMatch(html, /TODO|TBD|FIXME/);
});
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
node --test tests/javascript/merged_platform_product_prototype.test.mjs
```

Expected: FAIL because the output directory and focused files do not exist.

- [ ] **Step 3: Copy the real logo and write brand-spec**

Copy, do not redraw, the existing asset:

```bash
mkdir -p outputs/merged-platform-product-prototype/assets
cp src-tauri/icons/icon-black-gold-geometric.png outputs/merged-platform-product-prototype/assets/research-workbench-logo.png
```

`brand-spec.md` must record the source path, SHA-256, AlphaEngine screenshots as product-shell reference, Zhengyan as interaction reference, and these Token values:

```css
--chrome-navy: #061b2e;
--canvas-light: #f5f7fb;
--surface-light: #ffffff;
--action-blue: #2864dc;
--brand-gold: #c99737;
--text-primary: #19212f;
--text-secondary: #69758a;
--market-up: #d94b45;
--market-down: #16866b;
```

State explicitly that the existing Research Workbench VS Code-style UI is not preserved, and that Zhengyan's purple gradient/glass treatment is not copied.

- [ ] **Step 4: Create the HTML load order**

`index.html` loads CSS in Token → base → shell → components → pages → responsive order, then scripts in Store → router → data adapter → shell → tweaks → eight pages → journeys → app order. Use classic scripts so the artifact works under a simple static HTTP server without a bundler.

- [ ] **Step 5: Commit the scaffold**

```bash
git add tests/javascript/merged_platform_product_prototype.test.mjs outputs/merged-platform-product-prototype/index.html outputs/merged-platform-product-prototype/brand-spec.md outputs/merged-platform-product-prototype/assets/research-workbench-logo.png
git commit -m "feat: scaffold merged platform prototype"
```

## Task 2: Build the responsive shell, Store, Router, and Tweaks

**Files:**

- Create: `outputs/merged-platform-product-prototype/styles/tokens.css`
- Create: `outputs/merged-platform-product-prototype/styles/base.css`
- Create: `outputs/merged-platform-product-prototype/styles/shell.css`
- Create: `outputs/merged-platform-product-prototype/styles/components.css`
- Create: `outputs/merged-platform-product-prototype/styles/responsive.css`
- Create: `outputs/merged-platform-product-prototype/scripts/store.js`
- Create: `outputs/merged-platform-product-prototype/scripts/router.js`
- Create: `outputs/merged-platform-product-prototype/scripts/shell.js`
- Create: `outputs/merged-platform-product-prototype/scripts/tweaks.js`

- [ ] **Step 1: Define the Store contract**

```js
window.AlphaPrototype = {
  pages: new Map(),
  listeners: new Set(),
  state: {
    route: '/market-home',
    theme: 'light',
    density: 'compact',
    researchSpaceOpen: true,
    moduleDrawerOpen: false,
    demoState: 'default',
    dataMode: 'live-first',
    activeWorkspaceId: 'workspace-demo',
    activeAssetId: null,
    activePackKey: null,
    activeJourneyId: null,
  },
  setState(patch) {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener(this.state);
  },
  registerPage(route, page) {
    if (this.pages.has(route)) throw new Error(`duplicate route: ${route}`);
    this.pages.set(route, page);
  },
};
```

Every page object implements `title`, `module`, `render(state)`, `mount(container, state)`, and `unmount()`.

- [ ] **Step 2: Implement the product shell**

The shell has five stable areas:

```html
<header data-shell="topbar"></header>
<nav data-shell="product-nav"></nav>
<aside data-shell="module-sidebar"></aside>
<main data-shell="workspace" id="page-root"></main>
<aside data-shell="research-space"></aside>
```

Desktop navigation includes Market Home, Theme, Asset, FinGPT, Claw, Watchlists, Research Library and Capability Center. FinGPT and Claw are separate primary workspaces. The right panel is shared and contains Sources, Evidence, Claims, Notes and Artifacts tabs.

- [ ] **Step 3: Implement responsive contracts**

Use exact behavior:

```text
>=1440px: product nav + module sidebar + main + research space
1024-1439px: compact product nav; research space closed by default
768-1023px: module sidebar and research space are modal drawers
<768px: bottom product nav; full-width main; Composer fixed above nav
```

Touch targets under 768px are at least 44px. Drawer focus returns to its trigger. `prefers-reduced-motion` removes non-essential transitions.

- [ ] **Step 4: Implement Tweaks**

Tweaks controls `theme`, `density`, `researchSpaceOpen`, and `demoState`. It is completely hidden when closed. Allowed demo states are `default`, `loading`, `empty`, `partial`, `stale`, `unavailable`, `quarantined`, `error`, `permission_denied`, and `blocked_runtime`.

- [ ] **Step 5: Extend and run the structure tests**

Add assertions for the four breakpoints, reduced motion, visible focus, and every demo state string.

```bash
node --test tests/javascript/merged_platform_product_prototype.test.mjs
```

Expected: file-order and shell tests PASS; page registration tests remain pending until Tasks 3–6.

- [ ] **Step 6: Commit**

```bash
git add outputs/merged-platform-product-prototype/styles outputs/merged-platform-product-prototype/scripts/store.js outputs/merged-platform-product-prototype/scripts/router.js outputs/merged-platform-product-prototype/scripts/shell.js outputs/merged-platform-product-prototype/scripts/tweaks.js tests/javascript/merged_platform_product_prototype.test.mjs
git commit -m "feat: add responsive research product shell"
```

## Task 3: Implement FinGPT and the shared research space

**Files:**

- Create: `outputs/merged-platform-product-prototype/scripts/data-adapter.js`
- Create: `outputs/merged-platform-product-prototype/scripts/pages/fingpt.js`
- Modify: `outputs/merged-platform-product-prototype/styles/pages.css`
- Modify: `outputs/merged-platform-product-prototype/styles/components.css`

- [ ] **Step 1: Implement live-first data semantics**

```js
window.AlphaData = {
  async request(path, { fallback } = {}) {
    try {
      const response = await fetch(path, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return { mode: 'live', value: await response.json(), error: null };
    } catch (error) {
      return { mode: 'demo', value: fallback ?? null, error: String(error) };
    }
  },
};
```

Every fallback-rendered region displays `演示状态`; no fallback may contain unlabeled prices, returns, volumes or valuation figures.

- [ ] **Step 2: Implement the FinGPT empty/home state**

Include AlphaEngine-style centered research prompt, capability actions, unified text/URL/PDF/image Composer, current questions, history sidebar and the shared research-space panel. Reuse these Zhengyan reference questions as labeled prompts: `存储涨价到哪一段了？`, `日元套息风险高吗？`, `AI 收入真赚钱吗？`.

- [ ] **Step 3: Implement run and result states**

The running state shows queued/progress events, sources appearing in the right panel and a cancel action. The result state shows Evidence, Claim, Artifact actions, pin-to-Note, export controls and “升级为 Claw 任务”. Background runs remain visible when switching sessions.

- [ ] **Step 4: Register tracking links**

Add links for `CAP-FIN-*`, `PAGE-P04`, and all FinGPT `API-*` identifiers to `../merged-platform-blueprint/api-atlas.html#<id>`.

- [ ] **Step 5: Commit**

```bash
git add outputs/merged-platform-product-prototype/scripts/data-adapter.js outputs/merged-platform-product-prototype/scripts/pages/fingpt.js outputs/merged-platform-product-prototype/styles/pages.css outputs/merged-platform-product-prototype/styles/components.css
git commit -m "feat: prototype FinGPT research workspace"
```

## Task 4: Implement Claw as a distinct Agent task workspace

**Files:**

- Create: `outputs/merged-platform-product-prototype/scripts/pages/claw.js`
- Modify: `outputs/merged-platform-product-prototype/styles/pages.css`

- [ ] **Step 1: Build the task-first Claw home**

Do not duplicate FinGPT's “new chat” language. Use New Task, Running, Agent Teams, Schedules, Skills and Blackboard. The main composer accepts a goal and exposes Team, Skill, Runtime, budget, deadline and confirmation controls.

- [ ] **Step 2: Build the run board**

Show Supervisor plan, Agent lane status, Blackboard updates, tool/MCP calls, token/cost budget, deadline, Quality Gate and final Artifact. `blocked_runtime` must stop the main path and show missing capability plus Resolve Provider and Resume actions.

- [ ] **Step 3: Preserve shared-core behavior**

Claw reads the same Workspace, Evidence, Claims, Notes and Artifacts shown by FinGPT. Completion returns the Artifact to Research Library; no duplicate Claw history database is implied.

- [ ] **Step 4: Commit**

```bash
git add outputs/merged-platform-product-prototype/scripts/pages/claw.js outputs/merged-platform-product-prototype/styles/pages.css
git commit -m "feat: prototype Claw agent workspace"
```

## Task 5: Implement Market Home and Theme Research

**Files:**

- Create: `outputs/merged-platform-product-prototype/scripts/pages/market-home.js`
- Create: `outputs/merged-platform-product-prototype/scripts/pages/theme-research.js`
- Modify: `outputs/merged-platform-product-prototype/styles/pages.css`

- [ ] **Step 1: Build the five-section Market Home**

Render exactly Global Context, A-share Status, Market Mainlines, Important Events and Asset Moves. Every fact block shows `as_of`, source count and freshness. Historical date selection reads a close snapshot state; `stale` and `unavailable` are section-level, not full-page errors. Do not include AI summaries, research tasks, Watchlists, Agent status or system health.

- [ ] **Step 2: Build Theme Catalog and detail state**

The same page route switches between catalog and selected Pack. Detail contains Snapshot, KPI Series, Value Chain, Related Assets, Events and Data Health. Include Gold, Aerospace, Photovoltaic and AI Infrastructure/Optical Modules. Display Pack lifecycle and compatibility version.

- [ ] **Step 3: Add drill-through actions**

Market mainline → Theme Pack; Theme asset → Asset Detail; Theme action → prefilled FinGPT Workspace. Preserve API/CAP identifiers in `data-trace-id` attributes.

- [ ] **Step 4: Commit**

```bash
git add outputs/merged-platform-product-prototype/scripts/pages/market-home.js outputs/merged-platform-product-prototype/scripts/pages/theme-research.js outputs/merged-platform-product-prototype/styles/pages.css
git commit -m "feat: prototype market and theme research"
```

## Task 6: Implement Asset Observation and Watchlists

**Files:**

- Create: `outputs/merged-platform-product-prototype/scripts/pages/asset-observation.js`
- Create: `outputs/merged-platform-product-prototype/scripts/pages/watchlists.js`
- Modify: `outputs/merged-platform-product-prototype/styles/pages.css`

- [ ] **Step 1: Build the unified Asset Detail**

Render common identity, quote/NAV, history, events, themes, sources and type payload for stock, index, ETF and active fund. Peer comparison always shows peer-set definition and sample size. Missing type fields render `—` with a reason, never zero.

- [ ] **Step 2: Build Watchlist and Alert flows**

Support list creation, add/remove item, price/NAV/change/flow/valuation/holding/announcement/theme-event rule forms, event history and notification inbox. Demonstrate false-to-true trigger, cooldown dedupe, resolved and `skipped_data_stale` states.

- [ ] **Step 3: Add notification semantics**

The inbox is the durable source. Desktop notification is shown as a delivery channel with permission allowed/denied states; denial never hides the inbox record.

- [ ] **Step 4: Commit**

```bash
git add outputs/merged-platform-product-prototype/scripts/pages/asset-observation.js outputs/merged-platform-product-prototype/scripts/pages/watchlists.js outputs/merged-platform-product-prototype/styles/pages.css
git commit -m "feat: prototype asset observation and alerts"
```

## Task 7: Implement Research Library and Capability Center

**Files:**

- Create: `outputs/merged-platform-product-prototype/scripts/pages/research-library.js`
- Create: `outputs/merged-platform-product-prototype/scripts/pages/capability-center.js`
- Modify: `outputs/merged-platform-product-prototype/styles/pages.css`

- [ ] **Step 1: Build Research Library**

Provide Project, Evidence, Claim, Artifact and Research Note views. Notes show version history and source/run links. The page clearly states that Notes are research content and never modify fact tables.

- [ ] **Step 2: Build Capability Center**

Provide Runtime Providers, declarative Skills, Agent Teams, MCP authorization and Agent Schedules. Permission summaries show allowed internal tools, registered MCP ids, attachment types and controlled web domains. No code editor, Shell toggle, arbitrary filesystem path or arbitrary URL input is present.

- [ ] **Step 3: Register all eight pages and run tests**

```js
const routes = [
  '/market-home', '/themes', '/assets/:assetId', '/fingpt',
  '/claw', '/watchlists', '/research-library', '/capabilities',
];
assert.deepEqual(registeredRoutes.sort(), routes.sort());
```

Run:

```bash
node --test tests/javascript/merged_platform_product_prototype.test.mjs
```

Expected: all required files, routes, states and tracking links PASS.

- [ ] **Step 4: Commit**

```bash
git add outputs/merged-platform-product-prototype/scripts/pages/research-library.js outputs/merged-platform-product-prototype/scripts/pages/capability-center.js outputs/merged-platform-product-prototype/styles/pages.css tests/javascript/merged_platform_product_prototype.test.mjs
git commit -m "feat: prototype research and capability centers"
```

## Task 8: Implement the five clickable journeys

**Files:**

- Create: `outputs/merged-platform-product-prototype/scripts/journeys.js`
- Modify: `outputs/merged-platform-product-prototype/scripts/router.js`
- Modify: `outputs/merged-platform-product-prototype/scripts/store.js`
- Modify: `outputs/merged-platform-product-prototype/styles/components.css`

- [ ] **Step 1: Define journey steps as data**

```js
const journeys = {
  J01: ['/market-home', '/themes?pack=gold', '/assets/AU-DEMO', '/fingpt', '/research-library'],
  J02: ['/market-home?focus=events', '/assets/AU-DEMO?tab=events', '/fingpt', '/research-library?tab=claims'],
  J03: ['/assets/AU-DEMO', '/watchlists?action=add', '/watchlists?action=create-rule', '/watchlists?tab=inbox'],
  J04: ['/claw?action=new', '/claw?view=run', '/claw?view=blackboard', '/research-library?tab=artifacts'],
  J05: ['/capabilities?tab=schedules', '/claw?state=blocked_runtime', '/capabilities?tab=runtimes', '/claw?state=running'],
};
```

`AU-DEMO` is an explicit demo identity, never presented as a real tradable code.

- [ ] **Step 2: Implement journey navigation**

Provide Previous, Next, Exit and current step labels. A journey action updates only prototype state and URL hash. Never use `scrollIntoView`; use `window.scrollTo({ top: 0 })` after route changes.

- [ ] **Step 3: Add assertions**

Every journey starts and finishes on the declared route, every route exists, and J05 includes `blocked_runtime` followed by recovery.

- [ ] **Step 4: Commit**

```bash
git add outputs/merged-platform-product-prototype/scripts/journeys.js outputs/merged-platform-product-prototype/scripts/router.js outputs/merged-platform-product-prototype/scripts/store.js outputs/merged-platform-product-prototype/styles/components.css tests/javascript/merged_platform_product_prototype.test.mjs
git commit -m "feat: add prototype research journeys"
```

## Task 9: Add browser acceptance for routes, states, and viewports

**Files:**

- Create: `tests/e2e/merged_platform_product_prototype_playwright_core.js`

- [ ] **Step 1: Write the browser harness**

Follow the existing `tests/e2e/asset_search_playwright_core.js` resolution strategy. Start a Node static server for the output directory, resolve locally installed Chrome, fail on page errors or console errors, and capture screenshots under `output/playwright/merged-platform-product-prototype/`. Emit route, viewport, journey, console and exception results as newline-delimited JSON to stdout; the command wrapper tees that stream to `logs/merged-platform-product-prototype-e2e.log`. Always close the browser and server in `finally` blocks.

The core assertions are:

```js
for (const route of requiredRoutes) {
  await page.goto(`${baseUrl}/#${route}`);
  await page.locator(`[data-page-route="${route.split('?')[0]}"]`).waitFor();
}

for (const viewport of [
  { width: 1600, height: 1000, name: 'wide' },
  { width: 1180, height: 820, name: 'compact' },
  { width: 820, height: 1180, name: 'tablet' },
  { width: 390, height: 844, name: 'mobile' },
]) {
  await page.setViewportSize(viewport);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
}
```

Also run J01–J05, switch all demo states, verify keyboard focus, and assert that a `stale` Alert never produces a triggered notification state.

- [ ] **Step 2: Run deterministic and browser checks**

```bash
node --test tests/javascript/merged_platform_product_prototype.test.mjs
mkdir -p logs
node tests/e2e/merged_platform_product_prototype_playwright_core.js 2>&1 | tee logs/merged-platform-product-prototype-e2e.log
```

Expected: all routes and journeys PASS, no uncaught errors, no horizontal overflow at four viewports, screenshots written. If `playwright-core` or Chrome is unavailable, report the check as skipped; do not claim browser acceptance.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/merged_platform_product_prototype_playwright_core.js output/playwright/merged-platform-product-prototype
git commit -m "test: verify merged platform prototype"
```

## Task 10: Publish the prototype map and final handoff

**Files:**

- Create: `docs/architecture/merged-platform/product/brand-spec.md`
- Create: `docs/architecture/merged-platform/product/prototype-map.md`
- Modify: `docs/architecture/merged-platform/README.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `outputs/merged-platform-product-prototype/index.html`

- [ ] **Step 1: Write the traceability map**

For every page list route, capability ids, API ids, demo states and journey ids. Link API ids to `../merged-platform-blueprint/api-atlas.html#<id>` and architecture diagrams to `../merged-platform-blueprint/diagrams/<stem>.html`.

- [ ] **Step 2: Run the lightweight design self-check**

Check the declared Design Read, real Logo, asset paths, responsive rules, focus states, all colors from Token files, no `scrollIntoView`, no unlabeled fabricated data, no decorative dashboard charts, and no unrelated page additions.

- [ ] **Step 3: Run final commands**

```bash
node --test tests/javascript/merged_platform_product_prototype.test.mjs
mkdir -p logs
node tests/e2e/merged_platform_product_prototype_playwright_core.js 2>&1 | tee logs/merged-platform-product-prototype-e2e.log
rg -n "TODO|TBD|FIXME|待定" outputs/merged-platform-product-prototype docs/architecture/merged-platform/product
git diff --check
```

Expected: deterministic tests PASS; browser result recorded truthfully; `rg` has no output; diff check passes.

- [ ] **Step 4: Commit**

```bash
git add outputs/merged-platform-product-prototype docs/architecture/merged-platform/product docs/architecture/merged-platform/README.md docs/FILE_GUIDE.md docs/CHANGELOG.md tests/javascript/merged_platform_product_prototype.test.mjs tests/e2e/merged_platform_product_prototype_playwright_core.js
git commit -m "feat: publish merged platform product prototype"
```

## Delivery boundary

This plan produces a visual implementation blueprint, not the production Web application. Production integration into `app/web`, API wiring, Tauri packaging and native Windows validation require their own implementation plan after the prototype and architecture Catalog are accepted.
