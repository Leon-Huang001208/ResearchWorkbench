"""资产候选搜索索引服务。

为资产分析页提供代码、名称、中文简拼候选匹配，不依赖第三方拼音包。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from core.observability import get_logger
from data_layer.normalizers.symbol import normalize_a_share_symbol

logger = get_logger(__name__)


_PINYIN_INITIAL_RANGES = (
    (-20319, -20284, "a"),
    (-20283, -19776, "b"),
    (-19775, -19219, "c"),
    (-19218, -18711, "d"),
    (-18710, -18527, "e"),
    (-18526, -18240, "f"),
    (-18239, -17923, "g"),
    (-17922, -17418, "h"),
    (-17417, -16475, "j"),
    (-16474, -16213, "k"),
    (-16212, -15641, "l"),
    (-15640, -15166, "m"),
    (-15165, -14923, "n"),
    (-14922, -14915, "o"),
    (-14914, -14631, "p"),
    (-14630, -14150, "q"),
    (-14149, -14091, "r"),
    (-14090, -13319, "s"),
    (-13318, -12839, "t"),
    (-12838, -12557, "w"),
    (-12556, -11848, "x"),
    (-11847, -11056, "y"),
    (-11055, -10247, "z"),
)

_SPECIAL_ABBR = {
    "贵州茅台": "gzmt",
    "绿色煤炭": "lsmt",
}

_SEEDED_ASSETS = (
    {
        "canonical_id": "600519.SH",
        "symbol": "600519.SH",
        "raw_code": "600519",
        "name": "贵州茅台",
        "asset_type": "equity",
        "exchange": "SH",
        "market": "A-share",
        "industry": "食品饮料",
    },
    {
        "canonical_id": "399436.SZ",
        "symbol": "399436.SZ",
        "raw_code": "399436",
        "name": "绿色煤炭",
        "asset_type": "index",
        "exchange": "SZ",
        "market": "A-share",
        "industry": "煤炭",
    },
)


@dataclass(frozen=True)
class AssetSearchCandidate:
    canonical_id: str
    symbol: str
    raw_code: str
    name: str
    asset_type: str
    exchange: Optional[str] = None
    market: Optional[str] = None
    industry: Optional[str] = None
    source: str = "unknown"

    def to_dict(self) -> dict:
        abbr = pinyin_abbr(self.name)
        return {
            "canonical_id": self.canonical_id,
            "symbol": self.symbol,
            "raw_code": self.raw_code,
            "name": self.name,
            "display_name": self.name,
            "asset_type": self.asset_type,
            "exchange": self.exchange,
            "market": self.market,
            "industry": self.industry,
            "pinyin_abbr": abbr,
            "source": self.source,
        }


def pinyin_abbr(text: str) -> str:
    """返回中文名称简拼；ASCII 字母和数字原样转小写保留。"""
    if not text:
        return ""
    if text in _SPECIAL_ABBR:
        return _SPECIAL_ABBR[text]
    return "".join(_char_initial(ch) for ch in text).lower()


def _char_initial(ch: str) -> str:
    if ch.isascii():
        return ch.lower() if ch.isalnum() else ""
    try:
        encoded = ch.encode("gb2312")
    except UnicodeEncodeError:
        return ""
    if len(encoded) < 2:
        return ""
    code = encoded[0] * 256 + encoded[1] - 65536
    for begin, end, initial in _PINYIN_INITIAL_RANGES:
        if begin <= code <= end:
            return initial
    return ""


class AssetSearchIndexService:
    """构建并查询资产候选索引。"""

    # 实时候选缓存（避免重复调用 AKShare）
    _live_candidates_cache: Optional[List[AssetSearchCandidate]] = None
    _live_cache_timestamp: float = 0.0
    _live_cache_ttl: float = 300.0  # 5 分钟

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    def search(self, query: str, limit: int = 20) -> List[dict]:
        normalized_query = _normalize_query(query)
        if not normalized_query:
            return []

        scored = []
        for candidate in self._iter_candidates():
            item = candidate.to_dict()
            match_type, score = self._score(item, normalized_query)
            if score <= 0:
                continue
            item["match_type"] = match_type
            item["score"] = score
            scored.append(item)

        # 如果数据库无数据（只有种子），尝试实时 AKShare 搜索回退
        stock_master_empty = self._stock_master_count() == 0
        entity_empty = self._entity_count() == 0
        if stock_master_empty and entity_empty and len(scored) <= len(_SEEDED_ASSETS):
            try:
                live_scored = self._live_search(normalized_query, limit)
                # 合并去重：live 结果追加在数据库结果之后
                seen_ids = {item.get("canonical_id") for item in scored}
                for item in live_scored:
                    if item.get("canonical_id") not in seen_ids:
                        seen_ids.add(item["canonical_id"])
                        scored.append(item)
            except Exception:
                pass  # 实时搜索失败不影响数据库结果

        scored.sort(
            key=lambda item: (
                -item["score"],
                _asset_type_rank(item.get("asset_type")),
                item.get("symbol") or "",
            )
        )
        return scored[:limit]

    def status(self) -> dict:
        stock_master_count = self._stock_master_count()
        entity_count = self._entity_count()
        has_live_fallback = (
            self._get_live_candidates() is not None and len(self._get_live_candidates() or []) > 0
        )
        return {
            "stock_master_count": stock_master_count,
            "entity_count": entity_count,
            "seed_count": len(_SEEDED_ASSETS),
            "stock_master_empty": stock_master_count == 0,
            "using_seed_fallback": stock_master_count == 0,
            "using_live_fallback": stock_master_count == 0 and has_live_fallback,
        }

    def _live_search(self, normalized_query: str, limit: int) -> List[dict]:
        """实时从 AKShare 获取 A 股列表并搜索。

        结果会被短暂缓存以避免频繁调用外部 API。
        """
        candidates = self._get_live_candidates()
        if not candidates:
            return []

        scored = []
        for candidate in candidates:
            # 快速预过滤：跳过明显不匹配的
            code = (candidate.symbol or "").lower()
            name = (candidate.name or "").lower()
            abbr = pinyin_abbr(candidate.name)
            if (
                normalized_query not in code
                and normalized_query not in name
                and normalized_query not in abbr
            ):
                continue

            item = candidate.to_dict()
            match_type, score = self._score(item, normalized_query)
            if score <= 0:
                continue
            item["match_type"] = match_type
            item["score"] = score - 50  # 略微降权，数据库结果优先
            item["source"] = "akshare_live"
            scored.append(item)

        scored.sort(key=lambda i: (-i["score"], i.get("symbol") or ""))
        return scored[:limit]

    @classmethod
    def _get_live_candidates(cls) -> List[AssetSearchCandidate]:
        """获取实时 A 股候选列表（带缓存）"""
        import time

        now = time.time()
        if (
            cls._live_candidates_cache is not None
            and (now - cls._live_cache_timestamp) < cls._live_cache_ttl
        ):
            return cls._live_candidates_cache

        try:
            from data_layer.crawlers.akshare.base import AkShareAdapter

            adapter = AkShareAdapter()
            stock_list = adapter.market.get_stock_list(limit=None)

            candidates = []
            for stock in stock_list:
                candidates.append(
                    AssetSearchCandidate(
                        canonical_id=stock.symbol,
                        symbol=stock.symbol,
                        raw_code=stock.symbol.split(".")[0],
                        name=stock.name,
                        asset_type="equity",
                        exchange=stock.symbol.split(".")[-1] if "." in stock.symbol else None,
                        market="A-share",
                        industry=stock.industry,
                        source="akshare_live",
                    )
                )

            cls._live_candidates_cache = candidates
            cls._live_cache_timestamp = now
            logger.info(
                "live AKShare candidates cached",
                count=len(candidates),
            )
            return candidates

        except Exception as exc:
            logger.warning("live AKShare candidate fetch failed: %s", exc)
            # 缓存空结果以避免短时间内重复尝试
            cls._live_candidates_cache = []
            cls._live_cache_timestamp = now
            return []

    def _iter_candidates(self) -> Iterable[AssetSearchCandidate]:
        seen: set[str] = set()
        seed_by_symbol = {candidate.symbol: candidate for candidate in self._seed_candidates()}
        for candidate in self._stock_master_candidates():
            if candidate.symbol in seen:
                continue
            seen.add(candidate.symbol)
            yield candidate
        for candidate in self._entity_candidates():
            if candidate.symbol in seen:
                continue
            seed_candidate = seed_by_symbol.get(candidate.symbol)
            if seed_candidate:
                candidate = _merge_candidate_metadata(candidate, seed_candidate)
            seen.add(candidate.symbol)
            yield candidate
        for candidate in seed_by_symbol.values():
            if candidate.symbol in seen:
                continue
            seen.add(candidate.symbol)
            yield candidate

    def _seed_candidates(self) -> Iterable[AssetSearchCandidate]:
        for row in _SEEDED_ASSETS:
            yield AssetSearchCandidate(**row, source="seed")

    def _stock_master_candidates(self) -> Iterable[AssetSearchCandidate]:
        if self.db is None:
            return []
        try:
            from data_layer.repositories.models import StockMasterDB

            rows = self.db.query(StockMasterDB).order_by(StockMasterDB.updated_at.desc()).all()
        except Exception as exc:
            logger.warning("stock_master asset search source unavailable: %s", exc)
            return []

        candidates = []
        for row in rows:
            symbol = normalize_a_share_symbol(row.symbol)
            raw_code = row.raw_code or symbol.split(".")[0]
            exchange = row.exchange or (symbol.split(".")[1] if "." in symbol else None)
            candidates.append(
                AssetSearchCandidate(
                    canonical_id=symbol,
                    symbol=symbol,
                    raw_code=raw_code,
                    name=row.name,
                    asset_type="equity",
                    exchange=exchange,
                    market=row.market,
                    industry=row.industry_level1,
                    source="stock_master",
                )
            )
        return candidates

    def _entity_candidates(self) -> Iterable[AssetSearchCandidate]:
        if self.db is None:
            return []
        try:
            from data_layer.repositories.models import Entity

            rows = (
                self.db.query(Entity)
                .filter(Entity.entity_type.in_(["equity", "stock", "company", "asset", "index"]))
                .order_by(Entity.updated_at.desc())
                .all()
            )
        except Exception as exc:
            logger.warning("entity asset search source unavailable: %s", exc)
            return []

        candidates = []
        for row in rows:
            props = row.properties or {}
            symbol = props.get("symbol") or row.canonical_id
            symbol = normalize_a_share_symbol(symbol)
            raw_code = props.get("raw_code") or symbol.split(".")[0]
            exchange = props.get("exchange") or (symbol.split(".")[1] if "." in symbol else None)
            name = props.get("name_zh") or row.canonical_name
            candidates.append(
                AssetSearchCandidate(
                    canonical_id=symbol,
                    symbol=symbol,
                    raw_code=raw_code,
                    name=name,
                    asset_type=row.entity_type,
                    exchange=exchange,
                    market=props.get("market"),
                    industry=props.get("industry")
                    or props.get("sw_level_1")
                    or props.get("sector"),
                    source="entity",
                )
            )
        return candidates

    def _stock_master_count(self) -> int:
        if self.db is None:
            return 0
        try:
            from data_layer.repositories.models import StockMasterDB

            return self.db.query(StockMasterDB).count()
        except Exception as exc:
            logger.warning("stock_master count unavailable: %s", exc)
            return 0

    def _entity_count(self) -> int:
        if self.db is None:
            return 0
        try:
            from data_layer.repositories.models import Entity

            return (
                self.db.query(Entity)
                .filter(Entity.entity_type.in_(["equity", "stock", "company", "asset", "index"]))
                .count()
            )
        except Exception as exc:
            logger.warning("entity count unavailable: %s", exc)
            return 0

    @staticmethod
    def _score(item: dict, query: str) -> tuple[str, int]:
        symbol = _normalize_query(item.get("symbol"))
        raw_code = _normalize_query(item.get("raw_code"))
        name = _normalize_query(item.get("name"))
        abbr = _normalize_query(item.get("pinyin_abbr"))

        if query in {symbol, raw_code}:
            return "exact_code", 1000
        if symbol.startswith(query) or raw_code.startswith(query):
            return "code_prefix", 900
        if query == abbr:
            return "pinyin_exact", 850
        if abbr.startswith(query):
            return "pinyin_prefix", 800
        if query in name:
            return "name_contains", 700
        if query in symbol or query in raw_code:
            return "code_contains", 600
        if query in abbr:
            return "pinyin_contains", 500
        return "none", 0


def _normalize_query(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "")


def _asset_type_rank(asset_type: Optional[str]) -> int:
    return {"equity": 0, "stock": 0, "company": 1, "index": 2, "asset": 3}.get(asset_type or "", 9)


def _merge_candidate_metadata(
    primary: AssetSearchCandidate,
    fallback: AssetSearchCandidate,
) -> AssetSearchCandidate:
    """用种子元数据补齐稀疏候选；不覆盖 stock_master 这类主数据源。"""
    source = primary.source
    if fallback.source not in source.split("+"):
        source = f"{source}+{fallback.source}"
    return replace(
        primary,
        raw_code=primary.raw_code or fallback.raw_code,
        name=primary.name or fallback.name,
        exchange=primary.exchange or fallback.exchange,
        market=_prefer_market(primary.market, fallback.market),
        industry=primary.industry or fallback.industry,
        source=source,
    )


def _prefer_market(primary: Optional[str], fallback: Optional[str]) -> Optional[str]:
    if not primary:
        return fallback
    if primary.lower() == "global" and fallback:
        return fallback
    return primary
