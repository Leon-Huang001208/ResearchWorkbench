"""
cls - 财联社电报爬取技能 (CLI 版本)

仅支持 CLI 调用: python cls.py --args
"""
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    # 增量抓取模式（使用 updateTelegraphList API — 返回全部电报的唯一可靠API）
    use_incremental: bool = True  # True=增量模式(updateTelegraphList), False=全量历史模式(POST /api/sw)

    # 持久化去重
    state_path: Optional[str] = None  # 状态文件路径
    skip_existing: bool = True  # 是否跳过已存在的电报
    stop_on_known: bool = True  # 遇到已知电报时停止（水位线功能）


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
        self.update_api_url = "https://www.cls.cn/nodeapi/updateTelegraphList"
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
            log_filename=self.config.log_filename,
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
            "Connection": "keep-alive",
        }
        return headers

    def _random_delay(self, is_page_delay: bool = False):
        """随机延迟（反爬措施，使用通用工具函数）"""
        if is_page_delay:
            random_delay(base_delay=self.config.page_delay, jitter=self.config.page_delay_jitter)
        else:
            random_delay(base_delay=self.config.delay, jitter=self.config.delay_jitter)

    def _retry_request(
        self, url: str, method: str = "get", **kwargs
    ) -> Optional[requests.Response]:
        """带重试的请求（使用通用工具函数）"""
        return retry_request(
            session=self._session,
            url=url,
            method=method,
            max_retries=self.config.max_retries,
            retry_delay_min=self.config.retry_delay_min,
            retry_delay_max=self.config.retry_delay_max,
            **kwargs,
        )

    def get_telegram_data(self, date: datetime, page: int = 1) -> Optional[Dict[str, Any]]:
        """获取电报数据（rn=100 最旧优先）"""
        date_str = date.strftime("%Y-%m-%d")
        self.logger.debug(f"[fetch] 获取 {date_str} 第 {page} 页")

        try:
            page_url = f"{self.base_url}/telegraph?date={date_str}"
            self._session.get(page_url, headers=self._get_headers(page_url), timeout=30)

            headers = self._get_headers(page_url)
            params = {
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.4.6",
                "sign": "9f8797a1f4de66c2370f7a03990d2737",
            }

            data = {
                "type": "telegram",
                "keyword": "日",  # 每条CLS电报日期行都包含"日"，覆盖率最高(1.47M vs 1.36M)
                "page": page,
                "rn": 100,  # 100=最旧优先(全部电报), 10=最新优先(精选电报)
                "date": date_str,
            }

            response = self._retry_request(
                self.api_url, method="post", params=params, json=data, headers=headers, timeout=30
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

            # ============================================================
            # 检查是否遇到已知的电报
            # ============================================================
            found_known_telegram = None
            parsed_telegrams = []
            for item in telegram_list:
                telegram = self._parse_telegram(item, date_str)
                if telegram:
                    parsed_telegrams.append(telegram)
                    if self.state_manager and self.state_manager.is_processed(telegram.id):
                        found_known_telegram = telegram
                        self.logger.info(
                            f"[watermark] 检测到已知电报: {telegram.id} - {telegram.content[:50]}..."
                        )
                        break

            new_count = 0
            if found_known_telegram and self.config.stop_on_known:
                # 遇到已知的，只添加之前的
                for telegram in parsed_telegrams:
                    if telegram.id == found_known_telegram.id:
                        break
                    self._add_telegram(telegram)
                    new_count += 1
            else:
                # 没有遇到已知的，全部添加
                for telegram in parsed_telegrams:
                    self._add_telegram(telegram)
                    new_count += 1

            return {
                "total_num": total_num,
                "new_count": new_count,
                "found_known": found_known_telegram is not None,
                "known_telegram_id": found_known_telegram.id if found_known_telegram else None,
            }

        except Exception as e:
            self.logger.exception(f"[fetch] Error: {e}")
            return None

    def _parse_telegram(self, item: Dict[str, Any], api_date: str) -> Optional[TelegramItem]:
        """解析电报条目（兼容 POST /api/sw 和 updateTelegraphList 两种格式）"""
        try:
            telegram = TelegramItem()
            telegram.id = str(item.get("id", ""))

            # 格式检测：updateTelegraphList 用 ctime 字段，POST /api/sw 用 time 字段
            is_update_format = "ctime" in item and "brief" in item

            if is_update_format:
                # updateTelegraphList 格式：优先用 content，fallback 到 brief
                raw = (item.get("content") or item.get("brief", "")).strip()
                if raw.startswith("【") and "】" in raw:
                    # 检查 brief 是否更完整（不含省略号）
                    brief = item.get("brief", "").strip()
                    if brief and not brief.endswith("…") and not brief.endswith("..."):
                        raw = brief
                content = raw.replace("<em>", "").replace("</em>", "")
                telegram.content = content

                ctime = item.get("ctime", 0)
                if ctime:
                    dt = datetime.fromtimestamp(int(ctime))
                    telegram.date = dt.strftime("%Y-%m-%d %H:%M:%S")
                    telegram.day = dt.strftime("%Y-%m-%d")
                    telegram.hour = dt.hour
                    telegram.time = int(ctime)
                else:
                    telegram.day = api_date
                    telegram.date = f"{api_date} 00:00:00"
            else:
                # POST /api/sw 格式（descr + time）
                content = item.get("descr", "").strip()
                content = content.replace("<em>", "").replace("</em>", "")
                telegram.content = content

                time_str = item.get("time", "")
                if time_str:
                    dt = datetime.fromtimestamp(int(time_str))
                    telegram.date = dt.strftime("%Y-%m-%d %H:%M:%S")
                    telegram.day = dt.strftime("%Y-%m-%d")
                    telegram.hour = dt.hour
                    telegram.time = int(time_str)
                else:
                    telegram.day = api_date
                    telegram.date = f"{api_date} 00:00:00"

            telegram.api_date = api_date
            return telegram if telegram.content else None

        except Exception as e:
            self.logger.warning(f"[parse] Error: {e}")
            return None

    def _get_update_telegrams(self, last_time: str = "0") -> Optional[Dict[str, Any]]:
        """通过 updateTelegraphList API 获取增量电报（返回全部电报，非精选）"""
        self.logger.debug(f"[update_api] 获取 updateTelegraphList, lastTime={last_time}")

        try:
            headers = self._get_headers(f"{self.base_url}/telegraph")
            params = {
                "rn": 50,
                "os": "web",
                "sv": "8.4.6",
                "lastTime": last_time,
            }

            response = self._retry_request(
                self.update_api_url, method="get", params=params, headers=headers, timeout=30
            )

            if not response:
                return None

            result = response.json()

            if result.get("error") != 0:
                self.logger.warning(f"[update_api] Error: {result}")
                return None

            roll_data = result.get("data", {}).get("roll_data", [])
            if not roll_data:
                self.logger.info("[update_api] 无新电报")
                return {"items": [], "latest_ctime": None, "count": 0}

            today_str = datetime.now().strftime("%Y-%m-%d")
            parsed = []
            seen = set()
            latest_ctime = 0

            for item in roll_data:
                telegram = self._parse_telegram(item, today_str)
                if telegram and telegram.id not in seen:
                    seen.add(telegram.id)
                    parsed.append(telegram)
                    if telegram.time > latest_ctime:
                        latest_ctime = telegram.time

            self.logger.info(f"[update_api] 获取 {len(parsed)} 条电报, latest_ctime={latest_ctime}")

            return {
                "items": parsed,
                "latest_ctime": str(latest_ctime) if latest_ctime else None,
                "count": len(parsed),
            }

        except Exception as e:
            self.logger.exception(f"[update_api] Error: {e}")
            return None

    def _crawl_incremental(self) -> int:
        """增量抓取：使用 updateTelegraphList，只拉取上次以来的新电报"""
        # 从状态文件读取上次的 lastTime
        last_time = "0"
        if self.state_manager:
            wm = self.state_manager.get_watermark("cls:lastTime")
            if wm:
                last_time = str(wm.get("last_seen_id", "0"))

        self.logger.info(f"[incremental] 增量抓取, lastTime={last_time}")

        result = self._get_update_telegrams(last_time)
        if not result or not result.get("items"):
            return 0

        items = result["items"]
        latest_ctime = result.get("latest_ctime")

        new_count = 0
        for telegram in items:
            if self.state_manager and self.state_manager.is_processed(telegram.id):
                self.skipped_count += 1
                continue
            self._add_telegram(telegram)
            new_count += 1

        # 更新 lastTime 水位线
        if latest_ctime and self.state_manager:
            self.state_manager.set_watermark("cls:lastTime", latest_ctime)
            self.logger.info(f"[incremental] 更新 lastTime={latest_ctime}")

        self.logger.info(f"[incremental] 完成: {new_count} 条新增, {self.skipped_count} 条跳过")
        return new_count

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
                self.state_manager.mark_processed(telegram.id, content_preview=telegram.content)

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
            default_days=self.config.days,
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
            "daily_counts": daily_counts,
        }

    def crawl_telegrams(self):
        """爬取指定日期范围的电报"""
        if not self._initialized:
            self.initialize()

        if self.config.use_incremental:
            self._crawl_incremental()
            return

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
        """获取指定日期的所有电报（rn=100 最旧优先，逐页向后抓取全部电报）"""
        date_str = date.strftime("%Y-%m-%d")
        self.logger.info(f"===== 开始获取 {date_str} 的全部电报 =====")

        # Step 1: 探页获取 total_num（rn=100 最旧优先）
        probe_params = {
            "app": "CailianpressWeb",
            "os": "web",
            "sv": "8.4.6",
            "sign": "9f8797a1f4de66c2370f7a03990d2737",
        }
        probe_data = {"type": "telegram", "keyword": "日", "page": 1, "rn": 100, "date": date_str}
        probe_headers = self._get_headers(f"{self.base_url}/telegraph?date={date_str}")

        response = self._retry_request(
            self.api_url,
            method="post",
            params=probe_params,
            json=probe_data,
            headers=probe_headers,
            timeout=30,
        )
        if not response:
            self.logger.warning(f"[page] 探页失败，无法获取 {date_str}")
            return

        probe_result = response.json()
        if probe_result.get("errno") != 0:
            self.logger.warning(f"[api] 探页 Error: {probe_result.get('msg')}")
            return

        total_num = probe_result.get("data", {}).get("telegram", {}).get("total_num", 0)
        probe_list = probe_result.get("data", {}).get("telegram", {}).get("data", [])
        items_per_page = len(probe_list) if probe_list else 30  # CLS API 每页最多 30 条

        if date_str not in self.api_day_total:
            self.api_day_total[date_str] = total_num
            self.logger.info(f"[api] {date_str} 总计 {total_num} 条电报")

        # CLS API rn=100 → page 1 = 最旧条目，逐页递增 → 越来越新
        max_page = min(
            (total_num + items_per_page - 1) // items_per_page if items_per_page > 0 else 1,
            self.config.max_pages,
        )

        self.logger.info(f"[page] 从第1页(最旧)往后抓取, " f"每页~{items_per_page}条, 最多{max_page}页")

        # Step 2: 从第1页往后迭代（page 1 = 最旧电报）
        watermark_key = f"cls:{date_str}"
        stopped_by_watermark = False
        first_new_telegram_id: Optional[str] = None
        consecutive_known_pages = 0

        for page in range(1, max_page + 1):
            self.logger.info(f"[page] 正在获取第 {page}/{max_page} 页...")

            result = self.get_telegram_data(date, page)
            if not result:
                self.logger.warning(f"[page] 第 {page} 页获取失败")
                continue

            new_count = result["new_count"]
            found_known = result.get("found_known", False)
            known_telegram_id = result.get("known_telegram_id")

            # 水位线（最旧优先：遇到已知条目只记录，不停止，因为后续页可能有更新的未知条目）
            if found_known and self.config.stop_on_known and self.state_manager:
                self.logger.info(f"[watermark] 遇到已知电报: {known_telegram_id}")
                if self.new_telegrams and first_new_telegram_id is None:
                    first_new_telegram_id = self.new_telegrams[0].id
                stopped_by_watermark = True

            if self.new_telegrams and first_new_telegram_id is None:
                first_new_telegram_id = self.new_telegrams[0].id

            if stopped_by_watermark:
                if first_new_telegram_id:
                    self.state_manager.set_watermark(watermark_key, first_new_telegram_id)
                    self.logger.info(f"[watermark] 已更新水位线: {first_new_telegram_id}")
                break

            # 整页无新数据 → 更旧的页大概率也都是已知的
            if new_count == 0:
                consecutive_known_pages += 1
                self.logger.info(f"[page] 第 {page} 页无新数据 (连续{consecutive_known_pages}页)")
                if consecutive_known_pages >= self.config.max_empty_pages:
                    self.logger.info(f"[page] 已连续 {consecutive_known_pages} 页无新数据，停止")
                    break
            else:
                consecutive_known_pages = 0

            self._random_delay(is_page_delay=True)

        day_telegrams = self.daily_telegrams.get(date_str, [])
        api_total = self.api_day_total.get(date_str, 0)
        completion_rate = (len(day_telegrams) / api_total * 100) if api_total > 0 else 0

        stop_reason = "遇到水位线停止" if stopped_by_watermark else "正常完成"
        self.logger.info(
            f"[summary] {date_str} 完成: {len(day_telegrams)}/{api_total} 条 "
            f"({completion_rate:.2f}%) - {stop_reason}"
        )

    def save_to_json(self) -> str:
        """保存到 JSON"""
        filtered_telegrams = self.get_filtered_telegrams()
        filtered_daily = self.get_filtered_daily_telegrams()

        # 如果过滤后为空但实际有数据，跳过缓存直接使用全部电报
        if not filtered_telegrams and self.all_telegrams:
            self.logger.warning(
                f"[save] 过滤后为空但实际有 {len(self.all_telegrams)} 条, "
                f"start_hour={self.config.start_hour}, end_hour={self.config.end_hour}, "
                f"跳过过滤器直接保存"
            )
            filtered_telegrams = self.all_telegrams
            filtered_daily = self.daily_telegrams

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
                "output_format": "json",
            },
            "telegrams": [
                {"id": t.id, "content": t.content, "date": t.date} for t in filtered_telegrams
            ],
            "daily_stats": [],
        }

        # 添加每日统计
        for date_str in sorted(filtered_daily.keys()):
            day_telegrams = filtered_daily[date_str]
            if day_telegrams:
                json_data["daily_stats"].append({"日期": date_str, "电报数量": len(day_telegrams)})

        # 保存 JSON
        with open(json_path, "w", encoding="utf-8") as f:
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
            "errors": [],
        }


@dataclass
class DeepBackfillState:
    """深度回补游标状态"""

    current_id: int = 0
    direction: str = "backward"
    total_scanned: int = 0
    total_saved: int = 0
    total_miss: int = 0
    last_updated: str = ""
    batch_cooldown_until: Optional[str] = None


class CLSDeepBackfill:
    """CLS 深度历史回补 — 通过 /detail/{id} 逐条获取历史电报

    设计要点：
    - 从高 ID 向低 ID 递减扫描（先获取最近的）
    - 每个请求之间随机延迟 2-5 秒
    - 每 50 次扫描后冷却 3-5 分钟
    - 游标持久化到 JSON 文件，重启后继续
    - 只保存 type=-1（电报），跳过其他类型
    """

    def __init__(
        self,
        state_path: str = "./data/crawlers/cls/.deep_backfill_state.json",
        start_id: Optional[int] = None,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        cooldown_interval: int = 50,
        cooldown_min: float = 180.0,
        cooldown_max: float = 300.0,
        verbose: bool = True,
    ):
        self.state_path = Path(state_path)
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.cooldown_interval = cooldown_interval
        self.cooldown_min = cooldown_min
        self.cooldown_max = cooldown_max
        self.verbose = verbose

        self._session: Optional[requests.Session] = None
        self._initialized: bool = False

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        ]

        # 加载或创建游标
        self.state = self._load_state(start_id)

        # 日志
        if verbose:
            self.logger = setup_logging(logger_name="cls_deep_backfill", verbose=verbose)
        else:
            self.logger = logging.getLogger("cls_deep_backfill")

    def _load_state(self, start_id: Optional[int] = None) -> DeepBackfillState:
        """加载游标状态，如不存在则创建"""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = DeepBackfillState(
                    current_id=data.get("current_id", 0),
                    direction=data.get("direction", "backward"),
                    total_scanned=data.get("total_scanned", 0),
                    total_saved=data.get("total_saved", 0),
                    total_miss=data.get("total_miss", 0),
                    last_updated=data.get("last_updated", ""),
                    batch_cooldown_until=data.get("batch_cooldown_until"),
                )
                self.logger.info(
                    f"[deep_backfill] 加载游标: current_id={state.current_id}, scanned={state.total_scanned}, saved={state.total_saved}"
                )
                return state
            except Exception:
                self.logger.warning("[deep_backfill] 游标文件损坏，重新创建")

        # 新游标：从指定 ID 或估算的当前最高 ID 开始
        if start_id is None:
            start_id = self._estimate_current_max_id()
        return DeepBackfillState(current_id=start_id, direction="backward")

    @staticmethod
    def _estimate_current_max_id() -> int:
        """估算当前最高 article ID（基于日期推算）"""
        from datetime import datetime as dt

        days_since = (dt.now() - dt(2014, 3, 30)).days
        return int(250 + days_since * 575)  # ~575 IDs/day average

    def _save_state(self) -> None:
        """持久化游标状态"""
        self.state.last_updated = datetime.now().isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "current_id": self.state.current_id,
                    "direction": self.state.direction,
                    "total_scanned": self.state.total_scanned,
                    "total_saved": self.state.total_saved,
                    "total_miss": self.state.total_miss,
                    "last_updated": self.state.last_updated,
                    "batch_cooldown_until": self.state.batch_cooldown_until,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _init_session(self) -> requests.Session:
        """初始化 HTTP session 并预热 Cookie"""
        session = requests.Session()
        try:
            ua = random.choice(self.user_agents)
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            session.get("https://www.cls.cn", headers=headers, timeout=30)
            self.logger.info("[deep_backfill] Cookie 预热完成")
        except Exception as e:
            self.logger.warning(f"[deep_backfill] Cookie 预热失败: {e}")
        return session

    def _get_headers(self) -> Dict[str, str]:
        """获取带随机 User-Agent 的请求头"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.cls.cn/telegraph",
        }

    def _random_delay(self) -> None:
        """请求间随机延迟"""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def _cooldown(self) -> None:
        """批量冷却"""
        cooldown = random.uniform(self.cooldown_min, self.cooldown_max)
        self.state.batch_cooldown_until = (datetime.now() + timedelta(seconds=cooldown)).isoformat()
        self._save_state()
        self.logger.info(
            f"[deep_backfill] 冷却 {cooldown:.0f}s (已扫描 {self.state.total_scanned}, 已保存 {self.state.total_saved})"
        )
        time.sleep(cooldown)
        self.state.batch_cooldown_until = None

    def fetch_detail(self, article_id: int) -> Optional[Dict[str, Any]]:
        """获取单条 detail 页面，提取 __NEXT_DATA__ 中的 articleDetail

        Returns:
            包含 id, title, content, ctime, type 的字典，或 None（MISS/非电报）
        """
        if not self._session:
            self._session = self._init_session()

        url = f"https://www.cls.cn/detail/{article_id}"
        try:
            headers = self._get_headers()
            resp = self._session.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                self.logger.debug(f"[deep_backfill] id={article_id} HTTP {resp.status_code}")
                return None

            # 提取 __NEXT_DATA__
            match = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                resp.text,
                re.DOTALL,
            )
            if not match:
                self.logger.debug(f"[deep_backfill] id={article_id} no __NEXT_DATA__")
                return None

            data = json.loads(match.group(1))
            article = (
                data.get("props", {})
                .get("initialState", {})
                .get("detail", {})
                .get("articleDetail", {})
            )
            if not article or not isinstance(article, dict):
                self.logger.debug(f"[deep_backfill] id={article_id} empty articleDetail")
                return None

            article_type = article.get("type")
            if article_type != -1:  # 只取电报
                self.logger.debug(f"[deep_backfill] id={article_id} type={article_type}, skipping")
                return None

            ctime = article.get("ctime", 0)
            ctime_dt = datetime.fromtimestamp(int(ctime)) if ctime else None

            return {
                "id": str(article.get("id", article_id)),
                "title": article.get("title") or "",
                "content": article.get("content") or article.get("brief") or "",
                "ctime": int(ctime) if ctime else 0,
                "ctime_dt": ctime_dt.isoformat() if ctime_dt else "",
                "type": article_type,
            }

        except json.JSONDecodeError:
            self.logger.debug(f"[deep_backfill] id={article_id} JSON parse error")
            return None
        except requests.RequestException as e:
            self.logger.debug(f"[deep_backfill] id={article_id} request error: {e}")
            return None
        except Exception:
            self.logger.debug(f"[deep_backfill] id={article_id} unexpected error", exc_info=True)
            return None

    def run_batch(self, batch_size: int = 10) -> List[Dict[str, Any]]:
        """运行一批扫描，返回新发现的电报列表

        自动处理：
        - 批量冷却（每 cooldown_interval 次扫描后）
        - 游标持久化
        - MISS 跳过
        - 非电报类型跳过
        """
        results: List[Dict[str, Any]] = []
        batch_start = self.state.total_scanned

        self.logger.info(
            f"[deep_backfill] 开始批次: current_id={self.state.current_id}, " f"batch_size={batch_size}"
        )

        for i in range(batch_size):
            article_id = self.state.current_id
            if article_id < 250:  # 最老的文章 ID
                self.logger.info("[deep_backfill] 已到达最早文章 (id<250)，停止")
                break

            # 冷却检查
            scans_in_cycle = self.state.total_scanned % self.cooldown_interval
            if self.state.total_scanned > 0 and scans_in_cycle == 0:
                self._cooldown()
                # 重新初始化 session（冷却后可能需要新 Cookie）
                self._session = self._init_session()

            # 获取 detail
            item = self.fetch_detail(article_id)
            self.state.total_scanned += 1

            if item:
                results.append(item)
                self.state.total_saved += 1
                self.logger.info(
                    f"[deep_backfill] ✓ id={article_id} saved ({item['ctime_dt'][:10] if item.get('ctime_dt') else '?'}): "
                    f"{item['title'][:60]}"
                )
            else:
                self.state.total_miss += 1
                if self.verbose and self.state.total_scanned % 10 == 0:
                    self.logger.info(
                        f"[deep_backfill] 进度: scanned={self.state.total_scanned}, "
                        f"saved={self.state.total_saved}, miss={self.state.total_miss}"
                    )

            # 递减 ID
            self.state.current_id -= 1

            # 请求间延迟
            if i < batch_size - 1 and self.state.current_id >= 250:
                self._random_delay()

        # 持久化游标
        self._save_state()

        batch_scanned = self.state.total_scanned - batch_start
        self.logger.info(
            f"[deep_backfill] 批次完成: scanned={batch_scanned}, saved={len(results)}, "
            f"cursor={self.state.current_id}"
        )
        return results


from .utils.date_utils import parse_and_validate_date_range
from .utils.deduplication import DeduplicationStore
from .utils.log_utils import setup_logging
from .utils.net_utils import random_delay, retry_request

# ============================================================
# 仅支持 CLI 调用
# ============================================================


def parse_args():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="财联社电报爬虫 - 爬取财联社电报新闻",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本使用（爬取最近2天）
  python cls.py

  # 指定日期范围
  python cls.py --start_date 2026-04-01 --end_date 2026-04-15

  # 启用持久化去重
  python cls.py --state_path ./state/cls_telegrams.json
        """,
    )

    # 日期参数
    parser.add_argument("--start_date", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=2, help="默认爬取天数（未指定日期时）")

    # 过滤参数
    parser.add_argument("--start_hour", type=int, help="起始小时 (0-23)")
    parser.add_argument("--end_hour", type=int, help="结束小时 (0-23)")

    # 输出参数
    parser.add_argument("--output_dir", type=str, default="./output", help="输出目录")

    # 反爬参数
    parser.add_argument("--delay", type=float, default=1.5, help="基础请求延迟（秒）")
    parser.add_argument("--delay_jitter", type=float, default=0.8, help="延迟抖动范围（秒）")
    parser.add_argument("--max_retries", type=int, default=3, help="最大重试次数")
    parser.add_argument("--max_pages", type=int, default=150, help="最大爬取页数")
    parser.add_argument("--max_empty_pages", type=int, default=7, help="连续空页阈值")

    # 持久化去重
    parser.add_argument("--state_path", type=str, help="状态文件路径（用于持久化去重）")
    parser.add_argument("--skip_existing", action="store_true", default=True, help="跳过已存在的电报（默认启用）")

    # 日志参数
    parser.add_argument("--verbose", action="store_true", default=True, help="显示详细日志")
    parser.add_argument("--log_to_file", action="store_true", default=True, help="记录日志到文件")
    parser.add_argument("--log_filename", type=str, help="自定义日志文件名")

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
        if "new_telegrams" in result:
            print(f"  新电报: {result['new_telegrams']}")
        if "skipped_existing" in result:
            print(f"  跳过已有: {result['skipped_existing']}")
        print(f"  日期范围: {result.get('date_range', '')}")
        if result.get("output_files"):
            for fmt, path in result["output_files"].items():
                print(f"  {fmt.upper()}文件: {path}")
    else:
        print("爬取失败!")
        if result.get("errors"):
            print(f"  错误: {result['errors']}")
    print("=" * 60 + "\n")

    return result


if __name__ == "__main__":
    main()
