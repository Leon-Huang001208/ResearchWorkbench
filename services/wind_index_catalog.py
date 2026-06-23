"""Wind index catalog CSV helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from core.observability import get_logger

logger = get_logger(__name__)

DEFAULT_CATALOG_PATH = Path("data_sources") / "wind_index_catalog.csv"
DEFAULT_WIND_INDEX_CATALOG_PATH = DEFAULT_CATALOG_PATH


class WindIndexCatalogError(RuntimeError):
    """Raised when an existing Wind index catalog cannot be loaded."""


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


def load_wind_index_catalog(
    path: str | Path = DEFAULT_CATALOG_PATH,
) -> list[WindIndexCatalogEntry]:
    catalog_path = Path(path)
    if not catalog_path.exists():
        logger.warning("Wind index catalog not found: %s", catalog_path)
        return []

    entries: list[WindIndexCatalogEntry] = []
    try:
        with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            code_column = "code" if "code" in fieldnames else "wind_code" if "wind_code" in fieldnames else ""
            if not code_column:
                message = (
                    f"Failed to load Wind index catalog {catalog_path}: "
                    "missing required code header"
                )
                logger.error(message)
                raise WindIndexCatalogError(message)

            for row in reader:
                code = str(row.get(code_column) or "").strip()
                if not code:
                    logger.warning("Skipping Wind catalog row without code: %s", row)
                    continue
                entries.append(
                    WindIndexCatalogEntry(
                        code=code,
                        name=str(row.get("name") or "").strip(),
                        family=str(row.get("family") or "wind_concept").strip(),
                        category=str(row.get("category") or "热门概念").strip(),
                        is_active=_parse_bool(row.get("is_active"), default=True),
                        priority=_parse_int(row.get("priority")),
                        is_concept=_parse_bool(row.get("is_concept"), default=True),
                        view_key=str(row.get("view_key") or "").strip(),
                        view_label=str(row.get("view_label") or "").strip(),
                        notes=str(row.get("notes") or "").strip(),
                    )
                )
    except WindIndexCatalogError:
        raise
    except (UnicodeDecodeError, csv.Error, OSError) as exc:
        message = f"Failed to load Wind index catalog {catalog_path}: {exc}"
        logger.error(message)
        raise WindIndexCatalogError(message) from exc

    return entries


def save_wind_index_catalog(
    entries: Iterable[WindIndexCatalogEntry],
    path: str | Path = DEFAULT_CATALOG_PATH,
) -> None:
    catalog_path = Path(path)
    fieldnames = [
        "code",
        "name",
        "family",
        "category",
        "is_active",
        "priority",
        "is_concept",
        "view_key",
        "view_label",
        "notes",
    ]

    try:
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with catalog_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                writer.writerow(
                    {
                        "code": entry.code,
                        "name": entry.name,
                        "family": entry.family,
                        "category": entry.category,
                        "is_active": entry.is_active,
                        "priority": entry.priority,
                        "is_concept": entry.is_concept,
                        "view_key": entry.view_key,
                        "view_label": entry.view_label,
                        "notes": entry.notes,
                    }
                )
    except OSError as exc:
        logger.error("Failed to save Wind index catalog %s: %s", catalog_path, exc)
        raise


def _parse_bool(value: object, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def _parse_int(value: object) -> int:
    try:
        return int(str(value or "0").strip())
    except (TypeError, ValueError):
        logger.warning("Invalid Wind catalog priority value: %s", value)
        return 0
