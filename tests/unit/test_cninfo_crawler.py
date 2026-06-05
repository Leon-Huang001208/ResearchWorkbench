"""Tests for CNINFO crawler reliability behavior."""
from data_layer.crawlers.cninfo import cninfo as cninfo_module
from data_layer.crawlers.cninfo.cninfo import CninfoConfig, CninfoCrawler


class _FailingSession:
    def __init__(self):
        self.headers = {}
        self.trust_env = True

    def post(self, *args, **kwargs):
        raise RuntimeError("proxy refused")


class _ReqLib:
    @staticmethod
    def Session():
        return _FailingSession()


def test_cninfo_crawler_disables_env_proxy_by_default(monkeypatch):
    session = _FailingSession()

    class ReqLib:
        @staticmethod
        def Session():
            return session

    monkeypatch.setattr(cninfo_module, "HAS_DEPENDENCIES", True)
    monkeypatch.setattr(cninfo_module, "req_lib", ReqLib)

    crawler = CninfoCrawler(CninfoConfig(max_pages=1, timeout=1))
    crawler._initialize()

    assert session.trust_env is False


def test_cninfo_crawler_reports_page_failures(monkeypatch):
    monkeypatch.setattr(cninfo_module, "HAS_DEPENDENCIES", True)
    monkeypatch.setattr(cninfo_module, "req_lib", _ReqLib)

    crawler = CninfoCrawler(CninfoConfig(max_pages=1, timeout=1, verbose=False))
    result = crawler.execute()

    assert result["success"] is False
    assert result["total_count"] == 0
    assert result["errors"] == [{"page": 1, "error": "proxy refused"}]
