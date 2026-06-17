"""Desktop backend launcher for the AlphaFoundry Tauri shell."""
from __future__ import annotations

import argparse
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Sequence


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_LOG_DIR = Path("logs")
APP_IMPORT = "app.api.main:app"
PROJECT_ROOT = Path(os.environ.get("ALPHAFOUNDRY_PROJECT_ROOT", Path(__file__).resolve().parents[2]))


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the packaged desktop backend."""
    parser = argparse.ArgumentParser(description="Run the AlphaFoundry desktop backend")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for local dev")
    return parser


def configure_launcher_logging(log_dir: Path) -> Path:
    """Configure file logging and return the log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "desktop-backend.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    return log_file


def is_frozen() -> bool:
    """Return whether this launcher is running from a PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def desktop_data_dir() -> Path:
    """Return the persistent per-user data directory for desktop builds."""
    override = os.environ.get("ALPHAFOUNDRY_DESKTOP_DATA_DIR")
    if override:
        return Path(override).expanduser()

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "AlphaFoundry"
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "AlphaFoundry"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "AlphaFoundry"


def apply_frozen_desktop_defaults() -> Path | None:
    """Apply standalone desktop defaults before app settings are imported."""
    if not is_frozen():
        return None

    data_dir = desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "objects").mkdir(parents=True, exist_ok=True)
    (data_dir / "markdown").mkdir(parents=True, exist_ok=True)
    (data_dir / "raw_text").mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(data_dir))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{data_dir / 'alphafoundry.db'}")
    os.environ.setdefault("LOG_DIR", str(data_dir / "logs"))
    os.environ.setdefault("OBJECT_STORAGE_PATH", str(data_dir / "objects"))
    os.environ.setdefault("PDF_MARKDOWN_DIR", str(data_dir / "markdown"))
    os.environ.setdefault("PDF_RAW_TEXT_DIR", str(data_dir / "raw_text"))
    return data_dir


def run_backend(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI backend through uvicorn."""
    import uvicorn

    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    uvicorn.run(
        APP_IMPORT,
        host=host,
        port=port,
        reload=reload,
        log_config=None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Start the desktop backend and return a process exit code."""
    args = build_parser().parse_args(argv)
    data_dir = apply_frozen_desktop_defaults()
    if data_dir is not None and args.log_dir == DEFAULT_LOG_DIR:
        args.log_dir = data_dir / "logs"
    log_file = configure_launcher_logging(args.log_dir)
    logger = logging.getLogger("alphafoundry.desktop")
    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP", "1")
    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP_URL", f"http://{args.host}:{args.port}")

    try:
        logger.info(
            "Starting AlphaFoundry desktop backend",
            extra={"host": args.host, "port": args.port, "log_file": str(log_file)},
        )
        run_backend(args.host, args.port, args.reload)
    except Exception:
        logger.exception("AlphaFoundry desktop backend failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
