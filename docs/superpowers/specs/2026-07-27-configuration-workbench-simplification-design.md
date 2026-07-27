# Configuration Workbench Simplification Design

## Goal

Make the system-configuration landing page a quiet, task-oriented entry point: users should immediately see what still needs configuration and open the relevant setting without reading diagnostics or operating page-level controls.

## Decisions

- Remove the page-level **刷新状态** control. Configuration is loaded when the page opens, and saving or testing a section already updates the visible state.
- Remove the **显示配置** status filter. Six cards fit in the workbench and filtering obscures available configuration options.
- Retain completion status as one compact line above the cards: completed / total and a short progress bar. Do not show a separate connection-status control.
- Move the platform, paths, SDK checks, and capability diagnostics into a collapsed **运行环境** disclosure directly below the compact status line.
- Keep all configuration cards and their modal dialogs unchanged functionally. Cards show an icon, title, short state, and one action in a denser grid.

## Layout

1. Page title and one-sentence description.
2. Single compact progress row: `已完成 4 / 6` plus the existing progress indicator.
3. Collapsed `运行环境` disclosure. Expanding it reveals the existing safe environment paths and capability results.
4. Six configuration cards in a compact three-column grid, falling back to two and one columns on smaller screens.

## Behaviour and Accessibility

- The `details` / `summary` pattern provides a native keyboard-operable, screen-reader-readable running-environment disclosure.
- Environment content is rendered exactly as before; only its containing disclosure changes.
- Removing refresh and filtering also removes their event bindings and visibility mutation. Saving and connection testing still refresh their respective card state.
- Static frontend tests assert that the obsolete controls and handlers are absent, and that diagnostics live inside the running-environment disclosure.

## Non-goals

- No API, configuration model, data migration, or database behavior changes.
- No changes to the individual configuration forms or modal workflows in this iteration.
