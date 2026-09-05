from datetime import datetime

import pandas as pd

from data_layer.crawlers.akshare.news import AkShareNewsFetcher


class _CurrentAkShare:
    def stock_news_main_cx(self):
        return pd.DataFrame(
            [
                {"tag": "市场", "summary": "市场成交保持活跃", "url": "https://example.test/1"},
                {"tag": "宏观", "summary": "政策数据更新", "url": "https://example.test/2"},
            ]
        )


def test_fetch_caixin_news_supports_current_akshare_entry_point(monkeypatch):
    fetcher = AkShareNewsFetcher()
    monkeypatch.setattr(fetcher, "_initialize", lambda: None)
    fetcher._ak = _CurrentAkShare()
    fetcher._initialized = True

    result = fetcher.fetch_caixin_news(limit=1, keywords=["市场"])

    assert len(result) == 1
    assert result[0].source == "caixin"
    assert result[0].title == "市场"
    assert isinstance(result[0].publish_time, datetime)


def test_fetch_all_news_uses_caixin_when_legacy_sources_return_no_items(monkeypatch):
    fetcher = AkShareNewsFetcher()
    monkeypatch.setattr(fetcher, "fetch_sina_news", lambda **_kwargs: [])
    monkeypatch.setattr(fetcher, "fetch_eastmoney_news", lambda **_kwargs: [])
    monkeypatch.setattr(
        fetcher,
        "fetch_caixin_news",
        lambda **_kwargs: [
            type("News", (), {"title": "市场", "source": "caixin"})(),
        ],
    )

    result = fetcher.fetch_all_news(limit=3)

    assert [item.source for item in result] == ["caixin"]
