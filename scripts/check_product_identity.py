#!/usr/bin/env python3
"""Fail when the current tracked product leaks retired names or command prefixes."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RETIRED = re.compile(
    "Alpha" + r"Foundry|alpha" + r"foundry|alpha" + r"-foundry|io\.alpha" + r"foundry|"
    r"\baf(?:_|-|\s+(?:web|data|ingest|ask|report|crawl|knowledge))",
)
GIT_RETIRED = (
    "Alpha" + r"Foundry|alpha" + r"foundry|alpha" + r"-foundry|io\.alpha" + r"foundry|"
    r"(^|[^[:alnum:]_])af(_|-|[[:space:]]+(web|data|ingest|ask|report|crawl|knowledge))"
)
LEGACY_PRODUCT_DIR = ".alpha" + "foundry"
LEGACY_DATA_TOKENS = (
    f"{LEGACY_PRODUCT_DIR}/research-web",
    f'"{LEGACY_PRODUCT_DIR}" / "research-web"',
)
LEGACY_ALLOWLIST = {"app/cli/main.py"}
OFFLINE_FILE_FLAG = 0x40000000


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [item.decode() for item in result.stdout.split(b"\0") if item]


def committed_findings() -> dict[str, list[tuple[int, str]]]:
    result = subprocess.run(
        ["git", "grep", "-n", "-I", "-E", GIT_RETIRED, "HEAD", "--", "."],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout)
    findings: dict[str, list[tuple[int, str]]] = {}
    for match in result.stdout.splitlines():
        parts = match.split(":", maxsplit=3)
        if len(parts) != 4:
            continue
        try:
            line_number = int(parts[2])
        except ValueError:
            continue
        findings.setdefault(parts[1], []).append((line_number, parts[3]))
    return findings


def check_identity() -> list[str]:
    findings: list[str] = []
    tracked = tracked_files()
    committed = committed_findings()
    for relative in tracked:
        if RETIRED.search(relative):
            findings.append(f"retired path: {relative}")
            continue
        path = PROJECT_ROOT / relative
        try:
            is_offline = bool(path.stat().st_flags & OFFLINE_FILE_FLAG)
        except OSError:
            is_offline = True
        if is_offline:
            for line_number, line in committed.get(relative, []):
                if relative in LEGACY_ALLOWLIST and any(
                    token in line for token in LEGACY_DATA_TOKENS
                ):
                    continue
                findings.append(f"{relative}:{line_number}: retired product identity")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if relative in LEGACY_ALLOWLIST:
            for token in LEGACY_DATA_TOKENS:
                content = content.replace(token, "legacy-data-root")
        for line_number, line in enumerate(content.splitlines(), start=1):
            if RETIRED.search(line):
                findings.append(f"{relative}:{line_number}: retired product identity")
    return findings


def main() -> int:
    try:
        findings = check_identity()
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"identity check failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Research Workbench identity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
