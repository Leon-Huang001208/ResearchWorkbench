"""Offline capability lifecycle and hostile-package regression tests."""

import hashlib
import io
import json
import stat
import zipfile
from copy import deepcopy

import pytest
import yaml
from fastapi.testclient import TestClient
from test_api import NativeFixture

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.models import CapabilityError
from app.research_web.capabilities.seeds import seed_packages
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


def isolate_keyring(monkeypatch):
    """Give shared API fixtures synthetic credentials without consulting the host."""
    import keyring

    values = {}
    monkeypatch.setattr(
        keyring, "get_password", lambda service, account: values.get((service, account))
    )
    monkeypatch.setattr(
        keyring,
        "set_password",
        lambda service, account, value: values.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        keyring, "delete_password", lambda service, account: values.pop((service, account), None)
    )


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"中文": '行情\n引号"与反斜线\\及😀', "values": [None, True, False, 3.25]},
        {"nested": {"items": [{"key": "value"}] * 120}, "large": 10**30},
    ],
)
def test_catalog_save_uses_one_write_with_identical_json(tmp_path, monkeypatch, data):
    import os

    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog.root = tmp_path
    catalog.index = tmp_path / "catalog.json"
    catalog.data = data
    expected = io.StringIO()
    json.dump(data, expected, ensure_ascii=False)
    writes = []
    fdopen = os.fdopen

    class ObservedStream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def write(self, value):
            writes.append(value)
            return self.stream.write(value)

        def flush(self):
            return self.stream.flush()

        def fileno(self):
            return self.stream.fileno()

    monkeypatch.setattr(os, "fdopen", lambda *a, **k: ObservedStream(fdopen(*a, **k)))
    catalog.save()
    assert catalog.index.read_bytes() == expected.getvalue().encode("utf-8")
    assert writes == [expected.getvalue()]
    assert not list(tmp_path.glob("catalog-*"))


@pytest.mark.parametrize("stage", ["fsync", "replace", "serialization"])
def test_catalog_save_failure_preserves_previous_index(tmp_path, monkeypatch, stage):
    import os

    from app.research_web.capabilities.models import CapabilityError

    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog.root = tmp_path
    catalog.index = tmp_path / "catalog.json"
    previous = b'{"previous": true}'
    catalog.index.write_bytes(previous)
    catalog.data = {"next": object() if stage == "serialization" else True}

    def fail(*args):
        raise OSError("synthetic persistence failure")

    if stage != "serialization":
        monkeypatch.setattr(os, stage, fail)
    with pytest.raises(TypeError if stage == "serialization" else CapabilityError) as error:
        catalog.save()
    if stage != "serialization":
        assert error.value.code == "catalog_write_failed"
    assert catalog.index.read_bytes() == previous
    assert not list(tmp_path.glob("catalog-*"))


@pytest.fixture
def api(tmp_path, monkeypatch):
    isolate_keyring(monkeypatch)
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, native, service


def candidate(name="我的研究", slug="my-research"):
    return {
        "metadata": {
            "name": name,
            "slug": slug,
            "description": "基于上传资料开展有来源的研究",
            "category": "资料研究",
            "inputs": [
                {
                    "name": "question",
                    "label": "研究问题",
                    "type": "text",
                    "required": True,
                }
            ],
            "scenarios": ["解读研究资料"],
            "default_formats": ["md"],
            "required_tools": ["research_run_script"],
            "dependencies": [],
        },
        "instructions": f"---\nname: {slug}\ndescription: 有来源的研究\n---\n# 研究\n只读取本会话资料，不编造来源。",
        "files": [{"path": "templates/report.md", "content": "# 研究报告"}],
    }


def create(client, value=None):
    response = client.post("/api/research/capabilities", json=value or candidate())
    assert response.status_code == 201, response.text
    return response.json()


def test_builtin_dependency_inventory_is_scoped_to_initialization(tmp_path, monkeypatch):
    import importlib.metadata

    isolate_keyring(monkeypatch)
    installed = importlib.metadata.packages_distributions()
    scans = []
    present = True

    def inventory():
        scans.append(True)
        return {**installed, **({"task_only_module": ["task-only-dist"]} if present else {})}

    monkeypatch.setattr(importlib.metadata, "packages_distributions", inventory)
    catalog = CapabilityCatalog(tmp_path / "first")
    assert len(scans) == 1
    value = candidate()
    value["files"] = [{"path": "scripts/check.py", "content": "import task_only_module\n"}]
    draft = catalog._draft(value)
    draft["reviewed_scripts"] = [draft["files"][0]["sha256"]]
    assert catalog.validate("skill", draft)["valid"]
    present = False
    result = catalog.validate("skill", draft)
    assert any(issue["code"] == "dependency_missing" for issue in result["issues"])
    assert len(scans) == 3
    CapabilityCatalog(tmp_path / "second")
    assert len(scans) == 4
    assert catalog._initial_module_distributions is None

    def fail_inventory():
        raise ValueError("synthetic inventory failure")

    from app.research_web.capabilities.models import CapabilityError

    monkeypatch.setattr(importlib.metadata, "packages_distributions", fail_inventory)
    interrupted = CapabilityCatalog.__new__(CapabilityCatalog)
    with pytest.raises(CapabilityError):
        interrupted.__init__(tmp_path / "interrupted")
    assert not interrupted._initializing
    assert interrupted._initial_module_distributions is None


def test_external_module_inventory_projects_only_requested_fresh_metadata(tmp_path, monkeypatch):
    import importlib.metadata

    class Distribution:
        def __init__(self, name, *, declared=None, record=None, existing=()):
            self.name = name
            self.declared = declared
            self.record = record
            self.existing = set(existing)
            self.located = []

        @property
        def metadata(self):
            return {"Name": self.name}

        def read_text(self, filename):
            if filename == "top_level.txt":
                return self.declared
            if filename == "RECORD":
                return self.record
            return None

        def locate_file(self, filename):
            value = str(filename)
            self.located.append(value)
            return tmp_path / ("present" if value in self.existing else "missing")

        def _read_files_distinfo(self):
            return self.record and self.record.splitlines()

        def _read_files_egginfo_installed(self):
            return None

        def _read_files_egginfo_sources(self):
            return None

    (tmp_path / "present").write_text("present", encoding="utf-8")
    declared = Distribution("declared-dist", declared="shared\nexplicit\n")
    first_namespace = Distribution(
        "namespace-one",
        record="shared/one.py,,\nunrelated/large.py,,\n",
        existing={"shared/one.py", "unrelated/large.py"},
    )
    second_namespace = Distribution(
        "namespace-two", record="shared/two.py,,\n", existing={"shared/two.py"}
    )
    missing = Distribution("missing-dist", record="gone.py,,\n")
    current = [declared, first_namespace, second_namespace, missing]
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: iter(current))

    inventory = CapabilityCatalog._project_installed_module_distributions({"shared", "gone"})

    assert inventory == {"shared": ["declared-dist", "namespace-one", "namespace-two"]}
    assert first_namespace.located == ["shared/one.py"]
    assert second_namespace.located == ["shared/two.py"]
    assert missing.located == ["gone.py"]

    first_namespace.record = "replacement.py,,\n"
    second_namespace.record = "shared/two.py,,\n"
    second_namespace.existing.clear()
    assert CapabilityCatalog._project_installed_module_distributions({"shared"}) == {
        "shared": ["declared-dist"]
    }


def test_external_module_inventory_preserves_monkeypatched_api_semantics(monkeypatch):
    import importlib.metadata

    calls = []

    def inventory():
        calls.append(True)
        return {"custom_finder_module": ["custom-finder-dist"], "other": ["ignored"]}

    monkeypatch.setattr(importlib.metadata, "packages_distributions", inventory)
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"custom_finder_module"}) == {
        "custom_finder_module": ["custom-finder-dist"]
    }
    assert calls == [True]


def test_external_module_inventory_matches_real_api_and_propagates_scan_failure(monkeypatch):
    import importlib.metadata

    requested = {"jsonschema", "yaml", "requests", "module_that_is_not_installed"}
    expected = importlib.metadata.packages_distributions()
    assert CapabilityCatalog._project_installed_module_distributions(requested) == {
        module: expected[module] for module in requested if module in expected
    }

    def fail_scan():
        raise OSError("synthetic metadata scan failure")

    monkeypatch.setattr(importlib.metadata, "distributions", fail_scan)
    with pytest.raises(OSError, match="synthetic metadata scan failure"):
        CapabilityCatalog._project_installed_module_distributions({"jsonschema"})


@pytest.mark.parametrize(
    "malformed_row",
    [
        "unrelated.py,,not-an-integer",
        "unrelated.py,,,unexpected-column",
    ],
    ids=["invalid-size", "extra-column"],
)
def test_external_module_inventory_preserves_real_record_errors(
    tmp_path, monkeypatch, malformed_row
):
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    package = site / "requested_pkg"
    metadata = site / "fixture_dist-1.0.dist-info"
    package.mkdir(parents=True)
    metadata.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (site / "unrelated.py").write_text("", encoding="utf-8")
    (metadata / "METADATA").write_text("Name: fixture-dist\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text(
        f"{malformed_row}\nrequested_pkg/__init__.py,,0\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "path", [str(site)])

    with pytest.raises((TypeError, ValueError)):
        importlib.metadata.packages_distributions()
    with pytest.raises((TypeError, ValueError)):
        CapabilityCatalog._project_installed_module_distributions({"requested_pkg"})


def test_external_module_inventory_tracks_real_dist_info_record_changes(tmp_path, monkeypatch):
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    shared = site / "shared"
    shared.mkdir(parents=True)
    (shared / "__init__.py").write_text("", encoding="utf-8")
    declared = site / "declared_dist-1.0.dist-info"
    inferred = site / "inferred_dist-1.0.dist-info"
    declared.mkdir()
    inferred.mkdir()
    (declared / "METADATA").write_text("Name: declared-dist\nVersion: 1.0\n", encoding="utf-8")
    (declared / "top_level.txt").write_text("shared\n", encoding="utf-8")
    (declared / "RECORD").write_text("declared_dist-1.0.dist-info/METADATA,,\n")
    (inferred / "METADATA").write_text("Name: inferred-dist\nVersion: 1.0\n", encoding="utf-8")
    record = inferred / "RECORD"
    record.write_text("shared/__init__.py,,0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(site)])

    requested = {"shared"}
    assert CapabilityCatalog._project_installed_module_distributions(requested) == {
        "shared": ["declared-dist", "inferred-dist"]
    }
    assert CapabilityCatalog._project_installed_module_distributions(requested) == {
        module: values
        for module, values in importlib.metadata.packages_distributions().items()
        if module in requested
    }

    record.write_text("replacement/__init__.py,,0\n", encoding="utf-8")
    assert CapabilityCatalog._project_installed_module_distributions(requested) == {
        "shared": ["declared-dist"]
    }


def test_external_module_inventory_falls_back_before_real_custom_finder_is_consumed(
    tmp_path, monkeypatch
):
    import importlib.metadata
    import sys

    package = tmp_path / "custom_finder_module"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    calls = []

    class CustomDistribution(importlib.metadata.Distribution):
        @property
        def metadata(self):
            return {"Name": "custom-finder-dist"}

        def read_text(self, filename):
            return None

        def locate_file(self, path):
            return tmp_path / str(path)

        @property
        def files(self):
            path = importlib.metadata.PackagePath("custom_finder_module/__init__.py")
            path.dist = self
            return [path]

    class CustomFinder:
        def find_distributions(self, context=None):
            calls.append(context)
            return iter([CustomDistribution()])

    monkeypatch.setattr(sys, "meta_path", [CustomFinder(), *sys.meta_path])
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"custom_finder_module"}) == {
        "custom_finder_module": ["custom-finder-dist"]
    }
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("metadata_file", "entry"),
    [("installed-files.txt", "../eggmod.py"), ("SOURCES.txt", "eggmod.py")],
    ids=["installed-files", "sources"],
)
def test_external_module_inventory_matches_real_egg_info_layout(
    tmp_path, monkeypatch, metadata_file, entry
):
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    metadata = site / "fixture.egg-info"
    metadata.mkdir(parents=True)
    (site / "eggmod.py").write_text("", encoding="utf-8")
    (metadata / "PKG-INFO").write_text("Name: fixture-egg\nVersion: 1.0\n", encoding="utf-8")
    (metadata / metadata_file).write_text(entry + "\n", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(site)])

    requested = {"eggmod"}
    expected = {
        module: values
        for module, values in importlib.metadata.packages_distributions().items()
        if module in requested
    }
    assert expected == {"eggmod": ["fixture-egg"]}
    assert CapabilityCatalog._project_installed_module_distributions(requested) == expected


def test_external_module_inventory_falls_back_before_dynamic_metadata_finder_delegate(
    tmp_path, monkeypatch
):
    import importlib.metadata

    calls = []
    package = tmp_path / "dynamic_delegate"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")

    class CustomDistribution(importlib.metadata.Distribution):
        @property
        def metadata(self):
            return {"Name": "dynamic-delegate-dist"}

        def read_text(self, filename):
            return None

        def locate_file(self, path):
            return tmp_path / str(path)

        @property
        def files(self):
            path = importlib.metadata.PackagePath("dynamic_delegate/__init__.py")
            path.dist = self
            return [path]

    class DynamicMetadataFinder:
        @classmethod
        def find_distributions(cls, context=None):
            calls.append(context)
            return iter([CustomDistribution()])

    monkeypatch.setattr(importlib.metadata, "MetadataPathFinder", DynamicMetadataFinder)
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"dynamic_delegate"}) == {
        "dynamic_delegate": ["dynamic-delegate-dist"]
    }
    assert len(calls) == 1


def test_external_module_inventory_falls_back_before_dynamic_finder_descriptor(
    tmp_path, monkeypatch
):
    import importlib.metadata

    calls = []
    package = tmp_path / "descriptor_delegate"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")

    class CustomDistribution(importlib.metadata.Distribution):
        @property
        def metadata(self):
            return {"Name": "descriptor-delegate-dist"}

        def read_text(self, filename):
            return None

        def locate_file(self, path):
            return tmp_path / str(path)

        @property
        def files(self):
            path = importlib.metadata.PackagePath("descriptor_delegate/__init__.py")
            path.dist = self
            return [path]

    def find_distributions(cls, context=None):
        calls.append(context)
        return iter([CustomDistribution()])

    monkeypatch.setattr(
        importlib.metadata.MetadataPathFinder,
        "find_distributions",
        classmethod(find_distributions),
    )
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"descriptor_delegate"}) == {
        "descriptor_delegate": ["descriptor-delegate-dist"]
    }
    assert len(calls) == 1


def test_external_module_inventory_does_not_bind_unknown_path_finder_descriptor_twice(
    tmp_path, monkeypatch
):
    import importlib.machinery
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    metadata = site / "path_finder_dist-1.0.dist-info"
    package = site / "path_finder_module"
    metadata.mkdir(parents=True)
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (metadata / "METADATA").write_text("Name: path-finder-dist\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text("path_finder_module/__init__.py,,0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(site)])
    original = importlib.machinery.PathFinder.find_distributions
    calls = []

    class StatefulDescriptor:
        def __get__(self, instance, owner):
            calls.append((instance, owner))
            return original

    monkeypatch.setattr(
        importlib.machinery.PathFinder,
        "find_distributions",
        StatefulDescriptor(),
    )
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"path_finder_module"}) == {
        "path_finder_module": ["path-finder-dist"]
    }
    assert len(calls) == 1


def test_external_module_inventory_preserves_unknown_package_path_locate_error(
    tmp_path, monkeypatch
):
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    metadata = site / "locate_dist-1.0.dist-info"
    package = site / "locate_module"
    metadata.mkdir(parents=True)
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (metadata / "METADATA").write_text("Name: locate-dist\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text(
        "locate_module/__init__.py,,0\nunrelated_module.py,,0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "path", [str(site)])
    original = importlib.metadata.PackagePath.locate
    class_accesses = []
    instance_accesses = []

    class StatefulDescriptor:
        def __get__(self, instance, owner):
            if instance is None:
                class_accesses.append(owner)
                return original
            instance_accesses.append(str(instance))

            def locate():
                if str(instance) == "unrelated_module.py":
                    raise OSError("synthetic unrelated locate failure")
                return original(instance)

            return locate

    monkeypatch.setattr(importlib.metadata.PackagePath, "locate", StatefulDescriptor())
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    with pytest.raises(OSError, match="synthetic unrelated locate failure"):
        catalog._installed_module_distributions({"locate_module"})
    assert class_accesses == []
    assert instance_accesses == ["locate_module/__init__.py", "unrelated_module.py"]


def test_external_module_inventory_fails_closed_on_post_projection_delegate_change(
    tmp_path, monkeypatch
):
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    metadata = site / "stable_dist-1.0.dist-info"
    package = site / "stable_module"
    metadata.mkdir(parents=True)
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (metadata / "METADATA").write_text("Name: stable-dist\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text("stable_module/__init__.py,,0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(site)])
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None
    original_project = catalog._project_installed_module_distributions
    original_path_distribution = importlib.metadata.PathDistribution

    def change_after_projection(requested, *, require_stock=False):
        result = original_project(requested, require_stock=require_stock)

        class ChangedPathDistribution(original_path_distribution):
            pass

        monkeypatch.setattr(importlib.metadata, "PathDistribution", ChangedPathDistribution)
        return result

    monkeypatch.setattr(catalog, "_project_installed_module_distributions", change_after_projection)
    with pytest.raises(CapabilityError) as error:
        catalog._installed_module_distributions({"stable_module"})
    assert error.value.code == "dependency_inventory_changed"


def test_external_module_inventory_does_not_call_unknown_resolver_before_single_fallback(
    tmp_path, monkeypatch
):
    import importlib.machinery
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    metadata = site / "stateful_dist-1.0.dist-info"
    package = site / "stateful_module"
    metadata.mkdir(parents=True)
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (metadata / "METADATA").write_text("Name: stateful-dist\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text("stateful_module/__init__.py,,0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(site)])
    calls = []

    def stateful_resolvers():
        calls.append(True)
        return iter([importlib.machinery.PathFinder.find_distributions])

    monkeypatch.setattr(
        importlib.metadata.Distribution,
        "_discover_resolvers",
        staticmethod(stateful_resolvers),
    )
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"stateful_module"}) == {
        "stateful_module": ["stateful-dist"]
    }
    assert calls == [True]


def test_external_module_inventory_detects_in_place_public_api_code_change(monkeypatch):
    import importlib.metadata

    calls = []
    monkeypatch.setitem(importlib.metadata.__dict__, "_rwb_inplace_calls", calls)

    def replacement():
        _rwb_inplace_calls.append(True)  # noqa: F821
        return {"inplace_public_module": ["inplace-public-dist"]}

    monkeypatch.setattr(importlib.metadata.packages_distributions, "__code__", replacement.__code__)
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"inplace_public_module"}) == {
        "inplace_public_module": ["inplace-public-dist"]
    }
    assert calls == [True]


def test_external_module_inventory_detects_in_place_inferred_helper_code_change(
    tmp_path, monkeypatch
):
    import importlib.metadata
    import sys

    site = tmp_path / "site"
    metadata = site / "helper_dist-1.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: helper-dist\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text("helper_dist-1.0.dist-info/METADATA,,0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(site)])
    calls = []
    monkeypatch.setitem(importlib.metadata.__dict__, "_rwb_helper_calls", calls)

    def replacement(_distribution):
        _rwb_helper_calls.append(True)  # noqa: F821
        return ["inplace_helper_module"]

    monkeypatch.setattr(importlib.metadata._top_level_inferred, "__code__", replacement.__code__)
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    assert catalog._installed_module_distributions({"inplace_helper_module"}) == {
        "inplace_helper_module": ["helper-dist"]
    }
    assert calls == [True]


def test_catalog_import_survives_missing_private_metadata_primitive(tmp_path):
    import os
    import subprocess
    import sys

    script = """
import importlib.metadata as metadata
delattr(metadata.Distribution, '_read_files_egginfo_installed')
calls = []
def fallback():
    calls.append(True)
    return {'fallback_module': ['fallback-dist']}
metadata.packages_distributions = fallback
from app.research_web.capabilities import catalog
assert catalog._READ_FILES_EGGINFO_INSTALLED is catalog._MISSING
instance = catalog.CapabilityCatalog.__new__(catalog.CapabilityCatalog)
instance._initializing = False
instance._initial_module_distributions = None
assert instance._installed_module_distributions({'fallback_module'}) == {
    'fallback_module': ['fallback-dist'],
}
assert calls == [True]
print('missing-primitive-fallback-ok')
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "missing-primitive-fallback-ok"


@pytest.mark.parametrize("mode", ["hide", "expose", "error"])
def test_external_module_inventory_falls_back_before_dynamic_path_distribution(
    tmp_path, monkeypatch, mode
):
    import importlib.metadata
    import sys

    original = importlib.metadata.PathDistribution
    site = tmp_path / "site"
    metadata = site / "dynamic_dist-1.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: dynamic-dist\nVersion: 1.0\n", encoding="utf-8")
    raw_module = site / "raw_module.py"
    exposed_module = site / "exposed_module.py"
    raw_module.write_text("", encoding="utf-8")
    exposed_module.write_text("", encoding="utf-8")
    (metadata / "RECORD").write_text(
        ("raw_module.py,,0\n" if mode == "hide" else "dynamic_dist-1.0.dist-info/METADATA,,0\n"),
        encoding="utf-8",
    )
    instances = []

    class DynamicPathDistribution(original):
        def __init__(self, path):
            instances.append(path)
            super().__init__(path)

        @property
        def files(self):
            if mode == "error":
                raise ValueError("custom files failure")
            if mode == "hide":
                return []
            path = importlib.metadata.PackagePath("exposed_module.py")
            path.dist = self
            return [path]

    monkeypatch.setattr(importlib.metadata, "PathDistribution", DynamicPathDistribution)
    monkeypatch.setattr(sys, "path", [str(site)])
    catalog = CapabilityCatalog.__new__(CapabilityCatalog)
    catalog._initializing = False
    catalog._initial_module_distributions = None

    requested = {"raw_module" if mode == "hide" else "exposed_module"}
    if mode == "error":
        with pytest.raises(ValueError, match="custom files failure"):
            catalog._installed_module_distributions(requested)
    elif mode == "hide":
        assert catalog._installed_module_distributions(requested) == {}
    else:
        assert catalog._installed_module_distributions(requested) == {
            "exposed_module": ["dynamic-dist"]
        }
    assert len(instances) == 1


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("我的事件研究", "finance-news-event-research"),
        ("金融事件研究", "my-finance-event-research"),
    ],
)
def test_new_builtin_name_or_slug_conflict_skips_only_that_seed(tmp_path, monkeypatch, name, slug):
    target = "finance-news-event-research"
    shipped = seed_packages
    monkeypatch.setattr(
        "app.research_web.capabilities.catalog.seed_packages",
        lambda: [item for item in shipped() if item[0] != target],
    )
    existing = CapabilityCatalog(tmp_path)
    created = existing.create(candidate(name=name, slug=slug))
    existing.publish(created["id"])
    original_user_row = deepcopy(existing.row(created["id"]))

    monkeypatch.setattr("app.research_web.capabilities.catalog.seed_packages", shipped)
    warnings = []
    monkeypatch.setattr(
        "app.research_web.capabilities.catalog.log.warning",
        lambda event, **fields: warnings.append((event, fields)),
    )
    upgraded = CapabilityCatalog(tmp_path)

    assert upgraded.row(created["id"]) == original_user_row
    assert target not in upgraded.data["items"]
    assert {
        "document-reading",
        "industry-chain-research",
        "earnings-consensus-research",
        "macro-asset-research",
        "sell-side-report-reader",
    } <= upgraded.data["items"].keys()
    assert warnings == [
        (
            "capability_builtin_seed_conflict",
            {
                "capability_id": target,
                "conflict_code": "name_conflict",
                "action": "skipped",
            },
        )
    ]


def test_offline_seed_catalog_tools_and_workflows_without_session(api, monkeypatch):
    client, native, service = api
    from app.research_web.capabilities import tools as capability_tools

    ready_capabilities = {
        "search_assets",
        "market_bars",
        "market_snapshot",
        "financials",
        "market_activity",
        "fund_data",
        "search_news",
    }
    build_catalog = capability_tools.build_catalog

    def deterministic_catalog(**kwargs):
        catalog = build_catalog(**kwargs)
        for capability in catalog["capabilities"]:
            capability["callable_source_count"] = int(capability["id"] in ready_capabilities)
        return catalog

    monkeypatch.setattr(capability_tools, "build_catalog", deterministic_catalog)
    service.connected.clear()
    native.calls.clear()
    result = client.get("/api/research/capabilities")
    assert result.status_code == 200
    rows = result.json()["items"]
    shipped = seed_packages()
    assert len(rows) == len(shipped)
    assert len([row for row in rows if row["kind"] == "method"]) == sum(
        draft["kind"] == "method" for _, draft in shipped
    )
    assert {r["name"] for r in rows if r["kind"] == "skill"} == {
        "资料解读",
        "公司研究",
        "行业研究",
        "基金评价",
        "市场解读",
        "金融事件研究",
        "产业链与主题研究",
        "业绩与一致预期",
        "宏观与跨资产",
        "研报增量分析",
        "因子库研究",
        "框架深度验证",
        "每日市场简报",
        "政策哨兵",
        "事件复盘",
        "ETF 资金流监控",
        "财报披露监控",
        "业绩预告监控",
        "基金匹配",
        "基金持仓穿透",
        "组合重合度",
        "组合基准偏离",
        "行业景气度",
        "行业象限监控",
        "行业拥挤度",
        "利率均线择时研究",
        "股权风险溢价择时研究",
        "风格轮动研究",
        "平台突破研究",
        "缠论确认分型与笔研究",
        "持仓排雷（确定性核验）",
        "预期差（确定性核验）",
        "短线情绪（确定性核验）",
        "调研前置（确定性核验）",
        "事件复盘（确定性核验）",
        "海内外舆情（确定性核验）",
        "估值体检（确定性核验）",
        "筹码结构（确定性核验）",
        "财报季前瞻（确定性核验）",
        "公司资料核验",
        "新闻事实与条件传导",
        "调研材料准备",
    }
    assert all(r["source"] == "builtin" and r["version"] == 1 for r in rows)
    workflows = client.get("/api/research/workflows").json()["items"]
    assert len(workflows) == 4
    assert "report-production-workflow" in {row["id"] for row in workflows}
    tools = client.get("/api/research/tools").json()["items"]
    assert {t["id"] for t in tools if t["selectable"]} == {
        "research_run_script",
        "research_document_operation",
        "datahub_get_fund_data",
        "datahub_search_news",
        "datahub_search_assets",
        "datahub_get_market_bars",
        "datahub_get_market_snapshot",
        "datahub_get_financials",
        "datahub_get_market_activity",
        "web_search",
    }
    baseline_tool_ids = {
        "rwb_prepare_automation",
        "rwb_record_method_use",
        "research_document_operation",
        "research_run_script",
        "web_search",
        "skill",
        "subagent",
        "send_message",
        "interrupt_agent",
        "list_agents",
        "datahub_search_assets",
        "datahub_get_trading_calendar",
        "datahub_get_market_bars",
        "datahub_get_market_snapshot",
        "datahub_get_index_data",
        "datahub_get_financials",
        "datahub_get_market_activity",
        "datahub_get_factor_macro",
        "datahub_get_fund_data",
        "datahub_search_news",
        "datahub_search_announcements",
        "datahub_search_research",
        "datahub_search_web",
        "datahub_get_database_schema",
        "datahub_query_table",
        "report_workbook_refresh",
        "report_workbook_extract",
        "report_template_inspect",
        "report_chart_render",
        "report_docx_assemble",
        "report_pptx_assemble",
        "report_delivery_validate",
    }
    added_tool_ids = {
        "datahub_get_external_data",
        "rwb_list_automations",
        "rwb_prepare_automation_update",
        "rwb_run_automation",
        "ask_user_question",
        "research_check_quality",
        "research_read_source",
        "rwb_query_latest_cls_news",
    }
    assert {tool["id"] for tool in tools} == baseline_tool_ids | added_tool_ids
    assert all(
        not tool["selectable"]
        for tool in tools
        if tool["id"] in {"research_check_quality", "research_read_source"}
    )
    assert len(tools) == len(baseline_tool_ids | added_tool_ids)
    owned_news = next(tool for tool in tools if tool["id"] == "rwb_query_latest_cls_news")
    assert owned_news["required_tools"] == ["datahub_search_news"]
    assert owned_news["selectable"] is False
    assert owned_news["read_only"] is True
    assert owned_news["approval"] == "native-policy-unchanged"
    assert owned_news["conditions"] == [
        "需专属研究工具 preset，目录声明不代表实例在线或授权",
        "仅底层datahub_search_news及CLS来源/任务scope获准时；limit先行再正文子串筛选，empty不等于全市场无新闻",
    ]
    assert owned_news["parameters"] == {
        "type": "object",
        "properties": {
            "query": {"type": "string", "maxLength": 2000},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": [],
        "additionalProperties": False,
    }
    document_tool = next(tool for tool in tools if tool["id"] == "research_document_operation")
    assert document_tool["read_only"] is False
    workflow_tools = {t["id"] for t in tools if t.get("execution_surface") == "workflow_backend"}
    assert workflow_tools == {
        "report_workbook_refresh",
        "report_workbook_extract",
        "report_template_inspect",
        "report_chart_render",
        "report_docx_assemble",
        "report_pptx_assemble",
        "report_delivery_validate",
    }
    assert all(not t["selectable"] for t in tools if t["id"] in workflow_tools)
    assert sum(t["id"] == "datahub_get_fund_data" for t in tools) == 1
    assert all(t["parameters"] and t["source"] and t["conditions"] for t in tools)
    datahub_tools = [
        t
        for t in tools
        if t["source"] == "runtime/public-data.mjs" and t["id"] != "rwb_query_latest_cls_news"
    ]
    assert {tool["id"] for tool in datahub_tools} == {
        identifier
        for identifier in baseline_tool_ids | added_tool_ids
        if identifier.startswith("datahub_")
    }
    assert all(t["approval"] == "automatic" for t in datahub_tools)
    assert all(
        t["conditions"]
        == [
            "已配置且可用的 DataHub 来源自动执行，无逐次确认",
            "无可调用来源的能力不会注册到 Runtime",
        ]
        for t in datahub_tools
    )
    assert native.calls == []


def test_specialist_seed_metadata_boundaries_and_existing_contracts(api):
    client, _, _ = api
    rows = {row["id"]: row for row in client.get("/api/research/capabilities").json()["items"]}
    expected_scopes = {
        "industry-research": [
            {"capability": "search_news", "dataset": "telegram"},
            {
                "capability": "financials",
                "dataset": "financials",
                "required": False,
                "currency": "CNY",
                "omit_sections": ["专业财务量化章节"],
            },
        ],
        "fund-evaluation": [
            {
                "capability": "fund_data",
                "dataset": "fund_nav",
                "frequency": "daily",
                "adjustment": "none",
                "units": {"unit_nav": "currency/share"},
            }
        ],
    }
    existing = {
        "document-reading": (
            "资料解读",
            "资料研究",
            [],
            ["research_run_script", "datahub_search_news"],
        ),
        "company-research": (
            "公司研究",
            "公司",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_search_news"],
        ),
        "industry-research": (
            "行业研究",
            "行业",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_search_news"],
        ),
        "fund-evaluation": (
            "基金评价",
            "基金",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_get_fund_data"],
        ),
        "market-commentary": (
            "市场解读",
            "市场",
            ["docx", "html", "xlsx"],
            ["research_run_script", "datahub_search_news"],
        ),
        "factor-database-research": (
            "因子库研究",
            "因子研究",
            ["docx", "html", "xlsx"],
            [
                "research_run_script",
                "datahub_get_database_schema",
                "datahub_query_table",
            ],
        ),
    }
    for slug, (name, category, formats, tools) in existing.items():
        metadata = rows[slug]["metadata"]
        assert rows[slug]["version"] == 1
        assert metadata == {
            "slug": slug,
            "name": name,
            "description": f"基于实际材料开展{name}，保留来源、口径及数据缺失，按需交付真实文件。",
            "category": category,
            "inputs": [
                {
                    "name": "question",
                    "label": "研究问题与资料",
                    "type": "text",
                    "required": True,
                }
            ],
            "scenarios": [name],
            "default_formats": formats,
            "required_tools": tools,
            "dependencies": [],
            "method_policy": {"required": [], "recommended": [], "excluded": []},
            "data_requirements": expected_scopes.get(slug, []),
        }

    workflows = {
        "market-commentary-workflow": "市场资料筛选与解读交付",
        "fund-research-workflow": "基金资料准备与受限评价",
        "company-research-workflow": "公司资料研究与报告交付",
        "report-production-workflow": "报告项目资料准备与文件交付",
    }
    for slug, name in workflows.items():
        row = rows[slug]
        assert row["version"] == 1
        assert row["metadata"] == {
            "slug": slug,
            "name": name,
            "description": "有序研究步骤模板；并不表示任何步骤已经执行。",
            "category": "研究流程",
            "inputs": [
                {
                    "name": "question",
                    "label": "对象、期间与资料",
                    "type": "text",
                    "required": True,
                }
            ],
            "scenarios": [name],
            "default_formats": ["docx", "html", "xlsx"],
            "required_tools": ["research_run_script"],
            "dependencies": [],
            "method_policy": {"required": [], "recommended": [], "excluded": []},
        }

    specialists = {
        "finance-news-event-research": ("金融事件研究", "事件与政策"),
        "industry-chain-research": ("产业链与主题研究", "行业与主题"),
        "earnings-consensus-research": ("业绩与一致预期", "公司与业绩"),
        "macro-asset-research": ("宏观与跨资产", "宏观与资产"),
        "sell-side-report-reader": ("研报增量分析", "研报与资料"),
    }
    for slug, (name, category) in specialists.items():
        row = rows[slug]
        metadata = row["metadata"]
        detail = client.get(f"/api/research/capabilities/{slug}").json()
        header = yaml.safe_load(detail["draft"]["instructions"].split("---", 2)[1])
        assert row["kind"] == "skill" and row["source"] == "builtin"
        assert row["version"] == 1 and row["enabled"] is True
        assert metadata["slug"] == header["name"] == slug
        assert metadata["name"] == name and metadata["category"] == category
        assert metadata["default_formats"] == []
        assert metadata["required_tools"] == (
            ["research_run_script", "web_search"]
            if slug == "sell-side-report-reader"
            else ["web_search"]
        )
        assert metadata["dependencies"] == []
        assert "不" in metadata["description"]
    assert not any("router" in capability_id for capability_id in rows)


def test_specialist_exports_bundle_one_evidence_protocol_snapshot_and_reimports(
    api, monkeypatch, tmp_path
):
    client, _, _ = api
    slugs = (
        "finance-news-event-research",
        "industry-chain-research",
        "earnings-consensus-research",
        "macro-asset-research",
        "sell-side-report-reader",
    )
    protocol_hashes = set()
    exported = None
    for slug in slugs:
        response = client.get(f"/api/research/capabilities/{slug}/versions/1/export")
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            assert names.count("references/evidence-protocol.md") == 1
            protocol = archive.read("references/evidence-protocol.md")
            protocol_hashes.add(hashlib.sha256(protocol).hexdigest())
            assert b"DataHub" in protocol
            visible_package = b"\n".join(
                archive.read(name) for name in names if name.endswith((".md", ".json"))
            )
            assert b"ZhengYan" not in visible_package and b"OpenAI" not in visible_package
        exported = response.content
    assert len(protocol_hashes) == 1

    monkeypatch.setattr("app.research_web.capabilities.catalog.seed_packages", list)
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path / "reimport"))
    with TestClient(create_app(service)) as import_client:
        imported = import_client.post(
            "/api/research/capabilities/import",
            files={"file": ("specialist.zip", exported, "application/zip")},
        )
        assert imported.status_code == 201, imported.text
        draft = imported.json()["draft"]
        bundled = next(
            item for item in draft["files"] if item["path"] == "references/evidence-protocol.md"
        )
        assert bundled["sha256"] in protocol_hashes
        assert bundled["content"].encode() == protocol


def test_catalog_migrates_persisted_legacy_tool_ids_as_new_versions(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    custom = catalog.create(candidate())
    catalog.publish(custom["id"])

    for cid in ("document-reading", custom["id"]):
        row = catalog.row(cid)
        row["draft"]["metadata"]["required_tools"] = ["af_run_script"]
        row["draft"]["instructions"] = row["draft"]["instructions"].replace(
            "research_run_script", "af_run_script"
        )
        active = row["versions"][str(row["version"])]
        active["metadata"]["required_tools"] = ["af_run_script"]
        active["instructions"] = active["instructions"].replace(
            "research_run_script", "af_run_script"
        )

    workflow = catalog.row("fund-research-workflow")
    for record in (workflow["draft"], workflow["versions"]["1"]):
        record["metadata"]["required_tools"] = ["af_run_script"]
        record["steps"][0]["tools"] = ["af_public_data"]
        record["steps"][1]["tools"] = ["af_run_script"]
        record["steps"][2]["tools"] = ["af_run_script"]
    catalog.save()

    migrated = CapabilityCatalog(tmp_path)
    for cid in (
        "document-reading",
        "fund-research-workflow",
        "market-commentary-workflow",
        custom["id"],
    ):
        row = migrated.row(cid)
        assert row["version"] == 2
        active = row["versions"]["2"]
        assert "af_run_script" not in json.dumps(active, ensure_ascii=False)
        assert "af_public_data" not in json.dumps(active, ensure_ascii=False)
        assert migrated.selection(cid)["version"] == 2
    assert migrated.row("document-reading")["versions"]["1"]["metadata"]["required_tools"] == [
        "af_run_script"
    ]
    assert migrated.row("fund-research-workflow")["versions"]["2"]["steps"][0]["tools"] == [
        "datahub_get_fund_data"
    ]

    reloaded = CapabilityCatalog(tmp_path)
    assert reloaded.row("document-reading")["version"] == 2
    assert reloaded.row("market-commentary-workflow")["version"] == 2
    assert reloaded.row(custom["id"])["version"] == 2


def test_draft_check_publish_copy_versions_disable_rollback_export(api):
    client, _, service = api
    row = create(client)
    cid = row["id"]
    base = f"/api/research/capabilities/{cid}"
    assert row["status"] == "draft"
    assert client.post(base + "/check").json()["valid"] is True
    first = client.post(base + "/publish").json()
    assert first["status"] == "enabled" and first["version"] == 1
    version_path = service.capabilities.version_path(cid, 1)
    first_raw = (version_path / "SKILL.md").read_bytes()
    assert not (version_path / "SKILL.md").stat().st_mode & 0o222
    changed = candidate()
    changed["instructions"] += "\n新增研究要求。"
    assert client.patch(base + "/draft", json=changed).status_code == 200
    assert client.post(base + "/publish").json()["version"] == 2
    assert (version_path / "SKILL.md").read_bytes() == first_raw
    assert client.post(base + "/disable").json()["status"] == "disabled"
    assert client.post(base + "/enable").json()["status"] == "enabled"
    assert client.post(base + "/rollback", json={"version": 1}).json()["version"] == 1
    assert len(client.get(base + "/versions").json()["items"]) == 2
    exported = client.get(base + "/versions/1/export")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert archive.read("SKILL.md").decode() == candidate()["instructions"]
        assert json.loads(archive.read("capability.json"))["name"] == "我的研究"
    assert client.post("/api/research/capabilities", json=candidate()).status_code == 409
    assert (
        client.patch("/api/research/capabilities/company-research/draft", json=changed).status_code
        == 409
    )
    copied = client.post(
        "/api/research/capabilities/company-research/copy",
        json={"name": "公司研究副本", "slug": "company-copy"},
    )
    assert copied.status_code == 201 and copied.json()["source"] == "copy"
    assert copied.json()["status"] == "draft"


def test_metadata_dependencies_tools_invalid_preserved(api):
    client, _, _ = api
    value = candidate()
    value["metadata"]["dependencies"] = ["rwb-nonexistent-distribution-987==1.0"]
    row = create(client, value)
    base = f"/api/research/capabilities/{row['id']}"
    checks = client.post(base + "/check").json()
    assert checks["status"] == "blocked_dependencies"
    assert any(c["code"] == "dependency_missing" for c in checks["issues"])
    assert client.post(base + "/publish").status_code == 422
    value["metadata"]["dependencies"] = []
    value["metadata"]["required_tools"] = ["shell"]
    value["metadata"]["inputs"] = []
    client.patch(base + "/draft", json=value)
    checks = client.post(base + "/check").json()
    assert {c["code"] for c in checks["issues"]} >= {
        "tool_unavailable",
        "metadata_invalid",
    }
    assert client.get(base).json()["draft"]["metadata"]["required_tools"] == ["shell"]


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.md",
        "/absolute.md",
        "a/../../escape.md",
        "a\\evil.md",
        "nested.zip",
        "install.py",
        "payload.exe",
        ".git/config",
        "C:/evil.md",
    ],
)
def test_import_unsafe_zip_keeps_report_without_extraction(api, filename):
    client, _, service = api
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("SKILL.md", candidate()["instructions"])
        zf.writestr(filename, "malicious input")
    response = client.post(
        "/api/research/capabilities/import",
        files={"file": ("research.zip", archive.getvalue(), "application/zip")},
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["status"] == "invalid"
    assert row["checks"]["issues"]
    assert not (service.store.root.parent / "escape.md").exists()
    assert not list(service.capabilities.native_root.glob("rwb-*"))


def test_zip_link_duplicate_limits_and_missing_metadata(api):
    client, _, _ = api
    for kind in ("symlink", "duplicate", "count", "expanded"):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", candidate()["instructions"])
            if kind == "symlink":
                info = zipfile.ZipInfo("templates/link.md")
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                zf.writestr(info, "/etc/passwd")
            elif kind == "duplicate":
                zf.writestr("skill.MD", "ambiguous")
            elif kind == "count":
                for i in range(128):
                    zf.writestr(f"t{i}.md", "text")
            else:
                zf.writestr("huge.md", b"a" * (10 * 1024 * 1024 + 1))
        response = client.post(
            "/api/research/capabilities/import",
            files={"file": ("research.zip", archive.getvalue())},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "invalid"
    response = client.post(
        "/api/research/capabilities/import",
        files={"file": ("SKILL.md", candidate()["instructions"].encode())},
    )
    assert response.json()["status"] == "invalid"
    assert any(i["code"] == "metadata_invalid" for i in response.json()["checks"]["issues"])


def test_workflow_compiles_native_skill_template_not_execution(api):
    client, _, service = api
    value = candidate()
    value["kind"] = "workflow"
    value["instructions"] = ""
    value["steps"] = [
        {
            "title": "资料核对",
            "instruction": "核对来源和缺失",
            "skill_id": "document-reading",
            "tools": ["research_run_script"],
        },
        {"title": "交付", "instruction": "仅生成实际文件", "tools": []},
    ]
    row = create(client, value)
    result = client.post(f"/api/research/capabilities/{row['id']}/publish")
    assert result.status_code == 200, result.text
    compiled = (
        service.capabilities.native_root / result.json()["native_name"] / "SKILL.md"
    ).read_text()
    assert "步骤模板" in compiled and "未执行" in compiled and "document-reading" in compiled
    assert "1. 资料核对" in compiled and "2. 交付" in compiled


def test_research_script_requires_explicit_review_and_never_executes(api):
    client, _, _ = api
    value = candidate()
    value["files"].append(
        {
            "path": "scripts/research.py",
            "content": "raise RuntimeError('never execute')",
        }
    )
    row = create(client, value)
    base = f"/api/research/capabilities/{row['id']}"
    check = client.post(base + "/check").json()
    assert any(i["code"] == "script_review_required" for i in check["issues"])
    assert client.post(base + "/publish").status_code == 422
    reviewed = next(
        f["sha256"] for f in client.get(base).json()["draft"]["files"] if f["path"].endswith(".py")
    )
    value["reviewed_scripts"] = [reviewed]
    assert client.patch(base + "/draft", json=value).status_code == 200
    assert client.post(base + "/publish").status_code == 200
