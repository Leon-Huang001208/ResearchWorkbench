"""资产候选搜索索引测试。"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_layer.repositories.base import Base
from data_layer.repositories.models import Entity, StockMasterDB
from services.asset_search_index_service import AssetSearchIndexService, _etf_suffix


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
    db_session.add(_stock("6005191.SH", "茅台扩展样本", "食品饮料"))
    db_session.commit()

    results = AssetSearchIndexService(db_session).search("600519")

    assert [item["symbol"] for item in results[:2]] == ["600519.SH", "6005191.SH"]
    assert results[0]["match_type"] == "exact_code"
    assert results[1]["match_type"] == "code_prefix"
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


# ── ETF suffix rules ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw_code", "expected_suffix"),
    [
        ("159267", "SZ"),  # 深交所 ETF 159xxx
        ("510050", "SH"),  # 上交所 ETF 51xxxx
        ("588000", "SH"),  # 上交所 ETF 58xxxx
        ("169101", "SZ"),  # 深交所 LOF 16xxxx
        ("600000", "SH"),  # 上交所股票 6xxxxx
        ("000001", "SZ"),  # 深交所股票 0xxxxx
        ("300750", "SZ"),  # 创业板 3xxxxx
        ("200001", "SZ"),  # 深交所
        ("", "SH"),  # 空代码默认 SH
    ],
)
def test_etf_suffix_rules(raw_code, expected_suffix):
    """验证 ETF 代码到交易所后缀的映射规则。"""
    assert _etf_suffix(raw_code) == expected_suffix


# ── Fund ETF candidate integration ──────────────────────────────────


def test_fund_candidates_yields_etf_entries(db_session):
    """验证 _fund_candidates 从缓存返回 ETF 候选项。"""
    mock_data = [
        {
            "raw_code": "159267",
            "symbol": "159267.SZ",
            "name": "航天ETF华安",
            "exchange": "SZ",
            "market": "A-share",
        },
        {
            "raw_code": "510050",
            "symbol": "510050.SH",
            "name": "上证50ETF",
            "exchange": "SH",
            "market": "A-share",
        },
    ]
    with patch("services.asset_search_index_service._build_fund_cache", return_value=mock_data):
        service = AssetSearchIndexService(db_session)
        candidates = list(service._fund_candidates())
        assert len(candidates) == 2
        assert candidates[0].symbol == "159267.SZ"
        assert candidates[0].name == "航天ETF华安"
        assert candidates[0].asset_type == "etf"
        assert candidates[0].source == "fund_etf"
        assert candidates[1].symbol == "510050.SH"


def test_fund_search_finds_etf_by_code(db_session):
    """端到端测试：搜索 159267 可找到 ETF。"""
    mock_data = [
        {
            "raw_code": "159267",
            "symbol": "159267.SZ",
            "name": "航天ETF华安",
            "exchange": "SZ",
            "market": "A-share",
        },
        {
            "raw_code": "510050",
            "symbol": "510050.SH",
            "name": "上证50ETF",
            "exchange": "SH",
            "market": "A-share",
        },
    ]
    with patch("services.asset_search_index_service._build_fund_cache", return_value=mock_data):
        service = AssetSearchIndexService(db_session)
        results = service.search("159267")
        assert len(results) >= 1
        result = next(r for r in results if r["symbol"] == "159267.SZ")
        assert result["name"] == "航天ETF华安"
        assert result["asset_type"] == "etf"
        assert result["match_type"] == "exact_code"
        assert result["score"] == 1000


def test_fund_search_finds_etf_by_name(db_session):
    """端到端测试：按名称搜索 ETF。"""
    mock_data = [
        {
            "raw_code": "159267",
            "symbol": "159267.SZ",
            "name": "航天ETF华安",
            "exchange": "SZ",
            "market": "A-share",
        },
    ]
    with patch("services.asset_search_index_service._build_fund_cache", return_value=mock_data):
        service = AssetSearchIndexService(db_session)
        results = service.search("航天")
        assert len(results) >= 1
        assert results[0]["symbol"] == "159267.SZ"
        assert results[0]["asset_type"] == "etf"


def test_fund_candidates_graceful_fallback_when_akshare_raises(db_session):
    """AKShare 失败时 _fund_candidates 返回空列表，不抛异常。"""
    with patch(
        "services.asset_search_index_service._build_fund_cache",
        side_effect=ImportError("No akshare"),
    ):
        service = AssetSearchIndexService(db_session)
        candidates = list(service._fund_candidates())
        assert candidates == []


def test_fund_cache_empty_after_failure(db_session):
    """AKShare 返回空数据时 _fund_count 返回 0。"""
    import services.asset_search_index_service as svc

    # 重置模块级缓存，确保干净的测试状态
    svc._FUND_CACHE = None
    svc._FUND_CACHE_TIME = 0.0

    with patch.object(svc, "_build_fund_cache", return_value=[]):
        service = AssetSearchIndexService(db_session)
        status = service.status()
        assert status["fund_etf_count"] == 0


def test_fund_deduplicates_against_stock_master(db_session):
    """ETF 候选在 stock_master 已有相同 code 时不应覆盖。"""
    db_session.add(_stock("159267.SZ", "航天ETF（已有）", "金融"))
    db_session.commit()
    mock_data = [
        {
            "raw_code": "159267",
            "symbol": "159267.SZ",
            "name": "航天ETF华安",
            "exchange": "SZ",
            "market": "A-share",
        },
    ]
    with patch("services.asset_search_index_service._build_fund_cache", return_value=mock_data):
        service = AssetSearchIndexService(db_session)
        results = service.search("159267")
        # stock_master 的候选项在前，ETF 候选不应重复
        symbols = [r["symbol"] for r in results]
        assert symbols.count("159267.SZ") == 1
        # stock_master 优先（source 不是 fund_etf）
        result = next(r for r in results if r["symbol"] == "159267.SZ")
        assert result["source"] == "stock_master"
