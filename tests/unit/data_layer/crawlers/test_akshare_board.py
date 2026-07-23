"""AkShare board crawler tests."""

import os
import sys
from types import SimpleNamespace

import pandas as pd


def test_fetch_sector_board_ignores_bad_proxy_env_and_restores_it(monkeypatch):
    """Board fetch should not inherit a stale desktop proxy."""
    from data_layer.crawlers.akshare import board

    board._cache = None
    proxy_keys = [
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
    ]

    for key in proxy_keys:
        monkeypatch.setenv(key, "http://127.0.0.1:7890")
    monkeypatch.setenv("NO_PROXY", "localhost")

    def fake_stock_board_industry_summary_ths():
        leaked = [key for key in proxy_keys if os.environ.get(key)]
        assert leaked == []
        assert os.environ.get("NO_PROXY") == "*"
        return pd.DataFrame(
            [
                {
                    "板块": "小金属",
                    "涨跌幅": 3.52,
                    "净流入": 12.15,
                    "上涨家数": 21,
                    "下跌家数": 6,
                    "总成交量": 931.90,
                    "总成交额": 424.55,
                    "均价": 45.56,
                    "领涨股": "翔鹭钨业",
                    "领涨股-最新价": 39.34,
                    "领涨股-涨跌幅": 10.01,
                }
            ]
        )

    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(stock_board_industry_summary_ths=fake_stock_board_industry_summary_ths),
    )

    snapshot = board.fetch_sector_board(force_refresh=True)

    assert [sector.name for sector in snapshot.sectors] == ["小金属"]
    for key in proxy_keys:
        assert os.environ.get(key) == "http://127.0.0.1:7890"
    assert os.environ.get("NO_PROXY") == "localhost"
