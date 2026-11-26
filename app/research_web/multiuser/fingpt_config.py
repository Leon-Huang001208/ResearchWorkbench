"""Stdlib-only FinGPT configuration; help/Doctor never import model settings."""

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .origin import validate_origin


@dataclass(frozen=True)
class FinGPTConfig:
    origin: str
    client_secret: str
    cookie_isolated: bool = False

    def __post_init__(self):
        validate_origin(self.origin)
        if not isinstance(self.client_secret, str) or len(self.client_secret) < 32:
            raise ValueError("fingpt_client_secret_invalid")
        if type(self.cookie_isolated) is not bool:
            raise ValueError("fingpt_cookie_policy_invalid")

    @classmethod
    def configured(cls, root):
        path = Path(os.environ.get("RESEARCH_FINGPT_CONFIG", str(root / "fingpt.json")))
        try:
            before = path.lstat()
        except FileNotFoundError:
            return None
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > 16384
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != os.getuid()
        ):
            raise ValueError("fingpt_configuration_private_file_required")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            actual = os.fstat(fd)
            if (actual.st_dev, actual.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError("fingpt_configuration_changed")
            raw = os.read(fd, 16385)
            if len(raw) > 16384:
                raise ValueError("fingpt_configuration_too_large")
            value = json.loads(raw)
        finally:
            os.close(fd)
        return cls(value["origin"], value["client_secret"], value.get("cookie_isolated", False))

    @property
    def callback(self):
        return self.origin + "/api/v1/auth/oidc/callback"


def diagnostic(root):
    try:
        config = FinGPTConfig.configured(root)
        return {
            "enabled": config is not None,
            "status": "configured" if config else "disabled",
            "authentication": "native_oidc_userinfo",
            "runtime_verification": "NOT_RUN",
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {"enabled": None, "status": "invalid", "runtime_verification": "NOT_RUN"}
