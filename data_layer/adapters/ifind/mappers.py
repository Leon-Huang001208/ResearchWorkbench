"""iFinD 数据映射器"""
import hashlib
import logging
from datetime import datetime

from core.contracts.assets import AssetAnalysisSnapshot

logger = logging.getLogger(__name__)


class IFinDMapper:
    """iFinD 原始数据 → AssetAnalysisSnapshot 映射器"""

    def map_quotes(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射行情数据"""
        snapshots = []
        for item in raw_data:
            price_volume = {
                "open": item.get("ths_open_stock"),
                "high": item.get("ths_high_stock"),
                "low": item.get("ths_low_stock"),
                "close": item.get("ths_close_stock"),
                "volume": item.get("ths_vol_stock"),
                "turnover": item.get("ths_turnover_stock"),
            }
            # 计算均线（示例）
            # 这里假设 raw_data 是按日期排序的，实际实现时需要更复杂的逻辑
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "quotes"),
                as_of=as_of,
                price_volume=price_volume,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_financial(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射财务数据"""
        snapshots = []
        for item in raw_data:
            financial = {
                "eps": item.get("ths_eps_basic_stock"),
                "roe": item.get("ths_roe_stock"),
                "net_profit": item.get("ths_net_profit_stock"),
                "revenue": item.get("ths_revenue_stock"),
                "gross_margin": item.get("ths_gross_margin_stock"),
                "debt_ratio": item.get("ths_debt_ratio_stock"),
                "current_ratio": item.get("ths_current_ratio_stock"),
            }
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "financial"),
                as_of=as_of,
                financial=financial,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_fund_flow(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射资金流向数据"""
        snapshots = []
        for item in raw_data:
            fund_flow = {
                "main_net_inflow": item.get("main_net_inflow"),
                "super_large_net_inflow": item.get("super_large_net_inflow"),
                "large_net_inflow": item.get("large_net_inflow"),
                "medium_net_inflow": item.get("medium_net_inflow"),
                "small_net_inflow": item.get("small_net_inflow"),
            }
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "fund_flow"),
                as_of=as_of,
                fund_flow=fund_flow,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_industry(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射行业分类数据"""
        snapshots = []
        for item in raw_data:
            industry = {
                "sw_industry": item.get("ths_industry_stock"),
                "csrc_industry": item.get("csrc_industry"),
                "concept_boards": item.get("concept_boards"),
                "industry_rank": item.get("industry_rank"),
            }
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "industry"),
                as_of=as_of,
                industry=industry,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_macro(
        self, indicators: list[str], raw_data: list[dict], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射宏观经济数据"""
        snapshots = []
        for item in raw_data:
            macro_exposure = {
                "cpi_yoy": item.get("cpi_yoy"),
                "ppi_yoy": item.get("ppi_yoy"),
                "m2_yoy": item.get("m2_yoy"),
                "pmi": item.get("pmi"),
                "lpr": item.get("lpr"),
                "social_financing": item.get("social_financing"),
                "industry_pmi": item.get("industry_pmi"),
            }
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id("macro", as_of, "macro"),
                as_of=as_of,
                macro_exposure=macro_exposure,
                evidence_refs=[self._hash_data(item)],
            )
            snapshots.append(snapshot)
        return snapshots

    def map_research_report(
        self, code: str, raw_data: list[dict], as_of: datetime
    ) -> list[AssetAnalysisSnapshot]:
        """映射研报数据"""
        snapshots = []
        event_impacts = []
        for item in raw_data:
            title = item.get("title", "")
            rating = item.get("rating", "")
            event_impacts.append(f"研报: {title} | 评级: {rating}")
        if event_impacts:
            snapshot = AssetAnalysisSnapshot(
                canonical_id=self._generate_canonical_id(code, as_of, "research"),
                as_of=as_of,
                event_impact=event_impacts,
                evidence_refs=[self._hash_data(raw_data)],
            )
            snapshots.append(snapshot)
        return snapshots

    def _generate_canonical_id(self, code: str, as_of: datetime, domain: str) -> str:
        """生成 canonical_id"""
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:8]
        return f"ifind:{code}:{as_of.strftime('%Y%m%d')}:{domain_hash}"

    def _hash_data(self, data: dict | list) -> str:
        """生成数据指纹"""
        import json
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
