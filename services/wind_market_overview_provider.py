"""Wind-backed market overview data provider."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from core.observability import get_logger
from data_layer.adapters.wind import WindAdapter
from services.wind_index_catalog import (
    DEFAULT_WIND_INDEX_CATALOG_PATH,
    MARKET_VIEW_LABELS,
    WindIndexCatalogEntry,
    derive_market_view_key,
    load_wind_index_catalog,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class WindIndexSeed:
    code: str
    is_concept: bool = True
    view_key: str = "wind_hot_concept"
    view_label: str = "Wind热门概念"
    name: str = ""


WIND_MARKET_INDEX_SEEDS: tuple[WindIndexSeed, ...] = (
    WindIndexSeed("8841701.WI", True, "wind_hot_concept", "Wind热门概念"),  # GPU
    WindIndexSeed("8841738.WI", True, "wind_hot_concept", "Wind热门概念"),  # HBM
    WindIndexSeed("8841258.WI", True, "wind_hot_concept", "Wind热门概念"),  # CPO
    WindIndexSeed("8841058.WI", True, "wind_hot_concept", "Wind热门概念"),  # 服务器
    WindIndexSeed("8841901.WI", True, "wind_hot_concept", "Wind热门概念"),  # ASIC芯片
    WindIndexSeed("884789.WI", True, "wind_hot_concept", "Wind热门概念"),  # 覆铜板
    WindIndexSeed("8841243.WI", True, "wind_hot_concept", "Wind热门概念"),  # 超硬材料
    WindIndexSeed("8841678.WI", True, "wind_hot_concept", "Wind热门概念"),  # AI算力
    WindIndexSeed("8841892.WI", True, "wind_hot_concept", "Wind热门概念"),  # 光芯片
    WindIndexSeed("8841321.WI", True, "wind_hot_concept", "Wind热门概念"),  # 半导体设备
    WindIndexSeed("884857.WI", True, "wind_hot_concept", "Wind热门概念"),  # 钨矿指数
    WindIndexSeed("8841089.WI", True, "wind_hot_concept", "Wind热门概念"),  # 稀土指数
    WindIndexSeed("886001.WI", False, "wind_l1", "Wind一级"),  # 能源设备指数
    WindIndexSeed("886002.WI", False, "wind_l1", "Wind一级"),  # 石油天然气指数
    WindIndexSeed("886003.WI", False, "wind_l1", "Wind一级"),  # 煤炭指数
    WindIndexSeed("886004.WI", False, "wind_l1", "Wind一级"),  # 化工原料指数
    WindIndexSeed("886005.WI", False, "wind_l1", "Wind一级"),  # 化纤行业
    WindIndexSeed("886006.WI", False, "wind_l1", "Wind一级"),  # 精细化工指数
    WindIndexSeed("886007.WI", False, "wind_l1", "Wind一级"),  # 化肥农药指数
    WindIndexSeed("886008.WI", False, "wind_l1", "Wind一级"),  # 建材指数
    WindIndexSeed("886009.WI", False, "wind_l1", "Wind一级"),  # 包装指数
    WindIndexSeed("886010.WI", False, "wind_l1", "Wind一级"),  # 基本金属指数
)

DEFAULT_MARKET_VIEW_KEYS: tuple[str, ...] = tuple(MARKET_VIEW_LABELS)
MAX_ABS_DAILY_INDEX_CHANGE_PCT = 20.0
DEFAULT_WIND_INDEX_BATCH_CODES = 8


def _previous_weekday(current: date) -> date:
    previous = current - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return previous


def latest_weekday_trade_date(now: date | datetime | None = None) -> str:
    """Return a nearby weekday for Wind daily market formulas."""
    current_dt = now or datetime.now()
    current = current_dt.date() if isinstance(current_dt, datetime) else current_dt
    if current.weekday() == 5:
        current -= timedelta(days=1)
    elif current.weekday() == 6:
        current -= timedelta(days=2)
    elif (
        isinstance(current_dt, datetime)
        and current_dt.time() < datetime.strptime("09:30", "%H:%M").time()
    ):
        current = _previous_weekday(current)
    return current.isoformat()


class WindMarketOverviewProvider:
    """Build dashboard sector movers from Wind concept and industry indices."""

    def __init__(
        self,
        adapter: WindAdapter | None = None,
        trade_date_provider: Callable[[], str] = latest_weekday_trade_date,
        seeds: tuple[WindIndexSeed, ...] = WIND_MARKET_INDEX_SEEDS,
        catalog_path: str | Path | None = DEFAULT_WIND_INDEX_CATALOG_PATH,
        max_batch_codes: int = DEFAULT_WIND_INDEX_BATCH_CODES,
    ):
        self.adapter = adapter or WindAdapter()
        self.trade_date_provider = trade_date_provider
        self.max_batch_codes = max(1, int(max_batch_codes or DEFAULT_WIND_INDEX_BATCH_CODES))
        catalog_entries = load_wind_index_catalog(catalog_path) if catalog_path else ()
        self.seeds = tuple(self._seed_from_catalog_entry(entry) for entry in catalog_entries) or seeds

    def get_top_movers(self, limit: int = 10) -> tuple[list[dict], list[dict], bool, float]:
        grouped = self.get_grouped_movers(limit=limit)
        up = grouped["theme"]["up"] or grouped["industry"]["up"]
        down = grouped["theme"]["down"] or grouped["industry"]["down"]
        return up, down, grouped["has_real_data"], grouped["fetched_at"]

    def get_grouped_movers(
        self,
        limit: int = 10,
        view_keys: tuple[str, ...] | None = None,
    ) -> dict:
        seeds = self._filter_seeds(view_keys)
        if not seeds:
            return self._empty_grouped_movers()

        try:
            if hasattr(self.adapter, "is_available") and not self.adapter.is_available():
                logger.info("Wind adapter unavailable for market overview")
                return self._empty_grouped_movers()

            trade_date = self.trade_date_provider()
            codes = [seed.code for seed in seeds]
            seed_map = {seed.code: seed for seed in seeds}
            df = self._fetch_index_quotes(codes, trade_date=trade_date, seed_map=seed_map)
            if self._all_pct_changes_zero(df):
                fallback_trade_date = _previous_weekday(
                    datetime.fromisoformat(trade_date).date()
                ).isoformat()
                if fallback_trade_date != trade_date:
                    logger.info(
                        "Wind market overview all zero for %s, retrying %s",
                        trade_date,
                        fallback_trade_date,
                    )
                    df = self._fetch_index_quotes(
                        codes,
                        trade_date=fallback_trade_date,
                        seed_map=seed_map,
                    )
        except Exception as exc:
            logger.warning("Wind market overview fetch failed: %s", exc)
            return self._empty_grouped_movers()

        items: list[dict] = []
        for _, row in df.iterrows():
            code = str(row.get("code") or "")
            name = str(row.get("name") or "").strip()
            change = row.get("pct_change")
            if not code or not name or change is None:
                continue
            try:
                change_pct = round(float(change), 2)
            except (TypeError, ValueError):
                continue

            if abs(change_pct) > MAX_ABS_DAILY_INDEX_CHANGE_PCT:
                logger.warning("Ignoring abnormal Wind index change: %s %s%%", code, change_pct)
                continue

            seed = seed_map.get(code, WindIndexSeed(code, True))
            safe_code = code.replace(".", "-")
            items.append(
                {
                    "sector_id": f"wind-{safe_code}",
                    "name": name,
                    "change_pct": change_pct,
                    "leading_stocks": [],
                    "related_news_count": 0,
                    "is_concept": seed.is_concept,
                    "source": "wind",
                    "view_key": seed.view_key,
                    "view_label": seed.view_label,
                }
            )

        views = self._build_views(items, limit)
        theme_items = views["wind_hot_concept"]["up"] + views["wind_hot_concept"]["down"]
        industry_items = [
            item
            for key in DEFAULT_MARKET_VIEW_KEYS
            if key != "wind_hot_concept"
            for item in views[key]["up"] + views[key]["down"]
        ]

        theme_up, theme_down = self._split_movers(theme_items, limit)
        industry_up, industry_down = self._split_movers(industry_items, limit)

        grouped = {
            **views,
            "theme": {"up": theme_up, "down": theme_down},
            "industry": {"up": industry_up, "down": industry_down},
            "views": views,
            "has_real_data": bool(items),
            "fetched_at": datetime.now(UTC).timestamp(),
        }
        return grouped

    def _filter_seeds(self, view_keys: tuple[str, ...] | None) -> tuple[WindIndexSeed, ...]:
        if not view_keys:
            return self.seeds
        allowed = set(view_keys)
        return tuple(seed for seed in self.seeds if seed.view_key in allowed)

    def _fetch_index_quotes(
        self,
        codes: list[str],
        trade_date: str,
        seed_map: dict[str, WindIndexSeed] | None = None,
    ) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for offset in range(0, len(codes), self.max_batch_codes):
            batch = codes[offset : offset + self.max_batch_codes]
            try:
                names_by_code = {
                    code: seed.name
                    for code in batch
                    if seed_map and (seed := seed_map.get(code)) and seed.name
                }
                try:
                    df = self.adapter.fetch_index_quotes(
                        batch,
                        trade_date=trade_date,
                        names_by_code=names_by_code,
                        include_close=False,
                    )
                except TypeError as exc:
                    if "names_by_code" not in str(exc):
                        raise
                    df = self.adapter.fetch_index_quotes(batch, trade_date=trade_date)
            except Exception as exc:
                logger.warning(
                    "Wind market overview batch failed: trade_date=%s offset=%s size=%s error=%s",
                    trade_date,
                    offset,
                    len(batch),
                    exc,
                )
                continue
            if df is not None and not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _all_pct_changes_zero(df) -> bool:
        if df is None or df.empty or "pct_change" not in df:
            return False
        values = []
        for value in df["pct_change"].tolist():
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        return bool(values) and all(abs(value) < 0.000001 for value in values)

    @staticmethod
    def _seed_from_catalog_entry(entry: WindIndexCatalogEntry) -> WindIndexSeed:
        view_key = entry.view_key or derive_market_view_key(
            entry.family, entry.category, entry.is_concept
        )
        return WindIndexSeed(
            code=entry.code,
            is_concept=entry.is_concept,
            view_key=view_key,
            view_label=entry.view_label or MARKET_VIEW_LABELS.get(view_key, entry.category),
            name=entry.name,
        )

    def _build_views(self, items: list[dict], limit: int) -> dict[str, dict[str, list[dict]]]:
        views = self._empty_views()
        for key in DEFAULT_MARKET_VIEW_KEYS:
            matching = [item for item in items if item.get("view_key") == key]
            views[key]["up"], views[key]["down"] = self._split_movers(matching, limit)
        return views

    @staticmethod
    def _split_movers(items: list[dict], limit: int) -> tuple[list[dict], list[dict]]:
        up = sorted(
            [item for item in items if item["change_pct"] > 0],
            key=lambda item: item["change_pct"],
            reverse=True,
        )[:limit]
        down = sorted(
            [item for item in items if item["change_pct"] < 0],
            key=lambda item: item["change_pct"],
        )[:limit]
        return up, down

    @staticmethod
    def _empty_grouped_movers() -> dict:
        views = WindMarketOverviewProvider._empty_views()
        return {
            **views,
            "theme": {"up": [], "down": []},
            "industry": {"up": [], "down": []},
            "views": views,
            "has_real_data": False,
            "fetched_at": 0.0,
        }

    @staticmethod
    def _empty_views() -> dict[str, dict[str, list[dict]]]:
        return {key: {"up": [], "down": []} for key in DEFAULT_MARKET_VIEW_KEYS}
