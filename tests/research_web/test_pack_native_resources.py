"""Frozen Native package resources: no provider, model or production state."""

import copy
import hashlib
import json
import logging
from pathlib import Path

import pytest

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.models import CapabilityError
from app.research_web.capabilities.packages import decode_file, encode_file
from app.research_web.capabilities.seeds import RECEIPT_GATED_SKILLS


def test_nine_frozen_packages_have_complete_byte_identical_core():
    from app.research_web.capabilities.pack_resources import CORE_FILES, pack_packages
    from app.research_web.scenarios import packs

    packages = dict(pack_packages())
    assert len(packages) == 9
    for pack_id in packs.PACKS:
        draft = packages["research-pack-" + pack_id]
        files = {f["path"]: decode_file(f) for f in draft["files"]}
        manifest = json.loads(files["references/pack-code-manifest.json"])
        assert manifest["pack_id"] == pack_id
        assert manifest["method_version"] == (
            "1.1.0" if pack_id in {"research-prep", "global-opinion"} else "1.0.0"
        )
        for filename in CORE_FILES:
            assert (
                files["scripts/rwb_pack_core/" + filename]
                == (Path(packs.__path__[0]) / filename).read_bytes()
            )
        assert set(draft["reviewed_scripts"]) == {
            hashlib.sha256(raw).hexdigest() for path, raw in files.items() if path.endswith(".py")
        }
        assert len(manifest["closure_sha256"]) == 64


def test_nested_python_packages_publish_only_with_resolvable_imports(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    draft = catalog.detail("company-research")["draft"]
    draft["files"] = [
        encode_file("scripts/local/__init__.py", b"from .helper import value\n"),
        encode_file("scripts/local/helper.py", b"value = 1\n"),
        encode_file("scripts/calculate.py", b"from local import helper\n"),
    ]
    draft["reviewed_scripts"] = [file["sha256"] for file in draft["files"]]
    assert catalog.validate("skill", draft)["valid"]
    draft["files"][0] = encode_file("scripts/local/__init__.py", b"from ..escape import value\n")
    draft["reviewed_scripts"] = [file["sha256"] for file in draft["files"]]
    checks = catalog.validate("skill", draft)
    assert not checks["valid"]
    assert any(issue["code"] == "script_import_unresolved" for issue in checks["issues"])


def test_pack_manifest_tampering_is_rejected_and_old_gates_stay_disabled(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    assert all(catalog.row(cid)["status"] == "disabled" for cid in RECEIPT_GATED_SKILLS)
    draft = copy.deepcopy(catalog.row("research-pack-research-prep")["draft"])
    assert catalog.validate("skill", draft)["valid"]
    target = next(i for i, file in enumerate(draft["files"]) if file["path"].endswith("atoms.py"))
    draft["files"][target] = encode_file(draft["files"][target]["path"], b"# changed\n")
    draft["reviewed_scripts"] = [file["sha256"] for file in draft["files"]]
    assert any(
        issue["code"] == "pack_closure_invalid"
        for issue in catalog.validate("skill", draft)["issues"]
    )


@pytest.mark.parametrize("name", ["scripts/a/../../../x.py", "scripts/a/setup.py"])
def test_nested_resource_paths_cannot_escape_or_install(name):
    with pytest.raises(CapabilityError):
        encode_file(name, b"pass\n")


def test_user_copy_review_and_versions_survive_builtin_reinitialization(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    source = "research-pack-research-prep"
    copied = catalog.copy(source, "用户调研核验", "user-pack-check")
    cid = copied["id"]
    assert catalog.row(cid)["draft"]["reviewed_scripts"] == []
    assert not catalog.check(cid)["valid"]
    draft = copy.deepcopy(catalog.row(cid)["draft"])
    draft["reviewed_scripts"] = [
        item["sha256"] for item in draft["files"] if item["path"].endswith(".py")
    ]
    catalog.edit(cid, draft)
    catalog.publish(cid)
    first = copy.deepcopy(catalog.row(cid)["versions"]["1"])
    draft["instructions"] += "\n用户自己的展示说明。\n"
    catalog.edit(cid, draft)
    catalog.publish(cid)
    before = copy.deepcopy(catalog.row(cid))
    restored = CapabilityCatalog(tmp_path)
    assert restored.row(cid) == before
    assert restored.row(cid)["versions"]["1"] == first
    assert restored.row(cid)["origin"] == {"capability_id": source, "version": 1}


@pytest.mark.parametrize(
    "code",
    [b"import requests\n", b"from core.settings import settings\n", b"__import__('pathlib')\n"],
)
def test_pack_cannot_hide_nonapproved_imports_in_a_rehashed_manifest(tmp_path, code):
    from app.research_web.capabilities.pack_resources import MANIFEST_PATH, canonical, closure

    catalog = CapabilityCatalog(tmp_path)
    draft = copy.deepcopy(catalog.row("research-pack-research-prep")["draft"])
    draft["files"] = [
        encode_file(item["path"], code) if item["path"] == "scripts/calculate.py" else item
        for item in draft["files"]
    ]
    manifest = json.loads(
        decode_file(next(f for f in draft["files"] if f["path"] == MANIFEST_PATH))
    )
    manifest["files"] = [
        {"path": f["path"], "sha256": f["sha256"]}
        for f in sorted(draft["files"], key=lambda item: item["path"])
        if f["path"] != MANIFEST_PATH
    ]
    manifest["closure_sha256"] = closure(draft["files"])
    draft["files"] = [
        encode_file(MANIFEST_PATH, canonical(manifest)) if item["path"] == MANIFEST_PATH else item
        for item in draft["files"]
    ]
    draft["reviewed_scripts"] = [f["sha256"] for f in draft["files"] if f["path"].endswith(".py")]
    checked = catalog.validate("skill", draft)
    assert not checked["valid"]
    assert any(
        item["code"]
        in {"pack_import_forbidden", "script_import_unresolved", "pack_dynamic_import_forbidden"}
        for item in checked["issues"]
    )


def test_frozen_logging_adapter_keeps_structured_values_and_exceptions(caplog):
    from app.research_web.capabilities.pack_logging import get_logger

    logger = get_logger("research_pack_test").bind(component="native")
    with caplog.at_level(logging.INFO):
        logger.info("rows=%d", 256, percentage="20%", state="partial")
        try:
            raise ValueError("synthetic-only")
        except ValueError:
            logger.exception("rejected", error_type="ValueError")
    assert "rows=256" in caplog.text and "percentage='20%'" in caplog.text
    assert "component='native'" in caplog.text and "ValueError: synthetic-only" in caplog.text
