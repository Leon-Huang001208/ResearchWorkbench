# Desktop Cross-Platform CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically build and validate AlphaFoundry desktop artifacts on native macOS Apple Silicon and Windows x64 runners before release, then release both target artifacts under one tag.

**Architecture:** A pull-request/push verification workflow performs native sidecar and Tauri bundle builds without publishing. The existing release workflow uses the identical two-target matrix to create draft-release artifacts. Static regression tests guard the workflow contract: target OS runners, target-specific sidecar names, build sequence, and artifact retention.

**Tech Stack:** GitHub Actions, Python 3.11, PyInstaller, Node 20/npm, Rust/Tauri 2, pytest.

---

### Task 1: Lock the cross-platform workflow contract with failing tests

**Files:**
- Modify: `tests/unit/test_desktop_shell_scaffold.py`
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [ ] **Step 1: Add workflow locations and failing regression tests**

  Add the validation workflow path beside `DESKTOP_RELEASE_WORKFLOW`:

  ```python
  DESKTOP_VERIFY_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-verify.yml"
  ```

  Replace the current macOS-only release assertion with a two-target assertion and add this validation assertion:

  ```python
  def test_desktop_verify_workflow_builds_native_macos_and_windows_artifacts():
      source = DESKTOP_VERIFY_WORKFLOW.read_text(encoding="utf-8")

      assert "macos-14" in source
      assert "windows-2022" in source
      assert "aarch64-apple-darwin" in source
      assert "x86_64-pc-windows-msvc" in source
      assert "python scripts/desktop/build_sidecar.py" in source
      assert "python scripts/desktop/prepare_tauri_sidecar.py" in source
      assert "npm run desktop:build" in source
      assert "actions/upload-artifact@v4" in source


  def test_desktop_release_workflow_builds_macos_and_windows_draft_release():
      source = DESKTOP_RELEASE_WORKFLOW.read_text(encoding="utf-8")

      assert "macos-14" in source
      assert "windows-2022" in source
      assert "aarch64-apple-darwin" in source
      assert "x86_64-pc-windows-msvc" in source
      assert "python scripts/desktop/build_sidecar.py" in source
      assert "python scripts/desktop/prepare_tauri_sidecar.py" in source
      assert "tauri-apps/tauri-action@v0" in source
      assert "releaseDraft: true" in source
  ```

- [ ] **Step 2: Run the new assertions and verify they fail for the intended reason**

  Run:

  ```bash
  python -m pytest tests/unit/test_desktop_shell_scaffold.py \
    -k 'desktop_verify_workflow or desktop_release_workflow_builds_macos_and_windows' -q
  ```

  Expected: FAIL because `.github/workflows/desktop-verify.yml` does not exist and the current release workflow does not contain the Windows x64 matrix entry.

- [ ] **Step 3: Do not change implementation files in this task**

  Keep the red test in place. The workflow files are introduced only in Tasks 2 and 3.

### Task 2: Add native macOS/Windows desktop verification workflow

**Files:**
- Create: `.github/workflows/desktop-verify.yml`
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [ ] **Step 1: Create a path-filtered, manually runnable workflow**

  Add the following trigger and matrix shape:

  ```yaml
  name: Desktop Verify

  on:
    workflow_dispatch:
    pull_request:
      paths:
        - "src-tauri/**"
        - "desktop/**"
        - "scripts/desktop/**"
        - "core/settings/**"
        - "package.json"
        - "package-lock.json"
        - "pyproject.toml"
        - ".github/workflows/desktop-verify.yml"
        - ".github/workflows/desktop-release.yml"
    push:
      branches: [main]
      paths:
        - "src-tauri/**"
        - "desktop/**"
        - "scripts/desktop/**"
        - "core/settings/**"
        - "package.json"
        - "package-lock.json"
        - "pyproject.toml"
        - ".github/workflows/desktop-verify.yml"
        - ".github/workflows/desktop-release.yml"

  jobs:
    verify:
      name: ${{ matrix.label }}
      runs-on: ${{ matrix.os }}
      strategy:
        fail-fast: false
        matrix:
          include:
            - label: macOS Apple Silicon
              id: macos-arm
              os: macos-14
              triple: aarch64-apple-darwin
            - label: Windows x64
              id: windows-x64
              os: windows-2022
              triple: x86_64-pc-windows-msvc
  ```

- [ ] **Step 2: Install and cache all build inputs per native runner**

  In the `verify` job, use `actions/checkout@v4`, `actions/setup-node@v4` with Node 20 and npm cache, `actions/setup-python@v5` with Python 3.11, and `dtolnay/rust-toolchain@stable`. Install frontend dependencies with:

  ```yaml
  - name: Install Node dependencies
    run: npm ci
  ```

  Use runner-specific Python dependency steps so Windows is PowerShell-native:

  ```yaml
  - name: Install Python dependencies (macOS)
    if: runner.os == 'macOS'
    shell: bash
    run: |
      set -euo pipefail
      python -m pip install --upgrade pip
      python -m pip install -e . pyinstaller

  - name: Install Python dependencies (Windows)
    if: runner.os == 'Windows'
    shell: pwsh
    run: |
      $ErrorActionPreference = 'Stop'
      python -m pip install --upgrade pip
      python -m pip install -e . pyinstaller
  ```

- [ ] **Step 3: Run focused tests, build the target-native sidecar, and assert its name**

  Add these steps after dependency installation:

  ```yaml
  - name: Run desktop scaffold tests
    run: python -m pytest tests/unit/test_desktop_shell_scaffold.py -q

  - name: Build backend sidecar
    run: python scripts/desktop/build_sidecar.py

  - name: Verify generated sidecar
    shell: bash
    run: |
      set -euo pipefail
      suffix=""
      if [[ "${{ runner.os }}" == "Windows" ]]; then suffix=".exe"; fi
      test -f "build/desktop-sidecar/dist/alphafoundry-backend-${{ matrix.triple }}${suffix}"

  - name: Copy backend sidecar into Tauri
    run: python scripts/desktop/prepare_tauri_sidecar.py

  - name: Build Tauri bundle
    run: npm run desktop:build
  ```

  If the Windows Bash availability becomes a CI concern, replace only the `Verify generated sidecar` step with two conditional `bash`/`pwsh` variants; do not change the generated filename contract.

- [ ] **Step 4: Upload the native bundle for installation testing**

  Add a non-publishing artifact step:

  ```yaml
  - name: Upload desktop bundle
    if: always()
    uses: actions/upload-artifact@v4
    with:
      name: alphafoundry-desktop-${{ matrix.id }}
      path: src-tauri/target/release/bundle/**
      if-no-files-found: warn
      retention-days: 14
  ```

- [ ] **Step 5: Run the validation-workflow assertion and verify it passes**

  Run:

  ```bash
  python -m pytest tests/unit/test_desktop_shell_scaffold.py \
    -k desktop_verify_workflow_builds_native_macos_and_windows_artifacts -q
  ```

  Expected: PASS; the test now sees the two-target verification workflow. The release-workflow assertion remains red until Task 3.

### Task 3: Extend the release workflow to native macOS ARM and Windows x64 builds

**Files:**
- Modify: `.github/workflows/desktop-release.yml`
- Test: `tests/unit/test_desktop_shell_scaffold.py`

- [ ] **Step 1: Replace the release matrix with explicit supported targets**

  Replace the existing single macOS entry with:

  ```yaml
  matrix:
    include:
      - label: macOS Apple Silicon
        id: macos-arm
        os: macos-14
        triple: aarch64-apple-darwin
      - label: Windows x64
        id: windows-x64
        os: windows-2022
        triple: x86_64-pc-windows-msvc
  ```

  Retain `fail-fast: false`, release metadata resolution, draft prerelease settings, optional updater setup, and `tauri-apps/tauri-action@v0` release upload.

- [ ] **Step 2: Make shell-specific setup safe on both operating systems**

  Remove Linux-only disk/dependency steps. Split Rust fetch, Python dependency installation, and `TAURI_BUILD_ARGS` writes into macOS Bash and Windows PowerShell variants. The Windows updater-config equivalent must write the environment variable with:

  ```powershell
  "TAURI_BUILD_ARGS=--config src-tauri/tauri.release.conf.json" |
    Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
  ```

  The no-public-key branch must instead write `TAURI_BUILD_ARGS=` using the same PowerShell form. Keep the existing Bash behavior for macOS.

- [ ] **Step 3: Check that the matrix target matches the sidecar filename before publishing**

  After `python scripts/desktop/build_sidecar.py`, add platform-specific checks:

  ```yaml
  - name: Verify generated sidecar (macOS)
    if: runner.os == 'macOS'
    shell: bash
    run: test -f build/desktop-sidecar/dist/alphafoundry-backend-${{ matrix.triple }}

  - name: Verify generated sidecar (Windows)
    if: runner.os == 'Windows'
    shell: pwsh
    run: |
      $ErrorActionPreference = 'Stop'
      $path = "build/desktop-sidecar/dist/alphafoundry-backend-${{ matrix.triple }}.exe"
      if (-not (Test-Path $path)) { throw "Missing generated sidecar: $path" }
  ```

  Keep `python scripts/desktop/prepare_tauri_sidecar.py` immediately after these checks.

- [ ] **Step 4: Run the focused tests and verify the contract is green**

  Run:

  ```bash
  python -m pytest tests/unit/test_desktop_shell_scaffold.py -q
  ```

  Expected: PASS; both verification and release workflows declare exactly the two supported native targets.

### Task 4: Synchronize operating documentation and run repository validation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/desktop_packaging.md`
- Modify: `docs/CHANGELOG.md`
- Create: `.ai/reports/test_report_desktop_cross_platform_ci.md`

- [ ] **Step 1: Update the documented support matrix and CI boundary**

  In `docs/desktop_packaging.md`, name `.github/workflows/desktop-verify.yml` as the PR/push native-build gate and `.github/workflows/desktop-release.yml` as the draft-release builder. State that CI verifies sidecar and Tauri packaging but cannot replace real-device installation testing or a `/health` test with valid user PostgreSQL configuration.

- [ ] **Step 2: Update the change log and agent rule if wording needs alignment**

  Add a `docs/CHANGELOG.md` entry that names the native macOS ARM and Windows x64 CI coverage. Ensure `AGENTS.md` points to the final workflow names and still requires a real Windows installation smoke test before release.

- [ ] **Step 3: Create the test report**

  Create `.ai/reports/test_report_desktop_cross_platform_ci.md` with this initial structure, then replace the local result lines with the exact observed command output in Step 4:

  ```markdown
  # Desktop Cross-Platform CI Test Report

  ## Scope
  - macOS Apple Silicon (`aarch64-apple-darwin`)
  - Windows x64 (`x86_64-pc-windows-msvc`)

  ## Local verification
  - Focused desktop workflow tests: pending local execution.
  - Documentation synchronization: pending local execution.

  ## Required remote verification
  - GitHub Actions `Desktop Verify`, macOS Apple Silicon: pending workflow run.
  - GitHub Actions `Desktop Verify`, Windows x64: pending workflow run.

  ## Manual release gate
  - Windows x64 installation smoke test: pending a release candidate artifact.
  - macOS Apple Silicon installation smoke test: pending a release candidate artifact.
  ```

- [ ] **Step 4: Run local checks**

  Run:

  ```bash
  python -m pytest tests/unit/test_desktop_shell_scaffold.py -q
  git diff --check
  python scripts/check_doc_sync.py
  ```

  Expected: all commands pass. Do not claim Windows runtime validation has passed until the GitHub Actions job and real Windows installation smoke test have recorded successful results.

- [ ] **Step 5: Commit the implementation as an isolated change**

  Stage only the files in Tasks 1–4; do not stage unrelated existing worktree changes. Commit with:

  ```bash
  git add .github/workflows/desktop-verify.yml .github/workflows/desktop-release.yml \
    tests/unit/test_desktop_shell_scaffold.py AGENTS.md \
    docs/desktop_packaging.md docs/CHANGELOG.md \
    .ai/reports/test_report_desktop_cross_platform_ci.md
  git commit -m "ci: verify native desktop builds on mac and windows"
  ```

## Plan Self-Review

- Spec coverage: Tasks 1–3 implement the two-target native verification/release matrix; Task 4 records the CI boundary and real-device gate.
- Placeholder scan: no implementation task uses unresolved behavior; only test-report result fields are intentionally populated from actual future runs.
- Type/interface consistency: both workflows use the same `matrix.triple` values consumed by the existing `target_triple()`/`sidecar_name()` contract.
