"""资产候选搜索索引测试。"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_layer.repositories.base import Base
from data_layer.repositories.models import Entity, StockMasterDB
from services.asset_search_index_service import AssetSearchIndexService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


def _stock(symbol: str, name: str, industry: str = "消费") -> StockMasterDB:
    return StockMasterDB(
        symbol=symbol,
        raw_code=symbol.split(".")[0],
        name=name,
        exchange=symbol.split(".")[1],
        market="A-share",
        industry_level1=industry,
        source="unit-test",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_search_matches_chinese_pinyin_abbr(db_session):
    db_session.add(_stock("600519.SH", "贵州茅台", "食品饮料"))
    db_session.commit()

    results = AssetSearchIndexService(db_session).search("gzmt")

    assert results[0]["symbol"] == "600519.SH"
    assert results[0]["name"] == "贵州茅台"
    assert results[0]["pinyin_abbr"] == "gzmt"
    assert results[0]["source"] == "stock_master"
    assert results[0]["match_type"] in {"pinyin_exact", "pinyin_prefix"}


def test_search_matches_builtin_index_seed_by_abbr(db_session):
    results = AssetSearchIndexService(db_session).search("lsmt")

    assert results[0]["symbol"] == "399436.SZ"
    assert results[0]["name"] == "绿色煤炭"
    assert results[0]["asset_type"] == "index"
    assert results[0]["pinyin_abbr"] == "lsmt"
    assert results[0]["source"] == "seed"


def test_search_enriches_sparse_entity_with_seed_metadata(db_session):
    db_session.add(
        Entity(
            entity_id="entity-600519",
            canonical_id="600519.SH",
            entity_type="equity",
            canonical_name="贵州茅台",
            aliases=[],
            vendor_ids={},
            properties={"symbol": "600519.SH", "market": "global"},
        )
    )
    db_session.commit()

    results = AssetSearchIndexService(db_session).search("gzmt")

    assert results[0]["symbol"] == "600519.SH"
    assert results[0]["market"] == "A-share"
    assert results[0]["industry"] == "食品饮料"
    assert results[0]["source"] == "entity+seed"


def test_search_matches_code_prefix_and_name_fragment(db_session):
    db_session.add(_stock("600519.SH", "贵州茅台", "食品饮料"))
    db_session.commit()
    service = AssetSearchIndexService(db_session)

    assert any(item["symbol"] == "600519.SH" for item in service.search("600"))
    assert service.search("茅台")[0]["symbol"] == "600519.SH"


def test_search_ranks_exact_code_before_prefix_matches(db_session):
    db_session.add(_stock("600519.SH", "贵州茅台", "食品饮料"))
    db_session.add(_stock("600000.SH", "浦发银行", "银行"))
    db_session.commit()

    results = AssetSearchIndexService(db_session).search("600519")

    assert results[0]["symbol"] == "600519.SH"
    assert results[0]["match_type"] in {"exact_code", "code_prefix"}
    assert results[0]["score"] >= results[1]["score"]


def test_status_reports_stock_master_empty_and_seed_fallback(db_session):
    status = AssetSearchIndexService(db_session).status()

    assert status["stock_master_count"] == 0
    assert status["seed_count"] >= 2
    assert status["stock_master_empty"] is True
    assert status["using_seed_fallback"] is True

    db_session.add(_stock("600519.SH", "贵州茅台", "食品饮料"))
    db_session.commit()
    status = AssetSearchIndexService(db_session).status()

    assert status["stock_master_count"] == 1
    assert status["stock_master_empty"] is False
    assert status["using_seed_fallback"] is False
