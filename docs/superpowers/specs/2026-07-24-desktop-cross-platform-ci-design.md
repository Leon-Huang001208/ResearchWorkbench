# Desktop Cross-Platform CI Design

**Date:** 2026-07-24

## Goal

Make desktop compatibility a repeatable delivery property: changes affecting the desktop shell are built and automatically verified on native macOS Apple Silicon and Windows x64 runners before release; release builds produce installable artifacts for both targets.

## Scope

Supported release targets in this phase are:

- macOS Apple Silicon (`aarch64-apple-darwin`)
- Windows x64 (`x86_64-pc-windows-msvc`)

The work covers Tauri, the Python/PyInstaller sidecar, desktop launch/configuration scripts, release packaging, and their CI validation. Intel Mac, Windows ARM64, Linux release support, automatic code-signing setup, and product-level PostgreSQL installation are explicitly out of scope.

## Design

### Native build matrix

Desktop packages must be assembled only on the target operating system. The shared Python source is packaged by PyInstaller into a target-specific sidecar, then copied to `src-tauri/binaries/` with the Tauri target-triple suffix already produced by `scripts/desktop/build_sidecar.py`.

```text
macOS Apple Silicon runner
  Python source -> research-workbench-backend-aarch64-apple-darwin -> macOS Tauri bundle

Windows x64 runner
  Python source -> research-workbench-backend-x86_64-pc-windows-msvc.exe -> Windows Tauri bundle
```

The two outputs are independent. A successful macOS build neither creates nor validates a Windows executable.

### Pull-request and branch validation

A new desktop verification workflow runs when a pull request or a push changes desktop-sensitive paths: `src-tauri/**`, `desktop/**`, `scripts/desktop/**`, desktop settings/path modules, package metadata, Python dependency metadata, or the workflow itself. It can also be started manually.

It uses a two-entry matrix (macOS Apple Silicon and Windows x64). Every matrix entry:

1. checks out the source and installs Node 20, Python 3.11, Rust, Node dependencies, project Python dependencies, and PyInstaller;
2. runs the focused desktop scaffold test suite before packaging;
3. builds the native sidecar and verifies the expected filename exists;
4. copies the sidecar into Tauri's external-binary location;
5. builds a native Tauri bundle without publishing it;
6. uploads the generated bundle as a short-lived CI artifact for manual installation testing.

The workflow must fail at the first missing dependency, incorrect target triple, sidecar-copy failure, or Tauri packaging failure. A runtime `/health` probe is not part of this CI stage because the packaged backend intentionally fails without a user-provided PostgreSQL + pgvector configuration; the existing Python unit tests remain the automated coverage for launcher health/startup behavior.

### Release workflow

The existing desktop release workflow becomes the same two-target native matrix. It retains its tag/manual triggers and draft prerelease behavior. It performs the same sidecar preparation, optional updater configuration, and Tauri bundle upload for each platform under one GitHub Release tag.

The workflow's Windows commands use PowerShell-compatible steps; macOS commands use Bash. It must not rely on a Windows shell being present on macOS or vice versa.

### Human release gate

CI proves that target-native bundles can be assembled. Before publishing a release, a tester installs the Windows artifact on a real Windows x64 machine and records the results for installation, uninstall/upgrade, main-window startup, sidecar launch, health endpoint after valid PostgreSQL configuration, per-user paths, logs, and configuration persistence. Features that depend on Windows Excel/Wind, permissions, auto-update, or signing also require explicit real-machine verification. macOS follows the corresponding real-device validation.

## Error Handling

Build scripts continue to fail with explicit errors when the current operating system/architecture is unsupported or the generated sidecar is absent. CI commands use strict error propagation so an unsuccessful build cannot publish a partial release. CI artifact upload runs even after a failed bundle build only when a diagnosable bundle directory exists; publishing is never attempted after a failed matrix entry.

## Verification

1. Extend `tests/unit/test_desktop_shell_scaffold.py` with static regression tests for the two-target validation and release matrices, target triples, Windows runner, and artifact upload behavior.
2. Run the new tests red before each workflow/script behavior change, then green after implementation.
3. Run the focused desktop tests on macOS locally.
4. Trigger the verification workflow and require a successful macOS Apple Silicon and Windows x64 run.
5. Before the first public release, install the generated Windows artifact on a real Windows x64 machine and capture the smoke-test outcome.

## Documentation

Update:

- `AGENTS.md` with the enforced desktop validation rule.
- `docs/desktop_packaging.md` with the workflow names, support matrix, CI boundary, and human release checklist.
- `docs/CHANGELOG.md` with the new cross-platform CI coverage.
- `docs/modules/scripts.md` if the build-script responsibility changes.

## Non-goals

- Rewriting the Python backend in Rust.
- Cross-compiling a Windows sidecar from macOS or a macOS sidecar from Windows.
- Claiming that a CI bundle replaces real Windows installation testing.
- Adding Intel Mac, Windows ARM64, Linux, database bundling, or code signing in this phase.
