#!/usr/bin/env python3
"""Start a command in a detached session and write its PID.

This small helper keeps services launched by scripts/start_all.sh from being
terminated when the parent shell exits in desktop automation environments.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a detached command")
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--pid-file", required=True)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--stderr", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("command is required")
    return args


def child_main(args: argparse.Namespace) -> None:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    Path(args.pid_file).parent.mkdir(parents=True, exist_ok=True)
    Path(args.stdout).parent.mkdir(parents=True, exist_ok=True)
    Path(args.stderr).parent.mkdir(parents=True, exist_ok=True)

    with open(os.devnull, "rb", buffering=0) as stdin, open(
        args.stdout, "ab", buffering=0
    ) as stdout, open(args.stderr, "ab", buffering=0) as stderr:
        try:
            proc = subprocess.Popen(
                args.command,
                cwd=args.cwd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                close_fds=True,
            )
            Path(args.pid_file).write_text(f"{proc.pid}\n", encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive process launcher
            message = f"daemonize failed to launch {args.command!r}: {exc}\n"
            stderr.write(message.encode("utf-8", errors="replace"))
            os._exit(1)

    os._exit(0)


def main() -> int:
    args = parse_args()
    try:
        pid = os.fork()
    except OSError as exc:
        print(f"daemonize fork failed: {exc}", file=sys.stderr)
        return 1

    if pid:
        return 0

    os.setsid()
    child_main(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
