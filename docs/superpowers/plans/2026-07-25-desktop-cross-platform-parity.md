# Desktop Cross-Platform Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one AlphaFoundry codebase as a validated macOS Apple Silicon and Windows x64 desktop app, with equivalent Excel/Wind and Office workflows.

**Architecture:** Keep Tauri and FastAPI/Python shared. Introduce a small `services/desktop_platform` boundary that owns every native Office, folder-opening and capability decision; shared Wind/Workbook logic calls that boundary instead of `xlwings`, `osascript` or COM directly. Build the Python sidecar natively on each target and gate every desktop change with macOS ARM and Windows x64 CI plus a real-device Office/Wind release checklist.

**Tech Stack:** Tauri 2, Rust, Node 20/npm, Python 3.11, FastAPI, PyInstaller, xlwings, Windows COM, Apple Events, GitHub Actions, pytest.

---

## Scope and file map

This plan intentionally orders the work into dependent milestones. Do not start a later milestone until its preceding focused tests pass.

| Milestone | Files | Responsibility |
| --- | --- | --- |
| Native build gate | `package.json`, `package-lock.json`, `.github/workflows/desktop-verify.yml`, `.github/workflows/desktop-release.yml`, `tests/unit/test_desktop_shell_scaffold.py` | Reproducible two-target build and bundle validation. |
| Platform contract | `services/desktop_platform/*`, `app/api/routes/desktop_capabilities.py`, `app/api/main.py` | One API for native capability state and operations. |
| Wind parity | `data_layer/adapters/wind/client.py`, `services/wind_realtime_workbook.py`, `services/wind_workbook_manager.py` | Shared workbook logic; platform-specific Excel/Wind control. |
| Office parity | `app/api/routes/report_projects.py`, platform services | Windows Word PDF preview and safe file/folder reveal without macOS branches in routes. |
| Packaging and release | `pyproject.toml`, `scripts/desktop/build_sidecar.py`, docs, workflow tests, reports | Native dependencies, sidecar collection, signed-release and real-device gates. |

Existing in-progress cross-platform configuration changes are user-owned. Before each task, inspect `git status --short`; stage only the files named in that task. The pre-existing branch `codex/desktop-cross-platform-ci` may be used as a reference for its Node manifest and verification workflow, but do not blindly merge it over newer local changes.

### Task 1: Make macOS ARM and Windows x64 native builds a required CI contract

**Files:**
- Create: `package.json`
- Create: `package-lock.json`
- Create: `.github/workflows/desktop-verify.yml`
- Modify: `.github/workflows/desktop-release.yml`
- Modify: `tests/unit/test_desktop_shell_scaffold.py`
- Modify: `docs/desktop_packaging.md`
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [ ] **Step 1: Write the static workflow contract tests before changing workflow files.**

  Add the verify-workflow constant beside `DESKTOP_RELEASE_WORKFLOW`, then test the exact supported targets rather than a generic OS substring:

  ```python
  DESKTOP_VERIFY_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-verify.yml"

  def test_desktop_verify_workflow_builds_native_macos_and_windows():
      source = DESKTOP_VERIFY_WORKFLOW.read_text(encoding="utf-8")
      assert "macos-14" in source
      assert "windows-2022" in source
      assert "aarch64-apple-darwin" in source
      assert "x86_64-pc-windows-msvc" in source
      assert "python scripts/desktop/build_sidecar.py" in source
      assert "python scripts/desktop/prepare_tauri_sidecar.py" in source
      assert "npm run desktop:build" in source
      assert "actions/upload-artifact@v4" in source
  ```

  Replace the current assertion that Windows must be absent from the release workflow with an assertion that both supported target triples are present.

- [ ] **Step 2: Run the focused test and confirm the red state is caused by missing Windows verification.**

  Run:

  ```bash
  python -m pytest tests/unit/test_desktop_shell_scaffold.py \
    -k 'desktop_verify_workflow or desktop_release_workflow_builds_macos_and_windows' -q
  ```

  Expected: failure because `desktop-verify.yml` is absent and the release matrix has no Windows x64 entry.

- [ ] **Step 3: Add the root Node manifest and generate its lock file.**

  Create `package.json` with only the Tauri commands required by this repository:

  ```json
  {
    "name": "alphafoundry-desktop",
    "version": "0.1.0",
    "private": true,
    "type": "module",
    "scripts": {
      "tauri": "tauri",
      "desktop:dev": "tauri dev",
      "desktop:build": "tauri build",
      "desktop:build:debug": "tauri build --debug --bundles app",
      "desktop:sidecar": "python scripts/desktop/build_sidecar.py",
      "desktop:prepare-sidecar": "python scripts/desktop/prepare_tauri_sidecar.py"
    },
    "devDependencies": { "@tauri-apps/cli": "2.8.4" }
  }
  ```

  Run `npm install --package-lock-only` once, review the generated lock file, and commit both files together. Do not use an unpinned global Tauri CLI.

- [ ] **Step 4: Add the non-publishing native verification workflow.**

  Create `.github/workflows/desktop-verify.yml` with PR/push path filters covering `src-tauri/**`, `desktop/**`, `scripts/desktop/**`, `core/settings/**`, `services/desktop_platform/**`, `services/wind_*`, `pyproject.toml`, both Node manifests, and both desktop workflows. Its matrix must be exactly:

  ```yaml
  strategy:
    fail-fast: false
    matrix:
      include:
        - label: macOS Apple Silicon
          os: macos-14
          triple: aarch64-apple-darwin
        - label: Windows x64
          os: windows-2022
          triple: x86_64-pc-windows-msvc
  ```

  Each matrix job must run `actions/checkout@v4`, Node 20 with npm cache, Python 3.11, stable Rust, `npm ci`, `python -m pip install -e . pyinstaller`, focused desktop tests, `python scripts/desktop/build_sidecar.py`, target-specific sidecar existence checks, `python scripts/desktop/prepare_tauri_sidecar.py`, `npm run desktop:build`, and `actions/upload-artifact@v4` for `src-tauri/target/release/bundle/**`. Task 3 upgrades the Python command to install the new `desktop` extra after it exists.

  Use `bash` only on macOS and `pwsh` only on Windows. The Windows sidecar check is:

  ```powershell
  $ErrorActionPreference = 'Stop'
  $sidecar = "build/desktop-sidecar/dist/alphafoundry-backend-${{ matrix.triple }}.exe"
  if (-not (Test-Path -LiteralPath $sidecar -PathType Leaf)) {
    throw "Expected sidecar was not produced: $sidecar"
  }
  ```

- [ ] **Step 5: Update the release workflow to use the same explicit matrix.**

  Replace its current macOS-only entry with the Step 4 targets. Split release metadata, Rust fetch, Python dependency installation, updater-config environment writes and sidecar checks into macOS Bash and Windows PowerShell steps. For the Windows updater-config step, append this exact value to `$env:GITHUB_ENV`:

  ```powershell
  "TAURI_BUILD_ARGS=--config src-tauri/tauri.release.conf.json" |
    Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
  ```

  Keep `tauri-apps/tauri-action@v0`, draft prerelease behavior and target-native sidecar preparation. Remove Linux-only package and disk-cleanup steps because Linux is not a supported target.

- [ ] **Step 6: Run the local contract tests and document the boundary.**

  Run:

  ```bash
  python -m pytest tests/unit/test_desktop_shell_scaffold.py -q
  git diff --check
  ```

  Expected: all pass. Update `docs/desktop_packaging.md` to name `desktop-verify.yml` as the required native PR/push gate and state that build CI does not validate a licensed Office/Wind environment.

- [ ] **Step 7: Commit the isolated native CI foundation.**

  ```bash
  git add package.json package-lock.json .github/workflows/desktop-verify.yml \
    .github/workflows/desktop-release.yml tests/unit/test_desktop_shell_scaffold.py \
    docs/desktop_packaging.md
  git commit -m "ci: verify native desktop builds on mac and windows"
  ```

### Task 2: Define one tested platform capability and Office automation boundary

**Files:**
- Create: `services/desktop_platform/__init__.py`
- Create: `services/desktop_platform/models.py`
- Create: `services/desktop_platform/office.py`
- Create: `services/desktop_platform/factory.py`
- Create: `services/desktop_platform/macos_office.py`
- Create: `services/desktop_platform/windows_office.py`
- Create: `app/api/routes/desktop_capabilities.py`
- Modify: `app/api/main.py`
- Create: `tests/unit/services/desktop_platform/test_factory.py`
- Create: `tests/unit/services/desktop_platform/test_office.py`
- Create: `tests/unit/app/api/test_desktop_capabilities.py`

- [ ] **Step 1: Write contract tests using fake platform probes, not a real Office installation.**

  Add a factory test covering both supported systems and an unsupported system:

  ```python
  def test_factory_returns_windows_office_for_windows(monkeypatch):
      from services.desktop_platform.factory import create_office_automation
      monkeypatch.setattr("services.desktop_platform.factory.platform.system", lambda: "Windows")
      assert create_office_automation().__class__.__name__ == "WindowsOfficeAutomation"

  def test_factory_returns_unsupported_office_for_unknown_system(monkeypatch):
      from services.desktop_platform.factory import create_office_automation
      monkeypatch.setattr("services.desktop_platform.factory.platform.system", lambda: "Linux")
      capabilities = create_office_automation().capabilities()
      assert capabilities.excel.code == "platform_unsupported"
  ```

  Add API coverage asserting the local desktop endpoint returns a JSON object with `platform`, `excel`, `wind`, `word_preview`, and `folder_reveal`, but never emits environment secrets.

- [ ] **Step 2: Run the new tests and confirm imports fail before implementation.**

  ```bash
  python -m pytest tests/unit/services/desktop_platform tests/unit/app/api/test_desktop_capabilities.py -q
  ```

  Expected: collection failure because `services.desktop_platform` does not exist.

- [ ] **Step 3: Implement stable data models and the protocol.**

  In `models.py`, define immutable status objects with stable machine codes and Chinese messages:

  ```python
  @dataclass(frozen=True)
  class CapabilityStatus:
      code: str
      available: bool
      message: str
      remediation: str = ""

  @dataclass(frozen=True)
  class DesktopCapabilities:
      platform: str
      excel: CapabilityStatus
      wind: CapabilityStatus
      word_preview: CapabilityStatus
      folder_reveal: CapabilityStatus
  ```

  In `office.py`, define a `Protocol` with `capabilities()`, `open_workbook(path, *, read_only)`, `hide_application(app)`, `export_docx_to_pdf(source, destination)`, and `reveal_path(path)`. Define `OfficeAutomationError(code, message)` and `UnsupportedOfficeAutomation(system)` in the same file. Every method returns a typed result or raises the project-owned error; no raw COM or Apple Event exception may cross the interface.

- [ ] **Step 4: Implement the factory and platform adapters with lazy imports.**

  `factory.py` must contain the only system selection:

  ```python
  def create_office_automation() -> OfficeAutomation:
      system = platform.system()
      if system == "Darwin":
          return MacOSOfficeAutomation()
      if system == "Windows":
          return WindowsOfficeAutomation()
      return UnsupportedOfficeAutomation(system)
  ```

  The macOS adapter may use `osascript` only inside that file. The Windows adapter may import `xlwings`/COM only inside operation methods, convert missing modules to `office_not_installed`, and use `explorer /select,` only inside `reveal_path`. Both adapters must log the OS operation and target path without logging `.env` contents or credentials.

- [ ] **Step 5: Expose a local-only capability endpoint.**

  Add `GET /api/desktop/capabilities` in `desktop_capabilities.py`. Return `create_office_automation().capabilities()` and reuse the existing loopback request protection used by configuration routes. Include the router in `app/api/main.py`; its failure path logs the exception and returns a typed `platform_probe_failed` response rather than breaking application startup.

- [ ] **Step 6: Run the complete boundary test set and commit.**

  ```bash
  python -m pytest tests/unit/services/desktop_platform tests/unit/app/api/test_desktop_capabilities.py -q
  git add services/desktop_platform app/api/routes/desktop_capabilities.py app/api/main.py \
    tests/unit/services/desktop_platform tests/unit/app/api/test_desktop_capabilities.py
  git commit -m "feat: add desktop platform capability contract"
  ```

### Task 3: Make desktop dependencies and sidecar collection reproducible

**Files:**
- Modify: `pyproject.toml`
- Modify: `scripts/desktop/build_sidecar.py`
- Modify: `tests/unit/test_desktop_shell_scaffold.py`
- Create: `tests/unit/test_desktop_sidecar_dependencies.py`

- [ ] **Step 1: Obtain explicit approval before adding Python packages.**

  Stop and ask the user for approval to add `xlwings` as a declared desktop dependency and Windows-only `pywin32` support, explaining that they are needed for Excel/Wind COM automation and for PyInstaller to build a reproducible Windows sidecar. Do not run `pip install` until approval is received.

- [ ] **Step 2: Write metadata tests before modifying dependencies.**

  Parse `pyproject.toml` with `tomllib` and assert a `desktop` extra contains `xlwings`, while the Windows-only dependency uses a `sys_platform == 'win32'` marker. Assert `build_pyinstaller_args()` contains `--collect-submodules services.desktop_platform` and collects `xlwings` only when the desktop extra is installed.

- [ ] **Step 3: Add the approved dependency declarations and update the CI installation command.**

  Add a desktop optional dependency group in `pyproject.toml`:

  ```toml
  [project.optional-dependencies]
  desktop = [
    "xlwings>=0.36,<0.37",
    "pywin32>=312,<313; sys_platform == 'win32'",
  ]
  ```

  Use `python -m pip install -e '.[desktop]' pyinstaller` in both desktop workflows. Keep Office imports lazy so the web and non-Office tests remain importable without Excel.

- [ ] **Step 4: Include the new platform package in PyInstaller deliberately.**

  Add `services.desktop_platform` to `COLLECT_SUBMODULES`; add `xlwings` to `COLLECT_DATA` only after confirming the Windows sidecar executes its import in the native CI. Do not collect `pywin32` manually unless the PyInstaller native run reports it missing; then add the exact failed module as a hidden import and cover it with a test.

- [ ] **Step 5: Run metadata tests, build locally only for macOS, and commit.**

  ```bash
  python -m pytest tests/unit/test_desktop_sidecar_dependencies.py \
    tests/unit/test_desktop_shell_scaffold.py -q
  python scripts/desktop/build_sidecar.py
  git add pyproject.toml scripts/desktop/build_sidecar.py \
    tests/unit/test_desktop_sidecar_dependencies.py tests/unit/test_desktop_shell_scaffold.py
  git commit -m "build: package desktop office dependencies"
  ```

  Expected: the local command produces only the native macOS ARM sidecar. Windows correctness is asserted by the Windows runner; never claim it from a macOS build.

### Task 4: Move Wind workbook automation behind the platform interface

**Files:**
- Modify: `data_layer/adapters/wind/client.py`
- Modify: `data_layer/adapters/wind/wind_adapter.py`
- Modify: `services/wind_realtime_workbook.py`
- Modify: `services/wind_workbook_manager.py`
- Modify: `services/dashboard_service.py`
- Modify: `tests/unit/test_wind_adapter.py`
- Create: `tests/unit/test_wind_workbook_platform_contract.py`

- [ ] **Step 1: Add a fake OfficeAutomation contract test for workbook lifecycle.**

  Use a fake that records `open_workbook`, `hide_application`, `calculate`, and `save` calls. Verify `WindWorkbookManager.ensure_ready()` produces `ready` when the fake returns valid snapshot rows and returns `wind_login_required` when the heartbeat result is false. Verify `autostart_enabled()` no longer has a Darwin-only default:

  ```python
  def test_desktop_autostart_is_enabled_when_excel_and_wind_are_available(monkeypatch):
      manager = WindWorkbookManager(office=FakeOfficeAutomation(wind_available=True))
      monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP", "1")
      assert manager.autostart_enabled() is True
  ```

- [ ] **Step 2: Run the focused tests and confirm the constructor does not yet accept the adapter.**

  ```bash
  python -m pytest tests/unit/test_wind_workbook_platform_contract.py -q
  ```

  Expected: failure with `TypeError` for the unsupported `office` constructor argument.

- [ ] **Step 3: Inject OfficeAutomation into all workbook controllers.**

  Add an optional `office: OfficeAutomation | None = None` parameter to `WindExcelClient` and `WindWorkbookManager`; default it with `create_office_automation()`. Replace every direct `import xlwings`, `xw.App`, `app.api.Workbooks.Open`, `app.visible`, `book.save`, and macOS `osascript` branch in these files with protocol calls. Keep shared formula generation, polling, snapshot parsing and workbook health metrics in their existing modules.

  Preserve current public Wind APIs (`WindAdapter`, `WindExcelClient.execute`, `execute_batch`, `WindWorkbookManager.ensure_ready`) so the Wind routes, dashboard and existing callers do not change their request/response shape.

- [ ] **Step 4: Map native failures to stable status codes.**

  Add one translation table in `office.py` and require adapters to raise only these codes for expected conditions:

  ```python
  EXPECTED_OFFICE_CODES = {
      "office_not_installed", "office_busy", "office_permission_denied",
      "wind_addin_missing", "wind_login_required", "wind_formula_timeout",
      "operation_failed",
  }
  ```

  `WindExcelClient.is_available()` remains boolean for compatibility, while a new `status()` method returns the complete typed result. `WindWorkbookRuntimeStatus.status` must use the same codes, enabling the dashboard to display an actionable message without platform branching.

- [ ] **Step 5: Preserve dashboard fallback behavior through contract tests.**

  Update existing dashboard tests so only `wind_login_required`, `wind_addin_missing`, `office_not_installed`, timeouts and workbook-read failures trigger the established fallback/recovery path. A generic unexpected exception must be logged and reported as `operation_failed`, not treated as a successful fallback.

- [ ] **Step 6: Run focused Wind, dashboard and API tests; commit.**

  ```bash
  python -m pytest tests/unit/test_wind_adapter.py \
    tests/unit/test_wind_workbook_platform_contract.py \
    tests/unit/test_dashboard.py tests/unit/test_wind_api.py -q
  git add data_layer/adapters/wind services/wind_realtime_workbook.py \
    services/wind_workbook_manager.py services/dashboard_service.py \
    tests/unit/test_wind_adapter.py tests/unit/test_wind_workbook_platform_contract.py \
    tests/unit/test_dashboard.py
  git commit -m "feat: share Wind automation across desktop platforms"
  ```

### Task 5: Route Word previews and folder reveal through the same adapters

**Files:**
- Modify: `app/api/routes/report_projects.py`
- Modify: `services/desktop_platform/office.py`
- Modify: `services/desktop_platform/macos_office.py`
- Modify: `services/desktop_platform/windows_office.py`
- Create: `tests/unit/app/api/test_report_project_platform_operations.py`

- [ ] **Step 1: Write platform-independent route tests.**

  Inject a fake OfficeAutomation into the report-project route module. Verify a selected report invokes `reveal_path`, a folder invokes `reveal_path`, and a Word preview uses `export_docx_to_pdf`. Verify that `OfficeAutomationError("word_not_installed", ...)` yields a documented unavailable preview response rather than a 500.

- [ ] **Step 2: Run the route tests and verify they fail while helpers contain direct platform branches.**

  ```bash
  python -m pytest tests/unit/app/api/test_report_project_platform_operations.py -q
  ```

- [ ] **Step 3: Replace direct system calls in report routes.**

  Replace `_open_folder_command`, `_find_microsoft_word_app`, `_export_docx_pdf_with_microsoft_word`, and the macOS-only `sys.platform` handling with the factory-created office service. Preserve LibreOffice as the final portable fallback in the shared preview coordinator, but make Word the first choice on both supported desktop platforms.

  Windows Word export must use the adapter's COM implementation and close only documents it opened. It must write output to the existing preview cache path, set `DisplayAlerts` to suppress modal prompts, and translate COM timeout/busy errors to `office_busy` or `operation_failed`.

- [ ] **Step 4: Run all affected report tests and commit.**

  ```bash
  python -m pytest tests/unit/app/api/test_report_project_platform_operations.py \
    tests/unit/test_report_projects_api.py tests/unit/test_report_project_manager.py -q
  git add app/api/routes/report_projects.py services/desktop_platform \
    tests/unit/app/api/test_report_project_platform_operations.py
  git commit -m "feat: support native office operations on windows"
  ```

### Task 6: Verify packages, publish the operational contract, and complete real-device gates

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/desktop_packaging.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `.github/workflows/desktop-verify.yml`
- Create: `scripts/desktop/check_sidecar_health.py`
- Create: `.ai/reports/test_report_desktop_cross_platform_parity.md`
- Test: all focused tests from Tasks 1–5

- [ ] **Step 1: Add a support matrix and manual release checklist.**

  Update `docs/desktop_packaging.md` and `AGENTS.md` to name only these supported targets: macOS Apple Silicon and Windows x64. State that Windows support requires a native `windows-2022` CI success plus real Windows installation testing; do not state Linux or Intel Mac support.

  The Windows checklist must contain: install MSI, launch app, poll `/health` with valid PostgreSQL configuration, inspect `%LOCALAPPDATA%\\AlphaFoundry`, verify logs, install/open Office, verify Wind plugin login, refresh a formula, open a generated report folder, generate a Word preview, uninstall/reinstall, and perform an upgrade test.

- [ ] **Step 2: Add a sidecar health smoke test to the native CI workflow.**

  Update `desktop-verify.yml` after Task 3 so each runner starts an isolated pgvector PostgreSQL service, exports a temporary `DATABASE_URL`, starts the just-built sidecar on an unused loopback port, and polls `/health` before bundling. Use the same health helper script for macOS and Windows; create `scripts/desktop/check_sidecar_health.py` with CLI arguments `--executable`, `--port`, and `--timeout-seconds`. It must:

  ```python
  process = subprocess.Popen([str(executable), "--host", "127.0.0.1", "--port", str(port)], env=env)
  deadline = time.monotonic() + timeout_seconds
  while time.monotonic() < deadline:
      try:
          with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
              if response.status == 200:
                  return 0
      except OSError:
          time.sleep(1)
  raise SystemExit("desktop sidecar did not become healthy")
  ```

  In a `finally` block, terminate the child, wait ten seconds, then kill only that child if necessary; write stdout/stderr to `build/desktop-sidecar/health-smoke.log` for artifact upload. The workflow must fail if PostgreSQL, the sidecar, or `/health` fails. Do not substitute a `--help` check for this health test.

- [ ] **Step 3: Run local verification without overstating Windows coverage.**

  ```bash
  python -m pytest tests/unit/test_desktop_shell_scaffold.py \
    tests/unit/services/desktop_platform tests/unit/app/api/test_desktop_capabilities.py \
    tests/unit/test_wind_adapter.py tests/unit/test_wind_workbook_platform_contract.py \
    tests/unit/test_dashboard.py tests/unit/test_wind_api.py \
    tests/unit/app/api/test_report_project_platform_operations.py -q
  git diff --check
  python scripts/check_doc_sync.py
  ```

  Record exact command output in `.ai/reports/test_report_desktop_cross_platform_parity.md`. Mark Windows runtime and Wind tests as **pending** until a Windows native CI run and a real licensed Windows device have recorded results.

- [ ] **Step 4: Run and inspect the two native CI jobs.**

  Trigger `Desktop Verify` from GitHub Actions. Verify each job installed `.[desktop]`, produced its own target triple, built an installation bundle and uploaded an artifact. A macOS artifact never validates Windows behavior.

- [ ] **Step 5: Execute and record the real-device release gate.**

  Install the Windows x64 artifact on a Windows machine with PostgreSQL + pgvector, Microsoft Excel/Word and the licensed Wind plugin. Complete every Step 1 check, attach sanitized logs/screenshots to the report, and mark any unavailable prerequisite explicitly. Repeat the equivalent installation smoke on macOS Apple Silicon.

- [ ] **Step 6: Commit documentation and evidence separately from implementation.**

  ```bash
  git add AGENTS.md docs/desktop_packaging.md docs/CHANGELOG.md \
    .ai/reports/test_report_desktop_cross_platform_parity.md
  git commit -m "docs: document desktop platform parity verification"
  ```

## Plan self-review

- **Spec coverage:** Tasks 1 and 3 cover native sidecar/build reproducibility; Task 2 centralizes platform decisions and exposes capability state; Task 4 delivers cross-platform Excel/Wind behavior; Task 5 covers Word and folder operations; Task 6 supplies CI, signed-release and real-device validation gates.
- **Intentional dependency gate:** Task 3 requires explicit user approval before adding Python dependencies, satisfying the repository dependency rule.
- **Consistency:** `OfficeAutomation`, `CapabilityStatus`, `DesktopCapabilities`, and `OfficeAutomationError` are introduced in Task 2 before Wind and report routes use them. All downstream native failure handling uses the same stable codes.
- **Out-of-scope confirmation:** No task adds Intel Mac, Linux, Windows ARM, bundled PostgreSQL, bundled Office, or bundled Wind assets.
