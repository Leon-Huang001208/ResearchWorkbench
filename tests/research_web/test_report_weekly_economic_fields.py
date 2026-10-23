"""Host checks economic fields against immutable local Excel bytes, without Office."""

import copy
import json
from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook
from test_datahub_wind_excel_weekly import (
    native_export_observation,
    package,
    replace_resource,
    save_observation,
)
from test_report_weekly_data import synthetic_snapshot

from app.research_web.report_workflows.weekly_data import assess_weekly_snapshot
from app.research_web.report_workflows.weekly_sources import SOURCE_CONTRACT


def economic_package(root, *, previous=0):
    contract, source, manifest, save = package(root)
    book = Workbook()
    book.active.title = "经济数据"
    second = book.create_sheet("财经大事")
    header = ["日期", "时间", "国家/地区", "指标名称", "重要性", "前值", "预测值", "今值"]
    book.active.append(header)
    day = contract["next_calendar_start"]
    book.active.append(
        [date.fromisoformat(day), "09:00", "中国", "测试指标", "中等", previous, -49.97, 118]
    )
    book.active.append(["数据来源: Wind"])
    second.append(header[:5])
    second.append([date.fromisoformat(day), "待定", "美国", "测试事件", "低"])
    second.append(["数据来源: Wind"])
    stream = BytesIO()
    book.save(stream)
    book.close()
    sha = replace_resource(manifest, save, "inputs/calendar.xlsx", stream.getvalue())
    export = source["excel_exports"]["economic_calendar"]
    export.update(sha256=sha, sheet="经济数据", additional_sheets=["财经大事"])
    observation = native_export_observation(sha, contract)
    observation["pages"]["economic_data"]["sheet"] = "经济数据"
    observation["pages"]["financial_events"].update(
        sheet="财经大事", result="exported", message=None
    )
    save_observation(root, source, manifest, save, observation)
    proof = json.loads((root / "inputs/coverage.json").read_bytes())
    proof["windows"][0]["sha256"] = sha
    export["coverage_evidence_sha256"] = replace_resource(
        manifest, save, "inputs/coverage.json", json.dumps(proof).encode()
    )
    replace_resource(manifest, save, SOURCE_CONTRACT, json.dumps(source).encode())
    snapshot = synthetic_snapshot(contract)
    snapshot.update(
        collection_policy="wind-excel-weekly-v1",
        acquisition_kind="current_period",
        acquisition_started_at=contract["cutoff"],
        frozen_at=contract["cutoff"],
    )
    for item in [*snapshot["series"].values(), *snapshot["calendars"].values()]:
        item["retrieved_at"] = contract["cutoff"]
    snapshot["economic_calendar"].update(
        raw_sha256=sha,
        raw_payload=export,
        events=[
            {
                "date": day,
                "source_sheet": "经济数据",
                "time": "09:00",
                "country": "中国",
                "indicator": "测试指标",
                "importance": "较重要",
                "previous": previous,
                "forecast": -49.97,
                "actual": 118,
            },
            {
                "date": day,
                "source_sheet": "财经大事",
                "time": "待定",
                "country": "美国",
                "indicator": "测试事件",
                "importance": "一般",
                "previous": None,
                "forecast": None,
                "actual": None,
            },
        ],
    )
    return contract, source, manifest, save, snapshot


def assess(root, contract, manifest, snapshot, **kwargs):
    return assess_weekly_snapshot(snapshot, contract, run_root=root, manifest=manifest, **kwargs)


def test_host_accepts_native_values_and_absent_financial_columns(tmp_path):
    contract, _, manifest, _, snapshot = economic_package(tmp_path)
    result = assess(tmp_path, contract, manifest, snapshot)
    assert result["status"] == "passed", result["issues"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("time", "10:00"),
        ("previous", 1),
        ("previous", False),
        ("previous", 0.0),
        ("forecast", 49.97),
        ("actual", None),
        ("country", "其他"),
        ("indicator", "其他"),
        ("importance", "重要"),
        ("source_sheet", "财经大事"),
        ("date", "2026-10-20"),
    ],
)
def test_host_rejects_event_field_tampering(tmp_path, field, value):
    contract, _, manifest, _, snapshot = economic_package(tmp_path)
    snapshot["economic_calendar"]["events"][0][field] = value
    result = assess(tmp_path, contract, manifest, snapshot)
    assert result["status"] == "blocked_data", result
    assert "weekly_excel_economic_replay_unverified" in result["issues"]


@pytest.mark.parametrize(
    "attack", ["delete_field", "delete_event", "insert_event", "reorder", "raw_sha", "raw_payload"]
)
def test_host_rejects_missing_inserted_or_reordered_events(tmp_path, attack):
    contract, _, manifest, _, snapshot = economic_package(tmp_path)
    calendar = snapshot["economic_calendar"]
    if attack == "delete_field":
        del calendar["events"][0]["previous"]
    elif attack == "delete_event":
        calendar["events"].pop()
    elif attack == "insert_event":
        calendar["events"].append(copy.deepcopy(calendar["events"][0]))
    elif attack == "reorder":
        calendar["events"].reverse()
    elif attack == "raw_sha":
        calendar["raw_sha256"] = "f" * 64
    else:
        calendar["raw_payload"] = {}
    assert (
        "weekly_excel_economic_replay_unverified"
        in assess(tmp_path, contract, manifest, snapshot)["issues"]
    )


@pytest.mark.parametrize("context", ["root", "manifest", "resource", "contract", "bytes"])
def test_host_requires_immutable_run_context(tmp_path, context):
    contract, _, manifest, _, snapshot = economic_package(tmp_path)
    root = tmp_path
    if context == "root":
        root = None
    elif context == "manifest":
        manifest = None
    elif context == "resource":
        manifest["resources"][:] = [
            r for r in manifest["resources"] if r["path"] != SOURCE_CONTRACT
        ]
    elif context == "contract":
        (root / SOURCE_CONTRACT).write_text("{}")
    else:
        (root / "inputs/calendar.xlsx").write_bytes(b"changed")
    result = assess(root, contract, manifest, snapshot)
    assert "weekly_excel_economic_replay_unverified" in result["issues"]


def test_require_excel_flag_replays_even_without_collection_tag(tmp_path):
    contract, _, manifest, _, snapshot = economic_package(tmp_path)
    del snapshot["collection_policy"]
    snapshot["economic_calendar"]["events"][0]["actual"] = "forged"
    result = assess(tmp_path, contract, manifest, snapshot, require_excel_acquisition=True)
    assert "weekly_excel_economic_replay_unverified" in result["issues"]


@pytest.mark.parametrize("value", [False, True, float("nan"), float("inf"), -float("inf"), [], {}])
def test_host_rejects_unsupported_snapshot_optional_values(tmp_path, value):
    contract, _, manifest, _, snapshot = economic_package(tmp_path)
    snapshot["economic_calendar"]["events"][0]["previous"] = value
    assert assess(tmp_path, contract, manifest, snapshot)["status"] == "blocked_data"


def test_host_rejects_unsupported_native_excel_scalar(tmp_path):
    contract, _, manifest, _, snapshot = economic_package(tmp_path, previous=False)
    snapshot["economic_calendar"]["events"][0]["previous"] = 0
    result = assess(tmp_path, contract, manifest, snapshot)
    assert "weekly_excel_economic_replay_unverified" in result["issues"]
