"""
cls - 财联社电报爬取技能 (CLI 版本)

仅支持 CLI 调用: python cls.py --args
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json
import random
import logging

try:
    import requests
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False


# 输出格式常量（仅保留 JSON）
OUTPUT_FORMAT_JSON = "json"


@dataclass
class TelegramItem:
    """电报条目"""
    id: str = ""
    content: str = ""
    date: str = ""
    day: str = ""
    hour: int = 0
    time: int = 0
    api_date: str = ""


@dataclass
class CLSConfig:
    """财联社爬虫配置"""
    verbose: bool = True
    output_dir: str = "./output"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: int = 2
    start_hour: Optional[int] = None
    end_hour: Optional[int] = None
    output_format: str = OUTPUT_FORMAT_JSON

    # 日志相关配置
    log_to_file: bool = True  # 是否记录日志到文件
    log_filename: Optional[str] = None  # 自定义日志文件名

    # 反爬相关配置
    delay: float = 1.5
    delay_jitter: float = 0.8
    page_delay: float = 1.0
    page_delay_jitter: float = 0.5
    max_retries: int = 3
    retry_delay_min: float = 2.0
    retry_delay_max: float = 5.0

    # 爬取控制
    max_pages: int = 150
    max_empty_pages: int = 7

    # 持久化去重
    state_path: Optional[str] = None  # 状态文件路径
    skip_existing: bool = True  # 是否跳过已存在的电报


# CLSStateManager 已移除，使用通用的 DeduplicationStore


class CLSTelegramCrawler:
    """财联社电报爬虫"""

    def __init__(self, config: Optional[CLSConfig] = None):
        self.config = config or CLSConfig()
        self._initialized = False
        self._session: Optional[requests.Session] = None

        # User-Agent 轮换池（反爬措施）
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        ]

        # API 配置
        self.api_url = "https://www.cls.cn/api/sw"
        self.base_url = "https://www.cls.cn"

        # 数据存储
        self.all_telegrams: List[TelegramItem] = []
        self._seen_telegram_ids: set = set()  # O(1) 去重
        self.daily_telegrams: Dict[str, List[TelegramItem]] = {}
        self.api_day_total: Dict[str, int] = {}

        # 缓存
        self._filtered_telegrams: Optional[List[TelegramItem]] = None
        self._filtered_daily_telegrams: Optional[Dict[str, List[TelegramItem]]] = None

        # 状态管理（使用通用去重存储）
        self.state_manager: Optional[DeduplicationStore] = None
        self.new_telegrams: List[TelegramItem] = []
        self.skipped_count: int = 0

        # 日志
        self.logger: Optional[logging.Logger] = None

    def initialize(self):
        """初始化"""
        if self._initialized:
            return

        if not HAS_DEPENDENCIES:
            raise ImportError("需要安装依赖: pip install requests")

        # 设置日志
        self._setup_logging()

        # 初始化状态管理器（使用通用去重存储）
        if self.config.state_path:
            self.state_manager = DeduplicationStore(self.config.state_path)
            self.logger.info(f"[state] 使用状态文件: {self.config.state_path}")
            self.logger.info(f"[state] 已处理 {self.state_manager.get_count()} 条电报")

        # 创建 session
        self._session = requests.Session()

        # Cookie 预热
        self._warmup_cookies()

        self._initialized = True
        self.logger.info("[init] 初始化完成")

    def _setup_logging(self):
        """设置日志（使用通用工具函数）"""
        self.logger = setup_logging(
            logger_name="cls",
            verbose=self.config.verbose,
            log_to_file=self.config.log_to_file,
            log_filename=self.config.log_filename
        )

    def _warmup_cookies(self):
        """Cookie 预热 - 模拟真实用户访问"""
        self.logger.info("[warmup] 开始 Cookie 预热...")
        try:
            headers = self._get_headers()
            response = self._session.get(self.base_url, headers=headers, timeout=30)
            self.logger.info(f"[warmup] 预热完成, Status: {response.status_code}")
        except Exception as e:
            self.logger.warning(f"[warmup] 预热失败: {e}")

    def _get_headers(self, referer: str = None) -> Dict[str, str]:
        """获取请求头（带随机 User-Agent）"""
        user_agent = random.choice(self.user_agents)
        headers = {
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.base_url,
            "Referer": referer or f"{self.base_url}/telegraph",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive"
        }
        return headers

    def _random_delay(self, is_page_delay: bool = False):
        """随机延迟（反爬措施，使用通用工具函数）"""
        if is_page_delay:
            random_delay(
                base_delay=self.config.page_delay,
                jitter=self.config.page_delay_jitter
            )
        else:
            random_delay(
                base_delay=self.config.delay,
                jitter=self.config.delay_jitter
            )

    def _retry_request(self, url: str, method: str = "get", **kwargs) -> Optional[requests.Response]:
        """带重试的请求（使用通用工具函数）"""
        return retry_request(
            session=self._session,
            url=url,
            method=method,
            max_retries=self.config.max_retries,
            retry_delay_min=self.config.retry_delay_min,
            retry_delay_max=self.config.retry_delay_max,
            **kwargs
        )

    def get_telegram_data(self, date: datetime, page: int = 1) -> Optional[Dict[str, Any]]:
        """获取电报数据"""
        date_str = date.strftime("%Y-%m-%d")
        self.logger.debug(f"[fetch] 获取 {date_str} 第 {page} 页")

        try:
            # 先访问带日期的页面
            page_url = f"{self.base_url}/telegraph?date={date_str}"
            self._session.get(page_url, headers=self._get_headers(page_url), timeout=30)

            headers = self._get_headers(page_url)
            params = {
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.4.6",
                "sign": "9f8797a1f4de66c2370f7a03990d2737"
            }

            data = {
                "type": "telegram",
                "keyword": "%20",  # URL编码空格，绕过keyword非空检查
                "page": page,
                "rn": 100,
                "date": date_str
            }

            response = self._retry_request(
                self.api_url,
                method="post",
                params=params,
                json=data,
                headers=headers,
                timeout=30
            )

            if not response:
                return None

            result = response.json()

            if result.get("errno") != 0:
                self.logger.warning(f"[api] Error: {result.get('msg')}")
                return None

            telegram_list = result.get("data", {}).get("telegram", {}).get("data", [])
            total_num = result.get("data", {}).get("telegram", {}).get("total_num", 0)

            if date_str not in self.api_day_total:
                self.api_day_total[date_str] = total_num
                self.logger.info(f"[api] {date_str} 总计 {total_num} 条电报")

            new_count = 0
            for item in telegram_list:
                telegram = self._parse_telegram(item, date_str)
                if telegram:
                    self._add_telegram(telegram)
                    new_count += 1

            return {
                "total_num": total_num,
                "new_count": new_count
            }

        except Exception as e:
            self.logger.exception(f"[fetch] Error: {e}")
            return None

    def _parse_telegram(self, item: Dict[str, Any], api_date: str) -> Optional[TelegramItem]:
        """解析电报条目"""
        try:
            telegram = TelegramItem()
            telegram.id = str(item.get("id", ""))
            # API 返回的是 descr 字段，包含 <em> 高亮标签，需要清理
            content = item.get("descr", "").strip()
            content = content.replace("<em>", "").replace("</em>", "")
            telegram.content = content
            telegram.api_date = api_date

            # 解析时间
            time_str = item.get("time", "")
            if time_str:
                dt = datetime.fromtimestamp(int(time_str))
                telegram.date = dt.strftime("%Y-%m-%d %H:%M:%S")
                telegram.day = dt.strftime("%Y-%m-%d")
                telegram.hour = dt.hour
                telegram.time = int(time_str)
            else:
                telegram.day = api_date

            return telegram if telegram.content else None

        except Exception as e:
            self.logger.warning(f"[parse] Error: {e}")
            return None

    def _add_telegram(self, telegram: TelegramItem):
        """添加电报"""
        # O(1) 去重
        if telegram.id in self._seen_telegram_ids:
            return
        self._seen_telegram_ids.add(telegram.id)

        self.all_telegrams.append(telegram)

        if telegram.day not in self.daily_telegrams:
            self.daily_telegrams[telegram.day] = []
        self.daily_telegrams[telegram.day].append(telegram)

        # 持久化去重检查（使用通用去重存储）
        if self.state_manager:
            if self.state_manager.is_processed(telegram.id):
                if self.config.skip_existing:
                    self.skipped_count += 1
                    return
            else:
                self.new_telegrams.append(telegram)
                self.state_manager.mark_processed(
                    telegram.id,
                    content_preview=telegram.content
                )

        # 清除缓存
        self._filtered_telegrams = None
        self._filtered_daily_telegrams = None

    def _filter_telegrams(self, telegrams: List[TelegramItem]) -> List[TelegramItem]:
        """过滤电报"""
        filtered = []

        for t in telegrams:
            # 小时过滤
            if self.config.start_hour is not None and t.hour < self.config.start_hour:
                continue
            if self.config.end_hour is not None and t.hour > self.config.end_hour:
                continue

            filtered.append(t)

        return filtered

    def get_filtered_telegrams(self) -> List[TelegramItem]:
        """获取缓存的过滤后电报"""
        if self._filtered_telegrams is None:
            self._filtered_telegrams = self._filter_telegrams(self.all_telegrams)
        return self._filtered_telegrams

    def get_filtered_daily_telegrams(self) -> Dict[str, List[TelegramItem]]:
        """获取缓存的按天过滤后电报"""
        if self._filtered_daily_telegrams is None:
            self._filtered_daily_telegrams = {}
            for date_str, telegrams in self.daily_telegrams.items():
                self._filtered_daily_telegrams[date_str] = self._filter_telegrams(telegrams)
        return self._filtered_daily_telegrams

    def _get_output_folder(self) -> Path:
        """获取输出文件夹路径"""
        folder = Path(self.config.output_dir) / f"{self.config.start_date}_{self.config.end_date}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _get_output_filename(self, extension: str) -> str:
        """获取输出文件名"""
        return f"clstelegram.{extension}"

    def _parse_and_validate_dates(self) -> tuple:
        """统一解析和验证日期（使用通用工具函数）"""
        start_date, end_date = parse_and_validate_date_range(
            start_date_str=self.config.start_date,
            end_date_str=self.config.end_date,
            default_days=self.config.days
        )
        # 更新配置中的日期字符串
        self.config.start_date = start_date.strftime("%Y-%m-%d")
        self.config.end_date = end_date.strftime("%Y-%m-%d")
        return start_date, end_date

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要信息"""
        filtered = self.get_filtered_telegrams()
        filtered_daily = self.get_filtered_daily_telegrams()

        daily_counts = {}
        for date_str in sorted(filtered_daily.keys()):
            daily_counts[date_str] = len(filtered_daily[date_str])

        return {
            "total_telegrams": len(filtered),
            "total_crawled": len(self.all_telegrams),
            "date_range": f"{self.config.start_date} 至 {self.config.end_date}",
            "daily_counts": daily_counts
        }

    def crawl_telegrams(self):
        """爬取指定日期范围的电报"""
        if not self._initialized:
            self.initialize()

        start_date, end_date = self._parse_and_validate_dates()

        self.logger.info(f"===== 开始爬取 {self.config.start_date} 至 {self.config.end_date} 的电报 =====")

        current_date = end_date
        total_telegrams = 0

        while current_date >= start_date:
            self._get_all_day_telegrams(current_date)
            current_date -= timedelta(days=1)
            if current_date >= start_date:
                self._random_delay(is_page_delay=True)

        for date_str, day_telegrams in sorted(self.daily_telegrams.items()):
            if day_telegrams:
                total_telegrams += len(day_telegrams)
                self.logger.info(f"[daily] {date_str}: {len(day_telegrams)} 条")

        self.logger.info(f"[summary] 爬取完成，共处理 {total_telegrams} 条不重复电报")

    def _get_all_day_telegrams(self, date: datetime):
        """获取指定日期的所有电报"""
        date_str = date.strftime("%Y-%m-%d")
        self.logger.info(f"===== 开始获取 {date_str} 的全部电报 =====")

        page = 1
        consecutive_empty_pages = 0
        last_all_telegrams_count = len(self.all_telegrams)

        while page <= self.config.max_pages:
            self.logger.info(f"[page] 正在获取第 {page} 页...")

            result = self.get_telegram_data(date, page)
            if not result:
                self.logger.warning(f"[page] 第 {page} 页获取失败，尝试下一页")
                page += 1
                self._random_delay(is_page_delay=True)
                continue

            total_num = result["total_num"]
            new_count = result["new_count"]

            current_all_telegrams_count = len(self.all_telegrams)
            if new_count == 0 or current_all_telegrams_count == last_all_telegrams_count:
                consecutive_empty_pages += 1
                self.logger.info(f"[page] 连续 {consecutive_empty_pages} 页无新数据")
                if consecutive_empty_pages >= self.config.max_empty_pages:
                    self.logger.info(f"[page] 已连续 {self.config.max_empty_pages} 页无新数据，结束爬取")
                    break
            else:
                consecutive_empty_pages = 0
                last_all_telegrams_count = current_all_telegrams_count

            page += 1

            # 检查是否已获取足够数据
            telegrams_for_this_date = len(self.daily_telegrams.get(date_str, []))
            if telegrams_for_this_date >= total_num + 20:
                self.logger.info(f"[complete] 已获取足够电报 ({telegrams_for_this_date}/{total_num})")
                break

            if page > (total_num // 30 + 10) and consecutive_empty_pages > 2:
                completion_rate = (telegrams_for_this_date / total_num * 100) if total_num > 0 else 0
                self.logger.info(f"[complete] 超过预计页数，完成率: {completion_rate:.2f}%")
                break

            if page <= self.config.max_pages:
                self._random_delay(is_page_delay=True)

        day_telegrams = self.daily_telegrams.get(date_str, [])
        api_total = self.api_day_total.get(date_str, 0)
        completion_rate = (len(day_telegrams) / api_total * 100) if api_total > 0 else 0

        self.logger.info(f"[summary] {date_str} 完成: {len(day_telegrams)}/{api_total} 条 ({completion_rate:.2f}%)")

    def save_to_json(self) -> str:
        """保存到 JSON"""
        filtered_telegrams = self.get_filtered_telegrams()
        filtered_daily = self.get_filtered_daily_telegrams()

        output_folder = self._get_output_folder()
        json_path = str(output_folder / self._get_output_filename("json"))

        # 构建 JSON 数据
        json_data = {
            "metadata": {
                "crawl_time": datetime.now().isoformat(),
                "start_date": self.config.start_date,
                "end_date": self.config.end_date,
                "total_telegrams": len(filtered_telegrams),
                "total_crawled": len(self.all_telegrams),
                "output_format": "json"
            },
            "telegrams": [
                {
                    "id": t.id,
                    "content": t.content,
                    "date": t.date
                } for t in filtered_telegrams
            ],
            "daily_stats": []
        }

        # 添加每日统计
        for date_str in sorted(filtered_daily.keys()):
            day_telegrams = filtered_daily[date_str]
            if day_telegrams:
                json_data["daily_stats"].append({
                    "日期": date_str,
                    "电报数量": len(day_telegrams)
                })

        # 保存 JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"[save] JSON 已保存: {json_path}")
        return json_path

    def execute(self) -> Dict[str, Any]:
        """执行爬取"""
        self.crawl_telegrams()
        summary = self.get_summary()

        # 保存 JSON 文件
        output_files = {}
        json_path = self.save_to_json()
        output_files["json"] = json_path

        return {
            "success": True,
            "total_telegrams": summary["total_telegrams"],
            "total_crawled": summary["total_crawled"],
            "new_telegrams": len(self.new_telegrams),
            "skipped_existing": self.skipped_count,
            "date_range": summary["date_range"],
            "daily_counts": summary["daily_counts"],
            "output_file": json_path,
            "output_files": output_files,
            "errors": []
        }


from .utils.log_utils import setup_logging
from .utils.net_utils import random_delay, retry_request
from .utils.date_utils import parse_and_validate_date_range
from .utils.deduplication import DeduplicationStore

# ============================================================
# 仅支持 CLI 调用
# ============================================================

def parse_args():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='财联社电报爬虫 - 爬取财联社电报新闻',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本使用（爬取最近2天）
  python cls.py

  # 指定日期范围
  python cls.py --start_date 2026-04-01 --end_date 2026-04-15

  # 启用持久化去重
  python cls.py --state_path ./state/cls_telegrams.json
        """
    )

    # 日期参数
    parser.add_argument('--start_date', type=str, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end_date', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=2, help='默认爬取天数（未指定日期时）')

    # 过滤参数
    parser.add_argument('--start_hour', type=int, help='起始小时 (0-23)')
    parser.add_argument('--end_hour', type=int, help='结束小时 (0-23)')

    # 输出参数
    parser.add_argument('--output_dir', type=str, default='./output', help='输出目录')

    # 反爬参数
    parser.add_argument('--delay', type=float, default=1.5, help='基础请求延迟（秒）')
    parser.add_argument('--delay_jitter', type=float, default=0.8, help='延迟抖动范围（秒）')
    parser.add_argument('--max_retries', type=int, default=3, help='最大重试次数')
    parser.add_argument('--max_pages', type=int, default=150, help='最大爬取页数')
    parser.add_argument('--max_empty_pages', type=int, default=7, help='连续空页阈值')

    # 持久化去重
    parser.add_argument('--state_path', type=str, help='状态文件路径（用于持久化去重）')
    parser.add_argument('--skip_existing', action='store_true', default=True,
                        help='跳过已存在的电报（默认启用）')

    # 日志参数
    parser.add_argument('--verbose', action='store_true', default=True, help='显示详细日志')
    parser.add_argument('--log_to_file', action='store_true', default=True, help='记录日志到文件')
    parser.add_argument('--log_filename', type=str, help='自定义日志文件名')

    return parser.parse_args()


def args_to_config(args) -> CLSConfig:
    """将 argparse Namespace 转换为配置对象"""
    config = CLSConfig()

    # 日期参数
    if args.start_date:
        config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    config.days = args.days

    # 小时范围
    if args.start_hour is not None:
        config.start_hour = args.start_hour
    if args.end_hour is not None:
        config.end_hour = args.end_hour

    # 输出参数
    config.output_dir = args.output_dir

    # 反爬参数
    config.delay = args.delay
    config.delay_jitter = args.delay_jitter
    config.max_retries = args.max_retries
    config.max_pages = args.max_pages
    config.max_empty_pages = args.max_empty_pages

    # 持久化去重
    if args.state_path:
        config.state_path = args.state_path
    config.skip_existing = args.skip_existing

    # 日志参数
    config.verbose = args.verbose
    config.log_to_file = args.log_to_file
    if args.log_filename:
        config.log_filename = args.log_filename

    return config


def main():
    """CLI 主入口"""
    args = parse_args()
    config = args_to_config(args)

    print("\n" + "=" * 60)
    print("财联社电报爬虫 (仅 CLI 版本)")
    print("=" * 60)

    # 创建爬虫实例并执行
    crawler = CLSTelegramCrawler(config)
    result = crawler.execute()

    print("\n" + "=" * 60)
    if result.get("success"):
        print("爬取完成!")
        print(f"  总电报数: {result.get('total_telegrams', 0)}")
        print(f"  实际爬取: {result.get('total_crawled', 0)}")
        if 'new_telegrams' in result:
            print(f"  新电报: {result['new_telegrams']}")
        if 'skipped_existing' in result:
            print(f"  跳过已有: {result['skipped_existing']}")
        print(f"  日期范围: {result.get('date_range', '')}")
        if result.get('output_files'):
            for fmt, path in result['output_files'].items():
                print(f"  {fmt.upper()}文件: {path}")
    else:
        print("爬取失败!")
        if result.get('errors'):
            print(f"  错误: {result['errors']}")
    print("=" * 60 + "\n")

    return result


if __name__ == "__main__":
    main()
