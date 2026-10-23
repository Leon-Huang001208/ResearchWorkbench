"""Read-only exact-tree admission for completed managed GitHub deliveries."""

from __future__ import annotations

import binascii
import io
import json
import logging
import re
import stat
import struct
import subprocess
import zipfile
import zlib
from pathlib import Path

log = logging.getLogger(__name__)
SHA = re.compile(r"[a-f0-9]{40}\Z")
WORKFLOWS = (
    "project-constraints.yml",
    "research-web-checks.yml",
    "research-web-bootstrap.yml",
)
# Explicit automatic compatibility envelope. Unknown paths require a new
# reviewed controller/installation baseline, rather than guessing migration safety.
SAFE_PREFIXES = (
    "app/research_web/ui/",
    "app/web/",
    "tests/",
    "docs/",
    ".ai/reports/",
)
SAFE_FILES = frozenset(
    {
        "README.md",
        "app/research_web/main.py",
        "app/research_web/projection.py",
        "app/research_web/documentation.py",
        "app/research_web/delivery.py",
        "app/research_web/research_evidence.py",
    }
)


class UpdateBlocked(RuntimeError):
    """A stable diagnostic code without command output or credentials."""


def run(argv: list[str], *, cwd: Path | None = None, timeout: int = 30) -> str:
    try:
        completed = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateBlocked("resident_command_unavailable") from exc
    if completed.returncode or len(completed.stdout) > 8_000_000:
        raise UpdateBlocked("resident_command_failed")
    return completed.stdout.strip()


def run_archive(argv: list[str]) -> bytes:
    """Fetch fresh GitHub bytes without the gh display scanner or disk cache."""
    try:
        completed = subprocess.run(argv, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateBlocked("resident_command_unavailable") from exc
    if completed.returncode or len(completed.stdout) > 8_000_000:
        raise UpdateBlocked("resident_command_failed")
    return completed.stdout


def archive_job_logs(raw: bytes, jobs: list[dict]) -> dict[int, str]:
    """Read complete unique job logs; malformed or partial archives fail closed."""
    names = [job.get("name") for job in jobs]
    if any(
        not isinstance(name, str) or not name or "/" in name or "\\" in name for name in names
    ) or len(set(names)) != len(names):
        raise UpdateBlocked("resident_ci_archive_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            filenames = [entry.filename for entry in entries]
            if len(entries) > 2000 or len(set(filenames)) != len(filenames):
                raise ValueError("ambiguous archive")
            if sum(entry.file_size for entry in entries) > 64_000_000:
                raise ValueError("archive budget")
            for entry in entries:
                if (
                    stat.S_IFMT(entry.external_attr >> 16) not in {0, stat.S_IFREG, stat.S_IFDIR}
                    or (
                        stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFDIR
                        and not entry.is_dir()
                    )
                    or entry.flag_bits & 1
                    or "\\" in entry.filename
                    or entry.filename.startswith("/")
                    or ".." in entry.filename.split("/")
                ):
                    raise ValueError("unsafe archive member")
            result = {}
            for job in jobs:
                pattern = re.compile(r"[0-9]+_" + re.escape(job["name"]) + r"\.txt\Z")
                matches = [entry for entry in entries if pattern.fullmatch(entry.filename)]
                if len(matches) != 1 or matches[0].file_size > 8_000_000:
                    raise ValueError("job log missing or oversized")
                entry = matches[0]
                # Validate the local header/name and overlapping-member boundary.
                with archive.open(entry):
                    pass
                header = struct.unpack_from("<4s5H3I2H", raw, entry.header_offset)
                offset = entry.header_offset + 30 + header[9] + header[10]
                compressed = raw[offset : offset + entry.compress_size]
                if (
                    header[0] != b"PK\x03\x04"
                    or header[3] != entry.compress_type
                    or len(compressed) != entry.compress_size
                ):
                    raise ValueError("member header mismatch")
                if entry.compress_type == zipfile.ZIP_STORED:
                    content = compressed
                elif entry.compress_type == zipfile.ZIP_DEFLATED:
                    decoder = zlib.decompressobj(-15)
                    content = decoder.decompress(compressed, 8_000_001)
                    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                        raise ValueError("incomplete or trailing deflate stream")
                else:
                    raise ValueError("unsupported compression")
                if (
                    len(content) > 8_000_000
                    or len(content) != entry.file_size
                    or binascii.crc32(content) != entry.CRC
                ):
                    raise ValueError("member length or CRC mismatch")
                body = content.decode("utf-8")
                if len(body) > 8_000_000:
                    raise ValueError("log output budget")
                result[job["id"]] = body
            return result
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        zipfile.BadZipFile,
        EOFError,
        struct.error,
        zlib.error,
    ) as exc:
        log.warning("resident_ci_archive_rejected")
        raise UpdateBlocked("resident_ci_archive_invalid") from exc


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise UpdateBlocked("resident_record_invalid")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise UpdateBlocked("resident_record_invalid") from exc
    if not isinstance(value, dict):
        raise UpdateBlocked("resident_record_invalid")
    return value


def compatible(paths: list[str]) -> bool:
    return all(path in SAFE_FILES or path.startswith(SAFE_PREFIXES) for path in paths)


class GitHubEvidence:
    def __init__(self, gh: Path, repository: str, common: Path):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
            raise UpdateBlocked("resident_repository_invalid")
        self.gh, self.repository, self.common = gh, repository, common

    def api(self, endpoint: str):
        try:
            return json.loads(
                run(
                    [
                        str(self.gh),
                        "api",
                        f"repos/{self.repository}/{endpoint}",
                        "-H",
                        "Cache-Control: no-cache",
                    ]
                )
            )
        except ValueError as exc:
            raise UpdateBlocked("resident_github_response_invalid") from exc

    def latest(self) -> str:
        sha = self.api("commits/master").get("sha", "")
        if not SHA.fullmatch(sha):
            raise UpdateBlocked("resident_master_invalid")
        return sha

    def qualify(self, target: str) -> dict:
        if not SHA.fullmatch(target):
            raise UpdateBlocked("resident_candidate_invalid")
        records = self.common / "leon-engineering" / "deliveries"
        if not records.is_dir() or records.is_symlink():
            raise UpdateBlocked("resident_delivery_missing")
        candidates = sorted(records.glob("*.json"))
        if len(candidates) > 2000:
            raise UpdateBlocked("resident_delivery_scan_limit")
        for path in candidates:
            record = read_json(path)
            if record.get("remoteCommit") != target:
                continue
            if (
                record.get("status") not in {"ci_passed", "cleaned"}
                or record.get("mode") != "pr"
                or record.get("ci", {}).get("status") != "passed"
                or record.get("verification", {}).get("status") != "passed"
            ):
                continue
            head = record.get("integrationCommit", "")
            if not SHA.fullmatch(head):
                continue
            review = read_json(self.common / "leon-engineering/git-safety/reviews" / path.name)
            if review.get("reviewedCommit") != head or review.get("status") != "PASS":
                continue
            pr_number = record.get("pullRequest", {}).get("number")
            if type(pr_number) is not int:
                continue
            pr = self.api(f"pulls/{pr_number}")
            if (
                not pr.get("merged")
                or pr.get("merge_commit_sha") != target
                or pr.get("head", {}).get("sha") != head
                or pr.get("base", {}).get("ref") != "master"
            ):
                continue
            expected_tree = self.api(f"git/commits/{target}")["tree"]["sha"]
            evidence = []
            for workflow in WORKFLOWS:
                runs = self.api(f"actions/workflows/{workflow}/runs?head_sha={head}&per_page=10")
                runs = runs.get("workflow_runs", [])
                if not runs:
                    raise UpdateBlocked("resident_ci_missing")
                latest = max(runs, key=lambda item: item["id"])
                if latest.get("conclusion") != "success" or latest.get("status") != "completed":
                    raise UpdateBlocked("resident_ci_pending_or_failed")
                jobs = self.api(f"actions/runs/{latest['id']}/jobs?per_page=100")["jobs"]
                checks = [job for job in jobs if job.get("conclusion") == "success"]
                if not checks or (
                    workflow == WORKFLOWS[2]
                    and not any(
                        "macos" in label for job in checks for label in job.get("labels", [])
                    )
                ):
                    raise UpdateBlocked("resident_macos_ci_missing")
                raw_archive = run_archive(
                    [
                        str(self.gh),
                        "api",
                        f"repos/{self.repository}/actions/runs/{latest['id']}/logs",
                        "-H",
                        "Cache-Control: no-cache",
                    ]
                )
                logs = archive_job_logs(raw_archive, checks)
                checkout_shas = set()
                for job in checks:
                    job_checkouts = set()
                    raw = logs[job["id"]]
                    lines = raw.splitlines()
                    for index, line in enumerate(lines[:-1]):
                        if "git log -1 --format=%H" in line:
                            match = re.search(r"\b([a-f0-9]{40})\s*$", lines[index + 1])
                            if match:
                                job_checkouts.add(match[1])
                    if len(job_checkouts) != 1:
                        raise UpdateBlocked("resident_ci_checkout_unverified")
                    checkout_shas.update(job_checkouts)
                if len(checkout_shas) != 1:
                    raise UpdateBlocked("resident_ci_checkout_unverified")
                checkout = checkout_shas.pop()
                if self.api(f"git/commits/{checkout}")["tree"]["sha"] != expected_tree:
                    raise UpdateBlocked("resident_ci_tree_mismatch")
                evidence.append({"workflow": workflow, "run": latest["id"], "checkout": checkout})
            log.info("resident_candidate_verified", extra={"sha": target})
            return {"sha": target, "head": head, "pull_request": pr_number, "ci": evidence}
        raise UpdateBlocked("resident_reviewed_delivery_missing")
