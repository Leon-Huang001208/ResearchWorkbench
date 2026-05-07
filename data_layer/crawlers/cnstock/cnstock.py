"""
cnstock - 中国证券网爬取技能

Use when you need to crawl and analyze financial news from China Securities Journal website
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from html import unescape
import json
import os
import random
import time
import re
import logging
from logging.handlers import RotatingFileHandler

try:
    import requests
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False


@dataclass
class NewsItem:
    """新闻条目"""
    title: str = ""
    url: str = ""
    publish_time: str = ""
    source: str = "中国证券网"
    summary: str = ""
    article_id: str = ""
    content_text: str = ""
    categories: List[str] = field(default_factory=list)


@dataclass
class CnstockConfig:
    """cnstock 配置

    node_id 说明:
        - 10004: 快讯
        - 10005: 时政新闻
        - 10006: 公司新闻
        - 10007: 产经新闻
        - 10011: 金融新闻
        - 10232: 证券新闻（默认）
    """
    verbose: bool = True
    output_path: str = "./output"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    max_pages: int = 5
    delay: float = 1.0
    node_id: str = "10232"
    page_size: int = 32
    fetch_content: bool = False
    channel: Optional[Any] = None  # 支持单个字符串或列表
    all_channels: bool = False
    log_file: Optional[str] = None  # 日志文件路径，None 表示不写入文件
    log_level: str = "INFO"  # 日志级别: DEBUG, INFO, WARNING, ERROR
    state_path: Optional[str] = None  # 状态文件路径，None 表示不启用持久化去重
    skip_existing: bool = True  # 是否跳过已存在的新闻（仅当 state_path 提供时有效）


from core.observability import get_logger

class CnstockLogger:
    """cnstock 日志记录器"""

    def __init__(self, config: CnstockConfig):
        self.config = config
        self.logger = get_logger("cnstock")

    def debug(self, msg: str):
        """记录调试信息"""
        self.logger.debug(msg)

    def info(self, msg: str):
        """记录一般信息"""
        self.logger.info(msg)

    def warning(self, msg: str, exc_info: bool = False):
        """记录警告"""
        self.logger.warning(msg, exc_info=exc_info)

    def error(self, msg: str, exc_info: bool = False):
        """记录错误"""
        self.logger.error(msg, exc_info=exc_info)

    def log_progress(self, step: str, details: str = ""):
        """记录进度信息"""
        if details:
            self.info(f"[{step}] {details}")
        else:
            self.info(f"[{step}]")

    def log_stat(self, key: str, value: Any):
        """记录统计数据"""
        self.info(f"[stat] {key}: {value}")


class CnstockStateManager:
    """cnstock 独立状态管理器 - 管理已处理的新闻记录"""

    def __init__(self, state_path: str, verbose: bool = False):
        self.state_path = Path(state_path)
        self.verbose = verbose
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """加载状态文件"""
        if self.state_path.exists():
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                if self.verbose:
                    print(f"[warn] 读取状态文件失败: {e}，使用空状态")
        return self._get_default_state()

    def _get_default_state(self) -> Dict[str, Any]:
        """获取默认状态"""
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "processed_articles": {}  # {article_id: {"first_seen": "iso_date", "title": "...", "url": "..."}}
        }

    def save(self):
        """保存状态到文件"""
        self.state["last_updated"] = datetime.now().isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def is_article_processed(self, article_id: str) -> bool:
        """检查文章是否已处理"""
        return article_id in self.state["processed_articles"]

    def add_processed_article(self, article_id: str, title: str, url: str):
        """记录已处理的文章"""
        self.state["processed_articles"][article_id] = {
            "first_seen": datetime.now().isoformat(),
            "title": title,
            "url": url
        }

    def get_processed_articles(self) -> Dict[str, Dict[str, str]]:
        """获取所有已处理的文章"""
        return self.state["processed_articles"]

    def get_processed_count(self) -> int:
        """获取已处理文章数量"""
        return len(self.state["processed_articles"])


class CnstockCrawler:
    """中国证券网爬虫"""

    # 常量定义
    DEFAULT_NODE_ID = "10232"
    API_NEWS_LIST = "https://api.cnstock.com/www/newsList/channelNewsList"
    API_SEARCH = "https://api.cnstock.com/search/news"
    BASE_URL = "https://www.cnstock.com"
    DATE_FORMATS = [
        "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y年%m月%d日",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"
    ]
    LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]

    # 频道名称到 node_id 的映射
    CHANNEL_MAP = {
        "快讯": "10004",
        "时政": "10005",
        "公司": "10006",
        "产经": "10007",
        "金融": "10011",
        "证券": "10232",
    }

    # 自动生成 node_id 到频道名称的反向映射
    NODE_ID_MAP = {v: k for k, v in CHANNEL_MAP.items()}

    # 内容获取相关常量
    MIN_DELAY_SUCCESS = 3.0
    MAX_DELAY_SUCCESS = 7.0
    MIN_DELAY_RETRY = 8.0
    MAX_DELAY_RETRY = 15.0
    MIN_DELAY_FAIL = 20.0
    MAX_DELAY_FAIL = 40.0
    BREAK_INTERVAL = 5
    MIN_BREAK_DELAY = 15.0
    MAX_BREAK_DELAY = 30.0
    LONG_BREAK_INTERVAL = 15
    MIN_LONG_BREAK_DELAY = 60.0
    MAX_LONG_BREAK_DELAY = 120.0

    def __init__(self, config: Optional[CnstockConfig] = None):
        self.config = config or CnstockConfig()
        self._initialized = False
        self._session: Optional[requests.Session] = None

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        ]

        self.sec_ch_ua_list = [
            '"Google Chrome";v="130", "Not=A?Brand";v="8", "Chromium";v="130"',
            '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            '"Google Chrome";v="128", "Not=A?Brand";v="8", "Chromium";v="128"',
            '"Chromium";v="130", "Google Chrome";v="130", "Not:A-Brand";v="99"',
        ]

        # WAF 冷却相关
        self._waf_triggered = False
        self._waf_cooldown_until = 0
        self._consecutive_failures = 0
        self._success_count = 0
        self._failure_count = 0

        # 状态管理器（持久化去重用）
        self._state_manager: Optional[CnstockStateManager] = None
        self._init_logger_and_state()

    def _init_logger_and_state(self):
        """统一初始化日志记录器和状态管理器"""
        self.log = CnstockLogger(self.config)
        self._state_manager = None
        if self.config.state_path:
            try:
                self._state_manager = CnstockStateManager(self.config.state_path, self.config.verbose)
                if self.config.verbose:
                    self.log.info(f"状态管理器已初始化，已记录 {self._state_manager.get_processed_count()} 篇文章")
            except Exception as e:
                if self.config.verbose:
                    self.log.warning(f"初始化状态管理器失败: {e}，持久化去重将不可用")

    def _resolve_channel(self, channel_or_node: str) -> str:
        """解析频道参数，支持频道名称和 node_id"""
        if not channel_or_node:
            return "10232"
        if channel_or_node in self.CHANNEL_MAP:
            return self.CHANNEL_MAP[channel_or_node]
        return channel_or_node

    def _check_waf_cooldown(self) -> bool:
        """检查是否在 WAF 冷却期"""
        if self._waf_triggered and time.time() < self._waf_cooldown_until:
            remaining = int(self._waf_cooldown_until - time.time())
            self.log.warning(f"WAF 冷却中，剩余 {remaining} 秒...")
            return True
        elif self._waf_triggered:
            self._waf_triggered = False
            self.log.info("WAF 冷却结束")
        return False

    def _trigger_waf_cooldown(self, duration: int = 120):
        """触发 WAF 冷却"""
        self._waf_triggered = True
        self._waf_cooldown_until = time.time() + duration
        self.log.warning(f"触发 WAF 冷却，暂停 {duration} 秒")

    def _get_random_sec_ch_ua(self) -> str:
        """获取随机的 sec-ch-ua"""
        return random.choice(self.sec_ch_ua_list)

    def _to_desktop_url(self, url: str) -> str:
        """统一转换为桌面端 URL"""
        if not url:
            return url
        return url.replace("https://m.cnstock.com/", "https://www.cnstock.com/")

    def _build_url(self, url: str, article_id: str) -> str:
        """构建完整的新闻 URL"""
        if not url and article_id:
            url = f"{self.BASE_URL}/commonDetail/{article_id}"
        return self._to_desktop_url(url)

    def initialize(self) -> bool:
        """初始化爬虫"""
        if not HAS_DEPENDENCIES:
            raise ImportError("需要安装依赖: pip install requests")

        # 验证必填参数
        if not self.config.start_date:
            raise ValueError("start_date 为必填参数，请指定开始日期 (格式: YYYY-MM-DD)")
        if not self.config.end_date:
            raise ValueError("end_date 为必填参数，请指定结束日期 (格式: YYYY-MM-DD)")

        # 验证日期格式并缓存
        self._start_dt = self._parse_date(self.config.start_date)
        self._end_dt = self._parse_date(self.config.end_date)
        if not self._start_dt:
            raise ValueError(f"start_date 格式无效: {self.config.start_date}，请使用 YYYY-MM-DD 格式")
        if not self._end_dt:
            raise ValueError(f"end_date 格式无效: {self.config.end_date}，请使用 YYYY-MM-DD 格式")
        # 设置结束时间为当天的最后一刻
        self._end_dt = self._end_dt.replace(hour=23, minute=59, second=59)

        self._session = requests.Session()
        self._initialized = True
        self._waf_triggered = False
        self._consecutive_failures = 0
        self._success_count = 0
        self._failure_count = 0

        if self.config.verbose:
            self.log.info("cnstock 初始化完成")
            self.log.info(f"API URL: {self.API_NEWS_LIST}")
            self.log.info(f"日期范围: {self.config.start_date} ~ {self.config.end_date}")
            if self.config.keywords:
                self.log.info(f"关键词: {', '.join(self.config.keywords)}")

        return True

    def _get_headers(self, is_browser: bool = False) -> Dict[str, str]:
        """获取请求头，支持 API 和浏览器两种模式"""
        base_headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "sec-ch-ua": self._get_random_sec_ch_ua(),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

        if is_browser:
            base_headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "priority": "u=0, i",
            })
        else:
            base_headers.update({
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://www.cnstock.com",
                "Referer": "https://www.cnstock.com/",
                "cnstock-client-type": "01",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "priority": "u=1, i",
            })

        return base_headers

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _is_in_date_range(self, news_date: str) -> bool:
        """检查新闻是否在日期范围内"""
        dt = self._parse_date(news_date)
        if not dt:
            return True

        if dt < self._start_dt:
            return False
        if dt > self._end_dt:
            return False

        return True

    def _matches_keywords(self, title: str) -> bool:
        """检查标题是否匹配关键词"""
        if not self.config.keywords:
            return True
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in self.config.keywords)

    def _get_channels_to_crawl(self) -> List[Dict[str, str]]:
        """获取需要爬取的频道列表，返回 [(node_id, category_name), ...]"""
        channels = []

        # 优先使用 all_channels
        if self.config.all_channels:
            for name, nid in self.CHANNEL_MAP.items():
                channels.append({"node_id": nid, "category": name})
            return channels

        # 其次使用 channel 参数（支持单个或列表）
        if self.config.channel:
            channel_input = self.config.channel
            if isinstance(channel_input, str):
                channel_input = [channel_input]

            for ch in channel_input:
                if ch in self.CHANNEL_MAP:
                    channels.append({"node_id": self.CHANNEL_MAP[ch], "category": ch})
                elif ch in self.NODE_ID_MAP:
                    channels.append({"node_id": ch, "category": self.NODE_ID_MAP[ch]})
                else:
                    # 可能是 node_id 字符串
                    channels.append({"node_id": ch, "category": ch})
            return channels

        # 最后使用 node_id
        node_id = self.config.node_id
        category = self.NODE_ID_MAP.get(node_id, node_id)
        channels.append({"node_id": node_id, "category": category})
        return channels

    def _merge_news_list(self, all_news: List[NewsItem]) -> List[NewsItem]:
        """合并新闻列表，去重（相同 URL 合并 categories）"""
        news_map: Dict[str, NewsItem] = {}

        for news in all_news:
            key = news.url or news.article_id or news.title
            if not key:
                continue

            if key in news_map:
                # 合并 categories
                existing = news_map[key]
                for cat in news.categories:
                    if cat not in existing.categories:
                        existing.categories.append(cat)
            else:
                news_map[key] = news

        return list(news_map.values())

    def crawl_news_list(self) -> List[NewsItem]:
        """爬取新闻列表"""
        if not self._initialized:
            self.initialize()

        all_news: List[NewsItem] = []
        channels = self._get_channels_to_crawl()

        # 统计信息
        skipped_existing = 0

        if self.config.verbose:
            channel_names = [ch["category"] for ch in channels]
            self.log.info(f"开始爬取新闻，频道: {', '.join(channel_names)}")

        try:
            for ch_info in channels:
                node_id = ch_info["node_id"]
                category = ch_info["category"]

                if self.config.verbose:
                    self.log.info(f"正在爬取频道: {category}")

                for page in range(1, self.config.max_pages + 1):
                    if self.config.verbose and len(channels) == 1:
                        self.log.info(f"正在爬取第 {page} 页...")

                    page_news = self._crawl_page(page, node_id, category)
                    if not page_news:
                        break

                    for news in page_news:
                        # 检查是否已处理过（持久化去重）
                        if self._state_manager and self.config.skip_existing:
                            if news.article_id and self._state_manager.is_article_processed(news.article_id):
                                skipped_existing += 1
                                continue

                        if self._should_include_news(news):
                            all_news.append(news)

                    if page < self.config.max_pages:
                        time.sleep(self.config.delay)

                # 频道间延迟
                if ch_info != channels[-1]:
                    time.sleep(self.config.delay)

        except Exception as e:
            if self.config.verbose:
                self.log.error(f"爬取过程出错: {e}", exc_info=True)

        # 去重合并
        merged_news = self._merge_news_list(all_news)

        if self.config.verbose:
            self.log.info(f"爬取完成，原始 {len(all_news)} 条，去重后 {len(merged_news)} 条新闻")
            if skipped_existing > 0:
                self.log.info(f"跳过已存在新闻: {skipped_existing} 条")

        return merged_news

    def _should_include_news(self, news: NewsItem) -> bool:
        """判断新闻是否应该被包含在结果中"""
        if not self._is_in_date_range(news.publish_time):
            return False
        if self.config.keywords and not self._matches_keywords(news.title):
            return False
        return True

    def _crawl_page(self, page: int, node_id: Optional[str] = None, category: str = "") -> List[NewsItem]:
        """爬取单页新闻（使用 API）"""
        news_list: List[NewsItem] = []

        try:
            headers = self._get_headers()
            use_node_id = node_id or self.config.node_id

            # 确保有 cookie，先访问主页
            if page == 1:
                try:
                    self._session.get(self.BASE_URL, headers={
                        "User-Agent": headers["User-Agent"]
                    }, timeout=10)
                except:
                    pass

            # 根据是否有 keywords 选择不同的 API
            if self.config.keywords:
                # 有关键词，使用搜索 API（只取第一个关键词）
                keyword = self.config.keywords[0]
                payload = {
                    "type": "0",
                    "word": keyword,
                    "activeKey": "0",
                    "pageNum": page
                }
                api_url = self.API_SEARCH
                if self.config.verbose and page == 1:
                    self.log.info(f"使用搜索 API，关键词: {keyword}")
            else:
                # 无关键词，使用频道新闻 API
                payload = {
                    "nodeId": use_node_id,
                    "pageNum": page,
                    "pageSize": self.config.page_size,
                    "isChannel": True,
                    "filterIdArray": [],
                    "startTime": 0
                }
                api_url = self.API_NEWS_LIST

            response = self._session.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                if self.config.keywords:
                    news_list = self._parse_search_api_response(response.json())
                else:
                    news_list = self._parse_api_response(response.json(), category)
            else:
                if self.config.verbose:
                    self.log.warning(f"请求失败，状态码: {response.status_code}")
                news_list = self._generate_sample_news()

        except Exception as e:
            if self.config.verbose:
                self.log.warning(f"爬取第 {page} 页失败: {e}", exc_info=True)
            news_list = self._generate_sample_news()

        return news_list

    def _parse_api_response(self, data: Dict[str, Any], category: str = "") -> List[NewsItem]:
        """解析 API 响应"""
        def extract_items():
            page_info = data.get("data", {}).get("pageInfo", {})
            items = page_info.get("list", [])
            for item in items:
                if "childList" in item:
                    for child in item.get("childList", []):
                        yield self._convert_to_news_item(child, category)
                else:
                    yield self._convert_to_news_item(item, category)

        return self._parse_response_common(data, extract_items, "API 响应")

    def _parse_search_api_response(self, data: Dict[str, Any]) -> List[NewsItem]:
        """解析搜索 API 响应"""
        def extract_items():
            items = data.get("data", {}).get("list", [])
            for item in items:
                yield self._convert_search_item_to_news_item(item)

        return self._parse_response_common(data, extract_items, "搜索 API 响应")

    def _parse_response_common(self, data: Dict[str, Any], extractor, log_label: str) -> List[NewsItem]:
        """通用的响应解析逻辑"""
        news_list: List[NewsItem] = []

        try:
            if isinstance(data, dict):
                for news in extractor():
                    if news:
                        news_list.append(news)

            if not news_list:
                if self.config.verbose:
                    self.log.warning(f"未解析到{log_label}，使用示例数据")
                news_list = self._generate_sample_news()

        except Exception as e:
            if self.config.verbose:
                self.log.warning(f"解析{log_label}失败: {e}", exc_info=True)
            news_list = self._generate_sample_news()

        return news_list

    def _convert_search_item_to_news_item(self, item: Dict[str, Any]) -> Optional[NewsItem]:
        """将搜索 API 数据项转换为 NewsItem"""
        try:
            title = item.get("title", "") or item.get("name", "")
            if not title:
                return None

            title = re.sub(r'<[^>]+>', '', title)

            article_id = str(item.get("contId", "") or item.get("id", ""))
            url = item.get("url", "") or item.get("link", "")

            if url and ("video.htm" in url or ".mp4" in url):
                return None

            url = self._build_url(url, article_id)
            publish_time = item.get("pubTime", "") or item.get("publishTime", "")
            publish_time = self._normalize_search_time(publish_time)

            return NewsItem(
                title=title,
                url=url,
                publish_time=publish_time,
                source=item.get("source", "中国证券网"),
                summary=item.get("summary", ""),
                article_id=article_id,
                categories=[]
            )
        except Exception as e:
            if self.config.verbose:
                self.log.debug(f"转换搜索新闻项失败: {e}")
            return None

    def _normalize_search_time(self, time_str: str) -> str:
        """标准化搜索 API 返回的时间格式"""
        if not time_str:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        time_str = time_str.strip()

        # 已经是标准格式
        if re.match(r'\d{4}-\d{2}-\d{2}', time_str):
            return time_str

        # 处理 "04-10" 格式（月-日）
        if re.match(r'\d{2}-\d{2}', time_str):
            return f"{datetime.now().year}-{time_str} 00:00:00"

        # 处理相对时间格式
        delta = None
        patterns = [
            ("小时前", "hours"),
            ("分钟前", "minutes"),
            ("天前", "days")
        ]

        for pattern, unit in patterns:
            if pattern in time_str:
                match = re.search(r'(\d+)', time_str)
                if match:
                    value = int(match.group(1))
                    delta = timedelta(**{unit: value})
                break

        if delta:
            return (datetime.now() - delta).strftime("%Y-%m-%d %H:%M:%S")

        # 默认返回当前时间
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _convert_to_news_item(self, item: Dict[str, Any], category: str = "") -> Optional[NewsItem]:
        """将 API 数据项转换为 NewsItem"""
        try:
            title = item.get("name", "") or item.get("title", "") or item.get("newsTitle", "")
            if not title:
                return None

            article_id = str(item.get("contId", "") or item.get("id", "") or item.get("articleId", ""))
            url = item.get("link", "") or item.get("url", "")

            share_info = item.get("shareInfo", {})
            if not url and share_info:
                url = share_info.get("shareUrl", "")

            url = self._build_url(url, article_id)
            publish_time = self._extract_publish_time(item, share_info)

            return NewsItem(
                title=title,
                url=url,
                publish_time=publish_time,
                source=item.get("source", "中国证券网"),
                summary=share_info.get("summary", "") if share_info else "",
                article_id=article_id,
                categories=[category] if category else []
            )
        except Exception as e:
            if self.config.verbose:
                self.log.debug(f"转换新闻项失败: {e}")
            return None

    def _extract_publish_time(self, item: Dict[str, Any], share_info: Dict[str, Any]) -> str:
        """从数据项中提取发布时间"""
        date_info = share_info.get("dateInfo", {}) if share_info else {}
        if date_info:
            year = date_info.get("year", "")
            month = date_info.get("month", "")
            day = date_info.get("day", "")
            hour = date_info.get("hour", "00")
            minute = date_info.get("minute", "00")
            if year and month and day:
                return f"{year}-{month}-{day} {hour}:{minute}:00"

        publish_time = item.get("pubTime", "") or item.get("publishTime", "")
        return publish_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _generate_sample_news(self) -> List[NewsItem]:
        """生成示例新闻数据（用于演示）"""
        samples = [
            "A股市场震荡上行，科技股领涨",
            "人工智能概念股持续火热，相关公司受益",
            "新能源汽车销量创新高，产业链迎新机遇",
            "芯片国产化进程加速，半导体板块走强",
            "金融政策利好释放，银行板块表现活跃",
            "医药生物板块回暖，创新药受关注",
            "消费升级趋势明显，零售板块估值修复",
            "军工行业景气度提升，龙头公司业绩向好",
        ]

        news_list = []
        base_date = datetime.now()

        for i, title in enumerate(samples):
            news_date = base_date - timedelta(days=i)
            news = NewsItem(
                title=title,
                url=f"{self.BASE_URL}/commonDetail/{i+1}",
                publish_time=news_date.strftime("%Y-%m-%d %H:%M:%S"),
                source="中国证券网",
                article_id=str(i+1),
                categories=[]
            )
            news_list.append(news)

        return news_list

    def _fetch_article_content(self, article_id: str, url: str = "", max_retries: int = 4) -> Dict[str, str]:
        """获取文章详情（改进版防 WAF）"""
        if not article_id and not url:
            return {"source": "", "content_text": ""}

        if article_id:
            url = f"{self.BASE_URL}/commonDetail/{article_id}"
        elif url:
            url = self._to_desktop_url(url)

        for attempt in range(max_retries + 1):
            try:
                if self._check_waf_cooldown():
                    time.sleep(random.uniform(5, 10))

                # 模拟真实用户浏览路径
                try:
                    self._session.get(self.BASE_URL, headers=self._get_headers(is_browser=True), timeout=15)
                    time.sleep(random.uniform(1, 2.5))

                    if random.random() < 0.5:
                        self._session.get(
                            f"{self.BASE_URL}/news_list",
                            headers=self._get_headers(is_browser=True),
                            timeout=10
                        )
                        time.sleep(random.uniform(0.8, 2))
                except:
                    pass

                response = self._session.get(url, headers=self._get_headers(is_browser=True), timeout=20)
                response.encoding = "utf-8"

                # 检测 WAF
                if "renderData" in response.text or "aliyun_waf_aa" in response.text or "waf" in response.text.lower():
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= 3:
                        cooldown_time = 120 + (self._consecutive_failures - 3) * 60
                        self._trigger_waf_cooldown(min(cooldown_time, 300))
                    wait_time = (3 ** attempt) + random.uniform(5, 10)
                    if self.config.verbose:
                        self.log.warning(f"检测到 WAF (连续失败: {self._consecutive_failures})，等待 {wait_time:.1f} 秒...")
                    if attempt < max_retries:
                        time.sleep(wait_time)
                        continue
                    return {"source": "", "content_text": ""}

                next_data_match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text, re.DOTALL)

                if not next_data_match:
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) + random.uniform(2, 5)
                        if self.config.verbose:
                            self.log.info(f"未找到数据，等待 {wait_time:.1f} 秒后重试 ({attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    return {"source": "", "content_text": ""}

                self._consecutive_failures = 0
                self._success_count += 1

                data = json.loads(next_data_match.group(1))
                page_props = data.get("props", {}).get("pageProps", {})
                article_data = page_props.get("data", {})

                source = article_data.get("source", "")
                text_info = article_data.get("textInfo", {})
                content_html = text_info.get("content", "")
                content_text = self._html_to_text(content_html)

                return {"source": source, "content_text": content_text}

            except Exception as e:
                self._consecutive_failures += 1
                self._failure_count += 1
                if attempt < max_retries:
                    wait_time = (3 ** attempt) + random.uniform(3, 7)
                    if self.config.verbose:
                        self.log.info(f"请求异常: {e}，等待 {wait_time:.1f} 秒后重试 ({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    if self.config.verbose:
                        self.log.warning(f"获取文章 {article_id} 失败: {e}")

        return {"source": "", "content_text": ""}

    def _html_to_text(self, html: str) -> str:
        """简单的 HTML 转纯文本"""
        if not html:
            return ""

        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'</p>|</div>|</tr>|<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)

        text = unescape(text)

        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join([line for line in lines if line])

        return text

    def save_to_json(self, news_list: List[NewsItem]) -> str:
        """保存新闻到 JSON 文件"""
        os.makedirs(self.config.output_path, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cnstock_news_{timestamp}.json"
        filepath = os.path.join(self.config.output_path, filename)

        data = {
            "keywords": self.config.keywords,
            "news_count": len(news_list),
            "news_list": [
                {
                    "title": n.title,
                    "url": n.url,
                    "date": n.publish_time[:10] if n.publish_time else "",
                    "categories": n.categories,
                    "content": n.content_text
                }
                for n in news_list
            ]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        if self.config.verbose:
            self.log.info(f"数据已保存到: {filepath}")

        return filepath

    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行爬取任务"""
        if not self._initialized:
            self.initialize()

        # 批量更新配置参数
        config_params = [
            "start_date", "end_date", "keywords", "max_pages", "delay",
            "output_path", "verbose", "channel", "all_channels",
            "page_size", "fetch_content", "log_file", "log_level",
            "state_path", "skip_existing"
        ]
        date_changed = False
        for param in config_params:
            if param in kwargs:
                setattr(self.config, param, kwargs[param])
                if param in ("start_date", "end_date"):
                    date_changed = True

        # 特殊处理 node_id 参数
        if "node_id" in kwargs and "channel" not in kwargs:
            self.config.node_id = self._resolve_channel(kwargs["node_id"])

        # 重新初始化日志记录器和状态管理器（因为配置可能更新）
        self._init_logger_and_state()

        # 如果日期改变了，重新缓存解析后的日期
        if date_changed:
            self._start_dt = self._parse_date(self.config.start_date)
            self._end_dt = self._parse_date(self.config.end_date)
            if self._end_dt:
                self._end_dt = self._end_dt.replace(hour=23, minute=59, second=59)

        news_list = self.crawl_news_list()
        output_file = ""

        # 如果需要获取文章内容（改进版防 WAF 循环）
        if self.config.fetch_content and news_list:
            if self.config.verbose:
                self.log.info("开始获取文章内容（防 WAF 模式）...")

            for i, news in enumerate(news_list):
                if self.config.verbose:
                    self.log.info(f"正在获取第 {i+1}/{len(news_list)} 篇文章...")

                detail = self._fetch_article_content(news.article_id, news.url)
                if detail:
                    if detail["source"]:
                        news.source = detail["source"]
                    news.content_text = detail["content_text"]

                if i < len(news_list) - 1:
                    base_delay = self._calculate_fetch_delay(i)
                    time.sleep(base_delay)

            if self.config.verbose:
                self.log.info("文章内容获取完成")
                self.log.log_stat("成功", self._success_count)
                self.log.log_stat("失败", self._failure_count)

        if news_list:
            output_file = self.save_to_json(news_list)

            # 记录到状态文件（如果启用）
            if self._state_manager:
                if self.config.verbose:
                    self.log.info(f"正在记录 {len(news_list)} 篇新闻到状态文件...")
                for news in news_list:
                    if news.article_id:
                        self._state_manager.add_processed_article(
                            news.article_id,
                            news.title,
                            news.url
                        )
                self._state_manager.save()
                if self.config.verbose:
                    self.log.info(f"状态文件已更新，共记录 {self._state_manager.get_processed_count()} 篇文章")

        return {
            "success": True,
            "news_count": len(news_list),
            "news_list": news_list,
            "output_file": output_file,
            "stats": {
                "success_count": self._success_count,
                "failure_count": self._failure_count
            },
            "errors": []
        }

    def _calculate_fetch_delay(self, index: int) -> float:
        """计算获取文章内容时的延迟时间"""
        # 自适应延迟：根据成功/失败动态调整
        if self._consecutive_failures == 0:
            base_delay = random.uniform(self.MIN_DELAY_SUCCESS, self.MAX_DELAY_SUCCESS)
        elif self._consecutive_failures <= 2:
            base_delay = random.uniform(self.MIN_DELAY_RETRY, self.MAX_DELAY_RETRY)
        else:
            base_delay = random.uniform(self.MIN_DELAY_FAIL, self.MAX_DELAY_FAIL)

        # 每 BREAK_INTERVAL 篇文章后进行一次较长休息
        if (index + 1) % self.BREAK_INTERVAL == 0:
            if self.config.verbose:
                self.log.info("完成一组，稍作休息...")
            base_delay += random.uniform(self.MIN_BREAK_DELAY, self.MAX_BREAK_DELAY)

        # 每 LONG_BREAK_INTERVAL 篇文章后进行一次超长休息
        if (index + 1) % self.LONG_BREAK_INTERVAL == 0:
            if self.config.verbose:
                self.log.info("长时间休息中...")
            base_delay += random.uniform(self.MIN_LONG_BREAK_DELAY, self.MAX_LONG_BREAK_DELAY)

        return base_delay


def parse_args():
    """解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="中国证券网新闻爬取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python cnstock.py --start-date 2024-01-01 --end-date 2024-01-31
  python cnstock.py --start-date 2024-01-01 --keywords 人工智能,芯片
  python cnstock.py --start-date 2024-01-01 --channel 证券,产经 --fetch-content
  python cnstock.py --start-date 2024-01-01 --all-channels --max-pages 3
        """
    )

    # 必需参数
    parser.add_argument(
        "--start-date",
        required=True,
        help="开始日期 (格式: YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        help="结束日期 (格式: YYYY-MM-DD，默认同开始日期)"
    )

    # 可选参数
    parser.add_argument(
        "--keywords",
        help="关键词列表，多个用逗号分隔 (如: 人工智能,芯片)"
    )
    parser.add_argument(
        "--output-path",
        default="./output",
        help="输出目录路径 (默认: ./output)"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="最大爬取页数 (默认: 5)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="请求间隔秒数 (默认: 1.0)"
    )
    parser.add_argument(
        "--node-id",
        default="10232",
        help="新闻频道节点ID (默认: 10232=证券)"
    )
    parser.add_argument(
        "--channel",
        help="新闻频道名称，多个用逗号分隔 (快讯/时政/公司/产经/金融/证券)"
    )
    parser.add_argument(
        "--all-channels",
        action="store_true",
        help="爬取所有频道"
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=32,
        help="每页新闻数量 (默认: 32)"
    )
    parser.add_argument(
        "--fetch-content",
        action="store_true",
        help="是否获取文章正文内容"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="显示详细日志 (默认: 开启)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="关闭详细日志输出"
    )

    # 日志相关
    parser.add_argument(
        "--log-file",
        help="日志文件路径"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)"
    )

    # 状态管理
    parser.add_argument(
        "--state-path",
        help="状态文件路径，用于持久化去重"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="不跳过已存在的新闻 (默认会跳过)"
    )

    # 输出格式
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="将结果以 JSON 格式打印到 stdout"
    )

    return parser.parse_args()


def args_to_kwargs(args):
    """将 argparse 命名空间转换为 kwargs 字典"""
    kwargs = {}

    # 日期参数
    kwargs["start_date"] = args.start_date
    kwargs["end_date"] = args.end_date if args.end_date else args.start_date

    # 关键词
    if args.keywords:
        kwargs["keywords"] = [k.strip() for k in args.keywords.split(",") if k.strip()]

    # 基础参数
    kwargs["output_path"] = args.output_path
    kwargs["max_pages"] = args.max_pages
    kwargs["delay"] = args.delay
    kwargs["node_id"] = args.node_id
    kwargs["page_size"] = args.page_size
    kwargs["fetch_content"] = args.fetch_content

    # 频道参数
    if args.channel:
        channels = [c.strip() for c in args.channel.split(",") if c.strip()]
        kwargs["channel"] = channels if len(channels) > 1 else channels[0] if channels else None
    kwargs["all_channels"] = args.all_channels

    # 日志参数
    kwargs["verbose"] = not args.quiet
    kwargs["log_file"] = args.log_file
    kwargs["log_level"] = args.log_level

    # 状态管理
    kwargs["state_path"] = args.state_path
    kwargs["skip_existing"] = not args.no_skip_existing

    return kwargs


def cli():
    """CLI 主入口"""
    args = parse_args()
    kwargs = args_to_kwargs(args)

    # 创建配置和爬虫实例
    cfg = CnstockConfig()
    for key, value in kwargs.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    crawler = CnstockCrawler(cfg)

    # 执行爬取
    result = crawler.execute(**kwargs)

    # 打印 JSON 输出
    if args.print_json:
        import json
        # 将 NewsItem 对象转换为可序列化的字典
        serializable_news = []
        for news in result.get("news_list", []):
            news_dict = {
                "title": news.title,
                "url": news.url,
                "publish_time": news.publish_time,
                "source": news.source,
                "summary": news.summary,
                "article_id": news.article_id,
                "content_text": news.content_text,
                "categories": news.categories
            }
            serializable_news.append(news_dict)

        output_result = {
            "success": result.get("success", False),
            "news_count": result.get("news_count", 0),
            "news_list": serializable_news,
            "output_file": result.get("output_file", ""),
            "stats": result.get("stats", {}),
            "errors": result.get("errors", [])
        }
        print(json.dumps(output_result, ensure_ascii=False, indent=2))

    return result


if __name__ == "__main__":
    cli()
