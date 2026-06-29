#!/usr/bin/env python3
"""Run official CSI/CNI index constituent ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from data_layer.repositories.base import db_session
from data_layer.repositories.market_data_repository import MarketDataRepository
from services.official_index_structure_ingestion import (
    discover_official_index_codes,
    ingest_official_index_components,
)

logger = get_logger(__name__)

DEFAULT_CODES = {
    "CSI": ["000300", "000905", "000852"],
    "CNI": ["399001", "399006"],
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest official CSI/CNI constituents into index structure tables."
    )
    parser.add_argument(
        "--provider",
        choices=["CSI", "CNI", "all"],
        default="all",
        help="Index provider to ingest.",
    )
    parser.add_argument(
        "--index-code",
        action="append",
        default=[],
        help="Official index code. Repeat for multiple codes.",
    )
    parser.add_argument(
        "--discover-active",
        action="store_true",
        help="Discover active official index codes from provider catalogs.",
    )
    parser.add_argument(
        "--max-count",
        type=int,
        default=20,
        help="Max discovered index codes per provider. Use 0 for no cap.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        providers = ["CSI", "CNI"] if args.provider == "all" else [args.provider]
        output = {}
        with db_session() as db:
            repo = MarketDataRepository(db)
            for provider in providers:
                index_codes = _resolve_provider_index_codes(
                    provider,
                    explicit_codes=args.index_code,
                    discover_active=args.discover_active,
                    max_count=args.max_count,
                )
                output[provider] = ingest_official_index_components(
                    repo,
                    provider=provider,
                    index_codes=index_codes,
                )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        logger.error("Official index structure ingestion failed: %s", exc)
        print(f"Official index structure ingestion failed: {exc}", file=sys.stderr)
        return 1


def _resolve_provider_index_codes(
    provider: str,
    *,
    explicit_codes: list[str],
    discover_active: bool,
    max_count: int,
    discoverer=discover_official_index_codes,
) -> list[str]:
    if explicit_codes:
        return explicit_codes
    if discover_active:
        return discoverer(provider, max_count=max_count)
    return DEFAULT_CODES[provider]


if __name__ == "__main__":
    raise SystemExit(main())
