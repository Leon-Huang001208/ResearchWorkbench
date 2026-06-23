# AlphaFoundry Desktop Visual System Design

Date: 2026-06-17
Updated: 2026-06-18

## Goal

Redesign the AlphaFoundry web workbench for the desktop shell so it feels like a native macOS professional application while preserving the density and speed expected from an institutional research terminal.

The approved baseline is:

- 50% Apple visual treatment.
- Source-list left navigation from the 70% Apple mockup.
- High-density central research workspace.
- Persistent right-side AI Inspector.

This design is for the Tauri desktop experience first. The existing FastAPI-served web workbench can be migrated gradually without changing backend APIs up front.

The current desktop baseline is local-first:

- The installed macOS app at `/Applications/AlphaFoundry.app` is the primary daily entry point.
- The app starts a local backend on `127.0.0.1:8765`.
- The backend reads the active project root from `~/Library/Application Support/AlphaFoundry/dev-project-root`.
- The active project root is `/Users/leon/Desktop/Projects/AlphaFoundry`.
- Normal frontend/backend/template iteration should take effect after quitting and reopening the desktop app.
- The browser remains a debugging fallback, not the default user experience.
- The active database is local PostgreSQL: `postgresql://leon@localhost:5432/alphafoundry`.
- Background workers continue to run locally for crawl scheduling and knowledge processing.

## Product Feel

AlphaFoundry should feel like a buy-side research operating system:

- Calm, professional, and operational.
- Dense enough for market monitoring and research throughput.
- Native enough to feel at home as a desktop app.
- Structured around evidence, assets, reports, and decisions.
- Local and self-contained enough to feel dependable on a personal research machine.

It should not feel like:

- A generic SaaS dashboard.
- A marketing website.
- A VS Code clone.
- A chatbot shell.
- A decorative fintech concept.

## Design Principle

Use macOS interaction structure, not consumer-app softness.

The desktop shell borrows from Apple where it improves long-running professional workflows:

- Window frame and toolbar hierarchy.
- Source-list navigation.
- Segmented controls for workspace modes.
- Inspector-style contextual side panel.
- Persisted workspace state.

The shell keeps AlphaFoundry's terminal DNA where research velocity matters:

- Compact tables.
- Monospace numeric data.
- Low visual noise.
- Dark graphite surface.
- Amber accent.
- Strong evidence and confidence displays.

The shell must also make the local runtime legible without making it noisy. The user should be able to tell whether the local backend, database, crawler scheduler, and knowledge worker are healthy from compact status affordances, but those affordances must not dominate the research workspace.

## Global Layout

The app uses a four-layer desktop frame:

1. Native-feeling title bar.
2. Source-list left sidebar.
3. Central workspace.
4. Right AI Inspector.

### Title Bar

The title bar should contain:

- macOS traffic-light window affordances.
- Center segmented control for top-level modes.
- Right-side command center entry.
- Compact local runtime status, when needed.

Recommended segmented modes:

- Market
- Research
- Reports
- Monitor

The command center is the primary global search affordance:

- Label: `⌘K 搜索实体、事件、信号`
- Scope: assets, entities, events, reports, templates, workflows.
- Behavior: opens an overlay command palette, not a normal page search box.

Local runtime status should use small indicators rather than banners:

- Backend: local service healthy or unavailable.
- Database: local PostgreSQL connected.
- Scheduler: crawl scheduler running.
- Worker: knowledge worker running.
- Last crawl: latest successful ingest time.

Only unhealthy states should expand into a visible warning.

### Source List

The left sidebar should be a source list, not a function menu.

Primary workspaces:

- `市场研究`
- `资产观察`
- `报告生产`
- `信号实验室`

Each workspace row includes:

- Rounded square icon swatch.
- Large workspace label.
- Right-aligned count.
- Full-row active highlight.

Counts must represent actionable workload, not total object count:

- `市场研究`: today's high-priority events or unresolved market items.
- `资产观察`: watched assets with new evidence or alerts.
- `报告生产`: reports needing generation, review, or export.
- `信号实验室`: experiments, backtests, or signals requiring attention.

Secondary source-list groups may appear below primary workspaces:

- Collections: watchlists, sectors, report projects.
- Data: Wind, crawler status, document sources.
- System: pipeline, memory, settings.

Secondary rows should be visually smaller than primary workspace rows.

### Central Workspace

The central workspace changes by selected source-list item. It should not try to show every module at once.

Standard structure:

- Header: selected workspace title, state chips, local actions.
- Summary strip: 3-4 key metrics.
- Primary body: table, feed, editor, chart, or task list.
- Supporting body: chart, evidence timeline, logs, or diagnostics.

Cards are allowed only for meaningful panels, not as decorative page sections.

### AI Inspector

The right panel is an inspector, not a chat interface.

Default sections:

- 主线判断
- 置信度
- 证据
- 相关资产
- 建议动作

The inspector changes with selection:

- Selecting an event shows event thesis, evidence, affected assets, and recommended follow-up.
- Selecting an asset shows factor view, recent events, risk notes, and report actions.
- Selecting a report shows generation status, missing placeholders, source evidence, and export actions.
- Selecting a signal shows feature inputs, scoring explanation, backtest status, and promotion controls.

The inspector should be collapsible, but it should be visible by default on desktop widths.

## Workspace Information Architecture

### 市场研究

Purpose: Real-time market intelligence and daily research triage.

Absorbs current features:

- Dashboard market overview.
- Live crawl monitor.
- Event signal feed.
- News and sector lists.
- Relevant portions of pipeline monitor.

Primary layout:

- Summary strip: rising concepts, falling concepts, new events, AI confidence.
- Event feed: source, event, strength, impact, timestamp.
- Trend panel: sector movement, capital flow, or selected asset chart.
- AI Inspector: main theme, evidence, related assets, suggested action.

Default density: Compact.

### 资产观察

Purpose: Follow assets, industries, and entities over time.

Absorbs current features:

- Asset analysis.
- K-line terminal.
- Capital flow.
- Industry chain graph.
- Asset agent committee.
- Watchlists and related entity search.

Primary layout:

- Left internal explorer: watchlists, sectors, entities.
- Center: selected asset overview, charts, event timeline.
- Right AI Inspector: thesis, risk, factor changes, related assets.
- Bottom: evidence timeline or recent source documents.

Default density: Default.

### 报告生产

Purpose: Generate, configure, review, and export research reports.

Absorbs current features:

- Template management.
- Weekly report generation center.
- Placeholder configuration.
- Report preview.
- Generation logs.

Primary layout:

- Source list secondary group: report projects.
- Center: selected project workspace.
- Tabs: `配置`, `生成`, `预览`, `日志`.
- Right AI Inspector: missing inputs, source evidence, generation risks, export readiness.

Default density: Default.

### 信号实验室

Purpose: Build, evaluate, promote, or reject signals.

Absorbs current features:

- Signal Lab.
- Signal management.
- Backtest outcomes.
- Review queue for signal decisions.
- Memory and learning entries related to signals.

Primary layout:

- Summary strip: active experiments, pending validations, promoted signals, recent failures.
- Main table: experiments or candidate signals.
- Diagnostics panel: backtest chart, feature importance, failure memory.
- AI Inspector: scoring explanation, evidence, promotion or rejection recommendation.

Default density: Compact.

## Visual Tokens

The desktop shell should refine the existing terminal tokens rather than replace them.

The product brand mark is now red and gold:

- App icon: rich A-share red rounded square.
- Mark: gold abstract `A` with an integrated upward trend arrow.
- Style: slightly dimensional macOS icon treatment with softened shadow.
- Exclusions: no K-line background, no chip traces, no circuit pattern, no decorative data grid.

The app icon is a brand asset, not a full UI palette. Red and gold may appear as brand moments, but the workbench should still use restrained graphite surfaces and semantic market colors.

Recommended base palette:

- Page: `#101116`
- Main workspace: `#0F1219`
- Sidebar: `#20232D`
- Panel: `#1A1F2B`
- Elevated panel: `#1D2330`
- Border: `rgba(255,255,255,0.10)`
- Soft border: `rgba(255,255,255,0.06)`
- Primary text: `#F5F5F7`
- Secondary text: `#A4ACB8`
- Muted text: `#7B8493`
- Accent: `#FF9F0A`

Status colors should follow China market convention:

- Up / positive price movement: red.
- Down / negative price movement: green.
- Neutral: muted blue-gray.
- Warning: amber.

Brand colors:

- Brand red: `#D71920`
- Deep brand red: `#8F0909`
- Brand gold: `#F5B544`
- Deep gold: `#B77714`

Brand colors are appropriate for:

- App icon.
- About/splash identity.
- Small brand mark in the sidebar or title bar.
- Selected workspace swatch only when it does not conflict with semantic status.

Brand colors are not appropriate for:

- Every panel background.
- General table rows.
- Non-positive semantic status.
- Decorative gradients or large hero-like areas.

Typography:

- UI: Inter or system `-apple-system`.
- Numeric data: `SF Mono`, JetBrains Mono, or equivalent monospace.
- Workspace labels in the source list should be larger and heavier than ordinary navigation labels.

Radii:

- Primary source-list rows: 15px.
- Panels: 8px.
- Buttons and segmented controls: 8px.
- Dense tables: 6px.

Motion:

- Fade and subtle hover brighten only.
- No bounce, parallax, floating cards, glossy gradients, or decorative blobs.

## Theme System

The desktop visual system should preserve the current product capability for light mode, dark mode, and accent color selection, but the new implementation must constrain those options through a single token model.

Theme controls:

- Appearance: `System`, `Light`, `Dark`.
- Accent color: `Amber`, `Blue`, `Green`, `Red`, `Purple`.
- Default: `System` appearance with `Amber` accent.

Theme choices should affect:

- App background surfaces.
- Panel and sidebar surfaces.
- Text contrast tokens.
- Accent tokens.
- Focus rings.
- Active source-list states.
- Primary buttons.
- Selected segmented-control state.
- Chart emphasis lines.

Theme choices must not affect:

- China market up/down color convention.
- Risk, warning, danger, and success semantics.
- Numeric typography.
- Workspace layout density.
- Source-list hierarchy.
- AI Inspector information architecture.

### Dark Appearance

Dark appearance remains the primary AlphaFoundry experience.

It should use the graphite terminal palette defined in Visual Tokens:

- Dark graphite page.
- Dark source-list sidebar.
- Dense panels.
- Amber accent by default.
- Muted grid and border lines.

Dark mode is best for:

- Market monitoring.
- Signal review.
- Backtests.
- Real-time event triage.

### Light Appearance

Light appearance should be a macOS professional light theme, not a generic white web dashboard.

Recommended light palette:

- Page: `#F5F6F8`
- Main workspace: `#FFFFFF`
- Sidebar: `#E9EDF3`
- Panel: `#FFFFFF`
- Elevated panel: `#F8FAFC`
- Border: `rgba(17,24,39,0.12)`
- Soft border: `rgba(17,24,39,0.07)`
- Primary text: `#111827`
- Secondary text: `#4B5563`
- Muted text: `#7B8493`

Light mode is best for:

- Report production.
- Template configuration.
- Long-form review.
- Export and preview workflows.

### Accent Color Presets

Accent presets should map only to emphasis and interaction tokens.

Recommended presets:

- Amber: `#FF9F0A`
- Blue: `#0A84FF`
- Green: `#30D158`
- Red: `#FF453A`
- Purple: `#BF5AF2`

Accent colors may be used for:

- Active source-list swatch.
- Active row highlight tint.
- Primary button background.
- Focus outline.
- Segmented-control selected state.
- Command center highlight.
- Non-semantic chart emphasis.

Accent colors must not be used to replace semantic status colors. A green accent does not make negative price movement use another color; a red accent does not change warning or danger semantics.

The default desktop identity may use the red/gold app mark while keeping Amber as the default interaction accent. This avoids turning the whole product into a one-note red theme while preserving the A-share identity at the application level.

### Persistence

Theme preferences should be persisted independently from workspace state:

- `appearance`
- `accentColor`
- `densityByWorkspace`
- `inspectorCollapsed`

If `appearance` is `System`, the app should follow the operating system color scheme and keep the selected accent color.

## Component Rules

### Source List Row

Primary row:

- Height: 48-52px.
- Icon swatch: 30px square, 9px radius.
- Label: 18-20px, semibold.
- Count: right-aligned, muted.
- Active state: amber swatch, warm graphite row highlight.

Secondary row:

- Height: 36-40px.
- Icon swatch: 16-18px.
- Label: 13-14px.
- Count: right-aligned.

### Tables And Feeds

Tables and feeds are core UI, not secondary styling details.

Rules:

- Row height: 30-34px in Compact, 34-38px in Default.
- Sticky headers where scrolling is possible.
- Right-align numeric columns.
- Use monospace for strength, price, percentage, time, and confidence values.
- Hover only brightens the row background.
- Selected row drives the AI Inspector.

### Summary Strip

Use 3-4 metrics per workspace.

Metric cards must show:

- Label.
- Value.
- Optional delta.
- Optional status color.

Avoid large stat cards that consume the first viewport.

### Buttons

Use buttons for commands only:

- Generate report.
- Promote signal.
- Export.
- Refresh.
- Open evidence.

Use segmented controls for modes, chips for filters, toggles for binary states, and menus for option sets.

### Empty And Loading States

Loading should use skeleton rows or panel placeholders where possible.

Empty states should stay operational:

- Good: `今日暂无高优先级事件。`
- Good: `当前报告缺少 2 个数据源。`
- Avoid: playful or marketing copy.

### Runtime Status

Runtime status is part of the desktop visual system because AlphaFoundry is now a local app with local services.

Required states:

- Backend service.
- Local database.
- Crawl scheduler worker.
- Knowledge worker.
- Last successful crawl or processing heartbeat.

Display rules:

- Healthy states should be compact and quiet.
- Warning states should show a short actionable label.
- Error states should link to diagnostics or logs.
- Do not show raw logs in the primary workspace unless the user opens diagnostics.
- Do not log or display full crawled article bodies in normal operational status.

Recommended healthy copy:

- `本地服务正常`
- `PostgreSQL 已连接`
- `爬取中`
- `知识处理正常`

Recommended warning copy:

- `本地服务未连接`
- `数据库不可用`
- `爬虫未运行`
- `知识处理暂停`

## Migration Strategy

The redesign can be implemented incrementally.

### Phase 0: Desktop Runtime Baseline

Status: completed for macOS local development.

- macOS Tauri shell exists and can be installed as `/Applications/AlphaFoundry.app`.
- The app uses the red/gold AlphaFoundry icon.
- The installed app starts the local backend from the active project root.
- The active project root is configured through `~/Library/Application Support/AlphaFoundry/dev-project-root`.
- The backend serves the existing workbench on `127.0.0.1:8765`.
- The backend connects to local PostgreSQL.
- `crawl_scheduler_worker` and `knowledge_worker` run locally under watchdog supervision.
- Knowledge worker logs no longer emit full document content in normal `Item processed` lines.

This phase is an operating baseline, not the final visual redesign. It lets daily iteration happen in the desktop app before the visual migration is complete.

### Phase 1: Shell And Navigation

- Replace the VS Code-style activity bar with the source-list sidebar.
- Add the desktop title bar treatment inside the Tauri-hosted app.
- Keep existing sections mounted but route them through the four workspaces.
- Add local state for selected workspace and source-list active row.
- Add compact runtime status indicators for backend, database, scheduler, and knowledge worker.

### Phase 2: Market Research Workspace

- Build `市场研究` as the first complete workspace.
- Move dashboard market overview and live feed into a single workbench layout.
- Add the persistent AI Inspector shell with static sections first, then wire data.
- Define counts for source-list rows from current API data.

### Phase 3: Report Production Workspace

- Reorganize template management and report generation into `报告生产`.
- Convert the current upload/edit/generate flow into workspace tabs.
- Move generation logs into the lower supporting panel.

### Phase 4: Asset And Signal Workspaces

- Move asset analysis into `资产观察`.
- Move signal lab, signals, outcomes, and review decisions into `信号实验室`.
- Add density preference per workspace.

### Phase 5: Polish And Persistence

- Persist selected workspace, density, inspector collapsed state, and recently opened entities.
- Add command center.
- Replace old theme variants with the unified appearance and accent token system.

## Implementation Constraints

- Preserve current API endpoints during the visual migration.
- Avoid introducing a large frontend framework migration until the layout model is proven.
- Keep changes scoped to static HTML/CSS/JS first if that is the fastest path.
- Do not remove legacy sections until each replacement workflow is verified.
- Do not use decorative gradients, oversized cards, or marketing-style hero layouts.
- Keep the local desktop development path working: project changes should apply after quitting and reopening the installed app.
- Do not require cloud services for the core local desktop workflow.
- Do not treat crawler logs as data storage or deduplication state.
- Do not print full crawled article bodies in normal logs or status panels.

## Success Criteria

The redesign is successful when:

- A user can understand the four primary workspaces in under 10 seconds.
- The first viewport immediately shows useful research state, not navigation noise.
- Market monitoring remains dense and scannable.
- Report and template work feels calmer and more native.
- AI output reads like an analyst inspector, not a chat sidebar.
- The desktop shell feels coherent with macOS without losing AlphaFoundry's institutional terminal identity.
- The user can work from `AlphaFoundry.app` without opening the browser.
- Local backend, local database, scheduler, and knowledge worker health are visible when needed.
- Normal project iteration takes effect after quitting and reopening the installed app.

## Open Decisions Resolved

- Use source-list workspaces instead of the current icon activity bar.
- Keep dark graphite as the primary theme while supporting Light, Dark, System, and controlled accent presets.
- Use `市场研究 / 资产观察 / 报告生产 / 信号实验室` as the first four primary workspaces.
- Treat source-list counts as actionable workload counts.
- Make the 50% Apple hybrid the design baseline.
- Use the red/gold A-share app icon as the brand mark.
- Treat the desktop app as local-first: local backend, local PostgreSQL, and local workers are the default development and daily-use model.
- Use the browser only as a debugging fallback for the desktop workflow.
