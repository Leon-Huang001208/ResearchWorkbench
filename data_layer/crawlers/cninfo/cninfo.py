"""巨潮资讯网（Cninfo）爬虫模块

数据来源: https://www.cninfo.com.cn/
API 接口: cninfo 公告搜索 API (POST)

支持:
- 日期范围爬取
- 多板块（深市/沪市/北交所/全部）
- 多公告类别（年报/半年报/季报/招股书）
- 分页爬取
- 基本限速
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Any

from core.observability import get_logger

logger = get_logger(__name__)

HAS_DEPENDENCIES = False
try:
    import requests as req_lib

    HAS_DEPENDENCIES = True
except ImportError:
    req_lib = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# API 常量
# ---------------------------------------------------------------------------

CNINFO_SEARCH_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"

# 板块 → API column 参数映射
CNINFO_PLATES: dict[str, str] = {
    "szse": "szse",
    "sse": "sse",
    "bjse": "bjse",
    "all": "",
}

# 公告类别 → API category 参数映射
CNINFO_CATEGORIES: dict[str, str] = {
    "annual_report": "category_ndbg_szsh",
    "semi_annual": "category_bndbg_szsh",
    "quarterly": "category_yjdbg_szsh",
    "prospectus": "category_zhaoshu_szsh",
    "all": "",
}


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


@dataclass
class CninfoConfig:
    """爬虫配置"""

    verbose: bool = True
    page_size: int = 30
    max_pages: int = 5
    timeout: int = 30
    delay: float = 0.5
    start_date: str | None = None
    end_date: str | None = None
    plate: str = ""
    column: str = ""
    category: str = ""
    stock: str = ""
    output_dir: str = "./data/crawlers/cninfo"


# ---------------------------------------------------------------------------
# 爬虫
# ---------------------------------------------------------------------------


class CninfoCrawler:
    """巨潮资讯网公告爬虫.

    通过 cninfo 搜索 API 获取上市公司公告列表。
    """

    def __init__(self, config: CninfoConfig | None = None):
        """初始化爬虫.

        Args:
            config: 爬虫配置，为 None 时使用默认配置。
        """
        self.config = config or CninfoConfig()
        self._session: Any = None

    # ------------------------------------------------------------------
    # 核心入口
    # ------------------------------------------------------------------

    def execute(self) -> dict[str, Any]:
        """执行爬取，返回结果字典.

        Returns:
            dict with keys:
                - success: bool
                - announcements: list[dict] — 公告列表
                - total_count: int
                - elapsed_seconds: float
                - errors: list[dict]
        """
        start_time = time.time()
        errors: list[dict[str, Any]] = []

        try:
            self._initialize()
            announcements = self._crawl_all()

            elapsed = time.time() - start_time
            result = {
                "success": True,
                "announcements": announcements,
                "total_count": len(announcements),
                "elapsed_seconds": round(elapsed, 1),
                "errors": errors,
            }
            if self.config.verbose:
                logger.info(
                    f"Cninfo crawl completed: {len(announcements)} announcements "
                    f"in {elapsed:.1f}s, {len(errors)} errors"
                )
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Cninfo crawl failed after {elapsed:.1f}s: {e}", exc_info=True)
            return {
                "success": False,
                "announcements": [],
                "total_count": 0,
                "elapsed_seconds": round(elapsed, 1),
                "message": str(e),
                "errors": errors,
            }

    def _initialize(self) -> None:
        """初始化 HTTP 会话."""
        if self._session is not None:
            return

        if not HAS_DEPENDENCIES:
            raise ImportError("requests is required for CninfoCrawler. pip install requests")

        self._session = req_lib.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.cninfo.com.cn/",
            }
        )

    # ------------------------------------------------------------------
    # 爬取循环
    # ------------------------------------------------------------------

    def _crawl_all(self) -> list[dict[str, Any]]:
        """分页爬取所有公告.

        Returns:
            公告字典列表。
        """
        all_announcements: list[dict[str, Any]] = []

        for page in range(1, self.config.max_pages + 1):
            result = self._post_search(page)
            if result is None:
                break

            announcements = result.get("announcements") or []
            if not announcements:
                break

            all_announcements.extend(announcements)

            total_pages = result.get("totalpages", 0)
            if page >= total_pages:
                break

            # 限速
            if page < self.config.max_pages:
                time.sleep(self.config.delay)

        return all_announcements

    def _post_search(self, page_num: int) -> dict[str, Any] | None:
        """发送单页搜索请求.

        Args:
            page_num: 页码（从 1 开始）.

        Returns:
            API 响应 JSON dict，失败时返回 None。
        """
        se_date = ""
        if self.config.start_date and self.config.end_date:
            se_date = f"{self.config.start_date}~{self.config.end_date}"

        form_data = {
            "pageNum": page_num,
            "pageSize": self.config.page_size,
            "column": self.config.column,
            "tabName": "fulltext",
            "plate": "",
            "stock": self.config.stock,
            "searchkey": "",
            "secid": "",
            "category": self.config.category,
            "trade": "",
            "seDate": se_date,
        }

        try:
            resp = self._session.post(
                CNINFO_SEARCH_URL,
                data=form_data,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except Exception as e:
            logger.warning(
                "cninfo_crawl_page_failed",
                extra={"page": page_num, "error": str(e)},
            )
            return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cninfo_main() -> None:
    """CLI 入口 — 独立运行 cninfo 爬虫."""
    parser = argparse.ArgumentParser(description="巨潮资讯网公告爬虫")
    parser.add_argument("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument(
        "--plate", type=str, default="all", choices=["szse", "sse", "bjse", "all"], help="板块过滤"
    )
    parser.add_argument(
        "--category",
        type=str,
        default="all",
        choices=["annual_report", "semi_annual", "quarterly", "prospectus", "all"],
        help="公告类别",
    )
    parser.add_argument("--stock", type=str, default="", help="股票代码过滤")
    parser.add_argument("--max-pages", type=int, default=5, help="最大翻页数")
    parser.add_argument("--page-size", type=int, default=30, help="每页公告数")
    parser.add_argument("--output-dir", type=str, default="./data/crawlers/cninfo", help="输出目录")

    args = parser.parse_args()

    column = CNINFO_PLATES.get(args.plate, "")
    category = CNINFO_CATEGORIES.get(args.category, "")

    config = CninfoConfig(
        verbose=True,
        start_date=args.start_date,
        end_date=args.end_date,
        plate=args.plate,
        column=column,
        category=category,
        stock=args.stock,
        max_pages=args.max_pages,
        page_size=args.page_size,
        output_dir=args.output_dir,
    )

    crawler = CninfoCrawler(config)
    result = crawler.execute()

    print(f"\nDone: {result['total_count']} announcements, success={result['success']}")
    if result.get("errors"):
        print(f"Errors: {len(result['errors'])}")


if __name__ == "__main__":
    cninfo_main()
