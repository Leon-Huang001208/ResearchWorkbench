"""Stable CLI entrypoint that isolates Research Workbench from sibling packages."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    """Run the current repository CLI even when a sibling project also owns `app`."""
    project_root = str(Path(__file__).resolve().parents[1])
    if not sys.path or sys.path[0] != project_root:
        sys.path.insert(0, project_root)

    from app.cli.main import cli

    cli(prog_name="rwb")
