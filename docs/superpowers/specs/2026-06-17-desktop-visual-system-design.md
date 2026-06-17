# AlphaFoundry Desktop Visual System Design

Date: 2026-06-17

## Goal

Redesign the AlphaFoundry web workbench for the desktop shell so it feels like a native macOS professional application while preserving the density and speed expected from an institutional research terminal.

The approved baseline is:

- 50% Apple visual treatment.
- Source-list left navigation from the 70% Apple mockup.
- High-density central research workspace.
- Persistent right-side AI Inspector.

This design is for the Tauri desktop experience first. The existing FastAPI-served web workbench can be migrated gradually without changing backend APIs up front.

## Product Feel

AlphaFoundry should feel like a buy-side research operating system:

- Calm, professional, and operational.
- Dense enough for market monitoring and research throughput.
- Native enough to feel at home as a desktop app.
- Structured around evidence, assets, reports, and decisions.

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

Recommended segmented modes:

- Market
- Research
- Reports
- Monitor

The command center is the primary global search affordance:

- Label: `⌘K 搜索实体、事件、信号`
- Scope: assets, entities, events, reports, templates, workflows.
- Behavior: opens an overlay command palette, not a normal page search box.

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

## Migration Strategy

The redesign can be implemented incrementally.

### Phase 1: Shell And Navigation

- Replace the VS Code-style activity bar with the source-list sidebar.
- Add the desktop title bar treatment inside the Tauri-hosted app.
- Keep existing sections mounted but route them through the four workspaces.
- Add local state for selected workspace and source-list active row.

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
- Remove old theme variants that no longer match the desktop visual system.

## Implementation Constraints

- Preserve current API endpoints during the visual migration.
- Avoid introducing a large frontend framework migration until the layout model is proven.
- Keep changes scoped to static HTML/CSS/JS first if that is the fastest path.
- Do not remove legacy sections until each replacement workflow is verified.
- Do not use decorative gradients, oversized cards, or marketing-style hero layouts.

## Success Criteria

The redesign is successful when:

- A user can understand the four primary workspaces in under 10 seconds.
- The first viewport immediately shows useful research state, not navigation noise.
- Market monitoring remains dense and scannable.
- Report and template work feels calmer and more native.
- AI output reads like an analyst inspector, not a chat sidebar.
- The desktop shell feels coherent with macOS without losing AlphaFoundry's institutional terminal identity.

## Open Decisions Resolved

- Use source-list workspaces instead of the current icon activity bar.
- Keep dark graphite as the primary theme rather than making the 70% Apple option a light theme.
- Use `市场研究 / 资产观察 / 报告生产 / 信号实验室` as the first four primary workspaces.
- Treat source-list counts as actionable workload counts.
- Make the 50% Apple hybrid the design baseline.
