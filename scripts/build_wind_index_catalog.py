#!/usr/bin/env python3
"""Build a local Wind index catalog through Wind Excel formulas.

Example:
    python scripts/build_wind_index_catalog.py \
      --ranges 884001-884999 8841000-8841999 886001-886200 \
      --output data_sources/wind_index_catalog.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_layer.adapters.wind import WindExcelClient  # noqa: E402
from data_layer.adapters.wind import formulas as wf  # noqa: E402
from services.wind_index_catalog import (  # noqa: E402
    DEFAULT_WIND_INDEX_CATALOG_PATH,
    WindIndexCatalogEntry,
    expand_wind_code_ranges,
    load_wind_index_catalog,
    save_wind_index_catalog,
)

DEFAULT_RANGES = (
    "882001-882099",
    "882100-882199",
    "882200-882399",
    "882400-882699",
    "884001-884999",
    "8841000-8841999",
    "886001-886200",
)


def _is_valid_name(value: object) -> bool:
    if value is None or isinstance(value, Exception):
        return False
    text = str(value).strip()
    if not text:
        return False
    if text.upper().startswith("#"):
        return False
    if text.lower() in {"fetch...", "loading...", "calculating...", "connecting..."}:
        return False
    return True


def _family_for_code(code: str) -> tuple[str, str, bool]:
    numeric_code = code.split(".", 1)[0]
    if numeric_code.startswith("8820"):
        return "wind_l1", "Wind一级行业指数", False
    if numeric_code.startswith("8821"):
        return "wind_l2", "Wind二级行业指数", False
    if numeric_code.startswith("8822") or numeric_code.startswith("8823"):
        return "wind_l3", "Wind三级行业指数", False
    if (
        numeric_code.startswith("8824")
        or numeric_code.startswith("8825")
        or numeric_code.startswith("8826")
    ):
        return "wind_l4", "Wind四级行业指数", False
    if code.startswith("886"):
        return "wind_l1", "Wind一级行业", False
    return "wind_concept", "热门概念", True


def discover_entries(codes: tuple[str, ...], chunk_size: int = 80) -> list[WindIndexCatalogEntry]:
    client = WindExcelClient(visible=False, timeout=45.0)
    entries: list[WindIndexCatalogEntry] = []
    priority = len(codes)

    for offset in range(0, len(codes), chunk_size):
        chunk = codes[offset : offset + chunk_size]
        formulas = [wf.s_info_name(code) for code in chunk]
        results = client.execute_batch(formulas, timeout=60.0)
        for code, value in zip(chunk, results):
            if not _is_valid_name(value):
                continue
            name = str(value).strip()
            family, category, is_concept = _family_for_code(code)
            is_active = "退市" not in name and "废弃" not in name and "无效" not in name
            entries.append(
                WindIndexCatalogEntry(
                    code=code,
                    name=name,
                    family=family,
                    category=category,
                    is_active=is_active,
                    priority=priority,
                    is_concept=is_concept,
                )
            )
            priority -= 1
        print(f"scanned {min(offset + chunk_size, len(codes))}/{len(codes)}; valid={len(entries)}")

    return entries


def merge_entries(
    old_entries: tuple[WindIndexCatalogEntry, ...],
    new_entries: list[WindIndexCatalogEntry],
) -> list[WindIndexCatalogEntry]:
    merged: dict[str, WindIndexCatalogEntry] = {entry.code: entry for entry in old_entries}
    for entry in new_entries:
        merged[entry.code] = entry
    return sorted(merged.values(), key=lambda entry: entry.priority, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local Wind index catalog")
    parser.add_argument("--ranges", nargs="*", default=list(DEFAULT_RANGES))
    parser.add_argument("--output", default=str(DEFAULT_WIND_INDEX_CATALOG_PATH))
    parser.add_argument("--chunk-size", type=int, default=80)
    parser.add_argument("--replace", action="store_true", help="Do not merge existing output")
    args = parser.parse_args()

    output = Path(args.output)
    codes = expand_wind_code_ranges(args.ranges)
    print(f"discovering {len(codes)} Wind index codes -> {output}")

    discovered = discover_entries(codes, chunk_size=args.chunk_size)
    entries = discovered
    if not args.replace:
        entries = merge_entries(load_wind_index_catalog(output), discovered)

    save_wind_index_catalog(entries, output)
    print(f"saved {len(entries)} entries to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
