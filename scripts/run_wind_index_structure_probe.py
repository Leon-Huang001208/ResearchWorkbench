#!/usr/bin/env python3
"""Build, prime, and read the Wind index structure probe workbook."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from services.wind_index_structure_probe import (
    DEFAULT_PROBE_WORKBOOK_PATH,
    build_index_structure_probe_workbook,
    prime_index_structure_probe_workbook,
    read_index_structure_probe_snapshot,
)

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Research Workbench Wind index/ETF structure field probe."
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=DEFAULT_PROBE_WORKBOOK_PATH,
        help="Probe workbook path.",
    )
    parser.add_argument("--trade-date", default=None, help="Probe trade date YYYY-MM-DD.")
    parser.add_argument(
        "--index-code",
        action="append",
        default=[],
        help="Index code to probe. Repeat for multiple codes.",
    )
    parser.add_argument(
        "--etf-code",
        action="append",
        default=[],
        help="ETF code to probe. Repeat for multiple codes.",
    )
    parser.add_argument(
        "--prime",
        action="store_true",
        help="Open Excel hidden, calculate Wind formulas, and save cached values.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Keep Excel visible while priming.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=10.0,
        help="Seconds to wait after triggering Excel calculation.",
    )
    parser.add_argument(
        "--read",
        action="store_true",
        help="Read cached probe results after build/prime.",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist cached probe results into index/ETF structure tables.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Do not rebuild the workbook before prime/read/persist.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workbook_path = args.workbook.expanduser()
    try:
        if args.skip_build:
            path = workbook_path
            logger.info("Skipped Wind index structure probe workbook build: %s", path)
        else:
            path = build_index_structure_probe_workbook(
                workbook_path=workbook_path,
                trade_date=args.trade_date,
                index_codes=args.index_code or None,
                etf_codes=args.etf_code or None,
            )
            logger.info("Built Wind index structure probe workbook: %s", path)
            print(path)

        if args.prime:
            prime_index_structure_probe_workbook(
                path,
                visible=args.visible,
                wait_seconds=args.wait,
            )

        snapshot = None
        if args.read or args.persist:
            snapshot = read_index_structure_probe_snapshot(path)
        if args.persist and snapshot is not None:
            from data_layer.repositories.base import db_session
            from data_layer.repositories.market_data_repository import MarketDataRepository
            from services.wind_index_structure_ingestion import persist_probe_snapshot

            with db_session() as db:
                summary = persist_probe_snapshot(
                    MarketDataRepository(db),
                    snapshot,
                    trade_date=_trade_date_for_persist(args.trade_date),
                )
            print(json.dumps({"persisted": summary}, ensure_ascii=False, indent=2))

        if args.read and snapshot is not None:
            payload = {
                "status": snapshot.status,
                "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
                "error_count": snapshot.error_count,
                "message": snapshot.message,
                "rows": [
                    {
                        "probe_id": row.probe_id,
                        "domain": row.domain,
                        "target_code": row.target_code,
                        "formula_key": row.formula_key,
                        "label": row.label,
                        "value": row.value,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
                    for row in snapshot.rows
                ],
            }
            print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))
        return 0
    except Exception as exc:
        logger.error("Wind index structure probe failed: %s", exc)
        print(f"Wind index structure probe failed: {exc}", file=sys.stderr)
        return 1


def _trade_date_for_persist(value: str | None):
    from datetime import datetime

    if value:
        return datetime.strptime(value, "%Y-%m-%d")
    return datetime.now()


if __name__ == "__main__":
    raise SystemExit(main())
