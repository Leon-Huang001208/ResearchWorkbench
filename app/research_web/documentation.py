"""Serve only reviewed architecture HTML names, never a repository file browser."""

import os
import stat
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from core.observability import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/research")
ARTIFACT_ROOT = Path(__file__).absolute().parents[2] / "outputs" / "research-web-architecture"
DOCUMENT_NAMES = frozenset(
    f"{name}.html"
    for name in (
        "index",
        "01-deployment",
        "02-module-dependencies",
        "03-research-sequence",
        "04-data-file-flow",
        "05-capability-flow",
        "06-run-state",
        "07-delivery-state",
        "08-iteration-docs",
    )
)
DOCUMENT_CSP = (
    "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src data:; connect-src 'none'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
MAX_HTML_BYTES = 4 * 1024 * 1024


def read_document(name: str) -> bytes:
    """Open every directory and the final file without following links (POSIX only)."""
    if name not in DOCUMENT_NAMES:
        raise ValueError("unknown documentation name")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(ARTIFACT_ROOT.anchor, flags)
    try:
        for component in ARTIFACT_ROOT.parts[1:]:
            next_directory = os.open(component, flags, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_size > MAX_HTML_BYTES
            ):
                raise ValueError("invalid documentation artifact")
            content = stream.read(MAX_HTML_BYTES + 1)
            if len(content) > MAX_HTML_BYTES:
                raise ValueError("documentation artifact too large")
            return content
    finally:
        os.close(directory)


@router.get("/documentation/{name}")
def architecture_document(name: str):
    try:
        content = read_document(name)
    except (OSError, ValueError, AttributeError) as exc:
        log.warning("research_documentation_unavailable", error_type=type(exc).__name__)
        return JSONResponse(
            {
                "error": {
                    "code": "documentation_unavailable",
                    "message": "架构文档不可用或路径不受支持",
                }
            },
            status_code=404,
        )
    log.info("research_documentation_read", document=name, bytes=len(content))
    return Response(
        content, media_type="text/html", headers={"Content-Security-Policy": DOCUMENT_CSP}
    )
