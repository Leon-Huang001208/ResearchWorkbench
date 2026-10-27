"""Closed runtime roots, install-ledger exclusions and unlisted bytecode."""

import importlib.metadata

import pytest


def distribution(tmp_path, monkeypatch):
    from app.research_web.capabilities import pack_dependencies

    env = tmp_path / "managed"
    base = env / "lib/python3.12/site-packages"
    package = base / "jsonschema"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE=1\n")
    meta = base / "jsonschema-4.26.0.dist-info"
    meta.mkdir()
    (meta / "METADATA").write_text("Metadata-Version: 2.1\nName: jsonschema\nVersion: 4.26.0\n")
    (meta / "WHEEL").write_text("Wheel-Version: 1.0\nTag: py3-none-any\n")
    (meta / "INSTALLER").write_text("fixture-v1")
    (meta / "entry_points.txt").write_text("[console_scripts]\njsonschema=jsonschema.cli:main\n")
    entries = [
        "jsonschema/__init__.py",
        *[
            f"{meta.name}/{name}"
            for name in ("METADATA", "WHEEL", "INSTALLER", "entry_points.txt", "RECORD")
        ],
        "../../../bin/jsonschema",
    ]
    (meta / "RECORD").write_text("\n".join(name + ",," for name in entries))
    console = env / "bin/jsonschema"
    console.parent.mkdir()
    console.write_text("#!fixture-prefix-one\n")
    dist = importlib.metadata.PathDistribution(meta)
    original = pack_dependencies.importlib.metadata.distribution
    monkeypatch.setattr(
        pack_dependencies.importlib.metadata,
        "distribution",
        lambda name: dist if name == "jsonschema" else original(name),
    )
    return env, package, meta, console


def test_only_nonexecuted_install_bookkeeping_and_external_console_are_excluded(
    tmp_path, monkeypatch
):
    from app.research_web.capabilities.pack_dependencies import _dependency_identity

    env, _package, meta, console = distribution(tmp_path, monkeypatch)
    first = _dependency_identity("jsonschema", "4.26.0", env)
    (meta / "INSTALLER").write_text("fixture-v2")
    console.write_text("#!fixture-prefix-two\n")
    second = _dependency_identity("jsonschema", "4.26.0", env)
    assert first == second
    assert {item["reason"] for item in first["excluded"]} == {
        "installation_bookkeeping_not_executed",
        "external_console_entry_not_executed",
    }


@pytest.mark.parametrize("changed", ["source", "unlisted_source", "unlisted_pyc"])
def test_every_runtime_source_and_unlisted_cache_changes_the_actual_closure(
    tmp_path, monkeypatch, changed
):
    from app.research_web.capabilities.pack_dependencies import _dependency_identity

    env, package, _meta, _console = distribution(tmp_path, monkeypatch)
    first = _dependency_identity("jsonschema", "4.26.0", env)
    if changed == "source":
        (package / "__init__.py").write_text("VALUE=2\n")
    elif changed == "unlisted_source":
        (package / "not-in-record.py").write_text("VALUE=2\n")
    else:
        (package / "__pycache__").mkdir()
        (package / "__pycache__/not-in-record.pyc").write_bytes(b"synthetic-cache-bytes")
    second = _dependency_identity("jsonschema", "4.26.0", env)
    assert first["closure_sha256"] != second["closure_sha256"]


@pytest.mark.parametrize("bad", ["symlink", "metadata", "outside_code"])
def test_unsafe_links_fake_identity_and_external_code_are_rejected(tmp_path, monkeypatch, bad):
    from app.research_web.capabilities.pack_dependencies import _dependency_identity

    env, package, meta, _console = distribution(tmp_path, monkeypatch)
    if bad == "symlink":
        outside = tmp_path / "outside.py"
        outside.write_text("PRIVATE=1\n")
        (package / "alias.py").symlink_to(outside)
    elif bad == "metadata":
        (meta / "METADATA").write_text("Name: counterfeit\nVersion: 4.26.0\n")
    else:
        with (meta / "RECORD").open("a") as stream:
            stream.write("\n../../../bin/not-a-console.py,,")
    with pytest.raises(ValueError):
        _dependency_identity("jsonschema", "4.26.0", env)
