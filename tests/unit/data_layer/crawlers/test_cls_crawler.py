from datetime import datetime
from unittest.mock import Mock

from data_layer.crawlers.cls.cls import CLSConfig, CLSTelegramCrawler


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse({})


class FakeStateManager:
    def __init__(self, processed=None):
        self.processed = set(processed or [])
        self.watermarks = {}
        self.marked = []

    def is_processed(self, item_id):
        return str(item_id) in self.processed

    def mark_processed(self, item_id, title="", content_preview=""):
        self.processed.add(str(item_id))
        self.marked.append(str(item_id))

    def set_watermark(self, key, item_id, extra=None):
        self.watermarks[key] = str(item_id)


def make_crawler(**config_kwargs):
    crawler = CLSTelegramCrawler(CLSConfig(**config_kwargs))
    crawler._session = FakeSession()
    crawler.logger = Mock()
    return crawler


def test_get_telegram_data_keeps_new_items_after_known_item(monkeypatch):
    crawler = make_crawler(skip_existing=True, stop_on_known=True)
    crawler.state_manager = FakeStateManager(processed={"known"})

    payload = {
        "errno": 0,
        "data": {
            "telegram": {
                "total_num": 3,
                "data": [
                    {"id": "older-new", "descr": "older", "time": "1780452000"},
                    {"id": "known", "descr": "known", "time": "1780452060"},
                    {"id": "new-after-known", "descr": "newer", "time": "1780452120"},
                ],
            }
        },
    }

    monkeypatch.setattr(crawler, "_retry_request", lambda *args, **kwargs: FakeResponse(payload))

    result = crawler.get_telegram_data(datetime(2026, 6, 3), page=1)

    assert result["found_known"] is True
    assert result["new_count"] == 2
    assert [item.id for item in crawler.all_telegrams] == ["older-new", "new-after-known"]
    assert crawler.skipped_count == 1


def test_get_all_day_telegrams_uses_first_pages_when_limited(monkeypatch):
    crawler = make_crawler(max_pages=3, max_empty_pages=10, stop_on_known=False)

    probe_payload = {
        "errno": 0,
        "data": {
            "telegram": {
                "total_num": 300,
                "data": [{"id": str(i), "descr": "probe", "time": "1780452000"} for i in range(30)],
            }
        },
    }
    pages = []

    monkeypatch.setattr(
        crawler, "_retry_request", lambda *args, **kwargs: FakeResponse(probe_payload)
    )
    monkeypatch.setattr(crawler, "_random_delay", lambda *args, **kwargs: None)

    def fake_get_telegram_data(date, page):
        pages.append(page)
        return {"new_count": 1, "found_known": False, "known_telegram_id": None}

    monkeypatch.setattr(crawler, "get_telegram_data", fake_get_telegram_data)

    crawler._get_all_day_telegrams(datetime(2026, 6, 3))

    assert pages == [1, 2, 3]
