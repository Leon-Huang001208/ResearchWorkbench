"""Generation-scoped maintenance reader; frozen v1 evidence/controller stay unchanged.

Retains transport, total expansion, CRC, full-stream, UTF-8 and exact-tree gates.
Only explicit maintenance callers use the 20 MB job and 64 MiB business readers.
"""

from __future__ import annotations

import binascii
import io
import json
import logging
import os
import re
import stat
import struct
import zipfile
import zlib
from pathlib import Path

from . import evidence as legacy
from .evidence import SHA, WORKFLOWS, UpdateBlocked, run_archive

log = logging.getLogger(__name__)
JOB_LOG_LIMIT = 20_000_000


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
                if len(matches) != 1 or matches[0].file_size > JOB_LOG_LIMIT:
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
                    content = decoder.decompress(compressed, JOB_LOG_LIMIT + 1)
                    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                        raise ValueError("incomplete or trailing deflate stream")
                else:
                    raise ValueError("unsupported compression")
                if (
                    len(content) > JOB_LOG_LIMIT
                    or len(content) != entry.file_size
                    or binascii.crc32(content) != entry.CRC
                ):
                    raise ValueError("member length or CRC mismatch")
                body = content.decode("utf-8")
                if len(body) > JOB_LOG_LIMIT:
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


def _bounded_record(path: Path, limit: int, family: str) -> dict:
    try:
        if path.resolve() != path.absolute():
            raise ValueError("record_path_alias")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
                raise ValueError("record_shape_or_size")
            if getattr(info, "st_flags", 0) & getattr(stat, "SF_DATALESS", 0x40000000):
                raise UpdateBlocked(f"{family}_offline")
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("record_size")
        value = json.loads(raw.decode("utf8"))
        if not isinstance(value, dict):
            raise TypeError("record_object_required")
        return value
    except UpdateBlocked:
        raise
    except FileNotFoundError as exc:
        raise UpdateBlocked(f"{family}_missing") from exc
    except OSError as exc:
        raise UpdateBlocked(f"{family}_unreadable") from exc
    except (ValueError, TypeError) as exc:
        raise UpdateBlocked(f"{family}_invalid") from exc


def read_json(path: Path) -> dict:
    """Control metadata remains bounded at one MB; offline is a distinct state."""
    return _bounded_record(path, 1_000_000, "resident_record")


def read_business_index(path: Path) -> dict:
    """The established 64 MiB business budget never applies to control records."""
    return _bounded_record(path, 64 * 1024 * 1024, "resident_business_index")


class GitHubEvidence(legacy.GitHubEvidence):
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
