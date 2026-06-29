#!/usr/bin/env python3
"""Prime Wind realtime workbook formulas through Excel."""

from __future__ import annotations

import argparse
from pathlib import Path

from core.observability import get_logger
from services.wind_realtime_workbook import (
    DEFAULT_WORKBOOK_PATH,
    prime_realtime_workbook_formulas,
)

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite Wind formulas through Excel so the Wind add-in refreshes them."
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=DEFAULT_WORKBOOK_PATH,
        help="Path to AlphaFoundry_Wind_Realtime.xlsx",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1,
        help="View formulas per Excel write batch.",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=1.0,
        help="Seconds to pause between batches.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Keep Excel visible while priming formulas.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    workbook_path = args.workbook.expanduser().resolve()
    count = prime_realtime_workbook_formulas(
        workbook_path,
        chunk_size=args.chunk_size,
        pause_seconds=args.pause,
        visible=args.visible,
    )
    logger.info("Primed %s Wind batch formulas via script", count)


if __name__ == "__main__":
    main()
