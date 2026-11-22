"""Reuse only pure source facts while every runtime check observes current state."""

import ast
import importlib
import os
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_api import isolated_keyring  # noqa: F401

from app.research_web.capabilities import pack_dependencies as binding
from app.research_web.capabilities import pack_import_policy as policy
from app.research_web.capabilities.models import CapabilityError


def fixture_package(tmp_path, monkeypatch, source="import json\n"):
    root = tmp_path / "facts_fixture"
    root.mkdir()
    entry = root / "__init__.py"
    entry.write_text(source)
    monkeypatch.syspath_prepend(str(tmp_path))
    return entry, [{"origin": str(tmp_path), "roots": ["facts_fixture"]}]


def test_runtime_checks_stay_fresh_while_reusing_bounded_syntax_facts(monkeypatch):
    import idna

    entry_path = Path(idna.__file__)
    entry = str(entry_path)
    calls = Counter()
    reads, scans = [], []
    parse = ast.parse
    maps = []
    build = binding.build_policy
    read = Path.read_bytes
    modules = policy.module_files

    def observed_parse(source, filename="<unknown>", *args, **kwargs):
        if filename == entry:
            calls[filename] += 1
        return parse(source, filename, *args, **kwargs)

    def observed_read(path):
        if path == entry_path:
            reads.append(path)
        return read(path)

    def observed_modules(value):
        scans.append(1)
        return modules(value)

    def observed_build(dependencies, **kwargs):
        maps.append(kwargs.get("_source_facts"))
        return build(dependencies, **kwargs)

    monkeypatch.setattr(ast, "parse", observed_parse)
    monkeypatch.setattr(Path, "read_bytes", observed_read)
    monkeypatch.setattr(policy, "module_files", observed_modules)
    monkeypatch.setattr(binding, "build_policy", observed_build)
    first = binding.runtime_identity()
    second = binding.runtime_identity()
    assert calls[entry] == 1
    assert len(reads) == 4 and len(scans) == 6
    assert first == second
    assert maps[0] is not maps[1]
    assert maps == [{}, {}]  # finally releases every retained source byte.


def test_same_bytes_reuse_facts_but_reread_and_enumerate(tmp_path, monkeypatch):
    entry, dependencies = fixture_package(tmp_path, monkeypatch)
    reads, scans, parses = [], [], []
    read, modules, parse = Path.read_bytes, policy.module_files, ast.parse

    def observed_read(path):
        if path == entry:
            reads.append(path)
        return read(path)

    def observed_modules(value):
        scans.append(1)
        return modules(value)

    def observed_parse(source, *args, **kwargs):
        parses.append(1)
        return parse(source, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", observed_read)
    monkeypatch.setattr(policy, "module_files", observed_modules)
    monkeypatch.setattr(ast, "parse", observed_parse)
    facts = {}
    initial = policy.build_policy(dependencies, _source_facts=facts)
    policy.verify_policy(initial, dependencies, _source_facts=facts)
    assert len(reads) == 2 and len(scans) == 3 and len(parses) == 1
    assert all(isinstance(value, tuple) for value in facts.values())
    initial["stdlib_roots"].clear()
    assert policy.build_policy(dependencies, _source_facts=facts)["stdlib_roots"] == ["json"]


def test_fresh_runtime_maps_reuse_only_same_root_syntax_facts(tmp_path, monkeypatch):
    entry, dependencies = fixture_package(tmp_path, monkeypatch)
    reads, scans, parses = [], [], []
    read, modules, parse = Path.read_bytes, policy.module_files, ast.parse

    def observed_read(path):
        if path == entry:
            reads.append(path)
        return read(path)

    def observed_modules(value):
        scans.append(1)
        return modules(value)

    def observed_parse(source, *args, **kwargs):
        parses.append(1)
        return parse(source, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", observed_read)
    monkeypatch.setattr(policy, "module_files", observed_modules)
    monkeypatch.setattr(ast, "parse", observed_parse)
    first_facts, second_facts = {}, {}
    first = policy.build_policy(dependencies, _source_facts=first_facts)
    second = policy.build_policy(dependencies, _source_facts=second_facts)
    assert first == second
    assert first_facts is not second_facts
    assert len(reads) == 2 and len(scans) == 2
    assert len(parses) == 1


def test_syntax_fact_cache_invalidates_bytes_root_and_parser(tmp_path, monkeypatch):
    entry, dependencies = fixture_package(tmp_path, monkeypatch)
    parse = ast.parse
    parses = []

    def first_parser(source, *args, **kwargs):
        parses.append("first")
        return parse(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse", first_parser)
    initial = policy.build_policy(dependencies, _source_facts={})
    assert policy.build_policy(dependencies, _source_facts={}) == initial
    assert parses == ["first"]

    before = entry.stat()
    entry.write_text("import math\n")
    os.utime(entry, ns=(before.st_atime_ns, before.st_mtime_ns))
    changed = policy.build_policy(dependencies, _source_facts={})
    assert changed["stdlib_roots"] == ["math"]
    assert parses == ["first", "first"]

    alternate = tmp_path / "alternate"
    alternate_entry = alternate / "facts_fixture" / "__init__.py"
    alternate_entry.parent.mkdir(parents=True)
    alternate_entry.write_text("import json\n")
    alternate_dependencies = [{"origin": str(alternate), "roots": ["facts_fixture"]}]
    assert policy.build_policy(alternate_dependencies, _source_facts={}) == initial
    assert parses == ["first", "first", "first"]

    other_parses = []

    def second_parser(source, *args, **kwargs):
        other_parses.append(1)
        return parse(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse", second_parser)
    assert policy.build_policy(alternate_dependencies, _source_facts={}) == initial
    assert other_parses == [1]


def test_same_size_restored_mtime_change_is_not_reused(tmp_path, monkeypatch):
    entry, dependencies = fixture_package(tmp_path, monkeypatch, "import json\n")
    facts = {}
    initial = policy.build_policy(dependencies, _source_facts=facts)
    before = entry.stat()
    entry.write_text("import math\n")
    os.utime(entry, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert entry.stat().st_size == before.st_size
    with pytest.raises(ValueError, match="pack_import_policy_unverified"):
        policy.verify_policy(initial, dependencies, _source_facts=facts)


@pytest.mark.parametrize("source", ["def broken(:\n", "__import__('outside')\n"])
def test_changed_invalid_source_is_not_hidden(tmp_path, monkeypatch, source):
    entry, dependencies = fixture_package(tmp_path, monkeypatch)
    facts = {}
    initial = policy.build_policy(dependencies, _source_facts=facts)
    entry.write_text(source)
    with pytest.raises(ValueError, match="pack_import_policy_unverified"):
        policy.verify_policy(initial, dependencies, _source_facts=facts)


@pytest.mark.parametrize("change", ["added", "removed"])
def test_current_module_inventory_is_not_cached(tmp_path, monkeypatch, change):
    entry, dependencies = fixture_package(tmp_path, monkeypatch)
    facts = {}
    initial = policy.build_policy(dependencies, _source_facts=facts)
    if change == "added":
        (entry.parent / "child.py").write_text("import math\n")
        entry.write_text("from . import child\n")
    else:
        entry.unlink()
    with pytest.raises(ValueError, match="pack_import_policy_unverified"):
        policy.verify_policy(initial, dependencies, _source_facts=facts)


def test_relative_source_facts_include_module_context(tmp_path, monkeypatch):
    entry, dependencies = fixture_package(tmp_path, monkeypatch, "from . import child\n")
    child = (
        "import importlib\ndef lazy():\n"
        " import optional_extra\n return importlib.import_module('outside')\n"
    )
    (entry.parent / "child.py").write_text(child)
    other = tmp_path / "other_fixture"
    other.mkdir()
    (other / "__init__.py").write_bytes(entry.read_bytes())
    (other / "child.py").write_text(child)
    parsed = []
    extract = policy._import_facts

    def observed_extract(*args):
        parsed.append(1)
        return extract(*args)

    monkeypatch.setattr(policy, "_import_facts", observed_extract)
    facts = {}
    first = policy.build_policy(dependencies, _source_facts=facts)
    assert len(parsed) == 2
    assert policy.build_policy(dependencies, _source_facts=facts) == first
    assert len(parsed) == 2  # relative/lazy/dynamic facts all hit on the second pass.
    other_dependencies = [{"origin": str(tmp_path), "roots": ["other_fixture"]}]
    second = policy.build_policy(other_dependencies, _source_facts=facts)
    assert len(parsed) == 4
    assert policy.build_policy(other_dependencies, _source_facts=facts) == second
    assert len(parsed) == 4
    assert first["reachable_modules"] == ["facts_fixture", "facts_fixture.child"]
    assert second["reachable_modules"] == ["other_fixture", "other_fixture.child"]
    assert first["blocked_lazy"] == second["blocked_lazy"] == ["optional_extra"]
    assert first["dynamic_modules_guarded"] == ["facts_fixture.child"]
    assert second["dynamic_modules_guarded"] == ["other_fixture.child"]


@pytest.mark.parametrize("shadow", ["search", "loaded-absent", "loaded-existing"])
@pytest.mark.parametrize("repeat", range(2))
def test_source_reuse_keeps_current_search_and_loaded_checks(tmp_path, monkeypatch, shadow, repeat):
    entry, dependencies = fixture_package(tmp_path, monkeypatch)
    facts = {}
    initial = policy.build_policy(dependencies, _source_facts=facts)
    if shadow == "loaded-existing":
        monkeypatch.setitem(sys.modules, "facts_fixture", ModuleType("facts_fixture"))
    missing = object()
    previous = sys.modules.get("facts_fixture", missing)
    with monkeypatch.context() as scope:
        # Register the original absent/object state before a real import mutates it.
        scope.setitem(sys.modules, "facts_fixture", None)
        scope.delitem(sys.modules, "facts_fixture")
        if shadow == "search":
            alternate = tmp_path / "alternate"
            alternate.mkdir()
            (alternate / "facts_fixture.py").write_text("")
            scope.syspath_prepend(str(alternate))
        else:
            module = importlib.import_module("facts_fixture")
            scope.setattr(module, "__file__", str(entry) + ".shadow")
        with pytest.raises(ValueError, match="pack_import_policy_unverified"):
            policy.verify_policy(initial, dependencies, _source_facts=facts)
    assert sys.modules.get("facts_fixture", missing) is previous


def test_runtime_failure_releases_only_its_local_facts(monkeypatch):
    maps = []
    build = binding.build_policy

    def observed_build(dependencies, **kwargs):
        maps.append(kwargs["_source_facts"])
        return build(dependencies, **kwargs)

    def rejected(*args, **kwargs):
        raise ValueError("synthetic verification failure")

    monkeypatch.setattr(binding, "build_policy", observed_build)
    monkeypatch.setattr(binding, "verify_policy", rejected)
    with pytest.raises(CapabilityError) as error:
        binding.runtime_identity()
    assert error.value.code == "pack_runtime_unverified"
    assert maps == [{}]
