# AlphaFoundry Desktop Packaging

AlphaFoundry is moving toward a Tauri desktop shell while keeping the current FastAPI Web Workbench intact.

## Current Shape

- Existing UI remains served by `app.api.main:app`.
- Desktop development uses the ESM `scripts/desktop/run_backend.js` bridge, which resolves its own directory from `import.meta.url`, selects `run_backend.cmd` on Windows and `run_backend.sh` on macOS/Linux, then starts FastAPI on `127.0.0.1:8765`.
- Tauri loads `http://127.0.0.1:8765` in dev mode.
- Packaged builds include `desktop/dist/index.html`, which waits for `/health` and then opens the existing workbench.
- The Tauri shell expects a sidecar named `alphafoundry-backend`. The current macOS ARM development shim is `src-tauri/binaries/alphafoundry-backend-aarch64-apple-darwin` and delegates to the Python launcher.
- The Workbench page handles browser refresh locally: `F5`, macOS `Cmd+R`, and Windows/Linux `Ctrl+R` prevent the browser default and call `window.location.reload()`, including while an input has focus. This is page refresh only; it does not register a Tauri native shortcut, restart the sidecar, or enable HMR.
- `tauri dev` lets `beforeDevCommand` start the backend. Packaged debug and release builds start the bundled sidecar.
- The packaged sidecar resolves its resource root in this order: `ALPHAFOUNDRY_PROJECT_ROOT`, PyInstaller's `sys._MEIPASS` bundle directory, then the source-tree fallback. That resolved root is also passed to watchdog and worker processes as their cwd and `ALPHAFOUNDRY_PROJECT_ROOT`, so one-file bundles load self-contained resources instead of a temporary launcher-relative path.

## Why This Differs From cc-switch

cc-switch keeps most local backend behavior in Rust Tauri commands. AlphaFoundry keeps investment research, AI, document, market data, and report generation logic in Python because those modules already depend on FastAPI, SQLAlchemy, pandas, document tooling, model gateways, and financial data adapters.

The shared pattern is the desktop delivery layer:

- Tauri native shell
- platform-specific packaging
- GitHub Releases for distribution
- signed updater artifacts once release keys are configured

## Local Development

Run the backend directly:

```bash
scripts/desktop/run_backend.sh --host 127.0.0.1 --port 8765 --reload
```

Then run the Tauri shell after installing Node and Rust tooling:

```bash
npm install
npm run desktop:dev
```

To build a local debug `.app`:

```bash
npm run desktop:build:debug
```

The debug `.app` starts the bundled sidecar. If you build without replacing the shim, it delegates to the local Python launcher:

```bash
src-tauri/binaries/alphafoundry-backend-aarch64-apple-darwin --host 127.0.0.1 --port 8765
```

Set `ALPHAFOUNDRY_PYTHON=/path/to/python` when you want to force a specific Python environment.

## Local Packaging Flow

Build the Python backend sidecar:

```bash
npm run desktop:sidecar
```

Copy the generated platform-specific sidecar into Tauri's `externalBin` location:

```bash
npm run desktop:prepare-sidecar
```

Build the desktop bundle:

```bash
npm run desktop:build
```

The generated sidecar is intentionally written under `build/desktop-sidecar/dist/`. It is a self-contained PyInstaller package of `backend_launcher.py`, including required backend modules, third-party package data, and web/report-project assets. The `src-tauri/binaries/` checked-in macOS ARM file remains a small development shim; release workflows copy the real generated sidecar into that directory only inside the build workspace.

On the first frozen launch, the launcher creates an editable per-user `.env`. If `DATABASE_URL` is absent from both the process environment and that user file, the desktop app defaults to `data_dir/alphafoundry.db`; uncomment and configure the PostgreSQL `DATABASE_URL` template entry only when PostgreSQL is required.

## Native CI and GitHub Releases

`.github/workflows/desktop-verify.yml` is the required native build gate for pull requests and pushes to `main` that affect desktop packaging. It builds the macOS Apple Silicon target (`macos-14` / `aarch64-apple-darwin`) and the Windows x64 target (`windows-2022` / `x86_64-pc-windows-msvc`) independently. Each job installs the locked Node dependencies, Python 3.11 development test dependencies, Rust and PyInstaller; then it builds the native sidecar, verifies its target-specific filename, prepares an isolated database with the `vector` extension, and starts only that freshly built sidecar for a loopback `/health` smoke check. macOS uses Homebrew PostgreSQL 17 with `pgvector` and a temporary `PGDATA`; Windows uses a named `pgvector/pgvector:pg16` Docker container. The helper always terminates only its own child process; macOS stops only that temporary PostgreSQL data directory, while Windows removes only its named container. The bundle and `build/desktop-sidecar/health-smoke.log` are retained for 14 days.

The workflow at `.github/workflows/desktop-release.yml` can be triggered manually from GitHub Actions or by pushing a `v*` tag. It uses the same two native targets and publishes their bundles to one draft prerelease through `tauri-apps/tauri-action@v0`.

Native build CI validates that clean macOS and Windows runners can build their own sidecars and Tauri bundles. It does not replace installation-level acceptance on real devices with licensed Microsoft Office, Excel and Wind installed and signed in. Before a release, run that real-device acceptance on both supported platforms, including the relevant Office/Wind, permissions, installer, upgrade and uninstall flows.

Required repository permission:

- `contents: write` for creating/updating the GitHub Release.

Optional updater settings:

- `TAURI_UPDATER_PUBKEY` repository secret: public key written into generated `src-tauri/tauri.release.conf.json`.
- `TAURI_SIGNING_PRIVATE_KEY` repository secret: private key used by Tauri to sign updater artifacts.
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` repository secret: password for the private key if one is configured.
- `ALPHAFOUNDRY_UPDATER_ENDPOINT` repository variable: optional override for the updater `latest.json` URL. If omitted, the endpoint defaults to GitHub Releases: `https://github.com/Leon-Huang001208/AlphaFoundry/releases/latest/download/latest.json`.

When `TAURI_UPDATER_PUBKEY` is missing, CI still builds installable bundles but does not request updater artifacts.

## Release Work Still Needed

The next packaging pass should add:

- macOS Developer ID signing and notarization
- Windows MSI signing
- Linux AppImage, deb, and rpm artifact review after the first CI run
- Tauri updater runtime UI/check flow after signing keys are configured
- sidecar dependency trimming so the Python executable does not bundle unused ML/notebook/GUI packages
- data directory migration rules so user data survives app updates
