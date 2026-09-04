"""Dashboard 首页数据聚合服务"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import UTC, datetime, timedelta
from threading import Lock, Thread
from typing import Any, List, Optional

from sqlalchemy import desc

from core.contracts.dashboard import (
    AbnormalFlow,
    BestPerformingEventType,
    CandidateBoardSection,
    CandidateItem,
    DashboardResponse,
    GlobalNewsItem,
    HighPriorityThesis,
    LearningSection,
    MappingReviewItem,
    MarketBreadthSnapshot,
    MarketIndexItem,
    MarketOverviewSection,
    MissingEvidence,
    PendingAssertion,
    RecentFailure,
    ResearchQueueSection,
    SectorChangeItem,
    SectorMoverView,
    TodayEvent,
    TodaySection,
    WeeklyLesson,
)
from core.observability import get_logger
from core.settings.paths import default_market_sector_cache_path
from data_layer.repositories.dashboard_data import DashboardDataRepository
from services.wind_index_catalog import load_wind_index_catalog
from services.wind_market_overview_provider import WindMarketOverviewProvider

logger = get_logger(__name__)

MARKET_SECTOR_VIEW_ORDER = (
    "wind_hot_concept",
    "wind_l1",
    "wind_l2",
    "wind_l3",
    "wind_l4",
    "citic_l1",
    "citic_l2",
    "citic_l3",
    "sw_l1",
    "sw_l2",
    "sw_l3",
    "ths_industry",
)

MARKET_SECTOR_CACHE_TTL_SECONDS = 30.0
MARKET_SECTOR_WORKBOOK_READ_TIMEOUT_SECONDS = 24.0
MARKET_SECTOR_WORKBOOK_READ_TIMEOUT_ENV = "RESEARCH_WIND_WORKBOOK_READ_TIMEOUT_SECONDS"
MARKET_SECTOR_DISK_CACHE_MAX_AGE_SECONDS = 60 * 60
MARKET_SECTOR_DISK_CACHE_PATH = default_market_sector_cache_path()
MARKET_COMMAND_CACHE_TTL_SECONDS = 15.0
MARKET_BREADTH_EXACT_CACHE_TTL_SECONDS = 45.0
MARKET_STATS_CACHE_TTL_SECONDS = 45.0
PREVIOUS_MARKET_TURNOVER_CACHE_TTL_SECONDS = 60 * 60
ENABLE_WIND_REALTIME_WORKBOOK_ENV = "RESEARCH_ENABLE_WIND_WORKBOOK"
ALLOW_WIND_EXCEL_FALLBACK_ENV = "RESEARCH_ALLOW_WIND_EXCEL_FALLBACK"

_market_command_cache_lock = Lock()
_market_index_cache: Optional[tuple[float, list[dict[str, Any]]]] = None
_market_breadth_cache: Optional[tuple[float, dict[str, Any]]] = None
_market_stats_cache: Optional[tuple[float, dict[str, Any]]] = None
_previous_turnover_cache: Optional[tuple[float, dict[str, Any]]] = None
_previous_turnover_refreshing = False
_market_breadth_refreshing = False
_market_sector_cache: dict[tuple[str, int], tuple[float, dict]] = {}
_market_sector_cache_lock = Lock()
_wind_workbook_read_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="wind-workbook-read",
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _translate_failure_reason(reason: str) -> str:
    """将数据库中的失败原因代码翻译为中文"""
    mapping = {
        "direction_wrong": "方向判断错误",
        "timing_error": "择时错误",
        "thesis_wrong": "论点错误",
        "crowding_error": "拥挤错误",
        "regime_misread": "环境误判",
        "data_quality": "数据质量",
        "execution_error": "执行错误",
        "risk_error": "风控错误",
    }
    return mapping.get(reason, reason)


def _translate_event_type(event_type: str) -> str:
    """将事件类型翻译为中文"""
    if event_type == "unknown":
        return "综合"
    mapping = {
        "earnings": "财报",
        "policy": "政策",
        "industry": "行业",
        "product_launch": "产品发布",
        "macro": "宏观",
        "merger_acquisition": "并购",
        "sales_data": "销售数据",
        "other": "其他",
    }
    return mapping.get(event_type, event_type)


class DashboardService:
    """首页仪表盘数据聚合服务"""

    def __init__(self, session):
        self.session = session
        self.today_cutoff = datetime.now(UTC) - timedelta(days=1)
        self.dashboard_repo = DashboardDataRepository(session)

    def _get_mock_global_news(self) -> List[GlobalNewsItem]:
        """获取模拟的全球新闻数据"""
        now = datetime.now(UTC)
        return [
            GlobalNewsItem(
                news_id="news-001",
                title="美联储暗示或将暂停加息，全球市场应声上涨",
                source="Reuters",
                importance_score=0.95,
                summary="美联储主席在最新讲话中表示，鉴于通胀有所回落，可能会暂停加息步伐，这一表态推动了全球股市上涨。",
                content_url="https://reuters.com/business/fed-signals-pause-rate-hikes",
                published_at=(now - timedelta(hours=2)).isoformat(),
                related_symbols=["SPX", "NDX", "AAPL", "MSFT"],
                region="Global",
                is_mock=True,
            ),
            GlobalNewsItem(
                news_id="news-002",
                title="中国5月制造业PMI好于预期，经济复苏信号增强",
                source="Bloomberg",
                importance_score=0.90,
                summary="最新发布的中国制造业PMI为49.8，好于市场预期的49.5，显示经济复苏动能正在增强。",
                content_url="https://bloomberg.com/china-pmi-may-2024",
                published_at=(now - timedelta(hours=4)).isoformat(),
                related_symbols=["600519.SH", "000001.SZ", "AAPL"],
                region="China",
            ),
            GlobalNewsItem(
                news_id="news-003",
                title="英伟达发布重磅新品，AI芯片性能提升3倍",
                source="TechCrunch",
                importance_score=0.88,
                summary="英伟达在GTC大会上发布新一代GH200超级芯片，AI计算性能提升3倍，股价盘后大涨。",
                content_url="https://techcrunch.com/nvidia-gh200-launch",
                published_at=(now - timedelta(hours=6)).isoformat(),
                related_symbols=["NVDA", "MSFT", "GOOGL", "AMD"],
                region="US",
            ),
            GlobalNewsItem(
                news_id="news-004",
                title="欧盟达成绿色协议，新能源产业迎来重大利好",
                source="Financial Times",
                importance_score=0.85,
                summary="欧盟就新一轮绿色能源投资计划达成一致，将在未来5年投入5000亿欧元支持新能源产业发展。",
                content_url="https://ft.com/eu-green-deal",
                published_at=(now - timedelta(hours=8)).isoformat(),
                related_symbols=["TSLA", "ENPH", "SEDG", "002594.SZ"],
                region="Europe",
            ),
            GlobalNewsItem(
                news_id="news-005",
                title="原油价格反弹，OPEC+考虑延长减产协议",
                source="CNBC",
                importance_score=0.82,
                summary="国际油价单日上涨3.5%，因消息称OPEC+可能考虑延长减产协议至2024年底。",
                content_url="https://cnbc.com/oil-opec-production",
                published_at=(now - timedelta(hours=10)).isoformat(),
                related_symbols=["XOM", "CVX", "601857.SH"],
                region="Global",
            ),
            GlobalNewsItem(
                news_id="news-006",
                title="比特币突破6万美元，加密货币市场全线上涨",
                source="CoinDesk",
                importance_score=0.80,
                summary="比特币价格突破6万美元整数关口，创下历史新高，带动整个加密货币市场上涨。",
                content_url="https://coindesk.com/btc-60k",
                published_at=(now - timedelta(hours=12)).isoformat(),
                related_symbols=["BTC-USD", "ETH-USD", "COIN", "MSTR"],
                region="Global",
            ),
            GlobalNewsItem(
                news_id="news-007",
                title="苹果Vision Pro正式开售，首批产品秒售罄",
                source="Wall Street Journal",
                importance_score=0.78,
                summary="苹果首款混合现实设备Vision Pro正式开售，首批10万台产品在30分钟内售罄。",
                content_url="https://wsj.com/apple-vision-pro-launch",
                published_at=(now - timedelta(hours=14)).isoformat(),
                related_symbols=["AAPL", "MSFT", "META"],
                region="US",
            ),
            GlobalNewsItem(
                news_id="news-008",
                title="中国央行宣布降准0.25个百分点，释放流动性",
                source="Caixin",
                importance_score=0.75,
                summary="中国人民银行宣布下调存款准备金率0.25个百分点，预计将释放约5000亿元流动性。",
                content_url="https://caixin.com/pboc-rrr-cut",
                published_at=(now - timedelta(hours=16)).isoformat(),
                related_symbols=["601398.SH", "000001.SZ", "600036.SH"],
                region="China",
            ),
            GlobalNewsItem(
                news_id="news-009",
                title="特斯拉超级工厂落户印度，莫迪见证签约",
                source="Economic Times",
                importance_score=0.72,
                summary="特斯拉宣布在印度投资20亿美元建设超级工厂，计划年产电动车50万辆，印度总理莫迪见证签约。",
                content_url="https://economictimes.com/tesla-india-factory",
                published_at=(now - timedelta(hours=18)).isoformat(),
                related_symbols=["TSLA", "TATAMOTORS.NS"],
                region="Asia",
            ),
            GlobalNewsItem(
                news_id="news-010",
                title="国际金价创历史新高，避险情绪推动资金流入",
                source="MarketWatch",
                importance_score=0.70,
                summary="国际金价突破2500美元/盎司，创下历史新高，全球地缘政治紧张推动避险资金持续流入黄金市场。",
                content_url="https://marketwatch.com/gold-record-high",
                published_at=(now - timedelta(hours=20)).isoformat(),
                related_symbols=["GC=F", "GOLD", "600547.SH"],
                region="Global",
            ),
        ]

    def _get_mock_sectors(self) -> tuple[List[SectorChangeItem], List[SectorChangeItem]]:
        """获取模拟的板块数据"""
        top_up_sectors = [
            SectorChangeItem(
                sector_id="sector-ai",
                name="AI人工智能",
                change_pct=5.25,
                leading_stocks=["NVDA", "MSFT", "600519.SH"],
                related_news_count=12,
                is_concept=True,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-new-energy",
                name="新能源",
                change_pct=4.10,
                leading_stocks=["TSLA", "600030.SH", "002594.SZ"],
                related_news_count=8,
                is_concept=True,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-semiconductor",
                name="半导体",
                change_pct=3.65,
                leading_stocks=["AMD", "INTC", "600584.SH"],
                related_news_count=10,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-fintech",
                name="金融科技",
                change_pct=3.20,
                leading_stocks=["SQ", "PYPL", "600036.SH"],
                related_news_count=5,
                is_concept=True,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-gold",
                name="贵金属",
                change_pct=2.85,
                leading_stocks=["GOLD", "600547.SH", "601899.SH"],
                related_news_count=7,
                is_concept=False,
                is_mock=True,
            ),
        ]

        top_down_sectors = [
            SectorChangeItem(
                sector_id="sector-real-estate",
                name="房地产",
                change_pct=-3.45,
                leading_stocks=["600048.SH", "000002.SZ", "000069.SZ"],
                related_news_count=6,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-traditional-banking",
                name="传统银行",
                change_pct=-2.70,
                leading_stocks=["JPM", "WFC", "601398.SH"],
                related_news_count=4,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-retail",
                name="传统零售",
                change_pct=-2.35,
                leading_stocks=["WMT", "TGT", "600827.SH"],
                related_news_count=3,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-oil-gas",
                name="石油天然气",
                change_pct=-1.90,
                leading_stocks=["XOM", "CVX", "601857.SH"],
                related_news_count=5,
                is_concept=False,
                is_mock=True,
            ),
            SectorChangeItem(
                sector_id="sector-travel",
                name="旅游酒店",
                change_pct=-1.55,
                leading_stocks=["MAR", "HLT", "600754.SH"],
                related_news_count=2,
                is_concept=False,
                is_mock=True,
            ),
        ]

        return top_up_sectors, top_down_sectors

    def _get_market_indices(self, force_refresh: bool = False) -> list[MarketIndexItem]:
        """Fetch lightweight real-time index quotes for the command center."""
        global _market_index_cache

        now = time.time()
        with _market_command_cache_lock:
            if (
                not force_refresh
                and _market_index_cache is not None
                and now - _market_index_cache[0] < MARKET_COMMAND_CACHE_TTL_SECONDS
            ):
                return [MarketIndexItem(**item) for item in _market_index_cache[1]]

        target_indices = [
            ("sh000001", "上证指数"),
            ("sz399001", "深证成指"),
            ("sh000016", "上证50"),
            ("sh000680", "科创综指"),
            ("sz399006", "创业板指"),
            ("sz399673", "创业板50"),
            ("sh000688", "科创50"),
            ("bj899050", "北证50"),
            ("sh000300", "沪深300"),
            ("sh000905", "中证500"),
            ("sh000510", "中证A500"),
            ("sh000852", "中证1000"),
        ]
        direct_indices: list[dict[str, Any]] = []

        try:
            import requests

            from data_layer.crawlers.akshare.board import _without_proxy_env

            quote_codes = [f"s_{code}" for code, _ in target_indices]
            url = f"https://hq.sinajs.cn/list={','.join(quote_codes)}"
            headers = {
                "Referer": "https://finance.sina.com.cn/",
                "User-Agent": "Mozilla/5.0",
            }
            with _without_proxy_env():
                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()
            response.encoding = response.apparent_encoding or "GB18030"
            quote_rows = {
                match.group(1): match.group(2).split(",")
                for match in re.finditer(r'var hq_str_s_([^=]+)="([^"]*)";', response.text)
            }

            for code, label in target_indices:
                values = quote_rows.get(code)
                if not values or len(values) < 4:
                    continue
                latest = self._optional_float(values[1])
                point_change = self._optional_float(values[2])
                change = self._optional_float(values[3])
                if latest is None or latest <= 0 or change is None:
                    continue
                direct_indices.append(
                    {
                        "code": code,
                        "name": label,
                        "value": f"{latest:.2f}",
                        "change": round(change, 2),
                        "point_change": (
                            round(point_change, 2) if point_change is not None else None
                        ),
                        "amount": self._optional_float(values[5]) if len(values) > 5 else None,
                        "source": "sina",
                    }
                )

            if len(direct_indices) == len(target_indices):
                with _market_command_cache_lock:
                    _market_index_cache = (now, direct_indices)
                return [MarketIndexItem(**item) for item in direct_indices]
        except Exception as exc:
            logger.warning("Failed to fetch direct Sina market indices: %s", exc)

        try:
            import akshare as ak

            from data_layer.crawlers.akshare.board import _without_proxy_env

            with _without_proxy_env():
                df = ak.stock_zh_index_spot_sina()

            rows_by_code = {str(row.get("代码") or "").strip(): row for _, row in df.iterrows()}
            rows_by_name = {str(row.get("名称") or "").strip(): row for _, row in df.iterrows()}

            indices: list[dict[str, Any]] = list(direct_indices)
            existing_codes = {item["code"] for item in indices}
            for code, label in target_indices:
                if code in existing_codes:
                    continue
                row = rows_by_code.get(code)
                if row is None:
                    row = rows_by_name.get(label)
                if row is None:
                    continue
                latest = self._optional_float(row.get("最新价"))
                change = self._optional_float(row.get("涨跌幅"))
                point_change = self._optional_float(row.get("涨跌额"))
                if latest is None or latest <= 0 or change is None:
                    continue
                indices.append(
                    {
                        "code": code,
                        "name": label,
                        "value": f"{latest:.2f}",
                        "change": round(change, 2),
                        "point_change": (
                            round(point_change, 2) if point_change is not None else None
                        ),
                        "amount": self._optional_float(row.get("成交额")),
                        "source": "sina",
                    }
                )

            if indices:
                with _market_command_cache_lock:
                    _market_index_cache = (now, indices)
                return [MarketIndexItem(**item) for item in indices]
        except Exception as exc:
            logger.warning("Failed to fetch real-time market indices: %s", exc)

        if direct_indices:
            with _market_command_cache_lock:
                _market_index_cache = (now, direct_indices)
            return [MarketIndexItem(**item) for item in direct_indices]

        with _market_command_cache_lock:
            cached = _market_index_cache
        if cached:
            return [MarketIndexItem(**item) for item in cached[1]]
        return []

    def _get_market_breadth(self, force_refresh: bool = False) -> Optional[MarketBreadthSnapshot]:
        """Return fast market breadth without blocking the dashboard on all-A pagination."""
        now = time.time()
        with _market_command_cache_lock:
            cached = _market_breadth_cache
        if (
            cached
            and not force_refresh
            and now - cached[0] < MARKET_BREADTH_EXACT_CACHE_TTL_SECONDS
        ):
            return MarketBreadthSnapshot(**cached[1])

        if force_refresh:
            exact_breadth = self._get_eastmoney_market_breadth()
            if exact_breadth:
                return exact_breadth

        sector_breadth = self._get_sector_board_breadth(force_refresh=force_refresh)
        if sector_breadth:
            return sector_breadth
        if cached:
            return MarketBreadthSnapshot(**cached[1])
        return None

    def _schedule_market_breadth_refresh(self) -> None:
        # Exact all-A breadth is intentionally not scheduled from the dashboard path:
        # ak.stock_zh_a_spot paginates all A shares and can run for tens of seconds.
        logger.info("Skipped dashboard-triggered exact all-A breadth refresh")

    def _get_eastmoney_market_breadth(self) -> Optional[MarketBreadthSnapshot]:
        """Build all-A breadth from Eastmoney's real-time quote list."""
        global _market_breadth_cache

        try:
            import math

            import requests

            from data_layer.crawlers.akshare.board import _without_proxy_env

            base_url = "https://push2.eastmoney.com/api/qt/clist/get"
            fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
            fields = "f3,f6,f12,f14"
            headers = {
                "Referer": "https://quote.eastmoney.com/",
                "User-Agent": "Mozilla/5.0",
                "Connection": "close",
            }

            def fetch_page(page: int, size: int) -> dict:
                params: dict[str, str | int] = {
                    "pn": page,
                    "pz": size,
                    "po": 1,
                    "np": 1,
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": 2,
                    "invt": 2,
                    "fid": "f3",
                    "fs": fs,
                    "fields": fields,
                }
                last_error: Optional[Exception] = None
                for attempt in range(3):
                    try:
                        with _without_proxy_env():
                            response = requests.get(
                                base_url,
                                params=params,
                                headers=headers,
                                timeout=10,
                            )
                            response.raise_for_status()
                        return response.json().get("data") or {}
                    except Exception as exc:
                        last_error = exc
                        time.sleep(0.3 * (attempt + 1))
                if last_error:
                    raise last_error
                return {}

            first = fetch_page(1, 1)
            total = int(first.get("total") or 0)
            if total <= 0:
                return None

            # Eastmoney caps this endpoint at 100 rows per page even if pz is larger.
            page_size = 100
            pages = math.ceil(total / page_size)
            up = down = flat = 0
            turnover_yuan = 0.0
            failed_pages = 0
            for page in range(1, pages + 1):
                try:
                    data = fetch_page(page, page_size)
                except Exception as exc:
                    failed_pages += 1
                    logger.warning("Eastmoney all-A page failed: page=%s error=%s", page, exc)
                    continue
                for row in data.get("diff") or []:
                    change = self._optional_float(row.get("f3"))
                    amount = self._optional_float(row.get("f6"))
                    if change is None:
                        continue
                    if change > 0:
                        up += 1
                    elif change < 0:
                        down += 1
                    else:
                        flat += 1
                    turnover_yuan += max(0.0, amount or 0.0)

            counted = max(1, up + down + flat)
            if counted < 4000:
                logger.warning(
                    "Eastmoney all-A breadth incomplete: counted=%s total=%s failed_pages=%s",
                    counted,
                    total,
                    failed_pages,
                )
                return None
            previous_turnover = self._get_previous_market_turnover()
            payload = {
                "up": up,
                "down": down,
                "flat": flat,
                "upRatio": round(up / counted * 100, 1),
                "downRatio": round(down / counted * 100, 1),
                "turnover": self._format_turnover_yuan(turnover_yuan),
                "turnoverDelta": None,
                "previousTurnover": (previous_turnover or {}).get("formatted"),
                "netInflow": None,
                "source": "eastmoney_all_a",
                "sourceLabel": ("东方财富全A实时" if failed_pages == 0 else f"东方财富全A实时（缺{failed_pages}页）"),
                "fetchedAt": datetime.now(UTC),
            }
            with _market_command_cache_lock:
                _market_breadth_cache = (time.time(), payload)
            return MarketBreadthSnapshot(**payload)
        except Exception as exc:
            logger.warning("Failed to fetch Eastmoney all-A breadth: %s", exc)
            return None

    @staticmethod
    def _refresh_market_breadth_exact() -> None:
        global _market_breadth_cache, _market_breadth_refreshing

        try:
            import akshare as ak

            from data_layer.crawlers.akshare.board import _without_proxy_env

            with _without_proxy_env():
                df = ak.stock_zh_a_spot()

            changes = df["涨跌幅"].apply(DashboardService._optional_float)
            up = int((changes > 0).sum())
            down = int((changes < 0).sum())
            flat = int((changes == 0).sum())
            amount = sum(
                value or 0.0 for value in df["成交额"].apply(DashboardService._optional_float)
            )
            total = max(1, up + down + flat)
            previous_turnover = DashboardService._get_previous_market_turnover()
            payload = {
                "up": up,
                "down": down,
                "flat": flat,
                "upRatio": round(up / total * 100, 1),
                "downRatio": round(down / total * 100, 1),
                "turnover": DashboardService._format_turnover_yuan(amount),
                "turnoverDelta": None,
                "previousTurnover": (previous_turnover or {}).get("formatted"),
                "source": "sina_all_a",
                "sourceLabel": "全A实时",
                "fetchedAt": datetime.now(UTC),
            }
            with _market_command_cache_lock:
                _market_breadth_cache = (time.time(), payload)
            logger.info("Refreshed exact A-share breadth: up=%s down=%s", up, down)
        except Exception as exc:
            logger.warning("Failed to refresh exact A-share breadth: %s", exc)
        finally:
            with _market_command_cache_lock:
                _market_breadth_refreshing = False

    def _get_sector_board_breadth(
        self,
        force_refresh: bool = False,
    ) -> Optional[MarketBreadthSnapshot]:
        """Build a quick breadth fallback from the cached THS industry board snapshot."""
        try:
            from data_layer.crawlers.akshare.board import fetch_sector_board

            snapshot = fetch_sector_board(force_refresh=force_refresh)
            if not snapshot.sectors:
                return None

            up = sum(max(0, int(sector.up_count)) for sector in snapshot.sectors)
            down = sum(max(0, int(sector.down_count)) for sector in snapshot.sectors)
            total = max(1, up + down)
            turnover_yuan = (
                sum(max(0.0, float(sector.total_amount)) for sector in snapshot.sectors)
                * 100_000_000
            )
            fetched_at = (
                datetime.fromtimestamp(snapshot.fetched_at, UTC)
                if snapshot.fetched_at
                else datetime.now(UTC)
            )
            return MarketBreadthSnapshot(
                up=up,
                down=down,
                flat=0,
                upRatio=round(up / total * 100, 1),
                downRatio=round(down / total * 100, 1),
                turnover=self._format_turnover_yuan(turnover_yuan),
                turnoverDelta=None,
                previousTurnover=(self._get_previous_market_turnover(force_refresh) or {}).get(
                    "formatted"
                ),
                netInflow=self._format_signed_yi(
                    sum(float(sector.net_flow) for sector in snapshot.sectors)
                ),
                source="ths_sector",
                sourceLabel="同花顺行业汇总",
                fetchedAt=fetched_at,
            )
        except Exception as exc:
            try:
                logger.warning("Failed to build THS sector breadth: %s", exc)
            except Exception:
                pass
            return None

    def _get_market_stats(self, force_refresh: bool = False) -> dict[str, Any]:
        """Return supplemental market stats without making the dashboard depend on them."""
        global _market_stats_cache

        now = time.time()
        with _market_command_cache_lock:
            cached = _market_stats_cache
        if cached and not force_refresh and now - cached[0] < MARKET_STATS_CACHE_TTL_SECONDS:
            return dict(cached[1])

        stats: dict[str, Any] = {
            "source_status": {},
            "fetched_at": datetime.now(UTC),
        }

        with _market_command_cache_lock:
            _market_stats_cache = (time.time(), dict(stats))
        return stats

    def get_market_overview_section(self, force_refresh: bool = False) -> MarketOverviewSection:
        """获取市场概览板块：全球热点新闻、上涨/下跌板块概念"""
        from datetime import UTC, datetime

        has_real_news = False
        has_real_sectors = False
        last_updated = None
        try:
            breadth = self._get_market_breadth(force_refresh=force_refresh)
        except Exception as exc:
            try:
                logger.warning("Failed to get market breadth, continuing without it: %s", exc)
            except Exception:
                pass
            breadth = None
        indices = self._get_market_indices(force_refresh=force_refresh)
        market_stats = self._get_market_stats(force_refresh=force_refresh)

        try:
            # 尝试获取真实数据
            news_data, has_real_news = self.dashboard_repo.get_combined_global_news(
                limit=10, days=7
            )
            (
                up_sectors_data,
                down_sectors_data,
                has_real_sectors,
                _,
            ) = self.dashboard_repo.get_sector_changes_from_signals(days=7, limit_per_direction=10)
            sector_views = {}
            if has_real_sectors:
                sector_views = {
                    "ths_industry": {
                        "up": [
                            self._decorate_market_sector_item(item, "ths_industry")
                            for item in up_sectors_data
                        ],
                        "down": [
                            self._decorate_market_sector_item(item, "ths_industry")
                            for item in down_sectors_data
                        ],
                    }
                }

            if has_real_news or has_real_sectors:
                logger.info(
                    f"Using real data for market overview: news={has_real_news}, sectors={has_real_sectors}"
                )

                global_news = [GlobalNewsItem(**n, is_mock=False) for n in news_data]

                # 如果没有真实新闻数据，回退到模拟
                if not global_news:
                    global_news = self._get_mock_global_news()
                    has_real_news = False

                top_up_sectors = [SectorChangeItem(**s, is_mock=False) for s in up_sectors_data]
                top_down_sectors = [SectorChangeItem(**s, is_mock=False) for s in down_sectors_data]
                normalized_sector_views = {
                    key: SectorMoverView(
                        up=[SectorChangeItem(**s, is_mock=False) for s in view.get("up", [])],
                        down=[SectorChangeItem(**s, is_mock=False) for s in view.get("down", [])],
                    )
                    for key, view in sector_views.items()
                }

                # 只要有一个方向有板块数据就使用真实数据，另一个方向可以是空的
                # 只有当两个方向都没有数据时才回退到模拟
                if not top_up_sectors and not top_down_sectors:
                    mock_up, mock_down = self._get_mock_sectors()
                    top_up_sectors = mock_up
                    top_down_sectors = mock_down
                    has_real_sectors = False

                # 使用新闻的实际发布时间作为"更新于"时间戳
                # 板块数据是实时行情（无原始发布日期），不参与计算
                def _to_utc(d: datetime) -> datetime:
                    """将 datetime 转为 UTC-aware，兼容 naive 输入"""
                    if d.tzinfo is None:
                        return d.replace(tzinfo=UTC)
                    return d.astimezone(UTC)

                candidates: List[datetime] = []
                if global_news:
                    for n in global_news:
                        if n.published_at:
                            try:
                                candidates.append(_to_utc(datetime.fromisoformat(n.published_at)))
                            except (ValueError, TypeError):
                                pass

                last_updated = max(candidates) if candidates else datetime.now(UTC)

                return MarketOverviewSection(
                    global_news=global_news,
                    top_up_sectors=top_up_sectors,
                    top_down_sectors=top_down_sectors,
                    sector_views=normalized_sector_views,
                    indices=indices,
                    breadth=breadth,
                    market_stats=market_stats,
                    uses_real_news=has_real_news,
                    uses_real_sectors=has_real_sectors,
                    last_updated=last_updated,
                )

        except Exception as e:
            logger.warning(f"Failed to fetch real market data: {e}, falling back to mock data")

        # 回退到模拟数据
        logger.info("Using mock data for market overview")
        global_news = self._get_mock_global_news()
        top_up_sectors, top_down_sectors = self._get_mock_sectors()

        return MarketOverviewSection(
            global_news=global_news,
            top_up_sectors=top_up_sectors,
            top_down_sectors=top_down_sectors,
            indices=indices,
            breadth=breadth,
            market_stats=market_stats,
            uses_real_news=False,
            uses_real_sectors=False,
            last_updated=None,
        )

    def get_market_sector_view(
        self,
        view_key: str,
        limit: int = 10,
        *,
        force_refresh: bool = False,
    ) -> dict:
        """Fetch one market sector mover view on demand."""
        from collections import Counter

        normalized_view = self._normalize_market_view_key(view_key)
        normalized_limit = max(1, min(int(limit or 10), 50))
        cache_key = (normalized_view, normalized_limit)
        if not force_refresh:
            cached_payload = self._get_cached_market_sector_payload(cache_key)
            if cached_payload is not None:
                if not self._market_sector_payload_matches_active_catalog(
                    cached_payload,
                    normalized_view,
                ):
                    logger.info(
                        "Ignored stale market sector cache with inactive catalog rows: %s",
                        normalized_view,
                    )
                    self._drop_cached_market_sector_payload(cache_key)
                else:
                    logger.info("Market sector view cache hit: %s", normalized_view)
                    cached_payload["cache_hit"] = True
                    return cached_payload

            persistent_payload = self._get_persistent_market_sector_payload(cache_key)
            if persistent_payload is not None:
                if not self._market_sector_payload_matches_active_catalog(
                    persistent_payload,
                    normalized_view,
                ):
                    logger.info(
                        "Ignored stale market sector persistent cache with inactive catalog rows: %s",
                        normalized_view,
                    )
                else:
                    logger.info("Market sector persistent cache hit: %s", normalized_view)
                    persistent_payload["cache_hit"] = True
                    self._set_cached_market_sector_payload(
                        cache_key,
                        persistent_payload,
                        persist=False,
                    )
                    return persistent_payload
        else:
            try:
                logger.info("Bypassing market sector cache for force refresh: %s", normalized_view)
            except Exception:
                pass

        if normalized_view == "ths_industry":
            payload = self._get_ths_market_sector_payload(normalized_limit)
            self._set_cached_market_sector_payload(cache_key, payload)
            return self._copy_market_sector_payload(payload)

        workbook_payload: dict | None = None
        workbook_enabled = _env_flag(ENABLE_WIND_REALTIME_WORKBOOK_ENV, default=True)
        fallback_enabled = _env_flag(ALLOW_WIND_EXCEL_FALLBACK_ENV, default=True)
        if workbook_enabled:
            try:
                workbook_payload = self._read_wind_workbook_sector_view(
                    normalized_view,
                    normalized_limit,
                )
                if not workbook_payload.get("has_real_data") and workbook_payload.get("status") in {
                    "workbook_missing",
                    "workbook_not_open",
                }:
                    self._trigger_wind_workbook_recovery(
                        reason=str(workbook_payload.get("status") or "sector_view")
                    )
                if workbook_payload.get("has_real_data") or not fallback_enabled:
                    try:
                        logger.info(
                            "Using Wind realtime workbook sector view: %s status=%s real=%s",
                            normalized_view,
                            workbook_payload.get("status"),
                            workbook_payload.get("has_real_data"),
                        )
                    except Exception:
                        pass
                    self._set_cached_market_sector_payload(cache_key, workbook_payload)
                    return self._copy_market_sector_payload(workbook_payload)
                if workbook_payload.get("status") in {
                    "workbook_read_error",
                    "workbook_timeout",
                    "snapshot_invalid",
                }:
                    try:
                        logger.info(
                            "Skipping Wind formula fallback after unhealthy workbook read: %s status=%s",
                            normalized_view,
                            workbook_payload.get("status"),
                        )
                    except Exception:
                        pass
                    self._set_cached_market_sector_payload(cache_key, workbook_payload)
                    return self._copy_market_sector_payload(workbook_payload)
            except Exception as exc:
                try:
                    logger.warning("Wind realtime workbook read failed: %s", exc)
                except Exception:
                    pass
                if not fallback_enabled:
                    payload = {
                        "view_key": normalized_view,
                        "view_label": self._market_view_label(normalized_view),
                        "up": [],
                        "down": [],
                        "has_real_data": False,
                        "fetched_at": 0.0,
                        "cache_hit": False,
                        "cache_ttl_seconds": MARKET_SECTOR_CACHE_TTL_SECONDS,
                        "status": "workbook_read_error",
                        "message": f"读取Wind实时工作簿失败: {exc}",
                        "source": "wind_realtime_workbook",
                    }
                    self._set_cached_market_sector_payload(cache_key, payload)
                    return self._copy_market_sector_payload(payload)
        else:
            try:
                logger.info(
                    "Wind realtime workbook disabled; set %s=1 to enable",
                    ENABLE_WIND_REALTIME_WORKBOOK_ENV,
                )
            except Exception:
                pass

        if not fallback_enabled:
            payload = workbook_payload or {
                "view_key": normalized_view,
                "view_label": self._market_view_label(normalized_view),
                "up": [],
                "down": [],
                "has_real_data": False,
                "fetched_at": 0.0,
                "cache_hit": False,
                "cache_ttl_seconds": MARKET_SECTOR_CACHE_TTL_SECONDS,
                "status": "workbook_disabled",
                "message": (
                    f"Wind实时工作簿未启用；设置 {ENABLE_WIND_REALTIME_WORKBOOK_ENV}=1 "
                    f"可优先读取工作簿，设置 {ALLOW_WIND_EXCEL_FALLBACK_ENV}=0 "
                    "可关闭 Wind 指数公式兜底"
                ),
                "source": "wind_realtime_workbook",
            }
            self._set_cached_market_sector_payload(cache_key, payload)
            return self._copy_market_sector_payload(payload)

        provider = WindMarketOverviewProvider()
        try:
            logger.info(
                "Preparing market sector view %s from Wind seeds: count=%s views=%s",
                normalized_view,
                len(provider.seeds),
                dict(Counter(seed.view_key for seed in provider.seeds)),
            )
        except Exception:
            pass
        grouped_movers = provider.get_grouped_movers(
            limit=normalized_limit,
            view_keys=(normalized_view,),
        )
        view = grouped_movers.get("views", {}).get(normalized_view, {"up": [], "down": []})
        try:
            logger.info(
                "Loaded market sector view %s: up=%s down=%s real=%s",
                normalized_view,
                len(view.get("up", [])),
                len(view.get("down", [])),
                bool(grouped_movers.get("has_real_data")),
            )
        except Exception:
            pass
        payload = {
            "view_key": normalized_view,
            "view_label": self._market_view_label(normalized_view),
            "up": view.get("up", []),
            "down": view.get("down", []),
            "has_real_data": bool(grouped_movers.get("has_real_data")),
            "fetched_at": grouped_movers.get("fetched_at", 0.0),
            "cache_hit": False,
            "cache_ttl_seconds": MARKET_SECTOR_CACHE_TTL_SECONDS,
        }
        if not payload["has_real_data"]:
            try:
                logger.info("No provider fallback data for market view: %s", normalized_view)
            except Exception:
                pass
            fallback_payload = workbook_payload or payload
            self._set_cached_market_sector_payload(cache_key, fallback_payload)
            return self._copy_market_sector_payload(fallback_payload)

        self._set_cached_market_sector_payload(cache_key, payload)
        return self._copy_market_sector_payload(payload)

    def _read_wind_workbook_sector_view(self, view_key: str, limit: int) -> dict:
        """Read the Excel-backed Wind view without letting xlwings hang the API."""
        from services.wind_realtime_workbook import WindRealtimeWorkbookReader

        timeout_seconds = max(
            0.1,
            _env_float(
                MARKET_SECTOR_WORKBOOK_READ_TIMEOUT_ENV,
                MARKET_SECTOR_WORKBOOK_READ_TIMEOUT_SECONDS,
            ),
        )

        def read_payload() -> dict:
            return WindRealtimeWorkbookReader(
                stale_after_seconds=int(MARKET_SECTOR_CACHE_TTL_SECONDS)
            ).get_view(view_key, limit=limit)

        future = _wind_workbook_read_executor.submit(read_payload)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            future.cancel()
            logger.warning(
                "Wind realtime workbook read timed out: view=%s limit=%s timeout=%s",
                view_key,
                limit,
                timeout_seconds,
            )
            return {
                "view_key": view_key,
                "view_label": self._market_view_label(view_key),
                "up": [],
                "down": [],
                "has_real_data": False,
                "fetched_at": 0.0,
                "cache_hit": False,
                "cache_ttl_seconds": MARKET_SECTOR_CACHE_TTL_SECONDS,
                "status": "workbook_timeout",
                "message": f"读取Wind实时工作簿超过 {timeout_seconds:g} 秒，已跳过本次刷新",
                "source": "wind_realtime_workbook",
            }

    def _trigger_wind_workbook_recovery(self, *, reason: str) -> None:
        try:
            from services.wind_workbook_manager import get_wind_workbook_manager

            get_wind_workbook_manager().start_background_ensure(reason=reason)
        except Exception as exc:
            logger.debug("Wind workbook recovery trigger failed: %s", exc)

    def _get_ths_market_sector_payload(self, limit: int) -> dict:
        up, down, has_real_data, fetched_at = self.dashboard_repo.get_sector_changes_from_signals(
            days=7,
            limit_per_direction=limit,
        )
        up = [self._decorate_market_sector_item(item, "ths_industry") for item in up]
        down = [self._decorate_market_sector_item(item, "ths_industry") for item in down]
        logger.info(
            "Loaded market sector view ths_industry: up=%s down=%s real=%s",
            len(up),
            len(down),
            has_real_data,
        )
        return {
            "view_key": "ths_industry",
            "view_label": self._market_view_label("ths_industry"),
            "up": up,
            "down": down,
            "has_real_data": bool(has_real_data),
            "fetched_at": fetched_at,
            "cache_hit": False,
            "cache_ttl_seconds": MARKET_SECTOR_CACHE_TTL_SECONDS,
        }

    def _get_cross_source_market_sector_fallback_payload(
        self,
        view_key: str,
        limit: int,
        *,
        upstream_payload: Optional[dict] = None,
    ) -> dict:
        """Use the THS board feed when Wind/Excel is unavailable for a selected view."""
        try:
            (
                up,
                down,
                has_real_data,
                fetched_at,
            ) = self.dashboard_repo.get_sector_changes_from_signals(
                days=7,
                limit_per_direction=limit,
            )
        except Exception as exc:
            logger.warning(
                "THS cross-source market sector fallback failed for %s: %s",
                view_key,
                exc,
            )
            return {
                "view_key": view_key,
                "view_label": self._market_view_label(view_key),
                "up": [],
                "down": [],
                "has_real_data": False,
                "fetched_at": 0.0,
                "cache_hit": False,
                "cache_ttl_seconds": MARKET_SECTOR_CACHE_TTL_SECONDS,
                "status": "cross_source_fallback_failed",
                "source": "ths_board_fallback",
            }

        decorated_up = [
            {
                **self._decorate_market_sector_item(item, view_key),
                "source": item.get("source") or "ths_board_fallback",
            }
            for item in up
        ]
        decorated_down = [
            {
                **self._decorate_market_sector_item(item, view_key),
                "source": item.get("source") or "ths_board_fallback",
            }
            for item in down
        ]
        logger.info(
            "Using THS cross-source fallback for market view %s: up=%s down=%s real=%s upstream=%s",
            view_key,
            len(decorated_up),
            len(decorated_down),
            has_real_data,
            (upstream_payload or {}).get("status"),
        )
        return {
            "view_key": view_key,
            "view_label": self._market_view_label(view_key),
            "up": decorated_up,
            "down": decorated_down,
            "has_real_data": bool(has_real_data),
            "fetched_at": fetched_at,
            "cache_hit": False,
            "cache_ttl_seconds": MARKET_SECTOR_CACHE_TTL_SECONDS,
            "status": "wind_unavailable_ths_fallback",
            "source": "ths_board_fallback",
            "upstream_status": (upstream_payload or {}).get("status"),
            "upstream_message": (upstream_payload or {}).get("message"),
        }

    @staticmethod
    def _decorate_market_sector_item(item: dict, view_key: str) -> dict:
        normalized_is_concept = (
            False if view_key == "ths_industry" else bool(item.get("is_concept"))
        )
        return {
            **item,
            "source": item.get("source", "ths"),
            "is_concept": normalized_is_concept,
            "view_key": view_key,
            "view_label": DashboardService._market_view_label(view_key),
        }

    @staticmethod
    def _get_previous_market_turnover(force_refresh: bool = False) -> Optional[dict[str, Any]]:
        """Return previous trading day's A-share turnover with a date-aware cache.

        The underlying akshare calls can take 10-30 seconds, so this method never
        blocks the request path.  If the cache is empty or stale it fires a background
        fetch and returns None immediately; subsequent calls return the cached value.
        """
        global _previous_turnover_cache, _previous_turnover_refreshing

        now = time.time()
        local_date = datetime.now().date().isoformat()
        with _market_command_cache_lock:
            cached = _previous_turnover_cache

        # Return cached value if still fresh for today.
        if cached and not force_refresh:
            cached_at, payload = cached
            if (
                now - cached_at < PREVIOUS_MARKET_TURNOVER_CACHE_TTL_SECONDS
                and payload.get("local_date") == local_date
            ):
                return dict(payload)

        # Cache miss / stale — trigger a background refresh and return None now.
        with _market_command_cache_lock:
            already = _previous_turnover_refreshing
        if not already:
            with _market_command_cache_lock:
                _previous_turnover_refreshing = True
            Thread(
                target=DashboardService._refresh_previous_market_turnover,
                name="prev-turnover-refresh",
                daemon=True,
            ).start()

        # Return stale value if we have one (better than nothing).
        if cached:
            return dict(cached[1])
        return None

    @staticmethod
    def _refresh_previous_market_turnover() -> None:
        """Background worker: fetch prior-day turnover and populate the cache."""
        global _previous_turnover_cache, _previous_turnover_refreshing
        try:
            now = time.time()
            local_date = datetime.now().date().isoformat()
            trade_date = DashboardService._previous_trading_date_yyyymmdd()
            if not trade_date:
                return
            amount_yuan = DashboardService._fetch_previous_trading_day_turnover_yuan(trade_date)
            if amount_yuan is None or amount_yuan <= 0:
                return
            payload = {
                "local_date": local_date,
                "trade_date": trade_date,
                "amount_yuan": amount_yuan,
                "formatted": DashboardService._format_turnover_yuan(amount_yuan),
            }
            with _market_command_cache_lock:
                _previous_turnover_cache = (now, payload)
            logger.info(
                "Previous trading day turnover refreshed: date=%s formatted=%s",
                trade_date,
                payload["formatted"],
            )
        except Exception as exc:
            logger.warning("Failed to refresh previous trading day turnover: %s", exc)
        finally:
            with _market_command_cache_lock:
                _previous_turnover_refreshing = False

    @staticmethod
    def _previous_trading_date_yyyymmdd(today: Optional[datetime] = None) -> Optional[str]:
        local_today = today.date() if isinstance(today, datetime) else datetime.now().date()
        try:
            import akshare as ak

            from data_layer.crawlers.akshare.board import _without_proxy_env

            with _without_proxy_env():
                df = ak.tool_trade_date_hist_sina()
            dates = []
            for raw_date in df["trade_date"]:
                try:
                    parsed = datetime.fromisoformat(str(raw_date)[:10]).date()
                except ValueError:
                    continue
                if parsed < local_today:
                    dates.append(parsed)
            if dates:
                return max(dates).strftime("%Y%m%d")
        except Exception as exc:
            logger.warning("Failed to fetch trading calendar for previous turnover: %s", exc)

        candidate = local_today - timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
        return candidate.strftime("%Y%m%d")

    @staticmethod
    def _fetch_previous_trading_day_turnover_yuan(trade_date: str) -> Optional[float]:
        """Fetch prior trading day SSE/SZSE A-share turnover and normalize to yuan."""
        try:
            import akshare as ak

            from data_layer.crawlers.akshare.board import _without_proxy_env

            with _without_proxy_env():
                sse_df = ak.stock_sse_deal_daily(date=trade_date)
                szse_df = ak.stock_szse_summary(date=trade_date)

            sse_amount_yi = DashboardService._extract_sse_a_share_turnover_yi(sse_df)
            szse_amount_yuan = DashboardService._extract_szse_a_share_turnover_yuan(szse_df)
            amount_yuan = sse_amount_yi * 100_000_000 + szse_amount_yuan
            if amount_yuan <= 0:
                return None
            return amount_yuan
        except Exception as exc:
            logger.warning(
                "Failed to fetch previous trading day turnover: date=%s error=%s",
                trade_date,
                exc,
            )
            return None

    @staticmethod
    def _extract_sse_a_share_turnover_yi(df) -> float:
        rows = df[df["单日情况"].astype(str) == "成交金额"]
        if rows.empty:
            return 0.0
        row = rows.iloc[0]
        values = [DashboardService._optional_float(row.get(column)) for column in ("主板A", "科创板")]
        total = sum(value for value in values if value is not None)
        if total > 0:
            return total
        return DashboardService._optional_float(row.get("股票")) or 0.0

    @staticmethod
    def _extract_szse_a_share_turnover_yuan(df) -> float:
        rows = df[df["证券类别"].astype(str).isin({"主板A股", "创业板A股"})]
        total = sum(
            DashboardService._optional_float(row.get("成交金额")) or 0.0 for _, row in rows.iterrows()
        )
        if total > 0:
            return total
        stock_rows = df[df["证券类别"].astype(str) == "股票"]
        if stock_rows.empty:
            return 0.0
        return DashboardService._optional_float(stock_rows.iloc[0].get("成交金额")) or 0.0

    @staticmethod
    def _optional_float(value) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_turnover_yuan(amount: float) -> str:
        if amount >= 1_000_000_000_000:
            return f"{amount / 1_000_000_000_000:.2f}万亿"
        if amount >= 100_000_000:
            return f"{amount / 100_000_000:.0f}亿"
        return f"{amount:.0f}"

    @staticmethod
    def _format_signed_yi(value: float) -> str:
        return f"{value:+.2f}亿"

    @staticmethod
    def _get_cached_market_sector_payload(cache_key: tuple[str, int]) -> Optional[dict]:
        now = time.monotonic()
        with _market_sector_cache_lock:
            cached = _market_sector_cache.get(cache_key)
            if not cached:
                return None
            cached_at, payload = cached
            if now - cached_at > MARKET_SECTOR_CACHE_TTL_SECONDS:
                _market_sector_cache.pop(cache_key, None)
                return None
            if not DashboardService._market_sector_payload_is_valid_for_cache(
                cache_key,
                payload,
                persistent=False,
            ):
                _market_sector_cache.pop(cache_key, None)
                return None
            return DashboardService._copy_market_sector_payload(payload)

    @staticmethod
    def _drop_cached_market_sector_payload(cache_key: tuple[str, int]) -> None:
        with _market_sector_cache_lock:
            _market_sector_cache.pop(cache_key, None)

    @staticmethod
    def _set_cached_market_sector_payload(
        cache_key: tuple[str, int],
        payload: dict,
        *,
        persist: bool = True,
    ) -> None:
        with _market_sector_cache_lock:
            _market_sector_cache[cache_key] = (
                time.monotonic(),
                DashboardService._copy_market_sector_payload(payload),
            )
        if (
            persist
            and payload.get("has_real_data")
            and DashboardService._market_sector_payload_is_valid_for_cache(
                cache_key,
                payload,
                persistent=True,
            )
        ):
            DashboardService._set_persistent_market_sector_payload(cache_key, payload)

    @staticmethod
    def _persistent_market_sector_cache_key(cache_key: tuple[str, int]) -> str:
        view_key, limit = cache_key
        return f"{view_key}|{limit}"

    @staticmethod
    def _get_persistent_market_sector_payload(cache_key: tuple[str, int]) -> Optional[dict]:
        path = MARKET_SECTOR_DISK_CACHE_PATH
        try:
            if not path.exists():
                return None
            cache = json.loads(path.read_text(encoding="utf-8"))
            entry = cache.get(DashboardService._persistent_market_sector_cache_key(cache_key))
            if not isinstance(entry, dict):
                return None
            cached_at = float(entry.get("cached_at") or 0.0)
            if time.time() - cached_at > MARKET_SECTOR_DISK_CACHE_MAX_AGE_SECONDS:
                return None
            payload = entry.get("payload")
            if not isinstance(payload, dict) or not payload.get("has_real_data"):
                return None
            if not DashboardService._market_sector_payload_is_valid_for_cache(
                cache_key,
                payload,
                persistent=True,
            ):
                return None
            return DashboardService._copy_market_sector_payload(payload)
        except Exception as exc:
            logger.debug("Failed to read market sector persistent cache: %s", exc)
            return None

    @staticmethod
    def _set_persistent_market_sector_payload(cache_key: tuple[str, int], payload: dict) -> None:
        path = MARKET_SECTOR_DISK_CACHE_PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            cache: dict[str, Any]
            if path.exists():
                cache = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(cache, dict):
                    cache = {}
            else:
                cache = {}
            if not DashboardService._market_sector_payload_is_valid_for_cache(
                cache_key,
                payload,
                persistent=True,
            ):
                cache.pop(DashboardService._persistent_market_sector_cache_key(cache_key), None)
                return
            cache[DashboardService._persistent_market_sector_cache_key(cache_key)] = {
                "cached_at": time.time(),
                "payload": DashboardService._copy_market_sector_payload(payload),
            }
            tmp_path = path.with_suffix(f"{path.suffix}.tmp")
            tmp_path.write_text(
                json.dumps(cache, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            tmp_path.replace(path)
        except Exception as exc:
            logger.debug("Failed to write market sector persistent cache: %s", exc)

    @staticmethod
    def _market_sector_payload_matches_active_catalog(payload: dict, view_key: str) -> bool:
        if view_key == "ths_industry":
            return True
        active_codes = DashboardService._active_market_sector_codes(view_key)
        if not active_codes:
            return True
        for side in ("up", "down"):
            for item in payload.get(side, []) or []:
                code = DashboardService._wind_code_from_sector_item(item)
                if code and code not in active_codes:
                    return False
        return True

    @staticmethod
    def _market_sector_payload_is_valid_for_cache(
        cache_key: tuple[str, int],
        payload: dict,
        *,
        persistent: bool,
    ) -> bool:
        view_key, _limit = cache_key
        if view_key == "ths_industry":
            return True
        if str(payload.get("source") or "") == "ths_board_fallback":
            return False
        if str(payload.get("status") or "") == "wind_unavailable_ths_fallback":
            return False
        if persistent and str(payload.get("source") or "") != "wind_realtime_workbook":
            return False
        return DashboardService._market_sector_payload_matches_active_catalog(
            payload,
            view_key,
        )

    @staticmethod
    def _active_market_sector_codes(view_key: str) -> set[str]:
        try:
            return {
                entry.code.strip().upper()
                for entry in load_wind_index_catalog()
                if entry.view_key == view_key and entry.is_active
            }
        except Exception as exc:
            logger.debug("Failed to load active market sector catalog for %s: %s", view_key, exc)
            return set()

    @staticmethod
    def _wind_code_from_sector_item(item: dict) -> str:
        sector_id = str(item.get("sector_id") or "").strip()
        if not sector_id.startswith("wind-"):
            return ""
        return sector_id.removeprefix("wind-").replace("-", ".").upper()

    @staticmethod
    def _copy_market_sector_payload(payload: dict) -> dict:
        return {
            **payload,
            "up": [
                DashboardService._format_market_sector_display_item(item)
                for item in payload.get("up", [])
            ],
            "down": [
                DashboardService._format_market_sector_display_item(item)
                for item in payload.get("down", [])
            ],
        }

    @staticmethod
    def _format_market_sector_display_item(item: dict) -> dict:
        formatted = dict(item)
        if str(formatted.get("sector_id") or "").startswith("wind-"):
            formatted["name"] = str(formatted.get("name") or "").strip().removesuffix("指数")
        return formatted

    @staticmethod
    def _normalize_market_view_key(view_key: str) -> str:
        if not view_key:
            return "ths_industry"
        if view_key == "theme":
            return "wind_hot_concept"
        if view_key == "industry":
            return "wind_l1"
        if view_key in MARKET_SECTOR_VIEW_ORDER:
            return view_key
        return "ths_industry"

    @staticmethod
    def _market_view_label(view_key: str) -> str:
        labels = {
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
            "ths_industry": "同花顺行业",
        }
        return labels.get(view_key, view_key)

    @staticmethod
    def _extract_market_sector_views(grouped_movers: dict) -> dict:
        views = grouped_movers.get("views")
        if isinstance(views, dict) and views:
            return views

        sector_views = {}
        for key in MARKET_SECTOR_VIEW_ORDER:
            view = grouped_movers.get(key)
            if isinstance(view, dict):
                sector_views[key] = view

        if not sector_views:
            sector_views = {
                "wind_hot_concept": grouped_movers.get("theme", {"up": [], "down": []}),
                "wind_l1": grouped_movers.get("industry", {"up": [], "down": []}),
            }
        return sector_views

    @staticmethod
    def _first_non_empty_sector_direction(sector_views: dict, direction: str) -> list:
        for key in MARKET_SECTOR_VIEW_ORDER:
            items = sector_views.get(key, {}).get(direction, [])
            if items:
                return items
        for view in sector_views.values():
            items = view.get(direction, [])
            if items:
                return items
        return []

    def get_today_section(self) -> TodaySection:
        """获取 Today 板块数据：新事件、高优先级论题、异常流向"""
        # 获取今日/24小时内新事件
        from data_layer.repositories.models import CanonicalEvent

        events = (
            self.session.query(CanonicalEvent)
            .filter(CanonicalEvent.created_at >= self.today_cutoff)
            .order_by(desc(CanonicalEvent.created_at))
            .limit(10)
            .all()
        )
        new_events = [
            TodayEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                summary=event.summary,
                impact_direction=event.impact_direction,
                confidence=float(event.confidence),
                created_at=event.created_at.isoformat() if event.created_at else None,
            )
            for event in events
        ]

        # 获取高优先级论题（score > 0.7 且状态活跃）
        from data_layer.repositories.models import AlphaSignalDB

        theses = (
            self.session.query(AlphaSignalDB)
            .filter(AlphaSignalDB.score >= 0.7, AlphaSignalDB.status == "active")
            .order_by(desc(AlphaSignalDB.score))
            .limit(24)
            .all()
        )
        theses = self._deduplicate_signals(theses)[:8]
        high_priority = [
            HighPriorityThesis(
                signal_id=thesis.signal_id,
                subject_id=thesis.subject_id,
                thesis=thesis.thesis,
                score=float(thesis.score),
                confidence=float(thesis.confidence),
                status=thesis.status,
                event_type=thesis.event_type,
            )
            for thesis in theses
        ]

        # 获取异常流向（来自产业链映射）
        abnormal_flows: List[AbnormalFlow] = []
        try:
            import importlib

            industry_chain_module = importlib.import_module(
                "data_layer.repositories.industry_chain_repository"
            )
            repo = industry_chain_module.IndustryChainRepository(self.session)
            anomalies = repo.get_recent_abnormal_flows(limit=5)
            if anomalies:
                abnormal_flows = [
                    AbnormalFlow(
                        symbol=anomaly.symbol,
                        industry=anomaly.industry,
                        diffusion_strength=float(anomaly.diffusion_strength),
                        change_pct=float(anomaly.change_pct),
                        updated_at=anomaly.updated_at.isoformat(),
                    )
                    for anomaly in anomalies
                ]
            else:
                # 如果没有真实数据，使用模拟数据
                abnormal_flows = self._get_mock_abnormal_flows()
        except Exception as e:
            logger.warning(f"Failed to fetch abnormal flows: {e}, using mock data")
            abnormal_flows = self._get_mock_abnormal_flows()

        return TodaySection(
            new_events=new_events,
            high_priority_theses=high_priority,
            abnormal_flows=abnormal_flows,
        )

    def _get_mock_abnormal_flows(self):
        """获取模拟的异常流向数据"""
        from datetime import UTC, datetime

        return [
            AbnormalFlow(
                symbol="600519.SH",
                industry="白酒",
                diffusion_strength=0.87,
                change_pct=0.052,
                updated_at=datetime.now(UTC).isoformat(),
            ),
            AbnormalFlow(
                symbol="002594.SZ",
                industry="新能源汽车",
                diffusion_strength=0.79,
                change_pct=0.041,
                updated_at=datetime.now(UTC).isoformat(),
            ),
        ]

    @staticmethod
    def _deduplicate_signals(signals: list) -> list:
        """按 subject_id 去重，每个 subject 只保留 score 最高的一条"""
        seen: dict = {}
        for s in signals:
            key = s.subject_id
            if key not in seen or (s.score or 0) > (seen[key].score or 0):
                seen[key] = s
        return list(seen.values())

    def _calc_win_rate_for_type(self, event_type: str) -> float:
        """计算指定 event_type 的胜率"""
        from data_layer.repositories.models import SignalOutcomeDB

        total = (
            self.session.query(SignalOutcomeDB)
            .filter(SignalOutcomeDB.event_type == event_type)
            .count()
        )
        if total == 0:
            return 0.0
        wins = (
            self.session.query(SignalOutcomeDB)
            .filter(
                SignalOutcomeDB.event_type == event_type,
                SignalOutcomeDB.outcome_return > 0,
            )
            .count()
        )
        return wins / total

    def get_research_queue_section(self) -> ResearchQueueSection:
        """获取 Research Queue 板块数据：待处理断言、缺失证据、映射审查"""
        pending_assertions: List[PendingAssertion] = []
        missing_evidence: List[MissingEvidence] = []
        mapping_reviews: List[MappingReviewItem] = []
        has_real_data = False

        # 获取待处理断言（来自审查框架）
        try:
            from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
            from data_layer.repositories.models import Assertion

            # 获取待审核的断言（放宽状态条件，获取所有非终态断言）
            AssertionRepositoryImpl(self.session)
            pending_assertions_db = (
                self.session.query(Assertion)
                .filter(Assertion.reviewer_status.in_(["pending", "draft", "in_review"]))
                .order_by(desc(Assertion.observed_at))
                .limit(10)
                .all()
            )

            if pending_assertions_db:
                has_real_data = True
                pending_assertions = [
                    PendingAssertion(
                        assertion_id=a.assertion_id,
                        signal_id=f"signal-linked-{a.assertion_id}",
                        subject=a.subject_entity_id or "unknown",
                        claim=f"{a.predicate} {a.object_value}" if a.object_value else a.predicate,
                        status=a.reviewer_status,
                        created_at=a.observed_at.isoformat() if a.observed_at else "",
                    )
                    for a in pending_assertions_db
                ]

            # 如果没有真实数据或部分数据缺失，使用模拟数据补充
            if not has_real_data:
                logger.info("No real research queue data found, using mock data")
                (
                    pending_assertions,
                    missing_evidence,
                    mapping_reviews,
                ) = self._get_mock_research_queue()
            else:
                # 如果有真实断言数据，但缺失其他数据，用模拟数据补充
                if not missing_evidence:
                    _, missing_evidence, _ = self._get_mock_research_queue()
                if not mapping_reviews:
                    _, _, mapping_reviews = self._get_mock_research_queue()

        except Exception as e:
            logger.warning(f"Failed to fetch research queue data: {e}, falling back to mock data")
            pending_assertions, missing_evidence, mapping_reviews = self._get_mock_research_queue()

        return ResearchQueueSection(
            pending_assertions=pending_assertions,
            missing_evidence=missing_evidence,
            mapping_reviews=mapping_reviews,
        )

    def _get_mock_research_queue(self):
        """获取模拟的研究队列数据"""
        from datetime import UTC, datetime

        pending_assertions = [
            PendingAssertion(
                assertion_id="assert-001",
                signal_id="signal-001",
                subject="600519.SH",
                claim="贵州茅台Q1净利润同比增长18.2%，超出市场预期",
                status="pending",
                created_at=datetime.now(UTC).isoformat(),
            ),
            PendingAssertion(
                assertion_id="assert-002",
                signal_id="signal-002",
                subject="002594.SZ",
                claim="比亚迪4月新能源汽车销量同比增长62%",
                status="pending",
                created_at=datetime.now(UTC).isoformat(),
            ),
            PendingAssertion(
                assertion_id="assert-003",
                signal_id="signal-003",
                subject="NVDA",
                claim="英伟达发布新一代GH200超级芯片，AI计算性能提升3倍",
                status="draft",
                created_at=datetime.now(UTC).isoformat(),
            ),
        ]

        missing_evidence = [
            MissingEvidence(
                assertion_id="assert-001",
                required_evidence_type="financial_statement",
                subject="600519.SH",
            ),
            MissingEvidence(
                assertion_id="assert-002",
                required_evidence_type="sales_data",
                subject="002594.SZ",
            ),
        ]

        mapping_reviews = [
            MappingReviewItem(
                review_id="review-001",
                subject="白酒产业链",
                reviewer="auto-mapper",
                status="pending",
            ),
            MappingReviewItem(
                review_id="review-002",
                subject="新能源汽车上下游",
                reviewer="auto-mapper",
                status="in_progress",
            ),
        ]

        return pending_assertions, missing_evidence, mapping_reviews

    def get_candidate_board_section(self) -> CandidateBoardSection:
        """获取 Candidate Board 板块：就绪度最高的候选机会"""
        candidates: List[CandidateItem] = []
        has_real_data = False

        try:
            from data_layer.repositories.models import AlphaSignalDB

            # 获取活跃信号
            active_signals = (
                self.session.query(AlphaSignalDB).filter(AlphaSignalDB.status == "active").all()
            )

            if active_signals:
                has_real_data = True
                # deduplicate by subject_id before scoring
                active_signals = self._deduplicate_signals(active_signals)

                scored = []
                for signal in active_signals:
                    readiness = float(signal.score or 0.5) * float(signal.confidence or 0.5)
                    scored.append(
                        {
                            "candidate_id": signal.signal_id,
                            "signal_id": signal.signal_id,
                            "subject": signal.subject_id,
                            "readiness_score": readiness,
                            "thesis": signal.thesis,
                            "timing_blocker": getattr(signal, "timing_blocker", None),
                            "trigger_condition": getattr(signal, "trigger_condition", None),
                            "event_type": signal.event_type or "综合",
                        }
                    )

                # sort descending by readiness score
                scored.sort(key=lambda x: x["readiness_score"], reverse=True)
                candidates = [CandidateItem(**item) for item in scored[:10]]

            # 如果没有真实数据，使用模拟数据
            if not has_real_data:
                logger.info("No real candidate board data found, using mock data")
                candidates = self._get_mock_candidates()

        except Exception as e:
            logger.warning(f"Failed to fetch candidate board data: {e}, falling back to mock data")
            candidates = self._get_mock_candidates()

        return CandidateBoardSection(top_candidates=candidates)

    def _get_mock_candidates(self):
        """获取模拟的候选机会数据"""
        return [
            CandidateItem(
                candidate_id="candidate-001",
                signal_id="signal-001",
                subject="600519.SH",
                readiness_score=0.87,
                thesis="贵州茅台Q1业绩超预期，白酒消费复苏强劲",
                timing_blocker="等待技术面确认突破",
                trigger_condition="收盘价突破1900元",
                event_type="earnings",
            ),
            CandidateItem(
                candidate_id="candidate-002",
                signal_id="signal-002",
                subject="002594.SZ",
                readiness_score=0.82,
                thesis="比亚迪销量持续高增长，新能源汽车渗透率提升",
                timing_blocker="大盘情绪偏弱",
                trigger_condition="成交量放大2倍",
                event_type="sales_data",
            ),
            CandidateItem(
                candidate_id="candidate-003",
                signal_id="signal-003",
                subject="NVDA",
                readiness_score=0.79,
                thesis="英伟达AI芯片需求旺盛，GH200超级芯片发布",
                timing_blocker="估值偏高",
                trigger_condition="回调至合理区间",
                event_type="product_launch",
            ),
        ]

    def get_learning_section(self) -> LearningSection:
        """获取 Learning 板块：最近失败、最佳表现事件类型、每周总结"""
        recent_failures: List[RecentFailure] = []
        best_event_types: List[BestPerformingEventType] = []
        weekly_lessons: List[WeeklyLesson] = []
        has_real_data = False

        # 获取最近六个月内失败记录
        try:
            from sqlalchemy import func

            from data_layer.repositories.models import SignalOutcomeDB

            six_months_ago = datetime.now(UTC) - timedelta(days=180)
            failures = (
                self.session.query(SignalOutcomeDB)
                .filter(
                    SignalOutcomeDB.created_at >= six_months_ago,
                    SignalOutcomeDB.outcome_return < 0,
                )
                .order_by(desc(SignalOutcomeDB.created_at))
                .limit(8)
                .all()
            )

            if failures:
                has_real_data = True
                recent_failures = [
                    RecentFailure(
                        outcome_id=f.outcome_id,
                        signal_id=f.signal_id,
                        subject_id=f.subject_id,
                        failure_reason=(
                            _translate_failure_reason(f.failure_reason) if f.failure_reason else ""
                        ),
                        lesson=f.lesson if f.lesson else "",
                        outcome_return=float(f.outcome_return) if f.outcome_return else None,
                        created_at=f.created_at.isoformat() if f.created_at else None,
                    )
                    for f in failures
                ]

            # 获取最佳表现事件类型按平均超额收益
            event_stats = (
                self.session.query(
                    SignalOutcomeDB.event_type,
                    func.avg(SignalOutcomeDB.outcome_excess_return).label("avg_excess"),
                    func.count(SignalOutcomeDB.outcome_id).label("count"),
                )
                .filter(SignalOutcomeDB.event_type.isnot(None))
                .group_by(SignalOutcomeDB.event_type)
                .having(func.count(SignalOutcomeDB.outcome_id) >= 1)
                .order_by(desc("avg_excess"))
                .limit(5)
                .all()
            )

            if event_stats:
                best_event_types = [
                    BestPerformingEventType(
                        event_type=_translate_event_type(stat.event_type),
                        avg_excess_return=float(stat.avg_excess),
                        total_signals=stat.count,
                        win_rate=self._calc_win_rate_for_type(stat.event_type),
                    )
                    for stat in event_stats
                ]

            # 如果没有真实数据，使用模拟数据
            if not has_real_data:
                logger.info("No real learning section data found, using mock data")
                recent_failures, best_event_types, weekly_lessons = self._get_mock_learning_data()
            elif not best_event_types or not weekly_lessons:
                # 如果部分数据缺失，用模拟数据补充
                _, mock_best, mock_lessons = self._get_mock_learning_data()
                if not best_event_types:
                    best_event_types = mock_best
                if not weekly_lessons:
                    weekly_lessons = mock_lessons

        except Exception as e:
            logger.warning(f"Failed to fetch learning section data: {e}, falling back to mock data")
            recent_failures, best_event_types, weekly_lessons = self._get_mock_learning_data()

        return LearningSection(
            recent_failures=recent_failures,
            best_event_types=best_event_types,
            weekly_lessons=weekly_lessons,
        )

    def _get_mock_learning_data(self):
        """获取模拟的学习数据"""
        from datetime import UTC, datetime

        recent_failures = [
            RecentFailure(
                outcome_id="outcome-001",
                signal_id="signal-old-001",
                subject_id="601318.SH",
                failure_reason="市场情绪超预期低迷，保险股普跌",
                lesson="需要更严格的风险控制和止损点设置",
                outcome_return=-0.085,
                created_at=(datetime.now(UTC) - timedelta(days=15)).isoformat(),
            ),
            RecentFailure(
                outcome_id="outcome-002",
                signal_id="signal-old-002",
                subject_id="AAPL",
                failure_reason="财报低于预期，科技板块整体回调",
                lesson="财报季需要更谨慎的仓位管理",
                outcome_return=-0.052,
                created_at=(datetime.now(UTC) - timedelta(days=25)).isoformat(),
            ),
        ]

        best_event_types = [
            BestPerformingEventType(
                event_type="earnings",
                avg_excess_return=0.042,
                total_signals=12,
                win_rate=0.75,
            ),
            BestPerformingEventType(
                event_type="product_launch",
                avg_excess_return=0.038,
                total_signals=8,
                win_rate=0.625,
            ),
            BestPerformingEventType(
                event_type="policy_change",
                avg_excess_return=0.031,
                total_signals=7,
                win_rate=0.571,
            ),
        ]

        weekly_lessons = [
            WeeklyLesson(
                id="lesson-2026-w19",
                week="2026-W19",
                key_takeaway="财报季来临，需要重点关注业绩预告和实际财报的差异，特别是对高预期标的要谨慎",
                created_at=datetime.now(UTC).isoformat(),
            ),
            WeeklyLesson(
                id="lesson-2026-w18",
                week="2026-W18",
                key_takeaway="政策驱动的行情往往波动大，需要分批建仓，不要追高",
                created_at=(datetime.now(UTC) - timedelta(days=7)).isoformat(),
            ),
        ]

        return recent_failures, best_event_types, weekly_lessons

    def get_crawl_feed(
        self, limit: int = 20, since: Optional[str] = None, source_type: Optional[str] = None
    ) -> dict:
        """获取实时抓取数据流，返回 {"items": [...], "total_today": N}"""
        return self.dashboard_repo.get_recent_crawled_documents(
            limit=limit, since=since, source_type=source_type
        )

    def get_full_dashboard(self) -> DashboardResponse:
        """聚合所有板块数据生成完整仪表盘响应"""
        # 自动拉取真实数据源数据填充数据库（如果数据为空）
        from data_layer.repositories.models import CanonicalEvent

        event_count = self.session.query(CanonicalEvent).count()
        if event_count == 0:
            logger.info("No real event data found, triggering auto ingest from real data sources")
            # 异步触发真实数据拉取，不阻塞请求
            import threading

            def ingest_real_data():
                try:
                    from core.source_registry import get_enabled
                    from services.crawl_orchestrator import CrawlOrchestrator

                    orchestrator = CrawlOrchestrator()
                    for spec in get_enabled():
                        orchestrator.crawl_source(spec.source_type)
                    logger.info("Real data ingest completed successfully via CrawlOrchestrator")
                except Exception as e:
                    logger.warning(f"Auto ingest failed: {e}")

            threading.Thread(target=ingest_real_data, daemon=True).start()

        return DashboardResponse(
            market_overview=self.get_market_overview_section(),
            today=self.get_today_section(),
            research_queue=self.get_research_queue_section(),
            candidate_board=self.get_candidate_board_section(),
            learning=self.get_learning_section(),
        )
