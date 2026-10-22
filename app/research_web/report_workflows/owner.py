"""Read-only authorization of the attached administrator for weekly production."""

from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from uuid import UUID

from core.observability import get_logger

from ..multiuser.resident_binding import read_json
from ..multiuser.runtime import RuntimeErrorSafe
from .models import WorkflowError

log = get_logger(__name__)


def resolve_primary_owner(service, expected_owner_id: str | None = None) -> dict:
    """Never initialize a database, accept a browser role, or reuse cached roles."""
    try:
        authorizer = getattr(service, "report_owner_authorizer", None)
        if callable(authorizer):
            user = authorizer()
        else:
            data_root = Path(service.store.root)
            server = Path(
                getattr(service, "report_primary_owner_root", data_root.parent / "server")
            )
            if any(path.is_symlink() for path in (data_root, server)):
                raise ValueError("owner_path_invalid")
            binding = read_json(server / "resident.json")["binding"]
            owner_id = str(UUID(binding["primary_user_id"]))
            identity = data_root.stat()
            if Path(binding["home"]).resolve() / "research-web" != data_root.resolve() or binding[
                "data_identity"
            ] != [identity.st_dev, identity.st_ino]:
                raise ValueError("owner_binding_changed")
            database = server / "accounts.sqlite3"
            descriptor = os.open(database, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                before = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or (hasattr(os, "getuid") and before.st_uid != os.getuid())
                    or (os.name != "nt" and before.st_mode & 0o077)
                ):
                    raise ValueError("owner_database_invalid")
                with closing(
                    sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)
                ) as db:
                    db.execute("PRAGMA query_only=ON")
                    row = db.execute(
                        "SELECT id, role, enabled FROM accounts WHERE id = ?", (owner_id,)
                    ).fetchone()
                after = database.stat(follow_symlinks=False)
                if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                    raise ValueError("owner_database_changed")
            finally:
                os.close(descriptor)
            user = {"id": row[0], "role": row[1], "enabled": bool(row[2])} if row else None
        if (
            not isinstance(user, dict)
            or user.get("role") != "admin"
            or user.get("enabled") is not True
            or not user.get("id")
            or (expected_owner_id is not None and user["id"] != expected_owner_id)
        ):
            raise ValueError("owner_not_authorized")
        return {"id": user["id"], "role": "admin"}
    except (OSError, sqlite3.Error, RuntimeErrorSafe, ValueError, KeyError, TypeError) as exc:
        log.warning("report_weekly_owner_denied", error_type=type(exc).__name__)
        raise WorkflowError(
            "无法核验当前绑定的主管理员，周报生产已阻断", "weekly_owner_unavailable", 409
        ) from None
