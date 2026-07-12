"""系统配置 API 的进程内 CSRF 防护。"""

import secrets
from typing import Annotated

from fastapi import Header, HTTPException

CONFIGURATION_CSRF_META_PLACEHOLDER = "__ALPHAFOUNDRY_CONFIG_TOKEN__"
CONFIGURATION_CSRF_TOKEN = secrets.token_urlsafe(32)


def require_configuration_csrf_token(
    submitted_token: Annotated[str | None, Header(alias="X-AlphaFoundry-Config-Token")] = None,
) -> None:
    """以常量时间比较配置页面提交的进程级 CSRF token。"""
    if not secrets.compare_digest(submitted_token or "", CONFIGURATION_CSRF_TOKEN):
        raise HTTPException(status_code=403, detail="Forbidden")
