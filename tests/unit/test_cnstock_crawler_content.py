import json

from data_layer.adapters.cnstock_adapter import CNStockAdapter
from data_layer.crawlers.cnstock.cnstock import CnstockConfig, CnstockCrawler


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.encoding = "utf-8"


class _FakeSession:
    def __init__(self, text: str):
        self.text = text
        self.trust_env = True

    def get(self, *args, **kwargs):
        return _FakeResponse(self.text)


def _next_data_html(content: str) -> str:
    payload = {
        "props": {
            "pageProps": {
                "data": {
                    "source": "新华社",
                    "textInfo": {"content": f"<p>{content}</p>"},
                }
            }
        }
    }
    return (
        '<script src="/waf/awsc.js"></script>'
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>'
    )


def test_cnstock_article_content_allows_normal_waf_script_marker():
    crawler = CnstockCrawler(CnstockConfig(start_date="2026-06-21", end_date="2026-06-21"))
    crawler._initialized = True
    crawler._session = _FakeSession(_next_data_html("这是中国证券网文章正文。"))

    detail = crawler._fetch_article_content("731919", max_retries=0)

    assert detail["source"] == "新华社"
    assert detail["content_text"] == "这是中国证券网文章正文。"


def test_cnstock_initialize_ignores_broken_proxy_environment():
    crawler = CnstockCrawler(CnstockConfig(start_date="2026-06-21", end_date="2026-06-21"))

    crawler.initialize()

    assert crawler._session is not None
    assert crawler._session.trust_env is False


def test_cnstock_adapter_does_not_persist_app_slogan_as_body():
    adapter = CNStockAdapter()

    envelope = adapter.parse(
        {
            "article_id": "731919",
            "title": "热点问答｜梅洛尼与特朗普为何突然“翻脸”？",
            "summary": "权威、专业、价值 尽在上海证券报客户端",
            "publish_time": "2026-06-21 16:54:00",
        }
    )

    assert envelope.raw_text == "热点问答｜梅洛尼与特朗普为何突然“翻脸”？"
