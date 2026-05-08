"""资产分析服务"""
from datetime import datetime
from typing import Optional

from core.contracts import AssetAnalysisSnapshot
from core.interfaces import AssetSnapshotRepository, EntityRepository
from core.observability import get_logger
from data_layer.adapters import IFinDAdapter, LocalDataAdapter, AKShareAdapter

logger = get_logger(__name__)


class AssetAnalysisService:
    """资产分析服务
    
    Data source fallback chain:
    1. iFinD (if available) -> highest quality
    2. AKShare (if available) -> open source fallback for macOS
    3. Local -> cached data
    4. Mock -> last resort
    """

    def __init__(
        self,
        asset_snapshot_repo: AssetSnapshotRepository,
        entity_repo: Optional[EntityRepository] = None,
        ifind_adapter: Optional[IFinDAdapter] = None,
        local_adapter: Optional[LocalDataAdapter] = None,
        akshare_adapter: Optional[AKShareAdapter] = None,
        use_mock: bool = False,
    ):
        self.asset_snapshot_repo = asset_snapshot_repo
        self.entity_repo = entity_repo
        self.ifind_adapter = ifind_adapter
        self.local_adapter = local_adapter or LocalDataAdapter()
        self.akshare_adapter = akshare_adapter or AKShareAdapter()
        self._use_mock = use_mock

    def generate_snapshot(
        self,
        canonical_id: str,
        as_of: Optional[datetime] = None,
        use_mock: Optional[bool] = None,
        source: str = "local",
    ) -> AssetAnalysisSnapshot:
        """
        生成资产分析快照

        Args:
            canonical_id: 资产代码
            as_of: 快照时间
            use_mock: 是否使用模拟数据（兼容旧接口）；None 时使用构造函数设置
            source: 数据源: "mock", "local", "ifind"
        """
        if as_of is None:
            as_of = datetime.utcnow()

        # 合并实例级和调用级 use_mock
        effective_use_mock = use_mock if use_mock is not None else self._use_mock

        logger.info(
            "generating asset snapshot",
            canonical_id=canonical_id,
            as_of=as_of,
            source=source,
        )

        # 自动降级：iFinD → AKShare → Local → Mock
        if effective_use_mock or source == "mock":
            snapshot = self._generate_mock_snapshot(canonical_id, as_of)
        elif source == "akshare" and self.akshare_adapter.is_available():
            logger.info("Using AKShare open source data")
            snapshot = self._fetch_from_akshare(canonical_id, as_of)
        elif source == "local":
            snapshot = self._fetch_from_local(canonical_id, as_of)
        elif source == "ifind" and self.ifind_adapter:
            try:
                snapshot = self._fetch_from_ifind(canonical_id, as_of)
            except Exception as e:
                logger.warning(f"iFinD fetch failed, falling back to AKShare: {e}")
                if self.akshare_adapter.is_available():
                    snapshot = self._fetch_from_akshare(canonical_id, as_of)
                else:
                    snapshot = self._fetch_from_local(canonical_id, as_of)
        elif source == "auto":
            # 自动降级链
            success = False
            if self.ifind_adapter and self.ifind_adapter.is_available():
                try:
                    snapshot = self._fetch_from_ifind(canonical_id, as_of)
                    success = True
                except Exception as e:
                    logger.warning(f"iFinD failed: {e}")
            if not success and self.akshare_adapter.is_available():
                logger.info("Auto fallback: using AKShare open source data (iFinD unavailable)")
                snapshot = self._fetch_from_akshare(canonical_id, as_of)
                success = True
            if not success:
                logger.info("Auto fallback: using local cached data")
                snapshot = self._fetch_from_local(canonical_id, as_of)
                success = True
            if not success:
                logger.warning("All data sources failed, falling back to mock")
                snapshot = self._generate_mock_snapshot(canonical_id, as_of)
        elif self.akshare_adapter.is_available():
            logger.info("Using AKShare open source data (iFinD not available on macOS)")
            snapshot = self._fetch_from_akshare(canonical_id, as_of)
        elif source == "local":
            snapshot = self._fetch_from_local(canonical_id, as_of)
        else:
            logger.warning("No data source available, falling back to mock data")
            snapshot = self._generate_mock_snapshot(canonical_id, as_of)

        # 保存快照
        saved_snapshot = self.asset_snapshot_repo.save(snapshot)
        logger.info("asset snapshot saved", canonical_id=canonical_id)

        return saved_snapshot

    def _generate_mock_snapshot(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """生成模拟的资产分析快照"""
        return AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            financial={
                "revenue": {"ttm": 15000000000, "qoq": 0.08, "yoy": 0.15},
                "net_profit": {"ttm": 3200000000, "qoq": 0.12, "yoy": 0.22},
                "eps": {"ttm": 2.35, "qoq": 0.10, "yoy": 0.18},
                "roe": {"ttm": 0.185, "qoq": 0.005, "yoy": 0.02},
                "debt_ratio": 0.45,
            },
            fund_flow={
                "main_net_inflow": 250000000,
                "retail_net_inflow": 80000000,
                "institutional_holding": 0.62,
                "northbound_holding": 0.085,
                "pledge_ratio": 0.12,
            },
            price_volume={
                "close_price": 58.5,
                "ma5": 57.2,
                "ma20": 55.8,
                "ma60": 54.3,
                "volume_ma5": 125000000,
                "volume_ma20": 98000000,
                "high_52w": 72.3,
                "low_52w": 38.6,
                "rsi14": 62.5,
            },
            valuation={
                "pe_ttm": 24.9,
                "pe_lyr": 23.5,
                "pb": 3.8,
                "ps": 6.8,
                "ev_ebitda": 18.2,
                "dividend_yield": 0.021,
                "historical_percentile_pe": 0.65,
            },
            shareholder={
                "controlling_shareholder": "某某集团有限公司",
                "controlling_ratio": 0.352,
                "top10_holding_ratio": 0.585,
                "management_holding": 0.012,
                "pledge_notes": ["第一大股东质押比例：45%", "无平仓风险预警"],
            },
            industry={
                "sw_level1": "有色金属",
                "sw_level2": "贵金属",
                "sw_level3": "黄金",
                "industry_pe": 32.5,
                "industry_pb": 4.2,
                "sector_rank": 8,
                "total_sectors": 31,
            },
            event_impact=[
                "2026-04-28：发布一季报，净利润同比增长28%，超市场预期",
                "2026-04-15：机构调研纪要显示公司产能扩张进展良好",
                "2026-03-20：大股东增持0.5%股份，彰显信心",
            ],
            macro_exposure={
                "usd_cny_beta": 0.35,
                "gold_price_beta": 0.85,
                "interest_rate_sensitivity": -0.25,
                "crude_price_beta": 0.15,
            },
            evidence_refs=[
                "doc_20260428_q1_report",
                "doc_20260415_research_notes",
                "doc_20260320_announcement",
            ],
        )

    def _fetch_from_local(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """从本地数据文件读取"""
        data = self.local_adapter.get_asset_data(canonical_id)
        if data:
            logger.info("loaded data from local file", canonical_id=canonical_id)
            return AssetAnalysisSnapshot(canonical_id=canonical_id, as_of=as_of, **data)
        else:
            logger.warning("local data not found, falling back to mock", canonical_id=canonical_id)
            return self._generate_mock_snapshot(canonical_id, as_of)

    def _fetch_from_ifind(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """从 iFinD 获取真实数据"""
        # TODO: implement full fetching
        logger.warning("iFinD fetch not fully implemented", canonical_id=canonical_id)
        return self._generate_mock_snapshot(canonical_id, as_of)

    def _fetch_from_akshare(self, canonical_id: str, as_of: datetime) -> AssetAnalysisSnapshot:
        """从 AKShare 获取开源真实数据"""
        import akshare as ak
        import asyncio
        # 获取近一年行情
        end_date = as_of.strftime('%Y-%m-%d')
        start_date = (as_of.replace(year=as_of.year - 1)).strftime('%Y-%m-%d')
        
        quotes = asyncio.run(self.akshare_adapter.fetch_stock_quotes(canonical_id, start_date, end_date))
        financial = asyncio.run(self.akshare_adapter.fetch_financial_report(canonical_id))
        
        # 获取实时估值数据
        pe_ttm = None
        pb = None
        try:
            ak_code = canonical_id.split(".")[0]
            if ak_code:
                # 从东方财富接口获取实时估值
                realtime_df = ak.stock_zh_a_spot_em()
                row = realtime_df[realtime_df['代码'] == ak_code]
                if not row.empty:
                    pe_ttm = float(row.iloc[0]['PE-TTM'])
                    pb = float(row.iloc[0]['PB'])
        except Exception as e:
            # fallback: 手动计算 PE
            if quotes and financial and financial.get('eps'):
                last_quote = quotes[-1]
                pe_ttm = last_quote['close'] / financial['eps']
            logger.warning(f"AKShare failed to fetch realtime valuation: {e}, fallback manual")
        
        last_quote = quotes[-1] if quotes else None
        snapshot = AssetAnalysisSnapshot(
            canonical_id=canonical_id,
            as_of=as_of,
            financial={
                'revenue': {'ttm': financial.get('revenue', None) if financial else None},
                'net_profit': {'ttm': financial.get('net_profit', None) if financial else None},
                'eps': {'ttm': financial.get('eps', None) if financial else None},
                'roe': {'ttm': financial.get('roe', None) if financial else None},
                'debt_ratio': financial.get('debt_ratio', None) if financial else None,
            },
            fund_flow={},
            price_volume={
                'close_price': last_quote['close'] if last_quote else None,
                'high_52w': max(q['high'] for q in quotes) if quotes else None,
                'low_52w': min(q['low'] for q in quotes) if quotes else None,
            },
            valuation={
                'pe_ttm': pe_ttm,
                'pb': pb,
            },
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )
        
        logger.info("Fetched real data from AKShare", canonical_id=canonical_id, quotes=len(quotes))
        return snapshot

    def list_available_assets(self) -> list[str]:
        """列出所有可用的资产代码（来自本地数据）"""
        return self.local_adapter.list_available_assets()

    def get_latest_snapshot(self, canonical_id: str) -> Optional[AssetAnalysisSnapshot]:
        """获取最新的资产分析快照"""
        return self.asset_snapshot_repo.get_latest_by_canonical_id(canonical_id)
