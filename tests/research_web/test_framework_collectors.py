"""Deterministic public-source conversion and framework scoring regressions."""

import io
import zipfile

import httpx
import pytest

from app.research_web.frameworks.dollar.collector import DollarCollector
from app.research_web.frameworks.dollar.store import DollarSnapshotStore
from app.research_web.frameworks.goldar.collector import GoldCollector
from app.research_web.frameworks.goldar.store import GoldSnapshotStore
from app.research_web.frameworks.sources import fred_series


@pytest.mark.asyncio
async def test_fred_converter_drops_missing_values_and_keeps_observation_dates():
    rows = ["observation_date,SERIES"]
    rows.extend(f"2026-01-{day:02d},{'.' if day == 4 else day}" for day in range(1, 11))

    def handler(request):
        assert request.url.host == "fred.stlouisfed.org"
        return httpx.Response(200, text="\n".join(rows), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        points = await fred_series(client, "SERIES")

    assert len(points) == 9
    assert points[0] == {"date": "2026-01-01", "value": 1.0}
    assert points[-1] == {"date": "2026-01-10", "value": 10.0}


def _cftc_archive(year: int) -> bytes:
    header = (
        "CFTC_Contract_Market_Code,Report_Date_as_YYYY-MM-DD,"
        "M_Money_Positions_Long_All,M_Money_Positions_Short_All\n"
    )
    body = "".join(
        f"088691,{year}-01-{day:02d},{120000 + day * 1000},{50000 + day * 100}\n"
        for day in range(1, 8)
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(f"cftc-{year}.txt", header + body)
    return output.getvalue()


class CftcClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get(self, url, **_):
        year = int(url.rsplit("_", 1)[-1].split(".", 1)[0])
        request = httpx.Request("GET", url)
        return httpx.Response(200, content=_cftc_archive(year), request=request)


@pytest.mark.asyncio
async def test_cftc_refresh_is_idempotent_and_deduplicates_its_source(tmp_path):
    store = GoldSnapshotStore(tmp_path / "gold")
    collector = GoldCollector(store, client_factory=CftcClient)

    await collector.collect_cftc()
    first = store.read()
    first_score = next(
        item.score for item in first.pricing_drivers.factors if item.dimension == "flow"
    )
    await collector.collect_cftc()
    second = store.read()
    second_score = next(
        item.score for item in second.pricing_drivers.factors if item.dimension == "flow"
    )

    assert first_score == second_score
    assert sum("cftc" in item.url.casefold() for item in second.options.sources) == 1
    assert second.options.positioning[0].label == "管理基金净多"


def test_dollar_thresholds_and_high_gap_gate(tmp_path):
    store = DollarSnapshotStore(tmp_path / "dollar")
    collector = DollarCollector(store)
    value = store.read().model_dump(mode="json")
    for block in (
        value["quantity_q"],
        value["price_p"],
        value["fiscal_g"],
        value["plumbing_m"],
        value["cross_border_x"],
    ):
        block.update(status="complete", score=0.16, gaps=[])
    value["transmission"].update(status="complete", gaps=[])

    published = collector._finish(value)
    assert published.status == "偏松"
    assert published.research_state.score == pytest.approx(0.16)

    blocked = published.model_dump(mode="json")
    blocked["cross_border_x"]["gaps"] = [
        {
            "id": "basis",
            "label": "基差不可得",
            "severity": "high",
            "next_check": "补齐可审计来源",
        }
    ]
    gated = collector._finish(blocked)
    assert gated.status == "待核验"
    assert gated.research_state.score is None


class FailingClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get(self, url, **_):
        raise httpx.ConnectError("offline", request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_optional_cftc_failure_preserves_last_good_options_block(tmp_path):
    store = GoldSnapshotStore(tmp_path / "gold")
    value = store.read().model_dump(mode="json")
    value["options"]["status"] = "proxy"
    value["options"]["strikes"][0]["value"] = 987
    store.write(store.model.model_validate(value))

    await GoldCollector(store, client_factory=FailingClient).collect_cftc()

    snapshot = store.read()
    assert snapshot.options.status == "proxy"
    assert snapshot.options.strikes[0].value == 987
    assert snapshot.options.failure_code == "gold_cftc_failed"
    assert any(gap.id == "cftc-refresh" for gap in snapshot.options.gaps)


@pytest.mark.asyncio
async def test_dollar_custody_uses_h41_weekly_treasuries_with_exact_source_date(tmp_path):
    from datetime import date, timedelta
    from urllib.parse import parse_qs

    ids = []
    custody_dates = [(date(2026, 7, 1) + timedelta(days=7 * i)).isoformat() for i in range(10)]
    daily_dates = [(date(2026, 8, 1) + timedelta(days=i)).isoformat() for i in range(45)]
    bases = {
        "WALCL": 6_500_000,
        "WRESBAL": 3_000_000,
        "WDTGAL": 700_000,
        "RRPONTSYD": 100,
        "DFII10": 2,
        "DTWEXBGS": 120,
        "IORB": 4,
        "DGS2": 4,
        "DGS10": 4.5,
        "DEXJPUS": 150,
        "DEXCHUS": 7,
        "DEXUSEU": 1.1,
        "BAMLH0A0HYM2": 3,
        "WMTSECL1": 2_500_000,
        "TRESEGUSM052N": 243_800,
    }

    def handler(request):
        if request.url.host == "fred.stlouisfed.org":
            sid = parse_qs(str(request.url.query.decode()))["id"][0]
            ids.append(sid)
            dates = custody_dates if sid == "WMTSECL1" else daily_dates
            values = [
                bases[sid] + i * (1000 if sid == "WMTSECL1" else 0.01) for i in range(len(dates))
            ]
            return httpx.Response(
                200,
                text="observation_date,"
                + sid
                + "\n"
                + "\n".join(f"{d},{v}" for d, v in zip(dates, values)),
                request=request,
            )
        assert request.url.host == "markets.newyorkfed.org"
        return httpx.Response(
            200,
            json={
                "refRates": [
                    {"type": "SOFR", "effectiveDate": d, "percentRate": 4.0} for d in daily_dates
                ]
            },
            request=request,
        )

    def factory():
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    store = DollarSnapshotStore(tmp_path / "dollar")
    await DollarCollector(store, factory).collect_core()
    snapshot = store.read()
    assert "WMTSECL1" in ids
    assert "TRESEGUSM052N" not in ids
    series = next(s for s in snapshot.cross_border_x.series if "托管" in s.label)
    assert series.unit == "十亿美元"
    assert series.points[-1].date == custody_dates[-1]
    assert series.points[-1].value == pytest.approx(2509.0)
    metric = next(m for m in snapshot.cross_border_x.metrics if "托管" in m.label)
    assert "国际账户" in metric.label
    assert metric.value == "$2509bn"
    assert metric.proxy is False
    assert custody_dates[-1] in metric.interpretation
    source = next(s for s in snapshot.cross_border_x.sources if "WMTSECL1" in s.url)
    assert source.observed_at == custody_dates[-1]
    assert source.unit == "USD billions"
    assert "weekly" in source.method and "Wednesday" in source.method
    assert source.proxy is False
    assert snapshot.cross_border_x.score == pytest.approx(
        -((120.44 / 120.23 - 1) * 100) / 3, abs=0.001
    )


@pytest.mark.asyncio
async def test_unavailable_custody_source_never_republishes_wrong_legacy_value(
    tmp_path, monkeypatch
):
    from app.research_web.frameworks.dollar import collector as module

    async def unavailable(_client, ids):
        assert "WMTSECL1" in ids and "TRESEGUSM052N" not in ids
        request = httpx.Request(
            "GET", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=WMTSECL1"
        )
        response = httpx.Response(503, request=request)
        raise httpx.HTTPStatusError(
            "custody source unavailable", request=request, response=response
        )

    monkeypatch.setattr(module, "fred_series_map", unavailable)
    store = DollarSnapshotStore(tmp_path / "dollar")
    prior = store.read().model_dump(mode="json")
    prior["cross_border_x"].update(status="partial", score=0.1)
    prior["cross_border_x"]["metrics"][-1]["value"] = "$244bn"
    store.write(type(store.read()).model_validate(prior))
    await DollarCollector(store).collect_core()
    after = store.read()
    assert after.cross_border_x.metrics[-1].value == "$244bn"
    assert after.cross_border_x.status == "stale"
    assert after.cross_border_x.failure_code == "dollar_core_failed"
    assert after.status == "待核验"
    assert after.research_state.score is None
