"""Static wiring tests for the AlphaFoundry desktop shell scaffold."""
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TAURI_CONFIG = ROOT / "src-tauri" / "tauri.conf.json"
TAURI_LIB = ROOT / "src-tauri" / "src" / "lib.rs"
PACKAGE_JSON = ROOT / "package.json"
BOOTSTRAP_JS = ROOT / "desktop" / "dist" / "bootstrap.js"
BOOTSTRAP_HTML = ROOT / "desktop" / "dist" / "index.html"
LAUNCHER = ROOT / "scripts" / "desktop" / "backend_launcher.py"
RUN_BACKEND_SH = ROOT / "scripts" / "desktop" / "run_backend.sh"
BUILD_SIDECAR_SH = ROOT / "scripts" / "desktop" / "build_sidecar.sh"
BUILD_SIDECAR_PY = ROOT / "scripts" / "desktop" / "build_sidecar.py"
PREPARE_SIDECAR = ROOT / "scripts" / "desktop" / "prepare_tauri_sidecar.py"
WRITE_RELEASE_CONFIG = ROOT / "scripts" / "desktop" / "write_tauri_release_config.py"
DESKTOP_RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release.yml"
MACOS_ARM_SIDECAR = ROOT / "src-tauri" / "binaries" / "alphafoundry-backend-aarch64-apple-darwin"
MACOS_ICON = ROOT / "src-tauri" / "icons" / "icon.icns"
WINDOWS_ICON = ROOT / "src-tauri" / "icons" / "icon.ico"


def load_launcher_module():
    spec = importlib.util.spec_from_file_location("desktop_backend_launcher", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_tauri_config_wraps_existing_fastapi_workbench():
    config = json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))

    assert config["productName"] == "AlphaFoundry"
    assert config["build"]["devUrl"] == "http://127.0.0.1:8765"
    assert "scripts/desktop/run_backend.sh" in config["build"]["beforeDevCommand"]
    assert config["build"]["frontendDist"] == "../desktop/dist"
    assert config["bundle"]["targets"] == "all"
    assert config["bundle"]["icon"] == [
        "icons/icon.png",
        "icons/icon.icns",
        "icons/icon.ico",
    ]
    assert "binaries/alphafoundry-backend" in config["bundle"]["externalBin"]
    assert "http://127.0.0.1:8765" in config["app"]["security"]["csp"]


def test_macos_icon_is_available_for_tauri_resource_generation():
    assert MACOS_ICON.exists()
    assert MACOS_ICON.read_bytes().startswith(b"icns")


def test_windows_icon_is_available_for_tauri_resource_generation():
    assert WINDOWS_ICON.exists()
    assert WINDOWS_ICON.read_bytes().startswith(b"\x00\x00\x01\x00")


def test_tauri_rust_shell_starts_backend_sidecar():
    source = TAURI_LIB.read_text(encoding="utf-8")

    assert 'const BACKEND_SIDECAR: &str = "alphafoundry-backend";' in source
    assert "cfg!(dev)" in source
    assert "app.shell().sidecar(BACKEND_SIDECAR)" in source
    assert "beforeDevCommand starts the backend" in source
    assert "start_backend_sidecar" in source
    assert "stop_backend_sidecar" in source
    assert "tauri_plugin_shell::init()" in source


def test_macos_arm_sidecar_shim_invokes_python_launcher():
    source = MACOS_ARM_SIDECAR.read_text(encoding="utf-8")

    assert source.startswith("#!/usr/bin/env bash")
    assert "ALPHAFOUNDRY_PROJECT_ROOT" in source
    assert "dev-project-root" in source
    assert "resolve_project_root" in source
    assert "scripts/desktop/run_backend.sh" in source
    assert '"$@"' in source


def test_desktop_backend_shell_selects_python_runtime():
    source = RUN_BACKEND_SH.read_text(encoding="utf-8")

    assert "ALPHAFOUNDRY_PYTHON" in source
    assert "python3.11" in source
    assert "anaconda3/bin/python" in source
    assert "backend_launcher.py" in source
    assert 'cd "$REPO_ROOT"' in source


def test_sidecar_build_script_uses_pyinstaller_and_tauri_naming():
    shell = BUILD_SIDECAR_SH.read_text(encoding="utf-8")
    source = BUILD_SIDECAR_PY.read_text(encoding="utf-8")

    assert "build_sidecar.py" in shell
    assert "PyInstaller" in source
    assert "--onefile" in source
    assert "alphafoundry-backend-{triple}" in source
    assert "aarch64-apple-darwin" in source
    assert '"build" / "desktop-sidecar" / "dist"' in source
    assert '"app",' in source
    assert '"reporting",' in source
    assert '"data_layer",' in source
    assert 'COLLECT_DATA = ["akshare", "vectorbt"]' in source
    assert 'args.extend(["--collect-submodules", module])' in source
    assert 'args.extend(["--collect-data", package])' in source
    assert 'REPO_ROOT / "app" / "web"' in source
    assert 'REPO_ROOT / "reporting" / "templates"' in source
    assert 'REPO_ROOT / "report_projects"' in source
    assert "os.pathsep" in source


def test_prepare_sidecar_copies_generated_binary_to_tauri_binaries():
    source = PREPARE_SIDECAR.read_text(encoding="utf-8")

    assert "DIST_DIR / executable_name" in source
    assert 'REPO_ROOT / "src-tauri" / "binaries"' in source
    assert "shutil.copy2(source, destination)" in source
    assert "stat.S_IXUSR" in source


def test_release_config_uses_updater_secret_and_latest_json_endpoint(monkeypatch):
    module = load_module("write_tauri_release_config", WRITE_RELEASE_CONFIG)
    monkeypatch.delenv("ALPHAFOUNDRY_UPDATER_ENDPOINT", raising=False)

    config = module.release_config("public-key", module.DEFAULT_ENDPOINT)

    assert config["bundle"]["createUpdaterArtifacts"] is True
    assert config["plugins"]["updater"]["pubkey"] == "public-key"
    assert config["plugins"]["updater"]["endpoints"] == [module.DEFAULT_ENDPOINT]


def test_backend_launcher_allows_project_root_override(monkeypatch):
    monkeypatch.setenv("ALPHAFOUNDRY_PROJECT_ROOT", "/tmp/alphafoundry")
    launcher = load_launcher_module()

    assert str(launcher.PROJECT_ROOT) == "/tmp/alphafoundry"


def test_package_json_exposes_desktop_commands():
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert package["scripts"]["tauri"] == "tauri"
    assert package["scripts"]["desktop:dev"] == "tauri dev"
    assert package["scripts"]["desktop:build"] == "tauri build"
    assert package["scripts"]["desktop:sidecar"] == "python scripts/desktop/build_sidecar.py"
    assert (
        package["scripts"]["desktop:prepare-sidecar"]
        == "python scripts/desktop/prepare_tauri_sidecar.py"
    )
    assert package["scripts"]["desktop:release-config"] == (
        "python scripts/desktop/write_tauri_release_config.py"
    )
    assert "@tauri-apps/cli" in package["devDependencies"]


def test_desktop_release_workflow_builds_platform_matrix_and_draft_release():
    source = DESKTOP_RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "macos-latest" in source
    assert "windows-latest" not in source
    assert "ubuntu-22.04" not in source
    assert "python scripts/desktop/build_sidecar.py" in source
    assert "python scripts/desktop/prepare_tauri_sidecar.py" in source
    assert "Free Linux runner disk space" in source
    assert "cargo fetch --locked" in source
    assert "tauri-apps/tauri-action@v0" in source
    assert "releaseDraft: true" in source
    assert "TAURI_UPDATER_PUBKEY" in source
    assert "TAURI_SIGNING_PRIVATE_KEY" in source


def test_desktop_bootstrap_waits_for_backend_health():
    html = BOOTSTRAP_HTML.read_text(encoding="utf-8")
    source = BOOTSTRAP_JS.read_text(encoding="utf-8")

    assert "AlphaFoundry" in html
    assert "DEFAULT_BACKEND_URL = 'http://127.0.0.1:8765'" in source
    assert "fetch(`${baseUrl}/health`" in source
    assert "window.location.replace(`${baseUrl}/`)" in source
    assert "retry-button" in source


def test_desktop_backend_launcher_defaults_and_logging(tmp_path):
    launcher = load_launcher_module()
    parser = launcher.build_parser()
    args = parser.parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert launcher.PROJECT_ROOT == ROOT

    log_file = launcher.configure_launcher_logging(tmp_path)

    assert log_file == tmp_path / "desktop-backend.log"
    assert log_file.exists()


def test_frozen_backend_launcher_defaults_to_user_sqlite(monkeypatch, tmp_path):
    launcher = load_launcher_module()
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LOG_DIR", raising=False)

    data_dir = launcher.apply_frozen_desktop_defaults()

    assert data_dir == tmp_path
    assert os.environ["DATABASE_URL"] == f"sqlite:///{tmp_path / 'alphafoundry.db'}"
    assert os.environ["LOG_DIR"] == str(tmp_path / "logs")
    assert (tmp_path / "logs").is_dir()
