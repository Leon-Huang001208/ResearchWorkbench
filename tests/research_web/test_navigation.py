"""Persistent navigation remains independent of research execution and mode."""

import copy
from types import SimpleNamespace

import pytest

from app.research_web.claw_projects import ClawProjects
from app.research_web.navigation import Navigation
from app.research_web.store import Store, StoreError


@pytest.fixture
def research(tmp_path):
    return SimpleNamespace(store=Store(tmp_path), datahub=SimpleNamespace(summaries=lambda _: []))


def test_independent_projects_membership_moves_and_legacy_key(research):
    claw, fingpt = ClawProjects(research), ClawProjects(research, "fingpt")
    first, second = claw.create("Claw"), fingpt.create("FinGPT")
    session = research.store.create("fingpt", "研究")
    fingpt.move(session["id"], second["id"])
    assert fingpt.detail(second["id"])["sessions"][0]["mode"] == "fingpt"
    assert not claw.members("default")
    assert research.store.data["claw_projects"][first["id"]] == first
    assert Store(research.store.root).data["fingpt_projects"][second["id"]] == second
    with pytest.raises(StoreError):
        fingpt.move(session["id"], first["id"])
    with pytest.raises(StoreError, match="相同"):
        claw.move(session["id"], first["id"])
    with pytest.raises(StoreError) as error:
        claw.reference(session["id"], session["id"], "a" * 24, "b" * 64)
    assert error.value.code == "reference_project_mismatch"


def test_navigation_persistence_mode_isolation_and_reorder(research):
    nav = Navigation(research, "fingpt")
    session = research.store.create("fingpt", "研究")
    project = ClawProjects(research, "fingpt").create("项目")
    pins = [{"kind": "session", "id": session["id"]}, {"kind": "project", "id": project["id"]}]
    assert nav.get() == {"mode": "fingpt", "revision": 0, "pinned": [], "project_order": []}
    first = nav.update(revision=0, pinned=pins, project_order=[project["id"], "default"])
    second = nav.update(revision=1, pinned=list(reversed(pins)), project_order=["default"])
    assert second["revision"] == 2
    assert second["pinned"] == list(reversed(pins))
    reopened = SimpleNamespace(store=Store(research.store.root))
    assert Navigation(reopened, "fingpt").get() == second
    assert Navigation(research, "claw").get()["revision"] == 0
    with pytest.raises(StoreError) as error:
        nav.update(revision=first["revision"], pinned=[], project_order=[])
    assert error.value.code == "navigation_changed"
    assert nav.get() == second


def test_retired_ids_filtered_without_get_writes_and_rejected_on_patch(research, monkeypatch):
    nav = Navigation(research, "claw")
    session = research.store.create("claw", "研究")
    project = ClawProjects(research).create("项目")
    nav.update(
        revision=0,
        pinned=[{"kind": "session", "id": session["id"]}, {"kind": "project", "id": project["id"]}],
        project_order=[project["id"]],
    )
    research.store.soft_delete(session["id"])
    ClawProjects(research).update(project["id"], archived=True)
    before = copy.deepcopy(research.store.data)
    disk = research.store.index.read_bytes()
    monkeypatch.setattr(research.store, "save", lambda: pytest.fail("GET must not save"))
    assert nav.get() == {"mode": "claw", "revision": 1, "pinned": [], "project_order": []}
    assert research.store.data == before
    assert research.store.index.read_bytes() == disk
    for pin in before["session_navigation"]["claw"]["pinned"]:
        with pytest.raises(StoreError) as error:
            nav.update(revision=1, pinned=[pin], project_order=[])
        assert error.value.code == "invalid_navigation"


@pytest.mark.parametrize(
    "pinned,order",
    [
        ([{"kind": "project", "id": "default"}] * 2, []),
        ([], ["default", "default"]),
        ([], ["missing"]),
        ([{"kind": "unknown", "id": "default"}], []),
        ([{"kind": "project", "id": "default", "extra": 1}], []),
        ([{"kind": "session", "id": []}], []),
    ],
)
def test_invalid_navigation_preserves_store(research, pinned, order):
    before = copy.deepcopy(research.store.data)
    with pytest.raises(StoreError):
        Navigation(research, "claw").update(revision=0, pinned=pinned, project_order=order)
    assert research.store.data == before


@pytest.mark.parametrize("failure", [StoreError, OSError])
def test_navigation_cross_mode_and_failed_save_rollback(research, monkeypatch, failure):
    nav = Navigation(research, "claw")
    foreign = research.store.create("fingpt", "另一模式")
    with pytest.raises(StoreError):
        nav.update(revision=0, pinned=[{"kind": "session", "id": foreign["id"]}], project_order=[])
    before = copy.deepcopy(research.store.data)

    def fail():
        raise failure("无法保存")

    monkeypatch.setattr(research.store, "save", fail)
    with pytest.raises(StoreError):
        nav.update(revision=0, pinned=[], project_order=["default"])
    assert research.store.data == before
    research.store.data["session_navigation"] = {
        "claw": {"revision": 3, "pinned": [], "project_order": []},
        "fingpt": {"revision": 1, "pinned": [], "project_order": ["default"]},
    }
    before = copy.deepcopy(research.store.data)
    with pytest.raises(StoreError):
        nav.update(revision=3, pinned=[], project_order=["default"])
    assert research.store.data == before


def test_fingpt_reference_keeps_hash_and_move_failure_restores_membership(research, monkeypatch):
    projects = ClawProjects(research, "fingpt")
    source = research.store.create("fingpt", "来源")
    target = research.store.create("fingpt", "目标")
    path = research.store.directory(source["id"]) / "outputs" / "evidence.md"
    path.write_text("固定来源", encoding="utf-8")
    file = projects.detail("default")["files"][0]
    result = projects.reference(target["id"], source["id"], file["id"], file["sha256"])
    assert result["source_session_id"] == source["id"]
    assert result["sha256"] == file["sha256"]
    assert research.store.file_path(target["id"], result["id"]).read_text() == "固定来源"
    project = projects.create("移动目标")
    before = copy.deepcopy(research.store.data)

    def fail():
        raise StoreError("无法保存")

    monkeypatch.setattr(research.store, "save", fail)
    with pytest.raises(StoreError):
        projects.move(source["id"], project["id"])
    assert research.store.data == before


@pytest.mark.parametrize("mode", ["claw", "fingpt"])
@pytest.mark.parametrize("operation", ["create", "move", "reference"])
@pytest.mark.parametrize("existing_reference", [False, True])
def test_project_raw_tempfile_failure_restores_memory_disk_and_files(
    research, monkeypatch, mode, operation, existing_reference
):
    import tempfile

    projects = ClawProjects(research, mode)
    project = projects.create("目标项目") if operation != "create" else None
    source = research.store.create(mode, "来源")
    target = research.store.create(mode, "目标")
    source_path = research.store.directory(source["id"]) / "outputs" / "source.md"
    source_path.write_text("保留原文件", encoding="utf-8")
    file = projects.detail("default")["files"][0]
    # Also prove an existing reference survives a failed subsequent copy.
    if operation == "reference" and existing_reference:
        projects.reference(target["id"], source["id"], file["id"], file["sha256"])
    before = copy.deepcopy(research.store.data)
    disk_before = research.store.index.read_bytes()
    input_root = research.store.directory(target["id"]) / "inputs"
    files_before = {path.name: path.read_bytes() for path in input_root.iterdir()}

    def fail(*args, **kwargs):
        raise OSError("temporary index unavailable")

    monkeypatch.setattr(tempfile, "mkstemp", fail)
    with pytest.raises(StoreError) as error:
        if operation == "create":
            projects.create("不会留下")
        elif operation == "move":
            projects.move(source["id"], project["id"])
        else:
            projects.reference(target["id"], source["id"], file["id"], file["sha256"])
    assert isinstance(error.value.__cause__, OSError)
    assert research.store.data == before
    assert research.store.index.read_bytes() == disk_before
    assert {path.name: path.read_bytes() for path in input_root.iterdir()} == files_before
    assert source_path.read_text(encoding="utf-8") == "保留原文件"


@pytest.mark.parametrize("mode", ["claw", "fingpt"])
def test_reference_name_collision_preserves_existing_attachment(research, monkeypatch, mode):
    from app.research_web import claw_projects

    projects = ClawProjects(research, mode)
    source = research.store.create(mode, "来源")
    target = research.store.create(mode, "目标")
    source_path = research.store.directory(source["id"]) / "outputs" / "source.md"
    source_path.write_text("来源", encoding="utf-8")
    destination = research.store.directory(target["id"]) / "inputs" / "reference-fixed.md"
    destination.write_text("既有附件", encoding="utf-8")
    file = next(
        item for item in projects.detail("default")["files"] if item["session_id"] == source["id"]
    )
    before = copy.deepcopy(research.store.data)
    disk_before = research.store.index.read_bytes()
    monkeypatch.setattr(claw_projects, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    with pytest.raises(StoreError):
        projects.reference(target["id"], source["id"], file["id"], file["sha256"])
    assert destination.read_text(encoding="utf-8") == "既有附件"
    assert research.store.data == before
    assert research.store.index.read_bytes() == disk_before
