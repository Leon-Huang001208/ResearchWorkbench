"""Local Wind index catalog helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from core.observability import get_logger

logger = get_logger(__name__)

DEFAULT_WIND_INDEX_CATALOG_PATH = (
    Path(__file__).resolve().parents[1] / "data_sources" / "wind_index_catalog.csv"
)


@dataclass(frozen=True)
class WindIndexCatalogEntry:
    code: str
    name: str = ""
    family: str = "wind_concept"
    category: str = "热门概念"
    is_active: bool = True
    priority: int = 0
    is_concept: bool = True
    view_key: str = ""
    view_label: str = ""
    notes: str = ""


MARKET_VIEW_LABELS: dict[str, str] = {
    "wind_hot_concept": "Wind热门概念",
    "wind_l1": "Wind一级",
    "wind_l2": "Wind二级",
    "wind_l3": "Wind三级",
    "wind_l4": "Wind四级",
    "citic_l1": "中信一级",
    "citic_l2": "中信二级",
    "citic_l3": "中信三级",
    "sw_l1": "申万一级",
    "sw_l2": "申万二级",
    "sw_l3": "申万三级",
}


def derive_market_view_key(family: str, category: str, is_concept: bool) -> str:
    """Derive the dashboard market view key from catalog metadata."""
    family_value = str(family or "").strip().lower()
    category_value = str(category or "").strip()
    if family_value in MARKET_VIEW_LABELS:
        return family_value
    if family_value in {"wind_concept", "hot_concept"} or is_concept:
        return "wind_hot_concept"

    level_tokens = (
        ("一级", "l1"),
        ("二级", "l2"),
        ("三级", "l3"),
        ("四级", "l4"),
    )
    source_prefixes = (
        ("wind", "wind"),
        ("万得", "wind"),
        ("wind中国", "wind"),
        ("中信", "citic"),
        ("citic", "citic"),
        ("申万", "sw"),
        ("sw", "sw"),
    )
    combined = f"{family_value} {category_value}".lower()
    for source_token, prefix in source_prefixes:
        if source_token.lower() not in combined:
            continue
        for level_token, level_key in level_tokens:
            if level_token.lower() in combined:
                return f"{prefix}_{level_key}"

    return "wind_l1"


def normalize_wind_code(raw_code: str) -> str:
    """Normalize Wind index codes entered as either 8841701 or 8841701.WI."""
    code = str(raw_code or "").strip().upper()
    if not code:
        return ""
    if "." not in code:
        code = f"{code}.WI"
    return code


def expand_wind_code_ranges(specs: Sequence[str]) -> tuple[str, ...]:
    """Expand compact Wind index code ranges.

    Examples:
        ["8841701-8841703", "886001.WI"] -> 8841701.WI, 8841702.WI, ...
    """
    codes: list[str] = []
    seen: set[str] = set()
    for raw_spec in specs:
        spec = str(raw_spec or "").strip().upper()
        if not spec:
            continue
        if "-" in spec:
            start_raw, end_raw = spec.split("-", 1)
            start = int(start_raw.replace(".WI", ""))
            end = int(end_raw.replace(".WI", ""))
            step = 1 if end >= start else -1
            for value in range(start, end + step, step):
                code = normalize_wind_code(str(value))
                if code and code not in seen:
                    seen.add(code)
                    codes.append(code)
            continue
        code = normalize_wind_code(spec)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return tuple(codes)


def _truthy(value: object, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "active"}


def _int_value(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def load_wind_index_catalog(
    path: str | Path = DEFAULT_WIND_INDEX_CATALOG_PATH,
) -> tuple[WindIndexCatalogEntry, ...]:
    catalog_path = Path(path)
    if not catalog_path.exists():
        return ()

    entries: list[WindIndexCatalogEntry] = []
    seen: set[str] = set()
    try:
        with catalog_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                code = normalize_wind_code(row.get("wind_code") or row.get("code") or "")
                if not code or code in seen:
                    continue
                if not _truthy(row.get("is_active"), default=True):
                    continue
                seen.add(code)
                family = str(row.get("family") or "wind_concept")
                category = str(row.get("category") or "热门概念")
                is_concept = _truthy(row.get("is_concept"), default=True)
                view_key = str(row.get("view_key") or "").strip() or derive_market_view_key(
                    family, category, is_concept
                )
                entries.append(
                    WindIndexCatalogEntry(
                        code=code,
                        name=str(row.get("name") or ""),
                        family=family,
                        category=category,
                        is_active=True,
                        priority=_int_value(row.get("priority"), 0),
                        is_concept=is_concept,
                        view_key=view_key,
                        view_label=str(row.get("view_label") or "").strip()
                        or MARKET_VIEW_LABELS.get(view_key, category),
                        notes=str(row.get("notes") or "").strip(),
                    )
                )
    except Exception as exc:
        logger.warning("Failed to load Wind index catalog %s: %s", catalog_path, exc)
        return ()

    return tuple(sorted(entries, key=lambda entry: entry.priority, reverse=True))


def save_wind_index_catalog(
    entries: Iterable[WindIndexCatalogEntry],
    path: str | Path = DEFAULT_WIND_INDEX_CATALOG_PATH,
) -> Path:
    catalog_path = Path(path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with catalog_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "wind_code",
                "name",
                "family",
                "category",
                "is_active",
                "priority",
                "is_concept",
                "view_key",
                "view_label",
                "notes",
            ],
        )
        writer.writeheader()
        for entry in entries:
            view_key = entry.view_key or derive_market_view_key(
                entry.family, entry.category, entry.is_concept
            )
            view_label = entry.view_label or MARKET_VIEW_LABELS.get(view_key, entry.category)
            writer.writerow(
                {
                    "wind_code": normalize_wind_code(entry.code),
                    "name": entry.name,
                    "family": entry.family,
                    "category": entry.category,
                    "is_active": "true" if entry.is_active else "false",
                    "priority": entry.priority,
                    "is_concept": "true" if entry.is_concept else "false",
                    "view_key": view_key,
                    "view_label": view_label,
                    "notes": entry.notes,
                }
            )
    return catalog_path
