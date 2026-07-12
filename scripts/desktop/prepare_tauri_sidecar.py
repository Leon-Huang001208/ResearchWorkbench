"""Copy the generated backend executable into Tauri's externalBin location."""
from __future__ import annotations

import shutil
import stat
from pathlib import Path

from build_sidecar import DIST_DIR, REPO_ROOT, sidecar_name, target_triple

TAURI_BINARIES = REPO_ROOT / "src-tauri" / "binaries"


def prepare_sidecar() -> Path:
    """Copy the generated sidecar executable to src-tauri/binaries."""
    triple = target_triple()
    executable_name = sidecar_name(triple)
    source = DIST_DIR / executable_name
    destination = TAURI_BINARIES / executable_name

    if not source.exists():
        raise FileNotFoundError(f"Built sidecar not found: {source}")

    TAURI_BINARIES.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return destination


def main() -> int:
    """Prepare the Tauri sidecar and print its path."""
    destination = prepare_sidecar()
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
