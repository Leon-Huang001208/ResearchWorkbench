"""Paired origins change without token migration or foreign-file rollback."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.research_web.control_origin import ControlOriginError, ControlOriginTransaction
from app.research_web.datahub import security
from app.research_web.mcp_runtime import control
from app.research_web.store import StoreError

OLD = "http://127.0.0.1:8088"
NEW = "http://127.0.0.1:18088"
NAMES = ("datahub.json", "mcp-runtime.json")


@pytest.fixture
def root(tmp_path):
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    folder = data / ".control"
    folder.mkdir(mode=0o700)
    for name, value in zip(
        NAMES, ({"token": "x" * 43, "url": OLD}, {"version": 1, "token": "y" * 43, "url": OLD})
    ):
        path = folder / name
        path.write_text(json.dumps(value))
        path.chmod(0o600)
    (data / "business.json").write_bytes(b"unchanged research fixture\n")
    return data


def transaction(root, *, previous=OLD, next_origin=NEW, proof=lambda: True):
    return ControlOriginTransaction(root, previous, next_origin, quiescent=proof)


def snapshots(root):
    return [(root / ".control" / name).read_bytes() for name in NAMES]


def test_prepare_commit_preserves_tokens_and_business_data(root):
    originals = [json.loads(raw) for raw in snapshots(root)]
    tx = transaction(root)
    tx.prepare()
    for old, raw in zip(originals, snapshots(root)):
        assert json.loads(raw) == {**old, "url": NEW}
    journal = (root / ".control" / "origin-transaction.json").read_bytes()
    assert b"x" * 43 not in journal and b"y" * 43 not in journal
    assert b"token" not in journal
    tx.commit()
    assert not (root / ".control" / "origin-transaction.json").exists()
    assert (root / "business.json").read_bytes() == b"unchanged research fixture\n"
    assert security.load_control(root, NEW)["token"] == "x" * 43
    assert control.load_control(root, NEW)["token"] == "y" * 43


def test_failed_target_startup_restores_exact_bytes(root):
    before = snapshots(root)
    tx = transaction(root)
    tx.prepare()
    tx.rollback()
    assert snapshots(root) == before


def test_unchanged_origin_never_writes(root):
    before = [(root / ".control" / n).stat() for n in NAMES]
    tx = transaction(root, next_origin=OLD)
    tx.prepare()
    tx.commit()
    assert [(root / ".control" / n).stat() for n in NAMES] == before


@pytest.mark.parametrize("absent", [NAMES, (NAMES[0],), (NAMES[1],)])
def test_missing_records_remain_missing(root, absent):
    for name in absent:
        (root / ".control" / name).unlink()
    tx = transaction(root)
    tx.prepare()
    tx.commit()
    assert all(not (root / ".control" / name).exists() for name in absent)


def test_missing_control_directory_not_created(tmp_path):
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    tx = transaction(root)
    tx.prepare()
    tx.commit()
    assert not (root / ".control").exists()


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    "kind", ["token", "schema", "wrong_origin", "duplicate", "unsafe_mode", "symlink", "hardlink"]
)
def test_invalid_record_validates_pair_before_writes(root, name, kind):
    path = root / ".control" / name
    if kind in {"token", "schema", "wrong_origin", "duplicate"}:
        value = json.loads(path.read_bytes())
        if kind == "token":
            value["token"] = "bad"
        elif kind == "schema":
            if name == "mcp-runtime.json":
                value["version"] = True
            else:
                del value["url"]
        elif kind == "wrong_origin":
            value["url"] = NEW
        raw = json.dumps(value)
        if kind == "duplicate":
            raw = raw.replace('"url":', '"url": "http://127.0.0.1:8088", "url":')
        path.write_text(raw)
    elif kind == "unsafe_mode":
        path.chmod(0o644)
    elif kind == "symlink":
        saved = root / "saved"
        path.rename(saved)
        path.symlink_to(saved)
    else:
        os.link(path, root / "saved")
    before = snapshots(root)
    with pytest.raises(ControlOriginError):
        transaction(root).prepare()
    assert snapshots(root) == before


@pytest.mark.parametrize("proof", [lambda: False, lambda: None, lambda: "quiescent", lambda: 1])
def test_unknown_or_live_quiescence_rejected(root, proof):
    before = snapshots(root)
    with pytest.raises(ControlOriginError, match="control_origin_not_quiescent"):
        transaction(root, proof=proof).prepare()
    assert snapshots(root) == before


def test_quiescence_rechecked_before_rollback(root):
    state = [True]
    tx = transaction(root, proof=lambda: state[0])
    tx.prepare()
    state[0] = False
    with pytest.raises(ControlOriginError, match="control_origin_not_quiescent"):
        tx.rollback()
    assert all(json.loads(raw)["url"] == NEW for raw in snapshots(root))


def test_commit_after_target_starts_does_not_rebind(root):
    state = [True]
    tx = transaction(root, proof=lambda: state[0])
    tx.prepare()
    before = snapshots(root)
    identities = [(root / ".control" / name).stat() for name in NAMES]
    state[0] = False
    tx.commit()
    assert snapshots(root) == before
    assert [(root / ".control" / name).stat() for name in NAMES] == identities
    assert not (root / ".control" / "origin-transaction.json").exists()


def test_second_write_failure_rolls_back_first(root, monkeypatch):
    from research_workbench_entrypoint import runtime_mode

    original = runtime_mode._atomic_write_posix
    before = snapshots(root)

    def fail_second(path, raw, expected, **kwargs):
        if path.name == "mcp-runtime.json":
            raise OSError("synthetic write failure")
        return original(path, raw, expected, **kwargs)

    monkeypatch.setattr(runtime_mode, "_atomic_write_posix", fail_second)
    with pytest.raises(ControlOriginError, match="control_origin_io"):
        transaction(root).prepare()
    assert snapshots(root) == before


@pytest.mark.parametrize("operation", ["rollback", "commit"])
def test_content_identical_foreign_replacement_refused(root, operation):
    tx = transaction(root)
    tx.prepare()
    path = root / ".control" / "datahub.json"
    replacement = root / ".control" / "replacement"
    replacement.write_bytes(path.read_bytes())
    replacement.chmod(0o600)
    replacement.replace(path)
    before = snapshots(root)
    with pytest.raises(ControlOriginError, match="control_origin_recovery_unverified"):
        getattr(tx, operation)()
    assert snapshots(root) == before


def test_interrupted_journal_blocks_next_transaction(root):
    transaction(root).prepare()
    before = snapshots(root)
    with pytest.raises(ControlOriginError, match="control_origin_interrupted"):
        transaction(root, previous=NEW).prepare()
    assert snapshots(root) == before


@pytest.mark.parametrize("kind", ["permissions", "alias", "replacement"])
def test_unsafe_parent_refused(root, kind):
    tx = transaction(root)
    folder = root / ".control"
    if kind == "permissions":
        folder.chmod(0o755)
    else:
        tx.prepare()
        folder.rename(root / "saved")
        if kind == "alias":
            folder.symlink_to(root / "saved", target_is_directory=True)
        else:
            folder.mkdir(mode=0o700)
    with pytest.raises(ControlOriginError):
        tx.rollback() if kind != "permissions" else tx.prepare()


def test_existing_validators_still_reject_origin_drift(root):
    with pytest.raises(StoreError):
        security.load_control(root, NEW)
    with pytest.raises(control.ControlError):
        control.load_control(root, NEW)


def test_quiescence_callback_exception_is_safe(root):
    def unknown():
        raise RuntimeError("private exception text")

    with pytest.raises(ControlOriginError, match="^control_origin_not_quiescent$"):
        transaction(root, proof=unknown).prepare()


def test_publication_gap_never_guesses_ownership(root, monkeypatch):
    from research_workbench_entrypoint import runtime_mode

    real_write = runtime_mode._atomic_write_posix

    def write_then_lose_receipt(path, raw, expected, **kwargs):
        result = real_write(path, raw, expected, **kwargs)
        if path.name == "mcp-runtime.json":
            raise OSError("publication receipt lost")
        return result

    monkeypatch.setattr(runtime_mode, "_atomic_write_posix", write_then_lose_receipt)
    with pytest.raises(ControlOriginError, match="control_origin_recovery_unverified"):
        transaction(root).prepare()
    assert (root / ".control" / "origin-transaction.json").exists()
    assert all(json.loads(raw)["url"] == NEW for raw in snapshots(root))


def test_foreign_journal_replacement_prevents_commit(root):
    tx = transaction(root)
    tx.prepare()
    path = root / ".control" / "origin-transaction.json"
    replacement = root / ".control" / "foreign"
    replacement.write_bytes(path.read_bytes())
    replacement.chmod(0o600)
    replacement.replace(path)
    with pytest.raises(ControlOriginError, match="control_origin_recovery_unverified"):
        tx.commit()
    assert path.exists()


def test_existing_valid_extra_fields_preserved(root):
    expected = {}
    for name in NAMES:
        path = root / ".control" / name
        value = json.loads(path.read_bytes())
        value["metadata"] = {"owner": "fixture", "sequence": [1, True, None]}
        path.write_text(json.dumps(value))
        expected[name] = {**value, "url": NEW}
    tx = transaction(root)
    tx.prepare()
    tx.commit()
    for name in NAMES:
        assert json.loads((root / ".control" / name).read_bytes()) == expected[name]


def test_helpers_import_without_site_packages():
    checkout = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import research_workbench_entrypoint.runtime_endpoints; "
                "import app.research_web.control_origin"
            ),
            str(checkout),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_expanded_record_limit_checked_before_any_write(root):
    path = root / ".control" / "mcp-runtime.json"
    value = json.loads(path.read_bytes())
    value["padding"] = ""
    value["padding"] = "a" * (4090 - len(json.dumps(value)))
    path.write_text(json.dumps(value))
    before = snapshots(root)
    with pytest.raises(ControlOriginError, match="control_origin_schema"):
        transaction(root).prepare()
    assert snapshots(root) == before
    assert not (root / ".control" / "origin-transaction.json").exists()


def test_original_wrappers_keep_nontransaction_schema_semantics(root):
    extra = {"token": "x" * 43, "url": OLD, "extension": {"enabled": True}}
    assert security._parse_control(json.dumps(extra).encode(), OLD) == extra
    # Strict version types belong only to the new explicit transaction.
    mcp = {**extra, "version": True}
    assert control._parse(json.dumps(mcp).encode(), OLD) == mcp
    with pytest.raises(StoreError, match="DataHub 地址必须为字符串"):
        security._parse_control(json.dumps({**extra, "url": 123}).encode(), OLD)
    with pytest.raises(StoreError, match="DataHub 只接受可信回环服务地址"):
        security.checked_url("https://example.com:443")
