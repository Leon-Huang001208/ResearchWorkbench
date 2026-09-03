import os
import sys
from types import SimpleNamespace

import pandas as pd

from data_layer.adapters.cjpy_adapter import CjpyAdapter


def test_fetch_daily_quotes_uses_explicit_client_without_changing_proxy_env(monkeypatch):
    calls = {}

    def fake_get_market_data(code, start, end, cycle, rate, fields, client):
        calls["client"] = client
        calls["https_proxy_inside"] = os.environ.get("https_proxy")
        return pd.DataFrame(
            [
                {
                    "时间": "2026-06-23",
                    "open": 100.0,
                    "high": 106.0,
                    "low": 99.0,
                    "close": 105.0,
                }
            ]
        )

    fake_cjpy = SimpleNamespace(
        get_saved_token=lambda: "token",
        get_market_data=fake_get_market_data,
    )
    monkeypatch.setitem(sys.modules, "cjpy", fake_cjpy)
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:7890")

    owned_client = object()
    df = CjpyAdapter(token="token", client=owned_client).fetch_daily_quotes(
        ["688981.SH"],
        "20260623",
        "20260623",
        rate="不复权",
    )

    assert calls["https_proxy_inside"] == "http://127.0.0.1:7890"
    assert calls["client"] is owned_client
    assert os.environ["https_proxy"] == "http://127.0.0.1:7890"
    assert len(df) == 1
    assert df.iloc[0]["code"] == "688981.SH"
