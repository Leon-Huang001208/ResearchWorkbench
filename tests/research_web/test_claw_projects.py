"""Project isolation and explicit file references without a second research engine."""

from types import SimpleNamespace

import pytest

from app.research_web.claw_projects import ClawProjects
from app.research_web.store import Store, StoreError


@pytest.fixture
def projects(tmp_path):
    store = Store(tmp_path)
    return ClawProjects(
        SimpleNamespace(store=store, datahub=SimpleNamespace(summaries=lambda sid: []))
    )


def test_legacy_sessions_default_and_archiving_preserves_members(projects):
    store = projects.store
    old = store.create("claw", "旧研究")
    assert projects.detail("default")["sessions"][0]["id"] == old["id"]
    project = projects.create("产业链")
    projects.move(old["id"], project["id"])
    assert store.session(old["id"])["workspace_id"] == "research"
    projects.update(project["id"], name="产业链研究", archived=True)
    assert projects.detail(project["id"])["sessions"][0]["id"] == old["id"]
    with pytest.raises(StoreError, match="归档"):
        projects.move(store.create("claw", "新研究")["id"], project["id"])
    assert Store(store.root).session(old["id"])["project_id"] == project["id"]


def test_explicit_reference_binds_hash_and_rejects_cross_project(projects):
    store = projects.store
    source = store.create("claw", "来源")
    target = store.create("claw", "当前研究")
    path = store.directory(source["id"]) / "outputs" / "report.md"
    path.write_text("研究证据", encoding="utf-8")
    file = store.files(source["id"])[0]
    aggregate = projects.detail("default")
    assert aggregate["files"][0]["session_id"] == source["id"]
    ref = projects.reference(
        target["id"], source["id"], file["id"], aggregate["files"][0]["sha256"]
    )
    assert ref["source_session_id"] == source["id"]
    assert store.file_path(target["id"], ref["id"]).read_text() == "研究证据"
    path.write_text("新内容", encoding="utf-8")
    with pytest.raises(StoreError, match="变化"):
        projects.reference(target["id"], source["id"], file["id"], aggregate["files"][0]["sha256"])
    projects.move(source["id"], projects.create("另一项目")["id"])
    with pytest.raises(StoreError, match="项目"):
        projects.reference(target["id"], source["id"], file["id"], aggregate["files"][0]["sha256"])


def test_deleted_and_fingpt_sessions_are_not_project_members(projects):
    deleted = projects.store.create("claw", "删除")
    projects.store.soft_delete(deleted["id"])
    projects.store.create("fingpt", "即时研究")
    assert projects.detail("default")["sessions"] == []


def test_reference_rejects_symlink_and_failed_save_rolls_back(projects, monkeypatch, tmp_path):
    store = projects.store
    source = store.create("claw", "来源")
    target = store.create("claw", "目标")
    path = store.directory(source["id"]) / "outputs" / "report.md"
    path.write_text("safe")
    file = projects.detail("default")["files"][0]
    path.unlink()
    path.symlink_to(tmp_path / "index.json")
    with pytest.raises(StoreError):
        projects.reference(target["id"], source["id"], file["id"], file["sha256"])
    before = projects.list()
    monkeypatch.setattr(store, "save", lambda: (_ for _ in ()).throw(StoreError("无法保存")))
    with pytest.raises(StoreError):
        projects.create("不会留下")
    assert projects.list() == before


def test_reference_root_open_failure_closes_source_and_returns_domain_error(projects, monkeypatch):
    import io
    import os

    source = projects.store.create("claw", "来源")
    target = projects.store.create("claw", "目标")
    stream = io.BytesIO(b"safe")
    monkeypatch.setattr(projects.store, "open_file", lambda *args: (stream, "report.md"))
    monkeypatch.setattr(
        os, "open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("root unavailable"))
    )
    with pytest.raises(StoreError):
        projects.reference(target["id"], source["id"], "a" * 24, "b" * 64)
    assert stream.closed
