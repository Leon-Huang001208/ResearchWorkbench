"""Pinned DocReader overlay contracts without importing its heavy dependencies."""

import hashlib
import importlib.util
import socket
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

OVERLAY = Path(__file__).resolve().parents[2] / "deploy/weknora/docreader/plain_text_entrypoint.py"


def load_overlay(monkeypatch):
    def network_forbidden(*args, **kwargs):
        pytest.fail("plain-text decoding must not access the network or models")

    monkeypatch.setattr(socket.socket, "connect", network_forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", network_forbidden)

    class BaseParser:
        def __init__(self, file_name="", file_type=None, **kwargs):
            self.file_name = file_name
            self.file_type = file_type

        def parse(self, content):
            return self.parse_into_text(content)

    class Document:
        def __init__(self, *, content):
            self.content = content
            self.images = {}
            self.chunks = []
            self.source_blocks = []
            self.metadata = {}

    original = {"pdf": object(), "md": object(), "docx": object()}
    registry = SimpleNamespace(_engines={"builtin": dict(original), "other": {"txt": object()}})
    modules = {
        "docreader": ModuleType("docreader"),
        "docreader.models": ModuleType("docreader.models"),
        "docreader.models.document": ModuleType("docreader.models.document"),
        "docreader.parser": ModuleType("docreader.parser"),
        "docreader.parser.base_parser": ModuleType("docreader.parser.base_parser"),
        "docreader.parser.registry": ModuleType("docreader.parser.registry"),
    }
    modules["docreader.models.document"].Document = Document
    modules["docreader.parser.base_parser"].BaseParser = BaseParser
    modules["docreader.parser.registry"].registry = registry
    for name, value in modules.items():
        monkeypatch.setitem(sys.modules, name, value)
    spec = importlib.util.spec_from_file_location("rwb_plain_text_overlay", OVERLAY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, registry, original


@pytest.mark.parametrize("prefix", [b"", b"\xef\xbb\xbf"])
def test_txt_decodes_strict_utf8_preserves_text_and_original_file_bytes(
    monkeypatch, tmp_path, prefix
):
    module, registry, original = load_overlay(monkeypatch)
    raw = prefix + "标题\r\n  保留空格与链接 https://unvisited.invalid/a  \n".encode()
    path = tmp_path / "original.txt"
    path.write_bytes(raw)
    before = hashlib.sha256(raw).hexdigest()
    module.install_plain_text_parser()
    parser = registry._engines["builtin"]["txt"](file_name=str(path), file_type="txt")
    result = parser.parse(path.read_bytes())
    assert result.content == "标题\r\n  保留空格与链接 https://unvisited.invalid/a  \n"
    assert result.images == {}
    assert result.chunks == []
    assert result.source_blocks == []
    assert path.read_bytes() == raw
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert {key: registry._engines["builtin"][key] for key in original} == original


@pytest.mark.parametrize("raw", [b"", b" \r\n\t", b"\xef\xbb\xbf", b"\xffbad", b"\xe4\xb8"])
def test_txt_rejects_empty_or_invalid_utf8_without_fallback(monkeypatch, raw):
    module, registry, _ = load_overlay(monkeypatch)
    module.install_plain_text_parser()
    with pytest.raises(ValueError):
        registry._engines["builtin"]["txt"]().parse(raw)


def test_installation_preserves_existing_txt_and_other_engine_mappings(monkeypatch):
    module, registry, original = load_overlay(monkeypatch)
    existing = object()
    registry._engines["builtin"]["txt"] = existing
    other = dict(registry._engines["other"])
    module.install_plain_text_parser()
    module.install_plain_text_parser()
    assert registry._engines["builtin"] == {**original, "txt": existing}
    assert registry._engines["other"] == other


def test_entrypoint_installs_txt_then_runs_original_server_module(monkeypatch):
    module, registry, original = load_overlay(monkeypatch)
    calls = []

    def run_module(name, *, run_name):
        assert "txt" in registry._engines["builtin"]
        assert {key: registry._engines["builtin"][key] for key in original} == original
        calls.append((name, run_name))

    monkeypatch.setattr(module.runpy, "run_module", run_module)
    module.main()
    assert calls == [("docreader.main", "__main__")]


def test_registry_contract_drift_fails_before_server_starts(monkeypatch):
    module, registry, _ = load_overlay(monkeypatch)
    registry._engines = {"other": {}}
    monkeypatch.setattr(
        module.runpy, "run_module", lambda *args, **kwargs: pytest.fail("server must not start")
    )
    with pytest.raises(RuntimeError):
        module.main()
