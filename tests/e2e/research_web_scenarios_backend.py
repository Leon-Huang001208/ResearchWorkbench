"""Extend the existing isolated Host fixture with owned asset/legacy inputs only."""

import hashlib
import time
from uuid import uuid4

import research_web_dossiers_backend as base

original_build = base.build_fixture


def build_fixture(root, output):
    app, research, native = original_build(root, output)
    from fastapi.responses import Response

    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers import Result

    def seed(asset, period, unit):
        row = research.store.create("fingpt", "隔离验收 " + asset)
        row["source_scope"] = ["datahub", "web", "uploads"]
        sid = row["id"]

        def publish(capability, parameters, rows, fields=()):
            query = BusinessQuery(capability=capability, source="akshare", parameters=parameters)
            return research.datahub.snapshots.publish(
                sid,
                query,
                Result(
                    rows=rows,
                    raw=[b"offline fixture original"],
                    status="snapshot",
                    as_of="2026-10-26",
                    fields=list(fields),
                ),
                request_query=query,
                authorization_fingerprint=research.datahub.source_configuration_digest("akshare"),
            )

        quote = publish(
            "market_snapshot",
            {"assets": [asset]},
            [{"asset": asset, "name": "隔离验收公司", "price": 100, "as_of": "2026-10-26"}],
        )
        financial = publish(
            "financials",
            {"asset": asset},
            [
                {
                    "asset": asset,
                    "report_period": period,
                    "revenue": 120,
                    "relation_note": "600600.SH向601318.SH供应包装材料",
                }
            ],
            [{"name": "revenue", "unit": unit, "currency": "CNY", "basis": "合并累计"}],
        )
        oid = str(uuid4())
        research.store.data["asset_observations"][oid] = {
            "id": oid,
            "session_id": sid,
            "asset": asset,
            "asset_type": "stock",
            "source": "akshare",
            "status": "completed",
            "created_at": time.time(),
            "updated_at": time.time(),
            "blocks": {
                name: {"status": "complete", "dataset": dataset, "loaded_at": time.time()}
                for name, dataset in [
                    ("overview", quote),
                    ("valuation", quote),
                    ("financials", financial),
                ]
            },
            "request": {
                "asset": asset,
                "asset_type": "stock",
                "source": "akshare",
                "end_date": "2026-10-26",
                "frequency": "daily",
                "adjustment": "none",
            },
        }
        return oid, sid, financial

    oid, sid, financial = seed("600600.SH", "2026-06-30", "万元")
    peer, _, _ = seed("601318.SH", "2026-03-31", "元")
    raw = research.datahub.snapshots.read(sid, financial["dataset_id"], "rows.json")
    proof = {
        "source_session_id": sid,
        "reference": {"type": "dataset", "id": financial["dataset_id"]},
        "sha256": hashlib.sha256(raw).hexdigest(),
        "locator": {
            "kind": "json-cell",
            "row": 0,
            "field": "relation_note",
            "quote": "600600.SH向601318.SH供应包装材料",
        },
    }
    bundle = {
        "schema": "asset-research-workspace/v1",
        "subject": "600600.SH",
        "summaries": [
            {
                "id": "summary-one",
                "title": "经营资料摘录",
                "text": proof["locator"]["quote"],
                "evidence": [proof],
            }
        ],
        "relations": [
            {
                "id": "supply-one",
                "from_identity": "600600.SH",
                "to_identity": "601318.SH",
                "relation": "供应包装材料",
                "evidence": [proof],
            }
        ],
    }
    # An ordinary previously acquired fund snapshot exercises the original
    # non-asset handoff attributes, through the real API and event handler.
    query = BusinessQuery(
        capability="fund_data",
        source="eastmoney_fund",
        parameters={"dataset": "nav", "code": "000001", "limit": 20},
    )
    nav = research.datahub.snapshots.publish(
        sid,
        query,
        Result(
            rows=[{"date": "2026-10-23", "nav": "1.20"}],
            raw=[b"offline fund snapshot"],
            status="snapshot",
            as_of="2026-10-23",
        ),
        request_query=query,
        authorization_fingerprint=research.datahub.source_configuration_digest("eastmoney_fund"),
    )
    qid = str(uuid4())
    research.store.data["data_queries"][qid] = {
        "id": qid,
        "status": "completed",
        "section": "funds",
        "session_id": sid,
        "capability": "fund_data",
        "source": "eastmoney_fund",
        "created_at": time.time(),
        "completed_at": time.time(),
        "duration_ms": 1,
        "failure_code": None,
        "dataset": nav,
    }
    research.store.save()

    @app.get("/__fixture/asset-workspace")
    def fixture_workspace():
        return {
            "fixture": True,
            "observation_id": oid,
            "peer_observation_id": peer,
            "source_session_id": sid,
            "bundle": bundle,
            "legacy_dataset_id": nav["dataset_id"],
        }

    @app.get("/__fixture/banner.css")
    def fixture_banner_style():
        return Response(
            ".fixture-sample-banner{position:fixed;top:0;left:0;right:0;z-index:5000;background:#fff8eb;color:#674b22;text-align:center;font:12px/1.6 sans-serif;padding:3px;pointer-events:none}",
            media_type="text/css",
        )

    @app.middleware("http")
    async def sample_label(request, call_next):
        response = await call_next(request)
        if request.url.path != "/" or response.status_code != 200:
            return response
        raw = b"".join([part async for part in response.body_iterator])
        raw = raw.replace(
            b"</head>", b'<link rel="stylesheet" href="/__fixture/banner.css"></head>', 1
        )
        raw = raw.replace(
            b"<body>",
            '<body><div class="fixture-sample-banner">隔离验收样本 · 数据与关系均为合成测试材料</div>'.encode(),
            1,
        )
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(raw, status_code=response.status_code, headers=headers)

    base.log.info("scenario_fixture_assets_seeded observations=2 legacy_queries=1")
    return app, research, native


if __name__ == "__main__":
    base.build_fixture = build_fixture
    base.main()
