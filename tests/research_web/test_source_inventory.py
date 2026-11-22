"""Migration previews retain unreadable and dirty worktrees as protected objects."""

from research_workbench_entrypoint.resident import source_inventory as s


def test_metadata_does_not_follow_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("private")
    link = tmp_path / "link"
    link.symlink_to(outside)
    assert s.read_metadata(link)["status"] == "unsafe"
    assert s.read_metadata(tmp_path / "missing")["status"] == "missing"


def test_worktree_timeout_is_not_corruption_or_cleanup_authority(tmp_path, monkeypatch):
    reg = tmp_path / "registration"
    reg.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    (reg / "gitdir").write_text(str(work / ".git"))
    (reg / "HEAD").write_text("a" * 40)
    monkeypatch.setattr(s, "git_observation", lambda *a, **k: {"status": "READ_TIMEOUT"})
    row = s.worktree_row(reg)
    assert row["working_state"]["status"] == "READ_TIMEOUT"
    assert row["disposition"] == "protected" and row["occupancy"] == "not_certified"


def test_missing_registry_entry_remains_in_inventory(tmp_path, monkeypatch):
    project = tmp_path / "source"
    destination = tmp_path / "new"
    common = project / ".git"
    (common / "worktrees/missing-registration").mkdir(parents=True)

    def git(p, args, **kw):
        if args[0] == "rev-parse":
            return {"status": "observed", "stdout": str(common)}
        return {"status": "observed", "stdout": ""}

    monkeypatch.setattr(s, "git_observation", git)
    result = s.inventory(project, destination)
    assert result["worktree_count"] == 1
    assert result["worktrees"][0]["gitdir"]["status"] == "missing"
    assert result["apply_authorized"] is False


def test_dirty_and_untracked_state_is_retained(tmp_path, monkeypatch):
    reg = tmp_path / "registration"
    reg.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    (reg / "gitdir").write_text(str(work / ".git"))
    (reg / "HEAD").write_text("ref: refs/heads/task")
    monkeypatch.setattr(
        s,
        "git_observation",
        lambda *a, **k: {"status": "observed", "stdout": " M changed.py\0?? new.txt\0"},
    )
    row = s.worktree_row(reg)
    assert row["working_state"]["entries"] == [" M changed.py", "?? new.txt"]
    assert row["working_state"]["clean"] is False
    assert row["disposition"] == "protected"


def test_primary_checkout_without_linked_worktrees_is_valid(tmp_path, monkeypatch):
    project = tmp_path / "source"
    common = project / ".git"
    common.mkdir(parents=True)

    def git(p, args, **kw):
        return {"status": "observed", "stdout": str(common) if args[0] == "rev-parse" else ""}

    monkeypatch.setattr(s, "git_observation", git)
    result = s.inventory(project, tmp_path / "new")
    assert result["worktree_count"] == 0 and result["registry_stable"] is True
    assert result["apply_authorized"] is False
