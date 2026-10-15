"""Read-only exact-tree admission for completed managed GitHub deliveries."""

from __future__ import annotations

import json
import logging
import re
import subprocess
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
            return json.loads(run([str(self.gh), "api", f"repos/{self.repository}/{endpoint}"]))
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
                checkout_shas = set()
                for job in checks:
                    raw = run(
                        [
                            str(self.gh),
                            "api",
                            f"repos/{self.repository}/actions/jobs/{job['id']}/logs",
                        ]
                    )
                    lines = raw.splitlines()
                    for index, line in enumerate(lines[:-1]):
                        if "git log -1 --format=%H" in line:
                            match = re.search(r"\b([a-f0-9]{40})\s*$", lines[index + 1])
                            if match:
                                checkout_shas.add(match[1])
                if len(checkout_shas) != 1:
                    raise UpdateBlocked("resident_ci_checkout_unverified")
                checkout = checkout_shas.pop()
                if self.api(f"git/commits/{checkout}")["tree"]["sha"] != expected_tree:
                    raise UpdateBlocked("resident_ci_tree_mismatch")
                evidence.append({"workflow": workflow, "run": latest["id"], "checkout": checkout})
            log.info("resident_candidate_verified", extra={"sha": target})
            return {"sha": target, "head": head, "pull_request": pr_number, "ci": evidence}
        raise UpdateBlocked("resident_reviewed_delivery_missing")
