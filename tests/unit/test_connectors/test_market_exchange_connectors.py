import json

import requests

from core.connectors.base import DiscoveryItem, RawObject
from connectors.market.csindex import CsindexMarketConnector
from connectors.market.szse import SzseMarketConnector


def test_szse_session_ignores_environment_proxy_by_default():
    connector = SzseMarketConnector()

    assert connector._session.trust_env is False


def test_szse_retries_transient_request_disconnect(monkeypatch):
    connector = SzseMarketConnector({"retry": {"max_retries": 2, "base_delay": 0}})
    calls = []

    class Response:
        status_code = 200
        text = '[{"metadata":{"pagecount":1,"tabkey":"tab1"},"data":[]}]'

        def raise_for_status(self):
            return None

        def json(self):
            return [{"metadata": {"pagecount": 1, "tabkey": "tab1"}, "data": []}]

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            raise requests.ConnectionError("remote disconnected")
        return Response()

    monkeypatch.setattr(connector._session, "get", fake_get)

    data = connector._fetch_listed_page(1)

    assert len(calls) == 2
    assert data[0]["metadata"]["pagecount"] == 1


def test_csindex_session_ignores_environment_proxy_by_default():
    connector = CsindexMarketConnector()

    assert connector._session.trust_env is False


def test_csindex_parses_current_top10_weight_response():
    connector = CsindexMarketConnector()
    raw = RawObject(
        data=json.dumps(
            {
                "code": "200",
                "data": {
                    "updateDate": "2026-06-09",
                    "weightList": [
                        {
                            "indexCode": "000300",
                            "tradeDate": "20260609",
                            "securityCode": "300308",
                            "securityName": "中际旭创",
                            "securityNameEn": "ZHONGJI INNOLIGHT CO., LTD.",
                            "marketNameCn": "深圳证券交易所",
                            "weight": "3.28",
                        }
                    ],
                },
                "success": True,
            },
            ensure_ascii=False,
        ),
        content_type="application/json",
        source_uri="csindex://constituents/000300/top10",
        content_hash="hash",
        metadata={
            "dataset": "index_constituents",
            "item_type": "index_constituents",
            "index_code": "000300",
        },
    )

    table = connector.parse_table(raw)
    records = connector.normalize_bars(
        dataset="index_constituents",
        table=table,
        raw_uri="raw://csindex",
        content_hash="hash",
    )

    assert table.rows[0]["securityCode"] == "300308"
    assert records[0].payload["index_code"] == "000300"
    assert records[0].payload["as_of"] == "2026-06-09"
    assert records[0].payload["constituents"] == [
        {
            "entity_id": "300308.SZ",
            "name": "中际旭创",
            "name_en": "ZHONGJI INNOLIGHT CO., LTD.",
            "weight": 3.28,
            "market": "深圳证券交易所",
            "rank": None,
        }
    ]


def test_csindex_fetches_current_top10_endpoint(monkeypatch):
    connector = CsindexMarketConnector()
    calls = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"code": "200", "data": {"weightList": []}, "success": True}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(connector._session, "get", fake_get)

    raw = connector.fetch(
        "index_constituents",
        DiscoveryItem(
            item_id="csindex_index_constituents_000300",
            item_type="index_constituents",
            params={"index_code": "000300"},
        ),
    )

    assert calls[0][0].endswith("/csindex-home/index/weight/top10new/000300")
    assert raw.metadata["source_scope"] == "top10_weight"
