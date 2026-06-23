#!/usr/bin/env python3
"""Build the local Wind realtime workbook from the versioned index catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from services.wind_index_catalog import DEFAULT_WIND_INDEX_CATALOG_PATH
from services.wind_realtime_workbook import DEFAULT_WORKBOOK_PATH, build_realtime_workbook

logger = get_logger(__name__)
DEFAULT_CATALOG_FILE = project_root / DEFAULT_WIND_INDEX_CATALOG_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build AlphaFoundry Wind realtime workbook"
    )
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_FILE))
    parser.add_argument("--output", default=str(DEFAULT_WORKBOOK_PATH))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        path = build_realtime_workbook(
            catalog_path=Path(args.catalog).expanduser(),
            workbook_path=Path(args.output).expanduser(),
        )
    except RuntimeError as exc:
        logger.error("Wind realtime workbook build failed: %s", exc)
        print(f"Failed to build Wind realtime workbook: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
