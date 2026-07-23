# AlphaFoundry Desktop Packaging

AlphaFoundry is moving toward a Tauri desktop shell while keeping the current FastAPI Web Workbench intact.

## Current Shape

- Existing UI remains served by `app.api.main:app`.
- Desktop development uses the ESM `scripts/desktop/run_backend.js` bridge, which resolves its own directory from `import.meta.url`, selects `run_backend.cmd` on Windows and `run_backend.sh` on macOS/Linux, then starts FastAPI on `127.0.0.1:8765`.
- Tauri loads `http://127.0.0.1:8765` in dev mode.
- Packaged builds include `desktop/dist/index.html`, which waits for `/health` and then opens the existing workbench.
- The Tauri shell expects a sidecar named `alphafoundry-backend`. The current macOS ARM development shim is `src-tauri/binaries/alphafoundry-backend-aarch64-apple-darwin` and delegates to the Python launcher.
- `tauri dev` lets `beforeDevCommand` start the backend. Packaged debug and release builds start the bundled sidecar.

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

## GitHub Release Workflow

The workflow at `.github/workflows/desktop-release.yml` can be triggered manually from GitHub Actions or by pushing a `v*` tag. It builds a draft prerelease for:

- macOS ARM on `macos-latest`
- Windows x64 on `windows-latest`
- Linux x64 on `ubuntu-22.04`

Each job installs Node, Python 3.11, Rust, project Python dependencies, builds the PyInstaller sidecar, copies it into `src-tauri/binaries/`, and lets `tauri-apps/tauri-action@v0` upload platform bundles to the same draft GitHub Release.

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
