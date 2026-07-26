# AlphaFoundry Desktop Packaging

AlphaFoundry is moving toward a Tauri desktop shell while keeping the current FastAPI Web Workbench intact.

## Current Shape

- Existing UI remains served by `app.api.main:app`.
- Desktop development uses `scripts/desktop/run_backend.sh` to select a Python runtime and start FastAPI on `127.0.0.1:8765`.
- Tauri loads `http://127.0.0.1:8765` in dev mode.
- Packaged builds include `desktop/dist/index.html`, which waits for `/health` and then opens the existing workbench.
- The Tauri shell expects a sidecar named `alphafoundry-backend`. The current macOS ARM development shim is `src-tauri/binaries/alphafoundry-backend-aarch64-apple-darwin` and delegates to the Python launcher.
- `tauri dev` lets `beforeDevCommand` start the backend. Packaged debug and release builds start the bundled sidecar.
- 桌面端运行时配置由 `core/settings/runtime.py` 统一解析：Windows 使用 `%LOCALAPPDATA%\AlphaFoundry`，macOS 使用 `~/Library/Application Support/AlphaFoundry`；可用 `ALPHAFOUNDRY_DESKTOP_DATA_DIR` 覆盖。
- 安装包不会下载、安装或管理 PostgreSQL/pgvector。首次启动找不到可用数据库时会进入数据库配置模式，而不会静默降级 SQLite。
- `ALPHAFOUNDRY_BACKEND_URL` 是 worker、scheduler 和本地 API 调用的唯一地址来源；桌面默认 `http://127.0.0.1:8765`，Web 开发默认 `http://127.0.0.1:8000`。

## Desktop Runtime Configuration

### PostgreSQL prerequisite

Desktop builds do not bundle, download, install, upgrade, uninstall, or manage a database server. If the first launch cannot reach a usable PostgreSQL + pgvector instance, the desktop app stays healthy in **database setup mode**: only System Configuration is available and all database-dependent workbench features remain blocked.

Install PostgreSQL 15+ and pgvector yourself, create the `alphafoundry` database, and enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The first launch creates a per-user `.env` with owner-only permissions on macOS/Linux. Save a PostgreSQL psycopg v3 URL in System Configuration, then restart the desktop app before the full workbench can use the new connection:

```dotenv
DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/alphafoundry
```

### Location and migration

- Windows: `%LOCALAPPDATA%\AlphaFoundry`
- macOS: `~/Library/Application Support/AlphaFoundry`
- Override: `ALPHAFOUNDRY_DESKTOP_DATA_DIR`
- Explicit configuration file: `ALPHAFOUNDRY_CONFIG_FILE`

Windows upgrades detect a legacy `%APPDATA%\AlphaFoundry\.env` and copy it only when the new local directory has no `.env`; an existing local configuration is never overwritten. To move to another computer, close AlphaFoundry, copy the application data directory, export/import PostgreSQL with `pg_dump` / `pg_restore`, update `DATABASE_URL` if needed, then run `python scripts/bootstrap_db.py`.

### Local-only control plane

The desktop backend accepts only `localhost` or `127.0.0.1` as its listener. If the selected port is occupied, the launcher stops without terminating the unknown owning process. Configuration endpoints are restricted to loopback clients, do not return persisted secrets, and are disabled in `web-prod` mode. Database and advanced logging configuration changes are persisted for the next restart rather than falsely claiming that the current SQLAlchemy engine or logging handlers have switched. Values injected through the process environment are shown as locked and cannot be overwritten by the configuration page. `ALPHAFOUNDRY_BACKEND_URL` is the single base URL used by workers and scheduled API calls.

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

The generated sidecar is intentionally written under `build/desktop-sidecar/dist/`. The `src-tauri/binaries/` checked-in macOS ARM file remains a small development shim; release workflows copy the real generated sidecar into that directory only inside the build workspace.

## 跨平台开发与发布验证流程

AlphaFoundry 采用“一套源码、各目标平台原生构建”的策略：Tauri 壳和 Python 业务代码共用，但 Python sidecar 是平台相关的原生可执行文件，必须分别为 macOS 和 Windows 打包。macOS 产物不能用于 Windows，反之亦然。

### 日常开发

开发者可在 macOS 上修改和运行代码，无需为每次本地验证都重打安装包：`tauri dev` 使用源码启动 FastAPI 后端。应先运行与平台无关的单元、接口和前端测试。

### 每次桌面端相关改动

凡影响 `src-tauri/`、`desktop/`、`scripts/desktop/`、sidecar、桌面路径/配置、安装包、更新机制或 Excel/Wind 集成的改动，必须经过以下验证：

1. 在开发机运行相关的通用测试和本地桌面测试。
2. 通过 GitHub Actions 的原生 Windows runner 完成依赖安装、Python sidecar (`.exe`) 构建、Tauri Windows 安装包构建，以及真实 PostgreSQL + pgvector 的 `ready` 启动/`/health` 检查。
3. 通过 macOS runner 完成对应的 sidecar 和桌面包构建，并在两个 runner 上用不可连接但格式正确的 PostgreSQL URL 验证 `setup_required` 配置模式。CI 的临时 PostgreSQL 仅用于 ready 测试；安装包和 setup-required 测试不会安装或管理用户数据库。

macOS 本地测试不等于 Windows 验证；Windows CI 未通过或尚未运行时，不得宣称 Windows 兼容。

### 发布前冒烟测试

在发布新版本前，必须在真实 Windows x64 环境安装 CI 生成的安装包，并至少验证：安装/卸载/升级、主窗口启动、sidecar 启动、`/health`、用户数据目录、日志和配置文件。还必须验证没有 PostgreSQL 时能进入且仅能使用配置模式；保存可连接的 PostgreSQL + pgvector 配置后，重启可进入完整工作台。涉及 Excel/Wind、系统权限、签名/杀毒软件兼容或自动更新的版本，必须在真实 Windows 上验证相应功能。macOS 发版也应在对应架构的真实设备上完成相同级别的安装验证。

### 发布节奏

日常代码修改只需开发模式验证；只有需要让用户获得变更时，才由 CI 为每个目标平台构建新的 sidecar 和安装包，并以该构建产物完成测试后发布。

## GitHub Release Workflow

`.github/workflows/desktop-verify.yml` 会在桌面端及首次启动相关文件的 PR，以及直接推送到 `master` 时运行。它在原生 macOS Apple Silicon 和 Windows x64 runner 上执行桌面契约测试、构建平台对应的 Python sidecar，并验证两种 `/health` 契约：真实 PostgreSQL + pgvector 的 `ready`，以及独立数据目录和不可连接 PostgreSQL URL 下的 `setup_required`。两个 smoke 日志都会作为构建产物上传，最后才构建 Tauri 安装包。

为确保该检查在两个原生 runner 上都使用真实的 PostgreSQL + pgvector，macOS runner 使用 Homebrew 安装 PostgreSQL 与 pgvector；Windows runner 安装 PostgreSQL 16，并用 Visual Studio x64 工具链从固定的 pgvector 源码版本构建扩展。不能在 Windows runner 上使用 Linux 版 pgvector Docker 镜像，因为该 runner 的 Docker 引擎仅支持 Windows 容器。

The release workflow at `.github/workflows/desktop-release.yml` can be triggered manually from GitHub Actions or by pushing a `v*` tag. It builds a draft prerelease for:

- macOS Apple Silicon on `macos-14` (`aarch64-apple-darwin`)
- Windows x64 on `windows-2022` (`x86_64-pc-windows-msvc`)

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
- Tauri updater runtime UI/check flow after signing keys are configured
- sidecar dependency trimming so the Python executable does not bundle unused ML/notebook/GUI packages
- data directory migration rules so user data survives app updates
