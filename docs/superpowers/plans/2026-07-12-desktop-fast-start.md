# Desktop Fast Start Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent duplicate AlphaFoundry backend launches and bound desktop bootstrap waiting time.

**Architecture:** The Tauri shell owns single-instance enforcement and probes the existing backend before spawning a sidecar. The bootstrap page gives every health request an abort timeout so retries always advance.

**Tech Stack:** Rust, Tauri 2, browser JavaScript, pytest

---

### Task 1: Specify startup behavior

**Files:**
- Modify: `tests/unit/test_desktop_shell_scaffold.py`

- [ ] Add assertions for the single-instance plugin, backend health probe, and `AbortController` timeout.
- [ ] Run the focused tests and confirm they fail for the missing behavior.

### Task 2: Implement Tauri process coordination

**Files:**
- Modify: `src-tauri/Cargo.toml`
- Modify: `src-tauri/Cargo.lock`
- Modify: `src-tauri/src/lib.rs`

- [ ] Add the Tauri single-instance plugin.
- [ ] Implement a bounded HTTP health probe over localhost TCP.
- [ ] Reuse a healthy backend and spawn only when needed.
- [ ] Add Rust tests for healthy, unhealthy, and reachable local responses.

### Task 3: Bound bootstrap health requests

**Files:**
- Modify: `desktop/dist/bootstrap.js`

- [ ] Add `AbortController` timeout handling with timer cleanup.
- [ ] Keep the existing retry and user-visible failure behavior.

### Task 4: Verify

**Files:**
- Test: `tests/unit/test_desktop_shell_scaffold.py`
- Test: `src-tauri/src/lib.rs`

- [ ] Run focused pytest tests.
- [ ] Run `cargo fmt --check` and `cargo test`.
- [ ] Review the diff for unrelated changes.
