"""联网问答（提问优先联网查询）单元测试.

覆盖：
- WebSearchService.format_for_prompt 编号格式
- WebSearchService.search 正文补抓与降级
- AskService.ask 注入搜索结果 + 无 key 降级标注
- build_web_search_provider 按 settings 切换
"""

from unittest.mock import MagicMock, patch

from core.interfaces import WebSearchResult
from core.settings import settings
from data_layer.web_search.factory import build_web_search_provider
from services.ask_service import AskService
from services.web_search_service import WebSearchService

# ── 测试用 fake provider ──────────────────────────────────


class FakeProvider:
    """返回固定结果的 fake provider，便于断言."""

    def __init__(self, results: list[WebSearchResult]) -> None:
        self._results = results

    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        return list(self._results[:max_results])


def _make_result(title: str, url: str, snippet: str = "", content=None) -> WebSearchResult:
    return WebSearchResult(
        title=title,
        url=url,
        snippet=snippet,
        content=content,
        source="fake",
    )


# ── WebSearchService ──────────────────────────────────────


class TestWebSearchService:
    def test_format_for_prompt_empty(self):
        svc = WebSearchService(provider=FakeProvider([]))
        assert svc.format_for_prompt([]) == ""

    def test_format_for_prompt_numbered(self):
        svc = WebSearchService(provider=FakeProvider([]))
        results = [
            _make_result("标题A", "http://a", snippet="摘要A"),
            _make_result("标题B", "http://b", content="正文B"),
        ]
        text = svc.format_for_prompt(results)
        assert "[1] 标题A" in text
        assert "http://a" in text
        assert "摘要A" in text
        assert "[2] 标题B" in text
        assert "正文B" in text

    def test_search_uses_snippet_when_no_content_and_fetch_disabled(self):
        results = [_make_result("T", "http://x", snippet="S")]
        svc = WebSearchService(provider=FakeProvider(results), fetch_content_enabled=False)
        out = svc.search("q", fetch_content=False)
        assert len(out) == 1
        assert out[0].content is None  # 未补抓

    def test_search_fetches_content_when_missing(self):
        results = [_make_result("T", "http://x", snippet="S", content=None)]
        svc = WebSearchService(provider=FakeProvider(results), fetch_content_enabled=True)
        with patch(
            "services.web_search_service.fetch_page_content", return_value="抓到的正文"
        ) as mock_fetch:
            out = svc.search("q")
        assert out[0].content == "抓到的正文"
        mock_fetch.assert_called_once()

    def test_search_fetch_failure_degrades_to_none(self):
        results = [_make_result("T", "http://x", snippet="S", content=None)]
        svc = WebSearchService(provider=FakeProvider(results), fetch_content_enabled=True)
        with patch("services.web_search_service.fetch_page_content", return_value=None):
            out = svc.search("q")
        assert out[0].content is None  # 抓取失败优雅降级，不报错
        assert out[0].snippet == "S"

    def test_search_degrades_when_pool_provider_raises(self):
        provider = MagicMock()
        provider.search.side_effect = ConnectionError("offline")
        service = WebSearchService(provider=provider, fetch_content_enabled=False)

        assert service.search("query") == []
        provider.search.assert_called_once_with(
            "query", max_results=settings.WEB_SEARCH_MAX_RESULTS
        )

    def test_search_empty_results_when_provider_returns_none(self):
        svc = WebSearchService(provider=FakeProvider([]))
        assert svc.search("q") == []


# ── AskService ────────────────────────────────────────────


class TestAskService:
    def _mock_gateway(self, content: str = "答案是 [1]。", model_name: str = "test-model"):
        gw = MagicMock()
        resp = MagicMock()
        resp.content = content
        resp.model_name = model_name
        gw.chat.return_value = resp
        return gw

    def test_ask_injects_search_results_into_messages(self):
        results = [_make_result("标题", "http://a", content="正文")]
        web_search = WebSearchService(provider=FakeProvider(results), fetch_content_enabled=False)
        gw = self._mock_gateway()
        svc = AskService(model_gateway=gw, web_search=web_search)

        result = svc.ask("某问题", max_results=5, fetch_content=False)

        # gateway 被调用一次
        gw.chat.assert_called_once()
        messages = gw.chat.call_args.args[0]
        user_msg = messages[-1]["content"]
        # 搜索结果已注入 prompt
        assert "正文" in user_msg
        assert "某问题" in user_msg
        # 结果字段正确
        assert result.online is True
        assert result.answer == "答案是 [1]。"
        assert len(result.sources) == 1
        assert result.model == "test-model"

    def test_ask_degrades_when_no_search_results(self):
        """无 key / 搜索失败 → online=False，prompt 标注 [未联网]。"""
        web_search = WebSearchService(provider=FakeProvider([]), fetch_content_enabled=False)
        gw = self._mock_gateway()
        svc = AskService(model_gateway=gw, web_search=web_search)

        result = svc.ask("问题", fetch_content=False)

        assert result.online is False
        messages = gw.chat.call_args.args[0]
        user_msg = messages[-1]["content"]
        assert "[未联网]" in user_msg
        assert result.sources == []

    def test_ask_gateway_failure_returns_error(self):
        results = [_make_result("标题", "http://a", content="正文")]
        web_search = WebSearchService(provider=FakeProvider(results), fetch_content_enabled=False)
        gw = MagicMock()
        gw.chat.side_effect = RuntimeError("model down")
        svc = AskService(model_gateway=gw, web_search=web_search)

        result = svc.ask("问题", fetch_content=False)

        assert "生成答案失败" in result.answer
        assert result.online is True  # 搜索本身成功了

    def test_ask_does_not_leak_fetch_content_to_gateway(self):
        """fetch_content 是搜索参数，不能透传给 ModelGateway.chat（会污染底层 SDK）。"""
        web_search = WebSearchService(provider=FakeProvider([]), fetch_content_enabled=False)
        gw = self._mock_gateway()
        svc = AskService(model_gateway=gw, web_search=web_search)

        svc.ask("问题", fetch_content=False)

        # gateway.chat 的 kwargs 不应含 fetch_content
        kwargs = gw.chat.call_args.kwargs
        assert "fetch_content" not in kwargs


# ── factory provider 切换 ─────────────────────────────────


class TestWebSearchFactory:
    def test_pool_failure_marks_key_unavailable(self):
        from data_layer.web_search.key_pool import ApiKeyPool, PoolConfig
        from data_layer.web_search.tavily_provider import TavilyProvider

        pool = ApiKeyPool({"failed": "bad-key"}, config=PoolConfig(lock_seconds=60))
        provider = TavilyProvider(key_pool=pool)

        with patch.object(provider, "_search_with_key", side_effect=ConnectionError("offline")):
            try:
                provider.search("query")
            except ConnectionError:
                pass
            else:
                raise AssertionError("Expected pool search to propagate the failed request")

        stats = pool.get_stats("failed")
        assert stats is not None
        assert stats.is_locked
        assert stats.consecutive_failures == 1

    def test_default_is_tavily(self):
        from data_layer.web_search.tavily_provider import TavilyProvider

        with patch.object(settings, "WEB_SEARCH_PROVIDER", "tavily"):
            provider = build_web_search_provider()
        assert isinstance(provider, TavilyProvider)

    def test_switch_to_bing(self):
        from data_layer.web_search.bing_provider import BingProvider

        with patch.object(settings, "WEB_SEARCH_PROVIDER", "bing"):
            provider = build_web_search_provider()
        assert isinstance(provider, BingProvider)

    def test_unknown_provider_falls_back_to_tavily(self):
        from data_layer.web_search.tavily_provider import TavilyProvider

        with patch.object(settings, "WEB_SEARCH_PROVIDER", "unknown"):
            provider = build_web_search_provider()
        assert isinstance(provider, TavilyProvider)
