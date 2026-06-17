# Desktop Shell Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first AlphaFoundry desktop shell while keeping the existing FastAPI-served Web Workbench unchanged.

**Architecture:** Tauri owns the native window and bundled desktop assets. The existing Python/FastAPI application remains the backend and serves the current HTML/JS/CSS UI on `127.0.0.1:8765`; the desktop bootstrap page waits for `/health` and then navigates to the existing workbench. A Python launcher is the packaging boundary for a future sidecar binary.

**Tech Stack:** FastAPI, Python launcher, Tauri 2, Rust, static bootstrap HTML/CSS/JS, pytest wiring tests.

---

### Task 1: Desktop Backend Launcher

**Files:**
- Create: `scripts/desktop/backend_launcher.py`
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [x] **Step 1: Write a launcher that starts `app.api.main:app` on a desktop-specific port**

The launcher parses `--host`, `--port`, and `--log-dir`, creates the log directory, writes to `logs/desktop-backend.log`, and returns a non-zero exit code on startup errors.

- [x] **Step 2: Add tests for launcher defaults and log setup**

The tests import the launcher by path so `scripts/` does not need to become a Python package.

### Task 2: Tauri Shell Scaffold

**Files:**
- Create: `package.json`
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/capabilities/default.json`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/src/lib.rs`
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [x] **Step 1: Add root desktop scripts**

`npm run desktop:dev` runs Tauri against the local FastAPI dev URL. `npm run desktop:build` runs a production Tauri build once Rust, Node, and sidecar binaries are available.

- [x] **Step 2: Add a minimal Tauri 2 Rust application**

The app installs shell/log/dialog/process plugins, attempts to start an `alphafoundry-backend` sidecar in packaged builds, and logs a clear fallback message when the sidecar is not present during development.

- [x] **Step 3: Add Tauri config**

The config uses `desktop/dist` as the bundled frontend, points dev mode at `http://127.0.0.1:8765`, declares an external backend sidecar, and keeps CSP limited to the local backend.

### Task 3: Desktop Bootstrap UI

**Files:**
- Create: `desktop/dist/index.html`
- Create: `desktop/dist/bootstrap.js`
- Create: `desktop/dist/style.css`
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [x] **Step 1: Add a static loading page**

The page polls `http://127.0.0.1:8765/health`, shows retry state, and navigates to the existing FastAPI workbench once healthy.

### Task 4: Documentation

**Files:**
- Create: `docs/desktop_packaging.md`
- Modify: `docs/CHANGELOG.md`

- [x] **Step 1: Document the desktop architecture**

Explain what exists now, what still needs CI/signing/updater work, and how the cc-switch pattern maps to AlphaFoundry.

### Task 5: Verification

**Files:**
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [x] **Step 1: Run the focused pytest suite**

Run: `pytest tests/unit/test_desktop_shell_scaffold.py -q`

Expected: all desktop scaffold tests pass.
