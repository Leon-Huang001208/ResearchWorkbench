"""Build immutable Native resources from the single reviewed calculator source.

No provider or model is invoked. Logging is an explicit frozen stdlib adapter;
schema validation uses the already configured research interpreter dependency.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.observability import get_logger

from ..scenarios.packs.contracts import method_version
from ..scenarios.packs.record_contracts import RECORD_SCHEMAS
from .models import CapabilityError
from .pack_dependencies import runtime_identity
from .pack_result_contracts import contracts as output_contracts
from .packages import decode_file, encode_file

log = get_logger(__name__)
CORE_FILES = (
    "__init__.py",
    "atoms.py",
    "bundles.py",
    "contracts.py",
    "limited.py",
    "record_contracts.py",
    "format_profile.py",
)
PACK_NAMES = {
    "position-risk": "持仓排雷",
    "expectation-gap": "预期差",
    "short-sentiment": "短线情绪",
    "research-prep": "调研前置",
    "event-review": "事件复盘",
    "global-opinion": "海内外舆情",
    "valuation-check": "估值体检",
    "ownership-structure": "筹码结构",
    "earnings-preview": "财报季前瞻",
}
MANIFEST_PATH = "references/pack-code-manifest.json"


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def closure(files):
    return hashlib.sha256(
        canonical(
            [
                {"path": file["path"], "sha256": file["sha256"]}
                for file in sorted(files, key=lambda item: item["path"])
                if file["path"] != MANIFEST_PATH
            ]
        )
    ).hexdigest()


def verify_pack_manifest(files):
    """Check the entire resource set, including helper/schema/golden digests."""
    found = [file for file in files if file["path"] == MANIFEST_PATH]
    if not found:
        return None
    try:
        manifest = json.loads(decode_file(found[0]))
        entries = [
            {"path": f["path"], "sha256": hashlib.sha256(decode_file(f)).hexdigest()}
            for f in files
            if f["path"] != MANIFEST_PATH
        ]
        expected = sorted(manifest["files"], key=lambda item: item["path"])
        if (
            len(found) != 1
            or len({f["path"] for f in files}) != len(files)
            or sorted(entries, key=lambda item: item["path"]) != expected
            or any(f["sha256"] != hashlib.sha256(decode_file(f)).hexdigest() for f in files)
            or manifest["closure_sha256"] != closure(files)
            or manifest["schema"]
            not in {"research_pack_code_manifest_v1", "research_pack_code_manifest_v2"}
            or manifest["pack_id"] not in PACK_NAMES
            or manifest["method_version"]
            != (
                "1.0.0"
                if manifest["schema"] == "research_pack_code_manifest_v1"
                else method_version("pack:" + manifest["pack_id"])
            )
            or {entry["path"] for entry in entries}
            != {
                *("scripts/rwb_pack_core/" + name for name in CORE_FILES),
                "scripts/core/__init__.py",
                "scripts/core/observability.py",
                "scripts/pack_native.py",
                "scripts/pack_import_policy.py",
                "scripts/calculate.py",
                "references/synthetic-vectors.json",
                "references/record-contracts.json",
                "references/runtime.json",
                (
                    "references/output-contracts-v1.json"
                    if manifest["schema"] == "research_pack_code_manifest_v1"
                    else "references/output-contracts-v2.json"
                ),
            }
        ):
            raise ValueError("closure mismatch")
        if manifest["schema"] == "research_pack_code_manifest_v2":
            expected_output = next(
                item for item in entries if item["path"] == "references/output-contracts-v2.json"
            )
            expected_records = next(
                item for item in entries if item["path"] == "references/record-contracts.json"
            )
            if manifest.get("output_contract") != expected_output or manifest.get(
                "record_contract"
            ) != {**expected_records, "version": 2}:
                raise ValueError("contract reference mismatch")
        return manifest
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("research_pack_closure_rejected")
        raise CapabilityError("组合包完整资源清单校验失败", "pack_closure_invalid") from exc


def pack_packages():
    root = Path(__file__).parents[1] / "scenarios" / "packs"
    try:
        core = [
            encode_file("scripts/rwb_pack_core/" + name, (root / name).read_bytes())
            for name in CORE_FILES
        ]
        shared = [
            encode_file(
                "scripts/core/__init__.py",
                b'"""Frozen Native logging namespace; never Host settings."""\n',
            ),
            encode_file(
                "scripts/core/observability.py",
                (Path(__file__).parent / "pack_logging.py").read_bytes(),
            ),
            encode_file(
                "scripts/pack_native.py", (Path(__file__).parent / "pack_native.py").read_bytes()
            ),
            encode_file(
                "scripts/pack_import_policy.py",
                (Path(__file__).parent / "pack_import_policy.py").read_bytes(),
            ),
            encode_file("references/runtime.json", canonical(runtime_identity())),
            encode_file("references/output-contracts-v2.json", canonical(output_contracts())),
            encode_file(
                "references/synthetic-vectors.json", (root / "synthetic_vectors.json").read_bytes()
            ),
            encode_file("references/record-contracts.json", canonical(RECORD_SCHEMAS)),
        ]
    except (OSError, ValueError) as exc:
        log.error("research_pack_resource_build_failed", error_type=type(exc).__name__)
        raise CapabilityError("组合包资源构建失败", "pack_resource_unavailable", 503) from exc
    for pack_id, title in PACK_NAMES.items():
        cid = "research-pack-" + pack_id
        entry = f'''"""Approved {pack_id} entry: only the fixed Host launcher calls execute."""
import logging
from pack_native import run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def execute(input_path, output_path, binding):
    if binding.get("pack_id") != {pack_id!r}:
        raise ValueError("pack_identity_mismatch")
    return run(input_path, output_path, binding)
'''
        files = [*core, *shared, encode_file("scripts/calculate.py", entry.encode())]
        manifest = {
            "schema": "research_pack_code_manifest_v2",
            "pack_id": pack_id,
            "method_version": method_version("pack:" + pack_id),
            "output_contract": next(
                {"path": f["path"], "sha256": f["sha256"]}
                for f in files
                if f["path"] == "references/output-contracts-v2.json"
            ),
            "record_contract": next(
                {"path": f["path"], "sha256": f["sha256"], "version": 2}
                for f in files
                if f["path"] == "references/record-contracts.json"
            ),
            "authority": "app/research_web/scenarios/packs",
            "core_files": list(CORE_FILES),
            "logging_adapter": "stdlib_logging_v1",
            "runtime_dependencies": ["jsonschema"],
            "files": [
                {"path": f["path"], "sha256": f["sha256"]}
                for f in sorted(files, key=lambda item: item["path"])
            ],
            "closure_sha256": closure(files),
        }
        files.append(encode_file(MANIFEST_PATH, canonical(manifest)))
        yield cid, {
            "kind": "skill",
            "metadata": {
                "slug": cid,
                "name": title + "（确定性核验）",
                "description": title + "的有界确定性核验；来源资格、实际执行和报告质量分别核验。",
                "category": "研究组合包",
                "inputs": [
                    {"name": "question", "label": "研究问题", "type": "text", "required": True}
                ],
                "scenarios": [title],
                "default_formats": [],
                "required_tools": ["research_run_script"],
                "dependencies": [],
                "data_requirements": [],
                "method_policy": {"required": [], "recommended": [], "excluded": []},
            },
            "instructions": f"---\nname: {cid}\ndescription: {title}的确定性核验\n---\n只通过 research_run_script 的 Host 封印组合包描述执行冻结脚本；不得自建输入、代码、路径或通过标记。原18算法权限与回执门保持。部分计算和文件保存不表示来源完整或研究通过。\n",
            "files": files,
            "steps": [],
            "reviewed_scripts": [f["sha256"] for f in files if f["path"].endswith(".py")],
        }
