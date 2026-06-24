"""Wind index catalog tests."""


def test_load_wind_index_catalog_normalizes_codes_and_filters_inactive(tmp_path):
    from services.wind_index_catalog import load_wind_index_catalog

    catalog_path = tmp_path / "wind_index_catalog.csv"
    catalog_path.write_text(
        "wind_code,name,family,category,is_active,priority,is_concept,view_key,view_label\n"
        "8841701,GPU指数,wind_concept,热门概念,true,10,true,wind_hot_concept,Wind热门概念\n"
        "8841738.WI,HBM指数,wind_concept,热门概念,false,9,true,wind_hot_concept,Wind热门概念\n",
        encoding="utf-8",
    )

    entries = load_wind_index_catalog(catalog_path)

    assert [entry.code for entry in entries] == ["8841701.WI"]
    assert entries[0].name == "GPU指数"
    assert entries[0].is_concept is True
    assert entries[0].view_key == "wind_hot_concept"
    assert entries[0].view_label == "Wind热门概念"


def test_provider_prefers_catalog_entries_over_builtin_seeds(tmp_path):
    import pandas as pd

    from services.wind_market_overview_provider import WindMarketOverviewProvider

    catalog_path = tmp_path / "wind_index_catalog.csv"
    catalog_path.write_text(
        "wind_code,name,family,category,is_active,priority,is_concept,view_key,view_label\n"
        "8841701,GPU指数,wind_concept,热门概念,true,10,true,wind_hot_concept,Wind热门概念\n",
        encoding="utf-8",
    )

    class FakeWindAdapter:
        def is_available(self):
            return True

        def fetch_index_quotes(self, codes, trade_date=None):
            assert codes == ["8841701.WI"]
            return pd.DataFrame(
                [
                    {
                        "code": "8841701.WI",
                        "name": "GPU指数",
                        "close": 1000.0,
                        "pct_change": 4.8,
                    }
                ]
            )

    provider = WindMarketOverviewProvider(
        adapter=FakeWindAdapter(),
        trade_date_provider=lambda: "2026-06-18",
        catalog_path=catalog_path,
    )

    up, down, has_real_data, _ = provider.get_top_movers(limit=10)

    assert has_real_data is True
    assert [item["name"] for item in up] == ["GPU指数"]
    assert down == []


def test_expand_wind_code_ranges_normalizes_codes():
    from services.wind_index_catalog import expand_wind_code_ranges

    codes = expand_wind_code_ranges(["8841701-8841703", "886001.WI"])

    assert codes == ("8841701.WI", "8841702.WI", "8841703.WI", "886001.WI")


def test_catalog_derives_view_key_for_known_families(tmp_path):
    from services.wind_index_catalog import load_wind_index_catalog

    catalog_path = tmp_path / "wind_index_catalog.csv"
    catalog_path.write_text(
        "wind_code,name,family,category,is_active,priority,is_concept\n"
        "886001.WI,Wind一级样本,wind_l1,Wind一级行业,true,9,false\n"
        "CI005001.WI,中信三级样本,citic_l3,中信三级行业,true,8,false\n"
        "801010.SI,申万一级样本,sw_l1,申万一级行业,true,7,false\n",
        encoding="utf-8",
    )

    entries = load_wind_index_catalog(catalog_path)

    assert [entry.view_key for entry in entries] == ["wind_l1", "citic_l3", "sw_l1"]
    assert [entry.view_label for entry in entries] == ["Wind一级", "中信三级", "申万一级"]


def test_default_catalog_includes_shenwan_industry_levels():
    from services.wind_index_catalog import load_wind_index_catalog

    entries = load_wind_index_catalog()
    counts = {
        key: sum(1 for entry in entries if entry.view_key == key)
        for key in ("sw_l1", "sw_l2", "sw_l3")
    }

    assert counts == {"sw_l1": 31, "sw_l2": 131, "sw_l3": 336}
    assert any(entry.code == "801010.SI" and entry.name == "农林牧渔" for entry in entries)
    assert any(entry.code == "801012.SI" and entry.name == "农产品加工" for entry in entries)
    assert any(entry.code == "850111.SI" and entry.name == "种子" for entry in entries)
