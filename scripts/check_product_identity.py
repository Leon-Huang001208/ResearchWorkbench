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
LEGACY_PRODUCT_DIR = ".alpha" + "foundry"
LEGACY_DATA_TOKENS = (
    f"{LEGACY_PRODUCT_DIR}/research-web",
    f'"{LEGACY_PRODUCT_DIR}" / "research-web"',
)
LEGACY_ALLOWLIST = {"app/cli/main.py"}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [item.decode() for item in result.stdout.split(b"\0") if item]


def check_identity() -> list[str]:
    findings: list[str] = []
    for relative in tracked_files():
        if RETIRED.search(relative):
            findings.append(f"retired path: {relative}")
            continue
        path = PROJECT_ROOT / relative
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
