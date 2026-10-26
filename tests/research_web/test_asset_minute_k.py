"""Minute K keeps vendor interval timestamps, separate from daily aggregates."""

import pytest

from app.research_web.asset_minute_k import normalize_bars, project_prices, rebase_chip_reference


def row(day="2026-05-25", time="09:35:00", **extra):
    return {
        "代码": "SH603986",
        "时间": f"{day} {time}",
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        "vol": 100,
        "amount": 1100,
        "sectional_yclose": 10,
        "sectional_vol": 100,
        "sectional_amount": 1100,
        **extra,
    }


def test_minutes_do_not_collapse_to_date_and_daily_cumulative_resets():
    rows = normalize_bars(
        [
            row(),
            row(time="09:40:00", sectional_vol=200, sectional_amount=2200),
            row(day="2026-05-26"),
        ],
        "603986.SH",
        "5m",
        "2026-05-25",
        "2026-05-26",
    )
    assert len(rows) == 3 and rows[0]["date"].endswith("09:35:00+08:00")
    assert rows[0]["date"] != rows[1]["date"]
    assert rows[0]["volume"] == 100


@pytest.mark.parametrize(
    "cycle,time", [("15m", "09:35:00"), ("60m", "12:00:00"), ("120m", "10:30:00")]
)
def test_rejects_wrong_session_boundaries(cycle, time):
    with pytest.raises(ValueError):
        normalize_bars([row(time=time)], "603986.SH", cycle, "2026-05-25", "2026-05-25")


def test_price_adjustment_uses_one_multiplier_keeps_raw_volume_amount():
    raw = normalize_bars(
        [row(), row(day="2026-05-26")], "603986.SH", "5m", "2026-05-25", "2026-05-26"
    )
    factors = {"2016-08-18": 1, "2026-05-25": 2, "2026-05-26": 4}
    qfq = project_prices(raw, factors, "qfq", "2026-05-26", "2016-08-18")
    hfq = project_prices(raw, factors, "hfq", "2026-05-26", "2016-08-18")
    assert qfq[0]["close"] == 5.5 and qfq[1]["close"] == 11
    assert hfq[0]["close"] == 22 and hfq[1]["close"] == 44
    assert qfq[0]["volume"] == 100 and qfq[0]["amount"] == 1100
    assert qfq[0]["vwap"] == 5.5


def test_chip_rebase_rejects_factor_conflicts_and_does_not_mutate_old_rows():
    raw = [
        {
            "asset": "603986.SH",
            "date": "2026-05-25",
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "volume": 100,
            "amount": 1100,
        }
    ]
    frozen = [{**raw[0], "turnover_rate_pct": 2, "vwap": 11}]
    history = {"raw_rows": raw, "factors": {"2026-05-25": 2}, "anchor_date": "2026-05-25"}
    out = rebase_chip_reference(
        history, frozen, {"2026-05-25": 2, "2026-05-26": 4}, "qfq", "2026-05-26", "2016-08-18"
    )
    assert out[0]["close"] == 5.5 and out[0]["turnover_rate_pct"] == 2
    assert frozen[0]["close"] == 11
    with pytest.raises(ValueError, match="minute_factor_bridge_conflict"):
        rebase_chip_reference(
            history, frozen, {"2026-05-25": 3, "2026-05-26": 4}, "qfq", "2026-05-26", "2016-08-18"
        )


def test_contradictory_auxiliary_fields_preserve_verified_raw_bars_mask_mean():
    rows = normalize_bars(
        [
            row(amount=500, sectional_amount=500),
            row(time="09:40:00", sectional_vol=100, sectional_amount=1600),
        ],
        "603986.SH",
        "5m",
        "2026-05-25",
        "2026-05-25",
    )
    assert rows[0]["close"] == 11 and rows[0]["volume"] == 100
    assert rows[0]["vwap"] is None and rows[0]["quality_flags"] == ["source_vwap_outside_ohlc"]
    assert rows[1]["vwap"] is None and "source_cumulative_mismatch" in rows[1]["quality_flags"]


@pytest.mark.parametrize(
    "changes",
    [
        {"代码": "SH600000"},
        {"vol": -1},
        {"vol": float("nan")},
        {"high": 8},
        {"amount": None},
        {"vol": 0, "amount": 10},
    ],
)
def test_minute_identity_ohlcv_invalid_is_still_rejected(changes):
    with pytest.raises(ValueError):
        normalize_bars([row(**changes)], "603986.SH", "5m", "2026-05-25", "2026-05-25")


@pytest.mark.parametrize(
    "body",
    [
        {"cycle": "2m"},
        {"cycle": "5m", "refresh": 1},
        {"cycle": "5m", "source": "wind"},
        {"cycle": "5m", "formula": "anything"},
    ],
)
def test_minute_request_is_closed(body):
    from pydantic import ValidationError

    from app.research_web.asset_routes import MinuteKRequest

    with pytest.raises(ValidationError):
        MinuteKRequest.model_validate(body)


@pytest.mark.asyncio
async def test_cancelled_consumer_keeps_actual_task_visible_until_workspace_close(tmp_path):
    import asyncio
    from types import SimpleNamespace

    from app.research_web.asset_minute_k import MinuteK
    from app.research_web.store import Store

    store = Store(tmp_path)
    sid = store.create("fingpt", "synthetic minute task witness")["id"]
    entered = asyncio.Event()
    done = asyncio.Event()

    async def query(*_args):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            done.set()

    obs = {"id": "one", "session_id": sid, "asset": "603986.SH", "asset_type": "stock"}
    workspace = SimpleNamespace(
        store=store,
        closed=False,
        tasks={},
        observation=lambda _: obs,
        service=SimpleNamespace(
            datahub=SimpleNamespace(query=query, source_configuration_digest=lambda _: "a" * 64)
        ),
    )
    minute = MinuteK(workspace)
    consumer = asyncio.create_task(minute.load("one", "5m", "none"))
    await asyncio.wait_for(entered.wait(), 1)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer
    assert len(workspace.tasks) == 1 and not done.is_set()
    await minute.close()
    await asyncio.sleep(0)
    assert done.is_set() and not workspace.tasks and not minute.pending
