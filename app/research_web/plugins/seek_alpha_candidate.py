"""Reproducible first-party candidate archive; never invent a Registry identity."""

import io
import zipfile
from pathlib import Path

from core.observability import get_logger

from .packages import PluginError, parse_archive

log = get_logger(__name__)
FILES = ("plugin.json", ".mcp.json", "README.md")


def candidate_archive():
    folder = Path(__file__).parent / "candidates" / "seek-alpha"
    stream = io.BytesIO()
    try:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in FILES:
                path = folder / name
                if path.is_symlink() or not path.is_file():
                    raise PluginError("plugin_candidate_artifact_unavailable", 503)
                content = path.read_bytes()
                if len(content) > 65536:
                    raise PluginError("plugin_candidate_artifact_invalid", 503)
                info = zipfile.ZipInfo(name, date_time=(2026, 10, 23, 0, 0, 0))
                info.external_attr = 0o100400 << 16
                archive.writestr(info, content)
        raw = stream.getvalue()
        parse_archive(raw)
        return raw
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        log.warning("plugin_candidate_archive_failed", error_type=type(exc).__name__)
        raise PluginError("plugin_candidate_artifact_unavailable", 503) from exc
