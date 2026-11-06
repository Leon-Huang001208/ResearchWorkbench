"""Verify the pinned WeKnora patch artifact offline, without running Go/services.

The sparse fixtures retain exact upstream hunk lines at their original positions;
blank lines replace unrelated source. Full-source pre/post hashes are build-time
admission inputs, not hashes of these sparse fixtures. Tencent's MIT notice for
these excerpts is retained in deploy/weknora/patches/manifest.json.
"""

import hashlib
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import pytest

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = ROOT / "deploy" / "weknora" / "patches"
RELEASE_SHA = "f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7"
FROZEN_SOURCES = {
    "internal/application/service/extract.go": {
        "line_count": 944,
        "regions": [
            (
                167,
                (
                    "\ttenantID uint64,\n"
                    "\tknowledgeID string,\n"
                    "\tfileName, fileType, summaryModelID, "
                    "embeddingModelID string,\n"
                    ") {\n"
                    "\tft := "
                    "normalizeFileExtension(fileType)\n"
                    '\tif ft == "" && fileName != "" {\n'
                    "\t\tft = getFileType(fileName)\n"
                    "\t}\n"
                    "\tif !isDataTableFileType(ft) {\n"
                    "\t\treturn\n"
                    "\t}\n"
                    "\tif err := NewDataTableSummaryTask(ctx, client, tenantID, knowledgeID, "
                    "summaryModelID, embeddingModelID); err != nil {\n"
                    '\t\tlogger.Warnf(ctx, "Failed to enqueue data table summary task for knowledge %s: %v", '
                    "knowledgeID, err)\n"
                    "\t}\n"
                    "}\n"
                ),
            )
        ],
    },
    "internal/application/service/knowledge_create.go": {
        "line_count": 1498,
        "regions": [
            (
                299,
                (
                    "\t\tknowledge.ID,\n"
                    "\t)\n"
                    "\n"
                    "\t"
                    "enqueueDataTableSummaryIfNeeded(ctx, "
                    "s.task, tenantID, "
                    "knowledge.ID, safeFilename, "
                    "getFileType(safeFilename), "
                    "kb.SummaryModelID, "
                    "kb.EmbeddingModelID)\n"
                    "\n"
                    '\tlogger.Infof(ctx, "Knowledge '
                    "from file created "
                    'successfully, ID: %s", '
                    "knowledge.ID)\n"
                    "\treturn knowledge, nil\n"
                ),
            ),
            (
                747,
                (
                    "\t\t})\n"
                    '\tlogger.Infof(ctx, "Enqueued '
                    "file URL process task: id=%s "
                    'queue=%s knowledge_id=%s", '
                    "info.ID, info.Queue, "
                    "knowledge.ID)\n"
                    "\n"
                    "\t"
                    "enqueueDataTableSummaryIfNeeded(ctx, "
                    "s.task, tenantID, "
                    "knowledge.ID, fileName, "
                    "fileType, kb.SummaryModelID, "
                    "kb.EmbeddingModelID)\n"
                    "\n"
                    '\tlogger.Infof(ctx, "Knowledge '
                    "from file URL created "
                    'successfully, ID: %s", '
                    "knowledge.ID)\n"
                    "\treturn knowledge, nil\n"
                ),
            ),
        ],
    },
    "internal/application/service/knowledge_process.go": {
        "line_count": 4890,
        "regions": [
            (
                3103,
                (
                    "\t\trecordReparseStarted()\n"
                    "\n"
                    "\t\t// For data tables (csv, "
                    "xlsx, xls), also enqueue "
                    "summary task\n"
                    "\t\t"
                    "enqueueDataTableSummaryIfNeeded(ctx, "
                    "s.task, tenantID, "
                    "existing.ID, "
                    "existing.FileName, "
                    "existing.FileType, "
                    "kb.SummaryModelID, "
                    "kb.EmbeddingModelID)\n"
                    "\n"
                    "\t\treturn existing, nil\n"
                    "\t}\n"
                ),
            ),
            (
                3156,
                (
                    "\t\tlogger.Infof(ctx, "
                    '"Enqueued file URL reparse '
                    "task: id=%s queue=%s "
                    'knowledge_id=%s", info.ID, '
                    "info.Queue, existing.ID)\n"
                    "\t\trecordReparseStarted()\n"
                    "\n"
                    "\t\t"
                    "enqueueDataTableSummaryIfNeeded(ctx, "
                    "s.task, tenantID, "
                    "existing.ID, "
                    "existing.FileName, "
                    "existing.FileType, "
                    "kb.SummaryModelID, "
                    "kb.EmbeddingModelID)\n"
                    "\n"
                    "\t\treturn existing, nil\n"
                    "\t}\n"
                ),
            ),
        ],
    },
}

FROZEN_SOURCES["internal/application/service/extract_data_table_summary_test.go"] = json.loads(
    '{"line_count":292,"regions":[[290,"\\t}\\n\\trequire.Equal(t, map[string]string{summary.ID: summary.Content, column.ID: column.Content}, indexedContent)\\n}\\n"]]}'
)


def _load_artifacts():
    manifest = json.loads((PATCH_DIR / "manifest.json").read_text(encoding="utf-8"))
    patch = (PATCH_DIR / manifest["patch"]["path"]).read_bytes()
    return manifest, patch


def _materialize_context(root):
    for relative, fixture in FROZEN_SOURCES.items():
        lines = ["\n"] * fixture["line_count"]
        for start, text in fixture["regions"]:
            excerpt = text.splitlines(keepends=True)
            lines[start - 1 : start - 1 + len(excerpt)] = excerpt
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(lines), encoding="utf-8")


def _apply_patch(root, patch, *, dry_run=False):
    executable = shutil.which("patch")
    if executable is None:
        pytest.fail("The existing system patch executable is required; do not install it here")
    command = [executable, "-p1", "--batch", "--fuzz=0"]
    if dry_run:
        command.append("--dry-run")
    try:
        result = subprocess.run(
            command, input=patch, cwd=root, capture_output=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOGGER.error("WeKnora patch verification failed: %s", type(exc).__name__)
        pytest.fail(f"Could not verify the pinned patch: {type(exc).__name__}")
    LOGGER.info("Verified WeKnora patch artifact process exit=%s", result.returncode)
    return result


def test_weknora_patch_manifest_binds_exact_release_and_artifacts():
    manifest, patch = _load_artifacts()
    assert manifest["schema_version"] == 1
    assert manifest["upstream"] == {
        "repository": "https://github.com/Tencent/WeKnora",
        "release_tag": "v0.9.0",
        "release_sha": RELEASE_SHA,
    }
    assert manifest["patch"]["path"] == "0001-respect-table-summary-opt-out.patch"
    assert hashlib.sha256(patch).hexdigest() == manifest["patch"]["sha256"]
    assert {entry["path"] for entry in manifest["files"]} == set(FROZEN_SOURCES)
    for entry in manifest["files"]:
        for field in ("preimage_sha256", "postimage_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", entry[field])
        assert entry["preimage_sha256"] != entry["postimage_sha256"]
        assert entry["upstream_url"] == (
            f"https://github.com/Tencent/WeKnora/blob/{RELEASE_SHA}/{entry['path']}"
        )
    assert manifest["license"]["spdx"] == "MIT"
    assert "Copyright (C) 2026 Tencent" in manifest["license"]["notice"]
    assert "THE SOFTWARE IS PROVIDED" in manifest["license"]["notice"]
    assert manifest["verification"]["go_runtime_tests"] == "NOT_RUN"
    assert manifest["verification"]["actual_service"] == "NOT_RUN"
    assert manifest["verification"]["instance_zero_generation_enforcement"] == "NOT_IMPLEMENTED"
    template = json.loads((PATCH_DIR.parent / "embedding-only.json").read_text(encoding="utf-8"))
    assert template["server_enforced_zero_generation_profile"] == "NOT_IMPLEMENTED"
    assert template["ui_upload_status"] == "BLOCKED_NO_SERVER_ENFORCED_ZERO_GENERATION_PROFILE"
    assert template["ui_reparse_status"] == "BLOCKED_NO_SERVER_ENFORCED_ZERO_GENERATION_PROFILE"


def test_weknora_patch_applies_to_exact_frozen_context_and_covers_all_call_sites(tmp_path):
    _, patch = _load_artifacts()
    _materialize_context(tmp_path)
    result = _apply_patch(tmp_path, patch)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    helper = (tmp_path / "internal/application/service/extract.go").read_text(encoding="utf-8")
    guard = (
        "if processOverrides != nil && processOverrides.SummaryEnabled != nil "
        "&& !*processOverrides.SummaryEnabled {"
    )
    assert guard in helper
    assert helper.index(guard) < helper.index("NewDataTableSummaryTask(")
    guard_body = helper.split(guard, 1)[1].split("\n\t}", 1)[0]
    assert "logger.Infof" in guard_body
    assert "\n\t\treturn" in guard_body
    go_test = (
        tmp_path / "internal/application/service/extract_data_table_summary_test.go"
    ).read_text(encoding="utf-8")
    assert "func TestEnqueueDataTableSummaryHonorsExplicitOptOut" in go_test
    assert "queue.tasks" in go_test
    for name in ("knowledge_create.go", "knowledge_process.go"):
        text = (tmp_path / "internal/application/service" / name).read_text(encoding="utf-8")
        calls = [line for line in text.splitlines() if "enqueueDataTableSummaryIfNeeded(" in line]
        assert len(calls) == 2
        assert all(line.endswith("kb.EmbeddingModelID, processOverrides)") for line in calls)


def test_weknora_patch_rejects_changed_upstream_hunk_context(tmp_path):
    _, patch = _load_artifacts()
    _materialize_context(tmp_path)
    helper = tmp_path / "internal/application/service/extract.go"
    text = helper.read_text(encoding="utf-8")
    old = "fileName, fileType, summaryModelID, embeddingModelID string,"
    assert text.count(old) == 1
    helper.write_text(text.replace(old, "changedUpstreamSignature string,"), encoding="utf-8")
    result = _apply_patch(tmp_path, patch, dry_run=True)
    assert result.returncode != 0
    assert "failed" in (result.stdout + result.stderr).decode("utf-8", errors="replace").casefold()
