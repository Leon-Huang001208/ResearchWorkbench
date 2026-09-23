"""
cnstock 单元测试
"""
import pytest
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cnstock import (
    CnstockConfig,
    CnstockCrawler,
    NewsItem
)


class TestCnstockConfig:
    """配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        cfg = CnstockConfig()
        assert cfg.verbose is True
        assert cfg.output_path == "./output"
        assert cfg.keywords == []
        assert cfg.max_pages == 5
        assert cfg.delay == 1.0

    def test_custom_config(self):
        """测试自定义配置"""
        cfg = CnstockConfig(
            verbose=False,
            output_path="./data",
            keywords=["人工智能", "芯片"],
            max_pages=5,
            delay=2.0
        )
        assert cfg.verbose is False
        assert cfg.output_path == "./data"
        assert cfg.keywords == ["人工智能", "芯片"]
        assert cfg.max_pages == 5
        assert cfg.delay == 2.0


class TestNewsItem:
    """新闻条目测试"""

    def test_create_news_item(self):
        """测试创建新闻条目"""
        news = NewsItem(
            title="测试新闻",
            url="https://example.com/news/1",
            publish_time="2024-01-15 09:30:00",
            source="中国证券网"
        )
        assert news.title == "测试新闻"
        assert news.url == "https://example.com/news/1"
        assert news.publish_time == "2024-01-15 09:30:00"
        assert news.source == "中国证券网"


class TestCnstockCrawler:
    """爬虫类测试"""

    def test_create_crawler(self):
        """测试创建爬虫实例"""
        crawler = CnstockCrawler()
        assert crawler is not None
        assert crawler._initialized is False

    def test_setup_dates(self):
        """测试日期设置"""
        crawler = CnstockCrawler()
        crawler.initialize()

        assert crawler.config.start_date is not None
        assert crawler.config.end_date is not None

    def test_parse_date(self):
        """测试日期解析"""
        crawler = CnstockCrawler()
        crawler.initialize()

        dt = crawler._parse_date("2024-01-15")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

        dt = crawler._parse_date("2024-01-15 09:30:00")
        assert dt is not None
        assert dt.hour == 9
        assert dt.minute == 30

    def test_is_in_date_range(self):
        """测试日期范围判断"""
        crawler = CnstockCrawler()
        crawler.config.start_date = "2024-01-01"
        crawler.config.end_date = "2024-01-31"
        crawler._initialized = True

        assert crawler._is_in_date_range("2024-01-15") is True
        assert crawler._is_in_date_range("2023-12-31") is False
        assert crawler._is_in_date_range("2024-02-01") is False

    def test_matches_keywords(self):
        """测试关键词匹配"""
        crawler = CnstockCrawler()
        crawler.config.keywords = ["人工智能", "芯片"]
        crawler._initialized = True

        assert crawler._matches_keywords("人工智能概念股上涨") is True
        assert crawler._matches_keywords("芯片行业迎来新机遇") is True
        assert crawler._matches_keywords("普通新闻标题") is False

    def test_matches_keywords_empty(self):
        """测试无关键词时匹配"""
        crawler = CnstockCrawler()
        crawler.config.keywords = []
        crawler._initialized = True

        assert crawler._matches_keywords("任意标题") is True

    def test_generate_sample_news(self):
        """测试生成示例新闻"""
        crawler = CnstockCrawler()
        crawler.initialize()

        news_list = crawler._generate_sample_news()
        assert len(news_list) > 0
        assert all(isinstance(n, NewsItem) for n in news_list)
        assert all(n.title for n in news_list)
        assert all(n.url for n in news_list)


class TestCrawlerDirect:
    """直接测试爬虫类"""

    def test_create_crawler_with_config_dict(self):
        """测试通过字典配置创建爬虫"""
        cfg = CnstockConfig()
        cfg.verbose = False
        cfg.max_pages = 5
        skill = CnstockCrawler(cfg)
        assert skill is not None
        assert skill.config.verbose is False
        assert skill.config.max_pages == 5

    def test_execute_basic(self):
        """测试基本执行"""
        cfg = CnstockConfig()
        cfg.verbose = False
        # 设置必填的日期参数
        cfg.start_date = datetime.now().strftime("%Y-%m-%d")
        cfg.end_date = datetime.now().strftime("%Y-%m-%d")
        crawler = CnstockCrawler(cfg)
        result = crawler.execute()
        assert result["success"] is True
        assert "news_count" in result
        assert "news_list" in result

    def test_execute_with_keywords(self):
        """测试带关键词执行"""
        cfg = CnstockConfig()
        cfg.verbose = False
        cfg.start_date = datetime.now().strftime("%Y-%m-%d")
        cfg.end_date = datetime.now().strftime("%Y-%m-%d")
        cfg.keywords = ["人工智能"]
        crawler = CnstockCrawler(cfg)
        result = crawler.execute()
        assert result["success"] is True

    def test_execute_with_date_range(self):
        """测试带日期范围执行"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        cfg = CnstockConfig()
        cfg.verbose = False
        cfg.start_date = start_date
        cfg.end_date = end_date
        crawler = CnstockCrawler(cfg)
        result = crawler.execute()
        assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
