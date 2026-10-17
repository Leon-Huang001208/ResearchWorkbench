"""Lazy CLI for explicit, independently authorized AI news lifecycle operations."""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from .ai_news_manager import AiNewsManager
from .ai_news_transport import AiNewsError

log = logging.getLogger(__name__)


def run_ai_news(argv, project: Path, home: Path, credentials=None) -> int:
    parser = argparse.ArgumentParser(prog="rwb ai-news")
    parser.add_argument(
        "action", choices=("status", "doctor", "setup", "start", "stop", "backup", "restore")
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--data-home", type=Path)
    parser.add_argument("--file", type=Path)
    args = parser.parse_args(argv)
    manager = AiNewsManager(project, args.data_home or home, credentials)
    try:
        if args.action in {"setup", "restore"}:
            if args.action == "restore" and args.file is None:
                raise AiNewsError("ai_news_backup_path_required")
            result = (
                manager.setup(authorized=args.authorized)
                if args.action == "setup"
                else manager.restore(args.file, authorized=args.authorized)
            )
        elif args.action == "backup":
            if args.file is None:
                raise AiNewsError("ai_news_backup_path_required")
            result = manager.backup(args.file)
        else:
            result = getattr(manager, args.action)()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("state") != "invalid" else 1
    except AiNewsError as error:
        code = str(error)
        if not re.fullmatch(r"ai_news_[a-z0-9_]{1,100}", code):
            code = "ai_news_operation_failed"
        log.error("ai_news_cli_failed code=%s", code)
        print(json.dumps({"ok": False, "code": code}))
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        log.error("ai_news_cli_failed")
        print(json.dumps({"ok": False, "code": "ai_news_operation_failed"}))
        return 1
