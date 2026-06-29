"""Official index structure ingestion tests."""

from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_layer.repositories.base import Base
from data_layer.repositories.market_data_repository import MarketDataRepository


def test_ingest_csi_index_components_persists_full_weight_snapshot():
    from services.official_index_structure_ingestion import ingest_csi_index_components

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    repo = MarketDataRepository(session)

    class FakeAk:
        @staticmethod
        def index_stock_cons_weight_csindex(symbol: str):
            assert symbol == "000300"
            return pd.DataFrame(
                [
                    {
                        "日期": "2026-05-29",
                        "指数代码": "000300",
                        "指数名称": "沪深300",
                        "成分券代码": "000001",
                        "成分券名称": "平安银行",
                        "交易所": "深圳证券交易所",
                        "权重": "0.397",
                    },
                    {
                        "日期": "2026-05-29",
                        "指数代码": "000300",
                        "指数名称": "沪深300",
                        "成分券代码": "600519",
                        "成分券名称": "贵州茅台",
                        "交易所": "上海证券交易所",
                        "权重": 5.12,
                    },
                ]
            )

    summary = ingest_csi_index_components(repo, "000300", ak_module=FakeAk)

    assert summary == {"index_master": 1, "index_component_snapshot": 2}
    rows = repo.get_index_components("CSI:000300", source="csindex_official_akshare")
    assert [row.component_symbol for row in rows] == ["600519.SH", "000001.SZ"]
    assert rows[0].component_name == "贵州茅台"
    assert float(rows[0].weight_pct) == 5.12
    assert rows[0].source_scope == "full"

    session.close()


def test_ingest_cni_index_components_persists_stock_membership_lookup():
    from services.official_index_structure_ingestion import ingest_cni_index_components

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    repo = MarketDataRepository(session)

    class FakeAk:
        @staticmethod
        def index_detail_hist_cni(symbol: str):
            assert symbol == "399001"
            return pd.DataFrame(
                [
                    {
                        "日期": datetime(2026, 5, 29),
                        "样本代码": "000937",
                        "样本简称": "冀中能源",
                        "所属行业": "能源",
                        "总市值": 192.22,
                        "权重": 0.03,
                    }
                ]
            )

        @staticmethod
        def index_all_cni():
            return pd.DataFrame(
                [
                    {
                        "指数代码": "399001",
                        "指数简称": "深证成指",
                    }
                ]
            )

    summary = ingest_cni_index_components(repo, "399001", ak_module=FakeAk)

    assert summary == {"index_master": 1, "index_component_snapshot": 1}
    memberships = repo.get_stock_index_memberships(
        "000937.SZ",
        source="cnindex_official_akshare",
    )
    assert memberships[0]["index_id"] == "CNI:399001"
    assert memberships[0]["index_name"] == "深证成指"
    assert float(memberships[0]["weight_pct"]) == 0.03

    session.close()


def test_discover_official_index_codes_reads_provider_catalogs():
    from services.official_index_structure_ingestion import discover_official_index_codes

    class FakeAk:
        @staticmethod
        def index_csindex_all():
            return pd.DataFrame(
                [
                    {"指数代码": "300", "指数名称": "沪深300"},
                    {"指数代码": "000905", "指数名称": "中证500"},
                    {"指数代码": "", "指数名称": "空值"},
                ]
            )

        @staticmethod
        def index_all_cni():
            return pd.DataFrame(
                [
                    {"指数代码": "399001", "指数简称": "深证成指"},
                    {"指数代码": "399006", "指数简称": "创业板指"},
                ]
            )

    assert discover_official_index_codes("CSI", max_count=2, ak_module=FakeAk) == [
        "000300",
        "000905",
    ]
    assert discover_official_index_codes("CNI", max_count=1, ak_module=FakeAk) == ["399001"]
