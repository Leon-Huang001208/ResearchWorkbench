"""Generate a Tauri release config fragment for signed updater artifacts."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "src-tauri" / "tauri.release.conf.json"
DEFAULT_ENDPOINT = (
    "https://github.com/Leon-Huang001208/AlphaFoundry/releases/latest/download/latest.json"
)


def release_config(public_key: str, endpoint: str) -> dict[str, object]:
    """Return the Tauri config fragment merged during release builds."""
    return {
        "bundle": {
            "createUpdaterArtifacts": True,
        },
        "plugins": {
            "updater": {
                "pubkey": public_key,
                "endpoints": [endpoint],
            }
        },
    }


def write_config() -> Path:
    """Write the release config using environment-provided updater settings."""
    public_key = os.environ.get("TAURI_UPDATER_PUBKEY", "").strip()
    if not public_key:
        raise RuntimeError("TAURI_UPDATER_PUBKEY is required to generate updater config")

    endpoint = os.environ.get("ALPHAFOUNDRY_UPDATER_ENDPOINT", "").strip() or DEFAULT_ENDPOINT
    OUTPUT.write_text(
        json.dumps(release_config(public_key, endpoint), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return OUTPUT


def main() -> int:
    """Generate the release config and print its path."""
    print(write_config())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
