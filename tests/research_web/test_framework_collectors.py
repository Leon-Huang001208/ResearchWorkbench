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
