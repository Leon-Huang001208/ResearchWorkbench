"""Build the AlphaFoundry Python backend as a Tauri sidecar executable."""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "build" / "desktop-sidecar" / "dist"
WORK_DIR = REPO_ROOT / "build" / "desktop-sidecar" / "work"
SPEC_DIR = REPO_ROOT / "build" / "desktop-sidecar" / "spec"
ENTRYPOINT = REPO_ROOT / "scripts" / "desktop" / "backend_launcher.py"

COLLECT_SUBMODULES = [
    "app",
    "cognitive_agents",
    "connectors",
    "core",
    "data_layer",
    "data_sources",
    "ingestion",
    "knowledge_layer",
    "memory_learning",
    "reasoning",
    "reporting",
    "services",
    "signal_lab",
    "storage",
    "timing_engine",
]

COLLECT_DATA = ["akshare", "vectorbt"]

PROJECT_DATA = [
    (REPO_ROOT / "app" / "web", Path("app") / "web"),
    (REPO_ROOT / "reporting" / "templates", Path("reporting") / "templates"),
    (REPO_ROOT / "report_projects", Path("report_projects")),
]


def target_triple() -> str:
    """Return the Tauri sidecar target triple for the current runner."""
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return "aarch64-apple-darwin"
    if system == "Darwin" and machine in {"x86_64", "amd64"}:
        return "x86_64-apple-darwin"
    if system == "Linux" and machine in {"x86_64", "amd64"}:
        return "x86_64-unknown-linux-gnu"
    if system == "Linux" and machine in {"arm64", "aarch64"}:
        return "aarch64-unknown-linux-gnu"
    if system == "Windows" and machine in {"x86_64", "amd64"}:
        return "x86_64-pc-windows-msvc"

    raise SystemExit(f"Unsupported sidecar target: {system}-{machine}")


def sidecar_name(triple: str) -> str:
    """Return the executable name PyInstaller should produce for Tauri."""
    suffix = ".exe" if triple.endswith("windows-msvc") or "windows" in triple else ""
    return f"alphafoundry-backend-{triple}{suffix}"


def add_data_arg(source: Path, destination: Path) -> str:
    """Return a PyInstaller --add-data argument using the platform path separator."""
    return f"{source}{os.pathsep}{destination.as_posix()}"


def build_pyinstaller_args() -> list[str]:
    """Build PyInstaller argv for the current platform."""
    triple = target_triple()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--name",
        sidecar_name(triple),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(REPO_ROOT),
    ]

    for module in COLLECT_SUBMODULES:
        args.extend(["--collect-submodules", module])
    for source, destination in PROJECT_DATA:
        args.extend(["--add-data", add_data_arg(source, destination)])
    for package in COLLECT_DATA:
        args.extend(["--collect-data", package])

    args.append(str(ENTRYPOINT))
    return args


def main() -> int:
    """Run PyInstaller and return its exit code."""
    args = build_pyinstaller_args()
    return subprocess.call(args, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
