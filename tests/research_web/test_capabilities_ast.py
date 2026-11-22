"""Ordered validation equivalence; scripts remain inert source bytes throughout."""

import ast
import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_api import isolated_keyring  # noqa: F401
from test_capabilities import candidate

from app.research_web.capabilities import catalog as catalog_module
from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.pack_resources import MANIFEST_PATH, canonical, closure
from app.research_web.capabilities.packages import decode_file, encode_file

ORACLE = Path(__file__).parent / "fixtures/capabilities-ast-validation-oracle.json"


def validation_vectors():
    """Reuse every original process/allowed-name vector without executing it."""
    source = Path(__file__).with_name("test_capabilities_safety.py").read_text()
    tree = ast.parse(source)
    vectors = [
        {"id": "plain", "code": "value = 1"},
        {"id": "unreviewed", "code": "value = 1", "reviewed": False},
    ]
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef) or function.name not in {
            "test_reviewed_script_rejects_incompatible_runtime_entrypoints",
            "test_host_process_names_without_matching_import_are_allowed",
        }:
            continue
        for decorator in function.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not decorator.args or ast.literal_eval(decorator.args[0]) != "content":
                continue
            contents = ast.literal_eval(decorator.args[1])
            ids = ast.literal_eval(next(k.value for k in decorator.keywords if k.arg == "ids"))
            vectors.extend({"id": name, "code": content} for name, content in zip(ids, contents))
    vectors.extend(
        [
            {"id": "syntax", "code": "def broken("},
            {"id": "installer-import", "code": "import ensurepip\nensurepip.bootstrap()"},
            {
                "id": "installer-command",
                "code": "import subprocess\nsubprocess.run(['pip','install','fixture'])",
            },
            {"id": "installer-path", "code": "value=1", "path": "scripts/install_hook.py"},
            {"id": "relative-valid", "relative": "valid"},
            {"id": "relative-missing", "relative": "missing"},
            {"id": "relative-escape", "relative": "escape"},
            {"id": "encoding-api", "encoding": "api"},
            {"id": "encoding-defense", "encoding": "defense"},
            {
                "id": "multi-issue",
                "code": "from .missing import value\nimport subprocess\nimport missing_fixture_dependency\ncommand='pip install fixture'",
            },
            {"id": "pack-dynamic", "pack": True, "code": "__import__('os')"},
            {"id": "pack-third-party", "pack": True, "code": "import requests"},
            {"id": "pack-relative", "pack": True, "code": "from .missing import value"},
            {
                "id": "pack-multi-issue",
                "pack": True,
                "code": "__import__('os')\nimport subprocess\nimport missing_fixture_dependency",
            },
            {"id": "workflow-bindings", "builtin_kind": "workflow"},
            {"id": "method-status", "builtin_kind": "method"},
        ]
    )
    return vectors


def validation_draft(catalog, vector, marker):
    statement = f"\nopen({str(marker)!r}, 'w').write('must never execute')\n"
    if vector.get("builtin_kind"):
        row = next(r for r in catalog.data["items"].values() if r["kind"] == vector["builtin_kind"])
        return row["kind"], copy.deepcopy(row["draft"])
    if vector.get("pack"):
        row = catalog.data["items"]["research-pack-position-risk"]
        draft = copy.deepcopy(row["draft"])
        draft["files"] = [
            (
                encode_file(f["path"], (vector["code"] + statement).encode())
                if f["path"] == "scripts/calculate.py"
                else f
            )
            for f in draft["files"]
        ]
        manifest = json.loads(
            decode_file(next(f for f in draft["files"] if f["path"] == MANIFEST_PATH))
        )
        manifest["files"] = sorted(
            [
                {"path": f["path"], "sha256": f["sha256"]}
                for f in draft["files"]
                if f["path"] != MANIFEST_PATH
            ],
            key=lambda entry: entry["path"],
        )
        manifest["closure_sha256"] = closure(draft["files"])
        draft["files"] = [
            encode_file(MANIFEST_PATH, canonical(manifest)) if f["path"] == MANIFEST_PATH else f
            for f in draft["files"]
        ]
        draft["reviewed_scripts"] = [
            f["sha256"] for f in draft["files"] if f["path"].endswith(".py")
        ]
        return row["kind"], draft
    value = candidate()
    if vector.get("relative"):
        first = {
            "valid": "from . import helper",
            "missing": "from .missing import value",
            "escape": "from .. import helper",
        }[vector["relative"]]
        value["files"] = [
            {"path": "scripts/pkg/__init__.py", "content": first + statement},
            {"path": "scripts/pkg/helper.py", "content": "value=1" + statement},
            {"path": "scripts/research.py", "content": "from pkg import helper" + statement},
        ]
    else:
        value["files"] = [
            {
                "path": vector.get("path", "scripts/research.py"),
                "content": vector.get("code", "value=1") + statement,
            }
        ]
    if vector.get("encoding") == "api":
        raw = b"\xff" + statement.encode()
        value["files"] = [
            {
                "path": "scripts/research.py",
                "base64": base64.b64encode(raw).decode(),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ]
    draft = catalog._draft(value)
    if vector.get("encoding") == "defense":
        raw = b"\xff" + statement.encode()
        draft["files"][0].update(
            base64=base64.b64encode(raw).decode(),
            size=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
        )
    draft["reviewed_scripts"] = (
        [f["sha256"] for f in draft["files"]] if vector.get("reviewed", True) else []
    )
    return "skill", draft


def stable_validation(result):
    assert isinstance(result["checked_at"], (float, int)) and result["checked_at"] > 0
    return {key: value for key, value in result.items() if key != "checked_at"}


@pytest.fixture
def validator(tmp_path):
    return CapabilityCatalog(tmp_path)


def test_complete_ordered_validation_oracle_and_changed_source(validator, tmp_path):
    expected = json.loads(ORACLE.read_text())
    marker = tmp_path / "must-not-execute"
    vectors = validation_vectors()
    assert [v["id"] for v in vectors] == expected["case_ids"]
    for vector in vectors:
        kind, draft = validation_draft(validator, vector, marker)
        result = stable_validation(validator.validate(kind, draft))
        assert result == expected["results"][vector["id"]], vector["id"]
        assert not marker.exists()
    kind, safe = validation_draft(validator, {"id": "safe", "code": "value=1"}, marker)
    assert validator.validate(kind, safe)["valid"]
    kind, dangerous = validation_draft(
        validator, {"id": "changed", "code": "import subprocess"}, marker
    )
    changed = validator.validate(kind, dangerous)
    assert not changed["valid"] and any(
        i["code"] == "runtime_incompatible_script" for i in changed["issues"]
    )
    dangerous["reviewed_scripts"] = safe["reviewed_scripts"]
    unreviewed = validator.validate(kind, dangerous)
    assert any(i["code"] == "script_review_required" for i in unreviewed["issues"])
    assert not marker.exists()


def test_each_file_has_one_fresh_walk_on_every_validation(validator, tmp_path, monkeypatch):
    marker = tmp_path / "must-not-execute"
    kind, draft = validation_draft(validator, {"relative": "valid"}, marker)
    original_walk = catalog_module.ast.walk
    trees = []

    def observed_walk(tree):
        trees.append(tree)
        return original_walk(tree)

    monkeypatch.setattr(catalog_module.ast, "walk", observed_walk)
    assert validator.validate(kind, draft)["valid"]
    assert len(trees) == 3 and len({id(tree) for tree in trees}) == 3
    kind, second = validation_draft(validator, {"relative": "missing"}, marker)
    assert not validator.validate(kind, second)["valid"]
    assert len(trees) == 6 and len({id(tree) for tree in trees}) == 6
    assert not marker.exists()
