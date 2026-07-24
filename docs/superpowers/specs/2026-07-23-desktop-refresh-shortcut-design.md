# Desktop Workbench Refresh Shortcut Design

**Date:** 2026-07-23

## Goal

Allow a developer using the AlphaFoundry desktop workbench to reload the currently displayed workbench page without exiting or restarting the Tauri desktop window.

## Scope

This change adds page-level refresh shortcuts to the existing Web Workbench JavaScript entry point:

- `F5` on every platform.
- `Cmd+R` on macOS.
- `Ctrl+R` on Windows and Linux.

It deliberately does not add a native Tauri menu item, a global operating-system shortcut, or frontend hot-module replacement.

## Design

### Event handling

`app/web/static/js/app.js` owns the workbench-wide `DOMContentLoaded` initialization and is the single place for the new document-level `keydown` listener.

The handler detects either:

```text
F5
(Ctrl or Cmd) + R
```

For an eligible event, it calls `preventDefault()` and then invokes `window.location.reload()`. The shortcut applies even when an editable input has focus, matching the expected browser refresh behavior.

All other key events are ignored so existing Escape, Enter, navigation, and modifier-plus-wheel feature handlers continue unchanged.

### Cache behavior

The workbench server already sends no-store headers for HTML, JavaScript, and CSS. A full page reload therefore requests the newest local static assets without restarting the Python sidecar.

The `app.js` query-string version in `app/web/templates/index.html` will be bumped alongside the source change so existing long-running desktop windows load the new shortcut handler after their next page refresh.

### Desktop runtime behavior

This is a renderer/WebView behavior, not a Tauri shell behavior. It works for both a browser-hosted workbench and the Tauri WebView. It does not restart Uvicorn, the Python sidecar, workers, or the Tauri window.

The existing development behavior remains separate: a Uvicorn `--reload` restart changes `/_version`, and the page's version polling performs a full reload automatically.

## Error Handling

`window.location.reload()` is a browser-provided navigation operation and needs no custom error recovery. The handler is intentionally synchronous and side-effect-free except for preventing the default shortcut action and starting the page navigation.

## Verification

1. Add a static regression test in `tests/unit/test_desktop_shell_scaffold.py` that asserts the workbench entry point handles `keydown`, `F5`, `Ctrl`/`Cmd` + `R`, prevents the default action, and reloads the page.
2. Update the existing app bundle cache-version assertion to match the bumped `app.js` URL.
3. Verify the UI with Playwright MCP by loading the workbench and triggering the shortcut behavior.
4. Run the repository's required formatting, linting, type-check, test, task, and documentation-sync gates.

## Documentation

Update:

- `docs/desktop_packaging.md` with the supported refresh shortcuts and the fact that they reload the workbench without restarting the desktop app or Python sidecar.
- `docs/modules/app_web.md` to document the workbench-wide refresh behavior.
- `docs/FILE_GUIDE.md` if its `app.js` description needs to mention its new workbench-level keyboard behavior.
- `docs/CHANGELOG.md` with the user-visible desktop refresh shortcut.

## Non-goals

- Native menu-based Reload command.
- Hot module replacement for JavaScript or CSS.
- Reloading changes to `src-tauri/**`, workers, or an already packaged application binary.
- Refreshing the app while the bootstrap page is still waiting for the backend.
