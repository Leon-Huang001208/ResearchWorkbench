"""Safe implementation boundaries shared by Native, Docker and fallback Doctor.

An available implementation is not native acceptance. Verification evidence
belongs to the platform matrix, never to this operating-system projection.
This module deliberately depends only on the standard library.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

log = logging.getLogger(__name__)


def documentation_reader_available(*, platform_name: str | None = None) -> bool:
    """Require the existing no-follow directory-relative reader primitives."""
    platform = sys.platform if platform_name is None else platform_name
    return (
        platform in {"darwin", "linux"}
        and all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"))
        and os.open in os.supports_dir_fd
    )


def _capability(status: str, reason: str, *, required: bool = False) -> dict[str, Any]:
    return {"status": status, "reason_code": reason, "required": required, "validated": False}


def platform_capabilities(
    runtime_mode: str, *, platform_name: str | None = None
) -> dict[str, dict[str, Any]]:
    """Return fresh, path-free facts without probing services or credentials."""
    if runtime_mode not in {"native", "docker"}:
        log.warning("platform_capabilities_invalid_runtime_mode")
        raise ValueError("invalid runtime mode")
    platform = sys.platform if platform_name is None else platform_name
    model_store_available = runtime_mode == "native" and platform == "darwin"
    sandbox_available = runtime_mode == "native" and platform == "darwin"
    document_available = runtime_mode == "docker" or documentation_reader_available(
        platform_name=platform
    )
    capabilities = {
        "model_system_storage": _capability(
            "available" if model_store_available else "unsupported",
            (
                "macos_model_keychain_implementation"
                if model_store_available
                else "model_credential_backend_unavailable"
            ),
        ),
        "model_private_file_storage": _capability(
            "available" if runtime_mode == "docker" else "unsupported",
            (
                "docker_model_private_file_implementation"
                if runtime_mode == "docker"
                else "model_private_file_not_selected"
            ),
        ),
        "research_script_sandbox": _capability(
            "available" if sandbox_available else "unsupported",
            "macos_sandbox_implementation" if sandbox_available else "research_sandbox_unsupported",
        ),
        "architecture_documentation": _capability(
            "available" if document_available else "unsupported",
            (
                "posix_nofollow_reader_implementation"
                if document_available
                else "documentation_platform_unsupported"
            ),
        ),
    }
    if runtime_mode == "docker":
        capabilities["docker_credential_acl"] = _capability(
            "not_verified" if platform == "win32" else "available",
            (
                "docker_credentials_acl_unverified"
                if platform == "win32"
                else "posix_private_mount_implementation"
            ),
            required=True,
        )
        for name in ("office", "wind", "tabbit"):
            capabilities[name] = {
                **_capability("unavailable_in_docker", "host_integration_unavailable_in_docker"),
                "support_status": "unsupported",
            }
    log.debug("platform_capabilities_projected", extra={"runtime_mode": runtime_mode})
    return capabilities
