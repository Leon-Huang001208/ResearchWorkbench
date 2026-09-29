"""Immutable process commands shared without taking lifecycle ownership.

This module only describes processes; managers own spawning, authentication,
logging under logs/, and error handling at their existing process boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class ProcessSpec:
    role: Literal["runtime", "web"]
    port: int
    command: tuple[str, ...]
    signature: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WebProcessSpecs:
    runtime: ProcessSpec
    web: ProcessSpec
    runtime_state_root: Path


def build_process_specs(
    *,
    python: str,
    node: str,
    project_root: Path,
    data_root: Path,
    runtime_source: Path,
    state_root: Path,
    web_host: str,
    web_port: int,
    runtime_port: int,
) -> WebProcessSpecs:
    """Describe the same DSH/Web contract for Native and container supervisors.

    Keep the historical Native command fingerprint by omitting the optional
    state argument when the launcher default already names the requested root.
    The DSH listener and its Host callback always remain on loopback.
    """
    runtime_command = (
        python,
        "-m",
        "app.research_web.launch_runtime",
        "--source",
        str(runtime_source),
        "--data",
        str(data_root),
        "--node",
        node,
        "--port",
        str(runtime_port),
        "--datahub-url",
        f"http://127.0.0.1:{web_port}",
        "--research-tools",
    )
    if state_root != data_root / "runtime":
        runtime_command += ("--state", str(state_root))
    return WebProcessSpecs(
        runtime=ProcessSpec(
            role="runtime",
            port=runtime_port,
            command=runtime_command,
            signature=(
                str(runtime_source / "apps/cli/lib/bin.js"),
                str(state_root / "overlay.yml"),
                str(runtime_port),
            ),
        ),
        web=ProcessSpec(
            role="web",
            port=web_port,
            command=(
                python,
                "-m",
                "uvicorn",
                "app.research_web.main:app",
                "--app-dir",
                str(project_root),
                "--host",
                web_host,
                "--port",
                str(web_port),
            ),
            signature=("app.research_web.main:app", str(project_root), str(web_port)),
        ),
        runtime_state_root=state_root,
    )
