from pathlib import Path

from scripts import generate_py_file_index


def test_build_index_is_deterministic_and_tracks_public_structure(tmp_path: Path):
    package = tmp_path / "app"
    package.mkdir()
    (package / "sample.py").write_text(
        '"""Sample module."""\nimport json\n\nclass Demo:\n    def run(self):\n        return json.dumps({})\n\ndef helper():\n    return 1\n',
        encoding="utf-8",
    )

    first = generate_py_file_index.build_index(tmp_path, ["app"])
    second = generate_py_file_index.build_index(tmp_path, ["app"])

    assert first == second
    assert "## `app/sample.py`" in first
    assert "- `Demo`" in first
    assert "- methods: run" in first
    assert "- `helper`" in first


def test_build_index_changes_when_public_structure_changes(tmp_path: Path):
    package = tmp_path / "app"
    package.mkdir()
    source = package / "sample.py"
    source.write_text("def first():\n    return 1\n", encoding="utf-8")
    before = generate_py_file_index.build_index(tmp_path, ["app"])

    source.write_text(
        "def first():\n    return 1\n\ndef second():\n    return 2\n", encoding="utf-8"
    )
    after = generate_py_file_index.build_index(tmp_path, ["app"])

    assert before != after
    assert "- `second`" in after


def test_check_mode_fails_when_committed_index_is_stale(tmp_path: Path, monkeypatch):
    output = tmp_path / "py_file_index.md"
    output.write_text("stale", encoding="utf-8")
    monkeypatch.setattr(generate_py_file_index, "OUTPUT", output)
    monkeypatch.setattr(generate_py_file_index, "build_index", lambda: "expected")

    assert generate_py_file_index.main(["--check"]) == 1


def test_check_mode_accepts_current_index(tmp_path: Path, monkeypatch):
    output = tmp_path / "py_file_index.md"
    output.write_text("expected", encoding="utf-8")
    monkeypatch.setattr(generate_py_file_index, "OUTPUT", output)
    monkeypatch.setattr(generate_py_file_index, "build_index", lambda: "expected")

    assert generate_py_file_index.main(["--check"]) == 0
