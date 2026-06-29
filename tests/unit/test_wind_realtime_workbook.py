"""Wind realtime workbook generation and snapshot parsing tests."""


def test_build_realtime_workbook_writes_view_ranges(tmp_path):
    from openpyxl import load_workbook

    from services.wind_realtime_workbook import build_realtime_workbook

    catalog_path = tmp_path / "wind_index_catalog.csv"
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    catalog_path.write_text(
        "wind_code,name,family,category,is_active,priority,is_concept,view_key,view_label\n"
        "CI005001.WI,石油石化,citic_l1,中信一级行业,true,100,false,citic_l1,中信一级\n"
        "CI005002.WI,煤炭,citic_l1,中信一级行业,true,99,false,citic_l1,中信一级\n"
        "801010.SI,农林牧渔,sw_l1,申万一级行业,true,90,false,sw_l1,申万一级\n",
        encoding="utf-8",
    )

    build_realtime_workbook(catalog_path, workbook_path)

    workbook = load_workbook(workbook_path, data_only=False, read_only=True)
    assert "ViewRanges" in workbook.sheetnames
    rows = list(workbook["ViewRanges"].iter_rows(values_only=True))
    assert rows[0] == (
        "view_key",
        "view_label",
        "snapshot_start_row",
        "row_count",
        "updated_at",
    )
    assert rows[1][:4] == ("citic_l1", "中信一级", 2, 2)
    assert rows[2][:4] == ("sw_l1", "申万一级", 4, 1)
    assert "RealtimeRaw" in workbook.sheetnames
    assert "Snapshot" in workbook.sheetnames
    assert workbook["RealtimeRaw"]["F2"].value == (
        '=wss("CI005001.WI,CI005002.WI","sec_name,rt_last,rt_pct_chg",'
        '"cols=3;rows=2")'
    )
    assert workbook["RealtimeRaw"]["F4"].value == (
        '=wss("801010.SI","sec_name,rt_last,rt_pct_chg","cols=3;rows=1")'
    )
