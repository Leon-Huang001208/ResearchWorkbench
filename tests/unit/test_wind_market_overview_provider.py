"""Wind market overview provider tests."""

import pandas as pd


def test_wind_market_overview_provider_sorts_wind_indices_into_movers():
    from services.wind_market_overview_provider import WindMarketOverviewProvider

    class FakeWindAdapter:
        def is_available(self):
            return True

        def fetch_index_quotes(self, codes, trade_date=None):
            assert "8841089.WI" in codes
            assert "884785.WI" in codes
            assert trade_date == "2026-06-18"
            return pd.DataFrame(
                [
                    {
                        "code": "8841089.WI",
                        "name": "稀土指数",
                        "close": 4621.2686,
                        "pct_change": 5.70331748,
                    },
                    {
                        "code": "884785.WI",
                        "name": "锂矿指数",
                        "close": 8039.1544,
                        "pct_change": 7.00346382,
                    },
                    {
                        "code": "886002.WI",
                        "name": "石油天然气指数",
                        "close": 3527.8455,
                        "pct_change": -2.0811498,
                    },
                ]
            )

    provider = WindMarketOverviewProvider(
        adapter=FakeWindAdapter(),
        trade_date_provider=lambda: "2026-06-18",
    )

    up, down, has_real_data, _ = provider.get_top_movers(limit=2)

    assert has_real_data is True
    assert [item["name"] for item in up] == ["锂矿指数", "稀土指数"]
    assert up[0]["sector_id"] == "wind-884785-WI"
    assert up[0]["is_concept"] is True
    assert [item["name"] for item in down] == ["石油天然气指数"]


def test_wind_market_overview_provider_groups_theme_and_industry_movers():
    from services.wind_market_overview_provider import WindMarketOverviewProvider

    class FakeWindAdapter:
        def is_available(self):
            return True

        def fetch_index_quotes(self, codes, trade_date=None):
            return pd.DataFrame(
                [
                    {
                        "code": "8841701.WI",
                        "name": "GPU指数",
                        "close": 1000.0,
                        "pct_change": 4.8,
                    },
                    {
                        "code": "886001.WI",
                        "name": "能源设备指数",
                        "close": 14338.5,
                        "pct_change": 1.74,
                    },
                    {
                        "code": "886002.WI",
                        "name": "石油天然气指数",
                        "close": 3527.8,
                        "pct_change": -2.08,
                    },
                ]
            )

    provider = WindMarketOverviewProvider(
        adapter=FakeWindAdapter(),
        trade_date_provider=lambda: "2026-06-18",
        catalog_path=None,
    )

    grouped = provider.get_grouped_movers(limit=10)

    assert grouped["theme"]["up"][0]["name"] == "GPU指数"
    assert grouped["theme"]["down"] == []
    assert grouped["industry"]["up"][0]["name"] == "能源设备指数"
    assert grouped["industry"]["down"][0]["name"] == "石油天然气指数"


def test_wind_market_overview_provider_groups_configured_market_views(tmp_path):
    from services.wind_market_overview_provider import WindMarketOverviewProvider

    catalog_path = tmp_path / "wind_index_catalog.csv"
    catalog_path.write_text(
        "wind_code,name,family,category,is_active,priority,is_concept,view_key,view_label\n"
        "8841701.WI,GPU指数,wind_concept,热门概念,true,100,true,wind_hot_concept,Wind热门概念\n"
        "886001.WI,Wind一级样本,wind_l1,Wind一级行业,true,90,false,wind_l1,Wind一级\n"
        "886101.WI,Wind四级样本,wind_l4,Wind四级行业,true,80,false,wind_l4,Wind四级\n"
        "CI005001.WI,中信三级样本,citic_l3,中信三级行业,true,70,false,citic_l3,中信三级\n"
        "801010.SI,申万一级样本,sw_l1,申万一级行业,true,60,false,sw_l1,申万一级\n",
        encoding="utf-8",
    )

    class FakeWindAdapter:
        def is_available(self):
            return True

        def fetch_index_quotes(self, codes, trade_date=None):
            assert codes == [
                "8841701.WI",
                "886001.WI",
                "886101.WI",
                "CI005001.WI",
                "801010.SI",
            ]
            return pd.DataFrame(
                [
                    {"code": "8841701.WI", "name": "GPU指数", "close": 1, "pct_change": 2.2},
                    {"code": "886001.WI", "name": "Wind一级样本", "close": 1, "pct_change": 1.1},
                    {"code": "886101.WI", "name": "Wind四级样本", "close": 1, "pct_change": -1.3},
                    {"code": "CI005001.WI", "name": "中信三级样本", "close": 1, "pct_change": 0.9},
                    {"code": "801010.SI", "name": "申万一级样本", "close": 1, "pct_change": -0.8},
                    {"code": "999999.WI", "name": "离谱指数", "close": 1, "pct_change": 88.0},
                ]
            )

    provider = WindMarketOverviewProvider(
        adapter=FakeWindAdapter(),
        trade_date_provider=lambda: "2026-06-18",
        catalog_path=catalog_path,
    )

    grouped = provider.get_grouped_movers(limit=10)

    assert grouped["wind_hot_concept"]["up"][0]["name"] == "GPU指数"
    assert grouped["wind_l1"]["up"][0]["name"] == "Wind一级样本"
    assert grouped["wind_l4"]["down"][0]["name"] == "Wind四级样本"
    assert grouped["citic_l3"]["up"][0]["name"] == "中信三级样本"
    assert grouped["sw_l1"]["down"][0]["name"] == "申万一级样本"
    assert grouped["theme"]["up"][0]["name"] == "GPU指数"
    assert grouped["industry"]["up"][0]["name"] == "Wind一级样本"
    assert all(
        item["name"] != "离谱指数"
        for view in grouped["views"].values()
        for direction in ("up", "down")
        for item in view[direction]
    )


def test_wind_market_overview_provider_filters_requested_market_view(tmp_path):
    from services.wind_market_overview_provider import WindMarketOverviewProvider

    catalog_path = tmp_path / "wind_index_catalog.csv"
    catalog_path.write_text(
        "wind_code,name,family,category,is_active,priority,is_concept,view_key,view_label\n"
        "8841701.WI,GPU指数,wind_concept,热门概念,true,100,true,wind_hot_concept,Wind热门概念\n"
        "882011.WI,房地产,wind_l1,Wind一级行业,true,90,false,wind_l1,Wind一级\n",
        encoding="utf-8",
    )

    class FakeWindAdapter:
        def is_available(self):
            return True

        def fetch_index_quotes(self, codes, trade_date=None):
            assert codes == ["882011.WI"]
            return pd.DataFrame(
                [{"code": "882011.WI", "name": "房地产", "close": 1, "pct_change": -1.2}]
            )

    provider = WindMarketOverviewProvider(
        adapter=FakeWindAdapter(),
        trade_date_provider=lambda: "2026-06-18",
        catalog_path=catalog_path,
    )

    grouped = provider.get_grouped_movers(limit=10, view_keys=("wind_l1",))

    assert grouped["wind_hot_concept"]["up"] == []
    assert grouped["wind_l1"]["down"][0]["name"] == "房地产"
