"""资产候选搜索索引服务。

为资产分析页提供代码、名称、中文简拼候选匹配，不依赖第三方拼音包。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any, Iterable, List, Optional, cast

from sqlalchemy.orm import Session

from core.observability import get_logger
from data_layer.normalizers.symbol import normalize_a_share_symbol

logger = get_logger(__name__)

# ── ETF 缓存 ─────────────────────────────────────────────────────────
_FUND_CACHE: list[dict[str, Any]] | None = None
_FUND_CACHE_TIME: float = 0.0
_FUND_CACHE_TTL: float = 86400.0  # 24h


def _build_fund_cache() -> list[dict[str, Any]]:
    """通过 AKShare fund_etf_spot_em() 获取全量 ETF 列表并缓存。

    返回 list[dict]，每项包含 code, name, market 三个 key。
    首次调用约 20s，后续 24h 内命中模块级缓存。
    """
    global _FUND_CACHE, _FUND_CACHE_TIME
    now = time.time()
    if _FUND_CACHE is not None and (now - _FUND_CACHE_TIME) < _FUND_CACHE_TTL:
        return _FUND_CACHE

    try:
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            logger.warning("fund_etf_spot_em returned empty DataFrame")
            _FUND_CACHE = []
            _FUND_CACHE_TIME = now
            return _FUND_CACHE

        funds: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            code_val = str(row.get("代码", "")).strip()
            name_val = str(row.get("名称", "")).strip()
            if not code_val or not name_val:
                continue
            # 推断交易所后缀
            suffix = _etf_suffix(code_val)
            funds.append(
                {
                    "raw_code": code_val,
                    "symbol": f"{code_val}.{suffix}",
                    "name": name_val,
                    "exchange": suffix,
                    "market": "A-share",
                }
            )

        _FUND_CACHE = funds
        _FUND_CACHE_TIME = now
        logger.info("ETF cache built", extra={"count": len(funds)})
        return funds
    except Exception as exc:
        logger.warning("Failed to build ETF cache: %s", exc)
        _FUND_CACHE = []
        _FUND_CACHE_TIME = now
        return _FUND_CACHE


def _etf_suffix(raw_code: str) -> str:
    """根据 ETF 原始代码推断交易所后缀。

    - 159xxx → SZ（深交所 ETF）
    - 51xxxx → SH（上交所 ETF）
    - 58xxxx → SH（上交所 ETF）
    - 其他按首数字：5/6→SH，0/1/2/3→SZ
    """
    if not raw_code:
        return "SH"
    if raw_code.startswith("159"):
        return "SZ"
    if raw_code.startswith("51"):
        return "SH"
    if raw_code.startswith("58"):
        return "SH"
    if raw_code.startswith("16"):
        return "SZ"
    first_digit = raw_code[0]
    if first_digit in ("5", "6"):
        return "SH"
    return "SZ"


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
        fund_count = self._fund_count()
        return {
            "stock_master_count": stock_master_count,
            "entity_count": entity_count,
            "fund_etf_count": fund_count,
            "seed_count": len(_SEEDED_ASSETS),
            "stock_master_empty": stock_master_count == 0,
            "using_seed_fallback": stock_master_count == 0,
        }

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
        for candidate in self._fund_candidates():
            if candidate.symbol in seen:
                continue
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

    def _fund_candidates(self) -> Iterable[AssetSearchCandidate]:
        """从 AKShare fund_etf_spot_em 缓存中生成 ETF 候选。

        首次调用会触发 AKShare 拉取（约 20s），后续命中 24h 缓存。
        AKShare 不可用时返回空列表，不阻塞其他候选源。
        """
        try:
            funds = _build_fund_cache()
        except Exception as exc:
            logger.warning("fund ETF candidate source unavailable: %s", exc)
            return []

        for fund in funds:
            yield AssetSearchCandidate(
                canonical_id=fund["symbol"],
                symbol=fund["symbol"],
                raw_code=fund.get("raw_code", ""),
                name=fund["name"],
                asset_type="etf",
                exchange=fund.get("exchange"),
                market=fund.get("market"),
                source="fund_etf",
            )

    def _fund_count(self) -> int:
        """ETF 缓存候选数（不触发远程拉取）。"""
        return len(_FUND_CACHE) if _FUND_CACHE is not None else 0

    def _stock_master_count(self) -> int:
        if self.db is None:
            return 0
        try:
            from data_layer.repositories.models import StockMasterDB

            return cast(int, self.db.query(StockMasterDB).count())
        except Exception as exc:
            logger.warning("stock_master count unavailable: %s", exc)
            return 0

    def _entity_count(self) -> int:
        if self.db is None:
            return 0
        try:
            from data_layer.repositories.models import Entity

            return cast(
                int,
                (
                    self.db.query(Entity)
                    .filter(
                        Entity.entity_type.in_(["equity", "stock", "company", "asset", "index"])
                    )
                    .count()
                ),
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
