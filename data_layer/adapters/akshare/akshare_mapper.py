"""AkShare 数据映射器 - AkShare 原始数据 → AssetAnalysisSnapshot"""
import hashlib
import json
from datetime import datetime
from typing import Any

from core.contracts.assets import AssetAnalysisSnapshot
from core.observability import get_logger

logger = get_logger(__name__)


class AkShareMapper:
    """AkShare 原始数据 → AssetAnalysisSnapshot 映射器"""

    def map_market_data(
        self, code: str, raw_data: list[dict[str, Any]], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射行情数据 (ak.stock_zh_a_hist())"""
        snapshots = []
        for item in raw_data:
            price_volume = {
                "open": item.get("开盘"),
                "high": item.get("最高"),
                "low": item.get("最低"),
                "close": item.get("收盘"),
                "volume": item.get("成交量"),
                "turnover": item.get("换手率"),
                "amount": item.get("成交额"),
                "change_pct": item.get("涨跌幅"),
                "date": item.get("日期"),
            }
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "market_data"),
                as_of=as_of,
                price_volume=price_volume,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_financials(
        self, code: str, raw_data: list[dict[str, Any]], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射财务数据"""
        snapshots = []
        for item in raw_data:
            financial = {
                "eps": item.get("每股收益"),
                "roe": item.get("净资产收益率"),
                "net_profit": item.get("净利润"),
                "revenue": item.get("营业收入"),
                "gross_margin": item.get("毛利率"),
                "debt_ratio": item.get("资产负债率"),
                "current_ratio": item.get("流动比率"),
                "report_date": item.get("报告期"),
            }
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "financials"),
                as_of=as_of,
                financial=financial,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_fund_flow(
        self, code: str, raw_data: list[dict[str, Any]], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射资金流数据"""
        snapshots = []
        for item in raw_data:
            fund_flow = {
                "main_net_inflow": item.get("主力净流入"),
                "super_large_net_inflow": item.get("超大单净流入"),
                "large_net_inflow": item.get("大单净流入"),
                "medium_net_inflow": item.get("中单净流入"),
                "small_net_inflow": item.get("小单净流入"),
                "northbound_net_inflow": item.get("北向资金净流入"),
                "date": item.get("日期"),
            }
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "fund_flow"),
                as_of=as_of,
                fund_flow=fund_flow,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_valuation(
        self, code: str, raw_data: dict[str, Any], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射估值数据"""
        valuation = {
            "pe_ttm": raw_data.get("pe_ttm"),
            "pe_ttm_percentile": raw_data.get("pe_ttm_percentile"),
            "pb": raw_data.get("pb"),
            "pb_percentile": raw_data.get("pb_percentile"),
            "ps": raw_data.get("ps"),
            "ps_percentile": raw_data.get("ps_percentile"),
        }
        snapshot = AssetAnalysisSnapshot(
            canonical_id=self._generate_canonical_id(code, as_of, "valuation"),
            as_of=as_of,
            valuation=valuation,
            evidence_refs=[self._hash_data(raw_data)],
        )
        return [snapshot]

    def map_technical_indicators(
        self, code: str, raw_data: dict[str, Any], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射技术指标"""
        technical = {
            "trend": raw_data.get("trend"),
            "momentum": raw_data.get("momentum"),
            "volatility": raw_data.get("volatility"),
            "volume": raw_data.get("volume"),
            "all_indicators": raw_data.get("all_indicators"),
        }
        snapshot = AssetAnalysisSnapshot(
            canonical_id=self._generate_canonical_id(code, as_of, "technical"),
            as_of=as_of,
            technical=technical,
            evidence_refs=[self._hash_data(raw_data)],
        )
        return [snapshot]

    def map_sentiment(
        self, code: str | None, raw_data: dict[str, Any], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射情绪数据"""
        sentiment = {
            "overall_score": raw_data.get("overall_score"),
            "dimensions": raw_data.get("dimensions"),
            "signals": raw_data.get("signals"),
        }
        snapshot = AssetAnalysisSnapshot(
            canonical_id=self._generate_canonical_id(code or "market", as_of, "sentiment"),
            as_of=as_of,
            sentiment=sentiment,
            evidence_refs=[self._hash_data(raw_data)],
        )
        return [snapshot]

    def map_industry(
        self, code: str, raw_data: dict[str, Any], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射行业分类数据"""
        industry = {
            "sw_industry": raw_data.get("sw_industry"),
            "csrc_industry": raw_data.get("csrc_industry"),
            "concept_boards": raw_data.get("concept_boards"),
            "sector": raw_data.get("sector"),
        }
        snapshot = AssetAnalysisSnapshot(
            canonical_id=self._generate_canonical_id(code, as_of, "industry"),
            as_of=as_of,
            industry=industry,
            evidence_refs=[self._hash_data(raw_data)],
        )
        return [snapshot]

    def map_macro(self, raw_data: dict[str, Any], as_of: datetime) -> list[AssetAnalysisSnapshot]:
        """映射宏观数据"""
        macro_exposure = {
            "cpi_yoy": raw_data.get("cpi_yoy"),
            "ppi_yoy": raw_data.get("ppi_yoy"),
            "m2_yoy": raw_data.get("m2_yoy"),
            "pmi": raw_data.get("pmi"),
            "lpr": raw_data.get("lpr"),
            "gdp": raw_data.get("gdp"),
            "social_financing": raw_data.get("social_financing"),
        }
        snapshot = AssetAnalysisSnapshot(
            canonical_id=self._generate_canonical_id("macro", as_of, "macro"),
            as_of=as_of,
            macro_exposure=macro_exposure,
            evidence_refs=[self._hash_data(raw_data)],
        )
        return [snapshot]

    def _generate_canonical_id(self, code: str, as_of: datetime, domain: str) -> str:
        """生成 canonical_id"""
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:8]
        return f"akshare:{code}:{as_of.strftime('%Y%m%d')}:{domain_hash}"

    def _hash_data(self, data: dict | list) -> str:
        """生成数据指纹"""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
