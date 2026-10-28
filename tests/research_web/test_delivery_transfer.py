"""Cross-common receipt transfer never invents review or remote qualification."""

import json
from pathlib import Path

import pytest

from research_workbench_entrypoint.resident import delivery_transfer as d

SHA = "a" * 40
HEAD = "b" * 40


@pytest.fixture
def roots(tmp_path, monkeypatch):
    src, dst = tmp_path / "source", tmp_path / "destination"
    for root in (src, dst):
        (root / ".git").mkdir(parents=True)
    monkeypatch.setattr(d, "_common", lambda root: root / ".git")
    monkeypatch.setattr(d, "_remote", lambda root: "Leon-Huang001208/ResearchWorkbench")
    monkeypatch.setattr(
        d,
        "_qualify",
        lambda common, target, gh: {
            "sha": target,
            "head": HEAD,
            "pull_request": 244,
            "ci": ["verified-external-boundary"],
        },
    )
    for folder, value in [
        (
            "deliveries",
            {
                "remoteCommit": SHA,
                "integrationCommit": HEAD,
                "status": "ci_passed",
                "mode": "pr",
                "ci": {"status": "passed"},
                "verification": {"status": "passed"},
                "pullRequest": {"number": 244},
            },
        ),
        ("git-safety/reviews", {"reviewedCommit": HEAD, "status": "PASS"}),
    ]:
        p = src / ".git/leon-engineering" / folder / "real-task.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(value))
        p.chmod(0o600)
    return src, dst


def test_preview_and_apply_preserve_exact_original_bytes(roots):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    assert not (dst / ".git/leon-engineering/deliveries").exists()
    result = d.apply(plan)
    assert result["status"] == "verified"
    for folder in ("deliveries", "git-safety/reviews"):
        rel = Path("leon-engineering") / folder / "real-task.json"
        assert (src / ".git" / rel).read_bytes() == (dst / ".git" / rel).read_bytes()
    assert d.apply(plan)["status"] == "verified"


def test_source_change_after_preview_is_rejected(roots):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    (src / ".git/leon-engineering/deliveries/real-task.json").write_text("{}")
    with pytest.raises(d.TransferBlocked, match="source_changed"):
        d.apply(plan)
    assert not (dst / ".git/leon-engineering/deliveries/real-task.json").exists()


def test_conflicting_existing_record_is_preserved(roots):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    p = dst / ".git/leon-engineering/deliveries/real-task.json"
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    p.chmod(0o600)
    with pytest.raises(d.TransferBlocked, match="destination_conflict"):
        d.apply(plan)
    assert p.read_bytes() == b"{}"


def test_remote_failure_never_creates_qualification(roots, monkeypatch):
    src, dst = roots

    def fail(*args):
        raise d.TransferBlocked("remote_unverified")

    monkeypatch.setattr(d, "_qualify", fail)
    with pytest.raises(d.TransferBlocked, match="remote_unverified"):
        d.preview(src, dst, "real-task", SHA)
    assert not (dst / ".git/leon-engineering").exists()


@pytest.mark.parametrize("name", ["../other", "/tmp/a", "bad/name", "", "x" * 129])
def test_task_path_escape_rejected(roots, name):
    with pytest.raises(d.TransferBlocked):
        d.preview(*roots, name, SHA)


def test_wrong_target_and_review_rejected(roots):
    src, dst = roots
    with pytest.raises(d.TransferBlocked):
        d.preview(src, dst, "real-task", "c" * 40)
    p = src / ".git/leon-engineering/git-safety/reviews/real-task.json"
    p.write_text(json.dumps({"reviewedCommit": "c" * 40, "status": "PASS"}))
    with pytest.raises(d.TransferBlocked):
        d.preview(src, dst, "real-task", SHA)


def test_symlink_receipt_is_never_followed(roots):
    src, dst = roots
    p = src / ".git/leon-engineering/deliveries/real-task.json"
    p.rename(p.with_suffix(".original"))
    p.symlink_to(p.with_suffix(".original"))
    with pytest.raises(d.TransferBlocked):
        d.preview(src, dst, "real-task", SHA)


def test_rollback_restores_absence_but_keeps_originals_and_journal(roots, tmp_path):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    d.apply(plan)
    d.apply(plan)
    home = tmp_path / "home"
    (home / "resident").mkdir(parents=True, mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"source_common": str(src / ".git")}))
    assert d.verify(plan)["status"] == "verified"
    assert d.rollback(plan, home)["status"] == "rolled_back"
    assert not (dst / ".git/leon-engineering/deliveries/real-task.json").exists()
    assert (src / ".git/leon-engineering/deliveries/real-task.json").exists()
    assert (dst / ".git/leon-engineering/evidence-imports/real-task.json").exists()


def test_rollback_never_overwrites_later_changes_or_active_source(roots, tmp_path):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    d.apply(plan)
    home = tmp_path / "home"
    (home / "resident").mkdir(parents=True, mode=0o700)
    config = home / "resident/config.json"
    config.write_text(json.dumps({"source_common": str(dst / ".git")}))
    with pytest.raises(d.TransferBlocked, match="target_in_use"):
        d.rollback(plan, home)
    config.write_text(json.dumps({"source_common": str(src / ".git")}))
    (dst / ".git/leon-engineering/deliveries/real-task.json").write_text("{}")
    with pytest.raises(d.TransferBlocked, match="rollback_changed"):
        d.rollback(plan, home)


def test_stale_staging_cannot_block_unique_atomic_writes(tmp_path):
    base = tmp_path / ".git"
    base.mkdir(mode=0o700)
    target = base / "journal.json"
    old = base / ".journal.json.transfer-staging"
    old.write_text("old incomplete write")
    d._atomic(target, b"{}")
    assert target.read_bytes() == b"{}"
    assert old.read_text() == "old incomplete write"


def test_no_overwrite_even_if_other_writer_creates_identical_bytes(roots, monkeypatch):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    link = d.os.link

    def racing_link(source, target, **kw):
        Path(target).write_bytes(Path(source).read_bytes())
        return link(source, target, **kw)

    monkeypatch.setattr(d.os, "link", racing_link)
    with pytest.raises(d.TransferBlocked, match="destination_conflict"):
        d.apply(plan)
    assert (dst / ".git/leon-engineering/git-safety/reviews/real-task.json").exists()


def test_rollback_uses_journal_when_source_no_longer_exists(roots, tmp_path):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    d.apply(plan)
    src.rename(src.with_name("source-retained-elsewhere"))
    loaded = d.load_plan(dst, "real-task")
    home = tmp_path / "home"
    (home / "resident").mkdir(parents=True, mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"source_common": str(src / ".git")}))
    assert d.rollback(loaded, home)["status"] == "rolled_back"


def test_interrupted_rollback_resumes_only_own_missing_entries(roots, tmp_path):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    d.apply(plan)
    journal = dst / ".git/leon-engineering/evidence-imports/real-task.json"
    state = json.loads(journal.read_text())
    state["state"] = "rolling_back"
    journal.write_text(json.dumps(state))
    (dst / ".git/leon-engineering/deliveries/real-task.json").unlink()
    home = tmp_path / "home"
    (home / "resident").mkdir(parents=True, mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"source_common": str(src / ".git")}))
    assert d.rollback(plan, home)["status"] == "rolled_back"
    assert d.rollback(plan, home)["status"] == "rolled_back"


def test_prepared_unpublished_apply_can_be_rolled_back(roots, tmp_path, monkeypatch):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    link = d.os.link
    monkeypatch.setattr(
        d.os,
        "link",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("synthetic interrupted publication")),
    )
    with pytest.raises(OSError):
        d.apply(plan)
    monkeypatch.setattr(d.os, "link", link)
    home = tmp_path / "home"
    (home / "resident").mkdir(parents=True, mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"source_common": str(src / ".git")}))
    assert d.rollback(plan, home)["status"] == "rolled_back"


def test_rollback_rechecks_after_durable_journal_and_keeps_later_writer(
    roots, tmp_path, monkeypatch
):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    d.apply(plan)
    home = tmp_path / "home"
    (home / "resident").mkdir(parents=True, mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"source_common": str(src / ".git")}))
    atomic = d._atomic
    target = dst / ".git/leon-engineering/deliveries/real-task.json"

    def replace_after_journal(path, raw):
        atomic(path, raw)
        if json.loads(raw).get("state") == "rolling_back":
            replacement = target.with_suffix(".new")
            replacement.write_text('{"later_change":true}')
            replacement.replace(target)

    monkeypatch.setattr(d, "_atomic", replace_after_journal)
    with pytest.raises(d.TransferBlocked, match="rollback_changed"):
        d.rollback(plan, home)
    assert json.loads(target.read_text()) == {"later_change": True}


def test_existing_managed_repository_lock_is_never_removed(roots):
    src, dst = roots
    plan = d.preview(src, dst, "real-task", SHA)
    lock = dst / ".git/leon-engineering/git-safety/repository.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text('{"pid":99,"nonce":"other"}')
    with pytest.raises(d.TransferBlocked, match="repository_busy"):
        d.apply(plan)
    assert lock.read_text() == '{"pid":99,"nonce":"other"}'


def test_selected_task_pr_must_match_qualified_remote_pr(roots):
    src, dst = roots
    path = src / ".git/leon-engineering/deliveries/real-task.json"
    record = json.loads(path.read_text())
    record["pullRequest"] = {"number": 999}
    path.write_text(json.dumps(record))
    with pytest.raises(d.TransferBlocked, match="remote_mismatch"):
        d.preview(src, dst, "real-task", SHA)


def test_cli_never_echoes_unknown_secret_shaped_arguments():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_workbench_entrypoint.resident.delivery_transfer",
            "preview",
            "--source",
            "/tmp/source",
            "--destination",
            "/tmp/dest",
            "--task",
            "task",
            "--target",
            SHA,
            "--api-key",
            "do-not-echo-this",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2
    assert "do-not-echo-this" not in result.stdout + result.stderr
    assert "maintenance_arguments_invalid" in result.stderr


def test_metadata_encoding_must_remain_readable_by_frozen_utf8_reader(roots):
    src, dst = roots
    path = src / ".git/leon-engineering/git-safety/reviews/real-task.json"
    path.write_bytes(json.dumps({"reviewedCommit": HEAD, "status": "PASS"}).encode("utf16"))
    with pytest.raises(d.TransferBlocked):
        d.preview(src, dst, "real-task", SHA)


def test_fifo_receipt_is_rejected_without_waiting_for_writer(tmp_path):
    import os
    import subprocess
    import sys

    fifo = tmp_path / "receipt.json"
    os.mkfifo(fifo)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import sys; "
                "from research_workbench_entrypoint.resident.delivery_transfer import _read; "
                "_read(Path(sys.argv[1]))"
            ),
            str(fifo),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=3,
    )
    assert result.returncode != 0
    assert "evidence_record_invalid" in result.stderr
