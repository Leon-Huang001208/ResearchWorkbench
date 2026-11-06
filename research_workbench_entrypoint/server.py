"""Lazy, bounded handoff to the optional private multiuser Native entrypoint."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from .knowledge_configuration import knowledge_origin

log = logging.getLogger(__name__)


def dispatch(argv: list[str], project: Path) -> int:
    """Keep help/Doctor stdlib-only; use only the installed Web Python to serve."""
    from .bootstrap import native_environment, native_python

    python = native_python(project)
    # Help and read-only diagnostics must work even before Web installation.
    diagnostic = not argv or any(value in argv for value in ("--help", "-h", "doctor"))
    if not python.is_file():
        if not diagnostic:
            log.error("multiuser_cli_unavailable code=web_environment_missing")
            sys.stderr.write("请先执行 ./setup-web.sh --no-start 安装现有 Web 环境。\n")
            return 1
        python = Path(sys.executable)
    environment = native_environment(project, minimal=True)
    environment["RESEARCH_RUN_MODE"] = "web-prod"
    mcp_switch = os.environ.get("RWB_MCP_READONLY_ENABLED")
    if mcp_switch in {"0", "1"}:
        environment["RWB_MCP_READONLY_ENABLED"] = mcp_switch
    elif mcp_switch is not None:
        log.warning("multiuser_mcp_switch_invalid")
    try:
        origin = knowledge_origin()
        if origin:
            environment["RESEARCH_WEKNORA_ORIGIN"] = origin
    except ValueError:
        # Optional integration fails closed without echoing userinfo/query secrets.
        log.warning("multiuser_knowledge_origin_not_forwarded")
    try:
        result = subprocess.run(
            [str(python), "-m", "app.research_web.multiuser", *argv],
            cwd=project,
            env=environment,
            check=False,
        )
        return result.returncode
    except (OSError, KeyboardInterrupt) as exc:
        log.error("multiuser_cli_failed error_type=%s", type(exc).__name__)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
