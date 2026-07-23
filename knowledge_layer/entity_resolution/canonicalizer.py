"""
Canonical ID 生成器
"""

import hashlib
import re
from enum import Enum
from typing import Optional

from core.observability import get_logger
from knowledge_layer.entity_resolution.types import EntityType

logger = get_logger(__name__)


class Market(Enum):
    """市场枚举"""

    CN = "cn"  # 中国内地
    HK = "hk"  # 香港
    US = "us"  # 美国
    UK = "uk"  # 英国
    JP = "jp"  # 日本
    EU = "eu"  # 欧盟
    GLOBAL = "global"  # 全球


class Venue(Enum):
    """交易场所枚举"""

    SSE = "sse"  # 上交所
    SZSE = "szse"  # 深交所
    HKEX = "hkex"  # 港交所
    NYSE = "nyse"  # 纽交所
    NASDAQ = "nasdaq"  # 纳斯达克
    CME = "cme"  # 芝加哥商业交易所
    LME = "lme"  # 伦敦金属交易所
    SHFE = "shfe"  # 上海期货交易所
    DCE = "dce"  # 大连商品交易所
    CZCE = "czce"  # 郑州商品交易所
    OTHER = "other"  # 其他


class Canonicalizer:
    """Canonical ID 生成器"""

    def __init__(self):
        # 股票代码模式
        self._stock_patterns = {
            # A股
            "sse": [
                re.compile(r"^(\d{6})\.SH$", re.IGNORECASE),
                re.compile(r"^(\d{6})$"),
            ],
            "szse": [
                re.compile(r"^(\d{6})\.SZ$", re.IGNORECASE),
            ],
            # 港股
            "hkex": [
                re.compile(r"^(\d{5})$"),
                re.compile(r"^(\d{4})$"),
            ],
            # 美股
            "nyse": [],
            "nasdaq": [],
        }

        # A股市场前缀映射
        self._a_sh_prefix = {
            "600": "sse",
            "601": "sse",
            "603": "sse",
            "605": "sse",
            "688": "sse",
            "689": "sse",
            "000": "szse",
            "001": "szse",
            "002": "szse",
            "003": "szse",
            "300": "szse",
            "301": "szse",
            "302": "szse",
            "8": "bjse",
        }

    def generate_id(
        self,
        symbol: str,
        entity_type: EntityType,
        venue: Optional[Venue] = None,
        market: Optional[Market] = None,
    ) -> str:
        """
        生成 Canonical ID

        Args:
            symbol: 代码/符号
            entity_type: 实体类型
            venue: 交易场所
            market: 市场

        Returns:
            canonical_id
        """
        # 根据实体类型选择不同的生成策略
        if entity_type == EntityType.COMPANY:
            return self._generate_company_id(symbol, venue, market)
        elif entity_type in [EntityType.INDEX, EntityType.CONCEPT]:
            return self._generate_concept_id(symbol, entity_type)
        elif entity_type == EntityType.COMMODITY:
            return self._generate_commodity_id(symbol, venue)
        elif entity_type == EntityType.CURRENCY:
            return self._generate_currency_id(symbol)
        else:
            return self._generate_generic_id(symbol, entity_type)

    def _generate_company_id(
        self,
        symbol: str,
        venue: Optional[Venue] = None,
        market: Optional[Market] = None,
    ) -> str:
        """生成公司/股票的 Canonical ID"""
        symbol = symbol.strip().upper()

        # 如果没有提供 venue，尝试从 symbol 推断
        if venue is None:
            venue = self._infer_venue(symbol)

        # 如果没有提供 market，从 venue 推断
        if market is None:
            market = self._venue_to_market(venue)

        # 标准化 symbol
        normalized_symbol = self._normalize_symbol(symbol, venue)

        return f"equity:{market.value}:{venue.value}:{normalized_symbol}"

    def _generate_concept_id(self, symbol: str, entity_type: EntityType) -> str:
        """生成概念/指数的 Canonical ID"""
        # 使用哈希化名称
        clean_name = self._clean_name(symbol)
        hash_suffix = self._hash_string(clean_name)[:8]
        return f"{entity_type.value}:global:other:{clean_name}_{hash_suffix}"

    def _generate_commodity_id(self, symbol: str, venue: Optional[Venue]) -> str:
        """生成商品的 Canonical ID"""
        if venue is None:
            venue = Venue.OTHER
        market = self._venue_to_market(venue)
        normalized_symbol = symbol.strip().upper()
        return f"spot_commodity:{market.value}:{venue.value}:{normalized_symbol}"

    def _generate_currency_id(self, symbol: str) -> str:
        """生成货币的 Canonical ID"""
        normalized_symbol = symbol.strip().upper()
        return f"fx:global:other:{normalized_symbol}"

    def _generate_generic_id(self, symbol: str, entity_type: EntityType) -> str:
        """生成通用类型的 Canonical ID"""
        clean_name = self._clean_name(symbol)
        hash_suffix = self._hash_string(clean_name)[:8]
        return f"{entity_type.value}:global:other:{clean_name}_{hash_suffix}"

    def _infer_venue(self, symbol: str) -> Venue:
        """从 symbol 推断交易场所"""
        symbol = symbol.upper()

        # 检查 .SH/.SZ 后缀
        if symbol.endswith(".SH"):
            return Venue.SSE
        if symbol.endswith(".SZ"):
            return Venue.SZSE
        if symbol.endswith(".HK"):
            return Venue.HKEX

        # 检查 A股代码前缀
        if len(symbol) == 6 and symbol.isdigit():
            prefix = symbol[:3]
            if prefix in self._a_sh_prefix:
                venue_code = self._a_sh_prefix[prefix]
                return Venue(venue_code)

        # 默认
        return Venue.OTHER

    def _venue_to_market(self, venue: Venue) -> Market:
        """将 Venue 映射到 Market"""
        venue_market_map = {
            Venue.SSE: Market.CN,
            Venue.SZSE: Market.CN,
            Venue.HKEX: Market.HK,
            Venue.NYSE: Market.US,
            Venue.NASDAQ: Market.US,
            Venue.SHFE: Market.CN,
            Venue.DCE: Market.CN,
            Venue.CZCE: Market.CN,
            Venue.CME: Market.US,
            Venue.LME: Market.UK,
        }
        return venue_market_map.get(venue, Market.GLOBAL)

    def _normalize_symbol(self, symbol: str, venue: Venue) -> str:
        """标准化 symbol"""
        symbol = symbol.upper().strip()

        # 移除后缀
        if symbol.endswith((".SH", ".SZ", ".HK")):
            symbol = symbol[:-3]

        # A股6位数字，港股5位
        if venue in [Venue.SSE, Venue.SZSE]:
            if len(symbol) == 6 and symbol.isdigit():
                return symbol
        elif venue == Venue.HKEX:
            if len(symbol) in [4, 5] and symbol.isdigit():
                return symbol.zfill(5)

        return symbol

    def _clean_name(self, name: str) -> str:
        """清理名称用于ID生成"""
        # 移除特殊字符，转为小写
        cleaned = re.sub(r"[^\w一-鿿]", "", name)
        cleaned = cleaned.lower()
        # 移除空格
        cleaned = re.sub(r"\s+", "", cleaned)
        return cleaned or "unknown"

    def _hash_string(self, s: str) -> str:
        """生成字符串的哈希值"""
        return hashlib.md5(s.encode("utf-8")).hexdigest()
