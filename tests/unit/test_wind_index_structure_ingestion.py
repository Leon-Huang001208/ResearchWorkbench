"""Wind index structure probe ingestion tests."""

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_layer.repositories.base import Base
from data_layer.repositories.market_data_repository import MarketDataRepository
from services.wind_index_structure_probe import ProbeResultRow, ProbeSnapshot


def test_persist_probe_snapshot_writes_index_etf_link_and_daily_metric():
    from services.wind_index_structure_ingestion import persist_probe_snapshot

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    repo = MarketDataRepository(session)

    trade_date = datetime(2026, 6, 25, tzinfo=timezone.utc)
    snapshot = ProbeSnapshot(
        status="ok",
        updated_at=trade_date,
        error_count=0,
        rows=(
            _probe("index:000300.SH:index_name_wss", "index", "000300.SH", "index_name_wss", "沪深300"),
            _probe("etf:510300.SH:etf_name_wss", "etf", "510300.SH", "etf_name_wss", "沪深300ETF华泰柏瑞"),
            _probe(
                "etf:510300.SH:etf_tracking_index_wss",
                "etf",
                "510300.SH",
                "etf_tracking_index_wss",
                "000300.SH",
            ),
            _probe("etf:510300.SH:etf_nav_wss", "etf", "510300.SH", "etf_nav_wss", 4.9707),
            _probe(
                "etf:510300.SH:etf_shares_unit_total_wss",
                "etf",
                "510300.SH",
                "etf_shares_unit_total_wss",
                22886587700,
            ),
            _probe(
                "etf:510300.SH:etf_aum_netasset_total_wss",
                "etf",
                "510300.SH",
                "etf_aum_netasset_total_wss",
                199913855988.24,
            ),
        ),
    )

    summary = persist_probe_snapshot(repo, snapshot, trade_date=trade_date)

    assert summary == {
        "index_master": 1,
        "etf_master": 1,
        "index_etf_link": 1,
        "etf_daily_metric": 1,
    }
    memberships = repo.get_index_etfs("CSI:000300")
    metrics = repo.get_etf_daily_metrics("510300.SH")
    assert memberships[0]["etf_symbol"] == "510300.SH"
    assert memberships[0]["name"] == "沪深300ETF华泰柏瑞"
    assert float(metrics[0].nav) == 4.9707
    assert float(metrics[0].shares_outstanding) == 22886587700
    assert float(metrics[0].aum) == 199913855988.24

    session.close()


def test_infer_index_id_handles_cni_hsi_and_wind_codes():
    from services.wind_index_structure_ingestion import infer_index_id

    assert infer_index_id("000300.SH") == "CSI:000300"
    assert infer_index_id("399001.SZ") == "CNI:399001"
    assert infer_index_id("HSI.HI") == "HSI:HSI"
    assert infer_index_id("8841701.WI") == "WIND:8841701"


def _probe(probe_id: str, domain: str, target_code: str, formula_key: str, value):
    return ProbeResultRow(
        probe_id=probe_id,
        domain=domain,
        target_code=target_code,
        formula_key=formula_key,
        label=formula_key,
        formula_text="",
        value=value,
        updated_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
    )
