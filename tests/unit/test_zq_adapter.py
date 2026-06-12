from unittest.mock import MagicMock, patch

import pytest

from data_layer.adapters.zq_adapter import ZQAdapter


class TestZQAdapterFailures:
    def test_fetch_reports_raises_when_fetcher_fails(self):
        with patch("data_layer.crawlers.zq.report.ReportFetcher") as fetcher_class:
            fetcher = MagicMock()
            fetcher.fetch.return_value = {"success": False, "message": "remote disconnected"}
            fetcher_class.return_value = fetcher

            with pytest.raises(RuntimeError, match="remote disconnected"):
                ZQAdapter().fetch(doc_types="REPORT")

    def test_fetch_reports_raises_when_fetcher_has_no_output_file(self):
        with patch("data_layer.crawlers.zq.report.ReportFetcher") as fetcher_class:
            fetcher = MagicMock()
            fetcher.fetch.return_value = {"success": True, "terms": [{"status": "error"}]}
            fetcher_class.return_value = fetcher

            with pytest.raises(RuntimeError, match="No output file"):
                ZQAdapter().fetch(doc_types="REPORT")
