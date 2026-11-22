"""Synthetic isolated pack materials; real Host authority, no provider or model."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import research_web_scenarios_backend as scenarios

base = scenarios.base


def build_fixture(root, output):
    app, research, native = scenarios.build_fixture(root, output)
    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers import Result

    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    day = (today - timedelta(days=1)).isoformat()
    observation = next(
        row
        for row in research.store.data["asset_observations"].values()
        if row["asset"] == "600600.SH"
    )
    sid = observation["session_id"]
    research.store.session(sid)["created"] = True
    query = BusinessQuery(
        capability="market_bars",
        source="baostock",
        parameters={
            "asset": "600600.SH",
            "asset_type": "stock",
            "adjustment": "none",
            "start_date": day,
            "end_date": day,
        },
    )
    dataset = research.datahub.snapshots.publish(
        sid,
        query,
        Result(
            rows=[
                {
                    "asset": "600600.SH",
                    "date": day,
                    "close": 68.2,
                    "trading_status": True,
                    "adjustment": "none",
                }
            ],
            raw=[
                json.dumps(
                    [
                        {
                            "code": "sh.600600",
                            "date": day,
                            "close": "68.2",
                            "adjustflag": "3",
                            "tradestatus": "1",
                        }
                    ]
                ).encode()
            ],
            status="snapshot",
            fields={"close": {"unit": "currency_per_share", "currency": "CNY"}},
            metadata={
                "provider_semantics_revision": "baostock-raw-sh-sz-v1",
                "upstream_id": "baostock",
            },
        ),
        request_query=query,
        authorization_fingerprint=research.datahub.source_configuration_digest("baostock"),
    )
    observation["blocks"]["history"] = {"status": "complete", "dataset": dataset}
    observation["request"]["end_date"] = today.isoformat()
    research.store.save()
    original_rpc = research.client.rpc

    async def rpc(method, payload):
        if method == "skill.list":
            return {
                "skills": [
                    {"name": p.name} for p in research.capabilities.prepare_native_root().iterdir()
                ]
            }
        return await original_rpc(method, payload)

    research.client.rpc = rpc

    @app.get("/__fixture/packs")
    def fixture_packs():
        return {
            "fixture": True,
            "source_session_id": sid,
            "dataset_id": dataset["dataset_id"],
            "as_of": today.isoformat(),
            "release_at": day + "T10:00:00+08:00",
        }

    base.log.info("pack_ui_fixture_ready synthetic=1 provider_calls=0")
    return app, research, native


if __name__ == "__main__":
    base.build_fixture = build_fixture
    base.main()
