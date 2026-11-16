"""Account-owned strategy research contracts for archive IO, execution and pagination."""

import hashlib
import io
import json
import sqlite3
import struct
import zipfile
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_web.strategy_validation import engine, routes, storage
from app.research_web.strategy_validation.routes import router

BASE = "/api/research/strategy-validation"
ACTION = {"X-Research-User-Action": "?1"}
ZIP_HEADERS = {**ACTION, "Content-Type": "application/zip"}
RUN_HEADERS = {**ACTION, "Idempotency-Key": "study-fixture-1"}


def _client(root):
    root.mkdir(exist_ok=True)
    app = FastAPI()
    app.state.research = SimpleNamespace(store=SimpleNamespace(root=root))
    app.include_router(router)
    return TestClient(app)


def _archive(files, extra=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            prefix = "" if name == "data-spec.json" else "data/"
            archive.writestr(f"exit-backtest/{prefix}{name}", raw)
        archive.writestr("exit-backtest/engine.py", b"raise RuntimeError('must never execute')")
        archive.writestr("exit-backtest/example-results/summary.csv", b"fabricated result")
        if extra:
            archive.writestr(*extra)
    return output.getvalue()


@pytest.fixture
def files(monkeypatch):
    fields = dict.fromkeys(storage.REFERENCES, b"ignored\n")
    spec = b'{"test":"test frozen input"}'
    monkeypatch.setattr(storage, "SPEC_DIGEST", storage.digest(spec))
    codes = [f"sh.{600000 + i}" for i in range(160)]
    fields["universe.csv"] = ("code\n" + "\n".join(codes) + "\n").encode()
    fields["stock-basic.csv"] = (
        "code,type\n" + "\n".join(f"{code},1" for code in codes) + "\n"
    ).encode()
    fields["calendar.csv"] = b"calendar_date,is_trading_day\n2022-01-04,1\n"
    bars = b"date,close\n2022-01-04,1.00\n"
    fields["bars-receipts.json"] = json.dumps(
        {code: {"rows": 1, "sha256": storage.digest(bars)} for code in codes}
    ).encode()
    return {
        **fields,
        **{f"bars/{code}.csv": bars for code in codes},
        "source.json": json.dumps(
            {
                "source": "BaoStock SDK",
                "source_doc": "https://baostock.com/baostock/index.php/Python_API文档",
                "spec_sha256": storage.digest(spec),
                "files": {name: storage.digest(blob) for name, blob in fields.items()},
            }
        ).encode(),
        "data-spec.json": spec,
    }


def _submit(client, files):
    raw = _archive(files)
    response = client.post(BASE + "/datasets", headers=ZIP_HEADERS, content=raw)
    assert response.status_code == 201, response.text
    assert response.json()["sha256"] == hashlib.sha256(raw).hexdigest()
    return response.json()


def _engine(path, config):
    assert sorted(path.iterdir()) and "dataset_id" not in config
    assert not (path / "engine.py").exists()
    assert not (path / "example-results").exists()
    events = [
        {
            "rule": config["rules"][0],
            "date": "2022-01-04",
            "ticker": "sh.600000",
            "hold_return": None,
            "sell_advantage": None,
            "open_executable": False,
            "control_ticker": None,
            "control_return": None,
            "match_distance": None,
        },
        {
            "rule": config["rules"][0],
            "date": "2022-01-05",
            "ticker": "sh.600000",
            "hold_return": -0.01,
            "sell_advantage": 0.02,
            "open_executable": True,
            "control_ticker": "sh.600001",
            "control_return": -0.02,
            "match_distance": 0.205,
        },
    ]
    return {"rules": [{"id": config["rules"][0]}], "coverage": {"raw_rows": 160}}, iter(events)


def _request(dataset, **overrides):
    return {"dataset_id": dataset["id"], "rules": ["sma5_close"], **overrides}


def test_frozen_input_retry_pagination_and_account_isolation(tmp_path, monkeypatch, files):
    root = tmp_path / "owner"
    client = _client(root)
    sibling = _client(tmp_path / "other")
    calls = []

    def calculate(path, config):
        calls.append(config)
        return _engine(path, config)

    monkeypatch.setattr(engine, "run_validation", calculate)
    assert client.get(BASE).json() == {"datasets": [], "runs": []}
    assert not (root / storage.FOLDER).exists()
    dataset = _submit(client, files)
    assert _submit(client, files) == dataset
    with sqlite3.connect(root / storage.FOLDER / storage.DATABASE) as db:
        assert db.execute("SELECT count(*) FROM dataset_files").fetchone()[0] == len(files)
    posted = client.post(BASE + "/runs", headers=RUN_HEADERS, json=_request(dataset))
    assert posted.status_code == 201, posted.text
    run_id = posted.json()["id"]
    restored = _client(root)
    assert (
        restored.post(BASE + "/runs", headers=RUN_HEADERS, json=_request(dataset)).json()
        == posted.json()
    )
    assert len(calls) == 1
    conflict = restored.post(
        BASE + "/runs", headers=RUN_HEADERS, json=_request(dataset, horizon=10)
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "strategy_idempotency_conflict"
    detail = restored.get(f"{BASE}/runs/{run_id}").json()
    assert detail["research_only"] is True
    assert detail["historical_pit_verified"] is False
    page = restored.get(f"{BASE}/runs/{run_id}/events?rule=sma5_close&offset=1&limit=1").json()
    assert page == {
        "items": [
            {
                "rule": "sma5_close",
                "date": "2022-01-05",
                "ticker": "sh.600000",
                "hold_return": -0.01,
                "sell_advantage": 0.02,
                "open_executable": True,
                "control_ticker": "sh.600001",
                "control_return": -0.02,
                "match_distance": 0.205,
            }
        ],
        "total": 2,
        "offset": 1,
        "limit": 1,
    }
    assert sibling.get(BASE).json() == {"datasets": [], "runs": []}
    assert sibling.get(f"{BASE}/runs/{run_id}").status_code == 404
    assert (
        sibling.post(BASE + "/runs", headers=RUN_HEADERS, json=_request(dataset)).status_code == 404
    )
    assert sibling.get(f"{BASE}/runs/{run_id}/events?rule=sma5_close").status_code == 404


def test_reject_intent_media_archive_tamper_and_unbounded_config(tmp_path, files):
    client = _client(tmp_path)
    raw = _archive(files)
    assert client.post(BASE + "/datasets", content=raw).status_code == 403
    assert client.post(BASE + "/datasets", headers=ACTION, content=raw).status_code == 415
    traversal = _archive(files, ("exit-backtest/../owned.csv", b"invalid"))
    assert (
        client.post(BASE + "/datasets", headers=ZIP_HEADERS, content=traversal).status_code == 422
    )
    tampered = {**files, "bars/sh.600000.csv": b"date,close\n2022-01-04,2.00\n"}
    response = client.post(BASE + "/datasets", headers=ZIP_HEADERS, content=_archive(tampered))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "strategy_input_digest_mismatch"
    assert client.get(BASE).json() == {"datasets": [], "runs": []}
    dataset = _submit(client, files)
    for overrides in (
        {"rules": ["sma5_close", "sma5_close"]},
        {"rules": []},
        {"horizon": 30},
        {"horizon": True},
        {"high_window": 20.0},
        {"volume_ratio": 500},
        {"sell_cost_bps": 10.1},
        {"enable_production": True},
    ):
        request = _request(dataset, **overrides)
        response = client.post(BASE + "/runs", headers=RUN_HEADERS, json=request)
        assert response.status_code == 422, response.text
    assert client.get(BASE).json()["runs"] == []


def test_self_consistent_receipts_do_not_admit_non_mainboard_or_nonstock(tmp_path, files):
    client = _client(tmp_path)

    def seal(changed):
        source = json.loads(changed["source.json"])
        source["files"] = {name: storage.digest(changed[name]) for name in source["files"]}
        changed["source.json"] = json.dumps(source).encode()
        return _archive(changed)

    unsupported = dict(files)
    target = b"sh.600000"
    replacement = b"sz.300001"
    for name in ("universe.csv", "stock-basic.csv", "bars-receipts.json"):
        unsupported[name] = unsupported[name].replace(target, replacement)
    unsupported["bars/sz.300001.csv"] = unsupported.pop("bars/sh.600000.csv")
    nonstock = dict(files)
    nonstock["stock-basic.csv"] = nonstock["stock-basic.csv"].replace(
        b"sh.600000,1", b"sh.600000,2"
    )
    for archive in (seal(unsupported), seal(nonstock)):
        response = client.post(BASE + "/datasets", headers=ZIP_HEADERS, content=archive)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "strategy_frozen_scope_invalid"


def test_invalid_deflate_is_reported_as_archive_rejection(tmp_path, files):
    client = _client(tmp_path)
    raw = bytearray(_archive(files))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        header = archive.getinfo("exit-backtest/data-spec.json").header_offset
    name_length, extra_length = struct.unpack_from("<HH", raw, header + 26)
    raw[header + 30 + name_length + extra_length] = 0x07
    response = client.post(BASE + "/datasets", headers=ZIP_HEADERS, content=bytes(raw))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "strategy_archive_invalid"


def test_only_one_request_can_buffer_a_body(tmp_path, monkeypatch, files):
    client = _client(tmp_path)
    entered = Event()
    release = Event()
    original = routes._body

    async def hold_body(*args):
        entered.set()
        assert await routes.run_in_threadpool(release.wait, 5)
        return await original(*args)

    monkeypatch.setattr(routes, "_body", hold_body)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(_submit, client, files)
        try:
            assert entered.wait(5)
            assert routes.active()
            with _client(tmp_path) as other:
                response = other.post(
                    BASE + "/datasets", headers=ZIP_HEADERS, content=_archive(files)
                )
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "strategy_validation_busy"
        finally:
            release.set()
        first.result(timeout=10)
    assert not routes.active()


def test_failed_event_rolls_back_and_disconnected_worker_remains_active(
    tmp_path, monkeypatch, files
):
    client = _client(tmp_path)
    dataset = _submit(client, files)
    entered = Event()
    release = Event()

    def fail_after_event(path, config):
        result, items = _engine(path, config)

        def iterator():
            yield next(items)
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test synchronisation failed")
            raise ValueError("failed calculation")

        return result, iterator()

    monkeypatch.setattr(engine, "run_validation", fail_after_event)
    request = _request(dataset)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(client.post, BASE + "/runs", headers=RUN_HEADERS, json=request)
        try:
            assert entered.wait(5)
            assert storage.active()
            assert client.get(BASE).json()["runs"] == []
            busy = client.post(BASE + "/runs", headers=RUN_HEADERS, json=request)
            assert busy.status_code == 409
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 503
    assert not storage.active()
    assert client.get(BASE).json()["runs"] == []
    monkeypatch.setattr(engine, "run_validation", _engine)
    assert client.post(BASE + "/runs", headers=RUN_HEADERS, json=request).status_code == 201
