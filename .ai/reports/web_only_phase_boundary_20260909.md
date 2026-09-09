# Web-only phase boundary

Date: 2026-09-09

## Decision

Research Workbench product iteration is currently Web-only. Web pages, Research Web, general Web API/runtime code, shared Python/Node dependencies, and Web documentation are accepted with Web-focused tests and project constraints. They do not require sidecar, Tauri, installer, or native desktop CI.

Desktop packaging remains preserved. Its native macOS/Windows matrix and installation-level acceptance apply only when the user explicitly reopens desktop work or a task modifies desktop-owned paths such as `src-tauri/`, `desktop/`, `scripts/desktop/`, or `services/desktop_platform/`.

## CI routing

The Desktop Verify path filters now contain only desktop-owned code, desktop packaging documentation, and the desktop workflows themselves. Shared Web/backend/dependency paths were removed so a Web-only iteration cannot accidentally start the approximately 30-minute sidecar and Tauri matrix.

## Scope correction

The runtime-core reconciliation did not change `src-tauri/`, `desktop/`, `scripts/desktop/`, or `services/desktop_platform/`. Its completed native desktop run was additional evidence caused by the former broad path filters; it did not publish a desktop release.
