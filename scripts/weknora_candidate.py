"""Read-only WeKnora candidate, explicit inventory and frozen-benchmark checks.

This module never contacts Docker, WeKnora or a model, and never changes files.
Its receipts validate supplied evidence; they are not deployment authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import stat
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

log = logging.getLogger(__name__)
RELEASE = "v0.9.0"
SOURCE_REVISION = "f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7"
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
REVISION = re.compile(r"[a-f0-9]{40}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9:._-]{0,159}\Z")
IMAGE = re.compile(r"[a-z0-9][a-z0-9./:_-]*@sha256:([a-f0-9]{64})\Z")
COMPONENTS = frozenset({"app", "frontend", "docreader", "paradedb", "redis"})
PRODUCT_COMPONENTS = frozenset({"app", "frontend", "docreader"})
DISK_FIELDS = ("originals", "database", "index", "parsing", "recovery", "reserve")
FORBIDDEN_PARTS = frozenset({"snapshots", "templates", "workbooks", "outputs"})
MAX_JSON_BYTES = 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_INVENTORY_BYTES = 512 * 1024 * 1024


class CandidateError(ValueError):
    """Only a stable code is exposed; inputs may contain private references."""


def _reject(code: str) -> NoReturn:
    log.warning("weknora_candidate_rejected code=%s", code)
    raise CandidateError(code)


def _object(value: Any, code: str) -> dict:
    if not isinstance(value, dict):
        _reject(code)
    return value


def _integer(value: Any, code: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > 2**63 - 1:
        _reject(code)
    return value


def _id(value: Any, code: str) -> str:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        _reject(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        _reject(code)
    return value


def canonical_sha256(value: Any) -> str:
    """Bind a complete JSON contract without relying on whitespace or key order."""
    try:
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        _reject("json_contract_invalid")
    return hashlib.sha256(raw).hexdigest()


def _schema(value: Any) -> dict:
    row = _object(value, "manifest_invalid")
    if type(row.get("schema_version")) is not int or row["schema_version"] != 1:
        _reject("schema_version_invalid")
    return row


def capacity_plan(
    manifest: dict, *, available_disk_bytes: int, available_memory_bytes: int
) -> dict:
    """Check explicit peak estimates and declared immutable artifact evidence.

    Image/source evidence is an operator-supplied reference, not verified here
    against a registry. A sufficient estimate still requires runtime acceptance.
    """
    row = _schema(manifest)
    available_disk_bytes = _integer(available_disk_bytes, "available_disk_invalid")
    available_memory_bytes = _integer(available_memory_bytes, "available_memory_invalid")
    if row.get("release") != RELEASE or row.get("source_revision") != SOURCE_REVISION:
        _reject("release_binding_invalid")
    components = row.get("components")
    if not isinstance(components, list) or len(components) != len(COMPONENTS):
        _reject("components_invalid")
    seen = set()
    image_bytes = 0
    memory_bytes = 0
    for raw in components:
        component = _object(raw, "component_invalid")
        name = component.get("name")
        if not isinstance(name, str) or name not in COMPONENTS or name in seen:
            _reject("component_identity_invalid")
        seen.add(name)
        image = component.get("image")
        if not isinstance(image, str):
            _reject("image_binding_invalid")
        match = IMAGE.fullmatch(image)
        if match is None or ":latest" in image or component.get("platform") != "linux/arm64":
            _reject("image_binding_invalid")
        proof = _object(component.get("proof"), "image_proof_missing")
        revision = proof.get("source_revision")
        if (
            not isinstance(revision, str)
            or REVISION.fullmatch(revision) is None
            or (name in PRODUCT_COMPONENTS and revision != SOURCE_REVISION)
            or proof.get("image_digest") != match.group(1)
            or proof.get("platform") != "linux/arm64"
        ):
            _reject("image_proof_binding_invalid")
        _hash(proof.get("evidence_sha256"), "image_proof_hash_invalid")
        image_bytes += _integer(component.get("image_bytes"), "image_size_invalid", minimum=1)
        memory_bytes += _integer(
            component.get("peak_memory_bytes"), "component_memory_invalid", minimum=1
        )
    disk = _object(row.get("disk_bytes"), "disk_estimates_missing")
    if set(disk) != set(DISK_FIELDS):
        _reject("disk_estimates_invalid")
    estimates = {
        name: _integer(disk[name], "disk_estimate_invalid", minimum=1) for name in DISK_FIELDS
    }
    if estimates["recovery"] < sum(estimates[name] for name in ("originals", "database", "index")):
        _reject("recovery_estimate_insufficient")
    memory = _object(row.get("memory_bytes"), "memory_estimates_missing")
    if set(memory) != {"parsing_extra", "reserve"}:
        _reject("memory_estimates_invalid")
    memory_bytes += _integer(memory["parsing_extra"], "parsing_memory_invalid")
    memory_bytes += _integer(memory["reserve"], "memory_reserve_invalid", minimum=1)
    disk_bytes = image_bytes + sum(estimates.values())
    sufficient = disk_bytes <= available_disk_bytes and memory_bytes <= available_memory_bytes
    log.info("weknora_candidate_capacity_checked sufficient=%s", sufficient)
    return {
        "schema_version": 1,
        "status": "capacity_sufficient" if sufficient else "capacity_insufficient",
        "release": RELEASE,
        "source_revision": SOURCE_REVISION,
        "manifest_sha256": canonical_sha256(row),
        "required_disk_bytes": disk_bytes,
        "available_disk_bytes": available_disk_bytes,
        "required_memory_bytes": memory_bytes,
        "available_memory_bytes": available_memory_bytes,
        "disk_shortfall_bytes": max(0, disk_bytes - available_disk_bytes),
        "memory_shortfall_bytes": max(0, memory_bytes - available_memory_bytes),
        "artifact_evidence": "declared_not_runtime_verified",
        "deployment_authorized": False,
    }


def _file_identity(info: os.stat_result) -> tuple:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _directory(info: os.stat_result) -> None:
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        _reject("inventory_directory_unsafe")


@contextmanager
def _inventory_root(root: Path):
    if not root.is_absolute() or ".." in root.parts:
        _reject("inventory_root_invalid")
    # Reject symlinked ancestors as well as a symlinked final directory.
    for ancestor in (*reversed(root.parents), root):
        if stat.S_ISLNK(ancestor.lstat().st_mode):
            _reject("inventory_symlink")
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        _directory(before)
        yield descriptor
        if _file_identity(root.lstat()) != _file_identity(before):
            _reject("inventory_root_changed")
    finally:
        os.close(descriptor)


def _relative_path(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        _reject("inventory_path_invalid")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or str(path) != raw
        or any(part in {".", ".."} for part in raw.split("/"))
        or any(part.lower() in FORBIDDEN_PARTS for part in path.parts)
    ):
        _reject("inventory_path_invalid")
    return path.parts


def _hash_beneath(root_descriptor: int, parts: tuple[str, ...]) -> tuple[str, int]:
    with ExitStack() as stack:
        parent = root_descriptor
        directories = []
        for part in parts[:-1]:
            descriptor = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, descriptor)
            info = os.fstat(descriptor)
            _directory(info)
            directories.append((parent, part, _file_identity(info)))
            parent = descriptor
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        stack.callback(os.close, descriptor)
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or before.st_size > MAX_FILE_BYTES
        ):
            _reject("inventory_file_unsafe")
        digest = hashlib.sha256()
        size = 0
        while block := os.read(descriptor, 65536):
            size += len(block)
            if size > MAX_FILE_BYTES:
                _reject("inventory_file_too_large")
            digest.update(block)
        if (
            size != before.st_size
            or _file_identity(os.fstat(descriptor)) != _file_identity(before)
            or _file_identity(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False))
            != _file_identity(before)
        ):
            _reject("inventory_file_changed")
        for parent_fd, name, identity in directories:
            if _file_identity(os.stat(name, dir_fd=parent_fd, follow_symlinks=False)) != identity:
                _reject("inventory_directory_changed")
        return digest.hexdigest(), size


def inventory(root: Path, manifest: dict) -> dict:
    """Hash explicitly owned research documents without scanning or copying."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        _reject("inventory_platform_unsupported")
    row = _schema(manifest)
    owner = _id(row.get("owner_id"), "inventory_owner_missing")
    if owner.lower() in {"unknown", "unassigned", "none", "null"}:
        _reject("inventory_owner_missing")
    materials = row.get("materials")
    if not isinstance(materials, list) or not materials or len(materials) > 200:
        _reject("inventory_materials_invalid")
    seen_ids = set()
    seen_paths = set()
    entries = []
    total = 0
    try:
        with _inventory_root(Path(root)) as descriptor:
            for raw in materials:
                material = _object(raw, "inventory_material_invalid")
                source_id = _id(material.get("source_id"), "inventory_source_invalid")
                if material.get("owner_id") != owner or material.get("kind") != "research_material":
                    _reject("inventory_material_not_admitted")
                parts = _relative_path(material.get("relative_path"))
                if source_id in seen_ids or parts in seen_paths:
                    _reject("inventory_duplicate_material")
                seen_ids.add(source_id)
                seen_paths.add(parts)
                legacy_ref = material.get("legacy_ref")
                if not isinstance(legacy_ref, str) or not legacy_ref or len(legacy_ref) > 512:
                    _reject("inventory_legacy_ref_missing")
                sha256, size = _hash_beneath(descriptor, parts)
                expected = material.get("original_sha256")
                if expected is not None and _hash(expected, "inventory_hash_invalid") != sha256:
                    _reject("inventory_hash_mismatch")
                total += size
                if total > MAX_INVENTORY_BYTES:
                    _reject("inventory_total_too_large")
                entries.append(
                    {
                        "source_id": source_id,
                        "logical_id": canonical_sha256({"owner_id": owner, "source_id": source_id}),
                        "owner_id": owner,
                        "legacy_ref": legacy_ref,
                        "original_sha256": sha256,
                        "bytes": size,
                    }
                )
    except CandidateError:
        raise
    except (OSError, ValueError, TypeError):
        _reject("inventory_read_failed")
    log.info("weknora_candidate_inventory_checked count=%d", len(entries))
    return {
        "schema_version": 1,
        "status": "inventory_verified",
        "owner_id": owner,
        "manifest_sha256": canonical_sha256(row),
        "count": len(entries),
        "bytes": total,
        "items_sha256": canonical_sha256(entries),
        "items": entries,
        "migration_performed": False,
    }


def _citation_key(row: dict) -> tuple[str, str]:
    locator = row.get("locator")
    if not isinstance(locator, str) or not locator.strip() or len(locator) > 512:
        _reject("benchmark_locator_invalid")
    return locator, _hash(row.get("excerpt_sha256"), "benchmark_excerpt_hash_invalid")


def benchmark(gold: dict, actual: dict) -> dict:
    """Score supplied frozen artifacts, never create or infer golden answers.

    Every hit must resolve to a document hash and a locator/excerpt pair already
    present in the gold corpus. Producing trustworthy live artifacts remains the
    caller's responsibility; this arithmetic receipt is not live acceptance.
    """
    gold = _schema(gold)
    actual = _schema(actual)
    gold_sha256 = canonical_sha256(gold)
    if actual.get("gold_sha256") != gold_sha256:
        _reject("benchmark_gold_binding_invalid")
    raw_documents = gold.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents or len(raw_documents) > 200:
        _reject("benchmark_corpus_invalid")
    documents = {}
    for raw in raw_documents:
        document = _object(raw, "benchmark_document_invalid")
        identifier = _id(document.get("document_id"), "benchmark_document_id_invalid")
        if identifier in documents:
            _reject("benchmark_duplicate_document")
        sha256 = _hash(document.get("original_sha256"), "benchmark_original_hash_invalid")
        citations = document.get("citations")
        if not isinstance(citations, list) or not citations or len(citations) > 200:
            _reject("benchmark_citations_invalid")
        keys = {
            _citation_key(_object(citation, "benchmark_citation_invalid")) for citation in citations
        }
        if len(keys) != len(citations):
            _reject("benchmark_duplicate_citation")
        documents[identifier] = (sha256, keys)
    questions = gold.get("questions")
    responses = actual.get("questions")
    if (
        not isinstance(questions, list)
        or len(questions) != 20
        or not isinstance(responses, list)
        or len(responses) != 20
    ):
        _reject("benchmark_question_count_invalid")
    expected = {}
    for raw in questions:
        question = _object(raw, "benchmark_question_invalid")
        identifier = _id(question.get("question_id"), "benchmark_question_id_invalid")
        identifiers = question.get("expected_document_ids")
        if (
            identifier in expected
            or not isinstance(identifiers, list)
            or not identifiers
            or len(identifiers) > 8
            or any(not isinstance(value, str) or value not in documents for value in identifiers)
            or len(set(identifiers)) != len(identifiers)
        ):
            _reject("benchmark_expected_sources_invalid")
        expected[identifier] = set(identifiers)
    results = []
    seen = set()
    total_hits = 0
    verified_hits = 0
    scope_violations = 0
    for raw in responses:
        response = _object(raw, "benchmark_response_invalid")
        identifier = response.get("question_id")
        hits = response.get("hits")
        if (
            not isinstance(identifier, str)
            or identifier not in expected
            or identifier in seen
            or not isinstance(hits, list)
            or len(hits) > 8
        ):
            _reject("benchmark_response_scope_invalid")
        seen.add(identifier)
        hit_ids = []
        for raw_hit in hits:
            hit = _object(raw_hit, "benchmark_hit_invalid")
            document_id = _id(hit.get("document_id"), "benchmark_hit_document_invalid")
            original_sha256 = _hash(hit.get("original_sha256"), "benchmark_hit_hash_invalid")
            citation = _citation_key(hit)
            hit_ids.append(document_id)
            total_hits += 1
            if document_id not in documents:
                scope_violations += 1
            elif (
                documents[document_id][0] == original_sha256
                and citation in documents[document_id][1]
            ):
                verified_hits += 1
        results.append(
            {
                "question_id": identifier,
                "expected_document_ids": sorted(expected[identifier]),
                "actual_document_ids": hit_ids,
                "matched": bool(expected[identifier].intersection(hit_ids)),
            }
        )
    matched = sum(1 for result in results if result["matched"])
    citations_passed = total_hits > 0 and verified_hits == total_hits
    passed = matched >= 18 and citations_passed and scope_violations == 0
    log.info("weknora_candidate_benchmark_checked matched=%d passed=%s", matched, passed)
    return {
        "schema_version": 1,
        "status": "passed" if passed else "failed",
        "scope": "provided_frozen_artifacts",
        "live_acceptance": False,
        "gold_sha256": gold_sha256,
        "actual_sha256": canonical_sha256(actual),
        "questions": 20,
        "top_k": 8,
        "matched_questions": matched,
        "required_matched_questions": 18,
        "recall": matched / 20,
        "total_hits": total_hits,
        "verified_citations": verified_hits,
        "citation_coverage": verified_hits / total_hits if total_hits else 0,
        "scope_violations": scope_violations,
        "question_results": results,
        "question_results_sha256": canonical_sha256(results),
    }


def _read_json(path: Path) -> dict:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        _reject("input_platform_unsupported")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > MAX_JSON_BYTES
            ):
                _reject("input_file_unsafe")
            raw = stream.read(MAX_JSON_BYTES + 1)
            if _file_identity(os.fstat(stream.fileno())) != _file_identity(info) or _file_identity(
                path.lstat()
            ) != _file_identity(info):
                _reject("input_file_changed")
        if len(raw) > MAX_JSON_BYTES:
            _reject("input_file_too_large")
        return _object(json.loads(raw), "input_json_invalid")
    except CandidateError:
        raise
    except (OSError, ValueError, UnicodeError):
        _reject("input_read_failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capacity = commands.add_parser("capacity")
    capacity.add_argument("manifest", type=Path)
    capacity.add_argument("--available-disk-bytes", type=int, required=True)
    capacity.add_argument("--available-memory-bytes", type=int, required=True)
    materials = commands.add_parser("inventory")
    materials.add_argument("manifest", type=Path)
    materials.add_argument("--root", type=Path, required=True)
    evaluate = commands.add_parser("benchmark")
    evaluate.add_argument("gold", type=Path)
    evaluate.add_argument("actual", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "capacity":
            result = capacity_plan(
                _read_json(args.manifest),
                available_disk_bytes=args.available_disk_bytes,
                available_memory_bytes=args.available_memory_bytes,
            )
        elif args.command == "inventory":
            result = inventory(args.root, _read_json(args.manifest))
        else:
            result = benchmark(_read_json(args.gold), _read_json(args.actual))
        summary = {
            key: value for key, value in result.items() if key not in {"items", "question_results"}
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] not in {"failed", "capacity_insufficient"} else 1
    except CandidateError as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
